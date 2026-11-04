import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routers import console

H = {"X-API-Key": "test-key"}


class GlobeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app)

    def test_unconfigured(self):
        with patch.object(settings, "globe_url", ""):
            r = self.c.get("/api/v1/globe", headers=H).json()
            self.assertFalse(r["configured"]); self.assertIn("KAAL_GLOBE_URL", r["setup"])
            csp = self.c.get("/ui/").headers["content-security-policy"]
            self.assertIn("frame-src 'none'", csp)

    def test_origin_validation(self):
        for bad in ("ftp://x", "javascript:alert(1)", "http://user:pw@host:1", "nothing", "//host"):
            with patch.object(settings, "globe_url", bad):
                self.assertEqual(console.globe_origin(), "", bad)
        with patch.object(settings, "globe_url", "http://100.64.0.1:4173/some/path?x=1"):
            self.assertEqual(console.globe_origin(), "http://100.64.0.1:4173")      # origin only, no path

    def test_configured_reachable_and_csp_allows_only_that_origin(self):
        class Resp: status_code = 200
        with patch.object(settings, "globe_url", "http://100.64.0.1:4173"), patch.object(console.httpx, "get", return_value=Resp()):
            r = self.c.get("/api/v1/globe", headers=H).json()
            self.assertEqual((r["configured"], r["reachable"], r["url"]), (True, True, "http://100.64.0.1:4173"))
            csp = self.c.get("/ui/").headers["content-security-policy"]
            self.assertIn("frame-src http://100.64.0.1:4173;", csp)
            self.assertIn("frame-ancestors 'none'", csp)               # KAAL itself still cannot be framed by others

    def test_configured_but_down(self):
        with patch.object(settings, "globe_url", "http://100.64.0.1:4173"), patch.object(console.httpx, "get", side_effect=httpx.ConnectError("x")):
            r = self.c.get("/api/v1/globe", headers=H).json()
            self.assertEqual((r["configured"], r["reachable"]), (True, False)); self.assertIn("cannot reach", r["error"])

    def test_requires_key(self):
        self.assertEqual(self.c.get("/api/v1/globe").status_code, 401)


if __name__ == "__main__":
    unittest.main()
