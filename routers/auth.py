"""
Auth Router for HocNhanhTN (Backward Compatibility Shim).
Forwards to app.api.routes.auth and app.schemas.auth.
"""

from app.api.routes.auth import (
    GoogleAuthRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    SelectRoleRequest,
    check_approval_status,
    get_auth_config,
    get_current_google_client_id,
    get_current_user_profile,
    get_db,
    google_login,
    login,
    refresh_token,
    register,
    router,
    select_role,
    verify_google_payload,
)
from app.schemas.auth import RoleSelectionRequest  # noqa: F401

__all__ = [
    "router",
    "get_db",
    "RegisterRequest",
    "LoginRequest",
    "RefreshTokenRequest",
    "GoogleAuthRequest",
    "SelectRoleRequest",
    "RoleSelectionRequest",
    "get_auth_config",
    "google_login",
    "select_role",
    "check_approval_status",
    "get_current_user_profile",
    "register",
    "login",
    "refresh_token",
    "get_current_google_client_id",
    "verify_google_payload",
]
