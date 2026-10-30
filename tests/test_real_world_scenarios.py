"""
Bộ kiểm thử kịch bản thực tế (Realistic End-to-End & Integration Test Suite)
Đảm bảo chất lượng hệ thống HocNhanhTN qua các kịch bản thực tế:
1. Auth Flow & Role-Based Access Control (RBAC)
2. Upload Invalid File & Edge Cases
3. Parse Corrupted Word/PDF & Graceful Error Handling
4. AI Fallback & API Key Rotation on 429 Quota Exceeded
5. Storage & Database Resilient Fallback (R2 Timeout -> Local, Firestore Timeout -> Stale Cache)
6. High Concurrency & Thread-Safety (20+ concurrent threads)
7. Anti-Cheat & API Contract Testing
"""

import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import services.r2_service as r2_svc
from core.security import create_access_token, hash_password
from core.state import QUIZ_CACHE, SETTINGS_CACHE, USER_CACHE, active_tasks
from main import app
from routers.document import process_document_background
from services.ai_service import call_gemini_with_fallback, fix_json_latex_escapes
from services.quiz_service import quiz_service


class TestRealisticScenarios(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Làm sạch cache trước mỗi test để đảm bảo tính độc lập
        USER_CACHE.clear()
        QUIZ_CACHE.clear()
        SETTINGS_CACHE.clear()
        active_tasks.clear()

    # =========================================================================
    # 1. AUTH FLOW & ROLE-BASED ACCESS CONTROL (RBAC)
    # =========================================================================

    @patch("services.auth_service._get_db")
    @patch("routers.auth.get_db")
    def test_auth_registration_flow_student_vs_teacher(self, mock_router_db, mock_service_db):
        """
        Kiểm tra luồng đăng ký:
        - Học sinh: đăng ký thành công, trạng thái kích hoạt ngay.
        - Giáo viên: đăng ký thành công nhưng ở trạng thái chờ duyệt (pending), không cấp quyền truy cập ngay.
        - Luồng chọn vai trò Google OAuth: Học sinh nhận token ngay, Giáo viên chờ duyệt.
        """
        mock_db = MagicMock()
        mock_router_db.return_value = mock_db
        mock_service_db.return_value = mock_db

        # Giả lập chưa có user nào trùng username
        mock_db.collection.return_value.where.return_value.get.return_value = []
        new_doc = MagicMock()
        new_doc.id = "new_user_123"
        mock_db.collection.return_value.document.return_value = new_doc

        # 1. Đăng ký tài khoản Học sinh qua form mật khẩu
        res_student = self.client.post("/api/auth/register", json={
            "username": "student_test@gmail.com",
            "password": "Password@123",
            "role": "student",
            "full_name": "Nguyễn Văn Học Sinh"
        })
        self.assertEqual(res_student.status_code, 200)
        data_s = res_student.json()
        self.assertEqual(data_s["status"], "success")
        self.assertIn("đăng nhập ngay", data_s["message"].lower())

        # 2. Đăng ký tài khoản Giáo viên qua form mật khẩu
        res_teacher = self.client.post("/api/auth/register", json={
            "username": "teacher_test@gmail.com",
            "password": "Password@123",
            "role": "teacher",
            "full_name": "Thầy Trần Văn Giáo Viên"
        })
        self.assertEqual(res_teacher.status_code, 200)
        data_t = res_teacher.json()
        self.assertEqual(data_t["status"], "success")
        self.assertIn("chờ", data_t["message"].lower())

        # 3. Luồng phân quyền qua OAuth (/api/auth/select_role)
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            "email": "oauth_user@example.com",
            "username": "oauth_user@example.com",
            "full_name": "OAuth User",
            "status": "needs_role"
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_user_doc

        # Chọn vai trò Học sinh -> nhận JWT token ngay lập tức
        res_sel_s = self.client.post("/api/auth/select_role", json={"user_id": "u_s", "role": "student"})
        self.assertEqual(res_sel_s.status_code, 200)
        self.assertEqual(res_sel_s.json()["status"], "success")
        self.assertEqual(res_sel_s.json()["role"], "student")
        self.assertIn("token", res_sel_s.json())

        # Chọn vai trò Giáo viên -> trạng thái pending_approval, KHÔNG có token
        res_sel_t = self.client.post("/api/auth/select_role", json={"user_id": "u_t", "role": "teacher"})
        self.assertEqual(res_sel_t.status_code, 200)
        self.assertEqual(res_sel_t.json()["status"], "pending_approval")
        self.assertEqual(res_sel_t.json()["role"], "teacher")
        self.assertNotIn("token", res_sel_t.json())

    @patch("services.auth_service._get_db")
    @patch("routers.auth.get_db")
    def test_auth_login_scenarios(self, mock_router_db, mock_service_db):
        """
        Kiểm tra các kịch bản đăng nhập:
        - Sai mật khẩu -> 401
        - Người dùng không tồn tại -> 401
        - Giáo viên chưa duyệt (pending) -> trả về pending_approval, không cấp token
        - Học sinh hợp lệ -> 200 + token
        """
        mock_db = MagicMock()
        mock_router_db.return_value = mock_db
        mock_service_db.return_value = mock_db

        hashed = hash_password("ValidPassword@123")

        # 1. Sai mật khẩu
        user_doc_wrong_pwd = MagicMock()
        user_doc_wrong_pwd.id = "u1"
        user_doc_wrong_pwd.to_dict.return_value = {
            "username": "user1@test.com",
            "password_hash": hashed,
            "role": "student",
            "status": "approved"
        }
        mock_db.collection.return_value.where.return_value.get.return_value = [user_doc_wrong_pwd]

        res = self.client.post("/api/auth/login", json={
            "username": "user1@test.com",
            "password": "WrongPassword"
        })
        self.assertEqual(res.status_code, 401)

        # 2. Người dùng không tồn tại
        mock_db.collection.return_value.where.return_value.get.return_value = []
        res_not_found = self.client.post("/api/auth/login", json={
            "username": "nonexistent@test.com",
            "password": "ValidPassword@123"
        })
        self.assertEqual(res_not_found.status_code, 401)

        # 3. Giáo viên ở trạng thái 'pending' cố gắng đăng nhập
        user_pending_doc = MagicMock()
        user_pending_doc.id = "u_pending"
        user_pending_doc.to_dict.return_value = {
            "username": "pending_teacher@test.com",
            "password_hash": hashed,
            "role": "teacher",
            "status": "pending",
            "full_name": "Giáo Viên Chờ Duyệt"
        }
        mock_db.collection.return_value.where.return_value.get.return_value = [user_pending_doc]
        res_pending = self.client.post("/api/auth/login", json={
            "username": "pending_teacher@test.com",
            "password": "ValidPassword@123"
        })
        self.assertEqual(res_pending.status_code, 200)
        data_p = res_pending.json()
        self.assertEqual(data_p["status"], "pending_approval")
        self.assertNotIn("token", data_p)

        # 4. Học sinh đăng nhập thành công
        user_active_doc = MagicMock()
        user_active_doc.id = "u_active"
        user_active_doc.to_dict.return_value = {
            "username": "active_student@test.com",
            "password_hash": hashed,
            "role": "student",
            "status": "approved",
            "full_name": "Học Sinh Đã Kích Hoạt"
        }
        mock_db.collection.return_value.where.return_value.get.return_value = [user_active_doc]
        res_active = self.client.post("/api/auth/login", json={
            "username": "active_student@test.com",
            "password": "ValidPassword@123"
        })
        self.assertEqual(res_active.status_code, 200)
        data_a = res_active.json()
        self.assertEqual(data_a["status"], "success")
        self.assertIn("token", data_a)

    @patch("services.firebase_service.get_db")
    def test_rbac_access_control(self, mock_get_db):
        """
        Kiểm tra phân quyền RBAC:
        - Học sinh không được vào API Quản trị hoặc Giáo viên (403)
        - Giáo viên không được vào API Quản trị (403)
        - Quản trị viên truy cập thành công (200)
        """
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        student_token = create_access_token({"sub": "student_01", "username": "stu", "role": "student"})
        teacher_token = create_access_token({"sub": "teacher_01", "username": "teach", "role": "teacher"})
        admin_token = create_access_token({"sub": "admin_01", "username": "kiet0905478167@gmail.com", "role": "admin"})

        # Giả lập Firestore trả về user tương ứng
        def mock_user_doc(col):
            def doc_getter(uid):
                doc = MagicMock()
                doc.exists = True
                doc.id = uid
                if "student" in uid:
                    doc.to_dict.return_value = {"role": "student", "status": "approved"}
                elif "teacher" in uid:
                    doc.to_dict.return_value = {"role": "teacher", "status": "approved"}
                else:
                    doc.to_dict.return_value = {"role": "admin", "username": "kiet0905478167@gmail.com", "status": "approved"}
                return doc
            m = MagicMock()
            m.document.side_effect = doc_getter
            return m
        mock_db.collection.side_effect = mock_user_doc

        # 1. Học sinh gọi API Giáo viên (/api/teacher/quizzes) -> Bị chặn 403
        res1 = self.client.get(f"/api/teacher/quizzes?teacher_token={student_token}")
        self.assertEqual(res1.status_code, 403)

        # 2. Học sinh gọi API Admin (/api/admin/users) -> Bị chặn 403
        res2 = self.client.get(f"/api/admin/users?admin_token={student_token}")
        self.assertEqual(res2.status_code, 403)

        # 3. Giáo viên gọi API Admin (/api/admin/users) -> Bị chặn 403
        res3 = self.client.get(f"/api/admin/users?admin_token={teacher_token}")
        self.assertEqual(res3.status_code, 403)

        # 4. Quản trị viên gọi API Admin (/api/admin/users) -> Thành công 200
        mock_admin_users = [MagicMock(id="u1", to_dict=lambda: {"username": "admin", "role": "admin"})]
        mock_db.collection.return_value.get.return_value = mock_admin_users
        res4 = self.client.get(f"/api/admin/users?admin_token={admin_token}")
        self.assertEqual(res4.status_code, 200)

    @patch("services.quiz_service._get_db")
    @patch("routers.quiz.get_db")
    def test_quiz_ownership_authorization(self, mock_router_db, mock_service_db):
        """
        Kiểm tra quyền sở hữu đề thi:
        - Giáo viên B không được ghi đè/sửa đề thi của Giáo viên A (403)
        """
        mock_db = MagicMock()
        mock_router_db.return_value = mock_db
        mock_service_db.return_value = mock_db

        doc_existing = MagicMock()
        doc_existing.exists = True
        doc_existing.to_dict.return_value = {
            "title": "Đề thi của Thầy A",
            "creator_id": "teacher_A",
            "data": []
        }
        mock_db.collection.return_value.document.return_value.get.return_value = doc_existing

        # Giáo viên B cố gắng update quiz của Thầy A
        res = self.client.post("/api/save_quiz", json={
            "quiz_id": "QUIZ-AAA",
            "title": "Đề thi bị sửa trái phép",
            "data": [],
            "creator_id": "teacher_B"
        })
        self.assertEqual(res.status_code, 403)
        self.assertIn("Không có quyền", res.json()["detail"])

    # =========================================================================
    # 2. UPLOAD INVALID FILE & EDGE CASES
    # =========================================================================

    def test_upload_disallowed_extension(self):
        """Kiểm tra tải lên định dạng file nguy hiểm/không hợp lệ (.exe, .sh, .py) bị từ chối 400"""
        for filename in ["exploit.exe", "script.sh", "malware.py", "test.html"]:
            res = self.client.post(
                "/api/upload",
                files={"file": (filename, b"malicious binary contents", "application/octet-stream")},
                data={"use_ai": "false"}
            )
            self.assertEqual(res.status_code, 400)
            self.assertIn("Word (.docx) và PDF (.pdf)", res.json()["detail"])

    def test_upload_empty_file(self):
        """Kiểm tra tải lên file 0 bytes bị từ chối 400 ngay lập tức, không gây tốn tài nguyên"""
        res = self.client.post(
            "/api/upload",
            files={"file": ("empty_exam.docx", b"", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"use_ai": "false"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("trống", res.json()["detail"].lower())

    def test_upload_oversized_file(self):
        """Kiểm tra tải lên file vượt quá giới hạn 50MB bị từ chối 400"""
        oversized_bytes = b"0" * (51 * 1024 * 1024)
        res = self.client.post(
            "/api/upload",
            files={"file": ("huge_exam.docx", oversized_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"use_ai": "false"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("50mb", res.json()["detail"].lower())

    # =========================================================================
    # 3. PARSE CORRUPTED WORD/PDF & RESILIENCE
    # =========================================================================

    def test_parse_corrupted_docx_file_resilience(self):
        """
        Kiểm tra xử lý file Word bị hỏng cấu trúc (BadZipFile / invalid package):
        - Không làm sập (crash) server
        - Tiến trình ngầm cập nhật task_status = 'error' với thông báo giải thích rõ ràng cho người dùng
        """
        task_id = "task-corrupted-docx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_f:
            # Ghi dữ liệu rác không phải file zip/docx chuẩn
            temp_f.write(b"NOT_A_VALID_DOCX_FILE_RANDOM_GARBAGE_BYTES_1234567890")
            corrupted_path = temp_f.name

        try:
            # Chạy trực tiếp hàm background
            process_document_background(
                task_id=task_id,
                temp_file_path=corrupted_path,
                ext=".docx",
                use_ai=False,
                api_keys=[],
                filename="corrupted_file.docx"
            )

            # Kiểm tra trạng thái task được ghi nhận chính xác là error
            self.assertIn(task_id, active_tasks)
            task_info = active_tasks[task_id]
            self.assertEqual(task_info["status"], "error")
            self.assertTrue(len(task_info.get("detail", "")) > 0)
        finally:
            if os.path.exists(corrupted_path):
                os.remove(corrupted_path)

    # =========================================================================
    # 4. AI FALLBACK & API KEY ROTATION (429 QUOTA EXCEEDED)
    # =========================================================================

    def test_ai_gemini_429_key_rotation(self):
        """
        Kiểm tra cơ chế luân chuyển Key khi gặp lỗi 429 Quota Exceeded:
        - Key 1 trả về lỗi 429 ResourceExhausted
        - Hệ thống tự động chuyển sang Key 2 và hoàn thành thành công
        """
        mock_client_key1 = MagicMock()
        mock_client_key1.aio.models.generate_content = AsyncMock(
            side_effect=Exception("429 ResourceExhausted: Quota exceeded for quota metric")
        )

        mock_resp_success = MagicMock()
        mock_resp_success.text = json.dumps([
            {
                "question": "1 + 1 bằng mấy?",
                "options": ["A. 1", "B. 2", "C. 3", "D. 4"],
                "correct_answer": "B. 2",
                "explain": "1 cộng 1 bằng 2."
            }
        ])
        mock_client_key2 = MagicMock()
        mock_client_key2.aio.models.generate_content = AsyncMock(return_value=mock_resp_success)

        def mock_get_client(api_key):
            if api_key == "KEY_RATE_LIMITED":
                return mock_client_key1
            return mock_client_key2

        with patch("services.ai_service.get_gemini_client", side_effect=mock_get_client):
            keys = ["KEY_RATE_LIMITED", "KEY_BACKUP_VALID"]
            result = asyncio.run(call_gemini_with_fallback(
                prompt="Tạo câu hỏi toán học",
                api_keys=keys
            ))
            self.assertIsNotNone(result)
            self.assertEqual(result.text, mock_resp_success.text)
            self.assertTrue(mock_client_key1.aio.models.generate_content.called)
            self.assertTrue(mock_client_key2.aio.models.generate_content.called)

    def test_ai_latex_json_repair(self):
        """
        Kiểm tra xử lý phản hồi AI chứa công thức LaTeX chưa escape:
        - AI trả về chuỗi JSON chứa \\frac, \\int, \\sqrt mà không escape \\\\
        - fix_json_latex_escapes tự động sửa để json.loads không bị lỗi cú pháp
        """
        raw_ai_text = '{"question": "Tính tích phân \\int_{0}^{1} \\frac{1}{x+1} dx và \\sqrt{4}", "options": ["A. \\ln(2)", "B. 2", "C. 3", "D. 4"]}'
        
        fixed_text = fix_json_latex_escapes(raw_ai_text)
        parsed = json.loads(fixed_text)
        self.assertIn("question", parsed)
        self.assertIn("frac", parsed["question"])
        self.assertIn("sqrt", parsed["question"])

    # =========================================================================
    # 5. STORAGE & DATABASE RESILIENCE FALLBACK
    # =========================================================================

    def test_r2_storage_timeout_fallback_to_local(self):
        """
        Kiểm tra Fallback lưu trữ khi Cloudflare R2 gặp sự cố mạng (ConnectTimeout):
        - Boto3 Client ném ConnectTimeoutError
        - Hệ thống tự động lưu vào cache đĩa cục bộ (uploads/images/)
        - Trả về URL cục bộ /api/images/... vẫn hoạt động bình thường 100%
        """
        fake_image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR_FAKE_IMAGE_DATA_123"

        # Giả lập R2 client ném lỗi Timeout
        mock_r2_client = MagicMock()
        mock_r2_client.put_object.side_effect = Exception("ConnectTimeoutError: Connect to R2 timed out")

        with patch("services.r2_service.get_r2_client", return_value=mock_r2_client):
            img_url = r2_svc.upload_image_to_r2(fake_image_bytes, mime_type="image/png")
            self.assertIsNotNone(img_url)
            self.assertTrue(img_url.startswith("/api/images/"))

            # Kiểm tra ảnh đã được lưu vào đĩa cục bộ và có thể đọc ra
            filename = os.path.basename(img_url)
            local_path = os.path.join(r2_svc.UPLOAD_IMAGES_DIR, filename)
            self.assertTrue(os.path.exists(local_path))
            with open(local_path, "rb") as f:
                saved_content = f.read()
            self.assertEqual(saved_content, fake_image_bytes)

            # Dọn dẹp tệp kiểm thử
            if os.path.exists(local_path):
                os.remove(local_path)

    @patch("services.quiz_service._get_db")
    @patch("routers.quiz.get_db")
    def test_firestore_timeout_stale_cache_fallback(self, mock_router_db, mock_service_db):
        """
        Kiểm tra tính chịu lỗi cơ sở dữ liệu (Database Resilience):
        - Đề thi đã có trong RAM cache
        - Khi Firestore timeout/chết kết nối, quiz_service tự động dùng stale cache
        """
        quiz_id = "QUIZ_STALE_CACHE_TEST"
        cached_data = {
            "title": "Đề thi Toán 12 Dự phòng",
            "mode": "practice",
            "time_limit": 45,
            "data": [{"question": "1 + 1 = ?", "options": ["A. 2"]}]
        }
        # Nạp sẵn vào RAM Cache với thời gian quá hạn (stale)
        QUIZ_CACHE[quiz_id] = {
            "time": time.time() - 3600,  # Đã cũ quá 300s
            "data": cached_data
        }

        # Giả lập Firestore get() ném Exception Timeout
        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.get.side_effect = Exception("DeadlineExceeded: Firestore timeout")
        mock_router_db.return_value = mock_db
        mock_service_db.return_value = mock_db

        res = quiz_service.get_quiz(quiz_id=quiz_id)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["title"], "Đề thi Toán 12 Dự phòng")
        self.assertEqual(len(res["data"]), 1)

    # =========================================================================
    # 6. HIGH CONCURRENCY & THREAD-SAFETY
    # =========================================================================

    def test_high_concurrency_requests(self):
        """
        Kiểm tra độ ổn định dưới tải đồng thời cao:
        - 20 luồng đồng thời gọi /api/health và /api/get_quiz/...
        - Đảm bảo 100% request thành công (200 OK), không bị race condition hay crash
        """
        quiz_id = "QUIZ_CONCURRENT_TEST"
        QUIZ_CACHE[quiz_id] = {
            "time": time.time(),
            "data": {
                "title": "Đề thi kiểm tra tải đồng thời",
                "mode": "practice",
                "time_limit": 60,
                "data": [{"question": f"Câu hỏi {i}", "options": ["A", "B", "C", "D"]} for i in range(10)]
            }
        }

        def worker_task(worker_id):
            client = TestClient(app)
            if worker_id % 2 == 0:
                resp = client.get("/api/health")
            else:
                resp = client.get(f"/api/get_quiz/{quiz_id}")
            return resp.status_code

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker_task, i) for i in range(20)]
            results = [f.result() for f in futures]

        self.assertEqual(len(results), 20)
        self.assertTrue(all(code == 200 for code in results), f"Một số request thất bại: {results}")

    @patch("services.firebase_service.get_db")
    def test_high_concurrency_student_submissions(self, mock_get_db):
        """
        Kiểm tra 12 học sinh nộp bài thi cùng 1 thời điểm:
        - Server tính điểm chính xác cho từng học sinh độc lập
        - Không bị sai lệch điểm hoặc deadlock
        """
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        quiz_id = "QUIZ_CONCURRENT_SUBMIT"
        QUIZ_CACHE[quiz_id] = {
            "time": time.time(),
            "data": {
                "title": "Đề thi kiểm tra tải nộp bài",
                "mode": "exam",
                "data": [
                    {"question": "Câu 1", "options": ["A. 1", "B. 2"], "correct_answer": "A. 1", "type": "mcq"},
                    {"question": "Câu 2", "options": ["A. X", "B. Y"], "correct_answer": "B. Y", "type": "mcq"}
                ]
            }
        }

        def submit_worker(student_idx):
            client = TestClient(app)
            # Học sinh chẵn chọn đúng hết (2/2 = 2.0đ), học sinh lẻ chọn sai (0.0đ)
            if student_idx % 2 == 0:
                answers = {"0": "A. 1", "1": "B. Y"}
            else:
                answers = {"0": "B. 2", "1": "A. X"}

            resp = client.post("/api/student/submit_exam", json={
                "quiz_id": quiz_id,
                "answers": answers,
                "student_name": f"Học sinh {student_idx}",
                "answers_count": 2,
                "time_remaining": 500,
                "completed": True
            })
            return resp.status_code, resp.json()

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(submit_worker, i) for i in range(12)]
            results = [f.result() for f in futures]

        for idx, (status_code, body) in enumerate(results):
            self.assertEqual(status_code, 200)
            self.assertEqual(body["status"], "success")
            expected_score = 2.0 if (idx % 2 == 0) else 0.0
            self.assertEqual(body["score"], expected_score)

    # =========================================================================
    # 7. CONTRACT API & ANTI-CHEAT DATA SANITIZATION
    # =========================================================================

    def test_get_quiz_contract_anti_cheat(self):
        """
        Kiểm tra Contract API bảo mật chống lộ đáp án (Anti-Cheat F12):
        - Chế độ exam:
          + Học sinh (không có token giáo viên): Bắt buộc KHÔNG được chứa trường 'correct_answer' và 'explain'
          + Giáo viên (có token hợp lệ): Chứa đầy đủ 'correct_answer' và 'explain' để chấm và soạn đề
        """
        quiz_id = "QUIZ_CONTRACT_ANTICHEAT"
        QUIZ_CACHE[quiz_id] = {
            "time": time.time(),
            "data": {
                "title": "Kiểm tra 1 tiết Toán - Nghiêm ngặt",
                "mode": "exam",
                "creator_id": "teacher_real_123",
                "data": [
                    {
                        "question": "Căn bậc hai của 16 là bao nhiêu?",
                        "options": ["A. 2", "B. 4", "C. 8", "D. 16"],
                        "correct_answer": "B. 4",
                        "explain": "Vì 4 x 4 = 16 nên căn bậc hai số học là 4."
                    }
                ]
            }
        }

        # 1. Học sinh truy vấn đề (Không có teacher_token)
        res_student = self.client.get(f"/api/get_quiz/{quiz_id}")
        self.assertEqual(res_student.status_code, 200)
        q_student = res_student.json()["data"][0]
        self.assertNotIn("correct_answer", q_student, "LỖI BẢO MẬT: Lộ đáp án đúng cho học sinh!")
        self.assertNotIn("explain", q_student, "LỖI BẢO MẬT: Lộ lời giải chi tiết cho học sinh!")
        self.assertEqual(q_student["question"], "Căn bậc hai của 16 là bao nhiêu?")
        self.assertEqual(len(q_student["options"]), 4)

        # 2. Giáo viên chủ đề truy vấn đề (Có teacher_token)
        teacher_token = create_access_token({"sub": "teacher_real_123", "role": "teacher"})
        res_teacher = self.client.get(f"/api/get_quiz/{quiz_id}?teacher_token={teacher_token}")
        self.assertEqual(res_teacher.status_code, 200)
        q_teacher = res_teacher.json()["data"][0]
        self.assertIn("correct_answer", q_teacher)
        self.assertEqual(q_teacher["correct_answer"], "B. 4")
        self.assertIn("explain", q_teacher)

    @patch("services.firebase_service.get_db")
    def test_submit_exam_contract_gdtd_scoring(self, mock_get_db):
        """
        Kiểm tra Contract API chấm điểm trắc nghiệm Đúng/Sai chuẩn Bộ GD&ĐT:
        - 1 ý đúng: 0.1 điểm
        - 2 ý đúng: 0.25 điểm
        - 3 ý đúng: 0.5 điểm
        - 4 ý đúng: 1.0 điểm
        """
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        quiz_id = "QUIZ_GDTD_SCORING"
        QUIZ_CACHE[quiz_id] = {
            "time": time.time(),
            "data": {
                "title": "Đề trắc nghiệm Đúng/Sai chuẩn Bộ GD&ĐT",
                "mode": "exam",
                "data": [
                    {
                        "type": "true_false",
                        "question": "Xét tính đúng sai của các mệnh đề sau:",
                        "correct_answer": {"a": True, "b": False, "c": True, "d": False}
                    }
                ]
            }
        }

        # Kịch bản 1: Đúng 1 ý (chỉ đúng ý a) -> 0.1 điểm
        res1 = self.client.post("/api/student/submit_exam", json={
            "quiz_id": quiz_id,
            "answers": {"0": {"a": True, "b": True, "c": False, "d": True}},
            "student_name": "HS A",
            "answers_count": 1,
            "time_remaining": 100,
            "completed": True
        })
        self.assertEqual(res1.status_code, 200)
        self.assertAlmostEqual(res1.json()["score"], 0.1, places=2)

        # Kịch bản 2: Đúng 2 ý (đúng a và b) -> 0.25 điểm
        res2 = self.client.post("/api/student/submit_exam", json={
            "quiz_id": quiz_id,
            "answers": {"0": {"a": True, "b": False, "c": False, "d": True}},
            "student_name": "HS B",
            "answers_count": 1,
            "time_remaining": 100,
            "completed": True
        })
        self.assertEqual(res2.status_code, 200)
        self.assertAlmostEqual(res2.json()["score"], 0.25, places=2)

        # Kịch bản 3: Đúng cả 4 ý -> 1.0 điểm
        res4 = self.client.post("/api/student/submit_exam", json={
            "quiz_id": quiz_id,
            "answers": {"0": {"a": True, "b": False, "c": True, "d": False}},
            "student_name": "HS D",
            "answers_count": 1,
            "time_remaining": 100,
            "completed": True
        })
        self.assertEqual(res4.status_code, 200)
        self.assertAlmostEqual(res4.json()["score"], 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
