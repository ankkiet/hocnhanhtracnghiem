"""
Teacher Management Pydantic Schemas.
"""

from typing import List, Optional

from pydantic import BaseModel


class TeacherQuizActionRequest(BaseModel):
    quiz_id: str
    action: str  # 'publish', 'unpublish', 'archive', 'restore', 'permanent'
    teacher_token: str


class ExportWordRequest(BaseModel):
    quiz_id: str
    teacher_token: str
    include_answers: Optional[bool] = True
    target_audience: Optional[str] = "teacher"
    layout_mode: Optional[str] = "compact"
    options_layout: Optional[str] = "auto"
    show_answers: Optional[bool] = None
    show_key_table: Optional[bool] = None
    show_explains: Optional[bool] = None
    include_student_answer_grid: Optional[bool] = False


class ExportDocxCustomRequest(BaseModel):
    title: Optional[str] = "Đề thi trắc nghiệm"
    questions: Optional[List[dict]] = []
    time_limit: Optional[int] = 0
    target_audience: Optional[str] = "teacher"
    layout_mode: Optional[str] = "compact"
    options_layout: Optional[str] = "auto"
    show_answers: Optional[bool] = None
    show_key_table: Optional[bool] = None
    show_explains: Optional[bool] = None
    include_student_answer_grid: Optional[bool] = False


class GenerateQuizAIRequest(BaseModel):
    topic: str
    num_questions: int = 10
    grade: Optional[str] = "10"
    difficulty: Optional[str] = "medium"
    teacher_token: str
