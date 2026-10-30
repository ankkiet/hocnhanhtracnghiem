"""
Student Exam & History Schemas for HocNhanhTN.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class StartExamRequest(BaseModel):
    quiz_id: str
    student_name: str
    student_token: Optional[str] = None


class SubmitExamRequest(BaseModel):
    quiz_id: str
    student_name: str
    student_token: Optional[str] = None
    answers: Dict[str, Any] = {}
    time_elapsed: int = 0
    session_id: Optional[str] = None
    tab_switch_count: Optional[int] = 0


class SyncHistoryItem(BaseModel):
    quiz_id: str
    quiz_title: Optional[str] = "Đề thi trắc nghiệm"
    score: float
    total_questions: int
    time_elapsed: int
    submitted_at: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    answers: Optional[Dict[str, Any]] = None


class SyncHistoryRequest(BaseModel):
    student_token: str
    history_items: List[SyncHistoryItem]


class SubmitScoreRequest(BaseModel):
    quiz_id: str
    student_name: str
    score: int
    total_questions: int
    time_elapsed: int


class SaveProgressRequest(BaseModel):
    student_token: str
    quiz_id: str
    progress_data: dict


class PingSessionRequest(BaseModel):
    quiz_id: str
    session_id: str
    student_name: str
    answers_count: int
    time_remaining: int
    completed: bool
