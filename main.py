import os
import re
import json
import sqlite3
import uuid
import tempfile
import shutil
from typing import List, Dict, Any, Generator

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from docx import Document
import google.generativeai as genai

# ==========================================
# PHẦN 1: CẤU HÌNH & QUẢN LÝ DATABASE
# ==========================================
DB_FILE = 'quizzes.db'

def init_db():
    """Khởi tạo cấu trúc CSDL nếu chưa tồn tại"""
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS quizzes (
                id TEXT PRIMARY KEY,
                title TEXT,
                data TEXT
            )
        ''')
        conn.commit()

def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Dependency Injection: Quản lý vòng đời của DB an toàn"""
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
    finally:
        conn.close()

init_db()

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
        marker_weight = format_weights[start_idx]
        if marker_weight == 3: score += 1000    # Đỏ/Highlight
        elif marker_weight == 2: score += 500   # Gạch chân
        elif marker_weight == 1: score += 100   # In đậm
        
        # 2. Đo lường Trọng số trải dài trên toàn bộ nội dung đáp án
        if content_start < content_end:
            content_weights = format_weights[content_start:content_end]
            alnum_count = sum(1 for i in range(content_start, content_end) if full_text[i].isalnum())
            
            if alnum_count > 0:
                # Đếm số ký tự chữ/số được định dạng
                formatted_chars = sum(1 for i, w in enumerate(content_weights) if w > 0 and full_text[content_start+i].isalnum())
                max_w = max(content_weights)
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
            best_option_text = f"{opt['char']}. {opt['text'].strip()}"
            
    if best_score <= 0:
        return None
        
    return best_option_text

def extract_formatting_from_docx(file_path: str) -> List[Dict[str, Any]]:
    """Thuật toán phân tách Câu hỏi trắc nghiệm chuẩn Azota."""
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
    html_content = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <title>Tạo & Chỉnh sửa Câu hỏi</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; background: #f4f7f6; max-width: 800px; margin: auto; }
            .header { text-align: center; margin-bottom: 20px; }
            .upload-box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; text-align: center; }
            .question-box { background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #007bff; }
            .option { margin: 8px 0; display: flex; align-items: center; }
            .option-practice { margin: 8px 0; padding: 10px; border: 1px solid #ccc; border-radius: 4px; cursor: pointer; display: flex; align-items: center; }
            .option-practice:hover { background-color: #f1f1f1; }
            .option-practice input { margin-right: 10px; }
            input[type="text"], textarea { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
            button { padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
            button:hover { background: #218838; }
            .mode-switch { text-align: center; margin-bottom: 20px; display: none; }
            .mode-switch button { margin: 0 10px; background: #6c757d; }
            .mode-switch button.active { background: #007bff; }
            .correct { background-color: #d4edda !important; border-color: #c3e6cb !important; color: #155724; font-weight: bold; }
            .incorrect { background-color: #f8d7da !important; border-color: #f5c6cb !important; color: #721c24; text-decoration: line-through; }
            #score-board { display: none; text-align: center; font-size: 24px; font-weight: bold; margin-bottom: 20px; color: #d32f2f; }
        </style>
    </head>
    <body>
        <div class="header">
            <h2>Hệ thống Luyện thi Trắc nghiệm</h2>
        </div>
        
        <div class="mode-switch" id="modeSwitch">
            <button id="btnEdit" class="active" onclick="switchMode('edit')">🛠 Chế độ Chỉnh sửa</button>
            <button id="btnPractice" onclick="switchMode('practice')"> Luyện tập (Từng câu)</button>
            <button id="btnExam" onclick="switchMode('exam')">📝 Kiểm tra (Tất cả)</button>
            <button id="btnShuffle" onclick="shuffleQuiz()" style="background: #17a2b8; display: none; color: white;">🔀 Trộn đề</button>
        </div>

        <div class="upload-box">
            <input type="password" id="apiKey" placeholder="Nhập Gemini API Key (Bỏ trống để dùng thuật toán chuẩn Azota)" style="width: 100%; padding: 10px; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;">
            <input type="file" id="fileInput" accept=".docx">
            <button onclick="uploadFile()">Tải file lên & Phân tích</button>
        </div>

        <input type="text" id="quizTitle" placeholder="Nhập tên bài kiểm tra (VD: Đề cương Lịch sử kỳ 1)..." style="display:none; margin-bottom: 20px; font-size: 18px; font-weight: bold; width: 100%; box-sizing: border-box; padding: 10px; border: 2px solid #007bff; border-radius: 4px;">
        <div id="score-board"></div>
        <div id="quiz-container"></div>
        
        <div style="text-align: center;">
            <button id="saveBtn" style="display:none; background:#007bff; width: 100%;" onclick="saveData()">Lưu Câu hỏi (Tạo Link Gửi Cho Học Sinh)</button>
            <button id="submitBtn" style="display:none; background:#28a745; width: 100%; margin-top: 10px;" onclick="submitExam()">Nộp bài & Chấm điểm</button>
        </div>

        <script>
            let currentData = [];
            let currentMode = 'edit';
            let currentQuestionIndex = 0;
            let practiceScore = 0;
            let practiceAnswered = false;

            window.onload = async function() {
                const urlParams = new URLSearchParams(window.location.search);
                const quizId = urlParams.get('quiz_id');
                if (quizId) {
                    document.querySelector('.upload-box').style.display = 'none';
                    document.getElementById('btnEdit').style.display = 'none'; 
                    document.getElementById('quiz-container').innerHTML = "<p style='text-align:center;'>Đang tải bài thi...</p>";
                    try {
                        const response = await fetch('/api/get_quiz/' + quizId);
                        const result = await response.json();
                        if (result.status === 'success') {
                            currentData = result.data;
                            document.querySelector('.header h2').innerText = result.title;
                            document.getElementById('modeSwitch').style.display = 'block';
                            switchMode('practice'); 
                        } else { document.getElementById('quiz-container').innerHTML = "<p style='text-align:center;'>Bài thi không tồn tại.</p>"; }
                    } catch (e) {
                        document.getElementById('quiz-container').innerHTML = "<p style='text-align:center;'>Lỗi kết nối máy chủ.</p>";
                    }
                }
            };

            async function uploadFile() {
                const fileInput = document.getElementById('fileInput');
                if (!fileInput.files[0]) { alert("Vui lòng chọn file .docx!"); return; }
                
                const formData = new FormData();
                formData.append("api_key", document.getElementById('apiKey').value.trim());
                formData.append("file", fileInput.files[0]);
                document.getElementById('quiz-container').innerHTML = "<p style='text-align:center;'>Hệ thống đang bóc tách câu hỏi... Vui lòng đợi.</p>";

                try {
                    const response = await fetch('/api/upload', { method: 'POST', body: formData });
                    const result = await response.json();
                    if (result.status === "success") {
                        currentData = result.data || [];
                        renderData();
                    } else { alert("Lỗi: " + result.detail); }
                } catch (e) { alert("Lỗi kết nối máy chủ!"); }
            }

            function renderData() {
                const container = document.getElementById('quiz-container');
                container.innerHTML = '';
                if (currentData.length === 0) { container.innerHTML = "<p>Không tìm thấy câu hỏi nào. Vui lòng kiểm tra lại định dạng file Word.</p>"; return; }
                
                document.getElementById('score-board').style.display = 'none';
                
                if (currentMode === 'practice') {
                    renderPracticeQuestion();
                    return;
                }

                currentData.forEach((q, qIndex) => {
                    const box = document.createElement('div');
                    box.className = 'question-box';
                    box.id = `question_box_${qIndex}`;
                    
                    if (currentMode === 'edit') {
                        box.innerHTML += `<label><b>Câu hỏi ${qIndex + 1}:</b></label>
                                          <textarea rows="3" onchange="updateQ(${qIndex}, this.value)">${q.question}</textarea>`;
                        box.innerHTML += `<label style="display:block; margin-top:10px;"><b>Các đáp án (Chọn nút tròn để đổi đáp án đúng):</b></label>`;
                        q.options.forEach((opt, oIndex) => {
                            const isCorrect = q.correct_answer === opt;
                            box.innerHTML += `
                                <div class="option">
                                    <input type="radio" name="correct_${qIndex}" ${isCorrect ? 'checked' : ''} onchange="updateCorrect(${qIndex}, ${oIndex})">
                                    <input type="text" value="${opt}" onchange="updateOpt(${qIndex}, ${oIndex}, this.value)" style="margin-left:10px;">
                                </div>`;
                        });
                    } else {
                        box.innerHTML += `<h4>Câu ${qIndex + 1}: ${q.question.replace(/\\n/g, '<br>')}</h4>`;
                        q.options.forEach((opt, oIndex) => {
                            box.innerHTML += `
                                <label class="option-practice" id="exam_opt_${qIndex}_${oIndex}">
                                    <input type="radio" name="exam_${qIndex}" value="${opt}">
                                    ${opt.replace(/^[A-D][\.\:\)]\s*/i, '')}
                                </label>`;
                        });
                    }
                    container.appendChild(box);
                });
                
                document.getElementById('quizTitle').style.display = currentMode === 'edit' ? 'block' : 'none';
                document.getElementById('saveBtn').style.display = currentMode === 'edit' ? 'block' : 'none';
                document.getElementById('submitBtn').style.display = currentMode === 'exam' ? 'block' : 'none';
            }
            
            function renderPracticeQuestion() {
                const container = document.getElementById('quiz-container');
                container.innerHTML = '';
                
                if (currentQuestionIndex >= currentData.length) {
                    document.getElementById('score-board').style.display = 'block';
                    document.getElementById('score-board').innerHTML = `Hoàn thành luyện tập! Bạn đúng ${practiceScore} / ${currentData.length} câu. 🎉<br><button onclick="switchMode('practice')" style="margin-top:15px; background:#007bff; color:white; border:none; padding:10px 20px; border-radius:4px; cursor:pointer;">Luyện tập lại vòng nữa</button>`;
                    return;
                }

                practiceAnswered = false;
                const q = currentData[currentQuestionIndex];
                const box = document.createElement('div');
                box.className = 'question-box';
                
                box.innerHTML += `<h4>Câu ${currentQuestionIndex + 1} / ${currentData.length}: ${q.question.replace(/\\n/g, '<br>')}</h4>`;
                
                q.options.forEach((opt, oIndex) => {
                    box.innerHTML += `
                        <label class="option-practice" id="pract_opt_${oIndex}">
                            <input type="radio" name="pract_radio" onclick="checkPracticeAnswer(${oIndex})">
                            ${opt.replace(/^[A-D][\.\:\)]\s*/i, '')}
                        </label>`;
                });
                
                box.innerHTML += `<div id="pract_feedback" style="margin-top:15px; font-weight:bold; font-size:18px;"></div>`;
                box.innerHTML += `<button id="nextBtn" style="display:none; margin-top:15px; background:#17a2b8;" onclick="nextPracticeQuestion()">Câu tiếp theo ➔</button>`;
                
                container.appendChild(box);
            }

            function checkPracticeAnswer(oIndex) {
                if (practiceAnswered) return;
                practiceAnswered = true;
                
                const q = currentData[currentQuestionIndex];
                const isCorrect = q.options[oIndex] === q.correct_answer;
                
                if (isCorrect) practiceScore++;
                
                q.options.forEach((opt, idx) => {
                    const lbl = document.getElementById(`pract_opt_${idx}`);
                    lbl.querySelector('input').disabled = true;
                    if (opt === q.correct_answer) lbl.classList.add('correct');
                    else if (idx === oIndex && !isCorrect) lbl.classList.add('incorrect');
                });
                
                const feedback = document.getElementById('pract_feedback');
                let correctAnswerDisplay = q.correct_answer ? q.correct_answer.replace(/^[A-D][\.\:\)]\s*/i, '') : "Chưa xác định";
                feedback.innerHTML = isCorrect ? `<span style="color:#28a745;">✅ Chính xác!</span>` : `<span style="color:#dc3545;">❌ Sai rồi! Đáp án đúng là: ${correctAnswerDisplay}</span>`;
                
                document.getElementById('nextBtn').style.display = 'block';
                if (currentQuestionIndex === currentData.length - 1) document.getElementById('nextBtn').innerText = 'Xem kết quả tổng kết';
            }
            
            function nextPracticeQuestion() {
                currentQuestionIndex++;
                renderPracticeQuestion();
            }
            
            function shuffleQuiz() {
                for (let i = currentData.length - 1; i > 0; i--) {
                    const j = Math.floor(Math.random() * (i + 1));
                    [currentData[i], currentData[j]] = [currentData[j], currentData[i]];
                }
                currentData.forEach(q => {
                    for (let i = q.options.length - 1; i > 0; i--) {
                        const j = Math.floor(Math.random() * (i + 1));
                        [q.options[i], q.options[j]] = [q.options[j], q.options[i]];
                    }
                });
                currentQuestionIndex = 0;
                practiceScore = 0;
                renderData();
            }

            function switchMode(mode) {
                currentMode = mode;
                document.getElementById('btnEdit').className = mode === 'edit' ? 'active' : '';
                document.getElementById('btnPractice').className = mode === 'practice' ? 'active' : '';
                document.getElementById('btnExam').className = mode === 'exam' ? 'active' : '';
                document.getElementById('btnShuffle').style.display = mode === 'edit' ? 'none' : 'inline-block';
                currentQuestionIndex = 0;
                practiceScore = 0;
                renderData();
            }

            function updateQ(qIndex, value) { currentData[qIndex].question = value; }
            function updateOpt(qIndex, oIndex, value) {
                if (currentData[qIndex].correct_answer === currentData[qIndex].options[oIndex]) { currentData[qIndex].correct_answer = value; }
                currentData[qIndex].options[oIndex] = value; 
            }
            function updateCorrect(qIndex, oIndex) { currentData[qIndex].correct_answer = currentData[qIndex].options[oIndex]; }

            async function saveData() {
                const title = document.getElementById('quizTitle').value.trim() || "Bài kiểm tra không tên";
                document.getElementById('saveBtn').innerText = "Đang lưu...";
                try {
                    const response = await fetch('/api/save_quiz', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ title: title, data: currentData })
                    });
                    const result = await response.json();
                    if (result.status === 'success') {
                        const shareLink = window.location.origin + result.link;
                        prompt("Lưu thành công! Copy đường link bên dưới để gửi cho học sinh/lớp:", shareLink);
                    }
                } catch (e) { alert("Lỗi khi lưu bài!"); }
                document.getElementById('saveBtn').innerText = "Lưu Câu hỏi (Tạo Link Gửi Cho Học Sinh)";
            }
            
            function submitExam() {
                let score = 0;
                currentData.forEach((q, qIndex) => {
                    const selected = document.querySelector(`input[name="exam_${qIndex}"]:checked`);
                    const userAnswer = selected ? selected.value : null;
                    
                    q.options.forEach((opt, oIndex) => {
                        document.getElementById(`exam_opt_${qIndex}_${oIndex}`).classList.remove('correct', 'incorrect');
                    });
                    
                    q.options.forEach((opt, oIndex) => {
                        if (opt === q.correct_answer) {
                            document.getElementById(`exam_opt_${qIndex}_${oIndex}`).classList.add('correct');
                        } else if (opt === userAnswer && userAnswer !== q.correct_answer) {
                            document.getElementById(`exam_opt_${qIndex}_${oIndex}`).classList.add('incorrect');
                        }
                    });
                    
                    if (userAnswer === q.correct_answer) score++;
                });
                
                const scoreBoard = document.getElementById('score-board');
                scoreBoard.style.display = 'block';
                scoreBoard.innerHTML = `Bạn làm đúng ${score} / ${currentData.length} câu! 🎉`;
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/api/save_quiz", summary="Lưu bài thi và lấy link")
async def save_quiz(request: SaveQuizRequest, db: sqlite3.Connection = Depends(get_db)):
    quiz_id = str(uuid.uuid4())
    cursor = db.cursor()
    cursor.execute('INSERT INTO quizzes (id, title, data) VALUES (?, ?, ?)',
                   (quiz_id, request.title, json.dumps(request.data, ensure_ascii=False)))
    db.commit()
    return {"status": "success", "quiz_id": quiz_id, "link": f"/?quiz_id={quiz_id}"}

@app.get("/api/get_quiz/{quiz_id}", summary="Lấy dữ liệu bài thi qua ID")
async def get_quiz(quiz_id: str, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute('SELECT title, data FROM quizzes WHERE id = ?', (quiz_id,))
    row = cursor.fetchone()
    if row:
        return {"status": "success", "title": row[0], "data": json.loads(row[1])}
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