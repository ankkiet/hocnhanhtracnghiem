"""
API Router Aggregator for HocNhanhTN.
Đăng ký toàn bộ các API & Web routers vào ứng dụng FastAPI.
"""

from fastapi import FastAPI

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.document import router as document_router
from app.api.routes.health import router as health_router
from app.api.routes.pages import router as pages_router
from app.api.routes.quiz import router as quiz_router
from app.api.routes.student import router as student_router
from app.api.routes.teacher import router as teacher_router


def register_routes(app: FastAPI) -> None:
    """Đăng ký toàn bộ routes vào ứng dụng FastAPI."""
    # 1. API routers nghiệp vụ
    app.include_router(auth_router)
    app.include_router(quiz_router)
    app.include_router(student_router)
    app.include_router(teacher_router)
    app.include_router(admin_router)
    app.include_router(document_router)

    # 2. Uptime & Health Check
    app.include_router(health_router)

    # 3. Giao diện Web, SEO Metadata & Static Routes
    app.include_router(pages_router)
