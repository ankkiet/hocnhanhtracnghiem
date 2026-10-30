"""
Core Logging Config for HocNhanhTN (Backward Compatibility Shim).
Forwards to app.config.logging.
"""

from app.config.logging import get_logger, setup_logging

__all__ = ["get_logger", "setup_logging"]
