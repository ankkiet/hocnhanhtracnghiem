# =================================================================
# DOCKERFILE CHO HỆ THỐNG HOCNHANHTRACNGHIEM (PYTHON 3.11 SLIM)
# =================================================================

FROM python:3.11-slim

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Cài đặt các gói hệ thống cần thiết (cho lxml, xử lý ảnh và healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn ứng dụng
COPY . .

# Tạo thư mục uploads nếu chưa tồn tại
RUN mkdir -p uploads/images

# Expose cổng ứng dụng
EXPOSE 8000

# Kiểm tra trạng thái ứng dụng
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

# Khởi chạy FastAPI với Uvicorn server (Sử dụng shell để lấy biến môi trường PORT)
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"
