import os
import sys
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from core.security import hash_password

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

db = None
firebase_init_error = None

def init_firebase():
    """Khởi tạo kết nối Firebase Firestore và tạo tài khoản Admin mặc định nếu chưa có."""
    global db, firebase_init_error
    if db is not None:
        return db
        
    try:
        # 1. Thử lấy chìa khóa từ Biến môi trường (Dành cho Koyeb)
        firebase_env = os.environ.get("FIREBASE_JSON")
        
        if firebase_env:
            try:
                # Dùng strict=False để cho phép ký tự xuống dòng (raw newlines) thường gặp trên Koyeb
                cred_dict = json.loads(firebase_env, strict=False)
                cred = credentials.Certificate(cred_dict)
                logger.info(f"Đang kết nối Firebase bằng Biến môi trường (Koyeb)... Project: {cred.project_id}, Email: {cred.service_account_email}")
            except Exception as e:
                # Fallback: Nếu JSON có chứa raw newlines khiến json.loads() bó tay kể cả khi strict=False
                try:
                    firebase_env_fixed = firebase_env.replace('\n', '\\n')
                    cred_dict = json.loads(firebase_env_fixed)
                    cred = credentials.Certificate(cred_dict)
                    logger.info(f"Đang kết nối Firebase (Koyeb fallback thay thế newline)... Project: {cred.project_id}, Email: {cred.service_account_email}")
                except Exception as e2:
                    firebase_init_error = f"Lỗi parse FIREBASE_JSON: {str(e)} | Fallback error: {str(e2)}"
                    logger.error(firebase_init_error)
                    return None
        else:
            # 2. Đọc từ file vật lý (Dành cho Local)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cert_path = os.path.join(base_dir, "firebase-adminsdk.json")
            if not os.path.exists(cert_path):
                firebase_init_error = f"Không tìm thấy tệp {cert_path} và biến môi trường FIREBASE_JSON trống"
                logger.warning(firebase_init_error)
                return None
            cred = credentials.Certificate(cert_path)
            print("Đang kết nối Firebase bằng tệp vật lý (Local)...")
            
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://hocnhanhtracnghiem-default-rtdb.asia-southeast1.firebasedatabase.app/'
            })
        db = firestore.client()
        
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
            def query_where(collection_ref, field, value):
                return collection_ref.where(filter=FieldFilter(field, '==', value))
        except ImportError:
            def query_where(collection_ref, field, value):
                return collection_ref.where(field, '==', value)

        # Khởi tạo Admin mặc định NẾU CHƯA TỒN TẠI (Không ghi đè khi đã có)
        users = query_where(db.collection('users'), 'username', 'admin').get()
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

        # Đảm bảo tài khoản Quản trị viên kiet0905478167@gmail.com luôn tồn tại và có quyền Admin cao nhất
        admin_email = "kiet0905478167@gmail.com"
        kiet_users = query_where(db.collection('users'), 'username', admin_email).get()
        if not kiet_users:
            kiet_by_email = query_where(db.collection('users'), 'email', admin_email).get()
            if kiet_by_email:
                db.collection('users').document(kiet_by_email[0].id).update({
                    'role': 'admin',
                    'status': 'approved'
                })
            else:
                kiet_pwd = hash_password('kiet@123456')
                db.collection('users').add({
                    'username': admin_email,
                    'email': admin_email,
                    'password': kiet_pwd,
                    'full_name': 'Admin Kiệt',
                    'role': 'admin',
                    'status': 'approved'
                })
                print(f"Đã khởi tạo tài khoản Quản trị viên {admin_email}.")
        else:
            db.collection('users').document(kiet_users[0].id).update({
                'role': 'admin',
                'status': 'approved'
            })
            
        return db
        
    except Exception as e:
        firebase_init_error = f"Lỗi khởi tạo DB: {str(e)}"
        print(f"CẢNH BÁO: Không thể khởi tạo Firebase. Chi tiết: {e}")
        db = None
        return None

def get_db():
    if db is None:
        return init_firebase()
    return db
