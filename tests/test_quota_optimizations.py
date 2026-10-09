import unittest
import time
from unittest.mock import MagicMock
from core.state import USER_CACHE, SETTINGS_CACHE, QUIZ_CACHE, LEADERBOARD_CACHE, SUBMISSIONS_CACHE
from core.security import create_access_token, get_user_from_token, invalidate_user_cache

class TestQuotaOptimizations(unittest.TestCase):
    def setUp(self):
        USER_CACHE.clear()
        SETTINGS_CACHE.clear()
        QUIZ_CACHE.clear()
        LEADERBOARD_CACHE.clear()
        SUBMISSIONS_CACHE.clear()

    def test_user_cache_avoids_repeated_reads(self):
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.id = "user_123"
        mock_doc.to_dict.return_value = {
            "username": "teacher1",
            "role": "teacher",
            "status": "approved",
            "full_name": "Nguyen Van A"
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

        token = create_access_token({"sub": "user_123", "role": "teacher"})

        # Lần 1: Chưa có trong cache -> phải gọi Firestore get()
        u1 = get_user_from_token(token, mock_db)
        self.assertIsNotNone(u1)
        self.assertEqual(u1["id"], "user_123")
        self.assertEqual(mock_db.collection.return_value.document.return_value.get.call_count, 1)

        # Lần 2: Đã có trong cache -> KHÔNG được gọi Firestore get() nữa
        u2 = get_user_from_token(token, mock_db)
        self.assertIsNotNone(u2)
        self.assertEqual(u2["id"], "user_123")
        self.assertEqual(mock_db.collection.return_value.document.return_value.get.call_count, 1)

        # Invalidate cache -> Lần 3 phải gọi lại get()
        invalidate_user_cache("user_123")
        u3 = get_user_from_token(token, mock_db)
        self.assertIsNotNone(u3)
        self.assertEqual(mock_db.collection.return_value.document.return_value.get.call_count, 2)

    def test_settings_cache_functionality(self):
        from routers.document import get_cached_gemini_keys
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"api_keys": ["KEY_1", "KEY_2"]}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

        # Lần 1: gọi Firestore
        keys1 = get_cached_gemini_keys(mock_db)
        self.assertEqual(keys1, ["KEY_1", "KEY_2"])
        self.assertEqual(mock_db.collection.return_value.document.return_value.get.call_count, 1)

        # Lần 2: lấy từ cache
        keys2 = get_cached_gemini_keys(mock_db)
        self.assertEqual(keys2, ["KEY_1", "KEY_2"])
        self.assertEqual(mock_db.collection.return_value.document.return_value.get.call_count, 1)

if __name__ == '__main__':
    unittest.main()
