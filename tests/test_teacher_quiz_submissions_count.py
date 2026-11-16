import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from core.state import QUIZ_CACHE, SUBMISSIONS_CACHE
from app.services.student_service import student_service, SubmitExamRequest, SubmitScoreRequest


def test_teacher_quizzes_returns_total_submissions():
    """Kiểm tra API /api/teacher/quizzes trả về đúng tổng số lượt làm bài."""
    client = TestClient(app)

    mock_quiz_1 = MagicMock()
    mock_quiz_1.id = "quiz_101"
    mock_quiz_1.to_dict.return_value = {
        'title': 'Đề kiểm tra 15 phút',
        'mode': 'exam',
        'status': 'published',
        'data': [{'question': '1+1=?'}],
        'time_limit': 15,
        'total_submissions': 8,
        'created_at': '2026-11-16T10:00:00Z',
        'updated_at': '2026-11-16T12:00:00Z'
    }

    mock_quiz_2 = MagicMock()
    mock_quiz_2.id = "quiz_102"
    mock_quiz_2.to_dict.return_value = {
        'title': 'Đề luyện tập không có total_submissions sẵn',
        'mode': 'practice',
        'status': 'published',
        'data': [{'question': '2+2=?'}],
        'time_limit': 0,
        'created_at': '2026-11-16T08:00:00Z',
        'updated_at': '2026-11-16T09:00:00Z'
    }
    # Mock subcollection count cho quiz_2
    mock_subs_agg = MagicMock()
    mock_subs_agg.value = 5
    mock_subs_col = MagicMock()
    mock_subs_col.count.return_value.get.return_value = [[mock_subs_agg]]
    mock_quiz_2.reference.collection.return_value = mock_subs_col

    mock_db = MagicMock()
    # Mock truy vấn quizzes theo creator_id
    mock_db.collection.return_value.where.return_value.get.return_value = [mock_quiz_1, mock_quiz_2]

    with patch('app.api.routes.teacher._get_db', return_value=mock_db), \
         patch('app.api.routes.teacher._verify_teacher_access', return_value=({'role': 'teacher'}, 'teacher_uid_123')):

        res = client.get("/api/teacher/quizzes?teacher_token=valid_teacher_token")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get('status') == 'success'
        quizzes = data.get('data', [])
        assert len(quizzes) == 2

        # quiz_101: lấy từ total_submissions = 8
        q1 = next(q for q in quizzes if q['id'] == 'quiz_101')
        assert q1['total_submissions'] == 8
        assert q1['submission_count'] == 8

        # quiz_102: fallback tính từ subcollection count = 5
        q2 = next(q for q in quizzes if q['id'] == 'quiz_102')
        assert q2['total_submissions'] == 5
        assert q2['submission_count'] == 5


def test_submit_exam_increments_total_submissions_for_guest_and_registered():
    """
    Kiểm tra tổng lượt làm đề tính cả học sinh không đăng nhập (guest)
    và học sinh có đăng nhập (registered).
    """
    # 1. Test thí sinh tự do (không đăng nhập)
    req_guest = SubmitExamRequest(
        quiz_id="quiz_test_counts",
        student_name="Học sinh tự do",
        student_token=None,
        time_elapsed=60,
        answers={"0": "A"}
    )

    mock_quiz_doc = MagicMock()
    mock_quiz_doc.exists = True
    mock_quiz_doc.to_dict.return_value = {
        'title': 'Đề test lượt làm',
        'data': [{'question': 'Câu 1?', 'options': ['A', 'B'], 'correct_answer': 'A', 'type': 'mcq'}],
        'status': 'published',
        'total_submissions': 0
    }

    mock_db = MagicMock()
    mock_quiz_ref = MagicMock()
    mock_quiz_ref.get.return_value = mock_quiz_doc
    mock_sub_ref = MagicMock()
    mock_sub_ref.id = "sub_guest_1"
    mock_quiz_ref.collection.return_value.document.return_value = mock_sub_ref

    mock_db.collection.return_value.document.return_value = mock_quiz_ref

    SUBMISSIONS_CACHE.pop("quiz_test_counts", None)
    QUIZ_CACHE.pop("quiz_test_counts", None)

    with patch.object(student_service, 'get_db', return_value=mock_db):
        res_guest = asyncio.run(student_service.submit_exam(req_guest))
        assert res_guest['status'] == 'success'

        # Đảm bảo bài thi của học sinh tự do được lưu
        assert mock_sub_ref.set.called
        sub_call_args = mock_sub_ref.set.call_args[0][0]
        assert sub_call_args['is_guest'] is True
        assert sub_call_args['student_name'] == 'Học sinh tự do'

        # Đảm bảo lệnh tăng total_submissions được gọi trên quiz document
        assert mock_quiz_ref.set.called
        quiz_update_args = mock_quiz_ref.set.call_args[0][0]
        assert 'total_submissions' in quiz_update_args

    # 2. Test thí sinh đã đăng nhập
    req_user = SubmitExamRequest(
        quiz_id="quiz_test_counts",
        student_name="Nguyễn Văn A",
        student_token="student_token_xyz",
        time_elapsed=90,
        answers={"0": "A"}
    )

    mock_user_doc = {'id': 'user_student_123', 'name': 'Nguyễn Văn A'}

    with patch.object(student_service, 'get_db', return_value=mock_db), \
         patch.object(student_service, 'get_user', return_value=mock_user_doc):
        res_user = asyncio.run(student_service.submit_exam(req_user))
        assert res_user['status'] == 'success'

        sub_call_args_user = mock_sub_ref.set.call_args_list[-2][0][0]
        assert sub_call_args_user['is_guest'] is False
        assert sub_call_args_user['student_id'] == 'user_student_123'

        # Đảm bảo tăng total_submissions cả với học sinh đã đăng nhập
        assert mock_quiz_ref.set.called
        quiz_update_args_user = mock_quiz_ref.set.call_args[0][0]
        assert 'total_submissions' in quiz_update_args_user


def test_submit_score_legacy_increments_total_submissions():
    """Kiểm tra luồng submit_score_legacy cũng cập nhật total_submissions."""
    req = SubmitScoreRequest(
        quiz_id="quiz_legacy_test",
        student_name="Thí sinh legacy",
        score=8,
        total_questions=10,
        time_elapsed=120
    )

    mock_db = MagicMock()
    mock_quiz_ref = MagicMock()
    mock_sub_ref = MagicMock()
    mock_quiz_ref.collection.return_value.document.return_value = mock_sub_ref
    mock_db.collection.return_value.document.return_value = mock_quiz_ref

    with patch.object(student_service, 'get_db', return_value=mock_db):
        res = asyncio.run(student_service.submit_score_legacy(req))
        assert res['status'] == 'success'
        assert mock_sub_ref.set.called
        assert mock_quiz_ref.set.called
        call_args = mock_quiz_ref.set.call_args[0][0]
        assert 'total_submissions' in call_args
