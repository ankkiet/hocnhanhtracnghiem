import re
import base64
from typing import List, Dict, Any
from docx import Document
from docx.oxml.ns import qn, nsmap
if 'o' not in nsmap:
    nsmap['o'] = 'urn:schemas-microsoft-com:office:office'
if 'v' not in nsmap:
    nsmap['v'] = 'urn:schemas-microsoft-com:vml'
from docx.text.paragraph import Paragraph

from services.r2_service import upload_image_to_r2
from core.image_converter import process_image_blob
from core.mathml_parser import parse_omath
from core.answer_key_extractor import (
    extract_answer_key_from_doc,
    reconcile_quiz_with_answer_key,
    separate_answer_key_from_text,
    AnswerKeyMap
)
from services.ai_service import restore_image_placeholders

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
                    except:
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
                ca_char = q_item["correct_answer"].strip()[:2].upper()
                for opt in q_item["options"]:
                    if opt.upper().startswith(ca_char):
                        q_item["correct_answer"] = opt
                        break

    if image_mapping:
        extracted_data = replace_placeholders(extracted_data, image_mapping)

    return extracted_data


def parse_docx_to_marked_text(file_path: str):
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
                    except:
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
                                img_counter += 1
                                placeholder = f"[IMG_{img_counter}]"
                                image_mapping[placeholder] = img_tag
                                para_text += f"\n{placeholder}\n"
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
                
                if is_red_text or is_highlighted or is_underline:
                    para_text += f"<MARK>{formatted_text}</MARK>"
                else:
                    para_text += formatted_text
                    
        full_text.append(para_text)
        
    raw_output = "\n".join(full_text)
    for tag in ['b', 'i', 'u', 'sup', 'sub']:
        raw_output = raw_output.replace(f"</{tag}> <{tag}>", " ").replace(f"</{tag}><{tag}>", "")
    
    end_markers = ['\nHẾT\n', '\nHET\n', '\n--- HẾT ---\n', '\n---HẾT---\n', '\nTHE END\n']
    for marker in end_markers:
        pos = raw_output.upper().find(marker.upper())
        if pos != -1 and pos > len(raw_output) * 0.5:
            tail = raw_output[pos:].upper()
            if any(k in tail for k in ["BẢNG ĐÁP ÁN", "BANG DAP AN", "ĐÁP ÁN", "DAP AN", "ANSWER KEY", "HƯỚNG DẪN CHẤM"]):
                pass
            else:
                raw_output = raw_output[:pos]
            break
        
    # Tách các phương án A-D trên cùng 1 dòng thành từng dòng riêng biệt (yêu cầu tab, 2 khoảng trắng trở lên hoặc sau dấu câu)
    raw_output = re.sub(r'(?<!\n)(?:\t|\s{2,}|(?<=[;\.\:\?!])\s+)(\*?[A-D][\.\:\)]\s*)', r'\n\1', raw_output)
    raw_output = re.sub(r'(?<!\n)(?:\t|\s{2,}|(?<=[;\.\:\?!])\s+)(\*?[a-d][\)\.\:\-]\s*)', r'\n\1', raw_output)
    return raw_output, image_mapping
