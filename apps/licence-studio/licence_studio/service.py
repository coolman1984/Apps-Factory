"""Licence Studio logic: products, the vendor key, issuing and checking codes, the agent's requests, the audit.

Security model (vendor machine only, loopback only):
- The signing key is an Ed25519 private key encrypted with the owner's passphrase (cryptography's BestAvailableEncryption).
  It is decrypted only into the memory of the running studio after the owner unlocks it, and locks itself after idle time.
- The owner works in the local web page. An AI agent works through MCP, which calls this studio's API with an *agent token*:
  the agent can read, check codes and *request* codes. It may issue trial codes directly only when the owner switched that
  on, only device-bound, at most 14 days, and at most N per day. Paid editions always wait for the owner's approval.
- Every issued code is an append-only row; every action is in the audit with who did it (owner / agent).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .relay import Relay, RelayError

try:
    from af_license import codes
except ImportError:  # running from the repository checkout
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'packages' / 'af-license'))
    from af_license import codes

LOCK_AFTER_SECONDS = 30 * 60
AGENT_MAX_TRIAL_DAYS = 14
EDITIONS = ('trial', 'standard', 'pro', 'perpetual')
PERPETUAL = 'perpetual'  # stored as the last day of a code that never expires
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, name TEXT NOT NULL, trial_days INTEGER NOT NULL DEFAULT 14,
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS codes (
  serial TEXT PRIMARY KEY, product TEXT NOT NULL, edition TEXT NOT NULL, device TEXT, customer TEXT NOT NULL DEFAULT '',
  phone TEXT NOT NULL DEFAULT '', first_day TEXT NOT NULL, last_day TEXT NOT NULL, grace_days INTEGER NOT NULL, seats INTEGER NOT NULL,
  code TEXT NOT NULL, kid TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', issued_at TEXT NOT NULL, issued_by TEXT NOT NULL,
  request_id TEXT);
CREATE TABLE IF NOT EXISTS requests (
  id TEXT PRIMARY KEY, product TEXT NOT NULL, edition TEXT NOT NULL, device TEXT, customer TEXT NOT NULL, phone TEXT NOT NULL,
  days INTEGER NOT NULL, note TEXT NOT NULL, requested_by TEXT NOT NULL, requested_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', decided_at TEXT, decided_by TEXT, serial TEXT);
CREATE TABLE IF NOT EXISTS tokens (hash TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '');
-- One automatic trial per PC, for ever: the permanent record the relay's shorter memory is only a first filter for.
CREATE TABLE IF NOT EXISTS trial_ledger (
  product TEXT NOT NULL, machine TEXT NOT NULL, device TEXT NOT NULL, serial TEXT NOT NULL, relay_id TEXT, at TEXT NOT NULL,
  PRIMARY KEY (product, machine));
CREATE TRIGGER IF NOT EXISTS trial_ledger_append_only_u BEFORE UPDATE ON trial_ledger BEGIN SELECT RAISE(ABORT, 'trial ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trial_ledger_append_only_d BEFORE DELETE ON trial_ledger BEGIN SELECT RAISE(ABORT, 'trial ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS codes_append_only_u BEFORE UPDATE ON codes BEGIN SELECT RAISE(ABORT, 'codes are append-only'); END;
CREATE TRIGGER IF NOT EXISTS codes_append_only_d BEFORE DELETE ON codes BEGIN SELECT RAISE(ABORT, 'codes are append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_append_only_u BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_append_only_d BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
"""
# columns the relay's requests need on the older `requests` table (added once, never removed)
REQUEST_COLUMNS = (('source', "TEXT NOT NULL DEFAULT 'agent'"), ('relay_id', 'TEXT'), ('machine', 'TEXT'), ('src', 'TEXT'),
                   ('kind', "TEXT NOT NULL DEFAULT ''"), ('payment_ref', "TEXT NOT NULL DEFAULT ''"), ('held', "TEXT NOT NULL DEFAULT ''"),
                   ('relayed', 'INTEGER NOT NULL DEFAULT 0'), ('payment_confirmed', 'INTEGER NOT NULL DEFAULT 0'),
                   # the owner's «✅ موافق» on Telegram (recorded on the relay; never a licence by itself) and whether the owner's phone got a copy of the code
                   ('tg_decision', "TEXT NOT NULL DEFAULT ''"), ('tg_at', 'INTEGER'), ('code_sent', 'INTEGER NOT NULL DEFAULT 0'),
                   ('code_claim', 'INTEGER'),
                   # when a decision was taken (moved to `deciding`, in nanoseconds): it is also that decision's token (only its holder may finish or
                   # release it), and only one older than DECIDE_LEASE can have been left by a studio that died
                   ('decide_claim', 'INTEGER'))
DECIDE_LEASE = 120  # seconds: signing and saving one decision takes milliseconds, so a longer one belongs to a studio that is gone
UNATTENDED = ('auto-trial', 'telegram')  # actors that sign without the owner at the keyboard: they never keep the key open
MONTHLY_DAYS, MONTHLY_GRACE = 30, 3   # owner decision 2026-10-09: the Studio defaults for a monthly code
MAX_KEEP_UNLOCKED_HOURS = 12
DEFAULT_PRODUCTS = [('al-store', 'Al-Store · الستور', 14), ('hessa-centre', 'Hessa · حصّة', 14)]


class StudioError(Exception):
    def __init__(self, key, text, status=400):
        super().__init__(text)
        self.key, self.status = key, status


def utc_today():
    """The day `issued_at` is written with (now_iso is UTC): the daily count must use the same day, not the PC's local one."""
    return datetime.now(timezone.utc).date().isoformat()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _h(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Studio:
    def __init__(self, home: str | Path):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / 'keys').mkdir(exist_ok=True)
        try:
            os.chmod(self.home / 'keys', 0o700)
        except OSError:
            pass
        self.db = sqlite3.connect(self.home / 'studio.db', check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.executescript(SCHEMA)
        have = {r['name'] for r in self.db.execute('PRAGMA table_info(requests)').fetchall()}
        for name, ddl in REQUEST_COLUMNS:
            if name not in have:
                self.db.execute(f'ALTER TABLE requests ADD COLUMN {name} {ddl}')
                if name == 'code_sent':  # an older studio: its finished requests must not flood the owner's phone with old codes
                    self.db.execute("UPDATE requests SET code_sent = 1 WHERE status IN ('approved', 'refused')")
        self.db.execute('CREATE UNIQUE INDEX IF NOT EXISTS requests_relay ON requests(relay_id) WHERE relay_id IS NOT NULL')
        for pid, name, days in DEFAULT_PRODUCTS:
            self.db.execute('INSERT OR IGNORE INTO products(id, name, trial_days, created_at) VALUES (?, ?, ?, ?)', (pid, name, days, now_iso()))
        self._key: Ed25519PrivateKey | None = None
        self._unlocked_at = 0.0
        self._keep_until = 0.0  # the owner's explicit "stay unlocked for N hours" so the automatic trial policy can sign unattended
        self.relay = Relay(self.home)
        from .autotrial import AutoTrial  # here, not at the top: autotrial imports this module
        self.auto = AutoTrial(self)
        self._unlock_lock = threading.Lock()
        self._unlock_failures, self._unlock_blocked_until = 0, 0.0
        self._recover_deciding()

    def _recover_deciding(self):
        """A request is moved to `deciding` before the code is signed and to approved/refused after. A studio that was shut down in between
        (power cut, killed) would leave it there for ever: not waiting, not decided, never delivered. Each such request older than the lease is put
        right (a younger one belongs to a studio that is alive, maybe another window on the same folder, and is left alone): with a code already
        signed for it (codes are append-only and tied to the request) it is approved with that code, by whoever signed it, with the payment
        the owner had confirmed (saved when the decision was taken, before signing), and delivered by the next round; without one it waits again
        and the payment must be confirmed again. A paid request found with a code but no saved payment was left by a version that saved the
        confirmation only after signing: its code is kept (never a second one) but it is not approved on its own, it waits for the owner to confirm
        the payment again (his reference was never saved and cannot be guessed), and the same code then goes out."""
        now = time.time_ns()
        # old: taken longer ago than the lease, or stamped by a clock that was put back since (a dead BIOS battery after a power cut): the stamp is then
        # in the future, and waiting for the clock to catch up would leave the request stuck
        stale, future = now - DECIDE_LEASE * 10**9, now + DECIDE_LEASE * 10**9
        old = '(COALESCE(decide_claim, 0) < ? OR decide_claim > ?)'
        for r in self.rows(f"SELECT id, payment_ref, payment_confirmed, source, kind FROM requests WHERE status = 'deciding' AND {old}", stale, future):
            code = self.one('SELECT serial, issued_by FROM codes WHERE request_id = ?', r['id'])
            legacy_paid = bool(code) and r['source'] == 'relay' and r['kind'] in ('monthly', 'permanent') and not r['payment_confirmed']
            with self.lock:
                if legacy_paid:
                    moved = self.db.execute(f"UPDATE requests SET status = 'pending', decide_claim = NULL WHERE id = ? AND status = 'deciding' "
                                            f"AND {old} AND payment_confirmed = 0", (r['id'], stale, future)).rowcount
                elif code:
                    moved = self.db.execute("UPDATE requests SET status = 'approved', decided_at = COALESCE(decided_at, ?), decided_by = COALESCE(NULLIF(decided_by, ''), ?), "
                                            f"serial = ?, held = '', decide_claim = NULL WHERE id = ? AND status = 'deciding' AND {old}",
                                            (now_iso(), code['issued_by'], code['serial'], r['id'], stale, future)).rowcount
                else:
                    moved = self.db.execute("UPDATE requests SET status = 'pending', payment_confirmed = 0, decide_claim = NULL "
                                            f"WHERE id = ? AND status = 'deciding' AND {old} "
                                            "AND NOT EXISTS (SELECT 1 FROM codes WHERE request_id = ?)",  # (a code signed since the look above: the next pass approves with it)
                                            (r['id'], stale, future, r['id'])).rowcount
            if moved:
                self.audit('studio', 'request.recovered', {'id': r['id'], 'serial': code['serial'] if code else None,
                                                           **({'payment': 'confirm again'} if legacy_paid else {}),
                                                           **({'payment_ref': r['payment_ref']} if code and r['payment_ref'] and not legacy_paid else {})})

    # ------------------------------------------------------------------ helpers
    def rows(self, sql, *args):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def one(self, sql, *args):
        r = self.rows(sql, *args)
        return r[0] if r else None

    def audit(self, actor, action, detail=None):
        with self.lock:
            self.db.execute('INSERT INTO audit(at, actor, action, detail) VALUES (?, ?, ?, ?)',
                            (now_iso(), actor, action, json.dumps(detail or {}, ensure_ascii=False)))

    def setting(self, key, default=None):
        r = self.one('SELECT value FROM meta WHERE key = ?', key)
        return json.loads(r['value']) if r else default

    def set_setting(self, key, value, actor='owner'):
        with self.lock:
            self.db.execute('INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                            (key, json.dumps(value)))
        self.audit(actor, 'setting', {key: value})

    def policy(self):
        keep = self._keep_until if self._key and time.time() < self._keep_until else 0
        return {'agent_may_issue_trials': bool(self.setting('agent_may_issue_trials', False)),
                'agent_daily_limit': int(self.setting('agent_daily_limit', 10)),
                'lock_minutes': LOCK_AFTER_SECONDS // 60,
                # the owner-approved automatic trial policy (off until the owner switches it on): see autotrial.py
                'auto_trials': bool(self.setting('auto_trials', False)),
                'auto_trial_days': int(self.setting('auto_trial_days', AGENT_MAX_TRIAL_DAYS)),
                'auto_trial_daily_cap': int(self.setting('auto_trial_daily_cap', 10)),
                'keep_unlocked_until': (datetime.fromtimestamp(keep, timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z') if keep else None)}

    # ------------------------------------------------------------------ key
    def key_file(self):
        files = sorted((self.home / 'keys').glob('licence-*.pem'))
        return files[-1] if files else None

    def public_key(self):
        f = self.key_file()
        if not f:
            return None
        return (self.home / 'keys' / (f.stem + '.public.txt')).read_text(encoding='utf-8').strip()

    def create_key(self, passphrase: str):
        if self.key_file():
            raise StudioError('key.exists', 'A signing key already exists. Back it up; do not make a second one by accident.', 409)
        if not isinstance(passphrase, str) or len(passphrase) < 12:
            raise StudioError('key.weak', 'Use a passphrase of at least 12 characters (a short sentence is best).')
        private = Ed25519PrivateKey.generate()
        raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        public = base64.urlsafe_b64encode(raw).decode().rstrip('=')
        kid = hashlib.sha256(raw).hexdigest()[:16]
        pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.BestAvailableEncryption(passphrase.encode('utf-8')))
        path = self.home / 'keys' / f'licence-{kid}.pem'
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(pem)
        (self.home / 'keys' / f'licence-{kid}.public.txt').write_text(f'{kid}:{public}\n', encoding='utf-8')
        self._key, self._unlocked_at = private, time.time()
        self.audit('owner', 'key.create', {'kid': kid})
        return {'kid': kid, 'public': f'{kid}:{public}', 'file': str(path)}

    def unlock(self, passphrase: str):
        f = self.key_file()
        if not f:
            raise StudioError('key.none', 'Create the signing key first.', 409)
        passphrase = passphrase if isinstance(passphrase, str) else ''
        with self._unlock_lock:  # one guess at a time, and a pause after five wrong ones
            if time.time() < self._unlock_blocked_until:
                raise StudioError('key.blocked', 'Too many wrong passphrases. Wait a few minutes.', 429)
            try:
                key = serialization.load_pem_private_key(f.read_bytes(), password=passphrase.encode('utf-8'))
            except (ValueError, TypeError):
                time.sleep(0.8)  # slows guessing; the file itself is protected by the passphrase's KDF
                self._unlock_failures += 1
                if self._unlock_failures >= 5:
                    self._unlock_failures, self._unlock_blocked_until = 0, time.time() + 300
                self.audit('owner', 'key.unlock.failed')
                raise StudioError('key.wrong', 'Wrong passphrase.', 403)
            self._unlock_failures = 0
        if not isinstance(key, Ed25519PrivateKey):
            raise StudioError('key.type', 'The key file is not an Ed25519 key.', 500)
        self._key, self._unlocked_at = key, time.time()
        self.audit('owner', 'key.unlock')
        return True

    def lock_key(self):
        self._key, self._keep_until = None, 0.0
        self.audit('owner', 'key.lock')

    def keep_unlocked(self, hours):
        """The owner's explicit choice: the key stays in memory (only) for up to a working day, so the automatic trial policy can sign
        while nobody is at the PC. Locking, restarting or the end of the time puts it back behind the passphrase."""
        if not self.unlocked():
            raise StudioError('key.locked', 'The studio is locked. The owner unlocks it with the passphrase.', 423)
        hours = max(0.0, min(float(MAX_KEEP_UNLOCKED_HOURS), float(hours)))
        self._keep_until = time.time() + hours * 3600 if hours else 0.0
        self.audit('owner', 'key.keep_unlocked', {'hours': hours})
        return self.policy()

    def unlocked(self):
        if self._key and time.time() - self._unlocked_at > LOCK_AFTER_SECONDS and time.time() >= self._keep_until:
            self._key = None
        return self._key is not None

    def _pem(self, owner=True):
        if not self.unlocked():
            raise StudioError('key.locked', 'The studio is locked. The owner unlocks it with the passphrase.', 423)
        if owner:  # only the owner's own use keeps the key open; automatic signing never does (review of PR #34: it could keep it open for ever)
            self._unlocked_at = time.time()
        return self._key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())

    # ------------------------------------------------------------------ products
    def products(self):
        return self.rows('SELECT p.*, (SELECT COUNT(*) FROM codes c WHERE c.product = p.id) AS codes FROM products p ORDER BY p.created_at')

    def add_product(self, pid, name, trial_days=14, actor='owner'):
        pid = (pid or '').strip().lower()
        if not (3 <= len(pid) <= 48) or not all(ch.isalnum() or ch == '-' for ch in pid) or not pid[0].isalpha():
            raise StudioError('product.id', 'Product id: 3–48 letters, digits or dashes, starting with a letter (e.g. al-store).')
        if not (1 <= int(trial_days) <= 60):
            raise StudioError('product.days', 'Trial days must be 1 to 60.')
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO products(id, name, trial_days, created_at) VALUES (?, ?, ?, COALESCE((SELECT created_at '
                            'FROM products WHERE id = ?), ?))', (pid, (name or pid).strip()[:80], int(trial_days), pid, now_iso()))
        self.audit(actor, 'product.save', {'id': pid, 'trial_days': trial_days})
        return pid

    # ------------------------------------------------------------------ codes
    def _check_terms(self, product, edition, device, days):
        if not self.one('SELECT 1 FROM products WHERE id = ?', product):
            raise StudioError('product.unknown', 'Unknown product. Add it on the Products page first.', 404)
        if edition not in EDITIONS:
            raise StudioError('edition', 'Edition must be trial, standard, pro or perpetual.')
        if device:
            try:
                norm = codes.normalize(device)
            except ValueError:
                raise StudioError('device', 'The device code has letters that are not allowed.')
            if len(norm) != 10:
                raise StudioError('device', 'A device code has 10 characters, like 7KD2M-QX9TP.')
            device = codes.group(norm, 5)
        if not (1 <= int(days) <= 3660):
            raise StudioError('days', 'Days must be 1 to 3660.')
        return device

    @staticmethod
    def _need_device(edition, device):
        if edition in ('trial', 'perpetual') and not device:
            raise StudioError('device.required', 'A trial or perpetual code must be tied to the customer\'s device code (so it cannot be passed on).')

    def issue(self, product, edition, device, customer='', phone='', days=None, first_day=None, grace_days=0, seats=1, note='',
              actor='owner', request_id=None, machine=None, claim=None, once_per_device=False, daily_cap=None):
        if request_id:  # the same request asked twice (a retry after a crash) gives the same code, never a second one
            done = self.one('SELECT serial FROM codes WHERE request_id = ?', request_id)
            if done:
                return self.code(done['serial'])
        prod = self.one('SELECT * FROM products WHERE id = ?', product)
        days = int(days or (prod['trial_days'] if prod and edition == 'trial' else 365))
        device = self._check_terms(product, edition, device, days)
        self._need_device(edition, device)
        if edition == 'perpetual':
            grace_days = 0
        first = date.fromisoformat(first_day) if first_day else date.today()
        if first < date.today() - timedelta(days=1):
            raise StudioError('first_day', 'The first day cannot be in the past.')
        out = codes.issue_code(self._pem(owner=actor not in UNATTENDED), product, edition, first, days, device, int(grace_days), int(seats), date.today())
        kid = (self.public_key() or ':').split(':', 1)[0]
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                if claim and not self.db.execute("SELECT 1 FROM requests WHERE id = ? AND status = 'deciding' AND decide_claim = ?", (request_id, claim)).fetchone():
                    raise StudioError('request.closed', 'This decision was taken over (it waited more than two minutes) and is not yours any more.', 409)
                if once_per_device and device and self.db.execute('SELECT 1 FROM codes WHERE product = ? AND device = ?', (product, device)).fetchone():
                    raise StudioError('agent.repeat', 'This device already had a code. A new or longer code is the owner\'s decision.', 409)
                if daily_cap is not None:  # the daily limits are counted under the write lock too: two requests together cannot both pass a look taken before either wrote
                    used = self.db.execute("SELECT COUNT(*) AS n FROM codes WHERE issued_by = ? AND substr(issued_at, 1, 10) = ?", (actor, utc_today())).fetchone()['n']
                    if used >= daily_cap:
                        raise StudioError('agent.limit' if actor == 'agent' else 'daily_cap', 'Today\'s limit of automatic trial codes was reached. The owner can raise it.', 429)
                if request_id:  # asked again under the file's write lock: another window on this folder may have signed it since the check above
                    done = self.db.execute('SELECT serial FROM codes WHERE request_id = ?', (request_id,)).fetchone()
                    if done:
                        self.db.execute('ROLLBACK')
                        return self.code(done['serial'])
                if machine and edition == 'trial':  # one automatic trial per PC for ever: the primary key refuses a second, even in a race
                    try:
                        self.db.execute('INSERT INTO trial_ledger(product, machine, device, serial, relay_id, at) VALUES (?, ?, ?, ?, ?, ?)',
                                        (product, machine, device, out['serial'], request_id, now_iso()))
                    except sqlite3.IntegrityError:
                        raise StudioError('trial.repeat', 'This PC already had its trial.', 409) from None
                self.db.execute('INSERT INTO codes(serial, product, edition, device, customer, phone, first_day, last_day, grace_days, seats, code, kid, '
                                'note, issued_at, issued_by, request_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                (out['serial'], product, edition, device, (customer or '').strip()[:80], (phone or '').strip()[:20], out['first_day'],
                                 out['last_day'] or PERPETUAL, int(grace_days), int(seats), out['code'], kid, (note or '').strip()[:300], now_iso(), actor,
                                 request_id))
                self.db.execute('COMMIT')
            except BaseException:
                self.db.execute('ROLLBACK')
                raise
        self.audit(actor, 'code.issue', {'serial': out['serial'], 'product': product, 'edition': edition, 'device': device,
                                         'days': days, 'customer': customer})
        return self.code(out['serial'])

    def code(self, serial):
        c = self.one('SELECT * FROM codes WHERE serial = ?', (serial or '').upper())
        if not c:
            raise StudioError('code.unknown', 'No code with this serial.', 404)
        return self._decorate(c)

    def _decorate(self, c):
        today = date.today()
        if c['last_day'] == PERPETUAL:
            c['days_left'], c['expiring_soon'] = None, False
            c['status'] = 'not_started' if date.fromisoformat(c['first_day']) > today else 'active'
            return c
        last = date.fromisoformat(c['last_day'])
        c['days_left'] = (last - today).days + 1
        c['status'] = ('not_started' if date.fromisoformat(c['first_day']) > today else 'active' if today <= last
                       else 'grace' if today <= last + timedelta(days=c['grace_days']) else 'expired')
        c['expiring_soon'] = c['status'] == 'active' and c['days_left'] <= 3
        return c

    def list_codes(self, q='', product='', status='', limit=300):
        where, args = [], []
        if product:
            where.append('product = ?')
            args.append(product)
        if q:
            where.append('(customer LIKE ? OR phone LIKE ? OR device LIKE ? OR serial LIKE ? OR note LIKE ?)')
            args += [f'%{q}%'] * 5
        rows = self.rows(f"SELECT * FROM codes {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY issued_at DESC LIMIT ?",
                         *args, 2000 if status else min(int(limit), 2000))  # a status filter runs after the query: look at all of them
        rows = [self._decorate(r) for r in rows]
        if status == 'expiring':
            rows = [r for r in rows if r['expiring_soon']]
        elif status:
            rows = [r for r in rows if r['status'] == status]
        return rows[:min(int(limit), 2000)]

    def verify(self, code_text, product, device=None):
        keys = [self.public_key().split(':', 1)[1]] if self.public_key() else []
        r = codes.read_code(code_text, keys, product, device or None)
        out = {'valid': r.valid, 'state': r.state, 'reason': r.reason, 'terms': r.terms}
        if r.terms.get('serial'):
            known = self.one('SELECT customer, device, issued_by, issued_at FROM codes WHERE serial = ?', r.terms['serial'])
            out['issued_here'] = known
        if not device and r.reason == 'other_device':
            out['hint'] = 'This code is tied to a device. Give the device code to check it fully.'
        return out

    # ------------------------------------------------------------------ requests (agent → owner)
    def request(self, product, edition, device, customer, phone='', days=None, note='', actor='agent'):
        prod = self.one('SELECT * FROM products WHERE id = ?', product)
        days = int(days or (prod['trial_days'] if prod and edition == 'trial' else 365))
        device = self._check_terms(product, edition, device, days)
        self._need_device(edition, device)  # refused now: a request without its device could never be approved
        if not (customer or '').strip():
            raise StudioError('customer', 'Write the customer or shop name.')
        rid = str(uuid.uuid4())
        with self.lock:
            self.db.execute('INSERT INTO requests(id, product, edition, device, customer, phone, days, note, requested_by, requested_at) '
                            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (rid, product, edition, device, customer.strip()[:80],
                                                                      (phone or '')[:20], days, (note or '')[:300], actor, now_iso()))
        self.audit(actor, 'request.create', {'id': rid, 'product': product, 'edition': edition, 'device': device, 'days': days})
        return self.one('SELECT * FROM requests WHERE id = ?', rid)

    def requests(self, status='pending'):
        rows = self.rows("SELECT * FROM requests WHERE (? = '' OR status = ?) ORDER BY requested_at DESC LIMIT 200", status, status)
        for r in rows:
            if r['source'] == 'relay' and r['status'] == 'pending':  # what the owner-approved policy would do with it (a hint, nothing is changed)
                kind, reason, _ = self.auto.verdict(r, approved=r['tg_decision'] == 'approved')
                r['policy'] = {'verdict': kind, 'reason': reason}
        return rows

    def decide(self, rid, approve, actor='owner', payment_confirmed=False, payment_ref=''):
        r = self.one('SELECT * FROM requests WHERE id = ?', rid)
        if not r or r['status'] != 'pending':
            raise StudioError('request.closed', 'This request is not pending.', 409)
        relay = r['source'] == 'relay'
        paid = relay and r['kind'] in ('monthly', 'permanent')
        ref = (payment_ref or r['payment_ref'] or '').strip()[:60]
        if approve and paid and (not payment_confirmed or len(ref) < 3):  # a paid code is never given before the owner confirms the money arrived
            raise StudioError('payment.required', 'Tick that the payment arrived and write its reference first.', 400)
        if relay and approve and self.relay.configured():  # the owner's «❌ رفض» on the phone may have closed it while this page was open
            try:
                if self.auto.refresh_one(r):
                    raise StudioError('request.closed', 'The owner already refused or closed this request from Telegram. The shop will not get a code for it.', 409)
            except RelayError:
                pass  # the relay cannot be reached (or is older than 0.14): the owner may still sign; delivery is retried and a closed request is reported then
        token = self.claim(rid, ref if approve and paid else None)
        if not token:  # the automatic round took it a moment ago
            raise StudioError('request.closed', 'This request was decided a moment ago.', 409)
        try:
            serial = self._decide_claimed(r, approve, actor, relay, paid, ref, token)
        except BaseException:
            self.release(rid, token)
            raise
        if relay:
            self.auto.owner_decided(rid)
        return self.one('SELECT * FROM requests WHERE id = ?', rid)

    def claim(self, rid, payment_ref=None):
        """One decision per request: whoever moves it from pending to deciding decides it (the owner or the automatic round), and only
        that one signs and delivers (review of PR #34: both could decide the same request and the relay and the Studio disagreed).
        A paid approval saves the confirmed payment here, in the same step, so a studio switched off after signing still knows the money was confirmed.
        Returns the decision's token (0 when it was not taken). Signing, saving and releasing must show it: a window that slept longer than DECIDE_LEASE
        and finds its decision taken back and decided by another cannot overwrite that decision."""
        token = time.time_ns()
        with self.lock:
            if payment_ref is None:
                taken = self.db.execute("UPDATE requests SET status = 'deciding', decide_claim = ? WHERE id = ? AND status = 'pending'", (token, rid)).rowcount == 1
            else:
                taken = self.db.execute("UPDATE requests SET status = 'deciding', decide_claim = ?, payment_ref = ?, payment_confirmed = 1 "
                                        "WHERE id = ? AND status = 'pending'", (token, payment_ref, rid)).rowcount == 1
        return token if taken else 0

    def release(self, rid, token=None):
        with self.lock:
            self.db.execute("UPDATE requests SET status = 'pending', payment_confirmed = 0, decide_claim = NULL WHERE id = ? AND status = 'deciding' "
                            "AND (? IS NULL OR decide_claim = ?)", (rid, token, token))

    def _decide_claimed(self, r, approve, actor, relay, paid, ref, token):
        rid = r['id']
        serial = None
        if approve:
            days, grace = r['days'], 0
            if relay and r['kind'] == 'monthly':
                days, grace = MONTHLY_DAYS, MONTHLY_GRACE
            machine = r['machine'] if relay and r['kind'] == 'trial' else None
            if machine and self.one('SELECT 1 FROM trial_ledger WHERE product = ? AND machine = ?', r['product'], machine):
                machine = None  # the owner knowingly gives a second trial to this PC: it stays in the audit, the ledger keeps the first
            serial = self.issue(r['product'], r['edition'], r['device'], r['customer'], r['phone'], days, grace_days=grace, note=r['note'],
                                actor=actor, request_id=rid, machine=machine, claim=token)['serial']
        with self.lock:
            saved = self.db.execute("UPDATE requests SET status = ?, decided_at = ?, decided_by = ?, serial = ?, held = ?, payment_ref = ?, payment_confirmed = ? "
                                    "WHERE id = ? AND status = 'deciding' AND decide_claim = ?",
                                    ('approved' if approve else 'refused', now_iso(), actor, serial, '' if approve else 'owner_refused', ref,
                                     1 if (approve and paid) else 0, rid, token)).rowcount
        if not saved:  # taken back after the lease and decided by someone else: that decision stands
            raise StudioError('request.closed', 'This decision was taken over (it waited more than two minutes) and is not yours any more.', 409)
        self.audit(actor, 'request.' + ('approve' if approve else 'refuse'), {'id': rid, 'serial': serial, **({'payment_ref': ref} if paid and approve else {})})
        return serial

    def agent_issue_trial(self, product, device, customer, phone='', days=None, note=''):
        """The agent's only direct way to make a code: trial, device-bound, ≤ 14 days, daily limit, owner switched it on."""
        pol = self.policy()
        if not pol['agent_may_issue_trials']:
            return {'status': 'requested', 'request': self.request(product, 'trial', device, customer, phone, days, note)}
        days = int(days or AGENT_MAX_TRIAL_DAYS)
        if days > AGENT_MAX_TRIAL_DAYS:
            raise StudioError('agent.days', f'An agent may issue at most {AGENT_MAX_TRIAL_DAYS} trial days.')
        if not device:
            raise StudioError('device.required', 'A trial code must be tied to a device code.')
        normalized = codes.group(codes.normalize(device), 5) if isinstance(device, str) else None
        if normalized and self.one('SELECT 1 FROM codes WHERE product = ? AND device = ?', product, normalized):
            raise StudioError('agent.repeat', 'This device already had a code. A new or longer code is the owner\'s decision.', 409)
        used = self.one("SELECT COUNT(*) AS n FROM codes WHERE issued_by = 'agent' AND substr(issued_at, 1, 10) = ?", utc_today())['n']
        if used >= pol['agent_daily_limit']:
            raise StudioError('agent.limit', 'The agent reached today\'s limit of trial codes. The owner can raise it.', 429)
        return {'status': 'issued', 'code': self.issue(product, 'trial', device, customer, phone, days, note=note, actor='agent',
                                                       once_per_device=True, daily_cap=pol['agent_daily_limit'])}

    # ------------------------------------------------------------------ agent tokens
    def new_agent_token(self, name='AI agent'):
        token = 'lsa_' + secrets.token_urlsafe(32)
        with self.lock:
            self.db.execute('INSERT INTO tokens(hash, name, created_at) VALUES (?, ?, ?)', (_h(token), name[:60], now_iso()))
        self.audit('owner', 'agent.token.create', {'name': name})
        return token

    def agent_ok(self, token):
        return bool(token) and bool(self.one('SELECT 1 FROM tokens WHERE hash = ? AND revoked = 0', _h(token)))

    def tokens(self):
        return self.rows('SELECT substr(hash, 1, 8) AS id, name, created_at, revoked FROM tokens ORDER BY created_at DESC')

    def revoke_tokens(self):
        with self.lock:
            self.db.execute('UPDATE tokens SET revoked = 1')
        self.audit('owner', 'agent.token.revoke_all')

    def status(self):
        return {'key': bool(self.key_file()), 'unlocked': self.unlocked(), 'public_key': self.public_key(), 'policy': self.policy(),
                'products': len(self.products()), 'codes': self.one('SELECT COUNT(*) AS n FROM codes')['n'],
                'pending_requests': self.one("SELECT COUNT(*) AS n FROM requests WHERE status = 'pending'")['n'],
                'expiring_soon': len(self.list_codes(status='expiring')), 'home': str(self.home),
                'relay': {**self.relay.public(), 'last': dict(self.auto.last)}}

    def audit_log(self, limit=200):
        return self.rows('SELECT * FROM audit ORDER BY id DESC LIMIT ?', min(int(limit), 2000))
