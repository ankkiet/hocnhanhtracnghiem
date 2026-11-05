# -*- coding: utf-8 -*-
"""
Kiểm thử định dạng câu hỏi Đúng/Sai và làm sạch HTML khi xuất file Word (.docx).
- Đáp án Đúng: Bôi đỏ (RGB: 185, 28, 28) và gạch chân (underline = True).
- Đáp án Sai: Để nguyên (không gạch chân, không bôi đỏ).
- Gỡ bỏ hoàn toàn thẻ thừa [ Đúng / Sai ] hoặc [ Đ / S ].
- Không xuất hiện thẻ HTML lỗi (như </B>, <B>) trong tiêu đề phần hay nội dung câu hỏi.
"""

import io
import re
import pytest
from docx import Document
from docx.shared import RGBColor
from core.docx_exporter import export_quiz_to_docx


def test_docx_true_false_answer_styling_and_clean_tags():
    sample_quiz = {
        'title': 'Đề kiểm tra Hóa học 12 GDPT 2018',
        'subject': 'Hóa học',
        'grade': '12',
        'time_limit': 45,
        'questions': [
            {
                'group_title': 'PHẦN II. TRẮC NGHIỆM ĐÚNG SAI</B>',
                'type': 'true_false',
                'question': 'Tiến hành các thí nghiệm theo các bước sau:',
                'options': [
                    'a) Sau bước 2: Chất lỏng trong cả hai ống nghiệm đều phân thành hai lớp. [ Đúng / Sai ]',
                    'b) Sau bước 3: Ở hai ống nghiệm đều thu được sản phẩm giống nhau. [ Đúng / Sai ]',
                    'c) Sau bước 3: Ống nghiệm (1) thể tích lớp chất lỏng phía trên giảm. [ Đúng / Sai ]',
                    'd) Phản ứng thuỷ phân ester trong môi trường acid xảy ra tốt hơn. [ Đúng / Sai ]'
                ],
                'correct_answer': {
                    'a': True,
                    'b': False,
                    'c': True,
                    'd': False
                }
            }
        ]
    }

    # 1. Xuất file với show_answers = True (Bản giáo viên)
    stream_teacher = export_quiz_to_docx(sample_quiz, {'show_answers': True})
    doc_teacher = Document(stream_teacher)

    paragraphs_text = [p.text for p in doc_teacher.paragraphs]
    full_text = "\n".join(paragraphs_text)

    # Kiểm tra 1: Không có thẻ rác </B> trong tiêu đề phần
    assert '</B>' not in full_text, "Không được xuất hiện thẻ đóng HTML lỗi </B> trong tài liệu docx!"
    assert '<B>' not in full_text, "Không được xuất hiện thẻ HTML <B> trong tài liệu docx!"
    assert 'PHẦN II. TRẮC NGHIỆM ĐÚNG SAI' in full_text

    # Kiểm tra 2: Không còn thẻ [ Đúng / Sai ] hoặc [ Đ / S ]
    assert not re.search(r'\[\s*Đúng\s*[\/\\]\s*Sai\s*\]', full_text, re.IGNORECASE), \
        "Tất cả các thẻ [ Đúng / Sai ] phải được tự động lọc sạch!"
    assert not re.search(r'\[\s*Đ\s*[\/\\]\s*S\s*\]', full_text, re.IGNORECASE), \
        "Tất cả các thẻ [ Đ / S ] phải được tự động lọc sạch!"

    # Kiểm tra 3: Xác minh chi tiết thuộc tính từng đáp án Đúng/Sai
    # a: Đúng -> đỏ + gạch chân
    # b: Sai  -> không đỏ, không gạch chân
    # c: Đúng -> đỏ + gạch chân
    # d: Sai  -> không đỏ, không gạch chân
    verified_options = {}
    for p in doc_teacher.paragraphs:
        txt = p.text.strip()
        match = re.match(r'^([a-d])\)\s*', txt)
        if match:
            opt_key = match.group(1)
            # Kiểm tra run nhãn a), b), c), d)
            first_run = p.runs[0] if p.runs else None
            is_underlined = getattr(first_run, 'underline', False) is True
            color_rgb = None
            if first_run and first_run.font and first_run.font.color and first_run.font.color.rgb:
                color_rgb = first_run.font.color.rgb

            verified_options[opt_key] = {
                'underlined': is_underlined,
                'color_rgb': color_rgb,
                'full_text': txt
            }

    # Đáp án a (Đúng)
    assert 'a' in verified_options, "Phải tìm thấy ý a)"
    assert verified_options['a']['underlined'] is True, "Đáp án ĐÚNG (ý a) phải được gạch chân"
    assert verified_options['a']['color_rgb'] == RGBColor(185, 28, 28), "Đáp án ĐÚNG (ý a) phải bôi màu đỏ"

    # Đáp án b (Sai)
    assert 'b' in verified_options, "Phải tìm thấy ý b)"
    assert verified_options['b']['underlined'] is False, "Đáp án SAI (ý b) KHÔNG được gạch chân"
    assert verified_options['b']['color_rgb'] != RGBColor(185, 28, 28), "Đáp án SAI (ý b) KHÔNG được bôi đỏ"

    # Đáp án c (Đúng)
    assert 'c' in verified_options, "Phải tìm thấy ý c)"
    assert verified_options['c']['underlined'] is True, "Đáp án ĐÚNG (ý c) phải được gạch chân"
    assert verified_options['c']['color_rgb'] == RGBColor(185, 28, 28), "Đáp án ĐÚNG (ý c) phải bôi màu đỏ"

    # Đáp án d (Sai)
    assert 'd' in verified_options, "Phải tìm thấy ý d)"
    assert verified_options['d']['underlined'] is False, "Đáp án SAI (ý d) KHÔNG được gạch chân"
    assert verified_options['d']['color_rgb'] != RGBColor(185, 28, 28), "Đáp án SAI (ý d) KHÔNG được bôi đỏ"


def test_docx_student_view_has_no_answer_highlights():
    # 2. Xuất file với show_answers = False (Bản học sinh)
    sample_quiz = {
        'title': 'Đề kiểm tra Hóa học 12',
        'subject': 'Hóa học',
        'questions': [
            {
                'type': 'true_false',
                'question': 'Thí nghiệm este:',
                'options': [
                    'a) Nhận định 1 [ Đúng / Sai ]',
                    'b) Nhận định 2 [ Đúng / Sai ]'
                ],
                'correct_answer': {'a': True, 'b': False}
            }
        ]
    }
    stream_student = export_quiz_to_docx(sample_quiz, {'show_answers': False})
    doc_student = Document(stream_student)

    for p in doc_student.paragraphs:
        txt = p.text.strip()
        match = re.match(r'^([a-b])\)\s*', txt)
        if match:
            first_run = p.runs[0]
            # Bản học sinh không được gạch chân và không được bôi đỏ
            assert getattr(first_run, 'underline', False) is not True
            if first_run.font and first_run.font.color and first_run.font.color.rgb:
                assert first_run.font.color.rgb != RGBColor(185, 28, 28)
            # Và không còn thẻ [ Đúng / Sai ]
            assert '[ Đúng / Sai ]' not in txt


def test_docx_richtext_and_image_scaling():
    sample_quiz = {
        'title': 'Đề kiểm tra Định dạng Word',
        'questions': [
            {
                'type': 'mcq',
                'question': 'Câu hỏi có chữ <b>in đậm</b>, <i>in nghiêng</i>, <u>gạch chân</u>, <s>gạch ngang</s>, <sub>H2O</sub>, <sup>x2</sup> và <span style="color: #dc2626;">màu đỏ</span>.',
                'options': [
                    'A. Phương án 1',
                    'B. Phương án 2'
                ],
                'correct_answer': 'A'
            }
        ]
    }
    stream = export_quiz_to_docx(sample_quiz)
    doc = Document(stream)
    
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert 'in đậm' in full_text
    assert 'in nghiêng' in full_text
    assert 'gạch chân' in full_text
    assert 'gạch ngang' in full_text
    assert 'H2O' in full_text
    assert 'x2' in full_text
    assert 'màu đỏ' in full_text

    # Check run attributes in question paragraph
    found_strike = False
    found_color = False
    for p in doc.paragraphs:
        for r in p.runs:
            if 'gạch ngang' in r.text and getattr(r.font, 'strike', False):
                found_strike = True
            if 'màu đỏ' in r.text and r.font.color and r.font.color.rgb == RGBColor(220, 38, 38):
                found_color = True

    assert found_strike, "Thẻ <s>gạch ngang</s> phải được chuyển thành run.font.strike = True"
    assert found_color, "Thẻ <span style='color: #dc2626;'>màu đỏ</span> phải được chuyển thành RGBColor(220, 38, 38)"
def test_docx_options_with_trailing_dung_sai_tags():
    """Kiểm tra bóc tách và xóa sạch thẻ [ Đúng / Sai ] - ĐÚNG / SAI trong options"""
    sample_quiz = {
        'title': 'Đề kiểm tra Hóa học có gắn nhãn ĐÚNG SAI',
        'questions': [
            {
                'group_title': 'PHẦN II. TRẮC NGHIỆM ĐÚNG SAI</B>',
                'type': 'true_false',
                'question': 'Tiến hành các thí nghiệm theo các bước sau:',
                'options': [
                    'a) Sau bước 2: Phân thành hai lớp. [ Đúng / Sai ] - ĐÚNG',
                    'b) Sau bước 3: Thu được sản phẩm giống nhau. [ Đúng / Sai ] - SAI',
                    'c) Sau bước 3: Thể tích lớp chất lỏng giảm. [ Đúng / Sai ] - ĐÚNG',
                    'd) Phản ứng thuỷ phân xảy ra tốt hơn. [ Đúng / Sai ] - SAI'
                ],
                'correct_answer': {'a': True, 'b': False, 'c': True, 'd': False}
            }
        ]
    }
    stream = export_quiz_to_docx(sample_quiz, {'show_answers': True})
    doc = Document(stream)
    full_text = '\n'.join(p.text for p in doc.paragraphs)
    assert '</B>' not in full_text
    assert '[ Đúng / Sai ]' not in full_text
    assert '[ Đúng / Sai ] - ĐÚNG' not in full_text
    assert '[ Đúng / Sai ] - SAI' not in full_text
    assert ' - ĐÚNG' not in full_text
    assert ' - SAI' not in full_text
