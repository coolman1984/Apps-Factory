"""The activation chain, over real HTTP: a shop's request → the real relay Worker (Node, node:sqlite shim) → the studio's owner-approved
policy → the signed code back through the relay → the shop checks it with the vendor's PUBLIC key only. Skipped without Node 22.13+.

Covers: automatic trial, one trial per PC, a locked key, paid kinds that always wait for the owner, a relay that is down, the audit,
and the proof that the relay and the audit never hold a key, a passphrase or a Telegram token."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'packages' / 'af-license'))
from licence_studio import relay as relay_mod  # noqa: E402
from licence_studio.service import Studio, StudioError  # noqa: E402
from af_license import codes  # noqa: E402

PASS = 'a long passphrase for tests'
ADMIN = 'licence-admin-secret-for-tests'
SERVE = ROOT / 'templates' / 'telemetry-relay' / 'test' / 'serve.mjs'


def node_ok():
    node = shutil.which('node')
    if not node or not SERVE.exists():
        return False
    try:
        out = subprocess.run([node, '--experimental-sqlite', '-e', "require('node:sqlite'); console.log('ok')"], capture_output=True, text=True, timeout=20)
        return out.stdout.strip() == 'ok'
    except (OSError, subprocess.SubprocessError):
        return False


class TelegramStub(BaseHTTPRequestHandler):
    messages: list = []

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        TelegramStub.messages.append(json.loads(self.rfile.read(n)))
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *a):
        pass


def machine_tag(name):
    import hashlib
    return hashlib.sha256(('AF-MACHINE/1|' + name).encode()).hexdigest()


@unittest.skipUnless(node_ok(), 'Node 22.13+ (node:sqlite) is needed to run the relay Worker')
class Chain(unittest.TestCase):
    def setUp(self):
        TelegramStub.messages = []
        self.tg = HTTPServer(('127.0.0.1', 0), TelegramStub)
        threading.Thread(target=self.tg.serve_forever, daemon=True).start()
        self.relay_proc = subprocess.Popen([shutil.which('node'), '--experimental-sqlite', str(SERVE)], stdout=subprocess.PIPE, text=True,
                                           cwd=str(SERVE.parent))
        self.port = json.loads(self.relay_proc.stdout.readline())['port']
        self.base = f'http://127.0.0.1:{self.port}'
        os.environ.update(TELEGRAM_BOT_TOKEN='999:STUDIO-BOT-SECRET', TELEGRAM_OWNER_CHAT_ID='7', LS_TELEGRAM_API=f'http://127.0.0.1:{self.tg.server_port}')
        os.environ.pop('LS_RELAY_URL', None)
        os.environ.pop('LS_RELAY_TOKEN', None)
        self.dir = tempfile.mkdtemp()
        self.s = Studio(self.dir)
        self.s.create_key(PASS)
        self.s.relay.save(self.base, ADMIN)
        self.public = self.s.public_key().split(':', 1)[1]

    def tearDown(self):
        self.relay_proc.terminate()
        self.relay_proc.wait(10)
        self.relay_proc.stdout.close()
        self.tg.shutdown()
        self.tg.server_close()
        for k in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_OWNER_CHAT_ID', 'LS_TELEGRAM_API'):
            os.environ.pop(k, None)
        shutil.rmtree(self.dir, ignore_errors=True)

    # ---- the shop's side: plain HTTP, no key, no secret
    def shop(self, method, path, body=None, token=None, ip='203.0.113.9'):
        req = urllib.request.Request(self.base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type': 'application/json', 'X-Test-IP': ip, **({'Authorization': 'Bearer ' + token} if token else {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b'{}')

    def ask(self, pc='pc-1', install='install-1', kind='trial', **extra):
        device = codes.device_code(pc, install)
        body = {'product': 'al-store', 'kind': kind, 'device': device, 'nonce': str(uuid.uuid4()), 'shop': 'Test shop', 'version': '1.6.0',
                **({'machine': machine_tag(pc)} if kind == 'trial' else {}), **extra}
        st, d = self.shop('POST', '/licence/request', body)
        return device, st, d

    def status(self, d):
        return self.shop('GET', '/licence/status?id=' + d['id'], token=d['poll_token'])[1]

    def messages(self):
        return [m['text'] for m in TelegramStub.messages]

    def relay_telegram(self):
        with urllib.request.urlopen(self.base + '/__test/telegram', timeout=10) as r:
            return [m['body']['text'] for m in json.loads(r.read())]

    # ---- tests
    def test_trial_is_issued_by_policy_delivered_and_checked_by_the_shop(self):
        device, st, d = self.ask()
        self.assertEqual((st, d['status']), (202, 'pending'))
        self.assertEqual(len(self.relay_telegram()), 1, 'the owner\'s phone is told by the relay')
        self.assertNotIn('Test shop', self.relay_telegram()[0])
        # policy OFF (the default): the request is pulled and waits for the owner; nothing is signed
        out = self.s.auto.cycle()
        self.assertEqual((out['ok'], out['pulled'], out['issued']), (True, 1, 0))
        [req] = self.s.requests()
        self.assertEqual((req['source'], req['kind'], req['status'], req['policy']), ('relay', 'trial', 'pending', {'verdict': 'issue', 'reason': ''}))
        self.assertEqual(self.status(d)['status'], 'pending')
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 0)
        # the owner switches the policy on, and keeps the key open for the working day
        self.s.set_setting('auto_trials', True)
        self.s.keep_unlocked(10)
        out = self.s.auto.cycle()
        self.assertEqual((out['issued'], out['delivered']), (1, 1), out)
        got = self.status(d)
        self.assertEqual(got['status'], 'issued')
        # the shop checks the code ITSELF with the vendor's public key and its own device code: the relay is not trusted
        read = codes.read_code(got['code'], [self.public], 'al-store', device)
        self.assertEqual((read.valid, read.state, read.terms['edition'], read.terms['days_left']), (True, 'active', 'trial', 14))
        self.assertFalse(codes.read_code(got['code'], [self.public], 'al-store', codes.device_code('other-pc', 'x')).valid)
        self.assertEqual(self.shop('POST', '/licence/ack', {'id': d['id']}, token=d['poll_token'])[1]['status'], 'delivered')
        self.assertIn('✅', ' '.join(self.messages()))
        # a second look: nothing is pending and nothing is issued twice
        out = self.s.auto.cycle()
        self.assertEqual((out['pulled'], out['issued']), (0, 0))
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 1)

    def test_one_trial_per_pc_even_with_a_new_device_code(self):
        self.s.set_setting('auto_trials', True)
        self.s.keep_unlocked(1)
        _, _, first = self.ask(pc='pc-1', install='install-1')
        self.s.auto.cycle()
        self.assertEqual(self.status(first)['status'], 'issued')
        self.shop('POST', '/licence/ack', {'id': first['id']}, token=first['poll_token'])
        # reinstall: same PC, new install id, so a new device code
        _, st, again = self.ask(pc='pc-1', install='install-2')
        self.assertEqual((st, again['status'], again['reason']), (200, 'refused', 'already_used'), 'the relay refuses at once')
        self.assertEqual(self.s.auto.cycle()['pulled'], 0, 'and the owner is not bothered')
        # the studio's own permanent record also refuses, even if the relay forgot (a request that reached it anyway)
        item = {'id': str(uuid.uuid4()), 'product': 'al-store', 'kind': 'trial', 'device': codes.device_code('pc-1', 'install-3'),
                'machine': machine_tag('pc-1'), 'shop': 'x', 'ref': '', 'src': 'a' * 16}
        row = self.s.auto.ingest(item)
        self.assertEqual(self.s.auto.verdict(row)[:2], ('refuse', 'already_used'))
        # the SAME device asking again (it lost the code) gets the same code, not a new trial
        same = {**item, 'id': str(uuid.uuid4()), 'device': codes.device_code('pc-1', 'install-1')}
        row2 = self.s.auto.ingest(same)
        self.assertEqual(self.s.auto.verdict(row2)[0], 'reissue')
        # the ledger is permanent
        with self.assertRaises(Exception):
            self.s.db.execute('DELETE FROM trial_ledger')
        with self.assertRaises(StudioError) as e:
            self.s.issue('al-store', 'trial', codes.device_code('pc-1', 'install-9'), 'x', machine=machine_tag('pc-1'))
        self.assertEqual(e.exception.key, 'trial.repeat')
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 1)

    def test_a_locked_key_waits_and_says_so_then_the_next_round_issues(self):
        self.s.set_setting('auto_trials', True)
        self.s.keep_unlocked(1)
        self.s.lock_key()
        _, _, d = self.ask()
        out = self.s.auto.cycle()
        self.assertEqual((out['issued'], out['held']), (0, 1))
        self.assertEqual(self.s.requests()[0]['held'], 'locked')
        self.assertTrue(any('🔒' in m for m in self.messages()))
        self.s.auto.cycle()
        self.assertEqual(len([m for m in self.messages() if '🔒' in m]), 1, 'one message, not one per round')
        self.assertEqual(self.status(d)['status'], 'pending')
        self.s.unlock(PASS)
        self.assertEqual(self.s.auto.cycle()['issued'], 1)
        self.assertEqual(self.status(d)['status'], 'issued')

    def test_paid_kinds_never_go_out_without_the_owner_and_the_payment(self):
        self.s.set_setting('auto_trials', True)
        self.s.keep_unlocked(1)
        device, st, d = self.ask(kind='monthly', ref='InstaPay 5521')
        self.assertEqual(st, 202)
        self.s.auto.cycle()
        [req] = self.s.requests()
        self.assertEqual((req['status'], req['policy']['reason']), ('pending', 'payment_needed'))
        self.assertEqual(req['payment_ref'], '', 'a payment reference typed in the shop is not kept in the cloud: the owner writes his own (review of PR #33)')
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 0)
        with self.assertRaises(StudioError) as e:
            self.s.decide(req['id'], True)  # no payment confirmation
        self.assertEqual(e.exception.key, 'payment.required')
        with self.assertRaises(StudioError):
            self.s.decide(req['id'], True, payment_confirmed=True, payment_ref='x')
        self.s.decide(req['id'], True, payment_confirmed=True, payment_ref='InstaPay 5521 / 350 EGP')
        got = self.status(d)
        self.assertEqual(got['status'], 'issued')
        read = codes.read_code(got['code'], [self.public], 'al-store', device)
        self.assertEqual((read.terms['edition'], read.terms['grace_days'], read.valid), ('standard', 3, True))
        row = self.s.one('SELECT * FROM requests')
        self.assertEqual((row['payment_confirmed'], row['relayed'], row['decided_by']), (1, 1, 'owner'))
        # a permanent code is the same: only the owner, only with the money
        device2, _, d2 = self.ask(pc='pc-2', install='i2', kind='permanent')
        self.s.auto.cycle()
        req2 = [r for r in self.s.requests() if r['kind'] == 'permanent'][0]
        self.s.decide(req2['id'], True, payment_confirmed=True, payment_ref='transfer 9001')
        read2 = codes.read_code(self.status(d2)['code'], [self.public], 'al-store', device2)
        self.assertEqual((read2.terms['edition'], read2.terms['last_day'], read2.valid), ('perpetual', None, True))

    def test_the_owner_can_refuse_and_the_shop_sees_it(self):
        _, _, d = self.ask()
        self.s.auto.cycle()
        self.s.decide(self.s.requests()[0]['id'], False)
        got = self.status(d)
        self.assertEqual((got['status'], got['reason']), ('refused', 'owner_refused'))

    def test_daily_cap_and_a_flooding_address_wait_for_the_owner(self):
        self.s.set_setting('auto_trials', True)
        self.s.set_setting('auto_trial_daily_cap', 2)
        self.s.keep_unlocked(1)
        ds = [self.ask(pc=f'pc-{i}', install=f'i-{i}')[2] for i in range(4)]
        out = self.s.auto.cycle()
        self.assertEqual((out['issued'], out['held']), (2, 2))
        self.assertEqual(sorted(r['held'] for r in self.s.requests()), ['daily_cap', 'daily_cap'])
        self.assertEqual([self.status(d)['status'] for d in ds].count('issued'), 2)
        self.s.set_setting('auto_trial_daily_cap', 50)
        for i in range(10, 15):  # one address, five more requests in a day: the studio wants a human to look
            self.ask(pc=f'pc-{i}', install=f'i-{i}')
        self.s.auto.cycle()
        self.assertIn('review_src', {r['held'] for r in self.s.requests()})

    def test_relay_trouble_is_calm_and_delivery_is_retried(self):
        self.s.set_setting('auto_trials', True)
        self.s.keep_unlocked(1)
        _, _, d = self.ask()
        self.s.relay.save(self.base, 'a-wrong-token-a-wrong-token')
        out = self.s.auto.cycle()
        self.assertEqual((out['ok'], out['error']), (False, 'relay.http'))
        self.assertEqual(self.status(d)['status'], 'pending')
        self.s.relay.save(self.base, ADMIN)
        self.assertEqual(self.s.auto.cycle()['issued'], 1)
        # issued here but the relay could not be reached: the code stays in the studio and goes out in a later round
        _, _, d2 = self.ask(pc='pc-2', install='i2')
        self.s.auto.cycle()
        self.assertEqual(self.status(d2)['status'], 'issued')
        self.relay_proc.terminate()
        self.relay_proc.wait(10)
        dead = self.s.auto.cycle()
        self.assertEqual((dead['ok'], dead['error']), (False, 'relay.down'))
        self.assertEqual(self.s.requests(status='')[0]['relay_id'] is not None, True)

    def test_every_step_is_in_the_audit_and_no_secret_is_anywhere(self):
        self.s.set_setting('auto_trials', True)
        self.s.keep_unlocked(1)
        _, _, d = self.ask()
        self.s.auto.cycle()
        self.shop('POST', '/licence/ack', {'id': d['id']}, token=d['poll_token'])
        log = self.s.audit_log()
        actions = [r['action'] for r in log]
        for a in ('key.create', 'key.keep_unlocked', 'request.relay', 'code.issue', 'request.approve', 'request.delivered'):
            self.assertIn(a, actions)
        blob = json.dumps(log) + json.dumps(self.s.status()) + json.dumps(self.s.requests(status=''))
        for secret in (PASS, ADMIN, 'STUDIO-BOT-SECRET', d['poll_token']):
            self.assertNotIn(secret, blob)
        self.assertNotIn(ADMIN, json.dumps(self.s.relay.public()))
        private = [p for p in Path(self.dir, 'keys').glob('*.pem')][0].read_bytes()
        self.assertIn(b'ENCRYPTED', private, 'the signing key exists only here, encrypted')
        relay_text = json.dumps(self.relay_telegram())
        self.assertNotIn('PRIVATE KEY', relay_text)
        # the relay's own event log has the steps and no code
        req = urllib.request.Request(self.base + '/licence/events', headers={'Authorization': 'Bearer ' + ADMIN})
        with urllib.request.urlopen(req, timeout=10) as r:
            events = r.read().decode()
        self.assertIn('delivered', events)
        self.assertNotIn(self.status(d).get('code') or 'no-code', events)

    def test_keeping_the_key_open_is_the_owners_explicit_and_time_limited_choice(self):
        with self.assertRaises(StudioError):
            Studio(self.dir).keep_unlocked(1)  # a locked studio cannot be asked to stay open
        self.s.keep_unlocked(2)
        self.s._unlocked_at -= 3 * 3600  # no activity for 3 hours
        self.assertTrue(self.s.unlocked(), 'still open: the owner asked for 2 hours from now')
        self.s._keep_until = time.time() - 1
        self.assertFalse(self.s.unlocked(), 'the time is over: back behind the passphrase')
        self.s.unlock(PASS)
        self.s.keep_unlocked(99)
        self.assertLessEqual(self.s._keep_until - time.time(), 12 * 3600 + 5, 'never more than a working day')
        self.s.lock_key()
        self.assertEqual(self.s._keep_until, 0.0)

    # ---- review of PR #34
    def test_automatic_signing_never_keeps_the_key_open_past_the_owners_deadline(self):
        self.s.set_setting('auto_trials', True)
        self.s.keep_unlocked(1)
        self.s._unlocked_at -= 3 * 3600  # the owner left 3 hours ago
        self.ask()
        self.assertEqual(self.s.auto.cycle()['issued'], 1, 'inside the kept-open time the policy signs')
        self.assertLess(self.s._unlocked_at, time.time() - 3600, 'and that signing did not count as the owner being here')
        self.s._keep_until = time.time() - 1  # the owner's deadline passes
        self.assertFalse(self.s.unlocked(), 'locked, whatever the automatic traffic just before')

    def test_one_decision_per_request_even_when_the_owner_and_the_round_meet(self):
        _, _, d = self.ask(kind='monthly')
        self.s.auto.cycle()
        rid = self.s.requests()[0]['id']
        self.assertTrue(self.s.claim(rid), 'the automatic round takes it first')
        with self.assertRaises(StudioError) as e:
            self.s.decide(rid, False)  # the owner presses refuse at the same moment
        self.assertEqual(e.exception.key, 'request.closed')
        self.s.release(rid)
        self.s.decide(rid, False)
        self.assertEqual(self.status(d)['status'], 'refused')

    def test_a_request_the_relay_closed_is_not_reported_as_sent(self):
        _, _, d = self.ask()
        self.s.auto.cycle()
        rid = self.s.requests()[0]['id']
        real = self.s.relay.refuse

        def gone(*a, **k):
            raise relay_mod.RelayError('relay.http_409', 'closed', 409)
        self.s.relay.refuse = gone
        try:
            self.s.decide(rid, False)
        finally:
            self.s.relay.refuse = real
        row = self.s.one('SELECT relayed FROM requests WHERE id = ?', rid)
        self.assertEqual(row['relayed'], 2, 'not "sent": the owner is told to send it by hand')
        self.assertIn('request.undeliverable', [a['action'] for a in self.s.rows('SELECT action FROM audit')])

    def test_requests_waiting_for_the_owner_do_not_hide_newer_ones(self):
        for i in range(12):  # paid requests wait for the owner and stay pending on the relay
            self.ask(pc=f'paid-{i}', install=f'i-{i}', kind='monthly')
        self.ask(pc='new-pc', install='new-install')
        self.assertEqual(len(self.s.relay.pending(5)), 5, 'one page')
        every = self.s.relay.pending_all(page=5)
        self.assertEqual(len(every), 13, 'page by page, the newest request is reached too')
        self.assertEqual(len({r['id'] for r in every}), 13, 'no request twice')

    def test_the_relay_address_must_be_https_and_the_telegram_override_is_local_only(self):
        for bad in ('http://example.com', 'ftp://x', 'https://user:pw@example.com', 'example.com', ''):
            with self.assertRaises(relay_mod.RelayError, msg=bad):
                self.s.relay.save(bad)
        self.s.relay.save('https://relay.example.workers.dev/')
        self.assertEqual(self.s.relay.public()['host'], 'relay.example.workers.dev')
        mode = os.stat(Path(self.dir, 'relay.json')).st_mode & 0o777
        if os.name != 'nt':
            self.assertEqual(mode, 0o600)
        os.environ['LS_TELEGRAM_API'] = 'https://evil.example'
        self.assertFalse(relay_mod.telegram('hello'), 'the test override never sends the bot token to a remote host')
        self.assertEqual(TelegramStub.messages, [])


if __name__ == '__main__':
    unittest.main()
