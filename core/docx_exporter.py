import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def export_quiz_to_docx(title: str, questions: list, time_limit: int = 0) -> io.BytesIO:
    """Tạo file Word (.docx) chuẩn format đề thi in ấn cho Giáo viên."""
    doc = Document()
    
    # Thiết lập lề trang
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        
    # Tiêu đề đề thi
    p_header = doc.add_paragraph()
    p_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_header = p_header.add_run(f"ĐỀ KIỂM TRA TRẮC NGHIỆM: {title.upper()}")
    run_header.bold = True
    run_header.font.size = Pt(15)
    run_header.font.color.rgb = RGBColor(26, 86, 219)
    
    # Thông tin thời gian và học sinh
    time_str = f"Thời gian làm bài: {time_limit} phút" if time_limit > 0 else "Thời gian làm bài: Tự do"
    p_info = doc.add_paragraph()
    p_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_info.add_run(f"{time_str} | Tổng số câu: {len(questions)} câu\n").italic = True
    p_info.add_run("Họ và tên thí sinh: .............................................................. Lớp: .........................").bold = True
    
    doc.add_paragraph("-" * 55).alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Danh sách câu hỏi
    for idx, q in enumerate(questions, 1):
        q_text = q.get('question', '')
        options = q.get('options', [])
        
        # Tiêu đề câu hỏi
        p_q = doc.add_paragraph()
        run_q_title = p_q.add_run(f"Câu {idx}: ")
        run_q_title.bold = True
        run_q_title.font.color.rgb = RGBColor(30, 41, 59)
        p_q.add_run(q_text)
        
        # Các lựa chọn A, B, C, D
        for opt in options:
            p_opt = doc.add_paragraph()
            p_opt.paragraph_format.left_indent = Inches(0.3)
            p_opt.paragraph_format.space_after = Pt(2)
            p_opt.add_run(opt)
            
        doc.add_paragraph().paragraph_format.space_after = Pt(4)
        
    # Trang Bảng Đáp án (Answer Key)
    doc.add_page_break()
    p_key_title = doc.add_paragraph()
    p_key_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_key = p_key_title.add_run("--- BẢNG ĐÁP ÁN & HƯỚNG DẪN GIẢI ---")
    run_key.bold = True
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
            cell_q.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            cell_q.paragraphs[0].runs[0].bold = True
            shading_q = parse_xml(r'<w:shd {} w:fill="F1F5F9"/>'.format(nsdecls('w')))
            cell_q._tc.get_or_add_tcPr().append(shading_q)
            
            # Ô đáp án đúng (lấy chữ cái A, B, C, D đầu tiên)
            correct = q.get('correct_answer', '')
            correct_letter = ""
            for c in ["A", "B", "C", "D"]:
                if correct.strip().startswith(f"{c}.") or correct.strip().startswith(f"{c}:") or correct.strip() == c:
                    correct_letter = c
                    break
            if not correct_letter and correct:
                correct_letter = correct[:2]
                
            cell_ans = table.cell(row_idx + 1, col_idx)
            cell_ans.text = correct_letter or "-"
            cell_ans.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            if cell_ans.paragraphs[0].runs:
                cell_ans.paragraphs[0].runs[0].bold = True
                cell_ans.paragraphs[0].runs[0].font.color.rgb = RGBColor(220, 38, 38)
                
    # Thêm phần giải thích chi tiết nếu có
    has_explains = any(q.get('explain') for q in questions)
    if has_explains:
        doc.add_paragraph().paragraph_format.space_after = Pt(10)
        p_exp_title = doc.add_paragraph()
        p_exp_title.add_run("Chi tiết lời giải:").bold = True
        for idx, q in enumerate(questions, 1):
            exp = q.get('explain', '')
            if exp:
                p_exp = doc.add_paragraph()
                p_exp.add_run(f"Câu {idx}: ").bold = True
                p_exp.add_run(exp)
                
    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream
