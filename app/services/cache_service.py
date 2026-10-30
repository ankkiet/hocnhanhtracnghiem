"""
Cache Service for HocNhanhTN.
Cung cấp bộ nhớ đệm phân tầng (RAM BoundedTTLCache + Distributed Redis Cache).
"""

from typing import Any, Optional

from core.cache import BoundedTTLCache, DistributedCacheManager, cache_manager


class CacheService:
    """Service tiện ích thao tác với bộ nhớ đệm (Cache)."""

    def __init__(self, manager: DistributedCacheManager = cache_manager):
        self.manager = manager

    def get_json(self, key: str) -> Optional[Any]:
        return self.manager.get_json(key)

    def set_json(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        return self.manager.set_json(key, value, ttl_seconds=ttl_seconds)

    def delete(self, key: str) -> bool:
        return self.manager.delete(key)

    def is_redis_active(self) -> bool:
        return self.manager.is_redis_active()

    def create_bounded_cache(self, max_size: int = 1000, default_ttl: int = 300, name: str = "cache") -> BoundedTTLCache:
        return BoundedTTLCache(max_size=max_size, default_ttl=default_ttl, name=name)


cache_service = CacheService()
