import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app


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

        # Test /thi/test12345 (Làm bài theo schema mới)
        res_thi = client.get('/thi/test12345')
        assert res_thi.status_code == 200
        html_thi = res_thi.text
        assert '<title>Kiem Tra 15 Phut Toan 12 - HocNhanhTN</title>' in html_thi
        print("Test 4 Passed: /thi/test12345 serves exam page with dynamic title")

        # Test /thi/test12345/ten-de-thi (Làm bài kèm friendly slug sau mã đề)
        res_thi_slug = client.get('/thi/test12345/kiem-tra-15-phut-toan-12')
        assert res_thi_slug.status_code == 200
        html_thi_slug = res_thi_slug.text
        assert '<title>Kiem Tra 15 Phut Toan 12 - HocNhanhTN</title>' in html_thi_slug
        assert 'property="og:title" content="Kiem Tra 15 Phut Toan 12"' in html_thi_slug
        assert '/thi/test12345/kiem-tra-15-phut-toan-12' in html_thi_slug
        print("Test 4b Passed: /thi/test12345/slug serves exam page with slug in canonical URL and dynamic title")

        # Test /xep-hang/test12345 (Bảng xếp hạng)
        res_xh = client.get('/xep-hang/test12345')
        assert res_xh.status_code == 200
        html_xh = res_xh.text
        assert 'Bảng xếp hạng: Kiem Tra 15 Phut Toan 12' in html_xh
        print("Test 5 Passed: /xep-hang/test12345 renders leaderboard metadata")

        # Test /giao-vien/de/test12345 (Quản lý đề giáo viên)
        res_gv_de = client.get('/giao-vien/de/test12345')
        assert res_gv_de.status_code == 200
        html_gv_de = res_gv_de.text
        assert 'Quản lý đề thi: Kiem Tra 15 Phut Toan 12' in html_gv_de
        print("Test 6 Passed: /giao-vien/de/test12345 renders teacher quiz management metadata")

        # Test /editor/test12345 (Soát lỗi đề)
        res_ed = client.get('/editor/test12345')
        assert res_ed.status_code == 200
        html_ed = res_ed.text
        assert 'Soát lỗi đề: Kiem Tra 15 Phut Toan 12' in html_ed
        print("Test 7 Passed: /editor/test12345 renders studio editor with dynamic quiz title")

    # 8. Test role/feature pages without params
    res_login = client.get('/dang-nhap')
    assert res_login.status_code == 200
    assert 'Đăng nhập tài khoản - HocNhanhTN' in res_login.text

    res_dethi = client.get('/de-thi')
    assert res_dethi.status_code == 200
    assert 'Danh sách Đề thi' in res_dethi.text

    res_kq = client.get('/ket-qua/sub_test_01')
    assert res_kq.status_code == 200
    assert 'Kết quả và đáp án chi tiết bài thi #sub_test_01' in res_kq.text

    res_lichsu = client.get('/lich-su')
    assert res_lichsu.status_code == 200
    assert 'Lịch sử làm bài' in res_lichsu.text

    res_gv = client.get('/giao-vien')
    assert res_gv.status_code == 200
    assert 'Bảng điều khiển Giáo viên' in res_gv.text

    res_admin = client.get('/admin')
    assert res_admin.status_code == 200
    assert 'Quản trị hệ thống' in res_admin.text

    print("Test 8 Passed: All semantic view routes (/dang-nhap, /de-thi, /ket-qua/:id, /lich-su, /giao-vien, /admin) respond 200 OK with custom metadata")

if __name__ == '__main__':
    test_og_share()
    print("ALL TESTS PASSED SUCCESSFULLY!")
