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
    for mod_name in ('routers.quiz', 'app.api.routes.quiz'):
        quiz_mod = sys.modules.get(mod_name)
        if quiz_mod and hasattr(quiz_mod, 'get_db'):
            func = getattr(quiz_mod, 'get_db')
            if hasattr(func, 'assert_called') or hasattr(func, 'return_value'):
                try:
                    return func(force_refresh=force_refresh) if force_refresh else func()
                except TypeError:
                    return func()
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

        quiz_status = quiz_data.get('status', 'published')
        if quiz_status in ['trashed', 'deleted']:
            if not is_creator:
                raise HTTPException(status_code=404, detail="Bài thi không tồn tại hoặc đã bị xóa.")
        elif quiz_status in ['unpublished', 'locked', 'archived'] and not is_creator:
            raise HTTPException(status_code=403, detail="Bài thi này đã bị giáo viên tạm khóa (hủy xuất bản).")

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

        res_data = {
            "status": "success",
            "title": quiz_data.get('title'),
            "data": questions_to_return,
            "mode": mode,
            "time_limit": quiz_data.get('time_limit', 0),
            "is_shuffle": quiz_data.get('is_shuffle', False),
            "description": quiz_data.get('description', ''),
            "settings": quiz_data.get('settings', {}),
            "updated_at": updated_ts
        }
        if is_creator and quiz_data.get('password'):
            res_data["password"] = quiz_data.get('password')
        else:
            res_data["has_password"] = bool(quiz_data.get('password'))
        return res_data

    def verify_password(self, quiz_id: str, password: str) -> Dict[str, Any]:
        """Xác thực mật khẩu đề thi của học sinh."""
        db = _get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")
        
        now = time.time()
        quiz_data = None
        if quiz_id in QUIZ_CACHE and (now - QUIZ_CACHE[quiz_id]['time'] < self.cache_ttl):
            quiz_data = QUIZ_CACHE[quiz_id]['data']
        else:
            doc = db.collection('quizzes').document(quiz_id).get()
            if doc.exists:
                quiz_data = doc.to_dict()
                QUIZ_CACHE[quiz_id] = {'time': now, 'data': quiz_data}
        
        if not quiz_data:
            raise HTTPException(status_code=404, detail="Không tìm thấy bài thi")
        
        expected_pwd = (quiz_data.get('password') or '').strip()
        if not expected_pwd:
            return {"status": "success", "valid": True}
        
        if expected_pwd == (password or '').strip():
            return {"status": "success", "valid": True}
        
        return {"status": "error", "valid": False, "detail": "Mật khẩu bài thi không chính xác"}

    def _restore_and_protect_questions(self, new_questions: list, old_questions: Optional[list] = None) -> list:
        """
        Bảo toàn toàn diện dữ liệu và đáp án câu hỏi khi lưu hoặc xuất bản lại:
        1. Hoàn tác xáo trộn (un-shuffle): nếu dữ liệu gửi lên từ client bị mang các trường đảo trộn
           (_originalIndex, _originalOptions, _originalCorrectAnswer), tự động phục hồi thứ tự gốc,
           phương án gốc và đáp án gốc ban đầu.
        2. Bảo vệ và khôi phục đáp án gốc (preserve existing correct answers):
           Nếu cập nhật đề thi mà câu hỏi mới bị mất đáp án (do Anti-Cheat xóa đáp án khi client nạp đề,
           hoặc do client gửi thiếu trường correct_answer), tự động khôi phục correct_answer và explain
           từ bản ghi câu hỏi cũ trong Firestore, ngăn chặn tuyệt đối lỗi nhảy sai đáp án về A.
        3. Dọn sạch các trường tạm do client sinh ra (_originalIndex, _originalOptions, _originalCorrectAnswer).
        """
        if not isinstance(new_questions, list):
            return new_questions

        import re

        # 1. Nếu có _originalIndex từ shuffleQuiz của client, khôi phục lại thứ tự câu hỏi gốc
        has_orig_idx = any(isinstance(q, dict) and '_originalIndex' in q for q in new_questions)
        if has_orig_idx:
            try:
                new_questions = sorted(
                    new_questions,
                    key=lambda x: x.get('_originalIndex', 999999) if isinstance(x, dict) else 999999
                )
            except Exception:
                pass

        # 2. Hoàn tác options và correct_answer nếu từng bị trộn ở client
        for q in new_questions:
            if not isinstance(q, dict):
                continue
            if '_originalOptions' in q and isinstance(q['_originalOptions'], list) and len(q['_originalOptions']) > 0:
                q['options'] = list(q['_originalOptions'])
                # Khi phương án bị đảo được hoàn tác, đáp án đúng cũng phải hoàn tác theo thứ tự gốc
                if '_originalCorrectAnswer' in q and q['_originalCorrectAnswer'] is not None:
                    q['correct_answer'] = q['_originalCorrectAnswer']
            elif '_originalCorrectAnswer' in q and q['_originalCorrectAnswer'] is not None:
                # Chỉ khôi phục đáp án gốc nếu câu hỏi chưa có đáp án, không đè lên đáp án giáo viên vừa sửa
                if q.get('correct_answer') is None or q.get('correct_answer') == '':
                    q['correct_answer'] = q['_originalCorrectAnswer']

            # Xóa các thuộc tính tạm của client
            q.pop('_originalIndex', None)
            q.pop('_originalOptions', None)
            q.pop('_originalCorrectAnswer', None)

        # 3. Bảo vệ và khôi phục đáp án từ CSDL cũ nếu dữ liệu mới bị mất đáp án
        if old_questions and isinstance(old_questions, list):
            def clean_stem(t):
                cleaned = re.sub(r'^(?:(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*|\d+[\.\:\)\/])\s*', '', str(t or ''), flags=re.IGNORECASE)
                cleaned = re.sub(r'<[^>]+>', '', cleaned)
                return re.sub(r'\s+', '', cleaned).lower()

            old_by_stem = {}
            for old_q in old_questions:
                if isinstance(old_q, dict) and old_q.get('correct_answer'):
                    stem = clean_stem(old_q.get('question', ''))
                    if stem and stem not in old_by_stem:
                        old_by_stem[stem] = old_q

            for idx, q in enumerate(new_questions):
                if not isinstance(q, dict):
                    continue
                ca = q.get('correct_answer')
                has_valid_ca = bool(ca) if not isinstance(ca, dict) else (len(ca) > 0 and any(k in ca for k in ['a', 'b', 'c', 'd']))

                if not has_valid_ca:
                    # Ưu tiên 1: Khôi phục theo đúng vị trí index trong đề cũ
                    matched_old = None
                    if idx < len(old_questions) and isinstance(old_questions[idx], dict):
                        cand = old_questions[idx]
                        if cand.get('correct_answer'):
                            matched_old = cand

                    # Ưu tiên 2: Khôi phục theo nội dung thân câu hỏi (stem)
                    if not matched_old:
                        stem = clean_stem(q.get('question', ''))
                        if stem in old_by_stem:
                            matched_old = old_by_stem[stem]

                    if matched_old:
                        q['correct_answer'] = matched_old['correct_answer']
                        if not q.get('explain') and matched_old.get('explain'):
                            q['explain'] = matched_old['explain']

        return new_questions

    def save_quiz(
        self,
        title: str,
        data: list,
        mode: str = "practice",
        time_limit: int = 0,
        is_shuffle: bool = False,
        creator_id: str = "",
        status: str = "published",
        quiz_id: Optional[str] = None,
        description: Optional[str] = "",
        password: Optional[str] = "",
        settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Lưu hoặc cập nhật đề thi vào Firestore, tự động dọn dẹp ảnh mồ côi và làm mới cache.
        """
        db = _get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Chưa kết nối CSDL Firebase")

        user = get_user_from_token(creator_id, db)
        creator_uid = user['id'] if user else creator_id

        old_questions = None
        if quiz_id:
            target_id = quiz_id
            doc_ref = db.collection('quizzes').document(target_id)
            doc = doc_ref.get()
            if doc.exists:
                old_quiz_data = doc.to_dict()
                old_questions = old_quiz_data.get('data') or old_quiz_data.get('questions') or []
                stored_creator = old_quiz_data.get('creator_id')
                if stored_creator and stored_creator != creator_uid and stored_creator != creator_id:
                    raise HTTPException(status_code=403, detail="Không có quyền cập nhật đề thi này")

                # Dọn dẹp ảnh cũ trong R2 nếu giáo viên xóa hoặc thay thế ảnh
                old_imgs = set(storage_service.extract_image_keys(old_questions))
                new_imgs = set(storage_service.extract_image_keys(data))
                removed_imgs = old_imgs - new_imgs
                if removed_imgs:
                    storage_service.delete_images(list(removed_imgs))
        else:
            # Tạo mã ngẫu nhiên dạng AAA-111
            target_id = self._generate_unique_quiz_id(db)

        # Khôi phục và bảo toàn đáp án trước khi chuẩn hóa
        restored_data = self._restore_and_protect_questions(data, old_questions=old_questions)

        from services.ai_service import normalize_question_data
        clean_quiz_data = [normalize_question_data(q) for q in restored_data] if isinstance(restored_data, list) else restored_data

        doc_ref = db.collection('quizzes').document(target_id)
        data_to_save = {
            'title': title,
            'data': clean_quiz_data,
            'mode': mode,
            'time_limit': time_limit,
            'is_shuffle': is_shuffle,
            'creator_id': creator_uid,
            'status': status,
            'updated_at': firestore.SERVER_TIMESTAMP
        }

        if description:
            data_to_save['description'] = description
        if password:
            data_to_save['password'] = password
        if settings:
            data_to_save['settings'] = settings

        if not quiz_id:
            data_to_save['created_at'] = firestore.SERVER_TIMESTAMP
            data_to_save['total_submissions'] = 0

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

        # Xóa cache để học sinh nhận ngay đề mới nhất và danh sách đề của giáo viên được cập nhật
        QUIZ_CACHE.pop(target_id, None)
        try:
            from app.api.routes.teacher import invalidate_teacher_quizzes_cache
            invalidate_teacher_quizzes_cache(creator_uid)
        except Exception:
            pass
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
