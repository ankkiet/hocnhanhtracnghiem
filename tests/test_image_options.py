import unittest
from services.ai_service import clean_option_text, normalize_question_data

class TestImageOptionsPreservation(unittest.TestCase):
    def test_clean_option_text_preserves_img(self):
        opt = "A. <img src='/api/images/quizzes/images/test1.png' class='quiz-image' />"
        clean_text, is_corr, is_fls, char = clean_option_text(opt)
        self.assertEqual(char, "A")
        self.assertIn("<img src='/api/images/quizzes/images/test1.png'", clean_text)

    def test_clean_option_text_preserves_marked_img(self):
        opt = "*A. <img src='/api/images/quizzes/images/test2.png' />"
        clean_text, is_corr, is_fls, char = clean_option_text(opt)
        self.assertEqual(char, "A")
        self.assertTrue(is_corr)
        self.assertIn("<img src='/api/images/quizzes/images/test2.png'", clean_text)

    def test_normalize_question_data_preserves_mcq_image_options(self):
        q = {
            "type": "mcq",
            "question": "Chọn công thức cấu tạo đúng:",
            "options": [
                "A. <img src='/api/images/quizzes/images/img_a.png' />",
                "B. <img src='/api/images/quizzes/images/img_b.png' />",
                "C. <img src='/api/images/quizzes/images/img_c.png' />",
                "D. <img src='/api/images/quizzes/images/img_d.png' />"
            ],
            "correct_answer": "A. <img src='/api/images/quizzes/images/img_a.png' />"
        }
        res = normalize_question_data(q)
        self.assertEqual(len(res["options"]), 4)
        for i, letter in enumerate(["A", "B", "C", "D"]):
            self.assertTrue(res["options"][i].startswith(f"{letter}. "))
            self.assertIn(f"img_{letter.lower()}.png", res["options"][i])

    def test_normalize_question_data_preserves_tf_image_options(self):
        q = {
            "type": "true_false",
            "question": "Xét các phát biểu sau:",
            "options": [
                "a) <img src='/api/images/quizzes/images/tf_a.png' />",
                "b) <img src='/api/images/quizzes/images/tf_b.png' />",
                "c) <img src='/api/images/quizzes/images/tf_c.png' />",
                "d) <img src='/api/images/quizzes/images/tf_d.png' />"
            ],
            "correct_answer": {"a": True, "b": False, "c": True, "d": False}
        }
        res = normalize_question_data(q)
        self.assertEqual(len(res["options"]), 4)
        for i, letter in enumerate(["a", "b", "c", "d"]):
            self.assertTrue(res["options"][i].startswith(f"{letter}) "))
            self.assertIn(f"tf_{letter}.png", res["options"][i])

if __name__ == '__main__':
    unittest.main()
