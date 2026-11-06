import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from core.state import QUIZ_CACHE

def test_quiz_status_and_cache_invalidation():
    client = TestClient(app)

    # 1. Mock a trashed quiz
    mock_trashed_doc = MagicMock()
    mock_trashed_doc.exists = True
    mock_trashed_doc.to_dict.return_value = {
        'title': 'De Thi Da Xoa',
        'data': [{'question': '1+1=?', 'options': ['1', '2'], 'correct_answer': 'B'}],
        'status': 'trashed',
        'creator_id': 'teacher_123'
    }

    mock_db = MagicMock()
    mock_db.collection.return_value.document.return_value.get.return_value = mock_trashed_doc

    with patch('services.firebase_service.get_db', return_value=mock_db), \
         patch('app.services.quiz_service._get_db', return_value=mock_db), \
         patch('app.api.routes.teacher._get_db', return_value=mock_db):

        # Student fetching trashed quiz -> Must return 404 (not 200)
        QUIZ_CACHE.pop('quiz_trashed_123', None)
        res = client.get('/api/get_quiz/quiz_trashed_123')
        assert res.status_code == 404, f"Expected 404 for trashed quiz, got {res.status_code}"
        assert "xóa" in res.json().get('detail', '').lower()
        print("Test 1 Passed: Trashed quiz returns 404 for students")

        # 2. Mock an unpublished (locked) quiz
        mock_locked_doc = MagicMock()
        mock_locked_doc.exists = True
        mock_locked_doc.to_dict.return_value = {
            'title': 'De Thi Da Khoa',
            'data': [{'question': '1+1=?', 'options': ['1', '2'], 'correct_answer': 'B'}],
            'status': 'unpublished',
            'creator_id': 'teacher_123'
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_locked_doc

        QUIZ_CACHE.pop('quiz_locked_123', None)
        res_locked = client.get('/api/get_quiz/quiz_locked_123')
        assert res_locked.status_code == 403, f"Expected 403 for locked quiz, got {res_locked.status_code}"
        assert "khóa" in res_locked.json().get('detail', '').lower()
        print("Test 2 Passed: Locked/unpublished quiz returns 403 for students")

        # 3. Test Cache Invalidation on toggle_publish
        QUIZ_CACHE['quiz_test_cache'] = {'time': 9999999999, 'data': {'status': 'unpublished'}}
        assert 'quiz_test_cache' in QUIZ_CACHE

        mock_user = {'id': 'teacher_123', 'role': 'teacher'}
        with patch('app.api.routes.teacher._verify_teacher_access', return_value=(mock_user, 'teacher_123')):
            res_toggle = client.post('/api/teacher/toggle_publish', json={
                'teacher_token': 'fake_token',
                'quiz_id': 'quiz_test_cache',
                'status': 'published'
            })
            assert res_toggle.status_code == 200
            assert 'quiz_test_cache' not in QUIZ_CACHE, "QUIZ_CACHE must be evicted on toggle_publish!"
            print("Test 3 Passed: toggle_publish successfully evicts QUIZ_CACHE")

        # 4. Test Cache Invalidation on quiz_action (trash & permanent)
        QUIZ_CACHE['quiz_test_trash'] = {'time': 9999999999, 'data': {'status': 'published'}}
        with patch('app.api.routes.teacher._verify_teacher_access', return_value=(mock_user, 'teacher_123')):
            res_act = client.post('/api/teacher/quiz_action', json={
                'teacher_token': 'fake_token',
                'quiz_id': 'quiz_test_trash',
                'action': 'trash'
            })
            assert res_act.status_code == 200
            assert 'quiz_test_trash' not in QUIZ_CACHE, "QUIZ_CACHE must be evicted on trash action!"
            print("Test 4 Passed: quiz_action('trash') successfully evicts QUIZ_CACHE")

        QUIZ_CACHE['quiz_test_perm'] = {'time': 9999999999, 'data': {'status': 'trashed'}}
        with patch('app.api.routes.teacher._verify_teacher_access', return_value=(mock_user, 'teacher_123')):
            res_perm = client.post('/api/teacher/quiz_action', json={
                'teacher_token': 'fake_token',
                'quiz_id': 'quiz_test_perm',
                'action': 'permanent'
            })
            assert res_perm.status_code == 200
            assert 'quiz_test_perm' not in QUIZ_CACHE, "QUIZ_CACHE must be evicted on permanent delete!"
            print("Test 5 Passed: quiz_action('permanent') successfully evicts QUIZ_CACHE")

    print("\nALL QUIZ STATUS & CACHE TESTS PASSED 100%!")

if __name__ == '__main__':
    test_quiz_status_and_cache_invalidation()
