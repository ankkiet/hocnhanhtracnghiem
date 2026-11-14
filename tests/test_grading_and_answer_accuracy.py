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



def test_resolve_question_type_aliases_and_inference():
    """Kiểm tra resolve_question_type chuẩn hóa đầy đủ alias và tự suy luận khi thiếu/sai trường type."""
    from app.utils.helpers import resolve_question_type

    assert resolve_question_type({"type": "tf", "options": ["a) Đúng", "b) Sai"]}) == "true_false"
    assert resolve_question_type({"type": "dung_sai", "options": []}) == "true_false"
    assert resolve_question_type({"type": "sa", "correct_answer": "42"}) == "short_answer"
    assert resolve_question_type({"type": "tra_loi_ngan", "options": []}) == "short_answer"
    assert resolve_question_type({"type": "tu_luan", "options": []}) == "essay"
    assert resolve_question_type({"type": "Tự luận", "options": []}) == "essay"

    # Thiếu type hoặc gán nhầm 'mcq' nhưng phương án là a), b), c), d)
    assert resolve_question_type({
        "type": "mcq",
        "options": ["a) Ý 1", "b) Ý 2", "c) Ý 3", "d) Ý 4"],
        "correct_answer": {"a": True, "b": False, "c": True, "d": False}
    }) == "true_false"

    # Thiếu type, suy luận theo group_title hoặc đáp án dict/số
    assert resolve_question_type({
        "group_title": "PHẦN III. Câu hỏi trả lời ngắn",
        "options": [],
        "correct_answer": "12.5"
    }) == "short_answer"
    assert resolve_question_type({
        "group_title": "PHẦN IV. Tự luận",
        "options": [],
        "correct_answer": "Hướng dẫn chấm chi tiết"
    }) == "essay"
    assert resolve_question_type({
        "options": [],
        "correct_answer": {"a": True, "b": False}
    }) == "true_false"
    assert resolve_question_type({
        "options": ["A. 1", "B. 2", "C. 3", "D. 4"],
        "correct_answer": "A. 1"
    }) == "mcq"


def test_submit_exam_alias_types_and_history_max_score():
    """Kiểm tra submit_exam chấm đúng các câu alias/khuyết type và lưu max_score vào history."""
    import asyncio
    from unittest.mock import MagicMock, patch
    from app.services.student_service import StudentService
    from app.schemas.student import SubmitExamRequest
    from core.state import QUIZ_CACHE, SUBMISSIONS_CACHE, LEADERBOARD_CACHE

    QUIZ_CACHE.clear()
    SUBMISSIONS_CACHE.clear()
    LEADERBOARD_CACHE.clear()

    service = StudentService()
    mock_db = MagicMock()
    mock_quiz_doc = MagicMock()
    mock_quiz_doc.exists = True
    mock_quiz_doc.to_dict.return_value = {
        "title": "Đề hỗn hợp nhiều định dạng type",
        "questions": [
            {"question": "Câu 1 MCQ khuyết type", "options": ["A. 1", "B. 2", "C. 3", "D. 4"], "correct_answer": "A. 1"},
            {"question": "Câu 2 alias tf", "type": "tf", "options": ["a) Ý 1", "b) Ý 2", "c) Ý 3", "d) Ý 4"], "correct_answer": {"a": True, "b": False, "c": True, "d": False}},
            {"question": "Câu 3 alias sa", "type": "sa", "correct_answer": "2,5"},
            {"question": "Câu 4 SA theo group_title", "group_title": "PHẦN III: Trả lời ngắn", "options": [], "correct_answer": "100"},
            {"question": "Câu 5 alias tu_luan", "type": "tu_luan", "options": [], "correct_answer": "Bài giải mẫu"}
        ],
        "settings": {
            "scoring": {"mode": "auto", "total_score": 10.0}
        }
    }

    mock_sub_ref = MagicMock()
    mock_sub_ref.id = "sub_alias_1"
    mock_hist_ref = MagicMock()

    def _collection_side_effect(name):
        coll = MagicMock()
        if name == "quizzes":
            coll.document.return_value.get.return_value = mock_quiz_doc
            coll.document.return_value.collection.return_value.document.return_value = mock_sub_ref
        elif name == "users":
            coll.document.return_value.collection.return_value.document.return_value = mock_hist_ref
        return coll

    mock_db.collection.side_effect = _collection_side_effect

    req = SubmitExamRequest(
        quiz_id="TEST_ALIAS_MIXED",
        student_name="Nguyễn Văn A",
        student_token="valid_tok",
        answers={
            "0": "A. 1",
            "1": {"a": "đ", "b": "s", "c": "đ", "d": "s"},
            "2": "2.5",
            "3": "100",
            "4": "Bài làm tự luận của học sinh"
        },
        time_elapsed=300
    )

    with patch.object(service, "get_db", return_value=mock_db), \
         patch.object(service, "get_user", return_value={"id": "stu_1", "role": "student", "full_name": "Nguyễn Văn A"}):
        res = asyncio.run(service.submit_exam(req))

    assert res["status"] == "success"
    # Mỗi câu 2.0đ (10 / 5 câu): 4 câu đầu đúng trọn vẹn = 8.0đ, câu tự luận chấm tay = 0.0đ
    assert res["max_score"] == 10.0
    assert res["score"] == 8.0
    assert res["results"][1]["earned"] == 2.0
    assert res["results"][2]["is_correct"] is True
    assert res["results"][3]["is_correct"] is True

    # Kiểm tra bản ghi history cá nhân có lưu max_score
    assert mock_hist_ref.set.called
    hist_payload = mock_hist_ref.set.call_args[0][0]
    assert hist_payload["max_score"] == 10.0
    assert hist_payload["score"] == 8.0


def test_teacher_quiz_analytics_uses_max_score_instead_of_total_questions():
    """Kiểm tra thống kê /quiz_analytics quy đổi điểm hệ 10 theo max_score thực tế thay vì chia cho total_questions."""
    import asyncio
    from unittest.mock import MagicMock, patch
    from app.api.routes.teacher import get_quiz_analytics
    from core.state import QUIZ_CACHE, SUBMISSIONS_CACHE

    QUIZ_CACHE.clear()
    SUBMISSIONS_CACHE.clear()

    questions = [
        {"question": f"Câu {i}", "type": "mcq", "options": ["A. 1", "B. 2"], "correct_answer": "A. 1"}
        for i in range(40)
    ]
    quiz_data = {
        "creator_id": "teacher_1",
        "title": "Đề 40 câu thang 10",
        "data": questions,
        "scoring": {"mode": "auto", "total_score": 10.0},
    }

    sub1 = MagicMock()
    sub1.to_dict.return_value = {
        "student_name": "Học sinh 1",
        "score": 8.5,
        "max_score": 10.0,
        "total_questions": 40,
        "answers": {"0": "A. 1"},
        "time_elapsed": 600,
    }
    # Bài nộp cũ chưa lưu max_score: phải tự suy ra 10.0 từ scoring của đề, không chia 40
    sub2 = MagicMock()
    sub2.to_dict.return_value = {
        "student_name": "Học sinh 2",
        "score": 7.5,
        "total_questions": 40,
        "answers": {"0": "B. 2"},
        "time_elapsed": 700,
    }

    mock_quiz_doc = MagicMock()
    mock_quiz_doc.exists = True
    mock_quiz_doc.to_dict.return_value = quiz_data

    mock_subs_coll = MagicMock()
    mock_subs_coll.get.return_value = [sub1, sub2]

    mock_quiz_doc_ref = MagicMock()
    mock_quiz_doc_ref.get.return_value = mock_quiz_doc
    mock_quiz_doc_ref.collection.return_value = mock_subs_coll

    mock_db = MagicMock()
    mock_db.collection.return_value.document.return_value = mock_quiz_doc_ref

    with patch("app.api.routes.teacher._get_db", return_value=mock_db), \
         patch("app.api.routes.teacher._verify_teacher_access", return_value=({"id": "teacher_1", "role": "teacher"}, "teacher_1")):
        analytics = asyncio.run(get_quiz_analytics("QUIZ_40Q", teacher_token="tok", force_refresh=True))

    assert analytics["status"] == "success"
    students = {s["student_name"]: s for s in analytics["students"]}
    assert students["Học sinh 1"]["scaled_score"] == 8.5
    assert students["Học sinh 1"]["max_score"] == 10.0
    assert students["Học sinh 2"]["scaled_score"] == 7.5
    assert students["Học sinh 2"]["max_score"] == 10.0
    assert analytics["average_score"] == 8.0
    assert analytics["max_score"] == 8.5
    assert analytics["min_score"] == 7.5


def test_evaluate_true_false_unanswered_or_blank_never_awarded_false_credit():
    """Ô bỏ trống ('', None) hoặc chuỗi không hợp lệ tuyệt đối không bị ép thành False để ăn điểm miễn phí."""
    correct_all_false = {'a': False, 'b': False, 'c': False, 'd': False}
    is_c, earned = evaluate_true_false_answer({'a': '', 'b': None, 'c': '   ', 'd': 'unknown'}, correct_all_false)
    assert is_c is False
    assert earned == 0.0

    # Chỉ chọn đúng 1 ý 'd': 'đ', 3 ý còn lại bỏ trống -> chỉ được tính đúng 1 ý = 0.1đ
    correct_mix = {'a': False, 'b': False, 'c': False, 'd': True}
    is_c2, earned2 = evaluate_true_false_answer({'a': '', 'b': None, 'c': '', 'd': 'đ'}, correct_mix)
    assert is_c2 is False
    assert earned2 == 0.1


def test_submit_exam_top_level_scoring_and_top_short_answer_strict():
    """Kiểm tra submit_exam đọc được scoring ở cấp gốc quiz_data và trả lời ngắn không khớp bừa."""
    import asyncio
    from unittest.mock import MagicMock, patch
    from app.services.student_service import StudentService
    from app.schemas.student import SubmitExamRequest
    from core.state import QUIZ_CACHE, SUBMISSIONS_CACHE, LEADERBOARD_CACHE

    QUIZ_CACHE.clear()
    SUBMISSIONS_CACHE.clear()
    LEADERBOARD_CACHE.clear()

    assert evaluate_short_answer("2 + sqrt(3)", "2") is False
    assert evaluate_short_answer("2x+1", "2") is False

    service = StudentService()
    mock_db = MagicMock()
    mock_quiz_doc = MagicMock()
    mock_quiz_doc.exists = True
    mock_quiz_doc.to_dict.return_value = {
        "title": "Đề có scoring ở top-level",
        "questions": [
            {"question": "Q1", "type": "mcq", "options": ["A. 1", "B. 2"], "correct_answer": "A. 1"},
            {"question": "Q2", "type": "short_answer", "correct_answer": "2"},
        ],
        "scoring": {"mode": "auto", "total_score": 10.0}
    }
    mock_sub_ref = MagicMock()
    mock_sub_ref.id = "sub_top_scoring"
    mock_db.collection.return_value.document.return_value.get.return_value = mock_quiz_doc
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_sub_ref

    req = SubmitExamRequest(
        quiz_id="TEST_TOP_SCORING",
        student_name="Thí sinh 1",
        answers={"0": "A. 1", "1": "2 + sqrt(3)"},
        time_elapsed=120
    )
    with patch.object(service, "get_db", return_value=mock_db):
        res = asyncio.run(service.submit_exam(req))

    assert res["max_score"] == 10.0
    assert res["score"] == 5.0
    assert res["results"][0]["is_correct"] is True
    assert res["results"][1]["is_correct"] is False
