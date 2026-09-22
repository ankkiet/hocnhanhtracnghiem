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
    """
    Sửa lỗi LLM trả về các ký tự LaTeX (như \\frac, \\rightarrow) bị parser JSON hiểu nhầm thành ký tự escape.
    Chú ý: Chỉ fix dấu \\ đơn nằm ngoài các placeholder [IMG_X] và ngoài chuỗi JSON hợp lệ.
    """
    # Bảo vệ placeholder [IMG_X] trước khi sửa escape
    protected = re.sub(r'(\[IMG_\d+\])', lambda m: m.group(0), json_str)
    return re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', protected)

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
    
    # Đếm tổng số placeholder ảnh trong toàn bộ tài liệu để nhắc AI
    total_imgs = len(re.findall(r'\[IMG_\d+\]', marked_text))
    img_reminder = (
        f" Tài liệu chứa {total_imgs} ảnh được đánh dấu bằng [IMG_X] (X là số). "
        "TUYỆT ĐỐI PHẢI GIỮ NGUYÊN 100% các placeholder [IMG_X] đúng như trong văn bản gốc. "
        "KHÔNG được viết lại thành [Hình X], [Image X], [Ảnh X] hay bất kỳ dạng nào khác."
    ) if total_imgs > 0 else ""
    
    system_instruction = (
        "Bạn là một chuyên gia giáo dục và biên tập viên đề thi trắc nghiệm. "
        "Nhiệm vụ của bạn là bóc tách chuẩn xác toàn bộ câu hỏi và đáp án từ tài liệu được cung cấp. "
        "Quy tắc bất di bất dịch: Giữ nguyên các thẻ định dạng HTML (<b>, <i>, <u>, <sub>, <sup>) "
        "và các thẻ giữ chỗ hình ảnh [IMG_X] (KHÔNG ĐƯỢC sửa đổi, xóa bỏ hay đổi tên các thẻ [IMG_X]). "
        "Giữ nguyên công thức toán LaTeX được bọc trong \\( và \\). "
        "Luôn kèm trường 'explain' giải thích ngắn gọn, súc tích lý do chọn đáp án đúng. "
        f"Trả về kết quả dưới dạng JSON array duy nhất.{img_reminder}"
    )
    
    async def process_chunk(idx, chunk):
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
            
        async with concurrency_limit:
            if active_tasks is not None and task_id and task_id in active_tasks:
                active_tasks[task_id]["message"] = f"AI đang bóc tách phần {idx + 1}/{len(chunks)}..."
                
            prompt = f"""
            Trích xuất danh sách câu hỏi trắc nghiệm từ phần văn bản {idx + 1}/{len(chunks)} sau:
            
            1. Bóc tách câu hỏi và đúng 4 đáp án (A, B, C, D). Loại bỏ chữ 'Câu X:', 'Bài X:' hoặc số thứ tự ở đầu.
            2. Đáp án đúng là đáp án chứa nội dung nằm trong thẻ <MARK> hoặc có dấu * ở trước chữ cái. Loại bỏ <MARK> và dấu * khỏi kết quả.
            3. TUYỆT ĐỐI KHÔNG ĐƯỢC XÓA BỎ hoặc thay đổi các thẻ [IMG_X]. Phải sao chép NGUYÊN XI, ĐÚNG TỪNG KÝ TỰ các placeholder [IMG_X] vào câu hỏi hoặc đáp án tương ứng. Ví dụ: [IMG_1] phải được viết là [IMG_1], không phải [Hình 1] hay [Image 1].
            4. Trả về mảng JSON theo mẫu:
               [
                 {{
                   "group_title": "",
                   "question": "Nội dung câu hỏi. Ví dụ có ảnh: Hãy quan sát hình sau [IMG_1] và trả lời câu hỏi...",
                   "options": ["A. Lựa chọn 1", "B. Lựa chọn 2 [IMG_2]", "C. Lựa chọn 3", "D. Lựa chọn 4"],
                   "correct_answer": "A. Lựa chọn 1",
                   "explain": "Giải thích ngắn gọn lý do chọn đáp án này..."
                 }}
               ]{img_strict_rule}
               
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
                raw_text = response.text
                # Khôi phục lại placeholder ảnh mà AI có thể đã viết sai
                raw_text = restore_image_placeholders(raw_text)
                
                match = re.search(r'\[\s*\{.*?\}\s*\]', raw_text, re.DOTALL)
                json_text = match.group(0) if match else raw_text
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
        
    from services.r2_service import upload_image_to_r2
    from core.image_converter import process_image_blob

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

