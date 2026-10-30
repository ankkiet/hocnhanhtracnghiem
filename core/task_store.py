"""
Persistent Task Store module for HocNhanhTN.
Two-tier storage (RAM cache + Disk persistence) for background tasks.
Lives in core/ so it doesn't depend on services, preventing circular imports.
"""

import json
import os
import threading
from typing import Any, Dict, Optional

from core.cache import BoundedTTLCache
from core.logging_config import get_logger

logger = get_logger(__name__)

# Thư mục lưu trữ bền vững trạng thái tác vụ nền
TASK_CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".cache", "tasks"))
os.makedirs(TASK_CACHE_DIR, exist_ok=True)


class PersistentTaskStore(BoundedTTLCache):
    """
    Bộ lưu trữ trạng thái Task hai tầng (Two-Tier Task Store):
    - Tầng 1: BoundedTTLCache trong RAM (tốc độ cao, TTL 15 phút, giới hạn 500 tasks).
    - Tầng 2: Tệp JSON bền vững trên ổ đĩa (.cache/tasks/{task_id}.json).
    
    Giải quyết triệt để rủi ro:
    1. Khi server/worker khởi động lại, các task đang xử lý hoặc vừa hoàn tất không bị mất.
    2. Khi scale ngang nhiều process/worker, worker khác vẫn có thể đọc trạng thái task từ ổ đĩa chia sẻ.
    3. Tự động thu hồi RAM và xóa file sau 15 phút để chống rò rỉ bộ nhớ.
    """

    def __init__(self, max_size: int = 500, default_ttl: int = 900):
        super().__init__(max_size=max_size, default_ttl=default_ttl, name="tasks")
        self._disk_lock = threading.Lock()

    def _get_disk_path(self, task_id: str) -> str:
        safe_id = "".join(c for c in str(task_id) if c.isalnum() or c in ("-", "_"))
        return os.path.join(TASK_CACHE_DIR, f"{safe_id}.json")

    def _save_to_disk(self, task_id: str, data: Any) -> None:
        try:
            path = self._get_disk_path(task_id)
            with self._disk_lock:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"TaskStore: Không thể lưu task {task_id} ra đĩa: {e}")

    def _read_from_disk(self, task_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_disk_path(task_id)
        if not os.path.exists(path):
            return None
        try:
            with self._disk_lock:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"TaskStore: Không thể đọc task {task_id} từ đĩa: {e}")
            return None

    def _remove_from_disk(self, task_id: str) -> None:
        path = self._get_disk_path(task_id)
        if os.path.exists(path):
            try:
                with self._disk_lock:
                    os.remove(path)
            except Exception:
                pass

    def __getitem__(self, key: Any) -> Any:
        try:
            return super().__getitem__(key)
        except KeyError:
            disk_data = self._read_from_disk(str(key))
            if disk_data is not None:
                super().set(key, disk_data, ttl=self.default_ttl)
                return disk_data
            raise KeyError(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self._save_to_disk(str(key), value)

    def set(self, key: Any, value: Any, ttl: Optional[int] = None) -> None:
        super().set(key, value, ttl=ttl)
        self._save_to_disk(str(key), value)

    def __contains__(self, key: Any) -> bool:
        if super().__contains__(key):
            return True
        return os.path.exists(self._get_disk_path(str(key)))

    def __delitem__(self, key: Any) -> None:
        super().__delitem__(key)
        self._remove_from_disk(str(key))

    def pop(self, key: Any, default: Any = None) -> Any:
        val = super().pop(key, default)
        self._remove_from_disk(str(key))
        return val

    def clear(self) -> None:
        super().clear()
        try:
            with self._disk_lock:
                for fname in os.listdir(TASK_CACHE_DIR):
                    if fname.endswith(".json"):
                        try:
                            os.remove(os.path.join(TASK_CACHE_DIR, fname))
                        except Exception:
                            pass
        except Exception:
            pass
