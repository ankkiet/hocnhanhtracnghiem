from typing import List, Dict, Any

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

from core.image_converter import process_image_blob
from services.r2_service import upload_image_to_r2
from core.text_parser import extract_questions_from_text_bulletproof


def extract_questions_from_pdf_locally(pdf_path: str) -> List[Dict[str, Any]]:
    """Bóc tách câu hỏi và hình ảnh từ tệp PDF hoàn toàn cục bộ (không cần AI)."""
    if not fitz:
        return []
    try:
        doc = fitz.open(pdf_path)
        full_text_list = []
        image_mapping = {}
        img_counter = 0
        
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text("text")
            
            # Trích xuất ảnh trên trang PDF
            image_list = page.get_images(full=True)
            for img_info in image_list:
                try:
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image.get("image")
                    image_ext = base_image.get("ext", "png")
                    if image_bytes:
                        img_counter += 1
                        placeholder = f"[IMG_{img_counter}]"
                        processed_bytes, processed_mime = process_image_blob(image_bytes, f"image/{image_ext}")
                        img_url = upload_image_to_r2(processed_bytes, mime_type=processed_mime, extension=image_ext)
                        if img_url:
                            image_mapping[placeholder] = f"<br><img src='{img_url}' class='quiz-image' style='max-width:100%; height:auto;' /><br>"
                except Exception as img_err:
                    print(f"[CẢNH BÁO] Lỗi trích xuất ảnh PDF: {img_err}")
                    
            full_text_list.append(text)
        doc.close()
        
        merged_text = "\n".join(full_text_list)
        return extract_questions_from_text_bulletproof(merged_text, image_mapping)
    except Exception as e:
        print(f"[CẢNH BÁO] Lỗi đọc PDF cục bộ: {e}")
        return []
