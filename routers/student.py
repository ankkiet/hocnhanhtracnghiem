from typing import Optional, Dict, Any
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
            
        correct_ans = q.get('correct_answer')
        is_correct = (user_ans is not None and user_ans == correct_ans)
        
        if is_correct:
            score += 1
            
        results.append({
            "question_index": idx,
            "user_answer": user_ans,
            "correct_answer": correct_ans,
            "is_correct": is_correct,
            "explain": q.get('explain', '')
        })
        
    total_questions = len(questions)
    
    # Lưu bản ghi nộp bài đã được xác thực an toàn vào Firestore
    submission_ref = db.collection('quizzes').document(req.quiz_id).collection('submissions').document()
    submission_data = {
        'student_name': req.student_name.strip() or 'Ẩn danh',
        'score': score,
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
        "score": score,
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
        
    user = get_user_from_token(req.student_token, db)
    user_id = user['id'] if user else req.student_token
    
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
        
    user = get_user_from_token(student_token, db)
    user_id = user['id'] if user else student_token
    
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
        results.append({
            'student_name': data.get('student_name', 'Ẩn danh'),
            'score': data.get('score', 0),
            'time_elapsed': data.get('time_elapsed', 999999)
        })
    results.sort(key=lambda x: (-x['score'], x['time_elapsed']))
    return {"status": "success", "data": results[:50]}
