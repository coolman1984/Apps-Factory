"""SQLite store with forward-only migrations. All IDs are UUIDv7 (ARCH-03); every write is audited (DATA-02)."""
from __future__ import annotations
import json
import os
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone

MIGRATIONS = [
    """
    CREATE TABLE customers (id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT, city TEXT,
        notes TEXT, created_at TEXT NOT NULL);
    CREATE TABLE installs (id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
        product TEXT NOT NULL, tier TEXT NOT NULL, label TEXT, device_fingerprint TEXT,
        token_hash TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
    CREATE TABLE heartbeats (id TEXT PRIMARY KEY, install_id TEXT NOT NULL REFERENCES installs(id),
        received_at TEXT NOT NULL, version TEXT NOT NULL, licence_state TEXT NOT NULL,
        last_backup_at TEXT, last_sync_at TEXT, pending_sync INTEGER, error_count INTEGER NOT NULL,
        disk_free_mb INTEGER);
    CREATE INDEX heartbeats_install ON heartbeats(install_id, received_at);
    CREATE TABLE licences (id TEXT PRIMARY KEY, licence_id TEXT NOT NULL UNIQUE, install_id TEXT REFERENCES installs(id),
        customer_id TEXT NOT NULL REFERENCES customers(id), product TEXT NOT NULL, expires TEXT NOT NULL,
        document TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
    CREATE TABLE tickets (id TEXT PRIMARY KEY, install_id TEXT NOT NULL REFERENCES installs(id),
        subject TEXT NOT NULL, message TEXT NOT NULL, bundle TEXT NOT NULL, status TEXT NOT NULL,
        vendor_reply TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE grants (id TEXT PRIMARY KEY, install_id TEXT NOT NULL REFERENCES installs(id),
        ticket_id TEXT REFERENCES tickets(id), scopes TEXT NOT NULL, approved_by TEXT NOT NULL,
        code TEXT NOT NULL, expires_at TEXT NOT NULL, ended_at TEXT, ended_by TEXT, created_at TEXT NOT NULL);
    CREATE TABLE repairs (id TEXT PRIMARY KEY, install_id TEXT NOT NULL REFERENCES installs(id),
        grant_id TEXT NOT NULL REFERENCES grants(id), action TEXT NOT NULL, approved_by TEXT NOT NULL,
        requested_by TEXT NOT NULL, status TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL);
    CREATE TABLE vendor_tokens (id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
    CREATE TABLE audit (id TEXT PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
        object_id TEXT, detail TEXT NOT NULL);
    """,
    # 2: consented telemetry (TEL-01..03), incidents, per-person usage, alerts with per-channel delivery log
    """
    CREATE TABLE events (id TEXT PRIMARY KEY, install_id TEXT NOT NULL REFERENCES installs(id), node TEXT,
        product TEXT NOT NULL, version TEXT NOT NULL, env TEXT NOT NULL, ts TEXT NOT NULL, received_at TEXT NOT NULL,
        type TEXT NOT NULL, sev TEXT NOT NULL, subject TEXT, role TEXT, page TEXT, data TEXT NOT NULL);
    CREATE INDEX events_install ON events(install_id, ts);
    CREATE INDEX events_type ON events(type, ts);
    CREATE TABLE nonces (install_id TEXT NOT NULL, nonce TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY (install_id, nonce));
    CREATE TABLE incidents (id TEXT PRIMARY KEY, product TEXT NOT NULL, fingerprint TEXT NOT NULL, code TEXT NOT NULL,
        where_at TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, count INTEGER NOT NULL,
        installs TEXT NOT NULL, versions TEXT NOT NULL, status TEXT NOT NULL, UNIQUE (product, fingerprint));
    CREATE TABLE usage_daily (day TEXT NOT NULL, install_id TEXT NOT NULL, subject TEXT NOT NULL, type TEXT NOT NULL,
        item TEXT NOT NULL, count INTEGER NOT NULL, PRIMARY KEY (day, install_id, subject, type, item));
    CREATE TABLE alerts (id TEXT PRIMARY KEY, rule TEXT NOT NULL, severity TEXT NOT NULL, install_id TEXT,
        title TEXT NOT NULL, detail TEXT NOT NULL, dedupe_key TEXT NOT NULL, created_at TEXT NOT NULL,
        acked_at TEXT, acked_by TEXT);
    CREATE INDEX alerts_dedupe ON alerts(dedupe_key, created_at);
    CREATE TABLE alert_deliveries (id TEXT PRIMARY KEY, alert_id TEXT NOT NULL REFERENCES alerts(id),
        channel TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL, attempted_at TEXT NOT NULL, ms INTEGER NOT NULL);
    CREATE INDEX alert_deliveries_alert ON alert_deliveries(alert_id);
    CREATE TABLE settings (k TEXT PRIMARY KEY, v TEXT NOT NULL);
    """,
    # 3: telemetry hardening (0.9.0): new PCs wait as pending installs instead of being dropped; batches that cannot be
    # stored are kept (quarantine) instead of lost; alerts are queued and sent outside the database lock; clock skew
    """
    ALTER TABLE installs ADD COLUMN clock_skew_s INTEGER;
    ALTER TABLE installs ADD COLUMN last_contact TEXT;
    ALTER TABLE alerts ADD COLUMN delivery TEXT NOT NULL DEFAULT 'done';
    CREATE INDEX alerts_delivery ON alerts(delivery);
    CREATE TABLE pending_installs (id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, product TEXT, node TEXT, version TEXT,
        source TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, batches INTEGER NOT NULL, bytes INTEGER NOT NULL);
    CREATE TABLE pending_batches (id TEXT PRIMARY KEY, install_id TEXT NOT NULL REFERENCES pending_installs(id),
        body BLOB NOT NULL, sent_at INTEGER, received_at TEXT NOT NULL);
    CREATE INDEX pending_batches_install ON pending_batches(install_id);
    CREATE TABLE rejected_batches (id TEXT PRIMARY KEY, install_id TEXT, source TEXT NOT NULL, reason TEXT NOT NULL,
        size INTEGER NOT NULL, body BLOB, received_at TEXT NOT NULL);
    """,
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def uuid7() -> str:
    ms = int(time.time() * 1000)
    value = (ms & ((1 << 48) - 1)) << 80 | 0x7 << 76 | secrets.randbits(12) << 64 | 0b10 << 62 | secrets.randbits(62)
    return str(uuid.UUID(int=value))


def connect(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    current = row["version"] if row else 0
    for number, script in enumerate(MIGRATIONS[current:], start=current + 1):
        conn.execute("BEGIN")
        try:
            for statement in filter(str.strip, script.split(";")):
                conn.execute(statement)
            conn.execute("DELETE FROM schema_version")
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (number,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return len(MIGRATIONS)


def audit(conn: sqlite3.Connection, actor: str, action: str, object_id: str | None, **detail) -> None:
    conn.execute("INSERT INTO audit (id, at, actor, action, object_id, detail) VALUES (?,?,?,?,?,?)",
                 (uuid7(), now_iso(), actor, action, object_id, json.dumps(detail, ensure_ascii=False)))
