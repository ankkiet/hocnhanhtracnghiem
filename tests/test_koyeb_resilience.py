import unittest
from unittest.mock import MagicMock

from core.security import create_access_token, get_user_from_token
from core.state import QUIZ_CACHE, USER_CACHE
from services.firebase_service import execute_with_firebase_retry, get_db, reconnect_firebase


class TestKoyebResilience(unittest.TestCase):
    """Kiểm thử tính bền vững và khả năng tự phục hồi (Self-Healing) trên môi trường Koyeb."""

    def setUp(self):
        USER_CACHE.clear()
        QUIZ_CACHE.clear()

    def test_jwt_fallback_when_firestore_fails(self):
        """Kiểm tra: Khi Firestore bị lỗi (403/timeout), JWT Token hợp lệ vẫn xác thực người dùng thành công."""
        token_payload = {
            "sub": "user_teacher_999",
            "username": "giaovien@test.com",
            "role": "teacher",
            "full_name": "Thầy Giáo Test"
        }
        token = create_access_token(token_payload)

        # Giả lập db bị lỗi ném exception PermissionDenied / 403
        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.get.side_effect = Exception("403 PermissionDenied: The request has invalid credentials")

        user = get_user_from_token(token, mock_db)
        self.assertIsNotNone(user, "User không được là None khi JWT hợp lệ!")
        self.assertEqual(user['role'], 'teacher')
        self.assertEqual(user['username'], 'giaovien@test.com')
        self.assertEqual(user['id'], 'user_teacher_999')

    def test_reconnect_firebase_execution(self):
        """Kiểm tra: Hàm reconnect_firebase chạy an toàn và không gây crash."""
        new_db = reconnect_firebase()
        # Nếu có file credentials hợp lệ thì trả về db, không thì an toàn
        self.assertTrue(new_db is not None or get_db() is None)

    def test_execute_with_retry(self):
        """Kiểm tra: execute_with_firebase_retry tự động phục hồi khi gặp lỗi 403 lần đầu."""
        attempts = [0]

        def flaky_query(db_inst):
            attempts[0] += 1
            if attempts[0] == 1:
                raise Exception("403 PermissionDenied: Token expired")
            return "SUCCESS_DATA"

        result = execute_with_firebase_retry(flaky_query)
        self.assertEqual(result, "SUCCESS_DATA")
        self.assertEqual(attempts[0], 2, "Hàm phải được retry đúng 2 lần!")


if __name__ == '__main__':
    unittest.main()
