import os
import re
import json
import uuid
import tempfile
import shutil
import hashlib
import base64
import io
import datetime
from typing import List, Dict, Any
import random
import string

try:
    from PIL import Image
except ImportError:
    Image = None

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore

# ==========================================
# PHẦN 1: CẤU HÌNH & QUẢN LÝ DATABASE
# ==========================================

# Khởi tạo Firebase
try:
    # 1. Thử lấy chìa khóa từ Biến môi trường (Dành cho Koyeb)
    firebase_env = os.environ.get("FIREBASE_JSON")
    
    if firebase_env:
        # Chuyển chuỗi Text thành dạng Dictionary mà Firebase yêu cầu
        cred_dict = json.loads(firebase_env)
        cred = credentials.Certificate(cred_dict)
        print("Đang kết nối Firebase bằng Biến môi trường (Koyeb)...")
    else:
        # 2. Nếu không có biến môi trường, đọc từ file (Dành cho chạy trên máy tính)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cert_path = os.path.join(base_dir, "firebase-adminsdk.json")
        cred = credentials.Certificate(cert_path)
        print("Đang kết nối Firebase bằng tệp vật lý (Local)...")
        
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    # --- Phần khởi tạo Admin mặc định bên dưới giữ nguyên ---
    users = db.collection('users').where('username', '==', 'admin').get()
    admin_pwd_hash = hashlib.sha256('a@a@ankk'.encode()).hexdigest()
    if not users:
        db.collection('users').add({
            'username': 'admin',
            'password': admin_pwd_hash,
            'full_name': 'Quản trị viên (Admin)',
            'role': 'admin',
            'status': 'approved'
        })
    else:
        db.collection('users').document(users[0].id).update({
            'password': admin_pwd_hash
        })
        
except Exception as e:
    print(f"CẢNH BÁO: Không thể khởi tạo Firebase. Chi tiết: {e}")
    db = None

# ==========================================
# PHẦN 2: CẤU HÌNH FASTAPI & MIDDLEWARE
# ==========================================
app = FastAPI(
    title="Hệ thống Tạo Câu hỏi Trắc nghiệm AI - Chuẩn HocnhanhTN",
    description="Giao diện API hỗ trợ tải lên file Word và tự động bóc tách câu hỏi trắc nghiệm.",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SetApiKeyRequest(BaseModel):
    admin_token: str
    api_keys: List[str]

class SaveQuizRequest(BaseModel):
    quiz_id: str = None
    title: str
    data: list
    mode: str = "practice"
    time_limit: int = 0
    is_shuffle: bool = False
    creator_id: str = ""
    status: str = "published"

class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str

class LoginRequest(BaseModel):
    username: str
    password: str

class ApproveUserRequest(BaseModel):
    admin_token: str
    user_id: str

class ChangePasswordRequest(BaseModel):
    admin_token: str
    old_password: str
    new_password: str

class ResetPasswordRequest(BaseModel):
    admin_token: str
    user_id: str
    new_password: str

class TogglePublishRequest(BaseModel):
    teacher_token: str
    quiz_id: str
    status: str

class QuizActionRequest(BaseModel):
    teacher_token: str
    quiz_id: str
    action: str

class CheckQuizRequest(BaseModel):
    teacher_token: str
    quiz_data: list
    custom_prompt: str = ""

class SaveProgressRequest(BaseModel):
    student_token: str
    quiz_id: str
    progress_data: dict

class SubmitScoreRequest(BaseModel):
    quiz_id: str
    student_name: str
    score: int
    total_questions: int
    time_elapsed: int

class PingSessionRequest(BaseModel):
    quiz_id: str
    session_id: str
    student_name: str
    answers_count: int
    time_remaining: int
    completed: bool

# ==========================================
# PHẦN 3: LÕI THUẬT TOÁN & XỬ LÝ DỮ LIỆU
# ==========================================

def parse_omath(node):
    """Trình dịch thuật cục bộ Office MathML sang mã LaTeX chuẩn."""
    if node is None: return ""
    tag = node.tag.split('}')[-1] if '}' in node.tag else node.tag
    
    # Bộ từ điển chuyển đổi ký tự Unicode Toán/Hóa học sang LaTeX
    MATH_SYM_MAP = {
        'π': '\\pi ', 'α': '\\alpha ', 'β': '\\beta ', 'γ': '\\gamma ', 'Δ': '\\Delta ', 
        'δ': '\\delta ', 'θ': '\\theta ', 'λ': '\\lambda ', 'μ': '\\mu ', 'ρ': '\\rho ',
        'Σ': '\\Sigma ', 'Ω': '\\Omega ', 'ω': '\\omega ', '∞': '\\infty ', '→': '\\rightarrow ', 
        '⟶': '\\longrightarrow ', '⇌': '\\rightleftharpoons ',
        '⇒': '\\Rightarrow ', '⇔': '\\Leftrightarrow ', '≠': '\\neq ', '≈': '\\approx ',
        '≤': '\\leq ', '≥': '\\geq ', '±': '\\pm ', '×': '\\times ', '÷': '\\div ',
        '∫': '\\int ', '∑': '\\sum ', '°': '^\\circ ', '∈': '\\in ', '∉': '\\notin ',
        '⊂': '\\subset ', '∅': '\\emptyset ', '∩': '\\cap ', '∪': '\\cup '
    }
    
    if tag == 'f': # Phân số
        num = node.xpath('./*[local-name()="num"]')
        den = node.xpath('./*[local-name()="den"]')
        return f"\\frac{{{parse_omath(num[0]) if num else ''}}}{{{parse_omath(den[0]) if den else ''}}}"
    elif tag == 'sSup': # Mũ / Lũy thừa
        e = node.xpath('./*[local-name()="e"]')
        sup = node.xpath('./*[local-name()="sup"]')
        return f"{{{parse_omath(e[0]) if e else ''}}}^{{{parse_omath(sup[0]) if sup else ''}}}"
    elif tag == 'sSub': # Chỉ số dưới (Hóa học: H2O, CO2)
        e = node.xpath('./*[local-name()="e"]')
        sub = node.xpath('./*[local-name()="sub"]')
        return f"{{{parse_omath(e[0]) if e else ''}}}_{{{parse_omath(sub[0]) if sub else ''}}}"
    elif tag == 'sSubSup': # Tích hợp cả mũ và chỉ số dưới
        e = node.xpath('./*[local-name()="e"]')
        sub = node.xpath('./*[local-name()="sub"]')
        sup = node.xpath('./*[local-name()="sup"]')
        return f"{{{parse_omath(e[0]) if e else ''}}}_{{{parse_omath(sub[0]) if sub else ''}}}^{{{parse_omath(sup[0]) if sup else ''}}}"
    elif tag == 'rad': # Căn bậc 2, Căn bậc n
        deg = node.xpath('./*[local-name()="deg"]')
        e = node.xpath('./*[local-name()="e"]')
        if deg and deg[0].xpath('.//*[local-name()="t"]'):
            return f"\\sqrt[{parse_omath(deg[0])}]{{{parse_omath(e[0]) if e else ''}}}"
        return f"\\sqrt{{{parse_omath(e[0]) if e else ''}}}"
    elif tag == 'nary': # Tích phân, Tổng Sigma, Tích Pi
        naryPr = node.xpath('./*[local-name()="naryPr"]')
        chr_val = "\\int "
        if naryPr:
            chr_el = naryPr[0].xpath('./*[local-name()="chr"]')
            if chr_el:
                c = chr_el[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', '∫')
                if c == '∑': chr_val = "\\sum "
                elif c == '∏': chr_val = "\\prod "
        sub = node.xpath('./*[local-name()="sub"]')
        sup = node.xpath('./*[local-name()="sup"]')
        e = node.xpath('./*[local-name()="e"]')
        sub_str = f"_{{{parse_omath(sub[0])}}}" if sub and sub[0].xpath('.//*[local-name()="t"]') else ""
        sup_str = f"^{{{parse_omath(sup[0])}}}" if sup and sup[0].xpath('.//*[local-name()="t"]') else ""
        return f"{chr_val}{sub_str}{sup_str} {{{parse_omath(e[0]) if e else ''}}}"
    elif tag == 'limLow': # Giới hạn lim hoặc Mũi tên có chữ ở dưới
        e = node.xpath('./*[local-name()="e"]')
        lim = node.xpath('./*[local-name()="lim"]')
        e_text = parse_omath(e[0]) if e else ""
        lim_text = parse_omath(lim[0]) if lim else ""
        
        if 'rightarrow' in e_text or '→' in e_text:
            return f"\\xrightarrow[{lim_text}]{{}}"
        elif 'leftarrow' in e_text or '←' in e_text:
            return f"\\xleftarrow[{lim_text}]{{}}"
        elif 'rightleftharpoons' in e_text or '⇌' in e_text:
            return f"\\xrightleftharpoons[{lim_text}]{{}}"
        elif e_text.strip() == 'lim':
            return f"\\lim_{{{lim_text}}}"
        else:
            return f"\\underset{{{lim_text}}}{{{e_text}}}"
    elif tag == 'limUpp': # Mũi tên có chữ ở trên
        e = node.xpath('./*[local-name()="e"]')
        lim = node.xpath('./*[local-name()="lim"]')
        e_text = parse_omath(e[0]) if e else ""
        lim_text = parse_omath(lim[0]) if lim else ""
        
        if 'rightarrow' in e_text or '→' in e_text:
            return f"\\xrightarrow{{{lim_text}}}"
        elif 'leftarrow' in e_text or '←' in e_text:
            return f"\\xleftarrow{{{lim_text}}}"
        elif 'rightleftharpoons' in e_text or '⇌' in e_text:
            return f"\\xrightleftharpoons{{{lim_text}}}"
        else:
            return f"\\overset{{{lim_text}}}{{{e_text}}}"
    elif tag == 'groupChr': # Ký tự nhóm (Word hay dùng cho mũi tên phản ứng Hóa học)
        groupChrPr = node.xpath('./*[local-name()="groupChrPr"]')
        chr_val = ""
        pos = "bot"
        if groupChrPr:
            chr_el = groupChrPr[0].xpath('./*[local-name()="chr"]')
            if chr_el:
                chr_val = chr_el[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', '')
            pos_el = groupChrPr[0].xpath('./*[local-name()="pos"]')
            if pos_el:
                pos = pos_el[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', 'bot')
                
        e = node.xpath('./*[local-name()="e"]')
        e_text = parse_omath(e[0]) if e else ""
        
        if chr_val in ['→', '⟶', '\\rightarrow']:
            return f"\\xrightarrow{{{e_text}}}" if pos == 'bot' else f"\\xrightarrow[{e_text}]{{}}"
        elif chr_val in ['←', '⟵', '\\leftarrow']:
            return f"\\xleftarrow{{{e_text}}}" if pos == 'bot' else f"\\xleftarrow[{e_text}]{{}}"
        elif chr_val in ['⇌', '\\rightleftharpoons']:
            return f"\\xrightleftharpoons{{{e_text}}}" if pos == 'bot' else f"\\xrightleftharpoons[{e_text}]{{}}"
        elif chr_val == '︷':
            return f"\\overbrace{{{e_text}}}"
        elif chr_val == '︸':
            return f"\\underbrace{{{e_text}}}"
        else:
            return f"\\underset{{{chr_val}}}{{{e_text}}}" if pos == 'bot' else f"\\overset{{{chr_val}}}{{{e_text}}}"
    elif tag == 'undOvr': # Mũi tên có chữ cả trên lẫn dưới
        e = node.xpath('./*[local-name()="e"]')
        und = node.xpath('./*[local-name()="und"]')
        ovr = node.xpath('./*[local-name()="ovr"]')
        e_text = parse_omath(e[0]) if e else ""
        und_text = parse_omath(und[0]) if und else ""
        ovr_text = parse_omath(ovr[0]) if ovr else ""
        
        if 'rightarrow' in e_text or '→' in e_text:
            return f"\\xrightarrow[{und_text}]{{{ovr_text}}}"
        elif 'leftarrow' in e_text or '←' in e_text:
            return f"\\xleftarrow[{und_text}]{{{ovr_text}}}"
        elif 'rightleftharpoons' in e_text or '⇌' in e_text:
            return f"\\xrightleftharpoons[{und_text}]{{{ovr_text}}}"
        else:
            return f"\\munderover{{{e_text}}}{{{und_text}}}{{{ovr_text}}}"
    elif tag == 'm': # Ma trận / Cấu trúc bảng
        mr_nodes = node.xpath('./*[local-name()="mr"]')
        rows = []
        for mr in mr_nodes:
            e_nodes = mr.xpath('./*[local-name()="e"]')
            cols = [parse_omath(e_node) for e_node in e_nodes]
            rows.append(" & ".join(cols))
        joined_rows = " \\\\ ".join(rows)
        return f"\\begin{{matrix}} {joined_rows} \\end{{matrix}}"
    elif tag == 'd': # Dấu ngoặc (Trị tuyệt đối, ngoặc tròn, hệ phương trình)
        dPr = node.xpath('./*[local-name()="dPr"]')
        begChr, endChr = "(", ")"
        if dPr:
            beg_el = dPr[0].xpath('./*[local-name()="begChr"]')
            end_el = dPr[0].xpath('./*[local-name()="endChr"]')
            if beg_el: begChr = beg_el[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', '(')
            if end_el: endChr = end_el[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', ')')
        
        e = node.xpath('./*[local-name()="e"]')
        inner = "".join(parse_omath(c) for c in e)
        
        # Xử lý đặc biệt: Hệ phương trình (ngoặc nhọn 1 bên)
        if begChr == '{' and endChr == '':
            if '\\begin{matrix}' in inner:
                return inner.replace('\\begin{matrix}', '\\begin{cases}').replace('\\end{matrix}', '\\end{cases}')
        
        left_delim = "\\left\\{" if begChr == "{" else (f"\\left{begChr}" if begChr else "")
        right_delim = "\\right\\}" if endChr == "}" else ("\\right." if endChr == "" else f"\\right{endChr}")
        return f"{left_delim} {inner} {right_delim}"
    elif tag == 'acc': # Vector, Mũ (Đạo hàm, Hình học)
        accPr = node.xpath('./*[local-name()="accPr"]')
        chr_val = ""
        if accPr:
            chr_el = accPr[0].xpath('./*[local-name()="chr"]')
            if chr_el:
                c = chr_el[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', '')
                if c in ['⃗', '→']: chr_val = "\\vec"
                elif c == '̂': chr_val = "\\hat"
                elif c == '̅': chr_val = "\\overline"
        e = node.xpath('./*[local-name()="e"]')
        return f"{chr_val}{{{parse_omath(e[0]) if e else ''}}}" if chr_val else (parse_omath(e[0]) if e else "")
    elif tag == 't': # Text và Ký tự đặc biệt
        text = node.text or ""
        for k, v in MATH_SYM_MAP.items():
            text = text.replace(k, v)
        return text
    
    res = ""
    for child in node:
        res += parse_omath(child)
    return res

def replace_placeholders(data, mapping):
    if isinstance(data, dict):
        return {k: replace_placeholders(v, mapping) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_placeholders(v, mapping) for v in data]
    elif isinstance(data, str):
        for ph, img_tag in mapping.items():
            ph_clean = ph.replace('[', '').replace(']', '').strip()
            # Xử lý an toàn mọi trường hợp AI trả về sai [IMG], bị dính dấu \ hoặc viết thường
            data = re.sub(r'\\?\[\s*' + re.escape(ph_clean) + r'\s*\\?\]', lambda m: img_tag, data, flags=re.IGNORECASE)
            data = re.sub(r'\b' + re.escape(ph_clean) + r'\b', lambda m: img_tag, data, flags=re.IGNORECASE)
        return data
    return data

def recursive_unescape(data):
    if isinstance(data, dict):
        return {k: recursive_unescape(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [recursive_unescape(v) for v in data]
    elif isinstance(data, str):
        return data.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return data

def fix_json_latex_escapes(json_str: str) -> str:
    """Sửa lỗi LLM trả về các ký tự LaTeX (như \frac, \rightarrow) bị parser JSON hiểu nhầm thành ký tự điều khiển (Escape character)"""
    # Thay thế các dấu \ đơn độc thành \\, ngoại trừ các trường hợp nó đang escape " hoặc \ hoặc / hợp lệ của JSON
    return re.sub(r'(?<!\\)\\(?!["\\/])', r'\\\\', json_str)

def get_auto_numbering_prefix(para, doc, counters: dict) -> str:
    """Khôi phục lại text (Câu X / A, B) khi giáo viên dùng List Tự động trong Word"""
    pPr = para._p.pPr
    if pPr is None or pPr.numPr is None or pPr.numPr.numId is None:
        return ""
        
    numId = pPr.numPr.numId.val
    ilvl = pPr.numPr.ilvl.val if pPr.numPr.ilvl is not None else 0
    numFmt = "decimal"
    
    try:
        if doc.part.numbering_part is not None:
            numbering_part = doc.part.numbering_part
            num = numbering_part.element.num_having_numId(numId)
            if num is not None and num.abstractNumId is not None:
                abstractNum = numbering_part.element.abstractNum_having_abstractNumId(num.abstractNumId.val)
                for lvl in abstractNum.xpath('./*[local-name()="lvl"]'):
                    if lvl.get(qn('w:ilvl')) == str(ilvl):
                        numFmt_el = lvl.xpath('./*[local-name()="numFmt"]')
                        if numFmt_el:
                            numFmt = numFmt_el[0].get(qn('w:val'))
                        break
    except Exception:
        pass
        
    if numFmt in ["upperLetter", "lowerLetter"]:
        counters['opt'] += 1
        return f"{chr(ord('A') + (counters['opt'] - 1) % 26)}. "
    else:
        counters['q'] += 1
        counters['opt'] = 0
        return f"Câu {counters['q']}: "

def split_option_and_leading_text(text: str) -> int:
    """Trả về độ dài của phần đáp án (opt_part). Phần còn lại là leading_text."""
    lines = text.split('\n')
    opt_lines = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped:
            is_keyword = bool(re.match(r'^\s*(PHẦN|PART|CHƯƠNG|BÀI TẬP|TEST|PRACTICE|MỨC ĐỘ|DẠNG|I{1,3}\.|IV\.|V\.|VI{0,3}\.)\b', stripped, re.IGNORECASE))
            is_context_hint = bool(re.match(r'^\s*(Đọc đoạn|Đọc văn bản|Read the|Based on|Dựa vào|Cho đoạn|Cho bảng|Mark the|Choose the|Indicate the|Find the|Identify the|Complete the|Select the)\b', stripped, re.IGNORECASE))
            is_new_block = (i > 0 and not lines[i-1].strip() and len(stripped) > 10)
            if is_keyword or is_context_hint or is_new_block:
                break
        opt_lines.append(line)
        
    opt_str = '\n'.join(opt_lines)
    return min(len(opt_str), len(text))

def evaluate_correct_answer(options: List[Dict], full_text: str, format_weights: List[int], char_html: List[str] = None) -> str:
    """
    So sánh trọng số giữa 4 đáp án (A,B,C,D) để lọc ra đáp án chính xác nhất dựa trên định dạng.
    """
    def get_html(start, end):
        if not char_html: return ""
        joined = "".join(char_html[start:end])
        for tag in ['b', 'i', 'u', 'sup', 'sub']:
            joined = joined.replace(f"</{tag}><{tag}>", "")
        return joined.strip()

    # 1. Kiểm tra nếu có đáp án nào được đánh dấu * (Ưu tiên tuyệt đối)
    for opt in options:
        if opt.get('is_asterisk'):
            if char_html:
                return f"{opt['char']}. {get_html(opt['content_start'], opt['end_idx'])}"
            else:
                opt_len = split_option_and_leading_text(opt['text_raw'])
                return f"{opt['char']}. {opt['text_raw'][:opt_len].strip()}"
            
    # 2. Nếu không có dấu *, tiến hành so sánh theo màu sắc/in đậm
    best_score = -1
    best_option_text = None
    
    for opt in options:
        score = 0
        start_idx = opt['start_idx']
        content_start = opt['marker_end']
        content_end = opt['end_idx']
        
        # 1. Đo lường Trọng số tại điểm neo (Ví dụ ngay tại chữ 'A', 'B')
        marker_weight = format_weights[start_idx] if start_idx < len(format_weights) else 0
        if marker_weight == 3: score += 1000    # Đỏ/Highlight
        elif marker_weight == 2: score += 500   # Gạch chân
        elif marker_weight == 1: score += 100   # In đậm
        
        # 2. Đo lường Trọng số trải dài trên toàn bộ nội dung đáp án
        if content_start < content_end:
            content_weights = format_weights[content_start:content_end]
            # Đảm bảo không vượt quá index của full_text
            alnum_count = sum(1 for i in range(content_start, content_end) if i < len(full_text) and full_text[i].isalnum())
            
            if alnum_count > 0:
                formatted_chars = sum(1 for i, w in enumerate(content_weights) if w > 0 and (content_start+i) < len(full_text) and full_text[content_start+i].isalnum())
                max_w = max(content_weights) if content_weights else 0
                ratio = formatted_chars / alnum_count
                
                # Phân rã logic: Nhấn mạnh phần lớn câu vs. Chỉ nhấn mạnh một từ
                if ratio > 0.4:
                    if max_w == 3: score += 800
                    elif max_w == 2: score += 400
                    elif max_w == 1: score += 80
                elif formatted_chars >= 2:
                    if max_w == 3: score += 300
                    elif max_w == 2: score += 150
                    elif max_w == 1: score += 20
                    
        # Cập nhật đáp án có mức rank cao nhất
        if score > best_score:
            best_score = score
            if char_html:
                best_option_text = f"{opt['char']}. {get_html(content_start, content_end)}"
            else:
                opt_len = split_option_and_leading_text(opt['text_raw'])
                best_option_text = f"{opt['char']}. {opt['text_raw'][:opt_len].strip()}"
            
    if best_score <= 0:
        return None
        
    return best_option_text

def extract_formatting_from_docx(file_path: str) -> List[Dict[str, Any]]:
    """Thuật toán phân tách Câu hỏi trắc nghiệm siêu tốc và thông minh."""
    doc = Document(file_path)
    full_text = ""
    format_weights = []
    char_html = []
    image_mapping = {}
    img_counter = 0
    
    counters = {'q': 0, 'opt': 0}
    
    # BƯỚC 1: Quét tài liệu, ánh xạ văn bản và trọng số định dạng
    for p_element in doc.element.xpath('.//*[local-name()="p"]'):
        para = Paragraph(p_element, doc._body)
        raw_text = "".join(node.text for node in para._element.iter() if node.tag.endswith('}t') and node.text)
        has_text = bool(raw_text.strip())
        has_media = bool(para._element.xpath('.//*[local-name()="drawing" or local-name()="pict" or local-name()="object" or local-name()="oMath"]'))
        if not has_text and not has_media:
            full_text += "\n"
            format_weights.append(0)
            char_html.append("\n")
            continue
            
        prefix = get_auto_numbering_prefix(para, doc, counters)
        if prefix:
            para_text_strip = raw_text.strip()
            is_numbering_text = re.match(r'^\s*(Câu|Bài|Question|Q|\d+[\.\:\)]|\*?\s*[A-F][\.\:\)])', para_text_strip, re.IGNORECASE)
            is_group_title = re.match(r'^\s*(PHẦN|PART|CHƯƠNG|BÀI TẬP|TEST|PRACTICE|MỨC ĐỘ|DẠNG|I{1,3}\.|IV\.|V\.|VI{0,3}\.)\b', para_text_strip, re.IGNORECASE)
            
            if not is_numbering_text and not is_group_title:
                full_text += prefix
                format_weights.extend([0] * len(prefix))
                char_html.extend(list(prefix))
                
        for node in para._element.xpath('.//*[local-name()="t" or local-name()="drawing" or local-name()="pict" or local-name()="object" or local-name()="oMath"]'):
            if node.xpath('ancestor::*[local-name()="oMath"]') and not node.tag.endswith('}oMath'):
                continue
            if node.xpath('ancestor::*[local-name()="Fallback"]') or node.xpath('ancestor::*[local-name()="fallback"]'):
                continue
                
            if node.tag.endswith('}oMath'):
                math_latex = parse_omath(node)
                if math_latex:
                    encoded_math = math_latex.replace("<", "&lt;").replace(">", "&gt;")
                    math_tag = f" \\({encoded_math}\\) "
                    full_text += math_tag
                    format_weights.extend([0] * len(math_tag))
                    for char in math_tag:
                        char_html.append(f"<i>{char}</i>")
            elif node.tag.endswith('}drawing') or node.tag.endswith('}pict') or node.tag.endswith('}object'):
                img_nodes = node.xpath('.//*[local-name()="blip"] | .//*[local-name()="imagedata"] | .//*[local-name()="OLEObject"] | .//*[local-name()="svgBlip"]')
                if not img_nodes:
                    continue
                extent = node.xpath('.//*[local-name()="extent"]')
                img_style = "max-width: 100%; height: auto;"
                if extent:
                    try:
                        cx = int(extent[0].get('cx', 0))
                        if cx > 0:
                            px_width = int(cx / 9525)  # Đổi từ chuẩn EMU của Word sang Pixels (96 DPI)
                            img_style = f"width: {px_width}px; max-width: 100%; height: auto; vertical-align: middle; margin: 4px;"
                    except:
                        pass
                        
                for img_node in img_nodes:
                    rId = img_node.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    if not rId:
                        rId = img_node.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                    if not rId:
                        rId = img_node.get(qn('r:embed'))
                    if not rId:
                        rId = img_node.get(qn('r:id'))
                    if not rId:
                        for k, v in img_node.attrib.items():
                            if ('embed' in k.lower() or 'id' in k.lower()) and isinstance(v, str) and v.startswith('rId'):
                                rId = v
                                break
                    
                    if rId and rId in doc.part.related_parts:
                        image_part = doc.part.related_parts[rId]
                        b64_encoded = base64.b64encode(image_part.blob).decode('utf-8')
                        mime_type = image_part.content_type
                        img_counter += 1
                        placeholder = f"[IMG_{img_counter}]"
                        
                        if mime_type in ['image/x-emf', 'image/x-wmf']:
                            converted = False
                            if Image is not None:
                                try:
                                    img = Image.open(io.BytesIO(image_part.blob))
                                    out_io = io.BytesIO()
                                    img.save(out_io, format='PNG')
                                    b64_new = base64.b64encode(out_io.getvalue()).decode('utf-8')
                                    image_mapping[placeholder] = f"<br><img src='data:image/png;base64,{b64_new}' class='quiz-image' /><br>"
                                    converted = True
                                except Exception:
                                    pass
                            if not converted:
                                image_mapping[placeholder] = f"<br><div style='padding:10px; background:#fee2e2; color:#991b1b; border-radius:8px; font-size:0.9rem;'>⚠️ Hệ thống phát hiện ảnh định dạng cũ (WMF/EMF). Trình duyệt web không thể hiển thị loại ảnh này. Vui lòng mở Word, chụp màn hình ảnh này và dán lại dưới dạng JPG/PNG.</div><br>"
                        else:
                            image_mapping[placeholder] = f"<br><img src='data:{mime_type};base64,{b64_encoded}' class='quiz-image' style='{img_style}' /><br>"
                        
                        full_text += f" {placeholder} "
                        format_weights.extend([0] * len(f" {placeholder} "))
                        char_html.extend(list(f" {placeholder} "))
            elif node.tag.endswith('}t'):
                run_text = node.text
                if not run_text: continue
                
                r = node.getparent()
                rPr_list = r.xpath('./*[local-name()="rPr"]') if r is not None and r.tag.endswith('}r') else []
                is_bold = is_italic = is_underline = is_highlighted = is_red_text = is_subscript = is_superscript = False
                
                if rPr_list:
                    rPr = rPr_list[0]
                    if rPr.xpath('./*[local-name()="b"]'): is_bold = True
                    if rPr.xpath('./*[local-name()="i"]'): is_italic = True
                    # Nhận diện chữ gạch chân
                    if rPr.xpath('./*[local-name()="u"]'): is_underline = True
                    
                    highlight = rPr.xpath('./*[local-name()="highlight"]')
                    if highlight and highlight[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val') != 'none': is_highlighted = True
                        
                    color = rPr.xpath('./*[local-name()="color"]')
                    if color and color[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val') in ['FF0000', 'C00000', 'ED1C24', 'red', 'RED']:
                        is_red_text = True
                            
                    vertAlign = rPr.xpath('./*[local-name()="vertAlign"]')
                    if vertAlign:
                        val = vertAlign[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                        if val == 'subscript': is_subscript = True
                        if val == 'superscript': is_superscript = True
                
                full_text += run_text
                weight = 3 if (is_red_text or is_highlighted) else (2 if is_underline else (1 if is_bold else 0))
                format_weights.extend([weight] * len(run_text))
                
                for char in run_text:
                    encoded_char = char.replace("<", "&lt;").replace(">", "&gt;")
                    if is_subscript: encoded_char = f"<sub>{encoded_char}</sub>"
                    if is_superscript: encoded_char = f"<sup>{encoded_char}</sup>"
                    if is_italic: encoded_char = f"<i>{encoded_char}</i>"
                    if is_underline and not is_red_text: encoded_char = f"<u>{encoded_char}</u>"
                    if is_bold and not is_red_text: encoded_char = f"<b>{encoded_char}</b>"
                    char_html.append(encoded_char)
            
        full_text += "\n"
        format_weights.append(0)
        char_html.append("\n")

    def get_html(start, end):
        joined = "".join(char_html[start:end])
        for tag in ['b', 'i', 'u', 'sup', 'sub']:
            joined = joined.replace(f"</{tag}><{tag}>", "")
        return joined.strip()

    # BƯỚC 2: Phân tách bằng State Machine (Máy trạng thái) kết hợp Regex siêu chuẩn
    q_regex = r'(?:^|\n)\s*(?:Câu|Bài|Question|Q)\s*\d+\s*[\.\:\-\)]|(?:^|\n)\s*\d+\s*[\.\:\)]'
    opt_regex = r'(?:^|\s+|(?<=[\.\:\-]))(\*?\s*[A-F])[\.\:\)]'
    token_pattern = re.compile(f'({q_regex})|({opt_regex})', re.IGNORECASE)
    
    matches = list(token_pattern.finditer(full_text))
    if not matches: return []

    extracted_data = []
    current_q_start = 0
    current_q_end = 0
    options = []
    last_idx = 0
    state = "OUTSIDE" # Trạng thái xử lý: OUTSIDE, IN_QUESTION, IN_OPTION
    shared_context = "" # Biến lưu tiêu đề nhóm chung (để cấp cho các câu hỏi trống)
    
    for m in matches:
        is_question = m.group(1) is not None
        is_option = m.group(2) is not None
        
        match_start = m.start()
        match_end = m.end()
        text_between = full_text[last_idx:match_start]
        
        if is_question:
            if state == "IN_OPTION" and options:
                opt_len = split_option_and_leading_text(text_between)
                options[-1]['text_raw'] += text_between[:opt_len]
                options[-1]['end_idx'] = last_idx + opt_len
                lead_part_raw = text_between[opt_len:]
                
                correct_ans = evaluate_correct_answer(options, full_text, format_weights, char_html)
                    
                extracted_data.append({
                    "group_title": shared_context,
                    "question": get_html(current_q_start, current_q_end),
                    "options": [f"{opt['char']}. {get_html(opt['content_start'], opt['end_idx'])}" for opt in options],
                    "correct_answer": correct_ans
                })
                
                if lead_part_raw.strip():
                    shared_context = get_html(last_idx + opt_len, match_start)
                current_q_start = match_end
                current_q_end = match_end
            elif state == "OUTSIDE":
                opt_len = split_option_and_leading_text(text_between)
                lead_part_raw = text_between[opt_len:]
                if lead_part_raw.strip():
                    shared_context = get_html(last_idx + opt_len, match_start)
                current_q_start = match_end
                current_q_end = match_end
            else:
                current_q_start = match_end
                current_q_end = match_end
                
            options = []
            state = "IN_QUESTION"
            
        elif is_option:
            char_raw = m.group(3).upper() if m.group(3) else 'A'
            is_asterisk = '*' in char_raw
            char = char_raw.replace('*', '').strip()
            
            if state == "IN_QUESTION":
                current_q_end = match_start
            elif state == "IN_OPTION" and options:
                options[-1]['text_raw'] += text_between
                options[-1]['end_idx'] = match_start
                
            state = "IN_OPTION"
            options.append({
                'char': char,
                'start_idx': m.start(3) if m.start(3) != -1 else match_start,
                'content_start': match_end,
                'text_raw': "",
                'marker_end': match_end,
                'is_asterisk': is_asterisk,
                'end_idx': match_end
            })
            
        last_idx = match_end
        
    if state == "IN_OPTION" and options:
        text_between = full_text[last_idx:]
        opt_len = split_option_and_leading_text(text_between)
        options[-1]['text_raw'] += text_between[:opt_len]
        options[-1]['end_idx'] = last_idx + opt_len
        
        correct_ans = evaluate_correct_answer(options, full_text, format_weights, char_html)
            
        extracted_data.append({
            "group_title": shared_context,
            "question": get_html(current_q_start, current_q_end),
            "options": [f"{opt['char']}. {get_html(opt['content_start'], opt['end_idx'])}" for opt in options],
            "correct_answer": correct_ans
        })

    if image_mapping:
        extracted_data = replace_placeholders(extracted_data, image_mapping)

    return extracted_data

def parse_docx_to_marked_text(file_path: str) -> str:
    """Đánh dấu thẻ <MARK> cho các từ in đậm/đỏ để gửi lên AI, đồng thời giữ định dạng HTML"""
    doc = Document(file_path)
    full_text = []
    image_mapping = {}
    img_counter = 0
    counters = {'q': 0, 'opt': 0}
    
    for p_element in doc.element.xpath('.//*[local-name()="p"]'):
        para = Paragraph(p_element, doc._body)
        raw_text = "".join(node.text for node in para._element.iter() if node.tag.endswith('}t') and node.text)
        has_text = bool(raw_text.strip())
        has_media = bool(para._element.xpath('.//*[local-name()="drawing" or local-name()="pict" or local-name()="object" or local-name()="oMath"]'))
        if not has_text and not has_media:
            full_text.append("\n")
            continue
        
        para_text = ""
        prefix = get_auto_numbering_prefix(para, doc, counters)
        if prefix:
            para_text_strip = raw_text.strip()
            is_numbering_text = re.match(r'^\s*(Câu|Bài|Question|Q|\d+[\.\:\)]|\*?\s*[A-F][\.\:\)])', para_text_strip, re.IGNORECASE)
            is_group_title = re.match(r'^\s*(PHẦN|PART|CHƯƠNG|BÀI TẬP|TEST|PRACTICE|MỨC ĐỘ|DẠNG|I{1,3}\.|IV\.|V\.|VI{0,3}\.)\b', para_text_strip, re.IGNORECASE)
            if not is_numbering_text and not is_group_title:
                para_text += prefix
                
        for node in para._element.xpath('.//*[local-name()="t" or local-name()="drawing" or local-name()="pict" or local-name()="object" or local-name()="oMath"]'):
            if node.xpath('ancestor::*[local-name()="oMath"]') and not node.tag.endswith('}oMath'):
                continue
            if node.xpath('ancestor::*[local-name()="Fallback"]') or node.xpath('ancestor::*[local-name()="fallback"]'):
                continue

            if node.tag.endswith('}oMath'):
                math_latex = parse_omath(node)
                if math_latex:
                    encoded_math = math_latex.replace("<", "&lt;").replace(">", "&gt;")
                    para_text += f" \\({encoded_math}\\) "
            elif node.tag.endswith('}drawing') or node.tag.endswith('}pict') or node.tag.endswith('}object'):
                img_nodes = node.xpath('.//*[local-name()="blip"] | .//*[local-name()="imagedata"] | .//*[local-name()="OLEObject"] | .//*[local-name()="svgBlip"]')
                if not img_nodes:
                    continue
                extent = node.xpath('.//*[local-name()="extent"]')
                img_style = "max-width: 100%; height: auto;"
                if extent:
                    try:
                        cx = int(extent[0].get('cx', 0))
                        if cx > 0:
                            px_width = int(cx / 9525)
                            img_style = f"width: {px_width}px; max-width: 100%; height: auto; vertical-align: middle; margin: 4px;"
                    except:
                        pass
                        
                for img_node in img_nodes:
                    rId = img_node.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    if not rId:
                        rId = img_node.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                    if not rId:
                        rId = img_node.get(qn('r:embed'))
                    if not rId:
                        rId = img_node.get(qn('r:id'))
                    if not rId:
                        for k, v in img_node.attrib.items():
                            if ('embed' in k.lower() or 'id' in k.lower()) and isinstance(v, str) and v.startswith('rId'):
                                rId = v
                                break
                    
                    if rId and rId in doc.part.related_parts:
                        image_part = doc.part.related_parts[rId]
                        b64_encoded = base64.b64encode(image_part.blob).decode('utf-8')
                        mime_type = image_part.content_type
                        img_counter += 1
                        placeholder = f"[IMG_{img_counter}]"
                        
                        if mime_type in ['image/x-emf', 'image/x-wmf']:
                            converted = False
                            if Image is not None:
                                try:
                                    img = Image.open(io.BytesIO(image_part.blob))
                                    out_io = io.BytesIO()
                                    img.save(out_io, format='PNG')
                                    b64_new = base64.b64encode(out_io.getvalue()).decode('utf-8')
                                    image_mapping[placeholder] = f"<img src='data:image/png;base64,{b64_new}' class='quiz-image' style='{img_style}' />"
                                    converted = True
                                except Exception:
                                    pass
                            if not converted:
                                image_mapping[placeholder] = f"<div style='padding:10px; background:#fee2e2; color:#991b1b; border-radius:8px; font-size:0.9rem; margin: 10px 0;'>⚠️ Ảnh định dạng cũ (WMF/EMF) không được hỗ trợ. Vui lòng dán lại dưới dạng JPG/PNG.</div>"
                        else:
                            image_mapping[placeholder] = f"<img src='data:{mime_type};base64,{b64_encoded}' class='quiz-image' style='{img_style}' />"
                        para_text += f" {placeholder} "
            elif node.tag.endswith('}t'):
                run_text = node.text
                if not run_text: continue
                
                r = node.getparent()
                rPr_list = r.xpath('./*[local-name()="rPr"]') if r is not None and r.tag.endswith('}r') else []
                is_bold = is_italic = is_underline = is_highlighted = is_red_text = is_subscript = is_superscript = False
                
                if rPr_list:
                    rPr = rPr_list[0]
                    if rPr.xpath('./*[local-name()="b"]'): is_bold = True
                    if rPr.xpath('./*[local-name()="i"]'): is_italic = True
                    # Nhận diện chữ gạch chân
                    if rPr.xpath('./*[local-name()="u"]'): is_underline = True
                    
                    highlight = rPr.xpath('./*[local-name()="highlight"]')
                    if highlight and highlight[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val') != 'none': is_highlighted = True
                        
                    color = rPr.xpath('./*[local-name()="color"]')
                    if color and color[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val') in ['FF0000', 'C00000', 'ED1C24', 'red', 'RED']:
                        is_red_text = True
                            
                    vertAlign = rPr.xpath('./*[local-name()="vertAlign"]')
                    if vertAlign:
                        val = vertAlign[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                        if val == 'subscript': is_subscript = True
                        if val == 'superscript': is_superscript = True
                
                formatted_text = run_text.replace("<", "&lt;").replace(">", "&gt;")
                if is_subscript: formatted_text = f"<sub>{formatted_text}</sub>"
                if is_superscript: formatted_text = f"<sup>{formatted_text}</sup>"
                if is_italic: formatted_text = f"<i>{formatted_text}</i>"
                if is_underline and not is_red_text: formatted_text = f"<u>{formatted_text}</u>"
                if is_bold and not is_red_text: formatted_text = f"<b>{formatted_text}</b>"
                
                if is_red_text or is_highlighted or (is_underline and is_bold): 
                    para_text += f"<MARK>{formatted_text}</MARK>"
                else:
                    para_text += formatted_text
                    
        full_text.append(para_text)
        
    raw_output = "\n".join(full_text)
    for tag in ['b', 'i', 'u', 'sup', 'sub']:
        raw_output = raw_output.replace(f"</{tag}> <{tag}>", " ").replace(f"</{tag}><{tag}>", "")
        
    # Đảm bảo có khoảng trắng xuống dòng trước các đáp án A, B, C, D (Sửa lỗi dính liền cực an toàn)
    raw_output = re.sub(r'(?<!\n)(\s+)(\*?[A-D][\.\:\)]\s+)', r'\n\2', raw_output)
    return raw_output, image_mapping

def call_gemini_with_fallback(prompt: str, api_keys: List[str]):
    """Gọi Gemini AI với cơ chế chuyển giao giữa nhiều Key và nhiều Model"""
    if not api_keys:
        raise Exception("Hệ thống chưa được cấu hình API Key.")
        
    models_to_try = [
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-1.5-flash',
        'gemini-3.1-flash-lite',
        'gemini-3-flash',
        'gemini-2.5-flash-lite'
    ]
    last_error = None
    
    for key in api_keys:
        key = key.strip()
        if not key: continue
        genai.configure(api_key=key)
        
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1
                    )
                )
                return response
            except Exception as e:
                error_str = str(e).lower()
                if "404" in error_str or "not found" in error_str:
                    last_error = e
                    continue # Đổi model, giữ nguyên key
                elif "429" in error_str or "quota" in error_str or "503" in error_str or "overloaded" in error_str or "key invalid" in error_str:
                    last_error = e
                    break # Bỏ qua model còn lại, đổi sang Key khác
                else:
                    raise e
                    
    raise Exception(f"Tất cả các Key và Model đều thất bại. Lỗi cuối: {str(last_error)}")

def generate_mcq_with_gemini(marked_text: str, api_keys: List[str]) -> List[Dict[str, Any]]:
    """Dùng Gemini AI để bóc tách câu hỏi dựa trên văn bản đã gắn thẻ <MARK>"""
    prompt = f"""
    Bạn là một chuyên gia giáo dục. Nhiệm vụ của bạn là trích xuất câu hỏi từ văn bản dưới đây.
    1. Trích xuất câu hỏi và 4 đáp án (A, B, C, D). Tuyệt đối LOẠI BỎ chữ "Câu X:", "Bài X:" hoặc số thứ tự ở đầu câu hỏi.
    2. CHÚ Ý QUAN TRỌNG: Hãy tinh ý tách các đáp án A, B, C, D ra riêng biệt nếu chúng bị dính liền trên cùng một dòng.
    3. Đáp án đúng là đáp án chứa nội dung nằm trong thẻ <MARK> HOẶC có dấu * ở trước chữ cái đáp án (ví dụ *A, *B). Loại bỏ thẻ <MARK> và dấu * ra khỏi kết quả cuối cùng.
    4. GIỮ NGUYÊN TOÀN BỘ các thẻ định dạng HTML (như <b>, <i>, <u>, <sub>, <sup>). KHÔNG tự ý chuyển sang Markdown. TUYỆT ĐỐI KHÔNG ĐƯỢC XÓA BỎ các thẻ [IMG_X] (ví dụ [IMG_1], [IMG_2]). PHẢI GIỮ NGUYÊN CHÚNG TRONG NỘI DUNG.
    5. Các công thức Toán/Lý/Hóa đã được bọc sẵn trong thẻ \( và \). Dữ liệu này ĐÃ ĐƯỢC ESCAPE SẴN DẤU BACKSLASH (ví dụ \frac, \sqrt, \rightarrow). BẠN PHẢI GIỮ NGUYÊN ĐỊNH DẠNG NÀY KHI TRẢ VỀ JSON. Bắt buộc phải có 2 dấu backslash (\\\\) trong chuỗi JSON.
    6. Định dạng trả về bắt buộc là JSON array RẤT NGHIÊM NGẶT.
    Ví dụ: [{{"group_title": "Đọc đoạn văn...", "question": "Hình sau [IMG_1] là gì? Tính \\\\(x^2\\\\)", "options": ["A. <i>Có</i>", "B. Không", "C. 1", "D. 2"], "correct_answer": "A. <i>Có</i>"}}]
    
    Văn bản:
    {marked_text}
    """
    response = call_gemini_with_fallback(prompt, api_keys)
            
    match = re.search(r'\[\s*\{.*\}\s*\]', response.text, re.DOTALL)
    json_text = match.group(0) if match else response.text
    
    try:
        json_text = fix_json_latex_escapes(json_text)
        return json.loads(json_text, strict=False)
    except json.JSONDecodeError as e:
        raise Exception(f"AI trả về JSON không hợp lệ (thường do công thức toán học bị lỗi định dạng LaTeX). Hãy thử lại. Chi tiết: {str(e)}")


# ==========================================
# PHẦN 4: GIAO DIỆN & API ENDPOINTS
# ==========================================

@app.get("/")
async def root():
    return {"status": "success", "message": "Backend API is running!"}

@app.get("/api/keep-alive", summary="API giữ máy chủ luôn thức")
async def keep_alive():
    return {"status": "ok", "message": "Hệ thống đang thức và sẵn sàng!"}

@app.post("/api/auth/register", summary="Đăng ký tài khoản mới")
async def register(req: RegisterRequest):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    existing = db.collection('users').where('username', '==', req.username).get()
    if existing: raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")
    
    db.collection('users').add({
        'username': req.username,
        'password': hashlib.sha256(req.password.encode()).hexdigest(),
        'full_name': req.full_name,
        'role': req.role,
        'status': 'pending'
    })
    return {"status": "success"}

@app.post("/api/auth/login", summary="Đăng nhập")
async def login(req: LoginRequest):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    users = db.collection('users').where('username', '==', req.username).get()
    if not users: raise HTTPException(status_code=400, detail="Sai tài khoản hoặc mật khẩu")
    
    user_doc = users[0]
    user_data = user_doc.to_dict()
    
    if user_data['password'] != hashlib.sha256(req.password.encode()).hexdigest():
        raise HTTPException(status_code=400, detail="Sai tài khoản hoặc mật khẩu")
        
    if user_data['status'] != 'approved':
        raise HTTPException(status_code=403, detail="Tài khoản đang chờ Quản trị viên duyệt.")
        
    return {"status": "success", "token": user_doc.id, "role": user_data['role'], "full_name": user_data['full_name']}

@app.get("/api/admin/users", summary="Lấy danh sách user (Admin)")
async def get_all_users(admin_token: str):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    admin_doc = db.collection('users').document(admin_token).get()
    if not admin_doc.exists or admin_doc.to_dict().get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
        
    users = db.collection('users').get()
    res = []
    for u in users:
        d = u.to_dict()
        res.append({
            'id': u.id,
            'username': d.get('username'),
            'full_name': d.get('full_name'),
            'role': d.get('role'),
            'status': d.get('status')
        })
    return {"status": "success", "data": res}

@app.post("/api/admin/approve", summary="Duyệt user (Admin)")
async def approve_user(req: ApproveUserRequest):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    admin_doc = db.collection('users').document(req.admin_token).get()
    if not admin_doc.exists or admin_doc.to_dict().get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Không có quyền")
        
    db.collection('users').document(req.user_id).update({'status': 'approved'})
    return {"status": "success"}

@app.post("/api/admin/delete", summary="Xóa user (Admin)")
async def delete_user(req: ApproveUserRequest):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    admin_doc = db.collection('users').document(req.admin_token).get()
    if not admin_doc.exists or admin_doc.to_dict().get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Không có quyền")
        
    db.collection('users').document(req.user_id).delete()
    return {"status": "success"}

@app.post("/api/admin/change_password", summary="Đổi mật khẩu (Admin)")
async def change_admin_password(req: ChangePasswordRequest):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    admin_doc_ref = db.collection('users').document(req.admin_token)
    admin_doc = admin_doc_ref.get()
    
    if not admin_doc.exists or admin_doc.to_dict().get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
        
    admin_data = admin_doc.to_dict()
    if admin_data['password'] != hashlib.sha256(req.old_password.encode()).hexdigest():
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác")
        
    admin_doc_ref.update({'password': hashlib.sha256(req.new_password.encode()).hexdigest()})
    return {"status": "success"}

@app.post("/api/admin/reset_password", summary="Khôi phục mật khẩu user (Admin)")
async def reset_user_password(req: ResetPasswordRequest):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    admin_doc = db.collection('users').document(req.admin_token).get()
    if not admin_doc.exists or admin_doc.to_dict().get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Không có quyền")
        
    db.collection('users').document(req.user_id).update({
        'password': hashlib.sha256(req.new_password.encode()).hexdigest()
    })
    return {"status": "success"}

@app.post("/api/admin/set_api_key", summary="Cài đặt API Key chung (Admin)")
async def set_api_key(req: SetApiKeyRequest):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    admin_doc = db.collection('users').document(req.admin_token).get()
    if not admin_doc.exists or admin_doc.to_dict().get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Không có quyền")
        
    db.collection('settings').document('gemini').set({'api_keys': req.api_keys})
    return {"status": "success"}

@app.get("/api/admin/get_api_key", summary="Lấy API Key chung (Admin)")
async def get_api_key(admin_token: str):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    admin_doc = db.collection('users').document(admin_token).get()
    if not admin_doc.exists or admin_doc.to_dict().get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Không có quyền")
        
    settings_doc = db.collection('settings').document('gemini').get()
    api_keys = settings_doc.to_dict().get('api_keys', []) if settings_doc.exists else []
    return {"status": "success", "api_keys": api_keys}

@app.post("/api/save_quiz", summary="Lưu bài thi và lấy link")
async def save_quiz(request: SaveQuizRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
    if request.quiz_id:
        quiz_id = request.quiz_id
        doc_ref = db.collection('quizzes').document(quiz_id)
        doc = doc_ref.get()
        if doc.exists and doc.to_dict().get('creator_id') != request.creator_id:
            raise HTTPException(status_code=403, detail="Không có quyền cập nhật đề này")
    else:
        # Tạo mã ngẫu nhiên dạng AAA-111 (VD: Toán -> MTH-123)
        while True:
            part1 = ''.join(random.choices(string.ascii_uppercase, k=3))
            part2 = ''.join(random.choices(string.digits, k=3))
            quiz_id = f"{part1}-{part2}"
            if not db.collection('quizzes').document(quiz_id).get().exists:
                break
        
    doc_ref = db.collection('quizzes').document(quiz_id)
    data_to_save = {
        'title': request.title,
        'data': request.data,
        'mode': request.mode,
        'time_limit': request.time_limit,
        'is_shuffle': request.is_shuffle,
        'creator_id': request.creator_id,
        'status': request.status,
        'updated_at': firestore.SERVER_TIMESTAMP
    }
    
    if not request.quiz_id:
        data_to_save['created_at'] = firestore.SERVER_TIMESTAMP
        
    doc_ref.set(data_to_save, merge=True)
    return {"status": "success", "quiz_id": quiz_id, "link": f"/?id={quiz_id}"}

@app.get("/api/get_quiz/{quiz_id}", summary="Lấy dữ liệu bài thi qua ID")
async def get_quiz(quiz_id: str, teacher_token: str = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
    doc_ref = db.collection('quizzes').document(quiz_id)
    doc = doc_ref.get()
    if doc.exists:
        quiz_data = doc.to_dict()
        is_creator = teacher_token and quiz_data.get('creator_id') == teacher_token
        
        if quiz_data.get('status') == 'unpublished' and not is_creator:
            raise HTTPException(status_code=403, detail="Bài thi này đã bị giáo viên tạm khóa (Hủy xuất bản).")
            
        updated_at = quiz_data.get('updated_at')
        updated_ts = updated_at.timestamp() if hasattr(updated_at, 'timestamp') else 0
            
        return {
            "status": "success", 
            "title": quiz_data.get('title'), 
            "data": quiz_data.get('data'), 
            "mode": quiz_data.get('mode', 'practice'), 
            "time_limit": quiz_data.get('time_limit', 0),
            "is_shuffle": quiz_data.get('is_shuffle', False),
            "updated_at": updated_ts
        }
    raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")

@app.get("/api/teacher/quizzes", summary="Lấy danh sách đề thi của Giáo viên")
async def get_teacher_quizzes(teacher_token: str):
    if db is None: return {"status": "error"}
    # Chỉ lấy các đề do giáo viên này tạo
    docs = db.collection('quizzes').where('creator_id', '==', teacher_token).get()
    results = []
    for doc in docs:
        data = doc.to_dict()
        results.append({
            'id': doc.id,
            'title': data.get('title', 'Không tên'),
            'mode': data.get('mode', 'practice'),
            'status': data.get('status', 'published'),
            'question_count': len(data.get('data', []))
        })
    return {"status": "success", "data": results}

@app.post("/api/teacher/quiz_action", summary="Thao tác với đề thi (Thùng rác, Khôi phục, Xóa vĩnh viễn)")
async def quiz_action(req: QuizActionRequest):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    doc_ref = db.collection('quizzes').document(req.quiz_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get('creator_id') != req.teacher_token:
        raise HTTPException(status_code=403, detail="Không có quyền")
        
    if req.action == 'trash':
        doc_ref.update({'status': 'trashed'})
    elif req.action == 'restore':
        doc_ref.update({'status': 'unpublished'}) # Khôi phục về dạng đang khóa
    elif req.action == 'permanent':
        doc_ref.delete()
    return {"status": "success"}

@app.post("/api/teacher/toggle_publish", summary="Bật/Tắt xuất bản đề thi")
async def toggle_publish(req: TogglePublishRequest):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    doc_ref = db.collection('quizzes').document(req.quiz_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get('creator_id') != req.teacher_token:
        raise HTTPException(status_code=403, detail="Không có quyền")
        
    doc_ref.update({'status': req.status})
    return {"status": "success"}

@app.post("/api/teacher/check_quiz_ai", summary="AI Kiểm tra lỗi đề thi")
def check_quiz_ai(req: CheckQuizRequest):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    teacher_doc = db.collection('users').document(req.teacher_token).get()
    if not teacher_doc.exists or teacher_doc.to_dict().get('role') not in ['teacher', 'admin']:
        raise HTTPException(status_code=403, detail="Không có quyền")
        
    settings_doc = db.collection('settings').document('gemini').get()
    if not settings_doc.exists or not settings_doc.to_dict().get('api_keys'):
        raise HTTPException(status_code=400, detail="Quản trị viên chưa cấu hình Gemini API Key chung. Vui lòng liên hệ Admin.")
    api_keys = settings_doc.to_dict().get('api_keys')
    
    try:
        custom_instructions = f"\n**YÊU CẦU ĐẶC BIỆT TỪ NGƯỜI DÙNG (CẦN ƯU TIÊN THỰC HIỆN):**\n{req.custom_prompt}\n" if req.custom_prompt.strip() else ""
        
        prompt = f"""
        Bạn là một chuyên gia giáo dục và biên tập viên kiểm định đề thi trắc nghiệm.
        Hãy rà soát kỹ lưỡng danh sách câu hỏi trắc nghiệm dưới đây.
        {custom_instructions}
        Nếu người dùng không có yêu cầu đặc biệt nào, hãy tự động tìm các lỗi chung như: sai đáp án, lỗi chính tả, ngữ pháp, lỗi logic, trùng lặp đáp án, văn phong lủng củng.

        QUY TẮC ĐỊNH DẠNG JSON (BẮT BUỘC PHẢI TUÂN THỦ TUYỆT ĐỐI):
        1.  **CHỈ** phân tích những câu hỏi có lỗi. **BỎ QUA HOÀN TOÀN** những câu đúng.
        2.  Đối với mỗi câu lỗi, hãy cung cấp một JSON object chứa:
            *   `question_index`: (Number) Chỉ số của câu hỏi trong mảng (bắt đầu từ 0).
            *   `reason`: (String) Giải thích ngắn gọn, rõ ràng về lỗi đã phát hiện.
            *   `corrected_data`: (Object) Một object chứa dữ liệu đã được sửa, bao gồm `question`, `options`, và `correct_answer`. Giữ nguyên `group_title` của câu hỏi gốc.
        3.  Kết quả cuối cùng của bạn **BẮT BUỘC** phải là một JSON array chứa các object nói trên.
        4.  TUYỆT ĐỐI CHỈ TRẢ VỀ JSON ARRAY (KHÔNG KÈM BẤT KỲ VĂN BẢN GIẢI THÍCH NÀO BÊN NGOÀI). Nếu đề thi không có lỗi nào, trả về đúng 2 ký tự: []
        5.  **QUAN TRỌNG:** Giữ nguyên các thẻ HTML (<b>, <i>, <img>, v.v.) và công thức LaTeX (\\(...\\)) nếu có trong dữ liệu gốc.

        Ví dụ về định dạng JSON trả về nếu có lỗi ở câu 1 (index 0):
        [
          {{
            "question_index": 0,
            "reason": "Lỗi chính tả 'helo' trong câu hỏi.",
            "corrected_data": {{
              "group_title": "Đọc đoạn văn...",
              "question": "Sửa lại thành 'hello world'",
              "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
              "correct_answer": "A. ..."
            }}
          }}
        ]

        Dữ liệu đề thi (JSON array, câu hỏi được đánh index từ 0):
        {json.dumps(req.quiz_data, ensure_ascii=False)}
        """
        
        response = call_gemini_with_fallback(prompt, api_keys)
        
        # Cố gắng parse JSON từ response
        try:
            match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if not match:
                if "không có lỗi" in response.text.lower() or "hoàn hảo" in response.text.lower() or "tuyệt vời" in response.text.lower():
                     return {"status": "success", "feedback": []}
                return {"status": "success", "feedback": response.text}

            json_text = match.group(0)
            json_text = fix_json_latex_escapes(json_text)
            feedback_data = json.loads(json_text, strict=False)
            return {"status": "success", "feedback": feedback_data}
        except (json.JSONDecodeError, ValueError):
            return {"status": "success", "feedback": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi gọi AI: {str(e)}")

@app.post("/api/student/save_progress", summary="Lưu tiến trình làm bài của học sinh lên Cloud")
async def save_student_progress(req: SaveProgressRequest):
    if db is None: return {"status": "error"}
    user_doc = db.collection('users').document(req.student_token).get()
    if not user_doc.exists or user_doc.to_dict().get('role') != 'student':
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")

    db.collection('users').document(req.student_token).collection('progress').document(req.quiz_id).set({
        'progress_data': req.progress_data,
        'updated_at': firestore.SERVER_TIMESTAMP
    })
    return {"status": "success"}

@app.get("/api/student/get_progress/{quiz_id}", summary="Lấy tiến trình làm bài từ Cloud")
async def get_student_progress(quiz_id: str, student_token: str):
    if db is None: return {"status": "error"}
    prog_doc = db.collection('users').document(student_token).collection('progress').document(quiz_id).get()
    if prog_doc.exists:
        return {"status": "success", "data": prog_doc.to_dict().get('progress_data')}
    return {"status": "success", "data": None}

@app.post("/api/monitor/ping", summary="Nhận tín hiệu Ping từ thiết bị học sinh")
async def ping_session(req: PingSessionRequest):
    if db is None: return {"status": "error"}
    db.collection('quizzes').document(req.quiz_id).collection('active_sessions').document(req.session_id).set({
        'student_name': req.student_name,
        'answers_count': req.answers_count,
        'time_remaining': req.time_remaining,
        'completed': req.completed,
        'updated_at': firestore.SERVER_TIMESTAMP
    })
    return {"status": "success"}

@app.get("/api/teacher/monitor/{quiz_id}", summary="Lấy danh sách trạng thái làm bài trực tiếp")
async def get_monitor_data(quiz_id: str, teacher_token: str):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    doc_ref = db.collection('quizzes').document(quiz_id).get()
    if not doc_ref.exists or doc_ref.to_dict().get('creator_id') != teacher_token:
        raise HTTPException(status_code=403, detail="Không có quyền giám sát đề này")
    
    sessions = db.collection('quizzes').document(quiz_id).collection('active_sessions').get()
    res = []
    now = datetime.datetime.now(datetime.timezone.utc)
    for s in sessions:
        d = s.to_dict()
        updated_at = d.get('updated_at')
        is_online = False
        if updated_at and (now - updated_at).total_seconds() < 40:
            is_online = True
        res.append({
            'session_id': s.id,
            'student_name': d.get('student_name', 'Ẩn danh'),
            'answers_count': d.get('answers_count', 0),
            'time_remaining': d.get('time_remaining', 0),
            'completed': d.get('completed', False),
            'is_online': is_online
        })
    return {"status": "success", "data": res}

@app.post("/api/submit_score", summary="Lưu điểm và thời gian của học sinh")
async def submit_score(request: SubmitScoreRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
    
    doc_ref = db.collection('quizzes').document(request.quiz_id).collection('submissions').document()
    doc_ref.set({
        'student_name': request.student_name,
        'score': request.score,
        'total_questions': request.total_questions,
        'time_elapsed': request.time_elapsed,
        'timestamp': firestore.SERVER_TIMESTAMP
    })
    return {"status": "success"}

@app.get("/api/leaderboard/{quiz_id}", summary="Lấy bảng xếp hạng top thành tích")
async def get_leaderboard(quiz_id: str):
    if db is None: return {"status": "error"}
    subs_ref = db.collection('quizzes').document(quiz_id).collection('submissions')
    docs = subs_ref.get()
    results = []
    for doc in docs:
        data = doc.to_dict()
        results.append({
            'student_name': data.get('student_name', 'Ẩn danh'),
            'score': data.get('score', 0),
            'time_elapsed': data.get('time_elapsed', 999999)
        })
    # Sắp xếp theo ưu tiên: Điểm cao trước, thời gian ngắn (nhanh hơn) trước
    results.sort(key=lambda x: (-x['score'], x['time_elapsed']))
    return {"status": "success", "data": results[:50]} # Trả về top 50 người cao nhất

@app.post("/api/upload", summary="Tải lên và phân tích file DOCX")
def upload_document(file: UploadFile = File(...), use_ai: bool = Form(True)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".docx":
        raise HTTPException(status_code=400, detail="Hệ thống chỉ đang hỗ trợ nhận diện trực tiếp qua file .docx")
        
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name
            
        settings_doc = db.collection('settings').document('gemini').get() if db else None
        api_keys = settings_doc.to_dict().get('api_keys', []) if settings_doc and settings_doc.exists else []
        
        extracted_data = None
        if use_ai and api_keys:
            marked_text, image_mapping = parse_docx_to_marked_text(temp_file_path)
            extracted_data = generate_mcq_with_gemini(marked_text, api_keys)
            
            if image_mapping:
                extracted_data = replace_placeholders(extracted_data, image_mapping)
        else:
            extracted_data = extract_formatting_from_docx(temp_file_path)

        # Giải mã các thẻ HTML (do quá trình escape trước đó hoặc do AI trả về) để Frontend hiển thị chuẩn
        extracted_data = recursive_unescape(extracted_data)

        if not extracted_data:
             raise HTTPException(status_code=422, detail="Không thể trích xuất câu hỏi. Vui lòng đảm bảo cấu trúc file theo đúng chuẩn (A., B., C., D.)")

        return {
            "filename": file.filename,
            "status": "success",
            "message": "File đã được phân tích!",
            "data": extracted_data
        }
        
    except Exception as e:
        error_msg = str(e)
        if "Package not found" in error_msg:
            raise HTTPException(
                status_code=400, 
                detail="File tải lên không phải là định dạng Word (.docx) chuẩn. Có thể đây là file .doc cũ bị đổi tên đuôi hoặc file đã bị hỏng. Vui lòng mở file bằng Microsoft Word và chọn 'Save As' -> 'Word Document (*.docx)' rồi tải lên lại."
            )
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý hệ thống: {error_msg}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)