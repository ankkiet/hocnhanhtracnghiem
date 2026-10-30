"""
Document Processing & Quiz Generation Service for HocNhanhTN.
Chịu trách nhiệm: Điều phối bóc tách Word/PDF, xử lý ảnh công thức Toán,
quản lý tác vụ nền và kích hoạt Gemini AI tạo câu hỏi trắc nghiệm.
"""

import os
import uuid
from typing import Any, Dict

from fastapi import HTTPException, UploadFile

from app.config.logging import get_logger
from app.config.settings import settings
from app.repositories.document_repo import DocumentRepository, document_repo

logger = get_logger(__name__)


class DocumentService:
    """Service xử lý tài liệu và tác vụ nền tạo đề."""

    def __init__(self, repository: DocumentRepository = document_repo):
        self.repo = repository

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Lấy trạng thái xử lý tác vụ nền."""
        task = self.repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Không tìm thấy tiến trình xử lý.")
        return task

    def save_uploaded_file(self, file: UploadFile) -> Dict[str, Any]:
        """Lưu file tải lên vào thư mục tạm thời an toàn."""
        os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
        file_ext = os.path.splitext(file.filename or "")[1].lower()
        if file_ext not in ('.docx', '.pdf', '.txt'):
            raise HTTPException(
                status_code=400,
                detail="Định dạng tệp không được hỗ trợ. Vui lòng tải lên tệp .docx hoặc .pdf"
            )

        task_id = str(uuid.uuid4())
        safe_filename = f"{task_id}{file_ext}"
        saved_path = os.path.join(settings.UPLOADS_DIR, safe_filename)

        with open(saved_path, "wb") as f:
            content = file.file.read()
            f.write(content)

        task_init = {
            "status": "processing",
            "message": "Đang phân tích cấu trúc tài liệu...",
            "file_path": saved_path,
            "filename": file.filename,
            "file_ext": file_ext
        }
        self.repo.save_task(task_id, task_init)
        return {"status": "success", "task_id": task_id, "file_path": saved_path}


document_service = DocumentService()
