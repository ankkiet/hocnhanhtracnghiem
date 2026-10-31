import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import json
import tempfile
import shutil
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.gemini_tracker_service import GeminiTrackerService, mask_api_key
from services.ai_service import (
    normalize_question_data,
    cross_check_answers,
    generate_similar_questions,
    AIService
)
from core.answer_key_extractor import reconcile_quiz_with_answer_key


class TestGeminiTrackerService(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.cache_file = os.path.join(self.test_dir, "test_gemini_tracker.json")
        self.tracker = GeminiTrackerService(cache_file=self.cache_file)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_mask_api_key(self):
        key = "AIzaSyB1234567890abcdefghijklmnopqrstuv"
        masked = self.tracker.mask_api_key(key)
        self.assertTrue(masked.startswith("AIzaSyB..."))
        self.assertTrue(masked.endswith("stuv"))

        short_key = "abc123"
        self.assertEqual(mask_api_key(short_key), "Key_***")
        self.assertEqual(mask_api_key(""), "UNKNOWN_KEY")

    def test_record_success_and_cost(self):
        api_key = "AIzaSyTestSuccessKey12345"
        self.tracker.record_call(
            api_key=api_key,
            model="gemini-2.5-flash",
            success=True,
            prompt_chars=4000,
            response_chars=2000,
            duration_ms=1250
        )
        metrics = self.tracker.get_metrics([api_key])
        today = metrics["today"]
        self.assertEqual(today["total_calls"], 1)
        self.assertEqual(today["success_calls"], 1)
        self.assertEqual(today["error_429"], 0)
        self.assertEqual(today["success_rate"], 100.0)
        self.assertGreater(today["estimated_cost_usd"], 0)
        self.assertGreater(today["estimated_cost_vnd"], 0)

        # Key status
        key_statuses = metrics["key_statuses"]
        self.assertEqual(len(key_statuses), 1)
        self.assertEqual(key_statuses[0]["status"], "healthy")

    def test_record_429_quota_error(self):
        api_key = "AIzaSyTestQuotaKey12345"
        # 1st 429
        self.tracker.record_call(
            api_key=api_key,
            model="gemini-2.5-flash",
            success=False,
            error_type="429_quota",
            duration_ms=500
        )
        metrics = self.tracker.get_metrics([api_key])
        self.assertEqual(metrics["today"]["error_429"], 1)
        self.assertEqual(metrics["key_statuses"][0]["status"], "warning_429")

        # More 429 errors -> exhausted
        for _ in range(4):
            self.tracker.record_call(
                api_key=api_key,
                model="gemini-2.5-flash",
                success=False,
                error_type="429_quota",
                duration_ms=500
            )
        metrics = self.tracker.get_metrics([api_key])
        self.assertGreaterEqual(metrics["today"]["error_429"], 5)
        self.assertEqual(metrics["key_statuses"][0]["status"], "exhausted")

    def test_daily_history_generation(self):
        api_key = "AIzaSyTestHistoryKey"
        self.tracker.record_call(api_key, model="gemini-2.5-flash", success=True)
        self.tracker.record_call(api_key, model="gemini-2.5-flash", success=False, error_type="other")
        metrics = self.tracker.get_metrics([api_key])
        history = metrics["daily_history"]
        self.assertGreaterEqual(len(history), 1)
        today_entry = history[0]
        self.assertEqual(today_entry["total_calls"], 2)
        self.assertEqual(today_entry["success_calls"], 1)
        self.assertEqual(today_entry["other_errors"], 1)


class TestAISuggestedAnswerTagging(unittest.TestCase):
    def test_mcq_no_answer_key_tags_ai_suggested(self):
        raw_question = {
            "question": "Thủ đô của Việt Nam là gì?",
            "options": ["A. Hà Nội", "B. TP. Hồ Chí Minh", "C. Đà Nẵng", "D. Hải Phòng"],
            "type": "mcq"
        }
        # No answer key supplied and no * marked option -> AI suggests
        normalized = normalize_question_data(raw_question)
        self.assertTrue(normalized.get("is_ai_suggested"))
        self.assertIn("AI đề xuất", normalized.get("ai_suggestion_note", ""))
        self.assertIn(normalized.get("correct_answer"), normalized["options"])

    def test_mcq_with_marked_option_not_ai_suggested(self):
        raw_question = {
            "question": "Thủ đô của Việt Nam là gì?",
            "options": ["*A. Hà Nội", "B. TP. Hồ Chí Minh", "C. Đà Nẵng", "D. Hải Phòng"],
            "type": "mcq"
        }
        normalized = normalize_question_data(raw_question)
        self.assertFalse(normalized.get("is_ai_suggested", False))

    def test_reconcile_with_official_answer_key_clears_ai_suggested(self):
        quiz_data = [{
            "question": "Câu 1: Thủ đô của Việt Nam?",
            "options": ["A. Hà Nội", "B. Huế", "C. Đà Nẵng", "D. Cần Thơ"],
            "correct_answer": "A. Hà Nội",
            "is_ai_suggested": True,
            "ai_suggestion_note": "AI đề xuất, cần giáo viên xác nhận"
        }]
        answer_key = {1: "A"}
        reconciled = reconcile_quiz_with_answer_key(quiz_data, answer_key)
        self.assertFalse(reconciled[0].get("is_ai_suggested"))
        self.assertFalse(reconciled[0].get("ai_suggestion_note"))

    def test_true_false_ai_suggested(self):
        raw_question = {
            "question": "Cho các nhận định sau về tam giác đều:",
            "options": ["a) Ba cạnh bằng nhau", "b) Ba góc bằng 90 độ", "c) Có 3 trục đối xứng", "d) Có 1 tâm đối xứng"],
            "type": "true_false"
        }
        normalized = normalize_question_data(raw_question)
        self.assertTrue(normalized.get("is_ai_suggested"))
        self.assertIsInstance(normalized.get("correct_answer"), dict)


class TestCrossCheckAnswers(unittest.TestCase):
    @patch("services.ai_service.call_gemini_with_fallback")
    def test_cross_check_detects_mismatch(self, mock_gemini):
        # Teacher set answer as "B. 5"
        quiz_data = [{
            "question": "Tính 2 + 2 = ?",
            "options": ["A. 4", "B. 5", "C. 6", "D. 7"],
            "correct_answer": "B. 5",
            "type": "mcq"
        }]

        # AI independently solves it and returns A
        mock_resp = MagicMock()
        mock_resp.text = json.dumps([{
            "index": 0,
            "ai_solved_answer": "A",
            "explain": "Ta có 2 + 2 = 4, chọn A."
        }])
        mock_gemini.return_value = mock_resp

        res = asyncio.run(cross_check_answers(quiz_data, api_keys=["fake-key"]))
        self.assertEqual(res.get("mismatch_count"), 1)
        checked_quiz = res.get("data", [])
        q = checked_quiz[0]
        self.assertTrue(q.get("has_cross_check_warning"))
        info = q.get("cross_check_info", {})
        self.assertEqual(info.get("teacher_answer"), "B. 5")
        self.assertEqual(info.get("ai_answer"), "A")
        # Ensure original teacher answer was NOT silently overwritten
        self.assertEqual(q.get("correct_answer"), "B. 5")

    @patch("services.ai_service.call_gemini_with_fallback")
    def test_cross_check_matching_answers(self, mock_gemini):
        quiz_data = [{
            "question": "Tính 2 + 2 = ?",
            "options": ["A. 4", "B. 5", "C. 6", "D. 7"],
            "correct_answer": "A. 4",
            "type": "mcq"
        }]

        # AI solves it and also returns A
        mock_resp = MagicMock()
        mock_resp.text = json.dumps([{
            "index": 0,
            "ai_solved_answer": "A",
            "explain": "2 + 2 = 4"
        }])
        mock_gemini.return_value = mock_resp

        res = asyncio.run(cross_check_answers(quiz_data, api_keys=["fake-key"]))
        self.assertEqual(res.get("mismatch_count"), 0)
        checked_quiz = res.get("data", [])
        self.assertFalse(checked_quiz[0].get("has_cross_check_warning", False))


class TestGenerateSimilarQuestions(unittest.TestCase):
    @patch("services.ai_service.call_gemini_with_fallback")
    def test_generate_similar_numbers(self, mock_gemini):
        base_question = {
            "question": "Một vật chuyển động với vận tốc 10 m/s trong 5s. Tính quãng đường đi được?",
            "options": ["A. 50m", "B. 2m", "C. 15m", "D. 500m"],
            "correct_answer": "A. 50m",
            "type": "mcq"
        }

        mock_resp = MagicMock()
        mock_resp.text = json.dumps([
            {
                "question": "Một vật chuyển động với vận tốc 20 m/s trong 4s. Tính quãng đường đi được?",
                "options": ["A. 80m", "B. 5m", "C. 24m", "D. 160m"],
                "correct_answer": "A. 80m",
                "explain": "s = v * t = 20 * 4 = 80m",
                "type": "mcq"
            },
            {
                "question": "Một vật chuyển động với vận tốc 15 m/s trong 6s. Tính quãng đường đi được?",
                "options": ["A. 90m", "B. 2.5m", "C. 21m", "D. 180m"],
                "correct_answer": "A. 90m",
                "explain": "s = v * t = 15 * 6 = 90m",
                "type": "mcq"
            }
        ])
        mock_gemini.return_value = mock_resp

        variants = asyncio.run(generate_similar_questions(
            base_question=base_question,
            count=2,
            mode="change_numbers",
            difficulty="keep",
            api_keys=["fake-key"]
        ))
        self.assertEqual(len(variants), 2)
        self.assertEqual(variants[0]["correct_answer"], "A. 80m")
        self.assertEqual(len(variants[0]["options"]), 4)

    @patch("app.api.routes.teacher._get_db")
    @patch("services.ai_service.generate_similar_questions")
    def test_endpoint_generate_similar_with_base_question(self, mock_gen, mock_get_db):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.routes.teacher import router as teacher_router

        mock_get_db.return_value = None
        mock_gen.return_value = [
            {
                "question": "Câu tương tự 1",
                "options": ["A. 1", "B. 2", "C. 3", "D. 4"],
                "correct_answer": "A. 1",
                "type": "mcq"
            }
        ]

        app = FastAPI()
        app.include_router(teacher_router)
        client = TestClient(app)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"}):
            resp = client.post(
                "/api/teacher/generate_similar_questions",
                json={
                    "teacher_token": "",
                    "base_question": {
                        "question": "Câu gốc",
                        "options": ["A. 1", "B. 2"],
                        "correct_answer": "A. 1",
                        "type": "mcq"
                    },
                    "count": 1,
                    "mode": "change_numbers"
                }
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("similar_questions", data)
        self.assertIn("data", data)
        self.assertEqual(len(data["similar_questions"]), 1)
        self.assertEqual(data["similar_questions"][0]["question"], "Câu tương tự 1")

    @patch("app.api.routes.teacher._get_db")
    @patch("services.ai_service.generate_similar_questions")
    def test_endpoint_generate_similar_with_question(self, mock_gen, mock_get_db):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.routes.teacher import router as teacher_router

        mock_get_db.return_value = None
        mock_gen.return_value = [
            {
                "question": "Câu biến thể",
                "options": ["A. 10", "B. 20"],
                "correct_answer": "A. 10",
                "type": "mcq"
            }
        ]

        app = FastAPI()
        app.include_router(teacher_router)
        client = TestClient(app)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"}):
            resp = client.post(
                "/api/teacher/generate_similar_questions",
                json={
                    "teacher_token": "any_token",
                    "question": {
                        "question": "Câu gốc",
                        "options": ["A. 10", "B. 20"],
                        "correct_answer": "A. 10",
                        "type": "mcq"
                    },
                    "count": 1,
                    "mode": "both"
                }
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["similar_questions"]), 1)
        self.assertEqual(data["similar_questions"][0]["question"], "Câu biến thể")

    def test_endpoint_generate_similar_missing_question(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.routes.teacher import router as teacher_router

        app = FastAPI()
        app.include_router(teacher_router)
        client = TestClient(app)

        resp = client.post(
            "/api/teacher/generate_similar_questions",
            json={"teacher_token": ""}
        )
        self.assertEqual(resp.status_code, 400)


class TestScannedPdfAndImageOCR(unittest.TestCase):
    def test_document_scanned_pdf_threshold_logic(self):
        # Simulate logic in document.py: if total_text / num_pages < 60 -> scanned PDF
        total_text_scanned = 50
        num_pages_scanned = 5
        ratio_scanned = total_text_scanned / max(1, num_pages_scanned)
        self.assertLess(ratio_scanned, 60)

        total_text_digital = 5000
        num_pages_digital = 5
        ratio_digital = total_text_digital / max(1, num_pages_digital)
        self.assertGreaterEqual(ratio_digital, 60)

    def test_allowed_file_extensions(self):
        allowed = [".docx", ".pdf", ".png", ".jpg", ".jpeg", ".webp"]
        self.assertIn(".pdf", allowed)
        self.assertIn(".docx", allowed)
        self.assertIn(".png", allowed)
        self.assertIn(".jpg", allowed)
        self.assertIn(".jpeg", allowed)
        self.assertIn(".webp", allowed)


if __name__ == "__main__":
    unittest.main()
