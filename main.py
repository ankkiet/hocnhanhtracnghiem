import sys
import os
import re
import html
from typing import List, Dict, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
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
    title="HocNhanhTN - Hệ thống học nhanh trắc nghiệm cho học sinh & giáo viên",
    description="Hệ thống học nhanh trắc nghiệm cho học sinh & giáo viên - Hỗ trợ tải lên file Word, PDF, tự động bóc tách và tạo đề thi trắc nghiệm AI.",
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
# GẮN GIAO DIỆN WEB (STATIC FILES CHO FRONTEND & DYNAMIC OPEN GRAPH METADATA)
# ==========================================
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

@app.get("/", response_class=HTMLResponse, summary="Giao diện chính & Đề thi trắc nghiệm (Tự động hiển thị Tên đề & Thumbnail khi gửi link)")
@app.get("/index.html", response_class=HTMLResponse, summary="Giao diện chính & Đề thi trắc nghiệm")
@app.get("/quiz/{quiz_id}", response_class=HTMLResponse, summary="Link trực tiếp tới đề thi")
async def get_index_page(request: Request, id: Optional[str] = None, quiz_id: Optional[str] = None):
    index_path = os.path.join(templates_dir, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy index.html")
    
    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    target_quiz_id = quiz_id or id
    
    # URL ảnh đại diện tuyệt đối khi gửi link (Facebook / Zalo / Telegram / iMessage)
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    base_url = f"{proto}://{host}".rstrip('/')
    og_image_url = f"{base_url}/unnamed.jpg"
    
    quiz_title = None
    quiz_desc = None
    if target_quiz_id:
        try:
            database = get_db()
            if database is not None:
                doc = database.collection('quizzes').document(target_quiz_id).get()
                if doc.exists:
                    q_data = doc.to_dict()
                    raw_title = q_data.get('title')
                    if raw_title:
                        quiz_title = raw_title.strip()
                        q_count = len(q_data.get('data', []))
                        time_limit = q_data.get('time_limit', 0)
                        desc_parts = [f"Đề thi: {quiz_title}"]
                        if q_count > 0:
                            desc_parts.append(f"{q_count} câu hỏi")
                        if time_limit > 0:
                            desc_parts.append(f"{time_limit} phút làm bài")
                        quiz_desc = " • ".join(desc_parts) + ". Hệ thống học nhanh trắc nghiệm HocNhanhTN chuẩn GDPT 2018."
        except Exception as e:
            print(f"Lỗi truy vấn metadata đề thi {target_quiz_id}: {e}")
            
    if quiz_title:
        escaped_title = html.escape(quiz_title)
        full_page_title = f"{escaped_title} - HocNhanhTN"
        escaped_desc = html.escape(quiz_desc or f"Làm bài kiểm tra: {quiz_title}. Hệ thống học nhanh trắc nghiệm chuẩn GDPT 2018.")
        current_url = html.escape(str(request.url))
        
        # Thay thế tiêu đề <title>
        html_content = re.sub(r'<title>.*?</title>', f'<title>{full_page_title}</title>', html_content, flags=re.IGNORECASE)
        # Thay thế og:title & twitter:title
        html_content = re.sub(r'<meta\s+property=["\']og:title["\']\s+content=["\'].*?["\']', f'<meta property="og:title" content="{escaped_title}"', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+name=["\']twitter:title["\']\s+content=["\'].*?["\']', f'<meta name="twitter:title" content="{escaped_title}"', html_content, flags=re.IGNORECASE)
        # Thay thế meta description & og:description & twitter:description
        html_content = re.sub(r'<meta\s+name=["\']description["\']\s+content=["\'].*?["\']', f'<meta name="description" content="{escaped_desc}"', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+property=["\']og:description["\']\s+content=["\'].*?["\']', f'<meta property="og:description" content="{escaped_desc}"', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+name=["\']twitter:description["\']\s+content=["\'].*?["\']', f'<meta name="twitter:description" content="{escaped_desc}"', html_content, flags=re.IGNORECASE)
        # Cập nhật og:url
        html_content = re.sub(r'<meta\s+property=["\']og:url["\']\s+content=["\'].*?["\']', f'<meta property="og:url" content="{current_url}"', html_content, flags=re.IGNORECASE)
    else:
        current_url = html.escape(str(request.url))
        html_content = re.sub(r'<meta\s+property=["\']og:url["\']\s+content=["\'].*?["\']', f'<meta property="og:url" content="{current_url}"', html_content, flags=re.IGNORECASE)
        
    # Luôn đảm bảo og:image, og:image:secure_url và twitter:image dùng ảnh tuyệt đối unnamed.jpg
    html_content = re.sub(r'<meta\s+property=["\']og:image["\']\s+content=["\'].*?["\']', f'<meta property="og:image" content="{og_image_url}"', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<meta\s+property=["\']og:image:secure_url["\']\s+content=["\'].*?["\']', f'<meta property="og:image:secure_url" content="{og_image_url}"', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<meta\s+name=["\']twitter:image["\']\s+content=["\'].*?["\']', f'<meta name="twitter:image" content="{og_image_url}"', html_content, flags=re.IGNORECASE)
    
    return HTMLResponse(content=html_content, media_type="text/html")

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
