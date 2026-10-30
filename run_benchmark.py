"""
Công cụ chạy Benchmark bóc tách tài liệu (Parser Benchmark CLI) - HocNhanhTN.

Cách sử dụng:
  python run_benchmark.py                     # Chạy toàn bộ 40 test files
  python run_benchmark.py --subject "Toán"    # Chỉ chạy môn Toán học
  python run_benchmark.py --format "pdf"      # Chỉ chạy các file PDF
  python run_benchmark.py --file "toan_01"    # Chạy 1 file cụ thể
  python run_benchmark.py --save-baseline     # Lưu kết quả hiện tại làm mốc Baseline kiểm tra hồi quy
  python run_benchmark.py --fail-under 92.0   # Báo lỗi exit 1 nếu độ chính xác < 92%
"""

import argparse
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from tests.benchmark.evaluator import run_benchmark_suite

BASELINE_PATH = os.path.join(BASE_DIR, "tests", "benchmark", "baseline.json")


def format_bar(val: float, width: int = 15) -> str:
    filled = int(round(val / 100.0 * width))
    return "█" * filled + "░" * (width - filled)


def main():
    parser = argparse.ArgumentParser(description="HocNhanhTN Parser Benchmark Suite")
    parser.add_argument("--subject", type=str, default=None, help="Lọc theo môn học (vd: 'Toán học', 'Vật lý')")
    parser.add_argument("--format", type=str, default=None, choices=["docx", "pdf"], help="Lọc theo định dạng file ('docx' hoặc 'pdf')")
    parser.add_argument("--file", type=str, default=None, help="Chạy kiểm tra một file cụ thể")
    parser.add_argument("--save-baseline", action="store_true", help="Lưu kết quả chạy hiện tại thành baseline")
    parser.add_argument("--fail-under", type=float, default=90.0, help="Ngưỡng điểm tối thiểu (mặc định: 90.0%%)")
    parser.add_argument("--json", action="store_true", help="Xuất kết quả dưới định dạng JSON")
    args = parser.parse_args()

    print("=" * 90)
    print("      HOCNHANHTN PARSER BENCHMARK SUITE - ĐO LƯỜNG ĐỘ CHÍNH XÁC BÓC TÁCH      ")
    print("=" * 90)
    print(f"[*] Thời gian kiểm thử: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[*] Bộ lọc: Subject={args.subject or 'Tất cả'} | Format={args.format or 'Tất cả'} | File={args.file or 'Tất cả'}")
    print(f"[*] Baseline mốc hồi quy: {BASELINE_PATH if os.path.exists(BASELINE_PATH) else 'Chưa có (Dùng --save-baseline để tạo)'}")
    print("-" * 90)

    start_time = time.time()
    result = run_benchmark_suite(
        filter_subject=args.subject,
        filter_format=args.format,
        filter_file=args.file,
        baseline_path=BASELINE_PATH
    )
    duration = time.time() - start_time

    if args.json:
        report = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "duration_seconds": round(duration, 2),
            "total_files": result.total_files,
            "passed_files": result.passed_files,
            "average_overall_accuracy": result.average_accuracy,
            "average_answer_accuracy": result.average_answer_accuracy,
            "average_options_accuracy": result.average_options_accuracy,
            "regressions": result.regressions,
            "files": [r.to_dict() for r in result.file_results]
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    # In bảng chi tiết từng file
    header = f"{'STT':<4} | {'Tên File':<32} | {'Môn':<12} | {'Kiểu soạn':<13} | {'Số câu':<7} | {'Đáp án':<8} | {'Tổng điểm':<10} | {'Trạng thái'}"
    print(header)
    print("-" * len(header))

    for idx, r in enumerate(result.file_results, 1):
        status_str = "PASS [OK]" if r.is_passed else "FAIL [X]"
        q_count_str = f"{r.total_parsed}/{r.total_expected}"
        ans_str = f"{r.answer_accuracy * 100:.0f}%"
        overall_str = f"{r.overall_accuracy:.1f}%"
        print(f"{idx:<4} | {r.file_name:<32} | {r.subject:<12} | {r.style[:13]:<13} | {q_count_str:<7} | {ans_str:<8} | {overall_str:<10} | {status_str}")

    print("-" * len(header))

    # In phân tích theo Môn học
    print("\n" + "=" * 55)
    print("        TỔNG KẾT ĐỘ CHÍNH XÁC THEO MÔN HỌC        ")
    print("=" * 55)
    print(f"{'Môn học':<22} | {'Số file':<8} | {'Đáp án %':<10} | {'Tổng thể %'}")
    print("-" * 55)
    for sub, data in result.get_subject_breakdown().items():
        print(f"{sub:<22} | {data['passed_files']}/{data['total_files']:<6} | {data['avg_ans_score']:>6.1f}%   | {data['avg_score']:>6.1f}%  {format_bar(data['avg_score'])}")
    print("-" * 55)

    # In phân tích theo Định dạng
    print("\n" + "=" * 55)
    print("       TỔNG KẾT THEO ĐỊNH DẠNG TÀI LIỆU (DOCX / PDF)      ")
    print("=" * 55)
    docx_files = [r for r in result.file_results if r.file_name.endswith('.docx')]
    pdf_files = [r for r in result.file_results if r.file_name.endswith('.pdf')]
    if docx_files:
        docx_acc = sum(r.overall_accuracy for r in docx_files) / len(docx_files)
        docx_pass = sum(1 for r in docx_files if r.is_passed)
        print(f"{'Word (.docx)':<22} | {docx_pass}/{len(docx_files):<6} | {docx_acc:>6.1f}%  {format_bar(docx_acc)}")
    if pdf_files:
        pdf_acc = sum(r.overall_accuracy for r in pdf_files) / len(pdf_files)
        pdf_pass = sum(1 for r in pdf_files if r.is_passed)
        print(f"{'PDF (.pdf)':<22} | {pdf_pass}/{len(pdf_files):<6} | {pdf_acc:>6.1f}%  {format_bar(pdf_acc)}")
    print("-" * 55)

    # Hiển thị lỗi nếu có
    files_with_errors = [r for r in result.file_results if r.errors]
    if files_with_errors:
        print("\n" + "=" * 90)
        print("                 CHI TIẾT CÁC CÂU CẦN TỐI ƯU THÊM                 ")
        print("=" * 90)
        for r in files_with_errors:
            print(f"\n[!] File: {r.file_name} ({r.subject} - {r.style}) [Điểm: {r.overall_accuracy}%]:")
            for err in r.errors[:5]:
                print(f"    -> {err}")
            if len(r.errors) > 5:
                print(f"    -> ... và {len(r.errors) - 5} lỗi khác.")

    # Kiểm tra Hồi quy (Regression Analysis)
    print("\n" + "=" * 90)
    print("           KIỂM TRA HỒI QUY (REGRESSION DETECTION VS BASELINE)           ")
    print("=" * 90)
    if not os.path.exists(BASELINE_PATH) and not args.save_baseline:
        print("[*] Chưa thiết lập baseline. Hãy chạy 'python run_benchmark.py --save-baseline' để lưu mốc.")
    elif result.regressions:
        print(f"[CẢNH BÁO NGUY HIỂM] PHÁT HIỆN {len(result.regressions)} TRƯỜNG HỢP BỊ HỒI QUY SO VỚI BASELINE:")
        for reg in result.regressions:
            print(f"  ❌ File: {reg['file_name']} ({reg['subject']}): {reg['baseline_score']}% -> {reg['current_score']}% ({reg['diff']}%)")
            for err in reg["errors"][:2]:
                print(f"     Lỗi: {err}")
    else:
        print("  [OK] KHÔNG PHÁT HIỆN LỖI HỒI QUY NÀO! Tất cả các trường hợp cũ đều giữ nguyên hoặc tăng độ chính xác.")

    # Lưu Baseline nếu người dùng yêu cầu
    if args.save_baseline:
        baseline_save = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "average_overall_accuracy": result.average_accuracy,
            "average_answer_accuracy": result.average_answer_accuracy,
            "total_files": result.total_files,
            "files": {r.file_id: r.to_dict() for r in result.file_results}
        }
        with open(BASELINE_PATH, "w", encoding="utf-8") as bf:
            json.dump(baseline_save, bf, ensure_ascii=False, indent=2)
        print(f"\n[SUCCESS] Đã lưu Baseline mới thành công tại: {BASELINE_PATH}")
        print(f"  Mốc điểm trung bình: {result.average_accuracy}%")

    # Tổng kết
    print("\n" + "=" * 90)
    print("                                TỔNG KẾT CHUNG                               ")
    print("=" * 90)
    print(f"[*] Tổng số file kiểm tra:      {result.total_files}")
    print(f"[*] Số file đạt chuẩn (>=90%): {result.passed_files} / {result.total_files} ({(result.passed_files / result.total_files * 100):.1f}%)")
    print(f"[*] Tổng số câu hỏi kiểm tra:   {result.total_expected_questions} câu")
    print(f"[*] Độ chính xác đáp án:        {result.average_answer_accuracy}%")
    print(f"[*] Độ chính xác phương án:     {result.average_options_accuracy}%")
    print(f"[*] ĐỘ CHÍNH XÁC TRUNG BÌNH:    {result.average_accuracy}%")
    print(f"[*] Thời gian thực thi:         {duration:.2f} giây ({duration / max(1, result.total_files):.2f}s / file)")
    print("=" * 90)

    # Đánh giá điều kiện đạt chuẩn
    if result.average_accuracy < args.fail_under:
        print(f"\n[THẤT BẠI] Độ chính xác trung bình ({result.average_accuracy}%) dưới ngưỡng cho phép ({args.fail_under}%).")
        sys.exit(1)
    elif result.regressions:
        print("\n[THẤT BẠI] Phát hiện lỗi hồi quy so với Baseline cũ. Vui lòng kiểm tra lại code parser.")
        sys.exit(1)
    else:
        print("\n[THÀNH CÔNG] Tất cả các bài kiểm tra Parser Benchmark đều ĐẠT CHUẨN!")
        sys.exit(0)


if __name__ == "__main__":
    main()
