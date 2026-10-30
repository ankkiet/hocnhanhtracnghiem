import time
from typing import Any, List, Optional

import services.r2_service as r2
from core.logging_config import get_logger

logger = get_logger(__name__)


class StorageService:
    """
    Dịch vụ lưu trữ tệp đa tầng (Multi-tier Storage Service).
    Kết hợp lưu trữ đám mây Cloudflare R2 (S3-compatible) với bộ đệm đĩa cục bộ.
    Tích hợp cơ chế Retry, Timeout, Fallback và Logging chi tiết.
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 0.5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def is_configured(self) -> bool:
        """Kiểm tra dịch vụ Cloudflare R2 đã cấu hình đầy đủ chưa."""
        return r2.is_r2_configured()

    def upload_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        extension: Optional[str] = None
    ) -> Optional[str]:
        """
        Tải ảnh lên hệ thống lưu trữ với cơ chế Fallback và Retry tự động:
        1. Kiểm tra tính hợp lệ của ảnh.
        2. Thử tải lên qua r2_service (lưu bản sao cục bộ + đẩy ngầm lên Cloudflare R2).
        3. Tự động thử lại nếu gặp lỗi mạng tạm thời.
        4. Trả về endpoint URL chuẩn để nhúng vào đề thi.
        """
        if not image_bytes:
            logger.warning("StorageService: image_bytes rỗng, bỏ qua upload.")
            return None

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                url = r2.upload_image_to_r2(image_bytes, mime_type=mime_type, extension=extension)
                if url:
                    logger.debug(f"StorageService: Upload ảnh thành công (lần thử {attempt}): {url}")
                    return url
            except Exception as e:
                last_error = e
                logger.warning(
                    f"StorageService: Lỗi tải ảnh lên lưu trữ (lần {attempt}/{self.max_retries}): {e}. "
                    f"Đang chờ {self.retry_delay}s..."
                )
                time.sleep(self.retry_delay * attempt)

        logger.error(f"StorageService: Thất bại sau {self.max_retries} lần thử tải ảnh: {last_error}")
        return None

    def delete_images(self, image_keys_or_urls: List[str]) -> int:
        """
        Xóa danh sách ảnh khỏi cả Cloudflare R2 và bộ nhớ đệm máy chủ.
        """
        if not image_keys_or_urls:
            return 0
        try:
            count = r2.delete_images_from_r2(image_keys_or_urls)
            logger.info(f"StorageService: Đã dọn dẹp {count} ảnh từ danh sách yêu cầu.")
            return count
        except Exception as e:
            logger.error(f"StorageService: Lỗi khi xóa ảnh khỏi lưu trữ: {e}")
            return 0

    def extract_image_keys(self, quiz_data: Any) -> List[str]:
        """Trích xuất toàn bộ khóa/đường dẫn ảnh xuất hiện trong đề thi."""
        return r2.extract_image_keys_from_data(quiz_data)


# Thực thể singleton dùng chung cho toàn bộ ứng dụng
storage_service = StorageService()

# Re-exports tương thích ngược với các module đang import từ r2_service
upload_image_to_r2 = r2.upload_image_to_r2
delete_images_from_r2 = r2.delete_images_from_r2
extract_image_keys_from_data = r2.extract_image_keys_from_data
is_r2_configured = r2.is_r2_configured
get_stored_image = getattr(r2, 'get_stored_image', None)
