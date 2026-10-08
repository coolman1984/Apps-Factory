import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
from af_license import clock_rolled_back, fingerprint, generate_keypair, issue, verify  # noqa: E402

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
CLAIMS = {"licence_id": "LIC-0001", "product": "hessa-centre", "customer": "مركز تجريبي (SYNTHETIC)",
          "edition": "office", "features": ["receipts", "reports"], "seats": 5,
          "issued": "2026-10-01T00:00:00Z", "expires": "2026-11-01T00:00:00Z", "grace_days": 7}


class LicenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pem, cls.pub, cls.kid = generate_keypair()
        cls.upd_pem, cls.upd_pub, cls.upd_kid = generate_keypair()
        cls.keys = {cls.kid: cls.pub}

    def doc(self, **changes):
        claims = dict(CLAIMS, **changes)
        return issue(self.pem, "licence", claims)

    def check(self, doc, when=NOW, **kw):
        return verify(doc, self.keys, "licence", "hessa-centre", now=when, **kw)

    def test_valid_licence_with_arabic_customer(self):
        r = self.check(self.doc())
        self.assertTrue(r.full_access)
        self.assertEqual(r.claims["customer"], CLAIMS["customer"])

    def test_any_edit_breaks_signature(self):
        for field, value in (("expires", "2036-01-01T00:00:00Z"), ("seats", 500), ("features", ["all"])):
            with self.subTest(field=field):
                d = self.doc()
                d["payload"][field] = value
                self.assertEqual(self.check(d).reason, "bad_signature")

    def test_algorithm_and_format_are_fixed(self):
        d = self.doc()
        d["alg"] = "none"
        self.assertEqual(self.check(d).reason, "unexpected_algorithm")
        d = self.doc()
        d["format"] = "other"
        self.assertFalse(self.check(d).valid)

    def test_unknown_key_and_wrong_product(self):
        self.assertEqual(verify(self.doc(), {}, "licence", "hessa-centre", now=NOW).reason, "unknown_key")
        self.assertEqual(verify(self.doc(), self.keys, "licence", "trip-orders", now=NOW).reason, "wrong_product")

    def test_update_key_cannot_mint_licences(self):
        forged = issue(self.upd_pem, "update", dict(CLAIMS))
        forged["purpose"] = "licence"
        keys = {self.kid: self.pub, self.upd_kid: self.upd_pub}
        self.assertFalse(verify(forged, keys, "licence", "hessa-centre", now=NOW).valid)
        # licence app trusts only licence keys, so a genuine update document is also refused
        self.assertEqual(verify(issue(self.upd_pem, "update", dict(CLAIMS)), self.keys, "licence",
                                "hessa-centre", now=NOW).reason, "wrong_purpose")

    def test_expiry_grace_and_safe_degradation(self):
        self.assertEqual(self.check(self.doc(), when=datetime(2026, 11, 5, tzinfo=timezone.utc)).state, "grace")
        late = self.check(self.doc(), when=datetime(2026, 12, 1, tzinfo=timezone.utc))
        self.assertTrue(late.valid)
        self.assertEqual(late.state, "expired")
        self.assertFalse(late.full_access)  # app switches to read/export/backup, never deletes data

    def test_device_binding(self):
        dev = fingerprint("machine-guid-123", "install-abc")
        d = self.doc(devices=[dev])
        self.assertTrue(self.check(d, device_id=dev).full_access)
        self.assertEqual(self.check(d, device_id=fingerprint("other")).reason, "device_not_licensed")

    def test_garbage_never_raises(self):
        for junk in (None, [], {"format": "af-signed/1"}, {**self.doc(), "sig": "!!"}, {**self.doc(), "payload": "x"}):
            with self.subTest(junk=str(junk)[:30]):
                self.assertFalse(self.check(junk).valid)

    def test_missing_claims_refused_at_issue(self):
        with self.assertRaises(ValueError):
            issue(self.pem, "licence", {"product": "hessa-centre"})

    def test_clock_rollback(self):
        self.assertTrue(clock_rolled_back(NOW - timedelta(days=3), NOW))
        self.assertFalse(clock_rolled_back(NOW - timedelta(hours=2), NOW))

    def test_cli_round_trip(self):
        cli = [sys.executable, "-m", "af_license"]
        with tempfile.TemporaryDirectory() as d:
            run = lambda *a: subprocess.run(cli + list(a), cwd=PKG, capture_output=True, text=True)  # noqa: E731
            out = run("keygen", "--purpose", "licence", "--out-dir", d)
            self.assertEqual(out.returncode, 0, out.stderr)
            private = next(Path(d).glob("*.private.pem"))
            public = next(Path(d).glob("*.public.txt")).read_text().strip()
            claims = Path(d) / "claims.json"
            far = dict(CLAIMS, expires="2099-01-01T00:00:00Z")
            claims.write_text(json.dumps(far, ensure_ascii=False), encoding="utf-8")
            lic = Path(d) / "lic.json"
            self.assertEqual(run("issue", "--key", str(private), "--purpose", "licence",
                                 "--claims", str(claims), "--output", str(lic)).returncode, 0)
            ok = run("verify", str(lic), "--public", public, "--purpose", "licence", "--product", "hessa-centre")
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            tampered = json.loads(lic.read_text(encoding="utf-8"))
            tampered["payload"]["seats"] = 99
            lic.write_text(json.dumps(tampered), encoding="utf-8")
            bad = run("verify", str(lic), "--public", public, "--purpose", "licence", "--product", "hessa-centre")
            self.assertEqual(bad.returncode, 2)
            self.assertIn("bad_signature", bad.stdout)


if __name__ == "__main__":
    unittest.main()
