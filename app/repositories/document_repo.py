"""
Document & Task Repository for HocNhanhTN.
Quản lý lưu vết tiến trình trích xuất tài liệu (Word, PDF) và tác vụ nền.
"""

from typing import Any, Dict, Optional

from app.repositories.base_repo import BaseRepository
from core.state import active_tasks


class DocumentRepository(BaseRepository):
    """Repository quản lý các tác vụ nền trích xuất tài liệu."""

    def save_task(self, task_id: str, data: Dict[str, Any]) -> None:
        """Lưu hoặc cập nhật trạng thái tác vụ nền."""
        active_tasks[task_id] = data

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Lấy trạng thái tác vụ nền từ Persistent Task Store."""
        try:
            return active_tasks[task_id]
        except KeyError:
            return None

    def delete_task(self, task_id: str) -> None:
        """Xóa tác vụ nền."""
        active_tasks.pop(task_id, None)


document_repo = DocumentRepository()
