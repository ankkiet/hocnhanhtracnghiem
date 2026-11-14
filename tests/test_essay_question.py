import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.text_parser import extract_questions_from_text_bulletproof
from services.ai_service import normalize_question_data
from core.answer_key_extractor import AnswerKeyMap, reconcile_quiz_with_answer_key
from core.docx_exporter import export_quiz_to_docx


class TestEssayQuestion(unittest.TestCase):

    def test_text_parser_essay_section_part_iv(self):
        """Kiểm tra bóc tách đề thi chứa phần IV tự luận có hướng dẫn chấm và thang điểm."""
        raw_text = """
PHẦN I. Câu trắc nghiệm nhiều phương án lựa chọn
Câu 1: Cho hàm số y = f(x). Phương trình f'(x) = 0 có mấy nghiệm?
A. 1
*B. 2
C. 3
D. 4

PHẦN IV. TỰ LUẬN (2,0 điểm)
Câu 2: (1,0 điểm) Tìm giá trị lớn nhất của hàm số y = -x^2 + 4x trên đoạn [0, 3].
Hướng dẫn chấm:
Ta có y' = -2x + 4. y' = 0 <=> x = 2 thuộc [0, 3].
y(0) = 0, y(2) = 4, y(3) = 3.
Vậy giá trị lớn nhất của hàm số là 4 tại x = 2.

Câu 3: (1,0 điểm) Giải phương trình 2^(x+1) = 16.
Thang điểm:
Phương trình tương đương 2^(x+1) = 2^4 <=> x + 1 = 4 <=> x = 3.
Vậy tập nghiệm của phương trình là S = {3}.
"""
        questions = extract_questions_from_text_bulletproof(raw_text)
        self.assertEqual(len(questions), 3)

        # Câu 1: MCQ
        self.assertEqual(questions[0]['type'], 'mcq')
        self.assertTrue(len(questions[0]['options']) >= 4)

        # Câu 2: Tự luận
        q2 = questions[1]
        self.assertEqual(q2['type'], 'essay')
        self.assertEqual(q2['options'], [])
        self.assertIn("Tìm giá trị lớn nhất", q2['question'])
        self.assertIn("giá trị lớn nhất của hàm số là 4", q2['correct_answer'])

        # Câu 3: Tự luận
        q3 = questions[2]
        self.assertEqual(q3['type'], 'essay')
        self.assertEqual(q3['options'], [])
        self.assertIn("Giải phương trình", q3['question'])
        self.assertIn("x = 3", q3['correct_answer'])

    def test_text_parser_phan_ii_tu_luan(self):
        """Kiểm tra đề thi có 'Phần II: Tự luận' (ưu tiên Tự luận thay vì Đúng/Sai)."""
        raw_text = """
PHẦN I: TRẮC NGHIỆM KHÁCH QUAN
Câu 1: Số nào sau đây là số nguyên tố?
*A. 2
B. 4
C. 6
D. 8

PHẦN II: TỰ LUẬN
Câu 2: Chứng minh rằng tổng hai số chẵn luôn là một số chẵn.
Đáp án:
Gọi hai số chẵn là 2k và 2m (k, m thuộc Z).
Tổng là 2k + 2m = 2(k + m) chia hết cho 2, do đó là số chẵn.
"""
        questions = extract_questions_from_text_bulletproof(raw_text)
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]['type'], 'mcq')
        self.assertEqual(questions[1]['type'], 'essay')
        self.assertEqual(questions[1]['options'], [])
        self.assertIn("Tổng là 2k + 2m", questions[1]['correct_answer'])

    def test_normalize_quiz_data_essay(self):
        """Kiểm tra hàm chuẩn hóa normalize_question_data giữ đúng loại essay và xóa options."""
        raw_data = [
            {
                "question": "Tính đạo hàm của hàm số f(x) = sin(x)",
                "type": "tu_luan",
                "options": [],
                "correct_answer": "f'(x) = cos(x)",
                "explain": "Áp dụng bảng đạo hàm cơ bản."
            },
            {
                "question": "Phát biểu định lý Pytago",
                "type": "essay",
                "options": ["Phương án A", "Phương án B"], # Bị thừa options cần dọn dẹp
                "correct_answer": "Trong tam giác vuông, bình phương cạnh huyền bằng tổng bình phương hai cạnh góc vuông."
            }
        ]
        normalized = [normalize_question_data(q, use_ai=False) for q in raw_data]
        self.assertEqual(len(normalized), 2)
        for q in normalized:
            self.assertEqual(q['type'], 'essay')
            self.assertEqual(q['options'], [])
            self.assertTrue(bool(q['correct_answer']))

    def test_answer_key_extractor_part4_essay(self):
        """Kiểm tra AnswerKeyMap lưu trữ và đối soát câu hỏi tự luận phần 4."""
        ak = AnswerKeyMap()
        ak.set_answer(4, 1, "Hướng dẫn chấm câu 1: giải thích các bước...")
        self.assertEqual(ak.get_answer('essay', 1), "Hướng dẫn chấm câu 1: giải thích các bước...")

        quiz_data = [
            {
                "group_title": "PHẦN IV. TỰ LUẬN",
                "question": "Câu 1: Giải hệ phương trình",
                "type": "essay",
                "options": [],
                "correct_answer": ""
            }
        ]
        reconciled = reconcile_quiz_with_answer_key(quiz_data, ak)
        self.assertEqual(reconciled[0]['type'], 'essay')
        self.assertEqual(reconciled[0]['correct_answer'], "Hướng dẫn chấm câu 1: giải thích các bước...")

    def test_docx_export_essay_questions(self):
        """Kiểm tra xuất Word cho câu hỏi tự luận có đáp án và không có đáp án."""
        quiz_data = [
            {
                "group_title": "PHẦN I: TRẮC NGHIỆM",
                "question": "Câu 1: Thủ đô của Việt Nam là gì?",
                "type": "mcq",
                "options": ["A. Huế", "B. Đà Nẵng", "C. Hà Nội", "D. TP. Hồ Chí Minh"],
                "correct_answer": "C. Hà Nội"
            },
            {
                "group_title": "PHẦN IV: TỰ LUẬN",
                "question": "Câu 2: Trình bày ý nghĩa lịch sử của Cách mạng tháng Tám năm 1945.",
                "type": "essay",
                "options": [],
                "correct_answer": "Mở ra kỷ nguyên mới độc lập tự do cho dân tộc Việt Nam.",
                "explain": "Sách giáo khoa Lịch sử 12."
            }
        ]

        # 1. Xuất có kèm đáp án và thang điểm chấm
        doc_stream_with_ans = export_quiz_to_docx(title="Đề thi thử Tự luận", questions=quiz_data, show_answers=True)
        self.assertIsNotNone(doc_stream_with_ans)
        self.assertTrue(len(doc_stream_with_ans.getvalue()) > 1000)

        # 2. Xuất đề thi cho học sinh làm (kẻ dòng chấm tự luận)
        doc_stream_no_ans = export_quiz_to_docx(title="Đề thi thử Tự luận", questions=quiz_data, show_answers=False)
        self.assertIsNotNone(doc_stream_no_ans)
        self.assertTrue(len(doc_stream_no_ans.getvalue()) > 1000)

    def test_student_service_essay_evaluation(self):
        """Kiểm tra chấm bài thi có câu tự luận: lưu trữ bài làm, đặt is_correct=None chờ chấm."""
        import asyncio
        from unittest.mock import MagicMock, patch
        from app.services.student_service import StudentService
        from app.schemas.student import SubmitExamRequest

        service = StudentService()
        mock_db = MagicMock()
        mock_quiz_doc = MagicMock()
        mock_quiz_doc.exists = True
        mock_quiz_doc.to_dict.return_value = {
            "title": "Đề thi thử Tự luận Toán",
            "questions": [
                {
                    "question": "Câu 1: 1 + 1 bằng mấy?",
                    "type": "mcq",
                    "options": ["A. 1", "B. 2", "C. 3", "D. 4"],
                    "correct_answer": "B. 2"
                },
                {
                    "question": "Câu 2: Hãy chứng minh định lý căn bậc hai của 2 là số vô tỉ.",
                    "type": "essay",
                    "options": [],
                    "correct_answer": "Giả sử sqrt(2) = a/b tối giản...",
                    "explain": "Phương pháp phản chứng"
                }
            ],
            "settings": {}
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_quiz_doc
        mock_sub_ref = MagicMock()
        mock_sub_ref.id = "sub_test_123"
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_sub_ref

        req = SubmitExamRequest(
            quiz_id="TEST_ESSAY_QUIZ",
            student_name="Nguyễn Văn An",
            answers={
                "0": "B. 2",
                "1": "Giả sử sqrt(2) là số hữu tỉ, suy ra 2 = a^2 / b^2..."
            },
            time_elapsed=120
        )

        with patch.object(service, 'get_db', return_value=mock_db):
            res = asyncio.run(service.submit_exam(req))
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["score"], 1.0)  # MCQ được 1 điểm, Tự luận chưa tính điểm
            self.assertEqual(res["total_questions"], 2)

            results = res["results"]
            self.assertEqual(len(results), 2)
            # Câu 1: MCQ đúng
            self.assertEqual(results[0]["type"], "mcq")
            self.assertTrue(results[0]["is_correct"])
            self.assertEqual(results[0]["earned"], 1.0)
            # Câu 2: Tự luận chờ chấm
            self.assertEqual(results[1]["type"], "essay")
            self.assertIsNone(results[1]["is_correct"])
            self.assertEqual(results[1]["earned"], 0.0)
            self.assertIn("Giả sử sqrt(2)", results[1]["user_answer"])

    def test_student_service_custom_scoring_weights(self):
        """Kiểm tra chấm bài thi có thiết lập trọng số điểm (q.points) cho từng câu hỏi."""
        import asyncio
        from unittest.mock import MagicMock, patch
        from app.services.student_service import StudentService
        from app.schemas.student import SubmitExamRequest

        service = StudentService()
        mock_db = MagicMock()
        mock_quiz_doc = MagicMock()
        mock_quiz_doc.exists = True
        mock_quiz_doc.to_dict.return_value = {
            "title": "Đề thi tùy chỉnh điểm từng phần",
            "questions": [
                {
                    "question": "Câu 1: MCQ",
                    "type": "mcq",
                    "options": ["A. Đúng", "B. Sai"],
                    "correct_answer": "A. Đúng",
                    "points": 0.25
                },
                {
                    "question": "Câu 2: Đúng Sai 4 ý",
                    "type": "true_false",
                    "options": ["a) Ý 1", "b) Ý 2", "c) Ý 3", "d) Ý 4"],
                    "correct_answer": {"a": True, "b": False, "c": True, "d": False},
                    "points": 1.0
                },
                {
                    "question": "Câu 3: Trả lời ngắn",
                    "type": "short_answer",
                    "correct_answer": "42",
                    "points": 0.5
                },
                {
                    "question": "Câu 4: Tự luận",
                    "type": "essay",
                    "correct_answer": "Đáp án mẫu",
                    "points": 2.0
                }
            ],
            "settings": {
                "scoring": {
                    "mode": "custom"
                }
            }
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_quiz_doc
        mock_sub_ref = MagicMock()
        mock_sub_ref.id = "sub_custom_scoring_456"
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_sub_ref

        req = SubmitExamRequest(
            quiz_id="TEST_CUSTOM_SCORING",
            student_name="Trần Thị Mai",
            answers={
                "0": "A. Đúng", # Đúng hoàn toàn -> 0.25đ
                "1": {"a": True, "b": False, "c": False, "d": False}, # Đúng 3/4 ý -> tỉ lệ 0.5 * 1.0 = 0.5đ
                "2": "42", # Đúng hoàn toàn -> 0.5đ
                "3": "Bài làm tự luận của học sinh" # Tự luận -> 0đ (chờ chấm)
            },
            time_elapsed=200
        )

        with patch.object(service, 'get_db', return_value=mock_db):
            res = asyncio.run(service.submit_exam(req))
            self.assertEqual(res["status"], "success")
            # Điểm đạt = 0.25 + 0.5 + 0.5 = 1.25đ
            self.assertAlmostEqual(res["score"], 1.25, places=2)
            # Tổng điểm tối đa = 0.25 + 1.0 + 0.5 + 2.0 = 3.75đ
            self.assertAlmostEqual(res["max_score"], 3.75, places=2)

            results = res["results"]
            self.assertEqual(len(results), 4)
            self.assertEqual(results[0]["max_points"], 0.25)
            self.assertEqual(results[0]["earned"], 0.25)

            self.assertEqual(results[1]["max_points"], 1.0)
            self.assertEqual(results[1]["earned"], 0.5)

            self.assertEqual(results[2]["max_points"], 0.5)
            self.assertEqual(results[2]["earned"], 0.5)

            self.assertEqual(results[3]["max_points"], 2.0)
            self.assertEqual(results[3]["earned"], 0.0)

    def test_student_service_gdpt2018_scoring_mode(self):
        """Kiểm tra chấm bài thi chế độ chuẩn GDPT 2018 (Phần I: 3.0đ, Phần II: 4.0đ, Phần III: 3.0đ)."""
        import asyncio
        from unittest.mock import MagicMock, patch
        from app.services.student_service import StudentService
        from app.schemas.student import SubmitExamRequest

        service = StudentService()
        mock_db = MagicMock()
        mock_quiz_doc = MagicMock()
        mock_quiz_doc.exists = True
        mock_quiz_doc.to_dict.return_value = {
            "title": "Đề thi chuẩn GDPT 2018",
            "questions": [
                # 12 câu MCQ (Phần I = 3.0đ => 0.25đ/câu)
                {"question": f"Câu {i}: MCQ", "type": "mcq", "options": ["A. 1", "B. 2"], "correct_answer": "A. 1"}
                for i in range(1, 13)
            ] + [
                # 4 câu TF (Phần II = 4.0đ => 1.0đ/câu)
                {"question": f"Câu {i}: TF", "type": "true_false", "options": ["a", "b", "c", "d"], "correct_answer": {"a": True, "b": True, "c": True, "d": True}}
                for i in range(13, 17)
            ] + [
                # 6 câu Short Answer (Phần III = 3.0đ => 0.5đ/câu)
                {"question": f"Câu {i}: SA", "type": "short_answer", "correct_answer": "10"}
                for i in range(17, 23)
            ],
            "settings": {
                "scoring": {
                    "mode": "gdpt2018",
                    "part1_total": 3.0,
                    "part2_total": 4.0,
                    "part3_total": 3.0,
                    "part4_total": 0.0
                }
            }
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_quiz_doc
        mock_sub_ref = MagicMock()
        mock_sub_ref.id = "sub_gdpt_789"
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_sub_ref

        # Học sinh làm đúng tất cả 12 câu MCQ, 4 câu TF, 6 câu SA
        answers = {}
        for i in range(12):
            answers[str(i)] = "A. 1"
        for i in range(12, 16):
            answers[str(i)] = {"a": True, "b": True, "c": True, "d": True}
        for i in range(16, 22):
            answers[str(i)] = "10"

        req = SubmitExamRequest(
            quiz_id="TEST_GDPT2018",
            student_name="Lê Quốc Bảo",
            answers=answers,
            time_elapsed=1500
        )

        with patch.object(service, 'get_db', return_value=mock_db):
            res = asyncio.run(service.submit_exam(req))
            self.assertEqual(res["status"], "success")
            self.assertAlmostEqual(res["score"], 10.0, places=2)
            self.assertAlmostEqual(res["max_score"], 10.0, places=2)
            self.assertEqual(res["results"][0]["max_points"], 0.25)
            self.assertEqual(res["results"][12]["max_points"], 1.0)
            self.assertEqual(res["results"][16]["max_points"], 0.5)

    def test_student_service_essay_submission_with_image(self):
        """Kiểm tra học sinh nộp bài tự luận đính kèm ảnh chụp bài làm viết tay (Base64 dataURL)."""
        import asyncio
        from unittest.mock import MagicMock, patch
        from app.services.student_service import StudentService
        from app.schemas.student import SubmitExamRequest

        service = StudentService()
        mock_db = MagicMock()
        mock_quiz_doc = MagicMock()
        mock_quiz_doc.exists = True
        mock_quiz_doc.to_dict.return_value = {
            "title": "Đề kiểm tra học kỳ Toán",
            "questions": [
                {
                    "question": "Câu 1: Vẽ đồ thị và giải thích bài toán hình học.",
                    "type": "essay",
                    "options": [],
                    "correct_answer": "Xem đáp án chi tiết của giáo viên",
                    "points": 3.0
                }
            ],
            "settings": {}
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_quiz_doc
        mock_sub_ref = MagicMock()
        mock_sub_ref.id = "sub_image_essay_101"
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_sub_ref

        # Bài làm của học sinh chứa cả lời giải và ảnh bài chụp viết tay
        image_dataurl = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP..."
        student_submission_text = f"Lời giải của em:\nBước 1: Ta có định lý sin...\n![Ảnh bài làm chụp từ điện thoại]({image_dataurl})"

        req = SubmitExamRequest(
            quiz_id="TEST_IMAGE_ESSAY",
            student_name="Đặng Thùy Dung",
            answers={
                "0": student_submission_text
            },
            time_elapsed=600
        )

        with patch.object(service, 'get_db', return_value=mock_db):
            res = asyncio.run(service.submit_exam(req))
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["score"], 0.0) # Tự luận chờ giáo viên chấm
            self.assertEqual(res["max_score"], 3.0)

            ans_saved = res["results"][0]["user_answer"]
            self.assertIn("data:image/jpeg;base64", ans_saved)
            self.assertIn("Bước 1: Ta có định lý sin", ans_saved)


if __name__ == '__main__':
    unittest.main()
