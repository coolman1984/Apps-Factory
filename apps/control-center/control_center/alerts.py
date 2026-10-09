"""Alert rules and delivery (owner decision 2026-10-09).

Every alert is stored (that row IS the dashboard channel) and then fans out to ALL enabled channels at the same time:
(since 0.9.0 alerts raised while events are stored are only QUEUED inside the database transaction; a Deliverer thread
sends them afterwards, outside the database lock, so a slow mail server never freezes the dashboard or the ingest)
no priority, no fallback order. Each channel runs in its own thread with its own timeout; a failure or a hang in one
never blocks or cancels the others. Every attempt is logged per channel in alert_deliveries (sent / failed /
disabled / unsupported) with the time it took.

Channels are pluggable: subclass Channel, give it a name, `configured()` and `send(alert)`, add it to CHANNELS.
Secrets come ONLY from environment variables; the database keeps on/off switches and thresholds, never a secret.

| channel   | env (all required unless marked)                                            | default |
|-----------|-----------------------------------------------------------------------------|---------|
| dashboard | -                                                                           | on      |
| email     | CC_SMTP_HOST, CC_SMTP_PORT (587), CC_SMTP_USER*, CC_SMTP_PASSWORD*,          | on when configured |
|           | CC_ALERT_EMAIL_FROM, CC_ALERT_EMAIL_TO (comma list)                          |         |
| whatsapp  | CC_WA_TOKEN, CC_WA_PHONE_NUMBER_ID, CC_WA_TO (comma list), CC_WA_TEMPLATE*,  | on when configured |
|           | CC_WA_TEMPLATE_LANG* (ar), CC_WA_GRAPH_VERSION* (v21.0)                      |         |
| telegram  | TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID (or CC_TG_BOT_TOKEN, CC_TG_CHAT_ID) | ON as soon as configured; no switch |
| linkedin  | CC_LINKEDIN_TOKEN                                                            | OFF; see LinkedInChannel |

Open cost/verification points (docs/OPEN_POINTS.md): WhatsApp Cloud API needs Meta business verification and is
priced per message; free-form text is only delivered inside the 24-hour customer-service window, so business-initiated
alerts need an approved template (CC_WA_TEMPLATE). E-mail needs an SMTP provider and a verified sending domain.
"""
from __future__ import annotations
import json
import os
import smtplib
import ssl
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
import contextlib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Africa/Cairo")
except Exception:  # noqa: BLE001 - no tz database (some Windows Pythons): Egypt's summer offset
    LOCAL_TZ = timezone(timedelta(hours=3))

from . import db

TIMEOUT_S = 15
DEDUPE_HOURS = 6

FRIDAY, SATURDAY = 4, 5   # datetime.weekday()

# The 12 rules. Thresholds can be changed in settings (key "rules"); every rule can be switched off.
RULES = {
    "new_incident":        {"on": True, "severity": "high", "title": "خطأ جديد لم يظهر من قبل"},
    "incident_spike":      {"on": True, "severity": "high", "title": "خطأ يتكرر كثيرًا", "count": 20},
    "incident_spread":     {"on": True, "severity": "high", "title": "نفس الخطأ عند أكثر من عميل", "installs": 3},
    "upgrade_failed":      {"on": True, "severity": "high", "title": "فشل تحديث البرنامج"},
    "backup_failed":       {"on": True, "severity": "high", "title": "فشلت النسخة الاحتياطية"},
    "backup_stale":        {"on": True, "severity": "medium", "title": "لا توجد نسخة احتياطية حديثة", "hours": 48},
    "silent_install":      {"on": True, "severity": "medium", "title": "انقطع اتصال جهاز عميل", "hours": 26},
    "sync_failing":        {"on": True, "severity": "medium", "title": "المزامنة تفشل", "count": 3},
    "licence_attention":   {"on": True, "severity": "medium", "title": "الرخصة تحتاج متابعة"},
    "problem_report":      {"on": True, "severity": "medium", "title": "بلاغ مشكلة من عميل"},
    "permission_friction": {"on": True, "severity": "low", "title": "صلاحية تُرفض كثيرًا", "count": 10},
    "regression":          {"on": True, "severity": "high", "title": "خطأ قديم ظهر في إصدار جديد"},
}
# incident_spike counts errors of one fingerprint within the last hour (not since the beginning of time), so it fires
# while a spike is happening and stops by itself. silent_install and backup_stale count WORKING hours only (Africa/Cairo;
# Friday is always off, Saturday when saturday_off is set) and fire once per silence, not every dedupe window.


def _now():
    return datetime.now(timezone.utc)


def _iso(t):
    return t.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _env(name, default=""):
    return os.environ.get(name, default).strip()


# ---------------------------------------------------------------- channels
class Channel:
    name = "base"
    default_on = True
    always_on = False   # core channels: active whenever configured; settings cannot switch them off

    def configured(self) -> bool:
        return True

    def send(self, alert: dict) -> str:
        """Deliver or raise. Returns a short detail for the log (never a secret)."""
        raise NotImplementedError

    def status(self, switches: dict) -> dict:
        on = True if self.always_on else switches.get(self.name, self.default_on)
        return {"name": self.name, "configured": self.configured(), "switched_on": on, "always_on": self.always_on,
                "enabled": self.configured() and on, "note": self.note}


Channel.note = ""


class Unsupported(Exception):
    """The channel exists but cannot deliver this kind of message; logged as 'unsupported', never faked."""


def text_of(alert: dict) -> str:
    head = {"high": "🔴", "medium": "🟠", "low": "🟡"}.get(alert["severity"], "•")
    where = f" — {alert['customer']} / {alert['product']}" if alert.get("customer") else ""
    return f"{head} {alert['title']}{where}\n{alert['detail']}"


class DashboardChannel(Channel):
    note = "دائمًا مفعّلة"
    name = "dashboard"
    always_on = True

    def send(self, alert):
        return "stored"   # the alerts row is what the dashboard shows


class EmailChannel(Channel):
    note = "SMTP أو مزوّد بريد"
    name = "email"

    def configured(self):
        return bool(_env("CC_SMTP_HOST") and _env("CC_ALERT_EMAIL_FROM") and _env("CC_ALERT_EMAIL_TO"))

    def send(self, alert):
        msg = EmailMessage()
        msg["Subject"] = f"[تنبيه] {alert['title']}"
        msg["From"] = _env("CC_ALERT_EMAIL_FROM")
        to = [a.strip() for a in _env("CC_ALERT_EMAIL_TO").split(",") if a.strip()]
        msg["To"] = ", ".join(to)
        msg.set_content(text_of(alert))
        port = int(_env("CC_SMTP_PORT", "587") or 587)
        ctx = ssl.create_default_context()
        if port == 465:
            server = smtplib.SMTP_SSL(_env("CC_SMTP_HOST"), port, timeout=TIMEOUT_S, context=ctx)
        else:
            server = smtplib.SMTP(_env("CC_SMTP_HOST"), port, timeout=TIMEOUT_S)
            server.starttls(context=ctx)
        with server:
            if _env("CC_SMTP_USER"):
                server.login(_env("CC_SMTP_USER"), os.environ.get("CC_SMTP_PASSWORD", ""))
            server.send_message(msg)
        return f"sent to {len(to)} address(es)"


def _post_json(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return r.status
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}") from None


class WhatsAppChannel(Channel):
    """WhatsApp Business Cloud API (graph.facebook.com/<ver>/<phone id>/messages). With CC_WA_TEMPLATE set it sends that
    approved template with the alert text as its one body parameter (works any time); without it, a text message, which
    WhatsApp only delivers inside the 24-hour customer-service window. Never sends to customers (MSG-01)."""
    note = "⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين"
    name = "whatsapp"

    def configured(self):
        return bool(_env("CC_WA_TOKEN") and _env("CC_WA_PHONE_NUMBER_ID") and _env("CC_WA_TO"))

    def send(self, alert):
        url = f"https://graph.facebook.com/{_env('CC_WA_GRAPH_VERSION', 'v21.0')}/{_env('CC_WA_PHONE_NUMBER_ID')}/messages"
        to = [n.strip() for n in _env("CC_WA_TO").split(",") if n.strip()]
        text = text_of(alert)[:1000]
        for number in to:
            if _env("CC_WA_TEMPLATE"):
                body = {"messaging_product": "whatsapp", "to": number, "type": "template",
                        "template": {"name": _env("CC_WA_TEMPLATE"), "language": {"code": _env("CC_WA_TEMPLATE_LANG", "ar")},
                                     "components": [{"type": "body", "parameters": [{"type": "text", "text": text}]}]}}
            else:
                body = {"messaging_product": "whatsapp", "to": number, "type": "text", "text": {"body": text}}
            _post_json(url, body, {"Authorization": "Bearer " + _env("CC_WA_TOKEN")})
        return f"sent to {len(to)} number(s)" + ("" if _env("CC_WA_TEMPLATE") else " (text: 24-hour window only)")


def _tg_token():
    return _env("TELEGRAM_BOT_TOKEN") or _env("CC_TG_BOT_TOKEN")


def _tg_chat():
    return _env("TELEGRAM_OWNER_CHAT_ID") or _env("CC_TG_CHAT_ID")


class TelegramChannel(Channel):
    """Telegram Bot API sendMessage to the owner's chat. Free (BotFather). A core owner channel (owner decision
    2026-10-09 09:26): ON as soon as the bot token and the owner chat id are set; there is no separate switch."""
    note = "قناة أساسية مجانية: تعمل بمجرد ضبط التوكن ورقم محادثة المالك"
    name = "telegram"
    always_on = True

    def configured(self):
        return bool(_tg_token() and _tg_chat())

    def send(self, alert):
        _post_json(f"https://api.telegram.org/bot{_tg_token()}/sendMessage",
                   {"chat_id": _tg_chat(), "text": text_of(alert)[:4000]}, {})
        return "sent"


class LinkedInChannel(Channel):
    """LinkedIn: an adapter slot, OFF until a token is set AND it is switched on, and still not able to deliver.

    Limitation (open question, docs/OPEN_POINTS.md): LinkedIn's messaging APIs are available to approved partners
    only, and automated sending of messages is not allowed. The free self-serve API (Share on LinkedIn,
    w_member_social) only publishes PUBLIC posts on your own profile, which must never carry customer alerts. So this
    adapter does not post anything: every attempt is logged as 'unsupported'. When the owner obtains a sanctioned
    private-delivery API, implement `deliver()` here; nothing else in the engine changes."""
    note = "لا يمكنها الإرسال: رسائل LinkedIn الخاصة للشركاء فقط، ولن ننشر علنًا"
    name = "linkedin"
    default_on = False

    def configured(self):
        return bool(_env("CC_LINKEDIN_TOKEN"))

    def deliver(self, alert):
        raise Unsupported("no sanctioned private-message API for this account; public posting is deliberately not used")

    def send(self, alert):
        return self.deliver(alert)


CHANNELS = [DashboardChannel(), EmailChannel(), WhatsAppChannel(), TelegramChannel(), LinkedInChannel()]


def get_settings(conn) -> dict:
    row = conn.execute("SELECT v FROM settings WHERE k = 'alerts'").fetchone()
    data = json.loads(row[0]) if row else {}
    rules = {k: {**v, **data.get("rules", {}).get(k, {})} for k, v in RULES.items()}
    return {"channels": data.get("channels", {}), "rules": rules, "dedupe_hours": data.get("dedupe_hours", DEDUPE_HOURS),
            "saturday_off": bool(data.get("saturday_off", False))}


def save_settings(conn, channels: dict | None = None, rules: dict | None = None, dedupe_hours: int | None = None,
                  saturday_off: bool | None = None) -> dict:
    """Switches and thresholds only. Unknown channels/rules/keys are refused; no secret can be stored here."""
    current = get_settings(conn)
    stored = {"channels": dict(current["channels"]), "rules": {}, "dedupe_hours": current["dedupe_hours"],
              "saturday_off": current["saturday_off"]}
    row = conn.execute("SELECT v FROM settings WHERE k = 'alerts'").fetchone()
    if row:
        stored["rules"] = json.loads(row[0]).get("rules", {})
    names = {c.name for c in CHANNELS}
    for k, v in (channels or {}).items():
        always = {c.name for c in CHANNELS if c.always_on}
        if k not in names or not isinstance(v, bool) or k in always and v is False:
            raise ValueError(f"channel {k!r}: true/false for a known channel (dashboard and telegram cannot be switched off)")
        stored["channels"][k] = v
    for rule, change in (rules or {}).items():
        if rule not in RULES or not isinstance(change, dict):
            raise ValueError(f"unknown rule {rule!r}")
        for key, val in change.items():
            if key not in RULES[rule] or key in ("severity", "title") or not isinstance(val, type(RULES[rule][key])) \
                    or isinstance(val, bool) != isinstance(RULES[rule][key], bool):
                raise ValueError(f"rule {rule}.{key}: not changeable or wrong type")
            stored["rules"].setdefault(rule, {})[key] = val
    if dedupe_hours is not None:
        if not isinstance(dedupe_hours, int) or not 1 <= dedupe_hours <= 72:
            raise ValueError("dedupe_hours 1..72")
        stored["dedupe_hours"] = dedupe_hours
    if saturday_off is not None:
        if not isinstance(saturday_off, bool):
            raise ValueError("saturday_off: true/false")
        stored["saturday_off"] = saturday_off
    conn.execute("INSERT INTO settings (k, v) VALUES ('alerts', ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                 (json.dumps(stored),))
    return get_settings(conn)


def channel_status(conn) -> list[dict]:
    switches = get_settings(conn)["channels"]
    return [c.status(switches) for c in CHANNELS]


# ---------------------------------------------------------------- fan-out
_lock = threading.Lock()


def send_all(alert: dict, channels=None, switches=None) -> dict:
    """Deliver one alert on ALL enabled channels in parallel. No database access: safe to run outside the lock.
    Returns {channel: (status, detail, ms)}."""
    channels = channels if channels is not None else CHANNELS
    switches = switches or {}
    results = {}

    def run(ch):
        t0 = time.monotonic()
        try:
            detail = ch.send(alert)
            status = "sent"
        except Unsupported as e:
            status, detail = "unsupported", str(e)
        except Exception as e:  # noqa: BLE001 - one channel's failure never stops the others
            status, detail = "failed", f"{type(e).__name__}: {str(e)[:200]}"
        results[ch.name] = (status, str(detail)[:300], int((time.monotonic() - t0) * 1000))

    live = [c for c in channels if c.status(switches)["enabled"]]
    for c in channels:
        if c not in live:
            results[c.name] = ("disabled", "not configured" if not c.configured() else "switched off", 0)
    if live:
        pool = ThreadPoolExecutor(max_workers=len(live), thread_name_prefix="alert")
        futures = {pool.submit(run, c): c for c in live}
        done, pending = wait(futures, timeout=TIMEOUT_S + 5)
        for f in pending:
            c = futures[f]
            results.setdefault(c.name, ("failed", "timeout", (TIMEOUT_S + 5) * 1000))
        pool.shutdown(wait=False, cancel_futures=True)
    return {c.name: results[c.name] for c in channels}


def log_deliveries(conn, alert_id: str, results: dict) -> list[dict]:
    out = []
    with _lock:
        for name, (status, detail, ms) in results.items():
            conn.execute("INSERT INTO alert_deliveries (id, alert_id, channel, status, detail, attempted_at, ms) VALUES (?,?,?,?,?,?,?)",
                         (db.uuid7(), alert_id, name, status, detail, db.now_iso(), ms))
            out.append({"channel": name, "status": status, "detail": detail, "ms": ms})
        conn.execute("UPDATE alerts SET delivery = 'done' WHERE id = ?", (alert_id,))
    return out


def fan_out(conn, alert: dict, channels=None) -> list[dict]:
    """Deliver one alert now (synchronously) and log every channel's outcome. Used by the CLI and tests; the server
    queues instead (deliver=False) and lets the Deliverer send outside the lock."""
    return log_deliveries(conn, alert["id"], send_all(alert, channels, get_settings(conn)["channels"]))


def deliver_queued(conn, lock=None, channels=None, limit: int = 20) -> int:
    """Send queued alerts. The lock is held only to read and to log, never while talking to a channel."""
    guard = lock or contextlib.nullcontext()
    with guard:
        found = [dict(r) for r in conn.execute(
            "SELECT a.*, c.name AS customer, i.product FROM alerts a LEFT JOIN installs i ON i.id = a.install_id "
            "LEFT JOIN customers c ON c.id = i.customer_id WHERE a.delivery = 'queued' ORDER BY a.created_at LIMIT ?", (limit,))]
        if not found:
            return 0
        marks = ",".join("?" * len(found))
        conn.execute(f"UPDATE alerts SET delivery = 'sending' WHERE id IN ({marks})", [a["id"] for a in found])
        switches = get_settings(conn)["channels"]
    for a in found:
        results = send_all(a, channels, switches)
        with guard:
            log_deliveries(conn, a["id"], results)
    return len(found)


class Deliverer:
    """Background sender for queued alerts: woken after each stored batch, and every `every_s` seconds anyway."""

    def __init__(self, conn, lock, every_s: float = 30, channels=None):
        self.conn, self.lock, self.every, self.channels = conn, lock, every_s, channels
        self._wake, self._stop = threading.Event(), threading.Event()
        self._thread = None
        self._start_lock = threading.Lock()
        with lock:   # alerts left half-sent by a crash or restart go out again
            conn.execute("UPDATE alerts SET delivery = 'queued' WHERE delivery = 'sending'")

    def _ensure(self):
        with self._start_lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, name="cc-alerts", daemon=True)
                self._thread.start()

    def wake(self):
        self._ensure()
        self._wake.set()

    def stop(self, timeout: float = 30):
        """Stop the background thread and wait for it (call before closing the connection)."""
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _loop(self):
        while not self._stop.is_set():
            self._wake.wait(self.every)
            self._wake.clear()
            if self._stop.is_set():
                return
            try:
                while deliver_queued(self.conn, self.lock, self.channels):
                    pass
            except sqlite3.ProgrammingError:   # the connection was closed: the app is shutting down
                return
            except Exception as error:  # noqa: BLE001 - keep sending later
                print("alerts:", type(error).__name__, error, file=sys.stderr)

    def flush(self, timeout: float = 30) -> bool:
        """Deliver everything queued now (on this thread) and wait for anything the background thread is sending."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            deliver_queued(self.conn, self.lock, self.channels)
            with self.lock:
                left = self.conn.execute("SELECT COUNT(*) FROM alerts WHERE delivery IN ('queued','sending')").fetchone()[0]
            if not left:
                return True
            time.sleep(0.05)
        return False


def raise_alert(conn, rule: str, install_id: str | None, detail: str, key: str, now=None, deliver=True, channels=None,
                once=False):
    """Store one alert unless the same key fired within the dedupe window (or ever, with once=True); then fan it out
    now (deliver=True) or leave it queued for the Deliverer (deliver=False). Returns the alert or None."""
    settings = get_settings(conn)
    spec = settings["rules"][rule]
    if not spec.get("on", True):
        return None
    now = now or _now()
    since = "" if once else _iso(now - timedelta(hours=settings["dedupe_hours"]))
    dedupe = f"{rule}|{install_id or '-'}|{key}"
    if conn.execute("SELECT 1 FROM alerts WHERE dedupe_key = ? AND created_at >= ?", (dedupe, since)).fetchone():
        return None
    info = conn.execute("SELECT c.name AS customer, i.product FROM installs i JOIN customers c ON c.id = i.customer_id "
                        "WHERE i.id = ?", (install_id,)).fetchone() if install_id else None
    alert = {"id": db.uuid7(), "rule": rule, "severity": spec["severity"], "install_id": install_id, "title": spec["title"],
             "detail": detail[:500], "dedupe_key": dedupe, "created_at": _iso(now),
             "customer": info["customer"] if info else None, "product": info["product"] if info else None}
    conn.execute("INSERT INTO alerts (id, rule, severity, install_id, title, detail, dedupe_key, created_at, delivery) "
                 "VALUES (?,?,?,?,?,?,?,?,?)", (alert["id"], rule, alert["severity"], install_id, alert["title"],
                                                alert["detail"], dedupe, alert["created_at"], "sending" if deliver else "queued"))
    alert["deliveries"] = fan_out(conn, alert, channels) if deliver else []
    return alert


def dashboard_link(kind: str, item_id: str) -> str:
    return f"{_env('CC_DASHBOARD_URL', 'http://127.0.0.1:8765/').rstrip('/')}/#{kind}-{item_id}"


def working_hours(start: datetime, end: datetime, off_days) -> float:
    """Hours between start and end that fall on working days in Africa/Cairo (days in off_days do not count)."""
    if end <= start:
        return 0.0
    if (end - start).days > 60:
        return (end - start).total_seconds() / 3600 * 5 / 7
    total, cur, stop = 0.0, start.astimezone(LOCAL_TZ), end.astimezone(LOCAL_TZ)
    while cur < stop:
        nxt = (cur + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        seg = min(nxt, stop)
        if cur.weekday() not in off_days:
            total += (seg.astimezone(timezone.utc) - cur.astimezone(timezone.utc)).total_seconds()
        cur = seg
    return total / 3600


def off_days(settings: dict) -> set:
    return {FRIDAY, SATURDAY} if settings.get("saturday_off") else {FRIDAY}


# ---------------------------------------------------------------- rules
def on_event(conn, ev: dict, incident: dict | None, now=None, channels=None, deliver=True, regressed=None,
             ticket_id=None) -> list:
    """Rules that fire on one stored event. incident = the incident row after this event (errors only);
    regressed = 'fixed' / 'open' when a known fingerprint appears in a version it was not seen in before."""
    rules = get_settings(conn)["rules"]
    iid, t, d = ev["install_id"], ev["type"], ev["data"]
    fired = []

    def fire(rule, detail, key, install=iid):
        a = raise_alert(conn, rule, install, detail, key, now=now, channels=channels, deliver=deliver)
        if a:
            fired.append(a)
    if incident:
        if incident["count"] == d.get("count", 1) and incident["first_seen"] == incident["last_seen"]:
            fire("new_incident", f"{incident['code']} في {incident['where_at'] or '?'} (الإصدار {ev['version']})", incident["fingerprint"])
        since = (datetime.fromisoformat(ev["ts"].replace("Z", "+00:00")) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        hour = conn.execute("SELECT COALESCE(SUM(COALESCE(json_extract(data, '$.count'), 1)), 0) FROM events "
                            "WHERE type IN ('err.server','err.client') AND product = ? AND ts > ? AND ts <= ? "
                            "AND json_extract(data, '$.fingerprint') = ?",
                            (ev["product"], since, ev["ts"], incident["fingerprint"])).fetchone()[0]
        if hour >= rules["incident_spike"]["count"]:
            fire("incident_spike", f"{incident['code']}: {hour} مرة خلال ساعة", incident["fingerprint"])
        if regressed:
            what = "رجع بعد ما اتعلّم عليه «اتصلح»" if regressed == "fixed" else "لسه موجود"
            fire("regression", f"{incident['code']} في {incident['where_at'] or '?'} {what} — الإصدار {ev['version']}",
                 f"{incident['fingerprint']}|{ev['version']}", install=None)
        spread = len(json.loads(incident["installs"]))
        if spread >= rules["incident_spread"]["installs"]:
            fire("incident_spread", f"{incident['code']} عند {spread} أجهزة", incident["fingerprint"], install=None)
    if t == "upgrade.fail":
        fire("upgrade_failed", f"من {d.get('from')} إلى {d.get('to')}: {d.get('code')}", f"{d.get('to')}")
    elif t == "backup.fail":
        fire("backup_failed", f"السبب: {d.get('code')}", d.get("code", "-"))
    elif t == "sync.fail" and d.get("count", 1) >= rules["sync_failing"]["count"]:
        fire("sync_failing", f"{d.get('count')} مرات خلال ساعة: {d.get('code')}", d.get("code", "-"))
    elif t == "lic.state_change" and d.get("to") in ("grace", "expired", "invalid", "none"):
        fire("licence_attention", f"الرخصة أصبحت {d.get('to')}", d.get("to"))
    elif t == "fb.problem":
        # Never the customer's words: they stay on the dashboard; channels get the ticket id, category and a link.
        ref = ticket_id or ev["id"]
        fire("problem_report", f"بلاغ رقم {ref[-8:]} — التصنيف: {d.get('category') or '-'} — الصفحة: {d.get('page') or '?'}\n"
                               f"التفاصيل في لوحة التحكم: {dashboard_link('ticket', ref)}", ev["id"])
    elif t == "deny":
        day = ev["ts"][:10]
        row = conn.execute("SELECT COALESCE(SUM(count), 0) FROM usage_daily WHERE day = ? AND install_id = ? AND type = 'deny' "
                           "AND item = ?", (day, iid, d.get("perm"))).fetchone()
        if row[0] >= rules["permission_friction"]["count"]:
            fire("permission_friction", f"الصلاحية {d.get('perm')} رُفضت {row[0]} مرة اليوم", f"{d.get('perm')}|{day}")
    return fired


def periodic(conn, now=None, channels=None, deliver=True) -> list:
    """Rules that need time to pass: silent installs and stale backups. Run every few minutes. Only working hours
    count (Friday off, Saturday too when saturday_off), and each silence or stale backup alerts once, not every
    dedupe window: the key is the last contact / last backup itself."""
    now = now or _now()
    settings = get_settings(conn)
    rules, off = settings["rules"], off_days(settings)
    fired = []

    def parse(v):
        m = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return m if m.tzinfo else m.replace(tzinfo=timezone.utc)
    for inst in conn.execute("SELECT id FROM installs WHERE active = 1").fetchall():
        iid = inst["id"]
        last = conn.execute("SELECT MAX(t) FROM (SELECT MAX(received_at) AS t FROM events WHERE install_id = ? "
                            "UNION ALL SELECT MAX(received_at) FROM heartbeats WHERE install_id = ?)", (iid, iid)).fetchone()[0]
        if last and working_hours(parse(last), now, off) > rules["silent_install"]["hours"]:
            a = raise_alert(conn, "silent_install", iid, f"آخر اتصال {last}", f"silent|{last}", now=now, channels=channels,
                            deliver=deliver, once=True)
            fired += [a] if a else []
        first_hb = conn.execute("SELECT MIN(received_at) FROM events WHERE install_id = ? AND type = 'hb'", (iid,)).fetchone()[0]
        ok = conn.execute("SELECT MAX(ts) FROM events WHERE install_id = ? AND type = 'backup.ok'", (iid,)).fetchone()[0]
        start = ok or first_hb   # a new install gets the same working hours to make its first backup
        if first_hb and working_hours(parse(start), now, off) > rules["backup_stale"]["hours"]:
            a = raise_alert(conn, "backup_stale", iid, f"آخر نسخة ناجحة: {ok or 'لا توجد'}", f"backup|{ok or 'never'}",
                            now=now, channels=channels, deliver=deliver, once=True)
            fired += [a] if a else []
    return fired
