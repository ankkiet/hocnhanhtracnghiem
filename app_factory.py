"""
App Factory module for HocNhanhTN.
Forwards to app.core.app_factory for backward compatibility.
"""

from app.core.app_factory import create_app

__all__ = ["create_app"]
