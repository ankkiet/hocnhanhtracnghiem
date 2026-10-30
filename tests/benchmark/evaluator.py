"""
Bộ đánh giá độ chính xác của Parser (Benchmark Evaluator) - HocNhanhTN.
Chức năng:
1. Chạy bóc tách tài liệu cục bộ (DOCX và PDF) qua đúng pipeline xử lý của hệ thống.
2. So khớp từng câu hỏi với Ground Truth chuẩn:
   - Tỷ lệ nhận diện câu hỏi (Question Detection Rate)
   - Tỷ lệ bóc tách đúng các phương án (Option Extraction Accuracy)
   - Tỷ lệ nhận diện đúng đáp án (Answer Key Accuracy)
   - Tỷ lệ giữ nguyên nội dung/lời giải (Stem & Explanation Accuracy)
3. Tính toán độ chính xác tổng hợp (Overall Benchmark Score).
4. So sánh với Baseline để phát hiện lỗi hồi quy (Regression Detection).
"""

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.answer_key_extractor import (
    align_mcq_correct_answer,
    extract_answer_key_from_doc,
    reconcile_quiz_with_answer_key,
)
from core.docx_parser import (
    extract_formatting_from_docx,
    parse_docx_to_marked_text,
    recursive_unescape,
    split_merged_options,
)
from core.pdf_parser import extract_questions_from_pdf_locally
from core.text_parser import extract_questions_from_text_bulletproof
from services.ai_service import normalize_question_data


def parse_document_for_benchmark(file_path: str) -> List[Dict[str, Any]]:
    """
    Chạy pipeline bóc tách chuẩn xác cục bộ của HocNhanhTN trên tệp DOCX hoặc PDF.
    Không gọi qua API AI bên ngoài nhằm đảm bảo tốc độ và tính tất định (deterministic).
    """
    if not os.path.exists(file_path):
        return []

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".docx":
        file_ak = None
        try:
            file_ak = extract_answer_key_from_doc(file_path)
        except Exception:
            file_ak = None

        marked_text = ""
        image_mapping = {}
        extracted_data = None

        try:
            marked_text, image_mapping = parse_docx_to_marked_text(file_path)
            extracted_data = extract_questions_from_text_bulletproof(marked_text, image_mapping)
        except Exception:
            extracted_data = None

        # Fallback Engine 2
        if not extracted_data or len(extracted_data) == 0:
            try:
                extracted_data = extract_formatting_from_docx(file_path)
            except Exception:
                extracted_data = None

        extracted_data = recursive_unescape(extracted_data)

        if extracted_data and isinstance(extracted_data, list):
            if file_ak:
                extracted_data = reconcile_quiz_with_answer_key(extracted_data, file_ak)
            extracted_data = [normalize_question_data(q) for q in extracted_data if isinstance(q, dict)]
            for q in extracted_data:
                if isinstance(q, dict) and q.get("type", "mcq") == "mcq" and q.get("options"):
                    q["options"] = split_merged_options(q["options"])
                    if q.get("correct_answer"):
                        q["correct_answer"] = align_mcq_correct_answer(q["correct_answer"], q["options"])
        return extracted_data or []

    elif ext == ".pdf":
        extracted_data = extract_questions_from_pdf_locally(file_path)
        extracted_data = recursive_unescape(extracted_data)
        if extracted_data and isinstance(extracted_data, list):
            extracted_data = [normalize_question_data(q) for q in extracted_data if isinstance(q, dict)]
            for q in extracted_data:
                if isinstance(q, dict) and q.get("type", "mcq") == "mcq" and q.get("options"):
                    q["options"] = split_merged_options(q["options"])
                    if q.get("correct_answer"):
                        q["correct_answer"] = align_mcq_correct_answer(q["correct_answer"], q["options"])
        return extracted_data or []

    return []


def normalize_text_for_comparison(text: str) -> str:
    """Loại bỏ khoảng trắng thừa, thẻ HTML, dấu câu để so sánh nội dung câu hỏi."""
    if not text:
        return ""
    t = str(text)
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace('\xa0', ' ').replace('\u202f', ' ').replace('\ufeff', '')
    t = re.sub(r'^(?:Câu|Bài|Question|Q|\d+[\.\:\)])\s*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+', ' ', t).strip().lower()
    t = re.sub(r'[\.\:\,\;\!\?\'\"\`\(\)\[\]]', '', t)
    return t


def extract_answer_char(ans: Any) -> str:
    """Rút trích ký tự phương án (A, B, C, D) từ chuỗi đáp án."""
    if not ans:
        return ""
    if isinstance(ans, str):
        ans_clean = ans.strip().upper()
        m = re.match(r'^[\(\[]?\*?([A-F])[\.\:\)\s]?', ans_clean)
        if m:
            return m.group(1)
        m2 = re.search(r'\b([A-F])\b', ans_clean)
        if m2 and len(ans_clean) <= 5:
            return m2.group(1)
    return ""


def compare_answers(parsed_ans: Any, expected_ans: Any, q_type: str = "mcq") -> bool:
    """So khớp đáp án giữa kết quả bóc tách và Ground Truth."""
    if parsed_ans is None or expected_ans is None:
        return parsed_ans == expected_ans

    if q_type == "mcq":
        p_char = extract_answer_char(parsed_ans)
        e_char = extract_answer_char(expected_ans)
        if p_char and e_char:
            return p_char == e_char
        # So sánh chuỗi đã làm sạch
        return normalize_text_for_comparison(str(parsed_ans)) == normalize_text_for_comparison(str(expected_ans))

    elif q_type == "true_false":
        if isinstance(parsed_ans, dict) and isinstance(expected_ans, dict):
            # So khớp 4 ý a, b, c, d
            for key in ["a", "b", "c", "d"]:
                if key in expected_ans:
                    p_val = bool(parsed_ans.get(key))
                    e_val = bool(expected_ans.get(key))
                    if p_val != e_val:
                        return False
            return True
        return str(parsed_ans).strip().lower() == str(expected_ans).strip().lower()

    elif q_type == "short_answer":
        p_str = str(parsed_ans).replace(',', '.').strip().lower()
        e_str = str(expected_ans).replace(',', '.').strip().lower()
        p_str = re.sub(r'^(?:đáp án|đáp số|đs|kết quả)\s*[\:\-\=]?\s*', '', p_str)
        e_str = re.sub(r'^(?:đáp án|đáp số|đs|kết quả)\s*[\:\-\=]?\s*', '', e_str)
        try:
            return abs(float(p_str) - float(e_str)) < 1e-4
        except ValueError:
            return p_str == e_str

    return str(parsed_ans).strip().lower() == str(expected_ans).strip().lower()


class QuestionEvalResult:
    def __init__(self, q_num: int, is_detected: bool, type_match: bool, options_match: bool, answer_match: bool, stem_match: bool, explain_match: bool, details: str = ""):
        self.q_num = q_num
        self.is_detected = is_detected
        self.type_match = type_match
        self.options_match = options_match
        self.answer_match = answer_match
        self.stem_match = stem_match
        self.explain_match = explain_match
        self.details = details


class FileBenchmarkResult:
    def __init__(self, file_id: str, file_name: str, subject: str, style: str, total_expected: int):
        self.file_id = file_id
        self.file_name = file_name
        self.subject = subject
        self.style = style
        self.total_expected = total_expected
        self.total_parsed = 0
        self.question_results: List[QuestionEvalResult] = []
        self.errors: List[str] = []

    @property
    def question_count_accuracy(self) -> float:
        if self.total_expected == 0:
            return 1.0 if self.total_parsed == 0 else 0.0
        return max(0.0, 1.0 - abs(self.total_parsed - self.total_expected) / self.total_expected)

    @property
    def options_accuracy(self) -> float:
        if not self.question_results:
            return 0.0
        matches = sum(1 for r in self.question_results if r.options_match)
        return matches / self.total_expected

    @property
    def answer_accuracy(self) -> float:
        if not self.question_results:
            return 0.0
        matches = sum(1 for r in self.question_results if r.answer_match)
        return matches / self.total_expected

    @property
    def stem_accuracy(self) -> float:
        if not self.question_results:
            return 0.0
        matches = sum(1 for r in self.question_results if r.stem_match)
        return matches / self.total_expected

    @property
    def overall_accuracy(self) -> float:
        # Trọng số: 30% Số lượng câu hỏi + 30% Phương án + 30% Đáp án đúng + 10% Thân câu hỏi
        return round(
            (0.30 * self.question_count_accuracy +
             0.30 * self.options_accuracy +
             0.30 * self.answer_accuracy +
             0.10 * self.stem_accuracy) * 100, 2
        )

    @property
    def is_passed(self) -> bool:
        return self.overall_accuracy >= 90.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "subject": self.subject,
            "style": self.style,
            "total_expected": self.total_expected,
            "total_parsed": self.total_parsed,
            "question_count_accuracy": round(self.question_count_accuracy * 100, 2),
            "options_accuracy": round(self.options_accuracy * 100, 2),
            "answer_accuracy": round(self.answer_accuracy * 100, 2),
            "stem_accuracy": round(self.stem_accuracy * 100, 2),
            "overall_accuracy": self.overall_accuracy,
            "is_passed": self.is_passed,
            "errors": self.errors
        }


def evaluate_file(file_path: str, gt_path: str) -> FileBenchmarkResult:
    """Đánh giá chi tiết 1 tệp so với Ground Truth."""
    with open(gt_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    file_id = gt_data["file_id"]
    file_name = gt_data["file_name"]
    subject = gt_data["subject"]
    style = gt_data.get("style", "")
    gt_questions = gt_data.get("questions", [])

    result = FileBenchmarkResult(file_id, file_name, subject, style, len(gt_questions))

    parsed_questions = parse_document_for_benchmark(file_path)
    result.total_parsed = len(parsed_questions)

    if not parsed_questions:
        result.errors.append("Parser không bóc tách được câu hỏi nào từ file.")
        return result

    # Ghép câu hỏi đã bóc tách với câu hỏi kỳ vọng
    for idx, expected_q in enumerate(gt_questions):
        q_num = expected_q.get("question_number", idx + 1)
        expected_type = expected_q.get("type", "mcq")
        expected_ca = expected_q.get("correct_answer")
        expected_opts = expected_q.get("options", [])
        expected_stem = expected_q.get("question", "")

        matched_parsed = None
        # Ưu tiên tìm câu hỏi trùng số thứ tự (và trùng part nếu có)
        exp_part = expected_q.get("part")
        for pq in parsed_questions:
            if exp_part is not None:
                if pq.get("question_number") == q_num and pq.get("part") == exp_part:
                    matched_parsed = pq
                    break
            elif pq.get("question_number") == q_num:
                matched_parsed = pq
                break

        # Nếu không thấy theo số thứ tự, thử lấy theo index
        if not matched_parsed and idx < len(parsed_questions):
            matched_parsed = parsed_questions[idx]

        if not matched_parsed:
            result.question_results.append(QuestionEvalResult(
                q_num=q_num, is_detected=False, type_match=False,
                options_match=False, answer_match=False, stem_match=False,
                explain_match=False, details=f"Thiếu câu {q_num}"
            ))
            result.errors.append(f"Câu {q_num}: Không tìm thấy câu hỏi trong kết quả parser.")
            continue

        # 1. So khớp loại câu hỏi
        parsed_type = matched_parsed.get("type", "mcq")
        type_match = (parsed_type == expected_type)

        # 2. So khớp thân câu hỏi (stem)
        parsed_stem = matched_parsed.get("question", "")
        norm_p = normalize_text_for_comparison(parsed_stem)
        norm_e = normalize_text_for_comparison(expected_stem)
        # Khớp nếu tương đồng hoặc một bên là chuỗi con của bên kia
        stem_match = bool(norm_p and norm_e and (norm_p in norm_e or norm_e in norm_p or norm_p == norm_e))

        # 3. So khớp phương án (options)
        parsed_opts = matched_parsed.get("options", [])
        options_match = False
        if expected_type == "mcq":
            options_match = (len(parsed_opts) == len(expected_opts) and len(parsed_opts) >= 4)
        elif expected_type == "true_false":
            options_match = (len(parsed_opts) == len(expected_opts) or len(parsed_opts) >= 4)
        elif expected_type == "short_answer":
            options_match = True

        # 4. So khớp đáp án đúng (correct_answer)
        parsed_ca = matched_parsed.get("correct_answer")
        answer_match = compare_answers(parsed_ca, expected_ca, expected_type)

        # 5. So khớp lời giải
        exp_expected = expected_q.get("explain", "")
        exp_parsed = matched_parsed.get("explain", "")
        explain_match = True
        if exp_expected:
            explain_match = bool(exp_parsed and len(exp_parsed.strip()) > 5)

        details = ""
        if not answer_match:
            details = f"Sai đáp án (Kỳ vọng: {expected_ca} | Bóc tách: {parsed_ca})"
            result.errors.append(f"Câu {q_num}: {details}")
        elif not options_match:
            details = f"Số lượng phương án chưa đúng ({len(parsed_opts)}/{len(expected_opts)})"
            result.errors.append(f"Câu {q_num}: {details}")

        result.question_results.append(QuestionEvalResult(
            q_num=q_num,
            is_detected=True,
            type_match=type_match,
            options_match=options_match,
            answer_match=answer_match,
            stem_match=stem_match,
            explain_match=explain_match,
            details=details
        ))

    return result


class BenchmarkSuiteResult:
    def __init__(self):
        self.file_results: List[FileBenchmarkResult] = []
        self.regressions: List[Dict[str, Any]] = []

    @property
    def total_files(self) -> int:
        return len(self.file_results)

    @property
    def passed_files(self) -> int:
        return sum(1 for r in self.file_results if r.is_passed)

    @property
    def total_expected_questions(self) -> int:
        return sum(r.total_expected for r in self.file_results)

    @property
    def total_parsed_questions(self) -> int:
        return sum(r.total_parsed for r in self.file_results)

    @property
    def average_accuracy(self) -> float:
        if not self.file_results:
            return 0.0
        return round(sum(r.overall_accuracy for r in self.file_results) / len(self.file_results), 2)

    @property
    def average_answer_accuracy(self) -> float:
        if not self.file_results:
            return 0.0
        return round(sum(r.answer_accuracy for r in self.file_results) / len(self.file_results) * 100, 2)

    @property
    def average_options_accuracy(self) -> float:
        if not self.file_results:
            return 0.0
        return round(sum(r.options_accuracy for r in self.file_results) / len(self.file_results) * 100, 2)

    def get_subject_breakdown(self) -> Dict[str, Dict[str, Any]]:
        breakdown = {}
        for r in self.file_results:
            sub = r.subject
            if sub not in breakdown:
                breakdown[sub] = {"total_files": 0, "passed_files": 0, "scores": [], "ans_scores": []}
            breakdown[sub]["total_files"] += 1
            if r.is_passed:
                breakdown[sub]["passed_files"] += 1
            breakdown[sub]["scores"].append(r.overall_accuracy)
            breakdown[sub]["ans_scores"].append(r.answer_accuracy * 100)

        for sub, data in breakdown.items():
            data["avg_score"] = round(sum(data["scores"]) / len(data["scores"]), 2)
            data["avg_ans_score"] = round(sum(data["ans_scores"]) / len(data["ans_scores"]), 2)
        return breakdown

    def get_style_breakdown(self) -> Dict[str, Dict[str, Any]]:
        breakdown = {}
        for r in self.file_results:
            st = r.style or "standard"
            if st not in breakdown:
                breakdown[st] = {"total_files": 0, "passed_files": 0, "scores": []}
            breakdown[st]["total_files"] += 1
            if r.is_passed:
                breakdown[st]["passed_files"] += 1
            breakdown[st]["scores"].append(r.overall_accuracy)

        for st, data in breakdown.items():
            data["avg_score"] = round(sum(data["scores"]) / len(data["scores"]), 2)
        return breakdown


def run_benchmark_suite(
    manifest_path: Optional[str] = None,
    filter_subject: Optional[str] = None,
    filter_format: Optional[str] = None,
    filter_file: Optional[str] = None,
    baseline_path: Optional[str] = None
) -> BenchmarkSuiteResult:
    """Chạy toàn bộ hoặc một phần bộ Benchmark Suite và kiểm tra hồi quy."""
    if not manifest_path:
        manifest_path = os.path.join(BASE_DIR, "tests", "benchmark", "manifest.json")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    dataset_dir = os.path.join(os.path.dirname(manifest_path), "dataset")
    suite_result = BenchmarkSuiteResult()

    baseline_data = {}
    if baseline_path and os.path.exists(baseline_path):
        try:
            with open(baseline_path, "r", encoding="utf-8") as bf:
                baseline_data = json.load(bf).get("files", {})
        except Exception:
            baseline_data = {}

    for item in manifest.get("files", []):
        file_id = item["file_id"]
        file_name = item["file_name"]
        fmt = item["format_type"]
        sub = item["subject"]

        if filter_subject and filter_subject.lower() not in sub.lower():
            continue
        if filter_format and filter_format.lower() != fmt.lower():
            continue
        if filter_file and filter_file not in [file_id, file_name]:
            continue

        file_folder = "docx" if fmt == "docx" else "pdf"
        file_path = os.path.join(dataset_dir, file_folder, file_name)
        gt_path = os.path.join(dataset_dir, "ground_truth", f"{file_id}.json")

        if not os.path.exists(file_path) or not os.path.exists(gt_path):
            continue

        file_res = evaluate_file(file_path, gt_path)
        suite_result.file_results.append(file_res)

        # Kiểm tra hồi quy so với Baseline
        if file_id in baseline_data:
            base_score = baseline_data[file_id].get("overall_accuracy", 0.0)
            if file_res.overall_accuracy < base_score - 1.0:  # Giảm hơn 1% là hồi quy
                suite_result.regressions.append({
                    "file_id": file_id,
                    "file_name": file_name,
                    "subject": sub,
                    "baseline_score": base_score,
                    "current_score": file_res.overall_accuracy,
                    "diff": round(file_res.overall_accuracy - base_score, 2),
                    "errors": file_res.errors
                })

    return suite_result
