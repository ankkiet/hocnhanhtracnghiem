import os
import re
import json
import uuid
import tempfile
import shutil
import time
import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, File, UploadFile, HTTPException, Form, BackgroundTasks, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    import json_repair
except ImportError:
    json_repair = None

from services.firebase_service import get_db
from services.ai_service import (
    call_gemini_with_fallback,
    fix_json_latex_escapes,
    generate_mcq_with_gemini,
    generate_mcq_from_pdf,
    normalize_question_data
)
from services.r2_service import get_stored_image, extract_image_keys_from_data
from core.state import active_tasks, SETTINGS_CACHE

def get_cached_gemini_keys(db) -> list:
    """Lấy danh sách Gemini API Keys từ cache bộ nhớ đệm (10 phút) để tránh đọc Firestore liên tục."""
    if not db:
        return []
    now = time.time()
    if 'gemini' in SETTINGS_CACHE and (now - SETTINGS_CACHE['gemini']['time'] < 600):
        return SETTINGS_CACHE['gemini']['data']
    try:
        settings_doc = db.collection('settings').document('gemini').get()
        api_keys = settings_doc.to_dict().get('api_keys', []) if settings_doc.exists else []
        SETTINGS_CACHE['gemini'] = {'time': now, 'data': api_keys}
        return api_keys
    except Exception:
        return []
from core.answer_key_extractor import (
    extract_answer_key_from_doc,
    reconcile_quiz_with_answer_key,
    align_mcq_correct_answer
)
from core.docx_parser import (
    parse_docx_to_marked_text,
    extract_formatting_from_docx,
    replace_placeholders,
    split_merged_options,
    recursive_unescape
)
from core.text_parser import extract_questions_from_text_bulletproof
from core.pdf_parser import extract_questions_from_pdf_locally

router = APIRouter(tags=["Document & AI Generation"])


class GenerateQuizRequest(BaseModel):
    prompt: str
    num_questions: int = 5
    difficulty: str = "Trung bình"


async def generate_quiz_ai_background(task_id: str, req: GenerateQuizRequest, api_keys: List[str]):
    """Tác vụ chạy ngầm để tạo đề thi từ một chủ đề (prompt)"""
    try:
        active_tasks[task_id] = {"status": "processing", "message": "AI đang suy nghĩ và tạo đề..."}
        
        system_instruction = (
            "Bạn là một chuyên gia giáo dục và biên soạn đề thi trắc nghiệm xuất sắc. "
            "Nhiệm vụ của bạn là tạo ra các câu hỏi trắc nghiệm chất lượng cao, đúng chuẩn kiến thức, "
            "đúng 4 lựa chọn A, B, C, D rõ ràng, và luôn kèm lời giải chi tiết (explain). "
            "Nếu có công thức toán/lý/hóa, dùng cú pháp LaTeX bọc trong \\( và \\) (ví dụ \\(\\text{CH}_2\\)) hoặc thẻ HTML <sub>/<sup> (ví dụ CH<sub>2</sub>, H<sub>2</sub>O). "
            "TUYỆT ĐỐI KHÔNG viết dạng gạch dưới trần như CH_2, CO_2, H_2O. "
            "Định dạng trả về bắt buộc là một JSON array duy nhất."
        )
        
        prompt = f"""
        Hãy tạo đề thi trắc nghiệm theo thông số sau:
        - Chủ đề / Nội dung cốt lõi: {req.prompt}
        - Số lượng câu hỏi: {req.num_questions}
        - Độ khó: {req.difficulty}

        Mỗi câu hỏi có cấu trúc JSON:
        {{
          "group_title": "Tiêu đề nhóm hoặc đoạn văn đọc hiểu (nếu có, không có thì để trống '')",
          "question": "Nội dung câu hỏi (không thêm 'Câu X:')",
          "options": ["A. Lựa chọn 1", "B. Lựa chọn 2", "C. Lựa chọn 3", "D. Lựa chọn 4"],
          "correct_answer": "A. Lựa chọn 1",
          "explain": "Lời giải thích ngắn gọn, súc tích vì sao đáp án này đúng."
        }}
        """
        
        response = await call_gemini_with_fallback(
            prompt=prompt,
            api_keys=api_keys,
            system_instruction=system_instruction,
            thinking_budget=0
        )
        fixed_raw = fix_json_latex_escapes(response.text)
        data = None
        if json_repair is not None:
            try:
                data = json_repair.loads(fixed_raw)
            except Exception:
                try:
                    data = json_repair.loads(response.text)
                except Exception:
                    pass
        if data is None:
            match = re.search(r'\[\s*\{.*\}\s*\]', fixed_raw, re.DOTALL)
            json_text = match.group(0) if match else fixed_raw
            try:
                data = json.loads(json_text, strict=False)
            except Exception:
                pass

        if isinstance(data, dict):
            for k in ["questions", "data", "quiz", "result", "items", "cau_hoi", "list"]:
                if isinstance(data.get(k), list):
                    data = data[k]
                    break
            else:
                if "question" in data:
                    data = [data]
                else:
                    data = []

        if isinstance(data, list):
            data = [normalize_question_data(q) for q in data if isinstance(q, dict)]
            
        active_tasks[task_id] = {"status": "success", "data": data}

    except Exception as e:
        active_tasks[task_id] = {"status": "error", "detail": f"Lỗi khi gọi AI hoặc parse JSON: {str(e)}"}


def process_document_background(task_id: str, temp_file_path: str, ext: str, use_ai: bool, api_keys: list, filename: str):
    """Tiến trình ngầm bóc tách tệp tin DOCX hoặc PDF"""
    try:
        active_tasks[task_id] = {"status": "processing", "message": "Đang phân tích..."}
        
        file_ak = None
        if ext != ".pdf":
            try:
                file_ak = extract_answer_key_from_doc(temp_file_path)
            except Exception as ak_err:
                logger.warning(f"[CẢNH BÁO] Lỗi trích xuất bảng đáp án từ DOCX: {ak_err}")

        extracted_data = None
        if ext == ".pdf":
            if use_ai and api_keys:
                try:
                    active_tasks[task_id]["message"] = "AI đang phân tích tài liệu PDF..."
                    extracted_data = asyncio.run(generate_mcq_from_pdf(temp_file_path, api_keys, task_id))
                except Exception as pdf_ai_err:
                    logger.warning(f"[CẢNH BÁO] Lỗi AI bóc tách PDF: {pdf_ai_err}")
                    active_tasks[task_id]["message"] = "Tự động chuyển sang phân tích PDF nội bộ..."
                    extracted_data = extract_questions_from_pdf_locally(temp_file_path)
            else:
                active_tasks[task_id]["message"] = "Đang phân tích PDF bằng thuật toán nội bộ..."
                extracted_data = extract_questions_from_pdf_locally(temp_file_path)
                # Nếu bộ phân tích PDF nội bộ không tìm thấy câu hỏi mà có API Key, tự động cứu hộ bằng AI
                if (not extracted_data or len(extracted_data) == 0) and api_keys:
                    logger.warning("[CẢNH BÁO] PDF nội bộ không tìm thấy câu hỏi, tự động kích hoạt AI cứu hộ...")
                    active_tasks[task_id]["message"] = "Tự động kích hoạt AI cứu hộ PDF..."
                    try:
                        extracted_data = asyncio.run(generate_mcq_from_pdf(temp_file_path, api_keys, task_id))
                    except Exception as rescue_err:
                        logger.warning(f"[CẢNH BÁO] AI cứu hộ PDF gặp lỗi: {rescue_err}")
        elif use_ai and api_keys:
            try:
                active_tasks[task_id]["message"] = "AI đang phân tích tài liệu Word..."
                marked_text, image_mapping = parse_docx_to_marked_text(temp_file_path)
                extracted_data = asyncio.run(generate_mcq_with_gemini(marked_text, api_keys, task_id, answer_key=file_ak))
                if image_mapping and extracted_data:
                    extracted_data = replace_placeholders(extracted_data, image_mapping)
                if file_ak and extracted_data:
                    extracted_data = reconcile_quiz_with_answer_key(extracted_data, file_ak)
            except Exception as ai_err:
                logger.warning(f"[CẢNH BÁO] AI bóc tách gặp lỗi ({ai_err}). Tự động chuyển sang bóc tách Regex nội bộ...")
                active_tasks[task_id]["message"] = "Tự động chuyển sang bộ bóc tách nội bộ..."
                try:
                    extracted_data = extract_questions_from_text_bulletproof(marked_text, image_mapping)
                except Exception:
                    extracted_data = None
                if not extracted_data:
                    try:
                        extracted_data = extract_formatting_from_docx(temp_file_path)
                    except Exception:
                        pass
        else:
            # use_ai = False: Phân tích DOCX bằng Python nội bộ
            active_tasks[task_id]["message"] = "Đang phân tích tài liệu bằng thuật toán Python..."
            marked_text = ""
            image_mapping = {}
            try:
                marked_text, image_mapping = parse_docx_to_marked_text(temp_file_path)
                extracted_data = extract_questions_from_text_bulletproof(marked_text, image_mapping)
            except Exception as bp_err:
                logger.warning(f"[CẢNH BÁO] Bộ bóc tách Bulletproof gặp lỗi: {bp_err}")
                extracted_data = None
                
            # Nếu bộ bóc tách chính không tìm thấy câu hỏi, kích hoạt bộ bóc tách dự phòng (Engine 2)
            if not extracted_data or len(extracted_data) == 0:
                try:
                    extracted_data = extract_formatting_from_docx(temp_file_path)
                except Exception as docx_err:
                    logger.warning(f"[CẢNH BÁO] extract_formatting_from_docx gặp lỗi: {docx_err}")
                    extracted_data = None
                    
            # Nếu cả 2 bộ bóc tách nội bộ đều không tìm thấy câu hỏi mà hệ thống CÓ API key, tự động kích hoạt AI cứu hộ
            if (not extracted_data or len(extracted_data) == 0) and api_keys:
                logger.warning("[CẢNH BÁO] Bộ bóc tách nội bộ không tìm thấy câu hỏi, tự động kích hoạt AI cứu hộ...")
                active_tasks[task_id]["message"] = "Tự động kích hoạt AI cứu hộ..."
                try:
                    if not marked_text:
                        marked_text, image_mapping = parse_docx_to_marked_text(temp_file_path)
                    extracted_data = asyncio.run(generate_mcq_with_gemini(marked_text, api_keys, task_id, answer_key=file_ak))
                    if image_mapping and extracted_data:
                        extracted_data = replace_placeholders(extracted_data, image_mapping)
                    if file_ak and extracted_data:
                        extracted_data = reconcile_quiz_with_answer_key(extracted_data, file_ak)
                except Exception as rescue_err:
                    logger.warning(f"[CẢNH BÁO] AI cứu hộ gặp lỗi: {rescue_err}")

        extracted_data = recursive_unescape(extracted_data)

        if extracted_data and isinstance(extracted_data, list):
            if file_ak:
                extracted_data = reconcile_quiz_with_answer_key(extracted_data, file_ak)
            extracted_data = [normalize_question_data(q_item) for q_item in extracted_data if isinstance(q_item, dict)]
            for q_item in extracted_data:
                if isinstance(q_item, dict) and q_item.get("type", "mcq") == "mcq" and q_item.get("options"):
                    q_item["options"] = split_merged_options(q_item["options"])
                    if q_item.get("correct_answer"):
                        q_item["correct_answer"] = align_mcq_correct_answer(q_item["correct_answer"], q_item["options"])

        if not extracted_data:
            active_tasks[task_id] = {
                "status": "error",
                "detail": "Không thể trích xuất câu hỏi từ file. Vui lòng đảm bảo file có chứa câu hỏi dạng 'Câu 1:' hoặc '1.' và các phương án A, B, C, D."
            }
            return

        task_images = extract_image_keys_from_data(extracted_data)
        active_tasks[task_id] = {
            "status": "success",
            "data": extracted_data,
            "filename": filename,
            "images": task_images
        }
        
    except Exception as e:
        error_msg = str(e)
        if "Package not found" in error_msg:
            active_tasks[task_id] = {
                "status": "error",
                "detail": "File tải lên không phải là định dạng Word (.docx) chuẩn. Có thể đây là file .doc cũ bị đổi tên đuôi hoặc file đã bị hỏng. Vui lòng mở file bằng Microsoft Word và chọn 'Save As' -> 'Word Document (*.docx)' rồi tải lên lại."
            }
        else:
            active_tasks[task_id] = {"status": "error", "detail": f"Lỗi xử lý hệ thống: {error_msg}"}
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass


@router.post("/api/upload", summary="Tải lên và phân tích file DOCX hoặc PDF")
def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...), use_ai: bool = Form(True)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".docx", ".pdf"]:
        raise HTTPException(status_code=400, detail="Hệ thống chỉ hỗ trợ định dạng Word (.docx) và PDF (.pdf)")
        
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name
            
        db = get_db()
        api_keys = get_cached_gemini_keys(db)
        
        # Nếu người dùng bật AI nhưng hệ thống chưa có API key, tự động chuyển sang phân tích Python nội bộ
        if use_ai and not api_keys:
            use_ai = False
            
        task_id = str(uuid.uuid4())
        active_tasks[task_id] = {"status": "pending"}
        
        # Bắt đầu luồng phân tích ngầm và không chặn luồng kết nối HTTP
        background_tasks.add_task(process_document_background, task_id, temp_file_path, ext, use_ai, api_keys, file.filename)
        
        mode_msg = "AI" if (use_ai and api_keys) else "thuật toán Python"
        return {
            "status": "processing",
            "task_id": task_id,
            "message": f"File đang được xử lý bằng {mode_msg}..."
        }
        
    except HTTPException as he:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise he
    except Exception as e:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        error_msg = str(e)
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý hệ thống: {error_msg}")


@router.post("/api/generate_quiz_ai", summary="Tạo đề thi tự động bằng AI (Chạy ngầm)")
async def generate_quiz_ai(req: GenerateQuizRequest, background_tasks: BackgroundTasks):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
    
    api_keys = get_cached_gemini_keys(db)
    if not api_keys:
        raise HTTPException(status_code=400, detail="Hệ thống chưa cấu hình Gemini API Key. Vui lòng liên hệ Admin.")
    
    task_id = str(uuid.uuid4())
    active_tasks[task_id] = {"status": "pending"}
    
    background_tasks.add_task(generate_quiz_ai_background, task_id, req, api_keys)
    
    return {
        "status": "processing",
        "task_id": task_id,
        "message": "Yêu cầu đã được tiếp nhận. AI đang xử lý ngầm..."
    }


@router.get("/api/task_status/{task_id}", summary="Kiểm tra trạng thái tiến trình AI")
def get_task_status(task_id: str):
    now = time.time()
    
    # Tự động dọn dẹp các task cũ đã hoàn tất trên 15 phút (900 giây) để giải phóng RAM
    expired_keys = [
        k for k, v in active_tasks.items()
        if isinstance(v, dict) and v.get("status") in ["success", "error"] and (now - v.get("completed_at", now)) > 900
    ]
    for k in expired_keys:
        active_tasks.pop(k, None)

    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Không tìm thấy tiến trình xử lý hoặc tiến trình đã quá hạn")
    
    task_info = active_tasks[task_id]
    # Gắn mốc thời gian hoàn thành (không xóa ngay lập tức để tránh lỗi mất đề khi người dùng reload trang)
    if task_info.get("status") in ["success", "error"] and "completed_at" not in task_info:
        task_info["completed_at"] = now
        
    return task_info


@router.get("/api/images/{file_path:path}", summary="Phục vụ ảnh đề thi an toàn, tốc độ cao và không bị lỗi 403")
async def serve_image(file_path: str):
    """Phục vụ hình ảnh từ bộ nhớ cache cục bộ hoặc đồng bộ từ Cloudflare R2 qua S3 client."""
    content, mime = get_stored_image(file_path)
    if not content:
        raise HTTPException(status_code=404, detail="Không tìm thấy hình ảnh")
    return Response(
        content=content,
        media_type=mime,
        headers={"Cache-Control": "public, max-age=31536000, immutable"}
    )


@router.get("/api/download-sample-docx", summary="Tải file Word mẫu chuẩn HocNhanhTN để tránh lỗi nhận diện")
def download_sample_docx():
    """Tải tệp Word (.docx) mẫu chuẩn HocNhanhTN có hướng dẫn định dạng chi tiết."""
    template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "DE_THI_MAU_CHUAN_HocNhanhTN.docx")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy file mẫu Word")
    return FileResponse(
        path=template_path,
        filename="DE_THI_MAU_CHUAN_HocNhanhTN.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
