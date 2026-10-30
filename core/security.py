"""
Core Security for HocNhanhTN (Backward Compatibility Shim).
Forwards to app.utils.security.
"""

from app.utils.security import (
    ADMIN_EMAILS,
    ALGORITHM,
    SECRET_KEY,
    ACCESS_TOKEN_EXPIRE_DAYS,
    REFRESH_TOKEN_EXPIRE_DAYS,
    check_and_assign_admin,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_user_from_token,
    hash_password,
    invalidate_user_cache,
    is_legacy_hash,
    verify_admin_access,
    verify_password,
    verify_student_access,
    verify_teacher_access,
)

__all__ = [
    "SECRET_KEY",
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_DAYS",
    "REFRESH_TOKEN_EXPIRE_DAYS",
    "ADMIN_EMAILS",
    "hash_password",
    "verify_password",
    "is_legacy_hash",
    "create_access_token",
    "create_refresh_token",
    "decode_access_token",
    "decode_refresh_token",
    "get_user_from_token",
    "verify_teacher_access",
    "verify_student_access",
    "verify_admin_access",
    "invalidate_user_cache",
    "check_and_assign_admin",
]
