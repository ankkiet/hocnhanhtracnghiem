import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from core.logging_config import get_logger
from core.security import (
    ADMIN_EMAILS,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_user_from_token,
    hash_password,
    invalidate_user_cache,
    is_legacy_hash,
    verify_password,
)
from core.state import SETTINGS_CACHE
from services.audit_service import audit_service


def _get_db():
    for mod_name in ('routers.auth', 'app.api.routes.auth'):
        auth_mod = sys.modules.get(mod_name)
        if auth_mod and hasattr(auth_mod, 'get_db'):
            func = getattr(auth_mod, 'get_db')
            if hasattr(func, 'assert_called') or hasattr(func, 'return_value'):
                try:
                    return func()
                except Exception:
                    pass
    from services.firebase_service import get_db as fb_get_db
    return fb_get_db()
logger = get_logger(__name__)


def _query_where(coll, field, value):
    """Helper truy vấn Firestore tương thích cả phiên bản cũ và mới."""
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        return coll.where(filter=FieldFilter(field, '==', value))
    except ImportError:
        return coll.where(field, '==', value)


class AuthService:
    """
    Dịch vụ quản trị Danh tính & Xác thực (Authentication Service).
    Xử lý: Đăng ký, đăng nhập, Google OAuth2, phân quyền Vai trò (Học sinh / Giáo viên / Admin),
    cấp phát mã JWT và cơ chế xác minh token Google đa tầng (Fallback 4 cấp).
    """

    def get_google_client_id(self) -> str:
        """Lấy Google Client ID từ cấu hình Firestore (có cache 10 phút) hoặc biến môi trường."""
        now = time.time()
        if 'google_auth' in SETTINGS_CACHE and (now - SETTINGS_CACHE['google_auth']['time'] < 600):
            return SETTINGS_CACHE['google_auth']['data']

        db = _get_db()
        if db:
            try:
                doc = db.collection('settings').document('google_auth').get()
                if doc.exists:
                    cid = doc.to_dict().get('client_id', '').strip()
                    if cid:
                        SETTINGS_CACHE['google_auth'] = {'time': now, 'data': cid}
                        return cid
            except Exception as e:
                logger.warning(f"AuthService: Không thể đọc google_auth từ Firestore: {e}")

        cid = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        SETTINGS_CACHE['google_auth'] = {'time': now, 'data': cid}
        return cid

    async def verify_google_payload(
        self,
        credential: Optional[str],
        access_token: Optional[str],
        expected_client_id: str = ""
    ) -> Dict[str, Any]:
        """
        Xác thực Google Token với cơ chế Fallback đa tầng (4 cấp):
        1. Firebase Admin SDK verify_id_token (nhanh và chính xác nhất cho Firebase).
        2. Google Auth library verify_oauth2_token (offline verification).
        3. Endpoint tokeninfo của Google qua HTTP (timeout 10s).
        4. Endpoint userinfo của Google bằng OAuth2 Access Token (timeout 10s).
        """
        # Cấp 1: Firebase Admin SDK
        if credential:
            try:
                import firebase_admin.auth as fb_auth
                decoded = fb_auth.verify_id_token(credential)
                if decoded and "email" in decoded:
                    logger.debug("AuthService: Xác thực Google qua Firebase Admin SDK thành công.")
                    return {
                        "email": decoded.get("email"),
                        "name": decoded.get("name") or decoded.get("email", "").split("@")[0],
                        "picture": decoded.get("picture", ""),
                        "sub": decoded.get("uid") or decoded.get("sub", "")
                    }
            except Exception as e:
                logger.debug(f"AuthService: Firebase verify_id_token không khớp ({e}), thử tiếp cấp 2...")

            # Cấp 2: Thư viện google-auth chính thức
            try:
                req = google_requests.Request()
                audience = expected_client_id if expected_client_id else None
                id_info = google_id_token.verify_oauth2_token(credential, req, audience=audience)
                if id_info and "email" in id_info:
                    logger.debug("AuthService: Xác thực Google qua google-auth offline thành công.")
                    return id_info
            except Exception as e:
                logger.debug(f"AuthService: google-auth offline không khớp ({e}), thử tiếp cấp 3...")

            # Cấp 3: Endpoint tokeninfo trực tuyến của Google
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}")
                    if res.status_code == 200:
                        info = res.json()
                        if "email" in info:
                            logger.debug("AuthService: Xác thực Google qua tokeninfo HTTP thành công.")
                            return info
            except Exception as e:
                logger.warning(f"AuthService: Lỗi kết nối Google tokeninfo ({e}), thử tiếp cấp 4...")

        # Cấp 4: OAuth2 Access Token
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
                            logger.debug("AuthService: Xác thực Google qua userinfo access_token thành công.")
                            return info
            except Exception as e:
                logger.error(f"AuthService: Lỗi kết nối Google userinfo: {e}")

        raise HTTPException(status_code=400, detail="Xác thực tài khoản Google không hợp lệ hoặc đã hết hạn.")

    async def authenticate_google(
        self,
        credential: Optional[str] = None,
        access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Quy trình đăng nhập/đăng ký bằng tài khoản Google:
        - Kiểm tra quyền Super Admin.
        - Điều hướng người dùng mới tới bước chọn vai trò (Học sinh / Giáo viên).
        - Phát hành JWT token có thời hạn 7 ngày nếu tài khoản hợp lệ.
        """
        db = _get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")

        if not credential and not access_token:
            raise HTTPException(status_code=400, detail="Thiếu thông tin xác thực Google")

        client_id = self.get_google_client_id()
        google_user = await self.verify_google_payload(credential, access_token, client_id)

        email = (google_user.get("email") or "").strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Không tìm thấy email từ tài khoản Google")

        name = google_user.get("name") or email.split("@")[0]
        picture = google_user.get("picture", "")
        google_sub = google_user.get("sub", "")

        users = _query_where(db.collection('users'), 'email', email).get()
        if not users:
            users = _query_where(db.collection('users'), 'username', email).get()

        now_iso = datetime.now(timezone.utc).isoformat()
        is_super_admin = (email in ADMIN_EMAILS)

        if users:
            user_doc = users[0]
            user_data = user_doc.to_dict()
            user_id = user_doc.id

            update_fields = {
                'avatar': picture or user_data.get('avatar', ''),
                'last_login': now_iso,
                'google_id': google_sub
            }

            if is_super_admin:
                update_fields['role'] = 'admin'
                update_fields['status'] = 'approved'
                user_data['role'] = 'admin'
                user_data['status'] = 'approved'

            db.collection('users').document(user_id).update(update_fields)
            invalidate_user_cache(user_id)

            if is_super_admin:
                final_role = 'admin'
                final_name = user_data.get('full_name') or name
            else:
                current_role = user_data.get('role')
                current_status = user_data.get('status')
                has_selected_role = bool(user_data.get('role_selected_at'))

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
                        "message": "Vui lòng hoàn tất thông tin cá nhân và chọn bạn là học sinh hay giáo viên để tiếp tục."
                    }

                if current_role == 'teacher' and current_status != 'approved':
                    # Tự động kích hoạt tài khoản Giáo viên mà không cần chờ Admin duyệt
                    try:
                        db.collection('users').document(user_id).update({'status': 'approved'})
                        invalidate_user_cache(user_id)
                        current_status = 'approved'
                    except Exception as e:
                        logger.warning(f"Không thể cập nhật status giáo viên sang approved: {e}")

                final_role = current_role or 'student'
                final_name = user_data.get('full_name') or name
        else:
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
            "class_name": user_data.get('class_name', '') if ('user_data' in locals() and user_data) else '',
            "school": (user_data.get('school', '') or user_data.get('school_name', '')) if ('user_data' in locals() and user_data) else '',
            "email": email,
            "avatar": picture
        }

    def select_role(
        self,
        user_id: str,
        role: str,
        full_name: str = "",
        class_name: str = "",
        phone: str = "",
        school: str = "",
        extra_info: str = ""
    ) -> Dict[str, Any]:
        """Cập nhật thông tin cá nhân và lựa chọn vai trò người dùng."""
        db = _get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")

        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng")

        user_data = user_doc.to_dict()
        now_iso = datetime.now(timezone.utc).isoformat()
        selected_role = role.strip().lower()

        if selected_role not in ['student', 'teacher']:
            raise HTTPException(status_code=400, detail="Vai trò không hợp lệ. Vui lòng chọn 'student' hoặc 'teacher'.")

        email = user_data.get('email') or user_data.get('username', '')
        resolved_name = full_name.strip() if full_name.strip() else (user_data.get('full_name') or email.split('@')[0])

        update_payload = {
            'role': selected_role,
            'full_name': resolved_name,
            'class_name': class_name.strip(),
            'phone': phone.strip(),
            'school': school.strip(),
            'extra_info': extra_info.strip(),
            'role_selected_at': now_iso,
            'profile_completed': True
        }

        update_payload['status'] = 'approved'
        db.collection('users').document(user_id).update(update_payload)
        invalidate_user_cache(user_id)
        token_payload = {
            "sub": user_id,
            "username": email,
            "role": selected_role,
            "full_name": resolved_name,
            "class_name": class_name,
            "school": school
        }
        jwt_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)
        role_msg = "Đăng ký vai trò giáo viên thành công! Bạn có thể sử dụng tất cả tính năng ngay bây giờ." if selected_role == 'teacher' else "Cập nhật thông tin thành công! Chúc bạn học tập hiệu quả."
        return {
            "status": "success",
            "token": jwt_token,
            "access_token": jwt_token,
            "refresh_token": refresh_token,
            "role": selected_role,
            "full_name": resolved_name,
            "class_name": class_name,
            "phone": phone,
            "school": school,
            "email": email,
            "message": role_msg
        }

    def check_approval_status(self, user_id: str) -> Dict[str, Any]:
        """Kiểm tra trạng thái phê duyệt của tài khoản giáo viên."""
        db = _get_db()
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

        if status != 'approved':
            try:
                db.collection('users').document(user_id).update({'status': 'approved'})
                invalidate_user_cache(user_id)
                status = 'approved'
            except Exception as e:
                logger.warning(f"Không thể cập nhật status giáo viên: {e}")
                status = 'approved'

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
            "message": "Tài khoản của bạn đã được kích hoạt thành công!"
        }

    def get_user_profile(self, token: Optional[str]) -> Dict[str, Any]:
        """Xác thực token người dùng và trả về hồ sơ tài khoản."""
        db = _get_db()
        if not token or db is None:
            raise HTTPException(status_code=401, detail="Chưa đăng nhập hoặc phiên làm việc hết hạn")

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
                # Tự động duyệt tài khoản giáo viên
                try:
                    db.collection('users').document(user.get('id')).update({'status': 'approved'})
                    invalidate_user_cache(user.get('id'))
                    status = 'approved'
                except Exception as e:
                    logger.warning(f"Không thể cập nhật status giáo viên sang approved: {e}")
                    status = 'approved'

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

    def register_user(
        self,
        username: str,
        password: str,
        full_name: str,
        role: str,
        class_name: str = "",
        phone: str = "",
        school: str = ""
    ) -> Dict[str, Any]:
        """Đăng ký tài khoản mới bằng mật khẩu."""
        db = _get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")

        clean_username = username.strip().lower()
        existing = _query_where(db.collection('users'), 'username', clean_username).get()
        if existing:
            raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")

        # Kiểm tra trùng email nếu username có dạng email
        if "@" in clean_username:
            existing_email = _query_where(db.collection('users'), 'email', clean_username).get()
            if existing_email:
                raise HTTPException(status_code=400, detail="Email này đã được sử dụng")

        is_super_admin = (clean_username in ADMIN_EMAILS)
        if is_super_admin:
            final_role = 'admin'
            final_status = 'approved'
        elif role.strip().lower() == 'student':
            final_role = 'student'
            final_status = 'approved'
        else:
            final_role = 'teacher'
            final_status = 'approved'

        hashed_pwd = hash_password(password)
        now_iso = datetime.now(timezone.utc).isoformat()

        user_data = {
            'username': clean_username,
            'email': clean_username if "@" in clean_username else "",
            'password_hash': hashed_pwd,
            'full_name': full_name.strip(),
            'role': final_role,
            'status': final_status,
            'class_name': class_name.strip(),
            'phone': phone.strip(),
            'school': school.strip(),
            'role_selected_at': now_iso,
            'consent_pdpd_at': now_iso,
            'consent_terms_version': '2026.11-ND13',
            'profile_completed': True,
            'auth_provider': 'password',
            'created_at': now_iso,
            'last_login': now_iso
        }

        db.collection('users').add(user_data)

        return {
            "status": "success",
            "message": "Đăng ký thành công! Bạn có thể đăng nhập ngay."
        }

    def login_user(self, username: str, password: str) -> Dict[str, Any]:
        """Xác thực đăng nhập tài khoản bằng mật khẩu với cơ chế nâng cấp hash cũ."""
        db = _get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")

        clean_username = username.strip().lower()
        users = _query_where(db.collection('users'), 'username', clean_username).get()
        if not users and "@" in clean_username:
            users = _query_where(db.collection('users'), 'email', clean_username).get()

        if not users:
            raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

        user_doc = users[0]
        user_data = user_doc.to_dict()
        user_id = user_doc.id

        stored_hash = user_data.get('password_hash') or user_data.get('password') or ''
        if not verify_password(password, stored_hash):
            raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

        # Nâng cấp mật khẩu legacy hash sang Argon2/PBKDF2 bảo mật
        if is_legacy_hash(stored_hash):
            try:
                new_hash = hash_password(password)
                db.collection('users').document(user_id).update({'password_hash': new_hash})
                invalidate_user_cache(user_id)
                logger.info(f"AuthService: Đã tự động nâng cấp password hash cho user {clean_username}.")
            except Exception as e:
                logger.warning(f"AuthService: Không thể nâng cấp hash: {e}")

        email = user_data.get('email') or clean_username
        is_super_admin = (clean_username in ADMIN_EMAILS or email in ADMIN_EMAILS)

        if is_super_admin:
            role = 'admin'
            status = 'approved'
        else:
            role = user_data.get('role', 'student')
            status = user_data.get('status', 'approved')

        if role == 'teacher' and status != 'approved':
            # Tự động kích hoạt tài khoản Giáo viên mà không cần chờ Admin duyệt
            try:
                db.collection('users').document(user_id).update({'status': 'approved'})
                invalidate_user_cache(user_id)
                status = 'approved'
            except Exception as e:
                logger.warning(f"Không thể cập nhật status giáo viên sang approved: {e}")
                status = 'approved'

        now_iso = datetime.now(timezone.utc).isoformat()
        db.collection('users').document(user_id).update({'last_login': now_iso})
        invalidate_user_cache(user_id)

        token_payload = {
            "sub": user_id,
            "username": clean_username,
            "role": role,
            "full_name": user_data.get('full_name', '')
        }
        jwt_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)

        audit_service.record_event(
            action="USER_LOGIN",
            actor_id=user_id,
            actor_role=role,
            details={"username": clean_username}
        )

        return {
            "status": "success",
            "token": jwt_token,
            "access_token": jwt_token,
            "refresh_token": refresh_token,
            "role": role,
            "full_name": user_data.get('full_name', ''),
            "avatar": user_data.get('avatar', ''),
            "class_name": user_data.get('class_name', ''),
            "school": user_data.get('school', '') or user_data.get('school_name', ''),
            "message": "Đăng nhập thành công!"
        }

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Làm mới Access Token bằng Refresh Token hợp lệ."""
        payload = decode_refresh_token(refresh_token)
        if not payload or "sub" not in payload:
            raise HTTPException(status_code=401, detail="Refresh Token không hợp lệ hoặc đã hết hạn")

        user_id = payload["sub"]
        token_payload = {
            "sub": user_id,
            "username": payload.get("username", ""),
            "role": payload.get("role", "student"),
            "full_name": payload.get("full_name", "")
        }
        new_access = create_access_token(token_payload)
        new_refresh = create_refresh_token(token_payload)

        return {
            "status": "success",
            "token": new_access,
            "access_token": new_access,
            "refresh_token": new_refresh,
            "message": "Làm mới phiên làm việc thành công"
        }

    def delete_my_account(self, token: str, reason: str = "") -> Dict[str, Any]:
        """
        Thực thi Quyền xóa dữ liệu & Rút lại sự đồng ý của chủ thể dữ liệu
        theo Điều 9 và Điều 16 Nghị định 13/2023/NĐ-CP về Bảo vệ dữ liệu cá nhân.
        """
        if not token:
            raise HTTPException(status_code=401, detail="Thiếu mã xác thực (Token)")

        user_info = get_user_from_token(token)
        if not user_info:
            raise HTTPException(status_code=401, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn")

        user_id = user_info.get("id") or user_info.get("user_id")
        role = user_info.get("role", "student")
        username = (user_info.get("username") or user_info.get("email") or "").lower()

        if role == "admin" or username in ADMIN_EMAILS:
            raise HTTPException(
                status_code=403,
                detail="Tài khoản quản trị viên hệ thống không thể tự xóa qua cổng người dùng."
            )

        db = _get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")

        try:
            # 1. Xóa lịch sử làm bài và tiến độ lưu tạm của người dùng (nếu có)
            for coll_name, field_name in [
                ("student_history", "user_id"),
                ("student_progress", "user_id"),
            ]:
                try:
                    docs = _query_where(db.collection(coll_name), field_name, user_id).get()
                    for doc in docs:
                        db.collection(coll_name).document(doc.id).delete()
                except Exception as sub_err:
                    logger.warning(f"AuthService: Không thể dọn {coll_name} của {user_id}: {sub_err}")

            # 2. Xóa hồ sơ tài khoản cá nhân khỏi collection users
            db.collection("users").document(user_id).delete()
            invalidate_user_cache(user_id)

            audit_service.record_event(
                action="USER_SELF_DELETE_PDPD",
                actor_id=user_id,
                actor_role=role,
                details={"reason": (reason or "User requested erasure under Decree 13/2023/ND-CP")[:200]}
            )
        except Exception as e:
            logger.error(f"AuthService: Lỗi khi xóa dữ liệu cá nhân user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Không thể xóa dữ liệu tài khoản lúc này, vui lòng thử lại.")

        return {
            "status": "success",
            "message": "Đã xóa vĩnh viễn tài khoản và toàn bộ dữ liệu cá nhân của bạn theo Nghị định 13/2023/NĐ-CP."
        }

    def submit_legal_report(self, req_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tiếp nhận báo cáo vi phạm bản quyền (Điều 198b Luật SHTT 2022),
        nội dung vi phạm (Nghị định 147/2024/NĐ-CP) hoặc yêu cầu quyền dữ liệu cá nhân (NĐ 13/2023/NĐ-CP).
        """
        description = (req_data.get("description") or "").strip()
        reporter_email = (req_data.get("reporter_email") or "").strip()
        if len(description) < 5:
            raise HTTPException(status_code=400, detail="Vui lòng mô tả chi tiết nội dung cần báo cáo hoặc hỗ trợ.")

        now_iso = datetime.now(timezone.utc).isoformat()
        ticket_code = f"HNTN-{int(time.time())}"
        record = {
            "ticket_code": ticket_code,
            "report_type": (req_data.get("report_type") or "copyright").strip(),
            "quiz_id": (req_data.get("quiz_id") or "").strip(),
            "reporter_name": (req_data.get("reporter_name") or "Ẩn danh").strip()[:120],
            "reporter_email": reporter_email[:150],
            "reporter_role": (req_data.get("reporter_role") or "other").strip()[:50],
            "description": description[:3000],
            "consent_pdpd": bool(req_data.get("consent_pdpd", True)),
            "status": "pending_review",
            "created_at": now_iso,
        }

        db = _get_db()
        if db is not None:
            try:
                db.collection("legal_reports").add(record)
            except Exception as e:
                logger.warning(f"AuthService: Không thể ghi legal_reports lên Firestore: {e}")

        audit_service.record_event(
            action="LEGAL_REPORT_SUBMITTED",
            actor_id=reporter_email or "anonymous",
            actor_role=record["reporter_role"],
            details={
                "ticket_code": ticket_code,
                "report_type": record["report_type"],
                "quiz_id": record["quiz_id"],
            }
        )

        return {
            "status": "success",
            "ticket_code": ticket_code,
            "message": f"Đã tiếp nhận yêu cầu (Mã hồ sơ: {ticket_code}). Ban quản trị sẽ thẩm tra và xử lý trong vòng 24 - 48 giờ làm việc theo quy định pháp luật."
        }


# Thực thể singleton
auth_service = AuthService()
