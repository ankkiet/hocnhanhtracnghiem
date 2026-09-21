import re
import json
import asyncio
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import json_repair
except ImportError:
    json_repair = None

def fix_json_latex_escapes(json_str: str) -> str:
    """Sửa lỗi LLM trả về các ký tự LaTeX (như \\frac, \\rightarrow) bị parser JSON hiểu nhầm thành ký tự escape."""
    return re.sub(r'(?<!\\)\\(?!["\\/])', r'\\\\', json_str)

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

async def call_gemini_with_fallback(prompt: str, api_keys: List[str]):
    """Gọi Gemini AI sử dụng Google GenAI SDK mới nhất với cơ chế luân chuyển Key và Model."""
    if not api_keys:
        raise Exception("Hệ thống chưa được cấu hình API Key.")
        
    models_to_try = [
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-1.5-flash'
    ]
    last_error = None
    
    for key in api_keys:
        key = key.strip()
        if not key:
            continue
            
        try:
            client = genai.Client(api_key=key)
        except Exception as e:
            last_error = e
            continue
            
        for model_name in models_to_try:
            try:
                # Sử dụng client.aio cho async
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json"
                    )
                )
                return response
            except Exception as e:
                error_str = str(e).lower()
                if "api key not valid" in error_str or "invalid api key" in error_str:
                    last_error = e
                    break
                elif "404" in error_str or "not found" in error_str or "unsupported" in error_str:
                    last_error = e
                    continue
                elif "429" in error_str or "quota" in error_str or "503" in error_str or "overloaded" in error_str:
                    last_error = e
                    await asyncio.sleep(1)
                    break
                elif "deadline" in error_str or "timeout" in error_str:
                    last_error = Exception("AI xử lý quá lâu và bị ngắt kết nối (timeout).")
                    continue
                else:
                    last_error = e
                    continue
                    
    raise Exception(f"Tất cả các Key và Model đều thất bại. Lỗi cuối: {str(last_error)}")

async def generate_mcq_with_gemini(marked_text: str, api_keys: List[str], task_id: str = None, active_tasks: dict = None) -> List[Dict[str, Any]]:
    """Dùng Gemini AI để bóc tách câu hỏi dựa trên văn bản đã gắn thẻ <MARK>."""
    chunks = chunk_marked_text(marked_text, questions_per_chunk=15)
    all_extracted_data = []
    
    async def process_chunk(idx, chunk):
        if not chunk.strip():
            return None
        if active_tasks is not None and task_id and task_id in active_tasks:
            active_tasks[task_id]["message"] = f"AI đang bóc tách phần {idx + 1}/{len(chunks)}..."
            
        prompt = f"""
        Bạn là một chuyên gia giáo dục. Nhiệm vụ của bạn là trích xuất câu hỏi từ văn bản dưới đây.
        (Đây là phần {idx + 1}/{len(chunks)} của tài liệu).
        1. Trích xuất câu hỏi và 4 đáp án (A, B, C, D). Tuyệt đối LOẠI BỎ chữ "Câu X:", "Bài X:" hoặc số thứ tự ở đầu câu hỏi.
        2. CHÚ Ý QUAN TRỌNG: Hãy tinh ý tách các đáp án A, B, C, D ra riêng biệt nếu chúng bị dính liền trên cùng một dòng.
        3. Đáp án đúng là đáp án chứa nội dung nằm trong thẻ <MARK> HOẶC có dấu * ở trước chữ cái đáp án (ví dụ *A, *B). Loại bỏ thẻ <MARK> và dấu * ra khỏi kết quả cuối cùng.
        4. GIỮ NGUYÊN TOÀN BỘ các thẻ định dạng HTML (như <b>, <i>, <u>, <sub>, <sup>). KHÔNG tự ý chuyển sang Markdown. TUYỆT ĐỐI KHÔNG ĐƯỢC XÓA BỎ các thẻ [IMG_X] (ví dụ [IMG_1], [IMG_2]). PHẢI GIỮ NGUYÊN CHÚNG TRONG NỘI DUNG.
        5. Các công thức Toán/Lý/Hóa đã được bọc sẵn trong thẻ \\( và \\). Dữ liệu này ĐÃ ĐƯỢC ESCAPE SẴN DẤU BACKSLASH (ví dụ \\frac, \\sqrt, \\rightarrow). BẠN PHẢI GIỮ NGUYÊN ĐỊNH DẠNG NÀY KHI TRẢ VỀ JSON. Bắt buộc phải có 2 dấu backslash (\\\\) trong chuỗi JSON.
        6. Định dạng trả về bắt buộc là JSON array RẤT NGHIÊM NGẶT.
        Ví dụ: [{{"group_title": "Đọc đoạn văn...", "question": "Hình sau [IMG_1] là gì? Tính \\\\(x^2\\\\)", "options": ["A. <i>Có</i>", "B. Không", "C. 1", "D. 2"], "correct_answer": "A. <i>Có</i>"}}]
        
        Văn bản:
        {chunk}
        """
        try:
            response = await call_gemini_with_fallback(prompt, api_keys)
            match = re.search(r'\[\s*\{.*\}\s*\]', response.text, re.DOTALL)
            json_text = match.group(0) if match else response.text
            json_text = fix_json_latex_escapes(json_text)
            
            if json_repair is not None:
                parsed_json = json_repair.loads(json_text)
            else:
                parsed_json = json.loads(json_text, strict=False)
                
            if isinstance(parsed_json, list):
                return parsed_json
            return None
        except Exception as e:
            print(f"Lỗi khi xử lý chunk {idx + 1}: {e}")
            return None

    tasks = [process_chunk(idx, chunk) for idx, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks)
    
    for res in results:
        if res:
            all_extracted_data.extend(res)

    if not all_extracted_data and any(c.strip() for c in chunks):
        raise Exception("AI không thể trích xuất bất kỳ câu hỏi nào từ tài liệu.")

    return all_extracted_data

async def generate_mcq_from_pdf(pdf_path: str, api_keys: List[str], task_id: str = None, active_tasks: dict = None) -> List[Dict[str, Any]]:
    """Dùng PyMuPDF bóc tách text chính xác 100% sau đó đưa cho AI xử lý theo từng khối (Chunk)."""
    if not api_keys:
        raise Exception("Hệ thống chưa được cấu hình API Key.")
        
    if fitz is None:
        raise Exception("Thư viện PyMuPDF chưa được cài đặt.")
        
    doc = fitz.open(pdf_path)
    pdf_text = ""
    for page in doc:
        pdf_text += page.get_text("text") + "\n"
    doc.close()
    
    return await generate_mcq_with_gemini(pdf_text, api_keys, task_id, active_tasks)
