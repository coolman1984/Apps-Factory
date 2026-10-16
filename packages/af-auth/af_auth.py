"""af-auth: sign-up approval, password reset codes, login lockout and admin-safety guards (stdlib only).

Products vendor this file with `python scripts/vendor_auth.py <product>` → `server/afauth.py`.
The server still owns sessions, permission catalogues and replication wiring; this module holds the
rules proven in Trip Orders v1.1.5 (pending/approve/refuse/suspend, single-use reset codes that
replicate when burned, sole-admin lockout exemption, last-manager guards).

    python -m unittest discover -s tests
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

__version__ = '0.1.0'

USERNAME_RE = re.compile(r'^[A-Za-z0-9._-]{3,32}$')
USER_STATUSES = ('pending', 'approved', 'rejected', 'suspended')
RESET_CODE_HOURS = 24
RESET_CODE_MAX_ATTEMPTS = 3
MAX_PENDING_SIGNUPS = 25
REQUEST_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
DEFAULT_MANAGE = 'users.manage'
ITERATIONS = 600_000
COMMON = {
    'password', 'password1', 'password123', '12345678', '123456789', '1234567890', '11111111', '00000000',
    'qwerty123', 'qwertyuiop', 'abc12345', 'admin123', 'admin1234', 'administrator', 'welcome1', 'welcome123',
    'letmein1', 'iloveyou', 'company1', 'company123', 'changeme', 'p@ssw0rd', 'passw0rd', '87654321', '12341234',
    'aa123456',
}
LOCAL_USER_COLS = frozenset({'failed', 'locked_until'})
REPLICATED_USER_COLS = frozenset({
    'username', 'full_name', 'title', 'pw_hash', 'perms', 'scopes', 'role', 'active', 'deleted', 'must_change',
    'pw_changed_at', 'notes', 'created_at', 'created_by', 'updated_at', 'updated_by', 'status', 'status_reason',
    'status_at', 'status_by', 'request_code',
})


class AuthError(Exception):
    """Wrong login, weak password, policy refusal (maps to HTTP 400/401 in products)."""

    def __init__(self, msg='', key='', **vars):
        super().__init__(msg)
        self.key = key
        self.vars = vars


def now() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _parse(ts: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(ts) if ts else None


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), salt, ITERATIONS)
    return f'pbkdf2_sha256${ITERATIONS}${salt.hex()}${dk.hex()}'


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, n, salt, dk = stored.split('$')
        if algo != 'pbkdf2_sha256':
            return False
        test = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), bytes.fromhex(salt), int(n))
        return hmac.compare_digest(test.hex(), dk)
    except (ValueError, AttributeError):
        return False


_DUMMY = hash_password(secrets.token_hex(8))


def check_password(pw: str, username: str = '', full_name: str = '', min_len: int = 8) -> None:
    pw = pw or ''
    if len(pw) < min_len:
        raise AuthError(f'The password must have at least {min_len} characters.', key='autherr.pwShort', n=min_len)
    if len(pw) > 128:
        raise AuthError('The password is too long (maximum 128 characters).', key='autherr.pwLong')
    low = pw.lower()
    if low in COMMON or len(set(pw)) < 3:
        raise AuthError('This password is too easy to guess. Choose another one.', key='autherr.pwEasy')
    for part in [username] + (full_name or '').split():
        if part and len(part) >= 3 and part.lower() in low:
            raise AuthError('The password must not contain the user name or the person\'s name.', key='autherr.pwContains')
    if not (re.search(r'[A-Za-z]', pw) and re.search(r'[^A-Za-z]', pw)):
        raise AuthError('The password must contain letters and at least one number or symbol.', key='autherr.pwLetters')


def request_code() -> str:
    return ''.join(secrets.choice(REQUEST_CODE_ALPHABET) for _ in range(6))


def reset_code_plain() -> str:
    return ''.join(secrets.choice(REQUEST_CODE_ALPHABET) for _ in range(8))


def normalize_reset_code(code: str) -> str:
    return re.sub(r'[\s\-]', '', (code or '')).upper()


def status_message(status: str, reason: str = '') -> str:
    st = status or 'approved'
    if st == 'pending':
        return 'Your sign-up is waiting for the administrator to approve it.'
    if st == 'rejected':
        r = (reason or '').strip()
        return 'Your sign-up was refused.' + (f' Reason: {r}' if r else ' Talk to the administrator.')
    if st == 'suspended':
        return 'Your account is suspended. Talk to the administrator.'
    return ''


def sole_admin_id(rows: Iterable[Mapping[str, Any]], manage: str = DEFAULT_MANAGE) -> Optional[str]:
    """When only one active user may manage people, account lockout must not block the office."""
    admins = []
    for r in rows:
        if not r.get('deleted') and r.get('active'):
            perms = r.get('perms') or []
            if isinstance(perms, str):
                perms = json.loads(perms or '[]')
            if manage in perms:
                admins.append(r['id'])
    return admins[0] if len(admins) == 1 else None


def count_active_managers(rows: Iterable[Mapping[str, Any]], exclude: Optional[str] = None, manage: str = DEFAULT_MANAGE) -> int:
    n = 0
    for r in rows:
        if r.get('deleted') or not r.get('active'):
            continue
        if exclude and r['id'] == exclude:
            continue
        perms = r.get('perms') or []
        if isinstance(perms, str):
            perms = json.loads(perms or '[]')
        if manage in perms:
            n += 1
    return n


def loses_last_manager(
    row: Mapping[str, Any],
    all_rows: Iterable[Mapping[str, Any]],
    new_active: bool,
    new_perms: Optional[Sequence[str]] = None,
    manage: str = DEFAULT_MANAGE,
) -> bool:
    if not row or not row.get('active'):
        return False
    old_perms = row.get('perms') or []
    if isinstance(old_perms, str):
        old_perms = json.loads(old_perms or '[]')
    if manage not in old_perms:
        return False
    perms = list(new_perms) if new_perms is not None else list(old_perms)
    if new_active and manage in perms:
        return False
    return count_active_managers(all_rows, exclude=row['id'], manage=manage) == 0


def signup_username_blocked(existing: Optional[Mapping[str, Any]]) -> bool:
    """Suspended and other non-rejected usernames cannot register again."""
    if not existing or existing.get('deleted'):
        return bool(existing and existing.get('deleted'))
    st = existing.get('status') or 'approved'
    return st != 'rejected'


def clear_reset_code_op(uid: str, reset_hash: str) -> dict:
    return {
        'e': 'userCommands', 'id': uuid.uuid4().hex, 'op': 'insert', 'noaudit': True,
        's': {'cmd': 'clear-reset-code', 'user': uid, 'reset_hash': reset_hash},
    }


def set_reset_code_op(uid: str, reset_hash: str, reset_expires: str) -> dict:
    return {
        'e': 'userCommands', 'id': uuid.uuid4().hex, 'op': 'insert', 'noaudit': True,
        's': {'cmd': 'set-reset-code', 'user': uid, 'reset_hash': reset_hash, 'reset_expires': reset_expires},
    }


def apply_user_command(conn: sqlite3.Connection, cmd: Mapping[str, Any]) -> None:
    s = cmd.get('s') or cmd
    name = s.get('cmd')
    if name == 'unlock':
        conn.execute('UPDATE users SET failed=0, locked_until=NULL WHERE id=?', (s.get('user'),))
    elif name == 'set-reset-code':
        conn.execute('UPDATE users SET reset_hash=?, reset_expires=? WHERE id=?',
                     (s.get('reset_hash'), s.get('reset_expires'), s.get('user')))
    elif name == 'clear-reset-code':
        uid = s.get('user')
        bound = s.get('reset_hash')
        if bound:
            cur = conn.execute('SELECT reset_hash FROM users WHERE id=?', (uid,)).fetchone()
            if not cur or cur['reset_hash'] != bound:
                return
        conn.execute('UPDATE users SET reset_hash=?, reset_expires=? WHERE id=?', ('', '', uid))
    elif name == 'logout':
        conn.execute('DELETE FROM sessions WHERE user_id=?', (s.get('user'),))


def journal_clear_reset_hashes(ops: Iterable[Mapping[str, Any]]) -> List[str]:
    out = []
    for op in ops:
        s = (op.get('s') or {}) if isinstance(op, dict) else {}
        if s.get('cmd') == 'clear-reset-code':
            out.append(s.get('reset_hash') or '')
    return out


def login_failure_update(
    failed: int,
    sole_admin: bool,
    max_failed: int,
    lock_minutes: int,
    now_dt: Optional[datetime] = None,
) -> Tuple[int, Optional[str]]:
    """Returns (new_failed, locked_until iso or None). Sole admin never gets locked_until."""
    now_dt = now_dt or datetime.now()
    failed = int(failed or 0) + 1
    if sole_admin:
        return failed, None
    locked = None
    if failed >= max_failed:
        locked = (now_dt + timedelta(minutes=lock_minutes)).isoformat(timespec='seconds')
    return (0 if locked else failed), locked


def reset_guess_update(
    failed: int,
    sole_admin: bool,
    max_failed: int,
    lock_minutes: int,
    reset_attempts: int,
    expired: bool,
    now_dt: Optional[datetime] = None,
) -> Tuple[int, Optional[str], bool, bool]:
    """Wrong reset code: (failed, locked_until, burn_reset, clear_lock_counter_on_lock)."""
    now_dt = now_dt or datetime.now()
    failed = int(failed or 0) + 1
    burn = failed >= reset_attempts or expired
    locked = None
    if not sole_admin and failed >= max_failed:
        locked = (now_dt + timedelta(minutes=lock_minutes)).isoformat(timespec='seconds')
    clear_failed_on_lock = bool(locked)
    return (0 if locked else failed), locked, burn, clear_failed_on_lock


def patch_user_row(conn: sqlite3.Connection, uid: str, fields: Mapping[str, Any]) -> None:
    """Apply replicated user fields without touching local lockout counters."""
    safe = {k: v for k, v in fields.items() if k in REPLICATED_USER_COLS}
    if not safe:
        return
    cols = ', '.join(f'{k}=?' for k in safe)
    conn.execute(f'UPDATE users SET {cols}, ver=ver+1 WHERE id=?', (*safe.values(), uid))


class AuthStore:
    """SQLite-backed auth rules with an append-only replicated-op journal for tests and small LAN products."""

    def __init__(self, path: str = ':memory:', cfg: Optional[Mapping[str, Any]] = None):
        cfg = dict(cfg or {})
        self.max_failed = max(3, int(cfg.get('max_failed_logins', 5)))
        self.lock_minutes = max(1, int(cfg.get('lockout_minutes', 15)))
        self.min_len = max(8, int(cfg.get('min_password_length', 8)))
        self.manage = str(cfg.get('manage_permission', DEFAULT_MANAGE))
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self._journal: List[List[dict]] = []
        self._on_commit: Optional[Callable[[List[dict]], None]] = cfg.get('on_commit')
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE, full_name TEXT NOT NULL,
                title TEXT, pw_hash TEXT NOT NULL, perms TEXT NOT NULL DEFAULT '[]', scopes TEXT, role TEXT,
                active INTEGER NOT NULL DEFAULT 1, deleted INTEGER NOT NULL DEFAULT 0, must_change INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0, locked_until TEXT, reset_hash TEXT, reset_expires TEXT,
                status TEXT, status_reason TEXT, status_at TEXT, status_by TEXT, request_code TEXT,
                last_login TEXT, last_ip TEXT, pw_changed_at TEXT,
                created_at TEXT, created_by TEXT, updated_at TEXT, updated_by TEXT, ver INTEGER NOT NULL DEFAULT 1, notes TEXT);
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, created TEXT, last_seen TEXT, ip TEXT, agent TEXT);
        ''')
        self.conn.execute("UPDATE users SET status='approved' WHERE status IS NULL OR status=''")

    def close(self) -> None:
        self.conn.close()

    def journal_ops(self) -> List[dict]:
        out: List[dict] = []
        for batch in self._journal:
            out.extend(batch)
        return out

    def _commit(self, ops: List[dict], apply_local: Optional[Callable[[], None]] = None) -> None:
        with self.lock:
            if apply_local:
                apply_local()
            for op in ops:
                self._apply_op(op)
            self._journal.append(list(ops))
            if self._on_commit:
                self._on_commit(ops)

    def _apply_op(self, op: dict) -> None:
        e = op.get('e')
        if e == 'users':
            uid = op.get('id')
            s = op.get('s') or {}
            row = self.conn.execute('SELECT id FROM users WHERE id=?', (uid,)).fetchone()
            if row is None and op.get('op') == 'insert':
                r = op.get('r') or {'id': uid, **s}
                cols = [k for k in r if k in REPLICATED_USER_COLS or k == 'id']
                vals = [r[k] for k in cols]
                if isinstance(vals[cols.index('perms')] if 'perms' in cols else None, list):
                    i = cols.index('perms')
                    vals[i] = json.dumps(vals[i])
                self.conn.execute(
                    f'INSERT INTO users ({", ".join(cols)}) VALUES ({", ".join("?" * len(cols))})',
                    vals,
                )
            else:
                patch_user_row(self.conn, uid, s)
        elif e == 'userCommands':
            apply_user_command(self.conn, op)

    def rebuild_from_journal(self) -> None:
        """Drop replicated user state and replay the journal (simulates multi-PC fold)."""
        with self.lock:
            self.conn.execute('DELETE FROM users')
            self.conn.execute('DELETE FROM sessions')
            for batch in self._journal:
                for op in batch:
                    self._apply_op(op)

    def _rows(self) -> List[dict]:
        return [dict(r) for r in self.conn.execute('SELECT * FROM users WHERE deleted=0')]

    def _user(self, row: Optional[sqlite3.Row]) -> Optional[dict]:
        if not row:
            return None
        u = dict(row)
        u['perms'] = json.loads(u['perms'] or '[]')
        u['active'] = bool(u['active'])
        u['deleted'] = bool(u['deleted'])
        u['status'] = u.get('status') or 'approved'
        return u

    def get_by_username(self, username: str) -> Optional[dict]:
        with self.lock:
            r = self.conn.execute('SELECT * FROM users WHERE username=? AND deleted=0', (username.strip(),)).fetchone()
        return self._user(r)

    def get(self, uid: str) -> Optional[dict]:
        with self.lock:
            r = self.conn.execute('SELECT * FROM users WHERE id=? AND deleted=0', (uid,)).fetchone()
        return self._user(r)

    def has_users(self) -> bool:
        with self.lock:
            return self.conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] > 0

    def setup(self, username: str, full_name: str, password: str, ip: str = '') -> str:
        username, full_name = (username or '').strip(), (full_name or '').strip()
        if not USERNAME_RE.match(username):
            raise AuthError('User name: 3-32 letters, numbers, dot, dash or underscore (no spaces).', key='autherr.username')
        if not full_name:
            raise AuthError('Enter the full name.', key='autherr.fullname')
        check_password(password, username, full_name, self.min_len)
        if self.has_users():
            raise AuthError('The administrator account already exists. Please log in.', key='autherr.adminExists')
        ts = now()
        uid = uuid.uuid4().hex
        h = hash_password(password)
        row = {
            'username': username, 'full_name': full_name, 'title': 'Administrator', 'pw_hash': h,
            'perms': json.dumps([self.manage]), 'scopes': None, 'role': 'Administrator', 'active': 1, 'deleted': 0,
            'must_change': 0, 'pw_changed_at': ts, 'status': 'approved', 'status_reason': '', 'status_at': ts,
            'status_by': 'First setup', 'request_code': '', 'notes': '', 'created_at': ts, 'created_by': 'First setup',
            'updated_at': ts, 'updated_by': 'First setup',
        }
        self.conn.execute(
            f'INSERT INTO users (id, {", ".join(row)}) VALUES (?, {", ".join("?" * len(row))})',
            (uid, *row.values()),
        )
        return uid

    def register(self, username: str, full_name: str, password: str, ip: str = '', title: str = '', notes: str = '') -> dict:
        if not self.has_users():
            raise AuthError('The administrator account does not exist yet.', key='autherr.noAdmin')
        username, full_name = (username or '').strip(), (full_name or '').strip()
        if not USERNAME_RE.match(username):
            raise AuthError('User name: 3-32 letters, numbers, dot, dash or underscore (no spaces).', key='autherr.username')
        if not full_name:
            raise AuthError('Enter the full name.', key='autherr.fullname')
        check_password(password, username, full_name, self.min_len)
        with self.lock:
            pending_n = self.conn.execute("SELECT COUNT(*) FROM users WHERE deleted=0 AND status='pending'").fetchone()[0]
            existing = self.conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if pending_n >= MAX_PENDING_SIGNUPS:
            raise AuthError('Too many sign-up requests are waiting.', key='autherr.signupQueue')
        ts = now()
        code = request_code()
        h = hash_password(password)
        if existing:
            ex = self._user(existing)
            if signup_username_blocked(ex):
                raise AuthError('This user name is already taken.', key='autherr.usernameTaken')
            uid = ex['id']
            st = ex.get('status') or 'approved'
            row = {
                'full_name': full_name, 'title': (title or '')[:80], 'pw_hash': h, 'perms': '[]', 'scopes': None,
                'role': 'Custom', 'active': 0, 'must_change': 0, 'pw_changed_at': ts,
                'status': 'pending', 'status_reason': '', 'status_at': ts, 'status_by': 'Self sign-up', 'request_code': code,
                'notes': (notes or '')[:500], 'updated_at': ts, 'updated_by': 'Self sign-up',
            }
            ops: List[dict] = [{'e': 'users', 'id': uid, 'op': 'update', 's': row}]
            bound = (ex.get('reset_hash') or '') if ex else ''
            extra_ops: List[dict] = []

            def apply_local():
                self.conn.execute('UPDATE users SET failed=0, locked_until=NULL, reset_hash=?, reset_expires=? WHERE id=?',
                                  ('', '', uid))

            if bound:
                extra_ops.append(clear_reset_code_op(uid, bound))
            self._commit(ops + extra_ops, apply_local=apply_local)
            return {'ok': True, 'request_code': code}
        uid = uuid.uuid4().hex
        row = {
            'username': username, 'full_name': full_name, 'title': (title or '')[:80], 'pw_hash': h, 'perms': '[]',
            'scopes': None, 'role': 'Custom', 'active': 0, 'deleted': 0, 'must_change': 0, 'pw_changed_at': ts,
            'status': 'pending', 'status_reason': '', 'status_at': ts, 'status_by': 'Self sign-up', 'request_code': code,
            'notes': (notes or '')[:500], 'created_at': ts, 'created_by': 'Self sign-up', 'updated_at': ts,
            'updated_by': 'Self sign-up',
        }
        self._commit([{'e': 'users', 'id': uid, 'op': 'insert', 's': row, 'r': {'id': uid, **row}}])
        return {'ok': True, 'request_code': code}

    def review(self, uid: str, decision: str, reason: str = '', perms: Optional[Sequence[str]] = None) -> dict:
        if decision not in ('approve', 'reject', 'suspend'):
            raise AuthError('Unknown decision.')
        u = self.get(uid)
        if not u:
            raise AuthError('This user no longer exists.')
        st = u.get('status') or 'approved'
        if decision == 'approve' and st not in ('pending', 'rejected', 'suspended'):
            raise AuthError('This account cannot be approved from its current state.')
        if decision == 'reject' and st != 'pending':
            raise AuthError('Only a waiting sign-up can be refused.')
        if decision == 'suspend' and st not in ('pending', 'approved'):
            raise AuthError('This account cannot be suspended from its current state.')
        reason = str(reason or '').strip()[:400]
        if decision == 'reject' and len(reason) < 3:
            raise AuthError('Write the reason for refusing the sign-up.')
        rows = [dict(r) for r in self._rows()]
        use_perms = sorted(perms or ['overview.view'])
        if decision == 'approve':
            if loses_last_manager(u, rows, True, use_perms, self.manage):
                raise AuthError('At least one active user must keep the right to manage users.', key='autherr.lastAdmin')
        elif loses_last_manager(u, rows, False, manage=self.manage):
            raise AuthError('At least one active user must keep the right to manage users.', key='autherr.lastAdmin')
        ts = now()
        ops: List[dict] = []
        if decision == 'approve':
            row = {
                'status': 'approved', 'status_reason': '', 'status_at': ts, 'status_by': 'Administrator', 'active': 1,
                'role': 'Custom', 'perms': json.dumps(use_perms), 'request_code': '', 'updated_at': ts, 'updated_by': 'Administrator',
            }
            ops.append({'e': 'users', 'id': uid, 'op': 'update', 's': row})
            ops.append({'e': 'userCommands', 'id': uuid.uuid4().hex, 'op': 'insert', 'noaudit': True,
                        's': {'cmd': 'logout', 'user': uid}})
        elif decision == 'reject':
            row = {
                'status': 'rejected', 'status_reason': reason, 'status_at': ts, 'status_by': 'Administrator',
                'active': 0, 'request_code': '',
            }
            ops.append({'e': 'users', 'id': uid, 'op': 'update', 's': row})
            ops.append({'e': 'userCommands', 'id': uuid.uuid4().hex, 'op': 'insert', 'noaudit': True,
                        's': {'cmd': 'logout', 'user': uid}})
        else:
            row = {
                'status': 'suspended', 'status_reason': reason or 'Suspended', 'status_at': ts, 'status_by': 'Administrator',
                'active': 0, 'request_code': '',
            }
            ops.append({'e': 'users', 'id': uid, 'op': 'update', 's': row})
            ops.append({'e': 'userCommands', 'id': uuid.uuid4().hex, 'op': 'insert', 'noaudit': True,
                        's': {'cmd': 'logout', 'user': uid}})
        bound = u.get('reset_hash') or ''
        if decision in ('reject', 'suspend') and bound:
            ops.append(clear_reset_code_op(uid, bound))
        self._commit(ops)
        return self.get(uid) or {}

    def save_user_replicated(self, uid: str, fields: Mapping[str, Any]) -> None:
        """Administrator save of replicated fields; local lockout counters are never cleared."""
        self._commit([{'e': 'users', 'id': uid, 'op': 'update', 's': dict(fields)}])

    def issue_reset_code(self, uid: str) -> dict:
        u = self.get(uid)
        if not u:
            raise AuthError('This user no longer exists.')
        if (u.get('status') or 'approved') != 'approved':
            raise AuthError('Reset codes are only for approved accounts.', key='autherr.resetNotApproved')
        plain = reset_code_plain()
        exp = (datetime.now() + timedelta(hours=RESET_CODE_HOURS)).isoformat(timespec='seconds')
        ts = now()
        h = hash_password(plain)
        ops = [
            {'e': 'users', 'id': uid, 'op': 'update', 's': {'updated_at': ts, 'updated_by': 'Administrator'}},
            set_reset_code_op(uid, h, exp),
        ]
        self._commit(ops)
        return {'code': plain, 'expires': exp}

    def login(self, username: str, password: str, ip: str = '') -> Tuple[str, dict]:
        username = (username or '').strip()[:64]
        generic = 'Wrong user name or password.'
        u = self.get_by_username(username)
        if not u:
            verify_password(password or '', _DUMMY)
            raise AuthError(generic, key='autherr.wrong')
        ok = verify_password(password or '', u['pw_hash'])
        with self.lock:
            self.conn.execute('BEGIN IMMEDIATE')
            try:
                row = self.conn.execute('SELECT failed, locked_until FROM users WHERE id=?', (u['id'],)).fetchone()
                locked_until = row['locked_until']
                if locked_until and _parse(locked_until) > datetime.now():
                    self.conn.execute('ROLLBACK')
                    mins = max(1, round((_parse(locked_until) - datetime.now()).total_seconds() / 60))
                    raise AuthError(f'Account locked for {mins} more minute(s).', key='autherr.locked', mins=mins)
                sole = sole_admin_id(self._rows(), self.manage) == u['id'] and self.manage in u['perms']
                if not ok:
                    failed, locked = login_failure_update(int(row['failed'] or 0), sole, self.max_failed, self.lock_minutes)
                    if sole:
                        self.conn.execute('UPDATE users SET failed=? WHERE id=?', (failed, u['id']))
                    else:
                        self.conn.execute('UPDATE users SET failed=?, locked_until=? WHERE id=?', (failed, locked, u['id']))
                    self.conn.execute('COMMIT')
                    if locked:
                        raise AuthError(f'Too many wrong passwords. Locked for {self.lock_minutes} minutes.', key='autherr.lockedNow',
                                        mins=self.lock_minutes)
                    raise AuthError(generic, key='autherr.wrong')
                msg = status_message(u.get('status') or 'approved', u.get('status_reason') or '')
                if msg:
                    self.conn.execute('ROLLBACK')
                    key = 'autherr.signupPending' if u.get('status') == 'pending' else 'autherr.signupRejected'
                    if u.get('status') == 'rejected' and (u.get('status_reason') or '').strip():
                        key = 'autherr.signupRejectedReason'
                    raise AuthError(msg, key=key, reason=u.get('status_reason') or '')
                if not u['active']:
                    self.conn.execute('ROLLBACK')
                    raise AuthError('This account is disabled.', key='autherr.disabled')
                token = secrets.token_urlsafe(32)
                ts = now()
                th = hashlib.sha256(token.encode('ascii', 'ignore')).hexdigest()
                self.conn.execute('UPDATE users SET failed=0, locked_until=NULL, last_login=?, last_ip=? WHERE id=?', (ts, ip, u['id']))
                self.conn.execute('INSERT INTO sessions (token_hash, user_id, created, last_seen, ip, agent) VALUES (?,?,?,?,?,?)',
                                  (th, u['id'], ts, ts, ip, ''))
                self.conn.execute('COMMIT')
            except AuthError:
                raise
            except Exception:
                self.conn.execute('ROLLBACK')
                raise
        fresh = self.get(u['id'])
        return token, fresh or u

    def is_locked(self, uid: str) -> bool:
        with self.lock:
            r = self.conn.execute('SELECT locked_until FROM users WHERE id=?', (uid,)).fetchone()
        return bool(r and r['locked_until'] and _parse(r['locked_until']) > datetime.now())

    def reset_with_code(self, username: str, code: str, new_password: str, ip: str = '') -> dict:
        username = (username or '').strip()[:64]
        code = normalize_reset_code(code)
        generic = 'Wrong user name or reset code.'
        u = self.get_by_username(username)
        if not u or (u.get('status') or 'approved') != 'approved':
            verify_password(code or 'x', _DUMMY)
            raise AuthError(generic, key='autherr.resetWrong')
        ok_code = False
        burn_hash = None
        notify_ops: List[dict] = []
        with self.lock:
            self.conn.execute('BEGIN IMMEDIATE')
            try:
                row = self.conn.execute(
                    'SELECT failed, locked_until, reset_hash, reset_expires FROM users WHERE id=?', (u['id'],),
                ).fetchone()
                if not row or not row['reset_hash'] or not row['reset_expires']:
                    verify_password(code or 'x', _DUMMY)
                    self.conn.execute('ROLLBACK')
                    raise AuthError(generic, key='autherr.resetWrong')
                expired = _parse(row['reset_expires']) < datetime.now()
                ok_code = not expired and verify_password(code, row['reset_hash'])
                if row['locked_until'] and _parse(row['locked_until']) > datetime.now() and not ok_code:
                    self.conn.execute('ROLLBACK')
                    mins = max(1, round((_parse(row['locked_until']) - datetime.now()).total_seconds() / 60))
                    raise AuthError(f'Account locked for {mins} more minute(s).', key='autherr.locked', mins=mins)
                if ok_code:
                    self.conn.execute('ROLLBACK')
                else:
                    sole = sole_admin_id(self._rows(), self.manage) == u['id'] and self.manage in u['perms']
                    failed, locked, burn, _ = reset_guess_update(
                        int(row['failed'] or 0), sole, self.max_failed, self.lock_minutes,
                        RESET_CODE_MAX_ATTEMPTS, expired,
                    )
                    rh, re = ('', '') if burn else (row['reset_hash'], row['reset_expires'])
                    if sole:
                        self.conn.execute('UPDATE users SET failed=?, reset_hash=?, reset_expires=? WHERE id=?',
                                          (failed, rh, re, u['id']))
                    else:
                        self.conn.execute('UPDATE users SET failed=?, locked_until=?, reset_hash=?, reset_expires=? WHERE id=?',
                                          (failed, locked, rh, re, u['id']))
                    if burn:
                        burn_hash = row['reset_hash']
                        notify_ops.append(clear_reset_code_op(u['id'], burn_hash))
                    self.conn.execute('COMMIT')
            except AuthError:
                try:
                    self.conn.execute('ROLLBACK')
                except sqlite3.OperationalError:
                    pass
                raise
            except Exception:
                try:
                    self.conn.execute('ROLLBACK')
                except sqlite3.OperationalError:
                    pass
                if notify_ops:
                    self._commit(notify_ops)
                raise
        if notify_ops:
            self._commit(notify_ops)
        if not ok_code:
            raise AuthError(generic, key='autherr.resetWrong')
        check_password(new_password, u['username'], u['full_name'], self.min_len)
        ts = now()
        new_hash = hash_password(new_password)
        uid = u['id']
        with self.lock:
            row = self.conn.execute('SELECT reset_hash, reset_expires FROM users WHERE id=?', (uid,)).fetchone()
            if not row or not row['reset_hash'] or not verify_password(code, row['reset_hash']):
                raise AuthError(generic, key='autherr.resetWrong')
            burned = row['reset_hash']
        ops = [
            {'e': 'users', 'id': uid, 'op': 'update',
             's': {'pw_hash': new_hash, 'must_change': 0, 'pw_changed_at': ts, 'updated_at': ts, 'updated_by': 'Reset code'}},
            {'e': 'userCommands', 'id': uuid.uuid4().hex, 'op': 'insert', 'noaudit': True, 's': {'cmd': 'logout', 'user': uid}},
            clear_reset_code_op(uid, burned),
        ]

        def apply_local() -> None:
            self.conn.execute('UPDATE users SET failed=0, locked_until=NULL, reset_hash=?, reset_expires=? WHERE id=?',
                              ('', '', uid))

        self._commit(ops, apply_local=apply_local)
        return {'ok': True}
