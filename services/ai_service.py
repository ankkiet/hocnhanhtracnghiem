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

# Bộ nhớ đệm Client để tái sử dụng kết nối (Connection Pooling), tránh TLS handshake lặp lại
_client_pool: Dict[str, genai.Client] = {}

def get_gemini_client(api_key: str) -> genai.Client:
    """Lấy client từ pool hoặc tạo mới nếu chưa tồn tại."""
    global _client_pool
    key_clean = api_key.strip()
    if key_clean not in _client_pool:
        _client_pool[key_clean] = genai.Client(api_key=key_clean)
    return _client_pool[key_clean]

def fix_json_latex_escapes(json_str: str) -> str:
    """Sửa lỗi LLM trả về các ký tự LaTeX (như \\frac, \\rightarrow) bị parser JSON hiểu nhầm thành ký tự escape."""
    return re.sub(r'(?<!\\)\\(?!["\\/])', r'\\\\', json_str)

def normalize_question_data(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chuẩn hóa dữ liệu câu hỏi trắc nghiệm:
    - Đảm bảo các đáp án có tiền tố A., B., C., D. chuẩn mực, không bị trùng (vd: A. A. -> A.)
    - Đảm bảo correct_answer khớp chính xác với 1 trong các đáp án
    - Đảm bảo có trường explain (lời giải chi tiết)
    """
    if not isinstance(item, dict):
        return item
        
    options = item.get("options", [])
    if not isinstance(options, list):
        options = []
        
    prefixes = ["A. ", "B. ", "C. ", "D. "]
    normalized_options = []
    for idx, opt in enumerate(options[:4]):
        opt_str = str(opt).strip()
        # Xóa tiền tố lặp như A. A. hoặc A) A.
        opt_str = re.sub(r'^[A-D]\s*[\.\:\-\)]\s*([A-D]\s*[\.\:\-\)])', r'\1', opt_str)
        # Bổ sung tiền tố nếu thiếu
        if not re.match(r'^[A-D]\s*[\.\:\-\)]', opt_str):
            pref = prefixes[idx] if idx < len(prefixes) else ""
            opt_str = f"{pref}{opt_str}"
        normalized_options.append(opt_str)
        
    item["options"] = normalized_options
    
    # Chuẩn hóa correct_answer
    raw_ca = str(item.get("correct_answer", "")).strip()
    ca_match = re.match(r'^([A-D])(?:\s*[\.\:\-\)]|$)', raw_ca)
    if ca_match:
        letter = ca_match.group(1).upper()
        matched = False
        for opt in normalized_options:
            if opt.startswith(f"{letter}.") or opt.startswith(f"{letter} ") or opt.startswith(f"{letter}:"):
                item["correct_answer"] = opt
                matched = True
                break
        if not matched and normalized_options:
            item["correct_answer"] = raw_ca
    else:
        for opt in normalized_options:
            if raw_ca.lower() in opt.lower() or opt.lower() in raw_ca.lower():
                item["correct_answer"] = opt
                break
                
    # Chuẩn hóa explain
    item["explain"] = str(item.get("explain", "")).strip()
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
    prompt: str,
    api_keys: List[str],
    system_instruction: Optional[str] = None,
    thinking_budget: Optional[int] = 0
):
    """
    Gọi Gemini AI với cơ chế tối ưu hiệu năng:
    - Sử dụng Client Pool tái sử dụng kết nối
    - Tối ưu hóa chuỗi model: gemini-2.5-flash (siêu tốc ~1.4s) -> gemini-flash-latest -> gemini-3.5-flash
    - Tắt thinking_budget để loại bỏ độ trễ suy nghĩ nội bộ cho tác vụ trích xuất JSON
    - Tự động luân chuyển Key khi gặp 429 Quota Exceeded
    """
    if not api_keys:
        raise Exception("Hệ thống chưa được cấu hình API Key.")
        
    # Danh sách model tối ưu cho thế hệ mới nhất
    models_to_try = [
        'gemini-2.5-flash',
        'gemini-flash-latest',
        'gemini-3.5-flash',
        'gemini-2.5-flash-lite'
    ]
    last_error = None
    
    for key in api_keys:
        key = key.strip()
        if not key:
            continue
            
        try:
            client = get_gemini_client(key)
        except Exception as e:
            last_error = e
            continue
            
        for model_name in models_to_try:
            # Cấu hình tối ưu tốc độ
            config_params = {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
            if system_instruction:
                config_params["system_instruction"] = system_instruction
            if thinking_budget is not None and hasattr(types, "ThinkingConfig"):
                config_params["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)
                
            try:
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_params)
                )
                return response
            except Exception as e:
                error_str = str(e).lower()
                
                # Nếu model không hỗ trợ thinking_budget, thử lại ngay không kèm thinking_config
                if "thinking" in error_str or "invalid argument" in error_str:
                    try:
                        fallback_params = {k: v for k, v in config_params.items() if k != "thinking_config"}
                        response = await client.aio.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=types.GenerateContentConfig(**fallback_params)
                        )
                        return response
                    except Exception as inner_e:
                        error_str = str(inner_e).lower()
                        last_error = inner_e
                else:
                    last_error = e

                if "api key not valid" in error_str or "invalid api key" in error_str:
                    break  # Key lỗi, chuyển key kế tiếp
                elif "404" in error_str or "not found" in error_str or "unsupported" in error_str:
                    continue  # Model không tồn tại, thử model tiếp theo
                elif "429" in error_str or "quota" in error_str or "503" in error_str or "overloaded" in error_str:
                    await asyncio.sleep(0.5)
                    break  # Chạm giới hạn lượt gọi, chuyển sang API Key tiếp theo
                elif "deadline" in error_str or "timeout" in error_str:
                    continue
                else:
                    continue
                    
    raise Exception(f"Tất cả các Key và Model đều thất bại. Lỗi cuối: {str(last_error)}")

async def generate_mcq_with_gemini(
    marked_text: str,
    api_keys: List[str],
    task_id: str = None,
    active_tasks: dict = None
) -> List[Dict[str, Any]]:
    """Dùng Gemini AI để bóc tách câu hỏi dựa trên văn bản đã gắn thẻ <MARK> với Semaphore kiểm soát lưu lượng."""
    chunks = chunk_marked_text(marked_text, questions_per_chunk=15)
    all_extracted_data = []
    
    # Giới hạn tối đa 2 tác vụ chạy đồng thời để chống chạm Rate Limit 429 trên Google Free Tier
    concurrency_limit = asyncio.Semaphore(2)
    
    system_instruction = (
        "Bạn là một chuyên gia giáo dục và biên tập viên đề thi trắc nghiệm. "
        "Nhiệm vụ của bạn là bóc tách chuẩn xác toàn bộ câu hỏi và đáp án từ tài liệu được cung cấp. "
        "Quy tắc bất di bất dịch: Giữ nguyên các thẻ định dạng HTML (<b>, <i>, <u>, <sub>, <sup>) "
        "và các thẻ giữ chỗ hình ảnh [IMG_X]. Giữ nguyên công thức toán LaTeX được bọc trong \\( và \\). "
        "Luôn kèm trường 'explain' giải thích ngắn gọn, súc tích lý do chọn đáp án đúng. "
        "Trả về kết quả dưới dạng JSON array duy nhất."
    )
    
    async def process_chunk(idx, chunk):
        if not chunk.strip():
            return None
            
        async with concurrency_limit:
            if active_tasks is not None and task_id and task_id in active_tasks:
                active_tasks[task_id]["message"] = f"AI đang bóc tách phần {idx + 1}/{len(chunks)}..."
                
            prompt = f"""
            Trích xuất danh sách câu hỏi trắc nghiệm từ phần văn bản {idx + 1}/{len(chunks)} sau:
            
            1. Bóc tách câu hỏi và đúng 4 đáp án (A, B, C, D). Loại bỏ chữ 'Câu X:', 'Bài X:' hoặc số thứ tự ở đầu.
            2. Đáp án đúng là đáp án chứa nội dung nằm trong thẻ <MARK> hoặc có dấu * ở trước chữ cái. Loại bỏ <MARK> và dấu * khỏi kết quả.
            3. TUYỆT ĐỐI KHÔNG ĐƯỢC XÓA BỎ các thẻ [IMG_X]. Phải giữ nguyên chúng trong câu hỏi hoặc đáp án tương ứng.
            4. Trả về mảng JSON theo mẫu:
               [
                 {{
                   "group_title": "",
                   "question": "Nội dung câu hỏi [IMG_1]...",
                   "options": ["A. Lựa chọn 1", "B. Lựa chọn 2", "C. Lựa chọn 3", "D. Lựa chọn 4"],
                   "correct_answer": "A. Lựa chọn 1",
                   "explain": "Giải thích ngắn gọn lý do chọn đáp án này..."
                 }}
               ]
               
            Văn bản:
            {chunk}
            """
            try:
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
                    parsed_json = json_repair.loads(json_text)
                else:
                    parsed_json = json.loads(json_text, strict=False)
                    
                if isinstance(parsed_json, list):
                    # Chuẩn hóa từng câu hỏi
                    return [normalize_question_data(q) for q in parsed_json if isinstance(q, dict)]
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

async def generate_mcq_from_pdf(
    pdf_path: str,
    api_keys: List[str],
    task_id: str = None,
    active_tasks: dict = None
) -> List[Dict[str, Any]]:
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
