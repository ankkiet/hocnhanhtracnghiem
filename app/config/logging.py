"""
Logging Configuration module for HocNhanhTN.
Cung cấp định dạng log chuẩn mực, an toàn UTF-8 trên Windows console.
"""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Khởi tạo cấu hình logging toàn cục."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Đảm bảo UTF-8 stream handler cho console
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Tránh duplicate handlers khi gọi nhiều lần
    if not root_logger.handlers:
        root_logger.addHandler(handler)
    else:
        root_logger.handlers[0] = handler

    # Giảm mức độ ồn của một số thư viện ngoài
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Lấy logger theo tên module."""
    return logging.getLogger(name)
