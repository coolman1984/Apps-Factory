"""Alert rules and delivery (owner decision 2026-10-09).

Every alert is stored (that row IS the dashboard channel) and then fans out to ALL enabled channels at the same time:
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
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from . import db

TIMEOUT_S = 15
DEDUPE_HOURS = 6

# The 11 rules. Thresholds can be changed in settings (key "rules"); every rule can be switched off.
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
}


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
    return {"channels": data.get("channels", {}), "rules": rules, "dedupe_hours": data.get("dedupe_hours", DEDUPE_HOURS)}


def save_settings(conn, channels: dict | None = None, rules: dict | None = None, dedupe_hours: int | None = None) -> dict:
    """Switches and thresholds only. Unknown channels/rules/keys are refused; no secret can be stored here."""
    current = get_settings(conn)
    stored = {"channels": dict(current["channels"]), "rules": {}, "dedupe_hours": current["dedupe_hours"]}
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
    conn.execute("INSERT INTO settings (k, v) VALUES ('alerts', ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                 (json.dumps(stored),))
    return get_settings(conn)


def channel_status(conn) -> list[dict]:
    switches = get_settings(conn)["channels"]
    return [c.status(switches) for c in CHANNELS]


# ---------------------------------------------------------------- fan-out
_lock = threading.Lock()


def fan_out(conn, alert: dict, channels=None) -> list[dict]:
    """Deliver one alert on ALL enabled channels in parallel and log every channel's outcome."""
    channels = channels if channels is not None else CHANNELS
    switches = get_settings(conn)["channels"]
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
    out = []
    with _lock:
        for c in channels:
            status, detail, ms = results[c.name]
            conn.execute("INSERT INTO alert_deliveries (id, alert_id, channel, status, detail, attempted_at, ms) VALUES (?,?,?,?,?,?,?)",
                         (db.uuid7(), alert["id"], c.name, status, detail, db.now_iso(), ms))
            out.append({"channel": c.name, "status": status, "detail": detail, "ms": ms})
    return out


def raise_alert(conn, rule: str, install_id: str | None, detail: str, key: str, now=None, deliver=True, channels=None):
    """Store one alert unless the same key fired within the dedupe window; then fan it out. Returns the alert or None."""
    settings = get_settings(conn)
    spec = settings["rules"][rule]
    if not spec.get("on", True):
        return None
    now = now or _now()
    since = _iso(now - timedelta(hours=settings["dedupe_hours"]))
    dedupe = f"{rule}|{install_id or '-'}|{key}"
    if conn.execute("SELECT 1 FROM alerts WHERE dedupe_key = ? AND created_at >= ?", (dedupe, since)).fetchone():
        return None
    info = conn.execute("SELECT c.name AS customer, i.product FROM installs i JOIN customers c ON c.id = i.customer_id "
                        "WHERE i.id = ?", (install_id,)).fetchone() if install_id else None
    alert = {"id": db.uuid7(), "rule": rule, "severity": spec["severity"], "install_id": install_id, "title": spec["title"],
             "detail": detail[:500], "dedupe_key": dedupe, "created_at": _iso(now),
             "customer": info["customer"] if info else None, "product": info["product"] if info else None}
    conn.execute("INSERT INTO alerts (id, rule, severity, install_id, title, detail, dedupe_key, created_at) VALUES (?,?,?,?,?,?,?,?)",
                 (alert["id"], rule, alert["severity"], install_id, alert["title"], alert["detail"], dedupe, alert["created_at"]))
    alert["deliveries"] = fan_out(conn, alert, channels) if deliver else []
    return alert


# ---------------------------------------------------------------- rules
def on_event(conn, ev: dict, incident: dict | None, now=None, channels=None) -> list:
    """Rules that fire on one stored event. incident = the incident row after this event (errors only)."""
    rules = get_settings(conn)["rules"]
    iid, t, d = ev["install_id"], ev["type"], ev["data"]
    fired = []

    def fire(rule, detail, key):
        a = raise_alert(conn, rule, iid, detail, key, now=now, channels=channels)
        if a:
            fired.append(a)
    if incident:
        if incident["count"] == d.get("count", 1) and incident["first_seen"] == incident["last_seen"]:
            fire("new_incident", f"{incident['code']} في {incident['where_at'] or '?'} (الإصدار {ev['version']})", incident["fingerprint"])
        if incident["count"] >= rules["incident_spike"]["count"]:
            fire("incident_spike", f"{incident['code']}: {incident['count']} مرة", incident["fingerprint"])
        spread = len(json.loads(incident["installs"]))
        if spread >= rules["incident_spread"]["installs"]:
            a = raise_alert(conn, "incident_spread", None, f"{incident['code']} عند {spread} أجهزة", incident["fingerprint"],
                            now=now, channels=channels)
            if a:
                fired.append(a)
    if t == "upgrade.fail":
        fire("upgrade_failed", f"من {d.get('from')} إلى {d.get('to')}: {d.get('code')}", f"{d.get('to')}")
    elif t == "backup.fail":
        fire("backup_failed", f"السبب: {d.get('code')}", d.get("code", "-"))
    elif t == "sync.fail" and d.get("count", 1) >= rules["sync_failing"]["count"]:
        fire("sync_failing", f"{d.get('count')} مرات خلال ساعة: {d.get('code')}", d.get("code", "-"))
    elif t == "lic.state_change" and d.get("to") in ("grace", "expired", "invalid", "none"):
        fire("licence_attention", f"الرخصة أصبحت {d.get('to')}", d.get("to"))
    elif t == "fb.problem":
        fire("problem_report", f"صفحة {d.get('page') or '?'}: {d.get('text', '')[:140]}", ev["id"])
    elif t == "deny":
        day = ev["ts"][:10]
        row = conn.execute("SELECT COALESCE(SUM(count), 0) FROM usage_daily WHERE day = ? AND install_id = ? AND type = 'deny' "
                           "AND item = ?", (day, iid, d.get("perm"))).fetchone()
        if row[0] >= rules["permission_friction"]["count"]:
            fire("permission_friction", f"الصلاحية {d.get('perm')} رُفضت {row[0]} مرة اليوم", f"{d.get('perm')}|{day}")
    return fired


def periodic(conn, now=None, channels=None) -> list:
    """Rules that need time to pass: silent installs and stale backups. Run every few minutes."""
    now = now or _now()
    rules = get_settings(conn)["rules"]
    fired = []
    for inst in conn.execute("SELECT id FROM installs WHERE active = 1").fetchall():
        iid = inst["id"]
        last = conn.execute("SELECT MAX(t) FROM (SELECT MAX(received_at) AS t FROM events WHERE install_id = ? "
                            "UNION ALL SELECT MAX(received_at) FROM heartbeats WHERE install_id = ?)", (iid, iid)).fetchone()[0]
        if last and _iso(now - timedelta(hours=rules["silent_install"]["hours"])) > last:
            a = raise_alert(conn, "silent_install", iid, f"آخر اتصال {last}", "silent", now=now, channels=channels)
            fired += [a] if a else []
        seen = conn.execute("SELECT 1 FROM events WHERE install_id = ? AND type = 'hb' LIMIT 1", (iid,)).fetchone()
        ok = conn.execute("SELECT MAX(ts) FROM events WHERE install_id = ? AND type = 'backup.ok'", (iid,)).fetchone()[0]
        if seen and (not ok or _iso(now - timedelta(hours=rules["backup_stale"]["hours"])) > ok):
            a = raise_alert(conn, "backup_stale", iid, f"آخر نسخة ناجحة: {ok or 'لا توجد'}", "backup", now=now, channels=channels)
            fired += [a] if a else []
    return fired
