import os
import sys
import json
import base64
import logging
import threading
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
_init_lock = threading.Lock()
_admin_seeded = False


def _parse_service_account(raw_input: str) -> dict:
    """
    Phân tích và làm sạch dữ liệu Service Account JSON từ mọi định dạng:
    - Minified JSON
    - Multiline JSON với raw newlines
    - JSON bị bọc dấu ngoặc đơn hoặc ngoặc kép do Koyeb/Shell UI
    - Chuỗi Base64
    - Private key chứa ký tự thoát '\\n' thay vì ký tự xuống dòng thực tế
    - JSON có lỗi cú pháp nhẹ (sử dụng json_repair)
    """
    if not raw_input or not isinstance(raw_input, str):
        raise ValueError("Chuỗi thông tin xác thực Firebase rỗng hoặc không hợp lệ")

    s = raw_input.strip()
    s = s.lstrip('\ufeff')  # Loại bỏ ký tự BOM nếu có

    # Gỡ bỏ các dấu nháy đơn hoặc nháy kép bọc ngoài cùng (do Koyeb Web Dashboard hoặc shell thêm vào)
    while len(s) > 2 and (
        (s.startswith("'") and s.endswith("'")) or
        (s.startswith('"') and s.endswith('"') and not s.endswith('\\"'))
    ):
        s = s[1:-1].strip()

    # Nhận diện chuỗi Base64 nếu không bắt đầu bằng '{' và độ dài lớn
    if not s.startswith('{') and len(s) > 40:
        try:
            decoded = base64.b64decode(s).decode('utf-8', errors='ignore')
            if 'service_account' in decoded or 'private_key' in decoded:
                s = decoded.strip()
                while len(s) > 2 and (
                    (s.startswith("'") and s.endswith("'")) or
                    (s.startswith('"') and s.endswith('"'))
                ):
                    s = s[1:-1].strip()
        except Exception:
            pass

    cred_dict = None
    parse_errors = []

    # Thử 1: JSON parser chuẩn với strict=False
    try:
        cred_dict = json.loads(s, strict=False)
    except Exception as e1:
        parse_errors.append(f"json.loads: {e1}")

    # Thử 2: Trường hợp bị double JSON-encoded (chuỗi string chứa chuỗi JSON)
    if isinstance(cred_dict, str):
        try:
            cred_dict = json.loads(cred_dict, strict=False)
        except Exception as e_inner:
            parse_errors.append(f"double-json: {e_inner}")

    # Thử 3: json_repair để vá JSON hỏng cú pháp / thừa dấu phẩy
    if not isinstance(cred_dict, dict):
        try:
            import json_repair
            repaired = json_repair.loads(s)
            if isinstance(repaired, dict):
                cred_dict = repaired
            elif isinstance(repaired, str):
                cred_dict = json_repair.loads(repaired)
        except Exception as e3:
            parse_errors.append(f"json_repair: {e3}")

    if not isinstance(cred_dict, dict):
        raise ValueError(f"Không thể giải mã JSON Service Account: {'; '.join(parse_errors)}")

    # Chuẩn hóa Private Key PEM (YẾU TỐ QUYẾT ĐỊNH CHO KOYEB / DOCKER)
    # PEM format bắt buộc phải dùng ký tự xuống dòng thực tế '\n', không được để chuỗi '\\n'
    pk = cred_dict.get('private_key')
    if isinstance(pk, str):
        if '\\n' in pk:
            pk = pk.replace('\\n', '\n')
        pk = pk.replace('\r\n', '\n').replace('\r', '\n')
        cred_dict['private_key'] = pk

    return cred_dict


def _get_credentials_object():
    """Tìm nạp và khởi tạo Google Credentials từ biến môi trường hoặc tệp vật lý."""
    # Quét tất cả các tên biến môi trường phổ biến người dùng thường đặt trên Koyeb / VPS
    env_keys = [
        "FIREBASE_JSON",
        "FIREBASE_CREDENTIALS",
        "FIREBASE_SERVICE_ACCOUNT",
        "FIREBASE_ADMINSDK",
        "FIREBASE_ADMINSDK_JSON",
        "FIREBASE_KEY",
        "FIREBASE_CONFIG",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "FIREBASE_JSON_BASE64",
        "FIREBASE_BASE64",
        "FIREBASE_CREDENTIALS_BASE64"
    ]

    for key in env_keys:
        val = os.environ.get(key)
        if val and val.strip():
            raw_val = val.strip()
            # Nếu giá trị là đường dẫn file tồn tại trên hệ điều hành
            if os.path.isfile(raw_val):
                logger.info(f"Đang đọc Firebase Credentials từ file cấu hình trong biến môi trường {key}: {raw_val}")
                with open(raw_val, "r", encoding="utf-8") as f:
                    content = f.read()
                cred_dict = _parse_service_account(content)
                return credentials.Certificate(cred_dict), f"file_via_env:{key}"
            else:
                logger.info(f"Đang nạp Firebase Credentials từ biến môi trường {key} (Koyeb)...")
                cred_dict = _parse_service_account(raw_val)
                return credentials.Certificate(cred_dict), f"env:{key}"

    # Quét các file vật lý chuẩn (Local / Docker secret mount)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_candidates = [
        os.path.join(base_dir, "firebase-adminsdk.json"),
        "/secrets/firebase-adminsdk.json",
        "/secrets/firebase.json",
        "/etc/secrets/firebase-adminsdk.json",
        "/etc/secrets/firebase.json",
        os.path.join(base_dir, "secrets", "firebase-adminsdk.json")
    ]

    for file_path in file_candidates:
        if os.path.isfile(file_path):
            logger.info(f"Đang kết nối Firebase bằng tệp vật lý: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            cred_dict = _parse_service_account(content)
            return credentials.Certificate(cred_dict), f"file:{file_path}"

    raise FileNotFoundError(
        "Không tìm thấy cấu hình Firebase! Hãy cấu hình biến môi trường 'FIREBASE_JSON' trên Koyeb "
        "hoặc đặt tệp 'firebase-adminsdk.json' vào thư mục gốc của dự án."
    )


def _seed_default_admins(db_client):
    """
    Khởi tạo tài khoản Admin mặc định một cách an toàn.
    Chạy trong khối bảo vệ riêng biệt; nếu có lỗi mạng ban đầu sẽ KHÔNG làm hủy bỏ kết nối db.
    """
    global _admin_seeded
    if _admin_seeded or db_client is None:
        return

    try:
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
            def query_where(collection_ref, field, value):
                return collection_ref.where(filter=FieldFilter(field, '==', value))
        except ImportError:
            def query_where(collection_ref, field, value):
                return collection_ref.where(field, '==', value)

        # 1. Khởi tạo Admin mặc định NẾU CHƯA TỒN TẠI
        users = query_where(db_client.collection('users'), 'username', 'admin').get()
        if not users:
            admin_pwd_hash = hash_password('a@a@ankk')
            db_client.collection('users').add({
                'username': 'admin',
                'password': admin_pwd_hash,
                'full_name': 'Quản trị viên (Admin)',
                'role': 'admin',
                'status': 'approved'
            })
            logger.info("Đã khởi tạo tài khoản Quản trị viên (Admin) mặc định.")

        # 2. Đảm bảo tài khoản Quản trị viên kiet0905478167@gmail.com luôn có quyền Admin cao nhất
        admin_email = "kiet0905478167@gmail.com"
        kiet_users = query_where(db_client.collection('users'), 'username', admin_email).get()
        if not kiet_users:
            kiet_by_email = query_where(db_client.collection('users'), 'email', admin_email).get()
            if kiet_by_email:
                db_client.collection('users').document(kiet_by_email[0].id).update({
                    'role': 'admin',
                    'status': 'approved'
                })
            else:
                kiet_pwd = hash_password('kiet@123456')
                db_client.collection('users').add({
                    'username': admin_email,
                    'email': admin_email,
                    'password': kiet_pwd,
                    'full_name': 'Admin Kiệt',
                    'role': 'admin',
                    'status': 'approved'
                })
                logger.info(f"Đã khởi tạo tài khoản Quản trị viên {admin_email}.")
        else:
            db_client.collection('users').document(kiet_users[0].id).update({
                'role': 'admin',
                'status': 'approved'
            })

        _admin_seeded = True
    except Exception as e:
        logger.warning(f"Lưu ý: Chưa thể đồng bộ tài khoản admin ngay lúc này ({e}), cơ sở dữ liệu vẫn sẵn sàng hoạt động.")


def init_firebase():
    """Khởi tạo kết nối Firebase Firestore an toàn, chống crash và hỗ trợ đa nền tảng (Koyeb/Docker/Local)."""
    global db, firebase_init_error
    if db is not None:
        return db

    with _init_lock:
        if db is not None:
            return db

        try:
            cred, source = _get_credentials_object()

            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)

            app = firebase_admin.get_app()
            db_client = firestore.client(app=app)

            # Gán kết nối DB ngay lập tức
            db = db_client
            firebase_init_error = None

            logger.info(f"Đã kết nối Firebase Firestore thành công! Nguồn: {source}, Project: {cred.project_id}, Email: {cred.service_account_email}")

            # Đồng bộ admin trong khối an toàn
            _seed_default_admins(db)

            return db

        except Exception as e:
            firebase_init_error = str(e)
            logger.error(f"CẢNH BÁO: Không thể khởi tạo Firebase ({e})")
            return None


def get_db():
    """Lấy đối tượng Firestore Client, tự động tái kết nối nếu chưa khởi tạo."""
    if db is None:
        return init_firebase()
    return db


def get_firebase_error():
    """Trả về chi tiết lỗi khởi tạo Firebase gần nhất nếu có."""
    return firebase_init_error


def get_firebase_status():
    """Trả về báo cáo chẩn đoán trạng thái kết nối Firebase chi tiết."""
    env_keys = [
        "FIREBASE_JSON", "FIREBASE_CREDENTIALS", "FIREBASE_SERVICE_ACCOUNT",
        "FIREBASE_ADMINSDK", "GOOGLE_APPLICATION_CREDENTIALS",
        "FIREBASE_JSON_BASE64", "FIREBASE_BASE64"
    ]
    detected_envs = [k for k in env_keys if os.environ.get(k)]
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_file_exists = os.path.isfile(os.path.join(base_dir, "firebase-adminsdk.json"))

    return {
        "connected": db is not None,
        "error": firebase_init_error,
        "detected_envs": detected_envs,
        "local_file_exists": local_file_exists
    }
