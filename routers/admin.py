from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.firebase_service import get_db
from core.security import get_user_from_token, hash_password, verify_password

router = APIRouter(prefix="/api/admin", tags=["Admin Management"])

class SetApiKeyRequest(BaseModel):
    admin_token: str
    api_keys: List[str]

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

def verify_admin_access(token: str, db) -> tuple:
    """Xác minh quyền quản trị viên (Admin)."""
    user = get_user_from_token(token, db)
    if not user or user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Không có quyền truy cập Quản trị viên.")
    return user, user['id']

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
            'full_name': d.get('full_name'),
            'role': d.get('role'),
            'status': d.get('status')
        })
    return {"status": "success", "data": res}

@router.post("/approve", summary="Duyệt user (Admin)")
async def approve_user(req: ApproveUserRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    verify_admin_access(req.admin_token, db)
    db.collection('users').document(req.user_id).update({'status': 'approved'})
    return {"status": "success"}

@router.post("/delete", summary="Xóa user (Admin)")
async def delete_user(req: ApproveUserRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    verify_admin_access(req.admin_token, db)
    db.collection('users').document(req.user_id).delete()
    return {"status": "success"}

@router.post("/change_password", summary="Đổi mật khẩu (Admin)")
async def change_admin_password(req: ChangePasswordRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    admin_user, admin_uid = verify_admin_access(req.admin_token, db)
    
    stored_password = admin_user.get('password', '')
    if not verify_password(req.old_password, stored_password):
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác")
        
    new_salted = hash_password(req.new_password)
    db.collection('users').document(admin_uid).update({'password': new_salted})
    return {"status": "success"}

@router.post("/reset_password", summary="Khôi phục mật khẩu user (Admin)")
async def reset_user_password(req: ResetPasswordRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    verify_admin_access(req.admin_token, db)
    
    new_salted = hash_password(req.new_password)
    db.collection('users').document(req.user_id).update({'password': new_salted})
    return {"status": "success"}

@router.post("/set_api_key", summary="Cài đặt API Key chung (Admin)")
async def set_api_key(req: SetApiKeyRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    verify_admin_access(req.admin_token, db)
    db.collection('settings').document('gemini').set({'api_keys': req.api_keys})
    return {"status": "success"}

@router.get("/get_api_key", summary="Lấy API Key chung (Admin)")
async def get_api_key(admin_token: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Lỗi DB")
        
    verify_admin_access(admin_token, db)
    settings_doc = db.collection('settings').document('gemini').get()
    api_keys = settings_doc.to_dict().get('api_keys', []) if settings_doc.exists else []
    return {"status": "success", "api_keys": api_keys}
