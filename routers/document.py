"""
Document Router for HocNhanhTN (Backward Compatibility Shim).
Forwards to app.api.routes.document.
"""

from app.api.routes.document import (
    GenerateQuizRequest,
    download_sample_docx,
    generate_quiz_ai,
    generate_quiz_ai_background,
    get_cached_gemini_keys,
    get_task_status,
    process_document_background,
    router,
    serve_image,
    upload_document,
)
from services.firebase_service import get_db  # noqa: F401
from services.r2_service import extract_image_keys_from_data, get_stored_image

__all__ = [
    "router",
    "get_db",
    "get_stored_image",
    "extract_image_keys_from_data",
    "GenerateQuizRequest",
    "generate_quiz_ai_background",
    "process_document_background",
    "upload_document",
    "generate_quiz_ai",
    "get_task_status",
    "serve_image",
    "download_sample_docx",
    "get_cached_gemini_keys",
]
