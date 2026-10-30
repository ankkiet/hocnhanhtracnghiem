"""
Standard Response Envelope Helpers for HocNhanhTN.
Cung cấp định dạng chuẩn cho API Responses:
{
    "status": "success" | "error",
    "message": str,
    "data": Any,
    "code": int
}
"""

from typing import Any, Optional

from fastapi.responses import JSONResponse


def success_response(
    data: Any = None,
    message: str = "Thành công",
    status_code: int = 200,
    **kwargs: Any
) -> dict:
    """Tạo response thành công chuẩn hóa."""
    res = {
        "status": "success",
        "message": message,
        "code": status_code,
    }
    if data is not None:
        res["data"] = data
    res.update(kwargs)
    return res


def error_response(
    message: str = "Đã xảy ra lỗi",
    status_code: int = 400,
    details: Optional[Any] = None
) -> JSONResponse:
    """Tạo JSONResponse lỗi chuẩn hóa."""
    content = {
        "status": "error",
        "message": message,
        "code": status_code,
    }
    if details is not None:
        content["details"] = details
    return JSONResponse(status_code=status_code, content=content)
