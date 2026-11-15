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


def test_publish_share_url_format_with_slug():
    """Kiểm tra trang xuất bản tạo link chia sẻ chuẩn SEO /thi/{id}/{slug} thay vì link cũ ?id=."""
    for path in ["static/publish.html", "templates/publish.html"]:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "function slugifyVietnamese(" in content, f"{path} thiếu hàm slugifyVietnamese"
        assert "function getQuizExamUrl(" in content, f"{path} thiếu hàm getQuizExamUrl"
        assert "getQuizExamUrl(quizId" in content, f"{path} thiếu gọi getQuizExamUrl trong updateShareLinks"
        assert "/thi/${cleanId}/${slug}" in content, f"{path} thiếu định dạng link /thi/id/slug"
        assert "const shareUrl = `${window.location.origin}/?id=${encodeURIComponent(quizId)}`;" not in content, \
            f"{path} vẫn còn link dạng ?id= trong updateShareLinks"


def test_publish_scoring_ui_and_validation_to_ten_points():
    """Kiểm tra mục chia điểm trên giao diện xuất bản đảm bảo tổng 10.0 điểm, có nút cân bằng và kiểm tra trước khi xuất bản."""
    # 1. Kiểm tra publish.html & templates/publish.html
    for path in ["static/publish.html", "templates/publish.html"]:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "autoBalanceQuizScoreTo10" in content, f"{path} thiếu hàm autoBalanceQuizScoreTo10"
        assert "assignExactPointsToQuestions" in content, f"{path} thiếu hàm assignExactPointsToQuestions"
        assert "Cân bằng về 10 điểm" in content, f"{path} thiếu nút 'Cân bằng về 10 điểm'"
        assert "Math.abs(totalScore - 10.0) >= 0.05" in content, f"{path} thiếu kiểm tra tổng 10 điểm trước khi xuất bản"

    # 2. Kiểm tra editor.js & templates/editor.js
    for path in ["static/js/editor.js", "templates/editor.js"]:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "autoBalanceModalScoringTo10" in content, f"{path} thiếu hàm autoBalanceModalScoringTo10"
        assert "assignExactPointsToEditorQuestions" in content, f"{path} thiếu hàm assignExactPointsToEditorQuestions"
        assert "Math.abs(totalScore - 10.0) >= 0.05" in content, f"{path} thiếu kiểm tra tổng 10 điểm trước khi xuất bản"

    # 3. Kiểm tra script.source.js & templates/script.source.js
    for path in ["static/js/script.source.js", "templates/script.source.js"]:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "autoBalanceModalScoringTo10" in content, f"{path} thiếu hàm autoBalanceModalScoringTo10"
        assert "assignExactPointsToIndexQuestions" in content, f"{path} thiếu hàm assignExactPointsToIndexQuestions"
        assert "Math.abs(totalScore - 10.0) >= 0.05" in content, f"{path} thiếu kiểm tra tổng 10 điểm trước khi xuất bản"

    # 4. Kiểm tra nút bấm trên editor.html và index.html
    for path in ["templates/editor.html", "templates/index.html"]:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "autoBalanceModalScoringTo10()" in content, f"{path} thiếu gọi autoBalanceModalScoringTo10"
        assert "Cân bằng về 10 điểm" in content, f"{path} thiếu nút 'Cân bằng về 10 điểm'"


def test_student_submit_exam_exact_ten_points_with_fractional_questions():
    """Kiểm tra chấm bài thi với số câu không chia hết cho 10 (ví dụ 30 câu), đảm bảo học sinh làm đúng 100% đạt đúng 10.0 điểm."""
    import asyncio
    from unittest.mock import MagicMock, patch
    from app.services.student_service import StudentService
    from app.schemas.student import SubmitExamRequest

    service = StudentService()
    mock_db = MagicMock()
    mock_quiz_doc = MagicMock()
    mock_quiz_doc.exists = True

    # 30 câu hỏi MCQ, chế độ tự động chia đều thang 10
    total_q = 30
    questions = [
        {"question": f"Câu {i+1}", "type": "mcq", "options": ["A. Đúng", "B. Sai"], "correct_answer": "A. Đúng"}
        for i in range(total_q)
    ]
    mock_quiz_doc.to_dict.return_value = {
        "title": "Đề thi trắc nghiệm 30 câu",
        "questions": questions,
        "settings": {
            "scoring": {
                "mode": "auto",
                "total_score": 10.0
            }
        }
    }
    mock_db.collection.return_value.document.return_value.get.return_value = mock_quiz_doc
    mock_sub_ref = MagicMock()
    mock_sub_ref.id = "sub_exact_10_test"
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_sub_ref

    # Học sinh làm đúng tất cả 30 câu
    answers = {str(i): "A. Đúng" for i in range(total_q)}
    req = SubmitExamRequest(
        quiz_id="QUIZ_30_Q",
        student_name="Nguyễn Văn Hoàn Hảo",
        answers=answers,
        time_elapsed=600
    )

    with patch.object(service, 'get_db', return_value=mock_db):
        res = asyncio.run(service.submit_exam(req))
        assert res["status"] == "success"
        assert res["max_score"] == 10.0, f"max_score phải là 10.0 nhưng nhận {res['max_score']}"
        assert res["score"] == 10.0, f"score phải là 10.0 nhưng nhận {res['score']}"


def test_mobile_publish_button_visibility():
    """Kiểm tra nút xuất bản mobile: ẩn trên máy tính (desktop) và chỉ hiển thị ở giao diện mobile."""
    with open("templates/editor.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Nút xuất bản mobile phải có id, class studio-mobile-publish-btn, display: none inline để ẩn mặc định trên máy tính
    assert 'id="btnOpenPublishMobile"' in html
    assert 'class="studio-mobile-publish-btn"' in html
    assert 'style="display: none;"' in html
    assert 'btn-studio-primary studio-mobile-publish-btn' not in html

    for css_path in ["static/css/editor.css", "templates/editor.css"]:
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        # Desktop: phải ẩn tuyệt đối
        assert "#btnOpenPublishMobile,\n.studio-mobile-publish-btn {\n    display: none !important;\n}" in css or "#btnOpenPublishMobile,\r\n.studio-mobile-publish-btn {\r\n    display: none !important;\r\n}" in css, f"Thiếu quy tắc ẩn nút mobile publish trên desktop trong {css_path}"
        # Mobile: hiển thị inline-flex !important
        assert "#btnOpenPublishMobile,\n  .studio-mobile-publish-btn {\n    display: inline-flex !important;" in css or "#btnOpenPublishMobile,\r\n  .studio-mobile-publish-btn {\r\n    display: inline-flex !important;" in css, f"Thiếu quy tắc hiển thị nút mobile publish trên mobile trong {css_path}"


def test_editor_status_bar_responsiveness_and_cache_buster():
    """Kiểm tra thanh trạng thái editor: chống lỗi tràn vỡ hàng trên MacBook và màn hình laptop nhỏ."""
    with open("templates/editor.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Phải có cache buster mới (không dùng bản cũ 20261112)
    assert 'href="/editor.css?v=20261115_mac_statusbar_v2"' in html

    # Thẻ editorStatusBar phải có thuộc tính inline chống vỡ layout khi mạng chậm hoặc chưa nạp kịp CSS
    assert 'id="editorStatusBar"' in html
    assert 'style="height: 36px; min-height: 36px; display: flex; align-items: center; justify-content: space-between; overflow: hidden; background: #f8fafc; border-top: 1px solid #e2e8f0; box-sizing: border-box; flex-wrap: nowrap;"' in html

    # Kiểm tra cả 2 file CSS đồng bộ 100%
    for css_path in ["static/css/editor.css", "templates/editor.css"]:
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        assert "flex-wrap: nowrap !important;" in css
        assert "@container (max-width: 780px)" in css
        assert "@media (max-width: 1440px)" in css


def test_republish_preserves_answers_when_shuffled_or_sanitized():
    """Kiểm tra cơ chế bảo toàn và khôi phục đáp án gốc khi người dùng xuất bản lại đề thi."""
    from unittest.mock import MagicMock, patch
    from app.services.quiz_service import QuizService

    service = QuizService()
    mock_db = MagicMock()

    # Giả lập bản ghi đề thi cũ trong Firestore có đáp án chính xác
    fake_old_doc = MagicMock()
    fake_old_doc.exists = True
    fake_old_doc.to_dict.return_value = {
        'creator_id': 'teacher_xyz',
        'data': [
            {
                'question': 'Câu 1: Thủ đô của Việt Nam là gì?',
                'options': ['A. Hà Nội', 'B. Huế', 'C. Đà Nẵng', 'D. TP.HCM'],
                'correct_answer': 'A. Hà Nội',
                'explain': 'Hà Nội là thủ đô của Việt Nam từ năm 1945.'
            },
            {
                'question': 'Câu 2: Xét tính đúng sai:',
                'type': 'true_false',
                'options': ['a) 1 + 1 = 2', 'b) 2 + 2 = 5'],
                'correct_answer': {'a': True, 'b': False}
            }
        ]
    }
    mock_db.collection.return_value.document.return_value.get.return_value = fake_old_doc

    # Kịch bản 1: Client lỡ gửi câu hỏi bị Anti-cheat làm mất correct_answer khi gọi save_quiz cập nhật
    new_data_sanitized = [
        {
            'question': 'Câu 1: Thủ đô của Việt Nam là gì?',
            'options': ['A. Hà Nội', 'B. Huế', 'C. Đà Nẵng', 'D. TP.HCM']
            # Không có correct_answer do bị Anti-cheat ẩn
        },
        {
            'question': 'Câu 2: Xét tính đúng sai:',
            'type': 'true_false',
            'options': ['a) 1 + 1 = 2', 'b) 2 + 2 = 5']
            # Không có correct_answer do bị Anti-cheat ẩn
        }
    ]

    with patch('app.services.quiz_service._get_db', return_value=mock_db), \
         patch('app.services.quiz_service.get_user_from_token', return_value={'id': 'teacher_xyz'}):
        res = service.save_quiz(
            title="Đề thi bảo toàn đáp án",
            data=new_data_sanitized,
            quiz_id="TEST_REPUBLISH_001",
            creator_id="teacher_xyz"
        )
        assert res['status'] == 'success'
        saved_call = mock_db.collection.return_value.document.return_value.set.call_args[0][0]
        saved_data = saved_call['data']

        # Đáp án câu 1 phải được khôi phục nguyên vẹn là 'A. Hà Nội', không bị nhảy về A mặc định do lỗi
        assert saved_data[0]['correct_answer'] == 'A. Hà Nội'
        assert '1945' in saved_data[0].get('explain', '')

        # Đáp án câu 2 True/False phải được khôi phục nguyên vẹn
        assert saved_data[1]['correct_answer'] == {'a': True, 'b': False}

    # Kịch bản 2: Client lỡ gửi câu hỏi đã bị shuffleQuiz đảo vị trí và đảo options
    new_data_shuffled = [
        {
            'question': 'Câu 2: Xét tính đúng sai:',
            'type': 'true_false',
            'options': ['a) 1 + 1 = 2', 'b) 2 + 2 = 5'],
            'correct_answer': {'a': True, 'b': False},
            '_originalIndex': 1
        },
        {
            'question': 'Câu 1: Thủ đô của Việt Nam là gì?',
            'options': ['A. Đà Nẵng', 'B. TP.HCM', 'C. Hà Nội', 'D. Huế'], # Đã bị đảo
            'correct_answer': 'C. Hà Nội', # Đã bị cập nhật theo vị trí mới
            '_originalIndex': 0,
            '_originalOptions': ['A. Hà Nội', 'B. Huế', 'C. Đà Nẵng', 'D. TP.HCM'], # Gốc
            '_originalCorrectAnswer': 'A. Hà Nội' # Gốc
        }
    ]

    with patch('app.services.quiz_service._get_db', return_value=mock_db), \
         patch('app.services.quiz_service.get_user_from_token', return_value={'id': 'teacher_xyz'}):
        res2 = service.save_quiz(
            title="Đề thi đảo đề hoàn tác",
            data=new_data_shuffled,
            quiz_id="TEST_REPUBLISH_002",
            creator_id="teacher_xyz"
        )
        assert res2['status'] == 'success'
        saved_call2 = mock_db.collection.return_value.document.return_value.set.call_args[0][0]
        saved_data2 = saved_call2['data']

        # Phải được hoàn tác lại đúng thứ tự Câu 1 trước, Câu 2 sau
        assert 'Thủ đô' in saved_data2[0]['question']
        assert saved_data2[0]['options'][0] == 'A. Hà Nội'
        assert saved_data2[0]['correct_answer'] == 'A. Hà Nội'
        assert '_originalIndex' not in saved_data2[0]


def test_unshuffled_helper_present_in_all_publish_scripts():
    """Kiểm tra hàm hoàn tác trộn đề getCleanUnshuffledQuizData hiện diện ở tất cả các file xuất bản."""
    files_to_check = [
        "static/js/script.source.js",
        "templates/script.source.js",
        "static/js/editor.js",
        "templates/editor.js",
        "static/publish.html",
        "templates/publish.html"
    ]
    for fn in files_to_check:
        with open(fn, "r", encoding="utf-8") as f:
            code = f.read()
        assert "getCleanUnshuffledQuizData" in code, f"Thiếu getCleanUnshuffledQuizData trong {fn}"









