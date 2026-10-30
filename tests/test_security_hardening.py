"""
Bộ kiểm thử An ninh & Chống Gian Lận (Security Hardening & Anti-Cheat Test Suite)
Kiểm tra các cơ chế bảo mật cao cấp theo yêu cầu E:
1. JWT Refresh Token & Token Separation
2. Rate Limiting (Chống Brute Force / DDoS / Quota Abuse)
3. Anti-Cheat: Session ID, Server Timestamp, Anti-Replay & Tab Switching Detection
4. Audit Trail Logging (Nhật ký kiểm toán Admin)
5. Student Data Privacy & Cross-Teacher Authorization Isolation
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Request
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.rate_limiter import RateLimiter, clear_rate_limits
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from core.state import AUDIT_LOGS, EXAM_SESSIONS, QUIZ_CACHE, SETTINGS_CACHE, USER_CACHE
from main import app
from services.audit_service import audit_service


class TestSecurityHardening(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        USER_CACHE.clear()
        QUIZ_CACHE.clear()
        SETTINGS_CACHE.clear()
        EXAM_SESSIONS.clear()
        AUDIT_LOGS.clear()
        clear_rate_limits()

    # =========================================================================
    # 1. JWT REFRESH TOKEN & TOKEN ISOLATION
    # =========================================================================

    def test_jwt_refresh_token_generation_and_separation(self):
        """
        Kiểm tra tính năng Refresh Token:
        - Refresh Token có 'type': 'refresh'
        - Access Token có 'type': 'access'
        - Không thể dùng Refresh Token thay thế Access Token tại các route yêu cầu xác thực
        """
        user_payload = {"sub": "u_test_101", "username": "user101@test.com", "role": "student"}
        access_tok = create_access_token(user_payload)
        refresh_tok = create_refresh_token(user_payload)

        # 1. Kiểm tra decode đúng loại
        acc_decoded = decode_access_token(access_tok)
        self.assertIsNotNone(acc_decoded)
        self.assertEqual(acc_decoded.get("type"), "access")

        ref_decoded = decode_refresh_token(refresh_tok)
        self.assertIsNotNone(ref_decoded)
        self.assertEqual(ref_decoded.get("type"), "refresh")

        # 2. Chặn dùng Refresh Token ở decode_access_token
        self.assertIsNone(decode_access_token(refresh_tok), "LỖI BẢO MẬT: decode_access_token không được chấp nhận refresh token!")

    @patch("services.auth_service._get_db")
    @patch("routers.auth.get_db")
    def test_refresh_token_api_endpoint(self, mock_r_db, mock_s_db):
        """
        Kiểm tra endpoint /api/auth/refresh:
        - Gửi Refresh Token hợp lệ -> Nhận Access Token mới và Refresh Token mới
        - Gửi Access Token nhầm vào endpoint refresh -> Bị từ chối 401
        - Gửi Token giả mạo -> Bị từ chối 401
        """
        mock_db = MagicMock()
        mock_r_db.return_value = mock_db
        mock_s_db.return_value = mock_db

        user_payload = {"sub": "u_ref_01", "username": "user_ref@test.com", "role": "student"}
        valid_refresh = create_refresh_token(user_payload)
        valid_access = create_access_token(user_payload)

        # 1. Refresh hợp lệ
        res = self.client.post("/api/auth/refresh", json={"refresh_token": valid_refresh})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(decode_access_token(data["access_token"])["sub"], "u_ref_01")

        # 2. Dùng Access Token thay cho Refresh Token -> 401
        res_invalid = self.client.post("/api/auth/refresh", json={"refresh_token": valid_access})
        self.assertEqual(res_invalid.status_code, 401)

        # 3. Token giả mạo -> 401
        res_fake = self.client.post("/api/auth/refresh", json={"refresh_token": "fake.tampered.token"})
        self.assertEqual(res_fake.status_code, 401)

    # =========================================================================
    # 2. RATE LIMITING (SLIDING WINDOW)
    # =========================================================================

    def test_rate_limiter_enforcement(self):
        """
        Kiểm tra cơ chế giới hạn tần suất gọi API (Sliding Window Rate Limiter):
        - Cho phép tối đa 'times' yêu cầu trong 'seconds' giây
        - Yêu cầu vượt ngưỡng bị chặn với HTTP 429 Too Many Requests kèm Retry-After header
        """
        limiter = RateLimiter(times=3, seconds=5, key_prefix="test_unit")
        dummy_req = MagicMock(spec=Request)
        dummy_req.headers = {"x-forwarded-for": "198.51.100.10"}
        dummy_req.client.host = "198.51.100.10"
        dummy_req.url.path = "/api/test_endpoint"

        import asyncio

        from fastapi import HTTPException


        # Tạm bật rate limiting cho test case này
        with patch("core.rate_limiter.RATE_LIMIT_ENABLED", True), \
             patch("sys.modules", {}), \
             patch.dict(os.environ, {"TESTING": "false"}):

            # 3 lần gọi đầu tiên thành công
            asyncio.run(limiter(dummy_req))
            asyncio.run(limiter(dummy_req))
            asyncio.run(limiter(dummy_req))

            # Lần thứ 4 phải ném HTTPException 429
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(limiter(dummy_req))
            self.assertEqual(ctx.exception.status_code, 429)
            self.assertIn("Retry-After", ctx.exception.headers)
            self.assertIn("quá nhanh", ctx.exception.detail)

    # =========================================================================
    # 3. ANTI-CHEAT: EXAM SESSION & TIMESTAMP INTEGRITY
    # =========================================================================

    @patch("services.firebase_service.get_db")
    def test_exam_session_lifecycle_and_anti_replay(self, mock_get_db):
        """
        Kiểm tra vòng đời phiên thi và cơ chế chống nộp bài lặp lại (Anti-Replay Attack):
        1. Bắt đầu thi (/api/student/start_exam) -> Server tạo session_id và mốc thời gian máy chủ.
        2. Nộp bài lần 1 với session_id -> Chấm điểm thành công (200 OK).
        3. Nộp bài lần 2 với cùng session_id (Replay) -> Bị từ chối 400 Bad Request.
        """
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        quiz_id = "QUIZ_ANTICHEAT_SEC"
        QUIZ_CACHE[quiz_id] = {
            "time": time.time(),
            "data": {
                "title": "Đề thi Kiểm tra Bảo mật",
                "mode": "exam",
                "time_limit": 15,
                "data": [
                    {"question": "Thủ đô của Việt Nam là gì?", "options": ["A. Hà Nội", "B. Huế"], "correct_answer": "A. Hà Nội", "type": "mcq"}
                ]
            }
        }

        # Bước 1: Khởi tạo phiên thi
        start_res = self.client.post("/api/student/start_exam", json={
            "quiz_id": quiz_id,
            "student_name": "Lê Văn Thí Sinh",
        })
        self.assertEqual(start_res.status_code, 200)
        session_info = start_res.json()["data"]
        session_id = session_info["session_id"]
        self.assertTrue(session_id.startswith("sess_"))

        # Bước 2: Nộp bài lần 1 thành công
        submit_res1 = self.client.post("/api/student/submit_exam", json={
            "quiz_id": quiz_id,
            "session_id": session_id,
            "student_name": "Lê Văn Thí Sinh",
            "answers": {"0": "A. Hà Nội"},
            "time_elapsed": 120
        })
        self.assertEqual(submit_res1.status_code, 200)
        self.assertEqual(submit_res1.json()["status"], "success")

        # Bước 3: Tấn công Replay - Nộp lại bài thi đã nộp -> Bị chặn 400
        submit_res2 = self.client.post("/api/student/submit_exam", json={
            "quiz_id": quiz_id,
            "session_id": session_id,
            "student_name": "Lê Văn Thí Sinh",
            "answers": {"0": "A. Hà Nội"},
            "time_elapsed": 120
        })
        self.assertEqual(submit_res2.status_code, 400)
        self.assertIn("đã được nộp trước đó", submit_res2.json()["detail"])

    @patch("services.firebase_service.get_db")
    def test_anti_cheat_overtime_and_tab_switch_detection(self, mock_get_db):
        """
        Kiểm tra phát hiện gian lận:
        - Quá thời gian quy định phía Server
        - Chuyển tab quá số lần quy định (> 3 lần)
        - Gắn cờ cảnh báo (cheat_flags) và lưu vào audit log
        """
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        quiz_id = "QUIZ_OVERTIME_TEST"
        QUIZ_CACHE[quiz_id] = {
            "time": time.time(),
            "data": {
                "title": "Đề thi 5 phút",
                "mode": "exam",
                "time_limit": 5, # 5 phút = 300s
                "data": [{"question": "Q1", "options": ["A. 1"], "correct_answer": "A. 1", "type": "mcq"}]
            }
        }

        # Giả lập học sinh bắt đầu từ 10 phút trước (quá thời hạn 5 phút + 2 phút dung sai = 420s)
        session_id = "sess_fake_overtime_999"
        EXAM_SESSIONS[session_id] = {
            "session_id": session_id,
            "quiz_id": quiz_id,
            "student_name": "Thí Sinh Gian Lận",
            "student_id": "u_cheater",
            "started_at": int(time.time()) - 600, # 10 phút trước
            "time_limit": 5,
            "status": "in_progress"
        }

        # Gửi bài thi kèm hành vi chuyển tab 5 lần
        submit_res = self.client.post("/api/student/submit_exam", json={
            "quiz_id": quiz_id,
            "session_id": session_id,
            "student_name": "Thí Sinh Gian Lận",
            "answers": {"0": "A. 1"},
            "time_elapsed": 300, # Client báo 300s nhưng Server phát hiện 600s
            "tab_switch_count": 5
        })

        self.assertEqual(submit_res.status_code, 200)
        # Kiểm tra session_service đã gắn cờ vi phạm
        session_info = EXAM_SESSIONS[session_id]
        self.assertIn("overtime_submission", session_info["cheat_flags"])
        self.assertTrue(any("excessive_tab_switching" in f for f in session_info["cheat_flags"]))

        # Kiểm tra audit log đã ghi nhận sự kiện vi phạm
        suspicious_logs = audit_service.get_logs(action_filter="EXAM_SUSPICIOUS_ACTIVITY")
        self.assertTrue(len(suspicious_logs) > 0)
        self.assertEqual(suspicious_logs[0]["target_id"], quiz_id)

    # =========================================================================
    # 4. AUDIT TRAIL LOGGING
    # =========================================================================

    @patch("routers.admin.get_db")
    def test_admin_audit_logs_endpoint(self, mock_get_db):
        """
        Kiểm tra nhật ký kiểm toán cho Admin:
        - Admin gọi /api/admin/audit_logs -> xem được toàn bộ thao tác nhạy cảm
        - Học sinh gọi /api/admin/audit_logs -> 403 Forbidden
        """
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        admin_token = create_access_token({"sub": "admin_audit_01", "username": "admin", "role": "admin"})
        student_token = create_access_token({"sub": "student_audit_01", "username": "student", "role": "student"})

        # Giả lập Firestore trả về role tương ứng khi tra cứu user
        def mock_user_doc(uid):
            m = MagicMock()
            m.exists = True
            m.id = uid
            m.get.return_value = m
            if "admin" in uid:
                m.to_dict.return_value = {"role": "admin", "username": "admin", "status": "approved"}
            else:
                m.to_dict.return_value = {"role": "student", "username": "student", "status": "approved"}
            return m
        mock_db.collection.return_value.document.side_effect = mock_user_doc

        # Ghi một số event mẫu
        audit_service.record_event("ADMIN_APPROVE_USER", actor_id="admin_audit_01", actor_role="admin", target_id="teacher_99")
        audit_service.record_event("ADMIN_SET_API_KEY", actor_id="admin_audit_01", actor_role="admin")

        # 1. Học sinh truy cập -> 403
        res_stu = self.client.get(f"/api/admin/audit_logs?admin_token={student_token}")
        self.assertEqual(res_stu.status_code, 403)

        # 2. Admin truy cập -> 200 + danh sách logs
        res_adm = self.client.get(f"/api/admin/audit_logs?admin_token={admin_token}")
        self.assertEqual(res_adm.status_code, 200)
        logs_data = res_adm.json()["data"]
        self.assertTrue(len(logs_data) >= 2)
        actions = [item["action"] for item in logs_data]
        self.assertIn("ADMIN_APPROVE_USER", actions)
        self.assertIn("ADMIN_SET_API_KEY", actions)

    # =========================================================================
    # 5. STUDENT DATA PRIVACY & CROSS-TEACHER AUTHORIZATION
    # =========================================================================

    @patch("routers.teacher.get_db")
    def test_cross_teacher_data_leak_prevention(self, mock_get_db):
        """
        Bảo mật dữ liệu học sinh (Student Data Privacy):
        - Giáo viên B không được phép xem phân tích bài nộp và danh sách điểm của học sinh thuộc đề thi của Giáo viên A (403)
        """
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        quiz_id = "QUIZ_TEACHER_A"
        QUIZ_CACHE[quiz_id] = {
            "time": time.time(),
            "data": {
                "title": "Đề thi riêng của Giáo viên A",
                "creator_id": "teacher_A_uid",
                "data": []
            }
        }

        # Giả lập Firestore trả về role teacher cho Giáo viên B
        mock_teacher_doc = MagicMock()
        mock_teacher_doc.exists = True
        mock_teacher_doc.id = "teacher_B_uid"
        mock_teacher_doc.to_dict.return_value = {"role": "teacher", "username": "teacher_b@test.com", "status": "approved"}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_teacher_doc

        # Token của Giáo viên B
        teacher_B_token = create_access_token({"sub": "teacher_B_uid", "username": "teacher_b@test.com", "role": "teacher"})

        # Giáo viên B cố tình xem phân tích điểm học sinh của Giáo viên A
        res = self.client.get(f"/api/teacher/quiz_analytics/{quiz_id}?teacher_token={teacher_B_token}")
        self.assertEqual(res.status_code, 403)
        self.assertIn("Không có quyền xem phân tích bài nộp", res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
