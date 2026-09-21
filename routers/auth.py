from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.firebase_service import get_db
from core.security import hash_password, verify_password, is_legacy_hash, create_access_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str

class LoginRequest(BaseModel):
    username: str
    password: str

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
    db.collection('users').add({
        'username': username,
        'password': salted_pwd,
        'full_name': req.full_name.strip(),
        'role': req.role,
        'status': 'pending'
    })
    return {"status": "success", "message": "Đăng ký thành công, vui lòng chờ Admin duyệt tài khoản."}

@router.post("/login", summary="Đăng nhập và nhận JWT Token")
async def login(req: LoginRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu")
        
    username = req.username.strip().lower()
    users = db.collection('users').where('username', '==', username).get()
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
