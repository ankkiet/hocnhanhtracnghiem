"""
Pydantic Schemas package.
"""

from app.schemas.admin import (
    ApproveUserRequest,
    ChangePasswordRequest,
    ResetPasswordRequest,
    SetApiKeyRequest,
    SetGoogleClientIdRequest,
)
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RoleSelectionRequest,
    TeacherApprovalActionRequest,
    UpdateProfileRequest,
)
from app.schemas.document import (
    GenerateQuizRequest,
)
from app.schemas.quiz import (
    CheckQuizAIRequest,
    DiscardDraftRequest,
    QuizActionRequest,
    SaveQuizRequest,
)
from app.schemas.student import (
    StartExamRequest,
    SubmitExamRequest,
    SyncHistoryItem,
)
from app.schemas.teacher import (
    ExportWordRequest,
    GenerateQuizAIRequest,
    TeacherQuizActionRequest,
)

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "RefreshTokenRequest",
    "RoleSelectionRequest",
    "TeacherApprovalActionRequest",
    "UpdateProfileRequest",
    "SaveQuizRequest",
    "DiscardDraftRequest",
    "QuizActionRequest",
    "CheckQuizAIRequest",
    "SubmitExamRequest",
    "SyncHistoryItem",
    "StartExamRequest",
    "TeacherQuizActionRequest",
    "ExportWordRequest",
    "GenerateQuizAIRequest",
    "SetApiKeyRequest",
    "SetGoogleClientIdRequest",
    "ApproveUserRequest",
    "ChangePasswordRequest",
    "ResetPasswordRequest",
    "GenerateQuizRequest",
]
