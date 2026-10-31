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

    def clean_text(text: str) -> str:
        t = html.unescape(str(text or ''))
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

        s_str = html.unescape(str(s).strip())
        s_no_tag = re.sub(r'<[^>]+>', '', s_str).strip()

        # TH1: Chỉ có ký tự đại diện A-F (VD: "A", "A.", "*A", "A)")
        m_only = re.match(re_only_letter, s_no_tag)
        if m_only:
            char = m_only.group(1).upper()
            content = ''
            if opts and isinstance(opts, list):
                idx = ord(char) - ord('A')
                if 0 <= idx < len(opts):
                    opt_str = re.sub(r'<[^>]+>', '', html.unescape(str(opts[idx]).strip())).strip()
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
    - Thang điểm: 1 ý đúng = 0.1đ | 2 ý đúng = 0.25đ | 3 ý đúng = 0.5đ | 4 ý đúng = 1.0đ
    - Chuẩn hóa linh hoạt: key 'a'-'d' hoặc '0'-'3', giá trị bool hoặc 'true'/'dung'/'1'
    """
    def norm_tf(d: Any) -> Dict[str, bool]:
        if not isinstance(d, dict):
            return {}
        res = {}
        idx_map = {'0': 'a', '1': 'b', '2': 'c', '3': 'd'}
        for k, v in d.items():
            lk = str(k).lower().strip()
            if lk in idx_map:
                lk = idx_map[lk]
            if isinstance(v, bool):
                res[lk] = v
            elif isinstance(v, str):
                res[lk] = v.strip().lower() in ['true', 't', 'đúng', 'dung', 'd', '1']
            elif isinstance(v, (int, float)):
                res[lk] = bool(v)
            else:
                res[lk] = bool(v)
        return res

    u_norm = norm_tf(user_ans)
    c_norm = norm_tf(correct_ans)
    total_tf = len(c_norm)
    if total_tf == 0:
        return False, 0.0

    matches = sum(1 for k in c_norm if k in u_norm and u_norm[k] == c_norm[k])
    tf_scale = {0: 0.0, 1: 0.1, 2: 0.25, 3: 0.5, 4: 1.0}
    earned = tf_scale.get(matches, float(matches) / float(total_tf))
    is_correct = (matches == total_tf)
    return is_correct, earned


def evaluate_short_answer(user_ans: Any, correct_ans: Any) -> bool:
    """
    Chấm điểm câu hỏi trả lời ngắn (Short Answer):
    - Chuẩn hóa dấu phẩy thập phân ',' thành '.', loại bỏ khoảng trắng, dấu trừ unicode '−' thành '-'
    - Bỏ qua các tiền tố biến như 'x = ', 'y = ', 'kết quả: ', 'đáp số: '
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
        t = re.sub(r'[\u00a0\u200b\s]+', '', t)
        t = re.sub(r'^(?:x|y|z|t|kếtquả|đápsố|ans|answer)\s*[:=]\s*', '', t, flags=re.IGNORECASE)
        t = t.replace(',', '.')
        return t.strip().lower()

    u = clean_sa(user_ans)
    c = clean_sa(correct_ans)

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
    def parse_frac(val: str) -> Optional[float]:
        m = re.match(r'^([\+\-]?\d+(?:\.\d+)?)\/([\+\-]?\d+(?:\.\d+)?)$', val)
        if m:
            denom = float(m.group(2))
            if denom != 0:
                return float(m.group(1)) / denom
        return None

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
