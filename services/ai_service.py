import asyncio
import json
import logging
import math
import re
import time
from typing import Any, Dict, List, Optional

from services.gemini_tracker_service import gemini_tracker, mask_api_key

logger = logging.getLogger(__name__)

try:

    import pymupdf as fitz  # PyMuPDF

except ImportError:

    try:

        import fitz

    except ImportError:

        fitz = None



try:

    import json_repair

except ImportError:

    json_repair = None



# Bộ nhớ đệm Client để tái sử dụng kết nối (Connection Pooling), tránh TLS handshake lặp lại
_client_pool: Dict[str, Any] = {}

def get_gemini_client(api_key: str):
    """Lấy client từ pool hoặc tạo mới nếu chưa tồn tại."""
    key_clean = api_key.strip()
    if key_clean not in _client_pool:
        from google import genai
        _client_pool[key_clean] = genai.Client(api_key=key_clean)
    return _client_pool[key_clean]


class GeminiAPIException(Exception):
    """Ngoại lệ chuyên biệt cho lỗi Gemini AI, chứa thông tin chẩn đoán chi tiết."""
    def __init__(self, diagnostic: Dict[str, Any]):
        self.diagnostic = diagnostic
        err_name = diagnostic.get("error_name") or "Lỗi gọi AI"
        cause = diagnostic.get("cause") or ""
        code = diagnostic.get("error_code") or "AI_ERROR"
        super().__init__(f"{err_name}: {cause} ({code})")


def sanitize_error_text(text: str) -> str:
    """Làm sạch chuỗi lỗi, ẩn toàn bộ API Key nhạy cảm."""
    if not text:
        return ""
    return re.sub(
        r'AIzaSy[A-Za-z0-9_-]{33}',
        lambda m: mask_api_key(m.group(0)),
        str(text)
    )


def diagnose_gemini_error(
    error: Optional[Exception],
    keys_tried: Optional[List[str]] = None,
    models_tried: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Phân loại chi tiết lỗi khi gọi Gemini AI:
    Trả về cấu trúc chuẩn:
    - error_code: Mã lỗi chuẩn hóa (QUOTA_EXCEEDED_429, INVALID_API_KEY, MODEL_NOT_FOUND_404, SERVICE_UNAVAILABLE_503, NO_API_KEYS, REQUEST_TIMEOUT, RESPONSE_PARSE_ERROR, GENERAL_ERROR)
    - error_name: Tên lỗi tiếng Việt dễ hiểu ("Lỗi gì")
    - cause: Nguyên nhân sâu xa gốc rễ của lỗi ("Do đâu")
    - solution: Hướng dẫn chi tiết các bước xử lý / khắc phục cụ thể
    - technical_detail: Chi tiết kỹ thuật an toàn (đã ẩn API keys)
    - models_tried: Danh sách model đã thử gọi
    - keys_count: Số lượng API Key đã thử
    """
    keys_tried = keys_tried or []
    models_tried = models_tried or []

    # Nếu lỗi đã có chẩn đoán sẵn (GeminiAPIException)
    if isinstance(error, GeminiAPIException) and hasattr(error, "diagnostic"):
        diag = dict(error.diagnostic)
        if not diag.get("models_tried") and models_tried:
            diag["models_tried"] = models_tried
        return diag

    raw_err = str(error) if error else ""
    clean_err = sanitize_error_text(raw_err)
    err_lower = raw_err.lower()

    # 1. Chưa cấu hình API Key
    if not keys_tried or "chưa được cấu hình api key" in err_lower or "chưa cấu hình api key" in err_lower or "no api key" in err_lower:
        return {
            "status": "error",
            "error_code": "NO_API_KEYS",
            "error_name": "Chưa cấu hình Google Gemini API Key",
            "cause": "Hệ thống chưa có khóa API nào trong cơ sở dữ liệu (Firestore settings/gemini) hoặc biến môi trường (GEMINI_API_KEYS).",
            "solution": "1. Đăng nhập tài khoản quản trị (Admin) -> cài đặt hệ thống.\n2. Lấy API Key miễn phí tại Google AI Studio (https://aistudio.google.com/).\n3. Dán khóa API vào mục cấu hình Gemini API Key và lưu lại.",
            "technical_detail": clean_err or "api_keys list is empty",
            "models_tried": models_tried,
            "keys_count": 0
        }

    # 2. Quota / Rate limit (429 / resource exhausted)
    if any(k in err_lower for k in ["429", "quota", "resource_exhausted", "rate limit", "exhausted"]):
        return {
            "status": "error",
            "error_code": "QUOTA_EXCEEDED_429",
            "error_name": "Quá hạn mức gọi API Google Gemini (Quota Exceeded - 429)",
            "cause": "Tài khoản Google AI Studio đã chạm trần tốc độ gọi (thường là 15 yêu cầu/phút - 15 RPM ở gói Free Tier), hoặc đã hết hạn mức token được cấp miễn phí trong ngày.",
            "solution": "1. Vui lòng đợi khoảng 30 - 60 giây để Google hồi lại quota rồi bấm thử lại.\n2. Quản trị viên: Thêm 2-3 API Key từ các tài khoản Google khác nhau vào cài đặt quản trị (Admin) để hệ thống tự động luân chuyển khi một key bị chạm quota.\n3. Hoặc liên kết thẻ tín dụng (Pay-as-you-go) trên Google Cloud Console để mở rộng hạn mức lên 1000 RPM.",
            "technical_detail": clean_err,
            "models_tried": models_tried,
            "keys_count": len(keys_tried)
        }

    # 3. Invalid API Key / Auth (400 / 403 / api key not valid)
    if any(k in err_lower for k in ["api key not valid", "invalid api key", "api_key_invalid", "permission_denied", "unregistered"]) or ("403" in err_lower and "key" in err_lower):
        return {
            "status": "error",
            "error_code": "INVALID_API_KEY",
            "error_name": "Khóa API Google Gemini không hợp lệ hoặc đã bị vô hiệu hóa",
            "cause": "Khóa API được lưu trong hệ thống không chính xác, đã bị xóa/thu hồi trên Google Cloud Console, hoặc nhập sai định dạng.",
            "solution": "1. Quản trị viên truy cập https://aistudio.google.com/app/apikey để tạo khóa mới (bắt đầu bằng AIzaSy...).\n2. Vào trang cài đặt quản trị (Admin) -> ping kiểm tra khóa -> cập nhật khóa mới và xóa các khóa đã hỏng.",
            "technical_detail": clean_err,
            "models_tried": models_tried,
            "keys_count": len(keys_tried)
        }

    # 4. Model Not Found / Deprecated (404 / not found / unavailable)
    if any(k in err_lower for k in ["404", "not found", "no longer available", "unsupported model"]):
        return {
            "status": "error",
            "error_code": "MODEL_NOT_FOUND_404",
            "error_name": "Mô hình AI không tồn tại hoặc đã ngừng cung cấp (Model 404)",
            "cause": "Phiên bản mô hình AI yêu cầu không còn khả dụng trên tài khoản Google này hoặc đã bị ngừng hỗ trợ.",
            "solution": "1. Hệ thống đã tự động chuyển qua các model dự phòng (gemini-2.5-flash, gemini-2.5-flash-lite, gemini-flash-latest, gemini-2.0-flash).\n2. Nếu tất cả đều không tìm thấy, vui lòng bấm thử lại hoặc kiểm tra quyền truy cập mô hình trong Google AI Studio.",
            "technical_detail": clean_err,
            "models_tried": models_tried,
            "keys_count": len(keys_tried)
        }

    # 5. Service Unavailable / Overload (503 / 500 / high demand)
    if any(k in err_lower for k in ["503", "unavailable", "high demand", "overloaded", "capacity"]):
        return {
            "status": "error",
            "error_code": "SERVICE_UNAVAILABLE_503",
            "error_name": "Máy chủ Google Gemini đang quá tải tạm thời (503 Unavailable)",
            "cause": "Cụm máy chủ của Google AI đang tiếp nhận lưu lượng truy cập toàn cầu đột biến hoặc đang bảo trì tạm thời.",
            "solution": "1. Vui lòng chờ 15 - 30 giây rồi bấm thử lại.\n2. Khi máy chủ Google hạ tải, yêu cầu sẽ được xử lý lại bình thường.",
            "technical_detail": clean_err,
            "models_tried": models_tried,
            "keys_count": len(keys_tried)
        }

    # 6. Timeout / Deadline Exceeded
    if any(k in err_lower for k in ["timeout", "deadline", "timed out", "timedout"]):
        return {
            "status": "error",
            "error_code": "REQUEST_TIMEOUT",
            "error_name": "Hết thời gian chờ phản hồi từ AI (Request Timeout)",
            "cause": "Tài liệu đề thi quá dài hoặc đường truyền mạng quốc tế giữa máy chủ và Google Gemini bị chậm trễ kéo dài.",
            "solution": "1. Bấm thử lại sau vài giây.\n2. Nếu đề thi quá dài (hơn 50 câu), hãy chia thành các phần nhỏ hơn để AI xử lý nhanh hơn.",
            "technical_detail": clean_err,
            "models_tried": models_tried,
            "keys_count": len(keys_tried)
        }

    # 7. JSON Parse Error
    if any(k in err_lower for k in ["json", "parse", "decode", "syntaxerror"]) and "api" not in err_lower:
        return {
            "status": "error",
            "error_code": "RESPONSE_PARSE_ERROR",
            "error_name": "Không thể giải mã cấu trúc dữ liệu phản hồi từ AI (Parse Error)",
            "cause": "AI đã phản hồi nhưng nội dung trả về chứa ký tự đặc biệt hoặc cấu trúc JSON bị đứt đoạn bất thường.",
            "solution": "1. Bấm nút thử lại để AI sinh lại cấu trúc dữ liệu chuẩn mực.\n2. Bộ lọc tự động sửa JSON (json_repair) đã xử lý, lỗi này xuất hiện khi phản hồi bị ngắt kết nối đột ngột.",
            "technical_detail": clean_err,
            "models_tried": models_tried,
            "keys_count": len(keys_tried)
        }

    # 8. Mặc định: Lỗi tổng quát
    return {
        "status": "error",
        "error_code": "AI_GENERAL_ERROR",
        "error_name": "Lỗi giao tiếp với dịch vụ Google Gemini AI",
        "cause": f"Phát sinh lỗi trong quá trình xử lý: {clean_err[:180]}..." if len(clean_err) > 180 else f"Phát sinh lỗi trong quá trình xử lý: {clean_err}",
        "solution": "1. Vui lòng kiểm tra lại kết nối mạng và bấm thử lại.\n2. Nếu lỗi vẫn tiếp tục, vui lòng liên hệ quản trị viên để kiểm tra trạng thái khóa API.",
        "technical_detail": clean_err,
        "models_tried": models_tried,
        "keys_count": len(keys_tried)
    }



def fix_json_latex_escapes(json_str: str) -> str:

    """

    Sửa lỗi LLM trả về các ký tự LaTeX (như \\frac, \\rightarrow) bị parser JSON hiểu nhầm thành ký tự escape.

    Bảo vệ các lệnh LaTeX nhạy cảm có ký tự đầu là escape char của JSON (b, f, n, r, t).

    """

    # 1. Bảo vệ placeholder [IMG_X] trước khi sửa escape

    protected = re.sub(r'(\[IMG_\d+\])', lambda m: m.group(0), json_str)

    

    # 2. Bảo vệ các lệnh LaTeX phổ biến bắt đầu bằng b, f, n, r, t, s, v.v. (tránh \\f bị hiểu thành formfeed, \\t thành tab)

    latex_sensitive = (

        r'frac|sqrt|text|textbf|textit|mathrm|times|tan|tau|theta|to|'

        r'nearrow|searrow|nwarrow|swarrow|uparrow|downarrow|'
        r'neq|nu|nabla|rho|right|rightarrow|rightleftharpoons|'

        r'beta|bar|begin|binom|bf|sum|prod|int|lim|vec|hat|left|ln|log|sin|cos|alpha|lambda|pi|phi|omega|gamma|delta|sigma|mu|epsilon|subset|supset|in|notin|cap|cup|forall|exists|le|ge|cdot'

    )

    # Bảo vệ toàn bộ lệnh LaTeX có 2 ký tự trở lên (như \nearrow, \searrow, \frac, \text, \begin, \rho...)
    protected = re.sub(r'(?<!\\)\\(?=[a-zA-Z]{2,})', r'\\\\', protected)
    protected = re.sub(rf'(?<!\\)\\(?={latex_sensitive}\b)', r'\\\\', protected)

    # Bảo vệ dấu ngoặc LaTeX \\( \\) \\[ \\]

    protected = re.sub(r'(?<!\\)\\([()\[\]])', r'\\\\\1', protected)
    return protected


UNICODE_SUB_MAP = {
    '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
    '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
    '₊': '+', '₋': '-', 'ₐ': 'a', 'ₑ': 'e', 'ₒ': 'o',
    'ₓ': 'x', 'ₕ': 'h', 'ₖ': 'k', 'ₗ': 'l', 'ₘ': 'm',
    'ₙ': 'n', 'ₚ': 'p', 'ₛ': 's', 'ₜ': 't',
}
UNICODE_SUP_MAP = {
    '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
    '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
    '⁺': '+', '⁻': '-',
}

CHEM_ELEMENTS = (
    'He|Li|Be|Ne|Na|Mg|Al|Si|Cl|Ar|Ca|Sc|Ti|Cr|Mn|Fe|Co|Ni|Cu|Zn|Ga|Ge|As|Se|Br|Kr|'
    'Rb|Sr|Zr|Nb|Mo|Tc|Ru|Rh|Pd|Ag|Cd|In|Sn|Sb|Te|Xe|Cs|Ba|Pt|Au|Hg|Pb|Bi|'
    'H|B|C|N|O|F|P|S|K|I|U|V|Y|W'
)
CHEM_ELEM_PATTERN = f'(?:{CHEM_ELEMENTS})'
CHEM_FORMULA_PATTERN = (
    rf'(?<![A-Za-z0-9_])'
    rf'(?:\((?:{CHEM_ELEM_PATTERN}|\d+)+\)\d*|{CHEM_ELEM_PATTERN}\d*)*'
    rf'(?:{CHEM_ELEM_PATTERN}\d+|\)\d+)'
    rf'(?:{CHEM_ELEM_PATTERN}\d*|\))*'
)


PERCENT_AND_UNITS_PATTERN = (
    r'(?<![A-Za-z0-9_])'
    r'\d+(?:[.,]\d+)?'
    r'\s*'
    r'(?:'
    r'[%‰]'
    r'|M\b|mol(?:/[Ll])?\b|gam\b|kg\b|mg\b|g(?:/(?:mL|ml|cm3))?\b'
    r'|mL\b|ml\b|l\b|lít\b|lit\b'
    r'|atm\b|bar\b|mmHg\b|torr\b'
    r'|ppm\b|ppb\b'
    r'|V\b|W\b|J\b|kJ\b|cal\b|kcal\b'
    r'|[°℃]|oC\b|độ\b'
    r')'
)


def _format_chem_formula_token(tok: str) -> str:
    """Chuyen doi so chi so duoi sau nguyen to hoac dau ngoac thanh <sub>."""
    return re.sub(rf'({CHEM_ELEM_PATTERN}|\))\s*(\d+)', r'\1<sub>\2</sub>', tok)


def clean_subscripts_and_formulas(text: str) -> str:
    r"""
    Tu dong chuan hoa toan dien cong thuc hoa hoc va chi so duoi/tren cho de thi:
    1. Bao ve an toan tuyet doi: dai luong do luong (%, M, mol, gam, mL...), anh [IMG_X], bang bieu HTML va LaTeX.
    2. Chuyen doi ky tu chi so duoi Unicode (₁₇, ₃₅, ₂, ₄) sang <sub>...</sub> va chi so tren Unicode (², ³, ⁺, ⁻) sang <sup>...</sup>.
    3. Sua loi khoang trang roi rac trong cong thuc hoa hoc: (C 17 H 35 COO) 3 C 3 H 5 -> (C17H35COO)3C3H5.
    4. Tu dong nhan dien cong thuc hoa hoc dang so thuong (H2SO4, Fe2O3, CO2, H2O, C2H5OH, CH3COOH, (C17H35COO)3C3H5) va chuyen thanh <sub>...</sub>.
    5. Sua chi so duoi dang gach duoi (CH_2, CO_2, x_1, u_n) thanh <sub>...</sub>.
    6. Xoa triet de khoang trang thua giua chu cai va chi so (C <sub>17</sub> -> C<sub>17</sub>, ) <sub>3</sub> -> )<sub>3</sub>).
    """
    if not text or not isinstance(text, str):
        return text

    placeholders = []

    def save_ph(m):
        placeholders.append(m.group(0))
        return f'XYZPH{len(placeholders)-1}XYZ'

    # 1. Bao ve placeholder anh [IMG_X], [HINH_ANH_X]
    text = re.sub(r'(\[(?:IMG|HÌNH_ẢNH)_\d+\])', save_ph, text)

    # 2. Bao ve cac khoi LaTeX math (inline va display) voi bat ky so luong backslash nao
    text = re.sub(r'(\\+\[[\s\S]*?\\+\]|\\+\([\s\S]*?\\+\)|\$\$[\s\S]*?\$\$|\$[^\$]+?\$)', save_ph, text)

    # 3. Bao ve bang bieu HTML va cac the HTML khac (ngoai tru sub, sup de duoc don dep khoang trang)
    text = re.sub(r'(<table\b[\s\S]*?<\/table>|<(?!/?(?:sub|sup)\b)[^>]+>)', save_ph, text)

    # 4. Bao ve cac dai luong do luong (%, mol, M, gam, mL, do C...) de khong bi bien thanh chi so hoa hoc (vd: NaOH 30% -> khong thanh NaOH30)
    text = re.sub(PERCENT_AND_UNITS_PATTERN, save_ph, text)

    # 5. Chuyen doi chi so duoi / chi so tren Unicode sang <sub> / <sup>
    sub_chars = ''.join(UNICODE_SUB_MAP.keys())
    text = re.sub(f'[{sub_chars}]+', lambda m: '<sub>' + ''.join(UNICODE_SUB_MAP.get(c, c) for c in m.group(0)) + '</sub>', text)
    sup_chars = ''.join(UNICODE_SUP_MAP.keys())
    text = re.sub(f'[{sup_chars}]+', lambda m: '<sup>' + ''.join(UNICODE_SUP_MAP.get(c, c) for c in m.group(0)) + '</sup>', text)

    # 6. Thu gon khoang trang roi rac trong cong thuc hoa hoc: (C 17 H 35 COO) 3 C 3 H 5 -> (C17H35COO)3C3H5
    def _fix_chem_parens(m):
        inner = m.group(1)
        cleaned = re.sub(rf'({CHEM_ELEM_PATTERN})\s+(\d+)', r'\1\2', inner)
        cleaned = re.sub(rf'({CHEM_ELEM_PATTERN}|\d+)\s+({CHEM_ELEM_PATTERN})', r'\1\2', cleaned)
        cleaned = re.sub(r'\s+', '', cleaned)
        return f'({cleaned})'

    text = re.sub(rf'\((?=[^)]*[A-Za-z])((?:{CHEM_ELEM_PATTERN}|\d+|\s)+)\)', _fix_chem_parens, text)
    # Chi thu gon ngoac hoa hoc ro rang theo sau boi chi so so hoc: vd (OH) 2 -> (OH)2, (SO4) 3 -> (SO4)3
    text = re.sub(r'(\([A-Za-z]+[0-9]*[A-Za-z0-9]*\))\s+(\d+)', r'\1\2', text)
    # Thu gon phan con lai cua phuc chat/chat beo: vd (C17H35COO)3 C 3 H 5 -> (C17H35COO)3C3H5
    def _fix_after_paren_tail(m):
        return m.group(1) + re.sub(r'\s+', '', m.group(2))
    text = re.sub(r'(\([A-Za-z0-9]+\)\d+)\s+([A-Z]\s*\d+(?:\s*[A-Z]\s*\d+)*)', _fix_after_paren_tail, text)
    # Thu gon cac cum nguyen to kem so ro rang: vd C17 H35 -> C17H35
    text = re.sub(r'([A-Z][a-z]?\d+)\s+([A-Z][a-z]?\d+)', r'\1\2', text)

    # 7. Don dep khoang trang ben trong the <sub>, <sup>
    text = re.sub(r'<sub>\s*([^<]+?)\s*</sub>', r'<sub>\1</sub>', text)
    text = re.sub(r'<sup>\s*([^<]+?)\s*</sup>', r'<sup>\1</sup>', text)
    text = re.sub(r'([A-Za-z\)\>\]])\s+<sub>', r'\1<sub>', text)
    text = re.sub(r'([A-Za-z\)\>\]])\s+<sup>', r'\1<sup>', text)
    text = re.sub(r'</sub>\s+([A-Z])(?!YZPH)', r'</sub>\1', text)

    # 8. Sua chi so duoi dang _{...} va _so thanh <sub>...</sub>
    text = re.sub(r'([A-Za-z0-9\)\>\]])\s*_\s*\{([^}]+)\}', r'\1<sub>\2</sub>', text)
    text = re.sub(r'([A-Za-z0-9\)\>\]])\s*_\s*([0-9]+)', r'\1<sub>\2</sub>', text)
    text = re.sub(r'([A-Z][a-z]?|(?<![a-zA-Z\u00C0-\u1EF9])[uvxyzmkn])\s*_\s*([a-z0-9]+)', r'\1<sub>\2</sub>', text)
    text = re.sub(r'([A-Za-z0-9\)\>\]])\s*\^\s*\{([^}]+)\}', r'\1<sup>\2</sup>', text)
    text = re.sub(r'([A-Za-z0-9\)\>\]])\s*\^\s*([0-9\+\-]+)', r'\1<sup>\2</sup>', text)

    # 9. Tu dong nhan dien cong thuc hoa hoc co so thuong (vd: H2SO4, Fe2O3, (C17H35COO)3C3H5, Ca(OH)2, CO2)
    def _replace_chem_token(m):
        tok = m.group(0)
        if '<sub>' in tok or '<sup>' in tok:
            return tok
        return _format_chem_formula_token(tok)

    text = re.sub(CHEM_FORMULA_PATTERN, _replace_chem_token, text)

    # 10. Chuan hoa bien so toan/ly ngoai LaTeX: x1, x2, u1, un, v0 (tranh bat nham tu tieng Viet nhu 'Cau 4')
    text = re.sub(r'(?<![a-zA-Z\u00C0-\u1EF9])([xyz])\s*([1-9])(?![a-zA-Z0-9\u00C0-\u1EF9])', r'\1<sub>\2</sub>', text)
    text = re.sub(r'(?<![a-zA-Z\u00C0-\u1EF9])([uS])(?:\s*([1-9])|_([1-9n]))(?![a-zA-Z0-9\u00C0-\u1EF9])', lambda m: f"{m.group(1)}<sub>{m.group(2) or m.group(3)}</sub>", text)
    text = re.sub(r'(?<![a-zA-Z\u00C0-\u1EF9])(v)\s*(0)(?![a-zA-Z0-9\u00C0-\u1EF9])', r'\1<sub>\2</sub>', text)

    # 11. Chuan hoa don vi do luong pho bien: cm3, m2, m3, dm3, mm2
    text = re.sub(r'\b(cm|dm|mm|m|km)\s*([23])\b', r'\1<sup>\2</sup>', text)

    # 12. Khoi phuc lai cac noi dung duoc bao ve theo thu tu nguoc lai
    for i in range(len(placeholders) - 1, -1, -1):
        text = text.replace(f'XYZPH{i}XYZ', placeholders[i])

    # 13. Quet lai triet de khoang trang giua chu cai va sub/sup sau khi hoan tat
    text = re.sub(r'([A-Za-z\)\>\]])\s+<sub>', r'\1<sub>', text)
    text = re.sub(r'([A-Za-z\)\>\]])\s+<sup>', r'\1<sup>', text)
    text = re.sub(r'</sub>\s+([A-Z])(?!YZPH)', r'</sub>\1', text)

    return text



def clean_question_prefix(text: str) -> str:
    """Loại bỏ tiền tố 'Câu 1:', 'Câu 1.', 'Bài 1:', '1.', '[Câu 1]' khỏi nội dung câu hỏi, đồng thời cân bằng các thẻ đóng mở HTML."""
    if not text or not isinstance(text, str):
        return ""

    raw = text.strip()
    cleaned = re.sub(
        r'^(?:<[^>]+>\s*)*(?:(?:\[|\()?\s*(?:Câu\s*hỏi|Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*(?:<\/[^>]+>\s*)*',
        '',
        raw,
        flags=re.IGNORECASE
    )
    if not cleaned:
        cleaned = re.sub(
            r'^(?:(?:\[|\()?\s*(?:Câu\s*hỏi|Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*',
            '',
            raw,
            flags=re.IGNORECASE
        )

    # Cân bằng thẻ đóng mồ côi nếu mở đầu bằng một thẻ đóng (ví dụ: Acid linoleic (LA)</b>)
    first_close = re.search(r'</([a-zA-Z0-9]+)>', cleaned)
    first_open = re.search(r'<([a-zA-Z0-9]+)(?:\s+[^>]*)?>', cleaned)
    if first_close and (not first_open or first_close.start() < first_open.start()):
        tag = first_close.group(1).lower()
        if tag in ['b', 'strong', 'i', 'em', 'u']:
            cleaned = f'<{tag}>{cleaned}'

    return cleaned.strip()





def clean_option_text(opt: str) -> tuple:
    """
    Chuẩn hóa phương án chuẩn Bộ GD&ĐT và HocNhanhTN:
    - Bóc tách nội dung thuần túy (không dính tiền tố 'A. ', 'a) ', '*A. ', '<u>a)</u>', '<MARK><u>a)</u></MARK>')
    - Chuẩn HocNhanhTN Cách 3: Phát hiện gạch chân (thẻ <u>) hoặc <MARK> ở ký hiệu phương án -> Đáp án Đúng (is_correct=True)
    - Phát hiện đánh dấu đáp án đúng (*, [ĐÚNG], (Đúng), ✓, ✔)
    - Phát hiện đánh dấu đáp án sai ([SAI], (Sai), ✗, ✘)
    - Giữ và bảo toàn nhãn ma trận HocNhanhTN: [0, NB], [1, TH], [2, VD], [3, VDC] nếu có
    - Trả về: (nội_dung_sạch, is_correct, is_false, ký_tự_gốc)
    """
    if not opt:
        return "", False, False, ""

    opt_str = str(opt).strip()

    # 1. Phát hiện đánh dấu Đúng theo chuẩn Bộ GD&ĐT và chuẩn HocNhanhTN
    has_leading_asterisk = bool(re.match(r'^\s*[\(\[]?\s*\*\s*[A-Fa-f\d]', opt_str) or re.match(r'^\s*\*\s*[\(\[]?[A-Fa-f\d]', opt_str))
    
    # Chuẩn HocNhanhTN Cách 3: Gạch chân ký hiệu phương án đúng: <u>a)</u>, <u>a</u>), <u>a.</u>, <u>[0, NB] a)</u>, v.v.
    has_underline_marker = bool(re.search(
        r'^\s*(?:<MARK>\s*)?(?:\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*)?(?:<MARK>\s*)?<u>\s*(?:\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*)?\*?[A-Fa-f\d]',
        opt_str,
        re.IGNORECASE
    ))
    
    # Kiểm tra <MARK> bọc ký hiệu phương án
    has_mark_prefix = bool(re.search(
        r'^\s*<MARK>\s*(?:<u>)?\s*(?:\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*)?\*?[A-Fa-f\d][\)\.\:\-\]\/]',
        opt_str,
        re.IGNORECASE
    ))

    # Phát hiện gạch chân (<u>), highlight / tô đỏ / tô màu nền (<MARK>), dấu tick trong phương án
    has_mark_tag = bool(re.search(r'</?MARK>', opt_str, re.IGNORECASE))
    # Chỉ coi <u> là dấu hiệu đáp án đúng nếu gạch chân ở nhãn (<u>A.</u>) hoặc gạch chân toàn bộ nội dung phương án
    # Không tính gạch chân một chữ cái/âm tiết bên trong từ (ví dụ bài tập phát âm: ch<u>i</u>ldhood)
    has_phonetic_underline = bool(re.search(r'\b\w+<u>\w+</u>|\b\w*<u>[a-zA-Z]{1,2}</u>\w+\b', opt_str))
    has_underline_tag = bool(re.search(r'</?u>', opt_str, re.IGNORECASE)) and not has_phonetic_underline
    has_star = '*' in opt_str[:15]
    has_tick = any(c in opt_str for c in ['✓', '✔', '☑'])

    has_correct_tag = bool(re.search(r'\[(ĐÚNG|DUNG|Đ|TRUE|T)\]|\((Đúng|Dung|Đ|True|T)\)|✓|✔|☑', opt_str, re.IGNORECASE))
    is_correct = has_leading_asterisk or has_underline_marker or has_mark_prefix or has_correct_tag or has_mark_tag or has_underline_tag or has_star or has_tick

        # Phát hiện đánh dấu ở cuối dòng (ví dụ \tĐ, \tS, - Đ, - S, - Đúng, - Sai, : Đúng, : Sai)
    trailing_corr_m = re.search(r'(?:[\t\|]|[\-–—\:\;]\s*|\s{2,}|\s*-\s*|\s*:\s*)(Đúng|ĐÚNG|DUNG|dung|Đ)\s*$', opt_str, re.IGNORECASE)
    trailing_fls_m = re.search(r'(?:[\t\|]|[\-–—\:\;]\s*|\s{2,}|\s*-\s*|\s*:\s*)(Sai|SAI|S)\s*$', opt_str, re.IGNORECASE)

    has_correct_tag = bool(re.search(r'\[(ĐÚNG|DUNG|Đ|TRUE|T)\]|\((Đúng|Dung|Đ|True|T)\)|✓|✔|☑', opt_str, re.IGNORECASE))
    is_correct = has_leading_asterisk or has_underline_marker or has_mark_prefix or has_correct_tag or has_mark_tag or has_underline_tag or has_star or has_tick or bool(trailing_corr_m)

    is_false = bool(re.search(r'\[(SAI|S|FALSE|F)\]|\((Sai|S|False|F)\)|✗|✘', opt_str, re.IGNORECASE)) or bool(trailing_fls_m)

    if trailing_fls_m:
        is_correct = False
        is_false = True
    elif trailing_corr_m:
        is_correct = True
        is_false = False

    # Phát hiện đánh dấu Đúng/Sai dạng [ Đúng / Sai ] - ĐÚNG / SAI
    tf_bracket_tag = re.search(r'\[\s*(?:Đúng|Đ)\s*[/|\\]\s*(?:Sai|S)\s*\](?:\s*[\-–—\:]\s*(ĐÚNG|SAI|Đ|S|True|False))?', opt_str, re.IGNORECASE)
    if tf_bracket_tag:
        tag_val = (tf_bracket_tag.group(1) or '').upper()
        if tag_val in ['ĐÚNG', 'Đ', 'TRUE']:
            is_correct = True
            is_false = False
        elif tag_val in ['SAI', 'S', 'FALSE']:
            is_correct = False
            is_false = True

    # 2. Xóa các thẻ đánh dấu explicit [ĐÚNG], [SAI], [ Đúng / Sai ], checkmarks và đánh dấu Đ/S ở đuôi
    cleaned = re.sub(r'\[\s*(?:Đúng|Đ)\s*[/|\\]\s*(?:Sai|S)\s*\](?:\s*[\-–—\:]\s*(?:ĐÚNG|SAI|Đ|S|True|False))?', '', opt_str, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'\[(ĐÚNG|DUNG|SAI|Đ|S|TRUE|FALSE|T|F)\]|\((Đúng|Dung|Sai|Đ|S|True|False|T|F)\)|✓|✔|✗|✘', '', cleaned, flags=re.IGNORECASE).strip()
    if trailing_corr_m:
        cleaned = re.sub(r'(?:[\t\|]|[\-–—\:\;]\s*|\s{2,}|\s*-\s*|\s*:\s*)(?:Đúng|ĐÚNG|DUNG|dung|Đ)\s*$', '', cleaned, flags=re.IGNORECASE).strip()
    if trailing_fls_m:
        cleaned = re.sub(r'(?:[\t\|]|[\-–—\:\;]\s*|\s{2,}|\s*-\s*|\s*:\s*)(?:Sai|SAI|S)\s*$', '', cleaned, flags=re.IGNORECASE).strip()

    # 3. Trích xuất tag ma trận HocNhanhTN (ví dụ [0, NB], [1, TH], [NB]...) nếu có trước phương án
    azota_tag = ""
    m_tag = re.match(r'^\s*(?:<MARK>\s*|<u>\s*)*(\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\])\s*(?:</MARK>\s*|</u>\s*)*', cleaned, re.IGNORECASE)
    if m_tag:
        azota_tag = m_tag.group(1).strip()
        cleaned = cleaned[m_tag.end():].strip()

    # 4. Trích xuất ký tự phương án (A-F hoặc a-d hoặc số)
    # Khớp mọi thẻ HTML bao quanh ký hiệu phương án (mở hoặc đóng: p, b, span, font...), TRỪ thẻ ảnh/bảng
    WRAP_TAG = r'(?:<(?!\/?(?:img|table)\b)[^>]+>\s*)'
    char_match = re.match(
        rf'^\s*{WRAP_TAG}*(?:\*\s*)?[\(\[]?([A-Fa-f\d])[\)\.\:\-\]\/]{WRAP_TAG}*\s*(.*)',
        cleaned,
        flags=re.DOTALL | re.IGNORECASE
    )
    if not char_match:
        char_match = re.match(
            rf'^\s*{WRAP_TAG}*(?:\*\s*)?[\(\[]?([A-Fa-f\d]){WRAP_TAG}*[\)\.\:\-\]\/]\s*(.*)',
            cleaned,
            flags=re.DOTALL | re.IGNORECASE
        )

    if char_match:
        extracted_char = char_match.group(1)
        cleaned_content = char_match.group(2).strip()
    else:
        extracted_char = ""
        cleaned_content = cleaned.strip()

    # Safety fallback: nếu cleaned_content bị rỗng nhưng cleaned gốc có chứa thẻ hình ảnh <img> hoặc [IMG_
    if not cleaned_content and ('<img' in cleaned.lower() or '[img_' in cleaned.lower()):
        fallback_content = re.sub(
            rf'^\s*{WRAP_TAG}*(?:\*\s*)?[\(\[]?[A-Fa-f\d][\)\.\:\-\]\/]{WRAP_TAG}*\s*',
            '',
            cleaned,
            flags=re.IGNORECASE
        )
        if fallback_content:
            cleaned_content = fallback_content.strip()

    # 5. Nếu sau ký hiệu phương án lại có tag HocNhanhTN (ví dụ a) [0, NB] Mệnh đề...)
    if not azota_tag:
        m_tag_post = re.match(r'^\s*(\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\])\s*(.*)', cleaned_content, re.IGNORECASE | re.DOTALL)
        if m_tag_post:
            azota_tag = m_tag_post.group(1).strip()
            cleaned_content = m_tag_post.group(2).strip()

    # Loại bỏ các thẻ <MARK>, </MARK>, <u>, </u> đánh dấu đáp án khỏi nội dung phương án
    cleaned_content = re.sub(r'</?MARK>', '', cleaned_content, flags=re.IGNORECASE)
    cleaned_content = re.sub(r'</?u>', '', cleaned_content, flags=re.IGNORECASE).strip()
    # Loại bỏ thẻ đóng mồ côi ở đầu nội dung phương án (ví dụ </b>, </i>)
    cleaned_content = re.sub(r'^\s*</(?:b|B|i|I|u|U|MARK|mark|strong|STRONG)>\s*', '', cleaned_content).strip()

    # Giữ tiền tố ma trận HocNhanhTN chuẩn hóa
    if azota_tag:
        cleaned_content = f"{azota_tag} {cleaned_content}".strip()

    return cleaned_content, is_correct, is_false, extracted_char





def parse_tf_answer(raw_ca: Any) -> Dict[str, bool]:
    """Phân tích chuẩn xác các định dạng đáp án Đúng/Sai thành dict {'a': bool, 'b': bool, 'c': bool, 'd': bool}."""
    if not raw_ca:
        return {}

    tf_dict: Dict[str, bool] = {}

    if isinstance(raw_ca, dict):
        for k, v in raw_ca.items():
            k_clean = str(k).lower().strip().replace(')', '').replace('.', '')
            if k_clean in ['a', 'b', 'c', 'd']:
                if isinstance(v, bool):
                    tf_dict[k_clean] = v
                elif isinstance(v, (int, float)):
                    tf_dict[k_clean] = bool(v)
                elif isinstance(v, str):
                    tf_dict[k_clean] = v.strip().lower() in ['đ', 'đúng', 'dung', 'true', 't', '1', 'yes', 'y']
        return tf_dict

    elif isinstance(raw_ca, (list, tuple)) and len(raw_ca) >= 2:
        for idx, k in enumerate(['a', 'b', 'c', 'd'][:len(raw_ca)]):
            v = raw_ca[idx]
            if isinstance(v, bool):
                tf_dict[k] = v
            elif isinstance(v, (int, float)):
                tf_dict[k] = bool(v)
            elif isinstance(v, str):
                tf_dict[k] = v.strip().lower() in ['đ', 'đúng', 'dung', 'true', 't', '1', 'yes', 'y']
        return tf_dict

    elif isinstance(raw_ca, str):
        raw_str = raw_ca.strip()
        if not raw_str:
            return {}

        found_any = False
        for k in ['a', 'b', 'c', 'd']:
            m = re.search(rf'(?:^|\b|[\(\[])\s*{k}\s*(?:[\)\:\-\.\=]\s*|\s+)(?:là\s+)?(ĐÚNG|DUNG|SAI|TRUE|FALSE|Đ|S|T|F|1|0)\b', raw_str, re.IGNORECASE)
            if not m:
                m = re.search(rf'(?:^|\b|[\(\[])\s*{k}\s*[\)\:\-\.\=]\s*([^\s,;\/]+)', raw_str, re.IGNORECASE)
            if m:
                val_str = m.group(1).lower().strip()
                tf_dict[k] = val_str in ['đ', 'đúng', 'dung', 'true', 't', '1', 'yes', 'y']
                found_any = True

        if found_any:
            return tf_dict

        seq = re.findall(r'\b(Đ|S|ĐÚNG|SAI|TRUE|FALSE|T|F)\b', raw_str, re.IGNORECASE)
        if len(seq) == 4 or (len(seq) in [2, 3] and not re.search(r'[A-F]\.', raw_str)):
            for idx, k in enumerate(['a', 'b', 'c', 'd'][:len(seq)]):
                tf_dict[k] = seq[idx].lower() in ['đ', 'đúng', 'true', 't', '1']
            return tf_dict

    return tf_dict





def extract_mcq_options_from_text(text: str) -> tuple:
    """
    Tự động phát hiện và bóc tách các phương án A, B, C, D (CHỮ IN HOA) nếu bị lẫn trong nội dung câu hỏi.
    Trả về (question_stem, [A. ..., B. ..., C. ..., D. ...])
    """
    if not text or not isinstance(text, str):
        return text, []

    pattern = re.compile(
        r'(?:^|\n|\r|\t|\s{2,}|(?<=[;\.\:\?!])\s*|(?<=[\)\}\]\'\"\>])\s*)'
        r'((?:(?:<MARK>\s*|<u>\s*|<b>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC|nb|th|vd|vdc)\s*\]\s*(?:</MARK>\s*|</u>\s*|</b>\s*)*)?'
        r'(?:<MARK>\s*|<u>\s*|<b>\s*)*'
        r'(?:\(?\[?(\*?[A-F])[\.\:\)]|\b(\*?[A-F])[\.\:\)]))\s*'
    )
    table_ranges = [
        (tbl_m.start(), tbl_m.end())
        for tbl_m in re.finditer(r'<table\b[^>]*>.*?</table>', text, flags=re.DOTALL | re.IGNORECASE)
    ]
    def is_inside_table(pos: int) -> bool:
        return any(t_start <= pos < t_end for t_start, t_end in table_ranges)

    matches = [m for m in pattern.finditer(text) if not is_inside_table(m.start())]
    if len(matches) < 2:
        return text, []

    matched_chars = []
    valid_matches = []
    expected_next = 'A'
    for m in matches:
        raw_char = (m.group(2) or m.group(3)).replace('*', '').strip()
        if raw_char == expected_next:
            matched_chars.append(raw_char)
            valid_matches.append(m)
            if raw_char == 'A': expected_next = 'B'
            elif raw_char == 'B': expected_next = 'C'
            elif raw_char == 'C': expected_next = 'D'
            elif raw_char == 'D': expected_next = None

    if len(matched_chars) < 2:
        return text, []

    stem = text[:valid_matches[0].start()].strip()
    options = []
    for idx, vm in enumerate(valid_matches):
        full_block = text[vm.start(): valid_matches[idx + 1].start() if idx + 1 < len(valid_matches) else len(text)].strip()
        if idx == len(valid_matches) - 1:
            ans_split = re.split(
                r'\n\s*(?:Lời giải|Hướng dẫn giải|Giải thích|HDG|Đáp án|Đáp số)\s*[\:\-\=]',
                full_block,
                flags=re.IGNORECASE
            )
            if len(ans_split) > 1:
                full_block = ans_split[0].strip()
        options.append(full_block)

    return stem, options


def extract_sub_statements_from_text(text: str) -> tuple:
    """
    Tự động phát hiện và bóc tách các ý a), b), c), d) (CHỮ THƯỜNG) nếu bị lẫn trong nội dung câu hỏi.
    Hỗ trợ chuẩn HocNhanhTN có tiền tố ma trận [0, NB], [1, TH], [2, VD], [3, VDC] và markup <u>, <MARK>.
    Trả về (question_stem, [a) ..., b) ..., c) ..., d) ...])
    """
    if not text or not isinstance(text, str):
        return text, []

    # Pattern CHỮ THƯỜNG a-d (tuyệt đối KHÔNG có re.IGNORECASE để tránh nhận nhầm A, B, C, D của MCQ)
    pattern = re.compile(
        r'(?:^|\n|\r|\t|\s{2,}|(?<=[;\.\:\?!])\s*|(?<=[\)\}\]\'\"\>])\s*)'
        r'((?:(?:<MARK>\s*|<u>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*(?:</MARK>\s*|</u>\s*)*)?'
        r'(?:<MARK>\s*|<u>\s*)*'
        r'(?:\(?\[?(\*?[a-d])[\.\:\)\/\]\-]|\b(\*?[a-d])[\.\:\)\/]))\s*'
    )
    table_ranges = [
        (tbl_m.start(), tbl_m.end())
        for tbl_m in re.finditer(r'<table\b[^>]*>.*?</table>', text, flags=re.DOTALL | re.IGNORECASE)
    ]
    def is_inside_table_sub(pos: int) -> bool:
        return any(t_start <= pos < t_end for t_start, t_end in table_ranges)

    matches = [m for m in pattern.finditer(text) if not is_inside_table_sub(m.start())]
    if len(matches) < 2:
        return text, []

    matched_chars = []
    valid_matches = []
    expected_next = 'a'
    for m in matches:
        raw_char = (m.group(2) or m.group(3)).replace('*', '').strip()
        if raw_char == expected_next:
            matched_chars.append(raw_char)
            valid_matches.append(m)
            if raw_char == 'a': expected_next = 'b'
            elif raw_char == 'b': expected_next = 'c'
            elif raw_char == 'c': expected_next = 'd'
            elif raw_char == 'd': expected_next = None

    if len(matched_chars) < 2:
        return text, []

    stem = text[:valid_matches[0].start()].strip()
    options = []
    for idx, vm in enumerate(valid_matches):
        full_block = text[vm.start(): valid_matches[idx + 1].start() if idx + 1 < len(valid_matches) else len(text)].strip()
        if idx == len(valid_matches) - 1:
            ans_split = re.split(
                r'\n\s*(?:Lời giải|Hướng dẫn giải|Giải thích|HDG|Đáp án|Đáp số)\s*[\:\-\=]',
                full_block,
                flags=re.IGNORECASE
            )
            if len(ans_split) > 1:
                full_block = ans_split[0].strip()
        options.append(full_block)

    return stem, options


def normalize_question_data(item: Dict[str, Any], use_ai: bool = True) -> Dict[str, Any]:
    """
    Chuẩn hóa toàn diện dữ liệu câu hỏi theo chuẩn Bộ GD&ĐT (GDPT 2018):
    1. Trắc nghiệm nhiều lựa chọn (mcq): 4 lựa chọn A, B, C, D, đáp án khớp nguyên văn với lựa chọn A-D.
    2. Trắc nghiệm Đúng / Sai (true_false): 4 ý a), b), c), d), đáp án dict {"a": bool, "b": bool, "c": bool, "d": bool}.
    3. Trắc nghiệm Trả lời ngắn (short_answer): options=[], đáp án chuỗi ngắn.
    Làm sạch chỉ số dưới hóa học/toán học (CH_2 -> CH<sub>2</sub>), giữ nguyên ảnh [IMG_X] và thẻ HTML.
    Loại bỏ triệt để tiền tố 'Câu 1:', '1.' bị lặp lại trong nội dung câu hỏi.
    """
    if not isinstance(item, dict):
        return item

    # 1. Trích xuất question_number nếu AI hoặc parser trả về
    raw_num = item.get("question_number") or item.get("question_id") or item.get("id") or item.get("stt") or item.get("number")
    if raw_num is not None:
        try:
            m_num = re.search(r'\d+', str(raw_num))
            if m_num:
                item["question_number"] = int(m_num.group(0))
        except Exception:
            pass

    # 2. Chuẩn hóa question: kiểm tra các tên trường thay thế của LLM
    raw_q = str(
        item.get("question") or
        item.get("question_content") or
        item.get("content") or
        item.get("cau_hoi") or
        item.get("question_text") or
        item.get("noi_dung") or
        ""
    ).strip()

    if "question_number" not in item:
        m_q_prefix = re.match(r'^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*(\d+)|\s*(\d+)[\.\:\)])', raw_q, re.IGNORECASE)
        if m_q_prefix:
            item["question_number"] = int(m_q_prefix.group(1) or m_q_prefix.group(2))

    q_clean = clean_question_prefix(raw_q)
    # Loại bỏ thẻ MARK khỏi nội dung câu hỏi để tránh tự động highlight màu nền
    q_cleaned = re.sub(r'</?MARK>', '', (q_clean or raw_q), flags=re.IGNORECASE)
    item["question"] = clean_subscripts_and_formulas(q_cleaned)

    # 3. Chuẩn hóa group_title & explain
    if "group_title" in item:
        gt = str(item.get("group_title", "")).strip()
        item["group_title"] = clean_subscripts_and_formulas(gt)
    item["explain"] = clean_subscripts_and_formulas(str(item.get("explain", ""))).strip()

    raw_type = str(item.get("type", "")).lower().strip()

    # Chuẩn hóa options: hỗ trợ trường hợp AI trả về dạng dict {"A": "...", "B": "..."}
    raw_options = item.get("options")
    if raw_options is None:
        raw_options = item.get("choices") or item.get("phuong_an") or []

    if isinstance(raw_options, dict):
        options = [
            f"{k}. {v}" if not re.match(rf'^\*?\s*[\(\[]?{k}[\.\:\)\-\]]', str(v).strip(), re.IGNORECASE) else str(v).strip()
            for k, v in sorted(raw_options.items())
        ]
    elif isinstance(raw_options, list):
        options = raw_options
    else:
        options = []

    # Chuẩn hóa correct_answer: hỗ trợ trường hợp AI trả về answer / dap_an
    raw_ca = item.get("correct_answer")
    if raw_ca is None:
        raw_ca = item.get("answer") or item.get("dap_an") or item.get("correctAnswer") or item.get("key")

    header_text = (str(item.get("group_title", "")) + " " + str(item.get("question", ""))).lower()

    # 2.1 Tự động cứu hộ: Nếu options đang rỗng hoặc <= 1
    if len(options) <= 1:
        # Ưu tiên kiểm tra phương án trắc nghiệm A, B, C, D (chữ in hoa)
        extracted_stem_mcq, extracted_opts_mcq = extract_mcq_options_from_text(item["question"])
        if len(extracted_opts_mcq) >= 2:
            item["question"] = extracted_stem_mcq
            options = extracted_opts_mcq
            item["options"] = options
        else:
            # Nếu không có A-D, mới kiểm tra ý con Đúng/Sai a), b), c), d) (chữ thường)
            extracted_stem_tf, extracted_opts_tf = extract_sub_statements_from_text(item["question"])
            if len(extracted_opts_tf) >= 2:
                item["question"] = extracted_stem_tf
                options = extracted_opts_tf
                item["options"] = options

    # 2.2 Kiểm tra đặc trưng Đúng / Sai
    has_tf_dict = isinstance(raw_ca, dict) and any(str(k).lower() in ['a', 'b', 'c', 'd'] for k in raw_ca.keys())
    has_tf_str = False
    if isinstance(raw_ca, str):
        # Yêu cầu ít nhất 2 ý được đánh giá (ví dụ a-Đ, b-S) hoặc 3 chữ Đ/S liên tục
        tf_pat = r'(?:[a-d][\.\:\)\/\-\s]*(?:Đ|S|Đúng|Sai|True|False)[^\w\n]*[,\;\-]?\s*[a-d][\.\:\)\/\-\s]*(?:Đ|S|Đúng|Sai)|(?:Đ|S|Đúng|Sai)\s*[\,\;\-]\s*(?:Đ|S|Đúng|Sai))'
        if re.search(tf_pat, raw_ca, re.IGNORECASE):
            has_tf_str = True
        elif len(re.findall(r'\b(Đ|S|ĐÚNG|SAI|TRUE|FALSE)\b', raw_ca, re.IGNORECASE)) >= 3:
            has_tf_str = True

    has_tf_keywords = any(kw in header_text for kw in [
        "đúng sai", "đúng - sai", "đúng/sai", "dung sai", "dung-sai", "dung/sai",
        "phần ii", "phan ii", "phần 2", "phan 2", "part ii", "part 2",
        "mỗi ý a", "đúng hoặc sai", "true/false", "true or false"
    ])
    has_explicit_tf_marks = any(any(m in str(opt) for m in ['[ĐÚNG]', '[DUNG]', '[SAI]', '(Đúng)', '(Dung)', '(Sai)']) for opt in options)

    # Đếm số lượng phương án theo quy chuẩn Bộ GD&ĐT:
    # - MCQ: Ký hiệu CHỮ IN HOA A, B, C, D (A. hoặc A))
    # - Đúng / Sai: Ký hiệu CHỮ THƯỜNG a, b, c, d (a) hoặc a.)
    mcq_opt_re = re.compile(
        r'^\s*(?:<MARK>\s*|<u>\s*|<b>\s*)*'
        r'(?:\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC|nb|th|vd|vdc)\s*\]\s*)?'
        r'(?:<MARK>\s*|<u>\s*|<b>\s*)*'
        r'\(?\[?(\*?[A-F])(?:\s*</u>)*(?:\s*</b>)*(?:\s*</MARK>)*[\.\:\)]'
    )
    tf_opt_re = re.compile(
        r'^\s*(?:<MARK>\s*|<u>\s*)*'
        r'(?:\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*)?'
        r'(?:<MARK>\s*|<u>\s*)*'
        r'\(?\[?(\*?[a-d])(?:\s*</u>)*(?:\s*</MARK>)*[\)\.\:\-\]\/]'
    )

    mcq_count = sum(1 for opt in options[:4] if mcq_opt_re.match(str(opt).strip()))
    tf_count = sum(1 for opt in options[:4] if tf_opt_re.match(str(opt).strip()))

    is_all_uppercase_mcq = (mcq_count >= 2 and mcq_count >= tf_count)
    is_tf_paren_options = (tf_count >= 2 and tf_count > mcq_count)

    is_single_choice_ca = bool(
        re.match(r'^\s*\(?[A-Da-d]\)?\.?\s*$', str(raw_ca).strip()) or
        re.match(r'^\s*(?:đáp án|câu|phương án|chọn)\s*[A-Da-d]\b', str(raw_ca).strip(), re.IGNORECASE)
    )

    # 3. Phân loại câu hỏi thông minh & triệt để:
    is_true_false = False
    is_short_answer = False
    is_essay = False

    if raw_type in ["essay", "tu_luan", "tự luận", "tuluan", "descriptive"]:
        if mcq_count == 0 and tf_count < 2:
            is_essay = True
        elif is_all_uppercase_mcq:
            is_true_false = False
            is_short_answer = False
            is_essay = False
    elif is_all_uppercase_mcq:
        # NẾU CÁC PHƯƠNG ÁN LÀ A, B, C, D (CHỮ IN HOA) -> BẮT BUỘC VÀ DUY NHẤT LÀ MCQ!
        is_true_false = False
        is_short_answer = False
        is_essay = False
    elif is_tf_paren_options:
        # Nếu đáp án là chọn 1 chữ cái đơn lẻ (MCQ) và không có dấu hiệu Đúng/Sai -> Vẫn là MCQ
        if is_single_choice_ca and not (has_tf_dict or has_tf_str or has_explicit_tf_marks or has_tf_keywords):
            is_true_false = False
        else:
            is_true_false = True
        is_short_answer = False
        is_essay = False
    elif (has_tf_dict or has_tf_str or has_explicit_tf_marks) and mcq_count == 0:
        is_true_false = True
    elif raw_type in ["true_false", "tf", "dung_sai", "dung-sai", "dung/sai", "dung sai"] and mcq_count == 0:
        is_true_false = True
    elif raw_type in ["short_answer", "sa", "tra_loi_ngan", "tra-loi-ngan", "short", "dien_khuyet"]:
        if tf_count >= 2:
            is_true_false = True
        else:
            is_short_answer = True
    elif len(options) == 0:
        grp_u = str(item.get("group_title") or "").upper()
        if "TỰ LUẬN" in grp_u or "TU LUAN" in grp_u or "PHẦN IV" in grp_u or "PHẦN 4" in grp_u:
            is_essay = True
        else:
            is_short_answer = True
    else:
        is_true_false = False
        is_short_answer = False
        is_essay = False



    # 4. XỬ LÝ DẠNG ĐÚNG / SAI

    if is_true_false:

        item["type"] = "true_false"

        sub_prefixes = ["a) ", "b) ", "c) ", "d) "]

        normalized_options = []

        opt_tf_marks = {}



        # Hỗ trợ nếu AI xuất dạng "statements": [{"id": "a", "content": "...", "is_correct": true}]

        statements = item.get("statements", [])

        if isinstance(statements, list) and len(statements) > 0 and len(options) == 0:

            options = [f"{s.get('id', 'a')}) {s.get('content', '')}" for s in statements if isinstance(s, dict)]

            if not item.get("correct_answer"):

                item["correct_answer"] = {s.get('id', 'a'): s.get('is_correct', True) for s in statements if isinstance(s, dict)}



        for idx, opt in enumerate(options[:4]):
            clean_text, is_corr, is_fls, ext_char = clean_option_text(opt)
            if not clean_text and ('<img' in str(opt).lower() or '[img_' in str(opt).lower()):
                clean_text = re.sub(r'^\s*[\(\[]?[a-d][\)\.\:\-\]\/]\s*', '', str(opt), flags=re.IGNORECASE).strip()
            clean_text = clean_subscripts_and_formulas(clean_text)

            char_key = ['a', 'b', 'c', 'd'][idx]

            pref = sub_prefixes[idx]

            normalized_options.append(f"{pref}{clean_text}")

            if is_corr:

                opt_tf_marks[char_key] = True

            elif is_fls:

                opt_tf_marks[char_key] = False



        item["options"] = normalized_options



        raw_ca = item.get("correct_answer")

        has_explicit_raw_ca = False
        if isinstance(raw_ca, dict) and any(str(k).lower().strip().replace(')', '').replace('.', '') in ['a', 'b', 'c', 'd'] for k in raw_ca.keys()):
            has_explicit_raw_ca = True
        elif isinstance(raw_ca, str) and len(raw_ca.strip()) > 0:
            if re.search(r'(?:[a-d][\.\:\)\/\-\s]*(?:Đ|S|Đúng|Sai)|(?:Đ|S|Đúng|Sai)\s*[\,\;\-]\s*(?:Đ|S|Đúng|Sai))', raw_ca, re.IGNORECASE) or len(re.findall(r'\b(Đ|S|ĐÚNG|SAI)\b', raw_ca, re.IGNORECASE)) >= 2:
                has_explicit_raw_ca = True

        if has_explicit_raw_ca:
            tf_dict = parse_tf_answer(raw_ca)
            for k, v in opt_tf_marks.items():
                tf_dict[k] = v
        elif opt_tf_marks:
            # Chuẩn HocNhanhTN Cách 3 (Gạch chân trực tiếp đáp án đúng):
            # Ký hiệu ĐƯỢC gạch chân / đánh dấu -> Đúng (True)
            # Ký hiệu KHÔNG ĐƯỢC gạch chân / đánh dấu -> Sai (False)
            has_any_true = any(v is True for v in opt_tf_marks.values())
            if has_any_true:
                tf_dict = {k: bool(opt_tf_marks.get(k, False)) for k in ['a', 'b', 'c', 'd']}
            else:
                tf_dict = {k: opt_tf_marks.get(k, True) for k in ['a', 'b', 'c', 'd']}
        else:
            tf_dict = parse_tf_answer(raw_ca)

        # Đánh dấu gợi ý AI nếu dùng AI và không có đáp án đánh dấu sẵn từ giáo viên
        if not use_ai or item.get("use_ai") is False:
            item["is_ai_suggested"] = False
            item["ai_suggestion_note"] = ""
        elif item.get("is_ai_suggested") is True or item.get("ai_suggested") is True:
            item["is_ai_suggested"] = True
            item["ai_suggestion_note"] = "AI đề xuất, cần giáo viên xác nhận"
        elif not opt_tf_marks and not has_explicit_raw_ca and not item.get("from_answer_key"):
            item["is_ai_suggested"] = True
            item["ai_suggestion_note"] = "AI đề xuất, cần giáo viên xác nhận"
        elif "is_ai_suggested" not in item:
            item["is_ai_suggested"] = False

        item["correct_answer"] = tf_dict

        return item



    # 5. XỬ LÝ DẠNG TRẢ LỜI NGẮN

    elif is_short_answer:

        item["type"] = "short_answer"

        item["options"] = []

        raw_ca = str(item.get("correct_answer", "")).strip()

        raw_ca = re.sub(r'^(?:Đáp án|Đáp số|ĐS|Kết quả|Ans|Answer|x\s*=)\s*[\:\-\=]?\s*', '', raw_ca, flags=re.IGNORECASE).strip()

        if re.match(r'^-?\d+,\d+$', raw_ca):

            raw_ca = raw_ca.replace(',', '.')

        # Đánh dấu gợi ý AI nếu dùng AI và không có đáp án sẵn
        if not use_ai or item.get("use_ai") is False:
            item["is_ai_suggested"] = False
            item["ai_suggestion_note"] = ""
        elif item.get("is_ai_suggested") is True or item.get("ai_suggested") is True:
            item["is_ai_suggested"] = True
            item["ai_suggestion_note"] = "AI đề xuất, cần giáo viên xác nhận"
        elif not raw_ca and not item.get("from_answer_key"):
            item["is_ai_suggested"] = True
            item["ai_suggestion_note"] = "AI đề xuất, cần giáo viên xác nhận"
        elif "is_ai_suggested" not in item:
            item["is_ai_suggested"] = False

        item["correct_answer"] = clean_subscripts_and_formulas(raw_ca)

        return item

    # 5b. XỬ LÝ DẠNG TỰ LUẬN (ESSAY)

    elif is_essay:

        item["type"] = "essay"

        item["options"] = []

        raw_ca = str(item.get("correct_answer", "")).strip()

        raw_ca = re.sub(r'^(?:Hướng dẫn chấm|Thang điểm|Biểu điểm|Đáp án và thang điểm|Gợi ý làm bài|Đáp án)\s*[\:\-\=]?\s*', '', raw_ca, flags=re.IGNORECASE).strip()

        item["correct_answer"] = clean_subscripts_and_formulas(raw_ca) if raw_ca else ""

        if "is_ai_suggested" not in item:

            item["is_ai_suggested"] = False

        return item



    # 6. XỬ LÝ DẠNG TRẮC NGHIỆM NHIỀU LỰA CHỌN (MCQ)

    else:

        item["type"] = "mcq"

        prefixes = ["A. ", "B. ", "C. ", "D. ", "E. ", "F. "]

        normalized_options = []

        option_detected_correct = None



        for idx, opt in enumerate(options[:6]):
            clean_text, is_corr, _, ext_char = clean_option_text(opt)
            if not clean_text and ('<img' in str(opt).lower() or '[img_' in str(opt).lower()):
                clean_text = re.sub(r'^\s*[\(\[]?[A-Fa-f\d][\)\.\:\-\]\/]\s*', '', str(opt), flags=re.IGNORECASE).strip()
            clean_text = clean_subscripts_and_formulas(clean_text)

            pref = prefixes[idx] if idx < len(prefixes) else ""

            full_opt = f"{pref}{clean_text}"

            normalized_options.append(full_opt)

            if is_corr and option_detected_correct is None:

                option_detected_correct = full_opt



        item["options"] = normalized_options

        raw_ca_obj = item.get("correct_answer")
        final_ca = None

        if isinstance(raw_ca_obj, dict):
            # Cứu hộ khi AI hoặc parser vô tình gán dict {a: True, b: False} cho câu MCQ
            true_keys = [str(k).upper().replace(')', '').replace('.', '') for k, v in raw_ca_obj.items() if v is True or str(v).lower() in ['true', '1', 'đ', 'đúng']]
            if true_keys:
                target_char = true_keys[0]
                for opt in normalized_options:
                    if opt.startswith(f"{target_char}."):
                        final_ca = opt
                        break

        raw_ca = str(raw_ca_obj or "").strip()

        if raw_ca and not final_ca:
            ca_content, _, _, _ = clean_option_text(raw_ca)
            ca_content_clean = clean_subscripts_and_formulas(ca_content).strip()

            # 1. Kiểm tra nếu raw_ca có dạng nhãn chữ cái rõ ràng (VD: "A", "A.", "*A", "Đáp án A", "Chọn B")
            m_explicit_letter = re.match(r'^\*?\s*([A-F])(?:[\.\:\)]|\s*$)', raw_ca, re.IGNORECASE)
            if not m_explicit_letter:
                m_explicit_letter = re.search(r'(?:đáp\s*án|phương\s*án|chọn|câu)\s*([A-F])\b', raw_ca, re.IGNORECASE)

            if m_explicit_letter:
                target_char = m_explicit_letter.group(1).upper()
                for opt in normalized_options:
                    if opt.startswith(f"{target_char}."):
                        final_ca = opt
                        break

            # 2. So khớp theo nội dung văn bản (tránh bắt nhầm chữ cái đơn như "A" trong "A cat", "Điểm A")
            if not final_ca and ca_content_clean:
                for opt in normalized_options:
                    opt_body, _, _, _ = clean_option_text(opt)
                    opt_clean = clean_subscripts_and_formulas(opt_body).strip()
                    if ca_content_clean.lower() == opt_clean.lower():
                        final_ca = opt
                        break

                if not final_ca and len(ca_content_clean) >= 3:
                    for opt in normalized_options:
                        opt_body, _, _, _ = clean_option_text(opt)
                        opt_clean = clean_subscripts_and_formulas(opt_body).strip()
                        if ca_content_clean.lower() in opt_clean.lower() or opt_clean.lower() in ca_content_clean.lower():
                            final_ca = opt
                            break

            # 3. Fallback chữ cái nếu chuỗi ngắn
            if not final_ca and len(raw_ca) <= 4:
                m_single = re.search(r'\b([A-F])\b', raw_ca, re.IGNORECASE)
                if m_single:
                    target_char = m_single.group(1).upper()
                    for opt in normalized_options:
                        if opt.startswith(f"{target_char}."):
                            final_ca = opt
                            break



        is_ai_defaulted = False
        if not final_ca:
            if option_detected_correct:
                final_ca = option_detected_correct
            else:
                is_ai_defaulted = True
                final_ca = normalized_options[0] if normalized_options else raw_ca

        # Đánh dấu gợi ý AI nếu dùng AI và không có dấu hiệu đáp án của giáo viên
        if not use_ai or item.get("use_ai") is False:
            item["is_ai_suggested"] = False
            item["ai_suggestion_note"] = ""
        elif item.get("is_ai_suggested") is True or item.get("ai_suggested") is True:
            item["is_ai_suggested"] = True
            item["ai_suggestion_note"] = "AI đề xuất, cần giáo viên xác nhận"
        elif option_detected_correct:
            item["is_ai_suggested"] = False
            item["ai_suggestion_note"] = ""
        elif (is_ai_defaulted or not option_detected_correct) and not raw_ca_obj and not item.get("from_answer_key"):
            item["is_ai_suggested"] = True
            item["ai_suggestion_note"] = "AI đề xuất, cần giáo viên xác nhận"
        elif "is_ai_suggested" not in item:
            item["is_ai_suggested"] = False

        item["correct_answer"] = final_ca
        return item


def chunk_marked_text(marked_text: str, questions_per_chunk: int = 15) -> List[str]:

    """Chia nhỏ văn bản dựa trên các mốc câu hỏi để chống quá tải RAM và giới hạn token AI."""

    q_regex = r'(?:^|\n)\s*(?:Câu|Bài|Question|Q)\s*\d+\s*[\.\:\-\)]|(?:^|\n)\s*\d+\s*[\.\:\)]'

    matches = list(re.finditer(q_regex, marked_text, re.IGNORECASE))

    

    if not matches:

        chunks = []

        lines = marked_text.split('\n')

        current_chunk = ""

        for line in lines:

            current_chunk += line + "\n"

            if len(current_chunk) > 8000:

                chunks.append(current_chunk)

                current_chunk = ""

        if current_chunk:

            chunks.append(current_chunk)

        return chunks if chunks else [marked_text]



    chunks = []

    current_chunk_start = 0

    for i in range(0, len(matches), questions_per_chunk):

        end_idx = i + questions_per_chunk

        chunk_end_pos = matches[end_idx].start() if end_idx < len(matches) else len(marked_text)

        chunks.append(marked_text[current_chunk_start:chunk_end_pos])

        current_chunk_start = chunk_end_pos

    return chunks



async def call_gemini_with_fallback(
    prompt: Any,
    api_keys: List[str],
    system_instruction: Optional[str] = None,
    thinking_budget: Optional[int] = 0,
    timeout: float = 30.0,
):
    """
    Gọi Gemini AI với cơ chế tối ưu hiệu năng và giám sát Quota:
    - Sử dụng Client Pool tái sử dụng kết nối
    - Tối ưu hóa chuỗi model: gemini-2.5-flash (siêu tốc ~1.4s) -> gemini-2.5-flash-lite -> gemini-3.8-flash -> gemini-flash-latest -> gemini-1.5-flash
    - Hỗ trợ đa phương thức Multimodal (chữ + hình ảnh/PDF scan)
    - Tự động ghi nhận số lượt gọi, lỗi 429 quota, tính chi phí qua gemini_tracker
    - Tự động luân chuyển Key khi gặp 429 Quota Exceeded
    """
    if not api_keys:
        diag = diagnose_gemini_error(Exception("Chưa cấu hình API Key"), keys_tried=[])
        raise GeminiAPIException(diag)

    request_timeout = max(5.0, float(timeout)) if timeout is not None else 30.0

    # Đo độ dài prompt để ước tính token
    prompt_chars = 0
    if isinstance(prompt, str):
        prompt_chars = len(prompt)
    elif isinstance(prompt, list):
        for part in prompt:
            if isinstance(part, str):
                prompt_chars += len(part)
            else:
                prompt_chars += 1200 # Ước lượng ~300 tokens cho 1 ảnh
    else:
        prompt_chars = 1000

    t_start = time.time()

    # Danh sách model tối ưu: ưu tiên gemini-2.5-flash ổn định và phản hồi nhanh nhất,
    # dự phòng qua các nhóm model khác nhau nếu Google gặp quá tải 503 cục bộ
    models_to_try = [
        'gemini-2.5-flash',
        'gemini-2.5-flash-lite',
        'gemini-flash-latest',
        'gemini-2.0-flash',
        'gemini-2.0-flash-lite',
        'gemini-3.8-flash',
    ]

    last_error = None
    saw_transient_503 = False

    async def _attempt_once(candidate_models: List[str]):
        nonlocal last_error, saw_transient_503
        for key in api_keys:
            key = key.strip()
            if not key:
                continue

            try:
                client = get_gemini_client(key)
            except Exception as e:
                last_error = e
                gemini_tracker.record_call(
                    api_key=key,
                    model="unknown",
                    success=False,
                    error_message=f"Client pool error: {str(e)}",
                    prompt_chars=prompt_chars,
                    duration_ms=(time.time() - t_start) * 1000
                )
                continue

            from google.genai import types

            for model_name in candidate_models:
                config_params = {
                    "temperature": 0.1,
                    "response_mime_type": "application/json"
                }

                if system_instruction:
                    config_params["system_instruction"] = system_instruction

                if thinking_budget is not None and hasattr(types, "ThinkingConfig"):
                    config_params["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)

                try:
                    response = await asyncio.wait_for(
                        client.aio.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=types.GenerateContentConfig(**config_params)
                        ),
                        timeout=request_timeout
                    )

                    resp_len = len(response.text) if hasattr(response, "text") and response.text else 500
                    gemini_tracker.record_call(
                        api_key=key,
                        model=model_name,
                        success=True,
                        prompt_chars=prompt_chars,
                        response_chars=resp_len,
                        duration_ms=(time.time() - t_start) * 1000
                    )
                    return response

                except Exception as e:
                    error_str = str(e).lower()

                    if "thinking" in error_str or "invalid argument" in error_str:
                        try:
                            fallback_params = {k: v for k, v in config_params.items() if k != "thinking_config"}
                            response = await asyncio.wait_for(
                                client.aio.models.generate_content(
                                    model=model_name,
                                    contents=prompt,
                                    config=types.GenerateContentConfig(**fallback_params)
                                ),
                                timeout=request_timeout
                            )

                            resp_len = len(response.text) if hasattr(response, "text") and response.text else 500
                            gemini_tracker.record_call(
                                api_key=key,
                                model=model_name,
                                success=True,
                                prompt_chars=prompt_chars,
                                response_chars=resp_len,
                                duration_ms=(time.time() - t_start) * 1000
                            )
                            return response

                        except Exception as inner_e:
                            error_str = str(inner_e).lower()
                            last_error = inner_e
                    else:
                        last_error = e

                    gemini_tracker.record_call(
                        api_key=key,
                        model=model_name,
                        success=False,
                        error_message=str(last_error),
                        prompt_chars=prompt_chars,
                        duration_ms=(time.time() - t_start) * 1000
                    )

                    if "api key not valid" in error_str or "invalid api key" in error_str:
                        break  # Key lỗi, chuyển key kế tiếp
                    elif "404" in error_str or "not found" in error_str or "unsupported" in error_str or "no longer available" in error_str:
                        continue
                    elif "503" in error_str or "unavailable" in error_str or "high demand" in error_str or "overloaded" in error_str:
                        saw_transient_503 = True
                        continue
                    elif "429" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
                        break  # Hết quota lượt gọi của key này, chuyển sang API Key tiếp theo
                    elif "deadline" in error_str or "timeout" in error_str:
                        continue
                    else:
                        continue
        return None

    res = await _attempt_once(models_to_try)
    if res is not None:
        return res

    # Nếu gặp quá tải 503 tạm thời từ Google, chờ 1.8s rồi thử lại nhanh với các model chính
    if saw_transient_503:
        await asyncio.sleep(1.8)
        res_retry = await _attempt_once(['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash'])
        if res_retry is not None:
            return res_retry

    diag = diagnose_gemini_error(last_error, keys_tried=api_keys, models_tried=models_to_try)
    raise GeminiAPIException(diag)



def restore_image_placeholders(text: str) -> str:

    """

    Khôi phục lại các placeholder [IMG_X] mà AI có thể đã viết lại thành dạng khác.

    Ví dụ: AI hay viết [Hình 1], [Image 1], [Ảnh 1], [IMG1], (IMG_1) → phục hồi về [IMG_1].

    """

    # Chuẩn hóa các biến thể phổ biến mà AI hay viết sai

    # Mẫu: [Hình X], [Ảnh X], [Image X], [Pic X], [Hinh X], [IMG X], [IMG-X], [IMGX], (IMG_X), v.v.

    patterns = [

        # [IMG X], [IMG-X], [IMG_X], [IMGX] -> [IMG_X]

        (r'\[\s*IMG[\s_\-]*(\d+)\s*\]', r'[IMG_\1]'),

        # [Image X], [image X] -> [IMG_X]

        (r'\[\s*[Ii]mage[\s_\-]*(\d+)\s*\]', r'[IMG_\1]'),

        # [Hình X], [Hinh X] -> [IMG_X]

        (r'\[\s*[Hh][iíì]nh[\s_\-]*(\d+)\s*\]', r'[IMG_\1]'),

        # [Ảnh X], [Anh X] -> [IMG_X]

        (r'\[\s*[Ảảaa][Nn][Hh][\s_\-]*(\d+)\s*\]', r'[IMG_\1]'),

        # [Pic X], [Picture X] -> [IMG_X]

        (r'\[\s*(?:[Pp]ic|[Pp]icture)[\s_\-]*(\d+)\s*\]', r'[IMG_\1]'),

        # (IMG_X), (IMG X) -> [IMG_X]

        (r'\(\s*IMG[\s_\-]*(\d+)\s*\)', r'[IMG_\1]'),

        # IMG_X (không có ngoặc, đứng độc lập) -> [IMG_X]

        (r'(?<![\[\(\w])IMG[_\-\s]+(\d+)(?![\]\)\w])', r'[IMG_\1]'),

    ]

    for pattern, replacement in patterns:

        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text





def reinject_missing_image_placeholders(chunk_text: str, questions: list) -> list:
    """
    Tự động đối soát và khôi phục các placeholder ảnh [IMG_X] bị AI bỏ sót.
    Quét từng phân đoạn câu hỏi trong văn bản gốc; nếu câu hỏi gốc có [IMG_X]
    nhưng AI trích xuất bị thiếu thì tự động chèn lại vào nội dung câu hỏi.
    """
    if not chunk_text or not questions or not isinstance(questions, list):
        return questions

    img_matches = list(re.finditer(r'\[IMG_\d+\]', chunk_text))
    if not img_matches:
        return questions

    q_matches = list(re.finditer(
        r'(?:^|\n)\s*(?:<[^>]+>\s*)*(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*(\d+)|\s*(\d+)[\.\:\)])',
        chunk_text,
        re.IGNORECASE
    ))
    if not q_matches:
        return questions

    q_spans = []
    for i, m in enumerate(q_matches):
        q_num = int(m.group(1) or m.group(2))
        start_pos = m.start()
        end_pos = q_matches[i+1].start() if i + 1 < len(q_matches) else len(chunk_text)
        q_spans.append((q_num, start_pos, end_pos))

    q_expected_imgs = {}
    for q_num, start, end in q_spans:
        imgs = [m.group(0) for m in img_matches if start <= m.start() < end]
        if imgs:
            q_expected_imgs[q_num] = imgs

    for q in questions:
        if not isinstance(q, dict):
            continue
        q_num = q.get('question_number')
        if q_num not in q_expected_imgs:
            continue

        expected = q_expected_imgs[q_num]
        q_text = str(q.get('question', ''))
        opts_text = ' '.join(str(o) for o in q.get('options', []))
        total_text = q_text + ' ' + opts_text

        for img_tag in expected:
            num = re.search(r'\d+', img_tag).group(0)
            if not re.search(rf'\[\s*(?:IMG|HÌNH|ẢNH|Image)?[\s_#-]*{num}\s*\]', total_text, re.IGNORECASE):
                q['question'] = q_text.rstrip() + f'\n\n{img_tag}\n'
                logger.info(f'AI Service: Tự động khôi phục placeholder ảnh {img_tag} vào Câu {q_num} do AI bỏ sót.')

    return questions


async def generate_mcq_with_gemini(

    marked_text: str,

    api_keys: List[str],

    task_id: str = None,

    active_tasks: dict = None,

    answer_key: Any = None

) -> List[Dict[str, Any]]:

    """

    Dùng Gemini AI để bóc tách câu hỏi dựa trên văn bản đã gắn thẻ <MARK>.

    Tự động nhận diện và bảo toàn tuyệt đối 100% BẢNG ĐÁP ÁN ở cuối tài liệu (không để AI tự sửa đáp án hoặc tự thêm bớt câu hỏi).

    """

    if active_tasks is None:

        try:

            from core.state import active_tasks as global_active_tasks

            active_tasks = global_active_tasks

        except ImportError:

            pass



    from core.answer_key_extractor import reconcile_quiz_with_answer_key, separate_answer_key_from_text



    # Tách và phát hiện BẢNG ĐÁP ÁN ở cuối tài liệu

    if answer_key is None or not (getattr(answer_key, 'part1', None) or getattr(answer_key, 'part2', None) or getattr(answer_key, 'part3', None) or answer_key):

        text_without_ak, ak_raw, detected_ak = separate_answer_key_from_text(marked_text)

        marked_text = text_without_ak

        if detected_ak and (detected_ak.part1 or detected_ak.part2 or detected_ak.part3 or detected_ak):

            answer_key = detected_ak

    else:

        # Nếu đã có answer_key truyền vào từ file docx, cắt bỏ phần BẢNG ĐÁP ÁN khỏi text để tránh AI hiểu nhầm thành câu hỏi

        text_without_ak, _, _ = separate_answer_key_from_text(marked_text)

        marked_text = text_without_ak



    ak_prompt_section = ""

    if answer_key and hasattr(answer_key, 'to_summary_text'):

        ak_summary = answer_key.to_summary_text()

        if ak_summary:

            ak_prompt_section = f"""

            ========================================================================

            BẢNG ĐÁP ÁN CHÍNH THỨC CỦA ĐỀ THI (BẮT BUỘC TUÂN THỦ 100%):

            {ak_summary}

            ========================================================================

            QUY TẮC BẢO TOÀN ĐÁP ÁN & NỘI DUNG GỐC:

            1. TUYỆT ĐỐI TUÂN THỦ BẢNG ĐÁP ÁN TRÊN: Đối với mỗi câu hỏi, PHẢI gán đúng đáp án từ Bảng Đáp Án chính thức trên (hoặc từ ký hiệu Đ/S, dấu *, thẻ <MARK>). TUYỆT ĐỐI KHÔNG TỰ GIẢI ĐỂ THAY ĐỔI ĐÁP ÁN CỦA ĐỀ GỐC!

            2. NGUYÊN VĂN NỘI DUNG 100%: Sao chép trung thực nguyên văn nội dung câu hỏi và các phương án từ văn bản gốc. KHÔNG TỰ Ý THÊM BỚT từ ngữ, KHÔNG SÁNG TÁC THÊM PHƯƠNG ÁN HAY BỎ BỚT PHƯƠNG ÁN!

            3. ĐỐI VỚI CÂU HỎI ĐÚNG / SAI (true_false): Mọi câu hỏi có các ý a), b), c), d) BẮT BUỘC gán type: 'true_false', giữ nguyên đủ 4 ý a), b), c), d) trong options: ['a) ...', 'b) ...', 'c) ...', 'd) ...'], đáp án đúng format {{"a": bool, "b": bool, "c": bool, "d": bool}} theo đúng Bảng Đáp Án. TUYỆT ĐỐI KHÔNG GÁN 'short_answer' và TUYỆT ĐỐI KHÔNG để options là []!

            4. ĐỐI VỚI CÂU HỎI TRẢ LỜI NGẮN (short_answer): CHỈ DÀNH CHO câu tính toán ra 1 đáp số duy nhất (số hoặc từ ngắn). options BẮT BUỘC là [], correct_answer lấy chuẩn từ Bảng Đáp Án. TUYỆT ĐỐI KHÔNG dùng cho câu có các ý a), b), c), d).

            5. TUYỆT ĐỐI KHÔNG TẠO CÂU HỎI MỚI ngoài các câu có trong văn bản đề thi.

            """

    if not ak_prompt_section:
        ak_prompt_section = """
            ========================================================================
            TÀI LIỆU KHÔNG CÓ BẢNG ĐÁP ÁN TỔNG HỢP:
            1. AI HÃY TỰ GIẢI ĐỀ ĐỘC LẬP ĐỂ GỢI Ý ĐÁP ÁN ĐÚNG CHUẨN XÁC NHẤT KÈM LỜI GIẢI CHI TIẾT ('explain').
            2. VỚI MỖI CÂU HỎI MÀ BẠN TỰ GIẢI ĐỀ XUẤT ĐÁP ÁN (khi không có dấu hiệu đánh dấu của giáo viên), BẮT BUỘC GÁN:
               "is_ai_suggested": true,
               "ai_suggestion_note": "AI đề xuất, cần giáo viên xác nhận"
            ========================================================================
        """



    # Khử trùng lặp và làm sạch danh sách API Keys
    valid_keys = []
    seen_keys = set()
    for k in (api_keys or []):
        if k and isinstance(k, str) and k.strip() and k.strip() not in seen_keys:
            seen_keys.add(k.strip())
            valid_keys.append(k.strip())

    if not valid_keys:
        diag = diagnose_gemini_error(Exception("Chưa cấu hình API Key"), keys_tried=[])
        raise GeminiAPIException(diag)

    num_keys = len(valid_keys)

    # Đếm số câu hỏi sơ bộ trong văn bản để chia đều khối lượng công việc cho các API Key
    q_regex = r'(?:^|\n)\s*(?:Câu|Bài|Question|Q)\s*\d+\s*[\.\:\-\)]|(?:^|\n)\s*\d+\s*[\.\:\)]'
    detected_count = len(re.findall(q_regex, marked_text, re.IGNORECASE))

    # Tối ưu kích thước từng phần (chunk) theo số lượng Worker (API Keys):
    # Nếu có nhiều key và đề thi dài (> 15 câu), chia đều số câu cho các key (mỗi chunk 8 - 15 câu)
    if num_keys > 1 and detected_count > 15:
        target_per_key = math.ceil(detected_count / num_keys)
        questions_per_chunk = max(8, min(15, target_per_key))
    else:
        questions_per_chunk = 15

    chunks = chunk_marked_text(marked_text, questions_per_chunk=questions_per_chunk)
    all_extracted_data = []

    # Đếm tổng số placeholder ảnh trong toàn bộ tài liệu để nhắc AI
    total_imgs = len(re.findall(r'\[IMG_\d+\]', marked_text))
    img_reminder = (
        f" Tài liệu chứa {total_imgs} ảnh được đánh dấu bằng [IMG_X] (X là số). "
        "TUYỆT ĐỐI PHẢI GIỮ NGUYÊN 100% các placeholder [IMG_X] đúng như trong văn bản gốc. "
        "KHÔNG được viết lại thành [Hình X], [Image X], [Ảnh X] hay bất kỳ dạng nào khác."
    ) if total_imgs > 0 else ""

    system_instruction = (
        "Bạn là một chuyên gia giáo dục và biên tập viên đề thi trắc nghiệm chuẩn sư phạm. "
        "Nhiệm vụ của bạn là bóc tách chuẩn xác toàn bộ câu hỏi và đáp án từ tài liệu được cung cấp. "
        "Quy tắc bất di bất dịch:\n"
        "1. Giữ nguyên các thẻ định dạng HTML (<b>, <i>, <u>, <sub>, <sup>) và placeholder ảnh [IMG_X]. "
        "BẢO TOÀN BẢNG DỮ LIỆU HTML VÀ BẢNG BIẾN THIÊN: Nếu câu hỏi có bảng dữ liệu hoặc bảng biến thiên, "
        "BẮT BUỘC giữ nguyên vẹn 100% cấu trúc thẻ <table> thực chất trong trường 'question' (hoặc dựng thẻ <table class=\"quiz-table\" border=\"1\">...</table> như tạo bảng trong Word), tuyệt đối không xóa bảng hay làm xáo trộn các cột. "
        "BẮT BUỘC giữ nguyên vẹn 100% cấu trúc thẻ <table> trong trường 'question'. Nếu câu hỏi có bảng biến thiên/bảng số liệu, "
        "2. CÔNG THỨC HÓA HỌC / CHỈ SỐ DƯỚI (SUBSCRIPT): Tuyệt đối KHÔNG viết chỉ số dưới thành dấu gạch dưới trần như CH_2, CO_2, H_2O, Fe_2O_3, C_2H_5OH, x_1. "
        "BẮT BUỘC giữ nguyên thẻ HTML <sub> và <sup> (ví dụ: CH<sub>2</sub>, H<sub>2</sub>O, CO<sub>2</sub>, C<sub>2</sub>H<sub>5</sub>OH, cm<sup>2</sup>) "
        "hoặc đặt trọn vẹn trong công thức LaTeX \\( ... \\) như \\(\\text{CH}_2\\). "
        "3. CÔNG THỨC TOÁN LATEX: Mọi biểu thức toán học phải bọc trong \\( và \\). Nếu có chữ tiếng Việt trong công thức, phải dùng \\text{...}. "
        "4. BẢO TOÀN VÀ XÁC ĐỊNH ĐÁP ÁN ĐÚNG: Tuyệt đối tuân thủ Bảng Đáp Án đi kèm nếu có. "
        "Nếu trong đề không có bảng đáp án tổng hợp, ĐÁP ÁN ĐÚNG được xác định dựa trên bất kỳ dấu hiệu đánh dấu nào của giáo viên: "
        "- Thẻ <u> (chữ cái hoặc nội dung phương án được gạch chân), "
        "- Thẻ <MARK> (chữ được tô đỏ, đổi màu nổi bật, highlight dạ quang, hoặc tô màu nền shading trong Word), "
        "- Dấu hoa thị * (*A., A.*, *a)), "
        "- Dấu tick (✓, ✔, ☑), "
        "- Nhãn [ĐÚNG], (Đúng). "
        "Tuyệt đối KHÔNG tự ý giải lại đề để thay đổi đáp án của tác giả. "
        "5. QUY TẮC BẮT BUỘC PHÂN BIỆT 3 DẠNG CÂU HỎI (CHUẨN GDPT 2018):\n"
        "   - CÂU TRẮC NGHIỆM NHIỀU LỰA CHỌN (type: 'mcq'): BẮT BUỘC có các lựa chọn bắt đầu bằng CHỮ IN HOA 'A.', 'B.', 'C.', 'D.' (hoặc 'A)', 'B)', 'C)', 'D)'). Thí sinh chọn 1 trong 4 lựa chọn. BẮT BUỘC gán type: 'mcq', 'options': ['A. ...', 'B. ...', 'C. ...', 'D. ...'], 'correct_answer': 'X. ...' (chuỗi, ví dụ 'A. Lựa chọn 1'). TUYỆT ĐỐI KHÔNG GÁN type: 'true_false' và KHÔNG ĐƯỢC gán correct_answer dạng object/dict!\n"
        "   - CÂU TRẮC NGHIỆM ĐÚNG / SAI (type: 'true_false'): BẮT BUỘC có 4 ý/mệnh đề bắt đầu bằng CHỮ THƯỜNG 'a)', 'b)', 'c)', 'd)' (hoặc 'a.', 'b.', 'c.', 'd.'). Mỗi ý được đánh giá Đúng hoặc Sai độc lập. BẮT BUỘC gán type: 'true_false', 'options': ['a) ...', 'b) ...', 'c) ...', 'd) ...'], 'correct_answer': {'a': bool, 'b': bool, 'c': bool, 'd': bool}. Khi phương án hoặc nội dung được gạch chân (thẻ <u>), tô đỏ/highlight (thẻ <MARK>), hoặc có dấu *, ý đó là Đúng (true), các ý KHÔNG có dấu hiệu là Sai (false). Hỗ trợ đầy đủ tiền tố ma trận [0, NB], [1, TH], [2, VD], [3, VDC] trong các ý. TUYỆT ĐỐI KHÔNG GÁN type: 'mcq' và KHÔNG GÁN type: 'short_answer'!\n"
        "   - CÂU TRẢ LỜI NGẮN (short_answer): CHỈ DÀNH RIÊNG cho câu tự luận/tính toán điền một đáp số duy nhất (số nguyên, số thập phân, phân số, tọa độ hoặc từ ngắn), options: []. TUYỆT ĐỐI KHÔNG DÙNG CHO CÂU CÓ CÁC PHƯƠNG ÁN A, B, C, D HOẶC CÁC Ý a, b, c, d.\n"
        f"Trả về kết quả dưới dạng JSON array duy nhất.{img_reminder}"
    )

    last_chunk_error = None

    async def process_chunk(idx: int, chunk: str, chunk_keys: List[str]):
        nonlocal last_chunk_error

        if not chunk.strip():
            return None

        # Đếm placeholder ảnh trong chunk này
        chunk_imgs = re.findall(r'\[IMG_\d+\]', chunk)
        img_list_str = ", ".join(chunk_imgs) if chunk_imgs else ""
        img_strict_rule = (
            f"\n            QUAN TRỌNG: Chunk này chứa {len(chunk_imgs)} ảnh: {img_list_str}. "
            "Bạn PHẢI sao chép nguyên xi các placeholder ảnh này (đúng chính xác từng ký tự kể cả dấu ngoặc vuông và dấu gạch dưới) "
            "vào trường 'question' hoặc 'options' tương ứng. KHÔNG ĐƯỢC bỏ qua, viết lại hay sáng tác thêm placeholder ảnh mới."
        ) if chunk_imgs else ""

        prompt = f"""
            Bạn là trợ lý AI chuyên gia phân tích và bóc tách đề thi theo CHUẨN CẤU TRÚC MỚI CỦA BỘ GIÁO DỤC VÀ ĐÀO TẠO (Chương trình GDPT 2018).
            Nhiệm vụ: Trích xuất CHÍNH XÁC toàn bộ các câu hỏi từ phần văn bản {idx + 1}/{len(chunks)} sau thành danh sách JSON chuẩn.
            {ak_prompt_section}
            ĐỀ THI GỒM 3 DẠNG CÂU HỎI THEO QUY CHUẨN BỘ GD&ĐT:
            
            1. PHẦN I: TRẮC NGHIỆM NHIỀU LỰA CHỌN (type: "mcq")
               - 4 lựa chọn A, B, C, D (bắt buộc tiền tố 'A. ', 'B. ', 'C. ', 'D. ').
               - NGUYÊN TẮC SỐNG CÒN: Khi các lựa chọn là CHỮ IN HOA A, B, C, D (hoặc A), B), C), D)) -> 100% BẮT BUỘC gán type: "mcq". TUYỆT ĐỐI CẤM KHÔNG ĐƯỢC CHUYỂN SANG type: "true_false", KHÔNG ĐƯỢC BIẾN THÀNH a), b), c), d), VÀ KHÔNG ĐƯỢC GÁN correct_answer dạng dictionary!
               - QUY TẮC XÁC ĐỊNH ĐÁP ÁN ĐÚNG CHUẨN XÁC:
                 + Cách 1: Căn cứ Bảng đáp án chính thức / tổng hợp được cung cấp ở trên.
                 + Cách 2: PHƯƠNG ÁN ĐƯỢC ĐÁNH DẤU TRỰC TIẾP LÀ ĐÁP ÁN ĐÚNG:
                   * Có thẻ gạch chân <u> (ở ký hiệu A-D hoặc ở toàn bộ nội dung phương án).
                   * Có thẻ <MARK> (tương ứng với chữ tô đỏ, đổi màu nổi bật, highlight bút dạ quang, hoặc tô màu nền shading trong Word).
                   * Có dấu hoa thị * (*A., A.*) hoặc dấu tick (✓, ✔, ☑).
                   * Có nhãn [ĐÚNG], (Đúng).
                   -> BẮT BUỘC gán phương án đó vào 'correct_answer' (ví dụ: 'A. Lựa chọn 1').
               - Trong mảng 'options' và 'correct_answer', làm sạch các thẻ <MARK>, <u> và dấu * để nội dung câu hỏi sạch đẹp chuẩn sư phạm.
               - explain: Lời giải chi tiết lý do chọn đáp án này.
               - Mẫu JSON:
                 {{
                   "question_number": 1,
                   "type": "mcq",
                   "group_title": "",
                   "question": "Nội dung câu hỏi...",
                   "options": ["A. Lựa chọn 1", "B. Lựa chọn 2", "C. Lựa chọn 3", "D. Lựa chọn 4"],
                   "correct_answer": "A. Lựa chọn 1",
                   "explain": "Lời giải chi tiết..."
                 }}

            2. PHẦN II: TRẮC NGHIỆM ĐÚNG / SAI (type: "true_false")
               - Mỗi câu gồm 4 ý/mệnh đề độc lập: a), b), c), d) (tiền tố 'a) ', 'b) ', 'c) ', 'd) ' - BẮT BUỘC LÀ CHỮ THƯỜNG).
               - ĐẶC TRƯNG BẮT BUỘC: CHỈ GÁN type: "true_false" cho câu hỏi có các ý/mệnh đề là CHỮ THƯỜNG a), b), c), d). TUYỆT ĐỐI KHÔNG GÁN type: "true_false" cho câu có phương án chữ in hoa A, B, C, D!
               - HỖ TRỢ MA TRẬN MỨC ĐỘ NHẬN THỨC THEO CHUẨN HocNhanhTN:
                 Nếu có tiền tố ma trận như [0, NB], [1, TH], [2, VD], [3, VDC] (hoặc [NB], [TH], [VD], [VDC]) đặt trước hoặc sau ký hiệu a), b), c), d), HÃY BẢO TOÀN NGUYÊN VẸN tiền tố đó trong nội dung mệnh đề (ví dụ: 'a) [0, NB] Mệnh đề a' hoặc 'a) Mệnh đề a'), KHÔNG LÀM MẤT tiền tố và KHÔNG LẶP ký hiệu 'a) a)'.
               - QUY TẮC XÁC ĐỊNH ĐÁP ÁN ĐÚNG/SAI CHUẨN HocNhanhTN:
                 + Cách 1: Căn cứ Bảng đáp án tổng hợp (sau chữ HẾT) hoặc Bảng đáp án chính thức được cung cấp ở trên.
                 + Cách 2: Bảng đáp án riêng đặt ngay dưới từng câu hỏi (cột Đúng / Sai có dấu x, v, 1, ✓; hoặc hàng a, b, c, d với Đ, S).
                 + Cách 3: Gạch chân (thẻ <u>) hoặc highlight/tô màu đỏ/nền (thẻ <MARK>) hoặc dấu * hoặc dấu tick (✓, ✔, ☑) trực tiếp ở ký hiệu HOẶC ở nội dung mệnh đề:
                   * Mệnh đề CÓ bất kỳ dấu hiệu đánh dấu nào trên -> ĐÚNG (true)
                   * Mệnh đề KHÔNG CÓ dấu hiệu đánh dấu -> SAI (false)
               - Trong 'options', làm sạch các thẻ <MARK>, <u> và dấu * để hiển thị chuẩn đẹp.
               - correct_answer: Đối tượng quy định Đúng (true) hoặc Sai (false) cho từng ý:
                 {{"a": true, "b": false, "c": true, "d": false}}
               - explain: Lời giải chi tiết giải thích rõ lý do vì sao từng ý a, b, c, d là Đúng hoặc Sai.
               - Mẫu JSON:
                 {{
                   "question_number": 1,
                   "type": "true_false",
                   "group_title": "PHẦN II. Câu trắc nghiệm đúng sai...",
                   "question": "Nội dung câu hỏi hoặc thông tin dữ liệu...",
                   "options": [
                     "a) Mệnh đề a",
                     "b) Mệnh đề b",
                     "c) Mệnh đề c",
                     "d) Mệnh đề d"
                   ],
                   "correct_answer": {{"a": true, "b": false, "c": true, "d": false}},
                   "explain": "Giải thích vì sao a đúng, b sai, c đúng, d sai..."
                 }}

            3. PHẦN III: TRẮC NGHIỆM TRẢ LỜI NGẮN (type: "short_answer")
               - Câu hỏi tự luận điền kết quả / đáp số ngắn (số nguyên, số thập phân, phân số, tọa độ hoặc từ ngắn).
               - options: BẮT BUỘC là mảng rỗng [].
               - correct_answer: Chuỗi chứa đáp số ngắn chuẩn xác (ví dụ: "12", "-3.5", "1/2", "0.25").
               - explain: Lời giải chi tiết cách tính ra đáp số đó.
               - LƯU Ý ĐẶC BIỆT: TUYỆT ĐỐI KHÔNG GÁN type: "short_answer" cho các câu có các ý a), b), c), d). Mọi câu có ý a, b, c, d PHẢI LÀ type: "true_false"!
               - Mẫu JSON:
                 {{
                   "question_number": 1,
                   "type": "short_answer",
                   "group_title": "PHẦN III. Câu trắc nghiệm trả lời ngắn...",
                   "question": "Nội dung câu hỏi tính toán...",
                   "options": [],
                   "correct_answer": "12.5",
                   "explain": "Lời giải từng bước tính..."
                 }}

            QUY TẮC BẮT BUỘC VỀ ĐỊNH DẠNG:
            0. NGUYÊN TẮC CỐT LÕI ĐỂ PHÂN BIỆT TRẮC NGHIỆM (mcq) VÀ ĐÚNG SAI (true_false):
               - Lựa chọn là CHỮ IN HOA A, B, C, D -> 100% BẮT BUỘC type: "mcq", options: ["A. ...", "B. ...", "C. ...", "D. ..."], correct_answer: "X. ...". TUYỆT ĐỐI KHÔNG chuyển thành true_false, KHÔNG đổi sang a, b, c, d!
               - Ý/mệnh đề là CHỮ THƯỜNG a), b), c), d) -> 100% BẮT BUỘC type: "true_false", options: ["a) ...", "b) ...", "c) ...", "d) ..."], correct_answer: {{"a": bool, "b": bool, "c": bool, "d": bool}}.
            1. TUYỆT ĐỐI KHÔNG ĐỂ TIỀN TỐ "Câu 1:", "Câu 2:", "1." vào trường "question". Chỉ lấy nội dung câu hỏi thuần túy (ví dụ: "Cho hàm số y = f(x)..." thay vì "Câu 1: Cho hàm số y = f(x)...").
            2. group_title: Chỉ điền khi là tiêu đề mở đầu cho một phần/bài đọc (ví dụ: "PHẦN II. Trắc nghiệm Đúng/Sai"). TUYỆT ĐỐI KHÔNG sao chép lặp lại group_title ở từng câu hỏi đơn lẻ.
            3. DẠNG TRẮC NGHIỆM (mcq): Các phương án trong "options" PHẢI có dạng 'A. [Nội dung]', 'B. [Nội dung]', 'C. [Nội dung]', 'D. [Nội dung]'. "correct_answer" BẮT BUỘC PHẢI KHỚP NGUYÊN VĂN với một trong 4 phương án đó (ví dụ: "A. [Nội dung]"). TUYỆT ĐỐI KHÔNG thêm dấu hoa thị '*' hay thẻ [ĐÚNG] vào options.
            4. DẠNG ĐÚNG/SAI (true_false): Bất kỳ câu nào có 4 mệnh đề a), b), c), d) BẮT BUỘC PHẢI gán type là 'true_false'. Các ý trong "options" PHẢI có dạng 'a) [Nội dung]', 'b) [Nội dung]', 'c) [Nội dung]', 'd) [Nội dung]'. TUYỆT ĐỐI KHÔNG gán type là 'short_answer' và KHÔNG để options rỗng! TUYỆT ĐỐI KHÔNG ghi kết quả [ĐÚNG], [SAI], (Đúng), (Sai) vào nội dung phương án. Kết quả Đúng/Sai phải được thể hiện trong object "correct_answer": {{"a": true, "b": false, "c": true, "d": false}}.
            5. DẠNG TRẢ LỜI NGẮN (short_answer): CHỈ DÀNH CHO câu tính ra 1 đáp số. "options" BẮT BUỘC là mảng rỗng []. "correct_answer" là chuỗi đáp số ngắn (ví dụ: "12", "-3.5"). TUYỆT ĐỐI KHÔNG dùng cho câu có các ý a, b, c, d.
            6. CHỈ SỐ DƯỚI & CÔNG THỨC HÓA HỌC: Giữ nguyên thẻ <sub> và <sup>, TUYỆT ĐỐI KHÔNG viết thành CH_2, CO_2, H_2O. Phải viết là CH<sub>2</sub>, CO<sub>2</sub>, H<sub>2</sub>O hoặc \\(\text{{CH}}_2\\).
            7. CÔNG THỨC TOÁN LATEX: Mọi biểu thức toán học phải bọc trong \\( và \\).
            8. TUYỆT ĐỐI KHÔNG ĐƯỢC XÓA BỎ các thẻ [IMG_X]. Phải sao chép NGUYÊN XI, ĐÚNG TỪNG KÝ TỰ các placeholder [IMG_X] vào câu hỏi hoặc đáp án tương ứng.
            9. Chỉ trả về duy nhất mảng JSON [...] không có văn bản giải thích nào khác ngoài JSON.{img_strict_rule}

            Văn bản:
            {chunk}
            """

        try:
            response = await call_gemini_with_fallback(
                prompt=prompt,
                api_keys=chunk_keys,
                system_instruction=system_instruction,
                thinking_budget=0
            )

            raw_text = response.text
            # Khôi phục lại placeholder ảnh mà AI có thể đã viết sai
            raw_text = restore_image_placeholders(raw_text)
            fixed_raw = fix_json_latex_escapes(raw_text)
            parsed_json = None

            if json_repair is not None:
                try:
                    parsed_json = json_repair.loads(fixed_raw)
                except Exception:
                    try:
                        parsed_json = json_repair.loads(raw_text)
                    except Exception:
                        pass

            if parsed_json is None:
                match = re.search(r'\[\s*\{.*\}\s*\]', fixed_raw, re.DOTALL)
                json_text = match.group(0) if match else fixed_raw
                try:
                    parsed_json = json.loads(json_text, strict=False)
                except Exception:
                    pass

            # Nếu AI trả về bọc trong Object {"questions": [...]}, tự động trích xuất danh sách
            if isinstance(parsed_json, dict):
                for k in ["questions", "data", "quiz", "result", "items", "cau_hoi", "list"]:
                    if isinstance(parsed_json.get(k), list):
                        parsed_json = parsed_json[k]
                        break
                else:
                    if "question" in parsed_json:
                        parsed_json = [parsed_json]
                    else:
                        parsed_json = []

            if isinstance(parsed_json, list):
                norm_questions = [normalize_question_data(q) for q in parsed_json if isinstance(q, dict)]
                return reinject_missing_image_placeholders(chunk, norm_questions)
            return None

        except Exception as e:
            last_chunk_error = e
            logger.warning(f"Lỗi khi xử lý chunk {idx + 1}: {e}")
            err_str = str(e).lower()
            is_fatal = isinstance(e, GeminiAPIException) or any(k in err_str for k in ["429", "quota", "invalid", "not valid", "no api key", "chưa cấu hình", "tất cả các key"])
            if is_fatal:
                abort_event.set()
            return None

    # Thiết lập Multi-Key Worker Pool song song:
    # 1 key: 2 luồng, 2 keys: 4 luồng, 3 keys: 6 luồng, >= 4 keys: tối đa 8 luồng
    max_concurrency = max(2, min(num_keys * 2, 8))
    worker_semaphore = asyncio.Semaphore(max_concurrency)
    abort_event = asyncio.Event()
    completed_chunks = 0
    total_valid_chunks = sum(1 for c in chunks if c.strip()) or 1

    async def sem_process_chunk(idx: int, chunk: str, chunk_keys: List[str]):
        if abort_event.is_set():
            return (idx, None)
        async with worker_semaphore:
            if abort_event.is_set():
                return (idx, None)

            if active_tasks is not None and task_id and task_id in active_tasks:
                worker_no = (idx % num_keys) + 1
                active_tasks[task_id]["message"] = f"AI Worker #{worker_no} đang bóc tách phần {idx + 1}/{len(chunks)}..."

            res = await process_chunk(idx, chunk, chunk_keys)
            if res is not None and task_id and not abort_event.is_set():
                nonlocal completed_chunks
                completed_chunks += 1
                try:
                    from core.state import active_tasks as g_tasks
                    if task_id in g_tasks:
                        pct = min(85, round(35 + (completed_chunks / total_valid_chunks * 45)))
                        g_tasks[task_id]["progress"] = pct
                        g_tasks[task_id]["message"] = f"AI đã hoàn thành {completed_chunks}/{total_valid_chunks} phần ({pct}%)..."
                except Exception:
                    pass
            return (idx, res)

    # Phân phối đều các phần cho từng API Key theo mô hình Round-Robin kết hợp Fallback
    tasks = []
    for idx, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        primary_k_idx = idx % num_keys
        # Key chính được thử trước, các key còn lại làm fallback nếu key chính hết quota
        rotated_keys = [valid_keys[(primary_k_idx + offset) % num_keys] for offset in range(num_keys)]
        tasks.append(sem_process_chunk(idx, chunk, rotated_keys))

    raw_results = await asyncio.gather(*tasks)

    # RÁP LẠI TOÀN BỘ ĐỀ THI THEO ĐÚNG THỨ TỰ BAN ĐẦU (sắp xếp theo chunk index idx)
    sorted_results = sorted(raw_results, key=lambda x: x[0])
    for idx, chunk_res in sorted_results:
        if chunk_res:
            all_extracted_data.extend(chunk_res)

    if not all_extracted_data and any(c.strip() for c in chunks):
        diag = diagnose_gemini_error(last_chunk_error or Exception("AI không thể trích xuất bất kỳ câu hỏi nào từ tài liệu."), keys_tried=valid_keys)
        raise GeminiAPIException(diag)

    # Áp đặt lại Bảng đáp án chuẩn (Source of Truth) lên toàn bộ dữ liệu bóc tách
    if answer_key and hasattr(answer_key, 'get_answer'):
        from core.answer_key_extractor import reconcile_quiz_with_answer_key
        all_extracted_data = reconcile_quiz_with_answer_key(all_extracted_data, answer_key)



    return all_extracted_data



def apply_image_mapping_to_data(data, mapping):

    """Thay thế các placeholder ảnh [IMG_X] thành thẻ img HTML trong toàn bộ dữ liệu câu hỏi."""

    if isinstance(data, dict):

        return {k: apply_image_mapping_to_data(v, mapping) for k, v in data.items()}

    elif isinstance(data, list):

        return [apply_image_mapping_to_data(v, mapping) for v in data]

    elif isinstance(data, str):

        data = restore_image_placeholders(data)

        for ph, img_tag in mapping.items():

            num_match = re.search(r'\d+', ph)

            if num_match:

                num = num_match.group(0)

                pattern = re.compile(

                    r'\\?\[\s*(?:IMG|HÌNH|ẢNH|HINH|ANH|IMAGE|PIC|PICTURE)?[\s_#-]*' + re.escape(num) + r'\s*\\?\]'

                    r'|\b(?:IMG|HÌNH|ẢNH|HINH|ANH|IMAGE|PIC)[\s_-]+' + re.escape(num) + r'\b',

                    re.IGNORECASE

                )

                data = pattern.sub(lambda m: img_tag, data)

            else:

                ph_clean = ph.replace('[', '').replace(']', '').strip()

                data = re.sub(r'\\?\[\s*' + re.escape(ph_clean) + r'\s*\\?\]', lambda m: img_tag, data, flags=re.IGNORECASE)

                data = re.sub(r'\b' + re.escape(ph_clean) + r'\b', lambda m: img_tag, data, flags=re.IGNORECASE)

        return data

    return data



async def generate_mcq_from_pdf(

    pdf_path: str,

    api_keys: List[str],

    task_id: str = None,

    active_tasks: dict = None

) -> List[Dict[str, Any]]:

    """Dùng PyMuPDF bóc tách text và trích xuất hình ảnh chính xác sau đó đưa cho AI xử lý."""

    if not api_keys:

        raise Exception("Hệ thống chưa được cấu hình API Key.")

        

    if fitz is None:

        raise Exception("Thư viện PyMuPDF chưa được cài đặt.")

        

    from core.image_converter import process_image_blob
    from services.r2_service import upload_image_to_r2



    doc = fitz.open(pdf_path)

    full_text_parts = []

    image_mapping = {}

    img_counter = 0



    for page in doc:

        page_items = []

        # 1. Khối văn bản

        blocks = page.get_text("blocks")

        for b in blocks:

            txt = b[4].strip()

            if txt:

                page_items.append((b[1], b[0], 'text', b[4]))



        # 2. Khối hình ảnh

        for img_info in page.get_images():

            xref = img_info[0]

            width, height = img_info[2], img_info[3]

            if width < 30 or height < 30:

                continue



            rects = page.get_image_rects(xref)

            if not rects:

                continue



            try:

                extracted = doc.extract_image(xref)

                if not extracted or not extracted.get('image'):

                    continue

                

                raw_bytes = extracted['image']

                raw_ext = extracted.get('ext', 'png').lower()

                mime = f"image/{raw_ext}" if raw_ext != 'jpg' else "image/jpeg"

                processed_bytes, processed_mime = process_image_blob(raw_bytes, mime)

                

                img_url = upload_image_to_r2(processed_bytes, mime_type=processed_mime)

                if img_url:

                    img_counter += 1

                    ph = f"[IMG_{img_counter}]"

                    image_mapping[ph] = f"<img src='{img_url}' class='quiz-image' style='max-width: 100%; height: auto; margin: 8px 0;' />"

                    for r in rects:

                        page_items.append((r.y0, r.x0, 'image', f"\n{ph}\n"))

            except Exception as e:

                print(f"[CẢNH BÁO] Lỗi trích xuất ảnh PDF xref {xref}: {e}")



        page_items.sort(key=lambda x: (x[0], x[1]))

        page_text = "\n".join(item[3] for item in page_items)

        full_text_parts.append(page_text)



    doc.close()

    pdf_text = "\n\n".join(full_text_parts)



    extracted_data = await generate_mcq_with_gemini(pdf_text, api_keys, task_id, active_tasks)

    if image_mapping and extracted_data:

        extracted_data = apply_image_mapping_to_data(extracted_data, image_mapping)

        

    return extracted_data





async def process_pdf_with_ocr(
    pdf_path: str,
    api_keys: List[str],
    task_id: Optional[str] = None,
    active_tasks: Optional[dict] = None
) -> List[Dict[str, Any]]:
    """
    OCR chuyên sâu cho PDF scan / tài liệu chụp ảnh.
    Chuyển đổi từng trang thành ảnh chất lượng cao và dùng Gemini Multimodal để bóc tách câu hỏi,
    công thức LaTeX và hình vẽ.
    """
    valid_keys = []
    seen_keys = set()
    for k in (api_keys or []):
        if k and isinstance(k, str) and k.strip() and k.strip() not in seen_keys:
            seen_keys.add(k.strip())
            valid_keys.append(k.strip())

    if not valid_keys:
        diag = diagnose_gemini_error(Exception("Chưa cấu hình API Key"), keys_tried=[])
        raise GeminiAPIException(diag)

    num_keys = len(valid_keys)

    if fitz is None:
        raise Exception("Thư viện PyMuPDF chưa được cài đặt để đọc PDF.")

    if active_tasks is None:
        try:
            from core.state import active_tasks as global_active_tasks
            active_tasks = global_active_tasks
        except ImportError:
            pass

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    pages_bytes = []
    for page_idx in range(total_pages):
        page = doc[page_idx]
        pix = page.get_pixmap(dpi=180)
        pages_bytes.append((page_idx, pix.tobytes("jpeg")))
    doc.close()

    system_instruction = (
        "Bạn là chuyên gia OCR tài liệu đề thi trắc nghiệm Việt Nam chuẩn xác nhất.\n"
        "Nhiệm vụ: Đọc ảnh trang đề thi chụp/scan và bóc tách CHÍNH XÁC toàn bộ câu hỏi theo chuẩn GDPT 2018 (mcq, true_false, short_answer).\n"
        "Quy tắc sống còn:\n"
        "1. Nhận diện trung thực mọi chữ, số, công thức toán/hóa học, bảng biểu từ ảnh.\n"
        "2. Biểu thức toán BẮT BUỘC đặt trong \\( và \\). Công thức hóa học / chỉ số dưới dùng thẻ HTML <sub> và <sup> (vd: H<sub>2</sub>SO<sub>4</sub>, Fe<sup>3+</sup>).\n"
        "3. ĐÁP ÁN: Nếu đề có dấu hiệu đáp án của giáo viên (khoanh tròn, gạch chân, dấu tick, dấu *, hoặc bảng đáp án): "
        "hãy gán đúng đáp án đó và đặt is_ai_suggested: false.\n"
        "Nếu KHÔNG có bất kỳ dấu hiệu đáp án nào: HÃY TỰ GIẢI ĐỂ GỢI Ý ĐÁP ÁN ĐÚNG KÈM LỜI GIẢI ('explain'), "
        "và BẮT BUỘC đặt is_ai_suggested: true, ai_suggestion_note: 'AI đề xuất, cần giáo viên xác nhận'.\n"
        "4. Định dạng trả về: DUY NHẤT một JSON array [...] gồm các câu hỏi của trang này."
    )

    max_concurrency = max(2, min(num_keys * 2, 8))
    worker_semaphore = asyncio.Semaphore(max_concurrency)
    completed_pages = 0

    async def ocr_single_page(page_idx: int, img_bytes: bytes, page_keys: List[str]):
        page_num = page_idx + 1
        async with worker_semaphore:
            if active_tasks and task_id and task_id in active_tasks:
                worker_no = (page_idx % num_keys) + 1
                active_tasks[task_id]["message"] = f"AI Worker #{worker_no} đang OCR trang scan {page_num}/{total_pages}..."

            from google.genai import types
            image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
            prompt_text = f"""
            Trang đề thi số {page_num}/{total_pages}. Hãy nhận diện toàn bộ câu hỏi và trích xuất thành mảng JSON:
            [
              {{
                "question_number": {page_num},
                "type": "mcq",
                "group_title": "",
                "question": "Nội dung câu hỏi...",
                "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
                "correct_answer": "A. ...",
                "explain": "Lời giải chi tiết...",
                "is_ai_suggested": true,
                "ai_suggestion_note": "AI đề xuất, cần giáo viên xác nhận"
              }}
            ]
            """
            multimodal_contents = [image_part, prompt_text]

            try:
                response = await call_gemini_with_fallback(
                    prompt=multimodal_contents,
                    api_keys=page_keys,
                    system_instruction=system_instruction,
                    thinking_budget=0
                )

                raw_text = response.text
                fixed_raw = fix_json_latex_escapes(raw_text)
                parsed_page = None

                if json_repair is not None:
                    try:
                        parsed_page = json_repair.loads(fixed_raw)
                    except Exception:
                        try:
                            parsed_page = json_repair.loads(raw_text)
                        except Exception:
                            pass

                if parsed_page is None:
                    match = re.search(r'\[\s*\{.*\}\s*\]', fixed_raw, re.DOTALL)
                    json_text = match.group(0) if match else fixed_raw
                    try:
                        parsed_page = json.loads(json_text, strict=False)
                    except Exception:
                        pass

                if isinstance(parsed_page, dict):
                    for k in ["questions", "data", "quiz", "result", "items", "cau_hoi", "list"]:
                        if isinstance(parsed_page.get(k), list):
                            parsed_page = parsed_page[k]
                            break
                    else:
                        if "question" in parsed_page:
                            parsed_page = [parsed_page]
                        else:
                            parsed_page = []

                page_questions = []
                if isinstance(parsed_page, list):
                    for q in parsed_page:
                        if isinstance(q, dict):
                            norm_q = normalize_question_data(q)
                            page_questions.append(norm_q)

                nonlocal completed_pages
                completed_pages += 1
                if active_tasks and task_id and task_id in active_tasks:
                    pct = min(85, round(20 + (completed_pages / total_pages * 65)))
                    active_tasks[task_id]["progress"] = pct
                    active_tasks[task_id]["message"] = f"Đã OCR xong {completed_pages}/{total_pages} trang ({pct}%)..."

                return (page_idx, page_questions)
            except Exception as page_err:
                logger.warning(f"[CẢNH BÁO] OCR trang {page_num} gặp lỗi: {page_err}")
                return (page_idx, [])

    page_tasks = []
    for page_idx, img_b in pages_bytes:
        primary_k_idx = page_idx % num_keys
        page_keys = [valid_keys[(primary_k_idx + off) % num_keys] for off in range(num_keys)]
        page_tasks.append(ocr_single_page(page_idx, img_b, page_keys))

    page_results = await asyncio.gather(*page_tasks)
    sorted_page_results = sorted(page_results, key=lambda x: x[0])

    all_extracted_questions = []
    for p_idx, q_list in sorted_page_results:
        all_extracted_questions.extend(q_list)

    if not all_extracted_questions:
        raise Exception("Không thể nhận diện câu hỏi từ tài liệu PDF scan / ảnh.")

    return all_extracted_questions


async def process_image_with_ocr(
    image_bytes: bytes,
    api_keys: List[str],
    mime_type: str = "image/jpeg",
    task_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """OCR xử lý trực tiếp 1 ảnh chụp đề thi (.png, .jpg, .webp)."""
    from google.genai import types
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    prompt_text = """
    Hãy đọc kỹ ảnh chụp đề thi này và bóc tách toàn bộ câu hỏi trắc nghiệm thành danh sách JSON chuẩn.
    Nếu đề không có đáp án đánh dấu sẵn, hãy tự giải và gán is_ai_suggested: true, ai_suggestion_note: 'AI đề xuất, cần giáo viên xác nhận'.
    Trả về DUY NHẤT một mảng JSON các câu hỏi.
    """
    system_instruction = (
        "Bạn là chuyên gia OCR tài liệu sư phạm đề thi trắc nghiệm Việt Nam. "
        "Nhận diện chính xác chữ, ký hiệu, công thức LaTeX \\( ... \\), chỉ số dưới HTML <sub>, <sup>. "
        "Chuẩn hóa 3 dạng câu hỏi GDPT 2018 (mcq, true_false, short_answer). "
        "Gợi ý đáp án kèm lời giải nếu đề chưa có đáp án và đánh dấu is_ai_suggested: true."
    )
    response = await call_gemini_with_fallback(
        prompt=[image_part, prompt_text],
        api_keys=api_keys,
        system_instruction=system_instruction,
        thinking_budget=0
    )
    raw_text = response.text
    fixed_raw = fix_json_latex_escapes(raw_text)
    parsed = None
    if json_repair is not None:
        try:
            parsed = json_repair.loads(fixed_raw)
        except Exception:
            pass
    if parsed is None:
        match = re.search(r'\[\s*\{.*\}\s*\]', fixed_raw, re.DOTALL)
        json_text = match.group(0) if match else fixed_raw
        try:
            parsed = json.loads(json_text, strict=False)
        except Exception:
            pass
    if isinstance(parsed, dict):
        for k in ["questions", "data", "quiz", "result", "items"]:
            if isinstance(parsed.get(k), list):
                parsed = parsed[k]
                break
        else:
            parsed = [parsed] if "question" in parsed else []
    if isinstance(parsed, list):
        return [normalize_question_data(q) for q in parsed if isinstance(q, dict)]
    return []


def compact_quiz_for_ai_prompt(
    quiz_data: List[Dict[str, Any]],
    include_answers: bool = True,
    include_explain: bool = True,
    indices: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Rút gọn dữ liệu câu hỏi trước khi gửi vào prompt Gemini:
    - Loại bỏ Base64 image data URIs (thay bằng placeholder ngắn) và metadata UI thừa.
    - Chuẩn hóa loại câu hỏi qua resolve_question_type.
    - Không làm thay đổi (mutate) danh sách câu hỏi gốc.
    """
    from app.utils.helpers import resolve_question_type

    compacted = []
    target_pairs = (
        [(idx, quiz_data[idx]) for idx in indices if 0 <= idx < len(quiz_data)]
        if indices is not None
        else list(enumerate(quiz_data or []))
    )

    for idx, q in target_pairs:
        if not isinstance(q, dict):
            continue
        q_type = resolve_question_type(q)
        item: Dict[str, Any] = {
            "index": idx,
            "type": q_type,
            "question": q.get("question", ""),
        }
        opts = q.get("options")
        if isinstance(opts, list) and len(opts) > 0:
            item["options"] = opts
        if q.get("group_title"):
            item["group_title"] = q.get("group_title")
        if q.get("passage"):
            item["passage"] = q.get("passage")
        img = q.get("image")
        if img:
            img_str = str(img)
            item["image"] = "[CÓ_HÌNH_ẢNH]" if (img_str.startswith("data:") or len(img_str) > 300) else img_str
        if include_answers and q.get("correct_answer") not in (None, ""):
            item["correct_answer"] = q.get("correct_answer")
        if include_explain and q.get("explain"):
            item["explain"] = q.get("explain")
        compacted.append(item)

    return compacted


async def cross_check_answers(
    quiz_data: List[Dict[str, Any]],
    api_keys: List[str]
) -> Dict[str, Any]:
    """
    Kiểm tra chéo đáp án độc lập:
    AI tự giải lại từng câu hỏi mà KHÔNG nhìn vào đáp án của giáo viên,
    sau đó so sánh và phát hiện những câu có đáp án lệch nhau để cảnh báo giáo viên rà soát.
    """
    if not quiz_data:
        return {"status": "success", "total_checked": 0, "mismatch_count": 0, "mismatches": [], "data": quiz_data}

    valid_keys = []
    seen_keys = set()
    for k in (api_keys or []):
        if k and isinstance(k, str) and k.strip() and k.strip() not in seen_keys:
            seen_keys.add(k.strip())
            valid_keys.append(k.strip())

    if not valid_keys:
        return {"status": "error", "message": "Chưa cấu hình API Key"}

    num_keys = len(valid_keys)

    from app.utils.helpers import (
        evaluate_mcq_answer,
        evaluate_short_answer,
        evaluate_true_false_answer,
        resolve_question_type,
    )

    # Chuẩn bị dữ liệu gọn nhẹ chỉ chứa câu hỏi và phương án (bỏ qua câu tự luận mở)
    compacted_all = compact_quiz_for_ai_prompt(quiz_data, include_answers=False, include_explain=False)
    blind_questions = [item for item in compacted_all if item.get("type") != "essay"]

    if not blind_questions:
        cleaned = []
        for orig_q in quiz_data:
            q_copy = dict(orig_q)
            q_copy["has_cross_check_warning"] = False
            q_copy["cross_check_info"] = None
            cleaned.append(q_copy)
        return {
            "status": "success",
            "total_checked": len(quiz_data),
            "total_questions": len(quiz_data),
            "mismatch_count": 0,
            "mismatches_found": 0,
            "mismatches": [],
            "quiz_data": cleaned,
            "data": cleaned,
        }

    system_instruction = (
        "Bạn là Giám khảo Khảo thí Độc lập và Chuyên gia Giải đề cấp cao. "
        "Nhiệm vụ của bạn là GIẢI ĐỘC LẬP VÀ TUYỆT ĐỐI CHÍNH XÁC từng câu hỏi được giao. "
        "Hãy tính toán, suy luận logic, sư phạm để đưa ra đáp án chuẩn nhất. "
        "Đối với câu mcq: chọn đúng chữ cái A, B, C, D (ví dụ 'A. ...'). "
        "Đối với câu true_false: xác định đúng/sai cho từng ý a, b, c, d: {'a': bool, 'b': bool, 'c': bool, 'd': bool}. "
        "Đối với câu short_answer: điền đáp số ngắn. "
        "Trả về DUY NHẤT một mảng JSON các kết quả giải: "
        "[{\"index\": 0, \"ai_solved_answer\": \"...\", \"explain\": \"...\"}]"
    )

    # Chia thành các batch tối đa 15 câu để tránh chạm giới hạn output tokens
    batch_size = 15
    batches = [blind_questions[i:i + batch_size] for i in range(0, len(blind_questions), batch_size)]

    async def solve_single_batch(b_idx: int, b_questions: list, b_keys: List[str]):
        prompt = f"""
        Hãy giải độc lập danh sách {len(b_questions)} câu hỏi sau và cung cấp đáp án đúng cùng lời giải:
        {json.dumps(b_questions, ensure_ascii=False)}
        """
        try:
            response = await call_gemini_with_fallback(
                prompt=prompt,
                api_keys=b_keys,
                system_instruction=system_instruction,
                thinking_budget=0
            )

            fixed_raw = fix_json_latex_escapes(response.text)
            batch_list = None
            if json_repair is not None:
                try:
                    batch_list = json_repair.loads(fixed_raw)
                except Exception:
                    pass
            if batch_list is None:
                m = re.search(r'\[.*\]', fixed_raw, re.DOTALL)
                if m:
                    try:
                        batch_list = json.loads(m.group(0), strict=False)
                    except Exception:
                        pass

            if isinstance(batch_list, dict):
                for k in ["results", "data", "solutions", "answers"]:
                    if isinstance(batch_list.get(k), list):
                        batch_list = batch_list[k]
                        break

            if isinstance(batch_list, list):
                return {"items": batch_list, "error": None}
            return {"items": [], "error": None}
        except Exception as e:
            logger.warning(f"Lỗi khi giải chéo batch {b_idx + 1}: {e}")
            return {"items": [], "error": e}

    # Phân phối đều các batch cho từng API Key theo Round-Robin
    batch_tasks = []
    for b_idx, b_q in enumerate(batches):
        b_keys = [valid_keys[(b_idx + off) % num_keys] for off in range(num_keys)]
        batch_tasks.append(solve_single_batch(b_idx, b_q, b_keys))

    batch_results = await asyncio.gather(*batch_tasks)
    if batch_results and all(br.get("error") is not None for br in batch_results):
        raise batch_results[0]["error"]

    solved_list = []
    for br in batch_results:
        items = br.get("items") if isinstance(br, dict) else br
        if items:
            solved_list.extend(items)

    solved_map = {}
    for item in solved_list:
        if isinstance(item, dict):
            idx_val = item.get("index")
            if idx_val is None:
                idx_val = item.get("question_index") or item.get("id") or item.get("cau")
            if idx_val is not None:
                try:
                    num_match = re.search(r'\d+', str(idx_val))
                    if num_match:
                        parsed_idx = int(num_match.group(0))
                        solved_map[parsed_idx] = item
                except Exception:
                    pass

    # Tự động đồng bộ nếu AI giải trả về 1-based index (1 đến N) thay vì 0-based index (0 đến N-1)
    if solved_map and 0 not in solved_map and len(quiz_data) in solved_map:
        solved_map = {k - 1: v for k, v in solved_map.items()}

    mismatches = []
    updated_quiz_data = []

    for idx, orig_q in enumerate(quiz_data):
        q_copy = dict(orig_q)
        teacher_ca = q_copy.get("correct_answer")
        q_type = resolve_question_type(q_copy)

        if q_type != "essay" and idx in solved_map:
            ai_item = solved_map[idx]
            ai_ans = (
                ai_item.get("ai_solved_answer") or
                ai_item.get("ai_answer") or
                ai_item.get("answer") or
                ai_item.get("correct_answer") or
                ai_item.get("solution") or
                ai_item.get("dap_an")
            )
            ai_explain = (
                ai_item.get("explain") or
                ai_item.get("explanation") or
                ai_item.get("reason") or
                ai_item.get("loi_giai") or
                ""
            )

            # So sánh đáp án bằng bộ chuẩn hóa thống nhất của hệ thống
            is_different = False
            if ai_ans is not None:
                if q_type == "mcq":
                    t_str = str(teacher_ca or "").strip()
                    a_str = str(ai_ans or "").strip()
                    if t_str and a_str:
                        is_different = not evaluate_mcq_answer(a_str, t_str, q_copy.get("options"))
                elif q_type == "true_false":
                    t_tf = parse_tf_answer(teacher_ca)
                    a_tf = parse_tf_answer(ai_ans)
                    if t_tf and a_tf:
                        is_same, _ = evaluate_true_false_answer(a_tf, t_tf)
                        is_different = not is_same
                else:  # short_answer
                    t_str = str(teacher_ca or "").strip()
                    a_str = str(ai_ans or "").strip()
                    if t_str and a_str:
                        is_different = not evaluate_short_answer(a_str, t_str)

            if is_different:
                mismatch_record = {
                    "question_index": idx,
                    "teacher_answer": teacher_ca,
                    "ai_answer": ai_ans,
                    "ai_explain": ai_explain,
                    "reason": f"AI giải ra kết quả khác: {ai_ans}",
                    "warning_message": f"Cảnh báo lệch đáp án: giáo viên chọn [{teacher_ca}], AI giải ra [{ai_ans}]. Cần rà soát lại."
                }
                mismatches.append(mismatch_record)
                q_copy["has_cross_check_warning"] = True
                q_copy["cross_check_info"] = mismatch_record
            else:
                q_copy["has_cross_check_warning"] = False
                q_copy["cross_check_info"] = None
        else:
            q_copy["has_cross_check_warning"] = False
            q_copy["cross_check_info"] = None

        updated_quiz_data.append(q_copy)

    return {
        "status": "success",
        "total_checked": len(quiz_data),
        "total_questions": len(quiz_data),
        "mismatch_count": len(mismatches),
        "mismatches_found": len(mismatches),
        "mismatches": mismatches,
        "quiz_data": updated_quiz_data,
        "data": updated_quiz_data
    }


async def generate_similar_questions(
    base_question: Dict[str, Any],
    count: int = 1,
    mode: str = "change_numbers",
    difficulty: str = "keep",
    api_keys: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Sinh các câu hỏi tương tự từ một câu hỏi có sẵn:
    - mode="change_numbers": Thay đổi số liệu, tính toán lại chính xác đáp án và lời giải.
    - mode="change_context": Thay đổi tình huống đời sống / ngữ cảnh thực tế nhưng giữ nguyên dạng toán.
    - mode="both": Thay đổi toàn diện cả số liệu và ngữ cảnh.
    """
    if not api_keys:
        raise Exception("Chưa cấu hình API Key.")

    q_type = base_question.get("type", "mcq")
    mode_instructions = {
        "change_numbers": (
            "THAY ĐỔI SỐ LIỆU: Giữ nguyên hoàn toàn dạng bài, công thức và cấu trúc câu hỏi. "
            "Thay đổi các số liệu tham số đầu vào bằng các con số hợp lý, tính toán lại 100% ĐÁP ÁN ĐÚNG "
            "và tạo các phương án nhiễu logic. BẮT BUỘC cập nhật lời giải 'explain' từng bước theo số liệu mới."
        ),
        "change_context": (
            "THAY ĐỔI NGỮ CẢNH: Giữ nguyên dạng toán, mức độ tư duy và cốt lõi lý thuyết. "
            "Đổi tình huống thực tế, tên nhân vật, vật thể hoặc bối cảnh ứng dụng đời sống "
            "để học sinh tiếp cận dưới góc nhìn mới phong phú."
        ),
        "both": (
            "KẾT HỢP CẢ HAI: Thay đổi cả số liệu tính toán và đổi mới toàn diện tình huống đời sống / ngữ cảnh thực tế. "
            "Tính toán lại đáp án chuẩn xác 100% kèm lời giải chi tiết."
        )
    }.get(mode, "THAY ĐỔI SỐ LIỆU VÀ NGỮ CẢNH")

    system_instruction = (
        f"Bạn là Chuyên gia Khảo thí và Biên soạn Ngân hàng Đề thi chuẩn GDPT 2018. "
        f"Nhiệm vụ của bạn là sinh ra {count} câu hỏi tương tự từ câu hỏi gốc được cung cấp.\n"
        f"Yêu cầu nghiệp vụ:\n"
        f"1. {mode_instructions}\n"
        f"2. Đảm bảo câu hỏi mới có cùng kiểu loại (type: '{q_type}') và mức độ tư duy tương đương.\n"
        f"3. Công thức toán học bọc trong \\( và \\), chỉ số dưới hóa học dùng <sub> / <sup>. Nếu câu hỏi có bảng biến thiên hoặc bảng số liệu, BẮT BUỘC dùng định dạng bảng HTML thực chất <table class=\"quiz-table\" border=\"1\">...</table> chuẩn mực như tạo bảng trong Word.\n"
        f"4. Trả về DUY NHẤT một JSON array [...] gồm đúng {count} câu hỏi mới."
    )

    prompt = f"""
    Câu hỏi gốc:
    {json.dumps(base_question, ensure_ascii=False)}

    Hãy sinh ra đúng {count} câu hỏi tương tự theo chế độ '{mode}' (độ khó: '{difficulty}').
    Trả về định dạng JSON array:
    [
      {{
        "type": "{q_type}",
        "group_title": "",
        "question": "Nội dung câu hỏi mới...",
        "options": [...],
        "correct_answer": ...,
        "explain": "Lời giải chi tiết từng bước..."
      }}
    ]
    """

    response = await call_gemini_with_fallback(
        prompt=prompt,
        api_keys=api_keys,
        system_instruction=system_instruction,
        thinking_budget=0
    )

    fixed_raw = fix_json_latex_escapes(response.text)
    new_questions = None
    if json_repair is not None:
        try:
            new_questions = json_repair.loads(fixed_raw)
        except Exception:
            pass
    if new_questions is None:
        m = re.search(r'\[.*\]', fixed_raw, re.DOTALL)
        if m:
            try:
                new_questions = json.loads(m.group(0), strict=False)
            except Exception:
                pass

    if isinstance(new_questions, dict):
        for k in ["questions", "data", "items", "list"]:
            if isinstance(new_questions.get(k), list):
                new_questions = new_questions[k]
                break

    if not isinstance(new_questions, list):
        new_questions = []

    normalized_results = []
    for q in new_questions[:count]:
        if isinstance(q, dict):
            q["is_ai_generated_variant"] = True
            norm_q = normalize_question_data(q)
            normalized_results.append(norm_q)

    return normalized_results


class AIService:
    """
    Dịch vụ AI thông minh (AI Service) tương tác với Google Gemini.
    Tích hợp xoay vòng API Keys tự động, thử lại (Retry) khi gặp Rate Limit (429),
    chống treo tiến trình với Timeout an toàn và cơ chế sửa lỗi JSON/LaTeX.
    """

    async def generate_quiz_from_text(
        self,
        marked_text: str,
        api_keys: List[str],
        task_id: Optional[str] = None,
        active_tasks: Optional[dict] = None
    ) -> List[dict]:
        """Bóc tách và tạo đề thi trắc nghiệm chuẩn từ văn bản đã đánh dấu."""
        return await generate_mcq_with_gemini(marked_text, api_keys, task_id, active_tasks)

    async def generate_quiz_from_pdf(
        self,
        pdf_bytes: bytes,
        api_keys: List[str],
        task_id: Optional[str] = None,
        active_tasks: Optional[dict] = None
    ) -> List[dict]:
        """Trích xuất đề thi trắc nghiệm kèm công thức và hình ảnh từ tệp PDF."""
        return await generate_mcq_from_pdf(pdf_bytes, api_keys, task_id, active_tasks)

    async def call_gemini(
        self,
        prompt: str,
        api_keys: List[str],
        json_mode: bool = True
    ) -> Optional[str]:
        """Gọi mô hình Gemini an toàn với cơ chế tự động luân phiên khóa API và sửa lỗi."""
        return await call_gemini_with_fallback(prompt, api_keys, json_mode=json_mode)

    async def process_pdf_ocr(
        self,
        pdf_path: str,
        api_keys: List[str],
        task_id: Optional[str] = None,
        active_tasks: Optional[dict] = None
    ) -> List[dict]:
        """OCR bóc tách đề thi từ PDF scan / tài liệu chụp ảnh."""
        return await process_pdf_with_ocr(pdf_path, api_keys, task_id, active_tasks)

    async def cross_check_quiz(
        self,
        quiz_data: List[dict],
        api_keys: List[str]
    ) -> Dict[str, Any]:
        """Kiểm tra chéo đáp án độc lập và cảnh báo câu lệch đáp án."""
        return await cross_check_answers(quiz_data, api_keys)

    async def generate_variants(
        self,
        base_question: dict,
        count: int = 1,
        mode: str = "change_numbers",
        difficulty: str = "keep",
        api_keys: List[str] = None
    ) -> List[dict]:
        """Sinh câu hỏi tương tự từ câu hỏi gốc."""
        return await generate_similar_questions(base_question, count, mode, difficulty, api_keys)


# Thực thể singleton dùng chung
ai_service = AIService()
