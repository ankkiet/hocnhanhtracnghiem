"""
Quiz Schemas for HocNhanhTN.
"""

from typing import Any, List, Optional

from pydantic import BaseModel


class SaveQuizRequest(BaseModel):
    quiz_id: Optional[str] = None
    title: str
    data: list
    mode: str = "practice"
    time_limit: int = 0
    is_shuffle: bool = False
    creator_id: str = ""
    status: str = "published"


class DiscardDraftRequest(BaseModel):
    task_id: Optional[str] = None
    images: Optional[List[str]] = None
    quiz_data: Optional[Any] = None


class QuizResponse(BaseModel):
    status: str
    title: Optional[str] = None
    data: Optional[List[Any]] = None
    mode: Optional[str] = "practice"
    time_limit: Optional[int] = 0
    is_shuffle: Optional[bool] = False
    updated_at: Optional[float] = None


class CheckQuizAIRequest(BaseModel):
    quiz_id: str
    teacher_token: Optional[str] = None


CheckQuizRequest = CheckQuizAIRequest


class QuizActionRequest(BaseModel):
    action: str  # 'delete', 'archive', 'duplicate'
    quiz_id: str
    teacher_token: str


class TogglePublishRequest(BaseModel):
    quiz_id: str
    teacher_token: str

