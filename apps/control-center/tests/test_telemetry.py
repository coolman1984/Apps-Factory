"""Control Center telemetry: signed ingest (direct and through the relay), the firm limits again on arrival,
incidents, per-person usage, guide funnel, problem reports as tickets, the 11 alert rules, parallel fan-out to every
enabled channel with a per-channel log, settings without secrets, retention."""
import base64
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
sys.path[:0] = [str(APP), str(ROOT / "packages" / "af-license"), str(ROOT / "packages" / "af-telemetry"),
                str(ROOT / "packages" / "af-consent")]
from fastapi.testclient import TestClient  # noqa: E402

import af_consent  # noqa: E402
import af_telemetry  # noqa: E402
from control_center import alerts, db, telemetry  # noqa: E402
from control_center.app import create_app  # noqa: E402
from control_center.security import new_token, token_hash  # noqa: E402

AR = "consent.help.remote.ar.v1"
REAL_CHANNELS = list(alerts.CHANNELS)


class Product:
    """A product-side af-telemetry outbox with full consent, used to make real signed batches."""

    def __init__(self, install_id, token, product="hessa-centre", version="1.4.1", people=("u1",)):
        cdb = sqlite3.connect(":memory:")
        cdb.executescript(af_consent.SQL)
        consent = af_consent.Consent(cdb)
        consent.record("install", None, "agree", AR, "ar", by="owner")
        for p in people:
            consent.record("person", p, "agree", AR, "ar", by=p)
        self.tmp = tempfile.mkdtemp()
        self.tel = af_telemetry.Telemetry(Path(self.tmp) / "t.db", install_id, "pc1", product, version, "practice",
                                          "secret-" + install_id, consent)
        self.token = token

    def batch(self, ts=None, nonce=None, events=None):
        if events is not None:
            import gzip
            body = gzip.compress(json.dumps(events).encode())
            ids = []
        else:
            ids, body = self.tel.batch()
        ts = str(int(ts if ts is not None else time.time()))
        nonce = nonce or os.urandom(12).hex()
        headers = {"X-AF-Install": self.tel.install_id, "X-AF-Timestamp": ts, "X-AF-Nonce": nonce,
                   "X-AF-Signature": af_telemetry.sign(self.token, ts, nonce, body), "Content-Encoding": "identity"}
        return ids, body, headers


class Recorder(alerts.Channel):
    def __init__(self, name, delay=0.0, fail=False, configured=True, default_on=True):
        self.name, self.delay, self.fail, self._configured, self.default_on = name, delay, fail, configured, default_on
        self.got = []

    def configured(self):
        return self._configured

    def send(self, alert):
        time.sleep(self.delay)
        if self.fail:
            raise ConnectionError("provider down")
        self.got.append(alert)
        return "ok"


class Base(unittest.TestCase):
    def setUp(self):
        for k in list(os.environ):
            if k.startswith(("CC_SMTP", "CC_ALERT", "CC_WA_", "CC_TG_", "CC_LINKEDIN")):
                del os.environ[k]
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(str(Path(self.tmp.name) / "cc.db"))
        self.conn = self.app.state.conn
        self.c = TestClient(self.app)
        self.owner = new_token("ven")
        self.conn.execute("INSERT INTO vendor_tokens (id, name, token_hash, kind, created_at) VALUES (?,?,?,?,?)",
                          (db.uuid7(), "المالك", token_hash(self.owner), "owner", db.now_iso()))
        self.O = {"Authorization": "Bearer " + self.owner}
        self.cid = self.c.post("/api/customers", json={"name": "سنتر تجريبي"}, headers=self.O).json()["id"]
        self.p1 = self.product()
        self.quiet = mock.patch.object(alerts, "CHANNELS", [alerts.DashboardChannel()])
        self.quiet.start()

    def tearDown(self):
        self.quiet.stop()
        self.conn.close()
        self.tmp.cleanup()

    def product(self, **kw):
        r = self.c.post("/api/installs", json={"customer_id": self.cid, "product": "hessa-centre", "tier": "office_server"},
                        headers=self.O).json()
        return Product(r["id"], r["install_token"], **kw)

    def send(self, p, **kw):
        ids, body, headers = p.batch(**kw)
        r = self.c.post("/api/agent/events", content=body, headers=headers)
        if r.status_code == 202:
            p.tel.mark_sent(ids)
        return r


class Ingest(Base):
    def test_signed_batch_is_stored(self):
        t = self.p1.tel
        t.emit("use.page", {"page": "sell"}, user="u1", role="cashier")
        t.emit("guide.start", {"guide": "open-shift"}, user="u1")
        t.emit("hb", {"error_count": 0})
        r = self.send(self.p1)
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["stored"], 3)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 3)
        self.assertEqual(t.pending(), [])

    def test_bad_batches_are_refused(self):
        self.p1.tel.emit("hb", {})
        _, body, h = self.p1.batch()
        bad_sig = dict(h, **{"X-AF-Signature": "0" * 64})
        self.assertEqual(self.c.post("/api/agent/events", content=body, headers=bad_sig).status_code, 401)
        old = self.p1.batch(ts=time.time() - 400)
        self.assertEqual(self.c.post("/api/agent/events", content=old[1], headers=old[2]).status_code, 401)
        self.assertEqual(self.c.post("/api/agent/events", content=body, headers=h).status_code, 202)
        self.assertEqual(self.c.post("/api/agent/events", content=body, headers=h).status_code, 409, "nonce replay")
        stranger = dict(h, **{"X-AF-Install": db.uuid7()})
        self.assertEqual(self.c.post("/api/agent/events", content=body, headers=stranger).status_code, 401)
        _, junk, jh = self.p1.batch()
        self.assertEqual(self.c.post("/api/agent/events", content=b"not gzip", headers=dict(
            jh, **{"X-AF-Signature": af_telemetry.sign(self.p1.token, jh["X-AF-Timestamp"], jh["X-AF-Nonce"], b"not gzip")})).status_code, 400)

    def test_firm_limits_checked_again_on_arrival(self):
        p2 = self.product()
        good = {"v": 1, "id": af_telemetry.uuid7(), "install_id": self.p1.tel.install_id, "node": "pc1", "product": "hessa-centre",
                "version": "1.4.1", "env": "practice", "ts": db.now_iso(), "type": "use.page", "sev": "info", "anon": False,
                "subject": "p_" + "a" * 16, "role": "cashier", "page": "sell", "data": {"page": "sell", "count": 2}}
        forged = [
            dict(good, id=af_telemetry.uuid7(), data={"page": "sell", "name": "Ahmed"}),
            dict(good, id=af_telemetry.uuid7(), data={"page": "01012345678"}),
            dict(good, id=af_telemetry.uuid7(), subject="Ahmed Ali"),
            dict(good, id=af_telemetry.uuid7(), install_id=p2.tel.install_id),
            dict(good, id=af_telemetry.uuid7(), extra=1),
            dict(good, id=af_telemetry.uuid7(), type="keylog", data={}),
            dict(good, id=af_telemetry.uuid7(), type="fb.problem", data={"text": "اتصل بي 01012345678 a@b.com"}),
        ]
        r = self.send(self.p1, events=[good] + forged)
        self.assertEqual(r.json(), {"stored": 2, "duplicates": 0, "rejected": 6, "alerts": 1})
        ticket = self.conn.execute("SELECT message FROM tickets").fetchone()[0]
        self.assertNotIn("01012345678", ticket)
        self.assertNotIn("a@b.com", ticket)
        stored = json.dumps([dict(r) for r in self.conn.execute("SELECT * FROM events")], ensure_ascii=False)
        self.assertNotIn("Ahmed", stored)
        r = self.send(self.p1, events=[good])
        self.assertEqual(r.json()["duplicates"], 1)

    def test_dashboard_views(self):
        t = self.p1.tel
        for _ in range(3):
            t.emit("use.page", {"page": "sell"}, user="u1")
        t.emit("use.action", {"action": "sale.pay", "page": "sell"}, user="u1")
        t.emit("guide.start", {"guide": "open-shift"}, user="u1")
        t.emit("guide.done", {"guide": "open-shift"}, user="u1")
        t.emit("guide.start", {"guide": "close-shift"}, user="u1")
        t.emit("guide.abandon", {"guide": "close-shift", "step": 3}, user="u1")
        t.feedback("idea", "زر أكبر للدفع", page="sell", user="u1")
        self.send(self.p1)
        use = self.c.get("/api/usage", headers=self.O).json()
        self.assertEqual(len(use["people"]), 1)
        self.assertRegex(use["people"][0]["subject"], r"^p_[0-9a-f]{16}$")
        self.assertEqual(use["people"][0]["actions"], 4)
        self.assertIn({"type": "use.page", "item": "sell", "count": 3, "people": 1}, use["items"])
        funnel = {g["guide"]: g for g in self.c.get("/api/guides/funnel", headers=self.O).json()}
        self.assertEqual(funnel["open-shift"]["completion"], 1.0)
        self.assertEqual(funnel["close-shift"]["completion"], 0.0)
        self.assertEqual(funnel["close-shift"]["abandon"], 1)
        rel = self.c.get("/api/releases", headers=self.O).json()
        self.assertEqual(rel[0]["version"], "1.4.1")
        self.assertGreater(rel[0]["practice_events"], 0)
        inbox = self.c.get("/api/feedback", headers=self.O).json()
        self.assertEqual(inbox[0]["bundle"]["kind"], "fb.idea")
        self.assertTrue(inbox[0]["untrusted_text"])
        html = self.c.get("/").text
        for section in ("alertsTitle", "incTitle", "useTitle", "funnelTitle", "fbTitle", "chTitle", "relTitle"):
            self.assertIn(section, html)
        self.assertNotIn("innerHTML", html)


class Rules(Base):
    def error(self, p, fp="fp1", n=1):
        for _ in range(n):
            p.tel.emit("err.server", {"code": "KeyError", "fingerprint": fp, "where": "sales:pay"})

    def test_incidents_and_error_rules(self):
        self.error(self.p1)
        self.send(self.p1)
        inc = self.c.get("/api/incidents", headers=self.O).json()
        self.assertEqual((len(inc), inc[0]["count"], inc[0]["code"]), (1, 1, "KeyError"))
        rules = [a["rule"] for a in self.c.get("/api/alerts", headers=self.O).json()]
        self.assertEqual(rules, ["new_incident"])
        self.error(self.p1)
        self.send(self.p1)
        self.assertEqual(len(self.c.get("/api/alerts", headers=self.O).json()), 1, "same incident: no new alert")
        others = [self.product(), self.product()]
        for p in others:
            self.error(p)
            self.send(p)
        rules = sorted(a["rule"] for a in self.c.get("/api/alerts", headers=self.O).json())
        self.assertIn("incident_spread", rules)
        self.error(self.p1, n=1)
        for _ in range(17):
            self.p1.tel.emit("err.server", {"code": "KeyError", "fingerprint": "fp1", "where": "sales:pay"})
        self.send(self.p1)
        rules = [a["rule"] for a in self.c.get("/api/alerts", headers=self.O).json()]
        self.assertIn("incident_spike", rules)
        iid = self.c.get("/api/incidents", headers=self.O).json()[0]["id"]
        self.assertEqual(self.c.post(f"/api/incidents/{iid}", json={"status": "fixed"}, headers=self.O).status_code, 200)

    def test_event_rules(self):
        t = self.p1.tel
        t.emit("upgrade.fail", {"from": "1.4.0", "to": "1.4.1", "code": "disk"})
        t.emit("backup.fail", {"code": "locked"})
        t.emit("sync.fail", {"code": "peer_down", "count": 3})
        t.emit("lic.state_change", {"from": "active", "to": "grace"})
        t.feedback("problem", "الطابعة لا تطبع", page="sell")
        for _ in range(10):
            t.emit("deny", {"perm": "sales.refund", "page": "sell"}, user="u1")
        self.send(self.p1)
        rules = {a["rule"] for a in self.c.get("/api/alerts", headers=self.O).json()}
        self.assertEqual(rules, {"upgrade_failed", "backup_failed", "sync_failing", "licence_attention", "problem_report",
                                 "permission_friction"})

    def test_time_rules_and_retention(self):
        self.p1.tel.emit("hb", {"error_count": 0})
        self.send(self.p1)
        later = datetime.now(timezone.utc) + timedelta(hours=30)
        fired = {a["rule"] for a in alerts.periodic(self.conn, now=later)}
        self.assertEqual(fired, {"silent_install", "backup_stale"})
        self.assertEqual(alerts.periodic(self.conn, now=later), [], "deduplicated")
        self.assertEqual(len(alerts.RULES), 11)
        far = datetime.now(timezone.utc) + timedelta(days=400)
        out = telemetry.retention(self.conn, now=far)
        self.assertGreaterEqual(out["events"], 1)
        self.assertGreaterEqual(out["alerts"], 2)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM alert_deliveries").fetchone()[0], 0)

    def test_rules_can_be_switched_off(self):
        alerts.save_settings(self.conn, rules={"new_incident": {"on": False}})
        self.error(self.p1)
        self.send(self.p1)
        self.assertEqual(self.c.get("/api/alerts", headers=self.O).json(), [])


class FanOut(Base):
    def test_all_enabled_channels_in_parallel_and_failures_isolated(self):
        ok, slow, broken = Recorder("email"), Recorder("whatsapp", delay=0.6), Recorder("telegram", fail=True)
        slow2 = Recorder("linkedin", delay=0.6)
        off = Recorder("pager", configured=False)
        chans = [alerts.DashboardChannel(), ok, slow, broken, slow2, off]
        t0 = time.monotonic()
        a = alerts.raise_alert(self.conn, "backup_failed", self.p1.tel.install_id, "test", "k1", channels=chans)
        took = time.monotonic() - t0
        self.assertLess(took, 1.1, "two 0.6 s channels ran at the same time")
        status = {d["channel"]: d["status"] for d in a["deliveries"]}
        self.assertEqual(status, {"dashboard": "sent", "email": "sent", "whatsapp": "sent", "telegram": "failed",
                                  "linkedin": "sent", "pager": "disabled"})
        self.assertEqual(len(ok.got), 1)
        logged = {d["channel"]: d for d in self.c.get("/api/alerts", headers=self.O).json()[0]["deliveries"]}
        self.assertEqual(logged["telegram"]["status"], "failed")
        self.assertIn("provider down", logged["telegram"]["detail"])
        self.assertGreaterEqual(logged["whatsapp"]["ms"], 500)

    def test_a_hung_channel_does_not_block_the_others(self):
        hung = Recorder("whatsapp", delay=3)
        ok = Recorder("email")
        with mock.patch.object(alerts, "TIMEOUT_S", 0):
            t0 = time.monotonic()
            with mock.patch("control_center.alerts.wait", side_effect=lambda fs, timeout: __import__(
                    "concurrent.futures").futures.wait(fs, timeout=0.5)):
                a = alerts.raise_alert(self.conn, "backup_failed", None, "x", "k2", channels=[ok, hung])
            self.assertLess(time.monotonic() - t0, 2)
        status = {d["channel"]: d["status"] for d in a["deliveries"]}
        self.assertEqual(status, {"email": "sent", "whatsapp": "failed"})
        self.assertEqual(len(ok.got), 1)

    def test_real_adapters_with_fake_transports(self):
        os.environ.update({"CC_SMTP_HOST": "smtp.example", "CC_ALERT_EMAIL_FROM": "cc@example.com",
                           "CC_ALERT_EMAIL_TO": "owner@example.com", "CC_WA_TOKEN": "wa-secret-token",
                           "CC_WA_PHONE_NUMBER_ID": "123", "CC_WA_TO": "201000000000", "CC_WA_TEMPLATE": "cc_alert",
                           "CC_TG_BOT_TOKEN": "tg-secret", "CC_TG_CHAT_ID": "42", "CC_LINKEDIN_TOKEN": "li-secret"})
        sent_mail, posts = [], []

        class FakeSMTP:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def starttls(self, **k): pass
            def login(self, *a): pass
            def send_message(self, m): sent_mail.append(m)
        try:
            with mock.patch.object(alerts, "CHANNELS", REAL_CHANNELS), \
                    mock.patch("smtplib.SMTP", FakeSMTP), \
                    mock.patch.object(alerts, "_post_json", lambda url, body, h: posts.append((url, body)) or 200):
                a = alerts.raise_alert(self.conn, "problem_report", None, "تجربة", "k3")
                status = {d["channel"]: d["status"] for d in a["deliveries"]}
                self.assertEqual(status, {"dashboard": "sent", "email": "sent", "whatsapp": "sent",
                                          "telegram": "disabled", "linkedin": "disabled"},
                                 "Telegram and LinkedIn stay off until switched on")
                self.assertEqual(sent_mail[0]["To"], "owner@example.com")
                self.assertEqual(posts[0][1]["type"], "template")
                self.assertEqual(posts[0][1]["template"]["name"], "cc_alert")
                r = self.c.put("/api/alert-settings", json={"channels": {"telegram": True, "linkedin": True}}, headers=self.O)
                self.assertEqual(r.status_code, 200, r.text)
                self.assertNotIn("secret", r.text)
                a = self.c.post("/api/alerts/test", headers=self.O).json()
                status = {d["channel"]: d["status"] for d in a["deliveries"]}
                self.assertEqual(status["telegram"], "sent")
                self.assertEqual(status["linkedin"], "unsupported", "never faked, never a public post")
                self.assertEqual(status["email"], "sent", "LinkedIn's limit does not block the others")
                hosts = {urlparse(u).hostname for u, _ in posts}
                self.assertIn("api.telegram.org", hosts)
                self.assertFalse(any(h.endswith("linkedin.com") for h in hosts))
        finally:
            for k in list(os.environ):
                if k.startswith(("CC_SMTP", "CC_ALERT", "CC_WA_", "CC_TG_", "CC_LINKEDIN")):
                    del os.environ[k]

    def test_settings_refuse_secrets_and_unknowns(self):
        for body in ({"channels": {"dashboard": False}}, {"channels": {"pager": True}}, {"channels": {"email": "yes"}},
                     {"rules": {"made_up": {"on": True}}}, {"rules": {"incident_spike": {"token": "x"}}},
                     {"rules": {"incident_spike": {"count": "20"}}}, {"dedupe_hours": 0}, {"smtp_password": "x"}):
            with self.subTest(body=body):
                self.assertEqual(self.c.put("/api/alert-settings", json=body, headers=self.O).status_code, 422)
        ok = self.c.put("/api/alert-settings", json={"rules": {"incident_spike": {"count": 5}}, "dedupe_hours": 2}, headers=self.O)
        self.assertEqual(ok.json()["rules"]["incident_spike"]["count"], 5)
        with mock.patch.object(alerts, "CHANNELS", REAL_CHANNELS):
            names = [c["name"] for c in self.c.get("/api/alert-settings", headers=self.O).json()["channels"]]
        self.assertEqual(names, ["dashboard", "email", "whatsapp", "telegram", "linkedin"])


class Concurrency(Base):
    def test_parallel_dashboard_requests_share_one_connection_safely(self):
        self.p1.tel.emit("use.page", {"page": "sell"}, user="u1")
        self.send(self.p1)
        paths = ["/api/overview", "/api/installs", "/api/alerts", "/api/incidents", "/api/usage", "/api/guides/funnel",
                 "/api/releases", "/api/feedback", "/api/alert-settings", "/api/tickets"] * 4
        codes = []

        def hit(path):
            with TestClient(self.app) as c:
                codes.append(c.get(path, headers=self.O).status_code)
        threads = [threading.Thread(target=hit, args=(p,)) for p in paths]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(codes, [200] * len(paths))


class Relay(Base):
    def test_pull_ingest_ack(self):
        self.p1.tel.emit("backup.ok", {"size_mb": 3})
        _, body, h = self.p1.batch()
        rows = [{"id": "r1", "install_id": h["X-AF-Install"], "ts": int(h["X-AF-Timestamp"]), "nonce": h["X-AF-Nonce"],
                 "sig": h["X-AF-Signature"], "body": base64.b64encode(body).decode()},
                {"id": "r2", "install_id": h["X-AF-Install"], "ts": int(h["X-AF-Timestamp"]), "nonce": "f" * 24,
                 "sig": "0" * 64, "body": base64.b64encode(body).decode()}]
        calls = []

        def http(method, url, token, body=None):
            calls.append((method, url, token, body))
            return {"batches": rows} if method == "GET" else {"deleted": len(body["ids"])}
        out = telemetry.pull_relay(self.conn, "https://relay.example/", "pull-token", http=http)
        self.assertEqual((out["batches"], out["stored"], out["rejected_batches"]), (2, 1, 1))
        self.assertEqual(calls[0][:3], ("GET", "https://relay.example/pull?limit=100", "pull-token"))
        self.assertEqual(calls[1][3], {"ids": ["r1", "r2"]}, "acknowledged, including the bad one")
        self.assertEqual(self.c.post("/api/relay/pull", headers=self.O).status_code, 409, "no relay configured")


if __name__ == "__main__":
    unittest.main()
