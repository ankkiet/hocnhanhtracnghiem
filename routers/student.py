from typing import Optional, Dict, Any
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from firebase_admin import firestore
from services.firebase_service import get_db
from core.security import get_user_from_token

router = APIRouter(prefix="/api", tags=["Student Exam & Progress"])

class SubmitExamRequest(BaseModel):
    quiz_id: str
    student_name: str
    student_token: Optional[str] = None
    answers: Dict[str, Any] = {}
    time_elapsed: int = 0

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
        
    quiz_doc = db.collection('quizzes').document(req.quiz_id).get()
    if not quiz_doc.exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")
        
    quiz_data = quiz_doc.to_dict()
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
            "user_answer": user_ans,
            "correct_answer": correct_ans,
            "is_correct": is_correct,
            "earned": earned,
            "explain": q.get('explain', '')
        })
        
    total_questions = len(questions)
    
    # Lưu bản ghi nộp bài đã được xác thực an toàn vào Firestore
    submission_ref = db.collection('quizzes').document(req.quiz_id).collection('submissions').document()
    submission_data = {
        'student_name': req.student_name.strip() or 'Ẩn danh',
        'score': round(score, 2),
        'total_questions': total_questions,
        'time_elapsed': req.time_elapsed,
        'answers': req.answers,
        'timestamp': firestore.SERVER_TIMESTAMP
    }
    
    if req.student_token:
        user = get_user_from_token(req.student_token, db)
        if user:
            submission_data['student_id'] = user['id']
            
    submission_ref.set(submission_data)
    
    return {
        "status": "success",
        "score": round(score, 2),
        "total_questions": total_questions,
        "time_elapsed": req.time_elapsed,
        "results": results
    }

@router.post("/submit_score", summary="Lưu điểm của học sinh (Tương thích ngược)")
async def submit_score_legacy(request: SubmitScoreRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
    
    doc_ref = db.collection('quizzes').document(request.quiz_id).collection('submissions').document()
    doc_ref.set({
        'student_name': request.student_name,
        'score': request.score,
        'total_questions': request.total_questions,
        'time_elapsed': request.time_elapsed,
        'timestamp': firestore.SERVER_TIMESTAMP
    })
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
    db = get_db()
    if db is None:
        return {"status": "error"}
        
    db.collection('quizzes').document(req.quiz_id).collection('active_sessions').document(req.session_id).set({
        'student_name': req.student_name,
        'answers_count': req.answers_count,
        'time_remaining': req.time_remaining,
        'completed': req.completed,
        'updated_at': firestore.SERVER_TIMESTAMP
    })
    return {"status": "success"}

@router.get("/leaderboard/{quiz_id}", summary="Lấy bảng xếp hạng top thành tích")
async def get_leaderboard(quiz_id: str):
    db = get_db()
    if db is None:
        return {"status": "error"}
        
    subs_ref = db.collection('quizzes').document(quiz_id).collection('submissions')
    docs = subs_ref.get()
    results = []
    for doc in docs:
        data = doc.to_dict()
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
    return {"status": "success", "data": results[:50]}
