import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import latex2mathml.converter
from lxml import etree
from docx import Document
from docx.oxml import parse_xml

class TestDocxMath(unittest.TestCase):
    def setUp(self):
        self.xsl_path = os.path.join(os.path.dirname(__file__), '..', 'core', 'MML2OMML.XSL')
        self.assertTrue(os.path.exists(self.xsl_path), "MML2OMML.XSL must exist")
        self.xslt = etree.XSLT(etree.parse(self.xsl_path))

    def test_omath_para(self):
        doc = Document()
        p = doc.add_paragraph('Test oMathPara: ')
        xml_str = '<m:oMathPara xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:oMath><m:r><m:t>x = 1</m:t></m:r></m:oMath></m:oMathPara>'
        elem = parse_xml(xml_str.encode('utf-8'))
        p._p.append(elem)
        doc.save('test_omathpara.docx')
        self.assertTrue(os.path.exists('test_omathpara.docx'))
        os.remove('test_omathpara.docx')

    def test_latex_samples(self):
        samples = [
            r"f'(x)",
            r"y'",
            r"y''",
            r"(P): 2x - y + z - 1 = 0",
            r"d: \frac{x-1}{2} = \frac{y+2}{-1} = \frac{z}{3}",
            r"V = \frac{1}{3}Bh",
            r"\Delta ABC",
            r"\perp",
            r"\parallel",
            r"\angle A",
            r"\widehat{ABC}",
            r"\begin{aligned} x &= 1 \\ y &= 2 \end{aligned}",
            r"\begin{cases} x = 1 \\ y = 2 \end{cases}",
        ]
        parser = etree.XMLParser(recover=True)
        import re
        for s in samples:
            m = latex2mathml.converter.convert(s)
            m_fixed = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#x?[0-9a-fA-F]+);)', '&amp;', m)
            dom = etree.fromstring(m_fixed.encode('utf-8'), parser=parser)
            new_dom = self.xslt(dom)
            omml = etree.tostring(new_dom, encoding='utf-8')
            elem = parse_xml(omml)
            self.assertIsNotNone(elem)

    def test_export_quiz_to_docx(self):
        from core.docx_exporter import export_quiz_to_docx
        questions = [
            {
                "group_title": "PHẦN I: CÂU HỎI TRẮC NGHIỆM ĐẠI SỐ",
                "question": r"Cho hàm số \(y = \frac{x^2 - 3x + 2}{x - 1}\). Tìm tiệm cận xiên và giá trị của $m$ để $$x^2 - 4x + m = 0$$ có 2 nghiệm phân biệt.",
                "options": [
                    r"A. \(m < 4\)",
                    r"B. $m > 4$",
                    r"C. \(m = 4\)",
                    r"D. \(\forall m \in \mathbb{R}\)"
                ],
                "correct_answer": "A. m < 4",
                "explain": r"Biệt thức \(\Delta' = 4 - m\). Để phương trình có 2 nghiệm phân biệt thì \(\Delta' > 0 \Leftrightarrow 4 - m > 0 \Leftrightarrow m < 4\)."
            },
            {
                "question": r"Chất khí nào sinh ra khi cho Fe tác dụng với dung dịch HCl loãng: <b>Fe</b> + 2HCl \rightarrow FeCl<sub>2</sub> + H<sub>2</sub>?",
                "options": [
                    "A. Khí H2",
                    "B. Khí Cl2",
                    "C. Khí O2",
                    "D. Khí CO2"
                ],
                "correct_answer": "A",
                "explain": "Phản ứng giải phóng khí Hidro: Fe + 2HCl -> FeCl2 + H2."
            },
            {
                "question": r"Căn bậc hai của biểu thức \sqrt{x^2 + 2x + 1} bằng:",
                "options": [
                    r"A. \(|x + 1|\)",
                    r"B. \(x + 1\)",
                    r"C. \(-(x + 1)\)",
                    r"D. \((x + 1)^2\)"
                ],
                "correct_answer": "A",
                "explain": r"Vì \(\sqrt{(x+1)^2} = |x+1|\)."
            }
        ]
        stream = export_quiz_to_docx("ĐỀ THI KHẢO SÁT CHẤT LƯỢNG", questions, time_limit=45)
        self.assertIsNotNone(stream)
        stream_bytes = stream.getvalue()
        self.assertGreater(len(stream_bytes), 1000)

        # Kiểm tra đọc lại được tài liệu bằng docx.Document
        doc = Document(stream)
        self.assertGreaterEqual(len(doc.paragraphs), 5)
        self.assertEqual(len(doc.tables), 1)

        # Kiểm tra sự tồn tại của oMath trong XML
        full_xml = ""
        for p in doc.paragraphs:
            full_xml += p._p.xml
        self.assertIn("oMath", full_xml, "Văn bản Word phải chứa các đối tượng oMath (Word Equation)")
        # Đảm bảo không còn nguyên mã LaTeX thô như \frac hoặc \Delta trong văn bản thông thường
        self.assertNotIn(r"\frac", full_xml)
        self.assertNotIn(r"\Delta", full_xml)

if __name__ == '__main__':
    unittest.main()
