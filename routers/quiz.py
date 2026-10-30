from typing import Any, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.firebase_service import get_db  # noqa: F401
from services.quiz_service import quiz_service

router = APIRouter(prefix="/api", tags=["Quiz Management"])


class SaveQuizRequest(BaseModel):
    quiz_id: Optional[str] = None
    title: str
    data: list
    mode: str = "practice"
    time_limit: int = 0
    is_shuffle: bool = False
    creator_id: str = ""
    status: str = "published"


class DiscardDraftRequest(BaseModel):
    task_id: Optional[str] = None
    images: Optional[List[str]] = None
    quiz_data: Optional[Any] = None


@router.post("/discard_draft", summary="Hủy bản nháp và xóa toàn bộ ảnh tạm thời trên Cloudflare R2")
async def discard_draft(req: DiscardDraftRequest):
    """
    Xóa sạch mọi dấu vết của file tải lên khi người dùng không xuất bản mà thoát ra:
    - Xóa các ảnh đã upload trong task khỏi Cloudflare R2 và local cache.
    - Xóa task khỏi active_tasks bộ nhớ đệm.
    """
    return quiz_service.discard_draft(
        task_id=req.task_id,
        images=req.images,
        quiz_data=req.quiz_data
    )


@router.post("/save_quiz", summary="Lưu bài thi và lấy link")
async def save_quiz(request: SaveQuizRequest):
    """Lưu đề thi mới hoặc cập nhật đề thi hiện có vào Firestore."""
    return quiz_service.save_quiz(
        title=request.title,
        data=request.data,
        mode=request.mode,
        time_limit=request.time_limit,
        is_shuffle=request.is_shuffle,
        creator_id=request.creator_id,
        status=request.status,
        quiz_id=request.quiz_id
    )


@router.get("/get_quiz/{quiz_id}", summary="Lấy dữ liệu bài thi qua ID (Bảo mật chống F12)")
async def get_quiz(quiz_id: str, teacher_token: Optional[str] = None):
    """Truy vấn đề thi theo ID với cơ chế bảo mật chống xem trước đáp án."""
    return quiz_service.get_quiz(quiz_id=quiz_id, teacher_token=teacher_token)
