import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from unittest.mock import MagicMock, patch

def test_og_share():
    client = TestClient(app)

    # 1. Test Home page
    res_home = client.get('/')
    assert res_home.status_code == 200
    html_home = res_home.text
    assert 'unnamed.jpg' in html_home, "unnamed.jpg must be in home page"
    assert 'og:image' in html_home, "og:image must be in home page"
    print("Test 1 Passed: Home page has unnamed.jpg for og:image")

    # 2. Test Quiz page with mock db
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        'title': 'Kiem Tra 15 Phut Toan 12',
        'data': [{}, {}, {}],
        'time_limit': 15
    }
    mock_db = MagicMock()
    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

    with patch('main.get_db', return_value=mock_db):
        res_quiz = client.get('/?id=test12345')
        assert res_quiz.status_code == 200
        html_quiz = res_quiz.text
        assert 'Kiem Tra 15 Phut Toan 12' in html_quiz
        assert '<title>Kiem Tra 15 Phut Toan 12 - HocNhanhTN</title>' in html_quiz
        assert 'property="og:title" content="Kiem Tra 15 Phut Toan 12"' in html_quiz
        assert 'unnamed.jpg' in html_quiz
        print("Test 2 Passed: /?id= correctly replaces title and og:title with real quiz name and unnamed.jpg")

        # Test /quiz/test12345 path
        res_path = client.get('/quiz/test12345')
        assert res_path.status_code == 200
        html_path = res_path.text
        assert '<title>Kiem Tra 15 Phut Toan 12 - HocNhanhTN</title>' in html_path
        assert 'property="og:title" content="Kiem Tra 15 Phut Toan 12"' in html_path
        print("Test 3 Passed: /quiz/test12345 path route works identically")

if __name__ == '__main__':
    test_og_share()
    print("ALL TESTS PASSED SUCCESSFULLY!")
