import random
import string
import sys
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from firebase_admin import firestore

from core.logging_config import get_logger
from core.security import get_user_from_token
from core.state import QUIZ_CACHE, active_tasks


def _get_db(force_refresh=False):
    quiz_mod = sys.modules.get('routers.quiz')
    if quiz_mod and hasattr(quiz_mod, 'get_db'):
        try:
            return quiz_mod.get_db(force_refresh=force_refresh) if force_refresh else quiz_mod.get_db()
        except TypeError:
            return quiz_mod.get_db()
        except Exception:
            pass
    from services.firebase_service import get_db as fb_get_db
    return fb_get_db(force_refresh=force_refresh)
from services.storage_service import storage_service

logger = get_logger(__name__)


class QuizService:
    """
    Dịch vụ nghiệp vụ quản lý Đề thi (Quiz Service).
    Bao gồm: Lưu trữ, truy vấn, bảo mật chống gian lận F12, dọn dẹp ảnh nháp,
    và cơ chế Tự phục hồi kết nối (Self-Healing) kèm Stale Cache Fallback.
    """

    def __init__(self, cache_ttl: int = 900):
        self.cache_ttl = cache_ttl  # 15 phút lưu bộ đệm RAM để tiết kiệm quota đọc Firestore

    def get_quiz(self, quiz_id: str, teacher_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Truy vấn dữ liệu bài thi theo ID với cơ chế Bảo mật và Fallback đa tầng:
        1. Kiểm tra RAM cache trước để giảm tải Firestore.
        2. Truy vấn Firestore với cơ chế Self-Healing (tự làm mới token nếu 403).
        3. Sử dụng Stale Cache dự phòng nếu Firestore tạm thời mất kết nối.
        4. Bảo mật Anti-F12: Tự động loại bỏ đáp án đúng & lời giải khi học sinh làm bài 'exam'.
        """
        db = _get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối cơ sở dữ liệu Firebase")

        now = time.time()
        quiz_data = None

        # 1. Kiểm tra RAM cache
        if quiz_id in QUIZ_CACHE and (now - QUIZ_CACHE[quiz_id]['time'] < self.cache_ttl):
            quiz_data = QUIZ_CACHE[quiz_id]['data']
            logger.debug(f"QuizService: Lấy đề thi {quiz_id} từ RAM Cache.")
        else:
            try:
                doc_ref = db.collection('quizzes').document(quiz_id)
                doc = doc_ref.get()
                if doc.exists:
                    quiz_data = doc.to_dict()
                    QUIZ_CACHE[quiz_id] = {'time': now, 'data': quiz_data}
                else:
                    raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")
            except HTTPException:
                raise
            except Exception as e:
                # 2. Self-Healing: Thử kết nối lại DB với token mới
                logger.warning(f"QuizService: Lỗi truy vấn đề thi {quiz_id} ({e}). Đang tái kết nối DB...")
                try:
                    db = _get_db(force_refresh=True)
                    doc = db.collection('quizzes').document(quiz_id).get()
                    if doc.exists:
                        quiz_data = doc.to_dict()
                        QUIZ_CACHE[quiz_id] = {'time': now, 'data': quiz_data}
                    else:
                        raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")
                except HTTPException:
                    raise
                except Exception as retry_err:
                    # 3. Fallback: Dùng Stale Cache nếu có
                    if quiz_id in QUIZ_CACHE and QUIZ_CACHE[quiz_id].get('data'):
                        logger.warning(f"QuizService: Dùng Stale Cache dự phòng cho đề {quiz_id}: {retry_err}")
                        quiz_data = QUIZ_CACHE[quiz_id]['data']
                    else:
                        logger.error(f"QuizService: Không thể tải đề {quiz_id} sau khi thử phục hồi: {retry_err}")
                        raise HTTPException(
                            status_code=503,
                            detail="Hệ thống cơ sở dữ liệu đang đồng bộ lại. Vui lòng thử lại sau giây lát."
                        )

        # 4. Xác minh quyền sở hữu
        stored_creator = quiz_data.get('creator_id')
        is_creator = False
        if teacher_token:
            user = get_user_from_token(teacher_token, db)
            user_uid = user['id'] if user else teacher_token
            is_creator = (
                user_uid == stored_creator or
                teacher_token == stored_creator or
                (user and user.get('role') in ['teacher', 'admin'])
            )

        if quiz_data.get('status') == 'unpublished' and not is_creator:
            raise HTTPException(status_code=403, detail="Bài thi này đã bị giáo viên tạm khóa (Hủy xuất bản).")

        updated_at = quiz_data.get('updated_at')
        updated_ts = updated_at.timestamp() if hasattr(updated_at, 'timestamp') else 0

        raw_questions = quiz_data.get('data', [])
        mode = quiz_data.get('mode', 'practice')

        # 5. Bảo mật Anti-Cheat: Chế độ 'exam' cho học sinh sẽ ẩn toàn bộ đáp án đúng & lời giải
        if mode == 'exam' and not is_creator:
            sanitized_questions = []
            for q in raw_questions:
                q_copy = {k: v for k, v in q.items() if k not in ['correct_answer', 'explain']}
                sanitized_questions.append(q_copy)
            questions_to_return = sanitized_questions
        else:
            questions_to_return = raw_questions

        return {
            "status": "success",
            "title": quiz_data.get('title'),
            "data": questions_to_return,
            "mode": mode,
            "time_limit": quiz_data.get('time_limit', 0),
            "is_shuffle": quiz_data.get('is_shuffle', False),
            "updated_at": updated_ts
        }

    def save_quiz(
        self,
        title: str,
        data: list,
        mode: str = "practice",
        time_limit: int = 0,
        is_shuffle: bool = False,
        creator_id: str = "",
        status: str = "published",
        quiz_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lưu hoặc cập nhật đề thi vào Firestore, tự động dọn dẹp ảnh mồ côi và làm mới cache.
        """
        db = _get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")

        user = get_user_from_token(creator_id, db)
        creator_uid = user['id'] if user else creator_id

        if quiz_id:
            target_id = quiz_id
            doc_ref = db.collection('quizzes').document(target_id)
            doc = doc_ref.get()
            if doc.exists:
                stored_creator = doc.to_dict().get('creator_id')
                if stored_creator != creator_uid and stored_creator != creator_id:
                    raise HTTPException(status_code=403, detail="Không có quyền cập nhật đề thi này")

                # Dọn dẹp ảnh cũ trong R2 nếu giáo viên xóa hoặc thay thế ảnh
                old_quiz_data = doc.to_dict()
                old_imgs = set(storage_service.extract_image_keys(old_quiz_data.get('data', [])))
                new_imgs = set(storage_service.extract_image_keys(data))
                removed_imgs = old_imgs - new_imgs
                if removed_imgs:
                    storage_service.delete_images(list(removed_imgs))
        else:
            # Tạo mã ngẫu nhiên dạng AAA-111
            target_id = self._generate_unique_quiz_id(db)

        doc_ref = db.collection('quizzes').document(target_id)
        data_to_save = {
            'title': title,
            'data': data,
            'mode': mode,
            'time_limit': time_limit,
            'is_shuffle': is_shuffle,
            'creator_id': creator_uid,
            'status': status,
            'updated_at': firestore.SERVER_TIMESTAMP
        }

        if not quiz_id:
            data_to_save['created_at'] = firestore.SERVER_TIMESTAMP

        try:
            doc_ref.set(data_to_save, merge=True)
            logger.info(f"QuizService: Đã lưu đề thi {target_id} thành công.")
        except Exception as e:
            if "maximum document size" in str(e).lower() or "exceeds" in str(e).lower():
                raise HTTPException(
                    status_code=413,
                    detail="Dung lượng đề thi quá lớn (vượt quá 1MB). Vui lòng giảm bớt kích thước ảnh."
                )
            raise HTTPException(status_code=500, detail=f"Lỗi khi lưu vào cơ sở dữ liệu: {str(e)}")

        # Xóa cache để học sinh nhận ngay đề mới nhất
        QUIZ_CACHE.pop(target_id, None)
        return {"status": "success", "quiz_id": target_id, "link": f"/?id={target_id}"}

    def discard_draft(
        self,
        task_id: Optional[str] = None,
        images: Optional[List[str]] = None,
        quiz_data: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Hủy bản nháp và dọn sạch các ảnh tạm thời đã tải lên lưu trữ.
        """
        images_to_delete = set(images or [])

        if quiz_data:
            extracted = storage_service.extract_image_keys(quiz_data)
            images_to_delete.update(extracted)

        if task_id and task_id in active_tasks:
            task_info = active_tasks.pop(task_id, {})
            task_data = task_info.get("data")
            if task_data:
                extracted = storage_service.extract_image_keys(task_data)
                images_to_delete.update(extracted)

        deleted_count = storage_service.delete_images(list(images_to_delete))
        logger.info(f"QuizService: Đã hủy nháp task={task_id}, xóa {deleted_count} ảnh.")
        return {"status": "success", "deleted_images": deleted_count}

    def _generate_unique_quiz_id(self, db) -> str:
        """Sinh mã đề ngẫu nhiên dạng AAA-111 và đảm bảo không trùng lặp."""
        for _ in range(50):
            part1 = ''.join(random.choices(string.ascii_uppercase, k=3))
            part2 = ''.join(random.choices(string.digits, k=3))
            candidate_id = f"{part1}-{part2}"
            if not db.collection('quizzes').document(candidate_id).get().exists:
                return candidate_id
        # Fallback timestamp nếu quá nhiều đề
        return f"QZ-{int(time.time())}"


# Thực thể singleton
quiz_service = QuizService()
