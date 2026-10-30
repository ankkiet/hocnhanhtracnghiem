"""
Quiz Service Backward Compatibility Re-export.
"""
from app.services.quiz_service import QuizService, _get_db, quiz_service

__all__ = ["QuizService", "quiz_service", "_get_db"]
