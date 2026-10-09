"""af-telemetry: consented usage and error events, problem reports and the offline outbox (standard library only,
one file, vendorable). Controls PRIV-03..06, TEL-01..03, FB-01, ROLL-01.

Firm limits, enforced here in code and in tests (never by convention):
  * only the event types in events.json, each with its own allowlisted fields; anything else raises PrivacyError;
  * field values are short machine ids, counts, durations or booleans - never names, phones, national ids, e-mails,
    amounts, free text, passwords, keystrokes or screenshots; a field NAME on the never-list is refused even if a
    product adds it to its own taxonomy;
  * a person is a pseudonymous reference (HMAC of the person id with this installation's secret), never a name;
  * nothing is queued unless the installation agreed, and person-level events only when that person agreed too;
    declining or withdrawing deletes that person's pending events (purge_subject);
  * problem reports (fb.*) are the only free text: written by the person, redacted, previewed, and allowed without
    tracking consent (no person reference is attached when the person did not agree).

    tel = Telemetry('telemetry.db', install_id, node, product='al-store', version='1.2.0', env='practice',
                    secret=install_secret, consent=Consent(db))       # af_consent.Consent, or any object with
                                                                       # install_allowed() and allowed(user_id)
    tel.emit('use.page', {'page': 'sell'}, user=me.id, role=me.role)
    tel.capture(exc, where='sales:checkout')                           # err.server, no message text
    tel.feedback('problem', text, page='sell', user=me.id)             # always allowed; redacted
    tel.send_once(relay_url, install_token)                            # batch, gzip, sign, POST; backoff on failure
"""
import gzip
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import traceback
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

__version__ = '0.1.0'


def _taxonomy():
    here = Path(__file__).resolve().parent
    for name in ('events.json', 'aftelemetry_events.json'):   # in the package / vendored next to server/aftelemetry.py
        if (here / name).exists():
            return json.loads((here / name).read_text(encoding='utf-8'))
    return None


TAXONOMY = _taxonomy()

ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:\-/]{0,79}$')
LONG_DIGITS = re.compile(r'\d{8,}')
# Fingerprints are hex hashes written with letters only (0-9 -> g-p), so a hash can never look like a long number and
# be refused by the LONG_DIGITS rule (a phone or national-id guard).
HEX_LETTERS = str.maketrans('0123456789', 'ghijklmnop')
LIMITS = {'max_events': 5000, 'max_bytes': 5 * 1024 * 1024, 'max_age_days': 30, 'batch_bytes': 256 * 1024,
          'feedback_chars': 2000, 'sent_log': 200, 'backoff_min_s': 60, 'backoff_max_s': 6 * 3600}
ENVS = {'real', 'practice'}
SEVS = {'info', 'warn', 'error'}

REDACT = [
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+'), '[EMAIL]'),
    (re.compile(r'(?<!\d)(?:\+?20|0)?1[0125]\d{8}(?!\d)'), '[PHONE]'),
    (re.compile(r'(?<!\d)[23]\d{13}(?!\d)'), '[NATIONAL_ID]'),
    (re.compile(r'(?<!\d)(?:\d[ -]?){13,19}(?!\d)'), '[NUMBER]'),
    (re.compile(r'(?i)\b(bearer|token|password|passwd|secret|api[_-]?key|كلمة السر|الباسورد)\b\s*[:=]?\s*\S+'), r'\1=[SECRET]'),
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----'), '[PRIVATE_KEY]'),
    (re.compile(r'\b(?:cc|ins|ven)_[A-Za-z0-9_-]{20,}'), '[TOKEN]'),
]


class PrivacyError(ValueError):
    """An event broke the firm limits. Raised loudly so the product's tests catch it before release."""


def now_iso(t=None):
    return datetime.fromtimestamp(t if t is not None else time.time(), timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def uuid7(t=None):
    ms = int((t if t is not None else time.time()) * 1000)
    rand = int.from_bytes(os.urandom(10), 'big')
    value = (ms & ((1 << 48) - 1)) << 80 | 0x7 << 76 | (rand >> 68 & 0xFFF) << 64 | 0b10 << 62 | rand & ((1 << 62) - 1)
    return str(uuid.UUID(int=value))


def redact(text):
    for rx, rep in REDACT:
        text = rx.sub(rep, text)
    return text


def pseudonym(secret, user_id):
    """Stable per installation, meaningless elsewhere: p_ + 16 hex of HMAC-SHA256(install secret, person id)."""
    return 'p_' + hmac.new(secret.encode() if isinstance(secret, str) else secret, str(user_id).encode(), hashlib.sha256).hexdigest()[:16]


def sign(token, ts, nonce, body):
    """X-AF-Signature: HMAC-SHA256 keyed with sha256(install token) over ts \\n nonce \\n sha256(body). The Control
    Center keeps only sha256(token), so it can verify without storing the token itself."""
    key = hashlib.sha256(token.encode()).digest()
    msg = f'{ts}\n{nonce}\n{hashlib.sha256(body).hexdigest()}'.encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify(token_hash_hex, ts, nonce, body, signature, now=None, window=300):
    if abs((now if now is not None else time.time()) - int(ts)) > window:
        return False
    key = bytes.fromhex(token_hash_hex)
    msg = f'{ts}\n{nonce}\n{hashlib.sha256(body).hexdigest()}'.encode()
    return hmac.compare_digest(hmac.new(key, msg, hashlib.sha256).hexdigest(), str(signature))


def check_taxonomy(tax):
    """Problems in a taxonomy (a product may extend events.json): never-list field names, unknown value types."""
    out = []
    never = set(tax.get('never', []))
    for name, spec in tax.get('types', {}).items():
        if spec.get('level') not in ('install', 'person', 'feedback'):
            out.append(f'{name}: bad level')
        if spec.get('level') == 'feedback' and not name.startswith('fb.'):
            out.append(f'{name}: only fb.* may carry feedback')
        for field, f in spec.get('data', {}).items():
            if field in never:
                out.append(f'{name}.{field}: field name is on the never-collect list')
            if f.get('type') not in ('id', 'int', 'bool', 'feedback_text', 'diagnostics'):
                out.append(f'{name}.{field}: unknown type')
            if f.get('type') in ('feedback_text', 'diagnostics') and spec.get('level') != 'feedback':
                out.append(f'{name}.{field}: free text only in feedback events')
    return out


def clean_data(tax, etype, data):
    """Validated copy of data or PrivacyError. The single gate every event passes."""
    spec = tax['types'].get(etype)
    if spec is None:
        raise PrivacyError(f'unknown event type {etype!r}')
    if not isinstance(data, dict):
        raise PrivacyError('data must be an object')
    never = set(tax.get('never', []))
    out = {}
    for k, v in data.items():
        if k in never:
            raise PrivacyError(f'{etype}.{k}: never collected')
        f = spec['data'].get(k)
        if f is None:
            raise PrivacyError(f'{etype}.{k}: not an allowed field')
        t = f['type']
        if t == 'int':
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not -1e12 < v < 1e12:
                raise PrivacyError(f'{etype}.{k}: must be a number')
            out[k] = int(v)
        elif t == 'bool':
            if not isinstance(v, bool):
                raise PrivacyError(f'{etype}.{k}: must be true/false')
            out[k] = v
        elif t == 'id':
            if not isinstance(v, str) or not ID_RE.match(v) or LONG_DIGITS.search(v) or '@' in v:
                raise PrivacyError(f'{etype}.{k}: must be a short machine id (no names, phones or numbers)')
            out[k] = v
        elif t == 'feedback_text':
            if not isinstance(v, str):
                raise PrivacyError(f'{etype}.{k}: text')
            out[k] = redact(v.strip())[:LIMITS['feedback_chars']]
        elif t == 'diagnostics':
            if not isinstance(v, dict) or set(v) - set(tax.get('diagnostics', [])):
                raise PrivacyError(f'{etype}.{k}: only allowlisted diagnostics')
            for dk, dv in v.items():
                if isinstance(dv, bool) or not isinstance(dv, (int, float, str)) or \
                        (isinstance(dv, str) and (not ID_RE.match(dv) or LONG_DIGITS.search(dv))):
                    raise PrivacyError(f'diagnostics.{dk}: counts and versions only')
            out[k] = dict(v)
    if 'contact' in out and out['contact'] not in tax.get('contact', []):
        raise PrivacyError('contact must be one of ' + ', '.join(tax.get('contact', [])))
    return out


OUTBOX_SQL = """
CREATE TABLE IF NOT EXISTS outbox (
    id TEXT PRIMARY KEY, created REAL NOT NULL, type TEXT NOT NULL, prio INTEGER NOT NULL,
    subject TEXT, merge_key TEXT UNIQUE, body TEXT NOT NULL, size INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS outbox_order ON outbox (prio, created);
CREATE TABLE IF NOT EXISTS sent (id TEXT PRIMARY KEY, at REAL NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS counters (k TEXT PRIMARY KEY, n INTEGER NOT NULL);
"""


class Telemetry:
    def __init__(self, path, install_id, node, product, version, env, secret, consent, taxonomy=None, limits=None,
                 clock=time.time):
        if env not in ENVS:
            raise ValueError('env is real or practice')
        self.tax = taxonomy or TAXONOMY
        bad = check_taxonomy(self.tax)
        if bad:
            raise PrivacyError('; '.join(bad))
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.executescript(OUTBOX_SQL)
        self.install_id, self.node, self.product, self.version, self.env = install_id, node, product, version, env
        self.secret, self.consent, self.clock = secret, consent, clock
        self.limits = dict(LIMITS, **(limits or {}))

    def close(self):
        self.db.close()

    # ---------------------------------------------------------------- queue
    def _count(self, key, n=1):
        self.db.execute('INSERT INTO counters (k, n) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET n = n + ?', (key, n, n))

    def counters(self):
        return dict(self.db.execute('SELECT k, n FROM counters').fetchall())

    def subject(self, user):
        return pseudonym(self.secret, user) if user is not None else None

    def emit(self, etype, data=None, user=None, role=None, page=None, sev='info'):
        """Queue one event; returns its id, or None when consent says no (counted under dropped.*).
        Raises PrivacyError when the event itself breaks the limits, whatever the consent."""
        data = clean_data(self.tax, etype, data or {})
        spec = self.tax['types'][etype]
        for k, v in (('role', role), ('page', page)):
            if v is not None and (not isinstance(v, str) or not ID_RE.match(v) or LONG_DIGITS.search(v)):
                raise PrivacyError(f'{k} must be a short machine id')
        if sev not in SEVS:
            raise PrivacyError('bad severity')
        level = spec['level']
        if level == 'feedback':
            subject = self.subject(user) if (user is not None and self.consent.allowed(user)) else None
        elif not self.consent.install_allowed():
            self._count('dropped.no_install_consent')
            return None
        elif level == 'person':
            if user is None or not self.consent.allowed(user):
                self._count('dropped.no_person_consent')
                return None
            subject = self.subject(user)
        else:
            subject, role = None, None
        t = self.clock()
        ev = {'v': 1, 'id': uuid7(t), 'install_id': self.install_id, 'node': self.node, 'product': self.product,
              'version': self.version, 'env': self.env, 'ts': now_iso(t), 'type': etype, 'sev': sev,
              'anon': subject is None, 'subject': subject, 'role': role, 'page': page, 'data': data}
        merge = spec.get('merge')
        key = None
        if merge is not None:
            hour = int(t // 3600)
            key = '|'.join([etype, str(hour), subject or '-', page or '-'] + [str(data.get(m, '-')) for m in merge])
            row = self.db.execute('SELECT id, body FROM outbox WHERE merge_key = ?', (key,)).fetchone()
            if row:
                old = json.loads(row[1])
                old['data']['count'] = old['data'].get('count', 1) + data.get('count', 1)
                body = json.dumps(old, ensure_ascii=False, separators=(',', ':'))
                self.db.execute('UPDATE outbox SET body = ?, size = ? WHERE id = ?', (body, len(body.encode()), row[0]))
                return row[0]
            ev['data'].setdefault('count', 1)
        body = json.dumps(ev, ensure_ascii=False, separators=(',', ':'))
        self.db.execute('INSERT INTO outbox (id, created, type, prio, subject, merge_key, body, size) VALUES (?,?,?,?,?,?,?,?)',
                        (ev['id'], t, etype, spec['prio'], subject, key, body, len(body.encode())))
        self.enforce()
        return ev['id']

    def enforce(self):
        """Bounds: age, count, bytes. Over a limit, the least important (highest prio number), oldest go first."""
        lim = self.limits
        cut = self.clock() - lim['max_age_days'] * 86400
        n = self.db.execute('DELETE FROM outbox WHERE created < ?', (cut,)).rowcount
        if n:
            self._count('dropped.expired', n)
        while True:
            count, size = self.db.execute('SELECT COUNT(*), COALESCE(SUM(size), 0) FROM outbox').fetchone()
            if count <= lim['max_events'] and size <= lim['max_bytes']:
                return
            row = self.db.execute('SELECT id FROM outbox ORDER BY prio DESC, created ASC LIMIT 1').fetchone()
            self.db.execute('DELETE FROM outbox WHERE id = ?', (row[0],))
            self._count('dropped.full')

    def purge_subject(self, user):
        """Decline or withdraw: delete every pending event of this person (feedback they already sent stays sent)."""
        n = self.db.execute("DELETE FROM outbox WHERE subject = ? AND type NOT LIKE 'fb.%'", (self.subject(user),)).rowcount
        self._count('purged', n)
        return n

    def purge_all(self):
        """Installation consent withdrawn: nothing but the person's own problem reports stays queued."""
        return self.db.execute("DELETE FROM outbox WHERE type NOT LIKE 'fb.%'").rowcount

    def on_consent_change(self, scope, subject, decision):
        """Pass as af_consent.Consent(db, on_change=tel.on_consent_change)."""
        if decision in ('decline', 'withdraw'):
            return self.purge_all() if scope == 'install' else self.purge_subject(subject)
        return 0

    # ---------------------------------------------------------------- errors and feedback
    @staticmethod
    def fingerprint(exc, root=None):
        """Same bug, same fingerprint, on every PC: exception type + the product's own frames (file:function)."""
        frames = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
        own = [f for f in frames if root is None or str(f.filename).startswith(str(root))] or frames
        parts = [type(exc).__name__] + [f'{Path(f.filename).stem}:{f.name}' for f in own[-6:]]
        digest = hashlib.sha256('|'.join(parts).encode()).hexdigest()[:16].translate(HEX_LETTERS)
        return digest, (parts[-1] if len(parts) > 1 else parts[0])

    def capture(self, exc, where=None, status=500, root=None):
        """err.server for an exception: type, fingerprint and module:function only - never the message text."""
        fp, frame = self.fingerprint(exc, root)
        where = re.sub(r'[^A-Za-z0-9_.:\-/]', '_', where or frame)[:80]
        return self.emit('err.server', {'code': type(exc).__name__[:60], 'fingerprint': fp, 'where': where,
                                        'status': int(status)}, sev='error')

    def feedback_preview(self, kind, text, page=None, guide=None, problem=None, contact='none', diagnostics=None,
                         category=None):
        etype = 'fb.' + kind
        if etype not in self.tax['types'] or self.tax['types'][etype]['level'] != 'feedback':
            raise PrivacyError('kind is problem, idea or question')
        data = {'text': text, 'contact': contact}
        for k, v in (('page', page), ('guide', guide), ('problem', problem), ('category', category), ('diagnostics', diagnostics)):
            if v is not None:
                data[k] = v
        return etype, clean_data(self.tax, etype, data)

    def preview(self, kind, text, **kw):
        """What POST /api/telemetry/feedback/preview returns: the exact data that would be sent, and its digest.
        The send must carry the same digest (confirm=...), so nothing is sent that the person did not see."""
        etype, data = self.feedback_preview(kind, text, **kw)
        return {'event': {'type': etype, 'data': data}, 'digest': _digest(etype, data)}

    def feedback(self, kind, text, user=None, confirm=None, **kw):
        """A problem report, idea or question, exactly as previewed. Allowed without tracking consent."""
        etype, data = self.feedback_preview(kind, text, **kw)
        if not data['text']:
            raise PrivacyError('empty report')
        if confirm is not None and not hmac.compare_digest(str(confirm), _digest(etype, data)):
            raise PrivacyError('the report changed after the preview')
        return self.emit(etype, data, user=user, page=data.get('page'), sev='warn' if kind == 'problem' else 'info')

    BROWSER_TYPES = ('use.', 'guide.', 'problem.', 'err.client', 'err.shown', 'deny')

    def from_browser(self, events, user, role=None):
        """POST /api/telemetry/events from af-telemetry.js: only browser-side types, the signed-in person from the
        session (never from the body), consent and limits applied here. Bad events are counted, not raised."""
        out = {'queued': 0, 'dropped': 0, 'rejected': 0}
        for e in (events if isinstance(events, list) else [])[:200]:
            try:
                if not isinstance(e, dict) or not str(e.get('type', '')).startswith(self.BROWSER_TYPES):
                    raise PrivacyError('not a browser event')
                ok = self.emit(e['type'], e.get('data') or {}, user=user, role=role, page=e.get('page'),
                               sev='error' if e['type'].startswith('err.') else 'info')
                out['queued' if ok else 'dropped'] += 1
            except PrivacyError:
                out['rejected'] += 1
                self._count('rejected.browser')
        return out

    # ---------------------------------------------------------------- sending
    def pending(self, limit=50):
        return [json.loads(r[0]) for r in self.db.execute('SELECT body FROM outbox ORDER BY created DESC LIMIT ?', (limit,))]

    def recent_sent(self, limit=50):
        """For the optional «ماذا أُرسل؟» viewer."""
        return [json.loads(r[0]) for r in self.db.execute('SELECT body FROM sent ORDER BY at DESC LIMIT ?', (limit,))]

    def batch(self):
        """(ids, gzip body) of the next batch: most important first, oldest first, up to batch_bytes uncompressed."""
        ids, events, size = [], [], 2
        for eid, body, n in self.db.execute('SELECT id, body, size FROM outbox ORDER BY prio ASC, created ASC'):
            if size + n + 1 > self.limits['batch_bytes'] and events:
                break
            ids.append(eid)
            events.append(body)
            size += n + 1
        if not ids:
            return [], b''
        return ids, gzip.compress(('[' + ','.join(events) + ']').encode(), mtime=0)

    def mark_sent(self, ids):
        t = self.clock()
        for eid in ids:
            row = self.db.execute('SELECT body FROM outbox WHERE id = ?', (eid,)).fetchone()
            if row:
                self.db.execute('INSERT OR REPLACE INTO sent (id, at, body) VALUES (?, ?, ?)', (eid, t, row[0]))
                self.db.execute('DELETE FROM outbox WHERE id = ?', (eid,))
        self.db.execute('DELETE FROM sent WHERE id NOT IN (SELECT id FROM sent ORDER BY at DESC LIMIT ?)', (self.limits['sent_log'],))

    def _state(self, k, default=None):
        row = self.db.execute('SELECT v FROM state WHERE k = ?', (k,)).fetchone()
        return json.loads(row[0]) if row else default

    def _set(self, k, v):
        self.db.execute('INSERT INTO state (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v', (k, json.dumps(v)))

    def due(self):
        return self.clock() >= self._state('next_try', 0)

    def send_once(self, url, token, post=None):
        """Send one batch if due. post(url, body, headers) -> HTTP status (default: urllib). Returns
        ('sent', n) | ('idle', 0) | ('backoff', seconds) | ('failed', status)."""
        if not self.due():
            return 'backoff', int(self._state('next_try', 0) - self.clock())
        ids, body = self.batch()
        if not ids:
            return 'idle', 0
        ts, nonce = str(int(self.clock())), secrets.token_hex(12)
        headers = {'Content-Type': 'application/json', 'Content-Encoding': 'gzip', 'X-AF-Install': self.install_id,
                   'X-AF-Timestamp': ts, 'X-AF-Nonce': nonce, 'X-AF-Signature': sign(token, ts, nonce, body)}
        try:
            status = (post or _post)(url, body, headers)
        except OSError:
            status = 0
        if 200 <= status < 300:
            self.mark_sent(ids)
            self._set('fails', 0)
            self._set('next_try', 0)
            return 'sent', len(ids)
        fails = self._state('fails', 0) + 1
        wait = min(self.limits['backoff_max_s'], self.limits['backoff_min_s'] * 2 ** (fails - 1))
        self._set('fails', fails)
        self._set('next_try', self.clock() + wait)
        return 'failed', status


def _digest(etype, data):
    return hashlib.sha256(json.dumps([etype, data], ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _post(url, body, headers):
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
