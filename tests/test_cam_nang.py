"""
Unit test suite verifying the Educational Content & Study Guide Hub (Cẩm nang GDPT 2018):
- Hub page /cam-nang
- In-depth articles:
  1. /cam-nang/cau-truc-de-thi-tot-nghiep-thpt-2025-gdpt-2018
  2. /cam-nang/cach-lam-trac-nghiem-dung-sai-diem-toi-da
  3. /cam-nang/huong-dan-so-hoa-de-thi-word-pdf-cho-giao-vien
  4. /cam-nang/ky-nang-lam-trac-nghiem-tra-loi-ngan-toan-khtn
- AdSense high-value content depth requirements
- Cloudflare Pages Worker routing
- Sitemap inclusion
"""

import os
import subprocess
import pytest
from fastapi.testclient import TestClient

from core.config import settings


def test_hub_and_articles_exist():
    """Kiểm tra sự tồn tại của trang cẩm nang và 4 bài viết chuyên sâu."""
    hub_path = os.path.join(settings.TEMPLATES_DIR, "cam-nang.html")
    assert os.path.exists(hub_path), "Thiếu tệp templates/cam-nang.html"

    articles_dir = os.path.join(settings.TEMPLATES_DIR, "cam-nang")
    assert os.path.isdir(articles_dir), "Thiếu thư mục templates/cam-nang"

    expected_articles = [
        "cau-truc-de-thi-tot-nghiep-thpt-2025-gdpt-2018.html",
        "cach-lam-trac-nghiem-dung-sai-diem-toi-da.html",
        "huong-dan-so-hoa-de-thi-word-pdf-cho-giao-vien.html",
        "ky-nang-lam-trac-nghiem-tra-loi-ngan-toan-khtn.html",
    ]

    for art in expected_articles:
        fpath = os.path.join(articles_dir, art)
        assert os.path.exists(fpath), f"Thiếu bài viết {art}"
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        # Đảm bảo bài viết có dung lượng lớn và cấu trúc chuẩn AdSense
        assert len(content) > 3000, f"Bài viết {art} quá ngắn ({len(content)} ký tự) để đạt chuẩn AdSense High Value"
        assert "<article" in content, f"Bài viết {art} thiếu thẻ <article>"
        assert "application/ld+json" in content, f"Bài viết {art} thiếu Schema.org JSON-LD"
        assert "Ban Chuyên môn HocNhanhTN" in content or "HocNhanhTN" in content, f"Bài viết {art} thiếu thông tin tác giả"


def test_sitemap_contains_all_articles():
    """Kiểm tra sitemap.xml có chứa URL của chuyên mục và 4 bài viết."""
    sitemap_path = os.path.join(settings.TEMPLATES_DIR, "sitemap.xml")
    with open(sitemap_path, "r", encoding="utf-8") as f:
        content = f.read()

    expected_urls = [
        "https://hocnhanhtn.online/cam-nang",
        "https://hocnhanhtn.online/cam-nang/cau-truc-de-thi-tot-nghiep-thpt-2025-gdpt-2018",
        "https://hocnhanhtn.online/cam-nang/cach-lam-trac-nghiem-dung-sai-diem-toi-da",
        "https://hocnhanhtn.online/cam-nang/huong-dan-so-hoa-de-thi-word-pdf-cho-giao-vien",
        "https://hocnhanhtn.online/cam-nang/ky-nang-lam-trac-nghiem-tra-loi-ngan-toan-khtn",
    ]

    for url in expected_urls:
        tag = f"<loc>{url}</loc>"
        assert tag in content, f"Sitemap thiếu URL: {url}"


def test_worker_cam_nang_routing():
    """Kiểm tra templates/_worker.js có routing cẩm nang và cú pháp hợp lệ."""
    worker_path = os.path.join(settings.TEMPLATES_DIR, "_worker.js")
    with open(worker_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "'/cam-nang': '/cam-nang.html'" in content
    assert "url.pathname.toLowerCase().startsWith('/cam-nang/')" in content

    res = subprocess.run(["node", "-c", worker_path], capture_output=True, text=True)
    assert res.returncode == 0, f"Cú pháp _worker.js bị lỗi: {res.stderr}"


def test_fastapi_cam_nang_routes():
    """Kiểm tra các endpoint FastAPI phục vụ cẩm nang và bài viết chi tiết."""
    from fastapi import FastAPI
    from app.api.routes.pages import router as pages_router

    app = FastAPI()
    app.include_router(pages_router)
    client = TestClient(app)

    # 1. Test Hub page
    hub_resp = client.get("/cam-nang")
    assert hub_resp.status_code == 200
    assert "Cẩm Nang Ôn Thi & Chuyển Đổi Số Giáo Dục" in hub_resp.text

    # 2. Test các bài viết cụ thể
    articles = [
        ("cau-truc-de-thi-tot-nghiep-thpt-2025-gdpt-2018", "Cấu Trúc Đề Thi Tốt Nghiệp THPT"),
        ("cach-lam-trac-nghiem-dung-sai-diem-toi-da", "Trắc Nghiệm Đúng/Sai"),
        ("huong-dan-so-hoa-de-thi-word-pdf-cho-giao-vien", "Hướng Dẫn Giáo Viên"),
        ("ky-nang-lam-trac-nghiem-tra-loi-ngan-toan-khtn", "Trắc Nghiệm Trả Lời Ngắn"),
    ]

    for slug, expected_kw in articles:
        resp = client.get(f"/cam-nang/{slug}")
        assert resp.status_code == 200, f"Slug {slug} trả về {resp.status_code}"
        assert expected_kw in resp.text, f"Không tìm thấy '{expected_kw}' trong /cam-nang/{slug}"

    # 3. Test non-existent article trả về 404
    resp_404 = client.get("/cam-nang/bai-viet-khong-ton-tai")
    assert resp_404.status_code == 404
