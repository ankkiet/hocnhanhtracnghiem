"""
Core FastAPI Dependencies for HocNhanhTN.
Cung cấp dependency injection cho RateLimiter, database client và user authorization.
"""

from typing import Any, Dict, Optional, Tuple

from fastapi import Header, HTTPException, Query, Request

from app.utils.security import (
    get_user_from_token,
    verify_admin_access,
    verify_teacher_access,
)
from core.rate_limiter import RateLimiter, clear_rate_limits
from services.firebase_service import get_db

__all__ = [
    "RateLimiter",
    "clear_rate_limits",
    "get_db",
    "get_current_user",
    "get_current_teacher",
    "get_current_admin",
]


def _extract_token_from_request(
    authorization: Optional[str] = Header(None),
    token_param: Optional[str] = Query(None, alias="token"),
    teacher_token: Optional[str] = Query(None, alias="teacher_token"),
    student_token: Optional[str] = Query(None, alias="student_token"),
    admin_token: Optional[str] = Query(None, alias="admin_token"),
) -> Optional[str]:
    """Trích xuất token từ Authorization Header (Bearer) hoặc URL query parameter."""
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return authorization
    return teacher_token or admin_token or student_token or token_param


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Dependency: Xác thực người dùng hiện tại từ token."""
    raw_token = _extract_token_from_request(authorization=authorization, token_param=token)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Yêu cầu token xác thực.")
        
    db = get_db()
    user = get_user_from_token(raw_token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn.")
    return user


async def get_current_teacher(
    request: Request,
    authorization: Optional[str] = Header(None),
    teacher_token: Optional[str] = Query(None),
) -> Tuple[Dict[str, Any], str]:
    """Dependency: Xác thực quyền Giáo viên (hoặc Quản trị viên)."""
    raw_token = _extract_token_from_request(authorization=authorization, teacher_token=teacher_token)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Yêu cầu token giáo viên.")
        
    db = get_db()
    return verify_teacher_access(raw_token, db)


async def get_current_admin(
    request: Request,
    authorization: Optional[str] = Header(None),
    admin_token: Optional[str] = Query(None),
) -> Tuple[Dict[str, Any], str]:
    """Dependency: Xác thực quyền Quản trị viên (Admin)."""
    raw_token = _extract_token_from_request(authorization=authorization, admin_token=admin_token)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Yêu cầu token quản trị viên.")
        
    db = get_db()
    return verify_admin_access(raw_token, db)
