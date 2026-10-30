"""
API Dependencies for HocNhanhTN.
Re-exports dependencies from app.core.dependencies for standard FastApi routing.
"""

from app.core.dependencies import (
    RateLimiter,
    clear_rate_limits,
    get_current_admin,
    get_current_teacher,
    get_current_user,
    get_db,
)

__all__ = [
    "RateLimiter",
    "clear_rate_limits",
    "get_db",
    "get_current_user",
    "get_current_teacher",
    "get_current_admin",
]
