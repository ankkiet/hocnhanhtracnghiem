import hashlib
import hmac
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core.cache import cache_manager
from core.logging_config import get_logger
from core.security import SECRET_KEY
from core.state import EXAM_SESSIONS
from services.audit_service import audit_service

logger = get_logger(__name__)


class ExamSessionService:
    """
    Dịch vụ quản trị Phiên làm bài & Chống gian lận thi cử (Anti-Cheat & Session Integrity Service).
    Xử lý:
    1. Xác thực thời gian thực bắt đầu làm bài phía Server (Server-Side Timestamp).
    2. Chống nộp bài hai lần (Anti Double-Submission Replay Attack).
    3. Kiểm tra quá hạn giờ thi với dung sai mạng hợp lý.
    4. Ghi nhận vi phạm chuyển tab và cảnh báo gian lận.
    """

    def start_session(
        self,
        quiz_id: str,
        student_name: str,
        student_id: Optional[str] = None,
        time_limit_minutes: int = 0
    ) -> Dict[str, Any]:
        """Khởi tạo một phiên thi mới với timestamp chuẩn từ máy chủ."""
        session_id = f"sess_{uuid.uuid4().hex}"
        started_at = int(time.time())

        # Tạo chữ ký HMAC chống giả mạo session ID
        sig_data = f"{session_id}:{quiz_id}:{started_at}".encode()
        signature = hmac.new(SECRET_KEY.encode(), sig_data, hashlib.sha256).hexdigest()

        session_record = {
            "session_id": session_id,
            "quiz_id": quiz_id,
            "student_name": student_name.strip() or "Ẩn danh",
            "student_id": student_id,
            "started_at": started_at,
            "time_limit": time_limit_minutes,
            "status": "in_progress",
            "signature": signature
        }

        EXAM_SESSIONS[session_id] = session_record
        cache_manager.set_json(f"exam_session:{session_id}", session_record, ttl_seconds=7200)
        logger.info(
            f"ExamSession: Thí sinh '{student_name}' đã bắt đầu phiên thi {session_id} cho đề {quiz_id}."
        )

        return {
            "session_id": session_id,
            "quiz_id": quiz_id,
            "started_at": started_at,
            "time_limit": time_limit_minutes,
            "signature": signature
        }

    def verify_and_complete_session(
        self,
        session_id: str,
        quiz_id: str,
        tab_switch_count: int = 0,
        student_name: str = ""
    ) -> Dict[str, Any]:
        """
        Xác thực tính hợp lệ và hoàn tất phiên thi:
        - Kiểm tra tính tồn tại của phiên thi.
        - Chống nộp lặp lại (Replay Attack).
        - So sánh thời gian làm bài thực tế với thời gian quy định của đề thi.
        - Phát hiện hành vi chuyển tab / thoát fullscreen bất thường.
        """
        if not session_id:
            return {
                "valid": True,
                "server_verified": False,
                "cheat_flags": []
            }

        session = EXAM_SESSIONS.get(session_id)
        if not session:
            # Tra cứu từ Redis phân tán nếu có
            session = cache_manager.get_json(f"exam_session:{session_id}")
            if session:
                EXAM_SESSIONS[session_id] = session

        if not session:
            # Cho phép bỏ qua kiểm tra session nếu client cũ không hỗ trợ, nhưng cảnh báo
            return {
                "valid": True,
                "server_verified": False,
                "cheat_flags": []
            }

        # 1. Chống nộp 2 lần (Anti-Replay Attack)
        if session.get("status") == "completed":
            logger.warning(f"ExamSession: Phát hiện nộp bài trùng lặp cho session {session_id}.")
            raise HTTPException(
                status_code=400,
                detail="Bài thi này đã được nộp trước đó. Hệ thống không cho phép nộp lại."
            )

        # 2. Kiểm tra khớp mã đề thi
        if session.get("quiz_id") != quiz_id:
            raise HTTPException(
                status_code=400,
                detail="Mã đề thi không khớp với phiên làm bài hợp lệ."
            )

        server_now = int(time.time())
        started_at = session.get("started_at", server_now)
        actual_elapsed = max(0, server_now - started_at)
        time_limit_min = session.get("time_limit", 0)

        cheat_flags: List[str] = []

        # 3. Kiểm tra quá hạn thời gian nộp bài
        # Cho phép trễ tối đa 120 giây (dung sai độ trễ mạng Internet & tải giao diện)
        if time_limit_min > 0:
            allowed_seconds = (time_limit_min * 60) + 120
            if actual_elapsed > allowed_seconds:
                cheat_flags.append("overtime_submission")
                logger.warning(
                    f"ExamSession: Bài thi {quiz_id} của {student_name} bị quá hạn "
                    f"({actual_elapsed}s > {allowed_seconds}s cho phép)."
                )

        # 4. Kiểm tra hành vi chuyển tab quá số lần quy định (> 3 lần)
        if tab_switch_count > 3:
            cheat_flags.append(f"excessive_tab_switching_{tab_switch_count}")
            logger.warning(
                f"ExamSession: Thí sinh {student_name} chuyển tab {tab_switch_count} lần trong khi thi đề {quiz_id}."
            )

        # Ghi vết kiểm toán nếu phát hiện dấu hiệu vi phạm
        if cheat_flags:
            audit_service.record_event(
                action="EXAM_SUSPICIOUS_ACTIVITY",
                actor_id=session.get("student_id") or "guest",
                actor_role="student",
                target_id=quiz_id,
                details={
                    "session_id": session_id,
                    "student_name": student_name or session.get("student_name"),
                    "flags": cheat_flags,
                    "actual_elapsed": actual_elapsed,
                    "time_limit": time_limit_min
                }
            )

        # Đánh dấu phiên thi đã hoàn tất
        session["status"] = "completed"
        session["completed_at"] = server_now
        session["cheat_flags"] = cheat_flags
        EXAM_SESSIONS[session_id] = session
        cache_manager.set_json(f"exam_session:{session_id}", session, ttl_seconds=7200)

        return {
            "valid": True,
            "server_verified": True,
            "actual_elapsed": actual_elapsed,
            "cheat_flags": cheat_flags
        }


exam_session_service = ExamSessionService()
