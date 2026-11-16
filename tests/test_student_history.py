import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.security import create_access_token
from core.state import STUDENT_HISTORY_CACHE
from main import app


class TestStudentHistory(unittest.TestCase):
    def setUp(self):
        STUDENT_HISTORY_CACHE.clear()
        self.client = TestClient(app)
        self.mock_user = {
            'id': 'test_student_123',
            'username': 'student@example.com',
            'role': 'student',
            'full_name': 'Nguyễn Văn Học Sinh'
        }
        self.token = create_access_token({
            'sub': self.mock_user['id'],
            'username': self.mock_user['username'],
            'role': 'student',
            'full_name': self.mock_user['full_name']
        })

    @patch('routers.student.get_user_from_token')
    @patch('routers.student.get_db')
    def test_get_student_history_empty(self, mock_get_db, mock_get_user):
        mock_get_user.return_value = self.mock_user
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.limit.return_value.get.return_value = []
        mock_db.collection.return_value.document.return_value.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db

        res = self.client.get(f"/api/student/history?student_token={self.token}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(len(data.get("data", [])), 0)

    @patch('routers.student.get_user_from_token')
    @patch('routers.student.get_db')
    def test_get_student_history_with_records(self, mock_get_db, mock_get_user):
        mock_get_user.return_value = self.mock_user
        mock_db = MagicMock()

        mock_doc1 = MagicMock()
        mock_doc1.id = "sub_doc_1"
        mock_doc1.to_dict.return_value = {
            "quiz_id": "ABC-123",
            "quiz_title": "Kiểm tra 15p Vật lý",
            "score": 9.0,
            "total_questions": 10,
            "time_elapsed": 450,
            "submitted_at": "2026-11-12T10:00:00Z"
        }

        mock_doc2 = MagicMock()
        mock_doc2.id = "sub_doc_2"
        mock_doc2.to_dict.return_value = {
            "quiz_id": "XYZ-999",
            "quiz_title": "Đề thi thử Toán học",
            "score": 7.5,
            "total_questions": 10,
            "time_elapsed": 600,
            "submitted_at": "2026-11-12T11:00:00Z"
        }

        mock_coll = MagicMock()
        mock_coll.limit.return_value.get.return_value = [mock_doc1, mock_doc2]
        mock_db.collection.return_value.document.return_value.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db

        res = self.client.get(f"/api/student/history?student_token={self.token}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(len(data.get("data")), 2)
        # Sắp xếp mới nhất lên đầu
        self.assertEqual(data["data"][0]["quiz_id"], "XYZ-999")
        self.assertEqual(data["data"][1]["quiz_id"], "ABC-123")

    @patch('routers.student.get_user_from_token')
    @patch('routers.student.get_db')
    def test_get_student_history_sort_newest_first_with_mixed_formats(self, mock_get_db, mock_get_user):
        """Kiểm tra danh sách bài thi đã làm luôn sắp xếp theo thời gian mới nhất lên đầu với nhiều định dạng ngày."""
        mock_get_user.return_value = self.mock_user
        mock_db = MagicMock()

        # Đề cũ hơn: ngày 14/11/2026
        mock_doc_old = MagicMock()
        mock_doc_old.id = "sub_doc_old"
        mock_doc_old.to_dict.return_value = {
            "quiz_id": "OLD-001",
            "quiz_title": "Đề ngày 14",
            "score": 10.0,
            "submitted_at": "14/11/2026 09:00:00"
        }

        # Đề mới nhất: ngày 16/11/2026 (ISO format)
        mock_doc_newest = MagicMock()
        mock_doc_newest.id = "sub_doc_newest"
        mock_doc_newest.to_dict.return_value = {
            "quiz_id": "NEW-003",
            "quiz_title": "Đề mới nhất ngày 16",
            "score": 8.0,
            "submitted_at": "2026-11-16T20:30:00Z"
        }

        # Đề ở giữa: ngày 15/11/2026 (Vietnamese locale string)
        mock_doc_mid = MagicMock()
        mock_doc_mid.id = "sub_doc_mid"
        mock_doc_mid.to_dict.return_value = {
            "quiz_id": "MID-002",
            "quiz_title": "Đề giữa ngày 15",
            "score": 7.0,
            "submitted_at": "15/11/2026, 21:00:00"
        }

        mock_coll = MagicMock()
        mock_coll.limit.return_value.get.return_value = [mock_doc_old, mock_doc_newest, mock_doc_mid]
        mock_db.collection.return_value.document.return_value.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db

        res = self.client.get(f"/api/student/history?student_token={self.token}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(len(data.get("data")), 3)

        # Thứ tự phải luôn là: Mới nhất (NEW-003 ngày 16) -> Giữa (MID-002 ngày 15) -> Cũ (OLD-001 ngày 14)
        self.assertEqual(data["data"][0]["quiz_id"], "NEW-003")
        self.assertEqual(data["data"][1]["quiz_id"], "MID-002")
        self.assertEqual(data["data"][2]["quiz_id"], "OLD-001")

    @patch('routers.student.get_user_from_token')
    @patch('routers.student.get_db')
    def test_get_student_history_detail(self, mock_get_db, mock_get_user):
        mock_get_user.return_value = self.mock_user
        mock_db = MagicMock()

        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.id = "sub_doc_1"
        mock_doc.to_dict.return_value = {
            "quiz_id": "ABC-123",
            "quiz_title": "Kiểm tra 15p Vật lý",
            "score": 9.0,
            "total_questions": 10,
            "time_elapsed": 450,
            "results": [
                {
                    "question_index": 0,
                    "question": "Vận tốc ánh sáng là bao nhiêu?",
                    "options": ["300.000 km/s", "150.000 km/s"],
                    "user_answer": "300.000 km/s",
                    "correct_answer": "300.000 km/s",
                    "is_correct": True,
                    "earned": 1.0,
                    "explain": "Ánh sáng truyền trong chân không với vận tốc c = 3.10^8 m/s"
                }
            ]
        }
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc
        mock_get_db.return_value = mock_db

        res = self.client.get(f"/api/student/history/sub_doc_1?student_token={self.token}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data["data"]["quiz_id"], "ABC-123")
        self.assertEqual(len(data["data"]["results"]), 1)

    @patch('routers.student.get_user_from_token')
    @patch('routers.student.get_db')
    def test_delete_student_history(self, mock_get_db, mock_get_user):
        mock_get_user.return_value = self.mock_user
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref
        mock_get_db.return_value = mock_db

        res = self.client.delete(f"/api/student/history/sub_doc_1?student_token={self.token}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "success")
        mock_doc_ref.delete.assert_called_once()

    @patch('routers.student.get_user_from_token')
    @patch('routers.student.get_db')
    def test_sync_student_history(self, mock_get_db, mock_get_user):
        mock_get_user.return_value = self.mock_user
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.limit.return_value.get.return_value = []
        mock_new_doc = MagicMock()
        mock_new_doc.id = "new_sync_1"
        mock_coll.document.return_value = mock_new_doc
        mock_db.collection.return_value.document.return_value.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db

        payload = {
            "student_token": self.token,
            "history_items": [
                {
                    "quiz_id": "SYNC-001",
                    "quiz_title": "Đề thi offline",
                    "score": 8.0,
                    "total_questions": 10,
                    "time_elapsed": 500,
                    "submitted_at": "2026-11-15T09:00:00Z"
                }
            ]
        }
        res = self.client.post("/api/student/sync_history", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("saved_count"), 1)
        mock_new_doc.set.assert_called_once()

    @patch('routers.student.get_user_from_token')
    @patch('routers.student.get_db')
    def test_get_student_history_pagination_and_cache(self, mock_get_db, mock_get_user):
        """Kiểm tra cơ chế phân trang 5 bài/lần và tận dụng RAM cache không tốn read Firestore."""
        mock_get_user.return_value = self.mock_user
        mock_db = MagicMock()

        mock_docs = []
        for i in range(7):
            md = MagicMock()
            md.id = f"sub_doc_{i}"
            md.to_dict.return_value = {
                "quiz_id": f"QUIZ-{i}",
                "quiz_title": f"Đề thi số {i}",
                "score": 8.0,
                "total_questions": 10,
                "time_elapsed": 300,
                "submitted_at": f"2026-11-{10 + i:02d}T10:00:00Z",
                "results": [{"q": "test"}]  # Kết quả chi tiết phải bị xóa trong danh sách
            }
            mock_docs.append(md)

        mock_coll = MagicMock()
        mock_coll.limit.return_value.get.return_value = mock_docs
        mock_db.collection.return_value.document.return_value.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db

        # 1. Gọi lần đầu tiên (limit=5, offset=0)
        res1 = self.client.get(f"/api/student/history?student_token={self.token}&limit=5&offset=0")
        self.assertEqual(res1.status_code, 200)
        d1 = res1.json()
        self.assertEqual(d1["status"], "success")
        self.assertEqual(len(d1["data"]), 5)
        self.assertEqual(d1["total"], 7)
        self.assertTrue(d1["has_more"])
        self.assertFalse(d1.get("cached", False))
        # Kiểm tra results chi tiết đã được gọt bỏ để tiết kiệm payload và RAM
        self.assertNotIn("results", d1["data"][0])

        # 2. Gọi lần thứ hai (tải thêm: limit=5, offset=5) -> Phải trúng RAM cache (cached=True), 0 read Firestore
        res2 = self.client.get(f"/api/student/history?student_token={self.token}&limit=5&offset=5")
        self.assertEqual(res2.status_code, 200)
        d2 = res2.json()
        self.assertEqual(d2["status"], "success")
        self.assertEqual(len(d2["data"]), 2)
        self.assertEqual(d2["total"], 7)
        self.assertFalse(d2["has_more"])
        self.assertTrue(d2.get("cached", False))

    @patch('routers.student.get_user_from_token')
    @patch('routers.student.get_db')
    def test_get_student_history_auto_delete_expired_30_days(self, mock_get_db, mock_get_user):
        """Kiểm tra các bài thi quá hạn 30 ngày tự động bị xóa khỏi database và không hiển thị cho học sinh."""
        mock_get_user.return_value = self.mock_user
        mock_db = MagicMock()

        # Bài 1: Đã quá hạn 35 ngày (ngày 10/10/2026 so với 17/11/2026)
        mock_doc_expired = MagicMock()
        mock_doc_expired.id = "sub_doc_expired"
        mock_doc_expired.reference = MagicMock()
        mock_doc_expired.to_dict.return_value = {
            "quiz_id": "EXP-001",
            "quiz_title": "Đề thi đã quá hạn 35 ngày",
            "score": 6.0,
            "total_questions": 10,
            "submitted_at": "2026-10-10T10:00:00Z"
        }

        # Bài 2: Vừa làm 3 ngày trước (hợp lệ)
        mock_doc_valid = MagicMock()
        mock_doc_valid.id = "sub_doc_valid"
        mock_doc_valid.reference = MagicMock()
        mock_doc_valid.to_dict.return_value = {
            "quiz_id": "VALID-002",
            "quiz_title": "Đề thi còn hạn",
            "score": 9.5,
            "total_questions": 10,
            "submitted_at": "2026-11-14T15:00:00Z"
        }

        mock_coll = MagicMock()
        mock_coll.limit.return_value.get.return_value = [mock_doc_expired, mock_doc_valid]
        mock_db.collection.return_value.document.return_value.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db

        res = self.client.get(f"/api/student/history?student_token={self.token}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        # Chỉ bài hợp lệ được trả về
        self.assertEqual(len(data.get("data")), 1)
        self.assertEqual(data["data"][0]["quiz_id"], "VALID-002")
        # Bản ghi quá hạn phải được gọi hàm delete() để xóa vĩnh viễn khỏi CSDL
        mock_doc_expired.reference.delete.assert_called_once()
        mock_doc_valid.reference.delete.assert_not_called()

    @patch('routers.student.get_user_from_token')
    @patch('routers.student.get_db')
    def test_sync_student_history_skips_expired_30_days(self, mock_get_db, mock_get_user):
        """Kiểm tra khi đồng bộ từ máy học sinh, các bài cũ quá 30 ngày sẽ bị bỏ qua không lưu vào CSDL."""
        mock_get_user.return_value = self.mock_user
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.limit.return_value.get.return_value = []
        mock_new_doc = MagicMock()
        mock_new_doc.id = "new_sync_1"
        mock_coll.document.return_value = mock_new_doc
        mock_db.collection.return_value.document.return_value.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db

        payload = {
            "student_token": self.token,
            "history_items": [
                {
                    "quiz_id": "OLD-OFFLINE",
                    "quiz_title": "Đề offline 40 ngày trước",
                    "score": 5.0,
                    "total_questions": 10,
                    "time_elapsed": 400,
                    "submitted_at": "2026-10-01T08:00:00Z"  # > 30 ngày
                },
                {
                    "quiz_id": "NEW-OFFLINE",
                    "quiz_title": "Đề offline 2 ngày trước",
                    "score": 9.0,
                    "total_questions": 10,
                    "time_elapsed": 400,
                    "submitted_at": "2026-11-15T08:00:00Z"  # Còn hạn
                }
            ]
        }
        res = self.client.post("/api/student/sync_history", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        # Chỉ lưu 1 bài còn hạn, bài 40 ngày trước bị bỏ qua
        self.assertEqual(data.get("saved_count"), 1)
        mock_new_doc.set.assert_called_once()
        saved_doc_data = mock_new_doc.set.call_args[0][0]
        self.assertEqual(saved_doc_data["quiz_id"], "NEW-OFFLINE")
        self.assertIn("expire_at", saved_doc_data)

if __name__ == '__main__':
    unittest.main()
