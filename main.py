import sys
import os
from typing import List, Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Khởi tạo Firebase Firestore an toàn
from services.firebase_service import init_firebase, get_db
db = init_firebase()

# Import state
from core.state import active_tasks

# Import routers
from routers.auth import router as auth_router
from routers.quiz import router as quiz_router
from routers.student import router as student_router
from routers.teacher import router as teacher_router
from routers.admin import router as admin_router
from routers.document import (
    router as document_router,
    GenerateQuizRequest,
    generate_quiz_ai_background,
    process_document_background
)

# Re-exports for modularity & backwards compatibility with tests and consumers
from core.docx_parser import (
    extract_formatting_from_docx,
    parse_docx_to_marked_text,
    find_image_part_and_id,
    split_merged_options,
    replace_placeholders,
    recursive_unescape,
    get_auto_numbering_prefix,
    split_option_and_leading_text,
    evaluate_correct_answer
)
from core.text_parser import (
    extract_questions_from_text_bulletproof,
    extract_explain_from_block
)
from core.pdf_parser import (
    extract_questions_from_pdf_locally
)
from core.answer_key_extractor import (
    extract_answer_key_from_doc as extract_answer_key,
    extract_answer_key_from_doc,
    reconcile_quiz_with_answer_key,
    separate_answer_key_from_text,
    AnswerKeyMap
)
from services.ai_service import fix_json_latex_escapes

# Re-export legacy request models for backwards-compatibility
class SaveQuizRequest(BaseModel):
    quiz_id: str = None
    title: str
    data: list
    mode: str = "practice"
    time_limit: int = 0
    is_shuffle: bool = False
    creator_id: str = ""
    status: str = "published"

class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str

class LoginRequest(BaseModel):
    username: str
    password: str

class SetApiKeyRequest(BaseModel):
    admin_token: str
    api_keys: List[str]

# ==========================================
# CẤU HÌNH FASTAPI & MIDDLEWARE
# ==========================================
app = FastAPI(
    title="Hệ thống Tạo Câu hỏi Trắc nghiệm AI - Chuẩn HocnhanhTN",
    description="Giao diện API hỗ trợ tải lên file Word và tự động bóc tách câu hỏi trắc nghiệm.",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các Router tính năng
app.include_router(auth_router)
app.include_router(quiz_router)
app.include_router(student_router)
app.include_router(teacher_router)
app.include_router(admin_router)
app.include_router(document_router)


@app.get("/api/health", summary="Kiểm tra trạng thái máy chủ (Health Check & Keep-Alive)")
@app.get("/ping", summary="Ping đánh thức máy chủ")
def health_check():
    """Endpoint siêu nhẹ để Frontend đánh thức máy chủ (chống ngủ đông) hoặc giám sát Uptime."""
    return {"status": "ok", "message": "HocnhanhTN backend is awake and active"}


# ==========================================
# GẮN GIAO DIỆN WEB (STATIC FILES CHO FRONTEND)
# ==========================================
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

@app.get("/editor", summary="Giao diện Studio Biên tập & Soát lỗi Đề thi")
def get_editor_page():
    editor_path = os.path.join(templates_dir, "editor.html")
    if os.path.exists(editor_path):
        return FileResponse(editor_path)
    raise HTTPException(status_code=404, detail="Không tìm thấy trang editor.html")

if os.path.exists(templates_dir):
    app.mount("/", StaticFiles(directory=templates_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
