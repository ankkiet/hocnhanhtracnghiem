"""
User Repository for HocNhanhTN.
Quản lý truy xuất và lưu trữ tài khoản người dùng trong Firestore.
"""

from typing import Any, Dict, List, Optional

from app.repositories.base_repo import BaseRepository
from app.utils.security import check_and_assign_admin, invalidate_user_cache


class UserRepository(BaseRepository):
    """Repository quản lý dữ liệu người dùng (Users)."""

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin người dùng theo Firestore Document ID."""
        col = self.get_collection('users')
        if col is None:
            return None

        doc = col.document(user_id).get()
        if not doc.exists:
            return None

        user_data = doc.to_dict()
        user_data['id'] = doc.id
        return check_and_assign_admin(user_data)

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Tìm kiếm người dùng theo username."""
        col = self.get_collection('users')
        if col is None:
            return None

        docs = col.where('username', '==', username).limit(1).stream()
        for doc in docs:
            user_data = doc.to_dict()
            user_data['id'] = doc.id
            return check_and_assign_admin(user_data)
        return None

    def create_user(self, user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Tạo mới tài khoản người dùng."""
        col = self.get_collection('users')
        if col is None:
            raise RuntimeError("Chưa kết nối CSDL Firebase")

        col.document(user_id).set(user_data)
        invalidate_user_cache(user_id)
        user_data['id'] = user_id
        return user_data

    def update_user(self, user_id: str, updates: Dict[str, Any]) -> None:
        """Cập nhật thông tin tài khoản người dùng."""
        col = self.get_collection('users')
        if col is None:
            raise RuntimeError("Chưa kết nối CSDL Firebase")

        col.document(user_id).update(updates)
        invalidate_user_cache(user_id)

    def delete_user(self, user_id: str) -> None:
        """Xóa tài khoản người dùng."""
        col = self.get_collection('users')
        if col is None:
            raise RuntimeError("Chưa kết nối CSDL Firebase")

        col.document(user_id).delete()
        invalidate_user_cache(user_id)

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Lấy toàn bộ danh sách người dùng cho Quản trị viên."""
        col = self.get_collection('users')
        if col is None:
            return []

        users = []
        for doc in col.stream():
            u = doc.to_dict()
            u['id'] = doc.id
            users.append(check_and_assign_admin(u))
        return users


user_repo = UserRepository()
