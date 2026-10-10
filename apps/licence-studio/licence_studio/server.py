"""Licence Studio web server: the owner's page (loopback only) and the agent API used by the MCP bridge.

- Binds to 127.0.0.1 only. Host and Origin are checked (a web page elsewhere cannot drive it).
- The owner's session starts when the passphrase unlocks the key and ends when the key locks (idle 30 min, or "Lock").
- The agent API needs the bearer token the owner created on the "AI agent" page. It never sees the passphrase or the key.
"""
from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
import secrets
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .relay import RelayError
from .service import Studio, StudioError

STATIC = Path(__file__).parent / 'static'
AF_UI = Path(__file__).resolve().parents[3] / 'packages' / 'af-ui'  # the factory's shared design system
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; "
       "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
COOKIE = 'ls_owner'


class App:
    def __init__(self, studio: Studio, port: int):
        self.studio, self.port = studio, port
        self.sessions: set[str] = set()
        self.lock = threading.Lock()

    def owner_ok(self, token):
        if not self.studio.unlocked():
            with self.lock:
                self.sessions.clear()
            return False
        return token in self.sessions

    def new_session(self):
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.sessions.add(token)
        return token


def make_handler(app: App):
    S = app.studio

    class Handler(BaseHTTPRequestHandler):
        server_version = 'LicenceStudio/1.0'
        protocol_version = 'HTTP/1.1'

        def log_message(self, *a):
            pass

        def host_ok(self):
            return (self.headers.get('Host') or '').rsplit(':', 1)[0] in ('127.0.0.1', 'localhost')

        def send(self, code, body, ctype='application/json', headers=None):
            raw = json.dumps(body, ensure_ascii=False).encode() if not isinstance(body, (bytes, str)) else (
                body.encode() if isinstance(body, str) else body)
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            if ctype.startswith('text/html'):
                self.send_header('Content-Security-Policy', CSP)
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(raw)

        def cookie(self):
            for part in (self.headers.get('Cookie') or '').split(';'):
                k, _, v = part.strip().partition('=')
                if k == COOKIE:
                    return v
            return ''

        timeout = 30  # a stalled client must not hold a thread for ever

        def body(self):
            raw = self.headers.get('Content-Length') or '0'
            if not raw.isdigit() or int(raw) > 1_000_000:
                self.close_connection = True  # the body is not read: never reuse this connection
                raise StudioError('too_large', 'Request too large.', 413)
            n = int(raw)
            parsed = json.loads(self.rfile.read(n) or b'{}') if n else {}
            if not isinstance(parsed, dict):
                raise StudioError('bad_request', 'The request is not understood.', 400)
            return parsed

        def do_GET(self):
            if not self.host_ok():
                return self.send(421, {'error': 'unknown host'})
            url = urlparse(self.path)
            if url.path.startswith('/api/') or url.path.startswith('/agent/'):
                return self.guard(lambda: self.api('GET', url.path, {k: v[-1] for k, v in parse_qs(url.query, keep_blank_values=True).items()}, {}))
            base = STATIC
            rel = 'index.html' if url.path in ('/', '/index.html') else url.path.lstrip('/')
            if rel.startswith('af-ui/'):
                base, rel = AF_UI, rel[len('af-ui/'):]
            path = (base / rel).resolve()
            if not path.is_relative_to(base.resolve()) or not path.is_file():
                return self.send(404, {'error': 'not found'})
            ctype = {'.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8',
                     '.woff2': 'font/woff2', '.svg': 'image/svg+xml'}.get(path.suffix) or mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
            self.send(200, path.read_bytes(), ctype)

        def do_POST(self):
            if not self.host_ok():
                return self.send(421, {'error': 'unknown host'})
            origin = self.headers.get('Origin')
            if origin and urlparse(origin).netloc != self.headers.get('Host'):
                return self.send(403, {'error': 'cross-site request refused'})
            url = urlparse(self.path)
            self.guard(lambda: self.api('POST', url.path, {}, self.body()))

        def guard(self, fn):
            try:
                fn()
            except StudioError as e:
                self.send(e.status, {'error': str(e), 'key': e.key})
            except RelayError as e:  # the relay is a different computer: its trouble is a calm 502, never a crash
                self.send(502, {'error': str(e), 'key': e.key})
            except (ValueError, KeyError, TypeError, AttributeError, OverflowError, sqlite3.Error, json.JSONDecodeError) as e:
                self.send(400, {'error': f'Bad request: {e}', 'key': 'bad_request'})

        # ------------------------------------------------------------ routes
        def api(self, method, path, q, d):
            if path.startswith('/agent/'):
                token = (self.headers.get('Authorization') or '').removeprefix('Bearer ').strip()
                if not S.agent_ok(token):
                    raise StudioError('agent.token', 'Agent token missing or revoked.', 401)
                return self.send(200, self.agent(method, path, q, d))
            if path == '/api/status':
                st = S.status()
                st['owner'] = app.owner_ok(self.cookie())
                return self.send(200, st if st['owner'] else {k: st[k] for k in ('key', 'unlocked', 'owner')})
            if path == '/api/key/create' and method == 'POST':
                out = S.create_key(d.get('passphrase'))
                return self.send(200, out, headers=self.session_cookie())
            if path == '/api/unlock' and method == 'POST':
                S.unlock(d.get('passphrase'))
                return self.send(200, {'ok': True}, headers=self.session_cookie())
            if not app.owner_ok(self.cookie()):
                raise StudioError('owner.locked', 'Unlock the studio with your passphrase.', 401)
            if method == 'GET':
                if path == '/api/products':
                    return self.send(200, S.products())
                if path == '/api/codes':
                    return self.send(200, S.list_codes(q.get('q', ''), q.get('product', ''), q.get('status', '')))
                if path == '/api/code':
                    return self.send(200, S.code(q.get('serial')))
                if path == '/api/requests':
                    return self.send(200, S.requests(q.get('status', 'pending')))
                if path == '/api/audit':
                    return self.send(200, S.audit_log())
                if path == '/api/tokens':
                    return self.send(200, S.tokens())
                if path == '/api/relay':
                    return self.send(200, {**S.relay.public(), 'last': dict(S.auto.last), 'policy': S.policy()})
                if path == '/api/export.csv':
                    out = io.StringIO()
                    out.write('﻿')
                    rows = S.list_codes(limit=2000)
                    cols = ['serial', 'product', 'edition', 'customer', 'phone', 'device', 'first_day', 'last_day', 'status', 'issued_at', 'issued_by', 'note']
                    w = csv.writer(out)
                    w.writerow(cols)
                    for r in rows:
                        w.writerow([("'" + str(r[c])) if str(r[c])[:1] and str(r[c])[0] in '=+-@\t\r' else r[c] for c in cols])
                    return self.send(200, out.getvalue(), 'text/csv; charset=utf-8', {'Content-Disposition': 'attachment; filename="licence-codes.csv"'})
            if method == 'POST':
                if path == '/api/lock':
                    S.lock_key()
                    app.sessions.clear()
                    return self.send(200, {'ok': True})
                if path == '/api/issue':
                    return self.send(200, S.issue(d['product'], d.get('edition', 'trial'), d.get('device'), d.get('customer', ''), d.get('phone', ''),
                                                  d.get('days'), d.get('first_day'), d.get('grace_days', 0), d.get('seats', 1), d.get('note', '')))
                if path == '/api/verify':
                    return self.send(200, S.verify(d.get('code', ''), d.get('product', ''), d.get('device')))
                if path == '/api/product/save':
                    return self.send(200, {'id': S.add_product(d.get('id'), d.get('name'), d.get('trial_days', 14))})
                if path == '/api/request/decide':
                    return self.send(200, S.decide(d.get('id'), bool(d.get('approve')), payment_confirmed=d.get('payment_confirmed') is True,
                                                   payment_ref=str(d.get('payment_ref') or ''), defer=True))
                if path == '/api/policy':
                    if 'agent_may_issue_trials' in d:
                        S.set_setting('agent_may_issue_trials', bool(d['agent_may_issue_trials']))
                    if 'agent_daily_limit' in d:
                        S.set_setting('agent_daily_limit', max(0, min(100, int(d['agent_daily_limit']))))
                    if 'auto_trials' in d:
                        S.set_setting('auto_trials', d['auto_trials'] is True)
                    if 'auto_trial_days' in d:
                        S.set_setting('auto_trial_days', max(1, min(14, int(d['auto_trial_days']))))
                    if 'auto_trial_daily_cap' in d:
                        S.set_setting('auto_trial_daily_cap', max(0, min(100, int(d['auto_trial_daily_cap']))))
                    return self.send(200, S.policy())
                if path == '/api/relay/save':
                    S.relay.save(d.get('url'), d.get('token') or None)
                    S.audit('owner', 'relay.save', {'host': S.relay.public()['host']})
                    return self.send(200, S.relay.public())
                if path == '/api/relay/pull':
                    return self.send(200, S.auto.cycle())
                if path == '/api/auto/keep':
                    return self.send(200, S.keep_unlocked(float(d.get('hours') or 0)))
                if path == '/api/token/new':
                    return self.send(200, {'token': S.new_agent_token(d.get('name') or 'AI agent'), 'url': f'http://127.0.0.1:{app.port}'})
                if path == '/api/tokens/revoke':
                    S.revoke_tokens()
                    return self.send(200, {'ok': True})
            raise StudioError('not_found', 'Unknown address.', 404)

        def agent(self, method, path, q, d):
            if path == '/agent/status':
                st = S.status()
                st.pop('home', None)
                return st
            if path == '/agent/products':
                return S.products()
            if path == '/agent/codes':
                return S.list_codes(q.get('q', '') or d.get('q', ''), q.get('product', '') or d.get('product', ''),
                                    q.get('status', '') or d.get('status', ''), 100)
            if path == '/agent/code':
                return S.code(q.get('serial') or d.get('serial'))
            if path == '/agent/requests':
                return S.requests(q.get('status', d.get('status', 'pending')))
            if method == 'POST' and path == '/agent/verify':
                return S.verify(d.get('code', ''), d.get('product', ''), d.get('device'))
            if method == 'POST' and path == '/agent/request':
                return S.request(d['product'], d.get('edition', 'trial'), d.get('device'), d.get('customer', ''), d.get('phone', ''),
                                 d.get('days'), d.get('note', ''), actor='agent')
            if method == 'POST' and path == '/agent/issue_trial':
                return S.agent_issue_trial(d['product'], d.get('device'), d.get('customer', ''), d.get('phone', ''), d.get('days'), d.get('note', ''))
            raise StudioError('not_found', 'Unknown agent action.', 404)

        def session_cookie(self):
            return {'Set-Cookie': f'{COOKIE}={app.new_session()}; Path=/; HttpOnly; SameSite=Strict'}

    return Handler


def serve(studio: Studio, port: int = 8770):
    app = App(studio, port)
    httpd = ThreadingHTTPServer(('127.0.0.1', port), make_handler(app))
    httpd.daemon_threads = True
    every = float(os.environ.get('LS_RELAY_EVERY', 60))  # 0 switches the background round off (tests, or a PC that must stay quiet)
    app.stop_auto = studio.auto.start(every) if every > 0 else None
    return httpd, app
