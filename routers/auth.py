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
    class_name: Optional[str] = ""
    phone: Optional[str] = ""
    school: Optional[str] = ""

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

class SelectRoleRequest(BaseModel):
    user_id: str
    role: str
    full_name: Optional[str] = ""
    class_name: Optional[str] = ""
    phone: Optional[str] = ""
    school: Optional[str] = ""
    extra_info: Optional[str] = ""

@router.post("/google", summary="Đăng nhập hoặc đăng ký nhanh bằng Google")
async def google_login(req: GoogleAuthRequest):
    """
    Xác thực qua tài khoản Google.
    - Tài khoản Admin chỉ định luôn được cấp quyền Admin cao nhất.
    - Người dùng mới đăng nhập lần đầu sẽ phải chọn vai trò: Học sinh (dùng ngay) hoặc Giáo viên (chờ Admin duyệt).
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

    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        def _query_where(coll, field, value):
            return coll.where(filter=FieldFilter(field, '==', value))
    except ImportError:
        def _query_where(coll, field, value):
            return coll.where(field, '==', value)

    # Kiểm tra xem user đã có trong hệ thống chưa (tìm theo email hoặc username)
    users = _query_where(db.collection('users'), 'email', email).get()
    if not users:
        users = _query_where(db.collection('users'), 'username', email).get()

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

        if is_super_admin:
            final_role = 'admin'
            final_name = user_data.get('full_name') or name
        else:
            current_role = user_data.get('role')
            current_status = user_data.get('status')
            has_selected_role = bool(user_data.get('role_selected_at'))

            # QUAN TRỌNG: Tuyệt đối không mặc định tài khoản Google là giáo viên.
            # Bắt buộc chuyển sang trang chọn vai trò nếu chưa từng xác nhận chọn vai trò.
            if not has_selected_role or not current_role or current_role == 'pending_selection' or current_status == 'needs_role':
                return {
                    "status": "needs_role_selection",
                    "user_id": user_id,
                    "email": email,
                    "full_name": user_data.get('full_name') or name,
                    "class_name": user_data.get('class_name', ''),
                    "phone": user_data.get('phone', ''),
                    "school": user_data.get('school', ''),
                    "avatar": picture or user_data.get('avatar', ''),
                    "message": "Vui lòng hoàn tất thông tin cá nhân và chọn bạn là Học sinh hay Giáo viên để tiếp tục."
                }

            # Nếu là Giáo viên nhưng chưa được Admin duyệt
            if current_role == 'teacher' and current_status != 'approved':
                return {
                    "status": "pending_approval",
                    "user_id": user_id,
                    "email": email,
                    "full_name": user_data.get('full_name') or name,
                    "class_name": user_data.get('class_name', ''),
                    "phone": user_data.get('phone', ''),
                    "school": user_data.get('school', ''),
                    "role": "teacher",
                    "avatar": picture or user_data.get('avatar', ''),
                    "message": "Tài khoản Giáo viên của bạn đang chờ Quản trị viên phê duyệt."
                }

            final_role = current_role or 'student'
            final_name = user_data.get('full_name') or name
    else:
        # Người dùng Google lần đầu tiên
        if is_super_admin:
            final_role = 'admin'
            final_status = 'approved'
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
        else:
            # Người dùng mới: BẮT BUỘC lưu ở trạng thái cần chọn vai trò, KHÔNG BAO GIỜ mặc định giáo viên!
            new_user_data = {
                'username': email,
                'email': email,
                'full_name': name,
                'role': 'pending_selection',
                'status': 'needs_role',
                'class_name': '',
                'phone': '',
                'school': '',
                'role_selected_at': None,
                'profile_completed': False,
                'auth_provider': 'google',
                'avatar': picture,
                'google_id': google_sub,
                'created_at': now_iso,
                'last_login': now_iso
            }
            _, new_doc = db.collection('users').add(new_user_data)
            user_id = new_doc.id
            return {
                "status": "needs_role_selection",
                "user_id": user_id,
                "email": email,
                "full_name": name,
                "class_name": "",
                "phone": "",
                "school": "",
                "avatar": picture,
                "message": "Đăng nhập Google thành công! Vui lòng nhập thông tin cá nhân và chọn vai trò."
            }

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

@router.post("/select_role", summary="Chọn vai trò và cập nhật thông tin cá nhân")
async def select_role(req: SelectRoleRequest):
    """
    Xử lý cập nhật thông tin cá nhân (Tên, Lớp, SĐT, Trường) và vai trò sau đăng nhập Google:
    - Học sinh: Cấp quyền ngay (status=approved), trả về JWT Token.
    - Giáo viên: Đặt status=pending (Chờ Admin duyệt), không cấp quyền truy cập ngay.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")

    user_doc = db.collection('users').document(req.user_id).get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng")

    user_data = user_doc.to_dict()
    now_iso = datetime.now(timezone.utc).isoformat()
    selected_role = req.role.strip().lower()

    if selected_role not in ['student', 'teacher']:
        raise HTTPException(status_code=400, detail="Vai trò không hợp lệ. Vui lòng chọn 'student' hoặc 'teacher'.")

    email = user_data.get('email') or user_data.get('username', '')
    raw_name = (getattr(req, 'full_name', '') or '').strip()
    full_name = raw_name if raw_name else (user_data.get('full_name') or email.split('@')[0])
    class_name = (getattr(req, 'class_name', '') or '').strip()
    phone = (getattr(req, 'phone', '') or '').strip()
    school = (getattr(req, 'school', '') or '').strip()
    extra_info = (getattr(req, 'extra_info', '') or '').strip()

    update_payload = {
        'role': selected_role,
        'full_name': full_name,
        'class_name': class_name,
        'phone': phone,
        'school': school,
        'extra_info': extra_info,
        'role_selected_at': now_iso,
        'profile_completed': True
    }

    if selected_role == 'teacher':
        # Giáo viên: BẮT BUỘC chờ Quản trị viên duyệt
        update_payload['status'] = 'pending'
        db.collection('users').document(req.user_id).update(update_payload)
        return {
            "status": "pending_approval",
            "user_id": req.user_id,
            "role": "teacher",
            "email": email,
            "full_name": full_name,
            "class_name": class_name,
            "phone": phone,
            "school": school,
            "message": "Đã ghi nhận thông tin Giáo viên! Tài khoản của bạn đang chờ Quản trị viên xét duyệt trước khi có thể truy cập."
        }
    else:
        # Học sinh: Kích hoạt ngay lập tức
        update_payload['status'] = 'approved'
        db.collection('users').document(req.user_id).update(update_payload)
        token_payload = {
            "sub": req.user_id,
            "username": email,
            "role": "student",
            "full_name": full_name,
            "class_name": class_name
        }
        jwt_token = create_access_token(token_payload)
        return {
            "status": "success",
            "token": jwt_token,
            "role": "student",
            "full_name": full_name,
            "class_name": class_name,
            "phone": phone,
            "school": school,
            "email": email,
            "message": "Cập nhật thông tin thành công! Chúc bạn học tập hiệu quả."
        }

@router.get("/check_approval_status", summary="Kiểm tra trạng thái duyệt tài khoản")
async def check_approval_status(user_id: str):
    """Kiểm tra tài khoản giáo viên đã được Admin duyệt hay chưa để kích hoạt ngay mà không cần đăng nhập lại."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")

    user_doc = db.collection('users').document(user_id).get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng")

    user_data = user_doc.to_dict()
    status = user_data.get('status', 'pending')
    role = user_data.get('role', 'student')
    full_name = user_data.get('full_name', '')
    email = user_data.get('email') or user_data.get('username', '')

    if status == 'approved':
        token_payload = {
            "sub": user_id,
            "username": email,
            "role": role,
            "full_name": full_name
        }
        jwt_token = create_access_token(token_payload)
        return {
            "status": "approved",
            "token": jwt_token,
            "role": role,
            "full_name": full_name,
            "class_name": user_data.get('class_name', ''),
            "phone": user_data.get('phone', ''),
            "school": user_data.get('school', ''),
            "email": email,
            "message": "Tài khoản của bạn đã được Quản trị viên phê duyệt thành công!"
        }
    return {
        "status": "pending",
        "role": role,
        "full_name": full_name,
        "class_name": user_data.get('class_name', ''),
        "phone": user_data.get('phone', ''),
        "school": user_data.get('school', ''),
        "email": email,
        "message": "Tài khoản vẫn đang trong danh sách chờ Quản trị viên xét duyệt."
    }

@router.get("/me", summary="Lấy thông tin tài khoản hiện tại từ Token")
async def get_current_user_profile(token: Optional[str] = None):
    """
    Xác thực token người dùng, đảm bảo vai trò và trạng thái chính xác.
    Nếu tài khoản chưa hoàn tất chọn vai trò hoặc đang chờ duyệt, trả về trạng thái tương ứng.
    """
    db = get_db()
    if not token or db is None:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập hoặc phiên làm việc hết hạn")

    from core.security import get_user_from_token
    user = get_user_from_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")

    username = (user.get('username') or '').strip().lower()
    email = (user.get('email') or '').strip().lower()
    is_super_admin = (username in ADMIN_EMAILS or email in ADMIN_EMAILS)

    if not is_super_admin:
        has_selected_role = bool(user.get('role_selected_at'))
        role = user.get('role')
        status = user.get('status')

        # Nếu tài khoản Google hoặc tài khoản mới chưa từng xác nhận vai trò
        if not has_selected_role or not role or role == 'pending_selection' or status == 'needs_role':
            return {
                "status": "needs_role_selection",
                "user_id": user.get('id'),
                "email": email or username,
                "full_name": user.get('full_name', ''),
                "class_name": user.get('class_name', ''),
                "phone": user.get('phone', ''),
                "school": user.get('school', ''),
                "avatar": user.get('avatar', '')
            }

        if role == 'teacher' and status != 'approved':
            return {
                "status": "pending_approval",
                "user_id": user.get('id'),
                "email": email or username,
                "full_name": user.get('full_name', ''),
                "class_name": user.get('class_name', ''),
                "phone": user.get('phone', ''),
                "school": user.get('school', ''),
                "role": "teacher",
                "avatar": user.get('avatar', '')
            }

    return {
        "status": "success",
        "user_id": user.get('id'),
        "role": user.get('role', 'student'),
        "full_name": user.get('full_name', ''),
        "class_name": user.get('class_name', ''),
        "phone": user.get('phone', ''),
        "school": user.get('school', ''),
        "email": email or username,
        "avatar": user.get('avatar', ''),
        "status_code": user.get('status', 'approved')
    }

@router.post("/register", summary="Đăng ký tài khoản mới")
async def register(req: RegisterRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")
        
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        def _query_where(coll, field, value):
            return coll.where(filter=FieldFilter(field, '==', value))
    except ImportError:
        def _query_where(coll, field, value):
            return coll.where(field, '==', value)

    username = req.username.strip().lower()
    existing = _query_where(db.collection('users'), 'username', username).get()
    if existing:
        raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")
        
    salted_pwd = hash_password(req.password)
    
    is_super_admin = (username in ADMIN_EMAILS)
    if is_super_admin:
        role = 'admin'
        status = 'approved'
    elif req.role == 'student':
        role = 'student'
        status = 'approved' # Học sinh vào học ngay
    else:
        role = 'teacher'
        status = 'pending' # Giáo viên (hoặc giá trị khác) phải chờ admin duyệt

    now_iso = datetime.now(timezone.utc).isoformat()
    db.collection('users').add({
        'username': username,
        'email': username if '@' in username else '',
        'password': salted_pwd,
        'full_name': req.full_name.strip(),
        'role': role,
        'status': status,
        'class_name': (getattr(req, 'class_name', '') or '').strip(),
        'phone': (getattr(req, 'phone', '') or '').strip(),
        'school': (getattr(req, 'school', '') or '').strip(),
        'role_selected_at': now_iso,
        'profile_completed': True,
        'created_at': now_iso
    })
    
    if role == 'teacher':
        return {"status": "success", "message": "Đăng ký thành công! Tài khoản Giáo viên của bạn đang chờ Quản trị viên duyệt trước khi có thể đăng nhập."}
    return {"status": "success", "message": "Đăng ký thành công! Bạn có thể đăng nhập ngay."}

@router.post("/login", summary="Đăng nhập và nhận JWT Token")
async def login(req: LoginRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")
        
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        def _query_where(coll, field, value):
            return coll.where(filter=FieldFilter(field, '==', value))
    except ImportError:
        def _query_where(coll, field, value):
            return coll.where(field, '==', value)

    username = req.username.strip().lower()
    users = _query_where(db.collection('users'), 'username', username).get()
    if not users:
        # Thử tìm theo email nếu người dùng nhập email
        users = _query_where(db.collection('users'), 'email', username).get()
        
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
