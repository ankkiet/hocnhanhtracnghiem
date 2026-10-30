import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.security import hash_password, invalidate_user_cache, verify_admin_access, verify_password
from core.state import SETTINGS_CACHE
from services.audit_service import audit_service
from services.firebase_service import get_db

router = APIRouter(prefix="/api/admin", tags=["Admin Management"])


class SetApiKeyRequest(BaseModel):
    admin_token: str
    api_keys: List[str]


class SetGoogleClientIdRequest(BaseModel):
    admin_token: str
    client_id: str


class ApproveUserRequest(BaseModel):
    admin_token: str
    user_id: str


class ChangePasswordRequest(BaseModel):
    admin_token: str
    old_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    admin_token: str
    user_id: str
    new_password: str


@router.get("/users", summary="Lấy danh sách user (Admin)")
async def get_all_users(admin_token: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    verify_admin_access(admin_token, db)
        
    users = db.collection('users').get()
    res = []
    for u in users:
        d = u.to_dict()
        res.append({
            'id': u.id,
            'username': d.get('username'),
            'email': d.get('email') or d.get('username'),
            'full_name': d.get('full_name'),
            'role': d.get('role'),
            'status': d.get('status'),
            'class_name': d.get('class_name', ''),
            'phone': d.get('phone', ''),
            'school': d.get('school', ''),
            'created_at': d.get('created_at', '')
        })
    return {"status": "success", "data": res}


@router.post("/approve", summary="Duyệt user (Admin)")
async def approve_user(req: ApproveUserRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    admin_user, admin_uid = verify_admin_access(req.admin_token, db)
    db.collection('users').document(req.user_id).update({'status': 'approved'})
    invalidate_user_cache(req.user_id)

    audit_service.record_event(
        action="ADMIN_APPROVE_USER",
        actor_id=admin_uid,
        actor_role="admin",
        target_id=req.user_id,
        details={"status": "approved"}
    )
    return {"status": "success"}


@router.post("/delete", summary="Xóa user (Admin)")
async def delete_user(req: ApproveUserRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    admin_user, admin_uid = verify_admin_access(req.admin_token, db)
    db.collection('users').document(req.user_id).delete()
    invalidate_user_cache(req.user_id)

    audit_service.record_event(
        action="ADMIN_DELETE_USER",
        actor_id=admin_uid,
        actor_role="admin",
        target_id=req.user_id
    )
    return {"status": "success"}


@router.post("/change_password", summary="Đổi mật khẩu (Admin)")
async def change_admin_password(req: ChangePasswordRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    admin_user, admin_uid = verify_admin_access(req.admin_token, db)
    
    stored_password = admin_user.get('password', '') or admin_user.get('password_hash', '')
    if not verify_password(req.old_password, stored_password):
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác")
        
    new_salted = hash_password(req.new_password)
    db.collection('users').document(admin_uid).update({'password': new_salted, 'password_hash': new_salted})
    invalidate_user_cache(admin_uid)

    audit_service.record_event(
        action="ADMIN_CHANGE_PASSWORD",
        actor_id=admin_uid,
        actor_role="admin"
    )
    return {"status": "success"}


@router.post("/reset_password", summary="Khôi phục mật khẩu user (Admin)")
async def reset_user_password(req: ResetPasswordRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    admin_user, admin_uid = verify_admin_access(req.admin_token, db)
    
    new_salted = hash_password(req.new_password)
    db.collection('users').document(req.user_id).update({'password': new_salted, 'password_hash': new_salted})
    invalidate_user_cache(req.user_id)

    audit_service.record_event(
        action="ADMIN_RESET_USER_PASSWORD",
        actor_id=admin_uid,
        actor_role="admin",
        target_id=req.user_id
    )
    return {"status": "success"}


@router.post("/set_api_key", summary="Cài đặt API Key chung (Admin)")
async def set_api_key(req: SetApiKeyRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    admin_user, admin_uid = verify_admin_access(req.admin_token, db)
    db.collection('settings').document('gemini').set({'api_keys': req.api_keys})
    SETTINGS_CACHE['gemini'] = {'time': time.time(), 'data': req.api_keys}

    audit_service.record_event(
        action="ADMIN_SET_API_KEY",
        actor_id=admin_uid,
        actor_role="admin",
        details={"keys_count": len(req.api_keys)}
    )
    return {"status": "success"}


@router.get("/get_api_key", summary="Lấy API Key chung (Admin)")
async def get_api_key(admin_token: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    verify_admin_access(admin_token, db)
    now = time.time()
    if 'gemini' in SETTINGS_CACHE and (now - SETTINGS_CACHE['gemini']['time'] < 600):
        return {"status": "success", "api_keys": SETTINGS_CACHE['gemini']['data']}
        
    settings_doc = db.collection('settings').document('gemini').get()
    api_keys = settings_doc.to_dict().get('api_keys', []) if settings_doc.exists else []
    SETTINGS_CACHE['gemini'] = {'time': now, 'data': api_keys}
    return {"status": "success", "api_keys": api_keys}


@router.post("/set_google_client_id", summary="Cài đặt Google Client ID (Admin)")
async def set_google_client_id(req: SetGoogleClientIdRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    admin_user, admin_uid = verify_admin_access(req.admin_token, db)
    client_id_val = req.client_id.strip()
    db.collection('settings').document('google_auth').set({'client_id': client_id_val}, merge=True)
    SETTINGS_CACHE['google_auth'] = {'time': time.time(), 'data': client_id_val}

    audit_service.record_event(
        action="ADMIN_SET_GOOGLE_CLIENT_ID",
        actor_id=admin_uid,
        actor_role="admin"
    )
    return {"status": "success", "message": "Đã lưu Google Client ID thành công"}


@router.get("/get_google_client_id", summary="Lấy Google Client ID (Admin)")
async def get_google_client_id(admin_token: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    verify_admin_access(admin_token, db)
    now = time.time()
    if 'google_auth' in SETTINGS_CACHE and (now - SETTINGS_CACHE['google_auth']['time'] < 600):
        return {"status": "success", "client_id": SETTINGS_CACHE['google_auth']['data']}
        
    doc = db.collection('settings').document('google_auth').get()
    client_id = doc.to_dict().get('client_id', '') if doc.exists else ''
    if not client_id:
        import os
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    SETTINGS_CACHE['google_auth'] = {'time': now, 'data': client_id}
    return {"status": "success", "client_id": client_id}


@router.get("/audit_logs", summary="Lấy nhật ký kiểm toán hệ thống (Admin)")
async def get_audit_logs(admin_token: str, limit: int = 50, action: Optional[str] = None):
    """Truy xuất nhật ký kiểm toán các thao tác nhạy cảm dành riêng cho Admin."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    verify_admin_access(admin_token, db)
    logs = audit_service.get_logs(limit=limit, action_filter=action)
    return {
        "status": "success",
        "total": len(logs),
        "data": logs
    }
