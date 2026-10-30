"""
App Factory module for HocNhanhTN.
Chịu trách nhiệm khởi tạo, cấu hình Middleware, CORS, Routers và Static Files cho FastAPI.
"""

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import register_routes
from app.config.cors import setup_cors
from app.config.logging import get_logger, setup_logging
from app.config.settings import settings, setup_system_environment
from services.firebase_service import init_firebase


def create_app() -> FastAPI:
    """App Factory: Khởi tạo và cấu hình hoàn chỉnh ứng dụng FastAPI."""
    # 1. Khởi tạo môi trường & Logging
    setup_system_environment()
    setup_logging()
    logger = get_logger("app_factory")

    # 2. Khởi tạo kết nối Firebase Firestore an toàn
    init_firebase()

    # 3. Khởi tạo thực thể FastAPI
    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
    )

    # 4. Cấu hình Middleware CORS an toàn theo môi trường
    setup_cors(app)

    # 5. Đăng ký toàn bộ feature routes
    register_routes(app)

    # 6. Gắn thư mục tài nguyên tĩnh (Static Files cho Frontend)
    if os.path.exists(settings.STATIC_DIR):
        app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static_dir")

    if os.path.exists(settings.TEMPLATES_DIR):
        app.mount("/", StaticFiles(directory=settings.TEMPLATES_DIR, html=True), name="static")

    logger.info(
        f"FastAPI application instance created successfully. "
        f"Environment: {settings.ENVIRONMENT}, "
        f"CORS origins configured: {len(settings.CORS_ALLOW_ORIGINS)} allowed."
    )
    return app
