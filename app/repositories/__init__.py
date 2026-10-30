"""
Repositories package.
"""

from app.repositories.base_repo import BaseRepository
from app.repositories.document_repo import DocumentRepository, document_repo
from app.repositories.exam_repo import ExamRepository, exam_repo
from app.repositories.quiz_repo import QuizRepository, quiz_repo
from app.repositories.user_repo import UserRepository, user_repo

__all__ = [
    "BaseRepository",
    "QuizRepository",
    "quiz_repo",
    "UserRepository",
    "user_repo",
    "ExamRepository",
    "exam_repo",
    "DocumentRepository",
    "document_repo",
]
