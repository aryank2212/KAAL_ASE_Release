import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

_tmp = tempfile.mkdtemp(prefix="kaal-llm-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/t.db"
os.environ["KAAL_API_KEY"] = "test-key"

from fastapi.testclient import TestClient  # noqa: E402

from app import llm, llm_backend as lb  # noqa: E402
from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402

H = {"X-API-Key": "test-key"}
SEEN = []


def serve(handler_cls):
    srv = HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


class _Base(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        n = int(self.headers.get("Content-Length", 0)); return json.loads(self.rfile.read(n) or b"{}")


class FakeOllama(_Base):
    def do_GET(self):
        self._send({"models": [{"name": "gemma2:2b"}, {"name": "llama3.1:8b"}, {"name": "nomic-embed-text"}]} if self.path == "/api/tags" else {}, 200 if self.path == "/api/tags" else 404)
    def do_POST(self):
        b = self.body(); SEEN.append(("ollama", self.path, b.get("model")))
        if self.path == "/api/chat": self._send({"message": {"content": f"ollama:{b['model']}"}})
        elif self.path == "/api/embeddings": self._send({"embedding": [0.1, 0.2]})
        else: self._send({}, 404)


class FakeLMStudio(_Base):
    def do_GET(self):
        self._send({"data": [{"id": "qwen2.5-7b-instruct"}, {"id": "text-embedding-nomic-embed-text-v1.5"}]} if self.path == "/v1/models" else {}, 200 if self.path == "/v1/models" else 404)
    def do_POST(self):
        b = self.body(); SEEN.append(("lmstudio", self.path, b.get("model"), self.headers.get("Authorization")))
        if self.path == "/v1/chat/completions": self._send({"choices": [{"message": {"content": f"lms:{b['model']}"}}]})
        elif self.path == "/v1/embeddings": self._send({"data": [{"embedding": [0.3, 0.4, 0.5]}]})
        else: self._send({}, 404)


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.o, cls.ourl = serve(FakeOllama)
        cls.l, cls.lurl = serve(FakeLMStudio)
        cls.c = TestClient(app)

    def test_switch_ollama_then_lmstudio_and_model_live(self):
        r = self.c.put("/api/v1/llm", headers=H, json={"provider": "ollama", "base_url": self.ourl, "model": "llama3.1:8b"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["reachable"])
        self.assertEqual(llm._chat("s", "p"), "ollama:llama3.1:8b")          # old call sites follow the config
        self.assertEqual(llm.embed_text("x"), [0.1, 0.2])
        r = self.c.put("/api/v1/llm", headers=H, json={"provider": "lmstudio", "base_url": self.lurl,
                       "model": "qwen2.5-7b-instruct", "embed_model": "text-embedding-nomic-embed-text-v1.5", "api_key": "lm-secret"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["config"]["api_key"], "set")              # key is never echoed
        self.assertNotIn("lm-secret", r.text)
        self.assertEqual(llm._chat("s", "p"), "lms:qwen2.5-7b-instruct")
        self.assertEqual(llm.embed_text("x"), [0.3, 0.4, 0.5])
        self.assertEqual(SEEN[-1][3], "Bearer lm-secret")
        # change just the model, no restart
        names = [m["name"] for m in self.c.get("/api/v1/llm/models", headers=H).json()]
        self.assertIn("qwen2.5-7b-instruct", names)

    def test_unknown_model_rejected_with_available_list(self):
        r = self.c.put("/api/v1/llm", headers=H, json={"provider": "ollama", "base_url": self.ourl, "model": "does-not-exist"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("llama3.1:8b", r.json()["detail"])

    def test_bad_urls_and_unreachable_host(self):
        for url in ("ftp://x:1", "http://user:pw@host:1", "nothing"):
            r = self.c.put("/api/v1/llm", headers=H, json={"base_url": url, "verify": False})
            self.assertEqual(r.status_code, 422, url)
        r = self.c.put("/api/v1/llm", headers=H, json={"base_url": "http://127.0.0.1:1", "verify": True})
        self.assertEqual(r.status_code, 422)
        self.assertIn("cannot reach", r.json()["detail"])

    def test_status_when_host_down_and_auth(self):
        self.assertEqual(self.c.get("/api/v1/llm").status_code, 401)
        lb.save(lb.LLMConfig(provider="ollama", base_url="http://127.0.0.1:1"))
        s = self.c.get("/api/v1/llm", headers=H).json()
        self.assertFalse(s["reachable"]); self.assertIn("cannot reach", s["error"])


if __name__ == "__main__":
    unittest.main()
