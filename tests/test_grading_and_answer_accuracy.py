import pytest
from app.utils.helpers import (
    evaluate_mcq_answer,
    evaluate_true_false_answer,
    evaluate_short_answer,
)
from core.answer_key_extractor import extract_answer_key_from_doc, reconcile_quiz_with_answer_key
from services.ai_service import parse_tf_answer
from docx import Document


def test_two_column_table_mcq_and_tf_extraction():
    """Kiểm tra bóc tách bảng đáp án 2 cột (Câu | Đáp án) không bị nuốt chữ cái hoặc lộn sang part3."""
    doc = Document()
    tbl = doc.add_table(rows=5, cols=2)
    tbl.rows[0].cells[0].text = "Câu"
    tbl.rows[0].cells[1].text = "Đáp án"
    tbl.rows[1].cells[0].text = "1"
    tbl.rows[1].cells[1].text = "A"
    tbl.rows[2].cells[0].text = "2"
    tbl.rows[2].cells[1].text = "B"
    tbl.rows[3].cells[0].text = "3"
    tbl.rows[3].cells[1].text = "Đ S Đ S"
    tbl.rows[4].cells[0].text = "4"
    tbl.rows[4].cells[1].text = "15.5"

    ak = extract_answer_key_from_doc(doc)
    assert ak.part1.get(1) == "A", f"Câu 1 phải thuộc part1 (MCQ), nhận được: {ak.part1}"
    assert ak.part1.get(2) == "B", f"Câu 2 phải thuộc part1 (MCQ), nhận được: {ak.part1}"
    assert isinstance(ak.part2.get(3), dict), f"Câu 3 phải thuộc part2 (True/False dict), nhận được: {ak.part2}"
    assert ak.part2[3]['a'] is True and ak.part2[3]['b'] is False
    assert ak.part3.get(4) == "15.5", f"Câu 4 phải thuộc part3 (Short answer), nhận được: {ak.part3}"


def test_evaluate_true_false_vietnamese_d_letter():
    """Kiểm tra chấm điểm câu Đúng/Sai với chữ 'đ' (in thường) và 'Đ' (in hoa)."""
    correct = {'a': True, 'b': False, 'c': True, 'd': False}
    # Học sinh trả lời dạng 'đ' và 's'
    user_with_vietnamese_d = {'a': 'đ', 'b': 's', 'c': 'đ', 'd': 's'}
    is_corr, score = evaluate_true_false_answer(user_with_vietnamese_d, correct)
    assert is_corr is True, f"Học sinh làm đúng 4/4 ý bằng chữ 'đ'/'s' phải được True, nhận được: {is_corr}"
    assert score == 1.0, f"Học sinh làm đúng 4/4 ý phải được 1.0đ, nhận được: {score}"


def test_evaluate_true_false_with_keys_having_punctuation():
    """Kiểm tra key có dấu ngoặc như 'a)', 'b)' không bị chấm 0 điểm."""
    correct = {'a': True, 'b': False, 'c': True, 'd': False}
    user = {'a)': True, 'b)': False, 'c)': True, 'd)': False}
    is_corr, score = evaluate_true_false_answer(user, correct)
    assert is_corr is True
    assert score == 1.0


def test_evaluate_true_false_partial_scale_and_non_4_opts():
    """Kiểm tra barem GDPT 2018 cho 4 ý và câu ít hơn 4 ý."""
    correct_4 = {'a': True, 'b': False, 'c': True, 'd': False}
    # Đúng 1 ý -> 0.1đ
    assert evaluate_true_false_answer({'a': True, 'b': True, 'c': False, 'd': True}, correct_4)[1] == 0.1
    # Đúng 2 ý -> 0.25đ
    assert evaluate_true_false_answer({'a': True, 'b': False, 'c': False, 'd': True}, correct_4)[1] == 0.25
    # Đúng 3 ý -> 0.5đ
    assert evaluate_true_false_answer({'a': True, 'b': False, 'c': True, 'd': True}, correct_4)[1] == 0.5
    # Đúng 4 ý -> 1.0đ
    assert evaluate_true_false_answer({'a': True, 'b': False, 'c': True, 'd': False}, correct_4)[1] == 1.0

    # Câu chỉ có 2 ý (không phải 4 ý): đúng 2/2 phải được 1.0đ (không bị ép về 0.25đ)
    correct_2 = {'a': True, 'b': False}
    user_2 = {'a': True, 'b': False}
    is_c, sc = evaluate_true_false_answer(user_2, correct_2)
    assert is_c is True
    assert sc == 1.0, f"Đúng 2/2 ý của câu 2 ý phải được 1.0đ, nhận được: {sc}"


def test_parse_tf_answer_empty_returns_empty_dict():
    """parse_tf_answer khi chuỗi rỗng hoặc không có đáp án không được tự bịa đáp án fake."""
    assert parse_tf_answer("") == {}
    assert parse_tf_answer(None) == {}
    assert parse_tf_answer("Chưa có đáp án") == {}


def test_evaluate_short_answer_with_units():
    """Kiểm tra chấm điểm câu trả lời ngắn khi có đơn vị đo lường hoặc chú thích trong ngoặc."""
    # Giáo viên ghi '5 m' hoặc '5 (m)', học sinh nhập '5'
    assert evaluate_short_answer("5", "5 m") is True
    assert evaluate_short_answer("5", "5 (m)") is True
    assert evaluate_short_answer("5 m", "5") is True
    assert evaluate_short_answer("10 cm", "10") is True
    assert evaluate_short_answer("2.5 km/h", "2,5") is True
    assert evaluate_short_answer("30°", "30") is True
