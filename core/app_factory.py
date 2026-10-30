import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import settings, setup_system_environment
from core.logging_config import get_logger, setup_logging
from routers import register_routers
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

    # 4. Cấu hình Middleware (CORS phân chia an toàn theo môi trường dev / staging / production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_origin_regex=settings.CORS_ALLOW_ORIGIN_REGEX,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
        expose_headers=settings.CORS_EXPOSE_HEADERS,
        max_age=600,
    )

    # 5. Đăng ký toàn bộ feature routers (Auth, Quiz, Student, Teacher, Admin, Document, Health, Pages/SEO)
    register_routers(app)

    # 6. Gắn thư mục tài nguyên tĩnh (Static Files cho Frontend)
    if os.path.exists(settings.TEMPLATES_DIR):
        app.mount("/", StaticFiles(directory=settings.TEMPLATES_DIR, html=True), name="static")

    logger.info(
        f"FastAPI application instance created successfully. "
        f"Environment: {settings.ENVIRONMENT}, "
        f"CORS origins configured: {len(settings.CORS_ALLOW_ORIGINS)} allowed."
    )
    return app
