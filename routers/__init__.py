"""
Routers module for HocNhanhTN.
Quản lý và đăng ký toàn bộ feature routers của hệ thống.
Forwards to app.api.router for backward compatibility.
"""

from fastapi import FastAPI

from app.api.router import register_routes
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
    "register_routers",
]


def register_routers(app: FastAPI) -> None:
    """Đăng ký toàn bộ các API & Web router vào ứng dụng FastAPI."""
    register_routes(app)
