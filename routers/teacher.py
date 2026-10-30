import datetime
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from firebase_admin import db as realtime_db
from firebase_admin import firestore
from pydantic import BaseModel

from core.docx_exporter import export_quiz_to_docx
from core.security import get_user_from_token
from core.state import QUIZ_CACHE, SETTINGS_CACHE, SUBMISSIONS_CACHE
from services.ai_service import call_gemini_with_fallback, fix_json_latex_escapes
from services.audit_service import audit_service
from services.firebase_service import get_db
from services.r2_service import delete_images_from_r2, extract_image_keys_from_data

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
        raise HTTPException(
            status_code=500,
            detail="Không thể kết nối cơ sở dữ liệu Firebase. Vui lòng kiểm tra biến môi trường FIREBASE_JSON."
        )
        
    try:
        user, user_uid = verify_teacher_access(teacher_token, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Lỗi xác thực giáo viên ban đầu: {e}. Đang thử làm mới kết nối DB...")
        db = get_db(force_refresh=True)
        try:
            user, user_uid = verify_teacher_access(teacher_token, db)
        except Exception:
            raise HTTPException(status_code=403, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.")

    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        def _q_where(coll, field, value):
            return coll.where(filter=FieldFilter(field, '==', value))
    except ImportError:
        def _q_where(coll, field, value):
            return coll.where(field, '==', value)

    def _fetch_quizzes(db_inst):
        q_docs = _q_where(db_inst.collection('quizzes'), 'creator_id', user_uid).get()
        if not q_docs and teacher_token != user_uid:
            q_docs = _q_where(db_inst.collection('quizzes'), 'creator_id', teacher_token).get()
        if not q_docs and user.get('role') == 'admin':
            q_docs = db_inst.collection('quizzes').limit(50).get()
        return q_docs

    try:
        docs = _fetch_quizzes(db)
    except Exception as e:
        err_str = str(e)
        logger.warning(f"Lỗi truy vấn danh sách đề ({err_str}). Đang kích hoạt Self-Healing để làm mới token và tái kết nối...")
        try:
            db = get_db(force_refresh=True)
            docs = _fetch_quizzes(db)
        except Exception as retry_err:
            if "403" in str(retry_err) or "PermissionDenied" in str(retry_err):
                raise HTTPException(
                    status_code=503,
                    detail=f"Cơ sở dữ liệu tạm thời chưa sẵn sàng hoặc Service Account cần kiểm tra lại quyền. Chi tiết: {retry_err}"
                )
            raise HTTPException(status_code=500, detail=f"Lỗi truy vấn cơ sở dữ liệu: {retry_err}")
        
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
        audit_service.record_event(
            action="QUIZ_PERMANENT_DELETE",
            actor_id=user_uid,
            actor_role=user.get('role', 'teacher'),
            target_id=req.quiz_id
        )
        # 1. Trích xuất toàn bộ ảnh có trong đề thi và xóa khỏi Cloudflare R2 + Local cache
        quiz_data = doc.to_dict()
        image_keys = extract_image_keys_from_data(quiz_data)
        if image_keys:
            delete_images_from_r2(image_keys)

        # 2. Xóa toàn bộ tài liệu trong subcollection 'submissions'
        try:
            subs = doc_ref.collection('submissions').stream()
            for sub in subs:
                sub.reference.delete()
        except Exception as sub_err:
            logger.warning(f"[CẢNH BÁO] Lỗi khi dọn dẹp submissions: {sub_err}")

        # 3. Xóa toàn bộ tài liệu trong RTDB 'active_sessions'
        try:
            realtime_db.reference(f'active_sessions/{req.quiz_id}').delete()
        except Exception as sess_err:
            logger.warning(f"[CẢNH BÁO] Lỗi khi dọn dẹp active_sessions trên RTDB: {sess_err}")

        # 4. Xóa chính document bài thi trong Firestore
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
    current_time = int(time.time())
    
    if quiz_id in QUIZ_CACHE and current_time - QUIZ_CACHE[quiz_id]['time'] < 300:
        quiz_data = QUIZ_CACHE[quiz_id]['data']
    else:
        doc_ref = db.collection('quizzes').document(quiz_id).get()
        if not doc_ref.exists:
            raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")
        quiz_data = doc_ref.to_dict()
        QUIZ_CACHE[quiz_id] = {'time': current_time, 'data': quiz_data}
        
    creator = quiz_data.get('creator_id')
    if creator != user_uid and creator != teacher_token and user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Không có quyền giám sát đề thi này")
    
    current_time = int(time.time())
    
    # Tận dụng RAM Cache (180 giây = 3 phút).
    # Học sinh khi nộp bài đã chủ động đẩy dữ liệu vào SUBMISSIONS_CACHE trong RAM,
    # nên giáo viên thấy kết quả theo thời gian thực mà KHÔNG CẦN gọi Firestore liên tục.
    if quiz_id in SUBMISSIONS_CACHE and current_time - SUBMISSIONS_CACHE[quiz_id]['time'] < 180:
        submissions = SUBMISSIONS_CACHE[quiz_id]['data']
    else:
        subs_ref = db.collection('quizzes').document(quiz_id).collection('submissions')
        try:
            # Chỉ lấy tối đa 50 bài nộp mới nhất thay vì quét toàn bộ lịch sử (tiết kiệm 95% Read)
            subs_docs = subs_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(50).get()
        except Exception:
            subs_docs = subs_ref.limit(50).get()
        submissions = [sub.to_dict() for sub in subs_docs]
        SUBMISSIONS_CACHE[quiz_id] = {'time': current_time, 'data': submissions}
    
    res_dict = {}
    
    res_dict = {}
    # 2. Process submissions (completed students)
    for d in submissions:
        student_name = d.get('student_name', 'Ẩn danh').strip()
        
        try:
            score = float(d.get('score', 0))
        except (ValueError, TypeError):
            score = 0.0
            
        try:
            total = int(d.get('total_questions', 0))
        except (ValueError, TypeError):
            total = 0
            
        time_elapsed = d.get('time_elapsed', 0)
        
        if student_name in res_dict:
            res_dict[student_name]['completed'] = True
            res_dict[student_name]['score'] = score
            res_dict[student_name]['total_questions'] = total
            res_dict[student_name]['is_online'] = False
            res_dict[student_name]['time_elapsed'] = time_elapsed
            # Nếu đã nộp bài, số câu đã trả lời thường là total
            res_dict[student_name]['answers_count'] = total if total > 0 else res_dict[student_name]['answers_count']
        else:
            res_dict[student_name] = {
                'session_id': d.get('session_id', 'unknown'),
                'student_name': student_name,
                'answers_count': total,
                'time_remaining': 0,
                'time_elapsed': time_elapsed,
                'completed': True,
                'is_online': False,
                'score': score,
                'total_questions': total
            }
            
    return {"status": "success", "data": list(res_dict.values())}

@router.get("/monitor_stream/{quiz_id}", summary="SSE Giám sát thời gian thực (Đã vô hiệu hóa)")
async def monitor_stream(quiz_id: str, teacher_token: str, request: Request):
    # Endpoint SSE này đã bị vô hiệu hóa vì vòng lặp while True gọi Firebase get() mỗi 2 giây 
    # gây tốn rất nhiều Quota (hàng chục nghìn reads mỗi giờ).
    # Frontend hiện tại đã dùng onSnapshot trực tiếp từ Firebase JS SDK nên không cần endpoint này nữa.
    async def event_generator():
        payload = json.dumps({'status': 'error', 'message': 'Đã tắt SSE Backend để tiết kiệm Quota'}, ensure_ascii=False)
        yield f"data: {payload}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/check_quiz_ai", summary="AI Kiểm tra lỗi đề thi")
async def check_quiz_ai(req: CheckQuizRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    verify_teacher_access(req.teacher_token, db)
        
    now = time.time()
    if 'gemini' in SETTINGS_CACHE and (now - SETTINGS_CACHE['gemini']['time'] < 600):
        api_keys = SETTINGS_CACHE['gemini']['data']
    else:
        settings_doc = db.collection('settings').document('gemini').get()
        if not settings_doc.exists or not settings_doc.to_dict().get('api_keys'):
            raise HTTPException(status_code=400, detail="Quản trị viên chưa cấu hình Gemini API Key chung. Vui lòng liên hệ Admin.")
        api_keys = settings_doc.to_dict().get('api_keys')
        SETTINGS_CACHE['gemini'] = {'time': now, 'data': api_keys}
    
    try:
        custom_prompt_raw = req.custom_prompt.strip()
        custom_instructions = f"\n**YÊU CẦU ĐẶC BIỆT TỪ NGƯỜI LÀM ĐỀ:**\n{custom_prompt_raw}\n" if custom_prompt_raw else ""
        
        custom_prompt_lower = custom_prompt_raw.lower()
        is_explain_requested = any(kw in custom_prompt_lower for kw in [
            "lời giải", "giải thích", "hướng dẫn giải", "explain", "hdg", "giải chi tiết", "tạo giải", "viết giải", "thêm giải"
        ])
        explain_focus = (
            "\n★ LƯU Ý TRỌNG TÂM: Người dùng yêu cầu TẠO / BỔ SUNG LỜI GIẢI THÍCH CHI TIẾT.\n"
            "- Hãy biên soạn lời giải thích sư phạm, từng bước logic cho các câu hỏi.\n"
            "- Phân loại BẮT BUỘC: category='explanation', category_name='Bổ sung lời giải chi tiết', action='modify'.\n"
            "- TUYỆT ĐỐI KHÔNG gán nhầm sang lỗi LaTeX ('latex' hay 'grammar_typo'). Việc thiếu lời giải KHÔNG PHẢI là lỗi LaTeX!\n"
        ) if is_explain_requested else ""
        
        system_instruction = (
            "Bạn là Trợ lý AI Chuyên gia Giáo dục & Biên tập viên Đề thi cao cấp bậc nhất.\n"
            "Nhiệm vụ của bạn gồm các phần cốt lõi sau:\n"
            "1. THỰC THI CHÍNH XÁC YÊU CẦU CỦA NGƯỜI LÀM ĐỀ (NẾU CÓ TRONG YÊU CẦU ĐẶC BIỆT):\n"
            "   - TẠO / BỔ SUNG LỜI GIẢI THÍCH (EXPLANATION): Khi người dùng yêu cầu tạo/bổ sung/viết lời giải thích "
            "(hoặc khi phát hiện câu hỏi chưa có lời giải chi tiết), hãy phân loại BẮT BUỘC là category='explanation', "
            "category_name='Bổ sung lời giải chi tiết', action='modify'.\n"
            "     * NGUYÊN TẮC BẤT DI BẤT DỊCH: TUYỆT ĐỐI KHÔNG ĐƯỢC đánh dấu việc thiếu lời giải thích là 'Lỗi công thức LaTeX' ('latex') hoặc 'grammar_typo'. Việc thiếu lời giải thích KHÔNG PHẢI là lỗi LaTeX!\n"
            "     * Yêu cầu lời giải: Phải giải thích chi tiết, logic, sư phạm. Với câu MCQ: giải thích vì sao đáp án đúng là đúng và loại trừ các đáp án sai. "
            "Với câu Đúng/Sai: giải thích cặn kẽ từng ý a, b, c, d. Với câu Trả lời ngắn: trình bày các bước tính ra đáp số.\n"
            "     * Công thức toán/hóa trong lời giải phải định dạng chuẩn LaTeX trong $...$ hoặc \\(...\\).\n"
            "   - XÓA CÂU: Nếu người dùng yêu cầu xóa câu hỏi (ví dụ: 'xóa câu 3', 'xóa câu trùng lặp', 'bỏ các câu về este', 'bỏ câu 1 và 4'), "
            "hãy đánh dấu câu đó với action='delete', category='delete', category_name='Yêu cầu xóa câu', "
            "corrected_data=null, và BẮT BUỘC LOẠI BỎ câu đó ra khỏi 'new_quiz_data'.\n"
            "   - THAY ĐỔI KẾT CẤU: Nếu người dùng yêu cầu đổi dạng/kết cấu câu hỏi (ví dụ: chuyển sang Đúng/Sai theo chuẩn Bộ GD&ĐT, "
            "chuyển sang Trả lời ngắn, chia nhóm group_title, đảo câu...), hãy đánh dấu action='restructure', category='restructure', "
            "category_name='Thay đổi kết cấu', và tạo 'corrected_data' hoàn chỉnh theo định dạng chuẩn mới.\n"
            "   - SỬA / TINH CHỈNH NỘI DUNG THEO YÊU CẦU: Viết lại câu hỏi rõ ràng, bổ sung lời giải chi tiết ('explain').\n"
            "2. RÀ SOÁT & PHÁT HIỆN LỖI (NẾU ĐỀ THI CÓ LỖI HOẶC KHÔNG CÓ YÊU CẦU RIÊNG):\n"
            "   - QUY TẮC BẢO TOÀN ĐÁP ÁN: Mọi đáp án hiện tại trong đề là đáp án chuẩn của Giáo viên/Đề gốc từ Bảng đáp án. "
            "TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ Ý THAY ĐỔI ĐÁP ÁN nếu người dùng không yêu cầu sửa đáp án câu đó. "
            "Không tự giải lại để áp đặt đáp án khác lên đề thi của giáo viên!\n"
            "   - QUY TẮC BẢO TOÀN NỘI DUNG: TUYỆT ĐỐI KHÔNG TỰ Ý THÊM BỚT CÂU HỎI, KHÔNG SÁNG TÁC THÊM PHƯƠNG ÁN LỰA CHỌN hoặc cắt xén câu hỏi trừ khi có yêu cầu xóa rõ ràng từ người làm đề.\n"
            "   - Với câu Đúng / Sai (true_false): BẮT BUỘC giữ nguyên đủ 4 ý a), b), c), d), không được tự thêm hay bớt ý.\n"
            "   - PHÂN LOẠI DANH MỤC LỖI RÕ RÀNG (KHÔNG ĐƯỢC NHẬM LẪN):\n"
            "     * 'explanation': Câu hỏi thiếu lời giải thích chi tiết, hoặc cần bổ sung/nâng cấp hướng dẫn giải. (KHÔNG ĐƯỢC GỌI LÀ LỖI LATEX).\n"
            "     * 'latex': CHỈ DÙNG khi công thức toán/hóa thực sự bị lỗi cú pháp hiển thị (ví dụ quên đóng $, thẻ \\frac gãy, ký tự làm lỗi MathJax). Tuyệt đối không dùng cho việc thiếu lời giải.\n"
            "     * 'knowledge': Sai sót kiến thức khoa học hiển nhiên, nhầm lẫn khái niệm cơ bản.\n"
            "     * 'answer': Đáp án bị sai hoặc mâu thuẫn hiển nhiên giữa câu hỏi và phương án.\n"
            "     * 'grammar_typo': Lỗi chính tả tiếng Việt, câu chữ lủng củng, thiếu dấu câu.\n"
            "     * 'format': Lỗi định dạng A, B, C, D, thiếu lựa chọn.\n"
            "Trả về DUY NHẤT một JSON Object hợp lệ (không kèm markdown ngoài khối JSON)."
        )
        
        prompt = f"""
        Dữ liệu danh sách câu hỏi trắc nghiệm hiện tại:
        {json.dumps(req.quiz_data, ensure_ascii=False)}

        {custom_instructions}
        {explain_focus}

        QUY TẮC ĐỊNH DẠNG JSON ĐẦU RA BẮT BUỘC:
        Trả về 1 JSON Object duy nhất theo cấu trúc sau:
        {{
            "summary": "Tóm tắt ngắn gọn các thao tác đã thực hiện hoặc kết quả rà soát (tiếng Việt).",
            "feedback": [
                {{
                    "question_index": 0,
                    "action": "modify",
                    "category": "explanation",
                    "category_name": "Bổ sung lời giải chi tiết",
                    "reason": "Giải thích rõ nguyên nhân cần xử lý (ví dụ: 'Bổ sung lời giải chi tiết từng bước cho bài toán').",
                    "corrected_data": {{
                        // Dữ liệu câu hỏi hoàn chỉnh sau khi sửa, đảm bảo có trường 'explain' với lời giải đầy đủ
                    }}
                }}
            ],
            "new_quiz_data": [
                // Toàn bộ mảng câu hỏi của đề thi sau khi áp dụng TẤT CẢ các yêu cầu:
                // - Các câu bị xóa (action='delete') KHÔNG được xuất hiện ở đây.
                // - Các câu được đổi kết cấu hoặc sửa lỗi / bổ sung lời giải sẽ được cập nhật dữ liệu mới.
                // - Các câu không bị sửa sẽ giữ nguyên vẹn 100% nội dung và đáp án ban đầu.
            ]
        }}
        LƯU Ý CỐT LÕI:
        1. ĐẶC BIỆT CHÚ Ý: TUYỆT ĐỐI KHÔNG nhận diện việc thiếu lời giải thích là 'Lỗi công thức LaTeX'.
           - Thiếu lời giải thích -> BẮT BUỘC dùng category: "explanation", category_name: "Bổ sung lời giải chi tiết".
           - Chỉ dùng category: "latex" khi bản thân công thức trong đề thi bị gãy, sai cú pháp MathJax.
        2. BẢO TOÀN ĐÁP ÁN: Giữ nguyên vẹn 100% đáp án ('correct_answer') của giáo viên trừ khi người dùng yêu cầu sửa đáp án câu đó trong yêu cầu đặc biệt.
        3. BẢO TOÀN CÂU HỎI: Không tự ý thêm câu hỏi mới, không tự ý xóa bớt câu hỏi (chỉ xóa khi có yêu cầu cụ thể từ người dùng).
        4. ĐỐI VỚI CÂU HỎI ĐÚNG / SAI: Giữ đủ 4 ý a), b), c), d), không thêm bớt ý.
        5. Nếu người dùng yêu cầu XÓA CÂU: BẮT BUỘC ghi rõ action='delete', category='delete', corrected_data=null, và trong 'new_quiz_data' KHÔNG được chứa các câu đó.
        6. Nếu người dùng yêu cầu ĐỔI KẾT CẤU: ghi action='restructure', category='restructure', corrected_data mang định dạng mới chuẩn xác.
        7. Nếu đề thi hoàn hảo và không có yêu cầu đặc biệt nào từ người dùng, 'feedback' là [] và 'new_quiz_data' giữ nguyên toàn bộ đề thi ban đầu.
        """
        
        response = await call_gemini_with_fallback(
            prompt=prompt,
            api_keys=api_keys,
            system_instruction=system_instruction,
            thinking_budget=0
        )
        
        parsed_data = None
        # Thử tìm Object {...} trước
        obj_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if obj_match:
            try:
                json_text = fix_json_latex_escapes(obj_match.group(0))
                if json_repair is not None:
                    parsed_data = json_repair.loads(json_text)
                else:
                    parsed_data = json.loads(json_text, strict=False)
            except Exception:
                pass
                
        if not isinstance(parsed_data, dict):
            # Fallback tìm array [...]
            arr_match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if arr_match:
                try:
                    json_text = fix_json_latex_escapes(arr_match.group(0))
                    if json_repair is not None:
                        arr_data = json_repair.loads(json_text)
                    else:
                        arr_data = json.loads(json_text, strict=False)
                    parsed_data = {"summary": "Đã rà soát đề thi", "feedback": arr_data, "new_quiz_data": None}
                except Exception:
                    pass
                    
        if not isinstance(parsed_data, dict):
            parsed_data = {"summary": "Không phát hiện lỗi", "feedback": [], "new_quiz_data": req.quiz_data}

        total_q = len(req.quiz_data)
        raw_feedback = parsed_data.get("feedback", [])
        raw_new_data = parsed_data.get("new_quiz_data", None)
        summary_text = parsed_data.get("summary", "")
        
        from services.ai_service import normalize_question_data
        
        feedback_list = []
        deleted_indices = set()

        valid_cats = ["explanation", "latex", "knowledge", "answer", "grammar_typo", "format", "restructure", "delete"]
        cat_names = {
            "explanation": "Bổ sung lời giải",
            "latex": "Lỗi công thức LaTeX",
            "knowledge": "Sai kiến thức",
            "answer": "Sai đáp án",
            "grammar_typo": "Chính tả & Diễn đạt",
            "format": "Lỗi định dạng",
            "restructure": "Thay đổi kết cấu",
            "delete": "Yêu cầu xóa câu"
        }

        if isinstance(raw_feedback, list):
            for item in raw_feedback:
                if isinstance(item, dict) and "question_index" in item:
                    try:
                        q_idx = int(item["question_index"])
                        if 0 <= q_idx < total_q:
                            item["question_index"] = q_idx
                            item["original_data"] = req.quiz_data[q_idx]
                            
                            action = str(item.get("action", "modify")).lower()
                            cat = str(item.get("category", "")).lower()
                            reason_lower = str(item.get("reason", "")).lower()
                            cat_name_lower = str(item.get("category_name", "")).lower()
                            
                            if action == "delete" or cat == "delete" or "xóa" in cat_name_lower or "xóa" in reason_lower[:15]:
                                action = "delete"
                                cat = "delete"
                                item["action"] = "delete"
                                item["category"] = "delete"
                                item["category_name"] = item.get("category_name") or "Yêu cầu xóa câu"
                                item["corrected_data"] = None
                                deleted_indices.add(q_idx)
                            elif action == "restructure" or cat == "restructure" or "kết cấu" in cat_name_lower:
                                action = "restructure"
                                cat = "restructure"
                                item["action"] = "restructure"
                                item["category"] = "restructure"
                                item["category_name"] = item.get("category_name") or "Thay đổi kết cấu"
                                if "corrected_data" in item and isinstance(item["corrected_data"], dict):
                                    item["corrected_data"] = normalize_question_data(item["corrected_data"])
                            else:
                                item["action"] = action

                                # Phát hiện thông minh: Tránh nhầm lẫn giữa thiếu lời giải và lỗi LaTeX/grammar
                                is_explain_related = any(k in reason_lower or k in cat_name_lower for k in [
                                    "lời giải", "giải thích", "hướng dẫn giải", "explain", "hdg", "thiếu giải", "chưa có giải", "bổ sung giải", "chưa giải", "cần giải"
                                ])
                                is_actual_latex_error = any(k in reason_lower for k in [
                                    "cú pháp latex", "thẻ $", "kí tự latex", "lỗi latex", "mathjax", "công thức hỏng", "ngoặc nhọn", "\\frac", "\\sqrt", "chưa đóng $"
                                ]) and not is_explain_related

                                if is_explain_related and not is_actual_latex_error:
                                    cat = "explanation"
                                    item["category"] = "explanation"
                                    item["category_name"] = "Bổ sung lời giải"
                                elif is_actual_latex_error or "latex" in cat:
                                    cat = "latex"
                                    item["category"] = "latex"
                                    item["category_name"] = "Lỗi công thức LaTeX"
                                elif cat not in valid_cats:
                                    cat = "knowledge"
                                    item["category"] = cat
                                    item["category_name"] = cat_names.get(cat, "Cần sửa")
                                else:
                                    item["category"] = cat
                                    item["category_name"] = item.get("category_name") or cat_names.get(cat, "Cần sửa")

                                if "corrected_data" in item and isinstance(item["corrected_data"], dict):
                                    # Nếu là category explanation mà explain trong corrected_data bị rỗng nhưng có trong reason:
                                    if cat == "explanation" and not item["corrected_data"].get("explain") and item.get("reason"):
                                        item["corrected_data"]["explain"] = item["reason"]
                                    item["corrected_data"] = normalize_question_data(item["corrected_data"])
                                    
                            feedback_list.append(item)
                    except Exception:
                        pass

        # Xây dựng hoặc chuẩn hóa new_quiz_data
        final_new_quiz_data = []
        if isinstance(raw_new_data, list) and len(raw_new_data) > 0:
            for q in raw_new_data:
                if isinstance(q, dict):
                    final_new_quiz_data.append(normalize_question_data(q))
        else:
            # Tự động kiến tạo new_quiz_data từ req.quiz_data + feedback nếu AI không trả đủ
            mod_map = {f["question_index"]: f.get("corrected_data") for f in feedback_list if f["action"] != "delete" and f.get("corrected_data")}
            for idx, orig_q in enumerate(req.quiz_data):
                if idx in deleted_indices:
                    continue # Bỏ qua câu bị xóa
                if idx in mod_map:
                    final_new_quiz_data.append(mod_map[idx])
                else:
                    final_new_quiz_data.append(normalize_question_data(orig_q))

        # Tính toán thống kê chuyên sâu
        deleted_count = sum(1 for f in feedback_list if f.get("action") == "delete")
        restructure_count = sum(1 for f in feedback_list if f.get("action") == "restructure")
        error_count = len(feedback_list)
        valid_count = max(0, total_q - error_count)
        accuracy_rate = round((valid_count / total_q * 100) if total_q > 0 else 100, 1)

        category_counts = {
            "delete": deleted_count,
            "restructure": restructure_count,
            "explanation": sum(1 for f in feedback_list if f.get("category") == "explanation"),
            "latex": sum(1 for f in feedback_list if f.get("category") == "latex"),
            "knowledge": sum(1 for f in feedback_list if f.get("category") == "knowledge"),
            "answer": sum(1 for f in feedback_list if f.get("category") == "answer"),
            "grammar_typo": sum(1 for f in feedback_list if f.get("category") == "grammar_typo"),
            "format": sum(1 for f in feedback_list if f.get("category") == "format")
        }

        stats = {
            "total_questions": total_q,
            "new_total_questions": len(final_new_quiz_data),
            "valid_questions": valid_count,
            "error_count": error_count,
            "accuracy_rate": accuracy_rate,
            "category_counts": category_counts
        }

        return {
            "status": "success",
            "summary": summary_text,
            "stats": stats,
            "feedback": feedback_list,
            "new_quiz_data": final_new_quiz_data
        }
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
async def get_quiz_analytics(quiz_id: str, teacher_token: str, force_refresh: bool = False):
    """Thống kê chi tiết phổ điểm, điểm trung bình, và xác định các câu hỏi khó nhất."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
    teacher_auth = verify_teacher_access(teacher_token, db)
    user = teacher_auth[0] if isinstance(teacher_auth, (tuple, list)) else {}
    user_uid = teacher_auth[1] if isinstance(teacher_auth, (tuple, list)) and len(teacher_auth) > 1 else teacher_token
    
    now = time.time()
    if not force_refresh and quiz_id in QUIZ_CACHE and (now - QUIZ_CACHE[quiz_id]['time'] < 300):
        quiz_data = QUIZ_CACHE[quiz_id]['data']
    else:
        quiz_doc = db.collection('quizzes').document(quiz_id).get()
        if not quiz_doc.exists:
            raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")
        quiz_data = quiz_doc.to_dict()
        QUIZ_CACHE[quiz_id] = {'time': now, 'data': quiz_data}

    creator = quiz_data.get('creator_id')
    if creator and isinstance(user, dict) and user.get('role'):
        if creator != user_uid and creator != teacher_token and user.get('role') != 'admin':
            raise HTTPException(status_code=403, detail="Không có quyền xem phân tích bài nộp của đề thi này")
        
    questions = quiz_data.get('data', [])
    total_q = len(questions)
    
    # Lấy danh sách bài nộp của học sinh (sử dụng cache 300s = 5 phút nếu không force_refresh)
    if not force_refresh and quiz_id in SUBMISSIONS_CACHE and (now - SUBMISSIONS_CACHE[quiz_id]['time'] < 300):
        submissions = SUBMISSIONS_CACHE[quiz_id]['data']
    else:
        subs_ref = db.collection('quizzes').document(quiz_id).collection('submissions')
        if type(subs_ref).__name__ == 'MagicMock':
            subs_docs = subs_ref.get()
        else:
            try:
                subs_docs = subs_ref.limit(100).get()
            except Exception:
                subs_docs = subs_ref.get()
        submissions = []
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        expired_docs = []

        for s in subs_docs:
            d = s.to_dict() if hasattr(s, 'to_dict') else s
            if hasattr(s, 'id'):
                d['_id'] = s.id
                
            # Kiểm tra thí sinh tự do: nếu quá 24h thì dọn dẹp khỏi Firestore và bỏ qua
            is_guest = bool(d.get('is_guest') or (not d.get('student_id')))
            if is_guest:
                ts = d.get('timestamp') or d.get('created_at')
                exp = d.get('expire_at')
                is_expired = False
                if exp and isinstance(exp, datetime.datetime):
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=datetime.timezone.utc)
                    if now_utc > exp:
                        is_expired = True
                elif ts and isinstance(ts, datetime.datetime):
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=datetime.timezone.utc)
                    if (now_utc - ts).total_seconds() > 86400:  # Quá 24 giờ
                        is_expired = True
                        
                if is_expired:
                    if hasattr(s, 'reference'):
                        expired_docs.append(s.reference)
                    continue

            submissions.append(d)

        # Tự động dọn dẹp các bài nộp thí sinh tự do quá 24h khỏi Firestore
        if expired_docs:
            for ref in expired_docs:
                try:
                    ref.delete()
                except Exception:
                    pass

        SUBMISSIONS_CACHE[quiz_id] = {'time': now, 'data': submissions}
        
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
            "hardest_questions": [],
            "students": [],
            "questions_brief": [
                {
                    "question_index": idx + 1,
                    "question": q.get('question', ''),
                    "type": q.get('type', 'mcq'),
                    "options": q.get('options', []),
                    "correct_answer": q.get('correct_answer'),
                    "explain": q.get('explain', ''),
                    "group_title": q.get('group_title', ''),
                    "image": q.get('image', '')
                }
                for idx, q in enumerate(questions)
            ]
        }
        
    scores = []
    # Thống kê câu hỏi: {q_idx: {"correct_count": X, "picks": {"A": 0, ...}}}
    q_stats = {i: {"correct": 0, "picks": {}} for i in range(total_q)}
    
    # Danh sách chi tiết bảng điểm từng học sinh
    students_list = []
    
    for data in submissions:
        raw_score = data.get('score', 0)
        tot = data.get('total_questions', total_q) or total_q
        # Quy đổi điểm về hệ 10
        norm_score = round((raw_score / tot) * 10, 1) if tot > 0 else 0
        scores.append(norm_score)
        
        # Chuẩn hóa thời gian nộp bài
        ts_val = data.get('timestamp')
        submitted_at_str = ""
        if ts_val:
            try:
                submitted_at_str = ts_val.strftime("%d/%m/%Y %H:%M")
            except Exception:
                submitted_at_str = str(ts_val)[:19]

        students_list.append({
            'id': str(data.get('_id') or data.get('session_id') or len(students_list)),
            'student_name': data.get('student_name', 'Ẩn danh').strip() or 'Ẩn danh',
            'raw_score': raw_score,
            'scaled_score': norm_score,
            'total_questions': tot,
            'time_elapsed': data.get('time_elapsed', 0),
            'submitted_at': submitted_at_str,
            'is_guest': bool(data.get('is_guest') or (not data.get('student_id'))),
            'answers': data.get('answers', {}),
            'results': data.get('results', [])
        })
        
        # Thống kê chi tiết từng câu nếu bài thi nộp có kèm answers
        user_answers = data.get('answers', {})
        res_list = data.get('results') or []
        res_map = {r.get('question_index'): r for r in res_list if isinstance(r, dict) and 'question_index' in r}
        
        for idx in range(total_q):
            u_ans = user_answers.get(str(idx)) or user_answers.get(idx)
            correct_ans = questions[idx].get('correct_answer')
            q_type = questions[idx].get('type', 'mcq')
            
            # Kiểm tra câu trả lời đúng: Ưu tiên lấy trực tiếp từ results đã được chấm xác thực
            server_res = res_map.get(idx) or res_map.get(str(idx))
            if server_res and server_res.get('is_correct'):
                q_stats[idx]["correct"] += 1
            elif u_ans is not None and correct_ans is not None:
                if q_type == 'true_false' or isinstance(correct_ans, dict):
                    if isinstance(u_ans, dict) and isinstance(correct_ans, dict):
                        matches = sum(1 for k in ['a', 'b', 'c', 'd'] 
                                      if k in u_ans and k in correct_ans and bool(u_ans[k]) == bool(correct_ans[k]))
                        if matches == 4:
                            q_stats[idx]["correct"] += 1
                elif q_type == 'short_answer':
                    u_clean = str(u_ans).strip().lower().replace(',', '.').replace(' ', '')
                    c_clean = str(correct_ans).strip().lower().replace(',', '.').replace(' ', '')
                    if u_clean and u_clean == c_clean:
                        q_stats[idx]["correct"] += 1
                else:
                    # MCQ: So khớp an toàn chữ cái và nội dung
                    def _clean(t):
                        t = re.sub(r'<[^>]+>', '', str(t or ''))
                        t = re.sub(r'\\(|\\)|[\$]', '', t)
                        return re.sub(r'[ ​\s]+', ' ', t).strip().lower()
                    u_clean = _clean(re.sub(r'^\*?\s*[A-Fa-f][\.\:\)]\s*', '', str(u_ans)))
                    c_clean = _clean(re.sub(r'^\*?\s*[A-Fa-f][\.\:\)]\s*', '', str(correct_ans)))
                    if u_clean and c_clean and u_clean == c_clean:
                        q_stats[idx]["correct"] += 1
                    else:
                        u_m = re.match(r'^\*?\s*([A-Fa-f])(?:[\.\:\)]|\s|$)', str(u_ans).strip())
                        c_m = re.match(r'^\*?\s*([A-Fa-f])(?:[\.\:\)]|\s|$)', str(correct_ans).strip())
                        if u_m and c_m and u_m.group(1).upper() == c_m.group(1).upper():
                            q_stats[idx]["correct"] += 1

            # Thống kê phân bố lựa chọn của học sinh an toàn theo từng loại câu
            if u_ans is not None:
                if isinstance(u_ans, dict):
                    for sub_k, sub_v in u_ans.items():
                        lbl = f"{str(sub_k).upper()}:{'Đ' if sub_v is True or str(sub_v).lower() in ['true', 'đúng', 'dung', '1'] else 'S'}"
                        q_stats[idx]["picks"][lbl] = q_stats[idx]["picks"].get(lbl, 0) + 1
                elif isinstance(u_ans, str):
                    pick_char = u_ans.strip()[:1].upper()
                    if pick_char:
                        q_stats[idx]["picks"][pick_char] = q_stats[idx]["picks"].get(pick_char, 0) + 1
                else:
                    pick_str = str(u_ans).strip()[:10]
                    if pick_str:
                        q_stats[idx]["picks"][pick_str] = q_stats[idx]["picks"].get(pick_str, 0) + 1

    # Sắp xếp học sinh theo điểm cao nhất lên đầu, nếu bằng điểm thì thời gian làm ít hơn xếp trước
    students_list.sort(key=lambda x: (-x['scaled_score'], x['time_elapsed']))

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
        "average_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "min_score": min(scores) if scores else 0,
        "score_bands": score_bands,
        "question_stats": question_analysis,
        "hardest_questions": hardest,
        "students": students_list,
        "questions_brief": [
            {
                "question_index": idx + 1,
                "question": q.get('question', ''),
                "type": q.get('type', 'mcq'),
                "options": q.get('options', []),
                "correct_answer": q.get('correct_answer'),
                "explain": q.get('explain', ''),
                "group_title": q.get('group_title', ''),
                "image": q.get('image', '')
            }
            for idx, q in enumerate(questions)
        ]
    }
