"""
Configuration package.
"""

from app.config.cors import setup_cors
from app.config.logging import get_logger, setup_logging
from app.config.settings import settings

__all__ = ["settings", "get_logger", "setup_logging", "setup_cors"]
