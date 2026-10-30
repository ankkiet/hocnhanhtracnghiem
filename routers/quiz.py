"""
Quiz Router for HocNhanhTN (Backward Compatibility Shim).
Forwards to app.api.routes.quiz and app.schemas.quiz.
"""

from app.api.routes.quiz import (
    DiscardDraftRequest,
    SaveQuizRequest,
    discard_draft,
    get_db,
    get_quiz,
    router,
    save_quiz,
)

__all__ = [
    "router",
    "get_db",
    "SaveQuizRequest",
    "DiscardDraftRequest",
    "discard_draft",
    "save_quiz",
    "get_quiz",
]
