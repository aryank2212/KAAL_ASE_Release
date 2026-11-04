import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import launcher


class LauncherTests(unittest.TestCase):
    def test_env_file_does_not_override_real_environment(self):
        d = Path(tempfile.mkdtemp()); f = d / "e.env"
        f.write_text('# c\nKAAL_TEST_A=1\nKAAL_TEST_B="two words"\nKAAL_TEST_C=from-file\nbadline\n')
        with patch.dict(os.environ, {"KAAL_TEST_C": "from-env"}):
            self.assertEqual(launcher.load_env_file(f), 2)
            self.assertEqual((os.environ["KAAL_TEST_B"], os.environ["KAAL_TEST_C"]), ("two words", "from-env"))
        for k in ("KAAL_TEST_A", "KAAL_TEST_B"):
            os.environ.pop(k, None)
        self.assertEqual(launcher.load_env_file(d / "missing"), 0)

    def test_api_key_generated_once_with_private_permissions(self):
        d = Path(tempfile.mkdtemp())
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KAAL_API_KEY", None)
            k1, fresh1 = launcher.ensure_api_key(d); k2, fresh2 = launcher.ensure_api_key(d)
        self.assertTrue(fresh1 and not fresh2); self.assertEqual(k1, k2); self.assertGreaterEqual(len(k1), 40)
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE((d / "api_key").stat().st_mode), 0o600)

    def test_environment_key_wins_and_is_not_written(self):
        d = Path(tempfile.mkdtemp())
        with patch.dict(os.environ, {"KAAL_API_KEY": "from-env"}):
            self.assertEqual(launcher.ensure_api_key(d), ("from-env", False))
        self.assertFalse((d / "api_key").exists())

    def test_prepare_sets_up_sqlite_and_dirs(self):
        d = tempfile.mkdtemp()
        keep = {k: os.environ.get(k) for k in ("KAAL_DATA_DIR", "DATABASE_URL", "EVIDENCE_DIR", "KAAL_API_KEY", "KAAL_ENV_FILE")}
        try:
            for k in keep: os.environ.pop(k, None)
            a = launcher.prepare(["--data-dir", d, "--env-file", os.path.join(d, "none.env"), "--port", "9999"])
            self.assertEqual((a.host, a.port), ("127.0.0.1", 9999))
            self.assertTrue(os.environ["DATABASE_URL"].startswith("sqlite:///"))
            self.assertTrue(os.path.isdir(os.environ["EVIDENCE_DIR"]))
            self.assertEqual(os.environ["KAAL_API_KEY"], a.key)
        finally:
            for k, v in keep.items():
                os.environ.pop(k, None)
                if v is not None: os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
