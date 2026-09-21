import os
import uuid
import mimetypes
from typing import Optional, Tuple

try:
    import boto3
    from botocore.config import Config
except ImportError:
    boto3 = None

# Thư mục lưu trữ ảnh cục bộ an toàn (Cache & Fallback)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_IMAGES_DIR = os.path.join(BASE_DIR, "uploads", "images")
os.makedirs(UPLOAD_IMAGES_DIR, exist_ok=True)

# Tự động đọc file .env ở thư mục gốc (nếu có)
env_file = os.path.join(BASE_DIR, ".env")
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

# Đọc cấu hình từ Biến môi trường
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
        R2_BUCKET_NAME
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
    Lưu trữ ảnh đa tầng (Multi-tier Storage):
    1. Lưu bản sao cục bộ vào uploads/images/ để tải siêu tốc (0ms latency, không 403).
    2. Đồng bộ ngầm lên Cloudflare R2 qua S3 API.
    3. Trả về endpoint chuẩn `/api/images/...` để mọi trình duyệt hiển thị 100% không lỗi.
    """
    if not image_bytes:
        return None

    if not extension:
        if "png" in mime_type:
            extension = ".png"
        elif "webp" in mime_type:
            extension = ".webp"
        elif "gif" in mime_type:
            extension = ".gif"
        elif "svg" in mime_type:
            extension = ".svg"
        else:
            extension = ".jpg"
    elif not extension.startswith("."):
        extension = f".{extension}"

    img_id = str(uuid.uuid4())
    filename = f"{img_id}{extension}"
    r2_key = f"quizzes/images/{filename}"

    # 1. Lưu vào thư mục cache cục bộ
    local_file_path = os.path.join(UPLOAD_IMAGES_DIR, filename)
    try:
        with open(local_file_path, "wb") as f:
            f.write(image_bytes)
    except Exception as e:
        print(f"[CẢNH BÁO] Không thể lưu ảnh cục bộ: {e}")

    # 2. Đồng bộ lên Cloudflare R2 nếu có cấu hình
    client = get_r2_client()
    if client:
        try:
            client.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=r2_key,
                Body=image_bytes,
                ContentType=mime_type
            )
        except Exception as e:
            print(f"[CẢNH BÁO] Lỗi tải ảnh lên Cloudflare R2: {e}")

    # Trả về đường dẫn API an toàn tuyệt đối
    return f"/api/images/{r2_key}"


def get_stored_image(image_path: str) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Lấy dữ liệu ảnh và mime-type từ cache cục bộ hoặc Cloudflare R2.
    """
    clean_path = image_path.lstrip("/").replace("\\", "/")
    filename = os.path.basename(clean_path)

    # 1. Tìm trong thư mục cục bộ uploads/images/
    local_path = os.path.join(UPLOAD_IMAGES_DIR, filename)
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        mime, _ = mimetypes.guess_type(local_path)
        with open(local_path, "rb") as f:
            return f.read(), mime or "image/jpeg"

    # 2. Nếu không có ở cục bộ, tải từ Cloudflare R2 qua S3 API (chạy ngầm có quyền đọc)
    client = get_r2_client()
    if client:
        try:
            # Thử key nguyên bản (ví dụ quizzes/images/xxx.jpg)
            response = client.get_object(Bucket=R2_BUCKET_NAME, Key=clean_path)
            content = response['Body'].read()
            mime = response.get('ContentType') or mimetypes.guess_type(clean_path)[0] or "image/jpeg"
            # Lưu lại vào cache cục bộ để các lần sau tải tức thì
            try:
                with open(local_path, "wb") as f:
                    f.write(content)
            except Exception:
                pass
            return content, mime
        except Exception:
            # Thử lại nếu đường dẫn chỉ chứa filename
            if not clean_path.startswith("quizzes/images/"):
                try:
                    alt_key = f"quizzes/images/{filename}"
                    response = client.get_object(Bucket=R2_BUCKET_NAME, Key=alt_key)
                    content = response['Body'].read()
                    mime = response.get('ContentType') or mimetypes.guess_type(alt_key)[0] or "image/jpeg"
                    try:
                        with open(local_path, "wb") as f:
                            f.write(content)
                    except Exception:
                        pass
                    return content, mime
                except Exception:
                    pass

    return None, None
