"""
Authentication Router for HocNhanhTN.
Endpoint declarations for User Authentication, Registration, Role Selection, and Token Refresh.
"""

from typing import Optional

from fastapi import APIRouter, Depends

from app.core.dependencies import RateLimiter
from app.schemas.auth import (
    GoogleAuthRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    SelectRoleRequest,
)
from app.services.auth_service import auth_service
from services.firebase_service import get_db  # noqa: F401 (for test mocking compatibility)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/config", summary="Lấy cấu hình xác thực công khai")
async def get_auth_config():
    """Trả về các cấu hình frontend cần dùng, như Google Client ID."""
    client_id = auth_service.get_google_client_id()
    return {
        "status": "success",
        "google_client_id": client_id,
    }


@router.post("/google", summary="Đăng nhập hoặc đăng ký nhanh bằng Google")
async def google_login(req: GoogleAuthRequest):
    """
    Xác thực qua tài khoản Google.
    - Tài khoản Admin chỉ định luôn được cấp quyền Admin cao nhất.
    - Người dùng mới đăng nhập lần đầu sẽ phải chọn vai trò: Học sinh (dùng ngay) hoặc Giáo viên (chờ Admin duyệt).
    """
    return await auth_service.authenticate_google(
        credential=getattr(req, "credential", None),
        access_token=getattr(req, "access_token", None),
    )


@router.post("/select_role", summary="Chọn vai trò và cập nhật thông tin cá nhân")
async def select_role(req: SelectRoleRequest):
    """
    Xử lý cập nhật thông tin cá nhân (Tên, Lớp, SĐT, Trường) và vai trò sau đăng nhập Google:
    - Học sinh: Cấp quyền ngay (status=approved), trả về JWT Token.
    - Giáo viên: Đặt status=pending (Chờ Admin duyệt), không cấp quyền truy cập ngay.
    """
    return auth_service.select_role(
        user_id=getattr(req, "user_id", ""),
        role=getattr(req, "role", ""),
        full_name=getattr(req, "full_name", "") or "",
        class_name=getattr(req, "class_name", "") or "",
        phone=getattr(req, "phone", "") or "",
        school=getattr(req, "school", "") or "",
        extra_info=getattr(req, "extra_info", "") or "",
    )


@router.get("/check_approval_status", summary="Kiểm tra trạng thái duyệt tài khoản")
async def check_approval_status(user_id: str):
    """Kiểm tra tài khoản giáo viên đã được Admin duyệt hay chưa để kích hoạt ngay mà không cần đăng nhập lại."""
    return auth_service.check_approval_status(user_id=user_id)


@router.get("/me", summary="Lấy thông tin tài khoản hiện tại từ Token")
async def get_current_user_profile(token: Optional[str] = None):
    """
    Xác thực token người dùng, đảm bảo vai trò và trạng thái chính xác.
    Nếu tài khoản chưa hoàn tất chọn vai trò hoặc đang chờ duyệt, trả về trạng thái tương ứng.
    """
    return auth_service.get_user_profile(token=token)


@router.post(
    "/register",
    summary="Đăng ký tài khoản mới",
    dependencies=[Depends(RateLimiter(times=10, seconds=60, key_prefix="auth_reg"))],
)
async def register(req: RegisterRequest):
    """Đăng ký tài khoản hệ thống mới bằng mật khẩu với cơ chế chống Spam đăng ký."""
    return auth_service.register_user(
        username=getattr(req, "username", ""),
        password=getattr(req, "password", ""),
        full_name=getattr(req, "full_name", ""),
        role=getattr(req, "role", "student"),
        class_name=getattr(req, "class_name", "") or "",
        phone=getattr(req, "phone", "") or "",
        school=getattr(req, "school", "") or "",
    )


@router.post(
    "/login",
    summary="Đăng nhập và nhận JWT Token",
    dependencies=[Depends(RateLimiter(times=10, seconds=60, key_prefix="auth_login"))],
)
async def login(req: LoginRequest):
    """Đăng nhập và nhận JWT Access Token + Refresh Token với giới hạn tốc độ chống Brute Force."""
    return auth_service.login_user(
        username=getattr(req, "username", ""),
        password=getattr(req, "password", ""),
    )


@router.post(
    "/refresh",
    summary="Làm mới JWT Access Token bằng Refresh Token",
    dependencies=[Depends(RateLimiter(times=20, seconds=60, key_prefix="auth_refresh"))],
)
async def refresh_token(req: RefreshTokenRequest):
    """Cấp phát Access Token mới khi Access Token cũ hết hạn bằng Refresh Token hợp lệ."""
    return auth_service.refresh_access_token(refresh_token=req.refresh_token)


# Re-exports cho tương thích ngược nếu có module khác gọi trực tiếp
get_current_google_client_id = auth_service.get_google_client_id
verify_google_payload = auth_service.verify_google_payload
