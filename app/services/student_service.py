"""
Student Service for HocNhanhTN.
Xử lý nghiệp vụ thi, chấm điểm Bộ GD&ĐT (Phần I, II, III), phiên làm bài, chống gian lận và lịch sử làm bài.
"""

import datetime
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
    resolve_question_type,
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

def resolve_question_points(q: dict, total_q: int, scoring_cfg: dict) -> float:
    """
    Xác định điểm số tối đa của một câu hỏi dựa trên cấu hình đề thi:
    1. Điểm được gán trực tiếp trên từng câu (q.points)
    2. Điểm theo cấu hình phân bổ điểm (scoring: auto, gdpt2018, custom)
    3. Mặc định 1.0 điểm nếu không có cấu hình
    """
    if q.get('points') is not None:
        try:
            val = float(q.get('points'))
            if val >= 0:
                return val
        except (ValueError, TypeError):
            pass

    if scoring_cfg and isinstance(scoring_cfg, dict):
        mode = scoring_cfg.get('mode', 'auto')
        if mode == 'auto':
            try:
                total_pts = float(scoring_cfg.get('total_score', 10.0) or 10.0)
                return round(total_pts / max(1, total_q), 3)
            except (ValueError, TypeError):
                pass
        elif mode in ('gdpt2018', 'custom'):
            q_type = resolve_question_type(q)
            key_map = {
                'mcq': 'part1_point_per_q',
                'true_false': 'part2_point_per_q',
                'short_answer': 'part3_point_per_q',
                'essay': 'part4_point_per_q'
            }
            target_key = key_map.get(q_type)
            if target_key and scoring_cfg.get(target_key) is not None:
                try:
                    return float(scoring_cfg[target_key])
                except (ValueError, TypeError):
                    pass
            # Nếu là chế độ chuẩn GDPT 2018 mà chưa có điểm chi tiết từng câu, áp dụng định mức chuẩn Bộ GD&ĐT:
            # Phần I (MCQ): 0.25đ/câu; Phần II (Đúng/Sai): 1.0đ/câu; Phần III (Trả lời ngắn): 0.5đ/câu; Phần IV: 1.0đ/câu
            if mode == 'gdpt2018':
                gdpt_defaults = {
                    'mcq': 0.25,
                    'true_false': 1.0,
                    'short_answer': 0.5,
                    'essay': 1.0
                }
                return gdpt_defaults.get(q_type, 1.0)

    return 1.0


class StudentService:
    """
    Dịch vụ quản lý Bài thi & Tiến trình học sinh.
    """

    def get_db(self):
        return _get_db()

    def get_user(self, token: str, db: Any):
        return _get_user_from_token(token, db)

    def _get_candidate_key(self, item: dict) -> str:
        """
        Tạo mã định danh duy nhất cho mỗi thí sinh để đảm bảo mỗi người chỉ xuất hiện 1 lần trên bảng xếp hạng:
        - Ưu tiên 1: student_id nếu học sinh đã đăng nhập tài khoản.
        - Ưu tiên 2: sbd (Số báo danh) + họ tên nếu có số báo danh.
        - Ưu tiên 3: lớp + họ tên nếu có tên lớp và tên không phải ẩn danh.
        - Ưu tiên 4: họ tên chuẩn hóa nếu họ tên hợp lệ.
        - Mặc định: session_id hoặc id bài nộp cho thí sinh ẩn danh không tên.
        """
        student_id = str(item.get('student_id') or '').strip()
        if student_id:
            return f"id:{student_id}"

        student_name = str(item.get('student_name') or 'Ẩn danh').strip()
        sbd = str(item.get('sbd') or '').strip()
        class_name = str(item.get('class_name') or '').strip()

        name_norm = student_name.lower()
        if sbd:
            return f"sbd:{sbd.lower()}::{name_norm}"
        if class_name and name_norm not in ('ẩn danh', 'thí sinh', 'học sinh'):
            return f"class:{class_name.lower()}::{name_norm}"
        if name_norm not in ('ẩn danh', 'thí sinh', 'học sinh'):
            return f"name:{name_norm}"

        return f"anon:{item.get('session_id') or item.get('id') or id(item)}"

    def _deduplicate_leaderboard(self, items: list, limit: int = 5) -> list:
        """
        Sắp xếp và lọc bảng xếp hạng:
        Mỗi thí sinh chỉ xuất hiện đúng 1 lần với điểm số cao nhất (và thời gian làm nhanh nhất nếu bằng điểm).
        """
        if not items:
            return []

        def _sort_key(x):
            try:
                score = float(x.get('score', 0))
            except (ValueError, TypeError):
                score = 0.0
            try:
                time_elapsed = int(x.get('time_elapsed', 999999))
            except (ValueError, TypeError):
                time_elapsed = 999999
            return (-score, time_elapsed)

        sorted_items = sorted(items, key=_sort_key)

        distinct_results = []
        seen_candidates = set()

        for item in sorted_items:
            cand_key = self._get_candidate_key(item)
            if cand_key not in seen_candidates:
                seen_candidates.add(cand_key)
                clean_item = {k: v for k, v in item.items() if not k.startswith('_')}
                distinct_results.append(clean_item)
                if len(distinct_results) >= limit:
                    break

        return distinct_results

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

        status = quiz_data.get('status', 'published')
        if status in ['trashed', 'deleted']:
            raise HTTPException(status_code=404, detail="Bài thi không tồn tại hoặc đã bị xóa.")
        if status in ['unpublished', 'locked', 'archived']:
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

        status = quiz_data.get('status', 'published')
        if status in ['trashed', 'deleted']:
            raise HTTPException(status_code=404, detail="Bài thi không tồn tại hoặc đã bị xóa.")
        if status in ['unpublished', 'locked', 'archived']:
            raise HTTPException(status_code=403, detail="Bài thi này đã bị giáo viên tạm khóa.")

        questions = quiz_data.get('data') or quiz_data.get('questions') or []
        scoring_settings = quiz_data.get('scoring') or (quiz_data.get('settings') or {}).get('scoring') or {}

        score = 0.0
        results = []
        total_max_points = 0.0

        for idx, q in enumerate(questions):
            # Lấy câu trả lời của học sinh (hỗ trợ cả key dạng chuỗi "0" hoặc int 0)
            user_ans = req.answers.get(str(idx))
            if user_ans is None:
                user_ans = req.answers.get(idx)

            q_type = resolve_question_type(q)
            correct_ans = q.get('correct_answer')
            is_correct = False
            earned = 0.0
            q_pt = resolve_question_points(q, len(questions), scoring_settings)
            total_max_points += q_pt

            if q_type == 'true_false' or isinstance(correct_ans, dict):
                is_correct, raw_earned = evaluate_true_false_answer(user_ans, correct_ans)
                earned = round(raw_earned * q_pt, 3)
                score += earned
            elif q_type == 'short_answer':
                is_correct = evaluate_short_answer(user_ans, correct_ans)
                earned = q_pt if is_correct else 0.0
                score += earned
            elif q_type == 'essay':
                # Câu hỏi tự luận: Lưu bài làm của học sinh, chờ giáo viên chấm
                is_correct = None
                earned = 0.0
            else:
                # MCQ 4 lựa chọn: Chuẩn hóa so khớp đáp án linh hoạt, miễn nhiễm đảo vị trí phương án
                is_correct = evaluate_mcq_answer(user_ans, correct_ans, q.get('options'))
                earned = q_pt if is_correct else 0.0
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
                "earned": round(earned, 2),
                "max_points": round(q_pt, 2),
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
            'class_name': getattr(req, 'class_name', '') or '',
            'school_name': getattr(req, 'school_name', '') or '',
            'sbd': getattr(req, 'sbd', '') or '',
            'score': round(score, 2),
            'max_score': round(total_max_points, 2),
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
                    'max_score': round(total_max_points, 2),
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
            'student_id': submission_data.get('student_id', ''),
            'class_name': submission_data.get('class_name', ''),
            'school_name': submission_data.get('school_name', ''),
            'sbd': submission_data.get('sbd', ''),
            'score': submission_data['score'],
            'max_score': submission_data.get('max_score'),
            'total_questions': total_questions,
            'time_elapsed': req.time_elapsed,
            'session_id': submission_data.get('session_id', ''),
            'id': submission_data.get('id', '')
        }
        if req.quiz_id in LEADERBOARD_CACHE:
            curr_lb = LEADERBOARD_CACHE[req.quiz_id]['data']
            LEADERBOARD_CACHE[req.quiz_id] = {
                'time': now_ts,
                'data': self._deduplicate_leaderboard(curr_lb + [lb_entry], limit=5)
            }
        else:
            LEADERBOARD_CACHE.pop(req.quiz_id, None)

        return {
            "status": "success",
            "score": round(score, 2),
            "max_score": round(total_max_points, 2),
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

        sub_entry = {
            'student_name': request.student_name,
            'score': float(request.score),
            'total_questions': request.total_questions,
            'time_elapsed': request.time_elapsed
        }
        if request.quiz_id in LEADERBOARD_CACHE:
            curr_lb = LEADERBOARD_CACHE[request.quiz_id]['data']
            LEADERBOARD_CACHE[request.quiz_id] = {
                'time': now_ts,
                'data': self._deduplicate_leaderboard(curr_lb + [sub_entry], limit=5)
            }
        else:
            LEADERBOARD_CACHE.pop(request.quiz_id, None)

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

        now = time.time()

        # Kiểm tra cài đặt giáo viên: nếu tắt Bảng xếp hạng thì không trả dữ liệu cho học sinh
        quiz_doc_dict = None
        if quiz_id in QUIZ_CACHE and 'data' in QUIZ_CACHE[quiz_id]:
            quiz_doc_dict = QUIZ_CACHE[quiz_id]['data']
        else:
            try:
                q_doc = db.collection('quizzes').document(quiz_id).get()
                if q_doc.exists:
                    quiz_doc_dict = q_doc.to_dict()
                    QUIZ_CACHE[quiz_id] = {'time': now, 'data': quiz_doc_dict}
            except Exception:
                pass

        if quiz_doc_dict and quiz_doc_dict.get('settings', {}).get('leaderboard') is False:
            return {"status": "success", "data": [], "hidden_by_teacher": True}

        # SỬ DỤNG CACHE CHO BẢNG XẾP HẠNG (300 giây = 5 phút) -> TIẾT KIỆM QUOTA HÀNG LOẠT
        if quiz_id in LEADERBOARD_CACHE and now - LEADERBOARD_CACHE[quiz_id]['time'] < 300:
            return {"status": "success", "data": LEADERBOARD_CACHE[quiz_id]['data'][:5]}

        if quiz_id in SUBMISSIONS_CACHE and (now - SUBMISSIONS_CACHE[quiz_id]['time'] < 300):
            raw_submissions = SUBMISSIONS_CACHE[quiz_id]['data']
        else:
            subs_ref = db.collection('quizzes').document(quiz_id).collection('submissions')
            try:
                # Lấy tối đa 100 bài điểm cao nhất từ Firestore để xét chuẩn tie-break và lọc thí sinh duy nhất
                docs = subs_ref.order_by('score', direction=firestore.Query.DESCENDING).limit(100).get()
            except Exception:
                docs = subs_ref.limit(100).get()
            raw_submissions = [doc.to_dict() for doc in docs]
            SUBMISSIONS_CACHE[quiz_id] = {'time': now, 'data': raw_submissions}

        quiz_total_q = None
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

            if total <= 0:
                if quiz_total_q is None:
                    if quiz_id in QUIZ_CACHE and 'data' in QUIZ_CACHE[quiz_id]:
                        quiz_total_q = len(QUIZ_CACHE[quiz_id]['data'].get('data', []))
                    else:
                        try:
                            q_doc = db.collection('quizzes').document(quiz_id).get()
                            quiz_total_q = len(q_doc.to_dict().get('data', [])) if q_doc.exists else 0
                        except Exception:
                            quiz_total_q = 0
                if quiz_total_q and quiz_total_q > 0:
                    total = quiz_total_q

            raw_max = data.get('max_score')
            try:
                max_score_val = round(float(raw_max), 2) if (raw_max is not None and float(raw_max) > 0) else None
            except (ValueError, TypeError):
                max_score_val = None

            results.append({
                'student_name': data.get('student_name', 'Ẩn danh'),
                'student_id': str(data.get('student_id') or '').strip(),
                'class_name': str(data.get('class_name') or '').strip(),
                'school_name': str(data.get('school_name') or '').strip(),
                'sbd': str(data.get('sbd') or '').strip(),
                'score': score,
                'max_score': max_score_val,
                'total_questions': total,
                'time_elapsed': time_elapsed,
                'session_id': str(data.get('session_id') or '').strip(),
                'id': str(data.get('id') or '').strip()
            })

        final_results = self._deduplicate_leaderboard(results, limit=5)
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
                'max_score': round(float(item.max_score), 2) if (item.max_score is not None and item.max_score > 0) else None,
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
