"""Licence Studio: key handling, issuing, the agent's limits, the web API's guards, the MCP bridge, and the proof that a
code from the studio unlocks a real product (Al-Store) — the whole chain the owner uses."""
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'packages' / 'af-license'))
from licence_studio import mcp  # noqa: E402
from licence_studio.server import serve  # noqa: E402
from licence_studio.service import Studio, StudioError  # noqa: E402
from af_license import codes  # noqa: E402

PASS = 'a long passphrase for tests'
DEVICE = codes.device_code('shop-pc-1', 'install-1')


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.s = Studio(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_key_is_encrypted_and_needs_the_passphrase(self):
        with self.assertRaises(StudioError):
            self.s.create_key('short')
        out = self.s.create_key(PASS)
        pem = Path(out['file']).read_bytes()
        self.assertIn(b'ENCRYPTED', pem)
        with self.assertRaises(StudioError):
            self.s.create_key(PASS)  # never a second key by accident
        fresh = Studio(self.dir)
        self.assertFalse(fresh.unlocked())
        with self.assertRaises(StudioError) as e:
            fresh.issue('al-store', 'trial', DEVICE)
        self.assertEqual(e.exception.status, 423)
        with self.assertRaises(StudioError):
            fresh.unlock('wrong passphrase!!')
        fresh.unlock(PASS)
        self.assertTrue(fresh.issue('al-store', 'trial', DEVICE, 'Shop')['code'])

    def test_trial_defaults_device_binding_and_verification(self):
        self.s.create_key(PASS)
        with self.assertRaises(StudioError):
            self.s.issue('al-store', 'trial', None)  # a trial is always tied to a device
        c = self.s.issue('al-store', 'trial', DEVICE.lower().replace('-', ''), 'Al-Amal shop', '01000000000')
        self.assertEqual(c['last_day'], (date.today() + timedelta(days=13)).isoformat())
        self.assertEqual(c['device'], DEVICE)
        v = self.s.verify(c['code'], 'al-store', DEVICE)
        self.assertTrue(v['valid'])
        self.assertEqual(v['state'], 'active')
        self.assertEqual(v['issued_here']['customer'], 'Al-Amal shop')
        self.assertEqual(self.s.verify(c['code'], 'al-store', codes.device_code('other'))['reason'], 'other_device')
        with self.assertRaises(Exception):
            self.s.db.execute("UPDATE codes SET last_day = '2099-01-01'")

    def test_the_three_kinds_a_shop_buys(self):
        """Trial 14 days, monthly subscription (30 days + 3 grace), perpetual (device-bound, never expires)."""
        self.s.create_key(PASS)
        trial = self.s.issue('al-store', 'trial', DEVICE, 'Shop')
        self.assertEqual(trial['last_day'], (date.today() + timedelta(days=13)).isoformat())
        monthly = self.s.issue('al-store', 'standard', DEVICE, 'Shop', days=30, grace_days=3)
        self.assertEqual((monthly['last_day'], monthly['grace_days']), ((date.today() + timedelta(days=29)).isoformat(), 3))
        with self.assertRaises(StudioError):
            self.s.issue('al-store', 'perpetual', None)  # a perpetual code is always tied to one PC
        forever = self.s.issue('al-store', 'perpetual', DEVICE, 'Shop', grace_days=9)
        self.assertEqual((forever['last_day'], forever['days_left'], forever['status'], forever['grace_days']),
                         ('perpetual', None, 'active', 0))
        v = self.s.verify(forever['code'], 'al-store', DEVICE)
        self.assertEqual((v['state'], v['terms']['edition'], v['terms']['last_day']), ('active', 'perpetual', None))
        self.assertEqual(len(self.s.list_codes()), 3)
        for edition in ('perpetual', 'trial'):  # a request that could never be approved is refused when it is made
            with self.assertRaises(StudioError) as e:
                self.s.request('al-store', edition, None, 'Shop')
            self.assertEqual(e.exception.key, 'device.required')
        self.assertEqual(self.s.requests(), [])
        self.assertTrue(self.s.request('al-store', 'perpetual', DEVICE, 'Shop'))

    def test_wrong_passphrases_are_throttled(self):
        self.s.create_key(PASS)
        fresh = Studio(self.dir)
        import licence_studio.service as svc
        original, svc.time.sleep = svc.time.sleep, lambda _s: None
        try:
            for _ in range(5):
                with self.assertRaises(StudioError):
                    fresh.unlock('not the passphrase!')
            with self.assertRaises(StudioError) as e:
                fresh.unlock(PASS)  # even the right one waits: guessing is slowed down
            self.assertEqual(e.exception.status, 429)
        finally:
            svc.time.sleep = original
        with self.assertRaises(StudioError):
            fresh.unlock(None)

    def test_agent_requests_and_limits(self):
        self.s.create_key(PASS)
        out = self.s.agent_issue_trial('al-store', DEVICE, 'Shop')
        self.assertEqual(out['status'], 'requested')  # off by default: the owner decides
        rid = out['request']['id']
        self.s.decide(rid, True)
        self.assertEqual(self.s.requests('approved')[0]['id'], rid)
        self.s.set_setting('agent_may_issue_trials', True)
        self.s.set_setting('agent_daily_limit', 1)
        other, third = codes.device_code('pc-2', 'i-2'), codes.device_code('pc-3', 'i-3')
        with self.assertRaises(StudioError):
            self.s.agent_issue_trial('al-store', other, 'Shop', days=30)
        with self.assertRaises(StudioError) as e:  # DEVICE already had a code: another trial is the owner's decision
            self.s.agent_issue_trial('al-store', DEVICE, 'Shop')
        self.assertEqual(e.exception.status, 409)
        self.assertEqual(self.s.agent_issue_trial('al-store', other, 'Shop')['status'], 'issued')
        with self.assertRaises(StudioError) as e:
            self.s.agent_issue_trial('al-store', third, 'Shop')
        self.assertEqual(e.exception.status, 429)
        req = self.s.request('al-store', 'pro', DEVICE, 'Shop', days=365)
        self.assertEqual(req['status'], 'pending')  # paid editions only by request
        actors = {r['actor'] for r in self.s.audit_log()}
        self.assertEqual(actors, {'owner', 'agent'})


    def _two_windows_at_once(self, jobs):
        """Each job is a call on its own Studio window (same folder). Both are past their first look and have signed when either starts to write."""
        gate = threading.Barrier(len(jobs))
        real = codes.issue_code

        def slow(*a, **k):
            out = real(*a, **k)
            gate.wait(10)
            return out
        got, bad = [], []

        def run(job):
            try:
                got.append(job())
            except StudioError as e:
                bad.append(e.status)
        codes.issue_code = slow
        try:
            threads = [threading.Thread(target=run, args=(j,)) for j in jobs]
            [t.start() for t in threads]
            [t.join(30) for t in threads]
        finally:
            codes.issue_code = real
        return got, bad

    @unittest.skipUnless(hasattr(__import__('time'), 'tzset'), 'changing the time zone of the process needs tzset (not on Windows)')
    def test_the_agents_daily_limit_counts_the_day_the_code_is_stamped_with(self):
        """Review of PR #42: codes are stamped with the UTC day but the limit looked for the PC's local day, so on a PC whose date differs from
        UTC's (most of every day somewhere) the codes made today were never counted and the limit never held."""
        import time
        from datetime import datetime, timezone
        utc_day = lambda: datetime.now(timezone.utc).date().isoformat()  # noqa: E731
        self.s.create_key(PASS)
        self.s.set_setting('agent_may_issue_trials', True)
        self.s.set_setting('agent_daily_limit', 1)
        before = os.environ.get('TZ')
        d1, d2 = codes.device_code('pc-2', 'i-2'), codes.device_code('pc-3', 'i-3')
        try:
            for zone in ('Pacific/Kiritimati', 'Etc/GMT+12'):          # UTC+14 and UTC-12: one of them is on another date than UTC right now
                os.environ['TZ'] = zone
                time.tzset()
                if date.today().isoformat() != utc_day():
                    break
            self.assertNotEqual(date.today().isoformat(), utc_day())
            self.assertEqual(self.s.agent_issue_trial('al-store', d1, 'Shop')['status'], 'issued')
            with self.assertRaises(StudioError) as e:
                self.s.agent_issue_trial('al-store', d2, 'Shop')
            self.assertEqual(e.exception.status, 429)
        finally:
            if before is None:
                os.environ.pop('TZ', None)
            else:
                os.environ['TZ'] = before
            time.tzset()

    def test_the_automatic_trial_cap_holds_when_requests_arrive_together(self):
        """Review of PR #42: the owner's daily cap for automatic trials was a look followed by a write, like the agent's was."""
        self.s.create_key(PASS)
        self.s.keep_unlocked(1)
        other = Studio(self.dir)
        other.unlock(PASS)
        other.keep_unlocked(1)
        d1, d2 = codes.device_code('pc-2', 'i-2'), codes.device_code('pc-3', 'i-3')
        try:
            got, bad = self._two_windows_at_once([lambda: self.s.issue('al-store', 'trial', d1, 'Shop', actor='auto-trial', daily_cap=1)['serial'],
                                                  lambda: other.issue('al-store', 'trial', d2, 'Shop', actor='auto-trial', daily_cap=1)['serial']])
        finally:
            other.db.close()
        self.assertEqual((len(got), bad), (1, [429]))
        self.assertEqual(self.s.one("SELECT COUNT(*) AS n FROM codes WHERE issued_by = 'auto-trial'")['n'], 1)

    def test_two_agent_requests_for_one_device_at_once_make_one_trial(self):
        """Review of PR #26: «one trial per device» was a look followed by a write, so two requests arriving together (a double click, two windows)
        both passed the look and both trials were signed."""
        self.s.create_key(PASS)
        self.s.set_setting('agent_may_issue_trials', True)
        other = Studio(self.dir)
        other.unlock(PASS)
        try:
            got, bad = self._two_windows_at_once([lambda: self.s.agent_issue_trial('al-store', DEVICE, 'Shop'),
                                                  lambda: other.agent_issue_trial('al-store', DEVICE, 'Shop')])
        finally:
            other.db.close()
        self.assertEqual((len(got), bad), (1, [409]))
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes WHERE device = ?', DEVICE)['n'], 1)

    def test_the_agents_daily_limit_holds_when_requests_arrive_together(self):
        self.s.create_key(PASS)
        self.s.set_setting('agent_may_issue_trials', True)
        self.s.set_setting('agent_daily_limit', 1)
        other = Studio(self.dir)
        other.unlock(PASS)
        d1, d2 = codes.device_code('pc-2', 'i-2'), codes.device_code('pc-3', 'i-3')
        try:
            got, bad = self._two_windows_at_once([lambda: self.s.agent_issue_trial('al-store', d1, 'Shop'),
                                                  lambda: other.agent_issue_trial('al-store', d2, 'Shop')])
        finally:
            other.db.close()
        self.assertEqual((len(got), bad), (1, [429]))
        self.assertEqual(self.s.one("SELECT COUNT(*) AS n FROM codes WHERE issued_by = 'agent'")['n'], 1)


class WebAndMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.studio = Studio(cls.dir)
        import socket
        s = socket.socket(); s.bind(('127.0.0.1', 0)); cls.port = s.getsockname()[1]; s.close()
        cls.httpd, cls.app = serve(cls.studio, cls.port)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def call(self, method, path, body=None, cookie='', headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=20)
        h = {'Host': f'127.0.0.1:{self.port}', 'Content-Type': 'application/json', **({'Cookie': cookie} if cookie else {}), **(headers or {})}
        c.request(method, path, json.dumps(body).encode() if body is not None else None, h)
        r = c.getresponse()
        raw = r.read()
        set_cookie = r.getheader('Set-Cookie') or ''
        c.close()
        return r.status, (json.loads(raw) if raw[:1] in (b'{', b'[') else raw), set_cookie.split(';', 1)[0]

    def test_1_owner_flow_guards_agent_and_mcp(self):
        st, d, _ = self.call('GET', '/api/codes')
        self.assertEqual(st, 401)
        st, d, _ = self.call('GET', '/api/status', headers={'Host': 'evil.com'})
        self.assertEqual(st, 421)
        st, d, cookie = self.call('POST', '/api/key/create', {'passphrase': PASS})
        if st == 409:  # an earlier test already made the key: unlock it
            st, d, cookie = self.call('POST', '/api/unlock', {'passphrase': PASS})
        self.assertEqual(st, 200)
        st, d, _ = self.call('POST', '/api/issue', {'product': 'al-store', 'device': DEVICE}, cookie, {'Origin': 'http://evil.com'})
        self.assertEqual(st, 403)
        st, c, _ = self.call('POST', '/api/issue', {'product': 'al-store', 'edition': 'trial', 'device': DEVICE, 'customer': 'Shop'}, cookie)
        self.assertEqual(st, 200, c)
        st, rows, _ = self.call('GET', '/api/codes', cookie=cookie)
        self.assertEqual(rows[0]['serial'], c['serial'])
        st, d, _ = self.call('POST', '/api/token/new', {'name': 'test agent'}, cookie)
        token = d['token']
        # the agent API: token required, cannot reach owner endpoints
        self.assertEqual(self.call('GET', '/agent/status')[0], 401)
        st, d, _ = self.call('GET', '/agent/status', headers={'Authorization': 'Bearer ' + token})
        self.assertEqual(st, 200)
        self.assertNotIn('home', d)
        self.assertEqual(self.call('GET', '/api/codes', headers={'Authorization': 'Bearer ' + token})[0], 401)
        # the MCP bridge in a real subprocess, speaking JSON-RPC on stdio
        env = {**os.environ, 'LS_URL': f'http://127.0.0.1:{self.port}', 'LS_AGENT_TOKEN': token,
               'PYTHONPATH': os.pathsep.join([str(HERE), str(HERE.parents[1] / 'packages' / 'af-license')])}
        msgs = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': mcp.PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '1'}}},
                {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'verify_code', 'arguments': {'code': c['code'], 'product': 'al-store', 'device': DEVICE}}},
                {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'issue_trial_code', 'arguments': {'product': 'al-store', 'device': DEVICE, 'customer': 'Agent shop'}}},
                {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {'name': 'studio_doctor', 'arguments': {}}},
                {'jsonrpc': '2.0', 'id': 6, 'method': 'tools/call', 'params': {'name': 'nope', 'arguments': {}}}]
        p = subprocess.run([sys.executable, '-m', 'licence_studio', 'mcp'], input='\n'.join(json.dumps(m) for m in msgs) + '\n',
                           capture_output=True, text=True, env=env, timeout=60, cwd=str(HERE))
        out = {r['id']: r for r in map(json.loads, p.stdout.strip().splitlines())}
        self.assertEqual(out[1]['result']['serverInfo']['name'], 'licence-studio')
        self.assertEqual(len(out[2]['result']['tools']), len(mcp.TOOLS))
        verified = out[3]['result']['structuredContent']['result']
        self.assertEqual(verified['state'], 'active')
        issued = out[4]['result']['structuredContent']['result']
        self.assertEqual(issued['status'], 'requested')  # the owner has not allowed direct trials
        self.assertTrue(out[5]['result']['structuredContent']['result']['all_ok'])
        self.assertIn('error', out[6])
        self.assertNotIn(PASS, p.stdout)

    def test_0_bad_requests_get_calm_answers(self):
        st, d, cookie = self.call('POST', '/api/key/create', {'passphrase': PASS})
        self.assertIn(st, (200, 409))
        if st == 409:
            st, d, cookie = self.call('POST', '/api/unlock', {'passphrase': PASS})
        for body in ([], 'text', 5, None, {'product': ['x']}, {'product': 'al-store', 'days': 'many'}, {'product': 'al-store', 'device': 5}):
            for path in ('/api/issue', '/api/verify', '/api/product/save', '/api/policy', '/api/request/decide'):
                st, d, _ = self.call('POST', path, body, cookie)
                self.assertLess(st, 500, (path, body))
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)  # a negative length must not hang the server
        c.request('POST', '/api/issue', b'', {'Host': f'127.0.0.1:{self.port}', 'Content-Length': '-5', 'Cookie': cookie})
        self.assertEqual(c.getresponse().status, 413)
        c.close()
        st, raw, _ = self.call('GET', '/af-ui/../static/studio.js', cookie=cookie)  # no walking out of the shared folder
        self.assertIn(st, (200, 404))

    def test_2_code_from_the_studio_unlocks_al_store(self):
        """The full chain: studio key → code for a shop PC's device code → that shop's Al-Store accepts it, another PC refuses it."""
        store = Path(os.environ.get('AF_STORE_REPO', HERE.parents[2] / 'Store'))
        if not (store / 'server' / 'licence.py').exists():
            self.skipTest('Al-Store checkout not found next to Apps-Factory')
        public = self.studio.public_key().split(':', 1)[1]
        script = (
            'import os,sys,json,tempfile; sys.path.insert(0, "server");'
            'import app, licence;'
            'a = app.build(os.environ["SHOP_HOME"], practice=False);'
            'print(json.dumps({"device": licence.device(a.db)}))')
        env = {**os.environ, 'STORE_LICENCE_KEYS': public, 'STORE_DEVICE_ID': 'pilot-shop-pc', 'SHOP_HOME': tempfile.mkdtemp()}
        got = subprocess.run([sys.executable, "-c", script], cwd=store, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)
        dev = json.loads(got.stdout)["device"]
        c = self.studio.issue('al-store', 'trial', dev, 'Pilot shop')
        check = ('import os,sys,json; sys.path.insert(0, "server"); import app, licence;'
                 'a = app.build(os.environ["SHOP_HOME"], practice=False);'
                 f'print(json.dumps(licence.activate(a.db, {c["code"]!r})))')
        ok = subprocess.run([sys.executable, '-c', check], cwd=store, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(json.loads(ok.stdout)['state'], 'trial', ok.stderr)
        other = subprocess.run([sys.executable, '-c', check], cwd=store, env={**env, 'STORE_DEVICE_ID': 'another-pc'}, capture_output=True, text=True, timeout=60)
        self.assertIn('other_device', other.stderr)
        for edition, days, state in (('standard', 30, 'active'), ('perpetual', None, 'active')):
            c = self.studio.issue('al-store', edition, dev, 'Pilot shop', days=days)
            check = ('import os,sys,json; sys.path.insert(0, "server"); import app, licence;'
                     'a = app.build(os.environ["SHOP_HOME"], practice=False);'
                     f'print(json.dumps(licence.activate(a.db, {c["code"]!r})))')
            ok = subprocess.run([sys.executable, '-c', check], cwd=store, env=env, capture_output=True, text=True, timeout=60)
            got = json.loads(ok.stdout)
            self.assertEqual((got['state'], got['edition'], got['full']), (state, edition, True), ok.stderr)


if __name__ == '__main__':
    unittest.main()
