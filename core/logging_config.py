import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Cấu hình logging chuẩn hóa cho hệ thống."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def get_logger(name: str) -> logging.Logger:
    """Lấy logger theo tên module."""
    return logging.getLogger(name)
