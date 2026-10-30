"""
AI & Gemini Infrastructure Service for HocNhanhTN.
"""

from services.ai_service import (
    ai_service,
    call_gemini_with_fallback,
    cross_check_answers,
    fix_json_latex_escapes,
    generate_mcq_from_pdf,
    generate_mcq_with_gemini,
    generate_similar_questions,
    normalize_question_data,
    process_image_with_ocr,
    process_pdf_with_ocr,
)

__all__ = [
    "ai_service",
    "call_gemini_with_fallback",
    "generate_mcq_with_gemini",
    "generate_mcq_from_pdf",
    "process_pdf_with_ocr",
    "process_image_with_ocr",
    "cross_check_answers",
    "generate_similar_questions",
    "normalize_question_data",
    "fix_json_latex_escapes",
]
