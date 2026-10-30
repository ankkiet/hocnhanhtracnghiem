"""
Quiz Repository for HocNhanhTN.
Quản lý truy xuất và lưu trữ đề thi trong Firestore kèm cơ chế Cache tiết kiệm Quota.
"""

import time
from typing import Any, Dict, List, Optional

from app.config.logging import get_logger
from app.repositories.base_repo import BaseRepository
from core.state import QUIZ_CACHE

logger = get_logger(__name__)


class QuizRepository(BaseRepository):
    """Repository quản lý dữ liệu đề thi (Quizzes)."""

    def get_quiz_by_id(self, quiz_id: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Lấy thông tin đề thi theo ID, ưu tiên cache RAM nếu use_cache=True."""
        now = time.time()
        if use_cache and quiz_id in QUIZ_CACHE and (now - QUIZ_CACHE[quiz_id]['time'] < 60):
            return QUIZ_CACHE[quiz_id]['data']

        col = self.get_collection('quizzes')
        if col is None:
            return None

        doc = col.document(quiz_id).get()
        if not doc.exists:
            return None

        quiz_data = doc.to_dict()
        QUIZ_CACHE[quiz_id] = {'time': now, 'data': quiz_data}
        return quiz_data

    def save_quiz(self, quiz_id: str, data: Dict[str, Any]) -> None:
        """Tạo mới hoặc cập nhật đề thi vào Firestore và làm mới cache."""
        col = self.get_collection('quizzes')
        if col is None:
            raise RuntimeError("Chưa kết nối CSDL Firebase")

        col.document(quiz_id).set(data)
        QUIZ_CACHE[quiz_id] = {'time': time.time(), 'data': data}

    def update_quiz(self, quiz_id: str, updates: Dict[str, Any]) -> None:
        """Cập nhật một phần thuộc tính đề thi."""
        col = self.get_collection('quizzes')
        if col is None:
            raise RuntimeError("Chưa kết nối CSDL Firebase")

        col.document(quiz_id).update(updates)
        if quiz_id in QUIZ_CACHE:
            QUIZ_CACHE[quiz_id]['data'].update(updates)
            QUIZ_CACHE[quiz_id]['time'] = time.time()

    def delete_quiz(self, quiz_id: str) -> None:
        """Xóa vĩnh viễn đề thi khỏi Firestore."""
        col = self.get_collection('quizzes')
        if col is None:
            raise RuntimeError("Chưa kết nối CSDL Firebase")

        col.document(quiz_id).delete()
        QUIZ_CACHE.pop(quiz_id, None)

    def get_quizzes_by_creator(self, creator_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách đề thi theo ID giáo viên tạo."""
        col = self.get_collection('quizzes')
        if col is None:
            return []

        docs = col.where('creator_id', '==', creator_id).stream()
        res = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            res.append(item)
        return res


quiz_repo = QuizRepository()
