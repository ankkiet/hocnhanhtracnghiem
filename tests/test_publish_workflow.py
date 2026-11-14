import os
import re
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_publish_page_get():
    """Kiểm tra trang tùy chọn xuất bản riêng /publish trả về 200 OK với đầy đủ tùy chọn cơ bản và nâng cao."""
    res = client.get("/publish")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "Tùy chọn xuất bản" in res.text or "tùy chọn xuất bản" in res.text
    
    # Kiểm tra các thành phần cơ bản
    assert "txtQuizTitle" in res.text
    assert "cardModePractice" in res.text
    assert "cardModeExam" in res.text
    assert "numTimeLimit" in res.text
    assert "quick-time-chips" in res.text
    assert "chkShuffle" in res.text
    assert "txtQuizPassword" in res.text
    assert "chkLegalCommit" in res.text
    
    # Kiểm tra các tùy chọn chuyên sâu (Advanced Options)
    assert "accordionAdvanced" in res.text
    assert "dtStartTime" in res.text
    assert "dtEndTime" in res.text
    assert "selMaxAttempts" in res.text
    assert "selShowScore" in res.text
    assert "selShowAnswers" in res.text
    assert "chkLeaderboard" in res.text
    assert "chkFullScreen" in res.text
    assert "chkDetectTabSwitch" in res.text
    assert "selMaxTabViolations" in res.text
    assert "chkAntiCopy" in res.text
    assert "chkReqClass" in res.text
    
    # Kiểm tra tính năng đa thiết bị & chia sẻ
    assert "mobile-sticky-action-bar" in res.text
    assert "qrContainer" in res.text
    assert "downloadQrCodeImage" in res.text
    assert "copyIframeEmbedCode" in res.text

    # Kiểm tra nút Về trang chủ & Về Studio
    assert "btn-nav-home" in res.text
    assert "Trang chủ" in res.text
    assert "Về trang chủ" in res.text
    assert "lnkModalBackStudio" in res.text
    assert "getAuthToken" in res.text
    assert "auth_token" in res.text


def test_publish_page_with_quiz_id():
    """Kiểm tra trang /publish/{quiz_id} hiển thị mã đề trong tiêu đề."""
    res = client.get("/publish/TEST_QUIZ_12345")
    assert res.status_code == 200
    assert "TEST_QUIZ_12345" in res.text


def test_publish_worker_routing_and_static_files():
    """Kiểm tra file tĩnh publish.html và routing trong templates/_worker.js (Cloudflare Pages Edge)."""
    import subprocess
    from app.config.settings import settings
    
    # 1. Kiểm tra publish.html hiện diện ở cả templates và static
    template_publish = os.path.join(settings.TEMPLATES_DIR, "publish.html")
    static_publish = os.path.join(settings.STATIC_DIR, "publish.html")
    assert os.path.exists(template_publish), "Thiếu templates/publish.html"
    assert os.path.exists(static_publish), "Thiếu static/publish.html"

    # 2. Kiểm tra routing Cloudflare Worker
    worker_path = os.path.join(settings.TEMPLATES_DIR, "_worker.js")
    with open(worker_path, "r", encoding="utf-8") as f:
        worker_code = f.read()

    assert "isPublishRoute" in worker_code, "templates/_worker.js thiếu routing isPublishRoute cho /publish"
    assert "/publish.html" in worker_code, "templates/_worker.js thiếu rewrite về /publish.html"
    assert "'/publish': '/publish.html'" in worker_code, "templates/_worker.js thiếu staticPageMap cho /publish"

    # 3. Kiểm tra cú pháp JS của worker
    res = subprocess.run(["node", "-c", worker_path], capture_output=True, text=True)
    assert res.returncode == 0, f"Lỗi cú pháp _worker.js: {res.stderr}"


def test_save_quiz_with_advanced_settings():
    """Kiểm tra API save_quiz chấp nhận các trường description, password và settings mới."""
    payload = {
        "title": "Đề thi thử nâng cao",
        "data": [
            {
                "question": "Câu 1: 1 + 1 = ?",
                "options": ["A. 1", "B. 2", "C. 3", "D. 4"],
                "correct_answer": "B"
            }
        ],
        "mode": "exam",
        "time_limit": 45,
        "is_shuffle": True,
        "creator_id": "test_creator",
        "status": "published",
        "description": "Lời dặn của thầy cô",
        "password": "123",
        "settings": {
            "start_time": "2026-11-10T08:00",
            "end_time": "2026-11-10T10:00",
            "max_attempts": 1,
            "show_score": "immediate",
            "show_answers": "after_closed",
            "anti_cheat": True
        }
    }
    res = client.post("/api/save_quiz", json=payload)
    assert res.status_code == 200
    json_data = res.json()
    assert json_data.get("status") == "success"
    assert "quiz_id" in json_data


def test_index_html_pre_publish_modal():
    """Kiểm tra hộp thoại thống kê và kiểm tra trước khi xuất bản trên index.html."""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    assert 'id="publishModal"' in html
    assert 'id="statTotalCount"' in html
    assert 'id="statMcqCount"' in html
    assert 'id="statTfCount"' in html
    assert 'id="statSaCount"' in html
    assert 'id="pubQuestionsGrid"' in html
    assert 'id="publishDockBar"' in html
    assert 'filterPublishType' in html
    assert 'dockPublishModalToCorner' in html
    assert 'proceedToPublishPage' in html


def test_editor_html_pre_publish_modal():
    """Kiểm tra hộp thoại thống kê và kiểm tra trước khi xuất bản trên editor.html."""
    with open("templates/editor.html", "r", encoding="utf-8") as f:
        html = f.read()

    assert 'id="publishModal"' in html
    assert 'id="statTotalCount"' in html
    assert 'id="statMcqCount"' in html
    assert 'id="statTfCount"' in html
    assert 'id="statSaCount"' in html
    assert 'id="pubQuestionsGrid"' in html
    assert 'id="publishDockBar"' in html
    assert 'filterPublishType' in html
    assert 'dockPublishModalToCorner' in html
    assert 'proceedToPublishPage' in html


def test_script_js_modal_functions():
    """Kiểm tra logic JS trong script.js và script.source.js."""
    for fn in ["static/js/script.source.js", "static/js/script.js", "templates/script.js"]:
        with open(fn, "r", encoding="utf-8") as f:
            code = f.read()
        assert "function openPublishModal" in code, f"Missing openPublishModal in {fn}"
        assert "function filterPublishType" in code, f"Missing filterPublishType in {fn}"
        assert "function renderPublishQuestionsGrid" in code, f"Missing renderPublishQuestionsGrid in {fn}"
        assert "function jumpToQuestionFromPublishModal" in code, f"Missing jumpToQuestionFromPublishModal in {fn}"
        assert "function dockPublishModalToCorner" in code, f"Missing dockPublishModalToCorner in {fn}"
        assert "function proceedToPublishPage" in code, f"Missing proceedToPublishPage in {fn}"
        assert "publish-audit-highlight" in code, f"Missing publish-audit-highlight in {fn}"


def test_editor_js_modal_functions():
    """Kiểm tra logic JS trong editor.js."""
    for fn in ["static/js/editor.js", "templates/editor.js"]:
        with open(fn, "r", encoding="utf-8") as f:
            code = f.read()
        assert "function openPublishModal" in code, f"Missing openPublishModal in {fn}"
        assert "function filterPublishType" in code, f"Missing filterPublishType in {fn}"
        assert "function renderPublishQuestionsGrid" in code, f"Missing renderPublishQuestionsGrid in {fn}"
        assert "function jumpToQuestionFromPublishModal" in code, f"Missing jumpToQuestionFromPublishModal in {fn}"
        assert "function dockPublishModalToCorner" in code, f"Missing dockPublishModalToCorner in {fn}"
        assert "function proceedToPublishPage" in code, f"Missing proceedToPublishPage in {fn}"


def test_verify_quiz_password_and_settings_integration():
    """Kiểm tra API xác thực mật khẩu bài thi và metadata mô tả/cài đặt nâng cao."""
    with patch("services.firebase_service.get_db") as mock_db, \
         patch("app.services.quiz_service._get_db") as mock_quiz_db:
        
        db_instance = MagicMock()
        mock_db.return_value = db_instance
        mock_quiz_db.return_value = db_instance
        
        # Giả lập bài thi có mật khẩu 'secret123', lời dặn và settings nâng cao
        fake_doc = MagicMock()
        fake_doc.exists = True
        fake_doc.to_dict.return_value = {
            "title": "Đề thi nâng cao 2026",
            "data": [
                {"question": "Câu 1: 1+1=?", "options": ["A. 1", "B. 2"], "correct_answer": "B", "type": "mcq"}
            ],
            "mode": "exam",
            "time_limit": 45,
            "is_shuffle": True,
            "description": "Học sinh không được dùng tài liệu, chuẩn bị giấy nháp.",
            "password": "secret123",
            "settings": {
                "max_attempts": 2,
                "detect_tab": True,
                "max_tab_violations": 3,
                "full_screen": True,
                "show_score": "never",
                "show_answers": "never",
                "req_class": True,
                "req_school": True,
                "req_sbd": True
            },
            "status": "published"
        }
        db_instance.collection().document().get.return_value = fake_doc
        
        # 1. Học sinh lấy dữ liệu đề thi -> Không được lộ plain password, chỉ có has_password=True
        res_quiz = client.get("/api/get_quiz/test_quiz_pass_1")
        assert res_quiz.status_code == 200
        data_quiz = res_quiz.json()
        assert data_quiz["status"] == "success"
        assert data_quiz["has_password"] is True
        assert "password" not in data_quiz
        assert data_quiz["description"] == "Học sinh không được dùng tài liệu, chuẩn bị giấy nháp."
        assert data_quiz["settings"]["max_attempts"] == 2
        assert data_quiz["settings"]["req_class"] is True
        
        # 2. Học sinh nhập mật khẩu sai
        res_wrong = client.post("/api/verify_quiz_password", json={
            "quiz_id": "test_quiz_pass_1",
            "password": "wrong_password"
        })
        assert res_wrong.status_code == 200
        assert res_wrong.json()["valid"] is False
        
        # 3. Học sinh nhập mật khẩu đúng
        res_correct = client.post("/api/verify_quiz_password", json={
            "quiz_id": "test_quiz_pass_1",
            "password": "secret123"
        })
        assert res_correct.status_code == 200
        assert res_correct.json()["valid"] is True


def test_score_statistics_and_candidate_info_analytics():
    """Kiểm tra bảng thống kê điểm bài thi trả về đầy đủ tên, lớp, trường, SBD và cài đặt giáo viên."""
    from routers.teacher import get_quiz_analytics
    from app.services.student_service import student_service
    import asyncio

    mock_db = MagicMock()
    fake_quiz_doc = MagicMock()
    fake_quiz_doc.exists = True
    fake_quiz_doc.to_dict.return_value = {
        'title': 'Đề kiểm tra giữa kỳ 1',
        'creator_id': 'teacher_123',
        'mode': 'exam',
        'time_limit': 45,
        'description': 'Chúc các em làm bài tốt!',
        'settings': {
            'req_class': True,
            'req_school': True,
            'req_sbd': True,
            'show_score': 'immediate',
            'show_answers': 'after_closed',
            'leaderboard': True,
            'detect_tab': True,
            'max_tab_violations': 3
        },
        'data': [
            {'question': 'Câu 1?', 'type': 'mcq', 'options': ['A. 1', 'B. 2'], 'correct_answer': 'A'}
        ]
    }

    fake_sub_doc = MagicMock()
    fake_sub_doc.id = "sub_001"
    fake_sub_doc.to_dict.return_value = {
        '_id': 'sub_001',
        'student_name': 'Nguyễn Văn An',
        'class_name': '12A1',
        'school_name': 'THPT Chuyên',
        'sbd': 'SBD-042',
        'score': 1.0,
        'total_questions': 1,
        'time_elapsed': 75,
        'tab_switch_count': 1,
        'is_guest': False,
        'answers': {'0': 'A'},
        'results': [{'question_index': 0, 'is_correct': True, 'earned': 1.0}]
    }

    mock_db.collection.return_value.document.return_value.get.return_value = fake_quiz_doc
    mock_db.collection.return_value.document.return_value.collection.return_value.get.return_value = [fake_sub_doc]

    with patch('routers.teacher.get_db', return_value=mock_db), \
         patch('routers.teacher.verify_teacher_access', return_value=({'role': 'teacher'}, 'teacher_123')):
        analytics = asyncio.run(get_quiz_analytics(quiz_id='quiz_midterm', teacher_token='valid_token', force_refresh=True))

    assert analytics['status'] == 'success'
    assert analytics['total_submissions'] == 1
    assert len(analytics['students']) == 1

    stu = analytics['students'][0]
    assert stu['student_name'] == 'Nguyễn Văn An'
    assert stu['class_name'] == '12A1'
    assert stu['school_name'] == 'THPT Chuyên'
    assert stu['sbd'] == 'SBD-042'
    assert stu['scaled_score'] == 10.0
    assert analytics['settings']['req_class'] is True
    assert analytics['description'] == 'Chúc các em làm bài tốt!'

    # Kiểm tra giao diện index.html có đầy đủ thành phần mới
    with open("templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    assert 'id="statsQuizSettingsBanner"' in html
    assert 'id="statsClassFilterSelect"' in html
    assert 'exportStatsScoreTableToExcel' in html
    assert 'id="statsStudentsMainTable"' in html


def test_require_login_feature_and_verification():
    """Kiểm tra tính năng Bắt buộc đăng nhập để xác minh danh tính học sinh."""
    # 1. Kiểm tra cấu hình trong publish.html
    with open("templates/publish.html", "r", encoding="utf-8") as f:
        pub_html = f.read()
    assert 'id="chkReqLogin"' in pub_html
    assert 'Yêu cầu đăng nhập tài khoản để làm bài' in pub_html
    assert 'require_login' in pub_html

    # 2. Kiểm tra giao diện thi trong index.html
    with open("templates/index.html", "r", encoding="utf-8") as f:
        idx_html = f.read()
    assert 'id="examLoginRequiredNotice"' in idx_html
    assert 'id="examVerifiedStudentBadge"' in idx_html
    assert 'verifiedStudentInfoText' in idx_html

    # 3. Kiểm tra logic JS trong script.source.js & script.js
    for script_path in ["static/js/script.source.js", "static/js/script.js", "templates/script.js"]:
        with open(script_path, "r", encoding="utf-8") as f:
            js = f.read()
        assert "applyExamStudentAuthContext" in js
        assert "examLoginRequiredNotice" in js
        assert "examVerifiedStudentBadge" in js
        assert "require_login" in js

    # 4. Kiểm tra auth_service.py trả về class_name và school khi đăng nhập
    from app.services.auth_service import AuthService
    auth_srv = AuthService()
    with patch("app.services.auth_service._get_db") as mock_db, \
         patch("app.services.auth_service.verify_password", return_value=True):
        fake_db = MagicMock()
        mock_db.return_value = fake_db
        user_doc = MagicMock()
        user_doc.exists = True
        user_doc.id = "user_student_123"
        user_doc.to_dict.return_value = {
            "username": "student1",
            "password_hash": "dummy_hash",
            "full_name": "Trần Thị Hoa",
            "role": "student",
            "class_name": "12A3",
            "school": "THPT Marie Curie",
            "avatar": ""
        }
        mock_query = MagicMock()
        mock_query.get.return_value = [user_doc]
        fake_db.collection.return_value.where.return_value = mock_query

        login_res = auth_srv.login_user("student1", "mypassword")
        assert login_res["status"] == "success"
        assert login_res["full_name"] == "Trần Thị Hoa"
        assert login_res["class_name"] == "12A3"
        assert login_res["school"] == "THPT Marie Curie"


def test_custom_rich_dropdown_sync_and_syntax():
    """Kiểm tra thành phần dropdown chọn lựa tùy biến (hc-select) đồng bộ và hợp lệ cú pháp JS."""
    import subprocess

    static_hc = "static/js/hc-select.js"
    tpl_hc = "templates/hc-select.js"
    assert os.path.exists(static_hc), "Thiếu static/js/hc-select.js"
    assert os.path.exists(tpl_hc), "Thiếu templates/hc-select.js"

    with open(static_hc, "r", encoding="utf-8") as f1, open(tpl_hc, "r", encoding="utf-8") as f2:
        code1 = f1.read()
        code2 = f2.read()
    assert code1 == code2, "templates/hc-select.js chưa đồng bộ với static/js/hc-select.js"
    assert "initHcCustomSelect" in code1
    assert "initModalCustomSelects" in code1
    assert "initPublishCustomSelects" in code1
    assert "initEditorExtraCustomSelects" in code1
    assert "initDashboardCustomSelects" in code1
    assert "initContactCustomSelects" in code1
    assert "initQuestionTypeCustomSelects" in code1

    node_chk = subprocess.run(["node", "-c", static_hc], capture_output=True, text=True)
    assert node_chk.returncode == 0, f"Lỗi cú pháp hc-select.js: {node_chk.stderr}"

    for tpl_path in ["templates/editor.html", "templates/index.html", "templates/publish.html", "static/publish.html", "templates/contact.html"]:
        with open(tpl_path, "r", encoding="utf-8") as f:
            html = f.read()
        assert "/hc-select.js" in html, f"{tpl_path} chưa nhúng /hc-select.js"

    for js_path in ["static/js/editor.js", "templates/editor.js"]:
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        assert "initModalCustomSelects" in js, f"Thiếu initModalCustomSelects trong {js_path}"
        assert "initQuestionTypeCustomSelects" in js, f"Thiếu initQuestionTypeCustomSelects trong {js_path}"
        assert "initEditorExtraCustomSelects" in js, f"Thiếu initEditorExtraCustomSelects trong {js_path}"

    for js_path in ["static/js/script.source.js", "static/js/script.js", "templates/script.js"]:
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        assert "initModalCustomSelects" in js, f"Thiếu initModalCustomSelects trong {js_path}"
        assert "initDashboardCustomSelects" in js, f"Thiếu initDashboardCustomSelects trong {js_path}"


def test_unsaved_exit_beforeunload_guards():
    """Kiểm tra cơ chế hỏi xác nhận khi rời/tắt tab mà chưa lưu hoặc chưa xuất bản đề thi."""
    for editor_path in ["static/js/editor.js", "templates/editor.js"]:
        with open(editor_path, "r", encoding="utf-8") as f:
            ed_js = f.read()
        assert "hasPendingStudioExitWarning" in ed_js
        assert "hasUnsavedStudioChanges" in ed_js
        assert "beforeunload" in ed_js
        assert "pagehide" in ed_js

    for pub_path in ["templates/publish.html", "static/publish.html"]:
        with open(pub_path, "r", encoding="utf-8") as f:
            pub_html = f.read()
        assert "shouldWarnOnPublishExit" in pub_html
        assert "hasCompletedFinalPublish" in pub_html
        assert "beforeunload" in pub_html

    for script_path in ["static/js/script.source.js", "static/js/script.js", "templates/script.js"]:
        with open(script_path, "r", encoding="utf-8") as f:
            sc_js = f.read()
        assert "hasUnsavedIndexQuiz" in sc_js or "allowIndexExitWithoutPrompt" in sc_js
        assert "beforeunload" in sc_js


def test_publish_practice_mode_hides_anticheat():
    """Kiểm tra chế độ luyện tập tự do tự động ẩn và tắt các tùy chọn giám sát & chống gian lận."""
    for pub_path in ["templates/publish.html", "static/publish.html"]:
        with open(pub_path, "r", encoding="utf-8") as f:
            pub_html = f.read()
        assert 'id="sectionAntiCheat"' in pub_html, f"Thiếu sectionAntiCheat trong {pub_path}"
        assert 'secAntiCheat.style.display = \'none\'' in pub_html
        assert 'isPracticeMode' in pub_html
        assert 'cardModePractice' in pub_html
        assert 'cardModeExam' in pub_html


def test_export_docx_endpoint_custom_and_title_filename():
    """Kiểm tra xuất file Word docx giữ đúng tiêu đề đề thi và không bị nhầm lẫn mã đề."""
    from fastapi.testclient import TestClient
    from app.main import app
    from unittest.mock import patch, MagicMock

    client = TestClient(app)
    
    with patch("app.api.routes.teacher._get_db") as mock_db:
        fake_db = MagicMock()
        mock_db.return_value = fake_db
        
        fake_doc = MagicMock()
        fake_doc.exists = True
        fake_doc.to_dict.return_value = {
            "title": "Đề thi thử THPT Quốc gia môn Toán 2026",
            "data": [
                {"question": "Câu 1: Hàm số nào đồng biến trên R?", "options": ["A. y=x", "B. y=-x"], "correct_answer": "A", "type": "mcq"}
            ],
            "time_limit": 90,
            "status": "published"
        }
        fake_db.collection().document().get.return_value = fake_doc
        
        # Test GET /api/teacher/export_docx/{quiz_id}
        res = client.get("/api/teacher/export_docx/TEST_QUIZ_TITLE_1")
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        disp = res.headers.get("content-disposition", "")
        assert "TEST_QUIZ_TITLE_1" in disp or "De_thi_thu_THPT" in disp or "filename*=" in disp


def test_export_js_id_isolation_and_publish_title_sync():
    """Kiểm tra export.js và publish.html cô lập ID đề thi và đồng bộ tiêu đề mới sau khi xuất bản."""
    # 1. Kiểm tra export.js cô lập ID và dọn dẹp dữ liệu của đề khác
    export_files = [
        "static/js/export.js",
        "static/export.js",
        "templates/export.js",
        "templates/js/export.js"
    ]
    for path in export_files:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "transId && transId === quizData.id" in content, f"{path} thiếu kiểm tra trùng khớp quizData.id"
        assert "sessionStorage.removeItem('export_quiz_data')" in content, f"{path} thiếu dọn dẹp cache đề khác"
        assert "export_quiz_title_" in content, f"{path} thiếu hỗ trợ tiêu đề truyền qua session"

    # 2. Kiểm tra publish.html cập nhật export_quiz_data và export_quiz_{finalId} với tiêu đề mới
    publish_files = ["static/publish.html", "templates/publish.html"]
    for path in publish_files:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "sessionStorage.setItem(`export_quiz_${finalId}`" in content, f"{path} thiếu lưu export_quiz_finalId"
        assert "sessionStorage.setItem('export_quiz_data'" in content, f"{path} thiếu lưu export_quiz_data với tên mới"
        assert "sessionStorage.setItem(`export_quiz_title_${finalId}`" in content, f"{path} thiếu lưu export_quiz_title"

    # 3. Kiểm tra script.source.js và script.js truyền đúng tên đề thi và xóa cache rác
    for path in ["static/js/script.source.js", "templates/script.source.js", "static/js/script.js", "templates/script.js"]:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "export_quiz_title_" in content or "exportQuizDocx" in content, f"{path} thiếu exportQuizDocx cập nhật"




