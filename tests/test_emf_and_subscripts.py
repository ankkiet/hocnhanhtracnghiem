import unittest
import docx
from core.image_converter import process_image_blob, convert_vector_image_to_png
import core.image_converter as ic
from services.ai_service import clean_subscripts_and_formulas, reinject_missing_image_placeholders, normalize_question_data
from core.text_parser import extract_questions_from_text_bulletproof, replace_placeholders


class TestEmfAndSubscripts(unittest.TestCase):

    def test_crossplatform_emf_conversion(self):
        """Kiểm tra chuyển đổi EMF sang PNG trên môi trường giả lập Linux (tắt Windows GDI+)."""
        docx_path = r'C:\Users\pc\.gemini\antigravity\brain\c85f7b74-1a22-4e28-b877-5ad24b0d9718\.user_uploaded\media_1793856217385_0695d0a9.docx'
        doc = docx.Document(docx_path)
        
        # Tắt GDI+ để giả lập Linux container trên Koyeb
        old_clsid = ic.CLSID_PNG
        try:
            ic.CLSID_PNG = None
            
            # Kiểm tra ảnh Câu 5 (image2.emf)
            blob_la = doc.part.rels['rId6'].target_part.blob
            png_la, mime_la = process_image_blob(blob_la, 'image/x-emf')
            self.assertEqual(mime_la, 'image/png')
            self.assertIsNotNone(png_la)
            self.assertTrue(len(png_la) > 2000)
            self.assertTrue(png_la.startswith(b'\x89PNG\r\n\x1a\n'))
            
            # Kiểm tra ảnh Câu 6 (image3.emf)
            blob_ala = doc.part.rels['rId7'].target_part.blob
            png_ala, mime_ala = process_image_blob(blob_ala, 'image/x-emf')
            self.assertEqual(mime_ala, 'image/png')
            self.assertIsNotNone(png_ala)
            self.assertTrue(len(png_ala) > 2000)
            self.assertTrue(png_ala.startswith(b'\x89PNG\r\n\x1a\n'))
        finally:
            ic.CLSID_PNG = old_clsid

    def test_chemical_formula_subscripts(self):
        """Kiểm tra tự động gom khoảng cách và chuyển chỉ số dưới chuẩn HTML: (C 17 H 35 COO) 3 C 3 H 5."""
        raw_text = "Thủy phân tristearin (C 17 H 35 COO) 3 C 3 H 5 trong dung dịch NaOH"
        cleaned = clean_subscripts_and_formulas(raw_text)
        self.assertIn("(C<sub>17</sub>H<sub>35</sub>COO)<sub>3</sub>C<sub>3</sub>H<sub>5</sub>", cleaned)
        self.assertNotIn(" 17 ", cleaned)
        self.assertNotIn(" 35 ", cleaned)

    def test_solution_concentrations_and_percentages_not_subscripted(self):
        """Kiểm tra các đại lượng phần trăm (NaOH 30%), nồng độ (HCl 1M) không bị biến thành chỉ số dưới."""
        text1 = "- Bước 2: Thêm khoảng 2 mL dung dịch H2SO4 20% vào ống nghiệm (1) và khoảng 2 mL dung dịch NaOH 30% vào ống nghiệm (2)."
        cleaned1 = clean_subscripts_and_formulas(text1)
        self.assertIn("NaOH 30%", cleaned1)
        self.assertNotIn("NaOH<sub>30</sub>", cleaned1)
        self.assertNotIn("NaOH30", cleaned1)
        self.assertIn("H<sub>2</sub>SO<sub>4</sub> 20%", cleaned1)
        self.assertIn("ống nghiệm (1)", cleaned1)
        self.assertIn("ống nghiệm (2)", cleaned1)

        text2 = "Cho 5,6 gam Fe tác dụng với 200 mL dung dịch HCl 1M thu được V lít khí H2 (đkc)."
        cleaned2 = clean_subscripts_and_formulas(text2)
        self.assertIn("HCl 1M", cleaned2)
        self.assertNotIn("HCl<sub>1</sub>", cleaned2)
        self.assertIn("H<sub>2</sub> (đkc)", cleaned2)

    def test_reinject_missing_image_placeholders(self):
        """Kiểm tra tự động khôi phục placeholder ảnh [IMG_X] nếu AI bỏ sót."""
        chunk = """
        <b>Câu 5. </b>Acid linoleic (LA) có công thức:
        [IMG_3]
        <b>a)</b> LA là acid béo omega-6.
        """
        mock_ai_questions = [{
            "question_number": 5,
            "type": "true_false",
            "question": "Acid linoleic (LA) có công thức:",
            "options": ["a) LA là acid béo omega-6."]
        }]
        fixed = reinject_missing_image_placeholders(chunk, mock_ai_questions)
        self.assertIn("[IMG_3]", fixed[0]["question"])

    def test_true_false_bold_prefix_parsing(self):
        """Kiểm tra không để sót thẻ <b> ở cuối câu hỏi khi các ý là <b>a)</b>."""
        block = """
        PHẦN II. Câu trắc nghiệm đúng sai.
        Câu 5. Công thức khung của LA như sau:
        [IMG_3]
        <b>a)</b> LA là acid béo omega-6.
        <b>b)</b> Trong cấu trúc của LA có 2 liên kết đôi.
        <b>c)</b> Trên phổ hồng ngoại.
        <b>d)</b> Sử dụng viên uống.
        """
        questions = extract_questions_from_text_bulletproof(block)
        self.assertEqual(len(questions), 1)
        q = questions[0]
        self.assertFalse(q["question"].endswith("<b>"))
        self.assertIn("[IMG_3]", q["question"])
        self.assertTrue(q["options"][0].startswith("a)"))
        self.assertNotIn("<b>", q["options"][0][:5])

    def test_image_resize_aspect_ratio_preservation(self):
        """Kiểm tra ảnh siêu rộng (như phản ứng este Câu 7: 2832x485) khi resize không bị méo/phồng."""
        import io
        from PIL import Image
        
        # Tạo ảnh giả lập tỉ lệ 2832x485
        test_img = Image.new("RGB", (2832, 485), color=(255, 255, 255))
        buf = io.BytesIO()
        test_img.save(buf, format="PNG")
        raw_bytes = buf.getvalue()

        # Xử lý qua process_image_blob với max_width=800
        processed_bytes, mime = process_image_blob(raw_bytes, "image/png", max_width=800)
        self.assertEqual(mime, "image/png")
        
        with Image.open(io.BytesIO(processed_bytes)) as result_img:
            self.assertEqual(result_img.width, 800)
            expected_height = int(485 * 800 / 2832)  # ~137
            self.assertEqual(result_img.height, expected_height)
            orig_ratio = 2832 / 485
            new_ratio = result_img.width / result_img.height
            self.assertAlmostEqual(orig_ratio, new_ratio, delta=0.05)


if __name__ == '__main__':
    unittest.main()
