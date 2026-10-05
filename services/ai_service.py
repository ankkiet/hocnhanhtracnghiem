import re
import json
import asyncio
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types

try:
    import pymupdf as fitz  # PyMuPDF
except ImportError:
    try:
        import fitz
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
    Bảo vệ các lệnh LaTeX nhạy cảm có ký tự đầu là escape char của JSON (b, f, n, r, t).
    """
    # 1. Bảo vệ placeholder [IMG_X] trước khi sửa escape
    protected = re.sub(r'(\[IMG_\d+\])', lambda m: m.group(0), json_str)
    
    # 2. Bảo vệ các lệnh LaTeX phổ biến bắt đầu bằng b, f, n, r, t, s, v.v. (tránh \\f bị hiểu thành formfeed, \\t thành tab)
    latex_sensitive = (
        r'frac|sqrt|text|textbf|textit|mathrm|times|tan|tau|theta|to|'
        r'neq|nu|nabla|rho|right|rightarrow|rightleftharpoons|'
        r'beta|bar|begin|binom|bf|sum|prod|int|lim|vec|hat|left'
    )
    protected = re.sub(rf'(?<!\\)\\(?={latex_sensitive}\b)', r'\\\\', protected)
    # Bảo vệ dấu ngoặc LaTeX \\( \\) \\[ \\]
    protected = re.sub(r'(?<!\\)\\([()\[\]])', r'\\\\\1', protected)
    
    # 3. Nhân đôi các dấu \\ đơn độc khác ngoại trừ các escape hợp lệ của JSON (\" \\ \/)
    return re.sub(r'(?<!\\)\\(?!["\\/])', r'\\\\', protected)

def clean_subscripts_and_formulas(text: str) -> str:
    """
    Tự động sửa lỗi AI xuất công thức hóa học/toán học có chỉ số dưới dạng gạch dưới (như CH_2, CO_2, H_2O, Fe_2O_3)
    thành thẻ chuẩn <sub> để hiển thị đúng số nằm dưới chân chữ cái: CH<sub>2</sub>, CO<sub>2</sub>, H<sub>2</sub>O.
    Đồng thời bảo vệ các placeholder ảnh [IMG_X], thẻ HTML và các khối LaTeX \\( ... \\), \\[ ... \\].
    """
    if not text or not isinstance(text, str):
        return text

    placeholders = []
    def save_ph(m):
        placeholders.append(m.group(0))
        return f'XYZPH{len(placeholders)-1}XYZ'

    # 1. Bảo vệ placeholder ảnh [IMG_X]
    text = re.sub(r'(\[IMG_\d+\])', save_ph, text)
    # 2. Bảo vệ các khối LaTeX math (inline và display)
    text = re.sub(r'(\\\[[\s\S]*?\\\]|\\\(.*?\\\)|\$\$[\s\S]*?\$\$|\$[^\$]+?\$)', save_ph, text)
    # 3. Bảo vệ thẻ HTML (như <img ...>, <sub>, <sup>, <b>, <i>, ...)
    text = re.sub(r'(<[^>]+>)', save_ph, text)

    # 4. Sửa chỉ số dưới dạng _{...} thành <sub>...</sub> (vd: H_{2n+2} -> H<sub>2n+2</sub>)
    text = re.sub(r'([A-Za-z0-9\)\>\]])_\{([^}]+)\}', r'\1<sub>\2</sub>', text)
    # 5. Sửa chỉ số dưới số (vd: CH_2, H_2O, CO_2, Fe_2O_3, Ca(OH)_2) thành <sub>...</sub>
    text = re.sub(r'([A-Za-z0-9\)\>\]])_([0-9]+)', r'\1<sub>\2</sub>', text)
    # 6. Sửa chỉ số dưới chữ (vd: C_n, u_n, x_1, v_0, m_hh)
    text = re.sub(r'([A-Z][a-z]?|\b[uvxyzmkn])_([a-z0-9]+)', r'\1<sub>\2</sub>', text)
    # 7. Sửa chỉ số trên ^{...} và ^(số/dấu) (vd: cm^2, m^3, Fe^3+) thành <sup>...</sup>
    text = re.sub(r'([A-Za-z0-9\)\>\]])\^\{([^}]+)\}', r'\1<sup>\2</sup>', text)
    text = re.sub(r'([A-Za-z0-9\)\>\]])\^([0-9\+\-]+)', r'\1<sup>\2</sup>', text)

    # 8. Khôi phục lại các nội dung được bảo vệ theo thứ tự ngược lại
    for i in range(len(placeholders) - 1, -1, -1):
        text = text.replace(f'XYZPH{i}XYZ', placeholders[i])

    return text

def normalize_question_data(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chuẩn hóa toàn diện dữ liệu câu hỏi theo chuẩn Bộ GD&ĐT (GDPT 2018):
    1. Trắc nghiệm nhiều lựa chọn (mcq): 4 lựa chọn A, B, C, D, đáp án A-D.
    2. Trắc nghiệm Đúng / Sai (true_false): 4 ý a), b), c), d), đáp án dict {"a": bool, "b": bool, "c": bool, "d": bool}.
    3. Trắc nghiệm Trả lời ngắn (short_answer): options=[], đáp án chuỗi ngắn.
    Làm sạch chỉ số dưới hóa học/toán học (CH_2 -> CH<sub>2</sub>), giữ nguyên ảnh [IMG_X] và thẻ HTML.
    """
    if not isinstance(item, dict):
        return item
        
    # Chuẩn hóa question, group_title, explain
    if "question" in item:
        item["question"] = clean_subscripts_and_formulas(str(item.get("question", ""))).strip()
    if "group_title" in item:
        item["group_title"] = clean_subscripts_and_formulas(str(item.get("group_title", ""))).strip()
    item["explain"] = clean_subscripts_and_formulas(str(item.get("explain", ""))).strip()

    raw_type = str(item.get("type", "")).lower().strip()
    options = item.get("options", [])
    if not isinstance(options, list):
        options = []

    # Nhận diện tự động loại câu hỏi nếu chưa chỉ định rõ type
    is_true_false = False
    is_short_answer = False

    if raw_type in ["true_false", "tf", "dung_sai", "dung-sai"]:
        is_true_false = True
    elif raw_type in ["short_answer", "sa", "tra_loi_ngan", "tra-loi-ngan"]:
        is_short_answer = True
    else:
        # Sub-options của Đúng/Sai là chữ thường a), b), c), d) hoặc a., b., c., d.
        has_sub_options = any(re.match(r'^\s*(?:\*?\s*)?[\(\[]?[a-d][\)\.\:\-\]]', str(opt).strip()) for opt in options)
        raw_ca = item.get("correct_answer")
        has_tf_dict = isinstance(raw_ca, dict) and any(str(k).lower() in ['a', 'b', 'c', 'd'] for k in raw_ca.keys())
        has_tf_str = isinstance(raw_ca, str) and bool(re.search(r'[a-d]\s*[\:\-\=]?\s*(?:Đ|S|Đúng|Sai|True|False)', raw_ca, re.IGNORECASE))
        
        header_text = (str(item.get("group_title", "")) + " " + str(item.get("question", ""))).lower()
        if "đúng sai" in header_text or "đúng - sai" in header_text:
            is_true_false = True
        elif has_sub_options or has_tf_dict or has_tf_str:
            is_true_false = True
        elif "trả lời ngắn" in header_text or len(options) == 0:
            is_short_answer = True

    if is_true_false:
        item["type"] = "true_false"
        statements = item.get("statements", [])
        if isinstance(statements, list) and len(statements) > 0 and len(options) == 0:
            for s in statements:
                if isinstance(s, dict):
                    sid = str(s.get("id", "")).lower().strip() or "a"
                    scontent = str(s.get("content", "")).strip()
                    options.append(f"{sid}) {scontent}")
                    if "is_correct" in s and s.get("is_correct") is not None:
                        raw_ca_dict = item.get("correct_answer")
                        if not isinstance(raw_ca_dict, dict):
                            raw_ca_dict = {}
                            item["correct_answer"] = raw_ca_dict
                        raw_ca_dict[sid] = bool(s.get("is_correct"))

        sub_prefixes = ["a) ", "b) ", "c) ", "d) "]
        normalized_options = []
        for idx, opt in enumerate(options[:4]):
            opt_str = clean_subscripts_and_formulas(str(opt)).strip()
            opt_str = re.sub(r'^\*?\s*[\(\[]?[a-d][\)\.\:\-\]]\s*[\(\[]?([a-d])[\)\.\:\-\]]', r'\1) ', opt_str, flags=re.IGNORECASE)
            if not re.match(r'^\*?\s*[\(\[]?[a-d][\)\.\:\-\]]', opt_str, re.IGNORECASE):
                pref = sub_prefixes[idx] if idx < len(sub_prefixes) else ""
                opt_str = f"{pref}{opt_str}"
            else:
                m = re.match(r'^(\*?\s*)[\(\[]?([a-d])[\)\.\:\-\]]\s*(.*)', opt_str, re.IGNORECASE)
                if m:
                    asterisk = "*" if "*" in m.group(1) else ""
                    opt_str = f"{asterisk}{m.group(2).lower()}) {m.group(3)}"
            normalized_options.append(opt_str)
        item["options"] = normalized_options

        # Chuẩn hóa correct_answer thành dict {"a": bool, "b": bool, "c": bool, "d": bool}
        raw_ca = item.get("correct_answer")
        tf_dict = {"a": True, "b": False, "c": True, "d": False}
        if isinstance(raw_ca, dict):
            for k, v in raw_ca.items():
                k_clean = str(k).lower().strip().replace(')', '').replace('.', '')
                if k_clean in ['a', 'b', 'c', 'd']:
                    if isinstance(v, bool):
                        tf_dict[k_clean] = v
                    elif isinstance(v, str):
                        tf_dict[k_clean] = v.strip().lower() in ['đ', 'đúng', 'true', 't', '1', 'yes']
        elif isinstance(raw_ca, str):
            for k in ['a', 'b', 'c', 'd']:
                m = re.search(rf'\b{k}\s*[\:\-\.\)]?\s*(đúng|sai|đ|s|true|false)\b', raw_ca, re.IGNORECASE)
                if m:
                    val_str = m.group(1).lower()
                    tf_dict[k] = val_str in ['đ', 'đúng', 'true']
        
        # Kiểm tra đánh dấu trực tiếp trong từng option
        for idx, opt in enumerate(normalized_options):
            char = ['a', 'b', 'c', 'd'][idx] if idx < 4 else None
            if not char: continue
            if any(mark in opt for mark in ['*', '[ĐÚNG]', '[Đ]', '(Đúng)', '(Đ)', '✓', '✔']):
                tf_dict[char] = True
            elif any(mark in opt for mark in ['[SAI]', '[S]', '(Sai)', '(S)', '✗', '✘']):
                tf_dict[char] = False

        item["correct_answer"] = tf_dict
        return item

    elif is_short_answer:
        item["type"] = "short_answer"
        item["options"] = []
        raw_ca = str(item.get("correct_answer", "")).strip()
        raw_ca = re.sub(r'^(?:Đáp án|Đáp số|ĐS|Kết quả|Ans|Answer)\s*[\:\-\=]?\s*', '', raw_ca, flags=re.IGNORECASE).strip()
        item["correct_answer"] = clean_subscripts_and_formulas(raw_ca)
        return item

    else:
        item["type"] = "mcq"
        prefixes = ["A. ", "B. ", "C. ", "D. "]
        normalized_options = []
        for idx, opt in enumerate(options[:4]):
            opt_str = clean_subscripts_and_formulas(str(opt)).strip()
            opt_str = re.sub(r'^[A-D]\s*[\.\:\-\)]\s*([A-D]\s*[\.\:\-\)])', r'\1', opt_str)
            if not re.match(r'^[A-D]\s*[\.\:\-\)]', opt_str):
                pref = prefixes[idx] if idx < len(prefixes) else ""
                opt_str = f"{pref}{opt_str}"
            normalized_options.append(opt_str)
            
        item["options"] = normalized_options
        
        raw_ca = clean_subscripts_and_formulas(str(item.get("correct_answer", ""))).strip()
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
    active_tasks: dict = None,
    answer_key: Any = None
) -> List[Dict[str, Any]]:
    """
    Dùng Gemini AI để bóc tách câu hỏi dựa trên văn bản đã gắn thẻ <MARK>.
    Tự động nhận diện và bảo toàn tuyệt đối 100% BẢNG ĐÁP ÁN ở cuối tài liệu (không để AI tự sửa đáp án hoặc tự thêm bớt câu hỏi).
    """
    if active_tasks is None:
        try:
            from core.state import active_tasks as global_active_tasks
            active_tasks = global_active_tasks
        except ImportError:
            pass

    from core.answer_key_extractor import separate_answer_key_from_text, AnswerKeyMap, reconcile_quiz_with_answer_key

    # Tách và phát hiện BẢNG ĐÁP ÁN ở cuối tài liệu
    if answer_key is None or not (getattr(answer_key, 'part1', None) or getattr(answer_key, 'part2', None) or getattr(answer_key, 'part3', None) or answer_key):
        text_without_ak, ak_raw, detected_ak = separate_answer_key_from_text(marked_text)
        marked_text = text_without_ak
        if detected_ak and (detected_ak.part1 or detected_ak.part2 or detected_ak.part3 or detected_ak):
            answer_key = detected_ak
    else:
        # Nếu đã có answer_key truyền vào từ file docx, cắt bỏ phần BẢNG ĐÁP ÁN khỏi text để tránh AI hiểu nhầm thành câu hỏi
        text_without_ak, _, _ = separate_answer_key_from_text(marked_text)
        marked_text = text_without_ak

    ak_prompt_section = ""
    if answer_key and hasattr(answer_key, 'to_summary_text'):
        ak_summary = answer_key.to_summary_text()
        if ak_summary:
            ak_prompt_section = f"""
            ========================================================================
            BẢNG ĐÁP ÁN CHÍNH THỨC CỦA ĐỀ THI (BẮT BUỘC TUÂN THỦ 100%):
            {ak_summary}
            ========================================================================
            QUY TẮC BẢO TOÀN ĐÁP ÁN & NỘI DUNG GỐC:
            1. TUYỆT ĐỐI TUÂN THỦ BẢNG ĐÁP ÁN TRÊN: Đối với mỗi câu hỏi, PHẢI gán đúng đáp án từ Bảng Đáp Án chính thức trên (hoặc từ ký hiệu Đ/S, dấu *, thẻ <MARK>). TUYỆT ĐỐI KHÔNG TỰ GIẢI ĐỂ THAY ĐỔI ĐÁP ÁN CỦA ĐỀ GỐC!
            2. NGUYÊN VĂN NỘI DUNG 100%: Sao chép trung thực nguyên văn nội dung câu hỏi và các phương án từ văn bản gốc. KHÔNG TỰ Ý THÊM BỚT từ ngữ, KHÔNG SÁNG TÁC THÊM PHƯƠNG ÁN HAY BỎ BỚT PHƯƠNG ÁN!
            3. ĐỐI VỚI CÂU HỎI ĐÚNG / SAI (true_false): Bắt buộc giữ đủ 4 ý a), b), c), d) nguyên bản, đáp án đúng format {{"a": bool, "b": bool, "c": bool, "d": bool}} theo đúng Bảng Đáp Án.
            4. ĐỐI VỚI CÂU HỎI TRẢ LỜI NGẮN (short_answer): options là [], correct_answer lấy chuẩn từ Bảng Đáp Án.
            5. TUYỆT ĐỐI KHÔNG TẠO CÂU HỎI MỚI ngoài các câu có trong văn bản đề thi.
            """

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
        "Bạn là một chuyên gia giáo dục và biên tập viên đề thi trắc nghiệm chuẩn sư phạm. "
        "Nhiệm vụ của bạn là bóc tách chuẩn xác toàn bộ câu hỏi và đáp án từ tài liệu được cung cấp. "
        "Quy tắc bất di bất dịch:\n"
        "1. Giữ nguyên các thẻ định dạng HTML (<b>, <i>, <u>, <sub>, <sup>) và placeholder ảnh [IMG_X]. "
        "2. CÔNG THỨC HÓA HỌC / CHỈ SỐ DƯỚI (SUBSCRIPT): Tuyệt đối KHÔNG viết chỉ số dưới thành dấu gạch dưới trần như CH_2, CO_2, H_2O, Fe_2O_3, C_2H_5OH, x_1. "
        "BẮT BUỘC giữ nguyên thẻ HTML <sub> và <sup> (ví dụ: CH<sub>2</sub>, H<sub>2</sub>O, CO<sub>2</sub>, C<sub>2</sub>H<sub>5</sub>OH, cm<sup>2</sup>) "
        "hoặc đặt trọn vẹn trong công thức LaTeX \\( ... \\) như \\(\\text{CH}_2\\). "
        "3. CÔNG THỨC TOÁN LATEX: Mọi biểu thức toán học phải bọc trong \\( và \\). Nếu có chữ tiếng Việt trong công thức, phải dùng \\text{...}. "
        "4. BẢO TOÀN ĐÁP ÁN: Tuyệt đối tuân thủ Bảng Đáp Án đi kèm, không tự ý sửa đáp án hay thêm bớt câu hỏi. "
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
            Bạn là trợ lý AI chuyên gia phân tích và bóc tách đề thi theo CHUẨN CẤU TRÚC MỚI CỦA BỘ GIÁO DỤC VÀ ĐÀO TẠO (Chương trình GDPT 2018).
            Nhiệm vụ: Trích xuất CHÍNH XÁC toàn bộ các câu hỏi từ phần văn bản {idx + 1}/{len(chunks)} sau thành danh sách JSON chuẩn.
            {ak_prompt_section}
            ĐỀ THI GỒM 3 DẠNG CÂU HỎI THEO QUY CHUẨN BỘ GD&ĐT:
            
            1. PHẦN I: TRẮC NGHIỆM NHIỀU LỰA CHỌN (type: "mcq")
               - 4 lựa chọn A, B, C, D (bắt buộc tiền tố 'A. ', 'B. ', 'C. ', 'D. ').
               - correct_answer: Chuỗi đáp án đúng (ví dụ: 'A. Lựa chọn 1').
               - explain: Lời giải chi tiết lý do chọn đáp án này.
               - Mẫu JSON:
                 {{
                   "type": "mcq",
                   "group_title": "",
                   "question": "Nội dung câu hỏi...",
                   "options": ["A. Lựa chọn 1", "B. Lựa chọn 2", "C. Lựa chọn 3", "D. Lựa chọn 4"],
                   "correct_answer": "A. Lựa chọn 1",
                   "explain": "Lời giải chi tiết..."
                 }}

            2. PHẦN II: TRẮC NGHIỆM ĐÚNG / SAI (type: "true_false")
               - Mỗi câu gồm 4 ý/mệnh đề độc lập: a), b), c), d) (tiền tố 'a) ', 'b) ', 'c) ', 'd) ').
               - correct_answer: Đối tượng quy định Đúng (true) hoặc Sai (false) cho từng ý:
                 {{"a": true, "b": false, "c": true, "d": false}}
                 (Căn cứ vào bảng đáp án, ký hiệu Đ/S, dấu *, thẻ <MARK>, [ĐÚNG]/[SAI] nếu có; hoặc tự giải và xác định chuẩn xác).
               - explain: Lời giải chi tiết giải thích rõ lý do vì sao từng ý a, b, c, d là Đúng hoặc Sai.
               - Mẫu JSON:
                 {{
                   "type": "true_false",
                   "group_title": "PHẦN II. Câu trắc nghiệm đúng sai...",
                   "question": "Nội dung câu hỏi hoặc thông tin dữ liệu...",
                   "options": [
                     "a) Mệnh đề a",
                     "b) Mệnh đề b",
                     "c) Mệnh đề c",
                     "d) Mệnh đề d"
                   ],
                   "correct_answer": {{"a": true, "b": false, "c": true, "d": false}},
                   "explain": "Giải thích vì sao a đúng, b sai, c đúng, d sai..."
                 }}

            3. PHẦN III: TRẮC NGHIỆM TRẢ LỜI NGẮN (type: "short_answer")
               - Câu hỏi tự luận điền kết quả / đáp số ngắn (số nguyên, số thập phân, phân số, tọa độ hoặc từ ngắn).
               - options: BẮT BUỘC là mảng rỗng [].
               - correct_answer: Chuỗi chứa đáp số ngắn chuẩn xác (ví dụ: "12", "-3.5", "1/2", "0.25").
               - explain: Lời giải chi tiết cách tính ra đáp số đó.
               - Mẫu JSON:
                 {{
                   "type": "short_answer",
                   "group_title": "PHẦN III. Câu trắc nghiệm trả lời ngắn...",
                   "question": "Nội dung câu hỏi tính toán...",
                   "options": [],
                   "correct_answer": "12.5",
                   "explain": "Lời giải từng bước tính..."
                 }}

            QUY TẮC BẮT BUỘC VỀ ĐỊNH DẠNG:
            1. CHỈ SỐ DƯỚI & CÔNG THỨC HÓA HỌC: Giữ nguyên thẻ <sub> và <sup>, TUYỆT ĐỐI KHÔNG viết thành CH_2, CO_2, H_2O. Phải viết là CH<sub>2</sub>, CO<sub>2</sub>, H<sub>2</sub>O hoặc \(\text{{CH}}_2\).
            2. CÔNG THỨC TOÁN LATEX: Mọi biểu thức toán học phải bọc trong \( và \).
            3. TUYỆT ĐỐI KHÔNG ĐƯỢC XÓA BỎ các thẻ [IMG_X]. Phải sao chép NGUYÊN XI, ĐÚNG TỪNG KÝ TỰ các placeholder [IMG_X] vào câu hỏi hoặc đáp án tương ứng.
            4. Chỉ trả về duy nhất mảng JSON [...] không có văn bản giải thích nào khác ngoài JSON.{img_strict_rule}
            
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

    # Áp đặt lại Bảng đáp án chuẩn (Source of Truth) lên toàn bộ dữ liệu bóc tách
    if answer_key and hasattr(answer_key, 'get_answer'):
        from core.answer_key_extractor import reconcile_quiz_with_answer_key
        all_extracted_data = reconcile_quiz_with_answer_key(all_extracted_data, answer_key)

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

