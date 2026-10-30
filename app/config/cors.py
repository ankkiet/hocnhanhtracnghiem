"""
CORS Configuration module for HocNhanhTN.
Cấu hình Cross-Origin Resource Sharing an toàn theo môi trường.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.logging import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


def setup_cors(app: FastAPI) -> None:
    """Đăng ký middleware CORS an toàn vào ứng dụng FastAPI."""
    origins = settings.CORS_ALLOW_ORIGINS
    origin_regex = settings.CORS_ALLOW_ORIGIN_REGEX

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=origin_regex,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
        expose_headers=settings.CORS_EXPOSE_HEADERS,
    )
    logger.info(
        f"CORS configured for environment '{settings.ENVIRONMENT}'. "
        f"Allowed origins: {len(origins)} entries. Origin regex: {bool(origin_regex)}"
    )
