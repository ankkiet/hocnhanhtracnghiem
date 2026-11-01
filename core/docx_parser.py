import base64

import re

from typing import Any, Dict, List, Optional, Tuple



from docx import Document

from docx.oxml.ns import nsmap, qn



if 'o' not in nsmap:

    nsmap['o'] = 'urn:schemas-microsoft-com:office:office'

if 'v' not in nsmap:

    nsmap['v'] = 'urn:schemas-microsoft-com:vml'

from docx.table import Table

from docx.text.paragraph import Paragraph



from core.answer_key_extractor import (

    AnswerKeyMap,

    align_mcq_correct_answer,

    extract_answer_key_from_doc,

    reconcile_quiz_with_answer_key,

)

from core.image_converter import process_image_blob

from core.mathml_parser import parse_omath

from services.ai_service import restore_image_placeholders

from services.r2_service import upload_image_to_r2



# Biên dịch sẵn Regex (Tối ưu tốc độ quét vòng lặp văn bản)

RE_NUMBERING = re.compile(r'^\s*(Câu|Bài|Question|Q|\d+[\.\:\)]|\*?\s*[A-F][\.\:\)])', re.IGNORECASE)

RE_GROUP_TITLE = re.compile(r'^\s*(PHẦN|PART|CHƯƠNG|BÀI TẬP|TEST|PRACTICE|MỨC ĐỘ|DẠNG|I{1,3}\.|IV\.|V\.|VI{0,3}\.)\b', re.IGNORECASE)





def extract_answer_key(doc: Any, full_text: str = "") -> AnswerKeyMap:

    """Tự động dò tìm và bóc tách Bảng đáp án ở cuối tài liệu Word theo chuẩn Bộ GD&ĐT"""

    return extract_answer_key_from_doc(doc, full_text)





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

    """Thay thế các placeholder [IMG_X] thành thẻ img HTML."""

    if isinstance(data, dict):

        return {k: replace_placeholders(v, mapping) for k, v in data.items()}

    elif isinstance(data, list):

        return [replace_placeholders(v, mapping) for v in data]

    elif isinstance(data, str):

        data = restore_image_placeholders(data)

        for ph, img_tag in mapping.items():

            num_match = re.search(r'\d+', ph)

            if num_match:

                num = num_match.group(0)

                pattern = re.compile(

                    r'\\?\[\s*(?:IMG|HÍNH|HÌNH|ẢNH|HINH|ANH|ảnh|IMAGE|PIC|PICTURE)?[\s_#-]*' + re.escape(num) + r'\s*\\?\]'

                    r'|\b(?:IMG|HÍNH|HÌNH|ẢNH|HINH|ANH|IMAGE|PIC)[\s_-]+' + re.escape(num) + r'\b',

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





def get_auto_numbering_prefix(para, doc, counters: dict) -> str:
    """Khôi phục lại text (Câu X / A, B / a, b / 1, 2) khi giáo viên dùng List Tự động trong Word"""
    pPr = para._p.pPr
    if pPr is None or pPr.numPr is None or pPr.numPr.numId is None:
        return ""

    numId = pPr.numPr.numId.val
    ilvl = pPr.numPr.ilvl.val if pPr.numPr.ilvl is not None else 0
    numFmt = "decimal"
    lvlText = "%1."

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
                        lvlText_el = lvl.xpath('./*[local-name()="lvlText"]')
                        if lvlText_el:
                            lvlText = lvlText_el[0].get(qn('w:val'))
                        break
    except Exception:
        pass

    if numFmt == "lowerLetter":
        counters['sub'] = counters.get('sub', 0) + 1
        delim = ")" if ")" in lvlText else "."
        char = chr(ord('a') + (counters['sub'] - 1) % 26)
        return f"{char}{delim} "
    elif numFmt == "upperLetter":
        counters['opt'] = counters.get('opt', 0) + 1
        delim = ")" if ")" in lvlText else "."
        char = chr(ord('A') + (counters['opt'] - 1) % 26)
        return f"{char}{delim} "
    elif numFmt in ["upperRoman", "lowerRoman"]:
        counters['roman'] = counters.get('roman', 0) + 1
        val = counters['roman']
        roman_map = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X'}
        roman_str = roman_map.get(val, f"I{val}")
        return f"{roman_str}. "
    else:
        if "câu" in lvlText.lower() or "bài" in lvlText.lower():
            counters['q'] = counters.get('q', 0) + 1
            counters['opt'] = 0
            delim = ":" if ":" in lvlText else "."
            return f"Câu {counters['q']}{delim} "
        else:
            counters['dec'] = counters.get('dec', 0) + 1
            delim = ")" if ")" in lvlText else "."
            return f"{counters['dec']}{delim} "

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





def split_merged_options(options: List[str]) -> List[str]:

    """Hàm cứu hộ: Nếu 1 phương án bị gộp nhiều đáp án (ví dụ A chứa cả B, C, D), tự động bóc tách."""

    if not options or len(options) >= 4:

        return options



    has_merged = False

    for opt in options:

        if re.search(r'(?:(?<=[;\.\:\?!])\s*|\t|\s{2,})[B-F][\.\:\)\/\-]\s*', opt):

            has_merged = True

            break

    if not has_merged:

        return options



    new_options = []

    opt_split_pattern = re.compile(

        r'(?:^|\n|\t|\s{2,}|(?<=[;\.\:\?!])\s*|(?<=[\)\}\]\'\"\>])\s{2,})(?:\(?\[?([A-F])(?:[\.\:\/\)\]\-]|\b))\s*',

        re.IGNORECASE

    )



    for opt in options:

        matches = list(opt_split_pattern.finditer(opt))

        if len(matches) <= 1:

            new_options.append(opt)

        else:

            for k, m in enumerate(matches):

                char = m.group(1).upper()

                c_start = m.end()

                c_end = matches[k+1].start() if k+1 < len(matches) else len(opt)

                content = opt[c_start:c_end].strip()

                new_options.append(f"{char}. {content}")



    return new_options





def evaluate_correct_answer(options: List[Dict], full_text: str, format_weights: List[int], char_html: List[str] = None) -> str:

    """So sánh trọng số giữa các đáp án (A,B,C,D) để lọc ra đáp án chính xác nhất dựa trên định dạng."""

    def get_html(start, end):

        if not char_html: return ""

        joined = "".join(char_html[start:end])

        for tag in ['b', 'i', 'u', 'sup', 'sub']:

            joined = joined.replace(f"</{tag}><{tag}>", "")

        return joined.strip()



    for opt in options:

        if opt.get('is_asterisk'):

            if char_html:

                return f"{opt['char']}. {get_html(opt['content_start'], opt['end_idx'])}"

            else:

                opt_len = split_option_and_leading_text(opt['text_raw'])

                return f"{opt['char']}. {opt['text_raw'][:opt_len].strip()}"

            

    best_score = -1

    best_option_text = None

    

    for opt in options:

        score = 0

        start_idx = opt['start_idx']

        content_start = opt['marker_end']

        content_end = opt['end_idx']

        

        marker_weight = format_weights[start_idx] if start_idx < len(format_weights) else 0

        if marker_weight == 3: score += 1000

        elif marker_weight == 2: score += 500

        elif marker_weight == 1: score += 100

        

        if content_start < content_end:

            content_weights = format_weights[content_start:content_end]

            alnum_count = sum(1 for i in range(content_start, content_end) if i < len(full_text) and full_text[i].isalnum())

            

            if alnum_count > 0:

                formatted_chars = sum(1 for i, w in enumerate(content_weights) if w > 0 and (content_start+i) < len(full_text) and full_text[content_start+i].isalnum())

                max_w = max(content_weights) if content_weights else 0

                ratio = formatted_chars / alnum_count

                

                if ratio > 0.4:

                    if max_w == 3: score += 800

                    elif max_w == 2: score += 400

                    elif max_w == 1: score += 80

                elif formatted_chars >= 2:

                    if max_w == 3: score += 300

                    elif max_w == 2: score += 150

                    elif max_w == 1: score += 20

                    

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





def inspect_run_formatting(rPr, run_text: str = ""):

    """

    Phát hiện toàn diện các đặc trưng định dạng dùng để đánh dấu đáp án đúng trong Word:

    1. Gạch chân (w:u): Gạch chân chữ cái A-D, a-d hoặc gạch chân toàn bộ nội dung phương án

    2. Bút dạ quang (w:highlight): Tô vàng, xanh, hồng, lục...

    3. Thùng sơn / Màu nền (w:shd): Tô nền ký tự hoặc ô

    4. Màu chữ nổi bật (w:color): Chữ đỏ, cam, xanh lá, xanh dương, tím... (khác màu đen/auto)

    5. Ký tự tick (✓, ✔, ☑)

    6. In đậm (w:b), In nghiêng (w:i), Chỉ số dưới (subscript), Chỉ số trên (superscript)

    """

    is_bold = is_italic = is_underline = is_highlighted = is_red_text = is_subscript = is_superscript = False



    if rPr is not None:

        b_node = rPr.find(qn('w:b'))

        if b_node is not None and str(b_node.get(qn('w:val'), '')).lower() not in ['none', '0', 'false', 'off']:

            is_bold = True



        i_node = rPr.find(qn('w:i'))

        if i_node is not None and str(i_node.get(qn('w:val'), '')).lower() not in ['none', '0', 'false', 'off']:

            is_italic = True



        u_node = rPr.find(qn('w:u'))

        if u_node is not None and str(u_node.get(qn('w:val'), '')).lower() not in ['none', '0', 'false', 'off']:

            is_underline = True



        hl_node = rPr.find(qn('w:highlight'))

        if hl_node is not None and str(hl_node.get(qn('w:val'), '')).lower() not in ['none', '', '0']:

            is_highlighted = True



        shd_node = rPr.find(qn('w:shd'))

        if shd_node is not None:

            shd_val = str(shd_node.get(qn('w:fill'), '')).upper()

            if shd_val not in ['', 'NONE', 'AUTO', 'FFFFFF', '000000']:

                is_highlighted = True



        c_node = rPr.find(qn('w:color'))

        if c_node is not None:

            c_val = str(c_node.get(qn('w:val'), '')).upper()

            if c_val not in ['', 'AUTO', '000000', '111111', '222222', '333333', 'NONE', 'WINDOWSTEXT', 'DEFAULT']:

                is_red_text = True



        va_node = rPr.find(qn('w:vertAlign'))

        if va_node is not None:

            val = va_node.get(qn('w:val'))

            if val == 'subscript':

                is_subscript = True

            elif val == 'superscript':

                is_superscript = True



    if any(t in run_text for t in ['✓', '✔', '☑']):

        is_red_text = True



    return is_bold, is_italic, is_underline, is_highlighted, is_red_text, is_subscript, is_superscript





def extract_formatting_from_docx(file_path: str) -> List[Dict[str, Any]]:

    """Thuật toán phân tách Câu hỏi trắc nghiệm siêu tốc và thông minh từ tệp DOCX."""

    doc = Document(file_path)

    full_text_list = []

    format_weights = []

    char_html = []

    image_mapping = {}

    img_counter = 0

    counters = {'q': 0, 'opt': 0}

    

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

                

        for node in para._element.xpath('.//*[local-name()="t" or local-name()="tab" or local-name()="br" or local-name()="cr" or local-name()="drawing" or local-name()="pict" or local-name()="object" or local-name()="oMath"]'):

            if node.xpath('ancestor::*[local-name()="oMath"]') and not node.tag.endswith('}oMath'):

                continue

                

            if node.tag.endswith('}tab'):

                full_text_list.append("\t")

                format_weights.append(0)

                char_html.append("\t")

            elif node.tag.endswith('}br') or node.tag.endswith('}cr'):

                full_text_list.append("\n")

                format_weights.append(0)

                char_html.append("\n")

            elif node.tag.endswith('}oMath'):

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

                img_nodes = node.xpath('.//*[local-name()="blip" or local-name()="imagedata" or local-name()="svgBlip"]')

                if not img_nodes:

                    continue

                extent = node.xpath('.//*[local-name()="extent"]')

                img_style = "max-width: 100%; height: auto;"

                if extent:

                    try:

                        cx = int(extent[0].get('cx', 0))

                        if cx > 0:

                            px_width = int(cx / 9525)

                            if px_width <= 2:

                                continue

                            img_style = f"width: {px_width}px; max-width: 100%; height: auto; vertical-align: middle; margin: 4px;"

                    except Exception:

                        pass

                        

                processed_rids = set()

                for img_node in img_nodes:

                    try:

                        if img_node.tag.endswith('}svgBlip') and img_node.xpath('ancestor::*[local-name()="blip"]'):

                            continue



                        rId, image_part = find_image_part_and_id(img_node, doc)

                        if rId and rId not in processed_rids and image_part is not None:

                            processed_rids.add(rId)

                            mime_type = image_part.content_type

                            blob = image_part.blob

                            if not blob or len(blob) < 50:

                                continue



                            processed_blob, processed_mime = process_image_blob(blob, mime_type)

                            if not processed_blob:

                                continue



                            img_url = upload_image_to_r2(processed_blob, mime_type=processed_mime)

                            img_tag = None

                            if img_url:

                                img_tag = f"<br><img src='{img_url}' class='quiz-image' style='{img_style}' /><br>"

                            elif processed_mime and processed_mime.startswith("image/"):

                                b64_encoded = base64.b64encode(processed_blob).decode('utf-8')

                                img_tag = f"<br><img src='data:{processed_mime};base64,{b64_encoded}' class='quiz-image' style='{img_style}' /><br>"

                            

                            if img_tag:

                                img_counter += 1

                                placeholder = f"[IMG_{img_counter}]"

                                image_mapping[placeholder] = img_tag

                                full_text_list.append(f"\n{placeholder}\n")

                                format_weights.extend([0] * len(f"\n{placeholder}\n"))

                                char_html.extend(list(f"\n{placeholder}\n"))

                    except Exception as img_err:

                        print(f"[CẢNH BÁO] Không thể xử lý ảnh: {img_err}")

            elif node.tag.endswith('}t'):

                run_text = node.text

                if not run_text: continue

                

                r = node.getparent()

                rPr = r.xpath('./*[local-name()="rPr"]')[0] if r is not None and r.tag.endswith('}r') and r.xpath('./*[local-name()="rPr"]') else None

                is_bold, is_italic, is_underline, is_highlighted, is_red_text, is_subscript, is_superscript = inspect_run_formatting(rPr, run_text)

                

                full_text_list.append(run_text)

                weight = 3 if (is_red_text or is_highlighted or is_underline) else (1 if is_bold else 0)

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



    # Nhận diện biểu thức phân đoạn

    from core.text_parser import extract_explain_from_block

    q_regex = r'(?:^|\n)\s*(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])(?:\s+|$)'

    opt_regex = r'(?:^|\n|\t|\s{2,}|(?<=[;\.\:\?!])\s*|(?<=[\)\}\]\'\"\>])\s*|(?<=\s)(?=[B-F][\.\:\)\/\-]))(?:\(?\[?(\*?[A-F])(?:[\.\:\/\)\]\-]|\b))(?:\s+|$)'

    token_pattern = re.compile(f'({q_regex})|({opt_regex})', re.IGNORECASE)

    

    matches = list(token_pattern.finditer(full_text))

    if not matches: return []



    extracted_data = []

    current_q_start = 0

    current_q_end = 0

    options = []

    last_idx = 0

    state = "OUTSIDE"

    shared_context = ""

    

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

                q_text_html = get_html(current_q_start, current_q_end)

                opts_html = [f"{opt['char']}. {get_html(opt['content_start'], opt['end_idx'])}" for opt in options]

                q_text_clean, explain = extract_explain_from_block(q_text_html)

                if not explain and opts_html:

                    last_opt_clean, explain = extract_explain_from_block(opts_html[-1])

                    if explain:

                        opts_html[-1] = last_opt_clean

                    

                extracted_data.append({

                    "group_title": shared_context,

                    "question": q_text_clean,

                    "options": opts_html,

                    "correct_answer": correct_ans,

                    "explain": explain

                })

                

                if lead_part_raw.strip():

                    shared_context = get_html(last_idx + opt_len, match_start)

                current_q_start = match_end

                current_q_end = match_end

            elif state == "IN_QUESTION":

                q_text = get_html(current_q_start, match_start)

                if q_text.strip():

                    q_text_clean, explain = extract_explain_from_block(q_text)

                    extracted_data.append({

                        "group_title": shared_context,

                        "question": q_text_clean,

                        "options": [],

                        "correct_answer": "",

                        "explain": explain

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

        q_text_html = get_html(current_q_start, current_q_end)

        opts_html = [f"{opt['char']}. {get_html(opt['content_start'], opt['end_idx'])}" for opt in options]

        q_text_clean, explain = extract_explain_from_block(q_text_html)

        if not explain and opts_html:

            last_opt_clean, explain = extract_explain_from_block(opts_html[-1])

            if explain:

                opts_html[-1] = last_opt_clean

        extracted_data.append({

            "group_title": shared_context,

            "question": q_text_clean,

            "options": opts_html,

            "correct_answer": correct_ans,

            "explain": explain

        })

    elif state == "IN_QUESTION":

        q_text = get_html(current_q_start, len(full_text))

        if q_text.strip():

            q_text_clean, explain = extract_explain_from_block(q_text)

            extracted_data.append({

                "group_title": shared_context,

                "question": q_text_clean,

                "options": [],

                "correct_answer": "",

                "explain": explain

            })



    try:

        answer_key = extract_answer_key_from_doc(doc, full_text)

        if answer_key:

            extracted_data = reconcile_quiz_with_answer_key(extracted_data, answer_key)

    except Exception as e:

        print(f"[CẢNH BÁO] Lỗi đọc bảng đáp án: {e}")



    for q_item in extracted_data:

        if q_item.get("type", "mcq") == "mcq" and q_item.get("options"):

            q_item["options"] = split_merged_options(q_item["options"])

            if q_item.get("correct_answer"):

                q_item["correct_answer"] = align_mcq_correct_answer(q_item["correct_answer"], q_item["options"])



    if image_mapping:

        extracted_data = replace_placeholders(extracted_data, image_mapping)



    return extracted_data





def parse_hocnhanhtn_tf_table(table: Table) -> Optional[Dict[str, bool]]:

    """

    Kiểm tra và bóc tách bảng đáp án Đúng/Sai đặt ngay dưới từng câu hỏi (chuẩn HocNhanhTN Cách 2).

    Trả về dict {'a': bool, 'b': bool, 'c': bool, 'd': bool} nếu phát hiện, ngược lại None.

    Hàm này duy trì tương thích ngược 100% với các hàm gọi cũ.

    """

    res = parse_hocnhanhtn_tf_table_full(table)

    if res:

        return res[0]

    return None





def _process_p_element(p_element, doc, counters: dict, image_mapping: dict) -> str:

    """Xử lý định dạng HTML, toán LaTeX và hình ảnh cho một phần tử paragraph <w:p>"""

    para = Paragraph(p_element, doc._body)

    raw_text = "".join(node.text for node in para._element.iter() if node.tag.endswith('}t') and node.text)

    has_text = bool(raw_text.strip())

    has_media = bool(para._element.xpath('.//*[local-name()="drawing" or local-name()="pict" or local-name()="object" or local-name()="oMath"]'))

    if not has_text and not has_media:

        return ""



    para_text = ""

    prefix = get_auto_numbering_prefix(para, doc, counters)

    if prefix:

        para_text_strip = raw_text.strip()

        is_numbering_text = RE_NUMBERING.match(para_text_strip)

        is_group_title = RE_GROUP_TITLE.match(para_text_strip)

        if not is_numbering_text and not is_group_title:

            para_text += prefix



    for node in para._element.xpath('.//*[local-name()="t" or local-name()="tab" or local-name()="br" or local-name()="cr" or local-name()="drawing" or local-name()="pict" or local-name()="object" or local-name()="oMath"]'):

        if node.xpath('ancestor::*[local-name()="oMath"]') and not node.tag.endswith('}oMath'):

            continue



        if node.tag.endswith('}tab'):

            para_text += "\t"

        elif node.tag.endswith('}br') or node.tag.endswith('}cr'):

            para_text += "\n"

        elif node.tag.endswith('}oMath'):

            math_latex = parse_omath(node)

            if math_latex:

                encoded_math = math_latex.replace("<", "&lt;").replace(">", "&gt;")

                para_text += f" \\({encoded_math}\\) "

        elif node.tag.endswith('}drawing') or node.tag.endswith('}pict') or node.tag.endswith('}object'):

            img_nodes = node.xpath('.//*[local-name()="blip" or local-name()="imagedata" or local-name()="svgBlip"]')

            if not img_nodes:

                continue

            extent = node.xpath('.//*[local-name()="extent"]')

            img_style = "max-width: 100%; height: auto;"

            if extent:

                try:

                    cx = int(extent[0].get('cx', 0))

                    if cx > 0:

                        px_width = int(cx / 9525)

                        if px_width <= 2:

                            continue

                        img_style = f"width: {px_width}px; max-width: 100%; height: auto; vertical-align: middle; margin: 4px;"

                except Exception:

                    pass



            processed_rids = set()

            for img_node in img_nodes:

                try:

                    if img_node.tag.endswith('}svgBlip') and img_node.xpath('ancestor::*[local-name()="blip"]'):

                        continue



                    rId, image_part = find_image_part_and_id(img_node, doc)

                    if rId and rId not in processed_rids and image_part is not None:

                        processed_rids.add(rId)

                        mime_type = image_part.content_type

                        blob = image_part.blob

                        if not blob or len(blob) < 50:

                            continue



                        processed_blob, processed_mime = process_image_blob(blob, mime_type)

                        if not processed_blob:

                            continue



                        img_url = upload_image_to_r2(processed_blob, mime_type=processed_mime)

                        img_tag = None

                        if img_url:

                            img_tag = f"<img src='{img_url}' class='quiz-image' style='{img_style}' />"

                        elif processed_mime and processed_mime.startswith("image/"):

                            b64_encoded = base64.b64encode(processed_blob).decode('utf-8')

                            img_tag = f"<img src='data:{processed_mime};base64,{b64_encoded}' class='quiz-image' style='{img_style}' />"



                        if img_tag:

                            img_counter = len(image_mapping) + 1

                            placeholder = f"[IMG_{img_counter}]"

                            image_mapping[placeholder] = img_tag

                            para_text += f"\n{placeholder}\n"

                except Exception as img_err:

                    print(f"[CẢNH BÁO] parse_docx_to_marked_text lỗi ảnh: {img_err}")

        elif node.tag.endswith('}t'):

            run_text = node.text

            if not run_text: continue



            r = node.getparent()

            rPr = r.xpath('./*[local-name()="rPr"]')[0] if r is not None and r.tag.endswith('}r') and r.xpath('./*[local-name()="rPr"]') else None

            is_bold, is_italic, is_underline, is_highlighted, is_red_text, is_subscript, is_superscript = inspect_run_formatting(rPr, run_text)



            formatted_text = run_text.replace("<", "&lt;").replace(">", "&gt;")

            if is_subscript: formatted_text = f"<sub>{formatted_text}</sub>"

            if is_superscript: formatted_text = f"<sup>{formatted_text}</sup>"

            if is_italic: formatted_text = f"<i>{formatted_text}</i>"

            if is_underline: formatted_text = f"<u>{formatted_text}</u>"

            if is_bold: formatted_text = f"<b>{formatted_text}</b>"



            if is_red_text or is_highlighted or is_underline:

                para_text += f"<MARK>{formatted_text}</MARK>"

            else:

                para_text += formatted_text



    return para_text





def is_cell_shaded(cell) -> bool:

    """Kiểm tra xem ô bảng Word có được tô màu nền (highlight/shading) hay không"""

    try:

        tcPr = cell._tc.get_or_add_tcPr()

        shd = tcPr.find(qn('w:shd'))

        if shd is not None:

            fill = str(shd.get(qn('w:fill'), '')).upper()

            if fill and fill not in ['AUTO', 'NONE', 'FFFFFF', '000000', 'CLEAR']:

                return True

    except Exception:

        pass

    return False





def _extract_cell_content(cell, doc=None, counters: Optional[dict] = None, image_mapping: Optional[dict] = None) -> str:

    """Trích xuất nội dung văn bản, LaTeX và hình ảnh trong một ô bảng Word"""

    if not cell:

        return ""

    if doc is not None and counters is not None and image_mapping is not None:

        cell_paras = []

        for cp in cell._element.xpath('.//*[local-name()="p"]'):

            pt = _process_p_element(cp, doc, counters, image_mapping)

            if pt.strip():

                cell_paras.append(pt.strip())

        return " ".join(cell_paras)

    return cell.text.strip()





def is_answer_key_table(table: Table) -> bool:

    """Kiểm tra xem bảng có phải là Bảng đáp án tổng hợp ở cuối đề thi không."""

    if not table or not table.rows or len(table.rows) < 2:

        return False



    if len(table.rows) == 2:

        r0 = [c.text.strip() for c in table.rows[0].cells]

        r1 = [c.text.strip() for c in table.rows[1].cells]

        nums = [c for c in r0 if re.search(r'(?:Câu\s*)?\d+', c)]

        ans_chars = [c for c in r1 if re.match(r'^[A-FĐS]$', c, re.IGNORECASE) or re.search(r'^[a-d][\.\:\)\ blank\/\-\s]*(?:Đ|S)', c, re.IGNORECASE)]

        if len(nums) >= 3 and len(ans_chars) >= len(nums) * 0.7:

            return True



    h_texts = [c.text.strip().lower() for c in table.rows[0].cells]
    # Bảng câu hỏi hoặc ngân hàng đề tuyệt đối KHÔNG PHẢI bảng đáp án
    has_question_content_col = any(any(k in h for k in ['nội dung', 'câu hỏi', 'phương án', 'lựa chọn']) for h in h_texts)
    if has_question_content_col:
        return False


    has_q_col = any(re.search(r'^(?:câu|stt|số tt)\b', h) for h in h_texts)

    has_a_col = any(re.search(r'^(?:đáp án|đa|key|kết quả)\b', h) for h in h_texts)

    if has_q_col and has_a_col:

        short_ans_count = 0

        for r in table.rows[1:min(6, len(table.rows))]:

            for c in r.cells:

                txt = c.text.strip()

                if re.match(r'^[A-F]$', txt, re.IGNORECASE) or re.match(r'^[ĐS]$', txt, re.IGNORECASE):

                    short_ans_count += 1

        if short_ans_count >= 2:

            return True



    return False





def parse_hocnhanhtn_tf_table_full(table: Table, doc=None, counters=None, image_mapping=None) -> Optional[Tuple[Dict[str, bool], List[str]]]:
    """
    Bóc tách bảng Đúng / Sai toàn diện và trả về cả đáp án lẫn nội dung mệnh đề:
    - Bảng dọc 3 cột hoặc 4 cột: [Ý], [Mệnh đề/Khẳng định/Lệnh hỏi], [Đúng], [Sai]
    - Bảng dọc 2 cột: [Mệnh đề], [Đúng/Sai hoặc Đ/S]
    - Bảng ngang: Hàng chứa các ý a, b, c, d; Hàng tiếp theo chứa Đ, S (hoặc kèm nội dung)
    - Bảng không tiêu đề nhưng bắt đầu bằng ý a, b, c, d
    - Đánh dấu bằng ký tự (x, v, 1, ✓, ✔, Đ) hoặc tô màu nền (cell shading).
    Trả về: (tf_dict, statements) nếu phát hiện, ngược lại None.
    """
    if not table or not table.rows or len(table.rows) < 2:
        return None

    num_rows = len(table.rows)

    # 1. KIỂM TRA DẠNG NGANG (Hàng chứa a, b, c, d; Hàng tiếp theo chứa Đ, S)
    for r_idx in range(num_rows - 1):
        row_labels = [c.text.strip().lower() for c in table.rows[r_idx].cells]
        matched_cols = {}
        for c_idx, lab in enumerate(row_labels):
            m = re.match(r'^\s*(?:(?:lệnh hỏi|ý|phương án|mệnh đề|câu)\s*)?([a-d])[\)\.\:\-]?\s*$', lab, re.IGNORECASE)
            if m:
                matched_cols[m.group(1).lower()] = c_idx

        if len(matched_cols) >= 2:
            val_row_idx = None
            content_row_idx = None
            for next_r in range(r_idx + 1, num_rows):
                test_vals = [c.text.strip().lower() for c in table.rows[next_r].cells]
                is_val_row = any(re.match(r'^(?:[đstf10xv✓✔]|đúng|sai|true|false)$', v.strip(), re.IGNORECASE) for v in test_vals if v.strip())
                if is_val_row:
                    val_row_idx = next_r
                    if next_r == r_idx + 2:
                        content_row_idx = r_idx + 1
                    break

            if val_row_idx is not None:
                row_vals = [c.text.strip().lower() for c in table.rows[val_row_idx].cells]
                tf_dict = {}
                statements = []
                for char_key in ['a', 'b', 'c', 'd']:
                    if char_key in matched_cols:
                        c_idx = matched_cols[char_key]
                        if c_idx < len(row_vals):
                            val_str = row_vals[c_idx]
                            is_t = bool(re.search(r'\b(?:[đt1v✓✔]|đúng|true)\b', val_str, re.IGNORECASE)) and not bool(re.search(r'\b(?:[sf0]|sai|false)\b', val_str, re.IGNORECASE))
                            tf_dict[char_key] = is_t
                        if content_row_idx is not None and c_idx < len(table.rows[content_row_idx].cells):
                            cell = table.rows[content_row_idx].cells[c_idx]
                            cnt = _extract_cell_content(cell, doc, counters, image_mapping)
                            cnt_clean = re.sub(r'^\s*\(?\[?(?:Ý\s*)?[a-d][\)\.\:\-\]\/]?\s*', '', cnt, flags=re.IGNORECASE).strip()
                            if len(cnt_clean) > 3:
                                statements.append(f"{char_key}) {cnt_clean}")

                if len(tf_dict) >= 2:
                    for c in ['a', 'b', 'c', 'd']:
                        if c not in tf_dict:
                            tf_dict[c] = False
                    if len(statements) < 2:
                        statements = []
                    return tf_dict, statements

    # 2. KIỂM TRA DẠNG DỌC
    header_texts = [c.text.strip().lower() for c in table.rows[0].cells]
    col_correct = None
    col_false = None
    col_combined = None
    col_label = None
    col_content = None
    start_row = 1

    for idx, h in enumerate(header_texts):
        if re.search(r'(?:đúng\s*[\/\-]\s*sai|đ\s*[\/\-]\s*s|kết quả|ket qua|lựa chọn|lua chon|chọn)', h, re.IGNORECASE):
            col_combined = idx
        elif re.search(r'(?:^|[\s\(])(?:đúng|dung|true|đ|t)(?:[\s\)]|$)', h, re.IGNORECASE) and not re.search(r'sai|false', h, re.IGNORECASE):
            col_correct = idx
        elif re.search(r'(?:^|[\s\(])(?:sai|false|s|f)(?:[\s\)]|$)', h, re.IGNORECASE):
            col_false = idx
        elif any(k in h for k in ['lệnh hỏi', 'lenh hoi', 'ý hỏi', 'phương án', 'mệnh đề', 'khẳng định', 'phát biểu', 'nội dung', 'câu', 'ý kiến', 'thông tin']):
            if any(k in h for k in ['lệnh hỏi', 'lenh hoi', 'ý hỏi', 'ý', 'kí hiệu', 'ký hiệu', 'stt']):
                col_label = idx
            else:
                col_content = idx
        elif any(k in h for k in ['ý', 'stt', 'kí hiệu', 'ký hiệu']):
            col_label = idx

    if (col_correct is None or col_false is None) and col_combined is None:
        r0_cells = [c.text.strip() for c in table.rows[0].cells]
        if len(r0_cells) >= 3 and re.search(r'^[a-d][\)\.\:\-]', r0_cells[0], re.IGNORECASE):
            c1_m = any(k in r0_cells[1].lower() for k in ['x', 'v', '✓', '✔', '1', 'đ', 's'])
            c2_m = any(k in r0_cells[2].lower() for k in ['x', 'v', '✓', '✔', '1', 'đ', 's'])
            if c1_m or c2_m:
                start_row = 0
                col_correct = 1
                col_false = 2
                col_content = 0
        elif len(r0_cells) == 2 and re.search(r'^[a-d][\)\.\:\-]', r0_cells[0], re.IGNORECASE):
            c1_val = r0_cells[1].lower().strip()
            has_shd = any(is_cell_shaded(r.cells[1]) for r in table.rows if len(r.cells) > 1)
            if has_shd or any(re.match(r'^(?:[đstf10xv✓✔]|đúng|sai|true|false)$', w, re.IGNORECASE) for w in c1_val.split()):
                start_row = 0
                col_combined = 1
                col_content = 0

    if (col_correct is not None and col_false is not None) or col_combined is not None:
        tf_cols = {col_correct, col_false, col_combined} - {None}
        non_tf_cols = [i for i in range(len(table.rows[0].cells)) if i not in tf_cols]
        if col_content is None or col_label is None:
            if len(non_tf_cols) == 1:
                col_content = non_tf_cols[0]
                if col_label is None:
                    col_label = col_content
            elif len(non_tf_cols) >= 2:
                if col_label is None and col_content is None:
                    col_label = non_tf_cols[0]
                    col_content = non_tf_cols[1]
                elif col_label is None:
                    col_label = non_tf_cols[0] if non_tf_cols[0] != col_content else non_tf_cols[1]
                elif col_content is None:
                    col_content = non_tf_cols[1] if non_tf_cols[1] != col_label else non_tf_cols[0]

        tf_dict = {}
        statements = []
        found_chars = set()

        for r_idx in range(start_row, num_rows):
            row_cells = table.rows[r_idx].cells
            if not row_cells:
                continue

            label_text = row_cells[col_label].text.strip() if col_label is not None and col_label < len(row_cells) else ''
            content_text_raw = row_cells[col_content].text.strip() if col_content is not None and col_content < len(row_cells) else ''
            
            char_m = re.search(r'\b([a-d])[\)\.\:\-]?', label_text, re.IGNORECASE)
            if not char_m:
                char_m = re.search(r'^\s*\(?([a-d])[\)\.\:\-]?', content_text_raw, re.IGNORECASE)
            if not char_m and row_cells:
                char_m = re.search(r'\b([a-d])[\)\.\:\-]?', row_cells[0].text.strip(), re.IGNORECASE)

            expected_idx = r_idx - start_row
            if char_m:
                char_key = char_m.group(1).lower()
            elif 0 <= expected_idx < 4:
                char_key = ['a', 'b', 'c', 'd'][expected_idx]
            else:
                continue

            if col_correct is not None and col_false is not None:
                val_corr = row_cells[col_correct].text.strip().lower() if col_correct < len(row_cells) else ''
                val_fls = row_cells[col_false].text.strip().lower() if col_false < len(row_cells) else ''
                shd_corr = is_cell_shaded(row_cells[col_correct]) if col_correct < len(row_cells) else False
                shd_fls = is_cell_shaded(row_cells[col_false]) if col_false < len(row_cells) else False

                mark_corr = bool(re.search(r'[xv✓✔1đt]|đúng|true', val_corr, re.IGNORECASE)) or shd_corr
                mark_fls = bool(re.search(r'[xv✓✔1sf]|sai|false', val_fls, re.IGNORECASE)) or shd_fls

                if mark_corr and not mark_fls:
                    tf_dict[char_key] = True
                    found_chars.add(char_key)
                elif mark_fls and not mark_corr:
                    tf_dict[char_key] = False
                    found_chars.add(char_key)
                elif mark_corr and mark_fls:
                    tf_dict[char_key] = ('đ' in val_corr or 'true' in val_corr or shd_corr)
                    found_chars.add(char_key)
            elif col_combined is not None:
                val_comb = row_cells[col_combined].text.strip().lower() if col_combined < len(row_cells) else ''
                shd = is_cell_shaded(row_cells[col_combined]) if col_combined < len(row_cells) else False
                is_t = shd or (bool(re.search(r'\b(?:[đt1v✓✔]|đúng|true)\b', val_comb, re.IGNORECASE)) and not bool(re.search(r'\b(?:[sf0]|sai|false)\b', val_comb, re.IGNORECASE)))
                tf_dict[char_key] = is_t
                found_chars.add(char_key)

            cell_for_content = row_cells[col_content] if col_content is not None and col_content < len(row_cells) else row_cells[0]
            cnt_html = _extract_cell_content(cell_for_content, doc, counters, image_mapping)
            cnt_clean = re.sub(r'^\s*\(?\[?(?:Ý\s*)?[a-d][\)\.\:\-\]\/]?\s*', '', cnt_html, flags=re.IGNORECASE).strip()
            if len(cnt_clean) > 3:
                statements.append(f"{char_key}) {cnt_clean}")

        if len(found_chars) >= 2:
            for c in ['a', 'b', 'c', 'd']:
                if c not in tf_dict:
                    tf_dict[c] = False
            if len(statements) < 2:
                statements = []
            return tf_dict, statements

    return None


def extract_mcq_question_table(table: Table, doc=None, counters=None, image_mapping=None) -> Optional[List[str]]:

    """

    Nhận diện và bóc tách bảng câu hỏi trắc nghiệm A, B, C, D nhiều dòng (chuẩn ngân hàng đề / bảng đề thi).

    Cấu trúc: Cột STT/Câu, Cột Câu hỏi, Cột A, Cột B, Cột C, Cột D, Cột Đáp án, Cột Lời giải.

    """

    if not table or not table.rows or len(table.rows) < 2:

        return None



    header_texts = [c.text.strip().lower() for c in table.rows[0].cells]

    col_q = None

    col_a = None

    col_b = None

    col_c = None

    col_d = None

    col_ans = None

    col_exp = None

    col_num = None



    for idx, h in enumerate(header_texts):

        if re.search(r'^(?:stt|câu|số tt|tt|id)\b', h, re.IGNORECASE) and not re.search(r'câu hỏi', h, re.IGNORECASE):

            col_num = idx

        elif any(k in h for k in ['câu hỏi', 'nội dung câu hỏi', 'nội dung', 'đề bài', 'yêu cầu']):

            col_q = idx

        elif re.search(r'^(?:phương án\s*a|đáp án\s*a|lựa chọn\s*a|cột\s*a|a[\.\:\)]?$)', h, re.IGNORECASE):

            col_a = idx

        elif re.search(r'^(?:phương án\s*b|đáp án\s*b|lựa chọn\s*b|cột\s*b|b[\.\:\)]?$)', h, re.IGNORECASE):

            col_b = idx

        elif re.search(r'^(?:phương án\s*c|đáp án\s*c|lựa chọn\s*c|cột\s*c|c[\.\:\)]?$)', h, re.IGNORECASE):

            col_c = idx

        elif re.search(r'^(?:phương án\s*d|đáp án\s*d|lựa chọn\s*d|cột\s*d|d[\.\:\)]?$)', h, re.IGNORECASE):

            col_d = idx

        elif any(k in h for k in ['đáp án đúng', 'đáp án', 'đ/a', 'đa', 'key']):

            col_ans = idx

        elif any(k in h for k in ['lời giải', 'hướng dẫn giải', 'hướng dẫn', 'giải thích']):

            col_exp = idx



    opt_cols_found = [c for c in [col_a, col_b, col_c, col_d] if c is not None]

    if col_q is None or len(opt_cols_found) < 3:

        return None



    questions_output = []

    for r_idx in range(1, len(table.rows)):

        row_cells = table.rows[r_idx].cells

        if not row_cells or col_q >= len(row_cells):

            continue



        q_stem = _extract_cell_content(row_cells[col_q], doc, counters, image_mapping)

        if not q_stem.strip():

            continue



        q_num = None

        if col_num is not None and col_num < len(row_cells):

            num_m = re.search(r'\d+', row_cells[col_num].text.strip())

            if num_m:

                q_num = int(num_m.group(0))

        if q_num is None:

            num_m = re.search(r'^(?:Câu|Bài|Question|Q)?\s*(\d+)[\.\:\)]', q_stem, re.IGNORECASE)

            if num_m:

                q_num = int(num_m.group(1))

        if q_num is None:

            if counters is not None:

                counters['q'] += 1

                q_num = counters['q']

            else:

                q_num = r_idx



        q_stem_clean = re.sub(r'^(?:Câu|Bài|Question|Q)?\s*\d+[\.\:\)\-]?\s*', '', q_stem, flags=re.IGNORECASE).strip()



        ans_txt = ""
        ans_letter = None
        if col_ans is not None and col_ans < len(row_cells):
            ans_raw = row_cells[col_ans].text.strip()
            ans_m = re.search(r'\b([A-D])\b', ans_raw, re.IGNORECASE)
            if ans_m:
                ans_txt = ans_m.group(1).upper()
                ans_letter = ans_txt
            elif ans_raw:
                ans_txt = ans_raw

        opts = []
        for char_l, col_opt in [('A', col_a), ('B', col_b), ('C', col_c), ('D', col_d)]:
            if col_opt is not None and col_opt < len(row_cells):
                opt_txt = _extract_cell_content(row_cells[col_opt], doc, counters, image_mapping)
                opt_clean = re.sub(r'^\s*[\(\[]?' + char_l + r'[\)\.\:\-\]\/]?\s*', '', opt_txt, flags=re.IGNORECASE).strip()
                star = "*" if (ans_letter and char_l == ans_letter) else ""
                opts.append(f"{star}{char_l}. {opt_clean}")

        exp_txt = ""

        if col_exp is not None and col_exp < len(row_cells):

            exp_txt = _extract_cell_content(row_cells[col_exp], doc, counters, image_mapping)



        q_block = f"\nCâu {q_num}: {q_stem_clean}\n" + "\n".join(opts)

        if ans_txt:

            q_block += f"\nĐáp án: {ans_txt}"

        if exp_txt:

            q_block += f"\nLời giải: {exp_txt}"

        questions_output.append(q_block + "\n")



    return questions_output if questions_output else None





def extract_options_only_table(table: Table, doc=None, counters=None, image_mapping=None) -> Optional[List[str]]:

    """

    Nhận diện bảng chứa duy nhất các phương án lựa chọn A, B, C, D của một câu hỏi (thường là bảng 1x4 hoặc 2x2 hoặc 4x1).

    """

    if not table or not table.rows:

        return None



    total_cells = sum(len(r.cells) for r in table.rows)

    if total_cells < 2 or total_cells > 6 or len(table.rows) > 4:

        return None



    opt_cells = []

    matched_opts = 0

    for row in table.rows:

        for cell in row.cells:

            txt = _extract_cell_content(cell, doc, counters, image_mapping).strip()

            if not txt:

                continue

            is_opt = bool(re.match(r'^\s*(?:<[^>]+>\s*)*[\(\[]?(\*?[A-Da-d])[\)\.\:\-\]\/]', txt))

            if is_opt:

                matched_opts += 1

            opt_cells.append(txt)



    if matched_opts >= 2 and matched_opts >= (len(opt_cells) * 0.6):

        return opt_cells

    return None





def format_data_table_as_html(table: Table, doc=None, counters=None, image_mapping=None) -> str:

    """

    Chuyển đổi bảng dữ liệu/số liệu thông thường (thí nghiệm, biến thiên, thống kê...) thành bảng HTML đẹp mắt

    được bao bọc chuẩn class='quiz-table' và inline CSS để bảo toàn nguyên vẹn 100% định dạng trên giao diện thi.

    """

    html_rows = []

    for r_idx, row in enumerate(table.rows):

        cells_html = []

        is_header = (r_idx == 0)

        tag = "th" if is_header else "td"

        bg_style = "background: #f8fafc; font-weight: 700; color: #1e293b;" if is_header else "color: #334155;"



        for cell in row.cells:

            cell_content = _extract_cell_content(cell, doc, counters, image_mapping)

            if not cell_content.strip():

                cell_content = "&nbsp;"

            cells_html.append(

                f"<{tag} style='border: 1px solid #cbd5e1; padding: 6px 12px; {bg_style}'>{cell_content}</{tag}>"

            )

        html_rows.append(f"<tr>{''.join(cells_html)}</tr>")



    return f"<table class='quiz-table' border='1' style='border-collapse: collapse; margin: 10px auto; width: 100%; max-width: 650px; text-align: center;'><tbody>{''.join(html_rows)}</tbody></table>"





# Alias tương thích ngược

parse_azota_tf_table = parse_hocnhanhtn_tf_table





def parse_docx_to_marked_text(file_path):

    """Đánh dấu thẻ <MARK> cho các từ in đậm/đỏ/gạch chân để gửi lên AI, đồng thời giữ định dạng HTML và bóc tách bảng Đúng/Sai HocNhanhTN"""

    if hasattr(file_path, 'element') and hasattr(file_path, 'paragraphs'):

        doc = file_path

    else:

        doc = Document(file_path)

    full_text = []

    image_mapping = {}

    counters = {'q': 0, 'opt': 0}



    # Quét tuần tự các phần tử con của body để bảo toàn đúng vị trí câu hỏi và bảng đáp án (chuẩn HocNhanhTN Cách 2)

    for child in doc.element.body:

        if child.tag.endswith('}p'):

            para_text = _process_p_element(child, doc, counters, image_mapping)

            if para_text:

                full_text.append(para_text)

            else:

                full_text.append("\n")

        elif child.tag.endswith('}tbl'):
            tbl = Table(child, doc._body)

            # 1. Kiểm tra xem có phải bảng đáp án tổng hợp ở cuối đề không
            if is_answer_key_table(tbl):
                lines = ["\n[ANSWER_KEY_START]\nBẢNG ĐÁP ÁN\n"]
                for r in tbl.rows:
                    row_txts = [c.text.strip() for c in r.cells if c.text.strip()]
                    lines.append("\t".join(row_txts))
                lines.append("[ANSWER_KEY_END]\n")
                full_text.append("\n".join(lines) + "\n")
                continue

            r_c = len(tbl.rows)
            c_c = len(tbl.columns) if hasattr(tbl, 'columns') else len(tbl.rows[0].cells)

            # 1b. Layout Table 1 (1 hàng x 2-3 cột kết hợp nội dung câu hỏi/phương án và hình ảnh minh họa)
            if r_c == 1 and c_c in [2, 3] and any(len(c._element.xpath('.//*[local-name()="blip"]')) > 0 for c in tbl.rows[0].cells):
                cell_texts = [_extract_cell_content(c, doc, counters, image_mapping) for c in tbl.rows[0].cells]
                full_text.append("\n" + "\n".join(t for t in cell_texts if t.strip()) + "\n")
                continue

            # 1c. Layout Table 2 (2 hàng x 4 cột: 1 hàng hình ảnh và 1 hàng phương án A, B, C, D)
            if r_c == 2 and c_c == 4 and any(len(c._element.xpath('.//*[local-name()="blip"]')) > 0 for c in tbl.rows[0].cells) and any(re.search(r'^[A-D]\.', c.text.strip()) for c in tbl.rows[1].cells):
                opt_cells = []
                for col_i in range(4):
                    img_cnt = _extract_cell_content(tbl.rows[0].cells[col_i], doc, counters, image_mapping)
                    opt_cnt = _extract_cell_content(tbl.rows[1].cells[col_i], doc, counters, image_mapping)
                    opt_cells.append(f"\n{opt_cnt}\n{img_cnt}\n")
                full_text.append("\n".join(opt_cells))
                continue

            # 2. Kiểm tra xem có phải Bảng danh sách câu hỏi trắc nghiệm (MCQ Table nhiều dòng)
            mcq_table_res = extract_mcq_question_table(tbl, doc, counters, image_mapping)
            if mcq_table_res:
                for q_str in mcq_table_res:
                    full_text.append(q_str)
                continue

            # 3. Kiểm tra xem có phải bảng chứa riêng các phương án lựa chọn A-D của 1 câu hỏi (2x2, 1x4...)
            opts_res = extract_options_only_table(tbl, doc, counters, image_mapping)
            if opts_res:
                for opt_item in opts_res:
                    full_text.append(f"\n{opt_item}\n")
                continue

            # 4. Kiểm tra xem có phải bảng Đúng/Sai (chuẩn GDPT 2018 Phần II hoặc HocNhanhTN Cách 2)
            tf_full = parse_hocnhanhtn_tf_table_full(tbl, doc, counters, image_mapping)
            if tf_full:
                tf_res, statements = tf_full
                if statements:
                    full_text.append("\n" + "\n".join(statements))
                ans_str = ", ".join(f"{k}-{'Đ' if v else 'S'}" for k, v in tf_res.items())
                if ans_str:
                    full_text.append(f"\nĐáp án: {ans_str}\n")
                continue

            # 4b. Kiểm tra bảng câu hỏi Đúng/Sai dạng bảng Phát biểu / Đúng / Sai nhưng chưa tích sẵn đáp án
            if tbl.rows:
                r0_txts = [c.text.strip().lower() for c in tbl.rows[0].cells]
                if any(k in r0_txts for k in ['phát biểu', 'mệnh đề', 'lệnh hỏi', 'nội dung']) and any('đúng' in k for k in r0_txts) and any('sai' in k for k in r0_txts):
                    statements = []
                    col_content = 0
                    for c_i, h in enumerate(r0_txts):
                        if any(k in h for k in ['phát biểu', 'mệnh đề', 'lệnh hỏi', 'nội dung']):
                            col_content = c_i
                            break
                    for r_i, r in enumerate(tbl.rows[1:]):
                        cnt = _extract_cell_content(r.cells[col_content], doc, counters, image_mapping)
                        cnt_clean = re.sub(r'^\s*\(?\[?(?:Ý\s*)?[a-d][\)\.\:\-\]\/]?\s*', '', cnt, flags=re.IGNORECASE).strip()
                        char_key = ['a', 'b', 'c', 'd'][r_i] if r_i < 4 else chr(ord('a') + r_i)
                        statements.append(f"{char_key}) {cnt_clean}")
                    full_text.append("\n" + "\n".join(statements) + "\n")
                    continue

            # 5. Bảng thông thường (bảng dữ liệu thí nghiệm, số liệu...), bóc tách thành HTML Table để hiển thị đúng định dạng
            html_table = format_data_table_as_html(tbl, doc, counters, image_mapping)
            full_text.append("\n" + html_table + "\n")



    raw_output = "\n".join(full_text)

    for tag in ['b', 'i', 'u', 'sup', 'sub']:

        raw_output = raw_output.replace(f"</{tag}> <{tag}>", " ").replace(f"</{tag}><{tag}>", "")



    end_markers = ['\nHẾT\n', '\nHET\n', '\n--- HẾT ---\n', '\n---HẾT---\n', '\nTHE END\n']

    for marker in end_markers:

        pos = raw_output.upper().find(marker.upper())

        if pos != -1 and pos > len(raw_output) * 0.5:

            tail = raw_output[pos:].upper()

            if any(k in tail for k in ["BẢNG ĐÁP ÁN", "BANG DAP AN", "ĐÁP ÁN", "DAP AN", "ANSWER KEY", "HƯỚNG DẪN CHẤM", "LỜI GIẢI", "LOI GIAI", "HƯỚNG DẪN GIẢI", "HUONG DAN GIAI", "GIẢI THÍCH"]):

                pass

            else:

                raw_output = raw_output[:pos]

            break



    # Tách các phương án A-D trên cùng 1 dòng thành từng dòng riêng biệt (yêu cầu tab, 2 khoảng trắng trở lên hoặc sau dấu câu)

    raw_output = re.sub(

        r'(?<!\n)(?<!Đáp án:)(?<!Đáp số:)(?<!ĐS:)(?<!Kết quả:)(?:\t|\s{2,}|(?<=[;\.\?!])\s+)((?:(?:<MARK>\s*|<u>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*(?:</MARK>\s*|</u>\s*)*)?(?:<MARK>\s*|<u>\s*)*\*?[A-D][\.\:\)]\s*)',

        r'\n\1',

        raw_output

    )

    # Hỗ trợ tách các ý con a-d trên cùng 1 dòng kèm tiền tố ma trận HocNhanhTN [0, NB] và markup <u>, <MARK>

    raw_output = re.sub(

        r'(?<!\n)(?:\t|\s{2,}|(?<=[;\.\:\?!])\s+)((?:(?:<MARK>\s*|<u>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*(?:</MARK>\s*|</u>\s*)*)?(?:<MARK>\s*|<u>\s*)*\*?[a-d][\)\.\:\-]\s*)',

        r'\n\1',

        raw_output

    )

    return raw_output, image_mapping

