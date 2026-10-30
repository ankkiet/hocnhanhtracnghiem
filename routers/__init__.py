"""
Routers module for HocNhanhTN.
Quản lý và đăng ký toàn bộ feature routers của hệ thống.
"""

from fastapi import FastAPI

from routers.admin import router as admin_router
from routers.auth import router as auth_router
from routers.document import router as document_router
from routers.health import router as health_router
from routers.pages import router as pages_router
from routers.quiz import router as quiz_router
from routers.student import router as student_router
from routers.teacher import router as teacher_router

__all__ = [
    "auth_router",
    "quiz_router",
    "student_router",
    "teacher_router",
    "admin_router",
    "document_router",
    "health_router",
    "pages_router",
    "register_routers"
]


def register_routers(app: FastAPI) -> None:
    """Đăng ký toàn bộ các API & Web router vào ứng dụng FastAPI."""
    # 1. API routers nghiệp vụ
    app.include_router(auth_router)
    app.include_router(quiz_router)
    app.include_router(student_router)
    app.include_router(teacher_router)
    app.include_router(admin_router)
    app.include_router(document_router)

    # 2. Hệ thống, Uptime & Health Check
    app.include_router(health_router)

    # 3. Giao diện Web, SEO Metadata & Static Routes
    app.include_router(pages_router)
