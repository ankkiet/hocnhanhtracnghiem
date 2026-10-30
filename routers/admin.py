"""
Admin Router for HocNhanhTN (Backward Compatibility Shim).
Forwards to app.api.routes.admin and app.schemas.admin.
"""

from app.api.routes.admin import get_gemini_stats, ping_gemini_key, router
from app.schemas.admin import (  # noqa: F401
    ApproveUserRequest,
    ChangePasswordRequest,
    ResetPasswordRequest,
    SetApiKeyRequest,
    SetGoogleClientIdRequest,
)
from app.utils.security import verify_admin_access  # noqa: F401
from services.firebase_service import get_db  # noqa: F401

__all__ = [
    "router",
    "get_db",
    "verify_admin_access",
    "SetApiKeyRequest",
    "ApproveUserRequest",
    "get_gemini_stats",
    "ping_gemini_key",
]
