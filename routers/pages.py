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


@router.get("/", response_class=HTMLResponse, summary="Giao diện chính & Đề thi trắc nghiệm (Tự động hiển thị Tên đề & Thumbnail khi gửi link)")
@router.get("/index.html", response_class=HTMLResponse, summary="Giao diện chính & Đề thi trắc nghiệm")
@router.get("/login", response_class=HTMLResponse, summary="Trang Đăng nhập tài khoản")
@router.get("/register", response_class=HTMLResponse, summary="Trang Đăng ký tài khoản")
@router.get("/auth", response_class=HTMLResponse, summary="Trang Đăng nhập & Đăng ký")
@router.get("/privacy", response_class=HTMLResponse, summary="Chính sách bảo mật quyền riêng tư")
@router.get("/terms", response_class=HTMLResponse, summary="Điều khoản dịch vụ & sử dụng")
@router.get("/about", response_class=HTMLResponse, summary="Giới thiệu về Dự án HocNhanhTN")
@router.get("/contact", response_class=HTMLResponse, summary="Liên hệ & Hỗ trợ kỹ thuật")
@router.get("/quiz/{quiz_id}", response_class=HTMLResponse, summary="Link trực tiếp tới đề thi")
async def get_index_page(request: Request, id: Optional[str] = None, quiz_id: Optional[str] = None):
    templates_dir = settings.TEMPLATES_DIR
    index_path = os.path.join(templates_dir, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy index.html")

    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    target_quiz_id = quiz_id or id

    # URL ảnh đại diện tuyệt đối khi gửi link (Facebook / Zalo / Telegram / iMessage)
    canon_domain = settings.CANONICAL_DOMAIN
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    base_url = f"{proto}://{host}".rstrip('/')
    site_domain = canon_domain if any(h in host for h in ["localhost", "127.0.0.1", "testserver"]) else base_url
    og_image_url = f"{site_domain}/unnamed.jpg"

    quiz_title = None
    quiz_desc = None
    if target_quiz_id:
        try:
            now = time.time()
            if target_quiz_id in QUIZ_CACHE and (now - QUIZ_CACHE[target_quiz_id]['time'] < 300):
                q_data = QUIZ_CACHE[target_quiz_id]['data']
            else:
                database = _get_db()
                if database is not None:
                    doc = database.collection('quizzes').document(target_quiz_id).get()
                    if doc.exists:
                        q_data = doc.to_dict()
                        QUIZ_CACHE[target_quiz_id] = {'time': now, 'data': q_data}
                    else:
                        q_data = None
                else:
                    q_data = None

            if q_data:
                raw_title = q_data.get('title')
                if raw_title:
                    quiz_title = raw_title.strip()
                    q_count = len(q_data.get('data', []))
                    time_limit = q_data.get('time_limit', 0)
                    desc_parts = [f"Đề thi: {quiz_title}"]
                    if q_count > 0:
                        desc_parts.append(f"{q_count} câu hỏi")
                    if time_limit > 0:
                        desc_parts.append(f"{time_limit} phút làm bài")
                    quiz_desc = " • ".join(desc_parts) + ". Hệ thống học nhanh trắc nghiệm HocNhanhTN chuẩn GDPT 2018."
        except Exception as e:
            logger.error(f"Lỗi truy vấn metadata đề thi {target_quiz_id}: {e}")

    current_url = html.escape(str(request.url))
    req_path = request.url.path.rstrip('/') or '/'

    full_page_title = None
    og_title = None
    page_desc = None
    page_canonical = f"{site_domain}/"

    if req_path == "/privacy":
        full_page_title = "Chính sách bảo mật (Privacy Policy) - HocNhanhTN"
        og_title = full_page_title
        page_desc = "Chính sách bảo mật quyền riêng tư và cam kết an toàn dữ liệu cho học sinh & giáo viên trên HocNhanhTN."
        page_canonical = f"{site_domain}/privacy"
    elif req_path == "/terms":
        full_page_title = "Điều khoản dịch vụ & Sử dụng (Terms of Service) - HocNhanhTN"
        og_title = full_page_title
        page_desc = "Điều khoản sử dụng và quy định dịch vụ số hóa đề thi, phòng thi trực tuyến chuẩn GDPT 2018 tại HocNhanhTN."
        page_canonical = f"{site_domain}/terms"
    elif req_path == "/about":
        full_page_title = "Về chúng tôi (About Us) - Dự án HocNhanhTN"
        og_title = full_page_title
        page_desc = "HocNhanhTN là dự án công nghệ giáo dục phi lợi nhuận hỗ trợ học sinh và giáo viên số hóa đề thi trắc nghiệm chuẩn GDPT 2018."
        page_canonical = f"{site_domain}/about"
    elif req_path == "/contact":
        full_page_title = "Liên hệ & Hỗ trợ kỹ thuật - HocNhanhTN"
        og_title = full_page_title
        page_desc = "Thông tin liên hệ, phản hồi đóng góp và hỗ trợ kỹ thuật nhanh chóng cho giáo viên & học sinh tại HocNhanhTN."
        page_canonical = f"{site_domain}/contact"
    elif quiz_title:
        escaped_title = html.escape(quiz_title)
        full_page_title = f"{escaped_title} - HocNhanhTN"
        og_title = escaped_title
        page_desc = html.escape(quiz_desc or f"Làm bài kiểm tra: {quiz_title}. Hệ thống học nhanh trắc nghiệm chuẩn GDPT 2018.")
        page_canonical = current_url
    elif target_quiz_id:
        page_canonical = current_url

    if full_page_title:
        html_content = re.sub(r'<title>.*?</title>', f'<title>{full_page_title}</title>', html_content, flags=re.IGNORECASE)
    if og_title:
        html_content = re.sub(r'<meta\s+property=["\']og:title["\']\s+content=["\'].*?["\']\s*/?>', f'<meta property="og:title" content="{og_title}">', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+name=["\']twitter:title["\']\s+content=["\'].*?["\']\s*/?>', f'<meta name="twitter:title" content="{og_title}">', html_content, flags=re.IGNORECASE)

    if page_desc:
        html_content = re.sub(r'<meta\s+name=["\']description["\']\s+content=["\'].*?["\']\s*/?>', f'<meta name="description" content="{page_desc}">', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+property=["\']og:description["\']\s+content=["\'].*?["\']\s*/?>', f'<meta property="og:description" content="{page_desc}">', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+name=["\']twitter:description["\']\s+content=["\'].*?["\']\s*/?>', f'<meta name="twitter:description" content="{page_desc}">', html_content, flags=re.IGNORECASE)

    # Cập nhật Canonical & Open Graph URL chuẩn SEO
    html_content = re.sub(r'<link\s+rel=["\']canonical["\']\s+href=["\'].*?["\']\s*/?>', f'<link rel="canonical" href="{page_canonical}">', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<meta\s+property=["\']og:url["\']\s+content=["\'].*?["\']\s*/?>', f'<meta property="og:url" content="{page_canonical}">', html_content, flags=re.IGNORECASE)

    # Luôn đảm bảo og:image, og:image:secure_url và twitter:image dùng ảnh tuyệt đối unnamed.jpg
    html_content = re.sub(r'<meta\s+property=["\']og:image["\']\s+content=["\'].*?["\']\s*/?>', f'<meta property="og:image" content="{og_image_url}">', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<meta\s+property=["\']og:image:secure_url["\']\s+content=["\'].*?["\']\s*/?>', f'<meta property="og:image:secure_url" content="{og_image_url}">', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<meta\s+name=["\']twitter:image["\']\s+content=["\'].*?["\']\s*/?>', f'<meta name="twitter:image" content="{og_image_url}">', html_content, flags=re.IGNORECASE)

    return HTMLResponse(content=html_content, media_type="text/html")


@router.get("/editor", summary="Giao diện Studio Biên tập & Soát lỗi Đề thi")
def get_editor_page():
    editor_path = os.path.join(settings.TEMPLATES_DIR, "editor.html")
    if os.path.exists(editor_path):
        return FileResponse(editor_path)
    raise HTTPException(status_code=404, detail="Không tìm thấy trang editor.html")


@router.get("/canvas", summary="Interactive Component Canvas cho Design System & UI Variants")
def get_canvas_page():
    canvas_path = os.path.join(settings.TEMPLATES_DIR, "canvas.html")
    if os.path.exists(canvas_path):
        return FileResponse(canvas_path)
    raise HTTPException(status_code=404, detail="Không tìm thấy trang canvas.html")


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
