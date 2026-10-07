import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from core.state import active_tasks


class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check_endpoint(self):
        """Kiểm tra endpoint /api/health trả về 200 OK"""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data.get("status"), "ok")

    def test_ping_endpoint(self):
        """Kiểm tra endpoint /ping trả về 200 OK"""
        response = self.client.get("/ping")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data.get("status"), "ok")

    def test_task_status_not_found(self):
        """Kiểm tra /api/task_status với task_id không tồn tại trả về 404"""
        response = self.client.get("/api/task_status/nonexistent-id-9999")
        self.assertEqual(response.status_code, 404)

    def test_task_status_found(self):
        """Kiểm tra /api/task_status với task đang hoạt động"""
        task_id = "test-task-123"
        active_tasks[task_id] = {
            "status": "processing",
            "message": "Đang phân tích..."
        }
        try:
            response = self.client.get(f"/api/task_status/{task_id}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data.get("status"), "processing")
            self.assertEqual(data.get("message"), "Đang phân tích...")
        finally:
            active_tasks.pop(task_id, None)

    def test_upload_invalid_extension(self):
        """Kiểm tra upload file với định dạng không được hỗ trợ trả về 400"""
        response = self.client.post(
            "/api/upload",
            files={"file": ("test.txt", b"Hello world", "text/plain")}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Hệ thống chỉ hỗ trợ định dạng", response.json().get("detail", ""))

    def test_serve_image_not_found(self):
        """Kiểm tra /api/images/{file_path} khi ảnh không tồn tại trả về 404"""
        with patch("routers.document.get_stored_image", return_value=(None, None)):
            response = self.client.get("/api/images/nonexistent_image.png")
            self.assertEqual(response.status_code, 404)

    def test_serve_image_found(self):
        """Kiểm tra /api/images/{file_path} khi ảnh tồn tại trả về 200 với đúng mime type"""
        fake_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        with patch("routers.document.get_stored_image", return_value=(fake_bytes, "image/png")):
            response = self.client.get("/api/images/sample.png")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, fake_bytes)
            self.assertEqual(response.headers.get("content-type"), "image/png")

    @patch("routers.auth.get_db")
    def test_select_role_student(self, mock_get_db):
        """Kiểm tra chọn vai trò Học sinh được kích hoạt ngay và nhận token"""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "email": "student@example.com",
            "username": "student@example.com",
            "full_name": "Nguyen Van Hoc Sinh",
            "status": "needs_role"
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        response = self.client.post("/api/auth/select_role", json={"user_id": "u123", "role": "student"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["role"], "student")
        self.assertIn("token", data)
        mock_db.collection.return_value.document.return_value.update.assert_called_once()
        update_args = mock_db.collection.return_value.document.return_value.update.call_args[0][0]
        self.assertEqual(update_args["role"], "student")
        self.assertEqual(update_args["status"], "approved")

    @patch("routers.auth.get_db")
    def test_select_role_teacher_pending_approval(self, mock_get_db):
        """Kiểm tra chọn vai trò Giáo viên phải chờ Admin duyệt và không cấp token ngay"""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "email": "teacher@example.com",
            "username": "teacher@example.com",
            "full_name": "Tran Thi Giao Vien",
            "status": "needs_role"
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        response = self.client.post("/api/auth/select_role", json={"user_id": "u456", "role": "teacher"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "pending_approval")
        self.assertEqual(data["role"], "teacher")
        self.assertNotIn("token", data)
        update_args = mock_db.collection.return_value.document.return_value.update.call_args[0][0]
        self.assertEqual(update_args["role"], "teacher")
        self.assertEqual(update_args["status"], "pending")

    @patch("routers.auth.get_db")
    def test_check_approval_status(self, mock_get_db):
        """Kiểm tra endpoint kiểm tra trạng thái duyệt tài khoản giáo viên"""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "email": "teacher@example.com",
            "username": "teacher@example.com",
            "full_name": "Tran Thi Giao Vien",
            "role": "teacher",
            "status": "pending"
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        # Khi đang chờ duyệt
        res_pending = self.client.get("/api/auth/check_approval_status?user_id=u456")
        self.assertEqual(res_pending.status_code, 200)
        self.assertEqual(res_pending.json()["status"], "pending")
        
        # Khi đã được Admin duyệt
        mock_doc.to_dict.return_value["status"] = "approved"
        res_approved = self.client.get("/api/auth/check_approval_status?user_id=u456")
        self.assertEqual(res_approved.status_code, 200)
        self.assertEqual(res_approved.json()["status"], "approved")
    @patch("routers.auth.get_db")
    def test_select_role_with_profile_fields(self, mock_get_db):
        """Kiểm tra chọn vai trò kèm thông tin họ tên, lớp, sđt, trường học"""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "email": "teacher_new@example.com",
            "username": "teacher_new@example.com",
            "full_name": "Google User",
            "status": "needs_role"
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        payload = {
            "user_id": "u789",
            "role": "teacher",
            "full_name": "Thầy Nguyễn Văn Nam",
            "class_name": "Tổ Toán - Khối 12",
            "phone": "0987654321",
            "school": "THPT Chuyên Hà Nội - Amsterdam"
        }
        response = self.client.post("/api/auth/select_role", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "pending_approval")
        self.assertEqual(data["role"], "teacher")
        self.assertEqual(data["full_name"], "Thầy Nguyễn Văn Nam")
        self.assertEqual(data["class_name"], "Tổ Toán - Khối 12")
        self.assertEqual(data["phone"], "0987654321")
        self.assertEqual(data["school"], "THPT Chuyên Hà Nội - Amsterdam")
        
        update_args = mock_db.collection.return_value.document.return_value.update.call_args[0][0]
        self.assertEqual(update_args["role"], "teacher")
        self.assertEqual(update_args["status"], "pending")
        self.assertEqual(update_args["full_name"], "Thầy Nguyễn Văn Nam")
        self.assertEqual(update_args["class_name"], "Tổ Toán - Khối 12")
        self.assertEqual(update_args["phone"], "0987654321")
        self.assertEqual(update_args["school"], "THPT Chuyên Hà Nội - Amsterdam")
        self.assertTrue(update_args["profile_completed"])


if __name__ == "__main__":
    unittest.main()
