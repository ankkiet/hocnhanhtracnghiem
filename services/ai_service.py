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
    return protected


def clean_subscripts_and_formulas(text: str) -> str:

    """

    Tự động sửa lỗi AI xuất công thức hóa học/toán học có chỉ số dưới dạng gạch dưới (như CH_2, CO_2, H_2O, Fe_2O_3)

    thành thẻ chuẩn <sub> để hiển thị đúng số nằm dưới chân chữ cái: CH<sub>2</sub>, CO<sub>2</sub>, H<sub>2</sub>O.

    Đồng thời bảo vệ các placeholder ảnh [IMG_X], thẻ HTML và các khối LaTeX \( ... \), \[ ... \].

    """

    if not text or not isinstance(text, str):

        return text



    placeholders = []

    def save_ph(m):

        placeholders.append(m.group(0))

        return f'XYZPH{len(placeholders)-1}XYZ'



    # 1. Bảo vệ placeholder ảnh [IMG_X]

    text = re.sub(r'(\[IMG_\d+\])', save_ph, text)

    # 2. Bảo vệ các khối LaTeX math (inline và display) với bất kỳ số lượng backslash nào

    text = re.sub(r'(\\+\[[\s\S]*?\\+\]|\\+\([\s\S]*?\\+\)|\$\$[\s\S]*?\$\$|\$[^\$]+?\$)', save_ph, text)

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





def clean_question_prefix(text: str) -> str:

    """Loại bỏ tiền tố 'Câu 1:', 'Câu 1.', 'Bài 1:', '1.', '[Câu 1]' khỏi nội dung câu hỏi."""

    if not text or not isinstance(text, str):

        return ""

    cleaned = re.sub(

        r'^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*',

        '',

        text.strip(),

        flags=re.IGNORECASE

    )

    return cleaned.strip()





def clean_option_text(opt: str) -> tuple:
    """
    Chuẩn hóa phương án chuẩn Bộ GD&ĐT và HocNhanhTN:
    - Bóc tách nội dung thuần túy (không dính tiền tố 'A. ', 'a) ', '*A. ', '<u>a)</u>', '<MARK><u>a)</u></MARK>')
    - Chuẩn HocNhanhTN Cách 3: Phát hiện gạch chân (thẻ <u>) hoặc <MARK> ở ký hiệu phương án -> Đáp án Đúng (is_correct=True)
    - Phát hiện đánh dấu đáp án đúng (*, [ĐÚNG], (Đúng), ✓, ✔)
    - Phát hiện đánh dấu đáp án sai ([SAI], (Sai), ✗, ✘)
    - Giữ và bảo toàn nhãn ma trận HocNhanhTN: [0, NB], [1, TH], [2, VD], [3, VDC] nếu có
    - Trả về: (nội_dung_sạch, is_correct, is_false, ký_tự_gốc)
    """
    if not opt:
        return "", False, False, ""

    opt_str = str(opt).strip()

    # 1. Phát hiện đánh dấu Đúng theo chuẩn Bộ GD&ĐT và chuẩn HocNhanhTN
    has_leading_asterisk = bool(re.match(r'^\s*[\(\[]?\s*\*\s*[A-Fa-f\d]', opt_str) or re.match(r'^\s*\*\s*[\(\[]?[A-Fa-f\d]', opt_str))
    
    # Chuẩn HocNhanhTN Cách 3: Gạch chân ký hiệu phương án đúng: <u>a)</u>, <u>a</u>), <u>a.</u>, <u>[0, NB] a)</u>, v.v.
    has_underline_marker = bool(re.search(
        r'^\s*(?:<MARK>\s*)?(?:\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*)?(?:<MARK>\s*)?<u>\s*(?:\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*)?\*?[A-Fa-f\d]',
        opt_str,
        re.IGNORECASE
    ))
    
    # Kiểm tra <MARK> bọc ký hiệu phương án
    has_mark_prefix = bool(re.search(
        r'^\s*<MARK>\s*(?:<u>)?\s*(?:\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*)?\*?[A-Fa-f\d][\)\.\:\-\]\/]',
        opt_str,
        re.IGNORECASE
    ))

    # Phát hiện gạch chân (<u>), highlight / tô đỏ / tô màu nền (<MARK>), dấu tick ở BẤT KỲ ĐÂU trong phương án
    has_mark_tag = bool(re.search(r'</?MARK>', opt_str, re.IGNORECASE))
    has_underline_tag = bool(re.search(r'</?u>', opt_str, re.IGNORECASE))
    has_star = '*' in opt_str[:15]
    has_tick = any(c in opt_str for c in ['✓', '✔', '☑'])

    has_correct_tag = bool(re.search(r'\[(ĐÚNG|DUNG|Đ|TRUE|T)\]|\((Đúng|Dung|Đ|True|T)\)|✓|✔|☑', opt_str, re.IGNORECASE))
    is_correct = has_leading_asterisk or has_underline_marker or has_mark_prefix or has_correct_tag or has_mark_tag or has_underline_tag or has_star or has_tick

    is_false = bool(re.search(r'\[(SAI|S|FALSE|F)\]|\((Sai|S|False|F)\)|✗|✘', opt_str, re.IGNORECASE))

    # 2. Xóa các thẻ đánh dấu explicit [ĐÚNG], [SAI], checkmarks
    cleaned = re.sub(r'\[(ĐÚNG|DUNG|SAI|Đ|S|TRUE|FALSE|T|F)\]|\((Đúng|Dung|Sai|Đ|S|True|False|T|F)\)|✓|✔|✗|✘', '', opt_str, flags=re.IGNORECASE).strip()

    # 3. Trích xuất tag ma trận HocNhanhTN (ví dụ [0, NB], [1, TH], [NB]...) nếu có trước phương án
    azota_tag = ""
    m_tag = re.match(r'^\s*(?:<MARK>\s*|<u>\s*)*(\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\])\s*(?:</MARK>\s*|</u>\s*)*', cleaned, re.IGNORECASE)
    if m_tag:
        azota_tag = m_tag.group(1).strip()
        cleaned = cleaned[m_tag.end():].strip()

    # 4. Trích xuất ký tự phương án (A-F hoặc a-d hoặc số)
    char_match = re.match(
        r'^\s*(?:<[^>]+>\s*)*(?:\*\s*)?[\(\[]?([A-Fa-f\d])[\)\.\:\-\]\/](?:\s*</?[^>]+>\s*)*\s*(.*)',
        cleaned,
        flags=re.DOTALL | re.IGNORECASE
    )
    if not char_match:
        char_match = re.match(
            r'^\s*(?:<[^>]+>\s*)*(?:\*\s*)?[\(\[]?([A-Fa-f\d])(?:\s*</?[^>]+>\s*)*[\)\.\:\-\]\/]\s*(.*)',
            cleaned,
            flags=re.DOTALL | re.IGNORECASE
        )

    if char_match:
        extracted_char = char_match.group(1)
        cleaned_content = char_match.group(2).strip()
    else:
        extracted_char = ""
        cleaned_content = cleaned.strip()

    # 5. Nếu sau ký hiệu phương án lại có tag HocNhanhTN (ví dụ a) [0, NB] Mệnh đề...)
    if not azota_tag:
        m_tag_post = re.match(r'^\s*(\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\])\s*(.*)', cleaned_content, re.IGNORECASE | re.DOTALL)
        if m_tag_post:
            azota_tag = m_tag_post.group(1).strip()
            cleaned_content = m_tag_post.group(2).strip()

    # Loại bỏ các thẻ <MARK>, </MARK>, <u>, </u> đánh dấu đáp án khỏi nội dung phương án
    cleaned_content = re.sub(r'</?MARK>', '', cleaned_content, flags=re.IGNORECASE)
    cleaned_content = re.sub(r'</?u>', '', cleaned_content, flags=re.IGNORECASE).strip()

    # Giữ tiền tố ma trận HocNhanhTN chuẩn hóa
    if azota_tag:
        cleaned_content = f"{azota_tag} {cleaned_content}".strip()

    return cleaned_content, is_correct, is_false, extracted_char





def parse_tf_answer(raw_ca: Any) -> Dict[str, bool]:

    """Phân tích chuẩn xác các định dạng đáp án Đúng/Sai thành dict {'a': bool, 'b': bool, 'c': bool, 'd': bool}."""

    tf_dict = {"a": True, "b": False, "c": True, "d": False}

    if isinstance(raw_ca, dict):

        for k, v in raw_ca.items():

            k_clean = str(k).lower().strip().replace(')', '').replace('.', '')

            if k_clean in ['a', 'b', 'c', 'd']:

                if isinstance(v, bool):

                    tf_dict[k_clean] = v

                elif isinstance(v, (int, float)):

                    tf_dict[k_clean] = bool(v)

                elif isinstance(v, str):

                    tf_dict[k_clean] = v.strip().lower() in ['đ', 'đúng', 'dung', 'true', 't', '1', 'yes', 'y']

        return tf_dict

    elif isinstance(raw_ca, (list, tuple)) and len(raw_ca) >= 4:

        for idx, k in enumerate(['a', 'b', 'c', 'd']):

            v = raw_ca[idx]

            if isinstance(v, bool):

                tf_dict[k] = v

            elif isinstance(v, (int, float)):

                tf_dict[k] = bool(v)

            elif isinstance(v, str):

                tf_dict[k] = v.strip().lower() in ['đ', 'đúng', 'dung', 'true', 't', '1', 'yes', 'y']

        return tf_dict

    elif isinstance(raw_ca, str):

        found_any = False
        for k in ['a', 'b', 'c', 'd']:
            m = re.search(rf'(?:^|\b|[\(\[])\s*{k}\s*(?:[\)\:\-\.\=]\s*|\s+)(?:là\s+)?(ĐÚNG|DUNG|SAI|TRUE|FALSE|Đ|S|T|F|1|0)\b', raw_ca, re.IGNORECASE)
            if not m:
                m = re.search(rf'(?:^|\b|[\(\[])\s*{k}\s*[\)\:\-\.\=]\s*([^\s,;\/]+)', raw_ca, re.IGNORECASE)
            if m:
                val_str = m.group(1).lower().strip()
                tf_dict[k] = val_str in ['đ', 'đúng', 'dung', 'true', 't', '1', 'yes', 'y']
                found_any = True

        if found_any:
            return tf_dict

        seq = re.findall(r'\b(Đ|S|ĐÚNG|SAI|TRUE|FALSE|T|F)\b', raw_ca, re.IGNORECASE)

        if len(seq) == 4:

            for idx, k in enumerate(['a', 'b', 'c', 'd']):

                tf_dict[k] = seq[idx].lower() in ['đ', 'đúng', 'true', 't']

            return tf_dict

    return tf_dict





def extract_mcq_options_from_text(text: str) -> tuple:
    """
    Tự động phát hiện và bóc tách các phương án A, B, C, D (CHỮ IN HOA) nếu bị lẫn trong nội dung câu hỏi.
    Trả về (question_stem, [A. ..., B. ..., C. ..., D. ...])
    """
    if not text or not isinstance(text, str):
        return text, []

    pattern = re.compile(
        r'(?:^|\n|\r|\t|\s{2,}|(?<=[;\.\:\?!])\s*|(?<=[\)\}\]\'\"\>])\s*)'
        r'((?:(?:<MARK>\s*|<u>\s*|<b>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC|nb|th|vd|vdc)\s*\]\s*(?:</MARK>\s*|</u>\s*|</b>\s*)*)?'
        r'(?:<MARK>\s*|<u>\s*|<b>\s*)*'
        r'(?:\(?\[?(\*?[A-F])[\.\:\)]|\b(\*?[A-F])[\.\:\)]))\s*'
    )
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        return text, []

    matched_chars = []
    valid_matches = []
    expected_next = 'A'
    for m in matches:
        raw_char = (m.group(2) or m.group(3)).replace('*', '').strip()
        if raw_char == expected_next:
            matched_chars.append(raw_char)
            valid_matches.append(m)
            if raw_char == 'A': expected_next = 'B'
            elif raw_char == 'B': expected_next = 'C'
            elif raw_char == 'C': expected_next = 'D'
            elif raw_char == 'D': expected_next = None

    if len(matched_chars) < 2:
        return text, []

    stem = text[:valid_matches[0].start()].strip()
    options = []
    for idx, vm in enumerate(valid_matches):
        char = matched_chars[idx]
        full_block = text[vm.start(): valid_matches[idx + 1].start() if idx + 1 < len(valid_matches) else len(text)].strip()
        if idx == len(valid_matches) - 1:
            ans_split = re.split(
                r'\n\s*(?:Lời giải|Hướng dẫn giải|Giải thích|HDG|Đáp án|Đáp số)\s*[\:\-\=]',
                full_block,
                flags=re.IGNORECASE
            )
            if len(ans_split) > 1:
                full_block = ans_split[0].strip()
        options.append(full_block)

    return stem, options


def extract_sub_statements_from_text(text: str) -> tuple:
    """
    Tự động phát hiện và bóc tách các ý a), b), c), d) (CHỮ THƯỜNG) nếu bị lẫn trong nội dung câu hỏi.
    Hỗ trợ chuẩn HocNhanhTN có tiền tố ma trận [0, NB], [1, TH], [2, VD], [3, VDC] và markup <u>, <MARK>.
    Trả về (question_stem, [a) ..., b) ..., c) ..., d) ...])
    """
    if not text or not isinstance(text, str):
        return text, []

    # Pattern CHỮ THƯỜNG a-d (tuyệt đối KHÔNG có re.IGNORECASE để tránh nhận nhầm A, B, C, D của MCQ)
    pattern = re.compile(
        r'(?:^|\n|\r|\t|\s{2,}|(?<=[;\.\:\?!])\s*|(?<=[\)\}\]\'\"\>])\s*)'
        r'((?:(?:<MARK>\s*|<u>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*(?:</MARK>\s*|</u>\s*)*)?'
        r'(?:<MARK>\s*|<u>\s*)*'
        r'(?:\(?\[?(\*?[a-d])[\.\:\)\/\]\-]|\b(\*?[a-d])[\.\:\)\/]))\s*'
    )
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        return text, []

    matched_chars = []
    valid_matches = []
    expected_next = 'a'
    for m in matches:
        raw_char = (m.group(2) or m.group(3)).replace('*', '').strip()
        if raw_char == expected_next:
            matched_chars.append(raw_char)
            valid_matches.append(m)
            if raw_char == 'a': expected_next = 'b'
            elif raw_char == 'b': expected_next = 'c'
            elif raw_char == 'c': expected_next = 'd'
            elif raw_char == 'd': expected_next = None

    if len(matched_chars) < 2:
        return text, []

    stem = text[:valid_matches[0].start()].strip()
    options = []
    for idx, vm in enumerate(valid_matches):
        char = matched_chars[idx]
        full_block = text[vm.start(): valid_matches[idx + 1].start() if idx + 1 < len(valid_matches) else len(text)].strip()
        if idx == len(valid_matches) - 1:
            ans_split = re.split(
                r'\n\s*(?:Lời giải|Hướng dẫn giải|Giải thích|HDG|Đáp án|Đáp số)\s*[\:\-\=]',
                full_block,
                flags=re.IGNORECASE
            )
            if len(ans_split) > 1:
                full_block = ans_split[0].strip()
        options.append(full_block)

    return stem, options


def normalize_question_data(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chuẩn hóa toàn diện dữ liệu câu hỏi theo chuẩn Bộ GD&ĐT (GDPT 2018):
    1. Trắc nghiệm nhiều lựa chọn (mcq): 4 lựa chọn A, B, C, D, đáp án khớp nguyên văn với lựa chọn A-D.
    2. Trắc nghiệm Đúng / Sai (true_false): 4 ý a), b), c), d), đáp án dict {"a": bool, "b": bool, "c": bool, "d": bool}.
    3. Trắc nghiệm Trả lời ngắn (short_answer): options=[], đáp án chuỗi ngắn.
    Làm sạch chỉ số dưới hóa học/toán học (CH_2 -> CH<sub>2</sub>), giữ nguyên ảnh [IMG_X] và thẻ HTML.
    Loại bỏ triệt để tiền tố 'Câu 1:', '1.' bị lặp lại trong nội dung câu hỏi.
    """
    if not isinstance(item, dict):
        return item

    # 1. Trích xuất question_number nếu AI hoặc parser trả về
    raw_num = item.get("question_number") or item.get("question_id") or item.get("id") or item.get("stt") or item.get("number")
    if raw_num is not None:
        try:
            m_num = re.search(r'\d+', str(raw_num))
            if m_num:
                item["question_number"] = int(m_num.group(0))
        except Exception:
            pass

    # 2. Chuẩn hóa question: kiểm tra các tên trường thay thế của LLM
    raw_q = str(
        item.get("question") or
        item.get("question_content") or
        item.get("content") or
        item.get("cau_hoi") or
        item.get("question_text") or
        item.get("noi_dung") or
        ""
    ).strip()

    if "question_number" not in item:
        m_q_prefix = re.match(r'^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*(\d+)|\s*(\d+)[\.\:\)])', raw_q, re.IGNORECASE)
        if m_q_prefix:
            item["question_number"] = int(m_q_prefix.group(1) or m_q_prefix.group(2))

    q_clean = clean_question_prefix(raw_q)
    # Loại bỏ thẻ MARK khỏi nội dung câu hỏi để tránh tự động highlight màu nền
    q_cleaned = re.sub(r'</?MARK>', '', (q_clean or raw_q), flags=re.IGNORECASE)
    item["question"] = clean_subscripts_and_formulas(q_cleaned)

    # 3. Chuẩn hóa group_title & explain
    if "group_title" in item:
        gt = str(item.get("group_title", "")).strip()
        item["group_title"] = clean_subscripts_and_formulas(gt)
    item["explain"] = clean_subscripts_and_formulas(str(item.get("explain", ""))).strip()

    raw_type = str(item.get("type", "")).lower().strip()

    # Chuẩn hóa options: hỗ trợ trường hợp AI trả về dạng dict {"A": "...", "B": "..."}
    raw_options = item.get("options")
    if raw_options is None:
        raw_options = item.get("choices") or item.get("phuong_an") or []

    if isinstance(raw_options, dict):
        options = [
            f"{k}. {v}" if not re.match(rf'^\*?\s*[\(\[]?{k}[\.\:\)\-\]]', str(v).strip(), re.IGNORECASE) else str(v).strip()
            for k, v in sorted(raw_options.items())
        ]
    elif isinstance(raw_options, list):
        options = raw_options
    else:
        options = []

    # Chuẩn hóa correct_answer: hỗ trợ trường hợp AI trả về answer / dap_an
    raw_ca = item.get("correct_answer")
    if raw_ca is None:
        raw_ca = item.get("answer") or item.get("dap_an") or item.get("correctAnswer") or item.get("key")

    header_text = (str(item.get("group_title", "")) + " " + str(item.get("question", ""))).lower()

    # 2.1 Tự động cứu hộ: Nếu options đang rỗng hoặc <= 1
    if len(options) <= 1:
        # Ưu tiên kiểm tra phương án trắc nghiệm A, B, C, D (chữ in hoa)
        extracted_stem_mcq, extracted_opts_mcq = extract_mcq_options_from_text(item["question"])
        if len(extracted_opts_mcq) >= 2:
            item["question"] = extracted_stem_mcq
            options = extracted_opts_mcq
            item["options"] = options
        else:
            # Nếu không có A-D, mới kiểm tra ý con Đúng/Sai a), b), c), d) (chữ thường)
            extracted_stem_tf, extracted_opts_tf = extract_sub_statements_from_text(item["question"])
            if len(extracted_opts_tf) >= 2:
                item["question"] = extracted_stem_tf
                options = extracted_opts_tf
                item["options"] = options

    # 2.2 Kiểm tra đặc trưng Đúng / Sai
    has_tf_dict = isinstance(raw_ca, dict) and any(str(k).lower() in ['a', 'b', 'c', 'd'] for k in raw_ca.keys())
    has_tf_str = False
    if isinstance(raw_ca, str):
        # Yêu cầu ít nhất 2 ý được đánh giá (ví dụ a-Đ, b-S) hoặc 3 chữ Đ/S liên tục
        tf_pat = r'(?:[a-d][\.\:\)\/\-\s]*(?:Đ|S|Đúng|Sai|True|False)[^\w\n]*[,\;\-]?\s*[a-d][\.\:\)\/\-\s]*(?:Đ|S|Đúng|Sai)|(?:Đ|S|Đúng|Sai)\s*[\,\;\-]\s*(?:Đ|S|Đúng|Sai))'
        if re.search(tf_pat, raw_ca, re.IGNORECASE):
            has_tf_str = True
        elif len(re.findall(r'\b(Đ|S|ĐÚNG|SAI|TRUE|FALSE)\b', raw_ca, re.IGNORECASE)) >= 3:
            has_tf_str = True

    has_tf_keywords = any(kw in header_text for kw in [
        "đúng sai", "đúng - sai", "đúng/sai", "dung sai", "dung-sai", "dung/sai",
        "phần ii", "phan ii", "phần 2", "phan 2", "part ii", "part 2",
        "mỗi ý a", "đúng hoặc sai", "true/false", "true or false"
    ])
    has_explicit_tf_marks = any(any(m in str(opt) for m in ['[ĐÚNG]', '[DUNG]', '[SAI]', '(Đúng)', '(Dung)', '(Sai)']) for opt in options)

    # Đếm số lượng phương án theo quy chuẩn Bộ GD&ĐT:
    # - MCQ: Ký hiệu CHỮ IN HOA A, B, C, D (A. hoặc A))
    # - Đúng / Sai: Ký hiệu CHỮ THƯỜNG a, b, c, d (a) hoặc a.)
    mcq_opt_re = re.compile(
        r'^\s*(?:<MARK>\s*|<u>\s*|<b>\s*)*'
        r'(?:\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC|nb|th|vd|vdc)\s*\]\s*)?'
        r'(?:<MARK>\s*|<u>\s*|<b>\s*)*'
        r'\(?\[?(\*?[A-F])(?:\s*</u>)*(?:\s*</b>)*(?:\s*</MARK>)*[\.\:\)]'
    )
    tf_opt_re = re.compile(
        r'^\s*(?:<MARK>\s*|<u>\s*)*'
        r'(?:\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*)?'
        r'(?:<MARK>\s*|<u>\s*)*'
        r'\(?\[?(\*?[a-d])(?:\s*</u>)*(?:\s*</MARK>)*[\)\.\:\-\]\/]'
    )

    mcq_count = sum(1 for opt in options[:4] if mcq_opt_re.match(str(opt).strip()))
    tf_count = sum(1 for opt in options[:4] if tf_opt_re.match(str(opt).strip()))

    is_all_uppercase_mcq = (mcq_count >= 2 and mcq_count >= tf_count)
    is_tf_paren_options = (tf_count >= 2 and tf_count > mcq_count)

    is_single_choice_ca = bool(
        re.match(r'^\s*\(?[A-Da-d]\)?\.?\s*$', str(raw_ca).strip()) or
        re.match(r'^\s*(?:đáp án|câu|phương án|chọn)\s*[A-Da-d]\b', str(raw_ca).strip(), re.IGNORECASE)
    )

    # 3. Phân loại câu hỏi thông minh & triệt để:
    is_true_false = False
    is_short_answer = False

    if is_all_uppercase_mcq:
        # NẾU CÁC PHƯƠNG ÁN LÀ A, B, C, D (CHỮ IN HOA) -> BẮT BUỘC VÀ DUY NHẤT LÀ MCQ!
        is_true_false = False
        is_short_answer = False
    elif is_tf_paren_options:
        # Nếu đáp án là chọn 1 chữ cái đơn lẻ (MCQ) và không có dấu hiệu Đúng/Sai -> Vẫn là MCQ
        if is_single_choice_ca and not (has_tf_dict or has_tf_str or has_explicit_tf_marks or has_tf_keywords):
            is_true_false = False
        else:
            is_true_false = True
        is_short_answer = False
    elif (has_tf_dict or has_tf_str or has_explicit_tf_marks) and mcq_count == 0:
        is_true_false = True
    elif raw_type in ["true_false", "tf", "dung_sai", "dung-sai", "dung/sai", "dung sai"] and mcq_count == 0:
        is_true_false = True
    elif raw_type in ["short_answer", "sa", "tra_loi_ngan", "tra-loi-ngan", "short", "dien_khuyet", "tu_luan"]:
        if tf_count >= 2:
            is_true_false = True
        else:
            is_short_answer = True
    elif len(options) == 0:
        is_short_answer = True
    else:
        is_true_false = False
        is_short_answer = False



    # 4. XỬ LÝ DẠNG ĐÚNG / SAI

    if is_true_false:

        item["type"] = "true_false"

        sub_prefixes = ["a) ", "b) ", "c) ", "d) "]

        normalized_options = []

        opt_tf_marks = {}



        # Hỗ trợ nếu AI xuất dạng "statements": [{"id": "a", "content": "...", "is_correct": true}]

        statements = item.get("statements", [])

        if isinstance(statements, list) and len(statements) > 0 and len(options) == 0:

            options = [f"{s.get('id', 'a')}) {s.get('content', '')}" for s in statements if isinstance(s, dict)]

            if not item.get("correct_answer"):

                item["correct_answer"] = {s.get('id', 'a'): s.get('is_correct', True) for s in statements if isinstance(s, dict)}



        for idx, opt in enumerate(options[:4]):

            clean_text, is_corr, is_fls, ext_char = clean_option_text(opt)

            clean_text = clean_subscripts_and_formulas(clean_text)

            char_key = ['a', 'b', 'c', 'd'][idx]

            pref = sub_prefixes[idx]

            normalized_options.append(f"{pref}{clean_text}")

            if is_corr:

                opt_tf_marks[char_key] = True

            elif is_fls:

                opt_tf_marks[char_key] = False



        item["options"] = normalized_options



        raw_ca = item.get("correct_answer")

        has_explicit_raw_ca = False
        if isinstance(raw_ca, dict) and any(str(k).lower().strip().replace(')', '').replace('.', '') in ['a', 'b', 'c', 'd'] for k in raw_ca.keys()):
            has_explicit_raw_ca = True
        elif isinstance(raw_ca, str) and len(raw_ca.strip()) > 0:
            if re.search(r'(?:[a-d][\.\:\)\/\-\s]*(?:Đ|S|Đúng|Sai)|(?:Đ|S|Đúng|Sai)\s*[\,\;\-]\s*(?:Đ|S|Đúng|Sai))', raw_ca, re.IGNORECASE) or len(re.findall(r'\b(Đ|S|ĐÚNG|SAI)\b', raw_ca, re.IGNORECASE)) >= 2:
                has_explicit_raw_ca = True

        if has_explicit_raw_ca:
            tf_dict = parse_tf_answer(raw_ca)
            for k, v in opt_tf_marks.items():
                tf_dict[k] = v
        elif opt_tf_marks:
            # Chuẩn HocNhanhTN Cách 3 (Gạch chân trực tiếp đáp án đúng):
            # Ký hiệu ĐƯỢC gạch chân / đánh dấu -> Đúng (True)
            # Ký hiệu KHÔNG ĐƯỢC gạch chân / đánh dấu -> Sai (False)
            has_any_true = any(v is True for v in opt_tf_marks.values())
            if has_any_true:
                tf_dict = {k: bool(opt_tf_marks.get(k, False)) for k in ['a', 'b', 'c', 'd']}
            else:
                tf_dict = {k: opt_tf_marks.get(k, True) for k in ['a', 'b', 'c', 'd']}
        else:
            tf_dict = parse_tf_answer(raw_ca)

        item["correct_answer"] = tf_dict

        return item



    # 5. XỬ LÝ DẠNG TRẢ LỜI NGẮN

    elif is_short_answer:

        item["type"] = "short_answer"

        item["options"] = []

        raw_ca = str(item.get("correct_answer", "")).strip()

        raw_ca = re.sub(r'^(?:Đáp án|Đáp số|ĐS|Kết quả|Ans|Answer|x\s*=)\s*[\:\-\=]?\s*', '', raw_ca, flags=re.IGNORECASE).strip()

        if re.match(r'^-?\d+,\d+$', raw_ca):

            raw_ca = raw_ca.replace(',', '.')

        item["correct_answer"] = clean_subscripts_and_formulas(raw_ca)

        return item



    # 6. XỬ LÝ DẠNG TRẮC NGHIỆM NHIỀU LỰA CHỌN (MCQ)

    else:

        item["type"] = "mcq"

        prefixes = ["A. ", "B. ", "C. ", "D. ", "E. ", "F. "]

        normalized_options = []

        option_detected_correct = None



        for idx, opt in enumerate(options[:6]):

            clean_text, is_corr, _, ext_char = clean_option_text(opt)

            clean_text = clean_subscripts_and_formulas(clean_text)

            pref = prefixes[idx] if idx < len(prefixes) else ""

            full_opt = f"{pref}{clean_text}"

            normalized_options.append(full_opt)

            if is_corr and option_detected_correct is None:

                option_detected_correct = full_opt



        item["options"] = normalized_options

        raw_ca_obj = item.get("correct_answer")
        final_ca = None

        if isinstance(raw_ca_obj, dict):
            # Cứu hộ khi AI hoặc parser vô tình gán dict {a: True, b: False} cho câu MCQ
            true_keys = [str(k).upper().replace(')', '').replace('.', '') for k, v in raw_ca_obj.items() if v is True or str(v).lower() in ['true', '1', 'đ', 'đúng']]
            if true_keys:
                target_char = true_keys[0]
                for opt in normalized_options:
                    if opt.startswith(f"{target_char}."):
                        final_ca = opt
                        break

        raw_ca = str(raw_ca_obj or "").strip()

        if raw_ca and not final_ca:
            # 1. Tìm chữ cái A-F bằng word boundary (tránh bắt 'D' trong 'Dap an A')
            m = re.search(r'\b([A-F])\b', raw_ca, re.IGNORECASE)
            if m:
                target_char = m.group(1).upper()
                for opt in normalized_options:
                    if opt.startswith(f"{target_char}."):
                        final_ca = opt
                        break



            # 2. Nếu chưa khớp, so sánh nội dung

            if not final_ca:

                ca_content, _, _, _ = clean_option_text(raw_ca)

                ca_content_clean = clean_subscripts_and_formulas(ca_content).strip()

                if ca_content_clean:

                    for opt in normalized_options:

                        opt_body, _, _, _ = clean_option_text(opt)

                        if ca_content_clean.lower() == opt_body.lower() or ca_content_clean.lower() in opt_body.lower():

                            final_ca = opt

                            break



        if not final_ca:

            final_ca = option_detected_correct or (normalized_options[0] if normalized_options else raw_ca)



        item["correct_answer"] = final_ca
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
        'gemini-3.8-flash',
        'gemini-2.5-flash-lite',
        'gemini-flash-latest'
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

            3. ĐỐI VỚI CÂU HỎI ĐÚNG / SAI (true_false): Mọi câu hỏi có các ý a), b), c), d) BẮT BUỘC gán type: 'true_false', giữ nguyên đủ 4 ý a), b), c), d) trong options: ['a) ...', 'b) ...', 'c) ...', 'd) ...'], đáp án đúng format {{"a": bool, "b": bool, "c": bool, "d": bool}} theo đúng Bảng Đáp Án. TUYỆT ĐỐI KHÔNG GÁN 'short_answer' và TUYỆT ĐỐI KHÔNG để options là []!

            4. ĐỐI VỚI CÂU HỎI TRẢ LỜI NGẮN (short_answer): CHỈ DÀNH CHO câu tính toán ra 1 đáp số duy nhất (số hoặc từ ngắn). options BẮT BUỘC là [], correct_answer lấy chuẩn từ Bảng Đáp Án. TUYỆT ĐỐI KHÔNG dùng cho câu có các ý a), b), c), d).

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
        "4. BẢO TOÀN VÀ XÁC ĐỊNH ĐÁP ÁN ĐÚNG: Tuyệt đối tuân thủ Bảng Đáp Án đi kèm nếu có. "
        "Nếu trong đề không có bảng đáp án tổng hợp, ĐÁP ÁN ĐÚNG được xác định dựa trên bất kỳ dấu hiệu đánh dấu nào của giáo viên: "
        "- Thẻ <u> (chữ cái hoặc nội dung phương án được gạch chân), "
        "- Thẻ <MARK> (chữ được tô đỏ, đổi màu nổi bật, highlight dạ quang, hoặc tô màu nền shading trong Word), "
        "- Dấu hoa thị * (*A., A.*, *a)), "
        "- Dấu tick (✓, ✔, ☑), "
        "- Nhãn [ĐÚNG], (Đúng). "
        "Tuyệt đối KHÔNG tự ý giải lại đề để thay đổi đáp án của tác giả. "
        "5. QUY TẮC BẮT BUỘC PHÂN BIỆT 3 DẠNG CÂU HỎI (CHUẨN GDPT 2018):\n"
        "   - CÂU TRẮC NGHIỆM NHIỀU LỰA CHỌN (type: 'mcq'): BẮT BUỘC có các lựa chọn bắt đầu bằng CHỮ IN HOA 'A.', 'B.', 'C.', 'D.' (hoặc 'A)', 'B)', 'C)', 'D)'). Thí sinh chọn 1 trong 4 lựa chọn. BẮT BUỘC gán type: 'mcq', 'options': ['A. ...', 'B. ...', 'C. ...', 'D. ...'], 'correct_answer': 'X. ...' (chuỗi, ví dụ 'A. Lựa chọn 1'). TUYỆT ĐỐI KHÔNG GÁN type: 'true_false' và KHÔNG ĐƯỢC gán correct_answer dạng object/dict!\n"
        "   - CÂU TRẮC NGHIỆM ĐÚNG / SAI (type: 'true_false'): BẮT BUỘC có 4 ý/mệnh đề bắt đầu bằng CHỮ THƯỜNG 'a)', 'b)', 'c)', 'd)' (hoặc 'a.', 'b.', 'c.', 'd.'). Mỗi ý được đánh giá Đúng hoặc Sai độc lập. BẮT BUỘC gán type: 'true_false', 'options': ['a) ...', 'b) ...', 'c) ...', 'd) ...'], 'correct_answer': {'a': bool, 'b': bool, 'c': bool, 'd': bool}. Khi phương án hoặc nội dung được gạch chân (thẻ <u>), tô đỏ/highlight (thẻ <MARK>), hoặc có dấu *, ý đó là Đúng (true), các ý KHÔNG có dấu hiệu là Sai (false). Hỗ trợ đầy đủ tiền tố ma trận [0, NB], [1, TH], [2, VD], [3, VDC] trong các ý. TUYỆT ĐỐI KHÔNG GÁN type: 'mcq' và KHÔNG GÁN type: 'short_answer'!\n"
        "   - CÂU TRẢ LỜI NGẮN (short_answer): CHỈ DÀNH RIÊNG cho câu tự luận/tính toán điền một đáp số duy nhất (số nguyên, số thập phân, phân số, tọa độ hoặc từ ngắn), options: []. TUYỆT ĐỐI KHÔNG DÙNG CHO CÂU CÓ CÁC PHƯƠNG ÁN A, B, C, D HOẶC CÁC Ý a, b, c, d.\n"
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
               - NGUYÊN TẮC SỐNG CÒN: Khi các lựa chọn là CHỮ IN HOA A, B, C, D (hoặc A), B), C), D)) -> 100% BẮT BUỘC gán type: "mcq". TUYỆT ĐỐI CẤM KHÔNG ĐƯỢC CHUYỂN SANG type: "true_false", KHÔNG ĐƯỢC BIẾN THÀNH a), b), c), d), VÀ KHÔNG ĐƯỢC GÁN correct_answer dạng dictionary!
               - QUY TẮC XÁC ĐỊNH ĐÁP ÁN ĐÚNG CHUẨN XÁC:
                 + Cách 1: Căn cứ Bảng đáp án chính thức / tổng hợp được cung cấp ở trên.
                 + Cách 2: PHƯƠNG ÁN ĐƯỢC ĐÁNH DẤU TRỰC TIẾP LÀ ĐÁP ÁN ĐÚNG:
                   * Có thẻ gạch chân <u> (ở ký hiệu A-D hoặc ở toàn bộ nội dung phương án).
                   * Có thẻ <MARK> (tương ứng với chữ tô đỏ, đổi màu nổi bật, highlight bút dạ quang, hoặc tô màu nền shading trong Word).
                   * Có dấu hoa thị * (*A., A.*) hoặc dấu tick (✓, ✔, ☑).
                   * Có nhãn [ĐÚNG], (Đúng).
                   -> BẮT BUỘC gán phương án đó vào 'correct_answer' (ví dụ: 'A. Lựa chọn 1').
               - Trong mảng 'options' và 'correct_answer', làm sạch các thẻ <MARK>, <u> và dấu * để nội dung câu hỏi sạch đẹp chuẩn sư phạm.
               - explain: Lời giải chi tiết lý do chọn đáp án này.
               - Mẫu JSON:
                 {{
                   "question_number": 1,
                   "type": "mcq",
                   "group_title": "",
                   "question": "Nội dung câu hỏi...",
                   "options": ["A. Lựa chọn 1", "B. Lựa chọn 2", "C. Lựa chọn 3", "D. Lựa chọn 4"],
                   "correct_answer": "A. Lựa chọn 1",
                   "explain": "Lời giải chi tiết..."
                 }}

            2. PHẦN II: TRẮC NGHIỆM ĐÚNG / SAI (type: "true_false")
               - Mỗi câu gồm 4 ý/mệnh đề độc lập: a), b), c), d) (tiền tố 'a) ', 'b) ', 'c) ', 'd) ' - BẮT BUỘC LÀ CHỮ THƯỜNG).
               - ĐẶC TRƯNG BẮT BUỘC: CHỈ GÁN type: "true_false" cho câu hỏi có các ý/mệnh đề là CHỮ THƯỜNG a), b), c), d). TUYỆT ĐỐI KHÔNG GÁN type: "true_false" cho câu có phương án chữ in hoa A, B, C, D!
               - HỖ TRỢ MA TRẬN MỨC ĐỘ NHẬN THỨC THEO CHUẨN HocNhanhTN:
                 Nếu có tiền tố ma trận như [0, NB], [1, TH], [2, VD], [3, VDC] (hoặc [NB], [TH], [VD], [VDC]) đặt trước hoặc sau ký hiệu a), b), c), d), HÃY BẢO TOÀN NGUYÊN VẸN tiền tố đó trong nội dung mệnh đề (ví dụ: 'a) [0, NB] Mệnh đề a' hoặc 'a) Mệnh đề a'), KHÔNG LÀM MẤT tiền tố và KHÔNG LẶP ký hiệu 'a) a)'.
               - QUY TẮC XÁC ĐỊNH ĐÁP ÁN ĐÚNG/SAI CHUẨN HocNhanhTN:
                 + Cách 1: Căn cứ Bảng đáp án tổng hợp (sau chữ HẾT) hoặc Bảng đáp án chính thức được cung cấp ở trên.
                 + Cách 2: Bảng đáp án riêng đặt ngay dưới từng câu hỏi (cột Đúng / Sai có dấu x, v, 1, ✓; hoặc hàng a, b, c, d với Đ, S).
                 + Cách 3: Gạch chân (thẻ <u>) hoặc highlight/tô màu đỏ/nền (thẻ <MARK>) hoặc dấu * hoặc dấu tick (✓, ✔, ☑) trực tiếp ở ký hiệu HOẶC ở nội dung mệnh đề:
                   * Mệnh đề CÓ bất kỳ dấu hiệu đánh dấu nào trên -> ĐÚNG (true)
                   * Mệnh đề KHÔNG CÓ dấu hiệu đánh dấu -> SAI (false)
               - Trong 'options', làm sạch các thẻ <MARK>, <u> và dấu * để hiển thị chuẩn đẹp.
               - correct_answer: Đối tượng quy định Đúng (true) hoặc Sai (false) cho từng ý:
                 {{"a": true, "b": false, "c": true, "d": false}}
               - explain: Lời giải chi tiết giải thích rõ lý do vì sao từng ý a, b, c, d là Đúng hoặc Sai.
               - Mẫu JSON:
                 {{
                   "question_number": 1,
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
               - LƯU Ý ĐẶC BIỆT: TUYỆT ĐỐI KHÔNG GÁN type: "short_answer" cho các câu có các ý a), b), c), d). Mọi câu có ý a, b, c, d PHẢI LÀ type: "true_false"!
               - Mẫu JSON:
                 {{
                   "question_number": 1,
                   "type": "short_answer",
                   "group_title": "PHẦN III. Câu trắc nghiệm trả lời ngắn...",
                   "question": "Nội dung câu hỏi tính toán...",
                   "options": [],
                   "correct_answer": "12.5",
                   "explain": "Lời giải từng bước tính..."
                 }}

            QUY TẮC BẮT BUỘC VỀ ĐỊNH DẠNG:
            0. NGUYÊN TẮC CỐT LÕI ĐỂ PHÂN BIỆT TRẮC NGHIỆM (mcq) VÀ ĐÚNG SAI (true_false):
               - Lựa chọn là CHỮ IN HOA A, B, C, D -> 100% BẮT BUỘC type: "mcq", options: ["A. ...", "B. ...", "C. ...", "D. ..."], correct_answer: "X. ...". TUYỆT ĐỐI KHÔNG chuyển thành true_false, KHÔNG đổi sang a, b, c, d!
               - Ý/mệnh đề là CHỮ THƯỜNG a), b), c), d) -> 100% BẮT BUỘC type: "true_false", options: ["a) ...", "b) ...", "c) ...", "d) ..."], correct_answer: {{"a": bool, "b": bool, "c": bool, "d": bool}}.
            1. TUYỆT ĐỐI KHÔNG ĐỂ TIỀN TỐ "Câu 1:", "Câu 2:", "1." vào trường "question". Chỉ lấy nội dung câu hỏi thuần túy (ví dụ: "Cho hàm số y = f(x)..." thay vì "Câu 1: Cho hàm số y = f(x)...").
            2. group_title: Chỉ điền khi là tiêu đề mở đầu cho một phần/bài đọc (ví dụ: "PHẦN II. Trắc nghiệm Đúng/Sai"). TUYỆT ĐỐI KHÔNG sao chép lặp lại group_title ở từng câu hỏi đơn lẻ.
            3. DẠNG TRẮC NGHIỆM (mcq): Các phương án trong "options" PHẢI có dạng 'A. [Nội dung]', 'B. [Nội dung]', 'C. [Nội dung]', 'D. [Nội dung]'. "correct_answer" BẮT BUỘC PHẢI KHỚP NGUYÊN VĂN với một trong 4 phương án đó (ví dụ: "A. [Nội dung]"). TUYỆT ĐỐI KHÔNG thêm dấu hoa thị '*' hay thẻ [ĐÚNG] vào options.
            4. DẠNG ĐÚNG/SAI (true_false): Bất kỳ câu nào có 4 mệnh đề a), b), c), d) BẮT BUỘC PHẢI gán type là 'true_false'. Các ý trong "options" PHẢI có dạng 'a) [Nội dung]', 'b) [Nội dung]', 'c) [Nội dung]', 'd) [Nội dung]'. TUYỆT ĐỐI KHÔNG gán type là 'short_answer' và KHÔNG để options rỗng! TUYỆT ĐỐI KHÔNG ghi kết quả [ĐÚNG], [SAI], (Đúng), (Sai) vào nội dung phương án. Kết quả Đúng/Sai phải được thể hiện trong object "correct_answer": {{"a": true, "b": false, "c": true, "d": false}}.
            5. DẠNG TRẢ LỜI NGẮN (short_answer): CHỈ DÀNH CHO câu tính ra 1 đáp số. "options" BẮT BUỘC là mảng rỗng []. "correct_answer" là chuỗi đáp số ngắn (ví dụ: "12", "-3.5"). TUYỆT ĐỐI KHÔNG dùng cho câu có các ý a, b, c, d.
            6. CHỈ SỐ DƯỚI & CÔNG THỨC HÓA HỌC: Giữ nguyên thẻ <sub> và <sup>, TUYỆT ĐỐI KHÔNG viết thành CH_2, CO_2, H_2O. Phải viết là CH<sub>2</sub>, CO<sub>2</sub>, H<sub>2</sub>O hoặc \(\text{{CH}}_2\).
            7. CÔNG THỨC TOÁN LATEX: Mọi biểu thức toán học phải bọc trong \( và \).
            8. TUYỆT ĐỐI KHÔNG ĐƯỢC XÓA BỎ các thẻ [IMG_X]. Phải sao chép NGUYÊN XI, ĐÚNG TỪNG KÝ TỰ các placeholder [IMG_X] vào câu hỏi hoặc đáp án tương ứng.
            9. Chỉ trả về duy nhất mảng JSON [...] không có văn bản giải thích nào khác ngoài JSON.{img_strict_rule}

            

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

                

                fixed_raw = fix_json_latex_escapes(raw_text)
                parsed_json = None
                
                if json_repair is not None:
                    try:
                        parsed_json = json_repair.loads(fixed_raw)
                    except Exception:
                        try:
                            parsed_json = json_repair.loads(raw_text)
                        except Exception:
                            pass
                            
                if parsed_json is None:
                    match = re.search(r'\[\s*\{.*\}\s*\]', fixed_raw, re.DOTALL)
                    json_text = match.group(0) if match else fixed_raw
                    try:
                        parsed_json = json.loads(json_text, strict=False)
                    except Exception:
                        pass

                # Nếu AI trả về bọc trong Object {"questions": [...]}, tự động trích xuất danh sách
                if isinstance(parsed_json, dict):
                    for k in ["questions", "data", "quiz", "result", "items", "cau_hoi", "list"]:
                        if isinstance(parsed_json.get(k), list):
                            parsed_json = parsed_json[k]
                            break
                    else:
                        if "question" in parsed_json:
                            parsed_json = [parsed_json]
                        else:
                            parsed_json = []

                if isinstance(parsed_json, list):
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



