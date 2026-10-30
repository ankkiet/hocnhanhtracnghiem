"""
Bộ kiểm thử hồi quy và Benchmark Parser tự động (Automated Regression Test Suite).
Tích hợp với CI/CD qua: python -m unittest tests/test_parser_benchmark.py

Đảm bảo:
1. Mọi lần thay đổi code parser đều được kiểm tra trên toàn bộ 40 files mẫu thực tế.
2. Ngăn ngừa mọi lỗi hồi quy (regression) làm hỏng các trường hợp cũ.
3. Đạt tỷ lệ bóc tách chính xác trên 95% (toàn diện: câu hỏi, phương án, đáp án, GDPT 2018).
"""

import json
import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from tests.benchmark.evaluator import run_benchmark_suite


class TestParserBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest_path = os.path.join(BASE_DIR, "tests", "benchmark", "manifest.json")
        cls.baseline_path = os.path.join(BASE_DIR, "tests", "benchmark", "baseline.json")
        cls.dataset_dir = os.path.join(BASE_DIR, "tests", "benchmark", "dataset")

        # Đọc manifest
        with open(cls.manifest_path, "r", encoding="utf-8") as f:
            cls.manifest = json.load(f)

        # Chạy toàn bộ benchmark suite
        cls.suite_result = run_benchmark_suite(
            manifest_path=cls.manifest_path,
            baseline_path=cls.baseline_path
        )

    def test_dataset_integrity(self):
        """Kiểm tra tính toàn vẹn của dataset: đủ 40 files và 40 ground truth JSON."""
        total_files = self.manifest.get("total_files", 0)
        self.assertGreaterEqual(total_files, 30, f"Dataset cần ít nhất 30 files, hiện có {total_files}")
        self.assertEqual(len(self.suite_result.file_results), total_files)

        for item in self.manifest.get("files", []):
            fmt = item["format_type"]
            folder = "docx" if fmt == "docx" else "pdf"
            f_path = os.path.join(self.dataset_dir, folder, item["file_name"])
            gt_path = os.path.join(self.dataset_dir, "ground_truth", f"{item['file_id']}.json")
            self.assertTrue(os.path.exists(f_path), f"Thiếu file dữ liệu: {f_path}")
            self.assertTrue(os.path.exists(gt_path), f"Thiếu file ground truth: {gt_path}")

    def test_benchmark_overall_accuracy_above_threshold(self):
        """Kiểm tra độ chính xác trung bình toàn bộ dataset phải >= 95%."""
        avg_acc = self.suite_result.average_accuracy
        self.assertGreaterEqual(
            avg_acc, 95.0,
            f"Độ chính xác trung bình ({avg_acc}%) không đạt ngưỡng chuẩn 95.0%"
        )

    def test_benchmark_answer_accuracy_high(self):
        """Kiểm tra tỷ lệ bóc tách đúng đáp án của parser phải >= 95%."""
        ans_acc = self.suite_result.average_answer_accuracy
        self.assertGreaterEqual(
            ans_acc, 95.0,
            f"Tỷ lệ bóc tách đúng đáp án ({ans_acc}%) không đạt ngưỡng chuẩn 95.0%"
        )

    def test_benchmark_options_accuracy_perfect(self):
        """Kiểm tra tỷ lệ bóc tách đầy đủ các phương án (A,B,C,D / a,b,c,d) đạt 100%."""
        opts_acc = self.suite_result.average_options_accuracy
        self.assertEqual(
            opts_acc, 100.0,
            f"Tỷ lệ bóc tách phương án ({opts_acc}%) bị thiếu hoặc sai lệch."
        )

    def test_no_regressions_against_baseline(self):
        """
        KIỂM TRA HỒI QUY: Đảm bảo không có bất kỳ file nào bị giảm điểm so với baseline cũ.
        Mỗi lần sửa parser, test này lập tức phát hiện trường hợp cũ bị hỏng!
        """
        regressions = self.suite_result.regressions
        if regressions:
            error_msg = f"Phát hiện {len(regressions)} trường hợp bị hồi quy so với Baseline:\n"
            for r in regressions:
                error_msg += f" - {r['file_name']} ({r['subject']}): {r['baseline_score']}% -> {r['current_score']}%\n"
                for err in r.get("errors", []):
                    error_msg += f"    * {err}\n"
            self.fail(error_msg)

    def test_gdpt_2018_multi_part_parsing(self):
        """Kiểm tra đề thi chuẩn GDPT 2018: bóc tách chính xác cả 3 phần (MCQ, Đúng/Sai, Trả lời ngắn)."""
        gdpt_results = [r for r in self.suite_result.file_results if r.style == "gdpt_2018"]
        self.assertGreaterEqual(len(gdpt_results), 6, "Cần ít nhất 6 bài kiểm tra GDPT 2018.")
        for r in gdpt_results:
            self.assertGreaterEqual(
                r.overall_accuracy, 90.0,
                f"Đề GDPT 2018 {r.file_name} đạt {r.overall_accuracy}%, dưới ngưỡng 90%."
            )

    def test_pdf_parsing_accuracy(self):
        """Kiểm tra khả năng bóc tách các file PDF nội bộ (PyMuPDF) đạt chuẩn cao."""
        pdf_results = [r for r in self.suite_result.file_results if r.file_name.endswith('.pdf')]
        self.assertGreaterEqual(len(pdf_results), 10, "Cần ít nhất 10 bài kiểm tra PDF.")
        avg_pdf = sum(r.overall_accuracy for r in pdf_results) / len(pdf_results)
        self.assertGreaterEqual(
            avg_pdf, 95.0,
            f"Độ chính xác trung bình của PDF ({avg_pdf:.1f}%) không đạt ngưỡng 95.0%"
        )


if __name__ == "__main__":
    unittest.main()
