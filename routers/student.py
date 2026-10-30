"""
Student Router for HocNhanhTN (Backward Compatibility Shim).
Forwards to app.api.routes.student and app.schemas.student.
"""

from app.api.routes.student import (
    PingSessionRequest,
    SaveProgressRequest,
    StartExamRequest,
    SubmitExamRequest,
    SubmitScoreRequest,
    SyncHistoryItem,
    SyncHistoryRequest,
    delete_student_history,
    get_leaderboard,
    get_student_history,
    get_student_history_detail,
    get_student_progress,
    ping_session,
    router,
    save_student_progress,
    start_exam,
    submit_exam,
    submit_score_legacy,
    sync_student_history,
)
from core.security import get_user_from_token
from services.firebase_service import get_db

__all__ = [
    "router",
    "get_db",
    "get_user_from_token",
    "StartExamRequest",
    "SubmitExamRequest",
    "SyncHistoryItem",
    "SyncHistoryRequest",
    "SubmitScoreRequest",
    "SaveProgressRequest",
    "PingSessionRequest",
    "start_exam",
    "submit_exam",
    "submit_score_legacy",
    "save_student_progress",
    "get_student_progress",
    "ping_session",
    "get_leaderboard",
    "get_student_history",
    "get_student_history_detail",
    "delete_student_history",
    "sync_student_history",
]
