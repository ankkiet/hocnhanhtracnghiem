import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.logging_config import get_logger
from core.state import AUDIT_LOGS

logger = get_logger("audit")

# Số lượng log tối đa lưu trong bộ nhớ RAM
MAX_AUDIT_LOGS = 1000


class AuditService:
    """
    Dịch vụ ghi vết kiểm toán (Audit Trail Service).
    Lưu giữ các sự kiện nhạy cảm: phê duyệt giáo viên, đổi mật khẩu, cấu hình API key,
    phát hiện gian lận thi cử và xóa đề thi.
    """

    def record_event(
        self,
        action: str,
        actor_id: str,
        actor_role: str = "system",
        target_id: str = "",
        details: Optional[Dict[str, Any]] = None,
        ip_address: str = ""
    ) -> Dict[str, Any]:
        """Ghi nhận một sự kiện kiểm toán mới vào hệ thống."""
        now_iso = datetime.now(timezone.utc).isoformat()
        event_id = str(uuid.uuid4())
        
        event = {
            "id": event_id,
            "action": action,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "target_id": target_id,
            "details": details or {},
            "ip_address": ip_address,
            "timestamp": now_iso
        }

        # Lưu vào ring buffer RAM (giới hạn MAX_AUDIT_LOGS để chống phình RAM)
        AUDIT_LOGS.insert(0, event)
        if len(AUDIT_LOGS) > MAX_AUDIT_LOGS:
            AUDIT_LOGS.pop()

        logger.info(
            f"AUDIT: [{action}] by [{actor_role}:{actor_id}] on target [{target_id}]. IP: {ip_address}"
        )
        return event

    def get_logs(
        self,
        limit: int = 50,
        action_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lấy danh sách log kiểm toán gần nhất cho Quản trị viên."""
        logs = AUDIT_LOGS
        if action_filter:
            action_clean = action_filter.strip().upper()
            logs = [entry for entry in logs if entry.get("action") == action_clean]
        return logs[:limit]


audit_service = AuditService()
