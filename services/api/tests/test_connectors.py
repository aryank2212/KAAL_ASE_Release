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
        with self.assertRaises(policy.PolicyError):
            policy.check_denied("private_account")
        for n in ("holehe", "ghunt", "face_compare"):   # enabled in 2.1.0, behind the gates
            policy.check_denied(n)

    def test_email(self):
        self.assertEqual(policy.normalise_email(" Jane.Doe@Example.COM "), "jane.doe@example.com")
        for bad in ("a@b", "a b@example.com", "x@y@example.com", "", "a@example.com, b@example.com"):
            with self.assertRaises(policy.PolicyError, msg=bad):
                policy.normalise_email(bad)

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
                         "maigret", "sherlock", "theharvester", "wikipedia_briefing",
                         "holehe", "ghunt", "face_locate", "face_compare"} <= names)
        self.assertFalse(names & set(policy.DENIED))

    def test_sensitive_connectors_require_acknowledgment(self):
        for n in ("holehe", "ghunt", "face_compare"):
            self.assertTrue(registry.REGISTRY[n].people_adjacent, n)
        self.assertFalse(registry.REGISTRY["face_locate"].people_adjacent)

    def test_holehe_output_parsed(self):
        from app.connectors import sensitive
        sample = "[+] Email used, [-] Email not used, [x] Rate limit\n\r[+] twitter.com\n\r[+] adobe.com\n[-] nope.com\n[x] flaky.com\n[+] adobe.com\n"
        with patch.object(sensitive, "find_binary", return_value="/bin/true"), patch.object(sensitive, "run_cli", return_value=sample):
            r = sensitive.Holehe().run("a@example.com")
        self.assertEqual(r["outputs"]["services"], ["adobe.com", "twitter.com"])
        self.assertEqual((r["outputs"]["checked"], r["outputs"]["failed"]), (4, 1))
        self.assertIn("lead", r["warnings"][0])
        self.assertIn("not proof", r["warnings"][-1])

    def test_holehe_total_failure_is_an_error_not_an_empty_result(self):
        from app.connectors import sensitive
        from app.connectors.base import ConnectorError
        sample = "".join(f"[x] site{i}.com\n" for i in range(40))
        with patch.object(sensitive, "find_binary", return_value="/bin/true"), patch.object(sensitive, "run_cli", return_value=sample):
            with self.assertRaises(ConnectorError) as cm:
                sensitive.Holehe().run("a@example.com")
        self.assertIn("NOT a negative result", str(cm.exception))

    def test_ghunt_needs_login_before_running(self):
        from app.connectors import sensitive
        g = sensitive.Ghunt()
        with patch.dict(os.environ, {"GHUNT_CREDS": "/nonexistent/creds.m"}), patch.object(sensitive, "find_binary", return_value="/bin/true"):
            self.assertIn("ghunt login", g.setup_hint())
            with patch.dict(registry.REGISTRY, {"ghunt": g}), self.assertRaises(Exception) as cm:
                registry.execute("ghunt", "a@example.com", "Authorized brand-protection review", True)
            self.assertIn("needs setup", str(cm.exception))

    def test_face_compare_input_rules(self):
        from app.connectors import sensitive
        fc = sensitive.FaceCompare(_tmp)
        for bad in ("a.jpg", "a.jpg,a.jpg", "a.jpg,b.jpg,c.jpg", "../x.jpg,b.jpg", "/etc/passwd,b.jpg"):
            with self.assertRaises(policy.PolicyError, msg=bad):
                fc.normalise(bad)
        self.assertEqual(fc.normalise("a.jpg, b.jpg"), "a.jpg,b.jpg")

    def test_face_model_checksums_pinned(self):
        from app.connectors import sensitive
        self.assertEqual(len(sensitive.MODEL_SHA256), 2)
        self.assertTrue(all(len(h) == 64 for h in sensitive.MODEL_SHA256.values()))

    def test_username_cli_output_parsed(self):
        sample = "[*] Checking\n\r[+] GitHub: https://github.com/python\n[+] GitHub: https://github.com/python\n[+] Reddit: https://www.reddit.com/user/python\n[-] X: not found\n"
        for cls in (builtin.Maigret, builtin.Sherlock):
            with patch.object(builtin, "tool_cmd", return_value=["/bin/true"]), patch.object(builtin, "run_cli", return_value=sample):
                r = cls().run("python")
            self.assertEqual(r["outputs"]["count"], 2)
            self.assertLess(r["confidence"], 0.5)
            self.assertIn("lead", r["warnings"][0])

    def test_frozen_build_reruns_itself_as_the_tool(self):
        from app.connectors import base
        with patch.object(base, "find_binary", return_value=None), patch.object(base.sys, "frozen", True, create=True):
            self.assertEqual(base.tool_cmd("maigret"), [base.sys.executable, "--run-tool", "maigret"])
            self.assertEqual(base.tool_cmd("sherlock")[-1], "sherlock_project")
            self.assertIsNone(base.tool_cmd("holehe"))
        with patch.object(base, "find_binary", return_value=None):
            self.assertIsNone(base.tool_cmd("maigret"))

    def test_harvester_uses_passive_sources_only(self):
        a = builtin.TheHarvester().args("/x/theHarvester", "example.com", "/tmp/x.tmp/o")
        self.assertEqual(a[a.index("-b") + 1], builtin.TheHarvester.PASSIVE_SOURCES)
        for active in ("bruteforce", "dnsbrute", "-c", "-t", "-s", "-n", "-r", "-a"):
            self.assertNotIn(active, a)
        self.assertTrue(a[a.index("-f") + 1].endswith(".rpt"), "explicit extension protects against dots in the path")

    def test_harvester_parse_normalises_and_filters(self):
        data = {"hosts": ["*.example.com", "*.example.com:198.54.14.52", "www.Example.com:93.184.216.34", "evil.org:1.2.3.4",
                          "notexample.com", "a.b.example.com"], "emails": ["Info@Example.com", "x@other.com"],
                "ips": ["93.184.216.34", "93.184.216.34", "1.1.1.1"], "asns": ["AS15133"]}
        o = builtin.TheHarvester.parse(data, "example.com")
        self.assertEqual(o["hosts"], ["a.b.example.com", "example.com", "www.example.com"])
        self.assertEqual(o["total_hosts"], 3)
        self.assertEqual(o["host_ips"]["www.example.com"], ["93.184.216.34"])
        self.assertEqual(o["host_ips"]["example.com"], ["198.54.14.52"])
        self.assertEqual(o["emails"], ["info@example.com"])
        self.assertEqual(o["ips"], ["1.1.1.1", "93.184.216.34"])

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
