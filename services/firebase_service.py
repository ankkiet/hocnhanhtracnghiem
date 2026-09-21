import os
import sys
import json
import firebase_admin
from firebase_admin import credentials, firestore
from core.security import hash_password

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

db = None

def init_firebase():
    """Khởi tạo kết nối Firebase Firestore và tạo tài khoản Admin mặc định nếu chưa có."""
    global db
    if db is not None:
        return db
        
    try:
        # 1. Thử lấy chìa khóa từ Biến môi trường (Dành cho Koyeb)
        firebase_env = os.environ.get("FIREBASE_JSON")
        
        if firebase_env:
            cred_dict = json.loads(firebase_env)
            cred = credentials.Certificate(cred_dict)
            print("Đang kết nối Firebase bằng Biến môi trường (Koyeb)...")
        else:
            # 2. Đọc từ file vật lý (Dành cho Local)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cert_path = os.path.join(base_dir, "firebase-adminsdk.json")
            if not os.path.exists(cert_path):
                print(f"CẢNH BÁO: Không tìm thấy tệp cấu hình Firebase tại: {cert_path}")
                return None
            cred = credentials.Certificate(cert_path)
            print("Đang kết nối Firebase bằng tệp vật lý (Local)...")
            
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        # Khởi tạo Admin mặc định NẾU CHƯA TỒN TẠI (Không ghi đè khi đã có)
        users = db.collection('users').where('username', '==', 'admin').get()
        if not users:
            admin_pwd_hash = hash_password('a@a@ankk')
            db.collection('users').add({
                'username': 'admin',
                'password': admin_pwd_hash,
                'full_name': 'Quản trị viên (Admin)',
                'role': 'admin',
                'status': 'approved'
            })
            print("Đã khởi tạo tài khoản Quản trị viên (Admin) mặc định.")
            
        return db
        
    except Exception as e:
        print(f"CẢNH BÁO: Không thể khởi tạo Firebase. Chi tiết: {e}")
        db = None
        return None

def get_db():
    global db
    if db is None:
        return init_firebase()
    return db
