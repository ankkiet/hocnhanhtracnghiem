"""
Application Settings & Environment Configuration for HocNhanhTN.
Hỗ trợ đa môi trường: development / staging / production.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional


def setup_system_environment() -> None:
    """Thiết lập các biến môi trường hệ thống & mã hóa ký tự chuẩn UTF-8."""
    # Cấu hình gRPC KeepAlive chống rớt mạng / idle timeout trên Koyeb / Docker Cloud
    os.environ.setdefault("GRPC_ARG_KEEPALIVE_TIME_MS", "30000")       # Ping mỗi 30 giây
    os.environ.setdefault("GRPC_ARG_KEEPALIVE_TIMEOUT_MS", "10000")    # Timeout 10 giây
    os.environ.setdefault("GRPC_ARG_KEEPALIVE_PERMIT_WITHOUT_CALLS", "1")
    os.environ.setdefault("GRPC_ARG_HTTP2_MAX_PINGS_WITHOUT_DATA", "0")
    os.environ.setdefault("GRPC_ARG_HTTP2_MIN_TIME_BETWEEN_PINGS_MS", "10000")
    os.environ.setdefault("GRPC_ARG_HTTP2_MIN_PING_INTERVAL_WITHOUT_DATA_MS", "5000")
    os.environ.setdefault("GRPC_ENABLE_FORK_SUPPORT", "1")

    # Đảm bảo mã hóa UTF-8 cho Windows console
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, 'reconfigure'):
                getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
            if hasattr(sys.stderr, 'reconfigure'):
                getattr(sys.stderr, 'reconfigure')(encoding='utf-8')
        except Exception:
            pass


# Thực hiện thiết lập môi trường ngay khi nạp module
setup_system_environment()


class Settings:
    """Cấu hình tập trung cho toàn bộ ứng dụng HocNhanhTN."""

    # Thông tin ứng dụng
    APP_TITLE: str = "HocNhanhTN - Hệ thống học nhanh trắc nghiệm cho học sinh & giáo viên"
    APP_DESCRIPTION: str = (
        "Hệ thống học nhanh trắc nghiệm cho học sinh & giáo viên - "
        "Hỗ trợ tải lên file Word, PDF, tự động bóc tách và tạo đề thi trắc nghiệm AI."
    )
    APP_VERSION: str = "2.0"

    # Máy chủ & Môi trường
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    @property
    def ENVIRONMENT(self) -> str:
        return os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).strip().lower()

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT in ("production", "prod")

    @property
    def is_staging(self) -> bool:
        return self.ENVIRONMENT in ("staging", "stage")

    @property
    def is_development(self) -> bool:
        return not (self.is_production or self.is_staging)

    @property
    def RELOAD(self) -> bool:
        return self.is_development

    # Thư mục hệ thống (project root)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    TEMPLATES_DIR: str = str(BASE_DIR / "templates")
    STATIC_DIR: str = str(BASE_DIR / "static")
    UPLOADS_DIR: str = str(BASE_DIR / "uploads")

    # SEO & Tên miền chính thức
    CANONICAL_DOMAIN: str = "https://hocnhanhtn.online"

    # Bảo mật JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "hocnhanhtracnghiem-super-secret-key-2026-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200"))  # 30 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))

    # External services credentials
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    FIREBASE_CREDENTIALS_PATH: str = os.getenv(
        "FIREBASE_CREDENTIALS_PATH",
        str(BASE_DIR / "firebase-adminsdk.json")
    )
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL", None)

    # Cloudflare R2
    R2_ENDPOINT_URL: str = os.getenv("R2_ENDPOINT_URL", "")
    R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "hocnhanhtn-storage")
    R2_PUBLIC_URL: str = os.getenv("R2_PUBLIC_URL", "")

    # CORS origins list
    @property
    def CORS_ALLOW_ORIGINS(self) -> List[str]:
        """Danh sách origins được phép truy cập theo từng môi trường."""
        env_origins = os.getenv("CORS_ALLOWED_ORIGINS") or os.getenv("CORS_ORIGINS")
        if env_origins:
            return [o.strip() for o in env_origins.split(",") if o.strip()]

        if self.is_production:
            return [
                "https://hocnhanhtn.online",
                "https://www.hocnhanhtn.online",
                "https://hocnhanhtn.pages.dev",
                "https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app",
            ]

        if self.is_staging:
            return [
                "https://staging.hocnhanhtn.online",
                "https://hocnhanhtn.pages.dev",
                "https://hocnhanhtn.online",
                "https://www.hocnhanhtn.online",
                "https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app",
            ]

        # Development
        return [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5500",
            "http://127.0.0.1:5500",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "https://hocnhanhtn.online",
            "https://hocnhanhtn.pages.dev",
        ]

    @property
    def CORS_ALLOW_ORIGIN_REGEX(self) -> Optional[str]:
        if self.is_staging:
            return r"^https:\/\/([a-zA-Z0-9-]+\.)?hocnhanhtn\.pages\.dev$"
        if self.is_development:
            return r"^https?:\/\/(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?$"
        return None

    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    CORS_EXPOSE_HEADERS: List[str] = ["*"]


settings = Settings()
