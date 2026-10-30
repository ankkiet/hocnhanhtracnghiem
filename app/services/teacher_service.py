"""
Teacher & Exam Management Service for HocNhanhTN.
Chịu trách nhiệm: Phân tích kết quả bài thi, xuất file Word,
thao tác trạng thái đề thi và kiểm định chất lượng đề bằng AI.
"""

from io import BytesIO
from typing import Any, Dict

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.config.logging import get_logger
from app.repositories.exam_repo import ExamRepository, exam_repo
from app.repositories.quiz_repo import QuizRepository, quiz_repo
from app.schemas.quiz import QuizActionRequest
from app.utils.security import verify_teacher_access
from core.docx_exporter import export_quiz_to_docx
from services.audit_service import audit_service
from services.r2_service import delete_images_from_r2, extract_image_keys_from_data

logger = get_logger(__name__)


class TeacherService:
    """Service xử lý toàn bộ logic cho Giáo viên."""

    def __init__(
        self,
        quiz_repository: QuizRepository = quiz_repo,
        exam_repository: ExamRepository = exam_repo
    ):
        self.quiz_repo = quiz_repository
        self.exam_repo = exam_repository

    def handle_quiz_action(self, req: QuizActionRequest) -> Dict[str, Any]:
        """Thực hiện các thao tác quản lý trạng thái đề thi."""
        teacher_auth = verify_teacher_access(req.teacher_token, self.quiz_repo.db)
        user = teacher_auth[0] if isinstance(teacher_auth, (tuple, list)) else {}
        user_uid = teacher_auth[1] if isinstance(teacher_auth, (tuple, list)) and len(teacher_auth) > 1 else req.teacher_token

        quiz_data = self.quiz_repo.get_quiz_by_id(req.quiz_id, use_cache=False)
        if not quiz_data:
            raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")

        creator = quiz_data.get('creator_id')
        if creator and isinstance(user, dict) and user.get('role'):
            if creator != user_uid and creator != req.teacher_token and user.get('role') != 'admin':
                raise HTTPException(status_code=403, detail="Bạn không có quyền thao tác trên đề thi của giáo viên khác.")

        if req.action == 'publish':
            self.quiz_repo.update_quiz(req.quiz_id, {'status': 'published'})
        elif req.action == 'unpublish':
            self.quiz_repo.update_quiz(req.quiz_id, {'status': 'unpublished'})
        elif req.action == 'archive':
            self.quiz_repo.update_quiz(req.quiz_id, {'status': 'archived'})
        elif req.action == 'restore':
            self.quiz_repo.update_quiz(req.quiz_id, {'status': 'unpublished'})
        elif req.action == 'permanent':
            audit_service.record_event(
                action="QUIZ_PERMANENT_DELETE",
                actor_id=user_uid,
                actor_role=user.get('role', 'teacher'),
                target_id=req.quiz_id
            )
            image_keys = extract_image_keys_from_data(quiz_data)
            if image_keys:
                delete_images_from_r2(image_keys)
            self.quiz_repo.delete_quiz(req.quiz_id)

        return {"status": "success", "action": req.action}

    def get_quiz_analytics(self, quiz_id: str, teacher_token: str) -> Dict[str, Any]:
        """Tổng hợp thống kê phân tích điểm số và câu hỏi của đề thi."""
        teacher_auth = verify_teacher_access(teacher_token, self.quiz_repo.db)
        user = teacher_auth[0] if isinstance(teacher_auth, (tuple, list)) else {}
        user_uid = teacher_auth[1] if isinstance(teacher_auth, (tuple, list)) and len(teacher_auth) > 1 else teacher_token

        quiz_data = self.quiz_repo.get_quiz_by_id(quiz_id, use_cache=True)
        if not quiz_data:
            raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")

        creator = quiz_data.get('creator_id')
        if creator and isinstance(user, dict) and user.get('role'):
            if creator != user_uid and creator != teacher_token and user.get('role') != 'admin':
                raise HTTPException(status_code=403, detail="Không có quyền xem phân tích bài nộp của đề thi này.")

        submissions = self.exam_repo.get_submissions_by_quiz(quiz_id)
        total_sub = len(submissions)
        scores = [s.get('score', 0) for s in submissions]
        avg_score = round(sum(scores) / total_sub, 2) if total_sub > 0 else 0

        return {
            "status": "success",
            "quiz_id": quiz_id,
            "title": quiz_data.get('title', ''),
            "total_submissions": total_sub,
            "average_score": avg_score,
            "submissions": submissions
        }

    def export_word(self, quiz_id: str, teacher_token: str) -> StreamingResponse:
        """Xuất đề thi ra file Word (.docx) chuẩn."""
        verify_teacher_access(teacher_token, self.quiz_repo.db)
        quiz_data = self.quiz_repo.get_quiz_by_id(quiz_id, use_cache=True)
        if not quiz_data:
            raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")

        doc = export_quiz_to_docx(quiz_data)
        bio = BytesIO()
        doc.save(bio)
        bio.seek(0)

        filename = f"de_thi_{quiz_id}.docx"
        return StreamingResponse(
            bio,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


teacher_service = TeacherService()
