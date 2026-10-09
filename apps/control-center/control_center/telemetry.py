"""Event ingest (TEL-02, TEL-03): signed batches from products, directly or pulled from the Cloudflare relay.

A batch is a gzip JSON list of af-telemetry events signed with HMAC(sha256(install token), ts \\n nonce \\n
sha256(body)). This server keeps only sha256(token) (installs.token_hash), which is exactly the HMAC key, so the
token itself is never stored. Checks, in order: known active install, 5-minute window, nonce never seen, signature,
size, then every event again through af_telemetry.clean_data (the same firm limits as on the PC) plus a second
redaction of problem-report text. Events of another install, unknown types or fields are refused one by one.
"""
from __future__ import annotations
import base64
import gzip
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import alerts, db
from .redact import redact

try:
    import af_telemetry
except ImportError:  # running from the repository checkout
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "af-telemetry"))
    import af_telemetry

MAX_GZIP = 512 * 1024
MAX_JSON = 4 * 1024 * 1024
WINDOW_S = 300
RETENTION_DAYS = {"events": 90, "nonces": 1, "alerts": 365, "incidents_fixed": 365, "usage_daily": 730}
USAGE_TYPES = {"use.page": "page", "use.action": "action", "use.shortcut": "shortcut", "deny": "perm",
               "guide.start": "guide", "guide.done": "guide", "guide.abandon": "guide", "problem.open": "problem",
               "err.shown": "code"}


class Rejected(Exception):
    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status, self.reason = status, reason


def verify_batch(conn, install_id: str, ts: str, nonce: str, signature: str, body: bytes, now: float | None = None) -> dict:
    now = now if now is not None else time.time()
    inst = conn.execute("SELECT * FROM installs WHERE id = ? AND active = 1", (install_id,)).fetchone()
    if not inst:
        raise Rejected(401, "unknown or inactive install")
    if len(body) > MAX_GZIP:
        raise Rejected(413, "batch too large")
    try:
        ts_i = int(ts)
    except (TypeError, ValueError):
        raise Rejected(401, "bad timestamp") from None
    if not nonce or len(nonce) > 64 or not af_telemetry.verify(inst["token_hash"], ts_i, nonce, body, signature, now=now,
                                                              window=WINDOW_S):
        raise Rejected(401, "bad signature or outside the 5-minute window")
    try:
        conn.execute("INSERT INTO nonces (install_id, nonce, at) VALUES (?,?,?)", (install_id, nonce, db.now_iso()))
    except Exception:
        raise Rejected(409, "nonce already used") from None
    return dict(inst)


def decode(body: bytes) -> list:
    try:
        raw = gzip.decompress(body)
    except OSError:
        raise Rejected(400, "not gzip") from None
    if len(raw) > MAX_JSON:
        raise Rejected(413, "batch too large")
    try:
        events = json.loads(raw)
    except ValueError:
        raise Rejected(400, "not json") from None
    if not isinstance(events, list):
        raise Rejected(400, "a batch is a list")
    return events


UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ENVELOPE = {"v", "id", "install_id", "node", "product", "version", "env", "ts", "type", "sev", "anon", "subject", "role",
            "page", "data"}


def _check(ev, inst):
    if not isinstance(ev, dict) or set(ev) != ENVELOPE or ev["v"] != 1:
        raise af_telemetry.PrivacyError("envelope")
    if ev["install_id"] != inst["id"]:
        raise af_telemetry.PrivacyError("event of another install")
    if ev["product"] != inst["product"] or ev["env"] not in af_telemetry.ENVS or ev["sev"] not in af_telemetry.SEVS:
        raise af_telemetry.PrivacyError("product, env or sev")
    if not isinstance(ev["id"], str) or not UUID_RE.match(ev["id"]):
        raise af_telemetry.PrivacyError("id")
    for k in ("node", "version", "role", "page"):
        v = ev[k]
        if v is not None and (not isinstance(v, str) or not af_telemetry.ID_RE.match(v) or af_telemetry.LONG_DIGITS.search(v)):
            raise af_telemetry.PrivacyError(k)
    if ev["subject"] is not None and (not isinstance(ev["subject"], str) or not ev["subject"].startswith("p_")
                                      or len(ev["subject"]) != 18):
        raise af_telemetry.PrivacyError("subject must be a pseudonym")
    datetime.fromisoformat(str(ev["ts"]).replace("Z", "+00:00"))
    data = af_telemetry.clean_data(af_telemetry.TAXONOMY, ev["type"], ev["data"])
    if "text" in data:
        data["text"] = redact(data["text"])
    return {**ev, "data": data}


def ingest(conn, inst: dict, events: list, now=None, channels=None) -> dict:
    out = {"stored": 0, "duplicates": 0, "rejected": 0, "alerts": 0}
    for raw in events[:5000]:
        try:
            ev = _check(raw, inst)
        except (af_telemetry.PrivacyError, ValueError, TypeError, KeyError):
            out["rejected"] += 1
            continue
        cur = conn.execute("INSERT OR IGNORE INTO events (id, install_id, node, product, version, env, ts, received_at, type, "
                           "sev, subject, role, page, data) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (ev["id"], inst["id"], ev["node"], ev["product"], ev["version"], ev["env"], ev["ts"], db.now_iso(),
                            ev["type"], ev["sev"], ev["subject"], ev["role"], ev["page"],
                            json.dumps(ev["data"], ensure_ascii=False)))
        if not cur.rowcount:
            out["duplicates"] += 1
            continue
        out["stored"] += 1
        incident = _incident(conn, inst, ev) if ev["type"] in ("err.server", "err.client") else None
        _usage(conn, inst, ev)
        if ev["type"].startswith("fb."):
            _ticket(conn, inst, ev)
        out["alerts"] += len(alerts.on_event(conn, ev, incident, now=now, channels=channels))
    if out["rejected"]:
        db.audit(conn, f"install:{inst['id']}", "events.rejected", None, count=out["rejected"])
    return out


def _incident(conn, inst, ev):
    d = ev["data"]
    n = d.get("count", 1)
    row = conn.execute("SELECT * FROM incidents WHERE product = ? AND fingerprint = ?", (inst["product"], d["fingerprint"])).fetchone()
    if row is None:
        conn.execute("INSERT INTO incidents (id, product, fingerprint, code, where_at, first_seen, last_seen, count, installs, "
                     "versions, status) VALUES (?,?,?,?,?,?,?,?,?,?, 'open')",
                     (db.uuid7(), inst["product"], d["fingerprint"], d["code"], d.get("where"), ev["ts"], ev["ts"], n,
                      json.dumps([inst["id"]]), json.dumps([ev["version"]])))
    else:
        installs = sorted(set(json.loads(row["installs"])) | {inst["id"]})
        versions = sorted(set(json.loads(row["versions"])) | {ev["version"]})
        status = "open" if row["status"] == "fixed" and ev["version"] not in json.loads(row["versions"]) else row["status"]
        conn.execute("UPDATE incidents SET last_seen = MAX(last_seen, ?), count = count + ?, installs = ?, versions = ?, "
                     "status = ? WHERE id = ?", (ev["ts"], n, json.dumps(installs), json.dumps(versions), status, row["id"]))
    return dict(conn.execute("SELECT * FROM incidents WHERE product = ? AND fingerprint = ?",
                             (inst["product"], d["fingerprint"])).fetchone())


def _usage(conn, inst, ev):
    field = USAGE_TYPES.get(ev["type"])
    if not field or ev["data"].get(field) is None:
        return
    conn.execute("INSERT INTO usage_daily (day, install_id, subject, type, item, count) VALUES (?,?,?,?,?,?) "
                 "ON CONFLICT(day, install_id, subject, type, item) DO UPDATE SET count = count + excluded.count",
                 (ev["ts"][:10], inst["id"], ev["subject"] or "-", ev["type"], ev["data"][field], ev["data"].get("count", 1)))


KIND = {"fb.problem": "مشكلة", "fb.idea": "اقتراح", "fb.question": "سؤال"}


def _ticket(conn, inst, ev):
    d = ev["data"]
    now = db.now_iso()
    bundle = {k: d.get(k) for k in ("category", "page", "guide", "problem", "contact", "diagnostics") if d.get(k) is not None}
    bundle.update(kind=ev["type"], event_id=ev["id"], person=ev["subject"], version=ev["version"], env=ev["env"])
    conn.execute("INSERT INTO tickets (id, install_id, subject, message, bundle, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                 (db.uuid7(), inst["id"], f"{KIND[ev['type']]} من صفحة {d.get('page') or '?'}", d.get("text") or "-",
                  json.dumps(bundle, ensure_ascii=False), "open", now, now))


def receive(conn, headers: dict, body: bytes, now=None, channels=None) -> dict:
    """One signed batch from X-AF-* headers (direct POST or relay row)."""
    h = {k.lower(): v for k, v in headers.items()}
    inst = verify_batch(conn, h.get("x-af-install", ""), h.get("x-af-timestamp", ""), h.get("x-af-nonce", ""),
                        h.get("x-af-signature", ""), body, now=now)
    return ingest(conn, inst, decode(body), channels=channels)


# ---------------------------------------------------------------- relay
def _http(method, url, token, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def pull_relay(conn, url: str, token: str, http=None, limit: int = 100, now=None) -> dict:
    """Pull signed batches from the telemetry relay (templates/telemetry-relay), ingest, then acknowledge them so the
    relay deletes them at once. A batch that fails verification is acknowledged too (and counted) so it cannot loop;
    the relay's own clean-up removes anything older than 14 days anyway."""
    http = http or _http
    got = http("GET", f"{url.rstrip('/')}/pull?limit={int(limit)}", token)
    totals = {"batches": 0, "stored": 0, "rejected_batches": 0, "rejected": 0, "duplicates": 0, "alerts": 0}
    ack = []
    for b in got.get("batches", []):
        ack.append(b.get("id"))
        totals["batches"] += 1
        try:
            body = base64.b64decode(b["body"])
            r = receive(conn, {"X-AF-Install": b["install_id"], "X-AF-Timestamp": str(b["ts"]), "X-AF-Nonce": b["nonce"],
                               "X-AF-Signature": b["sig"]}, body,
                        now=float(b["ts"]) if now is None else now)   # the relay already enforced the window on arrival
            for k in ("stored", "rejected", "duplicates", "alerts"):
                totals[k] += r[k]
        except (Rejected, KeyError, ValueError, TypeError):
            totals["rejected_batches"] += 1
    if ack:
        http("POST", f"{url.rstrip('/')}/ack", token, {"ids": [a for a in ack if a]})
    if totals["batches"]:
        db.audit(conn, "relay", "relay.pull", None, **totals)
    return totals


def retention(conn, now=None) -> dict:
    """Raw events 90 days, nonces 1 day, alerts 12 months, fixed incidents 12 months after last seen,
    per-person daily usage 24 months (PARITY_PLAN §6.8)."""
    now = now or datetime.now(timezone.utc)
    cut = lambda days: (now - timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")  # noqa: E731
    out = {
        "events": conn.execute("DELETE FROM events WHERE received_at < ?", (cut(RETENTION_DAYS["events"]),)).rowcount,
        "nonces": conn.execute("DELETE FROM nonces WHERE at < ?", (cut(RETENTION_DAYS["nonces"]),)).rowcount,
        "incidents": conn.execute("DELETE FROM incidents WHERE status = 'fixed' AND last_seen < ?",
                                  (cut(RETENTION_DAYS["incidents_fixed"]),)).rowcount,
        "usage_daily": conn.execute("DELETE FROM usage_daily WHERE day < ?", (cut(RETENTION_DAYS["usage_daily"])[:10],)).rowcount,
    }
    old = cut(RETENTION_DAYS["alerts"])
    conn.execute("DELETE FROM alert_deliveries WHERE alert_id IN (SELECT id FROM alerts WHERE created_at < ?)", (old,))
    out["alerts"] = conn.execute("DELETE FROM alerts WHERE created_at < ?", (old,)).rowcount
    return out
