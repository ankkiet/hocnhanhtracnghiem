import pytest
from app.utils.helpers import evaluate_mcq_answer
from core.docx_exporter import extract_answer_display, is_option_correct
from services.ai_service import normalize_question_data


def test_evaluate_mcq_answer_with_images_after_shuffle():
    """Kiểm tra phương án chứa ảnh: khi đảo từ B lên A, học sinh chọn ảnh vẫn được chấm đúng."""
    opts_original = [
        "A. Hà Nội",
        'B. <img src="https://cdn.example.com/math_graph_2.png">',
        "C. Đà Nẵng",
        "D. Sài Gòn"
    ]
    correct_ans = 'B. <img src="https://cdn.example.com/math_graph_2.png">'
    
    # Học sinh làm bài sau khi shuffle, ảnh nhảy lên vị trí A
    user_ans = 'A. <img src="https://cdn.example.com/math_graph_2.png">'
    
    # So khớp phải trả về True
    assert evaluate_mcq_answer(user_ans, correct_ans, opts_original) is True


def test_extract_answer_display_text_ca():
    """Kiểm tra extract_answer_display khi correct_answer là text thuần túy."""
    q = {
        "question": "Thủ đô của Việt Nam là gì?",
        "options": ["A. Huế", "B. Hà Nội", "C. Đà Nẵng", "D. Cần Thơ"],
        "correct_answer": "Hà Nội",
        "type": "mcq"
    }
    # Phải trả về 'B' thay vì 'Hà'
    assert extract_answer_display(q) == "B"


def test_extract_answer_display_numeric_ca():
    """Kiểm tra extract_answer_display khi correct_answer là chỉ số 0, 1, 2, 3."""
    q = {
        "question": "Thủ đô của Việt Nam là gì?",
        "options": ["A. Huế", "B. Hà Nội", "C. Đà Nẵng", "D. Cần Thơ"],
        "correct_answer": 1,
        "type": "mcq"
    }
    assert extract_answer_display(q) == "B"


def test_is_option_correct_html_and_text():
    """Kiểm tra is_option_correct với HTML và nội dung text thuần."""
    assert is_option_correct(1, "B. <b>Hà Nội</b>", "Hà Nội") is True
    assert is_option_correct(0, "A. Huế", "Hà Nội") is False


def test_normalize_question_data_avoids_false_a_matching():
    """Kiểm tra không bị bắt nhầm chữ cái A khi đáp án là 'A book' hoặc 'Điểm A'."""
    item = {
        "question": "What is on the table?",
        "options": ["A. An apple", "B. An orange", "C. A ruler", "D. A book"],
        "correct_answer": "A book",
        "type": "mcq"
    }
    norm = normalize_question_data(item)
    # Phải là phương án D. A book, không được gán nhầm sang phương án A
    assert norm["correct_answer"] == "D. A book"


def test_search_trailing_tf_safety():
    """Kiểm tra match trailing TF an toàn, không nhận nhầm đơn vị giây 's' hoặc đường thẳng 'd'."""
    from core.text_parser import match_trailing_tf
    # Đơn vị vật lý giây 's' hoặc 'm/s'
    assert match_trailing_tf("Thời gian rơi là 2 s") is None
    assert match_trailing_tf("Vận tốc đạt 10 m/s") is None
    assert match_trailing_tf("Chu kỳ dao động T = 0.5s") is None

    # Ký hiệu toán học đường thẳng d
    assert match_trailing_tf("Mặt phẳng (P) chứa đường thẳng d") is None
    assert match_trailing_tf("Tìm hình chiếu trên d") is None

    # Nhãn Đúng / Sai thật sự
    assert match_trailing_tf("Mệnh đề này là đúng")[2] == "đúng"
    assert match_trailing_tf("Mệnh đề này là đúng")[0] is True
    assert match_trailing_tf("Mệnh đề này là Sai")[2] == "Sai"
    assert match_trailing_tf("Mệnh đề này là Sai")[0] is False
    assert match_trailing_tf("Phương trình vô nghiệm [Đúng]")[2] == "[Đúng]"
    assert match_trailing_tf("Phương trình vô nghiệm [Đúng]")[0] is True
    assert match_trailing_tf("Hàm số đồng biến (S)")[2] == "(S)"
    assert match_trailing_tf("Hàm số đồng biến (S)")[0] is False
    assert match_trailing_tf("Tập xác định D: Đ")[2] == "Đ"
    assert match_trailing_tf("Tập xác định D: Đ")[0] is True
    assert match_trailing_tf("Tập xác định D - S")[2] == "S"
    assert match_trailing_tf("Tập xác định D - S")[0] is False


def test_physics_units_not_flipping_true_false():
    """Kiểm tra phương án có đơn vị 2 s không bị lật thành Sai khi có dấu * ở đầu."""
    from core.text_parser import extract_questions_from_text_bulletproof
    text = """PHẦN II. Câu trắc nghiệm đúng sai
Câu 1: Một vật rơi tự do từ độ cao h.
*a) Thời gian rơi của vật là t = 2 s
b) Quãng đường vật đi được trong 1 s đầu là 5 m
*c) Vận tốc lúc chạm đất là v = 20 m/s
d) Gia tốc của vật là g = 9.8 m/s2
"""
    questions = extract_questions_from_text_bulletproof(text)
    assert len(questions) == 1
    q = questions[0]
    assert q["type"] == "true_false"
    ans = q["correct_answer"]
    assert ans["a"] is True, "Câu a có 2 s nhưng có dấu * ở đầu phải là True"
    assert ans["b"] is False, "Câu b không có dấu * phải là False"
    assert ans["c"] is True, "Câu c có 20 m/s nhưng có dấu * ở đầu phải là True"
    assert ans["d"] is False, "Câu d không có dấu * phải là False"


def test_math_variable_d_not_flipping_to_true():
    """Kiểm tra phương án có chứa đường thẳng d không bị lật thành Đúng."""
    from core.text_parser import extract_questions_from_text_bulletproof
    text = """PHẦN II. Câu trắc nghiệm đúng sai
Câu 1: Trong không gian Oxyz, cho mặt phẳng (P).
a) Mặt phẳng (P) đi qua điểm A(1, 0, 0)
*b) Mặt phẳng (P) song song với trục Oz
c) Mặt phẳng (P) vuông góc với đường thẳng d
d) Khoảng cách từ gốc O đến (P) bằng 2
"""
    questions = extract_questions_from_text_bulletproof(text)
    assert len(questions) == 1
    q = questions[0]
    assert q["type"] == "true_false"
    ans = q["correct_answer"]
    assert ans["a"] is False
    assert ans["b"] is True
    assert ans["c"] is False, "Câu c có đường thẳng d không được coi là Đúng"
    assert ans["d"] is False


def test_no_dummy_hardcoded_true_false_answers():
    """Đảm bảo không còn gán bậy đáp án mặc định { a: true, b: false, c: true, d: false }."""
    for fpath in ['static/js/script.source.js', 'static/js/editor.js']:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'a: true, b: false, c: true, d: false' not in content, f"{fpath} chứa đáp án mẫu giả định gán bừa!"


def test_preview_no_false_highlighting_when_undefined():
    """Đảm bảo giao diện xem trước không dùng !isTrue làm nhãn Sai tự động đỏ khi chưa chọn."""
    for fpath in ['static/js/script.source.js', 'static/js/editor.js']:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
            assert '!isTrue ? \'#fca5a5\'' not in content, f"{fpath} bị lỗi gán nhãn Sai tự động khi chưa chọn đáp án!"


def test_publish_clears_local_progress():
    """Đảm bảo khi xuất bản đề thi mới, tiến trình làm thử cũ của đề thi trên trình duyệt được xóa sạch."""
    for fpath in ['static/publish.html', 'templates/publish.html']:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'localStorage.removeItem(`quiz_progress_${finalId}`)' in content, f"{fpath} chưa xóa quiz_progress cũ!"


def test_tobooltf_returns_null_for_undefined_and_no_auto_tick_false():
    """Đảm bảo toBoolTF(undefined/null) trả về null thay vì false, tránh tự động tick 4 câu sai khi vào làm."""
    with open('static/js/script.source.js', 'r', encoding='utf-8') as f:
        src = f.read()
    # Kiểm tra toBoolTF xử lý giá trị rỗng/undefined
    assert "if (val === undefined || val === null || val === '') return null;" in src
    # Kiểm tra startStudentQuiz reset biến tiến trình luyện tập khi không phải resume
    assert "quizProgress.practiceIndex = 0;" in src
    assert "window.currentPracticeTF = {};" in src


def test_cache_busting_version_updated():
    """Đảm bảo chuỗi phiên bản cache buster được nâng cấp mới để vượt qua bộ nhớ đệm Cloudflare/trình duyệt."""
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        html = f.read()
    assert 'script.js?v=20261117_submissions_v1' in html
    assert '20261115_fix_tf_clean_v3' not in html


def test_publish_preserves_edited_questions_from_session():
    """Đảm bảo trang publish ưu tiên câu hỏi và đáp án mới từ session khi người dùng sửa đề từ editor."""
    for fpath in ['static/publish.html', 'templates/publish.html']:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'if (loadedFromSession && currentQuiz.questions && currentQuiz.questions.length > 0)' in content, \
                f"{fpath} thiếu logic bảo toàn câu hỏi từ session khi người dùng vừa sửa đề từ editor!"


def test_quiz_service_preserves_all_false_tf_answers():
    """Kiểm tra backend _restore_and_protect_questions không đè lại đáp án cũ khi giáo viên đổi đáp án Đúng/Sai thành 4 ý Sai."""
    from app.services.quiz_service import quiz_service

    old_questions = [
        {
            'question': 'Câu 1: Xét tính đúng sai của hàm số',
            'options': ['a) f(x) đồng biến', 'b) f(x) nghịch biến', 'c) f(x) có cực trị', 'd) f(x) liên tục'],
            'correct_answer': {'a': True, 'b': False, 'c': True, 'd': False},
            'type': 'true_false'
        }
    ]

    # Giáo viên sửa đề: đổi toàn bộ 4 ý thành False
    new_questions = [
        {
            'question': 'Câu 1: Xét tính đúng sai của hàm số',
            'options': ['a) f(x) đồng biến', 'b) f(x) nghịch biến', 'c) f(x) có cực trị', 'd) f(x) liên tục'],
            'correct_answer': {'a': False, 'b': False, 'c': False, 'd': False},
            'type': 'true_false'
        }
    ]

    restored = quiz_service._restore_and_protect_questions(new_questions, old_questions=old_questions)
    assert restored[0]['correct_answer'] == {'a': False, 'b': False, 'c': False, 'd': False}, \
        "Backend đã đè lại đáp án cũ khi câu hỏi Đúng/Sai có 4 ý False!"


def test_quiz_service_preserves_edited_mcq_answer():
    """Kiểm tra backend _restore_and_protect_questions giữ nguyên đáp án MCQ mới khi giáo viên đổi từ A sang C."""
    from app.services.quiz_service import quiz_service

    old_questions = [
        {
            'question': 'Câu 1: Thủ đô nước Pháp là gì?',
            'options': ['A. Paris', 'B. London', 'C. Berlin', 'D. Rome'],
            'correct_answer': 'A. Paris',
            'type': 'mcq'
        }
    ]

    new_questions = [
        {
            'question': 'Câu 1: Thủ đô nước Đức là gì?',
            'options': ['A. Paris', 'B. London', 'C. Berlin', 'D. Rome'],
            'correct_answer': 'C. Berlin',
            'type': 'mcq',
            '_originalCorrectAnswer': 'A. Paris'  # Trường tạm còn sót lại không được ghi đè đáp án mới
        }
    ]

    restored = quiz_service._restore_and_protect_questions(new_questions, old_questions=old_questions)
    assert restored[0]['correct_answer'] == 'C. Berlin', \
        "Backend đã để _originalCorrectAnswer đè lên đáp án mới vừa sửa!"





