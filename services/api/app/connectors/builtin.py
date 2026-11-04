import json
import re
import tempfile
import time
import urllib.parse

import httpx

from . import policy
from .base import Connector, ConnectorError, find_binary, run_cli, tool_cmd

UA = "KAAL-ASE/2.0 (+https://redclove.space)"
FOUND_RE = re.compile(r"^\[\+\]\s+(.+?):\s+(https?://\S+)", re.M)


def _http_get(url: str, timeout: float = 20.0, **kw) -> httpx.Response:
    try:
        r = httpx.get(url, timeout=timeout, headers={"User-Agent": UA}, follow_redirects=False, **kw)
    except httpx.HTTPError as e:
        raise ConnectorError(f"source did not respond: {type(e).__name__}")
    if r.status_code >= 400:
        raise ConnectorError(f"source returned HTTP {r.status_code}")
    return r


class DnsRecords(Connector):
    name, kind, license, dist = "dns_records", "domain", "ISC (dnspython)", "dnspython"
    description = "Public DNS records: A, AAAA, MX, NS, TXT, CAA, SOA."

    def normalise(self, t): return policy.normalise_domain(t)

    def run(self, domain):
        import dns.exception
        import dns.resolver
        res = dns.resolver.Resolver()
        res.lifetime = res.timeout = 5.0
        out, warnings = {}, []
        for rtype in ("A", "AAAA", "MX", "NS", "TXT", "CAA", "SOA"):
            try:
                out[rtype] = sorted(r.to_text() for r in res.resolve(domain, rtype))
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
                continue
            except dns.exception.Timeout:
                warnings.append(f"{rtype} lookup timed out")
        if not out:
            warnings.append("No records returned. The domain may not exist.")
        return {"outputs": {"records": out}, "source_references": [f"dns://{domain}"],
                "confidence": 0.95 if out else 0.0, "warnings": warnings}


class Whois(Connector):
    name, kind, license, dist = "whois", "domain", "MIT (python-whois)", "python-whois"
    description = "Registrar, dates, name servers and status. Registrant personal data is deliberately dropped."

    def normalise(self, t): return policy.normalise_domain(t)

    def run(self, domain):
        import whois
        try:
            w = whois.whois(domain)
        except Exception as e:
            raise ConnectorError(f"WHOIS lookup failed: {type(e).__name__}")

        def flat(v):
            v = v if isinstance(v, (list, tuple, set)) else [v]
            return sorted({str(x) for x in v if x is not None})
        keep = {k: flat(w.get(k)) for k in ("registrar", "creation_date", "expiration_date", "updated_date",
                                             "name_servers", "status", "dnssec") if w.get(k)}
        return {"outputs": {"whois": keep},
                "source_references": [f"whois://{domain}"], "confidence": 0.9 if keep else 0.0,
                "warnings": ["Registrant names, emails and addresses are not collected."] + ([] if keep else ["No WHOIS data returned."])}


class CertTransparency(Connector):
    name, kind, license, dist = "cert_transparency", "domain", "Public log data (crt.sh)", ""
    description = "Subdomains seen in public Certificate Transparency logs via crt.sh."

    def normalise(self, t): return policy.normalise_domain(t)

    def run(self, domain):
        url = f"https://crt.sh/?q={urllib.parse.quote('%.' + domain)}&output=json"
        try:
            rows = _http_get(url, timeout=30).json()
        except ValueError:
            raise ConnectorError("crt.sh returned an unreadable response")
        names = set()
        for row in rows:
            for n in str(row.get("name_value", "")).split("\n"):
                n = n.strip().lower().lstrip("*.")
                if n == domain or n.endswith("." + domain):
                    names.add(n)
        names = sorted(names)[:300]
        return {"outputs": {"subdomains": names, "count": len(names)}, "source_references": [url],
                "confidence": 0.85 if names else 0.0,
                "warnings": ["A name in a certificate does not prove the host is live or in scope."]}


class Wayback(Connector):
    name, kind, license, dist = "wayback", "domain", "Public archive (Internet Archive CDX)", ""
    description = "Archived snapshots of a domain from the Internet Archive."

    def normalise(self, t): return policy.normalise_domain(t)

    def run(self, domain):
        q = urllib.parse.urlencode({"url": domain, "output": "json", "fl": "timestamp,original,statuscode",
                                    "filter": "statuscode:200", "collapse": "digest", "limit": 25})
        rows = _http_get(f"https://web.archive.org/cdx/search/cdx?{q}", timeout=30).json()
        snaps = [{"timestamp": ts, "url": f"https://web.archive.org/web/{ts}/{orig}"} for ts, orig, _ in rows[1:]]
        return {"outputs": {"snapshots": snaps, "count": len(snaps)}, "source_references": [s["url"] for s in snaps[:25]],
                "confidence": 0.9 if snaps else 0.0, "warnings": [] if snaps else ["No archived snapshots found."]}


class PhoneParse(Connector):
    name, kind, license, dist = "phone_parse", "phone", "Apache-2.0 (phonenumbers)", "phonenumbers"
    description = "Offline validity, country and region for a phone number. No subscriber lookup."

    def normalise(self, t): return policy.normalise_phone(t)

    def run(self, number):
        import phonenumbers
        from phonenumbers import geocoder, number_type
        try:
            n = phonenumbers.parse(number, None)
        except phonenumbers.NumberParseException:
            raise ConnectorError("Could not parse that number.")
        out = {"e164": phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164),
               "valid": phonenumbers.is_valid_number(n), "possible": phonenumbers.is_possible_number(n),
               "country_code": n.country_code, "region": phonenumbers.region_code_for_number(n),
               "area": geocoder.description_for_number(n, "en"), "type": str(number_type(n))}
        return {"outputs": out, "source_references": ["offline:libphonenumber"], "confidence": 0.9 if out["valid"] else 0.2,
                "warnings": ["Offline parsing only. This says nothing about who holds the number."]}


class ImageMetadata(Connector):
    name, kind, license, dist = "image_metadata", "image", "ExifTool (Artistic/GPL) when installed, else BSD-3 (ExifRead)", "ExifRead"
    description = ("Metadata from an image already registered as evidence. Uses ExifTool when installed (far more complete: "
                   "maker notes, XMP, IPTC, video), otherwise falls back to ExifRead. GPS is flagged, not mapped to a person.")

    def __init__(self, evidence_dir: str):
        self.evidence_dir = evidence_dir

    def normalise(self, t):
        t = (t or "").strip()
        if not t or t.startswith("/") or ".." in t.split("/"):
            raise policy.PolicyError("Give a filename inside the evidence store (no absolute paths or '..').")
        return t

    def _resolve(self, filename):
        import pathlib
        root = pathlib.Path(self.evidence_dir).resolve()
        path = (root / filename).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ConnectorError("File not found in the evidence store.")
        return path

    def _exiftool(self, exe, path):
        text = run_cli([exe, "-j", "-G1", "-n", "-api", "largefilesupport=1", "--", str(path)], 60, stdout_only=True)
        try:
            row = json.loads(text)[0]
        except (ValueError, IndexError):
            raise ConnectorError("exiftool produced no readable output")
        drop = ("SourceFile", "System:", "ExifTool:")       # server paths, permissions, tool noise
        return {k: str(v)[:300] for k, v in list(row.items())[:600] if not k.startswith(drop)}

    def _exifread(self, path):
        import exifread
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)
        return {k: str(v)[:200] for k, v in tags.items() if not k.startswith("Thumbnail") and k != "JPEGThumbnail"}

    def run(self, filename):
        path = self._resolve(filename)
        exe = find_binary("exiftool", "EXIFTOOL_BIN")
        engine, keep = ("exiftool", self._exiftool(exe, path)) if exe else ("exifread", self._exifread(path))
        has_gps = any("GPS" in k for k in keep)
        w = ["GPS coordinates present: handle as sensitive and review before sharing."] if has_gps else []
        if engine == "exifread":
            w.append("ExifTool is not installed, so only basic EXIF was read. Install exiftool for full metadata.")
        return {"outputs": {"tags": keep, "has_gps": has_gps, "engine": engine, "tag_count": len(keep)},
                "source_references": [f"evidence://{filename}"],
                "confidence": 0.95 if keep else 0.0, "warnings": w + ([] if keep else ["No metadata found."])}


class _UsernameCli(Connector):
    kind = "username"
    people_adjacent = True
    binary = ""
    timeout = 120

    def available(self): return tool_cmd(self.binary) is not None
    def normalise(self, t): return policy.normalise_username(t)
    def args(self, cmd, username): raise NotImplementedError

    def run(self, username):
        bin_ = tool_cmd(self.binary)
        if not bin_:
            raise ConnectorError(f"{self.binary} is not installed")
        text = run_cli(self.args(bin_, username), self.timeout)
        seen, profiles = set(), []
        for site, url in FOUND_RE.findall(text.replace("\r", "\n")):  # Maigret prefixes result lines with \r
            if url not in seen:
                seen.add(url)
                profiles.append({"site": site.strip(), "url": url})
        return {"outputs": {"profiles": profiles, "count": len(profiles)}, "source_references": [p["url"] for p in profiles],
                "confidence": 0.35 if profiles else 0.0,
                "warnings": ["A matching username on a site is a lead, not proof of the same person. Verify before use."]}


class Maigret(_UsernameCli):
    name, license, dist, binary = "maigret", "MIT", "maigret", "maigret"
    description = "Username search across the top public sites (Maigret)."

    def args(self, b, u):
        return [*b, u, "--no-progressbar", "--no-color", "--timeout", "10", "--top-sites", "150", "--no-recursion",
                "--folderoutput", tempfile.mkdtemp(prefix="kaal-maigret-")]


class Sherlock(_UsernameCli):
    name, license, dist, binary = "sherlock", "MIT", "sherlock-project", "sherlock"
    description = "Username search across public social sites (Sherlock)."

    def args(self, b, u):
        return [*b, u, "--print-found", "--no-color", "--timeout", "10", "--folderoutput", tempfile.mkdtemp(prefix="kaal-sherlock-")]


class TheHarvester(Connector):
    """Opt-in. theHarvester is GPL-2.0, so it is run as a separate program and never imported or copied."""
    name, kind, license = "theharvester", "domain", "GPL-2.0 (run as external program)"
    description = "Passive-source domain recon (hosts, emails) via theHarvester. Needs THEHARVESTER_BIN set."
    PASSIVE_SOURCES = "crtsh,hackertarget,rapiddns,threatminer,urlscan,otx"
    timeout = 180

    def available(self): return find_binary("theHarvester", "THEHARVESTER_BIN") is not None
    def normalise(self, t): return policy.normalise_domain(t)

    def args(self, bin_, domain, out_base):
        return [bin_, "-d", domain, "-b", self.PASSIVE_SOURCES, "-l", "200", "-f", out_base]

    def run(self, domain):
        bin_ = find_binary("theHarvester", "THEHARVESTER_BIN")
        if not bin_:
            raise ConnectorError("theHarvester is not installed. Set THEHARVESTER_BIN to its executable.")
        out_base = tempfile.mkdtemp(prefix="kaal-harvest-") + "/out"
        run_cli(self.args(bin_, domain, out_base), self.timeout)
        try:
            data = json.load(open(out_base + ".json"))
        except (OSError, ValueError):
            raise ConnectorError("theHarvester produced no readable output")
        hosts = sorted({h.split(":")[0].lower() for h in data.get("hosts", []) if domain in h.lower()})[:300]
        emails = sorted({e.lower() for e in data.get("emails", []) if e.lower().endswith("@" + domain)})[:100]
        return {"outputs": {"hosts": hosts, "emails": emails}, "source_references": [f"theharvester://{domain}"],
                "confidence": 0.6 if (hosts or emails) else 0.0,
                "warnings": ["Passive sources only. Emails found are for the target domain and need analyst review."]}


class WikipediaBriefing(Connector):
    name, kind, license, dist = "wikipedia_briefing", "topic", "CC BY-SA content; extractive, quotes with permalinks", ""
    description = "Sourced briefing on a public topic: verbatim sentences with revision permalinks. Refuses pages about people."

    def normalise(self, t): return policy.normalise_topic(t)

    def run(self, question):
        from . import _briefing
        try:
            res = _briefing.run(question)
        except ValueError as e:
            raise policy.PolicyError(str(e))
        except Exception:
            raise ConnectorError("A public source did not respond.")
        if res["refused"]:
            raise policy.PolicyError(res["warnings"][0])
        claims = res["claims"]
        conf = sum(c["confidence"] for c in claims) / len(claims) if claims else 0.0
        return {"outputs": {"claims": claims}, "source_references": sorted({c["source_url"] for c in claims}),
                "confidence": conf, "warnings": res["warnings"]}
