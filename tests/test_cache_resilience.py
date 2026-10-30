"""
Kiểm thử bộ nhớ đệm chống rò rỉ RAM (BoundedTTLCache)
và khả năng lưu trữ tác vụ nền bền vững (PersistentTaskStore & DistributedCacheManager).
"""

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from core.cache import BoundedTTLCache, DistributedCacheManager
from services.task_service import TASK_CACHE_DIR, PersistentTaskStore


class TestCacheResilience(unittest.TestCase):
    """Bộ kiểm thử cho BoundedTTLCache, Task Persistence và Distributed Cache."""

    def test_bounded_ttl_cache_lru_eviction(self):
        """1. Kiểm tra chính sách đào thải LRU khi đạt max_size."""
        cache = BoundedTTLCache(max_size=3, default_ttl=60, name="test_lru")
        
        # Thêm 3 phần tử: k1, k2, k3
        cache["k1"] = "v1"
        cache["k2"] = "v2"
        cache["k3"] = "v3"
        self.assertEqual(len(cache), 3)

        # Truy cập k1 -> k1 trở thành Recently Used nhất; k2 trở thành Least Recently Used
        _ = cache["k1"]

        # Thêm k4 -> vượt quá max_size (3) -> k2 phải bị đào thải
        cache["k4"] = "v4"
        self.assertEqual(len(cache), 3)
        self.assertIn("k1", cache)
        self.assertIn("k3", cache)
        self.assertIn("k4", cache)
        self.assertNotIn("k2", cache)

    def test_bounded_ttl_cache_expiration(self):
        """2. Kiểm tra tự động hết hạn và thu hồi TTL."""
        cache = BoundedTTLCache(max_size=10, default_ttl=1, name="test_ttl")
        
        cache.set("short_lived", "data_1", ttl=1)
        cache.set("long_lived", "data_2", ttl=60)

        # Ngay sau khi lưu: cả hai còn hạn
        self.assertEqual(cache.get("short_lived"), "data_1")
        self.assertEqual(cache.get("long_lived"), "data_2")

        # Đợi 1.1s để short_lived hết hạn
        time.sleep(1.1)

        # short_lived phải tự động biến mất và trả về default
        self.assertIsNone(cache.get("short_lived"))
        self.assertNotIn("short_lived", cache)
        self.assertEqual(cache.get("long_lived"), "data_2")

        # Kiểm tra hàm prune_expired
        pruned = cache.prune_expired()
        self.assertIsInstance(pruned, int)

    def test_persistent_task_store_survives_ram_clear(self):
        """3. Kiểm tra tính bền vững của TaskStore (sống sót qua server restart / RAM drop)."""
        store = PersistentTaskStore(max_size=10, default_ttl=300)
        task_id = "test_task_durability_999"
        payload = {"status": "completed", "quiz_id": "quiz_abc", "questions_count": 40}

        # Lưu task vào store
        store[task_id] = payload
        
        # Xác minh file disk đã được tạo
        disk_path = os.path.join(TASK_CACHE_DIR, f"{task_id}.json")
        self.assertTrue(os.path.exists(disk_path), f"File {disk_path} phải được tạo trên ổ đĩa.")

        # Mô phỏng khởi động lại máy chủ (xóa sạch RAM của store)
        store._data.clear()
        store._expiry.clear()
        self.assertEqual(len(store._data), 0, "RAM store đã bị xóa sạch.")

        # Truy xuất lại: TaskStore phải tự động nạp từ đĩa
        recovered = store[task_id]
        self.assertEqual(recovered["status"], "completed")
        self.assertEqual(recovered["quiz_id"], "quiz_abc")
        self.assertEqual(recovered["questions_count"], 40)

        # Xóa task và kiểm tra dọn đĩa
        del store[task_id]
        self.assertFalse(os.path.exists(disk_path), "File task trên đĩa phải được xóa khi xóa khỏi store.")

    def test_distributed_cache_manager_local_fallback(self):
        """4. Kiểm tra fallback an toàn khi không có Redis URL."""
        with patch.dict(os.environ, {"REDIS_URL": ""}):
            mgr = DistributedCacheManager()
            self.assertFalse(mgr.is_redis_active())
            self.assertIsNone(mgr.get_redis_client())
            self.assertIsNone(mgr.get_json("any_key"))
            self.assertFalse(mgr.set_json("any_key", {"a": 1}))

    def test_distributed_cache_manager_with_mock_redis(self):
        """5. Kiểm tra hoạt động đọc/ghi JSON khi Redis kết nối thành công."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = '{"cached_title": "Đề kiểm tra 1 tiết"}'

        with patch("core.cache.redis") as mock_redis_mod:
            mock_redis_mod.from_url.return_value = mock_redis
            with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}):
                mgr = DistributedCacheManager()
                self.assertTrue(mgr.is_redis_active())
                
                # Test get_json
                res = mgr.get_json("quiz:123")
                self.assertEqual(res, {"cached_title": "Đề kiểm tra 1 tiết"})
                mock_redis.get.assert_called_with("quiz:123")

                # Test set_json
                ok = mgr.set_json("quiz:123", {"foo": "bar"}, ttl_seconds=60)
                self.assertTrue(ok)
                mock_redis.set.assert_called_once()


if __name__ == "__main__":
    unittest.main()
