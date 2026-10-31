"""
Pages & SEO Router for HocNhanhTN.
Chịu trách nhiệm render các trang giao diện trực tiếp từ templates/index.html & templates/editor.html
với SEO / Social OpenGraph tags chính xác, bảo toàn 100% typography (Plus Jakarta Sans, Inter)
và giao diện gốc tiêu chuẩn.
"""

import html
import os
import re
import sys
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from core.config import settings
from core.logging_config import get_logger
from core.state import QUIZ_CACHE

logger = get_logger(__name__)

router = APIRouter(tags=["Pages & SEO"])


def _get_db():
    """Lấy đối tượng Firestore DB an toàn, tương thích với unittest patch ('main.get_db')."""
    main_mod = sys.modules.get("main")
    if main_mod and hasattr(main_mod, "get_db"):
        try:
            return main_mod.get_db()
        except Exception:
            pass
    from services.firebase_service import get_db as fb_get_db
    return fb_get_db()


def _get_site_urls(request: Request):
    """Tính toán URL gốc và canonical domain an toàn."""
    canon_domain = settings.CANONICAL_DOMAIN
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    base_url = f"{proto}://{host}".rstrip('/')
    site_domain = canon_domain if any(h in host for h in ["localhost", "127.0.0.1", "testserver"]) else base_url
    og_image_url = f"{site_domain}/unnamed.jpg"
    return site_domain, og_image_url


def _get_quiz_meta(quiz_id: str):
    """Truy vấn tiêu đề và thông tin tóm tắt đề thi từ Cache hoặc Firestore."""
    if not quiz_id:
        return None, None
    try:
        now = time.time()
        if quiz_id in QUIZ_CACHE and (now - QUIZ_CACHE[quiz_id].get('time', 0) < 300):
            q_data = QUIZ_CACHE[quiz_id].get('data')
        else:
            database = _get_db()
            if database is not None:
                doc = database.collection('quizzes').document(quiz_id).get()
                if doc.exists:
                    q_data = doc.to_dict()
                    QUIZ_CACHE[quiz_id] = {'time': now, 'data': q_data}
                else:
                    q_data = None
            else:
                q_data = None

        if q_data:
            title = (q_data.get('title') or '').strip()
            count = len(q_data.get('data', []))
            time_limit = q_data.get('time_limit', 0)
            desc_parts = [f"Đề thi: {title}"]
            if count > 0:
                desc_parts.append(f"{count} câu hỏi")
            if time_limit > 0:
                desc_parts.append(f"{time_limit} phút làm bài")
            desc = " • ".join(desc_parts) + ". Hệ thống học nhanh trắc nghiệm HocNhanhTN chuẩn GDPT 2018."
            return title, desc
    except Exception as e:
        logger.error(f"Lỗi truy vấn metadata đề thi {quiz_id}: {e}")
    return None, None


def _guard_static_asset(raw_path: Optional[str]):
    """Phòng vệ: Nếu trình duyệt yêu cầu file tĩnh bị dính tiền tố route (/thi/script.js, /xep-hang/style.css)."""
    if raw_path and any(raw_path.endswith(ext) for ext in [".js", ".css", ".png", ".jpg", ".jpeg", ".ico", ".svg", ".map", ".json", ".webp", ".woff", ".woff2"]):
        asset_file = os.path.join(settings.TEMPLATES_DIR, raw_path)
        if not os.path.exists(asset_file):
            asset_file = os.path.join(settings.BASE_DIR, raw_path)
        if os.path.exists(asset_file):
            media_type = "application/javascript" if raw_path.endswith(".js") else ("text/css" if raw_path.endswith(".css") else None)
            return FileResponse(asset_file, media_type=media_type)
        raise HTTPException(status_code=404, detail="File not found")
    return None


def _render_index_with_meta(
    title: Optional[str] = None,
    og_title: Optional[str] = None,
    description: Optional[str] = None,
    canonical_url: Optional[str] = None,
    og_image_url: Optional[str] = None,
    route_class: str = "hntn-not-home-route",
) -> HTMLResponse:
    """Render index.html gốc với các thẻ title & OpenGraph được tùy biến chính xác, loại bỏ triệt để FOUC ám trang chủ."""
    index_path = os.path.join(settings.TEMPLATES_DIR, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy index.html")

    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    if route_class:
        html_content = re.sub(
            r'<html([^>]*)lang=["\']vi["\']([^>]*)>',
            rf'<html\1lang="vi" class="{route_class}"\2>',
            html_content,
            count=1,
            flags=re.IGNORECASE
        )

    if title:
        html_content = re.sub(r'<title>.*?</title>', f'<title>{html.escape(title)}</title>', html_content, flags=re.IGNORECASE)
    if og_title:
        html_content = re.sub(r'<meta\s+property=["\']og:title["\']\s+content=["\'].*?["\']\s*/?>', f'<meta property="og:title" content="{html.escape(og_title)}">', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+name=["\']twitter:title["\']\s+content=["\'].*?["\']\s*/?>', f'<meta name="twitter:title" content="{html.escape(og_title)}">', html_content, flags=re.IGNORECASE)
    if description:
        html_content = re.sub(r'<meta\s+name=["\']description["\']\s+content=["\'].*?["\']\s*/?>', f'<meta name="description" content="{html.escape(description)}">', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+property=["\']og:description["\']\s+content=["\'].*?["\']\s*/?>', f'<meta property="og:description" content="{html.escape(description)}">', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+name=["\']twitter:description["\']\s+content=["\'].*?["\']\s*/?>', f'<meta name="twitter:description" content="{html.escape(description)}">', html_content, flags=re.IGNORECASE)
    if canonical_url:
        html_content = re.sub(r'<link\s+rel=["\']canonical["\']\s+href=["\'].*?["\']\s*/?>', f'<link rel="canonical" href="{canonical_url}">', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+property=["\']og:url["\']\s+content=["\'].*?["\']\s*/?>', f'<meta property="og:url" content="{canonical_url}">', html_content, flags=re.IGNORECASE)
    if og_image_url:
        html_content = re.sub(r'<meta\s+property=["\']og:image["\']\s+content=["\'].*?["\']\s*/?>', f'<meta property="og:image" content="{og_image_url}">', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+property=["\']og:image:secure_url["\']\s+content=["\'].*?["\']\s*/?>', f'<meta property="og:image:secure_url" content="{og_image_url}">', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+name=["\']twitter:image["\']\s+content=["\'].*?["\']\s*/?>', f'<meta name="twitter:image" content="{og_image_url}">', html_content, flags=re.IGNORECASE)

    return HTMLResponse(content=html_content, media_type="text/html")


def _render_editor_with_meta(quiz_title: Optional[str] = None) -> HTMLResponse:
    """Render editor.html gốc với tiêu đề đề thi nếu có."""
    editor_path = os.path.join(settings.TEMPLATES_DIR, "editor.html")
    if not os.path.exists(editor_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy trang editor.html")

    with open(editor_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    if quiz_title:
        title = f"Soát lỗi đề: {quiz_title} - HocNhanhTN"
        html_content = re.sub(r'<title>.*?</title>', f'<title>{html.escape(title)}</title>', html_content, flags=re.IGNORECASE)

    return HTMLResponse(content=html_content, media_type="text/html")


# -------------------------------------------------------------
# 1. TRANG CHỦ & ĐỀ THI TRỰC TIẾP (?id=... / ?quiz_id=...)
# -------------------------------------------------------------
@router.get("/", response_class=HTMLResponse, summary="Giao diện chính & Đề thi trắc nghiệm")
@router.get("/index.html", response_class=HTMLResponse, summary="Giao diện chính")
async def home_page(request: Request, id: Optional[str] = None, quiz_id: Optional[str] = None):
    target_quiz_id = quiz_id or id
    site_domain, og_image_url = _get_site_urls(request)

    if target_quiz_id:
        quiz_title, quiz_desc = _get_quiz_meta(target_quiz_id)
        full_title = f"{quiz_title} - HocNhanhTN" if quiz_title else f"Đề thi #{target_quiz_id} - HocNhanhTN"
        og_t = quiz_title if quiz_title else f"Đề thi #{target_quiz_id}"
        desc = quiz_desc if quiz_desc else f"Làm bài kiểm tra: {quiz_title or target_quiz_id}. Hệ thống học nhanh trắc nghiệm chuẩn GDPT 2018."
        canon = f"{site_domain}/?id={target_quiz_id}"
        return _render_index_with_meta(title=full_title, og_title=og_t, description=desc, canonical_url=canon, og_image_url=og_image_url, route_class="hntn-not-home-route hntn-is-quiz-route")

    # Trang chủ sạch sẽ nguyên bản 100% như giao diện gốc
    index_path = os.path.join(settings.TEMPLATES_DIR, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), media_type="text/html")


# -------------------------------------------------------------
# 2. ĐĂNG NHẬP & ĐĂNG KÝ (/dang-nhap, /login, /register, /auth)
# -------------------------------------------------------------
@router.get("/dang-nhap", response_class=HTMLResponse, summary="Trang Đăng nhập tài khoản")
@router.get("/login", response_class=HTMLResponse, summary="Trang Đăng nhập (alias)")
@router.get("/register", response_class=HTMLResponse, summary="Trang Đăng ký (alias)")
@router.get("/auth", response_class=HTMLResponse, summary="Trang Xác thực (alias)")
async def login_page(request: Request):
    site_domain, og_image_url = _get_site_urls(request)
    return _render_index_with_meta(
        title="Đăng nhập tài khoản - HocNhanhTN",
        og_title="Đăng nhập tài khoản - HocNhanhTN",
        description="Đăng nhập tài khoản giáo viên hoặc học sinh để quản lý đề thi và lưu trữ tiến độ làm bài thi trắc nghiệm trên HocNhanhTN.",
        canonical_url=f"{site_domain}/dang-nhap",
        og_image_url=og_image_url,
        route_class="hntn-not-home-route hntn-is-auth-route",
    )


# -------------------------------------------------------------
# 3. DANH SÁCH ĐỀ THI (/de-thi)
# -------------------------------------------------------------
@router.get("/de-thi", response_class=HTMLResponse, summary="Khám phá danh sách đề thi trắc nghiệm")
async def quiz_list_page(request: Request):
    site_domain, og_image_url = _get_site_urls(request)
    return _render_index_with_meta(
        title="Danh sách Đề thi - Kho đề trắc nghiệm chuẩn GDPT 2018 - HocNhanhTN",
        og_title="Danh sách Đề thi - Kho đề trắc nghiệm chuẩn GDPT 2018 - HocNhanhTN",
        description="Khám phá danh sách các đề thi trắc nghiệm phong phú bám sát cấu trúc Bộ Giáo dục và Đào tạo mới nhất.",
        canonical_url=f"{site_domain}/de-thi",
        og_image_url=og_image_url,
        route_class="",
    )


# -------------------------------------------------------------
# 4. PHÒNG THI / LÀM BÀI (/thi/{ma_de}, /quiz/{ma_de})
# -------------------------------------------------------------
@router.get("/thi/{quiz_id}", response_class=HTMLResponse, summary="Phòng thi trực tuyến làm bài")
@router.get("/quiz/{quiz_id}", response_class=HTMLResponse, summary="Link trực tiếp tới đề thi (alias)")
async def exam_page(request: Request, quiz_id: str):
    guard = _guard_static_asset(quiz_id)
    if guard:
        return guard

    site_domain, og_image_url = _get_site_urls(request)
    quiz_title, quiz_desc = _get_quiz_meta(quiz_id)

    full_title = f"{quiz_title} - HocNhanhTN" if quiz_title else f"Phòng thi trực tuyến #{quiz_id} - HocNhanhTN"
    og_title = quiz_title if quiz_title else f"Phòng thi #{quiz_id}"
    desc = quiz_desc if quiz_desc else f"Làm bài kiểm tra: {quiz_title or quiz_id}. Hệ thống học nhanh trắc nghiệm chuẩn GDPT 2018."

    return _render_index_with_meta(
        title=full_title,
        og_title=og_title,
        description=desc,
        canonical_url=f"{site_domain}/thi/{quiz_id}",
        og_image_url=og_image_url,
        route_class="hntn-not-home-route hntn-is-quiz-route",
    )


# -------------------------------------------------------------
# 5. KẾT QUẢ & ĐÁP ÁN CHI TIẾT (/ket-qua/{id})
# -------------------------------------------------------------
@router.get("/ket-qua/{submission_id}", response_class=HTMLResponse, summary="Kết quả và đáp án chi tiết bài thi")
async def result_page(request: Request, submission_id: str):
    guard = _guard_static_asset(submission_id)
    if guard:
        return guard

    site_domain, og_image_url = _get_site_urls(request)
    return _render_index_with_meta(
        title=f"Kết quả và đáp án chi tiết bài thi #{submission_id} - HocNhanhTN",
        og_title=f"Kết quả bài thi #{submission_id}",
        description="Xem chi tiết điểm số, đáp án đúng/sai và phân tích giải thích bài thi tại HocNhanhTN.",
        canonical_url=f"{site_domain}/ket-qua/{submission_id}",
        og_image_url=og_image_url,
        route_class="hntn-not-home-route hntn-is-quiz-route",
    )


# -------------------------------------------------------------
# 6. LỊCH SỬ LÀM BÀI (/lich-su)
# -------------------------------------------------------------
@router.get("/lich-su", response_class=HTMLResponse, summary="Lịch sử làm bài thi của học sinh")
async def history_page(request: Request):
    site_domain, og_image_url = _get_site_urls(request)
    return _render_index_with_meta(
        title="Lịch sử làm bài & Bảng điểm học sinh - HocNhanhTN",
        og_title="Lịch sử làm bài & Bảng điểm học sinh - HocNhanhTN",
        description="Xem lại lịch sử các bài kiểm tra đã làm, đối chiếu bảng điểm và lời giải chi tiết từng câu hỏi.",
        canonical_url=f"{site_domain}/lich-su",
        og_image_url=og_image_url,
        route_class="hntn-not-home-route hntn-is-student-route",
    )


# -------------------------------------------------------------
# 7. BẢNG XẾP HẠNG (/xep-hang/{ma_de})
# -------------------------------------------------------------
@router.get("/xep-hang/{quiz_id}", response_class=HTMLResponse, summary="Bảng xếp hạng vinh danh đề thi")
async def leaderboard_page(request: Request, quiz_id: str):
    guard = _guard_static_asset(quiz_id)
    if guard:
        return guard

    site_domain, og_image_url = _get_site_urls(request)
    quiz_title, _ = _get_quiz_meta(quiz_id)
    label = quiz_title if quiz_title else f"#{quiz_id}"

    return _render_index_with_meta(
        title=f"Bảng xếp hạng: {label} - HocNhanhTN",
        og_title=f"Bảng xếp hạng: {label}",
        description=f"Xem bảng vinh danh và kết quả bài thi {label} tại HocNhanhTN.",
        canonical_url=f"{site_domain}/xep-hang/{quiz_id}",
        og_image_url=og_image_url,
        route_class="hntn-not-home-route hntn-is-quiz-route",
    )


# -------------------------------------------------------------
# 8. BẢNG ĐIỀU KHIỂN GIÁO VIÊN (/giao-vien)
# -------------------------------------------------------------
@router.get("/giao-vien", response_class=HTMLResponse, summary="Bảng điều khiển giáo viên")
async def teacher_page(request: Request):
    site_domain, og_image_url = _get_site_urls(request)
    return _render_index_with_meta(
        title="Bảng điều khiển Giáo viên - HocNhanhTN",
        og_title="Bảng điều khiển Giáo viên - HocNhanhTN",
        description="Quản lý kho đề thi, số hóa đề từ Word/PDF bằng AI và theo dõi kết quả làm bài của học sinh.",
        canonical_url=f"{site_domain}/giao-vien",
        og_image_url=og_image_url,
        route_class="hntn-not-home-route hntn-is-teacher-route",
    )


# -------------------------------------------------------------
# 9. QUẢN LÝ ĐỀ THI CỤ THỂ CỦA GIÁO VIÊN (/giao-vien/de/{id})
# -------------------------------------------------------------
@router.get("/giao-vien/de/{quiz_id}", response_class=HTMLResponse, summary="Quản lý chi tiết một đề thi")
async def teacher_quiz_detail_page(request: Request, quiz_id: str):
    guard = _guard_static_asset(quiz_id)
    if guard:
        return guard

    site_domain, og_image_url = _get_site_urls(request)
    quiz_title, _ = _get_quiz_meta(quiz_id)
    label = quiz_title if quiz_title else f"#{quiz_id}"

    return _render_index_with_meta(
        title=f"Quản lý đề thi: {label} - HocNhanhTN",
        og_title=f"Quản lý đề thi: {label}",
        description=f"Chỉnh sửa câu hỏi, xuất bản phòng thi và xem phổ điểm chi tiết của đề thi {label}.",
        canonical_url=f"{site_domain}/giao-vien/de/{quiz_id}",
        og_image_url=og_image_url,
        route_class="hntn-not-home-route hntn-is-teacher-route",
    )


# -------------------------------------------------------------
# 10. STUDIO BIÊN TẬP & SOÁT LỖI ĐỀ THI (/editor, /editor/{id})
# -------------------------------------------------------------
@router.get("/editor", response_class=HTMLResponse, summary="Giao diện Studio Biên tập & Soát lỗi Đề thi")
def get_editor_page():
    return _render_editor_with_meta()


@router.get("/editor/{quiz_id}", response_class=HTMLResponse, summary="Soát lỗi đề thi cụ thể trong Studio")
async def editor_quiz_page(request: Request, quiz_id: str):
    guard = _guard_static_asset(quiz_id)
    if guard:
        return guard

    quiz_title, _ = _get_quiz_meta(quiz_id)
    return _render_editor_with_meta(quiz_title=quiz_title or quiz_id)


# -------------------------------------------------------------
# 11. QUẢN TRỊ VIÊN HỆ THỐNG (/admin)
# -------------------------------------------------------------
@router.get("/admin", response_class=HTMLResponse, summary="Quản trị hệ thống HocNhanhTN")
async def admin_page(request: Request):
    site_domain, og_image_url = _get_site_urls(request)
    return _render_index_with_meta(
        title="Quản trị hệ thống - HocNhanhTN",
        og_title="Quản trị hệ thống - HocNhanhTN",
        description="Trang quản trị toàn diện: Thống kê Quota & Chi phí Gemini AI, danh sách đề thi và tài khoản người dùng.",
        canonical_url=f"{site_domain}/admin",
        og_image_url=og_image_url,
        route_class="hntn-not-home-route hntn-is-admin-route",
    )


# -------------------------------------------------------------
# 12. CÁC TRANG CHÍNH SÁCH & PHỤ TRỢ (Legal / Canvas)
# -------------------------------------------------------------
@router.get("/privacy", response_class=HTMLResponse, summary="Chính sách bảo mật quyền riêng tư")
async def privacy_page(request: Request):
    site_domain, og_image_url = _get_site_urls(request)
    return _render_index_with_meta(
        title="Chính sách bảo mật (Privacy Policy) - HocNhanhTN",
        og_title="Chính sách bảo mật (Privacy Policy) - HocNhanhTN",
        description="Chính sách bảo mật quyền riêng tư và cam kết an toàn dữ liệu cho học sinh & giáo viên trên HocNhanhTN.",
        canonical_url=f"{site_domain}/privacy", og_image_url=og_image_url, route_class="")


@router.get("/terms", response_class=HTMLResponse, summary="Điều khoản dịch vụ & sử dụng")
async def terms_page(request: Request):
    site_domain, og_image_url = _get_site_urls(request)
    return _render_index_with_meta(
        title="Điều khoản dịch vụ (Terms of Service) - HocNhanhTN",
        og_title="Điều khoản dịch vụ (Terms of Service) - HocNhanhTN",
        description="Điều khoản sử dụng dịch vụ và quy định nền tảng thi trắc nghiệm trực tuyến HocNhanhTN.",
        canonical_url=f"{site_domain}/terms", og_image_url=og_image_url, route_class="")


@router.get("/about", response_class=HTMLResponse, summary="Giới thiệu về Dự án HocNhanhTN")
async def about_page(request: Request):
    site_domain, og_image_url = _get_site_urls(request)
    return _render_index_with_meta(
        title="Về chúng tôi - Nền tảng số hóa đề thi HocNhanhTN",
        og_title="Về chúng tôi - Nền tảng số hóa đề thi HocNhanhTN",
        description="Dự án phi lợi nhuận hỗ trợ giáo viên và học sinh Việt Nam chuyển đổi số đề thi chuẩn GDPT 2018.",
        canonical_url=f"{site_domain}/about", og_image_url=og_image_url, route_class="")


@router.get("/contact", response_class=HTMLResponse, summary="Liên hệ & Hỗ trợ kỹ thuật")
async def contact_page(request: Request):
    site_domain, og_image_url = _get_site_urls(request)
    return _render_index_with_meta(
        title="Liên hệ & Hỗ trợ - HocNhanhTN",
        og_title="Liên hệ & Hỗ trợ - HocNhanhTN",
        description="Kênh tiếp nhận phản hồi, hỗ trợ kỹ thuật và đóng góp ý kiến nâng cấp hệ thống HocNhanhTN.",
        canonical_url=f"{site_domain}/contact", og_image_url=og_image_url, route_class="")


@router.get("/canvas", summary="Interactive Component Canvas cho Design System & UI Variants")
def get_canvas_page():
    canvas_path = os.path.join(settings.TEMPLATES_DIR, "canvas.html")
    if os.path.exists(canvas_path):
        return FileResponse(canvas_path)
    raise HTTPException(status_code=404, detail="Không tìm thấy trang canvas.html")


# -------------------------------------------------------------
# 13. TỆP CÔNG CỘNG & ROBOTS / SITEMAP / LLMS.TXT / AI CATALOG
# -------------------------------------------------------------
@router.get("/ads.txt", summary="Tệp xác thực quyền sở hữu tài khoản Google AdSense", include_in_schema=False)
def get_ads_txt():
    ads_file_path = os.path.join(settings.BASE_DIR, "ads.txt")
    if not os.path.exists(ads_file_path):
        ads_file_path = os.path.join(settings.TEMPLATES_DIR, "ads.txt")
    if os.path.exists(ads_file_path):
        return FileResponse(ads_file_path, media_type="text/plain")
    return HTMLResponse("google.com, pub-5865046257484388, DIRECT, f08c47fec0942fa0", media_type="text/plain")


@router.get("/robots.txt", summary="Tệp chỉ dẫn bọ tìm kiếm Googlebot", include_in_schema=False)
def get_robots_txt():
    robots_path = os.path.join(settings.BASE_DIR, "robots.txt")
    if not os.path.exists(robots_path):
        robots_path = os.path.join(settings.TEMPLATES_DIR, "robots.txt")
    if os.path.exists(robots_path):
        return FileResponse(robots_path, media_type="text/plain")
    return HTMLResponse("User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: https://hocnhanhtn.online/sitemap.xml", media_type="text/plain")


@router.get("/sitemap.xml", summary="Sơ đồ website cho Google Search Console", include_in_schema=False)
def get_sitemap_xml():
    sitemap_path = os.path.join(settings.BASE_DIR, "sitemap.xml")
    if not os.path.exists(sitemap_path):
        sitemap_path = os.path.join(settings.TEMPLATES_DIR, "sitemap.xml")
    if os.path.exists(sitemap_path):
        return FileResponse(sitemap_path, media_type="application/xml")
    raise HTTPException(status_code=404, detail="Không tìm thấy sitemap.xml")


@router.get("/llms.txt", summary="Tệp chỉ dẫn cho Large Language Models (LLMs)", include_in_schema=False)
def get_llms_txt():
    llms_path = os.path.join(settings.BASE_DIR, "llms.txt")
    if not os.path.exists(llms_path):
        llms_path = os.path.join(settings.TEMPLATES_DIR, "llms.txt")
    if os.path.exists(llms_path):
        return FileResponse(llms_path, media_type="text/plain; charset=utf-8")
    return HTMLResponse(
        "# HocNhanhTN\n\n> Hệ thống học nhanh trắc nghiệm thông minh cho học sinh & giáo viên - Chuẩn GDPT 2018.\n\n"
        "HocNhanhTN là nền tảng số hóa đề thi Word (.docx) và PDF thành phòng thi trực tuyến chuẩn Chương trình Giáo dục phổ thông 2018.\n\n"
        "## Tính năng & Liên kết chính\n"
        "- [Trang chủ HocNhanhTN](https://hocnhanhtn.online/): Nền tảng số hóa và tổ chức phòng thi trực tuyến.\n"
        "- [Quy trình số hóa](https://hocnhanhtn.online/#quy-trinh): Tự động nhận diện công thức Toán Lý Hóa.\n",
        media_type="text/plain; charset=utf-8"
    )


@router.get("/.well-known/ai-catalog.json", summary="Danh mục tài nguyên AI chuẩn ARD 1.0", include_in_schema=False)
@router.get("/ai-catalog.json", summary="Danh mục tài nguyên AI chuẩn ARD 1.0", include_in_schema=False)
def get_ai_catalog_json():
    catalog_path = os.path.join(settings.TEMPLATES_DIR, ".well-known", "ai-catalog.json")
    if not os.path.exists(catalog_path):
        catalog_path = os.path.join(settings.TEMPLATES_DIR, "ai-catalog.json")
    if os.path.exists(catalog_path):
        return FileResponse(catalog_path, media_type="application/json; charset=utf-8")
    raise HTTPException(status_code=404, detail="Không tìm thấy ai-catalog.json")
