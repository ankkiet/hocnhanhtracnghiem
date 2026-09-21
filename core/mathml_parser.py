import re

# Bộ từ điển chuyển đổi ký tự Unicode Toán/Hóa học sang LaTeX
MATH_SYM_MAP = {
    'π': '\\pi ', 'α': '\\alpha ', 'β': '\\beta ', 'γ': '\\gamma ', 'Δ': '\\Delta ', 
    'δ': '\\delta ', 'θ': '\\theta ', 'λ': '\\lambda ', 'μ': '\\mu ', 'ρ': '\\rho ',
    'Σ': '\\Sigma ', 'Ω': '\\Omega ', 'ω': '\\omega ', '∞': '\\infty ', '→': '\\rightarrow ', 
    '⟶': '\\longrightarrow ', '⇌': '\\rightleftharpoons ',
    '⇒': '\\Rightarrow ', '⇔': '\\Leftrightarrow ', '≠': '\\neq ', '≈': '\\approx ',
    '≤': '\\leq ', '≥': '\\geq ', '±': '\\pm ', '×': '\\times ', '÷': '\\div ',
    '∫': '\\int ', '∑': '\\sum ', '°': '^\\circ ', '∈': '\\in ', '∉': '\\notin ',
    '⊂': '\\subset ', '∅': '\\emptyset ', '∩': '\\cap ', '∪': '\\cup '
}

def parse_omath(node):
    """Trình dịch thuật cục bộ Office MathML sang mã LaTeX chuẩn."""
    if node is None:
        return ""
    tag = node.tag.split('}')[-1] if '}' in node.tag else node.tag
    
    if tag == 'f':  # Phân số
        num = node.xpath('./*[local-name()="num"]')
        den = node.xpath('./*[local-name()="den"]')
        return f"\\frac{{{parse_omath(num[0]) if num else ''}}}{{{parse_omath(den[0]) if den else ''}}}"
    elif tag == 'sSup':  # Mũ / Lũy thừa
        e = node.xpath('./*[local-name()="e"]')
        sup = node.xpath('./*[local-name()="sup"]')
        return f"{{{parse_omath(e[0]) if e else ''}}}^{{{parse_omath(sup[0]) if sup else ''}}}"
    elif tag == 'sSub':  # Chỉ số dưới (Hóa học: H2O, CO2)
        e = node.xpath('./*[local-name()="e"]')
        sub = node.xpath('./*[local-name()="sub"]')
        return f"{{{parse_omath(e[0]) if e else ''}}}_{{{parse_omath(sub[0]) if sub else ''}}}"
    elif tag == 'sSubSup':  # Tích hợp cả mũ và chỉ số dưới
        e = node.xpath('./*[local-name()="e"]')
        sub = node.xpath('./*[local-name()="sub"]')
        sup = node.xpath('./*[local-name()="sup"]')
        return f"{{{parse_omath(e[0]) if e else ''}}}_{{{parse_omath(sub[0]) if sub else ''}}}^{{{parse_omath(sup[0]) if sup else ''}}}"
    elif tag == 'rad':  # Căn bậc 2, Căn bậc n
        deg = node.xpath('./*[local-name()="deg"]')
        e = node.xpath('./*[local-name()="e"]')
        if deg and deg[0].xpath('.//*[local-name()="t"]'):
            return f"\\sqrt[{parse_omath(deg[0])}]{{{parse_omath(e[0]) if e else ''}}}"
        return f"\\sqrt{{{parse_omath(e[0]) if e else ''}}}"
    elif tag == 'nary':  # Tích phân, Tổng Sigma, Tích Pi
        naryPr = node.xpath('./*[local-name()="naryPr"]')
        chr_val = "\\int "
        if naryPr:
            chr_el = naryPr[0].xpath('./*[local-name()="chr"]')
            if chr_el:
                c = chr_el[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', '∫')
                if c == '∑': chr_val = "\\sum "
                elif c == '∏': chr_val = "\\prod "
        sub = node.xpath('./*[local-name()="sub"]')
        sup = node.xpath('./*[local-name()="sup"]')
        e = node.xpath('./*[local-name()="e"]')
        sub_str = f"_{{{parse_omath(sub[0])}}}" if sub and sub[0].xpath('.//*[local-name()="t"]') else ""
        sup_str = f"^{{{parse_omath(sup[0])}}}" if sup and sup[0].xpath('.//*[local-name()="t"]') else ""
        return f"{chr_val}{sub_str}{sup_str} {{{parse_omath(e[0]) if e else ''}}}"
    elif tag == 'limLow':  # Giới hạn lim hoặc Mũi tên có chữ ở dưới
        e = node.xpath('./*[local-name()="e"]')
        lim = node.xpath('./*[local-name()="lim"]')
        e_text = parse_omath(e[0]) if e else ""
        lim_text = parse_omath(lim[0]) if lim else ""
        
        if 'rightarrow' in e_text or '→' in e_text:
            return f"\\xrightarrow[{lim_text}]{{}}"
        elif 'leftarrow' in e_text or '←' in e_text:
            return f"\\xleftarrow[{lim_text}]{{}}"
        elif 'rightleftharpoons' in e_text or '⇌' in e_text:
            return f"\\xrightleftharpoons[{lim_text}]{{}}"
        elif e_text.strip() == 'lim':
            return f"\\lim_{{{lim_text}}}"
        else:
            return f"\\underset{{{lim_text}}}{{{e_text}}}"
    elif tag == 'limUpp':  # Mũi tên có chữ ở trên
        e = node.xpath('./*[local-name()="e"]')
        lim = node.xpath('./*[local-name()="lim"]')
        e_text = parse_omath(e[0]) if e else ""
        lim_text = parse_omath(lim[0]) if lim else ""
        
        if 'rightarrow' in e_text or '→' in e_text:
            return f"\\xrightarrow{{{lim_text}}}"
        elif 'leftarrow' in e_text or '←' in e_text:
            return f"\\xleftarrow{{{lim_text}}}"
        elif 'rightleftharpoons' in e_text or '⇌' in e_text:
            return f"\\xrightleftharpoons{{{lim_text}}}"
        else:
            return f"\\overset{{{lim_text}}}{{{e_text}}}"
    elif tag == 'groupChr':  # Ký tự nhóm
        groupChrPr = node.xpath('./*[local-name()="groupChrPr"]')
        chr_val = ""
        pos = "bot"
        if groupChrPr:
            chr_el = groupChrPr[0].xpath('./*[local-name()="chr"]')
            if chr_el:
                chr_val = chr_el[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', '')
            pos_el = groupChrPr[0].xpath('./*[local-name()="pos"]')
            if pos_el:
                pos = pos_el[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', 'bot')
                
        e = node.xpath('./*[local-name()="e"]')
        e_text = parse_omath(e[0]) if e else ""
        
        if chr_val in ['→', '⟶', '\\rightarrow']:
            return f"\\xrightarrow{{{e_text}}}" if pos == 'bot' else f"\\xrightarrow[{e_text}]{{}}"
        elif chr_val in ['←', '⟵', '\\leftarrow']:
            return f"\\xleftarrow{{{e_text}}}" if pos == 'bot' else f"\\xleftarrow[{e_text}]{{}}"
        elif chr_val in ['⇌', '\\rightleftharpoons']:
            return f"\\xrightleftharpoons{{{e_text}}}" if pos == 'bot' else f"\\xrightleftharpoons[{e_text}]{{}}"
        elif chr_val == '︷':
            return f"\\overbrace{{{e_text}}}"
        elif chr_val == '︸':
            return f"\\underbrace{{{e_text}}}"
        else:
            return f"\\underset{{{chr_val}}}{{{e_text}}}" if pos == 'bot' else f"\\overset{{{chr_val}}}{{{e_text}}}"
    elif tag == 'undOvr':  # Mũi tên có chữ cả trên lẫn dưới
        e = node.xpath('./*[local-name()="e"]')
        und = node.xpath('./*[local-name()="und"]')
        ovr = node.xpath('./*[local-name()="ovr"]')
        e_text = parse_omath(e[0]) if e else ""
        und_text = parse_omath(und[0]) if und else ""
        ovr_text = parse_omath(ovr[0]) if ovr else ""
        
        if 'rightarrow' in e_text or '→' in e_text:
            return f"\\xrightarrow[{und_text}]{{{ovr_text}}}"
        elif 'leftarrow' in e_text or '←' in e_text:
            return f"\\xleftarrow[{und_text}]{{{ovr_text}}}"
        elif 'rightleftharpoons' in e_text or '⇌' in e_text:
            return f"\\xrightleftharpoons[{und_text}]{{{ovr_text}}}"
        else:
            return f"\\munderover{{{e_text}}}{{{und_text}}}{{{ovr_text}}}"
    elif tag == 'm':  # Ma trận / Bảng
        mr_nodes = node.xpath('./*[local-name()="mr"]')
        rows = []
        for mr in mr_nodes:
            e_nodes = mr.xpath('./*[local-name()="e"]')
            cols = [parse_omath(e_node) for e_node in e_nodes]
            rows.append(" & ".join(cols))
        joined_rows = " \\\\ ".join(rows)
        return f"\\begin{{matrix}} {joined_rows} \\end{{matrix}}"
    elif tag == 'd':  # Dấu ngoặc
        dPr = node.xpath('./*[local-name()="dPr"]')
        begChr, endChr = "(", ")"
        if dPr:
            beg_el = dPr[0].xpath('./*[local-name()="begChr"]')
            end_el = dPr[0].xpath('./*[local-name()="endChr"]')
            if beg_el: begChr = beg_el[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', '(')
            if end_el: endChr = end_el[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', ')')
        
        e = node.xpath('./*[local-name()="e"]')
        inner = "".join(parse_omath(c) for c in e)
        
        if begChr == '{' and endChr == '':
            if '\\begin{matrix}' in inner:
                return inner.replace('\\begin{matrix}', '\\begin{cases}').replace('\\end{matrix}', '\\end{cases}')
        
        left_delim = "\\left\\{" if begChr == "{" else (f"\\left{begChr}" if begChr else "")
        right_delim = "\\right\\}" if endChr == "}" else ("\\right." if endChr == "" else f"\\right{endChr}")
        return f"{left_delim} {inner} {right_delim}"
    elif tag == 'acc':  # Vector, Mũ
        accPr = node.xpath('./*[local-name()="accPr"]')
        chr_val = ""
        if accPr:
            chr_el = accPr[0].xpath('./*[local-name()="chr"]')
            if chr_el:
                c = chr_el[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', '')
                if c in ['⃗', '→']: chr_val = "\\vec"
                elif c == '̂': chr_val = "\\hat"
                elif c == '̅': chr_val = "\\overline"
        e = node.xpath('./*[local-name()="e"]')
        return f"{chr_val}{{{parse_omath(e[0]) if e else ''}}}" if chr_val else (parse_omath(e[0]) if e else "")
    elif tag == 't':  # Text và Ký tự đặc biệt
        text = node.text or ""
        for k, v in MATH_SYM_MAP.items():
            text = text.replace(k, v)
        return text
    
    res = ""
    for child in node:
        res += parse_omath(child)
    return res
