from fastapi import APIRouter

router = APIRouter(tags=["Health & System"])


@router.api_route("/api/keep-alive", methods=["GET", "HEAD", "POST"], summary="Đánh thức máy chủ từ Cron-job (Keep-Alive)")
@router.api_route("/keep-alive", methods=["GET", "HEAD", "POST"], summary="Đánh thức máy chủ từ Cron-job (Keep-Alive)")
@router.api_route("/api/health", methods=["GET", "HEAD", "POST"], summary="Kiểm tra trạng thái máy chủ (Health Check & Keep-Alive)")
@router.api_route("/ping", methods=["GET", "HEAD", "POST"], summary="Ping đánh thức máy chủ")
def health_check():
    """Endpoint siêu nhẹ để Frontend & Cron-job đánh thức máy chủ (chống ngủ đông) hoặc giám sát Uptime."""
    return {"status": "ok", "message": "HocnhanhTN backend is awake and active"}


@router.get("/api/firebase/debug", summary="Kiểm tra trạng thái & quyền truy cập Firebase Firestore")
def debug_firebase():
    """Endpoint chẩn đoán chi tiết lỗi kết nối Firebase và lỗi 403 Permission Denied."""
    from services.firebase_service import test_firebase_connection
    return test_firebase_connection()
