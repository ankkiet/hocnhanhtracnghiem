# 🎓 HocNhanhTN - Hệ thống học nhanh trắc nghiệm cho học sinh & giáo viên

[![CI Workflow](https://github.com/ankkiet/hocnhanhtracnghiem/actions/workflows/ci.yml/badge.svg)](https://github.com/ankkiet/hocnhanhtracnghiem/actions)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: All Rights Reserved](https://img.shields.io/badge/License-All_Rights_Reserved-red.svg)](LICENSE)

**HocnhanhTN** là nền tại số hóa tài liệu giáo dục và tổ chức thi trực tuyến thông minh, tối ưu hóa theo **Chương trình Giáo dục Phổ thông 2018 (Bộ GD&ĐT)**. Hệ thống cho phép giáo viên tải lên tài liệu Microsoft Word (`.docx`) hoặc PDF (`.pdf`), tự động bóc tách câu hỏi, công thức toán học và hình ảnh, đồng thời hỗ trợ AI cứu hộ và sinh đề tự động bằng Google Gemini.

---

## 🌟 Tính Năng Nổi Bật

### 1. 📑 Bóc tách Đề thi Siêu Tốc & Siêu Bền Vững (Dual-Engine + AI Rescue)
* **Chuẩn Bộ GD&ĐT 2018:**
  * **Phần I:** Trắc nghiệm nhiều lựa chọn ($A, B, C, D$).
  * **Phần II:** Trắc nghiệm Đúng / Sai (các ý $a, b, c, d$ độc lập).
  * **Phần III:** Trắc nghiệm Trả lời ngắn (điền kết quả ngắn, số thập phân, phân số).
* **Bóc tách Bảng Đáp Án:** Tự động nhận diện bảng đáp án dạng bảng (Table) hoặc văn bản ở cuối tài liệu và đối chiếu chuẩn xác vào từng câu.
* **Xử lý Công thức & Hình ảnh:**
  * Nhận diện công thức Toán học `OMML / MathML / LaTeX`.
  * Trích xuất hình ảnh nhúng trong Word/PDF, tối ưu hóa dung lượng và lưu trữ an toàn trên **Cloudflare R2**.
* **Cơ chế 3 lớp bảo vệ:**
  1. *Engine 1:* Phân tích định dạng run/paragraph chuyên sâu và XML.
  2. *Engine 2:* Bóc tách Regex khối dự phòng (Bulletproof Regex Engine).
  3. *AI Rescue:* Tự động kích hoạt Google Gemini cứu hộ khi tài liệu có cấu trúc phi chuẩn hoặc scan.

### 2. 👥 Phân Quyền & Quản Lý Đa Cấp
* **Học sinh (Student):** Vào phòng thi bằng mã đề hoặc liên kết trực tiếp, bấm giờ làm bài, lưu tiến độ tự động, xem kết quả, đáp án chi tiết và bảng xếp hạng.
* **Giáo viên (Teacher):** Quản lý kho đề, studio biên tập & soát lỗi (`/editor`), tùy chỉnh chế độ thi/luyện tập, cấu hình xáo đề, theo dõi phiên thi trực tiếp và biểu đồ phân tích lỗi sai của học sinh.
* **Quản trị viên (Admin):** Quản lý danh sách tài khoản, phê duyệt giáo viên, cấu hình Pool API Keys cho Gemini và giám sát tài nguyên.

---

## 🏛️ Kiến Trúc Hệ Thống (Modular Architecture)

Dự án được cấu trúc theo mô hình phân lớp rõ ràng, tách biệt hoàn toàn giữa Parser, Router, Service và State:

```text
hocnhanhtracnghiem/
├── core/                           # Lõi thuật toán & Bóc tách tài liệu
│   ├── docx_parser.py             # Bộ bóc tách Word (.docx), OMML, formatting weight
│   ├── text_parser.py             # Bộ bóc tách văn bản thô theo cấu trúc chuẩn GDPT 2018
│   ├── pdf_parser.py              # Bộ bóc tách PDF cục bộ (PyMuPDF)
│   ├── answer_key_extractor.py    # Nhận diện & đối chiếu Bảng đáp án
│   ├── image_converter.py         # Nhận diện magic bytes, nén & convert ảnh WebP
│   ├── mathml_parser.py           # Phân tích & chuyển đổi công thức Toán học
│   └── state.py                   # Quản lý trạng thái background task bộ nhớ
├── routers/                        # Tầng API Endpoints (FastAPI Routers)
│   ├── auth.py                    # Xác thực JWT, Đăng ký, Đăng nhập, Google OAuth
│   ├── quiz.py                    # CRUD đề thi, xuất Word (.docx)
│   ├── student.py                 # Phòng thi, nộp bài, lưu tiến độ, bảng xếp hạng
│   ├── teacher.py                 # Thống kê, biểu đồ phân tích bài nộp, phiên thi
│   ├── admin.py                   # Quản lý người dùng, cấu hình API key
│   └── document.py                # Upload tài liệu, sinh đề AI, task status, phục vụ ảnh
├── services/                       # Tầng tích hợp dịch vụ bên thứ ba
│   ├── firebase_service.py        # Kết nối Cloud Firestore (an toàn, không crash khi thiếu key)
│   ├── ai_service.py              # Gemini AI orchestration, rate-limit fallback & pooling
│   └── r2_service.py              # Lưu trữ & tải ảnh Cloudflare R2 (S3 Protocol)
├── templates/                      # Giao diện Frontend (SPA / Static Web)
│   ├── index.html                 # Giao diện thi trắc nghiệm & cổng học sinh
│   ├── editor.html                # Studio biên tập & soát lỗi đề thi
│   ├── teacher.html               # Bảng điều khiển giáo viên
│   ├── admin.html                 # Trang quản trị hệ thống
│   └── style.css                  # Thiết kế giao diện hiện đại
├── tests/                          # Bộ kiểm thử tự động (Unit & Integration tests)
│   ├── test_bulletproof_parsing.py # Kiểm thử bóc tách Word & PDF
│   ├── test_fixed_features.py     # Kiểm thử nghiệp vụ giáo viên & học sinh
│   ├── test_docx_export.py        # Kiểm thử xuất đề thi kèm công thức toán
│   └── test_api_endpoints.py      # Kiểm thử FastAPI endpoints (TestClient)
├── .github/workflows/ci.yml       # Quy trình CI tự động chạy tests trên Python 3.10 & 3.11
├── Dockerfile                      # Dockerfile môi trường production
├── docker-compose.yml              # Cấu hình khởi chạy nhanh qua Docker Compose
├── requirements.txt                # Danh sách thư viện phụ thuộc
├── .env.example                    # File mẫu cấu hình biến môi trường
└── main.py                         # Điểm khởi chạy ứng dụng FastAPI (Lean & Clean)
```

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy Nhanh

### 1. Yêu Cầu Tiên Quyết
* Python `>= 3.10` (Khuyến nghị Python `3.11`)
* Git
* Tài khoản Firebase (Firestore) & Google AI Studio (Gemini API)

### 2. Cài Đặt Môi Trường Cục Bộ

```bash
# 1. Clone mã nguồn
git clone https://github.com/ankkiet/hocnhanhtracnghiem.git
cd hocnhanhtracnghiem

# 2. Tạo và kích hoạt môi trường ảo
# Trên Windows:
python -m venv venv
.\venv\Scripts\activate

# Trên Linux/macOS:
python3 -m venv venv
source venv/bin/activate

# 3. Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

### 3. Cấu Hình Biến Môi Trường (.env)

Sao chép tệp mẫu `.env.example` thành `.env`:
```bash
cp .env.example .env
```

Mở tệp `.env` và điền các tham số:
1. **Bảo mật JWT:** Đặt `JWT_SECRET` với chuỗi ngẫu nhiên bảo mật cao.
2. **Firebase Firestore:**
   * Cách 1 (Khuyên dùng khi Dev): Đặt tệp `serviceAccountKey.json` vào thư mục gốc dự án.
   * Cách 2 (Khuyên dùng trên Cloud/Docker): Mã hóa tệp JSON sang Base64 và điền vào biến `FIREBASE_SERVICE_ACCOUNT_BASE64`.
3. **Google Gemini:** Điền `GEMINI_API_KEY` (hoặc cấu hình pool nhiều key trong trang Admin).
4. **Cloudflare R2 (Tùy chọn):** Cấu hình `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` để lưu trữ ảnh đề thi trên đám mây.

### 4. Khởi Chạy Ứng Dụng

```bash
python main.py
```

Truy cập hệ thống tại:
* 🌐 **Giao diện làm bài / Trang chủ:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* 📝 **Studio Soát lỗi Đề thi:** [http://127.0.0.1:8000/editor](http://127.0.0.1:8000/editor)
* 📖 **Tài liệu API Swagger:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* 🩺 **Kiểm tra trạng thái (Health Check):** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## 🐳 Triển Khai Với Docker & Docker Compose

### Cách 1: Sử dụng Docker Compose (Khuyên dùng)

```bash
# Khởi chạy ứng dụng chạy ngầm
docker compose up -d

# Xem logs hoạt động
docker compose logs -f

# Dừng hệ thống
docker compose down
```

### Cách 2: Tự Build & Chạy Dockerfile

```bash
# Xây dựng Docker Image
docker build -t hocnhanhtn-backend:latest .

# Khởi chạy Docker Container
docker run -d -p 8000:8000 --env-file .env --name hocnhanhtn-app hocnhanhtn-backend:latest
```

---

## 🧪 Kiểm Thử Tự Động (Automated Testing)

Dự án bao gồm bộ kiểm thử đơn vị và tích hợp toàn diện:

```bash
# Chạy toàn bộ 35+ bài kiểm thử tự động
python -m unittest discover -s tests -p "test_*.py" -v
```

Kiểm thử bao gồm:
* `test_bulletproof_parsing.py`: Kiểm tra độ chính xác của bộ bóc tách Word, PDF, hình ảnh, MathML và Bảng đáp án.
* `test_api_endpoints.py`: Kiểm thử API Health, Ping, Upload validation, Serve Image và Task status.
* `test_docx_export.py`: Kiểm thử chức năng xuất file Word chuẩn kèm công thức Toán.
* `test_fixed_features.py`: Kiểm tra tính toàn vẹn nghiệp vụ làm bài, chấm điểm và phân tích đề của giáo viên.

---

## 🛡️ Checklist Sẵn Sàng Cho Production

- [x] Tách mã nguồn thành các module độc lập (`core/`, `routers/`, `services/`).
- [x] Loại bỏ file nhị phân và artifact khỏi Git history.
- [x] Cung cấp đầy đủ `.env.example` và `README.md`.
- [x] Đóng gói Docker (`Dockerfile`, `docker-compose.yml`, `.dockerignore`).
- [x] Thiết lập CI tự động kiểm tra cú pháp và chạy test qua GitHub Actions.
- [x] API Health Check & Ping endpoint chống ngủ đông máy chủ Cloud (Render, Hugging Face Spaces).
- [x] Tự động giải phóng RAM cho các tác vụ phân tích hoàn tất sau 15 phút.

---

## 📄 Bản Quyền & Giấy Phép (Copyright & License)

**Bản quyền © 2026 thuộc về tác giả / HocNhanhTN (ankkiet). Toàn bộ quyền được bảo lưu (All Rights Reserved).**

* Phần mềm này và toàn bộ mã nguồn liên quan là sản phẩm trí tuệ độc quyền.
* **Nghiêm cấm mọi hành vi sao chép, trích xuất, phân phối lại, chỉnh sửa hoặc khai thác thương mại** dưới bất kỳ hình thức nào khi chưa có sự đồng ý bằng văn bản từ tác giả / chủ sở hữu.
* **Email liên hệ & Cấp phép:** [kiet0905478167@gmail.com](mailto:kiet0905478167@gmail.com)
* Website chính thức: [hocnhanhtn.pages.dev](https://hocnhanhtn.pages.dev/)
