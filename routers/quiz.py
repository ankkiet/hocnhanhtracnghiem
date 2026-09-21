import random
import string
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from firebase_admin import firestore
from services.firebase_service import get_db
from core.security import get_user_from_token

router = APIRouter(prefix="/api", tags=["Quiz Management"])

class SaveQuizRequest(BaseModel):
    quiz_id: Optional[str] = None
    title: str
    data: list
    mode: str = "practice"
    time_limit: int = 0
    is_shuffle: bool = False
    creator_id: str = ""
    status: str = "published"

@router.post("/save_quiz", summary="Lưu bài thi và lấy link")
async def save_quiz(request: SaveQuizRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
    user = get_user_from_token(request.creator_id, db)
    creator_uid = user['id'] if user else request.creator_id
    
    if request.quiz_id:
        quiz_id = request.quiz_id
        doc_ref = db.collection('quizzes').document(quiz_id)
        doc = doc_ref.get()
        if doc.exists:
            stored_creator = doc.to_dict().get('creator_id')
            if stored_creator != creator_uid and stored_creator != request.creator_id:
                raise HTTPException(status_code=403, detail="Không có quyền cập nhật đề thi này")
    else:
        # Tạo mã ngẫu nhiên dạng AAA-111
        while True:
            part1 = ''.join(random.choices(string.ascii_uppercase, k=3))
            part2 = ''.join(random.choices(string.digits, k=3))
            quiz_id = f"{part1}-{part2}"
            if not db.collection('quizzes').document(quiz_id).get().exists:
                break
        
    doc_ref = db.collection('quizzes').document(quiz_id)
    data_to_save = {
        'title': request.title,
        'data': request.data,
        'mode': request.mode,
        'time_limit': request.time_limit,
        'is_shuffle': request.is_shuffle,
        'creator_id': creator_uid,
        'status': request.status,
        'updated_at': firestore.SERVER_TIMESTAMP
    }
    
    if not request.quiz_id:
        data_to_save['created_at'] = firestore.SERVER_TIMESTAMP
        
    try:
        doc_ref.set(data_to_save, merge=True)
    except Exception as e:
        if "maximum document size" in str(e).lower() or "exceeds" in str(e).lower():
            raise HTTPException(status_code=413, detail="Dung lượng đề thi quá lớn (vượt quá 1MB). Hệ thống không thể lưu. Vui lòng giảm bớt kích thước ảnh.")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu vào cơ sở dữ liệu: {str(e)}")

    return {"status": "success", "quiz_id": quiz_id, "link": f"/?id={quiz_id}"}

@router.get("/get_quiz/{quiz_id}", summary="Lấy dữ liệu bài thi qua ID (Bảo mật chống F12)")
async def get_quiz(quiz_id: str, teacher_token: Optional[str] = None):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
    doc_ref = db.collection('quizzes').document(quiz_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")
        
    quiz_data = doc.to_dict()
    stored_creator = quiz_data.get('creator_id')
    
    is_creator = False
    if teacher_token:
        user = get_user_from_token(teacher_token, db)
        user_uid = user['id'] if user else teacher_token
        is_creator = (user_uid == stored_creator or teacher_token == stored_creator or (user and user.get('role') == 'admin'))
        
    if quiz_data.get('status') == 'unpublished' and not is_creator:
        raise HTTPException(status_code=403, detail="Bài thi này đã bị giáo viên tạm khóa (Hủy xuất bản).")
        
    updated_at = quiz_data.get('updated_at')
    updated_ts = updated_at.timestamp() if hasattr(updated_at, 'timestamp') else 0
    
    raw_questions = quiz_data.get('data', [])
    mode = quiz_data.get('mode', 'practice')
    
    # BẢO MẬT ĐỀ THI CHẾ ĐỘ THI THỬ (EXAM MODE):
    # Nếu chế độ là 'exam' và người xem không phải giáo viên tạo đề:
    # LOẠI BỎ HOÀN TOÀN 'correct_answer' và 'explain' để chống học sinh mở F12/Network xem trước!
    if mode == 'exam' and not is_creator:
        sanitized_questions = []
        for q in raw_questions:
            q_copy = {k: v for k, v in q.items() if k not in ['correct_answer', 'explain']}
            sanitized_questions.append(q_copy)
        questions_to_return = sanitized_questions
    else:
        questions_to_return = raw_questions
        
    return {
        "status": "success",
        "title": quiz_data.get('title'),
        "data": questions_to_return,
        "mode": mode,
        "time_limit": quiz_data.get('time_limit', 0),
        "is_shuffle": quiz_data.get('is_shuffle', False),
        "updated_at": updated_ts
    }
