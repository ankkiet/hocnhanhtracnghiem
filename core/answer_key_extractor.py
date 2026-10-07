import os
import re
from typing import Dict, Any, Optional, Tuple, List

class AnswerKeyMap(dict):
    """
    Cấu trúc dữ liệu thông minh lưu trữ Bảng đáp án chuẩn Bộ GD&ĐT (GDPT 2018):
    - part1: {q_num: 'A'|'B'|'C'|'D'} (Phần I - Trắc nghiệm 4 lựa chọn)
    - part2: {q_num: {'a': bool, 'b': bool, 'c': bool, 'd': bool}} (Phần II - Đúng / Sai)
    - part3: {q_num: '12.5'} (Phần III - Trả lời ngắn)
    - linear: {global_idx: answer} (Dò theo số thứ tự liên tục 1, 2, 3...)
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.part1: Dict[int, str] = {}
        self.part2: Dict[int, Dict[str, bool]] = {}
        self.part3: Dict[int, str] = {}

    def set_answer(self, part: int, q_num: int, ans: Any):
        if part == 1:
            self.part1[q_num] = ans
        elif part == 2:
            self.part2[q_num] = ans
        elif part == 3:
            self.part3[q_num] = ans
        self[q_num] = ans

    def get_answer(self, q_type: str, linear_num: int = None, part_num: int = None, raw_num: int = None) -> Any:
        """
        Tìm đáp án chuẩn xác nhất dựa trên loại câu hỏi và số thứ tự:
        Ưu tiên: part_num trong từng phần -> raw_num -> linear_num
        """
        candidates = [c for c in [part_num, raw_num, linear_num] if c is not None]

        if q_type == "true_false":
            for c in candidates:
                if c in self.part2:
                    return self.part2[c]
            for c in candidates:
                if c in self and isinstance(self[c], dict):
                    return self[c]
            # Fallback nếu linear_num khớp trong part2
            if linear_num is not None and linear_num in self.part2:
                return self.part2[linear_num]

        elif q_type == "short_answer":
            for c in candidates:
                if c in self.part3:
                    return self.part3[c]
            for c in candidates:
                if c in self and isinstance(self[c], (str, int, float)) and not isinstance(self[c], dict):
                    s = str(self[c]).strip()
                    if len(s) <= 25 and not re.match(r'^[A-F]$', s, re.IGNORECASE):
                        return s
            if linear_num is not None and linear_num in self.part3:
                return self.part3[linear_num]

        else: # MCQ
            for c in candidates:
                if c in self.part1:
                    return self.part1[c]
            for c in candidates:
                if c in self and isinstance(self[c], str) and re.match(r'^[A-F]$', self[c].strip(), re.IGNORECASE):
                    return self[c].strip().upper()
            if linear_num is not None and linear_num in self.part1:
                return self.part1[linear_num]

        # Cuối cùng thử tra trong self nói chung
        for c in candidates:
            if c in self:
                return self[c]
        return None

    def to_summary_text(self) -> str:
        """Xuất Bảng đáp án thành dạng văn bản ngắn gọn, rõ ràng để chèn vào prompt AI."""
        lines = []
        if self.part1:
            lines.append("--- PHẦN I (TRẮC NGHIỆM NHIỀU LỰA CHỌN) ---")
            p1_items = [f"{q}.{ans}" for q, ans in sorted(self.part1.items())]
            lines.append("  ".join(p1_items))

        if self.part2:
            lines.append("--- PHẦN II (TRẮC NGHIỆM ĐÚNG / SAI) ---")
            for q, d in sorted(self.part2.items()):
                if isinstance(d, dict):
                    parts_str = ", ".join(f"{k}-{'Đ' if d.get(k) else 'S'}" for k in ['a', 'b', 'c', 'd'] if k in d)
                    lines.append(f"Câu {q}: {parts_str}")
                else:
                    lines.append(f"Câu {q}: {d}")

        if self.part3:
            lines.append("--- PHẦN III (TRẮC NGHIỆM TRẢ LỜI NGẮN) ---")
            p3_items = [f"Câu {q}: {ans}" for q, ans in sorted(self.part3.items())]
            lines.append(" | ".join(p3_items))

        # Nếu không có chia part nhưng có self chung
        if not lines and self:
            lines.append("--- BẢNG ĐÁP ÁN ---")
            for q, ans in sorted(self.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 999):
                if isinstance(ans, dict):
                    parts_str = ", ".join(f"{k}-{'Đ' if ans.get(k) else 'S'}" for k in ['a', 'b', 'c', 'd'] if k in ans)
                    lines.append(f"Câu {q}: {parts_str}")
                else:
                    lines.append(f"Câu {q}: {ans}")

        return "\n".join(lines)


def extract_answer_key_from_doc(doc, full_text: str = "") -> AnswerKeyMap:
    """
    Bóc tách toàn diện Bảng đáp án từ tài liệu Word (doc.tables) và từ khối văn bản cuối tài liệu.
    Hỗ trợ mọi định dạng chuẩn Bộ GD&ĐT:
    - Bảng ngang 2 hàng: Câu 1, 2... / Đáp án A, B...
    - Bảng Đúng/Sai 4 cột a, b, c, d
    - Bảng dọc 2 cột: Cột 0: Câu / Cột 1: Đáp án
    - Khối văn bản sau các tiêu đề BẢNG ĐÁP ÁN / ĐÁP ÁN / HƯỚNG DẪN CHẤM
    """
    ak = AnswerKeyMap()

    if isinstance(doc, str):
        if (doc.lower().endswith('.docx') or doc.lower().endswith('.doc')) and os.path.exists(doc):
            try:
                from docx import Document
                doc = Document(doc)
            except Exception:
                doc = None
        else:
            if not full_text:
                full_text = doc
            doc = None

    # Tự động trích xuất toàn bộ văn bản từ doc.paragraphs nếu chưa có full_text
    if doc is not None and hasattr(doc, 'paragraphs') and not full_text:
        full_text = "\n".join(p.text for p in doc.paragraphs if p.text)

    # 1. Quét các bảng trong tài liệu
    if doc is not None and hasattr(doc, 'tables') and doc.tables:
        for table in doc.tables:
            if not table.rows:
                continue

            num_rows = len(table.rows)
            num_cols = len(table.columns) if hasattr(table, 'columns') else len(table.rows[0].cells)

            # Dạng A: Bảng phân tích Đúng/Sai có các cột [Câu, a, b, c, d]
            header_cells = [c.text.strip().lower() for c in table.rows[0].cells]
            has_abcd_header = any('a' in h for h in header_cells) and any('b' in h for h in header_cells)
            if has_abcd_header and num_rows >= 2:
                col_a = next((idx for idx, h in enumerate(header_cells) if re.search(r'\ba\b|^a[\.\:\)]', h)), None)
                col_b = next((idx for idx, h in enumerate(header_cells) if re.search(r'\bb\b|^b[\.\:\)]', h)), None)
                col_c = next((idx for idx, h in enumerate(header_cells) if re.search(r'\bc\b|^c[\.\:\)]', h)), None)
                col_d = next((idx for idx, h in enumerate(header_cells) if re.search(r'\bd\b|^d[\.\:\)]', h)), None)

                if col_a is not None and col_b is not None:
                    for r_idx in range(1, num_rows):
                        row = table.rows[r_idx].cells
                        q_match = re.search(r'\b(\d+)\b', row[0].text.strip())
                        if not q_match:
                            continue
                        q_num = int(q_match.group(1))
                        tf_dict = {}
                        for char, c_idx in [('a', col_a), ('b', col_b), ('c', col_c), ('d', col_d)]:
                            if c_idx is not None and c_idx < len(row):
                                val_text = row[c_idx].text.strip().lower()
                                tf_dict[char] = any(k in val_text for k in ['đ', 'đúng', 'true', 't', '✓', '✔', 'x', '1']) and not any(k in val_text for k in ['s', 'sai', 'false', 'f', '0'])
                        if tf_dict:
                            ak.set_answer(2, q_num, tf_dict)
                    continue

            # Dạng B: Bảng 2 hàng kế tiếp (Hàng trên: Câu 1, Câu 2... Hàng dưới: Đáp án)
            if num_rows >= 2:
                for r_idx in range(num_rows - 1):
                    row_top = [c.text.strip() for c in table.rows[r_idx].cells]
                    row_bot = [c.text.strip() for c in table.rows[r_idx + 1].cells]

                    for c_top, c_bot in zip(row_top, row_bot):
                        num_m = re.search(r'(?:Câu\s*)?(\d+)', c_top)
                        if not num_m or not c_bot:
                            continue
                        q_num = int(num_m.group(1))

                        # 1. Đúng/Sai: a-Đ, b-S, c-Đ, d-S hoặc aĐ bS cĐ dS hoặc a. Đúng...
                        tf_m = re.search(r'(?:[a-d][\.\:\)\/\-\s]*(?:Đ|S|Đúng|Sai)|(?:Đ|S|Đúng|Sai)\s*[\,\;\-]\s*(?:Đ|S|Đúng|Sai))', c_bot, re.IGNORECASE)
                        if tf_m or len(re.findall(r'\b(Đ|S|ĐÚNG|SAI)\b', c_bot, re.IGNORECASE)) >= 3:
                            from services.ai_service import parse_tf_answer
                            tf_dict = parse_tf_answer(c_bot)
                            if tf_dict and any(tf_dict.values()):
                                ak.set_answer(2, q_num, tf_dict)
                                continue

                        # Chuỗi 4 chữ Đ/S liên tục (ví dụ: Đ S Đ S hoặc Đ-S-Đ-S)
                        seq_tf = re.findall(r'\b(Đ|S|ĐÚNG|SAI)\b', c_bot, re.IGNORECASE)
                        if len(seq_tf) == 4:
                            ak.set_answer(2, q_num, {
                                'a': seq_tf[0].lower() in ['đ', 'đúng'],
                                'b': seq_tf[1].lower() in ['đ', 'đúng'],
                                'c': seq_tf[2].lower() in ['đ', 'đúng'],
                                'd': seq_tf[3].lower() in ['đ', 'đúng']
                            })
                            continue

                        # 2. MCQ: A, B, C, D
                        ans_m = re.match(r'^\s*([A-F])\b', c_bot, re.IGNORECASE)
                        if ans_m and len(c_bot.strip()) <= 3:
                            ak.set_answer(1, q_num, ans_m.group(1).upper())
                            continue

                        # 3. Trả lời ngắn: 12.5, 12,5, -3, 1/2 v.v.
                        if len(c_bot) <= 35 and not re.search(r'^[A-F]\.', c_bot.strip()):
                            clean_sa = c_bot.strip()
                            clean_sa = re.sub(r'^(?:Đáp án|Đáp số|ĐS|Kết quả|Ans)\s*[\:\-\=]?\s*', '', clean_sa, flags=re.IGNORECASE).strip()
                            # Chuẩn hóa dấu phẩy thập phân kiểu Việt Nam: 12,5 -> 12.5
                            if re.match(r'^-?\d+,\d+$', clean_sa):
                                clean_sa = clean_sa.replace(',', '.')
                            ak.set_answer(3, q_num, clean_sa)

            # Dạng C: Bảng 2 cột (Cột 0: Câu, Cột 1: Đáp án)
            if num_cols == 2 and num_rows >= 3:
                for r_idx in range(num_rows):
                    c0 = table.rows[r_idx].cells[0].text.strip()
                    c1 = table.rows[r_idx].cells[1].text.strip()
                    num_m = re.search(r'(?:Câu\s*)?(\d+)', c0)
                    if not num_m or not c1:
                        continue
                    q_num = int(num_m.group(1))

                    tf_m = re.search(r'(?:[a-d][\.\:\)\/\-\s]*(?:Đ|S|Đúng|Sai)|(?:Đ|S|Đúng|Sai)\s*[\,\;\-]\s*(?:Đ|S|Đúng|Sai))', c1, re.IGNORECASE)
                    if tf_m or len(re.findall(r'\b(Đ|S|ĐÚNG|SAI)\b', c1, re.IGNORECASE)) >= 3:
                        from services.ai_service import parse_tf_answer
                        tf_dict = parse_tf_answer(c1)
                        if tf_dict and any(tf_dict.values()):
                            ak.set_answer(2, q_num, tf_dict)
                            continue

                    seq_tf = re.findall(r'\b(Đ|S|ĐÚNG|SAI)\b', c1, re.IGNORECASE)
                    if len(seq_tf) == 4:
                        ak.set_answer(2, q_num, {
                            'a': seq_tf[0].lower() in ['đ', 'đúng'],
                            'b': seq_tf[1].lower() in ['đ', 'đúng'],
                            'c': seq_tf[2].lower() in ['đ', 'đúng'],
                            'd': seq_tf[3].lower() in ['đ', 'đúng']
                        })
                        continue

                    ans_m = re.match(r'^\s*([A-F])\b', c1, re.IGNORECASE)
                    if ans_m and len(c1.strip()) <= 3:
                        ak.set_answer(1, q_num, ans_m.group(1).upper())
                        continue

                    if len(c1) <= 35:
                        clean_sa = c1.strip()
                        clean_sa = re.sub(r'^(?:Đáp án|Đáp số|ĐS|Kết quả|Ans)\s*[\:\-\=]?\s*', '', clean_sa, flags=re.IGNORECASE).strip()
                        if re.match(r'^-?\d+,\d+$', clean_sa):
                            clean_sa = clean_sa.replace(',', '.')
                        ak.set_answer(3, q_num, clean_sa)

    # 2. Quét trong khối văn bản cuối tài liệu sau tiêu đề BẢNG ĐÁP ÁN (bổ sung/kết hợp thêm)
    key_headers = [
        "BẢNG ĐÁP ÁN", "BANG DAP AN", "BẢNG ĐÁP SỐ", "ĐÁP ÁN CHI TIẾT",
        "ĐÁP ÁN VÀ HƯỚNG DẪN GIẢI", "ĐÁP ÁN", "DAP AN", "ANSWER KEY",
        "HƯỚNG DẪN CHẤM", "HƯỚNG DẪN GIẢI", "THANG ĐIỂM", "BẢNG ĐÁP ÁN VÀ THANG ĐIỂM"
    ]
    ans_section = ""
    for header in key_headers:
        pos = full_text.upper().rfind(header)
        if pos != -1 and (len(full_text) - pos) < 20000:
            ans_section = full_text[pos:]
            break

    if ans_section:
        part_splits = re.split(r'(\bPHẦN\s+(?:III|II|I|3|2|1)\b[^\n]*)', ans_section, flags=re.IGNORECASE)

        current_part = None
        for chunk in part_splits:
            chunk_upper = chunk.upper()
            if re.search(r'\bPHẦN\s+(?:III|3)\b|TRẢ LỜI NGẮN', chunk_upper):
                current_part = 3
                continue
            elif re.search(r'\bPHẦN\s+(?:II|2)\b|ĐÚNG SAI|ĐÚNG - SAI', chunk_upper):
                current_part = 2
                continue
            elif re.search(r'\bPHẦN\s+(?:I|1)\b|NHIỀU LỰA CHỌN|NHIỀU PHƯƠNG ÁN', chunk_upper):
                current_part = 1
                continue

            # 1. Dò đúng sai dạng: 1: a-Đ, b-S, c-Đ, d-S hoặc 1. aĐ bS cĐ dS hoặc 1. a. Đúng b. Sai
            tf_pattern = re.compile(
                r'(?:Câu\s*)?(\d+)\s*[\.\:\-\)]\s*([a-d]\s*[\-\:\.]?\s*(?:Đ|S|Đúng|Sai|True|False).*?)(?=(?:Câu\s*)?\d+[\.\:\-\)]|\bPHẦN|$|\n\n)',
                re.IGNORECASE
            )
            for m in tf_pattern.finditer(chunk):
                q_num = int(m.group(1))
                tf_str = m.group(2)
                from services.ai_service import parse_tf_answer
                tf_dict = parse_tf_answer(tf_str)
                if tf_dict and any(tf_dict.values()):
                    ak.set_answer(2, q_num, tf_dict)

            # Chuỗi 4 chữ Đ/S theo sau số câu trong phần II (ví dụ: Câu 1: Đ S Đ S hoặc 1. Đ, S, Đ, S)
            if current_part == 2 or "ĐÚNG" in chunk_upper or "Đ/S" in chunk_upper:
                seq_pattern = re.compile(r'(?:Câu\s*)?(\d+)\s*[\.\:\-\)]\s*([ĐSđsĐúngSai\s\-\,\;]{4,20})', re.IGNORECASE)
                for sm in seq_pattern.finditer(chunk):
                    q_num = int(sm.group(1))
                    raw_seq = sm.group(2)
                    found_letters = re.findall(r'\b(Đ|S|ĐÚNG|SAI)\b', raw_seq, re.IGNORECASE)
                    if len(found_letters) == 4 and q_num not in ak.part2:
                        ak.set_answer(2, q_num, {
                            'a': found_letters[0].lower() in ['đ', 'đúng'],
                            'b': found_letters[1].lower() in ['đ', 'đúng'],
                            'c': found_letters[2].lower() in ['đ', 'đúng'],
                            'd': found_letters[3].lower() in ['đ', 'đúng']
                        })

            # 2. Dò trả lời ngắn nếu current_part == 3 hoặc có từ khóa
            if current_part == 3 or "TRẢ LỜI NGẮN" in chunk_upper:
                sa_pattern = re.compile(r'(?:Câu\s*)?(\d+)\s*[\.\:\-\=\)]\s*([^\n\r\;\,]+)', re.IGNORECASE)
                for m in sa_pattern.finditer(chunk):
                    q_num = int(m.group(1))
                    val_str = m.group(2).strip()
                    val_str = re.sub(r'^(?:Đáp án|Đáp số|ĐS|Kết quả|Ans)\s*[\:\-\=]?\s*', '', val_str, flags=re.IGNORECASE).strip()
                    if val_str and len(val_str) <= 35 and not re.match(r'^[A-F]$', val_str, re.IGNORECASE):
                        if re.match(r'^-?\d+,\d+$', val_str):
                            val_str = val_str.replace(',', '.')
                        ak.set_answer(3, q_num, val_str)

            # 3. Dò MCQ dạng: 1.A 2.B hoặc Câu 1: A
            if current_part == 1 or current_part is None:
                mcq_pattern = re.compile(r'(?:Câu\s*)?(\d+)\s*[\.\:\-\)\/]?\s*([A-F])\b', re.IGNORECASE)
                for m in mcq_pattern.finditer(chunk):
                    q_num = int(m.group(1))
                    ans_char = m.group(2).upper()
                    ak.set_answer(1, q_num, ans_char)


    return ak


def separate_answer_key_from_text(full_text: str) -> Tuple[str, str, AnswerKeyMap]:
    """
    Phát hiện và tách khối BẢNG ĐÁP ÁN ở cuối văn bản:
    Trả về: (văn_bản_câu_hỏi_đã_lược_bỏ_bảng_đáp_án, văn_bản_bảng_đáp_án_gốc, AnswerKeyMap)
    Giúp AI chỉ bóc tách câu hỏi thực sự, không bị nhầm bảng đáp án thành câu hỏi.
    """
    section_patterns = [
        r'(?:^|\n)\s*(?:[-=~_*#]{2,}\s*)?(?:BẢNG\s+ĐÁP\s+ÁN|BANG\s+DAP\s+AN|BẢNG\s+ĐÁP\s+SỐ|ANSWER\s+KEY|HƯỚNG\s+DẪN\s+CHẤM)(?:\s*[-=~_*#]{2,})?\s*[:\-]?\s*(?:\n|$)',
        r'(?:^|\n)\s*(?:[-=~_*#]{2,}\s*)?(?:ĐÁP\s+ÁN|DAP\s+AN|ĐÁP\s+ÁN\s+CHI\s+TIẾT)(?:\s*[-=~_*#]{2,})?\s*[:\-]?\s*(?:\n|$)'
    ]
    
    found_pos = -1
    for p in section_patterns:
        for m in re.finditer(p, full_text, re.IGNORECASE):
            pos = m.start()
            # Bảng đáp án chỉ nằm ở nửa sau tài liệu
            if pos > len(full_text) * 0.3 and (len(full_text) - pos) < 15000:
                if found_pos == -1 or pos < found_pos:
                    found_pos = pos

    if found_pos != -1:
        text_questions = full_text[:found_pos].strip()
        ans_raw = full_text[found_pos:].strip()
        ak = extract_answer_key_from_doc(None, ans_raw)
        
        # Chỉ tách khi thực sự tìm thấy cấu trúc bảng đáp án hợp lệ (ít nhất 2 câu hoặc có part rõ ràng hoặc có từ khóa BẢNG ĐÁP ÁN)
        has_clear_ak = bool(ak.part1 or ak.part2 or ak.part3 or len(ak) >= 2 or "BẢNG ĐÁP ÁN" in ans_raw.upper() or "BANG DAP AN" in ans_raw.upper())
        if has_clear_ak and len(ak) > 0:
            return text_questions, ans_raw, ak

    # Nếu không tìm thấy header rõ ràng hoặc không có đáp án thực sự trong phần đuôi
    ak = extract_answer_key_from_doc(None, full_text)
    return full_text, "", ak


def reconcile_quiz_with_answer_key(quiz_data: List[Dict[str, Any]], answer_key: AnswerKeyMap) -> List[Dict[str, Any]]:
    """
    Đối chiếu và áp đặt Bảng đáp án chuẩn (Source of Truth) lên toàn bộ danh sách câu hỏi:
    1. Câu hỏi Đúng / Sai: Gán đúng dict {"a": bool, "b": bool, "c": bool, "d": bool} từ bảng đáp án.
    2. Câu hỏi Trả lời ngắn: Gán đúng chuỗi đáp số từ bảng đáp án.
    3. Câu hỏi MCQ: Tìm phương án khớp với chữ cái đáp án trong bảng đáp án (A, B, C, D...).
    TUYỆT ĐỐI không để AI tự bịa hay thay đổi đáp án khi đã có Bảng đáp án chính thức.
    """
    if not quiz_data or not answer_key:
        return quiz_data

    if not isinstance(answer_key, AnswerKeyMap):
        ak_obj = AnswerKeyMap()
        if isinstance(answer_key, dict):
            for k, v in answer_key.items():
                ak_obj[k] = v
        answer_key = ak_obj

    part_counters = {'mcq': 0, 'true_false': 0, 'short_answer': 0}

    for idx, q_item in enumerate(quiz_data):
        if not isinstance(q_item, dict):
            continue

        q_type = q_item.get('type', 'mcq')
        linear_num = idx + 1

        # Cố gắng tìm số thứ tự gốc trong đề bài nếu có (ví dụ: "Câu 5:", "5.")
        raw_num = None
        q_text = q_item.get('question', '')
        num_m = re.search(r'^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*(\d+)|\s*(\d+)[\.\:\)])', q_text, re.IGNORECASE)
        if num_m:
            raw_num = int(num_m.group(1) or num_m.group(2))

        # Tự động cứu hộ: Nếu câu hỏi bị gán nhầm là short_answer nhưng thực chất chứa các ý a, b, c, d
        if q_type == 'short_answer':
            from services.ai_service import extract_sub_statements_from_text
            stem, opts = extract_sub_statements_from_text(q_item.get('question', ''))
            if len(opts) >= 3:
                q_type = 'true_false'
                q_item['type'] = 'true_false'
                q_item['question'] = stem
                q_item['options'] = opts

        # Đếm số thứ tự con trong phần tương ứng
        if q_type == 'true_false':
            part_counters['true_false'] += 1
            part_num = part_counters['true_false']
        elif q_type == 'short_answer':
            part_counters['short_answer'] += 1
            part_num = part_counters['short_answer']
        else:
            part_counters['mcq'] += 1
            part_num = part_counters['mcq']

        # Nếu là câu Đúng/Sai nhưng options bị thiếu, tự trích xuất lại từ nội dung câu hỏi
        if q_type == 'true_false' and len(q_item.get('options', [])) <= 1:
            from services.ai_service import extract_sub_statements_from_text
            stem, opts = extract_sub_statements_from_text(q_item.get('question', ''))
            if len(opts) >= 3:
                q_item['question'] = stem
                q_item['options'] = opts

        official_ans = answer_key.get_answer(
            q_type=q_type,
            linear_num=linear_num,
            part_num=part_num,
            raw_num=raw_num
        )

        if official_ans is not None:
            if q_type == 'true_false':
                if isinstance(official_ans, dict):
                    q_item['correct_answer'] = official_ans
                elif isinstance(official_ans, str) and len(official_ans) >= 2:
                    from services.ai_service import parse_tf_answer
                    q_item['correct_answer'] = parse_tf_answer(official_ans)
            elif q_type == 'short_answer':
                q_item['correct_answer'] = str(official_ans).strip()
            else: # MCQ
                target_char = str(official_ans).strip()[:1].upper()
                opts = q_item.get('options', [])
                matched = False
                for opt in opts:
                    if opt.strip().upper().startswith(f"{target_char}."):
                        q_item['correct_answer'] = opt
                        matched = True
                        break
                if not matched and opts:
                    for opt in opts:
                        if re.match(rf'^\*?\s*{target_char}[\.\:\)]', opt.strip(), re.IGNORECASE):
                            q_item['correct_answer'] = opt
                            matched = True
                            break

    return quiz_data

