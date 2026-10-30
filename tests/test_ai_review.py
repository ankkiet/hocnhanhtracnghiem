import unittest
from unittest.mock import patch, MagicMock

class TestAIReviewLogic(unittest.TestCase):
    def test_heuristic_explanation_reclassification(self):
        # Giả lập logic chuẩn hóa feedback
        valid_cats = ["explanation", "latex", "knowledge", "answer", "grammar_typo", "format", "restructure", "delete"]
        cat_names = {
            "explanation": "Bổ sung lời giải",
            "latex": "Lỗi công thức LaTeX",
            "knowledge": "Sai kiến thức",
            "answer": "Sai đáp án",
            "grammar_typo": "Chính tả & Diễn đạt",
            "format": "Lỗi định dạng",
            "restructure": "Thay đổi kết cấu",
            "delete": "Yêu cầu xóa câu"
        }

        # Case 1: AI nhầm lẫn gán category là grammar_typo hoặc latex nhưng thực chất là thiếu lời giải
        item = {
            "question_index": 0,
            "action": "modify",
            "category": "latex", # AI nhầm gán là latex
            "category_name": "Lỗi công thức LaTeX",
            "reason": "Câu hỏi môn Toán thiếu lời giải thích chi tiết từng bước",
            "corrected_data": {
                "question": "Tính tích phân I",
                "options": ["A. 1", "B. 2", "C. 3", "D. 4"],
                "correct_answer": "A. 1",
                "explain": "Áp dụng công thức nguyên hàm cơ bản ta có..."
            }
        }

        reason_lower = str(item.get("reason", "")).lower()
        cat_name_lower = str(item.get("category_name", "")).lower()

        is_explain_related = any(k in reason_lower or k in cat_name_lower for k in [
            "lời giải", "giải thích", "hướng dẫn giải", "explain", "hdg", "thiếu giải", "chưa có giải", "bổ sung giải", "chưa giải", "cần giải"
        ])
        is_actual_latex_error = any(k in reason_lower for k in [
            "cú pháp latex", "thẻ $", "kí tự latex", "lỗi latex", "mathjax", "công thức hỏng", "ngoặc nhọn", "\\frac", "\\sqrt", "chưa đóng $"
        ]) and not is_explain_related

        cat = item["category"]
        if is_explain_related and not is_actual_latex_error:
            cat = "explanation"
            item["category"] = "explanation"
            item["category_name"] = "Bổ sung lời giải"

        self.assertEqual(item["category"], "explanation")
        self.assertEqual(item["category_name"], "Bổ sung lời giải")

    def test_actual_latex_error(self):
        item = {
            "question_index": 1,
            "action": "modify",
            "category": "grammar_typo",
            "reason": "Lỗi cú pháp LaTeX: thẻ $ chưa đóng trong công thức $x^2 + 1",
            "corrected_data": {"explain": ""}
        }

        reason_lower = str(item.get("reason", "")).lower()
        cat_name_lower = str(item.get("category_name", "")).lower()

        is_explain_related = any(k in reason_lower or k in cat_name_lower for k in [
            "lời giải", "giải thích", "hướng dẫn giải", "explain", "hdg", "thiếu giải", "chưa có giải", "bổ sung giải", "chưa giải", "cần giải"
        ])
        is_actual_latex_error = any(k in reason_lower for k in [
            "cú pháp latex", "thẻ $", "kí tự latex", "lỗi latex", "mathjax", "công thức hỏng", "ngoặc nhọn", "\\frac", "\\sqrt", "chưa đóng $"
        ]) and not is_explain_related

        if is_explain_related and not is_actual_latex_error:
            item["category"] = "explanation"
            item["category_name"] = "Bổ sung lời giải"
        elif is_actual_latex_error:
            item["category"] = "latex"
            item["category_name"] = "Lỗi công thức LaTeX"

        self.assertEqual(item["category"], "latex")
        self.assertEqual(item["category_name"], "Lỗi công thức LaTeX")

if __name__ == '__main__':
    unittest.main()
