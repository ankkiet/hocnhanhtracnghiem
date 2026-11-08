import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from services.ai_service import (
    GeminiAPIException,
    chunk_marked_text,
    cross_check_answers,
    generate_mcq_with_gemini,
)


class TestMultiKeyWorkerPool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Tạo văn bản mẫu gồm 30 câu hỏi chuẩn GDPT 2018
        self.sample_30_questions_text = "\n\n".join([
            f"Câu {i}. Nội dung câu hỏi số {i}?\n"
            f"A. Phương án A_{i}\n"
            f"B. Phương án B_{i}\n"
            f"C. Phương án C_{i}\n"
            f"D. Phương án D_{i}\n"
            f"Đáp án: A"
            for i in range(1, 31)
        ])

    def test_chunk_marked_text_custom_size(self):
        """Kiểm tra chunk_marked_text chia đúng số câu mong muốn."""
        chunks = chunk_marked_text(self.sample_30_questions_text, questions_per_chunk=10)
        self.assertEqual(len(chunks), 3)

        chunks_15 = chunk_marked_text(self.sample_30_questions_text, questions_per_chunk=15)
        self.assertEqual(len(chunks_15), 2)

    async def test_empty_api_keys_raises_exception(self):
        """Không có API Key hoặc chỉ có chuỗi rỗng phải báo lỗi GeminiAPIException(NO_API_KEYS)."""
        with self.assertRaises(GeminiAPIException) as ctx:
            await generate_mcq_with_gemini(self.sample_30_questions_text, api_keys=[])
        self.assertEqual(ctx.exception.diagnostic["error_code"], "NO_API_KEYS")

        with self.assertRaises(GeminiAPIException) as ctx2:
            await generate_mcq_with_gemini(self.sample_30_questions_text, api_keys=["   ", ""])
        self.assertEqual(ctx2.exception.diagnostic["error_code"], "NO_API_KEYS")

    @patch("services.ai_service.call_gemini_with_fallback")
    async def test_round_robin_distribution_across_multiple_keys(self, mock_call):
        """
        Kiểm tra với 3 keys và 30 câu (3 chunks x 10 câu):
        Mỗi chunk PHẢI được gán Primary Key khác nhau:
        - Chunk 0: Key1 thử trước
        - Chunk 1: Key2 thử trước
        - Chunk 2: Key3 thử trước
        """
        keys_used_per_call = []

        async def fake_call_gemini(prompt, api_keys, system_instruction=None, thinking_budget=0):
            # Ghi lại key đầu tiên (primary key) được truyền vào call_gemini cho chunk này
            keys_used_per_call.append(api_keys[0])
            # Trả về kết quả JSON giả lập câu hỏi
            mock_resp = MagicMock()
            mock_resp.text = json.dumps([
                {
                    "question_number": 1,
                    "type": "mcq",
                    "question": f"Câu hỏi xử lý bởi key {api_keys[0]}",
                    "options": ["A. Đúng", "B. Sai", "C. Khác", "D. Không rõ"],
                    "correct_answer": "A. Đúng",
                    "explain": "Lời giải mẫu"
                }
            ])
            return mock_resp

        mock_call.side_effect = fake_call_gemini

        keys = ["KeyA_1111", "KeyB_2222", "KeyC_3333"]
        result = await generate_mcq_with_gemini(self.sample_30_questions_text, api_keys=keys)

        # 30 câu với 3 keys sẽ chia thành 3 chunks (mỗi chunk 10 câu)
        self.assertEqual(len(keys_used_per_call), 3)
        self.assertEqual(keys_used_per_call, ["KeyA_1111", "KeyB_2222", "KeyC_3333"])
        self.assertEqual(len(result), 3)

    @patch("services.ai_service.call_gemini_with_fallback")
    async def test_failover_when_primary_key_fails(self, mock_call):
        """
        Kiểm tra cơ chế dự phòng (Failover):
        Khi KeyB bị lỗi 429 ở chunk 1, call_gemini_with_fallback xoay sang KeyC/KeyA và hoàn thành thành công.
        """
        async def fake_call_gemini_with_failover(prompt, api_keys, system_instruction=None, thinking_budget=0):
            # Nếu key đầu tiên là KeyB_Fail, mô phỏng việc key này đã chết và luân chuyển sang key kế tiếp
            chosen_key = api_keys[0]
            if chosen_key == "KeyB_Fail":
                # Fallback sang key thứ 2 trong danh sách
                chosen_key = api_keys[1]

            mock_resp = MagicMock()
            mock_resp.text = json.dumps([
                {
                    "question_number": 1,
                    "type": "mcq",
                    "question": f"Được cứu bởi key {chosen_key}",
                    "options": ["A. 1", "B. 2", "C. 3", "D. 4"],
                    "correct_answer": "A. 1",
                    "explain": "OK"
                }
            ])
            return mock_resp

        mock_call.side_effect = fake_call_gemini_with_failover

        keys = ["KeyA_OK", "KeyB_Fail", "KeyC_OK"]
        result = await generate_mcq_with_gemini(self.sample_30_questions_text, api_keys=keys)

        self.assertEqual(len(result), 3)
        # Kết quả của chunk 1 phải được phục hồi bằng KeyC_OK (fallback)
        self.assertIn("KeyC_OK", result[1]["question"])

    @patch("services.ai_service.call_gemini_with_fallback")
    async def test_order_preservation_when_chunks_finish_out_of_order(self, mock_call):
        """
        Kiểm tra Map-Reduce ráp đúng thứ tự đề thi:
        Dù Chunk 2 kết thúc siêu nhanh (0.01s), Chunk 0 kết thúc chậm nhất (0.05s),
        thì danh sách ráp lại CUỐI CÙNG VẪN PHẢI THEO THỨ TỰ: Chunk 0 -> Chunk 1 -> Chunk 2.
        """
        async def delayed_call(prompt, api_keys, system_instruction=None, thinking_budget=0):
            # Nhận diện chunk dựa vào primary key
            p_key = api_keys[0]
            if p_key == "Key1":
                # Chunk 0 kết thúc muộn nhất
                await asyncio.sleep(0.06)
                q_num = 1
            elif p_key == "Key2":
                # Chunk 1 kết thúc vừa
                await asyncio.sleep(0.03)
                q_num = 11
            else:
                # Chunk 2 kết thúc sớm nhất
                await asyncio.sleep(0.005)
                q_num = 21

            mock_resp = MagicMock()
            mock_resp.text = json.dumps([
                {
                    "question_number": q_num,
                    "type": "mcq",
                    "question": f"Nội dung bắt đầu từ câu {q_num}",
                    "options": ["A. Đáp án", "B. Sai", "C. Sai", "D. Sai"],
                    "correct_answer": "A. Đáp án",
                    "explain": "Chi tiết"
                }
            ])
            return mock_resp

        mock_call.side_effect = delayed_call

        keys = ["Key1", "Key2", "Key3"]
        result = await generate_mcq_with_gemini(self.sample_30_questions_text, api_keys=keys)

        self.assertEqual(len(result), 3)
        # Kiểm tra thứ tự nghiêm ngặt: Câu 1 -> Câu 11 -> Câu 21
        self.assertEqual(result[0]["question_number"], 1)
        self.assertEqual(result[1]["question_number"], 11)
        self.assertEqual(result[2]["question_number"], 21)

    @patch("services.ai_service.call_gemini_with_fallback")
    async def test_cross_check_answers_multi_key_batching(self, mock_call):
        """Kiểm tra cross_check_answers tự động chia batch và chạy song song trên nhiều key."""
        # Giả lập 20 câu hỏi (vượt qua batch_size 15, tạo thành 2 batch)
        quiz_data = [
            {
                "question_number": i,
                "type": "mcq",
                "question": f"Câu {i}",
                "options": ["A. Đúng", "B. Sai"],
                "correct_answer": "A. Đúng"
            }
            for i in range(20)
        ]

        keys_used = []

        async def fake_cross_check(prompt, api_keys, system_instruction=None, thinking_budget=0):
            keys_used.append(api_keys[0])
            # Trích xuất các index trong prompt để trả về kết quả
            mock_resp = MagicMock()
            # Trả về kết quả giải trùng khớp
            mock_resp.text = json.dumps([
                {"index": i, "ai_solved_answer": "A. Đúng", "explain": "Chính xác"}
                for i in range(20)
            ])
            return mock_resp

        mock_call.side_effect = fake_cross_check

        keys = ["KeyA", "KeyB"]
        res = await cross_check_answers(quiz_data, api_keys=keys)

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["total_checked"], 20)
        self.assertEqual(res["mismatches_found"], 0)
        self.assertIn("quiz_data", res)
        self.assertIn("data", res)
        # Vì có 20 câu và batch_size = 15 -> có 2 batch
        self.assertEqual(len(keys_used), 2)
        self.assertEqual(keys_used, ["KeyA", "KeyB"])

    @patch("services.ai_service.call_gemini_with_fallback")
    async def test_cross_check_answers_detects_mismatch_and_sets_warning(self, mock_call):
        """Kiểm tra cross_check_answers phát hiện chính xác câu lệch đáp án và gán cờ cảnh báo."""
        quiz_data = [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Câu 1: Thủ đô của Việt Nam là gì?",
                "options": ["A. Hà Nội", "B. TP.HCM"],
                "correct_answer": "B. TP.HCM"  # Giáo viên chọn sai
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Câu 2: 1 + 1 = ?",
                "options": ["A. 2", "B. 3"],
                "correct_answer": "A. 2"  # Giáo viên chọn đúng
            },
            {
                "question_number": 3,
                "type": "true_false",
                "question": "Câu 3: Chọn đúng sai",
                "options": ["a) Ý 1", "b) Ý 2"],
                "correct_answer": {"a": True, "b": False}  # Giáo viên chọn
            },
            {
                "question_number": 4,
                "type": "short_answer",
                "question": "Câu 4: Tính nghiệm x",
                "options": [],
                "correct_answer": "15,5"  # Dùng dấu phẩy
            }
        ]

        async def fake_cross_check(prompt, api_keys, system_instruction=None, thinking_budget=0):
            mock_resp = MagicMock()
            # AI giải: Câu 0 ra A (lệch), Câu 1 ra A (khớp), Câu 2 ý a ra False (lệch), Câu 3 ra 15.5 (khớp)
            mock_resp.text = json.dumps([
                {"index": 0, "ai_solved_answer": "A. Hà Nội", "explain": "Hà Nội là thủ đô"},
                {"index": 1, "ai_solved_answer": "A. 2", "explain": "1+1=2"},
                {"index": 2, "ai_solved_answer": {"a": False, "b": False}, "explain": "Ý a sai"},
                {"index": 3, "ai_solved_answer": "15.5", "explain": "x = 15.5"}
            ])
            return mock_resp

        mock_call.side_effect = fake_cross_check

        res = await cross_check_answers(quiz_data, api_keys=["KeyA"])

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["total_checked"], 4)
        self.assertEqual(res["mismatches_found"], 2)
        self.assertEqual(res["mismatch_count"], 2)

        # Kiểm tra quiz_data trả về
        checked_quiz = res["quiz_data"]
        # Câu 1 (index 0): Lệch đáp án -> has_cross_check_warning = True
        self.assertTrue(checked_quiz[0]["has_cross_check_warning"])
        self.assertIsNotNone(checked_quiz[0]["cross_check_info"])
        self.assertEqual(checked_quiz[0]["cross_check_info"]["ai_answer"], "A. Hà Nội")

        # Câu 2 (index 1): Trùng khớp -> has_cross_check_warning = False
        self.assertFalse(checked_quiz[1]["has_cross_check_warning"])
        self.assertIsNone(checked_quiz[1]["cross_check_info"])

        # Câu 3 (index 2): Lệch đúng/sai -> has_cross_check_warning = True
        self.assertTrue(checked_quiz[2]["has_cross_check_warning"])

        # Câu 4 (index 3): 15,5 vs 15.5 -> Trùng khớp -> has_cross_check_warning = False
        self.assertFalse(checked_quiz[3]["has_cross_check_warning"])


if __name__ == "__main__":
    unittest.main()
