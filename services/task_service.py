"""
Task Service for HocNhanhTN.
Cung cấp business logic cho việc tạo lập, theo dõi và dọn dẹp các background tasks.
"""

import time
from typing import Any, Dict, Optional

from core.logging_config import get_logger
from core.state import active_tasks, task_store  # noqa: F401
from core.task_store import TASK_CACHE_DIR, PersistentTaskStore  # noqa: F401  # Re-export for compatibility

logger = get_logger(__name__)


class TaskService:
    """Service tiện ích quản lý Task."""

    def __init__(self, store: Optional[PersistentTaskStore] = None):
        self.store = store if store is not None else active_tasks

    def create_task(self, task_id: str, status: str = "pending", message: str = "") -> Dict[str, Any]:
        task_data = {"status": status, "message": message, "created_at": time.time()}
        self.store[task_id] = task_data
        return task_data

    def update_task(self, task_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        current = self.get_task(task_id)
        if current is None:
            current = {"created_at": time.time()}
        current.update(kwargs)
        current["updated_at"] = time.time()
        self.store[task_id] = current
        return current

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            return self.store[task_id]
        except KeyError:
            return None

    def delete_task(self, task_id: str) -> None:
        self.store.pop(task_id, None)


task_service = TaskService()
