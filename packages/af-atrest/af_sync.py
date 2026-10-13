"""Crash-safe offline outbox for vendor escrow and off-site backup uploads."""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import time
from typing import Protocol

import af_atrest as core
from af_errors import AtRestError
from af_escrow import upload_escrow
from af_offsite import load_settings, offsite_due_today, save_settings, upload_offsite_backup

OUTBOX_DB = 'af-atrest-sync.sqlite'
SYNC_STATE_FILE = 'af-atrest-sync-state.json'
BACKOFF_MIN_S = 30.0
BACKOFF_MAX_S = 3600.0

_KIND_ESCROW = 'escrow'
_KIND_BACKUP = 'backup'


class Transport(Protocol):
    def post(self, url: str, headers: dict, body: bytes) -> tuple[int, bytes]: ...


def _outbox_path(data_dir: str) -> str:
    return os.path.join(os.path.abspath(data_dir), OUTBOX_DB)


def _state_path(data_dir: str) -> str:
    return os.path.join(os.path.abspath(data_dir), SYNC_STATE_FILE)


def _connect(data_dir: str) -> sqlite3.Connection:
    path = _outbox_path(data_dir)
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=FULL')
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS outbox (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          kind TEXT NOT NULL,
          payload TEXT NOT NULL,
          created REAL NOT NULL,
          tries INTEGER NOT NULL DEFAULT 0,
          next_try REAL NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS outbox_due ON outbox (next_try, id);
        """
    )
    return conn


def load_sync_state(data_dir: str) -> dict:
    path = _state_path(data_dir)
    base = {_KIND_ESCROW: None, _KIND_BACKUP: None}
    if not os.path.isfile(path):
        return base
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        raise AtRestError('ATREST_SYNC_STATE_BAD') from None
    if not isinstance(data, dict):
        raise AtRestError('ATREST_SYNC_STATE_BAD')
    for k in base:
        if k in data and data[k] is not None:
            base[k] = float(data[k])
    return base


def save_sync_state(data_dir: str, state: dict) -> None:
    path = _state_path(data_dir)
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f, sort_keys=True, indent=2)
        f.write('\n')
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _mark_success(data_dir: str, kind: str, when: float) -> None:
    state = load_sync_state(data_dir)
    state[kind] = when
    save_sync_state(data_dir, state)


def _token_field(data_dir: str, company_token: str) -> dict:
    sealed = core.seal_outbox_secret(data_dir, company_token)
    return {'company_token_enc': base64.b64encode(sealed).decode('ascii')}


def _payload_company_token(data_dir: str, payload: dict) -> str:
    enc = payload.get('company_token_enc')
    if isinstance(enc, str) and enc:
        try:
            return core.open_outbox_secret(data_dir, base64.b64decode(enc))
        except (ValueError, OSError):
            raise AtRestError('ATREST_SYNC_STATE_BAD') from None
    tok = payload.get('company_token')
    if isinstance(tok, str) and tok:
        return tok
    raise AtRestError('ATREST_SYNC_STATE_BAD')


def enqueue_escrow(
    data_dir: str,
    worker_url: str,
    company_token: str,
    package: dict,
    *,
    now: float | None = None,
) -> int:
    now = now if now is not None else time.time()
    body = {
        'worker_url': worker_url,
        'package': package,
        **_token_field(data_dir, company_token),
    }
    payload = json.dumps(body, sort_keys=True, separators=(',', ':'))
    conn = _connect(data_dir)
    try:
        cur = conn.execute(
            'INSERT INTO outbox (kind, payload, created, tries, next_try) VALUES (?,?,?,?,?)',
            (_KIND_ESCROW, payload, now, 0, now),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def enqueue_backup(
    data_dir: str,
    worker_url: str,
    company_token: str,
    company_id: str,
    device_code: str,
    backup_path: str,
    settings_path: str,
    *,
    now: float | None = None,
) -> int:
    now = now if now is not None else time.time()
    body = {
        'worker_url': worker_url,
        'company_id': company_id,
        'device_code': device_code,
        'backup_path': backup_path,
        'settings_path': settings_path,
        **_token_field(data_dir, company_token),
    }
    payload = json.dumps(body, sort_keys=True, separators=(',', ':'))
    conn = _connect(data_dir)
    try:
        cur = conn.execute(
            'INSERT INTO outbox (kind, payload, created, tries, next_try) VALUES (?,?,?,?,?)',
            (_KIND_BACKUP, payload, now, 0, now),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def outbox_pending(data_dir: str, kind: str | None = None) -> int:
    conn = _connect(data_dir)
    try:
        if kind:
            row = conn.execute('SELECT COUNT(*) FROM outbox WHERE kind = ?', (kind,)).fetchone()
        else:
            row = conn.execute('SELECT COUNT(*) FROM outbox').fetchone()
        return int(row[0])
    finally:
        conn.close()


def _backoff_seconds(tries: int) -> float:
    return min(BACKOFF_MAX_S, BACKOFF_MIN_S * (2 ** max(0, tries - 1)))


def _send_escrow(row_id: int, payload: dict, transport: Transport, now: float, data_dir: str) -> None:
    token = _payload_company_token(data_dir, payload)
    pkg = payload['package']
    company_id = pkg.get('company_id') if isinstance(pkg, dict) else ''
    upload_escrow(
        payload['worker_url'],
        token,
        str(company_id or ''),
        pkg,
        transport=transport,
    )
    _mark_success(data_dir, _KIND_ESCROW, now)


def _send_backup(row_id: int, payload: dict, transport: Transport, now: float, data_dir: str) -> None:
    settings_path = payload['settings_path']
    settings = load_settings(settings_path)
    if not settings.get('enabled'):
        raise AtRestError('ATREST_OFFSITE_DISABLED')
    upload_offsite_backup(
        payload['worker_url'],
        _payload_company_token(data_dir, payload),
        payload['company_id'],
        payload['device_code'],
        payload['backup_path'],
        transport,
    )
    settings['last_upload_date'] = settings.get('last_upload_date')
    from af_offsite import business_date_today

    tz = settings.get('timezone') or 'Africa/Cairo'
    settings['last_upload_date'] = business_date_today(tz)
    save_settings(settings_path, settings)
    _mark_success(data_dir, _KIND_BACKUP, now)


def flush_sync_queue(
    data_dir: str,
    transport: Transport,
    *,
    now: float | None = None,
) -> tuple[int, int]:
    """Try due outbox rows. Returns (sent_count, failed_count)."""
    now = now if now is not None else time.time()
    sent = failed = 0
    conn = _connect(data_dir)
    try:
        while True:
            row = conn.execute(
                'SELECT id, kind, payload, tries FROM outbox WHERE next_try <= ? ORDER BY id LIMIT 1',
                (now,),
            ).fetchone()
            if not row:
                break
            row_id, kind, payload_s, tries = row
            try:
                payload = json.loads(payload_s)
            except json.JSONDecodeError:
                conn.execute('DELETE FROM outbox WHERE id = ?', (row_id,))
                conn.commit()
                failed += 1
                continue
            try:
                if kind == _KIND_ESCROW:
                    _send_escrow(row_id, payload, transport, now, data_dir)
                elif kind == _KIND_BACKUP:
                    _send_backup(row_id, payload, transport, now, data_dir)
                else:
                    conn.execute('DELETE FROM outbox WHERE id = ?', (row_id,))
                    conn.commit()
                    failed += 1
                    continue
                conn.execute('DELETE FROM outbox WHERE id = ?', (row_id,))
                conn.commit()
                sent += 1
            except AtRestError:
                tries += 1
                nxt = now + _backoff_seconds(tries)
                conn.execute(
                    'UPDATE outbox SET tries = ?, next_try = ? WHERE id = ?',
                    (tries, nxt, row_id),
                )
                conn.commit()
                failed += 1
                break
            except OSError:
                tries += 1
                nxt = now + _backoff_seconds(tries)
                conn.execute(
                    'UPDATE outbox SET tries = ?, next_try = ? WHERE id = ?',
                    (tries, nxt, row_id),
                )
                conn.commit()
                failed += 1
                break
    finally:
        conn.close()
    return sent, failed


def maybe_enqueue_daily_backup(
    data_dir: str,
    settings_path: str,
    worker_url: str,
    company_token: str,
    company_id: str,
    device_code: str,
    backup_path: str,
    *,
    now: float | None = None,
) -> bool:
    """If off-site backup is enabled and due today, queue one upload. Returns True if queued."""
    settings = load_settings(settings_path)
    if not settings.get('enabled'):
        return False
    if not offsite_due_today(settings):
        return False
    enqueue_backup(
        data_dir,
        worker_url,
        company_token,
        company_id,
        device_code,
        backup_path,
        settings_path,
        now=now,
    )
    return True


def sync_warning(
    data_dir: str,
    *,
    now: float | None = None,
    warn_after_days: int = 3,
) -> dict[str, str] | None:
    """Bilingual warning when escrow or backup has not synced within ``warn_after_days``."""
    now = now if now is not None else time.time()
    threshold = warn_after_days * 86400.0
    state = load_sync_state(data_dir)
    escrow_pending = outbox_pending(data_dir, _KIND_ESCROW) > 0
    backup_pending = outbox_pending(data_dir, _KIND_BACKUP) > 0
    escrow_stale = escrow_pending or state[_KIND_ESCROW] is None or (now - state[_KIND_ESCROW]) > threshold
    backup_stale = backup_pending or state[_KIND_BACKUP] is None or (now - state[_KIND_BACKUP]) > threshold
    if not escrow_stale and not backup_stale:
        return None
    parts_en: list[str] = []
    parts_ar: list[str] = []
    if escrow_stale:
        parts_en.append('vendor key escrow has not synced recently')
        parts_ar.append('لم يتم مزامنة ضمان المفتاح مع المورّد مؤخرًا')
    if backup_stale:
        parts_en.append('encrypted off-site backup has not synced recently')
        parts_ar.append('لم يتم مزامنة النسخة الاحتياطية المشفّرة خارج الموقع مؤخرًا')
    en = 'Warning: ' + '; '.join(parts_en) + '. The app keeps working offline; uploads retry when online.'
    ar = 'تنبيه: ' + '؛ '.join(parts_ar) + '. التطبيق يعمل دون اتصال؛ تُعاد المحاولة عند توفر الشبكة.'
    return {'en': en, 'ar': ar}
