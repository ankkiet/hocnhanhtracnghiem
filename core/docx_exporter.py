import io
import re
import os
import html
import base64
from typing import Optional, List, Tuple
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

import latex2mathml.converter
from lxml import etree

# Khởi tạo XSLT Transformer từ file MML2OMML.XSL chuẩn của Microsoft
XSL_PATH = os.path.join(os.path.dirname(__file__), 'MML2OMML.XSL')
XSLT_TRANSFORMER = None
try:
    if os.path.exists(XSL_PATH):
        xslt_doc = etree.parse(XSL_PATH)
        XSLT_TRANSFORMER = etree.XSLT(xslt_doc)
    else:
        print(f"Warning: MML2OMML.XSL not found at {XSL_PATH}")
except Exception as e:
    print(f"Warning: Failed to load MML2OMML.XSL: {e}")


def latex_to_clean_unicode(latex_str: str) -> str:
    """Chuyển đổi chuỗi LaTeX sang Unicode toán học dễ đọc (dùng khi fallback)."""
    if not latex_str:
        return ""
    s = latex_str.strip()
    # Gỡ bỏ các ký hiệu bao quanh
    if s.startswith('$$') and s.endswith('$$') and len(s) >= 4:
        s = s[2:-2].strip()
    elif s.startswith('$') and s.endswith('$') and len(s) >= 2:
        s = s[1:-1].strip()
    elif s.startswith(r'\[') and s.endswith(r'\]') and len(s) >= 4:
        s = s[2:-2].strip()
    elif s.startswith(r'\(') and s.endswith(r'\)') and len(s) >= 4:
        s = s[2:-2].strip()

    # Phân số \frac{a}{b} -> (a)/(b)
    for _ in range(4):
        if r'\frac' not in s:
            break
        s = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'(\1)/(\2)', s)

    # Căn thức
    s = re.sub(r'\\sqrt\[([^\]]+)\]\{([^{}]+)\}', r'[\1]√(\2)', s)
    s = re.sub(r'\\sqrt\{([^{}]+)\}', r'√(\1)', s)

    # Chữ cái Hy Lạp
    greek_map = {
        r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\Delta': 'Δ', r'\delta': 'δ',
        r'\epsilon': 'ε', r'\varepsilon': 'ε', r'\zeta': 'ζ', r'\eta': 'η', r'\theta': 'θ',
        r'\lambda': 'λ', r'\mu': 'μ', r'\pi': 'π', r'\rho': 'ρ', r'\sigma': 'σ',
        r'\Sigma': 'Σ', r'\tau': 'τ', r'\phi': 'φ', r'\varphi': 'ϕ', r'\omega': 'ω',
        r'\Omega': 'Ω'
    }
    for k, v in greek_map.items():
        s = re.sub(re.escape(k) + r'(?![a-zA-Z])', v, s)

    # Ký hiệu toán học
    sym_map = {
        r'\pm': '±', r'\mp': '∓', r'\times': '×', r'\div': '÷', r'\cdot': '·',
        r'\leq': '≤', r'\le': '≤', r'\geq': '≥', r'\ge': '≥', r'\neq': '≠', r'\ne': '≠',
        r'\approx': '≈', r'\equiv': '≡', r'\in': '∈', r'\notin': '∉', r'\subset': '⊂',
        r'\cup': '∪', r'\cap': '∩', r'\emptyset': '∅', r'\infty': '∞',
        r'\rightarrow': '→', r'\to': '→', r'\longrightarrow': '⟶',
        r'\Rightarrow': '⇒', r'\Leftrightarrow': '⇔', r'\rightleftharpoons': '⇌',
        r'\forall': '∀', r'\exists': '∃', r'\perp': '⊥', r'\parallel': '∥',
        r'\angle': '∠', r'\circ': '°', r'\degree': '°',
        r'\dots': '...', r'\ldots': '...', r'\cdots': '...',
        r'\setminus': '\\', r'\mathbb{R}': 'ℝ', r'\mathbb{N}': 'ℕ',
        r'\mathbb{Z}': 'ℤ', r'\mathbb{Q}': 'ℚ', r'\mathbb{C}': 'ℂ',
        r'\int': '∫', r'\sum': '∑'
    }
    for k, v in sym_map.items():
        s = re.sub(re.escape(k) + r'(?![a-zA-Z])', v, s)

    # Bỏ các lệnh bọc text/font
    s = re.sub(r'\\(?:text|mathrm|mathbf|mathit|textbf|textit|underline|overline)\{([^{}]*)\}', r'\1', s)
    s = re.sub(r'\\left([(\[{|])', r'\1', s)
    s = re.sub(r'\\right([)\]}|])', r'\1', s)
    s = s.replace(r'\{', '{').replace(r'\}', '}')
    s = s.replace(r'\,', ' ').replace(r'\;', ' ').replace(r'\:', ' ').replace(r'\!', '')

    # Chỉ số trên và dưới đơn giản
    sup_map = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '+': '⁺', '-': '⁻', 'n': 'ⁿ', 'x': 'ˣ'}
    sub_map = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉', '+': '₊', '-': '₋', 'x': 'ₓ'}
    for k, v in sup_map.items():
        s = re.sub(r'\^\{?' + re.escape(k) + r'\}?', v, s)
    for k, v in sub_map.items():
        s = re.sub(r'_\{?' + re.escape(k) + r'\}?', v, s)

    s = re.sub(r'[{}]', '', s)
    s = s.replace('\\\\', ' ')
    return s.strip()


def latex_to_omml(latex_str: str) -> Optional[OxmlElement]:
    """Chuyển đổi chuỗi công thức LaTeX sang thẻ <m:oMath> chuẩn của Microsoft Word."""
    if not XSLT_TRANSFORMER or not latex_str or not latex_str.strip():
        return None
    
    s = latex_str.strip()
    if s.startswith('$$') and s.endswith('$$') and len(s) >= 4:
        s = s[2:-2].strip()
    elif s.startswith('$') and s.endswith('$') and len(s) >= 2:
        s = s[1:-1].strip()
    elif s.startswith(r'\[') and s.endswith(r'\]') and len(s) >= 4:
        s = s[2:-2].strip()
    elif s.startswith(r'\(') and s.endswith(r'\)') and len(s) >= 4:
        s = s[2:-2].strip()
        
    if not s:
        return None

    try:
        # Thay thế một số macro đặc thù
        s = s.replace(r'\degree', r'^\circ')
        
        # 1. Chuyển LaTeX sang MathML
        mathml = latex2mathml.converter.convert(s)
        # Sửa các ký tự '&' chưa escape trong MathML (như aligned hoặc ma trận)
        mathml_fixed = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#x?[0-9a-fA-F]+);)', '&amp;', mathml)
        
        # 2. Parse MathML thành XML DOM với parser có tính năng tự phục hồi
        parser = etree.XMLParser(recover=True)
        dom = etree.fromstring(mathml_fixed.encode('utf-8'), parser=parser)
        
        # 3. Dùng XSLT biến đổi MathML sang Office MathML (OMML)
        new_dom = XSLT_TRANSFORMER(dom)
        omml_bytes = etree.tostring(new_dom, encoding='utf-8')
        
        # 4. Parse thành OxmlElement của docx
        elem = parse_xml(omml_bytes)
        
        # Nếu phần tử bọc ngoài là oMathPara, lấy oMath bên trong để hiển thị inline liền mạch
        if elem.tag.endswith('oMathPara'):
            inner = elem.find(qn('m:oMath'))
            if inner is not None:
                return inner
        return elem
    except Exception as e:
        return None


def fetch_image_stream(src: str) -> Optional[io.BytesIO]:
    """Tải hoặc giải mã dữ liệu ảnh từ URL, Base64, hoặc file path."""
    try:
        if not src:
            return None
        if src.startswith("data:image/"):
            header, encoded = src.split(",", 1)
            img_bytes = base64.b64decode(encoded)
            return io.BytesIO(img_bytes)
        elif src.startswith("http://") or src.startswith("https://"):
            import requests
            resp = requests.get(src, timeout=5)
            if resp.status_code == 200:
                return io.BytesIO(resp.content)
        elif os.path.exists(src):
            with open(src, "rb") as f:
                return io.BytesIO(f.read())
    except Exception as e:
        print(f"Warning: Không thể tải ảnh '{src[:50]}...': {e}")
    return None


def add_formatted_text(
    paragraph,
    text: str,
    font_name: str = "Times New Roman",
    font_size_pt: float = 11,
    base_bold: bool = False,
    base_italic: bool = False,
    base_color: Optional[RGBColor] = None
):
    """
    Phân tích chuỗi chứa text, công thức LaTeX, thẻ HTML (sub, sup, b, i, img, br)
    và xuất ra paragraph trong Word dưới dạng công thức toán học chuyên nghiệp (OMML)
    và định dạng chuẩn in ấn.
    """
    if not text:
        return

    # Pattern nhận diện:
    # 1. Khối công thức Toán LaTeX: $$, \[, \(, $...$
    # 2. Khối LaTeX trần thường gặp: \frac{...}{...}, \sqrt{...}
    # 3. Thẻ ảnh HTML: <img ...>
    # 4. Xuống dòng: <br>, \n
    # 5. Thẻ định dạng HTML: <b>, </b>, <i>, </i>, <u>, </u>, <sup>, </sup>, <sub>, </sub>, <p>, </p>
    pattern = re.compile(
        r'('
        r'\$\$.*?\$\$|'
        r'\\\[.*?\\\]|'
        r'\\\(.*?\\\)|'
        r'(?<!\\)\$(?!\s)[^\$\n]+?(?<!\s)(?<!\\)\$|'
        r'\\(?:frac|sqrt)\s*(?:\[[^\]]*\]\s*)?\{[^{}]*\}\s*(?:\{[^{}]*\})?|'
        r'<img\b[^>]*\/?>|'
        r'<br\s*\/?>|'
        r'</?[a-zA-Z][^>]*>|'
        r'\r?\n'
        r')',
        re.DOTALL | re.IGNORECASE
    )

    parts = pattern.split(text)

    # Trạng thái định dạng
    is_bold = base_bold
    is_italic = base_italic
    is_underline = False
    is_sup = False
    is_sub = False

    for part in parts:
        if not part:
            continue

        lower_part = part.lower().strip()

        # 1. Thẻ HTML xuống dòng hoặc ký tự newline
        if lower_part in ('<br>', '<br/>', '<br />', '\n', '\r\n') or part in ('\n', '\r\n'):
            run = paragraph.add_run()
            run.add_break()
            continue

        # 2. Xử lý các thẻ định dạng HTML
        if lower_part in ('<b>', '<strong>'):
            is_bold = True
            continue
        elif lower_part in ('</b>', '</strong>'):
            is_bold = base_bold
            continue
        elif lower_part in ('<i>', '<em>'):
            is_italic = True
            continue
        elif lower_part in ('</i>', '</em>'):
            is_italic = base_italic
            continue
        elif lower_part == '<u>':
            is_underline = True
            continue
        elif lower_part == '</u>':
            is_underline = False
            continue
        elif lower_part == '<sup>':
            is_sup = True
            continue
        elif lower_part == '</sup>':
            is_sup = False
            continue
        elif lower_part == '<sub>':
            is_sub = True
            continue
        elif lower_part == '</sub>':
            is_sub = False
            continue
        elif lower_part in ('<p>', '</p>', '<span>', '</span>'):
            continue

        # 3. Thẻ ảnh HTML <img src="...">
        if lower_part.startswith('<img'):
            src_match = re.search(r'src=["\']([^"\']+)["\']', part, re.IGNORECASE)
            if src_match:
                src = src_match.group(1)
                stream = fetch_image_stream(src)
                if stream:
                    try:
                        run_img = paragraph.add_run()
                        run_img.add_picture(stream, width=Inches(3.5))
                        continue
                    except Exception as e:
                        print(f"Error adding picture to docx: {e}")
            continue

        # 4. Công thức toán học LaTeX
        is_math = (
            part.startswith('$$') and part.endswith('$$') and len(part) >= 4 or
            part.startswith(r'\[') and part.endswith(r'\]') and len(part) >= 4 or
            part.startswith(r'\(') and part.endswith(r'\)') and len(part) >= 4 or
            part.startswith('$') and part.endswith('$') and len(part) >= 2 or
            part.startswith(r'\frac') or
            part.startswith(r'\sqrt')
        )

        if is_math:
            omml_elem = latex_to_omml(part)
            if omml_elem is not None:
                # Chèn trực tiếp Equation Office MathML vào đoạn văn
                paragraph._p.append(omml_elem)
            else:
                # Fallback: Chuyển sang ký tự Unicode toán học sạch sẽ
                clean_math = latex_to_clean_unicode(part)
                run = paragraph.add_run(clean_math)
                run.font.name = font_name
                run.font.size = Pt(font_size_pt)
                run.italic = True
                if base_color:
                    run.font.color.rgb = base_color
            continue

        # 5. Đoạn text thông thường
        unescaped_text = html.unescape(part)
        run = paragraph.add_run(unescaped_text)
        run.font.name = font_name
        run.font.size = Pt(font_size_pt)
        run.bold = is_bold
        run.italic = is_italic
        run.underline = is_underline
        if is_sup:
            run.font.superscript = True
        if is_sub:
            run.font.subscript = True
        if base_color:
            run.font.color.rgb = base_color


def export_quiz_to_docx(title: str, questions: list, time_limit: int = 0) -> io.BytesIO:
    """
    Tạo file Word (.docx) chuẩn format đề thi in ấn cho Giáo viên,
    tự động biên dịch mọi công thức LaTeX thành phương trình Word Equation (OMML) chính xác và rõ nét.
    """
    doc = Document()
    
    # Thiết lập lề trang A4 chuẩn in ấn
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        
    # Tiêu đề đề thi
    p_header = doc.add_paragraph()
    p_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_header.paragraph_format.space_after = Pt(4)
    run_header = p_header.add_run(f"ĐỀ KIỂM TRA TRẮC NGHIỆM: {title.upper()}")
    run_header.bold = True
    run_header.font.name = 'Times New Roman'
    run_header.font.size = Pt(14)
    run_header.font.color.rgb = RGBColor(26, 86, 219)
    
    # Thông tin thời gian và học sinh
    time_str = f"Thời gian làm bài: {time_limit} phút" if time_limit > 0 else "Thời gian làm bài: Tự do"
    p_info = doc.add_paragraph()
    p_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_info.paragraph_format.space_after = Pt(4)
    run_time = p_info.add_run(f"{time_str} | Tổng số câu: {len(questions)} câu\n")
    run_time.font.name = 'Times New Roman'
    run_time.font.size = Pt(11)
    run_time.italic = True
    
    run_stu = p_info.add_run("Họ và tên thí sinh: .............................................................. Lớp: .........................")
    run_stu.font.name = 'Times New Roman'
    run_stu.font.size = Pt(11)
    run_stu.bold = True
    
    p_div = doc.add_paragraph("-" * 55)
    p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_div.paragraph_format.space_after = Pt(10)
    
    # Danh sách câu hỏi
    current_group = None
    for idx, q in enumerate(questions, 1):
        group_title = q.get('group_title', '').strip()
        if group_title and group_title != current_group:
            current_group = group_title
            p_group = doc.add_paragraph()
            p_group.paragraph_format.space_before = Pt(8)
            p_group.paragraph_format.space_after = Pt(4)
            run_g = p_group.add_run(f"[{group_title}]")
            run_g.bold = True
            run_g.italic = True
            run_g.font.name = 'Times New Roman'
            run_g.font.size = Pt(11)
            run_g.font.color.rgb = RGBColor(71, 85, 105)

        q_text = q.get('question', '')
        options = q.get('options', [])
        
        # Tiêu đề câu hỏi
        p_q = doc.add_paragraph()
        p_q.paragraph_format.space_before = Pt(6)
        p_q.paragraph_format.space_after = Pt(3)
        p_q.paragraph_format.line_spacing = 1.15
        
        run_q_title = p_q.add_run(f"Câu {idx}: ")
        run_q_title.bold = True
        run_q_title.font.name = 'Times New Roman'
        run_q_title.font.size = Pt(11)
        run_q_title.font.color.rgb = RGBColor(30, 41, 59)
        
        add_formatted_text(p_q, q_text, font_name='Times New Roman', font_size_pt=11)
        
        q_type = q.get('type', 'mcq')
        if q_type == 'short_answer':
            p_ans = doc.add_paragraph()
            p_ans.paragraph_format.left_indent = Inches(0.3)
            p_ans.paragraph_format.space_before = Pt(3)
            p_ans.paragraph_format.space_after = Pt(4)
            run_prompt = p_ans.add_run("Đáp số: ")
            run_prompt.bold = True
            run_prompt.font.name = 'Times New Roman'
            run_prompt.font.size = Pt(11)
            run_dots = p_ans.add_run("...................................................................................")
            run_dots.font.name = 'Times New Roman'
            run_dots.font.size = Pt(11)
        elif q_type == 'true_false' or isinstance(q.get('correct_answer'), dict):
            # Các mệnh đề a), b), c), d) trong câu hỏi Đúng / Sai
            for opt in options:
                p_opt = doc.add_paragraph()
                p_opt.paragraph_format.left_indent = Inches(0.3)
                p_opt.paragraph_format.space_after = Pt(2)
                p_opt.paragraph_format.line_spacing = 1.15
                
                match_prefix = re.match(r'^(\*?\s*[a-dA-D][\.\:\)])\s*(.*)', str(opt).strip())
                if match_prefix:
                    label = match_prefix.group(1) + " "
                    content = match_prefix.group(2)
                    run_label = p_opt.add_run(label)
                    run_label.bold = True
                    run_label.font.name = 'Times New Roman'
                    run_label.font.size = Pt(11)
                    add_formatted_text(p_opt, content, font_name='Times New Roman', font_size_pt=11)
                else:
                    add_formatted_text(p_opt, str(opt), font_name='Times New Roman', font_size_pt=11)
                
                run_tag = p_opt.add_run("   [ Đúng / Sai ]")
                run_tag.italic = True
                run_tag.bold = True
                run_tag.font.name = 'Times New Roman'
                run_tag.font.size = Pt(10)
                run_tag.font.color.rgb = RGBColor(100, 116, 139)
        else:
            # Các lựa chọn A, B, C, D (MCQ chuẩn)
            for opt in options:
                p_opt = doc.add_paragraph()
                p_opt.paragraph_format.left_indent = Inches(0.3)
                p_opt.paragraph_format.space_after = Pt(2)
                p_opt.paragraph_format.line_spacing = 1.15
                
                # Nhận diện tiền tố A. B. C. D. để in đậm
                match_prefix = re.match(r'^(\*?\s*[A-Fa-f][\.\:\)])\s*(.*)', str(opt).strip())
                if match_prefix:
                    label = match_prefix.group(1) + " "
                    content = match_prefix.group(2)
                    run_label = p_opt.add_run(label)
                    run_label.bold = True
                    run_label.font.name = 'Times New Roman'
                    run_label.font.size = Pt(11)
                    add_formatted_text(p_opt, content, font_name='Times New Roman', font_size_pt=11)
                else:
                    add_formatted_text(p_opt, str(opt), font_name='Times New Roman', font_size_pt=11)
            
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
        
    # Trang Bảng Đáp án (Answer Key)
    doc.add_page_break()
    p_key_title = doc.add_paragraph()
    p_key_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_key = p_key_title.add_run("--- BẢNG ĐÁP ÁN & HƯỚNG DẪN GIẢI ---")
    run_key.bold = True
    run_key.font.name = 'Times New Roman'
    run_key.font.size = Pt(13)
    run_key.font.color.rgb = RGBColor(22, 101, 52)
    
    # Tạo bảng đáp án nhanh
    if questions:
        cols = 5
        rows = (len(questions) + cols - 1) // cols
        table = doc.add_table(rows=rows * 2, cols=cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = 'Table Grid'
        
        for i, q in enumerate(questions):
            col_idx = i % cols
            row_idx = (i // cols) * 2
            
            # Ô số thứ tự câu
            cell_q = table.cell(row_idx, col_idx)
            cell_q.text = f"Câu {i+1}"
            p_cell_q = cell_q.paragraphs[0]
            p_cell_q.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if p_cell_q.runs:
                p_cell_q.runs[0].bold = True
                p_cell_q.runs[0].font.name = 'Times New Roman'
                p_cell_q.runs[0].font.size = Pt(10)
            shading_q = parse_xml(r'<w:shd {} w:fill="F1F5F9"/>'.format(nsdecls('w')))
            cell_q._tc.get_or_add_tcPr().append(shading_q)
            
            # Ô đáp án đúng (Hỗ trợ MCQ, Đúng/Sai, Trả lời ngắn theo Bộ GD&ĐT)
            q_type = q.get('type', 'mcq')
            raw_ca = q.get('correct_answer')
            correct_display = ""
            
            if q_type == 'true_false' or isinstance(raw_ca, dict):
                if isinstance(raw_ca, dict):
                    parts = [f"{k}-{'Đ' if raw_ca.get(k) else 'S'}" for k in ['a', 'b', 'c', 'd'] if k in raw_ca]
                    correct_display = ", ".join(parts) if parts else str(raw_ca)
                else:
                    correct_display = str(raw_ca)
            elif q_type == 'short_answer':
                correct_display = str(raw_ca or '')
            else:
                correct_str = str(raw_ca or '').strip()
                for c in ["A", "B", "C", "D"]:
                    if correct_str.startswith(f"{c}.") or correct_str.startswith(f"{c}:") or correct_str == c:
                        correct_display = c
                        break
                if not correct_display and correct_str:
                    correct_display = correct_str[:2]
                    
            cell_ans = table.cell(row_idx + 1, col_idx)
            cell_ans.text = correct_display or "-"
            p_cell_ans = cell_ans.paragraphs[0]
            p_cell_ans.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if p_cell_ans.runs:
                p_cell_ans.runs[0].bold = True
                p_cell_ans.runs[0].font.name = 'Times New Roman'
                p_cell_ans.runs[0].font.size = Pt(11)
                p_cell_ans.runs[0].font.color.rgb = RGBColor(220, 38, 38)
                
    # Thêm phần giải thích chi tiết nếu có
    has_explains = any(q.get('explain') for q in questions)
    if has_explains:
        doc.add_paragraph().paragraph_format.space_after = Pt(10)
        p_exp_title = doc.add_paragraph()
        run_exp_title = p_exp_title.add_run("Chi tiết lời giải:")
        run_exp_title.bold = True
        run_exp_title.font.name = 'Times New Roman'
        run_exp_title.font.size = Pt(12)
        run_exp_title.font.color.rgb = RGBColor(30, 41, 59)
        
        for idx, q in enumerate(questions, 1):
            exp = q.get('explain', '')
            if exp:
                p_exp = doc.add_paragraph()
                p_exp.paragraph_format.space_before = Pt(4)
                p_exp.paragraph_format.space_after = Pt(3)
                p_exp.paragraph_format.line_spacing = 1.15
                
                run_exp_q = p_exp.add_run(f"Câu {idx}: ")
                run_exp_q.bold = True
                run_exp_q.font.name = 'Times New Roman'
                run_exp_q.font.size = Pt(11)
                run_exp_q.font.color.rgb = RGBColor(79, 70, 229)
                
                add_formatted_text(p_exp, exp, font_name='Times New Roman', font_size_pt=11)
                
    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream
