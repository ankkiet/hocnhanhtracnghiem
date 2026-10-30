"""
Teacher Management Pydantic Schemas.
"""

from typing import Optional

from pydantic import BaseModel


class TeacherQuizActionRequest(BaseModel):
    quiz_id: str
    action: str  # 'publish', 'unpublish', 'archive', 'restore', 'permanent'
    teacher_token: str


class ExportWordRequest(BaseModel):
    quiz_id: str
    teacher_token: str
    include_answers: Optional[bool] = True


class GenerateQuizAIRequest(BaseModel):
    topic: str
    num_questions: int = 10
    grade: Optional[str] = "10"
    difficulty: Optional[str] = "medium"
    teacher_token: str
