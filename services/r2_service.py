import os
import uuid
from typing import Optional

try:
    import boto3
    from botocore.config import Config
except ImportError:
    boto3 = None

# Tự động đọc file .env ở thư mục gốc (nếu có)
env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_file):
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    val = v.strip().strip('"').strip("'")
                    if val:
                        os.environ[k.strip()] = val
    except Exception:
        pass

# Đọc cấu hình từ Biến môi trường (Environment Variables trên Koyeb hoặc .env)
R2_ACCOUNT_ID = (os.environ.get("R2_ACCOUNT_ID", "") or "a6af1f4c196200c4d9dc580820b67a72").strip()
R2_ACCESS_KEY_ID = (os.environ.get("R2_ACCESS_KEY_ID", "") or "f718c96568df9659906dd358c25acb95").strip()
R2_SECRET_ACCESS_KEY = (os.environ.get("R2_SECRET_ACCESS_KEY", "") or "7f5048ccd5a5790dfef45bee071aad990c89a06a85143c9d5cdc00a530a9b164").strip()
R2_BUCKET_NAME = (os.environ.get("R2_BUCKET_NAME", "") or "hocnhanhtn").strip()
R2_PUBLIC_URL = (os.environ.get("R2_PUBLIC_URL", "") or "https://pub-4ca74ee0e22a46a39755d1a829865251.r2.dev").strip().rstrip("/")

_s3_client = None

def is_r2_configured() -> bool:
    """Kiểm tra xem hệ thống đã được điền đủ thông số Cloudflare R2 chưa."""
    return bool(
        boto3 is not None and
        R2_ACCOUNT_ID and
        R2_ACCESS_KEY_ID and
        R2_SECRET_ACCESS_KEY and
        R2_BUCKET_NAME and
        R2_PUBLIC_URL
    )

def get_r2_client():
    """Tạo kết nối S3 Client trỏ tới Cloudflare R2 Endpoint."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client
        
    if not is_r2_configured():
        return None
        
    try:
        endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        _s3_client = boto3.client(
            service_name="s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4")
        )
        return _s3_client
    except Exception as e:
        print(f"CẢNH BÁO: Không thể khởi tạo kết nối Cloudflare R2: {e}")
        return None

def upload_image_to_r2(image_bytes: bytes, mime_type: str = "image/jpeg", extension: Optional[str] = None) -> Optional[str]:
    """
    Tải ảnh lên Cloudflare R2 Bucket và trả về Public URL.
    Nếu chưa cấu hình R2 hoặc upload lỗi, hàm sẽ trả về None để tự động fallback về Base64.
    """
    if not is_r2_configured():
        return None
        
    client = get_r2_client()
    if not client:
        return None
        
    try:
        if not extension:
            if "png" in mime_type:
                extension = ".png"
            elif "webp" in mime_type:
                extension = ".webp"
            elif "gif" in mime_type:
                extension = ".gif"
            else:
                extension = ".jpg"
        elif not extension.startswith("."):
            extension = f".{extension}"
            
        file_name = f"quizzes/images/{uuid.uuid4()}{extension}"
        
        client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=file_name,
            Body=image_bytes,
            ContentType=mime_type
        )
        
        public_link = f"{R2_PUBLIC_URL}/{file_name}"
        return public_link
    except Exception as e:
        print(f"Lỗi khi tải ảnh lên Cloudflare R2: {e}")
        return None
