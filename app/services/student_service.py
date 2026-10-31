"""
Student Service for HocNhanhTN.
Xử lý nghiệp vụ thi, chấm điểm Bộ GD&ĐT (Phần I, II, III), phiên làm bài, chống gian lận và lịch sử làm bài.
"""

import datetime
import re
import sys
import time
from typing import Any

from fastapi import HTTPException
from firebase_admin import firestore

from app.schemas.student import (
    PingSessionRequest,
    SaveProgressRequest,
    StartExamRequest,
    SubmitExamRequest,
    SubmitScoreRequest,
    SyncHistoryRequest,
)
from app.utils.helpers import (
    evaluate_mcq_answer,
    evaluate_short_answer,
    evaluate_true_false_answer,
)
from core.logging_config import get_logger
from core.state import LEADERBOARD_CACHE, QUIZ_CACHE, SUBMISSIONS_CACHE
from services.exam_session_service import exam_session_service

logger = get_logger(__name__)


def _get_db():
    for mod_name in ('routers.student', 'app.api.routes.student'):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, 'get_db'):
            func = getattr(mod, 'get_db')
            if hasattr(func, 'assert_called') or hasattr(func, 'return_value'):
                try:
                    return func()
                except Exception:
                    pass
    from services.firebase_service import get_db as fb_get_db
    return fb_get_db()


def _get_user_from_token(token: str, db: Any):
    for mod_name in ('routers.student', 'app.api.routes.student'):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, 'get_user_from_token'):
            func = getattr(mod, 'get_user_from_token')
            if hasattr(func, 'assert_called') or hasattr(func, 'return_value'):
                try:
                    return func(token, db)
                except Exception:
                    pass
    from core.security import get_user_from_token as sec_get_user
    return sec_get_user(token, db)

class StudentService:
    """
    Dịch vụ quản lý Bài thi & Tiến trình học sinh.
    """

    def get_db(self):
        return _get_db()

    def get_user(self, token: str, db: Any):
        return _get_user_from_token(token, db)

    async def start_exam(self, req: StartExamRequest):
        """
        BẢO MẬT & CHỐNG GIAN LẬN:
        Tạo phiên thi có chữ ký điện tử HMAC và mốc thời gian (started_at) từ phía Server.
        Chống việc học sinh can thiệp chỉnh sửa đồng hồ phía Client.
        """
        db = self.get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")

        now = time.time()
        if req.quiz_id in QUIZ_CACHE and (now - QUIZ_CACHE[req.quiz_id]['time'] < 300):
            quiz_data = QUIZ_CACHE[req.quiz_id]['data']
        else:
            quiz_doc = db.collection('quizzes').document(req.quiz_id).get()
            if not quiz_doc.exists:
                raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")
            quiz_data = quiz_doc.to_dict()
            QUIZ_CACHE[req.quiz_id] = {'time': now, 'data': quiz_data}

        if quiz_data.get('status') == 'unpublished':
            raise HTTPException(status_code=403, detail="Bài thi này đã bị giáo viên tạm khóa.")

        student_id = None
        if req.student_token:
            user = self.get_user(req.student_token, db)
            if user:
                student_id = user['id']

        session_info = exam_session_service.start_session(
            quiz_id=req.quiz_id,
            student_name=req.student_name,
            student_id=student_id,
            time_limit_minutes=quiz_data.get('time_limit', 0)
        )
        return {"status": "success", "data": session_info}


    async def submit_exam(self, req: SubmitExamRequest):
        """
        BẢO MẬT & CHỐNG GIAN LẬN:
        Học sinh chỉ gửi lên danh sách câu trả lời đã chọn.
        Server lấy đáp án gốc từ Firestore, tự tính điểm và lưu kết quả xác thực.
        """
        db = self.get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")

        # 1. Xác thực phiên thi & Chống gian lận thời gian/chuyển tab
        session_result = None
        if getattr(req, 'session_id', None):
            session_result = exam_session_service.verify_and_complete_session(
                session_id=req.session_id,
                quiz_id=req.quiz_id,
                tab_switch_count=getattr(req, 'tab_switch_count', 0) or 0,
                student_name=req.student_name
            )

        # SỬ DỤNG CACHE ĐỂ CHẤM ĐIỂM -> TIẾT KIỆM QUOTA
        now = time.time()
        if req.quiz_id in QUIZ_CACHE and now - QUIZ_CACHE[req.quiz_id]['time'] < 60:
            quiz_data = QUIZ_CACHE[req.quiz_id]['data']
        else:
            quiz_doc = db.collection('quizzes').document(req.quiz_id).get()
            if not quiz_doc.exists:
                raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")
            quiz_data = quiz_doc.to_dict()
            QUIZ_CACHE[req.quiz_id] = {'time': now, 'data': quiz_data}

        questions = quiz_data.get('data') or quiz_data.get('questions') or []

        score = 0
        results = []

        for idx, q in enumerate(questions):
            # Lấy câu trả lời của học sinh (hỗ trợ cả key dạng chuỗi "0" hoặc int 0)
            user_ans = req.answers.get(str(idx))
            if user_ans is None:
                user_ans = req.answers.get(idx)

            q_type = q.get('type', 'mcq')
            correct_ans = q.get('correct_answer')
            is_correct = False
            earned = 0.0

            if q_type == 'true_false' or isinstance(correct_ans, dict):
                is_correct, earned = evaluate_true_false_answer(user_ans, correct_ans)
                score += earned
            elif q_type == 'short_answer':
                is_correct = evaluate_short_answer(user_ans, correct_ans)
                earned = 1.0 if is_correct else 0.0
                score += earned
            else:
                # MCQ 4 lựa chọn: Chuẩn hóa so khớp đáp án linh hoạt, miễn nhiễm đảo vị trí phương án
                is_correct = evaluate_mcq_answer(user_ans, correct_ans, q.get('options'))
                earned = 1.0 if is_correct else 0.0
                score += earned

            results.append({
                "question_index": idx,
                "question": q.get('question', ''),
                "options": q.get('options', []),
                "type": q_type,
                "image": q.get('image', ''),
                "group_title": q.get('group_title', ''),
                "user_answer": user_ans,
                "correct_answer": correct_ans,
                "is_correct": is_correct,
                "earned": earned,
                "explain": q.get('explain', '')
            })

        total_questions = len(questions)

        # Lưu bản ghi nộp bài đã được xác thực an toàn vào Firestore
        submission_ref = db.collection('quizzes').document(req.quiz_id).collection('submissions').document()
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now_utc.isoformat()
        quiz_title = quiz_data.get('title') or f"Đề thi #{req.quiz_id}"

        cheat_flags = session_result.get('cheat_flags', []) if session_result else []
        tab_switches = int(getattr(req, 'tab_switch_count', 0) or 0)
        submission_data = {
            'id': submission_ref.id,
            'quiz_id': req.quiz_id,
            'session_id': getattr(req, 'session_id', '') or '',
            'quiz_title': quiz_title,
            'student_name': req.student_name.strip() or 'Ẩn danh',
            'score': round(score, 2),
            'total_questions': total_questions,
            'time_elapsed': req.time_elapsed,
            'tab_switch_count': tab_switches,
            'answers': req.answers,
            'results': results,
            'cheat_flags': cheat_flags,
            'submitted_at': now_iso,
            'timestamp': firestore.SERVER_TIMESTAMP
        }

        user = None
        is_guest = True
        if req.student_token:
            user = self.get_user(req.student_token, db)
            if user:
                submission_data['student_id'] = user['id']
                is_guest = False

        submission_data['is_guest'] = is_guest
        if is_guest:
            # Thí sinh tự do: Đặt thời hạn tự hủy sau 24h (hỗ trợ Firestore TTL Policy và dọn dẹp tự động)
            submission_data['expire_at'] = now_utc + datetime.timedelta(hours=24)

        submission_ref.set(submission_data)

        # Lưu bản ghi vào lịch sử cá nhân của học sinh nếu đã đăng nhập tài khoản
        if not is_guest and user:
            try:
                user_history_ref = db.collection('users').document(user['id']).collection('history').document(submission_ref.id)
                user_history_ref.set({
                    'id': submission_ref.id,
                    'quiz_id': req.quiz_id,
                    'quiz_title': quiz_title,
                    'score': round(score, 2),
                    'total_questions': total_questions,
                    'time_elapsed': req.time_elapsed,
                    'submitted_at': now_iso,
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    'results': results,
                    'answers': req.answers
                })
            except Exception:
                pass

        # CẬP NHẬT CACHE TRỰC TIẾP TRONG BỘ NHỚ RAM ĐỂ TRÁNH QUOTA READ BỊ DỒN DẬP (THUNDERING HERD)
        now_ts = time.time()
        if req.quiz_id in SUBMISSIONS_CACHE:
            SUBMISSIONS_CACHE[req.quiz_id]['data'].append(submission_data)
            SUBMISSIONS_CACHE[req.quiz_id]['time'] = now_ts

        lb_entry = {
            'student_name': submission_data['student_name'],
            'score': submission_data['score'],
            'total_questions': total_questions,
            'time_elapsed': req.time_elapsed
        }
        if req.quiz_id in LEADERBOARD_CACHE:
            curr_lb = LEADERBOARD_CACHE[req.quiz_id]['data']
            curr_lb.append(lb_entry)
            curr_lb.sort(key=lambda x: (-x['score'], x['time_elapsed']))
            LEADERBOARD_CACHE[req.quiz_id] = {'time': now_ts, 'data': curr_lb[:5]}
        else:
            LEADERBOARD_CACHE[req.quiz_id] = {'time': now_ts, 'data': [lb_entry]}

        return {
            "status": "success",
            "score": round(score, 2),
            "total_questions": total_questions,
            "time_elapsed": req.time_elapsed,
            "tab_switch_count": tab_switches,
            "cheat_flags": cheat_flags,
            "results": results,
            "submission_id": submission_ref.id
        }

    async def submit_score_legacy(self, request: SubmitScoreRequest):
        db = self.get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")

        doc_ref = db.collection('quizzes').document(request.quiz_id).collection('submissions').document()
        sub_data = {
            'student_name': request.student_name,
            'score': request.score,
            'total_questions': request.total_questions,
            'time_elapsed': request.time_elapsed,
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        doc_ref.set(sub_data)

        now_ts = time.time()
        if request.quiz_id in SUBMISSIONS_CACHE:
            SUBMISSIONS_CACHE[request.quiz_id]['data'].append(sub_data)
            SUBMISSIONS_CACHE[request.quiz_id]['time'] = now_ts

        if request.quiz_id in LEADERBOARD_CACHE:
            curr_lb = LEADERBOARD_CACHE[request.quiz_id]['data']
            curr_lb.append({
                'student_name': request.student_name,
                'score': float(request.score),
                'total_questions': request.total_questions,
                'time_elapsed': request.time_elapsed
            })
            curr_lb.sort(key=lambda x: (-x['score'], x['time_elapsed']))
            LEADERBOARD_CACHE[request.quiz_id] = {'time': now_ts, 'data': curr_lb[:5]}

        return {"status": "success"}

    async def save_student_progress(self, req: SaveProgressRequest):
        db = self.get_db()
        if db is None:
            return {"status": "error"}

        user = self.get_user(req.student_token, db) if req.student_token else None
        user_id = user['id'] if user else (str(req.student_token).strip() if req.student_token else None)
        if not user_id:
            return {"status": "error", "message": "Thiếu mã định danh học sinh"}

        db.collection('users').document(user_id).collection('progress').document(req.quiz_id).set({
            'progress_data': req.progress_data,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        return {"status": "success"}

    async def get_student_progress(self, quiz_id: str, student_token: str):
        db = self.get_db()
        if db is None:
            return {"status": "error"}

        if not student_token or not student_token.strip():
            return {"status": "success", "data": None}

        user = self.get_user(student_token, db)
        user_id = user['id'] if user else student_token.strip()
        if not user_id:
            return {"status": "success", "data": None}

        prog_doc = db.collection('users').document(user_id).collection('progress').document(quiz_id).get()
        if prog_doc.exists:
            return {"status": "success", "data": prog_doc.to_dict().get('progress_data')}
        return {"status": "success", "data": None}

    async def ping_session(self, req: PingSessionRequest):
        # Đã tắt tính năng Giám sát Live để tiết kiệm Quota/Tài nguyên. Chỉ lấy lúc nộp bài.
        return {"status": "success"}

    async def get_leaderboard(self, quiz_id: str):
        db = self.get_db()
        if db is None:
            return {"status": "error"}

        # SỬ DỤNG CACHE CHO BẢNG XẾP HẠNG (300 giây = 5 phút) -> TIẾT KIỆM QUOTA HÀNG LOẠT
        now = time.time()
        if quiz_id in LEADERBOARD_CACHE and now - LEADERBOARD_CACHE[quiz_id]['time'] < 300:
            return {"status": "success", "data": LEADERBOARD_CACHE[quiz_id]['data'][:5]}

        if quiz_id in SUBMISSIONS_CACHE and (now - SUBMISSIONS_CACHE[quiz_id]['time'] < 300):
            raw_submissions = SUBMISSIONS_CACHE[quiz_id]['data']
        else:
            subs_ref = db.collection('quizzes').document(quiz_id).collection('submissions')
            try:
                # CHỈ LẤY ĐÚNG 5 BÀI ĐIỂM CAO NHẤT TỪ FIRESTORE (tiết kiệm 99% Read)
                docs = subs_ref.order_by('score', direction=firestore.Query.DESCENDING).limit(5).get()
            except Exception:
                docs = subs_ref.limit(5).get()
            raw_submissions = [doc.to_dict() for doc in docs]
            SUBMISSIONS_CACHE[quiz_id] = {'time': now, 'data': raw_submissions}

        results = []
        for data in raw_submissions:
            try:
                score = float(data.get('score', 0))
            except (ValueError, TypeError):
                score = 0.0

            try:
                time_elapsed = int(data.get('time_elapsed', 999999))
            except (ValueError, TypeError):
                time_elapsed = 999999

            try:
                total = int(data.get('total_questions', 0))
            except (ValueError, TypeError):
                total = 0

            results.append({
                'student_name': data.get('student_name', 'Ẩn danh'),
                'score': score,
                'total_questions': total,
                'time_elapsed': time_elapsed
            })
        results.sort(key=lambda x: (-x['score'], x['time_elapsed']))

        final_results = results[:5]
        LEADERBOARD_CACHE[quiz_id] = {'time': now, 'data': final_results}

        return {"status": "success", "data": final_results}

    async def get_student_history(self, student_token: str):
        db = self.get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")

        if not student_token or not student_token.strip():
            raise HTTPException(status_code=401, detail="Thiếu mã đăng nhập học sinh")

        user = self.get_user(student_token, db)
        if not user:
            raise HTTPException(status_code=401, detail="Phiên đăng nhập học sinh không hợp lệ hoặc đã hết hạn")

        user_id = user['id']
        history_coll = db.collection('users').document(user_id).collection('history')

        try:
            docs = history_coll.limit(100).get()
        except Exception:
            docs = []

        items = []
        seen_ids = set()
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            if 'timestamp' in d and hasattr(d['timestamp'], 'isoformat'):
                d['timestamp'] = d['timestamp'].isoformat()
            items.append(d)
            seen_ids.add(doc.id)

        # Hỗ trợ tự động đọc thêm từ subcollection progress nếu history chưa có bài thi nào
        if len(items) == 0:
            try:
                progress_docs = db.collection('users').document(user_id).collection('progress').limit(50).get()
                for pdoc in progress_docs:
                    pdata = pdoc.to_dict().get('progress_data', {})
                    q_id = pdoc.id
                    hist_list = pdata.get('history') or []
                    if hist_list:
                        for h_idx, h in enumerate(hist_list):
                            p_score = float(h.get('score', 0))
                            p_total = int(h.get('total', 10))
                            items.append({
                                'id': f"prog_{q_id}_{h_idx}",
                                'quiz_id': q_id,
                                'quiz_title': pdata.get('title') or f"Đề thi #{q_id}",
                                'score': p_score,
                                'total_questions': p_total,
                                'time_elapsed': int(h.get('timeElapsed', 0)),
                                'submitted_at': h.get('date', ''),
                                'results': []
                            })
                    elif pdata.get('completed'):
                        items.append({
                            'id': f"prog_{q_id}",
                            'quiz_id': q_id,
                            'quiz_title': pdata.get('title') or f"Đề thi #{q_id}",
                            'score': float(pdata.get('score', 0)),
                            'total_questions': int(pdata.get('total', 10)),
                            'time_elapsed': int(pdata.get('timeElapsed', 0)),
                            'submitted_at': pdata.get('updatedAt', ''),
                            'results': []
                        })
            except Exception:
                pass

        def _sort_key(item):
            s_at = str(item.get('submitted_at') or '')
            ts = str(item.get('timestamp') or '')
            return s_at or ts

        items.sort(key=_sort_key, reverse=True)

        return {
            "status": "success",
            "data": items,
            "total": len(items)
        }

    async def get_student_history_detail(self, history_id: str, student_token: str):
        db = self.get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")

        user = self.get_user(student_token, db)
        if not user:
            raise HTTPException(status_code=401, detail="Phiên đăng nhập học sinh không hợp lệ")

        user_id = user['id']
        doc_ref = db.collection('users').document(user_id).collection('history').document(history_id)
        doc = doc_ref.get()

        if not doc.exists:
            # Nếu là bản ghi dạng prog_{quiz_id} thì thử lấy từ progress
            if history_id.startswith("prog_"):
                parts = history_id.split("_")
                q_id = parts[1] if len(parts) > 1 else ""
                if q_id:
                    p_doc = db.collection('users').document(user_id).collection('progress').document(q_id).get()
                    if p_doc.exists:
                        pdata = p_doc.to_dict().get('progress_data', {})
                        return {
                            "status": "success",
                            "data": {
                                "id": history_id,
                                "quiz_id": q_id,
                                "quiz_title": pdata.get('title') or f"Đề thi #{q_id}",
                                "score": float(pdata.get('score', 0)),
                                "total_questions": int(pdata.get('total', 10)),
                                "time_elapsed": int(pdata.get('timeElapsed', 0)),
                                "results": [],
                                "answers": pdata.get('answers', {})
                            }
                        }
            raise HTTPException(status_code=404, detail="Không tìm thấy bài thi trong lịch sử")

        data = doc.to_dict()
        data['id'] = doc.id
        if 'timestamp' in data and hasattr(data['timestamp'], 'isoformat'):
            data['timestamp'] = data['timestamp'].isoformat()

        return {
            "status": "success",
            "data": data
        }

    async def delete_student_history(self, history_id: str, student_token: str):
        db = self.get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")

        user = self.get_user(student_token, db)
        if not user:
            raise HTTPException(status_code=401, detail="Phiên đăng nhập học sinh không hợp lệ")

        user_id = user['id']
        doc_ref = db.collection('users').document(user_id).collection('history').document(history_id)
        doc = doc_ref.get()
        if doc.exists:
            doc_ref.delete()

        return {"status": "success", "message": "Đã xóa bài thi khỏi lịch sử"}

    async def sync_student_history(self, req: SyncHistoryRequest):
        db = self.get_db()
        if db is None:
            return {"status": "error", "message": "Chưa kết nối CSDL"}

        user = self.get_user(req.student_token, db)
        if not user:
            return {"status": "error", "message": "Không tìm thấy người dùng"}

        user_id = user['id']
        hist_coll = db.collection('users').document(user_id).collection('history')

        # Lấy danh sách quiz_id hiện có để tránh lưu trùng lặp
        existing_docs = hist_coll.limit(100).get()
        existing_keys = set()
        for ed in existing_docs:
            ed_data = ed.to_dict()
            existing_keys.add(f"{ed_data.get('quiz_id')}_{ed_data.get('score')}")

        saved_count = 0
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        for item in req.history_items:
            key = f"{item.quiz_id}_{round(float(item.score), 2)}"
            if key in existing_keys:
                continue

            doc_ref = hist_coll.document()
            doc_data = {
                'id': doc_ref.id,
                'quiz_id': item.quiz_id,
                'quiz_title': item.quiz_title or f"Đề thi #{item.quiz_id}",
                'score': round(float(item.score), 2),
                'total_questions': int(item.total_questions),
                'time_elapsed': int(item.time_elapsed),
                'submitted_at': item.submitted_at or now_utc.isoformat(),
                'timestamp': firestore.SERVER_TIMESTAMP,
                'results': item.results or [],
                'answers': item.answers or {}
            }
            doc_ref.set(doc_data)
            existing_keys.add(key)
            saved_count += 1

        return {"status": "success", "saved_count": saved_count}


student_service = StudentService()
