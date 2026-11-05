"""
Authentication Schemas for HocNhanhTN.
"""

from typing import Optional

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str = "student"
    class_name: Optional[str] = ""
    phone: Optional[str] = ""
    school: Optional[str] = ""


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class GoogleAuthRequest(BaseModel):
    credential: Optional[str] = None
    access_token: Optional[str] = None


class SelectRoleRequest(BaseModel):
    user_id: str
    role: str
    full_name: Optional[str] = ""
    class_name: Optional[str] = ""
    phone: Optional[str] = ""
    school: Optional[str] = ""
    extra_info: Optional[str] = ""


# Aliases for clean architecture schemas
RoleSelectionRequest = SelectRoleRequest


class TeacherApprovalActionRequest(BaseModel):
    user_id: str
    action: str  # 'approve' hoặc 'reject'
    admin_token: str


class UpdateProfileRequest(BaseModel):
    token: str
    full_name: Optional[str] = None
    class_name: Optional[str] = None
    phone: Optional[str] = None
    school: Optional[str] = None


class DeleteAccountRequest(BaseModel):
    token: str
    reason: Optional[str] = ""


class LegalReportRequest(BaseModel):
    report_type: str = "copyright"
    quiz_id: Optional[str] = ""
    reporter_name: str = ""
    reporter_email: str = ""
    reporter_role: Optional[str] = "other"
    description: str = ""
    consent_pdpd: bool = True

