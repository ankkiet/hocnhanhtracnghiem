import pytest
import asyncio
from services.ai_service import (
    diagnose_gemini_error,
    sanitize_error_text,
    GeminiAPIException
)

def test_sanitize_error_text_masks_keys():
    raw = "Failed on key AIzaSyD1234567890abcdefghijklmnopqrstuv in request"
    cleaned = sanitize_error_text(raw)
    assert "AIzaSyD1234567890abcdefghijklmnopqrstuv" not in cleaned
    assert "AIzaSyD...stuv" in cleaned

def test_diagnose_gemini_error_no_keys():
    diag = diagnose_gemini_error(Exception("No Gemini API keys configured"), keys_tried=[])
    assert diag["error_code"] == "NO_API_KEYS"
    assert "Chưa cấu hình" in diag["error_name"]
    assert "cause" in diag
    assert "solution" in diag
    assert diag["status"] == "error"

def test_diagnose_gemini_error_quota_429():
    diag = diagnose_gemini_error(
        Exception("ResourceExhausted: 429 Resource has been exhausted"),
        keys_tried=["AIzaSyFakeKey1234567890123456789012345"]
    )
    assert diag["error_code"] == "QUOTA_EXCEEDED_429"
    assert "429" in diag["error_name"] or "Quá hạn mức" in diag["error_name"]
    assert "cause" in diag
    assert "solution" in diag

def test_diagnose_gemini_error_invalid_key():
    diag = diagnose_gemini_error(
        Exception("API_KEY_INVALID: API key not valid. Please pass a valid API key."),
        keys_tried=["AIzaSyFakeKey1234567890123456789012345"]
    )
    assert diag["error_code"] == "INVALID_API_KEY"
    assert "không hợp lệ" in diag["error_name"].lower()
    assert "cause" in diag
    assert "solution" in diag

def test_diagnose_gemini_error_model_404():
    diag = diagnose_gemini_error(
        Exception("NotFound: 404 models/gemini-2.0-flash is not found"),
        keys_tried=["AIzaSyFakeKey1234567890123456789012345"]
    )
    assert diag["error_code"] == "MODEL_NOT_FOUND_404"
    assert "404" in diag["error_name"]

def test_diagnose_gemini_error_timeout():
    diag = diagnose_gemini_error(
        asyncio.TimeoutError("Request timed out"),
        keys_tried=["AIzaSyFakeKey1234567890123456789012345"]
    )
    assert diag["error_code"] == "REQUEST_TIMEOUT"
    assert "thời gian" in diag["error_name"].lower()

def test_gemini_api_exception_structure():
    diag = {
        "status": "error",
        "error_code": "TEST_CODE",
        "error_name": "Test Error Name",
        "cause": "Test Cause",
        "solution": "Test Solution",
        "technical_detail": "Key AIzaSy12345678901234567890123456789012345678 failed"
    }
    exc = GeminiAPIException(diag)
    assert exc.diagnostic["error_code"] == "TEST_CODE"
    assert exc.diagnostic["error_name"] == "Test Error Name"
    assert "TEST_CODE" in str(exc)
