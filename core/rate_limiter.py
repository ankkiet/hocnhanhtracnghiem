import os
import sys
import threading
import time
from typing import Dict, List

from fastapi import HTTPException, Request

from core.logging_config import get_logger

logger = get_logger(__name__)

# Dictionary lưu trữ cửa sổ trượt: f"{prefix}:{ip}" -> List[float timestamps]
_RATE_LIMIT_STORAGE: Dict[str, List[float]] = {}
_LOCK = threading.Lock()

# Cho phép vô hiệu hóa bằng biến môi trường (tiện cho chạy unit test tải cao)
RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes")


def get_client_ip(request: Request) -> str:
    """Trích xuất địa chỉ IP thực tế của client, hỗ trợ reverse proxy (Nginx, Cloudflare)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


class RateLimiter:
    """
    FastAPI Dependency giới hạn tần suất gọi API (Sliding Window Rate Limiter).
    Ví dụ:
        @router.post("/login", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
    """

    def __init__(self, times: int = 10, seconds: int = 60, key_prefix: str = "default"):
        self.times = times
        self.seconds = seconds
        self.key_prefix = key_prefix

    async def __call__(self, request: Request):
        # Bỏ qua rate limit nếu bị tắt hoặc đang chạy trong unittest environment
        if not RATE_LIMIT_ENABLED or "unittest" in sys.modules or os.environ.get("TESTING") == "true":
            return

        ip = get_client_ip(request)
        key = f"{self.key_prefix}:{ip}"
        now = time.time()
        window_start = now - self.seconds

        with _LOCK:
            # 1. Dọn dẹp các mốc thời gian ngoài cửa sổ trượt
            timestamps = _RATE_LIMIT_STORAGE.get(key, [])
            valid_timestamps = [ts for ts in timestamps if ts > window_start]

            # 2. Kiểm tra giới hạn số lần gọi
            if len(valid_timestamps) >= self.times:
                oldest_ts = valid_timestamps[0]
                retry_after = max(1, int(oldest_ts + self.seconds - now))
                logger.warning(
                    f"RateLimiter: IP {ip} vượt quá giới hạn trên endpoint {request.url.path} "
                    f"({len(valid_timestamps)}/{self.times} trong {self.seconds}s)."
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Bạn đang thao tác quá nhanh. Vui lòng thử lại sau {retry_after} giây.",
                    headers={"Retry-After": str(retry_after)}
                )

            # 3. Ghi nhận mốc thời gian mới
            valid_timestamps.append(now)
            _RATE_LIMIT_STORAGE[key] = valid_timestamps


def clear_rate_limits():
    """Hàm tiện ích dọn sạch bộ nhớ đếm rate limit."""
    with _LOCK:
        _RATE_LIMIT_STORAGE.clear()
