import os
import sys

# CẤU HÌNH GRPC KEEPALIVE CHỐNG RỚT MẠNG / IDLE TIMEOUT TRÊN KOYEB / DOCKER CLOUD
# Ngăn chặn Envoy Proxy và NAT Gateway ngắt kết nối TCP âm thầm sau thời gian Idle
os.environ.setdefault("GRPC_ARG_KEEPALIVE_TIME_MS", "30000")       # Ping mỗi 30 giây
os.environ.setdefault("GRPC_ARG_KEEPALIVE_TIMEOUT_MS", "10000")    # Timeout 10 giây
os.environ.setdefault("GRPC_ARG_KEEPALIVE_PERMIT_WITHOUT_CALLS", "1")
os.environ.setdefault("GRPC_ARG_HTTP2_MAX_PINGS_WITHOUT_DATA", "0")
os.environ.setdefault("GRPC_ARG_HTTP2_MIN_TIME_BETWEEN_PINGS_MS", "10000")
os.environ.setdefault("GRPC_ARG_HTTP2_MIN_PING_INTERVAL_WITHOUT_DATA_MS", "5000")
os.environ.setdefault("GRPC_ENABLE_FORK_SUPPORT", "1")

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
firebase_project_id = None
firebase_client_email = None
firebase_source = None
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

    # Quét tự động bất kỳ tệp JSON nào có chứa firebase-adminsdk trong thư mục gốc
    try:
        for f in os.listdir(base_dir):
            if f.endswith('.json') and ('firebase-adminsdk' in f.lower() or 'serviceaccount' in f.lower()):
                full_p = os.path.join(base_dir, f)
                if full_p not in file_candidates:
                    file_candidates.append(full_p)
    except Exception:
        pass

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


def reconnect_firebase():
    """
    Làm mới OAuth token của Service Account và tái tạo hoàn toàn Firestore Client (Self-Healing).
    Được gọi khi token hết hạn sau 1 giờ hoặc khi kết nối gRPC bị Envoy/NAT proxy ngắt sau thời gian idle.
    """
    global db, firebase_init_error
    with _init_lock:
        try:
            logger.info("Đang tự động làm mới OAuth Token & tái kết nối Firebase Firestore...")
            app = firebase_admin.get_app() if firebase_admin._apps else None
            if app:
                # 1. Thử làm mới OAuth Token của Google Service Account
                try:
                    from google.auth.transport.requests import Request
                    cred = app.credential.get_credential()
                    if hasattr(cred, 'refresh'):
                        cred.refresh(Request())
                        logger.info("Đã làm mới OAuth2 Access Token thành công.")
                except Exception as ref_err:
                    logger.warning(f"Lưu ý: Không thể refresh token trực tiếp ({ref_err}), sẽ thử nạp lại credentials.")

                # 2. Xóa sạch cache client nội bộ trong firebase_admin._FirestoreService
                try:
                    from firebase_admin import _utils
                    fs_service = _utils.get_app_service(app, firestore._FIRESTORE_ATTRIBUTE, firestore._FirestoreService)
                    if hasattr(fs_service, '_clients'):
                        fs_service._clients.clear()
                except Exception:
                    pass

                # 3. Đóng client cũ nếu có
                if db is not None:
                    try:
                        if hasattr(db, 'close'):
                            db.close()
                    except Exception:
                        pass

                # 4. Tạo Firestore Client mới tinh
                db = firestore.client(app=app)
                firebase_init_error = None
                logger.info("Đã tái tạo kết nối Firestore Client mới thành công!")
                return db
            else:
                db = None
                return init_firebase()
        except Exception as e:
            logger.error(f"Lỗi khi tái kết nối Firebase ({e})")
            firebase_init_error = str(e)
            return db


def init_firebase():
    """Khởi tạo kết nối Firebase Firestore an toàn, chống crash và hỗ trợ đa nền tảng (Koyeb/Docker/Local)."""
    global db, firebase_init_error
    if db is not None:
        return db

    with _init_lock:
        if db is not None:
            return db

        try:
            global firebase_project_id, firebase_client_email, firebase_source
            cred, source = _get_credentials_object()
            firebase_project_id = getattr(cred, 'project_id', None)
            firebase_client_email = getattr(cred, 'service_account_email', None)
            firebase_source = source

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


def get_db(force_refresh: bool = False):
    """
    Lấy đối tượng Firestore Client.
    Hỗ trợ tham số force_refresh=True để chủ động làm mới token và tái kết nối gRPC.
    """
    global db
    if force_refresh or db is None:
        if force_refresh and db is not None:
            return reconnect_firebase()
        return init_firebase()
    return db


def execute_with_firebase_retry(query_func, *args, **kwargs):
    """
    Thực thi an toàn một hàm truy vấn Firestore với cơ chế tự động phục hồi (Self-Healing):
    Nếu gặp lỗi 403 / PermissionDenied / Unavailable / Stale socket sau 1 khoảng thời gian,
    hàm sẽ tự động làm mới OAuth Token, tái tạo Client và thử lại (Retry) 1 lần nữa một cách trong suốt.
    """
    current_db = get_db()
    if current_db is None:
        raise RuntimeError("Chưa kết nối cơ sở dữ liệu Firebase Firestore")

    try:
        return query_func(current_db, *args, **kwargs)
    except Exception as e:
        err_msg = str(e)
        if any(err_key in err_msg for err_key in ["403", "PermissionDenied", "Unavailable", "503", "TransportError", "broken stream", "channel closed"]):
            logger.warning(f"Phát hiện sự cố kết nối/quyền Firestore ({e}). Đang tự động phục hồi kết nối và thử lại...")
            new_db = get_db(force_refresh=True)
            if new_db is not None:
                return query_func(new_db, *args, **kwargs)
        raise


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
        "project_id": firebase_project_id,
        "client_email": firebase_client_email,
        "source": firebase_source,
        "detected_envs": detected_envs,
        "local_file_exists": local_file_exists
    }


def test_firebase_connection():
    """Kiểm tra thực tế quyền đọc dữ liệu Firestore và chẩn đoán lỗi 403."""
    global db
    if db is None:
        db = init_firebase()
    if db is None:
        return {
            "status": "error",
            "message": f"Không thể khởi tạo kết nối Firebase: {firebase_init_error}",
            "project_id": firebase_project_id,
            "client_email": firebase_client_email,
            "source": firebase_source
        }

    try:
        docs = list(db.collection('quizzes').limit(1).stream())
        return {
            "status": "success",
            "message": "Kết nối Firestore và quyền đọc dữ liệu thành công!",
            "project_id": firebase_project_id,
            "client_email": firebase_client_email,
            "source": firebase_source,
            "sample_docs_count": len(docs)
        }
    except Exception as e:
        err_str = str(e)
        hint = ""
        if "403" in err_str or "PermissionDenied" in err_str:
            hint = (
                f"LỖI QUYỀN TRUY CẬP (403 Permission Denied): Service Account '{firebase_client_email}' "
                f"chưa được cấp quyền trên project Google Cloud '{firebase_project_id}'. "
                "👉 Cách khắc phục: Vào Google Cloud Console > IAM & Admin > IAM, tìm email trên và cấp vai trò "
                "'Cloud Datastore User' (roles/datastore.user) hoặc tạo lại Service Account Key từ Firebase Console."
            )
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "error_detail": err_str,
            "project_id": firebase_project_id,
            "client_email": firebase_client_email,
            "source": firebase_source,
            "hint": hint
        }
