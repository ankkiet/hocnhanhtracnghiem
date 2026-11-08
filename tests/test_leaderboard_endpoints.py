import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from core.state import LEADERBOARD_CACHE, SUBMISSIONS_CACHE, QUIZ_CACHE
from app.services.student_service import student_service

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_caches():
    LEADERBOARD_CACHE.clear()
    SUBMISSIONS_CACHE.clear()
    QUIZ_CACHE.clear()
    yield
    LEADERBOARD_CACHE.clear()
    SUBMISSIONS_CACHE.clear()
    QUIZ_CACHE.clear()

def test_leaderboard_endpoints_both_paths():
    """Kiểm tra cả 2 đường dẫn /api/leaderboard/{id} và /api/student/leaderboard/{id} đều hoạt động chính xác."""
    mock_db = MagicMock()
    mock_sub1 = MagicMock()
    mock_sub1.to_dict.return_value = {
        "student_name": "Nguyen Van A",
        "score": 10.0,
        "total_questions": 10,
        "time_elapsed": 120
    }
    mock_sub2 = MagicMock()
    mock_sub2.to_dict.return_value = {
        "student_name": "Tran Thi B",
        "score": 9.0,
        "total_questions": 10,
        "time_elapsed": 90
    }
    
    mock_query = MagicMock()
    mock_query.get.return_value = [mock_sub1, mock_sub2]
    mock_subs_ref = MagicMock()
    mock_subs_ref.order_by.return_value.limit.return_value = mock_query

    mock_db.collection.return_value.document.return_value.collection.return_value = mock_subs_ref

    with patch.object(student_service, "get_db", return_value=mock_db):
        # 1. Gọi đường dẫn frontend (/api/leaderboard/{quiz_id})
        res1 = client.get("/api/leaderboard/QUIZ_TEST_1")
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "success"
        assert len(data1["data"]) == 2
        assert data1["data"][0]["student_name"] == "Nguyen Van A"
        assert data1["data"][0]["score"] == 10.0

        # 2. Gọi đường dẫn gốc (/api/student/leaderboard/{quiz_id})
        res2 = client.get("/api/student/leaderboard/QUIZ_TEST_1")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "success"
        assert len(data2["data"]) == 2
        assert data2["data"][0]["student_name"] == "Nguyen Van A"

def test_leaderboard_tie_breaking_and_limit_5():
    """Kiểm tra logic tie-break: cùng điểm số thì người ít thời gian hơn xếp trước, và chỉ lấy top 5."""
    mock_db = MagicMock()
    
    # 7 thí sinh, nhiều người cùng điểm 10
    submissions = [
        {"student_name": "Student Slow 10", "score": 10.0, "total_questions": 10, "time_elapsed": 300},
        {"student_name": "Student Fast 10", "score": 10.0, "total_questions": 10, "time_elapsed": 45},
        {"student_name": "Student Mid 10", "score": 10.0, "total_questions": 10, "time_elapsed": 120},
        {"student_name": "Student Fast 9", "score": 9.0, "total_questions": 10, "time_elapsed": 60},
        {"student_name": "Student Slow 9", "score": 9.0, "total_questions": 10, "time_elapsed": 150},
        {"student_name": "Student 8", "score": 8.0, "total_questions": 10, "time_elapsed": 80},
        {"student_name": "Student 7", "score": 7.0, "total_questions": 10, "time_elapsed": 100},
    ]
    
    mock_docs = []
    for s in submissions:
        doc = MagicMock()
        doc.to_dict.return_value = s
        mock_docs.append(doc)

    mock_query = MagicMock()
    mock_query.get.return_value = mock_docs
    mock_subs_ref = MagicMock()
    mock_subs_ref.order_by.return_value.limit.return_value = mock_query
    mock_db.collection.return_value.document.return_value.collection.return_value = mock_subs_ref

    with patch.object(student_service, "get_db", return_value=mock_db):
        res = client.get("/api/leaderboard/QUIZ_TIE")
        assert res.status_code == 200
        data = res.json()["data"]
        
        # Chỉ lấy tối đa 5 người
        assert len(data) == 5
        
        # Hạng 1 phải là Student Fast 10 (45s)
        assert data[0]["student_name"] == "Student Fast 10"
        assert data[0]["score"] == 10.0
        assert data[0]["time_elapsed"] == 45
        
        # Hạng 2 là Student Mid 10 (120s)
        assert data[1]["student_name"] == "Student Mid 10"
        
        # Hạng 3 là Student Slow 10 (300s)
        assert data[2]["student_name"] == "Student Slow 10"
        
        # Hạng 4 là Student Fast 9 (60s)
        assert data[3]["student_name"] == "Student Fast 9"
        
        # Hạng 5 là Student Slow 9 (150s)
        assert data[4]["student_name"] == "Student Slow 9"

def test_leaderboard_auto_populates_missing_total_questions():
    """Kiểm tra tự động điền total_questions từ quiz nếu bản ghi cũ thiếu total_questions."""
    mock_db = MagicMock()
    mock_sub = MagicMock()
    mock_sub.to_dict.return_value = {
        "student_name": "Legacy Student",
        "score": 38.0,
        "total_questions": 0,  # Thiếu / = 0
        "time_elapsed": 500
    }
    
    mock_query = MagicMock()
    mock_query.get.return_value = [mock_sub]
    mock_subs_ref = MagicMock()
    mock_subs_ref.order_by.return_value.limit.return_value = mock_query

    # Mock quiz document có 40 câu
    mock_quiz_doc = MagicMock()
    mock_quiz_doc.exists = True
    mock_quiz_doc.to_dict.return_value = {
        "data": [{"question": f"Q{i}"} for i in range(40)]
    }

    def mock_collection(name):
        coll = MagicMock()
        if name == "quizzes":
            def mock_doc(doc_id):
                doc_mock = MagicMock()
                doc_mock.get.return_value = mock_quiz_doc
                doc_mock.collection.return_value = mock_subs_ref
                return doc_mock
            coll.document.side_effect = mock_doc
        return coll

    mock_db.collection.side_effect = mock_collection

    with patch.object(student_service, "get_db", return_value=mock_db):
        res = client.get("/api/leaderboard/QUIZ_LEGACY")
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["total_questions"] == 40
