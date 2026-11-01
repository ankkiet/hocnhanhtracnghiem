"""
Unit test suite verifying AdSense-compliant standalone policy and legal pages:
- /privacy (Privacy Policy with DoubleClick/DART cookies & opt-out)
- /terms (Terms of Service, intellectual property, student conduct)
- /about (About Us, mission, technology, GDPT 2018 format)
- /contact (Contact info, email, 24-48h SLA, interactive form)
- Cloudflare Pages Worker routing
- Sitemap entries
"""

import os
import subprocess
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from core.config import settings


def test_physical_html_files_exist():
    """Kiểm tra sự tồn tại của các tệp HTML độc lập trong templates/."""
    required_files = ["privacy.html", "terms.html", "about.html", "contact.html"]
    for filename in required_files:
        path = os.path.join(settings.TEMPLATES_DIR, filename)
        assert os.path.exists(path), f"Tệp {filename} không tồn tại trong {settings.TEMPLATES_DIR}"
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 1000, f"Tệp {filename} quá ngắn, có thể bị rỗng!"
        assert "<h1" in content, f"Tệp {filename} thiếu thẻ <h1>"
        assert "<footer" in content, f"Tệp {filename} thiếu thẻ <footer>"


def test_adsense_compliance_in_privacy():
    """Kiểm tra điều kiện bắt buộc của Google AdSense trong privacy.html."""
    privacy_path = os.path.join(settings.TEMPLATES_DIR, "privacy.html")
    with open(privacy_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "Google AdSense" in content
    assert "DART" in content
    assert "adssettings.google.com" in content
    assert "aboutads.info/choices" in content
    assert "kiet0905478167@gmail.com" in content


def test_contact_page_structure():
    """Kiểm tra thông tin liên hệ và form tương tác trong contact.html."""
    contact_path = os.path.join(settings.TEMPLATES_DIR, "contact.html")
    with open(contact_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "kiet0905478167@gmail.com" in content
    assert "24 - 48" in content
    assert "<form" in content
    assert 'name="email"' in content
    assert 'name="message"' in content


def test_sitemap_contains_legal_pages():
    """Kiểm tra sitemap.xml có chứa đầy đủ các URL chính sách độc lập."""
    sitemap_path = os.path.join(settings.TEMPLATES_DIR, "sitemap.xml")
    with open(sitemap_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    for route in ["/privacy", "/terms", "/about", "/contact"]:
        expected_url = f"<loc>https://hocnhanhtn.online{route}</loc>"
        assert expected_url in content, f"Thiếu {expected_url} trong sitemap.xml"


def test_worker_script_syntax_and_static_routes():
    """Kiểm tra cú pháp JS của templates/_worker.js và sự hiện diện của staticPageMap."""
    worker_path = os.path.join(settings.TEMPLATES_DIR, "_worker.js")
    with open(worker_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "'/privacy': '/privacy.html'" in content
    assert "'/terms': '/terms.html'" in content
    assert "'/about': '/about.html'" in content
    assert "'/contact': '/contact.html'" in content

    # Kiểm tra cú pháp bằng Node.js CLI
    result = subprocess.run(["node", "-c", worker_path], capture_output=True, text=True)
    assert result.returncode == 0, f"Lỗi cú pháp trong _worker.js: {result.stderr}"


def test_fastapi_legal_routes():
    """Kiểm tra các endpoint FastAPI trả về đúng nội dung HTML tĩnh độc lập."""
    from fastapi import FastAPI
    from app.api.routes.pages import router as pages_router

    # Sử dụng isolated app để tránh phụ thuộc Firestore kết nối mạng
    test_app = FastAPI()
    test_app.include_router(pages_router)
    client = TestClient(test_app)

    routes_to_test = [
        ("/privacy", "Chính sách bảo mật"),
        ("/terms", "Điều khoản"),
        ("/about", "Về Chúng Tôi"),
        ("/contact", "Liên Hệ & Hỗ Trợ Kỹ Thuật"),
    ]

    for path, expected_text in routes_to_test:
        resp = client.get(path)
        assert resp.status_code == 200, f"Route {path} trả về mã {resp.status_code}"
        assert resp.headers["content-type"].startswith("text/html")
        assert expected_text in resp.text, f"Không tìm thấy '{expected_text}' trong phản hồi từ {path}"
