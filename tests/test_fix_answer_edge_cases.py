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
