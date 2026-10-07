import re
from typing import List, Dict, Any
from core.answer_key_extractor import (
    separate_answer_key_from_text,
    reconcile_quiz_with_answer_key
)
from core.docx_parser import (
    split_merged_options,
    replace_placeholders
)
from services.ai_service import clean_option_text, parse_tf_answer


def extract_explain_from_block(text: str) -> tuple:
    """
    Trích xuất lời giải từ khối văn bản chứa câu hỏi (chuẩn Bộ GD&ĐT).
    Hỗ trợ các từ khóa: 'Lời giải:', 'Giải thích:', 'Hướng dẫn:', 'ĐÁP ÁN:'...
    Trả về: (text_không_có_lời_giải, lời_giải)
    """
    explain_pattern = re.compile(
        r'(?:^|\n)\s*(?:Lời giải|Lời giải chi tiết|Hướng dẫn giải|Giải thích|Hướng dẫn|Phân tích|Giải|Lời giải chi tiết)\s*[:\-]\s*',
        re.IGNORECASE
    )
    m = explain_pattern.search(text)
    if m:
        main_text = text[:m.start()].strip()
        explain_text = text[m.end():].strip()
        # Xóa các thẻ <MARK> khỏi lời giải
        explain_text = explain_text.replace('<MARK>', '').replace('</MARK>', '').strip()
        return main_text, explain_text
    return text, ""


def extract_questions_from_text_bulletproof(raw_text: str, image_mapping: dict = None) -> List[Dict[str, Any]]:
    """
    Bộ bóc tách câu hỏi dự phòng siêu bền vững bằng Regex khối chuẩn Bộ GD&ĐT (GDPT 2018):
    1. PHẦN I: Trắc nghiệm 4 lựa chọn (A, B, C, D).
    2. PHẦN II: Trắc nghiệm Đúng / Sai (ý a, b, c, d độc lập, hỗ trợ dấu *, [ĐÚNG]/[SAI]).
    3. PHẦN III: Trắc nghiệm Trả lời ngắn (điền kết quả ngắn, bóc tách 'Đáp án: ...', 'ĐS: ...').
    """
    if not raw_text or not raw_text.strip():
        return []

    # Tách Bảng đáp án trước khi cắt bỏ các từ khóa kết thúc đề (tránh làm mất bảng đáp án ở cuối tài liệu)
    raw_text_questions, ak_raw, detected_ak = separate_answer_key_from_text(raw_text)
    raw_text = raw_text_questions

    # Chuẩn Bộ GD&ĐT: Cắt bỏ nội dung sau từ khóa kết thúc đề "HẾT"
    end_markers = ['\nHẾT\n', '\nHET\n', '\n--- HẾT ---\n', '\n---HẾT---\n', '\nTHE END\n']
    for marker in end_markers:
        pos = raw_text.upper().find(marker.upper())
        if pos != -1 and pos > len(raw_text) * 0.5:
            raw_text = raw_text[:pos]
            break

    q_split_pattern = re.compile(
        r'(?:^|\n)\s*(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*',
        re.IGNORECASE
    )
    
    matches = list(q_split_pattern.finditer(raw_text))
    if not matches:
        return []
        
    results = []
    
    # Pattern nhận diện các phương án A-F (chữ hoa) cho MCQ
    mcq_opt_pattern = re.compile(
        r'(?:^|\n|\t|\s{2,}|(?<=[;\.\:\?!])\s*|(?<=[\)\}\}\'\"\>])\s*|(?<=\s)(?=[B-F][\.\:\)\/\-]))(?:\(?\[?(\*?[A-F])(?:[\.\:\/\)\]\-]|\b))\s*'
    )
    
    # Pattern nhận diện các ý con a-d (chữ thường) cho Đúng/Sai hỗ trợ ma trận Azota và markup
    sub_opt_pattern = re.compile(
        r'(?:^|\n|\t|\s{2,}|(?<=[;\.\:\?!])\s*|(?<=[\)\}\]\'\"\>])\s*|(?<=\s)(?=[b-d][\.\:\)\/\-]))'
        r'((?:(?:<MARK>|<mark>|<u>|<U>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC|nb|th|vd|vdc)\s*\]\s*(?:</MARK>|</mark>|</u>|</U>\s*)*)?'
        r'(?:<MARK>|<mark>|<u>|<U>\s*)*\(?\[?(\*?[a-d])(?:[\.\:\/\)\]\-]|\b))\s*'
    )
    
    for i, m in enumerate(matches):
        q_start = m.end()
        q_end = matches[i+1].start() if i+1 < len(matches) else len(raw_text)
        raw_block = raw_text[q_start:q_end].strip()
        
        # Tách phần lời giải trước để tránh nhầm a), b) trong lời giải thành phương án
        block, explain = extract_explain_from_block(raw_block)
        
        sub_matches = list(sub_opt_pattern.finditer(block))
        mcq_matches = list(mcq_opt_pattern.finditer(block))
        
        if len(sub_matches) >= 2:
            # 1. DẠNG TRẮC NGHIỆM ĐÚNG / SAI (PHẦN II)
            q_text = block[:sub_matches[0].start()].strip()
            options = []
            opt_tf_marks = {}
            explicit_ans = None
            
            for j, opt_m in enumerate(sub_matches[:4]):
                char = opt_m.group(2).replace('*', '').lower()
                opt_start = opt_m.start()
                opt_end = sub_matches[j+1].start() if j+1 < len(sub_matches) else len(block)
                opt_content_raw = block[opt_start:opt_end].strip()
                
                # Nếu là ý cuối cùng, kiểm tra và tách dòng Đáp án kèm theo
                if j == len(sub_matches[:4]) - 1:
                    ans_m = re.search(r'(?:\n|\r)\s*(?:Đáp án|Đáp số|ĐS|Kết quả|Ans)\s*[\:\-\=]?\s*(.*)$', opt_content_raw, re.IGNORECASE)
                    if ans_m:
                        ans_content = ans_m.group(1).strip()
                        opt_content_raw = opt_content_raw[:ans_m.start()].strip()
                        parsed_ans = parse_tf_answer(ans_content)
                        if parsed_ans and any(parsed_ans.values()):
                            explicit_ans = parsed_ans

                clean_text, is_corr, is_fls, ext_char = clean_option_text(opt_content_raw)
                options.append(f"{char}) {clean_text}")
                if is_corr:
                    opt_tf_marks[char] = True
                elif is_fls:
                    opt_tf_marks[char] = False
                
            if explicit_ans:
                tf_dict = explicit_ans
                for k, v in opt_tf_marks.items():
                    tf_dict[k] = v
            elif opt_tf_marks:
                has_any_true = any(v is True for v in opt_tf_marks.values())
                if has_any_true:
                    tf_dict = {k: bool(opt_tf_marks.get(k, False)) for k in ['a', 'b', 'c', 'd']}
                else:
                    tf_dict = {k: opt_tf_marks.get(k, True) for k in ['a', 'b', 'c', 'd']}
            else:
                tf_dict = {"a": True, "b": False, "c": True, "d": False}

            results.append({
                "type": "true_false",
                "group_title": "",
                "question": q_text,
                "options": options,
                "correct_answer": tf_dict,
                "explain": explain
            })
            
        elif len(mcq_matches) >= 2:
            # 2. DẠNG TRẮC NGHIỆM NHIỀU LỰA CHỌN (PHẦN I)
            q_text = block[:mcq_matches[0].start()].strip()
            options = []
            correct_ans = ""
            
            for j, opt_m in enumerate(mcq_matches[:4]):
                char_raw = opt_m.group(1).upper()
                is_asterisk = '*' in char_raw
                char = char_raw.replace('*', '').strip()
                
                opt_start = opt_m.end()
                opt_end = mcq_matches[j+1].start() if j+1 < len(mcq_matches) else len(block)
                opt_content_raw = block[opt_start:opt_end].strip()
                
                opt_content = re.sub(r'\s+', ' ', opt_content_raw)
                if is_asterisk or '<MARK>' in opt_content or '[ĐÚNG]' in opt_content or '✓' in opt_content:
                    clean_opt = opt_content.replace('<MARK>', '').replace('</MARK>', '').strip()
                    correct_ans = f"{char}. {clean_opt}"
                    
                clean_opt_for_list = opt_content.replace('<MARK>', '').replace('</MARK>', '').strip()
                options.append(f"{char}. {clean_opt_for_list}")
                
            results.append({
                "type": "mcq",
                "group_title": "",
                "question": q_text,
                "options": options,
                "correct_answer": correct_ans,
                "explain": explain
            })
            
        else:
            # Cứu hộ: Kiểm tra xem block có thực sự là Đúng / Sai có ý a, b, c, d bị dính liền không
            from services.ai_service import extract_sub_statements_from_text, parse_tf_answer
            stem, tf_opts = extract_sub_statements_from_text(block)
            if len(tf_opts) >= 3:
                tf_ca = {"a": True, "b": False, "c": True, "d": False}
                ans_match = re.search(r'(?:Đáp án|Đáp số|ĐS|Kết quả|Ans)\s*[\:\-\=]?\s*([^\n\r]+)', block, re.IGNORECASE)
                if ans_match:
                    tf_ca = parse_tf_answer(ans_match.group(1).strip())
                results.append({
                    "type": "true_false",
                    "group_title": "",
                    "question": stem,
                    "options": tf_opts,
                    "correct_answer": tf_ca,
                    "explain": explain
                })
            else:
                # 3. DẠNG TRẮC NGHIỆM TRẢ LỜI NGẮN (PHẦN III)
                q_text = block
                ans_val = ""
                ans_match = re.search(r'(?:Đáp án|Đáp số|ĐS|Kết quả|Ans|Answer)\s*[\:\-\=]?\s*([^\n\r\;]+)', q_text, re.IGNORECASE)
                if ans_match:
                    ans_val = ans_match.group(1).strip()
                    q_text = q_text[:ans_match.start()].strip() + " " + q_text[ans_match.end():].strip()
                    q_text = q_text.strip()
                elif explain:
                    ans_match_exp = re.search(r'(?:Đáp án|Đáp số|ĐS|Kết quả)\s*[\:\-\=]?\s*([^\n\r\;]+)', explain, re.IGNORECASE)
                    if ans_match_exp:
                        ans_val = ans_match_exp.group(1).strip()
                        
                results.append({
                    "type": "short_answer",
                    "group_title": "",
                    "question": q_text,
                    "options": [],
                    "correct_answer": ans_val,
                    "explain": explain
                })
            
    # Đối chiếu toàn diện với Bảng đáp án bóc tách được từ văn bản
    if detected_ak:
        results = reconcile_quiz_with_answer_key(results, detected_ak)

    for q_item in results:
        if q_item.get("type", "mcq") == "mcq" and q_item.get("options"):
            q_item["options"] = split_merged_options(q_item["options"])
            if q_item.get("correct_answer"):
                ca_char = q_item["correct_answer"].strip()[:2].upper()
                for opt in q_item["options"]:
                    if opt.upper().startswith(ca_char):
                        q_item["correct_answer"] = opt
                        break

    if image_mapping and results:
        results = replace_placeholders(results, image_mapping)
        
    return results
