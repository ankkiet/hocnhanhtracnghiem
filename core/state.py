"""
Trạng thái dùng chung toàn hệ thống (Application Shared State).
Được nâng cấp với BoundedTTLCache (giới hạn RAM + tự động thu hồi TTL)
và PersistentTaskStore (lưu trữ tác vụ nền bền vững hai tầng RAM + Disk).
"""

from typing import Any, Dict, List

from core.cache import BoundedTTLCache
from core.task_store import PersistentTaskStore

# Caches to save Firebase Quota (giới hạn số lượng mục & TTL rõ ràng chống rò rỉ RAM)
QUIZ_CACHE = BoundedTTLCache(max_size=500, default_ttl=300, name="quizzes")
LEADERBOARD_CACHE = BoundedTTLCache(max_size=200, default_ttl=60, name="leaderboard")
SUBMISSIONS_CACHE = BoundedTTLCache(max_size=300, default_ttl=180, name="submissions")
USER_CACHE = BoundedTTLCache(max_size=1000, default_ttl=1800, name="users")
SETTINGS_CACHE = BoundedTTLCache(max_size=100, default_ttl=600, name="settings")

# Security & Session Tracking
EXAM_SESSIONS = BoundedTTLCache(max_size=1000, default_ttl=7200, name="exam_sessions")
AUDIT_LOGS: List[Dict[str, Any]] = []  # Ring buffer for administrative & security audit events
REFRESH_TOKENS = BoundedTTLCache(max_size=1000, default_ttl=1209600, name="refresh_tokens")

# Persistent Task Store (RAM + Disk fallback)
active_tasks = PersistentTaskStore(max_size=500, default_ttl=900)
task_store = active_tasks
