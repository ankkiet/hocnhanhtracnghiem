import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from core.security import create_access_token

class TestStudentHistory(unittest.TestCase):
    def setUp(self):
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
            "submitted_at": "2026-10-12T10:00:00Z"
        }

        mock_doc2 = MagicMock()
        mock_doc2.id = "sub_doc_2"
        mock_doc2.to_dict.return_value = {
            "quiz_id": "XYZ-999",
            "quiz_title": "Đề thi thử Toán học",
            "score": 7.5,
            "total_questions": 10,
            "time_elapsed": 600,
            "submitted_at": "2026-10-12T11:00:00Z"
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
                    "submitted_at": "2026-10-12T09:00:00Z"
                }
            ]
        }
        res = self.client.post("/api/student/sync_history", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("saved_count"), 1)
        mock_new_doc.set.assert_called_once()

if __name__ == '__main__':
    unittest.main()
