import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from services.firebase_service import get_db
from core.security import (
    hash_password,
    verify_password,
    is_legacy_hash,
    create_access_token,
    ADMIN_EMAILS,
    check_and_assign_admin
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str

class LoginRequest(BaseModel):
    username: str
    password: str

class GoogleAuthRequest(BaseModel):
    credential: Optional[str] = None
    access_token: Optional[str] = None

def get_current_google_client_id(db) -> str:
    """Lấy Google Client ID từ cấu hình Firestore hoặc biến môi trường."""
    if db:
        try:
            doc = db.collection('settings').document('google_auth').get()
            if doc.exists:
                cid = doc.to_dict().get('client_id', '').strip()
                if cid:
                    return cid
        except Exception:
            pass
    return os.environ.get("GOOGLE_CLIENT_ID", "").strip()

async def verify_google_payload(credential: Optional[str], access_token: Optional[str], expected_client_id: str = "") -> dict:
    """Xác thực token Google (Firebase ID Token hoặc Google OAuth2 Token) và lấy thông tin người dùng."""
    # 1. Thử xác thực qua Firebase Admin SDK (Chính thức và nhanh nhất cho Firebase Auth)
    if credential:
        try:
            import firebase_admin.auth as fb_auth
            decoded = fb_auth.verify_id_token(credential)
            if decoded and "email" in decoded:
                return {
                    "email": decoded.get("email"),
                    "name": decoded.get("name") or decoded.get("email", "").split("@")[0],
                    "picture": decoded.get("picture", ""),
                    "sub": decoded.get("uid") or decoded.get("sub", "")
                }
        except Exception:
            pass

        # 2. Thử xác thực offline bằng thư viện chính thức google-auth
        try:
            req = google_requests.Request()
            audience = expected_client_id if expected_client_id else None
            id_info = google_id_token.verify_oauth2_token(credential, req, audience=audience)
            if id_info and "email" in id_info:
                return id_info
        except Exception:
            pass

        # 3. Fallback gọi trực tiếp endpoint tokeninfo của Google
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}")
                if res.status_code == 200:
                    info = res.json()
                    if "email" in info:
                        return info
        except Exception:
            pass

    # 4. Thử xác thực qua OAuth2 Access Token
    if access_token:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if res.status_code == 200:
                    info = res.json()
                    if "email" in info:
                        return info
        except Exception:
            pass

    raise HTTPException(status_code=400, detail="Xác thực tài khoản Google không hợp lệ hoặc đã hết hạn.")

@router.get("/config", summary="Lấy cấu hình xác thực công khai")
async def get_auth_config():
    """Trả về các cấu hình frontend cần dùng, như Google Client ID."""
    db = get_db()
    client_id = get_current_google_client_id(db)
    return {
        "status": "success",
        "google_client_id": client_id
    }

@router.post("/google", summary="Đăng nhập hoặc đăng ký nhanh bằng Google")
async def google_login(req: GoogleAuthRequest):
    """
    Xác thực qua tài khoản Google.
    - Tài khoản kiet0905478167@gmail.com luôn được cấp quyền Admin cao nhất.
    - Tự động đồng bộ thông tin và cấp JWT Token an toàn.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")

    if not req.credential and not req.access_token:
        raise HTTPException(status_code=400, detail="Thiếu thông tin xác thực Google")

    client_id = get_current_google_client_id(db)
    google_user = await verify_google_payload(req.credential, req.access_token, client_id)

    email = (google_user.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Không tìm thấy email từ tài khoản Google")

    name = google_user.get("name") or email.split("@")[0]
    picture = google_user.get("picture", "")
    google_sub = google_user.get("sub", "")

    # Kiểm tra xem user đã có trong hệ thống chưa (tìm theo email hoặc username)
    users = db.collection('users').where('email', '==', email).get()
    if not users:
        users = db.collection('users').where('username', '==', email).get()

    now_iso = datetime.now(timezone.utc).isoformat()
    is_super_admin = (email in ADMIN_EMAILS)

    if users:
        user_doc = users[0]
        user_data = user_doc.to_dict()
        user_id = user_doc.id

        # Cập nhật thông tin mới nhất từ Google
        update_fields = {
            'avatar': picture or user_data.get('avatar', ''),
            'last_login': now_iso,
            'google_id': google_sub
        }

        # Nếu là tài khoản Admin chỉ định thì luôn bảo đảm role admin và status approved
        if is_super_admin:
            update_fields['role'] = 'admin'
            update_fields['status'] = 'approved'
            user_data['role'] = 'admin'
            user_data['status'] = 'approved'

        db.collection('users').document(user_id).update(update_fields)

        if user_data.get('status') != 'approved':
            raise HTTPException(status_code=403, detail="Tài khoản của bạn đang chờ Quản trị viên phê duyệt.")

        final_role = user_data.get('role', 'student')
        final_name = user_data.get('full_name') or name
    else:
        # Tạo người dùng mới
        final_role = 'admin' if is_super_admin else 'teacher'
        final_status = 'approved' # Người dùng qua Google đã xác thực email
        final_name = name

        new_user_data = {
            'username': email,
            'email': email,
            'full_name': final_name,
            'role': final_role,
            'status': final_status,
            'auth_provider': 'google',
            'avatar': picture,
            'google_id': google_sub,
            'created_at': now_iso,
            'last_login': now_iso
        }
        _, new_doc = db.collection('users').add(new_user_data)
        user_id = new_doc.id

    # Tạo JWT Token bảo mật 7 ngày
    token_payload = {
        "sub": user_id,
        "username": email,
        "role": final_role,
        "full_name": final_name
    }
    jwt_token = create_access_token(token_payload)

    return {
        "status": "success",
        "token": jwt_token,
        "role": final_role,
        "full_name": final_name,
        "email": email,
        "avatar": picture
    }

@router.post("/register", summary="Đăng ký tài khoản mới")
async def register(req: RegisterRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")
        
    username = req.username.strip().lower()
    existing = db.collection('users').where('username', '==', username).get()
    if existing:
        raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")
        
    salted_pwd = hash_password(req.password)
    
    is_super_admin = (username in ADMIN_EMAILS)
    role = 'admin' if is_super_admin else req.role
    status = 'approved' if is_super_admin else 'pending'

    db.collection('users').add({
        'username': username,
        'email': username if '@' in username else '',
        'password': salted_pwd,
        'full_name': req.full_name.strip(),
        'role': role,
        'status': status,
        'created_at': datetime.now(timezone.utc).isoformat()
    })
    
    msg = "Đăng ký thành công!" if is_super_admin else "Đăng ký thành công, vui lòng chờ Admin duyệt tài khoản."
    return {"status": "success", "message": msg}

@router.post("/login", summary="Đăng nhập và nhận JWT Token")
async def login(req: LoginRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")
        
    username = req.username.strip().lower()
    users = db.collection('users').where('username', '==', username).get()
    if not users:
        # Thử tìm theo email nếu người dùng nhập email
        users = db.collection('users').where('email', '==', username).get()
        
    if not users:
        raise HTTPException(status_code=400, detail="Sai tài khoản hoặc mật khẩu")
        
    user_doc = users[0]
    user_data = user_doc.to_dict()
    stored_pwd = user_data.get('password', '')
    
    if not verify_password(req.password, stored_pwd):
        raise HTTPException(status_code=400, detail="Sai tài khoản hoặc mật khẩu")
        
    # Tự động nâng cấp mật khẩu lên chuẩn PBKDF2 có Salt nếu đang là SHA256 cũ
    if is_legacy_hash(stored_pwd):
        new_salted = hash_password(req.password)
        db.collection('users').document(user_doc.id).update({'password': new_salted})

    # Nếu là super admin thì đảm bảo role và status là admin và approved
    if username in ADMIN_EMAILS or user_data.get('email', '').lower() in ADMIN_EMAILS:
        user_data['role'] = 'admin'
        user_data['status'] = 'approved'
        db.collection('users').document(user_doc.id).update({'role': 'admin', 'status': 'approved'})
        
    if user_data.get('status') != 'approved':
        raise HTTPException(status_code=403, detail="Tài khoản đang chờ Quản trị viên phê duyệt.")
        
    # Tạo JWT Token bảo mật có thời hạn 7 ngày
    token_payload = {
        "sub": user_doc.id,
        "username": username,
        "role": user_data.get('role', 'student'),
        "full_name": user_data.get('full_name', '')
    }
    jwt_token = create_access_token(token_payload)
    
    return {
        "status": "success",
        "token": jwt_token,
        "role": user_data.get('role', 'student'),
        "full_name": user_data.get('full_name', '')
    }
