# HỆ THỐNG BENCHMARK & KIỂM THỬ HỒI QUY PARSER (HOCNHANHTN)

> **"Đây là phần quan trọng nhất của sản phẩm. Mỗi lần sửa parser, bạn biết ngay có làm hỏng trường hợp cũ không."**

---

## 1. Tổng quan Bộ dữ liệu Benchmark (40 Tệp chuẩn)

Hệ thống cung cấp sẵn **40 tệp đề thi thực tế** (30 tệp Word `.docx` và 10 tệp PDF `.pdf`) cùng **40 tệp Ground Truth chuẩn xác 100%** (`.json`) với tổng cộng **204 câu hỏi** thực tế từ các trường THCS và THPT Việt Nam.

### A. Phân bổ theo 10 Môn học:
| Môn học | Số lượng tệp | Số câu hỏi | Ghi chú các đặc thù bóc tách |
| :--- | :---: | :---: | :--- |
| **Toán học** | 5 tệp (4 docx, 1 pdf) | 27 câu | Công thức số học, đạo hàm, tích phân, tọa độ Oxyz, mặt cầu |
| **Vật lý** | 4 tệp (3 docx, 1 pdf) | 21 câu | Dao động cơ, sóng cơ, dòng điện xoay chiều, nhiệt học |
| **Hóa học** | 4 tệp (3 docx, 1 pdf) | 21 câu | Este, lipit, chỉ số dưới hóa học ($C_4H_8O_2$), cân bằng hóa học |
| **Sinh học** | 4 tệp (3 docx, 1 pdf) | 21 câu | Di truyền Menđen, NST 2n, đột biến gen, hệ sinh thái |
| **Tiếng Anh** | 6 tệp (4 docx, 2 pdf) | 30 câu | Bài đọc hiểu (`group_title`), ngữ âm, trọng âm, hội thoại |
| **Lịch sử** | 4 tệp (3 docx, 1 pdf) | 20 câu | Cách mạng tháng Tám, kháng chiến chống Mỹ, ASEAN, Ianta |
| **Địa lý** | 4 tệp (3 docx, 1 pdf) | 21 câu | Địa lý tự nhiên, kinh tế vùng, đô thị hóa, số liệu thống kê |
| **GDKT & Pháp luật** | 3 tệp (2 docx, 1 pdf) | 14 câu | Tình huống pháp luật dài nhiều nhân vật, quyền bình đẳng |
| **Tin học** | 3 tệp (2 docx, 1 pdf) | 16 câu | Đoạn mã code Python, SQL, mạng máy tính, thuật toán |
| **Ngữ văn & Khác** | 3 tệp (3 docx) | 14 câu | Đọc hiểu trích dẫn thơ/văn, tiền tố đặc biệt (`1/`, `Bài 3:`) |
| **TỔNG CỘNG** | **40 tệp** | **204 câu** | **Độ chính xác hiện tại: 99.53%** |

### B. Phân bổ theo các Kiểu soạn thảo của Giáo viên:
1. **Gạch chân (`<u>`)**: Đáp án đúng được giáo viên gạch chân dưới ký tự hoặc toàn bộ phương án.
2. **Chữ màu đỏ (`#FF0000`)**: Tô màu đỏ cho đáp án đúng trong văn bản Word.
3. **In đậm (`<b>`)**: Bôi đậm toàn bộ phương án đúng trong khi các phương án khác để thường.
4. **Dấu hoa thị (`*`)**: Đánh dấu `*A.`, `*B.`, `*C.`, `*D.` hoặc `A.*`.
5. **Bảng đáp án cuối bài (Word Table)**: Không đánh dấu trong câu, có bảng Word 2 hàng ở cuối đề (`Câu` / `Đáp án`).
6. **Bảng đáp án dạng Text**: Dòng văn bản cuối đề dạng `1.A  2.B  3.C` hoặc `1-A, 2-B, 3-C`.
7. **Lời giải chi tiết sau mỗi câu**: Khối `Lời giải chi tiết:` hoặc `Hướng dẫn giải:` được bóc tách riêng biệt vào trường `explain`.
8. **Phương án trên 1 dòng**: Các lựa chọn A, B, C, D nằm trên cùng 1 hàng phân cách bằng tab/khoảng trắng.
9. **Chuẩn GDPT 2018 (3 Phần)**:
   - *PHẦN I*: Trắc nghiệm 4 lựa chọn (A, B, C, D).
   - *PHẦN II*: Trắc nghiệm Đúng / Sai (4 ý độc lập a, b, c, d).
   - *PHẦN III*: Trắc nghiệm Trả lời ngắn (Điền số / kết quả ngắn).
10. **Nhóm câu hỏi đọc hiểu**: Ngữ liệu văn bản dùng chung (`group_title`) cho nhiều câu hỏi liên tiếp.
11. **Tiền tố câu hỏi không chuẩn**: `1.`, `2/`, `Bài 3:`, `Question 4.`, `Q5:`.

---

## 2. Hướng dẫn Sử dụng CLI Runner (`run_benchmark.py`)

Công cụ dòng lệnh `run_benchmark.py` cung cấp giao diện trực quan với bảng tiến độ, tỷ lệ đáp án, và cơ chế phát hiện lỗi hồi quy tự động.

### Lệnh cơ bản:
```bash
# Chạy toàn bộ 40 test files và so sánh với baseline:
python run_benchmark.py

# Lọc chạy riêng theo môn học:
python run_benchmark.py --subject "Toán học"
python run_benchmark.py --subject "Tiếng Anh"

# Lọc chạy riêng theo định dạng file:
python run_benchmark.py --format "docx"
python run_benchmark.py --format "pdf"

# Chạy kiểm tra một file cụ thể:
python run_benchmark.py --file "toan_01_gach_chan.docx"

# Thiết lập/cập nhật mốc Baseline sau khi nâng cấp parser:
python run_benchmark.py --save-baseline

# Đặt ngưỡng điểm chặn (exit code 1 nếu trung bình < 95%):
python run_benchmark.py --fail-under 95.0

# Xuất báo cáo kết quả ra định dạng JSON:
python run_benchmark.py --json
```

---

## 3. Tích hợp Kiểm thử Tự động (CI / CD)

Tích hợp trực tiếp với hệ thống kiểm thử tiêu chuẩn Python:
```bash
python -m unittest tests/test_parser_benchmark.py
```

Các ca kiểm thử tự động bao gồm:
- `test_dataset_integrity`: Kiểm tra đầy đủ 40 tệp và 40 Ground Truth JSON.
- `test_benchmark_overall_accuracy_above_threshold`: Đảm bảo độ chính xác trung bình toàn hệ thống $\ge 95\%$.
- `test_benchmark_answer_accuracy_high`: Đảm bảo tỷ lệ bóc tách đúng đáp án $\ge 95\%$.
- `test_benchmark_options_accuracy_perfect`: Đảm bảo tỷ lệ bóc tách đủ 4 phương án đạt $100\%$.
- `test_no_regressions_against_baseline`: **Báo lỗi FAIL ngay lập tức nếu bất kỳ file nào có điểm số bị tụt lùi so với baseline cũ!**
- `test_gdpt_2018_multi_part_parsing`: Kiểm tra chuyên sâu đề chuẩn GDPT 2018 (3 phần).
- `test_pdf_parsing_accuracy`: Kiểm tra chất lượng bóc tách PDF cục bộ.

---

## 4. Cơ chế Đo lường Độ chính xác (Scoring Algorithm)

Độ chính xác của mỗi tệp ($Accuracy_{file}$) được tính theo công thức trọng số toàn diện:

$$Accuracy_{file} = 30\% \cdot Acc_{Số\_lượng} + 30\% \cdot Acc_{Phương\_án} + 30\% \cdot Acc_{Đáp\_án} + 10\% \cdot Acc_{Thân\_câu}$$

Trong đó:
- $Acc_{Số\_lượng} = \max\left(0, 1 - \frac{|Parsed - Expected|}{Expected}\right)$: Đo lường tỷ lệ bắt đúng số lượng câu hỏi.
- $Acc_{Phương\_án}$: Đo lường tỷ lệ bóc tách đủ 4 phương án $A, B, C, D$ (hoặc $a, b, c, d$).
- $Acc_{Đáp\_án}$: Đo lường tỷ lệ phát hiện đúng đáp án:
  - MCQ: Trùng ký tự phương án ($A, B, C, D$).
  - Đúng/Sai: Khớp chính xác dictionary 4 mệnh đề `{"a": bool, "b": bool, "c": bool, "d": bool}`.
  - Trả lời ngắn: Chuẩn hóa số thực/nguyên (vd: $12,5 \equiv 12.5$).
- $Acc_{Thân\_câu}$: Đo lường sự toàn vẹn của nội dung câu hỏi sau khi loại bỏ tiền tố và thẻ rác.

---

## 5. Quy trình Bổ sung File Mẫu Mới của Giáo viên

Để mở rộng bộ dữ liệu lên 50, 100+ file thực tế:

1. **Thêm file tài liệu**:
   - Copy file Word vào `tests/benchmark/dataset/docx/<ten_file>.docx`
   - Hoặc copy file PDF vào `tests/benchmark/dataset/pdf/<ten_file>.pdf`

2. **Tạo tệp Ground Truth**:
   - Tạo file `tests/benchmark/dataset/ground_truth/<file_id>.json` với cấu trúc:
   ```json
   {
     "file_id": "docx_toan_de_chuyen_01",
     "file_name": "toan_de_chuyen_01.docx",
     "format_type": "docx",
     "subject": "Toán học",
     "style": "underline",
     "style_description": "Đề thi thử trường Chuyên Amsterdam",
     "tags": ["toan", "chuyen", "underline"],
     "total_questions": 5,
     "questions": [
       {
         "question_number": 1,
         "type": "mcq",
         "question": "Nội dung câu hỏi...",
         "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
         "correct_answer": "A. ...",
         "explain": "Lời giải nếu có..."
       }
     ]
   }
   ```

3. **Cập nhật Manifest & Kiểm tra**:
   - Thêm thông tin tệp vào `tests/benchmark/manifest.json`.
   - Chạy `python run_benchmark.py --file <file_id>` để kiểm tra ngay.
   - Nếu kết quả tốt, chạy `python run_benchmark.py --save-baseline` để cập nhật mốc hồi quy mới.
