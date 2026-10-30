"""
Admin & Governance Service for HocNhanhTN.
Chịu trách nhiệm: Duyệt tài khoản, phân quyền, cấu hình hệ thống
và truy vấn nhật ký kiểm toán (Audit Trail).
"""

from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.config.logging import get_logger
from app.repositories.user_repo import UserRepository, user_repo
from app.schemas.admin import (
    ApproveUserRequest,
    ChangePasswordRequest,
    ResetPasswordRequest,
    SetApiKeyRequest,
    SetGoogleClientIdRequest,
)
from app.utils.security import (
    hash_password,
    invalidate_user_cache,
    verify_admin_access,
    verify_password,
)
from core.state import SETTINGS_CACHE
from services.audit_service import audit_service

logger = get_logger(__name__)


class AdminService:
    """Service xử lý nghiệp vụ Quản trị viên."""

    def __init__(self, repository: UserRepository = user_repo):
        self.repo = repository

    def get_all_users(self, admin_token: str) -> Dict[str, Any]:
        """Lấy danh sách toàn bộ người dùng trong hệ thống."""
        verify_admin_access(admin_token, self.repo.db)
        users = self.repo.get_all_users()
        return {"status": "success", "data": users}

    def approve_user(self, req: ApproveUserRequest) -> Dict[str, Any]:
        """Phê duyệt tài khoản giáo viên."""
        _, admin_uid = verify_admin_access(req.admin_token, self.repo.db)
        self.repo.update_user(req.user_id, {"status": "approved"})

        audit_service.record_event(
            action="ADMIN_APPROVE_USER",
            actor_id=admin_uid,
            actor_role="admin",
            target_id=req.user_id,
            details={"status": "approved"}
        )
        return {"status": "success"}

    def delete_user(self, req: ApproveUserRequest) -> Dict[str, Any]:
        """Xóa tài khoản người dùng."""
        _, admin_uid = verify_admin_access(req.admin_token, self.repo.db)
        self.repo.delete_user(req.user_id)

        audit_service.record_event(
            action="ADMIN_DELETE_USER",
            actor_id=admin_uid,
            actor_role="admin",
            target_id=req.user_id
        )
        return {"status": "success"}

    def set_api_key(self, req: SetApiKeyRequest) -> Dict[str, Any]:
        """Cấu hình Gemini API Keys dùng chung."""
        _, admin_uid = verify_admin_access(req.admin_token, self.repo.db)
        col = self.repo.get_collection('settings')
        if col is None:
            raise HTTPException(status_code=500, detail="Lỗi DB")

        cleaned_keys = [k.strip() for k in req.api_keys if k and k.strip()]
        col.document('api_keys').set({'keys': cleaned_keys})
        SETTINGS_CACHE.pop('api_keys', None)

        audit_service.record_event(
            action="ADMIN_SET_API_KEY",
            actor_id=admin_uid,
            actor_role="admin",
            details={"count": len(cleaned_keys)}
        )
        return {"status": "success", "count": len(cleaned_keys)}

    def set_google_client_id(self, req: SetGoogleClientIdRequest) -> Dict[str, Any]:
        """Cấu hình Google Client ID."""
        _, admin_uid = verify_admin_access(req.admin_token, self.repo.db)
        col = self.repo.get_collection('settings')
        if col is None:
            raise HTTPException(status_code=500, detail="Lỗi DB")

        col.document('google_auth').set({'client_id': req.client_id.strip()})
        SETTINGS_CACHE.pop('google_auth', None)
        return {"status": "success"}

    def change_password(self, req: ChangePasswordRequest) -> Dict[str, Any]:
        """Đổi mật khẩu người dùng."""
        user, user_id = verify_admin_access(req.admin_token, self.repo.db)
        if not verify_password(req.old_password, user.get('password', '')):
            raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không chính xác.")

        new_hash = hash_password(req.new_password)
        self.repo.update_user(user_id, {'password': new_hash})
        invalidate_user_cache(user_id)
        return {"status": "success"}

    def reset_password(self, req: ResetPasswordRequest) -> Dict[str, Any]:
        """Admin đặt lại mật khẩu cho thành viên."""
        _, admin_uid = verify_admin_access(req.admin_token, self.repo.db)
        new_hash = hash_password(req.new_password)
        self.repo.update_user(req.user_id, {'password': new_hash})
        invalidate_user_cache(req.user_id)

        audit_service.record_event(
            action="ADMIN_RESET_PASSWORD",
            actor_id=admin_uid,
            actor_role="admin",
            target_id=req.user_id
        )
        return {"status": "success"}

    def get_audit_logs(
        self,
        admin_token: str,
        limit: int = 50,
        action_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Truy xuất lịch sử kiểm toán bảo mật."""
        verify_admin_access(admin_token, self.repo.db)
        logs = audit_service.get_logs(limit=limit, action_filter=action_filter)
        return {"status": "success", "data": logs}


admin_service = AdminService()
