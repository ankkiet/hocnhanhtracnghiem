"""
General Utility Helpers for HocNhanhTN.
"""

import html
import re
from typing import Any, Dict


def sanitize_filename(filename: str) -> str:
    """Loại bỏ các ký tự nguy hiểm khỏi tên file."""
    clean = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
    return clean[:200]


def unescape_content(text: str) -> str:
    """Giải mã các ký tự HTML entity trong nội dung đề thi."""
    if not text or not isinstance(text, str):
        return text
    return html.unescape(text)


def extract_dict_subset(data: Dict[str, Any], keys: list) -> Dict[str, Any]:
    """Trích xuất một tập con của dictionary an toàn."""
    return {k: data[k] for k in keys if k in data}
