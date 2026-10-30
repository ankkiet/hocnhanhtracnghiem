"""
HocNhanhTN - Hệ thống học nhanh trắc nghiệm cho học sinh & giáo viên.
Entrypoint ứng dụng: Khởi tạo ASGI app thông qua App Factory và chạy máy chủ Uvicorn/Gunicorn.
"""

from typing import List, Optional

from pydantic import BaseModel

from core.app_factory import create_app
from core.config import settings
from core.logging_config import get_logger

logger = get_logger(__name__)

# Khởi tạo thực thể FastAPI bằng App Factory
app = create_app()


# ==============================================================================
# RE-EXPORTS ĐẢM BẢO TƯƠNG THÍCH NGƯỢC (BACKWARDS COMPATIBILITY)
# Giúp các file tests, scripts cũ và consumers không bị ảnh hưởng khi tái cấu trúc
# ==============================================================================
from services.firebase_service import get_db, init_firebase  # noqa: F401

db = get_db()

from core.answer_key_extractor import (  # noqa: F401
    extract_answer_key_from_doc as extract_answer_key,
)
from core.docx_parser import (  # noqa: F401
    evaluate_correct_answer,
    extract_formatting_from_docx,
    find_image_part_and_id,
    get_auto_numbering_prefix,
    parse_docx_to_marked_text,
    recursive_unescape,
    replace_placeholders,
    split_merged_options,
    split_option_and_leading_text,
)
from core.pdf_parser import (  # noqa: F401
    extract_questions_from_pdf_locally,
)
from core.state import QUIZ_CACHE, active_tasks  # noqa: F401
from core.text_parser import (  # noqa: F401
    extract_explain_from_block,
    extract_questions_from_text_bulletproof,
)
from routers.admin import router as admin_router  # noqa: F401
from routers.auth import router as auth_router  # noqa: F401
from routers.document import (  # noqa: F401
    router as document_router,
)
from routers.quiz import router as quiz_router  # noqa: F401
from routers.student import router as student_router  # noqa: F401
from routers.teacher import router as teacher_router  # noqa: F401
from services.ai_service import fix_json_latex_escapes  # noqa: F401


# Legacy Request Models cho các consumers cũ
class SaveQuizRequest(BaseModel):
    quiz_id: Optional[str] = None
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


# ==============================================================================
# ENTRYPOINT CHẠY TRỰC TIẾP QUA UVICORN
# ==============================================================================
if __name__ == "__main__":
    import uvicorn

    logger.info(
        f"App startup in {settings.ENVIRONMENT} mode on http://{settings.HOST}:{settings.PORT}"
    )
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.RELOAD)
