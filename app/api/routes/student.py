"""
Student Router for HocNhanhTN.
Endpoint declarations for Student Exam Submissions, Session Management, Leaderboards, and Exam History.
"""


from fastapi import APIRouter, Depends

from app.core.dependencies import RateLimiter
from app.schemas.student import (
    PingSessionRequest,
    SaveProgressRequest,
    StartExamRequest,
    SubmitExamRequest,
    SubmitScoreRequest,
    SyncHistoryItem,
    SyncHistoryRequest,
)
from app.services.student_service import _get_db as get_db
from app.services.student_service import _get_user_from_token as get_user_from_token
from app.services.student_service import student_service

router = APIRouter(prefix="/api", tags=["Student Exam & Progress"])

__all__ = [
    "router",
    "get_db",
    "get_user_from_token",
    "StartExamRequest",
    "SubmitExamRequest",
    "SyncHistoryItem",
    "SyncHistoryRequest",
    "SubmitScoreRequest",
    "SaveProgressRequest",
    "PingSessionRequest",
    "start_exam",
    "submit_exam",
    "submit_score_legacy",
    "save_student_progress",
    "get_student_progress",
    "ping_session",
    "get_leaderboard",
    "get_student_history",
    "get_student_history_detail",
    "delete_student_history",
    "sync_student_history",
]


@router.post("/student/start_exam", summary="Khởi tạo phiên thi với mốc thời gian thực từ Server")
async def start_exam(req: StartExamRequest):
    return await student_service.start_exam(req)


@router.post(
    "/student/submit_exam",
    summary="Chấm điểm bài thi an toàn phía Backend",
    dependencies=[Depends(RateLimiter(times=20, seconds=60, key_prefix="exam_submit"))],
)
async def submit_exam(req: SubmitExamRequest):
    return await student_service.submit_exam(req)


@router.post("/student/submit_score", summary="Ghi nhận điểm thi (Legacy API)")
async def submit_score_legacy(request: SubmitScoreRequest):
    return await student_service.submit_score_legacy(request)


@router.post("/student/save_progress", summary="Lưu tiến độ làm bài thi tạm thời")
async def save_student_progress(req: SaveProgressRequest):
    return await student_service.save_student_progress(req)


@router.get("/student/get_progress/{quiz_id}", summary="Lấy tiến độ làm bài thi chưa hoàn thành")
async def get_student_progress(quiz_id: str, student_token: str):
    return await student_service.get_student_progress(quiz_id=quiz_id, student_token=student_token)


@router.post("/student/ping_session", summary="Cập nhật trạng thái heartbeat phiên làm bài")
async def ping_session(req: PingSessionRequest):
    return await student_service.ping_session(req)


@router.get("/student/leaderboard/{quiz_id}", summary="Lấy bảng xếp hạng học sinh theo đề thi")
async def get_leaderboard(quiz_id: str):
    return await student_service.get_leaderboard(quiz_id=quiz_id)


@router.get("/student/history", summary="Lấy danh sách lịch sử thi của học sinh")
async def get_student_history(student_token: str):
    return await student_service.get_student_history(student_token=student_token)


@router.get("/student/history/{history_id}", summary="Lấy chi tiết một bài thi đã nộp trong lịch sử")
async def get_student_history_detail(history_id: str, student_token: str):
    return await student_service.get_student_history_detail(history_id=history_id, student_token=student_token)


@router.delete("/student/history/{history_id}", summary="Xóa bài thi khỏi lịch sử học sinh")
async def delete_student_history(history_id: str, student_token: str):
    return await student_service.delete_student_history(history_id=history_id, student_token=student_token)


@router.post("/student/sync_history", summary="Đồng bộ lịch sử từ bộ nhớ máy lên tài khoản học sinh")
async def sync_student_history(req: SyncHistoryRequest):
    return await student_service.sync_student_history(req)
