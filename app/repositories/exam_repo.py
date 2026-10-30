"""
Exam & Submission Repository for HocNhanhTN.
Quản lý lưu vết bài làm, lịch sử làm bài và phiên thi của học sinh.
"""

from typing import Any, Dict, List, Optional

from app.repositories.base_repo import BaseRepository
from core.state import EXAM_SESSIONS


class ExamRepository(BaseRepository):
    """Repository quản lý bài nộp và phiên thi (Submissions & Sessions)."""

    def create_submission(self, submission_data: Dict[str, Any]) -> str:
        """Lưu bài thi đã nộp vào Firestore."""
        col = self.get_collection('submissions')
        if col is None:
            raise RuntimeError("Chưa kết nối CSDL Firebase")

        sub_id = submission_data.get('id')
        if sub_id:
            col.document(sub_id).set(submission_data)
            return sub_id
        else:
            doc_ref = col.document()
            submission_data['id'] = doc_ref.id
            doc_ref.set(submission_data)
            return doc_ref.id

    def get_submission_by_id(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết một bài thi đã nộp."""
        col = self.get_collection('submissions')
        if col is None:
            return None

        doc = col.document(submission_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data['id'] = doc.id
        return data

    def delete_submission(self, submission_id: str) -> None:
        """Xóa một bài thi đã nộp."""
        col = self.get_collection('submissions')
        if col is None:
            raise RuntimeError("Chưa kết nối CSDL Firebase")
        col.document(submission_id).delete()

    def get_submissions_by_quiz(self, quiz_id: str) -> List[Dict[str, Any]]:
        """Lấy tất cả bài nộp của một đề thi cụ thể."""
        col = self.get_collection('submissions')
        if col is None:
            return []

        docs = col.where('quiz_id', '==', quiz_id).stream()
        res = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            res.append(item)
        return res

    def get_submissions_by_student(self, student_identifier: str) -> List[Dict[str, Any]]:
        """Lấy danh sách bài nộp của một học sinh."""
        col = self.get_collection('submissions')
        if col is None:
            return []

        docs = col.where('student_id', '==', student_identifier).stream()
        res = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            res.append(item)
        return res

    # ==========================
    # QUẢN LÝ PHIÊN THI (SESSIONS)
    # ==========================
    def save_session(self, session_id: str, session_data: Dict[str, Any]) -> None:
        """Lưu phiên thi vào RAM cache & distributed cache."""
        EXAM_SESSIONS[session_id] = session_data

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin phiên thi."""
        return EXAM_SESSIONS.get(session_id)


exam_repo = ExamRepository()
