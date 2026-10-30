"""
API Routes package.
"""

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.document import router as document_router
from app.api.routes.health import router as health_router
from app.api.routes.pages import router as pages_router
from app.api.routes.quiz import router as quiz_router
from app.api.routes.student import router as student_router
from app.api.routes.teacher import router as teacher_router

__all__ = [
    "auth_router",
    "quiz_router",
    "student_router",
    "teacher_router",
    "admin_router",
    "document_router",
    "health_router",
    "pages_router",
]
