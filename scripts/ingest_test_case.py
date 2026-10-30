"""
Công cụ Nạp tự động File đề thi mới vào Bộ Benchmark (Auto Test-Case Ingestion Tool).

Cách sử dụng:
  python scripts/ingest_test_case.py --file "duong/dan/de_thi_cua_giao_vien.docx" --subject "Toán học"
  python scripts/ingest_test_case.py --file "duong/dan/de_thi_la.pdf" --subject "Vật lý" --style "bottom_text"

Quy trình tự động thực hiện:
1. Sao chép file vào thư mục dataset chuẩn (tests/benchmark/dataset/docx hoặc pdf).
2. Tự động trích xuất cấu trúc câu hỏi, phương án, đáp án và lời giải.
3. Tự động sinh tệp Ground Truth JSON (tests/benchmark/dataset/ground_truth/<id>.json).
4. Tự động cập nhật vào manifest.json.
5. Chạy đánh giá tức thì và hiển thị bảng chấm điểm cho file mới.
"""

import argparse
import json
import os
import re
import shutil
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from tests.benchmark.evaluator import evaluate_file, parse_document_for_benchmark


def slugify(text: str) -> str:
    """Tạo slug an toàn từ tên tệp."""
    t = text.lower()
    t = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', t)
    t = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', t)
    t = re.sub(r'[ìíịỉĩ]', 'i', t)
    t = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', t)
    t = re.sub(r'[ùúụủũưừứựửữ]', 'u', t)
    t = re.sub(r'[ỳýỵỷỹ]', 'y', t)
    t = re.sub(r'[đ]', 'd', t)
    t = re.sub(r'[^a-z0-9]+', '_', t)
    return t.strip('_')


def ingest_file(
    source_file_path: str,
    subject: str = "Chưa phân loại",
    style: str = "standard",
    description: str = "",
    tags: list = None
):
    if not os.path.exists(source_file_path):
        print(f"[LỖI] Không tìm thấy file nguồn: {source_file_path}")
        return False

    raw_name = os.path.basename(source_file_path)
    base_name, ext = os.path.splitext(raw_name)
    ext = ext.lower()

    if ext not in [".docx", ".pdf"]:
        print(f"[LỖI] Định dạng file không được hỗ trợ ({ext}). Chỉ hỗ trợ .docx và .pdf.")
        return False

    fmt = "docx" if ext == ".docx" else "pdf"
    clean_name = f"{slugify(base_name)}{ext}"
    file_id = f"{fmt}_{slugify(base_name)}"

    dataset_dir = os.path.join(BASE_DIR, "tests", "benchmark", "dataset")
    target_folder = os.path.join(dataset_dir, fmt)
    target_file_path = os.path.join(target_folder, clean_name)
    gt_dir = os.path.join(dataset_dir, "ground_truth")
    gt_path = os.path.join(gt_dir, f"{file_id}.json")
    manifest_path = os.path.join(BASE_DIR, "tests", "benchmark", "manifest.json")

    print(f"[*] Bắt đầu nạp tự động file: {raw_name}")
    print(f"    - ID: {file_id}")
    print(f"    - Định dạng: {fmt.upper()}")
    print(f"    - Môn học: {subject}")

    # 1. Copy file vào dataset
    os.makedirs(target_folder, exist_ok=True)
    os.makedirs(gt_dir, exist_ok=True)
    shutil.copy2(source_file_path, target_file_path)
    print(f"  [1/4] Đã lưu file vào: {target_file_path}")

    # 2. Bóc tách tự động
    print("  [2/4] Đang chạy bóc tách qua Parser để sinh khung Ground Truth...")
    parsed_questions = parse_document_for_benchmark(target_file_path)

    if not parsed_questions:
        print("  [CẢNH BÁO] Parser hiện tại chưa nhận diện được câu hỏi nào từ file này.")
        print("             Hệ thống sẽ tạo file Ground Truth rỗng để bạn điền đáp án chuẩn vào.")
        gt_questions = []
    else:
        print(f"  [OK] Parser bóc tách được {len(parsed_questions)} câu hỏi ban đầu.")
        gt_questions = []
        for q in parsed_questions:
            gt_questions.append({
                "question_number": q.get("question_number", 1),
                "part": q.get("part", 1),
                "type": q.get("type", "mcq"),
                "group_title": q.get("group_title", ""),
                "question": q.get("question", ""),
                "options": q.get("options", []),
                "correct_answer": q.get("correct_answer", ""),
                "explain": q.get("explain", "")
            })

    # 3. Tạo file Ground Truth JSON
    gt_data = {
        "file_id": file_id,
        "file_name": clean_name,
        "format_type": fmt,
        "subject": subject,
        "style": style,
        "style_description": description or f"Đề thi thật nạp tự động từ giáo viên ({raw_name})",
        "tags": tags or [slugify(subject), fmt],
        "total_questions": len(gt_questions),
        "questions": gt_questions
    }

    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(gt_data, f, ensure_ascii=False, indent=2)
    print(f"  [3/4] Đã tạo file Ground Truth: {gt_path}")

    # 4. Cập nhật manifest.json
    manifest = {"files": []}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                manifest = json.load(mf)
        except Exception:
            manifest = {"files": []}

    # Xóa mục cũ nếu trùng ID
    manifest["files"] = [f for f in manifest.get("files", []) if f.get("file_id") != file_id]
    manifest["files"].append({
        "file_id": file_id,
        "file_name": clean_name,
        "format_type": fmt,
        "subject": subject,
        "style": style,
        "style_description": gt_data["style_description"],
        "tags": gt_data["tags"],
        "total_questions": len(gt_questions)
    })
    manifest["total_files"] = len(manifest["files"])
    manifest["total_questions"] = sum(f.get("total_questions", 0) for f in manifest["files"])

    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, ensure_ascii=False, indent=2)
    print(f"  [4/4] Đã cập nhật vào: {manifest_path}")

    # 5. Chạy đánh giá tức thì
    print("-" * 70)
    print("  KẾT QUẢ ĐÁNH GIÁ TỨC THÌ (EVALUATION PREVIEW):")
    res = evaluate_file(target_file_path, gt_path)
    print(f"  * Số câu nhận diện: {res.total_parsed} / {res.total_expected}")
    print(f"  * Độ chính xác phương án: {res.options_accuracy * 100:.1f}%")
    print(f"  * Độ chính xác đáp án:   {res.answer_accuracy * 100:.1f}%")
    print(f"  * Tổng điểm bóc tách:    {res.overall_accuracy}%")
    if res.errors:
        print("  * Các điểm cần chú ý / điều chỉnh:")
        for err in res.errors[:3]:
            print(f"    - {err}")
    print("-" * 70)
    print(f"[HOÀN TẤT] File đã sẵn sàng trong Benchmark Suite!")
    print(f"Mẹo: Nếu đáp án tự động chưa đúng ý giáo viên, mở '{gt_path}' để sửa lại, rồi chạy 'python run_benchmark.py'.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto Test-Case Ingestion Tool for HocNhanhTN")
    parser.add_argument("--file", required=True, type=str, help="Đường dẫn đến file Word hoặc PDF của giáo viên")
    parser.add_argument("--subject", default="Toán học", type=str, help="Môn học của đề thi")
    parser.add_argument("--style", default="standard", type=str, help="Kiểu soạn thảo (underline, red, bold, asterisk, bottom_table...)")
    parser.add_argument("--desc", default="", type=str, help="Mô tả trường hợp đặc biệt của đề này")
    args = parser.parse_args()

    ingest_file(args.file, subject=args.subject, style=args.style, description=args.desc)
