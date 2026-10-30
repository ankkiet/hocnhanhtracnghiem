import json
import os
import threading
import time
from collections import OrderedDict
from collections.abc import MutableMapping
from typing import Any, Dict, Iterator, Optional

from core.logging_config import get_logger

logger = get_logger(__name__)

# Kiểm tra Redis driver (nếu có cài đặt)
try:
    import redis
except ImportError:
    redis = None


class BoundedTTLCache(MutableMapping):
    """
    Bộ nhớ đệm LRU đa luồng (Thread-safe) có giới hạn dung lượng tối đa và thời gian sống (TTL).
    Ngăn chặn hoàn toàn rủi ro Memory Leak và phình RAM khi hệ thống chạy thời gian dài.
    
    Đặc điểm:
    - Triển khai đầy đủ MutableMapping (tương thích 100% cú pháp dict: cache[k], k in cache, cache.get(), cache.pop()).
    - Chính sách đào thải LRU (Least Recently Used) khi đạt max_size.
    - Tự động xóa các mục đã hết hạn (TTL).
    - Bảo vệ đa luồng bằng RLock.
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300, name: str = "cache"):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.name = name
        self._data: OrderedDict = OrderedDict()
        self._expiry: Dict[str, float] = {}
        self._lock = threading.RLock()

    def _is_expired(self, key: str, now: float) -> bool:
        exp = self._expiry.get(key)
        return exp is not None and now > exp

    def __getitem__(self, key: Any) -> Any:
        with self._lock:
            key_str = str(key)
            now = time.time()
            if key_str not in self._data:
                raise KeyError(key)
            if self._is_expired(key_str, now):
                self._del_internal(key_str)
                raise KeyError(key)
            # Đưa lên đầu danh sách LRU (vừa được truy cập)
            self._data.move_to_end(key_str)
            return self._data[key_str]

    def __setitem__(self, key: Any, value: Any) -> None:
        self.set(key, value, ttl=self.default_ttl)

    def set(self, key: Any, value: Any, ttl: Optional[int] = None) -> None:
        """Lưu trữ dữ liệu vào cache với thời gian sống (TTL) tuỳ chỉnh."""
        with self._lock:
            key_str = str(key)
            now = time.time()
            item_ttl = ttl if ttl is not None else self.default_ttl
            
            if key_str in self._data:
                self._data.move_to_end(key_str)
            elif len(self._data) >= self.max_size:
                # Đào thải phần tử cũ nhất (LRU Eviction)
                oldest_key, _ = self._data.popitem(last=False)
                self._expiry.pop(oldest_key, None)
                logger.debug(f"BoundedTTLCache [{self.name}]: Đào thải LRU key '{oldest_key}' vì đạt max_size {self.max_size}.")

            self._data[key_str] = value
            self._expiry[key_str] = now + item_ttl

    def _del_internal(self, key_str: str) -> None:
        self._data.pop(key_str, None)
        self._expiry.pop(key_str, None)

    def __delitem__(self, key: Any) -> None:
        with self._lock:
            key_str = str(key)
            if key_str in self._data:
                self._del_internal(key_str)
            else:
                raise KeyError(key)

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            key_str = str(key)
            now = time.time()
            if key_str not in self._data:
                return False
            if self._is_expired(key_str, now):
                self._del_internal(key_str)
                return False
            return True

    def __iter__(self) -> Iterator[Any]:
        with self._lock:
            now = time.time()
            valid_keys = [k for k in self._data.keys() if not self._is_expired(k, now)]
            return iter(valid_keys)

    def __len__(self) -> int:
        with self._lock:
            now = time.time()
            return sum(1 for k in self._data.keys() if not self._is_expired(k, now))

    def get(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            try:
                return self[key]
            except KeyError:
                return default

    def pop(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            key_str = str(key)
            now = time.time()
            if key_str in self._data:
                if self._is_expired(key_str, now):
                    self._del_internal(key_str)
                    return default
                val = self._data.pop(key_str)
                self._expiry.pop(key_str, None)
                return val
            return default

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._expiry.clear()

    def prune_expired(self) -> int:
        """Chủ động dọn dẹp toàn bộ các khóa đã hết hạn để thu hồi RAM ngay lập tức."""
        with self._lock:
            now = time.time()
            expired_keys = [k for k, exp in self._expiry.items() if now > exp]
            for k in expired_keys:
                self._del_internal(k)
            if expired_keys:
                logger.debug(f"BoundedTTLCache [{self.name}]: Đã dọn dẹp {len(expired_keys)} khóa hết hạn.")
            return len(expired_keys)

    def copy(self) -> Dict[str, Any]:
        """Tạo bản sao từ điển các phần tử còn hạn."""
        with self._lock:
            now = time.time()
            return {k: v for k, v in self._data.items() if not self._is_expired(k, now)}

    def items(self) -> Any:  # type: ignore[override]
        with self._lock:
            now = time.time()
            return [(k, v) for k, v in self._data.items() if not self._is_expired(k, now)]


class DistributedCacheManager:
    """
    Quản trị Cache phân tán (Distributed Cache Manager).
    Hỗ trợ:
    1. Kết nối Redis khi có cấu hình REDIS_URL (phục vụ scale ngang nhiều instance/worker).
    2. Tự động Fallback sang BoundedTTLCache (bộ nhớ RAM có giới hạn) khi không có Redis hoặc mất kết nối.
    """

    def __init__(self):
        self.redis_url = os.environ.get("REDIS_URL", "").strip()
        self._redis_client = None
        self._is_redis_ready = False
        self._init_redis()

    def _init_redis(self):
        if not self.redis_url or redis is None:
            logger.info("CacheManager: Không cấu hình REDIS_URL hoặc chưa cài đặt thư viện redis. Sử dụng BoundedTTLCache cục bộ.")
            return
        try:
            self._redis_client = redis.from_url(
                self.redis_url,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
                decode_responses=True
            )
            self._redis_client.ping()
            self._is_redis_ready = True
            logger.info(f"CacheManager: Đã kết nối Redis phân tán thành công tại {self.redis_url.split('@')[-1]}!")
        except Exception as e:
            logger.warning(f"CacheManager: Không thể kết nối Redis ({e}). Tự động fallback về RAM BoundedTTLCache.")
            self._is_redis_ready = False

    def is_redis_active(self) -> bool:
        return self._is_redis_ready and self._redis_client is not None

    def get_redis_client(self):
        return self._redis_client if self.is_redis_active() else None

    def get_json(self, key: str) -> Optional[Any]:
        """Đọc đối tượng JSON từ Redis nếu khả dụng."""
        if self.is_redis_active() and self._redis_client is not None:
            try:
                raw = self._redis_client.get(key)
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.warning(f"CacheManager: Lỗi đọc Redis key '{key}': {e}")
        return None

    def set_json(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Ghi đối tượng JSON vào Redis nếu khả dụng."""
        if self.is_redis_active() and self._redis_client is not None:
            try:
                raw = json.dumps(value, ensure_ascii=False)
                self._redis_client.set(key, raw, ex=ttl_seconds)
                return True
            except Exception as e:
                logger.warning(f"CacheManager: Lỗi ghi Redis key '{key}': {e}")
        return False

    def delete(self, key: str) -> bool:
        if self.is_redis_active() and self._redis_client is not None:
            try:
                self._redis_client.delete(key)
                return True
            except Exception:
                pass
        return False


# Khởi tạo singleton manager
cache_manager = DistributedCacheManager()
