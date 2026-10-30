"""
Base Repository for HocNhanhTN.
Cung cấp kết nối Firebase Firestore an toàn và các tiện ích truy xuất chung.
"""

from typing import Any, Optional

from app.config.logging import get_logger

logger = get_logger(__name__)


class BaseRepository:
    """Lớp nền tảng cho mọi Repository trong hệ thống."""

    @property
    def db(self) -> Any:
        """Lấy instance Firestore Client hiện tại."""
        from services.firebase_service import get_db
        database = get_db()
        if database is None:
            logger.error("BaseRepository: Chưa kết nối hoặc mất kết nối tới Firebase Firestore.")
        return database

    def get_collection(self, collection_name: str) -> Optional[Any]:
        """Lấy Firestore Collection Reference an toàn."""
        database = self.db
        if database is None:
            return None
        return database.collection(collection_name)
