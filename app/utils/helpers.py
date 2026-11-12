"""
General Utility Helpers for HocNhanhTN.
"""

import html
import re
from typing import Any, Dict, List, Optional, Tuple


def sanitize_filename(filename: str) -> str:
    """Loại bỏ các ký tự nguy hiểm khỏi tên file."""
    clean = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
    return clean[:200]


def unescape_content(text: str) -> str:
    """Giải mã các ký tự HTML entity trong nội dung đề thi."""
    if not text or not isinstance(text, str):
        return text
    return html.unescape(text)


def extract_dict_subset(data: Dict[str, Any], keys: list) -> Dict[str, Any]:
    """Trích xuất một tập con của dictionary an toàn."""
    return {k: data[k] for k in keys if k in data}


def evaluate_mcq_answer(user_ans: Any, correct_ans: Any, options: Optional[List[str]] = None) -> bool:
    """
    So khớp chính xác đáp án trắc nghiệm 4 lựa chọn (MCQ):
    - Miễn nhiễm 100% với việc đảo trộn vị trí phương án (A, B, C, D) giữa các thiết bị.
    - Hỗ trợ correct_answer là chữ cái ('A'), chỉ số ('0'), chuỗi đầy đủ ('A. Hà Nội'), hoặc có dấu hoa thị ('*A. Hà Nội').
    - Hỗ trợ options có hoặc không có tiền tố chữ cái A-F, có hoặc không có thẻ HTML (<b>, <u>, <mark>).
    """
    if user_ans is None or correct_ans is None:
        return False

    u_raw = str(user_ans).strip()
    c_raw = str(correct_ans).strip()
    if not u_raw or not c_raw:
        return False

    def preserve_image_tags(text: str) -> str:
        def _img_sub(match):
            m_src = re.search(r'src=["\']?([^"\'>\s]+)["\']?', match.group(0), re.IGNORECASE)
            src_val = m_src.group(1).split('/')[-1] if m_src else "image"
            return f" [img:{src_val}] "
        t = re.sub(r'<img\b[^>]*>', _img_sub, str(text or ''), flags=re.IGNORECASE)
        # Hỗ trợ cả placeholder [IMG_X]
        t = re.sub(r'\[IMG_\d+\]', lambda m: f" [{m.group(0).lower()}] ", t, flags=re.IGNORECASE)
        return t

    def clean_text(text: str) -> str:
        t = preserve_image_tags(text)
        t = html.unescape(t)
        t = re.sub(r'<[^>]+>', '', t)
        t = re.sub(r'\\\(|\\\)|[\$]', '', t)
        t = t.replace('−', '-').replace('–', '-').replace('—', '-')
        t = re.sub(r'[\u00a0\u200b\s]+', ' ', t)
        return t.strip().lower()

    re_only_letter = r'^\*?\s*([A-Fa-f])[\.\:\)]?\s*$'
    re_prefix = r'^\*?\s*([A-Fa-f])(?:[\.\:\)]\s*|\s+)'

    def parse_item(s: Any, opts: Optional[List[str]]) -> Tuple[Optional[str], str]:
        # Nếu là chỉ số số nguyên hoặc chuỗi số '0', '1', '2'...
        if str(s).strip().isdigit() and opts and isinstance(opts, list):
            idx = int(str(s).strip())
            if 0 <= idx < len(opts):
                s = str(opts[idx]).strip()

        s_str = preserve_image_tags(str(s).strip())
        s_str = html.unescape(s_str)
        s_no_tag = re.sub(r'<[^>]+>', '', s_str).strip()

        # TH1: Chỉ có ký tự đại diện A-F (VD: "A", "A.", "*A", "A)")
        m_only = re.match(re_only_letter, s_no_tag)
        if m_only:
            char = m_only.group(1).upper()
            content = ''
            if opts and isinstance(opts, list):
                idx = ord(char) - ord('A')
                if 0 <= idx < len(opts):
                    opt_str = re.sub(r'<[^>]+>', '', html.unescape(preserve_image_tags(str(opts[idx]).strip()))).strip()
                    m_p = re.match(re_prefix, opt_str)
                    content = clean_text(opt_str[m_p.end():] if m_p else opt_str)
            return char, content

        # TH2: Có tiền tố chữ cái theo sau bởi nội dung (VD: "A. Hà Nội", "B) Paris")
        m_p = re.match(re_prefix, s_no_tag)
        if m_p:
            char = m_p.group(1).upper()
            content = clean_text(s_no_tag[m_p.end():])
            return char, content

        # TH3: Không có tiền tố chữ cái, chỉ có nội dung thuần túy
        return None, clean_text(s_no_tag)

    u_char, u_content = parse_item(u_raw, options)
    c_char, c_content = parse_item(c_raw, options)

    # 1. Nếu cả 2 đều có nội dung text: Ưu tiên tuyệt đối so khớp nội dung
    if u_content and c_content:
        return u_content == c_content

    # 2. Nếu một trong 2 bên không có nội dung text (chỉ có chữ cái đơn A-F):
    if u_char and c_char:
        return u_char == c_char

    # 3. So khớp trực tiếp chuỗi đã làm sạch
    if clean_text(u_raw) == clean_text(c_raw):
        return True

    return False


def evaluate_true_false_answer(user_ans: Any, correct_ans: Any) -> Tuple[bool, float]:
    """
    Chấm điểm câu hỏi trắc nghiệm Đúng / Sai theo chuẩn Bộ GD&ĐT:
    - Thang điểm chuẩn (4 ý): 1 ý đúng = 0.1đ | 2 ý đúng = 0.25đ | 3 ý đúng = 0.5đ | 4 ý đúng = 1.0đ
    - Chuẩn hóa linh hoạt: key 'a'-'d' (hoặc 'a)', '(a)', 'a.', '0'-'3'), giá trị bool hoặc 'true'/'đúng'/'dung'/'đ'/'d'/'1'
    - Nếu câu hỏi có số ý khác 4 (VD: 2 hoặc 3 ý): tính điểm tỉ lệ theo số ý đúng
    """
    def norm_tf(d: Any) -> Dict[str, bool]:
        if not isinstance(d, dict):
            if isinstance(d, (str, list, tuple)):
                from services.ai_service import parse_tf_answer
                d = parse_tf_answer(d)
            else:
                return {}
        if not isinstance(d, dict):
            return {}

        res = {}
        idx_map = {'0': 'a', '1': 'b', '2': 'c', '3': 'd'}
        for k, v in d.items():
            raw_k = str(k).lower().strip()
            # Làm sạch dấu ngoặc, dấu chấm: 'a)' -> 'a', '(b)' -> 'b', 'c.' -> 'c'
            clean_k = re.sub(r'[\(\)\[\]\.\:\-\s]', '', raw_k)
            if clean_k in idx_map:
                clean_k = idx_map[clean_k]
            if clean_k not in ['a', 'b', 'c', 'd']:
                m_k = re.search(r'[a-d0-3]', raw_k)
                if m_k:
                    found = m_k.group(0)
                    clean_k = idx_map.get(found, found)
                else:
                    continue

            if isinstance(v, bool):
                res[clean_k] = v
            elif isinstance(v, (int, float)):
                res[clean_k] = bool(v)
            elif isinstance(v, str):
                res[clean_k] = v.strip().lower() in ['true', 't', 'đúng', 'dung', 'đ', 'd', '1', 'yes', 'y']
            else:
                res[clean_k] = bool(v)
        return res

    u_norm = norm_tf(user_ans)
    c_norm = norm_tf(correct_ans)
    total_tf = len(c_norm)
    if total_tf == 0:
        return False, 0.0

    matches = sum(1 for k in c_norm if k in u_norm and u_norm[k] == c_norm[k])
    if total_tf == 4:
        tf_scale = {0: 0.0, 1: 0.1, 2: 0.25, 3: 0.5, 4: 1.0}
        earned = tf_scale.get(matches, 0.0)
    else:
        earned = round(float(matches) / float(total_tf), 2)

    is_correct = (matches == total_tf)
    return is_correct, earned


def evaluate_short_answer(user_ans: Any, correct_ans: Any) -> bool:
    """
    Chấm điểm câu hỏi trả lời ngắn (Short Answer):
    - Chuẩn hóa dấu phẩy thập phân ',' thành '.', loại bỏ khoảng trắng, dấu trừ unicode '−' thành '-'
    - Bỏ qua các tiền tố biến như 'x = ', 'y = ', 'kết quả: ', 'đáp số: '
    - Loại bỏ đơn vị đo lường và chú thích trong ngoặc (VD: '5 m' == '5', '5 (m)' == '5')
    - Hỗ trợ nhiều đáp án tương đương phân tách bởi '|' hoặc ';'
    - So sánh số thực (float) để 2.5 == 2.50 == 2,5
    - So sánh phân số cơ bản (VD: 1/2 == 0.5)
    """
    if user_ans is None or correct_ans is None:
        return False

    def clean_sa(s: Any) -> str:
        t = html.unescape(str(s or ''))
        t = re.sub(r'<[^>]+>', '', t)
        t = re.sub(r'\\\(|\\\)|[\$]', '', t)
        t = t.replace('−', '-').replace('–', '-').replace('—', '-')
        t = re.sub(r'[\u00a0\u200b\s]+', ' ', t).strip()
        t = re.sub(r'^(?:x|y|z|t|kết\s*quả|đáp\s*số|ans|answer|ket\s*qua|dap\s*so)\s*[:=]\s*', '', t, flags=re.IGNORECASE)
        # Loại bỏ chú thích trong ngoặc ở cuối (VD: "(m)", "(cm)", "(đvdt)", "(đáp số)")
        t = re.sub(r'\s*\([^\)]*\)\s*$', '', t).strip()
        # Loại bỏ đơn vị đo lường ở đuôi sau số (VD: 5m, 10cm, 2.5km/h, 30°, 50%)
        t = re.sub(r'(?<=\d)\s*(?:[a-zA-Z°%]+(?:\/[a-zA-Z]+)?(?:\^\d+)?)\s*$', '', t).strip()
        t = t.replace(' ', '')
        t = t.replace(',', '.')
        return t.strip().lower()

    def parse_frac(val: str) -> Optional[float]:
        m = re.match(r'^([\+\-]?\d+(?:\.\d+)?)\/([\+\-]?\d+(?:\.\d+)?)$', val)
        if m:
            denom = float(m.group(2))
            if denom != 0:
                return float(m.group(1)) / denom
        return None

    def compare_single(u_val: Any, c_val: Any) -> bool:
        u = clean_sa(u_val)
        c = clean_sa(c_val)
        if not u or not c:
            return False
        if u == c:
            return True

        # 1. So sánh số thực (float)
        try:
            if abs(float(u) - float(c)) < 1e-6:
                return True
        except Exception:
            pass

        # 2. So sánh phân số cơ bản (VD: 1/2 == 0.5 hoặc 2/4 == 1/2)
        try:
            u_f = parse_frac(u)
            c_f = parse_frac(c)
            if u_f is not None and c_f is not None and abs(u_f - c_f) < 1e-6:
                return True
            if u_f is not None:
                if abs(u_f - float(c)) < 1e-6:
                    return True
            if c_f is not None:
                if abs(float(u) - c_f) < 1e-6:
                    return True
        except Exception:
            pass

        return False

    c_raw = str(correct_ans).strip()
    # Hỗ trợ nhiều đáp án tương đương nếu được phân tách bằng '|' hoặc ';'
    if '|' in c_raw or (';' in c_raw and not re.search(r'\d+;\d+', c_raw)):
        candidates = [p.strip() for p in re.split(r'\s*[|;]\s*', c_raw) if p.strip()]
        return any(compare_single(user_ans, cand) for cand in candidates)

    return compare_single(user_ans, correct_ans)
