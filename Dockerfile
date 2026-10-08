# =================================================================
# DOCKERFILE CHO HỆ THỐNG HOCNHANHTRACNGHIEM (PYTHON 3.11 SLIM)
# =================================================================

FROM python:3.11-slim

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    ENVIRONMENT=production \
    HOST=0.0.0.0

WORKDIR /app

# Cài đặt các gói hệ thống cần thiết (cho lxml, xử lý ảnh và healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Tạo user không phải root để tăng tính bảo mật
RUN useradd -m -u 1000 appuser

# Cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn ứng dụng
COPY . .

# Tạo thư mục uploads và phân quyền cho appuser
RUN mkdir -p uploads/images && chown -R appuser:appuser /app

# Chuyển sang user không phải root
USER appuser

# Expose cổng ứng dụng
EXPOSE 8000

# Kiểm tra trạng thái ứng dụng
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

# Khởi chạy ứng dụng với Gunicorn (Production-grade ASGI server)
CMD gunicorn main:app --workers=4 --worker-class=uvicorn.workers.UvicornWorker --bind=0.0.0.0:${PORT:-8000} --timeout=120 --access-logfile=- --error-logfile=- --log-level=info
