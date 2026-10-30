import os
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.app_factory import create_app


class TestCORSSecurity(unittest.TestCase):
    """Kiểm tra cấu hình bảo mật CORS phân chia theo môi trường (Production / Staging / Development)."""

    def test_production_cors_strictness(self):
        """Trong môi trường production, chỉ domain chính thức được phép, chặn toàn bộ domain lạ và localhost."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            app = create_app()
            client = TestClient(app)

            # 1. Domain chính thức được phép
            res_prod = client.get("/api/health", headers={"Origin": "https://hocnhanhtn.online"})
            self.assertEqual(res_prod.status_code, 200)
            self.assertEqual(res_prod.headers.get("access-control-allow-origin"), "https://hocnhanhtn.online")
            self.assertEqual(res_prod.headers.get("access-control-allow-credentials"), "true")

            # 2. Domain Cloudflare Pages được phép
            res_pages = client.get("/api/health", headers={"Origin": "https://hocnhanhtn.pages.dev"})
            self.assertEqual(res_pages.headers.get("access-control-allow-origin"), "https://hocnhanhtn.pages.dev")

            # 3. Domain độc hại/lạ bị chặn (không có header access-control-allow-origin)
            res_evil = client.get("/api/health", headers={"Origin": "https://evil-hacker.com"})
            self.assertIsNone(res_evil.headers.get("access-control-allow-origin"))

            # 4. Localhost bị chặn ở production
            res_local = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
            self.assertIsNone(res_local.headers.get("access-control-allow-origin"))

    def test_development_cors_flexibility(self):
        """Trong môi trường development, cho phép localhost và các cổng phát triển frontend."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            app = create_app()
            client = TestClient(app)

            # 1. Localhost 3000 (React / Next.js) được phép
            res_local3000 = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
            self.assertEqual(res_local3000.headers.get("access-control-allow-origin"), "http://localhost:3000")

            # 2. Localhost 5173 (Vite) được phép
            res_vite = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})
            self.assertEqual(res_vite.headers.get("access-control-allow-origin"), "http://127.0.0.1:5173")

            # 3. Mạng nội bộ LAN 192.168.x.x được phép khi dev trên thiết bị di động
            res_lan = client.get("/api/health", headers={"Origin": "http://192.168.1.50:3000"})
            self.assertEqual(res_lan.headers.get("access-control-allow-origin"), "http://192.168.1.50:3000")

            # 4. Domain độc hại bên ngoài vẫn bị chặn
            res_evil = client.get("/api/health", headers={"Origin": "https://attacker-site.com"})
            self.assertIsNone(res_evil.headers.get("access-control-allow-origin"))

    def test_custom_cors_env_override(self):
        """Cho phép cấu hình custom origins thông qua biến môi trường CORS_ALLOWED_ORIGINS."""
        custom_domain = "https://custom-partner.edu.vn"
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ALLOWED_ORIGINS": f"{custom_domain},https://partner2.com"
        }, clear=False):
            app = create_app()
            client = TestClient(app)

            # Custom domain được cấu hình
            res_custom = client.get("/api/health", headers={"Origin": custom_domain})
            self.assertEqual(res_custom.headers.get("access-control-allow-origin"), custom_domain)

            # Domain khác không có trong danh sách bị chặn
            res_other = client.get("/api/health", headers={"Origin": "https://unauthorized.com"})
            self.assertIsNone(res_other.headers.get("access-control-allow-origin"))


if __name__ == "__main__":
    unittest.main()
