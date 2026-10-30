"""
Health Router for HocNhanhTN (Backward Compatibility Shim).
Forwards to app.api.routes.health.
"""

from app.api.routes.health import router

__all__ = ["router"]
