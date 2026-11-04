"""Sandbox every test run: nothing may touch the real home directory or a real database."""
import os
import tempfile

_root = tempfile.mkdtemp(prefix="kaal-pytest-")
os.environ["KAAL_DATA_DIR"] = os.path.join(_root, "data")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_root}/default.db")
os.environ.setdefault("KAAL_API_KEY", "test-key")
os.environ.setdefault("EVIDENCE_DIR", os.path.join(_root, "evidence"))
os.environ.setdefault("KAAL_TOOLS_DIR", os.environ.get("KAAL_TOOLS_DIR", os.path.join(_root, "tools")))
