"""
Gemini API Quota & Usage Tracker Service.
Theo dõi số lần gọi, trạng thái từng API Key (cảnh báo 429/sắp hết quota),
lịch sử lỗi theo ngày và ước tính chi phí sử dụng.
"""

import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

# Định giá Gemini Flash tham khảo (USD / 1M tokens)
# Free Tier: $0, Paid tier chuẩn: Input $0.075 / 1M, Output $0.30 / 1M
COST_INPUT_PER_1M = 0.075
COST_OUTPUT_PER_1M = 0.30
USD_TO_VND_RATE = 25400


def get_current_date_vn() -> str:
    """Trả về ngày hiện tại theo giờ Việt Nam (YYYY-MM-DD)."""
    return datetime.now(VN_TZ).strftime("%Y-%m-%d")


def mask_api_key(key: str) -> str:
    """Ẩn bớt API key để hiển thị an toàn trên giao diện Admin (vd: AIzaSyB...X9y1)."""
    if not key:
        return "UNKNOWN_KEY"
    if len(key) < 10:
        return "Key_***"
    return f"{key[:7]}...{key[-4:]}"


class GeminiTrackerService:
    def __init__(self, cache_file: str = ".cache/gemini_tracker.json"):
        self.cache_file = cache_file
        self.lock = threading.Lock()
        
        # Cấu trúc lưu trữ dữ liệu
        self.data: Dict[str, Any] = {
            "daily_stats": {},     # "YYYY-MM-DD": { "total": 0, "success": 0, "errors": 0, "errors_429": 0, ... }
            "key_stats": {},       # "masked_key": { "calls_today": 0, "total_calls": 0, "status": "healthy", ... }
            "all_time_totals": {
                "total_calls": 0,
                "total_success": 0,
                "total_errors": 0,
                "total_429": 0,
                "estimated_prompt_tokens": 0,
                "estimated_response_tokens": 0,
            }
        }
        
        self._load_from_disk()

    def mask_api_key(self, key: str) -> str:
        return mask_api_key(key)

    def _load_from_disk(self) -> None:
        """Đọc dữ liệu thống kê từ tệp JSON cache cục bộ nếu có."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        self.data["daily_stats"] = saved.get("daily_stats", {})
                        self.data["key_stats"] = saved.get("key_stats", {})
                        self.data["all_time_totals"] = saved.get("all_time_totals", self.data["all_time_totals"])
        except Exception as e:
            logger.warning(f"[GEMINI TRACKER] Lỗi đọc cache từ file: {e}")

    def _save_to_disk(self) -> None:
        """Ghi dữ liệu thống kê xuống tệp JSON cache cục bộ."""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[GEMINI TRACKER] Lỗi ghi cache xuống file: {e}")

    def record_call(
        self,
        api_key: str,
        model: str,
        success: bool,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        prompt_chars: int = 0,
        response_chars: int = 0,
        duration_ms: float = 0.0,
    ) -> None:
        """Ghi nhận một lượt gọi Gemini API (Thành công hoặc Lỗi)."""
        if not api_key:
            return

        if not error_message and error_type:
            error_message = error_type

        masked = mask_api_key(api_key)
        date_str = get_current_date_vn()
        now_iso = datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")

        # Ước tính token (trung bình 1 token ~ 4 ký tự)
        prompt_tokens = max(1, prompt_chars // 4) if prompt_chars > 0 else 500
        response_tokens = max(1, response_chars // 4) if response_chars > 0 else (300 if success else 0)

        with self.lock:
            # 1. Cập nhật Daily Stats
            if date_str not in self.data["daily_stats"]:
                self.data["daily_stats"][date_str] = {
                    "date": date_str,
                    "total_calls": 0,
                    "success_calls": 0,
                    "error_calls": 0,
                    "errors_429": 0,
                    "errors_invalid_key": 0,
                    "errors_timeout": 0,
                    "errors_other": 0,
                    "prompt_tokens": 0,
                    "response_tokens": 0,
                }
            
            day_entry = self.data["daily_stats"][date_str]
            day_entry["total_calls"] += 1
            day_entry["prompt_tokens"] += prompt_tokens
            day_entry["response_tokens"] += response_tokens

            # 2. Cập nhật All-Time Totals
            totals = self.data["all_time_totals"]
            totals["total_calls"] += 1
            totals["estimated_prompt_tokens"] += prompt_tokens
            totals["estimated_response_tokens"] += response_tokens

            # 3. Cập nhật Key Stats
            if masked not in self.data["key_stats"]:
                self.data["key_stats"][masked] = {
                    "masked_key": masked,
                    "status": "healthy",
                    "status_label": "🟢 Đang hoạt động",
                    "calls_today": 0,
                    "calls_total": 0,
                    "errors_today": 0,
                    "errors_429_today": 0,
                    "last_used_date": date_str,
                    "last_used_at": now_iso,
                    "last_error": None,
                    "last_error_at": None,
                    "model_used": model,
                }

            key_entry = self.data["key_stats"][masked]
            # Reset lượt gọi ngày nếu sang ngày mới
            if key_entry.get("last_used_date") != date_str:
                key_entry["calls_today"] = 0
                key_entry["errors_today"] = 0
                key_entry["errors_429_today"] = 0
                key_entry["last_used_date"] = date_str

            key_entry["calls_today"] += 1
            key_entry["calls_total"] += 1
            key_entry["last_used_at"] = now_iso
            key_entry["model_used"] = model

            if success:
                day_entry["success_calls"] += 1
                totals["total_success"] += 1
                # Nếu key đang warning mà gọi thành công, chuyển lại healthy
                if key_entry.get("status") in ["warning_429", "error"]:
                    key_entry["status"] = "healthy"
                    key_entry["status_label"] = "🟢 Đang hoạt động"
            else:
                day_entry["error_calls"] += 1
                totals["total_errors"] += 1
                key_entry["errors_today"] += 1
                key_entry["last_error"] = error_message or "Unknown error"
                key_entry["last_error_at"] = now_iso

                err_lower = (error_message or "").lower()
                if "429" in err_lower or "quota" in err_lower or "overloaded" in err_lower or "resource_exhausted" in err_lower:
                    day_entry["errors_429"] += 1
                    totals["total_429"] += 1
                    key_entry["errors_429_today"] += 1
                    key_entry["status"] = "warning_429"
                    key_entry["status_label"] = "🔴 Hết Quota (Lỗi 429)"
                elif "api key not valid" in err_lower or "invalid api key" in err_lower or "400" in err_lower:
                    day_entry["errors_invalid_key"] += 1
                    key_entry["status"] = "invalid_key"
                    key_entry["status_label"] = "⚠️ Khóa không hợp lệ"
                elif "deadline" in err_lower or "timeout" in err_lower:
                    day_entry["errors_timeout"] += 1
                else:
                    day_entry["errors_other"] += 1
                    if key_entry.get("status") != "warning_429":
                        key_entry["status"] = "error"
                        key_entry["status_label"] = "⚠️ Gặp lỗi kết nối"

            # Lưu lại sau mỗi 5 cuộc gọi hoặc khi có lỗi
            if not success or (day_entry["total_calls"] % 5 == 0):
                self._save_to_disk()

    def get_metrics(self, current_configured_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """Tổng hợp số liệu thống kê chi tiết cho trang Admin."""
        date_str = get_current_date_vn()

        with self.lock:
            # Lấy số liệu ngày hôm nay
            today_entry = self.data["daily_stats"].get(date_str, {
                "total_calls": 0,
                "success_calls": 0,
                "error_calls": 0,
                "errors_429": 0,
                "errors_invalid_key": 0,
                "prompt_tokens": 0,
                "response_tokens": 0,
            })

            totals = self.data["all_time_totals"]

            # Danh sách ngày gần nhất (sắp xếp giảm dần, tối đa 14 ngày)
            sorted_days = sorted(self.data["daily_stats"].keys(), reverse=True)[:14]
            daily_history = []
            for d in sorted_days:
                de = self.data["daily_stats"][d]
                tot = de.get("total_calls", 0)
                errs = de.get("error_calls", 0)
                e429 = de.get("errors_429", 0)
                err_rate = round((errs / tot * 100), 1) if tot > 0 else 0.0
                daily_history.append({
                    "date": d,
                    "total_calls": tot,
                    "success_calls": de.get("success_calls", 0),
                    "error_calls": errs,
                    "error_429": e429,
                    "errors_429": e429,
                    "other_errors": max(0, errs - e429),
                    "errors_invalid": de.get("errors_invalid_key", 0),
                    "error_rate_percent": err_rate,
                })

            # Tình trạng các Key đang cấu hình
            keys_result = []
            configured_masked_set = set()
            if current_configured_keys:
                for idx, k in enumerate(current_configured_keys):
                    masked = mask_api_key(k)
                    configured_masked_set.add(masked)
                    k_stat = self.data["key_stats"].get(masked, {
                        "masked_key": masked,
                        "status": "healthy",
                        "status_label": "🟢 Đang hoạt động",
                        "calls_today": 0,
                        "calls_total": 0,
                        "errors_today": 0,
                        "errors_429_today": 0,
                        "last_used_at": "Chưa dùng",
                        "last_error": None,
                    })
                    e429_count = k_stat.get("errors_429_today", 0)
                    k_status = k_stat.get("status", "healthy")
                    if e429_count >= 4 or k_status == "exhausted":
                        k_status = "exhausted"
                        status_label = "🔴 Hết Quota (Exhausted)"
                    elif e429_count > 0 or k_status == "warning_429":
                        k_status = "warning_429"
                        status_label = "🟡 Sắp đầy / Gặp lỗi 429"
                    else:
                        status_label = k_stat.get("status_label", "🟢 Đang hoạt động")

                    keys_result.append({
                        "index": idx + 1,
                        "masked_key": masked,
                        "status": k_status,
                        "status_label": status_label,
                        "calls_today": k_stat.get("calls_today", 0),
                        "calls_total": k_stat.get("calls_total", 0),
                        "errors_429_today": e429_count,
                        "last_used_at": k_stat.get("last_used_at", "Chưa dùng"),
                        "last_error": k_stat.get("last_error"),
                    })

            # Tính toán ước tính chi phí (USD & VND)
            total_prompt_tok = totals.get("estimated_prompt_tokens", 0)
            total_resp_tok = totals.get("estimated_response_tokens", 0)
            cost_usd = (total_prompt_tok / 1_000_000 * COST_INPUT_PER_1M) + (total_resp_tok / 1_000_000 * COST_OUTPUT_PER_1M)
            cost_vnd = int(cost_usd * USD_TO_VND_RATE)

            today_prompt_tok = today_entry.get("prompt_tokens", 0)
            today_resp_tok = today_entry.get("response_tokens", 0)
            today_cost_usd = (today_prompt_tok / 1_000_000 * COST_INPUT_PER_1M) + (today_resp_tok / 1_000_000 * COST_OUTPUT_PER_1M)
            today_cost_vnd = int(today_cost_usd * USD_TO_VND_RATE)

            total_c = today_entry.get("total_calls", 0)
            succ_c = today_entry.get("success_calls", 0)
            success_rate = round((succ_c / total_c * 100), 1) if total_c > 0 else 100.0

            warning_keys_count = sum(1 for k in keys_result if k.get("status") in ["warning_429", "invalid_key", "exhausted"])

            today_dict = {
                "total_calls": total_c,
                "success_calls": succ_c,
                "error_calls": today_entry.get("error_calls", 0),
                "error_429": today_entry.get("errors_429", 0),
                "other_errors": max(0, today_entry.get("error_calls", 0) - today_entry.get("errors_429", 0)),
                "success_rate": success_rate,
                "estimated_cost_usd": round(today_cost_usd, 4),
                "estimated_cost_vnd": today_cost_vnd,
            }
            all_time_dict = {
                "total_calls": totals.get("total_calls", 0),
                "success_calls": totals.get("total_success", 0),
                "total_errors": totals.get("total_errors", 0),
                "error_429": totals.get("total_429", 0),
                "other_errors": max(0, totals.get("total_errors", 0) - totals.get("total_429", 0)),
                "estimated_cost_usd": round(cost_usd, 4),
                "estimated_cost_vnd": cost_vnd,
            }

            return {
                "today": today_dict,
                "all_time": all_time_dict,
                "summary": {
                    "calls_today": total_c,
                    "success_today": succ_c,
                    "errors_today": today_entry.get("error_calls", 0),
                    "errors_429_today": today_entry.get("errors_429", 0),
                    "success_rate_percent": success_rate,
                    "total_configured_keys": len(keys_result),
                    "warning_keys_count": warning_keys_count,
                    "all_time_calls": totals.get("total_calls", 0),
                    "all_time_errors": totals.get("total_errors", 0),
                },
                "cost_estimation": {
                    "is_free_tier": True,
                    "today_tokens_estimated": today_prompt_tok + today_resp_tok,
                    "today_cost_usd": round(today_cost_usd, 4),
                    "today_cost_vnd": today_cost_vnd,
                    "all_time_cost_usd": round(cost_usd, 4),
                    "all_time_cost_vnd": cost_vnd,
                    "pricing_note": "Hệ thống tận dụng Free Tier Gemini. Chi phí ước tính tính theo biểu giá trả phí Google ($0.075 / 1M input tokens).",
                },
                "keys_status": keys_result,
                "key_statuses": keys_result,
                "daily_history": daily_history,
            }


# Singleton instance toàn cục
gemini_tracker = GeminiTrackerService()
