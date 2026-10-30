"""
Services module for HocNhanhTN.
Chứa các lớp dịch vụ (Service Layer) đóng gói logic nghiệp vụ và tương tác với các hệ thống bên ngoài:
- firebase_service: Kết nối và quản trị Firestore, cơ chế Self-Healing.
- storage_service: Lưu trữ đa tầng Cloudflare R2 + Local Cache với Retry & Fallback.
- auth_service: Nghiệp vụ xác thực người dùng, Google OAuth, phân quyền Role, JWT Access/Refresh tokens.
- quiz_service: Nghiệp vụ lưu trữ, bảo mật Anti-Cheat đề thi, Stale Cache Fallback.
- ai_service: Tương tác mô hình AI Google Gemini, xoay vòng API Keys và phân tích đề.
- exam_session_service: Quản lý phiên thi, xác thực mốc thời gian Server-side, chống nộp lặp lại, giám sát gian lận.
- audit_service: Ghi vết kiểm toán các thao tác nhạy cảm của hệ thống và quản trị viên.
"""

from services.ai_service import ai_service
from services.audit_service import audit_service
from services.auth_service import auth_service
from services.exam_session_service import exam_session_service
from services.firebase_service import get_db, init_firebase
from services.quiz_service import quiz_service
from services.storage_service import storage_service

__all__ = [
    "init_firebase",
    "get_db",
    "storage_service",
    "quiz_service",
    "auth_service",
    "ai_service",
    "exam_session_service",
    "audit_service"
]
