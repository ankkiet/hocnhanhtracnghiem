import os
import tempfile
import pytest
from app.api.routes.document import process_document_background
from core.state import active_tasks

def test_scanned_pdf_without_ai_triggers_scanned_pdf_needs_ai():
    """Kiểm tra: Nếu tải PDF scan/ảnh (không có lớp chữ) mà tắt AI, hệ thống phải báo SCANNED_PDF_NEEDS_AI rõ ràng thay vì lỗi mạng AI ảo."""
    import fitz
    # Tạo 1 file PDF rỗng (chỉ có trang trắng, không có chữ số hóa)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        doc = fitz.open()
        doc.new_page()  # Trang 1: 0 ký tự
        doc.save(tmp_path)
        doc.close()

        task_id = "test_scanned_pdf_task_1"
        process_document_background(
            task_id=task_id,
            temp_file_path=tmp_path,
            ext=".pdf",
            use_ai=False,
            api_keys=[],
            filename="de_thi_scan.pdf",
            user_requested_ai=False
        )

        task_res = active_tasks.get(task_id)
        assert task_res is not None
        assert task_res.get("status") == "error"
        assert task_res.get("error_code") == "SCANNED_PDF_NEEDS_AI"
        assert "Dùng AI bóc tách siêu chuẩn" in task_res.get("solution", "")
        assert "PDF Scan" in task_res.get("error_name", "")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        active_tasks.pop("test_scanned_pdf_task_1", None)


def test_image_upload_without_api_keys_triggers_no_api_keys():
    """Kiểm tra: Nếu tải ảnh chụp đề thi mà hệ thống chưa có API key, phải báo NO_API_KEYS với hướng dẫn thêm key rõ ràng."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
        tmp_path = tmp.name

    try:
        task_id = "test_img_no_keys_task"
        process_document_background(
            task_id=task_id,
            temp_file_path=tmp_path,
            ext=".png",
            use_ai=True,
            api_keys=[],
            filename="de_thi.png",
            user_requested_ai=True
        )

        task_res = active_tasks.get(task_id)
        assert task_res is not None
        assert task_res.get("status") == "error"
        assert task_res.get("error_code") == "NO_API_KEYS"
        assert "Gemini API Key" in task_res.get("solution", "")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        active_tasks.pop("test_img_no_keys_task", None)
