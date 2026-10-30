"""
Teacher Router for HocNhanhTN (Backward Compatibility Shim).
Forwards to app.api.routes.teacher.
"""

from app.api.routes.teacher import (
    CheckQuizRequest,
    CrossCheckAnswersRequest,
    GenerateSimilarQuestionsRequest,
    QuizActionRequest,
    TogglePublishRequest,
    cross_check_quiz_answers,
    export_quiz_docx,
    generate_similar_quiz_questions,
    get_quiz_analytics,
    get_teacher_quizzes,
    monitor_stream,
    quiz_action,
    router,
    toggle_publish,
    verify_teacher_access,
)
from services.firebase_service import get_db

export_docx = export_quiz_docx

__all__ = [
    "router",
    "get_db",
    "QuizActionRequest",
    "TogglePublishRequest",
    "CheckQuizRequest",
    "verify_teacher_access",
    "get_teacher_quizzes",
    "quiz_action",
    "toggle_publish",
    "export_quiz_docx",
    "export_docx",
    "get_quiz_analytics",
    "monitor_stream",
    "CrossCheckAnswersRequest",
    "GenerateSimilarQuestionsRequest",
    "cross_check_quiz_answers",
    "generate_similar_quiz_questions",
]
