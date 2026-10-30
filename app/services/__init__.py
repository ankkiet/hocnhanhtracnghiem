"""
Services package.
"""

from app.services.admin_service import AdminService, admin_service
from app.services.ai_service import (
    call_gemini_with_fallback,
    generate_mcq_from_pdf,
    generate_mcq_with_gemini,
)
from app.services.auth_service import AuthService, auth_service
from app.services.cache_service import CacheService, cache_service
from app.services.document_service import DocumentService, document_service
from app.services.firebase_service import get_db, init_firebase
from app.services.quiz_service import QuizService, quiz_service
from app.services.storage_service import storage_service
from app.services.student_service import StudentService, student_service
from app.services.teacher_service import TeacherService, teacher_service

__all__ = [
    "AuthService",
    "auth_service",
    "QuizService",
    "quiz_service",
    "StudentService",
    "student_service",
    "TeacherService",
    "teacher_service",
    "AdminService",
    "admin_service",
    "DocumentService",
    "document_service",
    "call_gemini_with_fallback",
    "generate_mcq_with_gemini",
    "generate_mcq_from_pdf",
    "storage_service",
    "CacheService",
    "cache_service",
    "get_db",
    "init_firebase",
]
