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

    def test_three_sales_types_and_existing_codes(self):
        self.s.create_key(PASS)
        trial = self.s.issue('al-store', 'trial', DEVICE, 'Store')
        self.assertEqual(trial['days_left'], 14)
        with self.assertRaises(StudioError):
            self.s.issue('al-store', 'trial', DEVICE, 'Store')
        monthly = self.s.issue('al-store', 'monthly', DEVICE, 'Store')
        self.assertEqual(monthly['days_left'], 30)
        self.assertEqual(monthly['status'], 'active')
        with self.assertRaises(StudioError):
            self.s.issue('al-store', 'monthly', DEVICE, 'Store', days=31)
        lifetime = self.s.issue('al-store', 'lifetime', DEVICE, 'Store')
        self.assertTrue(lifetime['permanent'])
        self.assertIsNone(lifetime['last_day'])
        self.assertIsNone(lifetime['days_left'])
        self.assertFalse(lifetime['expiring_soon'])
        check = self.s.verify(lifetime['code'], 'al-store', DEVICE)
        self.assertTrue(check['valid'])
        self.assertTrue(check['terms']['permanent'])
        self.assertEqual(check['state'], 'active')
        with self.assertRaises(StudioError):
            self.s.issue('al-store', 'lifetime', None, 'Store')
        self.assertFalse(any(c['edition'] == 'lifetime' for c in self.s.list_codes(status='expiring')))
        self.assertEqual(self.s.request('al-store', 'lifetime', DEVICE, 'Another shop')['status'], 'pending')
        self.assertEqual(self.s.request('al-store', 'monthly', DEVICE, 'Another shop')['days'], 30)

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


if __name__ == '__main__':
    unittest.main()
