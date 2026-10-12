import time
import datetime
from typing import Optional, Dict, Any, List
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from firebase_admin import firestore, db as realtime_db
from services.firebase_service import get_db
from core.security import get_user_from_token
from core.state import QUIZ_CACHE, LEADERBOARD_CACHE, SUBMISSIONS_CACHE

router = APIRouter(prefix="/api", tags=["Student Exam & Progress"])

class SubmitExamRequest(BaseModel):
    quiz_id: str
    student_name: str
    student_token: Optional[str] = None
    answers: Dict[str, Any] = {}
    time_elapsed: int = 0

class SyncHistoryItem(BaseModel):
    quiz_id: str
    quiz_title: Optional[str] = "Đề thi trắc nghiệm"
    score: float
    total_questions: int
    time_elapsed: int
    submitted_at: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    answers: Optional[Dict[str, Any]] = None

class SyncHistoryRequest(BaseModel):
    student_token: str
    history_items: List[SyncHistoryItem]

class SubmitScoreRequest(BaseModel):
    quiz_id: str
    student_name: str
    score: int
    total_questions: int
    time_elapsed: int

class SaveProgressRequest(BaseModel):
    student_token: str
    quiz_id: str
    progress_data: dict

class PingSessionRequest(BaseModel):
    quiz_id: str
    session_id: str
    student_name: str
    answers_count: int
    time_remaining: int
    completed: bool

@router.post("/student/submit_exam", summary="Chấm điểm bài thi an toàn phía Backend")
async def submit_exam(req: SubmitExamRequest):
    """
    BẢO MẬT & CHỐNG GIAN LẬN:
    Học sinh chỉ gửi lên danh sách câu trả lời đã chọn.
    Server lấy đáp án gốc từ Firestore, tự tính điểm và lưu kết quả xác thực.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
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
        
    questions = quiz_data.get('data', [])
    
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
            # Quy chuẩn chấm trắc nghiệm Đúng/Sai của Bộ GD&ĐT:
            # 1 ý đúng = 0.1đ | 2 ý đúng = 0.25đ | 3 ý đúng = 0.5đ | 4 ý đúng = 1.0đ
            if isinstance(user_ans, dict) and isinstance(correct_ans, dict):
                def norm_tf(d):
                    res = {}
                    for k, v in d.items():
                        lk = str(k).lower().strip()
                        if isinstance(v, bool):
                            res[lk] = v
                        elif isinstance(v, str):
                            res[lk] = v.strip().lower() in ['true', 't', 'đúng', 'dung', 'd', '1']
                        elif isinstance(v, (int, float)):
                            res[lk] = bool(v)
                        else:
                            res[lk] = bool(v)
                    return res

                u_norm = norm_tf(user_ans)
                c_norm = norm_tf(correct_ans)
                total_tf = len(c_norm)
                if total_tf == 0:
                    earned = 0.0
                    is_correct = False
                else:
                    matches = sum(1 for k in c_norm if k in u_norm and u_norm[k] == c_norm[k])
                    # Thang điểm chuẩn Bộ GD&ĐT cho câu Đúng/Sai 4 ý:
                    # 1 ý đúng = 0.1đ | 2 ý đúng = 0.25đ | 3 ý đúng = 0.5đ | 4 ý đúng = 1.0đ
                    tf_scale = {0: 0.0, 1: 0.1, 2: 0.25, 3: 0.5, 4: 1.0}
                    earned = tf_scale.get(matches, float(matches) / float(total_tf))
                    is_correct = (matches == total_tf)
            score += earned
        elif q_type == 'short_answer':
            u_clean = str(user_ans or '').strip().lower().replace(',', '.').replace(' ', '')
            c_clean = str(correct_ans or '').strip().lower().replace(',', '.').replace(' ', '')
            is_correct = bool(u_clean and u_clean == c_clean)
            earned = 1.0 if is_correct else 0.0
            score += earned
        else:
            # MCQ 4 lựa chọn: Chuẩn hóa so khớp đáp án linh hoạt
            is_correct = False
            if user_ans is not None and correct_ans is not None:
                u_str = str(user_ans).strip()
                c_str = str(correct_ans).strip()
                
                # Sửa lỗi: Nếu correct_answer là index (VD: "0", "1") do AI sinh ra
                if c_str.isdigit() and q.get('options') and isinstance(q.get('options'), list):
                    idx = int(c_str)
                    if 0 <= idx < len(q['options']):
                        c_str = str(q['options'][idx]).strip()

                if u_str.upper() == c_str.upper():
                    is_correct = True
                else:
                    # Ràng buộc chặt chẽ: Chỉ lấy A, B, C, D nếu nó đứng đầu và theo sau là dấu câu hoặc khoảng trắng
                    re_prefix = r'^([A-Da-d])(?:[\.\:\)]\s*|\s+|$)'
                    u_m = re.match(re_prefix, u_str)
                    c_m = re.match(re_prefix, c_str)
                    u_char = u_m.group(1).upper() if u_m else None
                    c_char = c_m.group(1).upper() if c_m else None
                    
                    u_clean = re.sub(r'^[A-Da-d][\.\:\)]\s*', '', u_str).strip().lower()
                    c_clean = re.sub(r'^[A-Da-d][\.\:\)]\s*', '', c_str).strip().lower()
                    
                    opt_clean = c_clean
                    if not opt_clean and c_char and q.get('options') and isinstance(q.get('options'), list):
                        idx_opt = ord(c_char) - ord('A')
                        if 0 <= idx_opt < len(q['options']):
                            opt_str = str(q['options'][idx_opt]).strip()
                            opt_clean = re.sub(r'^[A-Da-d][\.\:\)]\s*', '', opt_str).strip().lower()
                            if u_str.upper() == opt_str.upper():
                                is_correct = True

                    if not is_correct:
                        if u_clean and opt_clean:
                            # Ưu tiên so khớp nội dung: Giải quyết lỗi đảo vị trí đáp án nhưng bị trùng chữ cái A,B,C,D
                            if u_clean == opt_clean:
                                is_correct = True
                        else:
                            # Fallback: Nếu không có text, mới so khớp bằng chữ cái đại diện
                            if u_char and c_char and u_char == c_char:
                                is_correct = True
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

    submission_data = {
        'id': submission_ref.id,
        'quiz_id': req.quiz_id,
        'quiz_title': quiz_title,
        'student_name': req.student_name.strip() or 'Ẩn danh',
        'score': round(score, 2),
        'total_questions': total_questions,
        'time_elapsed': req.time_elapsed,
        'answers': req.answers,
        'results': results,
        'submitted_at': now_iso,
        'timestamp': firestore.SERVER_TIMESTAMP
    }
    
    user = None
    is_guest = True
    if req.student_token:
        user = get_user_from_token(req.student_token, db)
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
        "results": results,
        "submission_id": submission_ref.id
    }

@router.post("/submit_score", summary="Lưu điểm của học sinh (Tương thích ngược)")
async def submit_score_legacy(request: SubmitScoreRequest):
    db = get_db()
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

@router.post("/student/save_progress", summary="Lưu tiến trình làm bài của học sinh lên Cloud")
async def save_student_progress(req: SaveProgressRequest):
    db = get_db()
    if db is None:
        return {"status": "error"}
        
    user = get_user_from_token(req.student_token, db) if req.student_token else None
    user_id = user['id'] if user else (str(req.student_token).strip() if req.student_token else None)
    if not user_id:
        return {"status": "error", "message": "Thiếu mã định danh học sinh"}
    
    db.collection('users').document(user_id).collection('progress').document(req.quiz_id).set({
        'progress_data': req.progress_data,
        'updated_at': firestore.SERVER_TIMESTAMP
    })
    return {"status": "success"}

@router.get("/student/get_progress/{quiz_id}", summary="Lấy tiến trình làm bài từ Cloud")
async def get_student_progress(quiz_id: str, student_token: str):
    db = get_db()
    if db is None:
        return {"status": "error"}
        
    if not student_token or not student_token.strip():
        return {"status": "success", "data": None}
        
    user = get_user_from_token(student_token, db)
    user_id = user['id'] if user else student_token.strip()
    if not user_id:
        return {"status": "success", "data": None}
    
    prog_doc = db.collection('users').document(user_id).collection('progress').document(quiz_id).get()
    if prog_doc.exists:
        return {"status": "success", "data": prog_doc.to_dict().get('progress_data')}
    return {"status": "success", "data": None}

@router.post("/monitor/ping", summary="Nhận tín hiệu Ping từ thiết bị học sinh")
async def ping_session(req: PingSessionRequest):
    # Đã tắt tính năng Giám sát Live để tiết kiệm Quota/Tài nguyên. Chỉ lấy lúc nộp bài.
    return {"status": "success"}

@router.get("/leaderboard/{quiz_id}", summary="Lấy bảng xếp hạng top 5 thành tích cao nhất")
async def get_leaderboard(quiz_id: str):
    db = get_db()
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

@router.get("/student/history", summary="Lấy danh sách lịch sử làm bài và điểm số của học sinh")
async def get_student_history(student_token: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
    
    if not student_token or not student_token.strip():
        raise HTTPException(status_code=401, detail="Thiếu mã đăng nhập học sinh")
        
    user = get_user_from_token(student_token, db)
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

@router.get("/student/history/{history_id}", summary="Lấy chi tiết một bài thi đã nộp trong lịch sử")
async def get_student_history_detail(history_id: str, student_token: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
    user = get_user_from_token(student_token, db)
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

@router.delete("/student/history/{history_id}", summary="Xóa bài thi khỏi lịch sử học sinh")
async def delete_student_history(history_id: str, student_token: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
    user = get_user_from_token(student_token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập học sinh không hợp lệ")
        
    user_id = user['id']
    doc_ref = db.collection('users').document(user_id).collection('history').document(history_id)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.delete()
        
    return {"status": "success", "message": "Đã xóa bài thi khỏi lịch sử"}

@router.post("/student/sync_history", summary="Đồng bộ lịch sử từ bộ nhớ máy lên tài khoản học sinh")
async def sync_student_history(req: SyncHistoryRequest):
    db = get_db()
    if db is None:
        return {"status": "error", "message": "Chưa kết nối CSDL"}
        
    user = get_user_from_token(req.student_token, db)
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
