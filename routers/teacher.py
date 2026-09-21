import json
import re
import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.firebase_service import get_db
from core.security import get_user_from_token
from core.docx_exporter import export_quiz_to_docx
from services.ai_service import call_gemini_with_fallback, fix_json_latex_escapes

try:
    import json_repair
except ImportError:
    json_repair = None


router = APIRouter(prefix="/api/teacher", tags=["Teacher Management"])

class QuizActionRequest(BaseModel):
    teacher_token: str
    quiz_id: str
    action: str

class TogglePublishRequest(BaseModel):
    teacher_token: str
    quiz_id: str
    status: str

class CheckQuizRequest(BaseModel):
    teacher_token: str
    quiz_data: list
    custom_prompt: str = ""

def verify_teacher_access(token: str, db) -> tuple:
    """Xác minh quyền giáo viên/quản trị viên."""
    user = get_user_from_token(token, db)
    if not user:
        raise HTTPException(status_code=403, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.")
    if user.get('role') not in ['teacher', 'admin']:
        raise HTTPException(status_code=403, detail="Tài khoản không có quyền Giáo viên.")
    return user, user['id']

@router.get("/quizzes", summary="Lấy danh sách đề thi của Giáo viên")
async def get_teacher_quizzes(teacher_token: str):
    db = get_db()
    if db is None:
        return {"status": "error"}
        
    user, user_uid = verify_teacher_access(teacher_token, db)
    
    # Hỗ trợ tìm kiếm theo cả ID người dùng mới và token cũ
    docs = db.collection('quizzes').where('creator_id', '==', user_uid).get()
    if not docs and teacher_token != user_uid:
        docs = db.collection('quizzes').where('creator_id', '==', teacher_token).get()
        
    results = []
    for doc in docs:
        data = doc.to_dict()
        results.append({
            'id': doc.id,
            'title': data.get('title', 'Không tên'),
            'mode': data.get('mode', 'practice'),
            'status': data.get('status', 'published'),
            'question_count': len(data.get('data', [])),
            'time_limit': data.get('time_limit', 0)
        })
    return {"status": "success", "data": results}

@router.post("/quiz_action", summary="Thao tác với đề thi (Thùng rác, Khôi phục, Xóa vĩnh viễn)")
async def quiz_action(req: QuizActionRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    user, user_uid = verify_teacher_access(req.teacher_token, db)
    doc_ref = db.collection('quizzes').document(req.quiz_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")
        
    creator = doc.to_dict().get('creator_id')
    if creator != user_uid and creator != req.teacher_token and user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Không có quyền thao tác trên đề thi này")
        
    if req.action == 'trash':
        doc_ref.update({'status': 'trashed'})
    elif req.action == 'restore':
        doc_ref.update({'status': 'unpublished'})
    elif req.action == 'permanent':
        doc_ref.delete()
    return {"status": "success"}

@router.post("/toggle_publish", summary="Bật/Tắt xuất bản đề thi")
async def toggle_publish(req: TogglePublishRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    user, user_uid = verify_teacher_access(req.teacher_token, db)
    doc_ref = db.collection('quizzes').document(req.quiz_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")
        
    creator = doc.to_dict().get('creator_id')
    if creator != user_uid and creator != req.teacher_token and user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Không có quyền thay đổi trạng thái")
        
    doc_ref.update({'status': req.status})
    return {"status": "success"}

@router.get("/monitor/{quiz_id}", summary="Lấy danh sách trạng thái làm bài trực tiếp")
async def get_monitor_data(quiz_id: str, teacher_token: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    user, user_uid = verify_teacher_access(teacher_token, db)
    doc_ref = db.collection('quizzes').document(quiz_id).get()
    if not doc_ref.exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")
        
    creator = doc_ref.to_dict().get('creator_id')
    if creator != user_uid and creator != teacher_token and user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Không có quyền giám sát đề thi này")
    
    sessions = db.collection('quizzes').document(quiz_id).collection('active_sessions').get()
    res = []
    now = datetime.datetime.now(datetime.timezone.utc)
    for s in sessions:
        d = s.to_dict()
        updated_at = d.get('updated_at')
        is_online = False
        if updated_at and (now - updated_at).total_seconds() < 40:
            is_online = True
        res.append({
            'session_id': s.id,
            'student_name': d.get('student_name', 'Ẩn danh'),
            'answers_count': d.get('answers_count', 0),
            'time_remaining': d.get('time_remaining', 0),
            'completed': d.get('completed', False),
            'is_online': is_online
        })
    return {"status": "success", "data": res}

@router.post("/check_quiz_ai", summary="AI Kiểm tra lỗi đề thi")
async def check_quiz_ai(req: CheckQuizRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    verify_teacher_access(req.teacher_token, db)
        
    settings_doc = db.collection('settings').document('gemini').get()
    if not settings_doc.exists or not settings_doc.to_dict().get('api_keys'):
        raise HTTPException(status_code=400, detail="Quản trị viên chưa cấu hình Gemini API Key chung. Vui lòng liên hệ Admin.")
    api_keys = settings_doc.to_dict().get('api_keys')
    
    try:
        custom_instructions = f"\n**YÊU CẦU ĐẶC BIỆT TỪ NGƯỜI DÙNG:**\n{req.custom_prompt}\n" if req.custom_prompt.strip() else ""
        
        system_instruction = (
            "Bạn là một chuyên gia giáo dục và biên tập viên kiểm định chất lượng đề thi trắc nghiệm. "
            "Nhiệm vụ của bạn là rà soát tỉ mỉ đề thi, phát hiện lỗi sai kiến thức, sai đáp án, "
            "lỗi ngữ pháp, logic hoặc trùng lặp, và đề xuất sửa lại. "
            "Chỉ báo cáo các câu có lỗi. Trả về kết quả dưới dạng JSON array duy nhất."
        )
        
        prompt = f"""
        Hãy rà soát kỹ lưỡng danh sách câu hỏi trắc nghiệm dưới đây:
        {custom_instructions}

        QUY TẮC ĐỊNH DẠNG JSON:
        1. CHỈ phân tích những câu hỏi có lỗi. BỎ QUA HOÀN TOÀN những câu đúng.
        2. Mỗi câu lỗi gồm:
           * question_index: (Number) Chỉ số của câu hỏi trong mảng (bắt đầu từ 0).
           * reason: (String) Giải thích ngắn gọn lỗi.
           * corrected_data: (Object) Chứa dữ liệu đã sửa (question, options, correct_answer, group_title).
        3. BẮT BUỘC chỉ trả về JSON array. Nếu không có lỗi nào, trả về: []
        
        Dữ liệu đề thi:
        {json.dumps(req.quiz_data, ensure_ascii=False)}
        """
        
        response = await call_gemini_with_fallback(
            prompt=prompt,
            api_keys=api_keys,
            system_instruction=system_instruction,
            thinking_budget=0
        )
        match = re.search(r'\[.*\]', response.text, re.DOTALL)
        if not match:
            if "không có lỗi" in response.text.lower() or "hoàn hảo" in response.text.lower():
                return {"status": "success", "feedback": []}
            return {"status": "success", "feedback": response.text}

        json_text = match.group(0)
        json_text = fix_json_latex_escapes(json_text)
        if json_repair is not None:
            feedback_data = json_repair.loads(json_text)
        else:
            feedback_data = json.loads(json_text, strict=False)
        return {"status": "success", "feedback": feedback_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi gọi AI: {str(e)}")

@router.get("/export_docx/{quiz_id}", summary="Xuất đề thi ra file Word (.docx) chuẩn in ấn")
async def export_quiz_docx(quiz_id: str, teacher_token: Optional[str] = None):
    """Xuất đề thi ra định dạng Word .docx kèm Bảng đáp án để in ấn."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
    doc = db.collection('quizzes').document(quiz_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")
        
    quiz_data = doc.to_dict()
    title = quiz_data.get('title', 'Đề thi trắc nghiệm')
    questions = quiz_data.get('data', [])
    time_limit = quiz_data.get('time_limit', 0)
    
    docx_stream = export_quiz_to_docx(title, questions, time_limit)
    safe_filename = re.sub(r'[^a-zA-Z0-9_\-]', '_', quiz_id)
    
    return StreamingResponse(
        docx_stream,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename=de_thi_{safe_filename}.docx"
        }
    )

@router.get("/quiz_analytics/{quiz_id}", summary="Thống kê phổ điểm và phân tích câu hỏi học sinh hay sai")
async def get_quiz_analytics(quiz_id: str, teacher_token: str):
    """Thống kê chi tiết phổ điểm, điểm trung bình, và xác định các câu hỏi khó nhất."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
    verify_teacher_access(teacher_token, db)
    
    quiz_doc = db.collection('quizzes').document(quiz_id).get()
    if not quiz_doc.exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")
        
    quiz_data = quiz_doc.to_dict()
    questions = quiz_data.get('data', [])
    total_q = len(questions)
    
    # Lấy toàn bộ danh sách bài nộp của học sinh
    submissions = db.collection('quizzes').document(quiz_id).collection('submissions').get()
    sub_count = len(submissions)
    
    if sub_count == 0:
        return {
            "status": "success",
            "total_submissions": 0,
            "average_score": 0,
            "max_score": 0,
            "min_score": 0,
            "score_bands": {"0-2": 0, "2-4": 0, "4-6": 0, "6-8": 0, "8-10": 0},
            "question_stats": [],
            "hardest_questions": []
        }
        
    scores = []
    # Thống kê câu hỏi: {q_idx: {"correct_count": X, "picks": {"A": 0, ...}}}
    q_stats = {i: {"correct": 0, "picks": {}} for i in range(total_q)}
    
    for s in submissions:
        data = s.to_dict()
        raw_score = data.get('score', 0)
        tot = data.get('total_questions', total_q) or total_q
        # Quy đổi điểm về hệ 10
        norm_score = round((raw_score / tot) * 10, 1) if tot > 0 else 0
        scores.append(norm_score)
        
        # Thống kê chi tiết từng câu nếu bài thi nộp có kèm answers
        user_answers = data.get('answers', {})
        for idx in range(total_q):
            u_ans = user_answers.get(str(idx)) or user_answers.get(idx)
            correct_ans = questions[idx].get('correct_answer')
            if u_ans and correct_ans and u_ans == correct_ans:
                q_stats[idx]["correct"] += 1
            if u_ans:
                first_char = u_ans.strip()[:1].upper()
                q_stats[idx]["picks"][first_char] = q_stats[idx]["picks"].get(first_char, 0) + 1

    # Phân bố điểm
    score_bands = {"0-2": 0, "2-4": 0, "4-6": 0, "6-8": 0, "8-10": 0}
    for sc in scores:
        if sc < 2: score_bands["0-2"] += 1
        elif sc < 4: score_bands["2-4"] += 1
        elif sc < 6: score_bands["4-6"] += 1
        elif sc < 8: score_bands["6-8"] += 1
        else: score_bands["8-10"] += 1
        
    # Phân tích câu hỏi
    question_analysis = []
    for idx, stat in q_stats.items():
        corr = stat["correct"]
        rate = round((corr / sub_count) * 100, 1) if sub_count > 0 else 0
        q_text = questions[idx].get('question', '')[:90] + "..." if len(questions[idx].get('question', '')) > 90 else questions[idx].get('question', '')
        question_analysis.append({
            "question_index": idx + 1,
            "question_preview": q_text,
            "correct_count": corr,
            "accuracy_rate": rate,
            "picks": stat["picks"]
        })
        
    # Top 5 câu khó nhất (tỷ lệ đúng thấp nhất)
    hardest = sorted(question_analysis, key=lambda x: x["accuracy_rate"])[:5]
    
    return {
        "status": "success",
        "total_submissions": sub_count,
        "average_score": round(sum(scores) / len(scores), 2),
        "max_score": max(scores),
        "min_score": min(scores),
        "score_bands": score_bands,
        "question_stats": question_analysis,
        "hardest_questions": hardest
    }
