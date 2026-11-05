import base64
import html
import io
import os
import re
from typing import Optional

import latex2mathml.converter
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor
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


# Danh sách các lệnh LaTeX chuẩn bắt đầu bằng chữ 'n' không được làm biến dạng
VALID_LATEX_N_COMMANDS = {
    'nearrow', 'nwarrow', 'neq', 'ne', 'notin', 'nabla', 'nu', 'not', 'neg',
    'natural', 'nleq', 'ngeq', 'nless', 'ngtr', 'nprec', 'nsucc', 'nsim',
    'nsubset', 'nsupset', 'nsubseteq', 'nsupseteq', 'normalsize', 'noindent',
    'newcommand', 'newenvironment'
}


def sanitize_latex_formula(latex_str: str) -> str:
    """
    Làm sạch và phục hồi công thức LaTeX bị lỗi HTML/newline/bảng biến thiên trước khi render sang OMML/MathML.
    Khắc phục triệt để lỗi thẻ <br>, chuỗi thoát \\n, dấu \\ thừa làm vỡ bảng biến thiên và công thức.
    """
    if not latex_str or not latex_str.strip():
        return ""
    s = latex_str.strip()

    # 1. Gỡ bỏ các ký hiệu bao quanh ($$, $, \[, \])
    if s.startswith('$$') and s.endswith('$$') and len(s) >= 4:
        s = s[2:-2].strip()
    elif s.startswith('$') and s.endswith('$') and len(s) >= 2:
        s = s[1:-1].strip()
    elif s.startswith(r'\[') and s.endswith(r'\]') and len(s) >= 4:
        s = s[2:-2].strip()
    elif s.startswith(r'\(') and s.endswith(r'\)') and len(s) >= 4:
        s = s[2:-2].strip()

    # 2. Chuyển đổi các thực thể HTML phổ biến
    s = s.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

    # 3. Xử lý các thẻ <br>, <br/> bị lọt vào công thức
    # Nếu đi liền sau dấu \\ (xuống dòng của LaTeX) -> Giữ lại \\ và loại bỏ <br>
    s = re.sub(r'\\\\(?:\s*<br\s*\/?>|\s*\\?n|\s*\\?\r?\n)+', r'\\\\ \n', s, flags=re.IGNORECASE)
    s = re.sub(r'\\<br\s*\/?>', r'\\\\ \n', s, flags=re.IGNORECASE)

    # Nếu là <br> đứng trong môi trường bảng/mảng (array, matrix, cases, aligned)
    if any(env in s for env in ['array', 'matrix', 'pmatrix', 'bmatrix', 'cases', 'align', 'aligned']):
        # Nếu <br> ở ngay trước \end{...}, loại bỏ để tránh tạo dòng trống cuối bảng
        s = re.sub(r'<br\s*\/?>\s*(?:\\?n\s*)*(?=\\end\{)', ' ', s, flags=re.IGNORECASE)
        # Các <br> còn lại trong mảng chuyển thành \\ xuống dòng LaTeX
        s = re.sub(r'<br\s*\/?>', r'\\\\ \n', s, flags=re.IGNORECASE)
    else:
        s = re.sub(r'<br\s*\/?>', ' ', s, flags=re.IGNORECASE)

    # Loại bỏ các thẻ HTML bao bọc khác nếu có
    s = re.sub(r'<\/?(?:span|div|p|b|i|u|font|mark)[^>]*>', ' ', s, flags=re.IGNORECASE)

    # 4. Khắc phục lỗi chuỗi thoát \\n hoặc \n (bị in ra thành text \nx, \ny, \n-1...)
    def _fix_n_command(m):
        cmd = m.group(1)
        if cmd.lower() in VALID_LATEX_N_COMMANDS:
            return '\\' + cmd
        if cmd.startswith('n') and len(cmd) > 1:
            return ' ' + cmd[1:]
        if cmd == 'n':
            return ' '
        return '\\' + cmd

    s = re.sub(r'\\([a-zA-Z]+)', _fix_n_command, s)
    s = re.sub(r'\\n(?=[^a-zA-Z]|$)', ' ', s)

    # 5. Dọn dẹp dấu \\ thừa ở cuối môi trường (tránh sinh dòng trống cuối bảng)
    s = re.sub(r'\\\\\s*\\end\{(array|matrix|pmatrix|bmatrix|cases|aligned)\}', r'\\end{\1}', s)

    # 6. Thay thế macro đặc thù
    s = s.replace(r'\degree', r'^\circ')

    return s.strip()


def latex_to_clean_unicode(latex_str: str) -> str:
    """Chuyển đổi chuỗi LaTeX sang Unicode toán học dễ đọc (dùng khi fallback)."""
    if not latex_str:
        return ""
    s = sanitize_latex_formula(latex_str)
    if not s:
        return ""

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
        r'\rightarrow': '→', r'\to': '→', r'\longrightarrow': '⟶', r'\nearrow': '↗', r'\searrow': '↘', r'\nwarrow': '↖', r'\swarrow': '↙', r'\uparrow': '↑', r'\downarrow': '↓',
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

    s = sanitize_latex_formula(latex_str)
    if not s:
        return None

    try:

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
    except Exception:
        return None


DOCX_IMAGE_CACHE = {}


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
            if src in DOCX_IMAGE_CACHE:
                return io.BytesIO(DOCX_IMAGE_CACHE[src])
            import requests
            resp = requests.get(src, timeout=5)
            if resp.status_code == 200:
                DOCX_IMAGE_CACHE[src] = resp.content
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
        r'\\begin\{(?:array|matrix|pmatrix|bmatrix|cases|aligned|align\*?)\}[\s\S]*?\\end\{(?:array|matrix|pmatrix|bmatrix|cases|aligned|align\*?)\}|'
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
    is_strike = False
    is_sup = False
    is_sub = False
    active_color = base_color

    for part in parts:
        if not part:
            continue

        lower_part = part.lower().strip()

        # 1. Thẻ HTML xuống dòng hoặc ký tự newline
        if re.match(r'^<br\b[^>]*\/?>$', lower_part) or lower_part in ('\n', '\r\n', '&lt;br&gt;', '&lt;br/&gt;', '&lt;br /&gt;') or part in ('\n', '\r\n'):
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
        elif lower_part in ('<s>', '<strike>', '<del>'):
            is_strike = True
            continue
        elif lower_part in ('</s>', '</strike>', '</del>'):
            is_strike = False
            continue
        elif lower_part.startswith('<span') or lower_part.startswith('<font'):
            # Trích xuất mã màu từ style="color: #..." hoặc color="..."
            color_match = re.search(r'color:\s*(#[0-9a-fA-F]{3,6}|rgb\([^)]+\)|[a-zA-Z]+)', part, re.IGNORECASE) or re.search(r'color=["\']([^"\']+)["\']', part, re.IGNORECASE)
            if color_match:
                c_str = color_match.group(1).strip().lower()
                if c_str.startswith('#'):
                    hex_val = c_str.lstrip('#')
                    if len(hex_val) == 3:
                        hex_val = ''.join([c*2 for c in hex_val])
                    if len(hex_val) == 6:
                        try:
                            r = int(hex_val[0:2], 16)
                            g = int(hex_val[2:4], 16)
                            b = int(hex_val[4:6], 16)
                            active_color = RGBColor(r, g, b)
                        except Exception:
                            pass
                elif c_str in ('red', 'do', 'đỏ'):
                    active_color = RGBColor(220, 38, 38)
                elif c_str in ('blue', 'xanh'):
                    active_color = RGBColor(37, 99, 235)
                elif c_str in ('green', 'xanh lá'):
                    active_color = RGBColor(22, 163, 74)
            continue
        elif lower_part in ('</span>', '</font>'):
            active_color = base_color
            continue
        elif lower_part in ('<p>', '</p>', '<span>'):
            continue

        # 3. Thẻ ảnh HTML <img src="...">
        if lower_part.startswith('<img'):
            src_match = re.search(r'src=["\']([^"\']+)["\']', part, re.IGNORECASE)
            if src_match:
                src = src_match.group(1)
                stream = fetch_image_stream(src)
                if stream:
                    try:
                        # Trích xuất kích thước width tùy biến nếu người dùng kéo giãn trong editor
                        w_inches = 3.5
                        w_match = re.search(r'width:\s*(\d+)px', part, re.IGNORECASE) or re.search(r'width=["\'](\d+)(?:px)?["\']', part, re.IGNORECASE)
                        if w_match:
                            try:
                                px_val = float(w_match.group(1))
                                if px_val > 0:
                                    w_inches = min(6.5, max(1.0, px_val / 96.0))
                            except Exception:
                                pass
                        run_img = paragraph.add_run()
                        run_img.add_picture(stream, width=Inches(w_inches))
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
            part.startswith(r'\sqrt') or
            part.startswith(r'\begin{')
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
        # Loại bỏ dấu backslash thừa ở cuối dòng text (ví dụ: "có bảng biến thiên như sau:\")
        unescaped_text = re.sub(r'\\+(?=\s*$)', '', unescaped_text)
        run = paragraph.add_run(unescaped_text)
        run.font.name = font_name
        run.font.size = Pt(font_size_pt)
        run.bold = is_bold
        run.italic = is_italic
        run.underline = is_underline
        if is_strike:
            run.font.strike = True
        if is_sup:
            run.font.superscript = True
        if is_sub:
            run.font.subscript = True
        if active_color:
            run.font.color.rgb = active_color


def markdown_table_to_html(text: str) -> str:
    """Chuyển đổi cú pháp bảng Markdown (| ... | ... |) sang HTML <table> chuẩn."""
    if not text or '|' not in text:
        return text

    # Sửa lỗi lịch sử earrow bị rớt ký tự \n khi parse JSON
    text = re.sub(r'\\?\s*\bearrow\b', r'\\nearrow', text)
    text = re.sub(r'\\?\s*\bsearrow\b', r'\\searrow', text)

    # Chuẩn hóa các ký tự xuống dòng thoát \\n hoặc <br> thành newline
    text_norm = re.sub(r'\\n', '\n', text)
    text_norm = re.sub(r'\\?&lt;br\s*\/?&gt;', '\n', text_norm)
    text_norm = re.sub(r'\\?<br\s*\/?>', '\n', text_norm)

    lines = text_norm.split('\n')
    new_lines = []
    table_lines = []
    in_table = False

    def process_table(tbl_lines):
        if not tbl_lines:
            return ''
        valid_rows = [l.strip() for l in tbl_lines if '|' in l]
        if len(valid_rows) < 2:
            return '\n'.join(tbl_lines)

        rows_data = []
        has_separator = False

        for r in valid_rows:
            raw_cells = r.strip().strip('|').split('|')
            cells = [c.strip() for c in raw_cells]
            if all(re.match(r'^:?-+:?$', c) for c in cells if c):
                has_separator = True
                continue
            rows_data.append(cells)

        if not rows_data:
            return '\n'.join(tbl_lines)

        max_cols = max(len(r) for r in rows_data)
        html_tbl = ['<table class="quiz-content-table">']
        start_idx = 0
        if has_separator and len(rows_data) > 0:
            html_tbl.append('<thead><tr>')
            for c in rows_data[0]:
                html_tbl.append(f'<th>{c}</th>')
            for _ in range(len(rows_data[0]), max_cols):
                html_tbl.append('<th></th>')
            html_tbl.append('</tr></thead>')
            start_idx = 1

        html_tbl.append('<tbody>')
        for row in rows_data[start_idx:]:
            html_tbl.append('<tr>')
            for c in row:
                html_tbl.append(f'<td>{c}</td>')
            for _ in range(len(row), max_cols):
                html_tbl.append('<td></td>')
            html_tbl.append('</tr>')
        html_tbl.append('</tbody></table>')
        return ''.join(html_tbl)

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') or (stripped.endswith('|') and '|' in stripped):
            table_lines.append(stripped)
            in_table = True
        else:
            if in_table:
                new_lines.append(process_table(table_lines))
                table_lines = []
                in_table = False
            new_lines.append(line)

    if in_table:
        new_lines.append(process_table(table_lines))

    return '\n'.join(new_lines)


def render_html_table_in_docx(doc, table_html: str, font_name: str = "Times New Roman", font_size_pt: float = 10.5):
    """Chuyển đổi thẻ HTML <table> thành bảng Word chuyên nghiệp."""
    try:
        from lxml import html as lxml_html
        tree = lxml_html.fragment_fromstring(table_html, create_parent='div')
        table_nodes = tree.xpath('.//table')
        if not table_nodes:
            return
        tbl = table_nodes[0]
        rows = tbl.xpath('.//tr')
        if not rows:
            return

        grid_data = []
        max_cols = 0
        has_thead = bool(tbl.xpath('.//thead//tr'))
        for tr in rows:
            cells = tr.xpath('./td | ./th')
            cell_texts = []
            for td in cells:
                raw_cell = lxml_html.tostring(td, encoding='utf-8').decode('utf-8')
                inner = re.sub(r'^<t[dh][^>]*>', '', raw_cell, flags=re.IGNORECASE)
                inner = re.sub(r'</t[dh]>$', '', inner, flags=re.IGNORECASE).strip()
                cell_texts.append(inner)
            if cell_texts:
                grid_data.append(cell_texts)
                if len(cell_texts) > max_cols:
                    max_cols = len(cell_texts)

        if not grid_data or max_cols == 0:
            return

        word_tbl = doc.add_table(rows=len(grid_data), cols=max_cols)
        word_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        word_tbl.style = 'Table Grid'

        for r_idx, row_cells in enumerate(grid_data):
            trPr = word_tbl.rows[r_idx]._tr.get_or_add_trPr()
            trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
            is_header_row = (r_idx == 0 and has_thead)
            for c_idx, cell_content in enumerate(row_cells):
                cell = word_tbl.cell(r_idx, c_idx)
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.line_spacing = 1.05
                if is_header_row:
                    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F8FAFC"/>')
                    cell._tc.get_or_add_tcPr().append(shd)
                add_formatted_text(p, cell_content, font_name=font_name, font_size_pt=font_size_pt, base_bold=is_header_row)
    except Exception as e:
        print(f"Warning: Không thể render HTML table sang docx: {e}")


def add_block_content(doc, text: str, font_name: str = "Times New Roman", font_size_pt: float = 11,
                      first_p=None, space_before: Pt = Pt(2), space_after: Pt = Pt(2), line_spacing: float = 1.05):
    """
    Hỗ trợ xuất nội dung có thể chứa cả thẻ HTML <table>, bảng Markdown (|...|),
    lẫn text/LaTeX vào tài liệu Word.
    """
    if not text:
        return
    text = markdown_table_to_html(text)
    if "<table" not in text.lower():
        p = first_p if first_p is not None else doc.add_paragraph()
        if first_p is None:
            p.paragraph_format.space_before = space_before
            p.paragraph_format.space_after = space_after
            p.paragraph_format.line_spacing = line_spacing
        add_formatted_text(p, text, font_name=font_name, font_size_pt=font_size_pt)
        return

    table_pattern = re.compile(r'(<table\b[\s\S]*?<\/table>)', re.IGNORECASE)
    parts = table_pattern.split(text)
    is_first = True
    for part in parts:
        if not part or not part.strip():
            continue
        if part.lower().startswith('<table'):
            render_html_table_in_docx(doc, part, font_name=font_name, font_size_pt=font_size_pt - 0.5)
        else:
            if is_first and first_p is not None:
                p = first_p
            else:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.line_spacing = line_spacing
            add_formatted_text(p, part, font_name=font_name, font_size_pt=font_size_pt)
            is_first = False


def create_borderless_table(doc, num_rows, num_cols, col_widths=None):
    tbl = doc.add_table(rows=num_rows, cols=num_cols)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tblPr = tbl._tbl.tblPr
    tblBorders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}><w:top w:val="none"/><w:left w:val="none"/><w:bottom w:val="none"/><w:right w:val="none"/><w:insideH w:val="none"/><w:insideV w:val="none"/></w:tblBorders>'
    )
    tblPr.append(tblBorders)
    tblCellMar = parse_xml(
        f'<w:tblCellMar {nsdecls("w")}><w:top w:w="0" w:type="dxa"/><w:bottom w:w="30" w:type="dxa"/><w:left w:w="40" w:type="dxa"/><w:right w:w="40" w:type="dxa"/></w:tblCellMar>'
    )
    tblPr.append(tblCellMar)
    for row in tbl.rows:
        trPr = row._tr.get_or_add_trPr()
        trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
    if col_widths:
        for row in tbl.rows:
            for idx, width in enumerate(col_widths):
                if idx < len(row.cells):
                    row.cells[idx].width = width
    return tbl


def determine_options_columns(options: list, user_choice: str = "auto") -> int:
    if not options:
        return 1
    if user_choice in ("1", "1_col", 1):
        return 1
    if user_choice in ("4", "4_col", 4) and len(options) == 4:
        return 4
    if user_choice in ("2", "2_col", 2) and len(options) in (2, 4):
        return 2

    for opt in options:
        opt_s = str(opt)
        if '<img' in opt_s.lower() or '$$' in opt_s or r'\[' in opt_s or '\n' in opt_s:
            return 1

    def clean_len(opt):
        s = str(opt)
        s = re.sub(r'<[^>]+>', '', s)
        s = re.sub(r'\\(?:frac|sqrt|left|right|text|mathrm)\b', '', s)
        s = re.sub(r'[\$\{\}\\\^_\s]+', ' ', s)
        return len(s.strip())

    lengths = [clean_len(opt) for opt in options]
    max_len = max(lengths) if lengths else 0

    if len(options) == 4:
        if max_len <= 18:
            return 4
        elif max_len <= 42:
            return 2
        else:
            return 1
    elif len(options) == 2:
        if max_len <= 42:
            return 2
        else:
            return 1
    return 1


def is_option_correct(opt_idx: int, opt_text: str, raw_ca) -> bool:
    if not raw_ca:
        return False
    clean_opt = str(opt_text).strip()
    if clean_opt.startswith('*'):
        return True
    clean_ca = str(raw_ca).strip()
    letter = chr(ord('A') + opt_idx) if 0 <= opt_idx < 26 else ""
    if clean_ca.upper() == letter:
        return True
    if clean_ca.upper().startswith(f"{letter}.") or clean_ca.upper().startswith(f"{letter}:") or clean_ca.upper().startswith(f"{letter})"):
        return True
    if clean_ca == str(opt_idx):
        return True
    match_prefix = re.match(r'^(\*?\s*[A-Fa-f][\.\:\)])\s*(.*)', clean_opt)
    if match_prefix and match_prefix.group(2).strip() and clean_ca.strip() == match_prefix.group(2).strip():
        return True
    return False


def normalize_tf_ca(raw_ca) -> dict:
    """Chuẩn hóa đáp án Đúng/Sai thành dict {'a': bool, 'b': bool, 'c': bool, 'd': bool}."""
    if isinstance(raw_ca, dict):
        result = {}
        for k, v in raw_ca.items():
            clean_k = str(k).lower().strip().replace(')', '').replace('.', '')
            is_true = (v is True or str(v).lower() in ('đ', 'd', 'true', '1'))
            result[clean_k] = is_true
        return result
    if isinstance(raw_ca, str):
        raw_str = raw_ca.strip()
        if raw_str.startswith('{') and raw_str.endswith('}'):
            try:
                import json
                parsed = json.loads(raw_str)
                if isinstance(parsed, dict):
                    return normalize_tf_ca(parsed)
            except Exception:
                pass
        try:
            from services.ai_service import parse_tf_answer
            return parse_tf_answer(raw_str)
        except Exception:
            pass
    if isinstance(raw_ca, (list, tuple, set)):
        return {str(x).lower().strip().replace(')', '').replace('.', ''): True for x in raw_ca}
    return {}


def extract_answer_display(q: dict) -> str:
    """Trích xuất chuỗi hiển thị đáp án đúng ngắn gọn (A, B, C, D hoặc a-Đ b-S hoặc số đáp án ngắn)."""
    q_type = q.get('type', 'mcq')
    raw_ca = q.get('correct_answer')
    if raw_ca is None or raw_ca == '':
        return "-"

    if q_type == 'true_false' or isinstance(raw_ca, dict):
        ca_dict = normalize_tf_ca(raw_ca)
        if ca_dict:
            parts = [f"{k}-{'Đ' if ca_dict.get(k) else 'S'}" for k in ['a', 'b', 'c', 'd'] if k in ca_dict]
            return ", ".join(parts) if parts else str(raw_ca)
        return str(raw_ca)

    elif q_type == 'short_answer':
        return str(raw_ca or '')

    else:
        correct_str = str(raw_ca or '').strip()
        for c in ["A", "B", "C", "D"]:
            if correct_str.startswith(f"{c}.") or correct_str.startswith(f"{c}:") or correct_str == c:
                return c
        if correct_str:
            return correct_str[:2]
        return "-"


def render_quiz_document_content(
    doc: Document,
    title: str,
    questions: list,
    time_limit: int = 0,
    target_audience: str = "teacher",
    layout_mode: str = "compact",
    options_layout: str = "auto",
    show_answers: bool = True,
    show_key_table: bool = True,
    show_explains: bool = True,
    include_student_answer_grid: bool = False,
    exam_code: Optional[str] = None,
    school_name: Optional[str] = None,
    show_candidate_info: bool = True
):
    """Điền nội dung một đề thi hoàn chỉnh vào đối tượng Document (đáp ứng cả đề đơn và đề con trong tập gộp)."""
    is_compact = (layout_mode == "compact")
    font_size_pt = 10.5 if is_compact else 11.0
    q_space_before = Pt(3 if is_compact else 6)
    q_space_after = Pt(1.5 if is_compact else 3)
    q_line_spacing = 1.08 if is_compact else 1.2
    opt_space_after = Pt(1.5 if is_compact else 2.5)
    opt_line_spacing = 1.05 if is_compact else 1.15
    available_width_inches = 7.17 if is_compact else 6.77

    # 1. Tên trường / Đơn vị tổ chức nếu có
    if school_name:
        p_school = doc.add_paragraph()
        p_school.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_school.paragraph_format.space_before = Pt(0)
        p_school.paragraph_format.space_after = Pt(1)
        run_s = p_school.add_run(school_name.upper())
        run_s.bold = True
        run_s.font.name = 'Times New Roman'
        run_s.font.size = Pt(10 if is_compact else 10.5)
        run_s.font.color.rgb = RGBColor(71, 85, 105)

    # 2. Tiêu đề đề thi
    p_header = doc.add_paragraph()
    p_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_header.paragraph_format.space_before = Pt(0)
    p_header.paragraph_format.space_after = Pt(2 if is_compact else 3)
    run_header = p_header.add_run(f"ĐỀ KIỂM TRA TRẮC NGHIỆM: {title.upper()}")
    run_header.bold = True
    run_header.font.name = 'Times New Roman'
    run_header.font.size = Pt(13 if is_compact else 14)
    run_header.font.color.rgb = RGBColor(26, 86, 219)

    # Nhãn Mã đề thi nổi bật (nếu có mã đề)
    if exam_code:
        p_code = doc.add_paragraph()
        p_code.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_code.paragraph_format.space_before = Pt(0)
        p_code.paragraph_format.space_after = Pt(2)
        run_code = p_code.add_run(f"MÃ ĐỀ THI: {exam_code}")
        run_code.bold = True
        run_code.font.name = 'Times New Roman'
        run_code.font.size = Pt(11.5 if is_compact else 12.0)
        run_code.font.color.rgb = RGBColor(15, 23, 42)

    if target_audience == "teacher":
        p_badge = doc.add_paragraph()
        p_badge.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_badge.paragraph_format.space_before = Pt(0)
        p_badge.paragraph_format.space_after = Pt(3)
        code_suffix = f" - MÃ {exam_code}" if exam_code else ""
        run_badge = p_badge.add_run(f"[ BẢN GIÁO VIÊN - ĐÁP ÁN & HƯỚNG DẪN GIẢI{code_suffix} ]")
        run_badge.bold = True
        run_badge.font.name = 'Times New Roman'
        run_badge.font.size = Pt(10.5)
        run_badge.font.color.rgb = RGBColor(185, 28, 28)

    # Thông tin thời gian và học sinh
    time_str = f"Thời gian làm bài: {time_limit} phút" if time_limit > 0 else "Thời gian làm bài: Tự do"
    p_info = doc.add_paragraph()
    p_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_info.paragraph_format.space_before = Pt(0)
    p_info.paragraph_format.space_after = Pt(3 if is_compact else 4)
    run_time = p_info.add_run(f"{time_str} | Tổng số câu: {len(questions)} câu\n")
    run_time.font.name = 'Times New Roman'
    run_time.font.size = Pt(font_size_pt)
    run_time.italic = True

    if show_candidate_info:
        run_stu = p_info.add_run("Họ và tên thí sinh: .............................................................. SBD: ................. Lớp: .........................")
        run_stu.font.name = 'Times New Roman'
        run_stu.font.size = Pt(font_size_pt)
        run_stu.bold = True

    # Phiếu điền đáp án trắc nghiệm cho học sinh (nếu được bật)
    if target_audience == "student" and include_student_answer_grid and questions:
        p_grid_title = doc.add_paragraph()
        p_grid_title.paragraph_format.space_before = Pt(4)
        p_grid_title.paragraph_format.space_after = Pt(2)
        run_gt = p_grid_title.add_run("PHIẾU TRẢ LỜI TRẮC NGHIỆM:")
        run_gt.bold = True
        run_gt.font.name = 'Times New Roman'
        run_gt.font.size = Pt(10)
        run_gt.font.color.rgb = RGBColor(30, 41, 59)

        total_q = len(questions)
        grid_cols = 20 if total_q > 40 else 10
        grid_rows = ((total_q + grid_cols - 1) // grid_cols) * 2
        grid_table = doc.add_table(rows=grid_rows, cols=grid_cols)
        grid_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        grid_table.style = 'Table Grid'
        for row in grid_table.rows:
            trPr = row._tr.get_or_add_trPr()
            trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))

        for q_idx in range(total_q):
            row_pair = (q_idx // grid_cols) * 2
            col_pos = q_idx % grid_cols
            # Ô nhãn câu
            c_header = grid_table.cell(row_pair, col_pos)
            c_header.text = f"{q_idx + 1}"
            p_ch = c_header.paragraphs[0]
            p_ch.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_ch.paragraph_format.space_before = Pt(1)
            p_ch.paragraph_format.space_after = Pt(1)
            if p_ch.runs:
                p_ch.runs[0].bold = True
                p_ch.runs[0].font.name = 'Times New Roman'
                p_ch.runs[0].font.size = Pt(8.5 if grid_cols == 20 else 9.5)
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F1F5F9"/>')
            c_header._tc.get_or_add_tcPr().append(shd)

            # Ô để trống cho học sinh viết
            c_empty = grid_table.cell(row_pair + 1, col_pos)
            c_empty.text = " "
            p_ce = c_empty.paragraphs[0]
            p_ce.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_ce.paragraph_format.space_before = Pt(1)
            p_ce.paragraph_format.space_after = Pt(2)

    p_div = doc.add_paragraph("-" * (65 if is_compact else 55))
    p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_div.paragraph_format.space_before = Pt(2)
    p_div.paragraph_format.space_after = Pt(6 if is_compact else 10)

    # 4. Danh sách câu hỏi
    current_group = None
    for idx, q in enumerate(questions, 1):
        raw_gt = q.get('group_title', '')
        group_title = re.sub(r'<[^>]+>', ' ', str(raw_gt))
        group_title = re.sub(r'\s+', ' ', group_title).strip()
        if group_title and group_title != current_group:
            current_group = group_title
            p_group = doc.add_paragraph()
            p_group.paragraph_format.space_before = Pt(6 if is_compact else 8)
            p_group.paragraph_format.space_after = Pt(2 if is_compact else 4)
            run_g = p_group.add_run(f"[{group_title}]")
            run_g.bold = True
            run_g.italic = True
            run_g.font.name = 'Times New Roman'
            run_g.font.size = Pt(font_size_pt)
            run_g.font.color.rgb = RGBColor(71, 85, 105)

        q_text = q.get('question', '')
        options = q.get('options', [])
        q_type = q.get('type', 'mcq')
        raw_ca = q.get('correct_answer')

        # Dòng đề bài
        p_q = doc.add_paragraph()
        p_q.paragraph_format.space_before = q_space_before
        p_q.paragraph_format.space_after = q_space_after
        p_q.paragraph_format.line_spacing = q_line_spacing
        p_q.paragraph_format.keep_with_next = True

        run_q_title = p_q.add_run(f"Câu {idx}: ")
        run_q_title.bold = True
        run_q_title.font.name = 'Times New Roman'
        run_q_title.font.size = Pt(font_size_pt)
        run_q_title.font.color.rgb = RGBColor(30, 41, 59)

        add_block_content(doc, q_text, font_name='Times New Roman', font_size_pt=font_size_pt, first_p=p_q, line_spacing=q_line_spacing)

        # Xử lý các dạng câu hỏi
        if q_type == 'short_answer':
            p_ans = doc.add_paragraph()
            p_ans.paragraph_format.left_indent = Inches(0.25 if is_compact else 0.3)
            p_ans.paragraph_format.space_before = Pt(1 if is_compact else 3)
            p_ans.paragraph_format.space_after = Pt(2 if is_compact else 4)
            run_prompt = p_ans.add_run("Đáp số: ")
            run_prompt.bold = True
            run_prompt.font.name = 'Times New Roman'
            run_prompt.font.size = Pt(font_size_pt)
            if show_answers:
                run_ca = p_ans.add_run(f" {raw_ca or ''}")
                run_ca.bold = True
                run_ca.font.name = 'Times New Roman'
                run_ca.font.size = Pt(font_size_pt)
                run_ca.font.color.rgb = RGBColor(185, 28, 28)
            else:
                run_dots = p_ans.add_run("...................................................................................")
                run_dots.font.name = 'Times New Roman'
                run_dots.font.size = Pt(font_size_pt)

        elif q_type == 'true_false' or isinstance(raw_ca, dict):
            raw_ca_dict = normalize_tf_ca(raw_ca)
            for opt in options:
                p_opt = doc.add_paragraph()
                p_opt.paragraph_format.left_indent = Inches(0.25 if is_compact else 0.3)
                p_opt.paragraph_format.space_before = Pt(0)
                p_opt.paragraph_format.space_after = opt_space_after
                p_opt.paragraph_format.line_spacing = opt_line_spacing

                opt_clean = str(opt).strip()
                # Gỡ bỏ triệt để các đuôi [ Đúng / Sai ], [ Đúng / Sai ] - ĐÚNG / SAI, [Đ/S], [ĐÚNG], [SAI]
                opt_clean = re.sub(r'\s*\[\s*(?:Đúng|Đ)\s*[\/\\]\s*(?:Sai|S)\s*\](?:\s*[\-–—\:]\s*(?:ĐÚNG|SAI|Đ|S|True|False))?', '', opt_clean, flags=re.IGNORECASE)
                opt_clean = re.sub(r'\s*\[\s*(?:ĐÚNG|DUNG|SAI|Đ|S|TRUE|FALSE)\s*\]', '', opt_clean, flags=re.IGNORECASE)
                opt_clean = re.sub(r'(?:[\t\|]|[\-–—\:\;]\s*|\s{2,}|\s*-\s*|\s*:\s*)(?:ĐÚNG|SAI|Đ|S)\s*$', '', opt_clean, flags=re.IGNORECASE).strip()

                match_prefix = re.match(r'^(\*?\s*([a-dA-D]))([\.\:\)])\s*(.*)', opt_clean)
                sub_key = ""
                is_d = False
                if match_prefix:
                    sub_key = match_prefix.group(2).lower()
                    has_star = match_prefix.group(1).strip().startswith('*')
                    is_d = has_star or raw_ca_dict.get(sub_key, False)

                    label = match_prefix.group(2) + match_prefix.group(3) + " "
                    content = match_prefix.group(4)
                    run_label = p_opt.add_run(label)
                    run_label.bold = True
                    run_label.font.name = 'Times New Roman'
                    run_label.font.size = Pt(font_size_pt)
                    if show_answers and is_d:
                        run_label.underline = True
                        run_label.font.color.rgb = RGBColor(185, 28, 28)
                    add_formatted_text(p_opt, content, font_name='Times New Roman', font_size_pt=font_size_pt)
                else:
                    add_formatted_text(p_opt, opt_clean, font_name='Times New Roman', font_size_pt=font_size_pt)

# Thẻ [ Đúng / Sai ] đã được gỡ bỏ theo yêu cầu

        else:
            cols = determine_options_columns(options, options_layout)

            if cols in (2, 4) and len(options) in (2, 4):
                num_cols = cols
                num_rows = len(options) // num_cols
                col_width = Inches(available_width_inches / num_cols)
                table = create_borderless_table(doc, num_rows, num_cols, [col_width] * num_cols)

                for opt_idx, opt in enumerate(options):
                    r_idx = opt_idx // num_cols
                    c_idx = opt_idx % num_cols
                    cell = table.cell(r_idx, c_idx)
                    p_cell = cell.paragraphs[0]
                    p_cell.paragraph_format.space_before = Pt(0)
                    p_cell.paragraph_format.space_after = opt_space_after
                    p_cell.paragraph_format.line_spacing = opt_line_spacing

                    is_corr = is_option_correct(opt_idx, str(opt), raw_ca)
                    match_prefix = re.match(r'^(\*?\s*[A-Fa-f][\.\:\)])\s*(.*)', str(opt).strip())
                    if match_prefix:
                        label = match_prefix.group(1) + " "
                        content = match_prefix.group(2)
                        run_label = p_cell.add_run(label)
                        run_label.bold = True
                        run_label.font.name = 'Times New Roman'
                        run_label.font.size = Pt(font_size_pt)
                        if show_answers and is_corr:
                            run_label.underline = True
                            run_label.font.color.rgb = RGBColor(185, 28, 28)
                        add_formatted_text(p_cell, content, font_name='Times New Roman', font_size_pt=font_size_pt)
                    else:
                        add_formatted_text(p_cell, str(opt), font_name='Times New Roman', font_size_pt=font_size_pt)

            else:
                for opt_idx, opt in enumerate(options):
                    p_opt = doc.add_paragraph()
                    p_opt.paragraph_format.left_indent = Inches(0.25 if is_compact else 0.3)
                    p_opt.paragraph_format.space_before = Pt(0)
                    p_opt.paragraph_format.space_after = opt_space_after
                    p_opt.paragraph_format.line_spacing = opt_line_spacing

                    is_corr = is_option_correct(opt_idx, str(opt), raw_ca)
                    match_prefix = re.match(r'^(\*?\s*[A-Fa-f][\.\:\)])\s*(.*)', str(opt).strip())
                    if match_prefix:
                        label = match_prefix.group(1) + " "
                        content = match_prefix.group(2)
                        run_label = p_opt.add_run(label)
                        run_label.bold = True
                        run_label.font.name = 'Times New Roman'
                        run_label.font.size = Pt(font_size_pt)
                        if show_answers and is_corr:
                            run_label.underline = True
                            run_label.font.color.rgb = RGBColor(185, 28, 28)
                        add_formatted_text(p_opt, content, font_name='Times New Roman', font_size_pt=font_size_pt)
                    else:
                        add_formatted_text(p_opt, str(opt), font_name='Times New Roman', font_size_pt=font_size_pt)

    # 5. Bảng đáp án tổng hợp (Chỉ in khi show_key_table = True)
    if show_key_table and questions:
        if is_compact:
            p_div_key = doc.add_paragraph()
            p_div_key.paragraph_format.space_before = Pt(12)
            p_div_key.paragraph_format.space_after = Pt(4)
            p_div_key.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_dk = p_div_key.add_run("=" * 45)
            run_dk.bold = True
            run_dk.font.color.rgb = RGBColor(100, 116, 139)
        else:
            doc.add_page_break()

        p_key_title = doc.add_paragraph()
        p_key_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_key_title.paragraph_format.space_before = Pt(4)
        p_key_title.paragraph_format.space_after = Pt(6)
        key_suffix = f" (MÃ {exam_code})" if exam_code else ""
        run_key = p_key_title.add_run(f"--- BẢNG ĐÁP ÁN{key_suffix} ---")
        run_key.bold = True
        run_key.font.name = 'Times New Roman'
        run_key.font.size = Pt(12.5)
        run_key.font.color.rgb = RGBColor(22, 101, 52)

        cols = 10 if is_compact and len(questions) >= 10 else 5
        rows = (len(questions) + cols - 1) // cols
        table = doc.add_table(rows=rows * 2, cols=cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = 'Table Grid'

        for i, q in enumerate(questions):
            col_idx = i % cols
            row_idx = (i // cols) * 2

            cell_q = table.cell(row_idx, col_idx)
            cell_q.text = f"Câu {i+1}"
            p_cell_q = cell_q.paragraphs[0]
            p_cell_q.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if p_cell_q.runs:
                p_cell_q.runs[0].bold = True
                p_cell_q.runs[0].font.name = 'Times New Roman'
                p_cell_q.runs[0].font.size = Pt(9.5 if cols == 10 else 10)
            shading_q = parse_xml(r'<w:shd {} w:fill="F1F5F9"/>'.format(nsdecls('w')))
            cell_q._tc.get_or_add_tcPr().append(shading_q)

            correct_display = extract_answer_display(q)

            cell_ans = table.cell(row_idx + 1, col_idx)
            cell_ans.text = correct_display or "-"
            p_cell_ans = cell_ans.paragraphs[0]
            p_cell_ans.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if p_cell_ans.runs:
                p_cell_ans.runs[0].bold = True
                p_cell_ans.runs[0].font.name = 'Times New Roman'
                p_cell_ans.runs[0].font.size = Pt(10 if cols == 10 else 11)
                p_cell_ans.runs[0].font.color.rgb = RGBColor(220, 38, 38)

    # 6. Hướng dẫn giải chi tiết (Chỉ in khi show_explains = True)
    has_explains = any(q.get('explain') for q in questions)
    if show_explains and has_explains:
        p_exp_div = doc.add_paragraph()
        p_exp_div.paragraph_format.space_before = Pt(10)
        p_exp_div.paragraph_format.space_after = Pt(4)
        exp_suffix = f" (MÃ {exam_code})" if exam_code else ""
        run_exp_title = p_exp_div.add_run(f"HƯỚNG DẪN GIẢI CHI TIẾT{exp_suffix}:")
        run_exp_title.bold = True
        run_exp_title.font.name = 'Times New Roman'
        run_exp_title.font.size = Pt(11.5)
        run_exp_title.font.color.rgb = RGBColor(30, 41, 59)

        for idx, q in enumerate(questions, 1):
            exp = q.get('explain', '')
            if exp:
                p_exp = doc.add_paragraph()
                p_exp.paragraph_format.space_before = Pt(2 if is_compact else 4)
                p_exp.paragraph_format.space_after = Pt(2 if is_compact else 3)
                p_exp.paragraph_format.line_spacing = opt_line_spacing

                run_exp_q = p_exp.add_run(f"Câu {idx}: ")
                run_exp_q.bold = True
                run_exp_q.font.name = 'Times New Roman'
                run_exp_q.font.size = Pt(font_size_pt)
                run_exp_q.font.color.rgb = RGBColor(79, 70, 229)

                add_block_content(doc, exp, font_name='Times New Roman', font_size_pt=font_size_pt, first_p=p_exp, line_spacing=opt_line_spacing)


def export_quiz_to_docx(
    title: str,
    questions: Optional[list] = None,
    time_limit: int = 0,
    target_audience: str = "teacher",
    layout_mode: str = "compact",
    options_layout: str = "auto",
    show_answers: Optional[bool] = None,
    show_key_table: Optional[bool] = None,
    show_explains: Optional[bool] = None,
    include_student_answer_grid: bool = False,
    exam_code: Optional[str] = None,
    school_name: Optional[str] = None,
    show_candidate_info: bool = True
) -> io.BytesIO:
    """Xuất đề thi đơn lẻ ra định dạng Word (.docx). Hoàn toàn tương thích ngược với mọi code cũ."""
    if isinstance(title, dict):
        quiz_data = title
        if isinstance(questions, dict):
            config = questions
            if show_answers is None and 'show_answers' in config:
                show_answers = config['show_answers']
            if show_key_table is None and 'show_key_table' in config:
                show_key_table = config['show_key_table']
            if show_explains is None and 'show_explains' in config:
                show_explains = config['show_explains']
            if 'target_audience' in config:
                target_audience = config['target_audience']
            if 'layout_mode' in config:
                layout_mode = config['layout_mode']
            if 'options_layout' in config:
                options_layout = config['options_layout']
            if 'school_name' in config:
                school_name = config['school_name']
            if 'exam_code' in config:
                exam_code = config['exam_code']
        title = quiz_data.get('title', 'Đề thi trắc nghiệm')
        questions = quiz_data.get('data') or quiz_data.get('questions') or []
        time_limit = quiz_data.get('time_limit', 0)
    elif questions is None:
        questions = []

    doc = Document()
    is_compact = (layout_mode == "compact")

    # Cấu hình lề trang (Margins)
    for section in doc.sections:
        if is_compact:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.55)
            section.right_margin = Inches(0.55)
        else:
            section.top_margin = Inches(0.75)
            section.bottom_margin = Inches(0.75)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)

    if show_answers is None:
        show_answers = (target_audience != "student")
    if show_key_table is None:
        show_key_table = (target_audience != "student")
    if show_explains is None:
        show_explains = (target_audience != "student")

    render_quiz_document_content(
        doc=doc,
        title=title,
        questions=questions,
        time_limit=time_limit,
        target_audience=target_audience,
        layout_mode=layout_mode,
        options_layout=options_layout,
        show_answers=show_answers,
        show_key_table=show_key_table,
        show_explains=show_explains,
        include_student_answer_grid=include_student_answer_grid,
        exam_code=exam_code,
        school_name=school_name,
        show_candidate_info=show_candidate_info
    )

    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream


def export_multi_quizzes_to_docx(
    sub_quizzes: list,
    master_title: str = "Đề thi trắc nghiệm",
    school_name: str = "SỞ GIÁO DỤC VÀ ĐÀO TẠO",
    time_limit: int = 0,
    target_audience: str = "teacher",
    layout_mode: str = "compact",
    options_layout: str = "auto",
    show_answers: Optional[bool] = None,
    show_key_table: Optional[bool] = None,
    show_explains: Optional[bool] = None,
    include_student_answer_grid: bool = False,
    include_answer_matrix: bool = True,
    show_candidate_info: bool = True
) -> io.BytesIO:
    """Xuất trọn bộ nhiều đề con (các mã đề thi khác nhau) gộp chung vào 1 file Word duy nhất, ngăn cách bởi Page Break và kèm Ma trận đáp án ở cuối."""
    doc = Document()
    is_compact = (layout_mode == "compact")

    for section in doc.sections:
        if is_compact:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.55)
            section.right_margin = Inches(0.55)
        else:
            section.top_margin = Inches(0.75)
            section.bottom_margin = Inches(0.75)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)

    if show_answers is None:
        show_answers = (target_audience != "student")
    if show_key_table is None:
        show_key_table = (target_audience != "student")
    if show_explains is None:
        show_explains = (target_audience != "student")

    # 1. Kết xuất từng đề con
    for idx, sq in enumerate(sub_quizzes):
        if idx > 0:
            doc.add_page_break()
        code = str(sq.get('exam_code') or f"10{idx+1}")
        sub_title = sq.get('title') or master_title
        sub_q = sq.get('questions') or []
        render_quiz_document_content(
            doc=doc,
            title=sub_title,
            questions=sub_q,
            time_limit=time_limit,
            target_audience=target_audience,
            layout_mode=layout_mode,
            options_layout=options_layout,
            show_answers=show_answers,
            show_key_table=show_key_table,
            show_explains=show_explains,
            include_student_answer_grid=include_student_answer_grid,
            exam_code=code,
            school_name=school_name,
            show_candidate_info=show_candidate_info
        )

    # 2. Bảng Ma trận đáp án các mã đề (Master Answer Key Matrix)
    if include_answer_matrix and sub_quizzes:
        doc.add_page_break()

        p_m_title = doc.add_paragraph()
        p_m_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_m_title.paragraph_format.space_before = Pt(6)
        p_m_title.paragraph_format.space_after = Pt(2)
        run_mt = p_m_title.add_run("BẢNG MA TRẬN ĐÁP ÁN CÁC MÃ ĐỀ")
        run_mt.bold = True
        run_mt.font.name = 'Times New Roman'
        run_mt.font.size = Pt(14)
        run_mt.font.color.rgb = RGBColor(22, 101, 52)

        codes_str = ", ".join(str(sq.get('exam_code') or f"10{i+1}") for i, sq in enumerate(sub_quizzes))
        p_m_sub = doc.add_paragraph()
        p_m_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_m_sub.paragraph_format.space_before = Pt(0)
        p_m_sub.paragraph_format.space_after = Pt(8)
        run_ms = p_m_sub.add_run(f"Đề bài: {master_title.upper()} | Mã đề: {codes_str}")
        run_ms.italic = True
        run_ms.font.name = 'Times New Roman'
        run_ms.font.size = Pt(10.5)

        max_q = max((len(sq.get('questions') or []) for sq in sub_quizzes), default=0)
        num_cols = 1 + len(sub_quizzes)
        num_rows = 1 + max_q

        tbl = doc.add_table(rows=num_rows, cols=num_cols)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.style = 'Table Grid'

        for row in tbl.rows:
            trPr = row._tr.get_or_add_trPr()
            trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))

        # Dòng tiêu đề cột (Header Row)
        hdr_c0 = tbl.cell(0, 0)
        hdr_c0.text = "Câu hỏi"
        p_h0 = hdr_c0.paragraphs[0]
        p_h0.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if p_h0.runs:
            p_h0.runs[0].bold = True
            p_h0.runs[0].font.name = 'Times New Roman'
            p_h0.runs[0].font.size = Pt(10.5)
        shd0 = parse_xml(f'<w:shd {nsdecls("w")} w:fill="E2E8F0"/>')
        hdr_c0._tc.get_or_add_tcPr().append(shd0)

        for j, sq in enumerate(sub_quizzes):
            code_j = str(sq.get('exam_code') or f"10{j+1}")
            hdr_cj = tbl.cell(0, j + 1)
            hdr_cj.text = f"Mã {code_j}"
            p_hj = hdr_cj.paragraphs[0]
            p_hj.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if p_hj.runs:
                p_hj.runs[0].bold = True
                p_hj.runs[0].font.name = 'Times New Roman'
                p_hj.runs[0].font.size = Pt(10.5)
                p_hj.runs[0].font.color.rgb = RGBColor(30, 58, 138)
            shdj = parse_xml(f'<w:shd {nsdecls("w")} w:fill="E2E8F0"/>')
            hdr_cj._tc.get_or_add_tcPr().append(shdj)

        # Dòng dữ liệu cho từng câu hỏi 1..max_q
        for i in range(max_q):
            row_idx = i + 1
            # Cột 0: Tên câu
            c_qnum = tbl.cell(row_idx, 0)
            c_qnum.text = f"Câu {i + 1}"
            p_qn = c_qnum.paragraphs[0]
            p_qn.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_qn.paragraph_format.space_before = Pt(1)
            p_qn.paragraph_format.space_after = Pt(1)
            if p_qn.runs:
                p_qn.runs[0].bold = True
                p_qn.runs[0].font.name = 'Times New Roman'
                p_qn.runs[0].font.size = Pt(9.5)
            shd_q = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F8FAFC"/>')
            c_qnum._tc.get_or_add_tcPr().append(shd_q)

            # Cột j + 1: Đáp án tương ứng của mã đề j
            for j, sq in enumerate(sub_quizzes):
                q_list = sq.get('questions') or []
                c_ans = tbl.cell(row_idx, j + 1)
                ans_str = "-"
                if i < len(q_list):
                    ans_str = extract_answer_display(q_list[i])
                c_ans.text = ans_str
                p_an = c_ans.paragraphs[0]
                p_an.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_an.paragraph_format.space_before = Pt(1)
                p_an.paragraph_format.space_after = Pt(1)
                if p_an.runs:
                    p_an.runs[0].bold = True
                    p_an.runs[0].font.name = 'Times New Roman'
                    p_an.runs[0].font.size = Pt(10.5)
                    p_an.runs[0].font.color.rgb = RGBColor(185, 28, 28)

    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream
