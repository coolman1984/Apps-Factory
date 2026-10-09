"""Control Center telemetry: token ingest (direct and through the relay), the firm limits again on arrival,
incidents, per-person usage, guide funnel, problem reports as tickets, the 12 alert rules, parallel fan-out to every
enabled channel with a per-channel log, settings without secrets, retention.

Regression tests for the 0.9.0 telemetry hardening are in the classes at the end (one per fix)."""
import base64
import gzip
import sqlite3 as _sqlite3
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
    """A product-side af-telemetry outbox with full consent, used to make real batches."""

    def __init__(self, install_id, token, product="hessa-centre", version="1.4.1", people=("u1",), clock=time.time):
        cdb = sqlite3.connect(":memory:")
        cdb.executescript(af_consent.SQL)
        consent = af_consent.Consent(cdb)
        consent.record("install", None, "agree", AR, "ar", by="owner")
        for p in people:
            consent.record("person", p, "agree", AR, "ar", by=p)
        self.tmp = tempfile.mkdtemp()
        self.tel = af_telemetry.Telemetry(Path(self.tmp) / "t.db", install_id, "pc1", product, version, "practice",
                                          "secret-" + install_id, consent, clock=clock)
        self.token = token

    def batch(self, sent_at=None, events=None, token=None):
        if events is not None:
            body = gzip.compress(json.dumps(events).encode())
            ids = []
        else:
            ids, body = self.tel.batch()
        headers = {"X-AF-Install": self.tel.install_id, "Authorization": "Bearer " + (token or self.token),
                   "X-AF-Sent-At": str(int(sent_at if sent_at is not None else self.tel.now())),
                   "Content-Encoding": "identity"}
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
            if k.startswith(("CC_SMTP", "CC_ALERT", "CC_WA_", "CC_TG_", "CC_LINKEDIN", "TELEGRAM_")):
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
        self.app.state.deliverer.stop()
        self.quiet.stop()
        self.app.state.close()
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
    def test_batch_with_install_token_is_stored(self):
        t = self.p1.tel
        t.emit("use.page", {"page": "sell"}, user="u1", role="cashier")
        t.emit("guide.start", {"guide": "open-shift"}, user="u1")
        t.emit("hb", {"error_count": 0})
        r = self.send(self.p1)
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["stored"], 3)
        self.assertAlmostEqual(r.json()["server_time"], time.time(), delta=5)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 3)
        self.assertEqual(t.pending(), [])

    def test_bad_batches_are_refused(self):
        self.p1.tel.emit("hb", {})
        _, body, h = self.p1.batch()
        post = lambda headers, content=body: self.c.post("/api/agent/events", content=content, headers=headers)  # noqa: E731
        wrong = post(dict(h, Authorization="Bearer ins_" + "x" * 40))
        self.assertEqual(wrong.status_code, 401)
        self.assertIn("server_time", wrong.json(), "even a refusal tells the PC the server's clock")
        self.assertEqual(post({k: v for k, v in h.items() if k != "Authorization"}).status_code, 401)
        self.assertEqual(post(dict(h, **{"X-AF-Install": "not-a-uuid"})).status_code, 400)
        self.assertEqual(post(h).status_code, 202)
        again = post(h)
        self.assertEqual((again.status_code, again.json()["duplicates"]), (202, 1), "a replay only counts duplicates")
        self.assertEqual(post(h, b"not gzip").status_code, 400)
        self.c.post(f"/api/installs/{self.p1.tel.install_id}/deactivate", headers=self.O)
        self.assertEqual(post(h).status_code, 403)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)

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
        r = self.send(self.p1, events=[good] + forged).json()
        self.assertEqual({k: r[k] for k in ("stored", "duplicates", "rejected", "alerts")},
                         {"stored": 2, "duplicates": 0, "rejected": 6, "alerts": 1})
        self.assertEqual(sum(r["reasons"].values()), 6)
        self.assertIn("event of another install", r["reasons"])
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
        for section in ("alertsTitle", "incTitle", "useTitle", "funnelTitle", "fbTitle", "chTitle", "relTitle", "pendTitle"):
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
        monday = datetime(2026, 10, 12, 7, 0, tzinfo=timezone.utc)          # Monday 10:00 Cairo
        self.conn.execute("UPDATE events SET received_at = ?, ts = ?", (alerts._iso(monday),) * 2)
        later = monday + timedelta(hours=30)
        self.assertEqual({a["rule"] for a in alerts.periodic(self.conn, now=later)}, {"silent_install"},
                         "a new install gets 48 working hours for its first backup")
        self.assertEqual(alerts.periodic(self.conn, now=later), [], "deduplicated")
        self.assertEqual({a["rule"] for a in alerts.periodic(self.conn, now=monday + timedelta(hours=50))}, {"backup_stale"})
        self.assertEqual(len(alerts.RULES), 12)
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
                           "TELEGRAM_BOT_TOKEN": "tg-secret", "TELEGRAM_OWNER_CHAT_ID": "42", "CC_LINKEDIN_TOKEN": "li-secret"})
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
                                          "telegram": "sent", "linkedin": "disabled"},
                                 "Telegram is on as soon as it is configured; LinkedIn stays off")
                tg = [b for u, b in posts if urlparse(u).hostname == "api.telegram.org"]
                self.assertEqual(tg[0]["chat_id"], "42")
                self.assertEqual(sent_mail[0]["To"], "owner@example.com")
                self.assertEqual(posts[0][1]["type"], "template")
                self.assertEqual(posts[0][1]["template"]["name"], "cc_alert")
                r = self.c.put("/api/alert-settings", json={"channels": {"linkedin": True}}, headers=self.O)
                self.assertEqual(r.status_code, 200, r.text)
                self.assertNotIn("secret", r.text)
                a = self.c.post("/api/alerts/test", headers=self.O).json()
                self.assertEqual(a["deliveries"], [], "queued: sent in the background, outside the lock")
                self.assertTrue(self.app.state.deliverer.flush(10))
                a = next(x for x in self.c.get("/api/alerts", headers=self.O).json() if x["id"] == a["id"])
                status = {d["channel"]: d["status"] for d in a["deliveries"]}
                self.assertEqual(status["telegram"], "sent")
                self.assertEqual(status["linkedin"], "unsupported", "never faked, never a public post")
                self.assertEqual(status["email"], "sent", "LinkedIn's limit does not block the others")
                hosts = {urlparse(u).hostname for u, _ in posts}
                self.assertIn("api.telegram.org", hosts)
                self.assertEqual(hosts, {"graph.facebook.com", "api.telegram.org"}, "nothing was sent to LinkedIn")
        finally:
            for k in list(os.environ):
                if k.startswith(("CC_SMTP", "CC_ALERT", "CC_WA_", "CC_TG_", "CC_LINKEDIN", "TELEGRAM_")):
                    del os.environ[k]

    def test_settings_refuse_secrets_and_unknowns(self):
        for body in ({"channels": {"dashboard": False}}, {"channels": {"telegram": False}}, {"channels": {"pager": True}}, {"channels": {"email": "yes"}},
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


class TelegramDefault(Base):
    def test_on_when_configured_off_when_not(self):
        tg = alerts.TelegramChannel()
        self.assertFalse(tg.status({})["enabled"], "no token: nothing to send with")
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_OWNER_CHAT_ID": "1"}):
            st = tg.status({"telegram": False})
            self.assertTrue(st["enabled"] and st["always_on"], "a stored switch cannot turn the core channel off")
        with mock.patch.dict(os.environ, {"CC_TG_BOT_TOKEN": "t", "CC_TG_CHAT_ID": "1"}):
            self.assertTrue(tg.configured(), "older CC_TG_* names still work")


class Relay(Base):
    def row(self, rid, body, inst=None, token=None, sent_at=None):
        return {"id": rid, "install_id": inst or self.p1.tel.install_id, "token_hash": token_hash(token or self.p1.token),
                "sent_at": int(sent_at or time.time()), "received_at": int(time.time()),
                "body": base64.b64encode(body).decode()}

    def test_pull_ingest_ack(self):
        self.p1.tel.emit("backup.ok", {"size_mb": 3})
        _, body, _ = self.p1.batch()
        stranger = af_telemetry.uuid7()
        rows = [self.row("r1", body), self.row("r2", body, token="ins_wrong"), dict(self.row("r3", body), body="%%%"),
                self.row("r4", gzip.compress(b"[]"), inst=stranger, token="ins_" + "s" * 40)]
        calls = []

        def http(method, url, token, body=None):
            calls.append((method, url, token, body))
            return {"batches": rows} if method == "GET" else {"ok": True}
        out = telemetry.pull_relay(self.conn, "https://relay.example/", "pull-token", http=http)
        self.assertEqual({k: out[k] for k in ("batches", "stored", "quarantined", "pending", "kept")},
                         {"batches": 4, "stored": 1, "quarantined": 2, "pending": 1, "kept": 0})
        self.assertEqual(calls[0][:2], ("POST", "https://relay.example/installs"), "the relay learns the installs first")
        self.assertEqual(calls[0][3]["installs"][0]["token_hash"], token_hash(self.p1.token))
        self.assertNotIn(self.p1.token, json.dumps(calls[0][3]), "only hashes leave this server")
        self.assertEqual(calls[1][:3], ("GET", "https://relay.example/pull?limit=100", "pull-token"))
        self.assertEqual(calls[2][3], {"ids": ["r1", "r2", "r3", "r4"]}, "stored, quarantined or pending: safe to delete")
        reasons = {r[0] for r in self.conn.execute("SELECT reason FROM rejected_batches")}
        self.assertEqual(reasons, {"wrong token for this install", "malformed relay row"})
        calls.clear()
        telemetry.pull_relay(self.conn, "https://relay.example/", "pull-token", http=http)
        self.assertNotIn("POST https://relay.example/installs", [f"{c[0]} {c[1]}" for c in calls], "sync only on change")
        self.assertEqual(self.c.post("/api/relay/pull", headers=self.O).status_code, 409, "no relay configured")


class Fix1PoisonEvent(Base):
    """An err.* without a fingerprint passed the gate and crashed ingest mid-batch; via the relay the batch was deleted."""

    def events(self, *extra):
        t = self.p1.tel
        good = dict(v=1, install_id=t.install_id, node="pc1", product="hessa-centre", version="1.4.1", env="practice",
                    ts=db.now_iso(), sev="info", anon=True, subject=None, role=None, page=None)
        return [dict(good, id=af_telemetry.uuid7(), type="hb", data={}),
                dict(good, id=af_telemetry.uuid7(), type="err.server", sev="error", data={"code": "KeyError", "where": "x"}),
                dict(good, id=af_telemetry.uuid7(), type="backup.ok", data={"size_mb": 1}), *extra]

    def test_a_bad_event_is_rejected_alone_with_a_reason(self):
        r = self.send(self.p1, events=self.events()).json()
        self.assertEqual((r["stored"], r["rejected"]), (2, 1))
        self.assertEqual(r["reasons"], {"err.server.fingerprint: required": 1})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 2)

    def test_a_crash_in_a_rule_rolls_back_only_that_event(self):
        real = alerts.on_event

        def boom(conn, ev, *a, **k):
            if ev["type"] == "backup.ok":
                raise KeyError("bug in a rule")
            return real(conn, ev, *a, **k)
        with mock.patch.object(alerts, "on_event", boom):
            r = self.send(self.p1, events=self.events()).json()
        self.assertEqual((r["stored"], r["rejected"], r["reasons"].get("KeyError")), (1, 2, 1))
        types = [x[0] for x in self.conn.execute("SELECT type FROM events")]
        self.assertEqual(types, ["hb"], "the failed event left nothing half-written")

    def test_relay_batch_is_deleted_only_when_stored(self):
        _, body, _ = self.p1.batch(events=self.events())
        row = {"id": "r1", "install_id": self.p1.tel.install_id, "token_hash": token_hash(self.p1.token),
               "sent_at": int(time.time()), "received_at": int(time.time()), "body": base64.b64encode(body).decode()}
        acks = []

        def http(method, url, token, body=None):
            if url.endswith("/ack"):
                acks.extend(body["ids"])
            return {"batches": [row]} if method == "GET" else {}
        busy = mock.patch.object(telemetry, "_usage", side_effect=_sqlite3.OperationalError("database is locked"))
        busy.start()
        try:
            out = telemetry.pull_relay(self.conn, "https://relay.example", "t", http=http)
        finally:
            busy.stop()
        self.assertEqual((out["kept"], acks), (1, []), "a temporary failure keeps the batch on the relay")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0, "whole batch rolled back")
        out = telemetry.pull_relay(self.conn, "https://relay.example", "t", http=http)
        self.assertEqual((out["stored"], out["rejected"], acks), (2, 1, ["r1"]))


class Fix2ClockSkew(Base):
    def test_a_pc_two_hours_behind_is_accepted_and_corrected(self):
        behind = lambda: time.time() - 7200  # noqa: E731
        p = self.product(clock=behind)
        p.tel.emit("hb", {})
        r = self.send(p)
        self.assertEqual(r.status_code, 202, "no time window: a wrong clock is never a refusal")
        self.assertAlmostEqual(r.json()["clock_corrected_s"], 7200, delta=5)
        ts = self.conn.execute("SELECT ts FROM events").fetchone()[0]
        self.assertLess(abs(telemetry._utc(ts).timestamp() - time.time()), 10, "event time shifted to server time")
        skew = self.conn.execute("SELECT clock_skew_s FROM installs WHERE id = ?", (p.tel.install_id,)).fetchone()[0]
        self.assertAlmostEqual(skew, 7200, delta=5)
        # the product learns the offset from server_time and stamps later events right
        p.tel.emit("hb", {})

        def post(url, body, headers):
            resp = self.c.post("/api/agent/events", content=body, headers=dict(headers, **{"Content-Encoding": "identity"}))
            return resp.status_code, resp.json().get("server_time")
        self.assertEqual(p.tel.send_once("https://cc.example/api/agent/events", p.token, post=post)[0], "sent")
        self.assertAlmostEqual(p.tel._state("clock_offset"), 7200, delta=5)
        p.tel.emit("hb", {})
        self.assertLess(abs(telemetry._utc(p.tel.pending()[0]["ts"]).timestamp() - time.time()), 10)


class Fix5Strangers(Base):
    def test_unknown_installs_are_parked_with_small_caps(self):
        stranger = af_telemetry.uuid7()
        tok = "ins_" + "z" * 40
        h = {"X-AF-Install": stranger, "Authorization": "Bearer " + tok, "Content-Encoding": "identity"}
        small = gzip.compress(b"[]")
        for _ in range(telemetry.PENDING_MAX_BATCHES):
            self.assertEqual(self.c.post("/api/agent/events", content=small, headers=h).json()["pending"], True)
        self.assertEqual(self.c.post("/api/agent/events", content=small, headers=h).status_code, 429)
        self.assertEqual(self.c.post("/api/agent/events", content=small, headers=dict(h, Authorization="Bearer ins_other")).status_code,
                         401, "the first token is pinned")
        big = gzip.compress(os.urandom(telemetry.PENDING_MAX_BODY))
        other = dict(h, **{"X-AF-Install": af_telemetry.uuid7()})
        self.assertEqual(self.c.post("/api/agent/events", content=big, headers=other).status_code, 413)
        with mock.patch.object(telemetry, "PENDING_MAX_INSTALLS", 1):
            self.assertEqual(self.c.post("/api/agent/events", content=small, headers=other).status_code, 429)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0, "nothing from strangers is used")


class Fix6NewPCs(Base):
    def test_a_new_pc_waits_on_the_dashboard_and_nothing_is_lost(self):
        iid, tok = af_telemetry.uuid7(), "ins_" + "n" * 40
        p = Product(iid, tok)
        p.tel.emit("hb", {})
        p.tel.emit("backup.ok", {"size_mb": 2})
        r = self.send(p)
        self.assertEqual((r.status_code, r.json()["pending"]), (202, True))
        self.assertEqual(p.tel.pending(), [], "the PC may forget it: the server keeps it")
        self.assertEqual(self.c.get("/api/overview", headers=self.O).json()["pending_installs"], 1)
        pend = self.c.get("/api/installs/pending", headers=self.O).json()
        self.assertEqual((pend[0]["id"], pend[0]["product"], pend[0]["node"]), (iid, "hessa-centre", "pc1"))
        self.assertNotIn("token_hash", pend[0])
        bad = self.c.post(f"/api/installs/pending/{iid}/approve", json={"customer_id": self.cid, "tier": "nope"}, headers=self.O)
        self.assertEqual(bad.status_code, 422)
        ok = self.c.post(f"/api/installs/pending/{iid}/approve", json={"customer_id": self.cid, "tier": "standalone",
                                                                       "label": "كاشير 2"}, headers=self.O)
        self.assertEqual(ok.status_code, 201, ok.text)
        self.assertEqual((ok.json()["batches"], ok.json()["stored"]), (1, 2))
        self.assertEqual(self.c.get("/api/installs/pending", headers=self.O).json(), [])
        p.tel.emit("hb", {})
        r = self.send(p)
        self.assertEqual((r.status_code, r.json()["stored"]), (202, 1), "same id and token now count normally")
        self.assertIn(iid, [i["id"] for i in self.c.get("/api/installs", headers=self.O).json()])
        other = Product(af_telemetry.uuid7(), "ins_" + "d" * 40)
        other.tel.emit("hb", {})
        self.send(other)
        self.assertEqual(self.c.post(f"/api/installs/pending/{other.tel.install_id}/discard", headers=self.O).json(), {"ok": True})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM pending_batches").fetchone()[0], 0)


class Fix7AsyncAlerts(Base):
    def test_a_slow_channel_never_blocks_ingest_or_the_dashboard(self):
        slow = Recorder("email", delay=1.5)
        with mock.patch.object(alerts, "CHANNELS", [alerts.DashboardChannel(), slow]):
            self.p1.tel.emit("backup.fail", {"code": "locked"})
            t0 = time.monotonic()
            r = self.send(self.p1)
            self.assertEqual(r.json()["alerts"], 1)
            self.assertLess(time.monotonic() - t0, 1.0, "storing does not wait for the e-mail")
            time.sleep(0.2)          # the deliverer is now inside the slow send
            t0 = time.monotonic()
            self.assertEqual(self.c.get("/api/alerts", headers=self.O).status_code, 200)
            self.assertLess(time.monotonic() - t0, 1.0, "the dashboard is not frozen during the send")
            self.assertTrue(self.app.state.deliverer.flush(10))
        self.assertEqual(len(slow.got), 1)
        logged = {d["channel"]: d["status"] for d in self.c.get("/api/alerts", headers=self.O).json()[0]["deliveries"]}
        self.assertEqual(logged, {"dashboard": "sent", "email": "sent"})


class Fix8AlertRepeats(Base):
    def errors(self, n, at=None, version="1.4.1", fp="fpx"):
        t = self.p1.tel
        base = dict(v=1, install_id=t.install_id, node="pc1", product="hessa-centre", version=version, env="real",
                    ts=at or db.now_iso(), type="err.server", sev="error", anon=True, subject=None, role=None, page=None)
        return [dict(base, id=af_telemetry.uuid7(), data={"code": "KeyError", "fingerprint": fp, "where": "a:b"})
                for _ in range(n)]

    def inst(self):
        return dict(self.conn.execute("SELECT * FROM installs WHERE id = ?", (self.p1.tel.install_id,)).fetchone())

    def test_spike_counts_the_last_hour_and_does_not_repeat_forever(self):
        old = datetime.now(timezone.utc) - timedelta(hours=7)
        telemetry.ingest(self.conn, self.inst(), self.errors(25, at=alerts._iso(old)), now=old)
        rules = [r[0] for r in self.conn.execute("SELECT rule FROM alerts")]
        self.assertEqual(rules.count("incident_spike"), 1)
        telemetry.ingest(self.conn, self.inst(), self.errors(1))
        rules = [r[0] for r in self.conn.execute("SELECT rule FROM alerts")]
        self.assertEqual(rules.count("incident_spike"), 1, "26 in total, but 1 in the last hour: no new spike alert")

    def test_an_old_fingerprint_in_a_new_version_alerts_once(self):
        telemetry.ingest(self.conn, self.inst(), self.errors(1))
        iid = self.c.get("/api/incidents", headers=self.O).json()[0]["id"]
        self.c.post(f"/api/incidents/{iid}", json={"status": "fixed"}, headers=self.O)
        telemetry.ingest(self.conn, self.inst(), self.errors(1, version="1.5.0"))
        telemetry.ingest(self.conn, self.inst(), self.errors(1, version="1.5.0"))
        reg = [dict(r) for r in self.conn.execute("SELECT * FROM alerts WHERE rule = 'regression'")]
        self.assertEqual(len(reg), 1)
        self.assertIn("1.5.0", reg[0]["detail"])
        self.assertEqual(reg[0]["severity"], "high")

    def contact(self, when):
        self.conn.execute("INSERT INTO events (id, install_id, node, product, version, env, ts, received_at, type, sev, data) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (af_telemetry.uuid7(), self.p1.tel.install_id, "pc1", "hessa-centre",
                                                             "1.4.1", "real", alerts._iso(when), alerts._iso(when), "hb", "info", "{}"))

    def test_silence_counts_working_days_only_and_alerts_once(self):
        cairo = timezone(timedelta(hours=3))
        thursday = datetime(2026, 10, 8, 20, 0, tzinfo=cairo)
        self.contact(thursday)
        self.conn.execute("INSERT INTO events (id, install_id, node, product, version, env, ts, received_at, type, sev, data) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (af_telemetry.uuid7(), self.p1.tel.install_id, "pc1", "hessa-centre",
                                                             "1.4.1", "real", alerts._iso(thursday), alerts._iso(thursday),
                                                             "backup.ok", "info", "{}"))
        saturday = datetime(2026, 10, 10, 14, 0, tzinfo=cairo)
        self.assertEqual(alerts.periodic(self.conn, now=saturday), [], "Thu 4 h + Sat 14 h = 18 working hours < 26")
        sunday = datetime(2026, 10, 11, 14, 0, tzinfo=cairo)
        alerts.save_settings(self.conn, saturday_off=True)
        self.assertEqual(alerts.periodic(self.conn, now=sunday), [], "Saturday off: still 18 working hours")
        alerts.save_settings(self.conn, saturday_off=False)
        self.assertEqual({a["rule"] for a in alerts.periodic(self.conn, now=sunday)}, {"silent_install"})
        for days in (1, 2, 3):
            fired = {a["rule"] for a in alerts.periodic(self.conn, now=sunday + timedelta(days=days))}
            self.assertNotIn("silent_install", fired, "one alert per silence, not every 6 hours")
        self.assertEqual(self.c.put("/api/alert-settings", json={"saturday_off": True}, headers=self.O).json()["weekend"],
                         ["fri", "sat"])
        self.assertEqual(self.c.put("/api/alert-settings", json={"saturday_off": "yes"}, headers=self.O).status_code, 422)
        self.assertAlmostEqual(alerts.working_hours(thursday, thursday + timedelta(days=7), {alerts.FRIDAY}), 144)


class Fix9ProblemReportText(Base):
    def test_channels_get_an_id_and_a_link_never_the_text(self):
        os.environ.update({"TELEGRAM_BOT_TOKEN": "tg", "TELEGRAM_OWNER_CHAT_ID": "1", "CC_DASHBOARD_URL": "https://cc.example/"})
        posts = []
        try:
            with mock.patch.object(alerts, "CHANNELS", REAL_CHANNELS), \
                    mock.patch.object(alerts, "_post_json", lambda url, body, h: posts.append(body) or 200):
                self.p1.tel.feedback("problem", "الطابعة بتطبع فاتورة فاضية عند العميل", page="sell", category="printing")
                self.send(self.p1)
                self.assertTrue(self.app.state.deliverer.flush(10))
        finally:
            for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_CHAT_ID", "CC_DASHBOARD_URL"):
                os.environ.pop(k, None)
        ticket = self.conn.execute("SELECT id, message FROM tickets").fetchone()
        self.assertIn("الطابعة", ticket["message"], "the full text stays on the dashboard")
        detail = self.conn.execute("SELECT detail FROM alerts WHERE rule = 'problem_report'").fetchone()[0]
        self.assertNotIn("الطابعة", detail)
        self.assertIn(ticket["id"][-8:], detail)
        self.assertIn("printing", detail)
        self.assertIn(f"https://cc.example/#ticket-{ticket['id']}", detail)
        self.assertEqual(len(posts), 1)
        self.assertNotIn("الطابعة", posts[0]["text"])


if __name__ == "__main__":
    unittest.main()
