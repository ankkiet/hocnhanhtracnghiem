import os
import re
import json
import uuid
import tempfile
import shutil
import hashlib
from typing import List, Dict, Any

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from docx import Document
from docx.oxml.ns import qn
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore

# ==========================================
# PHẦN 1: CẤU HÌNH & QUẢN LÝ DATABASE
# ==========================================

# Khởi tạo Firebase
try:
    # Đảm bảo bạn đã tải file firebase-adminsdk.json từ Firebase Console và để cùng thư mục
    cred = credentials.Certificate("firebase-adminsdk.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    # Khởi tạo Admin mặc định nếu chưa có
    users = db.collection('users').where('username', '==', 'admin').get()
    admin_pwd_hash = hashlib.sha256('a@a@ankk'.encode()).hexdigest()
    if not users:
        db.collection('users').add({
            'username': 'admin',
            'password': admin_pwd_hash, # Mật khẩu mặc định là a@a@ankk
            'full_name': 'Quản trị viên (Admin)',
            'role': 'admin',
            'status': 'approved'
        })
    else:
        # Cập nhật đè lại mật khẩu để đảm bảo Admin luôn vào được bằng mật khẩu mới
        db.collection('users').document(users[0].id).update({
            'password': admin_pwd_hash
        })
except Exception as e:
    print(f"CẢNH BÁO: Không thể khởi tạo Firebase. Vui lòng kiểm tra file firebase-adminsdk.json. Chi tiết: {e}")
    db = None

# ==========================================
# PHẦN 2: CẤU HÌNH FASTAPI & MIDDLEWARE
# ==========================================
app = FastAPI(
    title="Hệ thống Tạo Câu hỏi Trắc nghiệm AI - Chuẩn Azota",
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

# ==========================================
# PHẦN 3: LÕI THUẬT TOÁN & XỬ LÝ DỮ LIỆU
# ==========================================

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
                for lvl in abstractNum.xpath('w:lvl'):
                    if lvl.get(qn('w:ilvl')) == str(ilvl):
                        numFmt_el = lvl.xpath('w:numFmt')
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

def split_option_and_leading_text(text: str) -> tuple[str, str]:
    """Tách phần văn bản thuộc về đáp án và phần tiêu đề/context của câu tiếp theo."""
    lines = text.split('\n')
    opt_lines = []
    leading_lines = []
    found_leading = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        if found_leading:
            leading_lines.append(line)
            continue
            
        if not stripped:
            opt_lines.append(line)
            continue
            
        # Heuristic nhận diện nhóm/context: Dấu hiệu từ khóa hoặc đoạn văn bản riêng biệt
        is_keyword = bool(re.match(r'^\s*(PHẦN|PART|CHƯƠNG|BÀI TẬP|TEST|PRACTICE|MỨC ĐỘ|DẠNG|I{1,3}\.|IV\.|V\.|VI{0,3}\.)\b', stripped, re.IGNORECASE))
        is_context_hint = bool(re.match(r'^\s*(Đọc đoạn|Đọc văn bản|Read the|Based on|Dựa vào|Cho đoạn|Cho bảng|Mark the|Choose the|Indicate the|Find the|Identify the|Complete the|Select the)\b', stripped, re.IGNORECASE))
        is_new_block = (i > 0 and not lines[i-1].strip() and len(stripped) > 10)
        
        if is_keyword or is_context_hint or is_new_block:
            found_leading = True
            leading_lines.append(line)
        else:
            opt_lines.append(line)
            
    return '\n'.join(opt_lines).strip(), '\n'.join(leading_lines).strip()

def evaluate_correct_answer(options: List[Dict], full_text: str, format_weights: List[int]) -> str:
    """
    So sánh trọng số giữa 4 đáp án (A,B,C,D) để lọc ra đáp án chính xác nhất dựa trên định dạng.
    """
    # 1. Kiểm tra nếu có đáp án nào được đánh dấu * (Ưu tiên tuyệt đối)
    for opt in options:
        if opt.get('is_asterisk'):
            opt_part, _ = split_option_and_leading_text(opt['text'])
            return f"{opt['char']}. {opt_part}"
            
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
            opt_part, _ = split_option_and_leading_text(opt['text'])
            best_option_text = f"{opt['char']}. {opt_part}"
            
    if best_score <= 0:
        return None
        
    return best_option_text

def extract_formatting_from_docx(file_path: str) -> List[Dict[str, Any]]:
    """Thuật toán phân tách Câu hỏi trắc nghiệm chuẩn Azota siêu tốc và thông minh."""
    doc = Document(file_path)
    full_text = ""
    format_weights = []
    
    counters = {'q': 0, 'opt': 0}
    
    # BƯỚC 1: Quét tài liệu, ánh xạ văn bản và trọng số định dạng
    for para in doc.paragraphs:
        if not para.text.strip():
            full_text += "\n"
            format_weights.append(0)
            continue
            
        prefix = get_auto_numbering_prefix(para, doc, counters)
        if prefix:
            para_text_strip = para.text.strip()
            is_numbering_text = re.match(r'^\s*(Câu|Bài|Question|Q|\d+[\.\:\)]|\*?\s*[A-F][\.\:\)])', para_text_strip, re.IGNORECASE)
            is_group_title = re.match(r'^\s*(PHẦN|PART|CHƯƠNG|BÀI TẬP|TEST|PRACTICE|MỨC ĐỘ|DẠNG|I{1,3}\.|IV\.|V\.|VI{0,3}\.)\b', para_text_strip, re.IGNORECASE)
            
            if not is_numbering_text and not is_group_title:
                full_text += prefix
                format_weights.extend([0] * len(prefix))
                
        for run in para.runs:
            run_text = run.text
            if not run_text: continue
            
            is_bold = run.bold
            is_underline = run.underline
            
            is_red = False
            if run.font.color and run.font.color.rgb:
                rgb_str = str(run.font.color.rgb).upper()
                if rgb_str in ['FF0000', 'C00000', 'ED1C24', 'RED']:
                    is_red = True
                    
            is_highlight = run.font.highlight_color is not None and run.font.highlight_color != 0
            
            weight = 0
            if is_red or is_highlight:
                weight = 3  
            elif is_underline:
                weight = 2  
            elif is_bold:
                weight = 1  
                
            full_text += run_text
            format_weights.extend([weight] * len(run_text))
            
        full_text += "\n"
        format_weights.append(0)

    # BƯỚC 2: Phân tách bằng State Machine (Máy trạng thái) kết hợp Regex siêu chuẩn
    # Xóa bỏ \s* ở cuối để không nuốt khoảng trắng của đáp án A. Dùng lookbehind (?<=) cho các trường hợp viết dính liền (1.A.)
    q_regex = r'(?:^|\n)\s*(?:Câu|Bài|Question|Q)\s*\d+\s*[\.\:\-\)]|(?:^|\n)\s*\d+\s*[\.\:\)]'
    opt_regex = r'(?:^|\s+|(?<=[\.\:\-]))(\*?\s*[A-F])[\.\:\)]'
    token_pattern = re.compile(f'({q_regex})|({opt_regex})', re.IGNORECASE)
    
    matches = list(token_pattern.finditer(full_text))
    if not matches: return []

    extracted_data = []
    current_q_text = ""
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
                opt_part, lead_part = split_option_and_leading_text(text_between)
                options[-1]['text'] += opt_part
                options[-1]['end_idx'] = match_start - len(lead_part)
                
                correct_ans = evaluate_correct_answer(options, full_text, format_weights)
                
                q_text_clean = current_q_text.strip()
                    
                extracted_data.append({
                    "group_title": shared_context,
                    "question": q_text_clean,
                    "options": [f"{opt['char']}. {split_option_and_leading_text(opt['text'])[0]}" for opt in options],
                    "correct_answer": correct_ans
                })
                
                if lead_part:
                    shared_context = lead_part
                    
                # Kế thừa ngữ cảnh (Phần I, đoạn văn...) vào câu tiếp theo
                current_q_text = lead_part + "\n" if lead_part else ""
            elif state == "OUTSIDE":
                _, lead_part = split_option_and_leading_text(text_between)
                if lead_part:
                    shared_context = lead_part
                current_q_text = text_between + "\n"
            else:
                current_q_text += text_between + "\n"
                
            # Cố tình loại bỏ phần chữ "Câu X:" (m.group(1)) để web tự động điền lại STT đúng
            options = []
            state = "IN_QUESTION"
            
        elif is_option:
            char_raw = m.group(3).upper() if m.group(3) else 'A'
            is_asterisk = '*' in char_raw
            char = char_raw.replace('*', '').strip()
            
            if state == "IN_QUESTION":
                current_q_text += text_between
            elif state == "IN_OPTION" and options:
                options[-1]['text'] += text_between
                options[-1]['end_idx'] = match_start
                
            state = "IN_OPTION"
            options.append({
                'char': char,
                'start_idx': m.start(3) if m.start(3) != -1 else match_start,
                'text': "",
                'marker_end': match_end,
                'is_asterisk': is_asterisk
            })
            
        last_idx = match_end
        
    if state == "IN_OPTION" and options:
        text_between = full_text[last_idx:]
        opt_part, lead_part = split_option_and_leading_text(text_between)
        options[-1]['text'] += opt_part
        options[-1]['end_idx'] = len(full_text) - len(lead_part)
        
        correct_ans = evaluate_correct_answer(options, full_text, format_weights)
        
        q_text_clean = current_q_text.strip()
            
        extracted_data.append({
            "group_title": shared_context,
            "question": q_text_clean,
            "options": [f"{opt['char']}. {split_option_and_leading_text(opt['text'])[0]}" for opt in options],
            "correct_answer": correct_ans
        })

    return extracted_data

def parse_docx_to_marked_text(file_path: str) -> str:
    """Đánh dấu thẻ <MARK> cho các từ in đậm/đỏ để gửi lên AI"""
    doc = Document(file_path)
    full_text = []
    counters = {'q': 0, 'opt': 0}
    
    for para in doc.paragraphs:
        if not para.text.strip():
            full_text.append("\n")
            continue
        
        para_text = ""
        prefix = get_auto_numbering_prefix(para, doc, counters)
        if prefix:
            para_text_strip = para.text.strip()
            is_numbering_text = re.match(r'^\s*(Câu|Bài|Question|Q|\d+[\.\:\)]|\*?\s*[A-F][\.\:\)])', para_text_strip, re.IGNORECASE)
            is_group_title = re.match(r'^\s*(PHẦN|PART|CHƯƠNG|BÀI TẬP|TEST|PRACTICE|MỨC ĐỘ|DẠNG|I{1,3}\.|IV\.|V\.|VI{0,3}\.)\b', para_text_strip, re.IGNORECASE)
            if not is_numbering_text and not is_group_title:
                para_text += prefix
                
        for run in para.runs:
            is_highlighted = run.font.highlight_color is not None and run.font.highlight_color != 0
            is_red_text = run.font.color and run.font.color.rgb and str(run.font.color.rgb) == 'FF0000'
            
            if run.bold or run.underline or is_highlighted or is_red_text:
                para_text += f"<MARK>{run.text}</MARK>"
            else:
                para_text += run.text
        full_text.append(para_text)
    return "\n".join(full_text)

def call_gemini_with_fallback(prompt: str, api_keys: List[str]):
    """Gọi Gemini AI với cơ chế chuyển giao giữa nhiều Key và nhiều Model"""
    if not api_keys:
        raise Exception("Hệ thống chưa được cấu hình API Key.")
        
    models_to_try = [
        'gemini-3.1-flash-lite',
        'gemini-3-flash',
        'gemini-2.5-flash-lite',
        'gemini-2.5-flash',
        'gemini-1.5-flash'
    ]
    last_error = None
    
    for key in api_keys:
        key = key.strip()
        if not key: continue
        genai.configure(api_key=key)
        
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
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
    1. Trích xuất câu hỏi và 4 đáp án (A, B, C, D).
    2. Đáp án đúng là đáp án chứa nội dung nằm trong thẻ <MARK> HOẶC có dấu * ở trước chữ cái đáp án (ví dụ *A, *B).
    3. Loại bỏ thẻ <MARK> và dấu * ra khỏi kết quả cuối cùng.
    4. Định dạng trả về bắt buộc là JSON array RẤT NGHIÊM NGẶT.
    Ví dụ: [{{"group_title": "Đọc đoạn văn...", "question": "Q1?", "options": ["A. 1", "B. 2", "C. 3", "D. 4"], "correct_answer": "A. 1"}}]
    
    Văn bản:
    {marked_text}
    """
    response = call_gemini_with_fallback(prompt, api_keys)
            
    match = re.search(r'\[\s*\{.*\}\s*\]', response.text, re.DOTALL)
    if match: return json.loads(match.group(0))
    return json.loads(response.text)


# ==========================================
# PHẦN 4: GIAO DIỆN & API ENDPOINTS
# ==========================================

@app.get("/")
async def root():
    return {"status": "success", "message": "Backend API is running!"}

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
        quiz_id = str(uuid.uuid4())
        
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
    return {"status": "success", "quiz_id": quiz_id, "link": f"/?quiz_id={quiz_id}"}

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
            
        return {
            "status": "success", 
            "title": quiz_data.get('title'), 
            "data": quiz_data.get('data'), 
            "mode": quiz_data.get('mode', 'practice'), 
            "time_limit": quiz_data.get('time_limit', 0),
            "is_shuffle": quiz_data.get('is_shuffle', False)
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
async def check_quiz_ai(req: CheckQuizRequest):
    if db is None: raise HTTPException(status_code=500, detail="Lỗi DB")
    teacher_doc = db.collection('users').document(req.teacher_token).get()
    if not teacher_doc.exists or teacher_doc.to_dict().get('role') not in ['teacher', 'admin']:
        raise HTTPException(status_code=403, detail="Không có quyền")
        
    settings_doc = db.collection('settings').document('gemini').get()
    if not settings_doc.exists or not settings_doc.to_dict().get('api_keys'):
        raise HTTPException(status_code=400, detail="Quản trị viên chưa cấu hình Gemini API Key chung. Vui lòng liên hệ Admin.")
    api_keys = settings_doc.to_dict().get('api_keys')
    
    try:
        prompt = f"""
        Bạn là một chuyên gia giáo dục và biên tập viên kiểm định đề thi trắc nghiệm.
        Hãy rà soát kỹ lưỡng danh sách câu hỏi trắc nghiệm dưới đây và phát hiện các lỗi sau:
        1. Lỗi chính tả, dư thừa chữ, sai ngữ pháp, văn phong lủng củng.
        2. Lỗi ngữ cảnh, câu hỏi bị thiếu dữ kiện, hoặc nội dung không hợp lý.
        3. Sai đáp án (nếu dựa vào kiến thức phổ thông bạn phát hiện đáp án được chọn không chính xác).
        4. Lỗi định dạng/bóc tách: Chữ bị dính liền nhau (lỗi dính chữ), tiêu đề/đoạn văn bị dính vào phần đáp án, hoặc lỗi font chữ gây khó đọc.
        5. Các lỗi logic khác (ví dụ: các đáp án trùng lặp).
        
        Hãy liệt kê chi tiết: Chỉ đích danh "Câu [số]" mắc lỗi gì và đề xuất cách sửa đổi. Trình bày rõ ràng, dễ đọc. Nếu đề thi đã rất tốt, hãy xác nhận không có lỗi.
        Dữ liệu đề thi (JSON): {json.dumps(req.quiz_data, ensure_ascii=False)}
        """
        
        response = call_gemini_with_fallback(prompt, api_keys)
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
async def upload_document(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".docx":
        raise HTTPException(status_code=400, detail="Hệ thống chỉ đang hỗ trợ nhận diện trực tiếp qua file .docx")
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        shutil.copyfileobj(file.file, temp_file)
        temp_file_path = temp_file.name
        
    settings_doc = db.collection('settings').document('gemini').get() if db else None
    api_keys = settings_doc.to_dict().get('api_keys', []) if settings_doc and settings_doc.exists else []

    try:
        extracted_data = None
        if api_keys:
            marked_text = parse_docx_to_marked_text(temp_file_path)
            extracted_data = generate_mcq_with_gemini(marked_text, api_keys)
        else:
            extracted_data = extract_formatting_from_docx(temp_file_path)

        if not extracted_data:
             raise HTTPException(status_code=422, detail="Không thể trích xuất câu hỏi. Vui lòng đảm bảo cấu trúc file theo đúng chuẩn (A., B., C., D.)")

        return {
            "filename": file.filename,
            "status": "success",
            "message": "File đã được phân tích!",
            "data": extracted_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý hệ thống: {str(e)}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)