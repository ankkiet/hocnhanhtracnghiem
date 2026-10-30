"""
Authentication Service Backward Compatibility Re-export.
"""
from app.services.auth_service import AuthService, _get_db, auth_service

__all__ = ["AuthService", "auth_service", "_get_db"]
