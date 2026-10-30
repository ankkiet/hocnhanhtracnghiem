"""
Admin Management Pydantic Schemas.
"""

from typing import List

from pydantic import BaseModel


class SetApiKeyRequest(BaseModel):
    admin_token: str
    api_keys: List[str]


class SetGoogleClientIdRequest(BaseModel):
    admin_token: str
    client_id: str


class ApproveUserRequest(BaseModel):
    admin_token: str
    user_id: str


class ChangePasswordRequest(BaseModel):
    admin_token: str
    old_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    admin_token: str
    user_id: str
    new_password: str
