# Quy tắc dự án HocNhanhTN (Project Guidelines & Rules)

## 1. Quy tắc chính tả tiếng Việt & Viết hoa (Vietnamese Orthography & Capitalization)

- **NGHIÊM CẤM VIẾT HOA CHỮ CÁI ĐẦU BỪA BÃI (NO TITLE-CASE):**
  Tiếng Việt **không dùng quy tắc Title Case** như tiếng Anh (không viết hoa chữ cái đầu của mỗi từ trong câu/cụm từ/tiêu đề).
  
- **QUY TẮC BẮT BUỘC (Sentence case):**
  1. Chỉ viết hoa chữ cái đầu tiên của câu, đầu dòng, tiêu đề, nhãn nút bấm, thẻ badge hoặc placeholder.
  2. Chỉ viết hoa danh từ riêng, tên thương hiệu, tên người, địa danh: `HocNhanhTN`, `Việt Nam`, `Hà Nội`, `Nguyễn Văn An`.
  3. Chỉ viết hoa từ viết tắt, chuẩn quy định hoặc thuật ngữ kỹ thuật: `AI`, `GDPT 2018`, `PDF`, `Word`, `Excel`, `CSV`, `QR`, `API`, `LMS`, `UI`, `SHTT`, `SBD`, `GD&ĐT`, `NĐ 13/2023/NĐ-CP`.
  4. Chỉ viết hoa tên phần/bài cụ thể kèm số thứ tự: `Phần I`, `Phần II`, `Câu 1`, `Bài 2`.
  5. **Tất cả các từ còn lại trong cụm từ, nhãn, nút bấm, tiêu đề, modal đều phải viết thường.**

- **VÍ DỤ SO SÁNH:**
  - ❌ **SAI (Title Case bừa bãi):**
    - "Trung Tâm Tùy Chọn Xuất Bản HocNhanhTN"
    - "1. Cấu Hình Cơ Bản"
    - "2. Tùy Chọn Nâng Cao & Quản Lý Ca Thi Chuyên Sâu"
    - "A. Giới Hạn Ca Thi & Lượt Làm Bài"
    - "B. Hiển Thị Kết Quả & Đáp Án Chi Tiết"
    - "C. Giám Sát Phòng Thi & Chống Gian Lận"
    - "D. Thông Tin Thí Sinh & Xác Minh Danh Tính"
    - "Hoàn Tất & Xuất Bản Ngay"
    - "Xem Trước Màn Hình Học Sinh"
    - "Chia Sẻ & Mã QR Phòng Thi"
    - "Xuất Bản Đề Thi Thành Công!"
    - "Bắt Buộc Chế Độ Toàn Màn Hình"
    - "Phát Hiện & Ghi Nhận Nhật Ký Chuyển Tab"
    - "Khóa Chống Sao Chép & Chống Copy Đề Thi"
    - "Thời Điểm Hiển Thị Điểm Số"
  - ✅ **ĐÚNG (Sentence case chuẩn tiếng Việt):**
    - "Trung tâm tùy chọn xuất bản HocNhanhTN"
    - "1. Cấu hình cơ bản"
    - "2. Tùy chọn nâng cao & quản lý ca thi chuyên sâu"
    - "A. Giới hạn ca thi & lượt làm bài"
    - "B. Hiển thị kết quả & đáp án chi tiết"
    - "C. Giám sát phòng thi & chống gian lận"
    - "D. Thông tin thí sinh & xác minh danh tính"
    - "Hoàn tất & xuất bản ngay"
    - "Xem trước màn hình học sinh"
    - "Chia sẻ & mã QR phòng thi"
    - "Xuất bản đề thi thành công!"
    - "Bắt buộc chế độ toàn màn hình"
    - "Phát hiện & ghi nhận nhật ký chuyển tab"
    - "Khóa chống sao chép & chống sao chép đề thi"
    - "Thời điểm hiển thị điểm số"

- **PHẠM VI BẮT BUỘC ÁP DỤNG:**
  - Giao diện người dùng: toàn bộ thẻ HTML (`<title>`, `<h1>`..`<h6>`, `<button>`, `<label>`, `<span>`, `<p>`, `placeholder`, `title` tooltip, modal).
  - Mã JavaScript: toàn bộ chuỗi thông báo người dùng (`alert`, `confirm`, `showToast`, `textContent`, `innerHTML`, `dockBar`).
  - Toàn bộ văn bản trao đổi, phản hồi và tài liệu hướng dẫn cho người dùng.

---

## 2. Tiêu chuẩn đồng bộ mã nguồn & Kiểm thử (Code Sync & Verification Standards)

- Mọi thay đổi trong `static/js/script.source.js` bắt buộc phải được minify bằng `npx terser` sang `static/js/script.js` và đồng bộ sang `templates/script.source.js` + `templates/script.js`.
- Mọi thay đổi trong `static/js/editor.js` bắt buộc phải đồng bộ sang `templates/editor.js`.
- Chạy kiểm thử tự động với `python -m pytest` để đảm bảo 100% test pass trước khi hoàn tất phản hồi.
