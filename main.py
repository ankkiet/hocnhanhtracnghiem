import sys
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

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import fitz  # PyMuPDF: Thư viện đọc PDF siêu tốc và chính xác
except ImportError:
    fitz = None

try:
    import json_repair  # Thư viện tự động sửa lỗi JSON của AI
except ImportError:
    json_repair = None

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from docx import Document
from docx.oxml.ns import qn, nsmap
if 'o' not in nsmap:
    nsmap['o'] = 'urn:schemas-microsoft-com:office:office'
if 'v' not in nsmap:
    nsmap['v'] = 'urn:schemas-microsoft-com:vml'
from docx.text.paragraph import Paragraph
from services.firebase_service import init_firebase, get_db
from services.ai_service import (
    call_gemini_with_fallback,
    fix_json_latex_escapes,
    generate_mcq_with_gemini,
    generate_mcq_from_pdf,
    normalize_question_data
)
from services.r2_service import upload_image_to_r2, get_stored_image
from core.image_converter import process_image_blob
from core.mathml_parser import parse_omath, MATH_SYM_MAP
from core.state import active_tasks

# ==========================================
# PHẦN 1: CẤU HÌNH & QUẢN LÝ DATABASE
# ==========================================
# Khởi tạo Firebase Firestore an toàn (Bảo vệ mật khẩu Admin không bị ghi đè khi restart)
db = init_firebase()

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
    
class GenerateQuizRequest(BaseModel):
    prompt: str
    num_questions: int = 5
    difficulty: str = "Trung bình"

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

# Biên dịch sẵn Regex (Tối ưu tốc độ quét vòng lặp văn bản)
RE_NUMBERING = re.compile(r'^\s*(Câu|Bài|Question|Q|\d+[\.\:\)]|\*?\s*[A-F][\.\:\)])', re.IGNORECASE)
RE_GROUP_TITLE = re.compile(r'^\s*(PHẦN|PART|CHƯƠNG|BÀI TẬP|TEST|PRACTICE|MỨC ĐỘ|DẠNG|I{1,3}\.|IV\.|V\.|VI{0,3}\.)\b', re.IGNORECASE)

# Khởi tạo bộ nhớ tạm để lưu trạng thái các Tác vụ chạy ngầm (Background Tasks)
active_tasks = {}
def extract_answer_key(doc: Document, full_text: str) -> Dict[int, str]:
    """
    Tự động dò tìm và bóc tách Bảng đáp án ở cuối tài liệu Word (nếu có).
    Hỗ trợ:
    1. Bảng biểu 2 hàng: Hàng trên là số câu (1, 2, 3...), Hàng dưới là chữ cái A, B, C, D.
    2. Khối văn bản sau tiêu đề BẢNG ĐÁP ÁN / ĐÁP ÁN / ANSWER KEY (vd: 1.A 2.B 3.C...).
    """
    answer_map = {}
    
    # 1. Quét các bảng trong tài liệu
    if hasattr(doc, 'tables') and doc.tables:
        for table in doc.tables:
            if len(table.rows) >= 2:
                for r_idx in range(len(table.rows) - 1):
                    row_top = [c.text.strip() for c in table.rows[r_idx].cells]
                    row_bot = [c.text.strip() for c in table.rows[r_idx + 1].cells]
                    
                    matches_in_table = 0
                    temp_table_map = {}
                    for c_top, c_bot in zip(row_top, row_bot):
                        num_m = re.search(r'\b(\d+)\b', c_top)
                        ans_m = re.search(r'\b([A-F])\b', c_bot, re.IGNORECASE)
                        if num_m and ans_m:
                            q_num = int(num_m.group(1))
                            temp_table_map[q_num] = ans_m.group(1).upper()
                            matches_in_table += 1
                    
                    if matches_in_table >= 1:
                        answer_map.update(temp_table_map)
                        
    if answer_map:
        return answer_map

    # 2. Quét trong khối văn bản cuối tài liệu sau tiêu đề BẢNG ĐÁP ÁN
    key_headers = ["BẢNG ĐÁP ÁN", "BANG DAP AN", "ĐÁP ÁN", "DAP AN", "ANSWER KEY", "HƯỚNG DẪN CHẤM"]
    ans_section = ""
    for header in key_headers:
        pos = full_text.upper().rfind(header)
        if pos != -1 and (len(full_text) - pos) < 8000:
            ans_section = full_text[pos:]
            break
            
    if ans_section:
        pattern = re.compile(r'(?:Câu\s*)?(\d+)\s*[\.\:\-\)\/]?\s*([A-F])\b', re.IGNORECASE)
        for m in pattern.finditer(ans_section):
            q_num = int(m.group(1))
            ans_char = m.group(2).upper()
            answer_map[q_num] = ans_char
            
    return answer_map


def find_image_part_and_id(img_node, doc):
    """Tìm mã quan hệ rId và image_part của ảnh trong tài liệu Word một cách toàn diện nhất"""
    rId = None
    attrs_to_check = [
        '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed',
        '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id',
        '{http://schemas.microsoft.com/office/2006/relationships}id',
        '{urn:schemas-microsoft-com:office:office}relid',
        '{http://schemas.openxmlformats.org/drawingml/2006/main}embed',
        '{http://schemas.openxmlformats.org/drawingml/2006/main}link',
        'id'
    ]
    try:
        attrs_to_check.append(qn('r:embed'))
        attrs_to_check.append(qn('r:id'))
    except Exception:
        pass

    for attr in attrs_to_check:
        try:
            val = img_node.get(attr)
            if val and isinstance(val, str) and (val.startswith('rId') or 'rId' in val):
                rId = val
                break
        except Exception:
            continue
            
    if not rId:
        try:
            for k, v in img_node.attrib.items():
                if isinstance(v, str) and ('rId' in v or 'image' in v.lower()):
                    rId = v
                    break
        except Exception:
            pass

    if not rId:
        return None, None

    image_part = None
    try:
        if hasattr(doc, 'part') and doc.part is not None:
            if hasattr(doc.part, 'related_parts') and rId in doc.part.related_parts:
                image_part = doc.part.related_parts[rId]
            elif hasattr(doc.part, 'rels') and rId in doc.part.rels:
                rel = doc.part.rels[rId]
                if hasattr(rel, 'target_part'):
                    image_part = rel.target_part
    except Exception:
        pass

    return rId, image_part

def replace_placeholders(data, mapping):
    if isinstance(data, dict):
        return {k: replace_placeholders(v, mapping) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_placeholders(v, mapping) for v in data]
    elif isinstance(data, str):
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
    full_text_list = []
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
            full_text_list.append("\n")
            format_weights.append(0)
            char_html.append("\n")
            continue
            
        prefix = get_auto_numbering_prefix(para, doc, counters)
        if prefix:
            para_text_strip = raw_text.strip()
            is_numbering_text = RE_NUMBERING.match(para_text_strip)
            is_group_title = RE_GROUP_TITLE.match(para_text_strip)
            
            if not is_numbering_text and not is_group_title:
                full_text_list.append(prefix)
                format_weights.extend([0] * len(prefix))
                char_html.extend(list(prefix))
                
        for node in para._element.xpath('.//*[local-name()="t" or local-name()="drawing" or local-name()="pict" or local-name()="object" or local-name()="oMath"]'):
            if node.xpath('ancestor::*[local-name()="oMath"]') and not node.tag.endswith('}oMath'):
                continue
                
            if node.tag.endswith('}oMath'):
                try:
                    math_latex = parse_omath(node)
                    if math_latex:
                        encoded_math = math_latex.replace("<", "&lt;").replace(">", "&gt;")
                        math_tag = f" \\({encoded_math}\\) "
                        full_text_list.append(math_tag)
                        format_weights.extend([0] * len(math_tag))
                        for char in math_tag:
                            char_html.append(f"<i>{char}</i>")
                except Exception:
                    pass
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
                    try:
                        rId, image_part = find_image_part_and_id(img_node, doc)
                        if rId and image_part is not None:
                            mime_type = image_part.content_type
                            img_counter += 1
                            placeholder = f"[IMG_{img_counter}]"
                            
                            processed_blob, processed_mime = process_image_blob(image_part.blob, mime_type)
                            img_url = upload_image_to_r2(processed_blob, mime_type=processed_mime)
                            if img_url:
                                image_mapping[placeholder] = f"<br><img src='{img_url}' class='quiz-image' style='{img_style}' /><br>"
                            else:
                                b64_encoded = base64.b64encode(processed_blob).decode('utf-8')
                                image_mapping[placeholder] = f"<br><img src='data:{processed_mime};base64,{b64_encoded}' class='quiz-image' style='{img_style}' /><br>"
                            
                            full_text_list.append(f" {placeholder} ")
                            format_weights.extend([0] * len(f" {placeholder} "))
                            char_html.extend(list(f" {placeholder} "))
                    except Exception as img_err:
                        print(f"[CẢNH BÁO] Không thể xử lý ảnh: {img_err}")
            elif node.tag.endswith('}t'):
                run_text = node.text
                if not run_text: continue
                
                r = node.getparent()
                rPr_list = r.xpath('./*[local-name()="rPr"]') if r is not None and r.tag.endswith('}r') else []
                is_bold = is_italic = is_underline = is_highlighted = is_red_text = is_subscript = is_superscript = False
                
                if rPr_list:
                    rPr = rPr_list[0]
                    # Tối ưu: Dùng hàm .find nhanh gấp 5-10 lần so với .xpath()
                    if rPr.find(qn('w:b')) is not None: is_bold = True
                    if rPr.find(qn('w:i')) is not None: is_italic = True
                    if rPr.find(qn('w:u')) is not None: is_underline = True
                    
                    highlight = rPr.find(qn('w:highlight'))
                    if highlight is not None and highlight.get(qn('w:val')) not in ['none', None]: is_highlighted = True
                        
                    color = rPr.find(qn('w:color'))
                    if color is not None:
                        c_val = str(color.get(qn('w:val'), '')).upper()
                        # Nhận diện cả màu Đỏ lẫn màu Xanh lá (giáo viên hay dùng để đánh dấu đáp án)
                        if c_val in ['FF0000', 'C00000', 'ED1C24', 'RED', '008000', '00B050', '059669', '10B981', '22C55E', '16A34A', 'GREEN']:
                            is_red_text = True
                            
                    vertAlign = rPr.find(qn('w:vertAlign'))
                    if vertAlign is not None:
                        val = vertAlign.get(qn('w:val'))
                        if val == 'subscript': is_subscript = True
                        if val == 'superscript': is_superscript = True

                # Nhận diện ký tự dấu tích đúng (✓, ✔)
                if '✓' in run_text or '✔' in run_text:
                    is_red_text = True
                
                full_text_list.append(run_text)
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
            
        full_text_list.append("\n")
        format_weights.append(0)
        char_html.append("\n")
        
    full_text = "".join(full_text_list)

    def get_html(start, end):
        joined = "".join(char_html[start:end])
        for tag in ['b', 'i', 'u', 'sup', 'sub']:
            joined = joined.replace(f"</{tag}><{tag}>", "")
        return joined.strip()

    # BƯỚC 2: Phân tách bằng State Machine (Máy trạng thái) kết hợp Regex siêu chuẩn
    # Hỗ trợ: Câu 1, Câu 1:, Câu 1., Câu 1/, Câu 1-, [Câu 1], (Câu 1), Bài 1, Question 1, Q1, 1., 1/, 1:, 1)
    q_regex = r'(?:^|\n)\s*(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])(?:\s+|$)'
    # Hỗ trợ: A., B., C., D., A:, A), A/, A -, (A), [A], *A., a., b.
    opt_regex = r'(?:^|\n|\t|\s{2,}|(?<=[;\.\:\?!]\s)|(?<=\))\s*)(?:\(?\[?(\*?[A-F])(?:[\.\:\/\)\]\-]|\b))(?:\s+|$)'
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
            elif state == "IN_QUESTION":
                # Câu hỏi trước đó không có lựa chọn A, B, C, D rõ ràng -> vẫn lưu lại
                q_text = get_html(current_q_start, match_start)
                if q_text.strip():
                    extracted_data.append({
                        "group_title": shared_context,
                        "question": q_text,
                        "options": [],
                        "correct_answer": ""
                    })
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
    elif state == "IN_QUESTION":
        q_text = get_html(current_q_start, len(full_text))
        if q_text.strip():
            extracted_data.append({
                "group_title": shared_context,
                "question": q_text,
                "options": [],
                "correct_answer": ""
            })

    # BƯỚC 3: Nếu có câu hỏi chưa tìm được đáp án đúng, dò tìm Bảng đáp án cuối tài liệu
    try:
        answer_key = extract_answer_key(doc, full_text)
        for idx, q_item in enumerate(extracted_data):
            q_num = idx + 1
            if not q_item.get("correct_answer") and q_num in answer_key:
                target_char = answer_key[q_num]
                for opt in q_item.get("options", []):
                    if opt.strip().upper().startswith(f"{target_char}."):
                        q_item["correct_answer"] = opt
                        break
    except Exception as e:
        print(f"[CẢNH BÁO] Lỗi đọc bảng đáp án: {e}")

    # Đảm bảo câu hỏi luôn có đáp án hợp lệ (ưu tiên A nếu không rõ)
    for q_item in extracted_data:
        if not q_item.get("correct_answer") and q_item.get("options"):
            q_item["correct_answer"] = q_item["options"][0]

    if image_mapping:
        extracted_data = replace_placeholders(extracted_data, image_mapping)

    return extracted_data


def extract_questions_from_text_bulletproof(raw_text: str, image_mapping: dict = None) -> List[Dict[str, Any]]:
    """
    Bộ bóc tách câu hỏi dự phòng siêu bền vững bằng Regex khối.
    Tự động chia tách văn bản thành từng câu hỏi và bóc tách các lựa chọn A, B, C, D.
    """
    if not raw_text or not raw_text.strip():
        return []

    q_split_pattern = re.compile(
        r'(?:^|\n)\s*(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*',
        re.IGNORECASE
    )
    
    matches = list(q_split_pattern.finditer(raw_text))
    if not matches:
        return []
        
    results = []
    opt_pattern = re.compile(
        r'(?:^|\n|\t|\s{2,}|(?<=[;\.\:\?!]\s)|(?<=\))\s*)(?:\(?\[?(\*?[A-F])(?:[\.\:\/\)\]\-]|\b))\s*',
        re.IGNORECASE
    )
    
    for i, m in enumerate(matches):
        q_start = m.end()
        q_end = matches[i+1].start() if i+1 < len(matches) else len(raw_text)
        block = raw_text[q_start:q_end].strip()
        
        opt_matches = list(opt_pattern.finditer(block))
        if opt_matches:
            q_text = block[:opt_matches[0].start()].strip()
            options = []
            correct_ans = None
            
            for j, opt_m in enumerate(opt_matches):
                char_raw = opt_m.group(1).upper()
                is_asterisk = '*' in char_raw
                char = char_raw.replace('*', '').strip()
                
                opt_start = opt_m.end()
                opt_end = opt_matches[j+1].start() if j+1 < len(opt_matches) else len(block)
                opt_content = block[opt_start:opt_end].strip()
                
                opt_content = re.sub(r'\s+', ' ', opt_content)
                
                if is_asterisk or '<MARK>' in opt_content or '[ĐÚNG]' in opt_content or '✓' in opt_content or '✔' in opt_content:
                    clean_opt = opt_content.replace('<MARK>', '').replace('</MARK>', '').strip()
                    correct_ans = f"{char}. {clean_opt}"
                    
                clean_opt_for_list = opt_content.replace('<MARK>', '').replace('</MARK>', '').strip()
                options.append(f"{char}. {clean_opt_for_list}")
                
            if not correct_ans and options:
                correct_ans = options[0]
                
            results.append({
                "group_title": "",
                "question": q_text,
                "options": options,
                "correct_answer": correct_ans
            })
        else:
            results.append({
                "group_title": "",
                "question": block,
                "options": [],
                "correct_answer": ""
            })
            
    if image_mapping and results:
        results = replace_placeholders(results, image_mapping)
        
    return results


def extract_questions_from_pdf_locally(pdf_path: str) -> List[Dict[str, Any]]:
    """Bóc tách câu hỏi và hình ảnh từ tệp PDF hoàn toàn cục bộ (không cần AI)."""
    if not fitz:
        return []
    try:
        doc = fitz.open(pdf_path)
        full_text_list = []
        image_mapping = {}
        img_counter = 0
        
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text("text")
            
            # Trích xuất ảnh trên trang PDF
            image_list = page.get_images(full=True)
            for img_info in image_list:
                try:
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image.get("image")
                    image_ext = base_image.get("ext", "png")
                    if image_bytes:
                        img_counter += 1
                        placeholder = f"[IMG_{img_counter}]"
                        processed_bytes, processed_mime = process_image_blob(image_bytes, f"image/{image_ext}")
                        img_url = upload_image_to_r2(processed_bytes, mime_type=processed_mime, extension=image_ext)
                        if img_url:
                            image_mapping[placeholder] = f"<br><img src='{img_url}' class='quiz-image' style='max-width:100%; height:auto;' /><br>"
                except Exception as img_err:
                    print(f"[CẢNH BÁO] Lỗi trích xuất ảnh PDF: {img_err}")
                    
            full_text_list.append(text)
        doc.close()
        
        merged_text = "\n".join(full_text_list)
        return extract_questions_from_text_bulletproof(merged_text, image_mapping)
    except Exception as e:
        print(f"[CẢNH BÁO] Lỗi đọc PDF cục bộ: {e}")
        return []


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
            is_numbering_text = RE_NUMBERING.match(para_text_strip)
            is_group_title = RE_GROUP_TITLE.match(para_text_strip)
            if not is_numbering_text and not is_group_title:
                para_text += prefix
                
        for node in para._element.xpath('.//*[local-name()="t" or local-name()="drawing" or local-name()="pict" or local-name()="object" or local-name()="oMath"]'):
            if node.xpath('ancestor::*[local-name()="oMath"]') and not node.tag.endswith('}oMath'):
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
                    try:
                        rId, image_part = find_image_part_and_id(img_node, doc)
                        if rId and image_part is not None:
                            mime_type = image_part.content_type
                            img_counter += 1
                            placeholder = f"[IMG_{img_counter}]"
                            
                            processed_blob, processed_mime = process_image_blob(image_part.blob, mime_type)
                            img_url = upload_image_to_r2(processed_blob, mime_type=processed_mime)
                            if img_url:
                                image_mapping[placeholder] = f"<img src='{img_url}' class='quiz-image' style='{img_style}' />"
                            else:
                                b64_encoded = base64.b64encode(processed_blob).decode('utf-8')
                                image_mapping[placeholder] = f"<img src='data:{processed_mime};base64,{b64_encoded}' class='quiz-image' style='{img_style}' />"
                            
                            para_text += f" {placeholder} "
                    except Exception as img_err:
                        print(f"[CẢNH BÁO] parse_docx_to_marked_text lỗi ảnh: {img_err}")
            elif node.tag.endswith('}t'):
                run_text = node.text
                if not run_text: continue
                
                r = node.getparent()
                rPr_list = r.xpath('./*[local-name()="rPr"]') if r is not None and r.tag.endswith('}r') else []
                is_bold = is_italic = is_underline = is_highlighted = is_red_text = is_subscript = is_superscript = False
                
                if rPr_list:
                    rPr = rPr_list[0]
                    if rPr.find(qn('w:b')) is not None: is_bold = True
                    if rPr.find(qn('w:i')) is not None: is_italic = True
                    if rPr.find(qn('w:u')) is not None: is_underline = True
                    
                    highlight = rPr.find(qn('w:highlight'))
                    if highlight is not None and highlight.get(qn('w:val')) not in ['none', None]: is_highlighted = True
                        
                    color = rPr.find(qn('w:color'))
                    if color is not None:
                        c_val = str(color.get(qn('w:val'), '')).upper()
                        if c_val in ['FF0000', 'C00000', 'ED1C24', 'RED', '008000', '00B050', '059669', '10B981', '22C55E', '16A34A', 'GREEN']:
                            is_red_text = True
                            
                    vertAlign = rPr.find(qn('w:vertAlign'))
                    if vertAlign is not None:
                        val = vertAlign.get(qn('w:val'))
                        if val == 'subscript': is_subscript = True
                        if val == 'superscript': is_superscript = True

                if '✓' in run_text or '✔' in run_text:
                    is_red_text = True
                
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

# Các thuật toán xử lý AI đã được chuyển sang services/ai_service.py

# ==========================================
# PHẦN 4: GIAO DIỆN & API ENDPOINTS
# ==========================================

@app.get("/api/status", summary="Kiểm tra trạng thái máy chủ")
async def root_status():
    return {"status": "success", "message": "Backend API is running!"}

@app.get("/api/keep-alive", summary="API giữ máy chủ luôn thức")
async def keep_alive():
    return {"status": "ok", "message": "Hệ thống đang thức và sẵn sàng!"}

# ==========================================
# ĐĂNG KÝ CÁC MODULE ROUTER (TÁCH BIỆT & BẢO MẬT)
# ==========================================
from routers.auth import router as auth_router
from routers.quiz import router as quiz_router
from routers.student import router as student_router
from routers.teacher import router as teacher_router
from routers.admin import router as admin_router

app.include_router(auth_router)
app.include_router(quiz_router)
app.include_router(student_router)
app.include_router(teacher_router)
app.include_router(admin_router)

async def generate_quiz_ai_background(task_id: str, req: GenerateQuizRequest, api_keys: List[str]):
    """Tác vụ chạy ngầm để tạo đề thi từ một chủ đề (prompt)"""
    try:
        active_tasks[task_id] = {"status": "processing", "message": "AI đang suy nghĩ và tạo đề..."}
        
        system_instruction = (
            "Bạn là một chuyên gia giáo dục và biên soạn đề thi trắc nghiệm xuất sắc. "
            "Nhiệm vụ của bạn là tạo ra các câu hỏi trắc nghiệm chất lượng cao, đúng chuẩn kiến thức, "
            "đúng 4 lựa chọn A, B, C, D rõ ràng, và luôn kèm lời giải chi tiết (explain). "
            "Nếu có công thức toán/lý/hóa, dùng cú pháp LaTeX bọc trong \\( và \\). "
            "Định dạng trả về bắt buộc là một JSON array duy nhất."
        )
        
        prompt = f"""
        Hãy tạo đề thi trắc nghiệm theo thông số sau:
        - Chủ đề / Nội dung cốt lõi: {req.prompt}
        - Số lượng câu hỏi: {req.num_questions}
        - Độ khó: {req.difficulty}

        Mỗi câu hỏi có cấu trúc JSON:
        {{
          "group_title": "Tiêu đề nhóm hoặc đoạn văn đọc hiểu (nếu có, không có thì để trống '')",
          "question": "Nội dung câu hỏi (không thêm 'Câu X:')",
          "options": ["A. Lựa chọn 1", "B. Lựa chọn 2", "C. Lựa chọn 3", "D. Lựa chọn 4"],
          "correct_answer": "A. Lựa chọn 1",
          "explain": "Lời giải thích ngắn gọn, súc tích vì sao đáp án này đúng."
        }}
        """
        
        response = await call_gemini_with_fallback(
            prompt=prompt,
            api_keys=api_keys,
            system_instruction=system_instruction,
            thinking_budget=0
        )
        match = re.search(r'\[\s*\{.*\}\s*\]', response.text, re.DOTALL)
        json_text = match.group(0) if match else response.text
        json_text = fix_json_latex_escapes(json_text)
        
        if json_repair is not None:
            data = json_repair.loads(json_text)
        else:
            data = json.loads(json_text, strict=False)
            
        if isinstance(data, list):
            data = [normalize_question_data(q) for q in data if isinstance(q, dict)]
            
        active_tasks[task_id] = {"status": "success", "data": data}

    except Exception as e:
        active_tasks[task_id] = {"status": "error", "detail": f"Lỗi khi gọi AI hoặc parse JSON: {str(e)}"}


@app.post("/api/generate_quiz_ai", summary="Tạo đề thi tự động bằng AI (Chạy ngầm)")
async def generate_quiz_ai(req: GenerateQuizRequest, background_tasks: BackgroundTasks):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    
    settings_doc = db.collection('settings').document('gemini').get()
    if not settings_doc.exists or not settings_doc.to_dict().get('api_keys'):
        raise HTTPException(status_code=400, detail="Hệ thống chưa cấu hình Gemini API Key. Vui lòng liên hệ Admin.")
    api_keys = settings_doc.to_dict().get('api_keys')
    
    task_id = str(uuid.uuid4())
    active_tasks[task_id] = {"status": "pending"}
    
    background_tasks.add_task(generate_quiz_ai_background, task_id, req, api_keys)
    
    return {
        "status": "processing",
        "task_id": task_id,
        "message": "Yêu cầu đã được tiếp nhận. AI đang xử lý ngầm..."
    }



@app.get("/api/images/{file_path:path}", summary="Phục vụ ảnh đề thi an toàn, tốc độ cao và không bị lỗi 403")
async def serve_image(file_path: str):
    """Phục vụ hình ảnh từ bộ nhớ cache cục bộ hoặc đồng bộ từ Cloudflare R2 qua S3 client."""
    content, mime = get_stored_image(file_path)
    if not content:
        raise HTTPException(status_code=404, detail="Không tìm thấy hình ảnh")
    return Response(
        content=content,
        media_type=mime,
        headers={"Cache-Control": "public, max-age=31536000, immutable"}
    )

def process_document_background(task_id: str, temp_file_path: str, ext: str, use_ai: bool, api_keys: list, filename: str):
    import asyncio
    try:
        active_tasks[task_id] = {"status": "processing", "message": "Đang phân tích..."}
        
        extracted_data = None
        if ext == ".pdf":
            if use_ai and api_keys:
                try:
                    active_tasks[task_id]["message"] = "AI đang phân tích tài liệu PDF..."
                    extracted_data = asyncio.run(generate_mcq_from_pdf(temp_file_path, api_keys, task_id))
                except Exception as pdf_ai_err:
                    print(f"[CẢNH BÁO] Lỗi AI bóc tách PDF: {pdf_ai_err}")
                    active_tasks[task_id]["message"] = "Tự động chuyển sang phân tích PDF nội bộ..."
                    extracted_data = extract_questions_from_pdf_locally(temp_file_path)
            else:
                active_tasks[task_id]["message"] = "Đang phân tích PDF bằng thuật toán nội bộ..."
                extracted_data = extract_questions_from_pdf_locally(temp_file_path)
                # Nếu bộ phân tích PDF nội bộ không tìm thấy câu hỏi mà có API Key, tự động cứu hộ bằng AI
                if (not extracted_data or len(extracted_data) == 0) and api_keys:
                    print("[CẢNH BÁO] PDF nội bộ không tìm thấy câu hỏi, tự động kích hoạt AI cứu hộ...")
                    active_tasks[task_id]["message"] = "Tự động kích hoạt AI cứu hộ PDF..."
                    try:
                        extracted_data = asyncio.run(generate_mcq_from_pdf(temp_file_path, api_keys, task_id))
                    except Exception as rescue_err:
                        print(f"[CẢNH BÁO] AI cứu hộ PDF gặp lỗi: {rescue_err}")
        elif use_ai and api_keys:
            try:
                active_tasks[task_id]["message"] = "AI đang phân tích tài liệu Word..."
                marked_text, image_mapping = parse_docx_to_marked_text(temp_file_path)
                extracted_data = asyncio.run(generate_mcq_with_gemini(marked_text, api_keys, task_id))
                if image_mapping and extracted_data:
                    extracted_data = replace_placeholders(extracted_data, image_mapping)
            except Exception as ai_err:
                print(f"[CẢNH BÁO] AI bóc tách gặp lỗi ({ai_err}). Tự động chuyển sang bóc tách Regex nội bộ...")
                active_tasks[task_id]["message"] = "Tự động chuyển sang bộ bóc tách nội bộ..."
                try:
                    extracted_data = extract_formatting_from_docx(temp_file_path)
                except Exception:
                    extracted_data = None
                if not extracted_data:
                    try:
                        extracted_data = extract_questions_from_text_bulletproof(marked_text, image_mapping)
                    except Exception:
                        pass
        else:
            # use_ai = False: Phân tích DOCX bằng Python nội bộ
            active_tasks[task_id]["message"] = "Đang phân tích tài liệu bằng thuật toán Python..."
            try:
                extracted_data = extract_formatting_from_docx(temp_file_path)
            except Exception as docx_err:
                print(f"[CẢNH BÁO] extract_formatting_from_docx gặp lỗi: {docx_err}")
                extracted_data = None
                
            # Nếu bộ bóc tách chính không tìm thấy câu hỏi, kích hoạt bộ bóc tách dự phòng (Engine 2)
            if not extracted_data or len(extracted_data) == 0:
                try:
                    marked_text, image_mapping = parse_docx_to_marked_text(temp_file_path)
                    extracted_data = extract_questions_from_text_bulletproof(marked_text, image_mapping)
                except Exception as fb_err:
                    print(f"[CẢNH BÁO] Bộ bóc tách dự phòng gặp lỗi: {fb_err}")
                    
            # Nếu cả 2 bộ bóc tách nội bộ đều không tìm thấy câu hỏi mà hệ thống CÓ API key, tự động kích hoạt AI cứu hộ
            if (not extracted_data or len(extracted_data) == 0) and api_keys:
                print("[CẢNH BÁO] Bộ bóc tách nội bộ không tìm thấy câu hỏi, tự động kích hoạt AI cứu hộ...")
                active_tasks[task_id]["message"] = "Tự động kích hoạt AI cứu hộ..."
                try:
                    marked_text, image_mapping = parse_docx_to_marked_text(temp_file_path)
                    extracted_data = asyncio.run(generate_mcq_with_gemini(marked_text, api_keys, task_id))
                    if image_mapping and extracted_data:
                        extracted_data = replace_placeholders(extracted_data, image_mapping)
                except Exception as rescue_err:
                    print(f"[CẢNH BÁO] AI cứu hộ gặp lỗi: {rescue_err}")

        extracted_data = recursive_unescape(extracted_data)

        if not extracted_data:
             active_tasks[task_id] = {"status": "error", "detail": "Không thể trích xuất câu hỏi từ file. Vui lòng đảm bảo file có chứa câu hỏi dạng 'Câu 1:' hoặc '1.' và các phương án A, B, C, D."}
             return

        active_tasks[task_id] = {
            "status": "success",
            "data": extracted_data,
            "filename": filename
        }
        
    except Exception as e:
        error_msg = str(e)
        if "Package not found" in error_msg:
            active_tasks[task_id] = {"status": "error", "detail": "File tải lên không phải là định dạng Word (.docx) chuẩn. Có thể đây là file .doc cũ bị đổi tên đuôi hoặc file đã bị hỏng. Vui lòng mở file bằng Microsoft Word và chọn 'Save As' -> 'Word Document (*.docx)' rồi tải lên lại."}
        else:
            active_tasks[task_id] = {"status": "error", "detail": f"Lỗi xử lý hệ thống: {error_msg}"}
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try: os.remove(temp_file_path)
            except Exception: pass

@app.post("/api/upload", summary="Tải lên và phân tích file DOCX hoặc PDF")
def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...) , use_ai: bool = Form(True)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".docx", ".pdf"]:
        raise HTTPException(status_code=400, detail="Hệ thống chỉ hỗ trợ định dạng Word (.docx) và PDF (.pdf)")
        
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name
            
        settings_doc = db.collection('settings').document('gemini').get() if db else None
        api_keys = settings_doc.to_dict().get('api_keys', []) if settings_doc and settings_doc.exists else []
        
        # Nếu người dùng bật AI nhưng hệ thống chưa có API key, tự động chuyển sang phân tích Python nội bộ
        if use_ai and not api_keys:
            use_ai = False
            
        task_id = str(uuid.uuid4())
        active_tasks[task_id] = {"status": "pending"}
        
        # Bắt đầu luồng phân tích ngầm và không chặn luồng kết nối HTTP
        background_tasks.add_task(process_document_background, task_id, temp_file_path, ext, use_ai, api_keys, file.filename)
        
        mode_msg = "AI" if (use_ai and api_keys) else "thuật toán Python"
        return {
            "status": "processing",
            "task_id": task_id,
            "message": f"File đang được xử lý bằng {mode_msg}..."
        }
        
    except HTTPException as he:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise he
    except Exception as e:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        error_msg = str(e)
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý hệ thống: {error_msg}")

@app.get("/api/task_status/{task_id}", summary="Kiểm tra trạng thái tiến trình AI")
def get_task_status(task_id: str):
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Không tìm thấy tiến trình xử lý")
    
    task_info = active_tasks[task_id]
    if task_info["status"] in ["success", "error"]:
        # Xóa tiến trình khỏi bộ nhớ sau khi Frontend đã nhận được kết quả
        return active_tasks.pop(task_id)
        
    return task_info

# ==========================================
# GẮN GIAO DIỆN WEB (STATIC FILES CHO FRONTEND)
# ==========================================
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
if os.path.exists(templates_dir):
    app.mount("/", StaticFiles(directory=templates_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)