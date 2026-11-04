import os
import tempfile
import unittest
from unittest.mock import patch

_tmp = tempfile.mkdtemp(prefix="kaal-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/t.db"
os.environ["KAAL_API_KEY"] = "test-key"
os.environ["EVIDENCE_DIR"] = _tmp

from fastapi.testclient import TestClient  # noqa: E402

from app.connectors import builtin, policy, registry  # noqa: E402
from app.connectors.base import Connector  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AuditEvent, Case, Evidence  # noqa: E402

H = {"X-API-Key": "test-key"}


class Fake(Connector):
    name, kind, license = "fake", "domain", "test"
    def normalise(self, t): return policy.normalise_domain(t)
    def run(self, t): return {"outputs": {"x": t}, "source_references": ["fake://" + t], "confidence": 0.5, "warnings": []}


class FakeUser(Fake):
    name, kind, people_adjacent = "fakeuser", "username", True
    def normalise(self, t): return policy.normalise_username(t)


class PolicyTests(unittest.TestCase):
    def test_domain(self):
        self.assertEqual(policy.normalise_domain(" Example.COM. "), "example.com")
        for bad in ("http://example.com", "127.0.0.1", "localhost", "a.internal", "user@example.com", "example.com/x", "x.local", ""):
            with self.assertRaises(policy.PolicyError, msg=bad):
                policy.normalise_domain(bad)

    def test_denied(self):
        for n in ("holehe", "ghunt", "face_match"):
            with self.assertRaises(policy.PolicyError):
                policy.check_denied(n)

    def test_purpose(self):
        with self.assertRaises(policy.PolicyError): policy.check_purpose("short")
        self.assertTrue(policy.check_purpose("Authorized brand-protection review"))

    def test_phone_and_username(self):
        policy.normalise_phone("+14155550100")
        with self.assertRaises(policy.PolicyError): policy.normalise_phone("4155550100")
        with self.assertRaises(policy.PolicyError): policy.normalise_username("a b")


class ConnectorTests(unittest.TestCase):
    def test_registry_lists_all_and_hides_denied(self):
        names = {c["name"] for c in registry.describe()}
        self.assertTrue({"dns_records", "whois", "cert_transparency", "wayback", "phone_parse", "image_metadata",
                         "maigret", "sherlock", "theharvester", "wikipedia_briefing"} <= names)
        self.assertFalse(names & set(policy.DENIED))

    def test_username_cli_output_parsed(self):
        sample = "[*] Checking\n\r[+] GitHub: https://github.com/python\n[+] GitHub: https://github.com/python\n[+] Reddit: https://www.reddit.com/user/python\n[-] X: not found\n"
        for cls in (builtin.Maigret, builtin.Sherlock):
            with patch.object(builtin, "find_binary", return_value="/bin/true"), patch.object(builtin, "run_cli", return_value=sample):
                r = cls().run("python")
            self.assertEqual(r["outputs"]["count"], 2)
            self.assertLess(r["confidence"], 0.5)
            self.assertIn("lead", r["warnings"][0])

    def test_harvester_uses_passive_sources_only(self):
        a = builtin.TheHarvester().args("/x/theHarvester", "example.com", "/tmp/o")
        self.assertEqual(a[a.index("-b") + 1], builtin.TheHarvester.PASSIVE_SOURCES)
        for active in ("bruteforce", "dnsbrute", "-c", "-t", "-s"):
            self.assertNotIn(active, a)

    def test_image_path_traversal_blocked(self):
        c = builtin.ImageMetadata(_tmp)
        for bad in ("/etc/passwd", "../x.jpg"):
            with self.assertRaises(policy.PolicyError): c.normalise(bad)
        with self.assertRaises(Exception): c.run("missing.jpg")

    def test_phone_offline(self):
        r = builtin.PhoneParse().run("+14155552671")
        self.assertEqual(r["outputs"]["region"], "US")
        self.assertEqual(r["source_references"], ["offline:libphonenumber"])

    def test_execute_contract(self):
        with patch.dict(registry.REGISTRY, {"fake": Fake()}):
            r = registry.execute("fake", "Example.com", "Authorized brand-protection review")
        self.assertTrue(r["requires_human_review"])
        self.assertEqual(r["target"], "example.com")
        for k in ("job_id", "outputs", "source_references", "confidence", "warnings", "sha256"):
            self.assertIn(k, r)

    def test_username_requires_acknowledgment(self):
        with patch.dict(registry.REGISTRY, {"fakeuser": FakeUser()}):
            with self.assertRaises(policy.PolicyError):
                registry.execute("fakeuser", "someone", "Authorized brand-protection review")
            self.assertTrue(registry.execute("fakeuser", "someone", "Authorized brand-protection review", True))


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        with SessionLocal() as db:
            c = Case(title="t"); db.add(c); db.commit(); cls.case_id = str(c.case_id)

    def post(self, body):
        return self.client.post(f"/api/v1/cases/{self.case_id}/osint/run", json=body, headers=H)

    def test_requires_api_key(self):
        self.assertEqual(self.client.get("/api/v1/osint/connectors").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/osint/connectors", headers=H).status_code, 200)

    def test_run_stores_proposed_evidence_and_audit(self):
        with patch.dict(registry.REGISTRY, {"fake": Fake()}):
            r = self.post({"connector": "fake", "target": "example.org", "purpose": "Authorized brand-protection review"})
        self.assertEqual(r.status_code, 201, r.text)
        with SessionLocal() as db:
            ev = db.get(Evidence, __import__("uuid").UUID(r.json()["evidence_id"]))
            self.assertEqual(ev.ingestion_status, "proposed")
            self.assertEqual(ev.chain_of_custody[0]["connector"], "fake")
            acts = [a.action for a in db.query(AuditEvent).all()]
        self.assertIn("osint.run", acts)

    def test_denied_and_unacknowledged_are_refused_and_audited(self):
        r = self.post({"connector": "holehe", "target": "a@b.com", "purpose": "Authorized brand-protection review"})
        self.assertEqual(r.status_code, 422)
        with patch.dict(registry.REGISTRY, {"fakeuser": FakeUser()}):
            r = self.post({"connector": "fakeuser", "target": "someone", "purpose": "Authorized brand-protection review"})
        self.assertEqual(r.status_code, 422)
        with SessionLocal() as db:
            self.assertGreaterEqual(db.query(AuditEvent).filter_by(action="osint.refused").count(), 2)

    def test_unknown_case_404(self):
        r = self.client.post("/api/v1/cases/00000000-0000-0000-0000-000000000000/osint/run", headers=H,
                             json={"connector": "fake", "target": "example.org", "purpose": "Authorized brand-protection review"})
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
