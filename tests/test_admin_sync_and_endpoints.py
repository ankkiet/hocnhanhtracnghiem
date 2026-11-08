import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.api.routes.admin import router as admin_router
from services.gemini_tracker_service import gemini_tracker

app = FastAPI()
app.include_router(admin_router)

class TestAdminSyncAndEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("app.api.routes.document.get_cached_gemini_keys")
    @patch("app.api.routes.admin.verify_admin_access")
    @patch("app.api.routes.admin._get_db")
    def test_get_api_key_sync_with_cached_keys(self, mock_get_db, mock_auth, mock_get_keys):
        """Kiểm tra /api/admin/get_api_key đồng bộ với get_cached_gemini_keys (fallback .env)"""
        mock_get_db.return_value = MagicMock()
        mock_auth.return_value = ({"email": "admin@example.com", "role": "admin"}, "admin_123")
        mock_get_keys.return_value = ["AIzaSyKey1_Valid", "AIzaSyKey2_Valid"]

        response = self.client.get("/api/admin/get_api_key?admin_token=valid_token")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("api_keys"), ["AIzaSyKey1_Valid", "AIzaSyKey2_Valid"])

    @patch("app.api.routes.document.get_cached_gemini_keys")
    @patch("app.api.routes.admin.verify_admin_access")
    @patch("app.api.routes.admin._get_db")
    def test_gemini_stats_returns_both_data_and_metrics(self, mock_get_db, mock_auth, mock_get_keys):
        """Kiểm tra /api/admin/gemini_stats trả về cả data và metrics để frontend KPI không bị undefined"""
        mock_get_db.return_value = MagicMock()
        mock_auth.return_value = ({"email": "admin@example.com", "role": "admin"}, "admin_123")
        mock_get_keys.return_value = ["AIzaSyTestKey123456"]

        response = self.client.get("/api/admin/gemini_stats?admin_token=valid_token")
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(res_json.get("status"), "success")
        self.assertIn("data", res_json)
        self.assertIn("metrics", res_json)
        
        # Verify key_statuses item includes original 'key' alongside 'masked_key'
        keys_list = res_json["metrics"].get("key_statuses", [])
        self.assertTrue(len(keys_list) > 0)
        self.assertEqual(keys_list[0]["key"], "AIzaSyTestKey123456")
        self.assertIn("masked_key", keys_list[0])

    @patch("services.ai_service.get_gemini_client")
    @patch("app.api.routes.admin.verify_admin_access")
    @patch("app.api.routes.admin._get_db")
    def test_ping_gemini_key_success(self, mock_get_db, mock_auth, mock_get_client):
        """Kiểm tra /api/admin/ping_gemini_key trả về đúng format result và latency_ms"""
        mock_get_db.return_value = MagicMock()
        mock_auth.return_value = ({"email": "admin@example.com", "role": "admin"}, "admin_123")
        
        # Mock successful Gemini API response
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=MagicMock())
        mock_get_client.return_value = mock_client

        response = self.client.post(
            "/api/admin/ping_gemini_key",
            json={"admin_token": "valid_token", "api_key": "AIzaSyTestKey123456"}
        )
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(res_json.get("status"), "success")
        self.assertIn("Hoạt động tốt", res_json.get("result", ""))
        self.assertIn("latency_ms", res_json)

    def test_tracker_get_metrics_includes_key(self):
        """Kiểm tra gemini_tracker.get_metrics trả về trường key cho frontend ping"""
        active_keys = ["AIzaSyKeyA", "AIzaSyKeyB"]
        metrics = gemini_tracker.get_metrics(current_configured_keys=active_keys)
        self.assertIn("key_statuses", metrics)
        self.assertEqual(len(metrics["key_statuses"]), 2)
        for k in metrics["key_statuses"]:
            self.assertIn("key", k)
            self.assertIn("masked_key", k)
            self.assertIn("status", k)

if __name__ == "__main__":
    unittest.main()
