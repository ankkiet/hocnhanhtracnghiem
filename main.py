import os
import re
import json
import uuid
import tempfile
import shutil
from typing import List, Dict, Any

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from docx import Document
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

class SaveQuizRequest(BaseModel):
    title: str
    data: list

# ==========================================
# PHẦN 3: LÕI THUẬT TOÁN & XỬ LÝ DỮ LIỆU
# ==========================================

def clean_option_text(text: str) -> str:
    """Xóa các tiêu đề nhóm/phần (thường dính vào cuối đáp án) để tránh rác dữ liệu."""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        # Nếu gặp dòng nghi ngờ là Tiêu đề nhóm -> dừng lấy văn bản đáp án
        if re.match(r'^\s*(PHẦN|PART|CHƯƠNG|BÀI TẬP|TEST|PRACTICE|MỨC ĐỘ|DẠNG|I{1,3}\.|IV\.|V\.|VI{0,3}\.)\b', line, re.IGNORECASE):
            break
        cleaned.append(line)
    return '\n'.join(cleaned).strip()

def evaluate_correct_answer(options: List[Dict], full_text: str, format_weights: List[int]) -> str:
    """
    So sánh trọng số giữa 4 đáp án (A,B,C,D) để lọc ra đáp án chính xác nhất dựa trên định dạng.
    """
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
            best_option_text = f"{opt['char']}. {clean_option_text(opt['text'])}"
            
    if best_score <= 0:
        return None
        
    return best_option_text

def extract_formatting_from_docx(file_path: str) -> List[Dict[str, Any]]:
    """Thuật toán phân tách Câu hỏi trắc nghiệm chuẩn Azota siêu tốc và thông minh."""
    doc = Document(file_path)
    full_text = ""
    format_weights = []
    
    # BƯỚC 1: Quét tài liệu, ánh xạ văn bản và trọng số định dạng
    for para in doc.paragraphs:
        if not para.text.strip():
            full_text += "\n"
            format_weights.append(0)
            continue
            
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

    # BƯỚC 2: Phân tách Câu hỏi và Đáp án bằng Regex
    pattern = re.compile(r'(?:^|\s|\n)([A-D])([\.\:\)])\s*')
    matches = list(pattern.finditer(full_text))
    
    if not matches: return []

    extracted_data = []
    current_q_text = ""
    options = []
    last_idx = 0
    
    for i, m in enumerate(matches):
        char = m.group(1)
        start_idx = m.start(1)
        text_before = full_text[last_idx:m.start()].strip()
        
        if char == 'A':
            if options:
                split_match = re.search(r'\n\s*(?:Câu|Bài)\s*\d+[\.\:\-]', text_before, re.IGNORECASE)
                if split_match:
                    last_opt_text = text_before[:split_match.start()].strip()
                    new_q_text = text_before[split_match.start():].strip()
                else:
                    last_opt_text = text_before
                    new_q_text = ""
                    
                options[-1]['text'] += " " + last_opt_text
                options[-1]['end_idx'] = last_idx + len(last_opt_text)
                
                correct_ans = evaluate_correct_answer(options, full_text, format_weights)
                
                extracted_data.append({
                    "question": current_q_text.strip(),
                    "options": [f"{opt['char']}. {opt['text'].strip()}" for opt in options],
                    "correct_answer": correct_ans
                })
                current_q_text = new_q_text
                options = []
            else:
                current_q_text += " " + text_before
        else:
            if options:
                options[-1]['text'] += " " + text_before
                options[-1]['end_idx'] = m.start()
            else:
                current_q_text += " " + text_before
                
        options.append({
            'char': char,
            'start_idx': start_idx,
            'text': "",
            'marker_end': m.end()
        })
        last_idx = m.end()
        
    if options:
        options[-1]['text'] += " " + full_text[last_idx:].strip()
        options[-1]['end_idx'] = len(full_text)
        correct_ans = evaluate_correct_answer(options, full_text, format_weights)
        extracted_data.append({
            "question": current_q_text.strip(),
            "options": [f"{opt['char']}. {opt['text'].strip()}" for opt in options],
            "correct_answer": correct_ans
        })

    return extracted_data

def parse_docx_to_marked_text(file_path: str) -> str:
    """Đánh dấu thẻ <MARK> cho các từ in đậm/đỏ để gửi lên AI"""
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        if not para.text.strip():
            full_text.append("\n")
            continue
        
        para_text = ""
        for run in para.runs:
            is_highlighted = run.font.highlight_color is not None and run.font.highlight_color != 0
            is_red_text = run.font.color and run.font.color.rgb and str(run.font.color.rgb) == 'FF0000'
            
            if run.bold or run.underline or is_highlighted or is_red_text:
                para_text += f"<MARK>{run.text}</MARK>"
            else:
                para_text += run.text
        full_text.append(para_text)
    return "\n".join(full_text)

def generate_mcq_with_gemini(marked_text: str, api_key: str) -> List[Dict[str, Any]]:
    """Dùng Gemini AI để bóc tách câu hỏi dựa trên văn bản đã gắn thẻ <MARK>"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Bạn là một chuyên gia giáo dục. Nhiệm vụ của bạn là trích xuất câu hỏi từ văn bản dưới đây.
    1. Trích xuất câu hỏi và 4 đáp án (A, B, C, D).
    2. Đáp án đúng là đáp án chứa nội dung nằm trong thẻ <MARK>.
    3. Loại bỏ thẻ <MARK> ra khỏi kết quả cuối cùng.
    4. Định dạng trả về bắt buộc là JSON array RẤT NGHIÊM NGẶT.
    Ví dụ: [{{"question": "Q1?", "options": ["A. Lựa chọn 1", "B. 2", "C. 3", "D. 4"], "correct_answer": "A. Lựa chọn 1"}}]
    
    Văn bản:
    {marked_text}
    """
    response = model.generate_content(prompt)
    match = re.search(r'\[\s*\{.*\}\s*\]', response.text, re.DOTALL)
    if match: return json.loads(match.group(0))
    return json.loads(response.text)


# ==========================================
# PHẦN 4: GIAO DIỆN & API ENDPOINTS
# ==========================================

@app.get("/")
async def root():
    return {"status": "success", "message": "Backend API is running!"}

@app.post("/api/save_quiz", summary="Lưu bài thi và lấy link")
async def save_quiz(request: SaveQuizRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
    quiz_id = str(uuid.uuid4())
    doc_ref = db.collection('quizzes').document(quiz_id)
    doc_ref.set({
        'title': request.title,
        'data': request.data  # Lưu trực tiếp dạng array/dict không cần json.dumps
    })
    return {"status": "success", "quiz_id": quiz_id, "link": f"/?quiz_id={quiz_id}"}

@app.get("/api/get_quiz/{quiz_id}", summary="Lấy dữ liệu bài thi qua ID")
async def get_quiz(quiz_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
    doc_ref = db.collection('quizzes').document(quiz_id)
    doc = doc_ref.get()
    if doc.exists:
        quiz_data = doc.to_dict()
        return {"status": "success", "title": quiz_data.get('title'), "data": quiz_data.get('data')}
    raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")

@app.post("/api/upload", summary="Tải lên và phân tích file DOCX")
async def upload_document(file: UploadFile = File(...), api_key: str = Form(None)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".docx":
        raise HTTPException(status_code=400, detail="Hệ thống chỉ đang hỗ trợ nhận diện trực tiếp qua file .docx")
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        shutil.copyfileobj(file.file, temp_file)
        temp_file_path = temp_file.name

    try:
        extracted_data = None
        if api_key:
            # Dùng AI nếu có nhập mã Key
            marked_text = parse_docx_to_marked_text(temp_file_path)
            extracted_data = generate_mcq_with_gemini(marked_text, api_key)
        else:
            # Dùng thuật toán chuẩn Azota siêu tốc (Mặc định)
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