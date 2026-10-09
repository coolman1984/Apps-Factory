"""Event ingest (TEL-02, TEL-03): batches from products, directly or pulled from the Cloudflare relay.

Protocol 2 (0.9.0): a batch is a gzip JSON list of af-telemetry events sent over HTTPS with
`Authorization: Bearer <install token>`, `X-AF-Install` and `X-AF-Sent-At`. This server keeps only sha256(token)
(installs.token_hash). There is no signature, nonce or time window any more: every event has a unique id and is stored
with INSERT OR IGNORE, so a replayed batch only counts duplicates. The answer carries `server_time` so a PC with a
wrong clock corrects itself; a large difference is also corrected here (the event times are shifted) and shown per
install (installs.clock_skew_s).

Order of checks: install id shape, then
  * a known install: the token must match (401) and the install must be active (403);
  * an unknown install: nothing is lost and nothing is trusted. The batch waits under pending_installs /
    pending_batches (small caps) until the owner approves the PC on the dashboard, which then replays it.
Then every event again through af_telemetry.clean_data (the same firm limits as on the PC) plus a second redaction of
problem-report text. The whole batch is one transaction and every event its own savepoint: a bad event is rolled back
and counted with a reason; it never takes the rest of the batch with it. A batch that cannot be read at all is kept in
rejected_batches (quarantine) so the relay can delete it without losing evidence; a temporary failure (database
busy) leaves it on the relay for the next pull.
"""
from __future__ import annotations
import base64
import binascii
import contextlib
import gzip
import json
import re
import sqlite3
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import alerts, db
from .redact import redact
from .security import same, token_hash

try:
    import af_telemetry
except ImportError:  # running from the repository checkout
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "af-telemetry"))
    import af_telemetry

MAX_GZIP = 512 * 1024
MAX_JSON = 4 * 1024 * 1024
MAX_EVENTS = 5000
SKEW_TOLERANCE_S = 120
PENDING_MAX_BODY = 64 * 1024        # an unapproved PC may only park small batches
PENDING_MAX_INSTALLS = 50
PENDING_MAX_BATCHES = 20            # per unapproved PC
QUARANTINE_MAX_ROWS = 1000
QUARANTINE_MAX_BODY = 64 * 1024
RETENTION_DAYS = {"events": 90, "nonces": 1, "alerts": 365, "incidents_fixed": 365, "usage_daily": 730, "pending": 30,
                  "rejected_batches": 30}
USAGE_TYPES = {"use.page": "page", "use.action": "action", "use.shortcut": "shortcut", "deny": "perm",
               "guide.start": "guide", "guide.done": "guide", "guide.abandon": "guide", "problem.open": "problem",
               "err.shown": "code"}


class Rejected(Exception):
    """A batch refused as a whole. permanent=False means 'try again later' (it stays on the relay)."""

    def __init__(self, status: int, reason: str, permanent: bool = True):
        super().__init__(reason)
        self.status, self.reason, self.permanent = status, reason, permanent


def decode(body: bytes) -> list:
    try:
        raw = gzip.decompress(body)
    except (OSError, EOFError):
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


def _utc(value) -> datetime:
    moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _epoch_iso(seconds) -> str:
    return _iso(datetime.fromtimestamp(float(seconds), timezone.utc))


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
    if not isinstance(ev["ts"], str):
        raise af_telemetry.PrivacyError("ts")
    ts = _iso(_utc(ev["ts"]))
    data = af_telemetry.clean_data(af_telemetry.TAXONOMY, ev["type"], ev["data"])
    if "text" in data:
        data["text"] = redact(data["text"])
    return {**ev, "ts": ts, "data": data}


_REASON_SAFE = re.compile(r"[^A-Za-z0-9_.:' -]")


def _reason(error: Exception) -> str:
    """A short, safe reason for the rejected-events count (never an event value)."""
    if isinstance(error, af_telemetry.PrivacyError):
        return _REASON_SAFE.sub("?", str(error))[:80] or "privacy"
    return f"{type(error).__name__}"[:40]


def ingest(conn, inst: dict, events: list, now=None, channels=None, ts_offset: int = 0, received_at: str | None = None) -> dict:
    """Store a decoded batch for a known install. One transaction; one savepoint per event, so a bad event (or a bug
    in a rule) rolls back that event only and is counted under reasons. Database trouble (busy, disk) aborts the whole
    batch and is raised, so the caller keeps the batch for a retry."""
    out = {"stored": 0, "duplicates": 0, "rejected": 0, "alerts": 0, "reasons": {}}
    reasons = Counter()
    received_at = received_at or db.now_iso()
    own = not conn.in_transaction
    if own:
        conn.execute("BEGIN IMMEDIATE")
    try:
        for raw in events[:MAX_EVENTS]:
            conn.execute("SAVEPOINT ev")
            try:
                ev = _check(raw, inst)
                if ts_offset:
                    ev["ts"] = _iso(_utc(ev["ts"]) + timedelta(seconds=ts_offset))
                cur = conn.execute("INSERT OR IGNORE INTO events (id, install_id, node, product, version, env, ts, received_at, "
                                   "type, sev, subject, role, page, data) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                   (ev["id"], inst["id"], ev["node"], ev["product"], ev["version"], ev["env"], ev["ts"],
                                    received_at, ev["type"], ev["sev"], ev["subject"], ev["role"], ev["page"],
                                    json.dumps(ev["data"], ensure_ascii=False)))
                if not cur.rowcount:
                    conn.execute("RELEASE ev")
                    out["duplicates"] += 1
                    continue
                incident, regressed = _incident(conn, inst, ev) if ev["type"] in ("err.server", "err.client") else (None, None)
                _usage(conn, inst, ev)
                ticket_id = _ticket(conn, inst, ev) if ev["type"].startswith("fb.") else None
                fired = alerts.on_event(conn, ev, incident, now=now, channels=channels, deliver=False,
                                        regressed=regressed, ticket_id=ticket_id)
                conn.execute("RELEASE ev")
                out["stored"] += 1
                out["alerts"] += len(fired)
            except sqlite3.OperationalError:
                raise                                    # busy / disk: not this event's fault; keep the batch
            except Exception as error:  # noqa: BLE001 - one bad event never sinks the batch
                conn.execute("ROLLBACK TO ev")
                conn.execute("RELEASE ev")
                out["rejected"] += 1
                reasons[_reason(error)] += 1
        if len(events) > MAX_EVENTS:
            out["rejected"] += len(events) - MAX_EVENTS
            reasons[f"over {MAX_EVENTS} events in one batch"] += len(events) - MAX_EVENTS
        out["reasons"] = dict(reasons)
        if out["rejected"]:
            db.audit(conn, f"install:{inst['id']}", "events.rejected", None, count=out["rejected"], reasons=out["reasons"])
        if own:
            conn.execute("COMMIT")
    except BaseException:
        if own and conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return out


def _incident(conn, inst, ev):
    """The incident row after this event, and whether a known fingerprint showed up in a version it was not seen in
    before: None, 'fixed' (it had been marked fixed) or 'open'."""
    d = ev["data"]
    n = d.get("count", 1)
    row = conn.execute("SELECT * FROM incidents WHERE product = ? AND fingerprint = ?", (inst["product"], d["fingerprint"])).fetchone()
    regressed = None
    if row is None:
        conn.execute("INSERT INTO incidents (id, product, fingerprint, code, where_at, first_seen, last_seen, count, installs, "
                     "versions, status) VALUES (?,?,?,?,?,?,?,?,?,?, 'open')",
                     (db.uuid7(), inst["product"], d["fingerprint"], d["code"], d.get("where"), ev["ts"], ev["ts"], n,
                      json.dumps([inst["id"]]), json.dumps([ev["version"]])))
    else:
        old_versions = json.loads(row["versions"])
        installs = sorted(set(json.loads(row["installs"])) | {inst["id"]})
        versions = sorted(set(old_versions) | {ev["version"]})
        if ev["version"] not in old_versions:
            regressed = "fixed" if row["status"] == "fixed" else "open"
        status = "open" if row["status"] == "fixed" and ev["version"] not in old_versions else row["status"]
        conn.execute("UPDATE incidents SET last_seen = MAX(last_seen, ?), count = count + ?, installs = ?, versions = ?, "
                     "status = ? WHERE id = ?", (ev["ts"], n, json.dumps(installs), json.dumps(versions), status, row["id"]))
    return dict(conn.execute("SELECT * FROM incidents WHERE product = ? AND fingerprint = ?",
                             (inst["product"], d["fingerprint"])).fetchone()), regressed


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
    tid = db.uuid7()
    bundle = {k: d.get(k) for k in ("category", "page", "guide", "problem", "contact", "diagnostics") if d.get(k) is not None}
    bundle.update(kind=ev["type"], event_id=ev["id"], person=ev["subject"], version=ev["version"], env=ev["env"])
    conn.execute("INSERT INTO tickets (id, install_id, subject, message, bundle, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                 (tid, inst["id"], f"{KIND[ev['type']]} من صفحة {d.get('page') or '?'}", d.get("text") or "-",
                  json.dumps(bundle, ensure_ascii=False), "open", now, now))
    return tid


# ---------------------------------------------------------------- one batch, any path
def known_install(conn, install_id: str, hashed: str):
    """The install row for a matching token; None for an id this server has never registered (it goes to pending)."""
    if not isinstance(install_id, str) or not UUID_RE.match(install_id):
        raise Rejected(400, "bad install id")
    if not isinstance(hashed, str) or not re.fullmatch(r"[0-9a-f]{64}", hashed):
        raise Rejected(401, "install token required")
    inst = conn.execute("SELECT * FROM installs WHERE id = ?", (install_id,)).fetchone()
    if inst is None:
        return None
    if not same(inst["token_hash"], hashed):
        raise Rejected(401, "wrong token for this install")
    if not inst["active"]:
        raise Rejected(403, "install deactivated")
    return dict(inst)


def store_batch(conn, inst: dict, body: bytes, sent_at, received_at: str, now=None, channels=None) -> dict:
    if len(body) > MAX_GZIP:
        raise Rejected(413, "batch too large")
    events = decode(body)
    offset = 0
    if sent_at is not None:
        skew = int(_utc(received_at).timestamp() - int(sent_at))
        offset = skew if abs(skew) > SKEW_TOLERANCE_S else 0
        conn.execute("UPDATE installs SET clock_skew_s = ?, last_contact = MAX(COALESCE(last_contact, ''), ?) WHERE id = ?",
                     (skew, received_at, inst["id"]))
    out = ingest(conn, inst, events, now=now, channels=channels, ts_offset=offset, received_at=received_at)
    if offset:
        out["clock_corrected_s"] = offset
    return out


def _peek(body: bytes) -> dict:
    """product / node / version of an unknown PC, from its first event, for the owner to recognise it."""
    try:
        first = decode(body)[0]
        return {k: first[k] for k in ("product", "node", "version")
                if isinstance(first.get(k), str) and af_telemetry.ID_RE.match(first[k]) and not af_telemetry.LONG_DIGITS.search(first[k])}
    except Exception:  # noqa: BLE001 - only a hint for the dashboard
        return {}


def store_pending(conn, install_id: str, hashed: str, body: bytes, sent_at, received_at: str, source: str) -> dict:
    """A PC this server does not know yet. Trust on first use: its first token is pinned; the batch waits (small caps)
    until the owner approves it on the dashboard (approve_pending), or it ages out after 30 days."""
    if len(body) > PENDING_MAX_BODY:
        raise Rejected(413, "unapproved install: batch too large")
    row = conn.execute("SELECT * FROM pending_installs WHERE id = ?", (install_id,)).fetchone()
    if row is not None:
        if not same(row["token_hash"], hashed):
            raise Rejected(401, "token differs from this install's first contact")
        if row["batches"] >= PENDING_MAX_BATCHES:
            raise Rejected(429, "unapproved install: waiting for the owner's approval")
    elif conn.execute("SELECT COUNT(*) FROM pending_installs").fetchone()[0] >= PENDING_MAX_INSTALLS:
        raise Rejected(429, "too many unapproved installs")
    hint = _peek(body)
    with _txn(conn):
        if row is None:
            conn.execute("INSERT INTO pending_installs (id, token_hash, product, node, version, source, first_seen, last_seen, "
                         "batches, bytes) VALUES (?,?,?,?,?,?,?,?,0,0)", (install_id, hashed, hint.get("product"), hint.get("node"),
                                                                        hint.get("version"), source, received_at, received_at))
            db.audit(conn, f"install:{install_id}", "install.pending", install_id, product=hint.get("product"), source=source)
        conn.execute("INSERT INTO pending_batches (id, install_id, body, sent_at, received_at) VALUES (?,?,?,?,?)",
                     (db.uuid7(), install_id, body, sent_at, received_at))
        conn.execute("UPDATE pending_installs SET batches = batches + 1, bytes = bytes + ?, last_seen = ?, "
                     "version = COALESCE(?, version) WHERE id = ?", (len(body), received_at, hint.get("version"), install_id))
    return {"stored": 0, "duplicates": 0, "rejected": 0, "alerts": 0, "reasons": {}, "pending": True}


@contextlib.contextmanager
def _txn(conn):
    own = not conn.in_transaction
    if own:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        if own:
            conn.execute("COMMIT")
    except BaseException:
        if own and conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def handle(conn, install_id: str, hashed: str, body: bytes, sent_at, received_at: str, source: str, now=None,
           channels=None) -> dict:
    inst = known_install(conn, install_id, hashed)
    if inst is None:
        return store_pending(conn, install_id, hashed, body, sent_at, received_at, source)
    return store_batch(conn, inst, body, sent_at, received_at, now=now, channels=channels)


def quarantine(conn, install_id, source: str, reason: str, body: bytes | None) -> None:
    """Keep a batch that could not be stored (bad gzip, wrong token, over a cap) instead of losing it silently."""
    keep = body if body is not None and len(body) <= QUARANTINE_MAX_BODY else None
    conn.execute("INSERT INTO rejected_batches (id, install_id, source, reason, size, body, received_at) VALUES (?,?,?,?,?,?,?)",
                 (db.uuid7(), str(install_id)[:40] if install_id else None, source, reason[:120], len(body or b""), keep,
                  db.now_iso()))
    conn.execute("DELETE FROM rejected_batches WHERE id NOT IN (SELECT id FROM rejected_batches ORDER BY received_at DESC, "
                 "id DESC LIMIT ?)", (QUARANTINE_MAX_ROWS,))


def _int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def bearer(headers: dict) -> str:
    auth = str(headers.get("authorization", ""))
    return auth[7:].strip() if auth[:7].lower() == "bearer " else ""


def receive(conn, headers: dict, body: bytes, now=None, channels=None) -> dict:
    """One batch POSTed straight to this server (when it is reachable)."""
    h = {k.lower(): v for k, v in headers.items()}
    token = bearer(h)
    if not token or len(token) > 200:
        raise Rejected(401, "install token required")
    out = handle(conn, h.get("x-af-install", ""), token_hash(token), body, _int(h.get("x-af-sent-at")), db.now_iso(),
                 "direct", now=now, channels=channels)
    out["server_time"] = int(time.time())
    return out


# ---------------------------------------------------------------- relay
def _http(method, url, token, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def sync_relay_installs(conn, url: str, token: str, http=None, lock=None, force=False) -> int | None:
    """Tell the relay which installs exist (id + sha256 of the token, never the token) so it can refuse strangers
    cheaply and apply per-install caps. Only sent when the list changed, or once a day."""
    http = http or _http
    guard = lock or contextlib.nullcontext()
    with guard:
        found = [{"id": r["id"], "token_hash": r["token_hash"]} for r in
                 conn.execute("SELECT id, token_hash FROM installs WHERE active = 1 ORDER BY id")]
        digest = token_hash(json.dumps(found))
        row = conn.execute("SELECT v FROM settings WHERE k = 'relay_installs'").fetchone()
        last = json.loads(row[0]) if row else {}
    if not force and last.get("digest") == digest and time.time() - last.get("at", 0) < 86400:
        return None
    http("POST", f"{url.rstrip('/')}/installs", token, {"installs": found})
    with guard:
        conn.execute("INSERT INTO settings (k, v) VALUES ('relay_installs', ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                     (json.dumps({"digest": digest, "at": time.time()}),))
    return len(found)


def pull_relay(conn, url: str, token: str, http=None, limit: int = 100, now=None, lock=None, channels=None) -> dict:
    """Pull batches from the telemetry relay (templates/telemetry-relay) and acknowledge ONLY the ones that are safe
    here: stored, parked as pending, or kept in quarantine. Anything that failed for a temporary reason stays on the
    relay for the next pull. Network calls run outside `lock`, so the dashboard never waits for the relay."""
    http = http or _http
    guard = lock or contextlib.nullcontext()
    base = url.rstrip("/")
    sync_relay_installs(conn, base, token, http=http, lock=lock)
    got = http("GET", f"{base}/pull?limit={max(1, min(int(limit), 100))}", token)
    totals = {"batches": 0, "stored": 0, "pending": 0, "quarantined": 0, "kept": 0, "rejected": 0, "duplicates": 0, "alerts": 0}
    ack = []
    for b in got.get("batches", []):
        totals["batches"] += 1
        body = None
        try:
            body = base64.b64decode(b["body"], validate=True)
            received = _epoch_iso(b["received_at"])
            with guard:
                r = handle(conn, b["install_id"], b["token_hash"], body, _int(b.get("sent_at")), received, "relay",
                           now=now, channels=channels)
            if r.get("pending"):
                totals["pending"] += 1
            for k in ("stored", "rejected", "duplicates", "alerts"):
                totals[k] += r[k]
            ack.append(b["id"])
        except Rejected as error:
            if not error.permanent:
                totals["kept"] += 1
                continue
            with guard:
                quarantine(conn, b.get("install_id"), "relay", error.reason, body)
            totals["quarantined"] += 1
            ack.append(b.get("id"))
        except (KeyError, ValueError, TypeError, binascii.Error, OverflowError):
            with guard:
                quarantine(conn, b.get("install_id") if isinstance(b, dict) else None, "relay", "malformed relay row", body)
            totals["quarantined"] += 1
            if isinstance(b, dict) and b.get("id"):
                ack.append(b["id"])
        except Exception:  # noqa: BLE001 - database busy etc.: keep it on the relay and try again next time
            totals["kept"] += 1
    ack = [a for a in ack if isinstance(a, str) and a]
    for i in range(0, len(ack), 100):
        http("POST", f"{base}/ack", token, {"ids": ack[i:i + 100]})
    if totals["batches"]:
        with guard:
            db.audit(conn, "relay", "relay.pull", None, **totals)
    return totals


# ---------------------------------------------------------------- pending installs
def list_pending(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT id, product, node, version, source, first_seen, last_seen, batches, bytes "
                                          "FROM pending_installs ORDER BY first_seen DESC")]


def approve_pending(conn, pending_id: str, customer_id: str, tier: str, label: str | None, actor: str, product=None,
                    channels=None) -> dict:
    """Turn a pending PC into a registered install (keeping its own id and token) and replay its parked batches."""
    p = conn.execute("SELECT * FROM pending_installs WHERE id = ?", (pending_id,)).fetchone()
    if p is None:
        raise Rejected(404, "no pending install with this id")
    product = product or p["product"]
    if not product:
        raise Rejected(422, "product unknown: give it")
    with _txn(conn):
        conn.execute("INSERT INTO installs (id, customer_id, product, tier, label, device_fingerprint, token_hash, created_at)"
                     " VALUES (?,?,?,?,?,?,?,?)", (p["id"], customer_id, product, tier, label, None, p["token_hash"], db.now_iso()))
        db.audit(conn, actor, "install.approve", p["id"], product=product, tier=tier)
    inst = dict(conn.execute("SELECT * FROM installs WHERE id = ?", (p["id"],)).fetchone())
    out = {"id": p["id"], "batches": 0, "stored": 0, "rejected": 0, "quarantined": 0}
    for b in conn.execute("SELECT * FROM pending_batches WHERE install_id = ? ORDER BY received_at", (p["id"],)).fetchall():
        try:
            r = store_batch(conn, inst, b["body"], b["sent_at"], b["received_at"], channels=channels)
            out["stored"] += r["stored"]
            out["rejected"] += r["rejected"]
        except Rejected as error:
            quarantine(conn, p["id"], "pending", error.reason, b["body"])
            out["quarantined"] += 1
        conn.execute("DELETE FROM pending_batches WHERE id = ?", (b["id"],))
        out["batches"] += 1
    conn.execute("DELETE FROM pending_installs WHERE id = ?", (p["id"],))
    return out


def discard_pending(conn, pending_id: str, actor: str) -> bool:
    with _txn(conn):
        conn.execute("DELETE FROM pending_batches WHERE install_id = ?", (pending_id,))
        gone = conn.execute("DELETE FROM pending_installs WHERE id = ?", (pending_id,)).rowcount
        if gone:
            db.audit(conn, actor, "install.pending_discard", pending_id)
    return bool(gone)


def retention(conn, now=None) -> dict:
    """Raw events 90 days, nonces 1 day, alerts 12 months, fixed incidents 12 months after last seen,
    per-person daily usage 24 months (PARITY_PLAN §6.8); unapproved PCs and quarantined batches 30 days."""
    now = now or datetime.now(timezone.utc)
    cut = lambda days: (now - timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")  # noqa: E731
    out = {
        "events": conn.execute("DELETE FROM events WHERE received_at < ?", (cut(RETENTION_DAYS["events"]),)).rowcount,
        "nonces": conn.execute("DELETE FROM nonces WHERE at < ?", (cut(RETENTION_DAYS["nonces"]),)).rowcount,
        "incidents": conn.execute("DELETE FROM incidents WHERE status = 'fixed' AND last_seen < ?",
                                  (cut(RETENTION_DAYS["incidents_fixed"]),)).rowcount,
        "usage_daily": conn.execute("DELETE FROM usage_daily WHERE day < ?", (cut(RETENTION_DAYS["usage_daily"])[:10],)).rowcount,
        "rejected_batches": conn.execute("DELETE FROM rejected_batches WHERE received_at < ?",
                                         (cut(RETENTION_DAYS["rejected_batches"]),)).rowcount,
    }
    stale = cut(RETENTION_DAYS["pending"])
    conn.execute("DELETE FROM pending_batches WHERE install_id IN (SELECT id FROM pending_installs WHERE last_seen < ?)", (stale,))
    out["pending_installs"] = conn.execute("DELETE FROM pending_installs WHERE last_seen < ?", (stale,)).rowcount
    old = cut(RETENTION_DAYS["alerts"])
    conn.execute("DELETE FROM alert_deliveries WHERE alert_id IN (SELECT id FROM alerts WHERE created_at < ?)", (old,))
    out["alerts"] = conn.execute("DELETE FROM alerts WHERE created_at < ?", (old,)).rowcount
    return out
