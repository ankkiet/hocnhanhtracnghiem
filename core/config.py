"""
Core Config for HocNhanhTN (Backward Compatibility Shim).
Forwards to app.config.settings.
"""

from app.config.settings import Settings, settings, setup_system_environment

__all__ = ["Settings", "settings", "setup_system_environment"]
