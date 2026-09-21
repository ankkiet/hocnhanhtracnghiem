import os
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "hocnhanhtn-secret-jwt-key-2026-secure-token-999")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

def hash_password(password: str) -> str:
    """Băm mật khẩu sử dụng PBKDF2-HMAC-SHA256 kèm Salt ngẫu nhiên chống tấn công Rainbow Table."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"pbkdf2_sha256$100000${salt}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Xác minh mật khẩu, hỗ trợ tương thích ngược cả chuẩn SHA256 cũ lẫn PBKDF2 mới.
    """
    if not hashed_password:
        return False
        
    # Chuẩn mới: pbkdf2_sha256$iterations$salt$hash
    if hashed_password.startswith("pbkdf2_sha256$"):
        parts = hashed_password.split("$")
        if len(parts) == 4:
            iterations = int(parts[1])
            salt = parts[2]
            stored_hash = parts[3]
            calculated_key = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), iterations)
            return hmac.compare_digest(calculated_key.hex(), stored_hash)
            
    # Chuẩn cũ: SHA-256 thuần (64 ký tự hex)
    old_hash = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
    return hmac.compare_digest(old_hash, hashed_password)

def is_legacy_hash(hashed_password: str) -> bool:
    """Kiểm tra xem mật khẩu có đang dùng chuẩn cũ SHA-256 không để tự nâng cấp."""
    return not hashed_password.startswith("pbkdf2_sha256$")

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Tạo JWT Token có thời hạn và chữ ký điện tử an toàn."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Giải mã JWT Token an toàn."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None

def get_user_from_token(token: str, db) -> Optional[Dict[str, Any]]:
    """
    Xác thực token người dùng:
    1. Ưu tiên giải mã JWT.
    2. Nếu không phải JWT (token cũ là Firestore Doc ID), tra cứu trực tiếp trong Firestore để tương thích ngược.
    """
    if not token or db is None:
        return None
        
    token = str(token).strip()
    payload = decode_access_token(token)
    if payload and "sub" in payload:
        user_id = payload["sub"]
        doc = db.collection('users').document(user_id).get()
        if doc.exists:
            user_data = doc.to_dict()
            user_data['id'] = doc.id
            return user_data
            
    try:
        doc = db.collection('users').document(token).get()
        if doc.exists:
            user_data = doc.to_dict()
            user_data['id'] = doc.id
            return user_data
    except Exception:
        pass
        
    return None

