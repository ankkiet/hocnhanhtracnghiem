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

    # Thư mục hệ thống
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    TEMPLATES_DIR: str = str(BASE_DIR / "templates")
    UPLOADS_DIR: str = str(BASE_DIR / "uploads")

    # SEO & Tên miền chính thức
    CANONICAL_DOMAIN: str = "https://hocnhanhtn.online"

    # =========================================================================
    # CẤU HÌNH CORS (Cross-Origin Resource Sharing) AN TOÀN THEO MÔI TRƯỜNG
    # =========================================================================
    @property
    def CORS_ALLOW_ORIGINS(self) -> List[str]:
        """Danh sách origins được phép truy cập theo từng môi trường."""
        # 1. Nếu có cấu hình tùy biến từ biến môi trường thì luôn ưu tiên cao nhất
        env_origins = os.getenv("CORS_ALLOWED_ORIGINS") or os.getenv("CORS_ORIGINS")
        if env_origins:
            return [o.strip() for o in env_origins.split(",") if o.strip()]

        # 2. Môi trường Production: Khóa chặt, chỉ cho phép các domain chính thức của hệ thống
        if self.is_production:
            return [
                "https://hocnhanhtn.online",
                "https://www.hocnhanhtn.online",
                "https://hocnhanhtn.pages.dev",
                "https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app",
            ]

        # 3. Môi trường Staging / Pre-release
        if self.is_staging:
            return [
                "https://staging.hocnhanhtn.online",
                "https://hocnhanhtn.pages.dev",
                "https://hocnhanhtn.online",
                "https://www.hocnhanhtn.online",
                "https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app",
            ]

        # 4. Môi trường Development / Localhost: Hỗ trợ các cổng dev thông dụng
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
        """Biểu thức chính quy cho origin hợp lệ (preview deployment hoặc dynamic port)."""
        if self.is_staging:
            # Cho phép các preview deployments của Cloudflare Pages: https://<hash>.hocnhanhtn.pages.dev
            return r"^https:\/\/([a-zA-Z0-9-]+\.)?hocnhanhtn\.pages\.dev$"
        if self.is_development:
            # Cho phép mọi cổng dev và IP mạng nội bộ (LAN) khi thử nghiệm trên điện thoại/máy cùng mạng
            return r"^https?:\/\/(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?$"
        return None

    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    CORS_EXPOSE_HEADERS: List[str] = ["*"]


settings = Settings()
