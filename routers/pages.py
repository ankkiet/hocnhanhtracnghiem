"""
Pages & Static Router for HocNhanhTN (Backward Compatibility Shim).
Forwards to app.api.routes.pages.
"""

from app.api.routes.pages import router

__all__ = ["router"]
