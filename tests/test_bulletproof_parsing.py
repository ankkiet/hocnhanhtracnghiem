import os
import io
import unittest
import xml.etree.ElementTree as ET
from docx import Document
from fastapi.testclient import TestClient

import tempfile
from core.image_converter import detect_image_format, process_image_blob
from core.mathml_parser import parse_omath
from services.r2_service import upload_image_to_r2, get_stored_image
from main import app, extract_answer_key, extract_formatting_from_docx, parse_docx_to_marked_text


class TestBulletproofParsing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_image_format_detection(self):
        """Test accurate sniffing of image magic bytes."""
        png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        jpeg_data = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        gif_data = b"GIF89a"
        bmp_data = b"BM" + b"\x00" * 20
        emf_data = b"\x01\x00\x00\x00" + b"\x00" * 36 + b" EMF"
        wmf_data = b"\xd7\xcd\xc6\x9a" + b"\x00" * 20

        self.assertEqual(detect_image_format(png_data), "png")
        self.assertEqual(detect_image_format(jpeg_data), "jpeg")
        self.assertEqual(detect_image_format(gif_data), "gif")
        self.assertEqual(detect_image_format(bmp_data), "bmp")
        self.assertEqual(detect_image_format(emf_data), "emf")
        self.assertEqual(detect_image_format(wmf_data), "wmf")

    def test_image_blob_processing(self):
        """Test processing standard raster images without crashing."""
        tiny_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        processed, ext = process_image_blob(tiny_png, "image/png")
        self.assertIn("png", ext.lower())
        self.assertTrue(len(processed) > 0)
        self.assertEqual(processed[:4], b"\x89PNG")

    def test_mathml_equation_arrays_and_fractions(self):
        """Test MathML parse_omath with fractions, superscripts and equation arrays."""
        from docx.oxml import parse_xml

        fraction_xml = """<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
            <m:f>
                <m:num><m:r><m:t>x</m:t></m:r></m:num>
                <m:den><m:r><m:t>2</m:t></m:r></m:den>
            </m:f>
        </m:oMath>"""
        elem = parse_xml(fraction_xml)
        latex = parse_omath(elem)
        self.assertIn(r"\frac{x}{2}", latex)

        eq_arr_xml = """<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
            <m:eqArr>
                <m:e><m:r><m:t>x = 1</m:t></m:r></m:e>
                <m:e><m:r><m:t>y = 2</m:t></m:r></m:e>
            </m:eqArr>
        </m:oMath>"""
        elem_arr = parse_xml(eq_arr_xml)
        latex_arr = parse_omath(elem_arr)
        self.assertIn(r"\begin{aligned}", latex_arr)
        self.assertIn(r"x = 1", latex_arr)
        self.assertIn(r"y = 2", latex_arr)
        self.assertIn(r"\end{aligned}", latex_arr)

    def test_extract_answer_key_from_docx_table(self):
        """Test extracting answer keys from bottom tables in DOCX."""
        doc = Document()
        doc.add_paragraph("Câu 1: Thủ đô của Việt Nam là gì?")
        doc.add_paragraph("A. Đà Nẵng")
        doc.add_paragraph("B. Hà Nội")
        doc.add_paragraph("C. TP.HCM")
        doc.add_paragraph("D. Cần Thơ")

        doc.add_paragraph("Câu 2: Số nguyên tố chẵn duy nhất là?")
        doc.add_paragraph("A. 0")
        doc.add_paragraph("B. 2")
        doc.add_paragraph("C. 4")
        doc.add_paragraph("D. 6")

        table = doc.add_table(rows=2, cols=2)
        row_q = table.rows[0].cells
        row_a = table.rows[1].cells
        row_q[0].text = "Câu 1"
        row_a[0].text = "B"
        row_q[1].text = "Câu 2"
        row_a[1].text = "B"

        full_text = "\n".join([p.text for p in doc.paragraphs])
        keys = extract_answer_key(doc, full_text)
        self.assertEqual(keys.get(1), "B")
        self.assertEqual(keys.get(2), "B")

    def test_docx_parsing_with_formatting_and_answer_table(self):
        """Test parsing questions from DOCX with formatting and linked answer table."""
        doc = Document()
        p1 = doc.add_paragraph()
        p1.add_run("Câu 1: Nước sôi ở bao nhiêu độ C?")
        doc.add_paragraph("A. 50")
        doc.add_paragraph("B. 80")
        doc.add_paragraph("C. 100")
        doc.add_paragraph("D. 120")

        # Answer key table
        table = doc.add_table(rows=2, cols=1)
        table.rows[0].cells[0].text = "Câu 1"
        table.rows[1].cells[0].text = "C"

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
            temp_path = tf.name
            doc.save(temp_path)

        try:
            questions = extract_formatting_from_docx(temp_path)
            self.assertTrue(len(questions) >= 1)
            self.assertIn("Nước sôi", questions[0]["question"])
            self.assertIn("C.", questions[0]["correct_answer"])
            self.assertEqual(len(questions[0]["options"]), 4)

            # Test text marking parser
            marked_text, img_map = parse_docx_to_marked_text(temp_path)
            self.assertIn("Nước sôi", marked_text)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_image_serving_endpoint(self):
        """Test caching and serving images via /api/images/{file_path:path}."""
        test_data = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        image_url = upload_image_to_r2(test_data, "test_img.gif")
        self.assertTrue(image_url.startswith("/api/images/"))

        response = self.client.get(image_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, test_data)
        self.assertIn("image/gif", response.headers["content-type"])
        self.assertIn("max-age=31536000", response.headers.get("cache-control", ""))


    def test_wmf_emf_safe_handling(self):
        """Test that WMF/EMF binaries never raise unhandled exceptions and convert safely."""
        fake_emf = b"\x01\x00\x00\x00" + b"\x00" * 40
        data, mime = process_image_blob(fake_emf, "image/x-emf")
        self.assertIsNotNone(data)
        self.assertTrue(isinstance(data, bytes))

    def test_ai_audit_statistics_logic(self):
        """Test calculation of AI Quality Audit metrics and error breakdown."""
        total_questions = 10
        raw_issues = [
            {"question_index": 2, "category": "knowledge", "issue": "Sai công thức", "suggestion": "..."},
            {"question_index": 5, "category": "answer", "issue": "Đáp án C bị trùng", "suggestion": "..."},
            {"question_index": 8, "category": "grammar_typo", "issue": "Sai chính tả", "suggestion": "..."}
        ]
        
        category_counts = {
            "knowledge": 0,
            "answer": 0,
            "grammar_typo": 0,
            "format": 0
        }
        for item in raw_issues:
            cat = item.get("category", "knowledge")
            if cat in category_counts:
                category_counts[cat] += 1
            else:
                category_counts["knowledge"] += 1

        error_count = len(raw_issues)
        valid_questions = max(0, total_questions - error_count)
        accuracy_rate = round((valid_questions / total_questions) * 100, 1)

        self.assertEqual(error_count, 3)
        self.assertEqual(valid_questions, 7)
        self.assertEqual(accuracy_rate, 70.0)
        self.assertEqual(category_counts["knowledge"], 1)
        self.assertEqual(category_counts["answer"], 1)
        self.assertEqual(category_counts["grammar_typo"], 1)
        self.assertEqual(category_counts["format"], 0)


    def test_extract_questions_from_text_bulletproof(self):
        """Test bulletproof text extractor on unusual question and option formats."""
        from main import extract_questions_from_text_bulletproof

        text = """
        Câu 1 Cho hàm số y = f(x)
        A/ Giá trị 10
        B/ Giá trị 20
        C/ [ĐÚNG] Giá trị 30
        D/ Giá trị 40

        [Câu 2] Phương trình có nghiệm:
        (A) x = 1
        (B) x = 2
        (C) x = 3
        (D) x = 4
        """
        results = extract_questions_from_text_bulletproof(text)
        self.assertEqual(len(results), 2)
        self.assertEqual(len(results[0]["options"]), 4)
        self.assertIn("C.", results[0]["correct_answer"])
        self.assertEqual(len(results[1]["options"]), 4)

    def test_upload_docx_without_ai(self):
        """Test uploading a DOCX file without AI (use_ai=False) works 100% without error."""
        import time
        doc = Document()
        doc.add_paragraph("Câu 1: Mặt trời mọc ở hướng nào?")
        doc.add_paragraph("A. Đông")
        doc.add_paragraph("B. Tây")
        doc.add_paragraph("C. Nam")
        doc.add_paragraph("D. Bắc")

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)

        response = self.client.post(
            "/api/upload",
            files={"file": ("test_no_ai.docx", buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"use_ai": "false"}
        )
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(res_json["status"], "processing")
        task_id = res_json["task_id"]

        # Chờ task hoàn tất
        time.sleep(0.5)
        task_res = self.client.get(f"/api/task_status/{task_id}")
        self.assertEqual(task_res.status_code, 200)
        task_data = task_res.json()
        self.assertEqual(task_data["status"], "success")
        self.assertTrue(len(task_data["data"]) >= 1)
        self.assertIn("Mặt trời", task_data["data"][0]["question"])

    def test_upload_pdf_without_ai(self):
        """Test uploading a PDF file without AI (use_ai=False) parses locally instead of throwing 400 error."""
        try:
            import pymupdf as fitz
        except ImportError:
            try:
                import fitz
            except ImportError:
                fitz = None
        if fitz is None:
            self.skipTest("PyMuPDF (fitz) không được cài đặt trong môi trường này")
        import time

        # Tạo file PDF đơn giản bằng PyMuPDF
        pdf_doc = fitz.open()
        page = pdf_doc.new_page()
        page.insert_text(
            (50, 72),
            "Câu 1: 1 + 1 bằng bao nhiêu?\nA. 1\nB. 2\nC. 3\nD. 4\n\nCâu 2: 2 + 2 bằng bao nhiêu?\nA. 2\nB. 4\nC. 6\nD. 8"
        )
        pdf_bytes = pdf_doc.write()
        pdf_doc.close()

        response = self.client.post(
            "/api/upload",
            files={"file": ("test_no_ai.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"use_ai": "false"}
        )
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(res_json["status"], "processing")
        task_id = res_json["task_id"]

        time.sleep(0.5)
        task_res = self.client.get(f"/api/task_status/{task_id}")
        self.assertEqual(task_res.status_code, 200)
        task_data = task_res.json()
        self.assertEqual(task_data["status"], "success")
        self.assertEqual(len(task_data["data"]), 2)

    def test_find_image_part_and_id_keyerror_o(self):
        """Test that find_image_part_and_id safely handles drawing nodes without KeyError 'o'."""
        from main import find_image_part_and_id
        from docx.oxml import parse_xml

        mock_xml = """<v:shape xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
            <v:imagedata o:relid="rId99" r:id="rId99"/>
        </v:shape>"""
        node = parse_xml(mock_xml)
        imagedata = node[0]
        doc = Document()
        rId, image_part = find_image_part_and_id(imagedata, doc)
        self.assertEqual(rId, "rId99")

    def test_split_same_line_options_in_docx(self):
        """Test that options glued on one line (Câu 3/4) are parsed into 4 distinct options."""
        from main import split_merged_options
        merged = ["A. 2-ethylpentane.B. 4-ethylpentane.C. 2-methylhexane.D. 3-methylhexane."]
        split = split_merged_options(merged)
        self.assertEqual(len(split), 4)
        self.assertEqual(split[0], "A. 2-ethylpentane.")
        self.assertEqual(split[1], "B. 4-ethylpentane.")
        self.assertEqual(split[2], "C. 2-methylhexane.")
        self.assertEqual(split[3], "D. 3-methylhexane.")

    def test_docx_with_tabs_between_options(self):
        """Test that docx using <w:tab/> between options correctly extracts 4 separate options."""
        from docx.oxml import OxmlElement
        doc = Document()
        p = doc.add_paragraph()
        p.add_run("Câu 3: Cho alkane X có CTCT: CH3CH(C2H5)CH2CH2CH3. Danh pháp thay thế của X là")
        
        p2 = doc.add_paragraph()
        p2.add_run("A. 2-ethylpentane.")
        r_tab1 = OxmlElement('w:r')
        r_tab1.append(OxmlElement('w:tab'))
        p2._element.append(r_tab1)
        p2.add_run("B. 4-ethylpentane.")
        r_tab2 = OxmlElement('w:r')
        r_tab2.append(OxmlElement('w:tab'))
        p2._element.append(r_tab2)
        p2.add_run("C. 2-methylhexane.")
        r_tab3 = OxmlElement('w:r')
        r_tab3.append(OxmlElement('w:tab'))
        p2._element.append(r_tab3)
        p2.add_run("D. 3-methylhexane.")

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
            temp_path = tf.name
        doc.save(temp_path)

        try:
            results = extract_formatting_from_docx(temp_path)
            self.assertEqual(len(results), 1)
            self.assertEqual(len(results[0]["options"]), 4)
            self.assertTrue(results[0]["options"][0].startswith("A."))
            self.assertTrue(results[0]["options"][1].startswith("B."))
            self.assertTrue(results[0]["options"][2].startswith("C."))
            self.assertTrue(results[0]["options"][3].startswith("D."))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_chemdraw_ole_object_rejected(self):
        """Test that OLE compound document binaries (ChemDraw .bin) are rejected and never treated as images."""
        # Header OLE2 CFBF signature of ChemDraw .bin
        ole_binary = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 1000 + b"ChemDraw.Document.6.0"
        processed, mime = process_image_blob(ole_binary, "application/vnd.openxmlformats-officedocument.oleObject")
        self.assertIsNone(processed)
        self.assertEqual(mime, "")

        url = upload_image_to_r2(ole_binary, mime_type="application/vnd.openxmlformats-officedocument.oleObject")
        self.assertIsNone(url)



    def test_extract_true_false_questions_bulletproof(self):
        """Kiểm tra bóc tách câu hỏi Đúng / Sai chuẩn Bộ GD&ĐT (GDPT 2018)."""
        from main import extract_questions_from_text_bulletproof
        
        sample_tf = """
        PHẦN II. Câu trắc nghiệm đúng sai.
        Câu 1. Cho hàm số y = f(x) = x^3 - 3x + 1.
        *a) Đồ thị hàm số đi qua điểm M(0; 1).
        b) Hàm số đồng biến trên toàn bộ R. [SAI]
        *c) Điểm cực đại của đồ thị hàm số là (-1; 3).
        d) Giá trị nhỏ nhất của hàm số trên đoạn [0; 2] bằng 1. [SAI]
        Hướng dẫn giải:
        a) Với x=0 thì y=1 -> Đúng.
        b) y' = 3x^2 - 3 có nghiệm x=±1 nên đổi dấu -> Sai.
        """
        
        questions = extract_questions_from_text_bulletproof(sample_tf)
        self.assertEqual(len(questions), 1)
        q = questions[0]
        self.assertEqual(q["type"], "true_false")
        self.assertEqual(len(q["options"]), 4)
        self.assertTrue(q["options"][0].startswith("a) "))
        self.assertTrue(q["options"][1].startswith("b) "))
        self.assertTrue(q["options"][2].startswith("c) "))
        self.assertTrue(q["options"][3].startswith("d) "))
        self.assertEqual(q["correct_answer"], {"a": True, "b": False, "c": True, "d": False})
        self.assertIn("Với x=0", q["explain"])

    def test_extract_short_answer_questions_bulletproof(self):
        """Kiểm tra bóc tách câu hỏi Trắc nghiệm trả lời ngắn chuẩn Bộ GD&ĐT (GDPT 2018)."""
        from main import extract_questions_from_text_bulletproof
        
        sample_sa = """
        PHẦN III. Câu trắc nghiệm trả lời ngắn.
        Câu 1. Cho khối chóp có diện tích đáy bằng 12 và chiều cao bằng 5. Tính thể tích khối chóp.
        Đáp án: 20
        Lời giải: V = 1/3 * B * h = 1/3 * 12 * 5 = 20.
        
        Câu 2. Tìm giá trị lớn nhất của hàm số y = -x^2 + 4x + 1.
        ĐS: 5
        """
        
        questions = extract_questions_from_text_bulletproof(sample_sa)
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]["type"], "short_answer")
        self.assertEqual(questions[0]["correct_answer"], "20")
        self.assertEqual(questions[0]["options"], [])
        self.assertIn("1/3 * 12 * 5", questions[0]["explain"])
        
        self.assertEqual(questions[1]["type"], "short_answer")
        self.assertEqual(questions[1]["correct_answer"], "5")

    def test_normalize_question_data_bgd_types(self):
        """Kiểm tra normalize_question_data chuẩn hóa chính xác cả 3 dạng câu hỏi."""
        from services.ai_service import normalize_question_data
        
        # 1. MCQ
        mcq = normalize_question_data({
            "question": "Câu 1: Hàm số nào đồng biến?",
            "options": ["A. y = x^3", "B. y = x^4", "C. y = -x", "D. y = 1/x"],
            "correct_answer": "A"
        })
        self.assertEqual(mcq["type"], "mcq")
        self.assertEqual(mcq["correct_answer"], "A. y = x<sup>3</sup>")
        
        # 2. True / False
        tf = normalize_question_data({
            "question": "Câu 2: Cho hàm số f(x)...",
            "options": ["*a) Ý một", "b) Ý hai", "*c) Ý ba", "d) Ý bốn"],
            "correct_answer": "a: Đ, b: S, c: Đ, d: S"
        })
        self.assertEqual(tf["type"], "true_false")
        self.assertEqual(tf["correct_answer"], {"a": True, "b": False, "c": True, "d": False})
        
        # 3. Short Answer
        sa = normalize_question_data({
            "question": "Câu 3: Tính diện tích tam giác...",
            "options": [],
            "correct_answer": "Đáp án: 15.5"
        })
        self.assertEqual(sa["type"], "short_answer")
    def test_normalize_question_data_edge_cases(self):
        """Kiểm tra các trường hợp đặc biệt: tiền tố Câu X, chữ hoa/thường, dấu hoa thị, tag [ĐÚNG]/[SAI]."""
        from services.ai_service import normalize_question_data
        from core.docx_parser import split_merged_options
        
        # Tiền tố [Câu 1] và dấu hoa thị *A.
        q1 = normalize_question_data({
            "question": "[Câu 10] Cho chất hữu cơ X...",
            "options": ["*A. C_2H_5OH", "B. CH_3COOH", "C. H_2O", "D. CO_2"],
            "correct_answer": "Đáp án A"
        })
        self.assertEqual(q1["question"], "Cho chất hữu cơ X...")
        self.assertEqual(q1["options"][0], "A. C<sub>2</sub>H<sub>5</sub>OH")
        self.assertNotIn("*", q1["options"][0])
        self.assertEqual(q1["correct_answer"], "A. C<sub>2</sub>H<sub>5</sub>OH")
        self.assertEqual(q1["type"], "mcq")

        # Phương án dạng chữ thường a, b, c, d nhưng là MCQ (không có cấu trúc Đúng/Sai)
        q2 = normalize_question_data({
            "question": "1. Thủ đô của Việt Nam là gì?",
            "options": ["a. Hà Nội", "b. Đà Nẵng", "c. Huế", "d. TP.HCM"],
            "correct_answer": "(A)"
        })
        self.assertEqual(q2["question"], "Thủ đô của Việt Nam là gì?")
        self.assertEqual(q2["options"][0], "A. Hà Nội")
        self.assertEqual(q2["correct_answer"], "A. Hà Nội")
        self.assertEqual(q2["type"], "mcq")

        # Dạng Đúng / Sai có tag [ĐÚNG], [SAI] trong nội dung options
        q3 = normalize_question_data({
            "type": "true_false",
            "question": "Câu 2: Các mệnh đề sau:",
            "options": ["a) Đường thẳng song song mặt phẳng [ĐÚNG]", "b) Mặt phẳng vuông góc đường thẳng [SAI]"],
            "correct_answer": ""
        })
        self.assertEqual(q3["question"], "Các mệnh đề sau:")
        self.assertEqual(q3["options"][0], "a) Đường thẳng song song mặt phẳng")
        self.assertEqual(q3["options"][1], "b) Mặt phẳng vuông góc đường thẳng")
        self.assertTrue(q3["correct_answer"]["a"])
        self.assertFalse(q3["correct_answer"]["b"])

        # Bảo vệ câu toán có dấu chấm trong câu không bị chẻ nhầm bởi split_merged_options
        opts = [
            "A. Cho tam giác ABC vuông tại A và B. Biết AB = 2a.",
            "B. Cho tam giác ABC đều.",
            "C. Cho hình vuông ABCD.",
            "D. Cho hình thang vuông."
        ]
        res_opts = split_merged_options(opts)
        self.assertEqual(len(res_opts), 4)
        self.assertEqual(res_opts[0], opts[0])


if __name__ == "__main__":
    unittest.main()
