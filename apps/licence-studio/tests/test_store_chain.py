"""The whole chain with the real parts of all three programs: the shop's program (Al-Store, a real process with a real database), the relay
Worker (Node, real code) and the Licence Studio (real key, real policy). The shop presses nothing but the request; the owner's program
decides by policy; the shop checks the code with the public key and switches itself on.

Skipped unless an Al-Store checkout with `server/trial.py` sits next to this repository (or AF_STORE_REPO points at one) and Node 22.13+ exists."""
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'packages' / 'af-license'))
sys.path.insert(0, str(HERE / 'tests'))
from test_relay_chain import ADMIN, PASS, SERVE, node_ok  # noqa: E402
from licence_studio.service import Studio  # noqa: E402

STORE = Path(os.environ.get('AF_STORE_REPO', ROOT.parent / 'Store'))


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


@unittest.skipUnless(node_ok() and (STORE / 'server' / 'trial.py').exists(), 'needs Node 22.13+ and an Al-Store checkout with server/trial.py')
class StoreChain(unittest.TestCase):
    def setUp(self):
        self.relay = subprocess.Popen([shutil.which('node'), '--experimental-sqlite', str(SERVE)], stdout=subprocess.PIPE, text=True, cwd=str(SERVE.parent))
        relay_base = f"http://127.0.0.1:{json.loads(self.relay.stdout.readline())['port']}"
        os.environ.pop('TELEGRAM_BOT_TOKEN', None)
        self.dir = tempfile.mkdtemp()
        self.studio = Studio(self.dir)
        self.studio.create_key(PASS)
        self.studio.relay.save(relay_base, ADMIN)
        self.studio.set_setting('auto_trials', True)
        self.studio.keep_unlocked(1)
        public = self.studio.public_key().split(':', 1)[1]
        self.env = {**os.environ, 'STORE_LICENCE_KEYS': public, 'STORE_LICENCE_RELAY': relay_base, 'STORE_DEVICE_ID': 'chain-test-pc', 'PYTHONUTF8': '1'}
        self.shops = []
        self.start_shop()

    def start_shop(self):
        """A shop program with its own database (a new install) on the same PC identity."""
        self.port = free_port()
        proc = subprocess.Popen([sys.executable, str(STORE / 'server' / 'app.py'), '--port', str(self.port), '--host', '127.0.0.1', '--no-browser'],
                                env={**self.env, 'STORE_HOME': tempfile.mkdtemp()}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(STORE))
        self.shops.append(proc)
        for _ in range(100):
            try:
                socket.create_connection(('127.0.0.1', self.port), timeout=0.5).close()
                break
            except OSError:
                time.sleep(0.2)
        self.cookie = ''

    def tearDown(self):
        for p in (*self.shops, self.relay):
            p.terminate()
            p.wait(15)
        self.relay.stdout.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def call(self, method, path, body=None):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=20)
        headers = {'Host': f'127.0.0.1:{self.port}', 'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{self.port}', **({'Cookie': self.cookie} if self.cookie else {})}
        c.request(method, path, json.dumps(body).encode() if body is not None else None, headers)
        r = c.getresponse()
        raw = r.read()
        cookie = r.getheader('Set-Cookie')
        if cookie:
            self.cookie = cookie.split(';', 1)[0]
        c.close()
        return r.status, json.loads(raw) if raw[:1] in (b'{', b'[') else raw

    def test_shop_asks_studio_decides_shop_switches_itself_on(self):
        st, d = self.call('POST', '/api/setup', {'username': 'owner1', 'full_name': 'Owner', 'password': 'Owner Pass 1', 'shop_name': 'Chain shop'})
        self.assertEqual(st, 200, d)
        self.assertEqual(self.call('GET', '/api/licence')[1]['state'], 'none')
        self.assertEqual(self.call('POST', '/api/customer/save', {'name': 'x'})[0], 402, 'locked: no code yet')
        st, d = self.call('POST', '/api/licence/request', {'kind': 'trial'})
        self.assertEqual((st, d['status']), (200, 'waiting'), d)
        out = self.studio.auto.cycle()  # the owner's trusted PC pulls, applies the policy, signs, sends the code back
        self.assertEqual((out['pulled'], out['issued'], out['delivered']), (1, 1, 1), out)
        st, d = self.call('POST', '/api/licence/request/retry')  # the shop's own loop does this every 20 seconds
        self.assertEqual(d['status'], 'activated', d)
        lic = self.call('GET', '/api/licence')[1]
        self.assertEqual((lic['state'], lic['edition'], lic['full'], lic['days_left']), ('trial', 'trial', True, 14))
        self.assertEqual(self.call('POST', '/api/customer/save', {'name': 'x'})[0], 200, 'selling and changes are open')
        self.assertEqual(self.call('POST', '/api/licence/request', {'kind': 'trial'})[1]['key'], 'err.trialHave', 'a working licence does not ask for a trial')
        row = self.studio.one('SELECT * FROM trial_ledger')
        self.assertEqual(len(row['machine']), 64)
        self.assertNotIn('chain-test-pc', json.dumps(self.studio.requests(status='')), "the PC's own identity never reaches the owner")
        # a reinstall: a new database, so a new device code, on the same PC. The company recognises the PC and refuses a second trial.
        old_device = lic['device']
        self.start_shop()
        self.call('POST', '/api/setup', {'username': 'owner1', 'full_name': 'Owner', 'password': 'Owner Pass 1', 'shop_name': 'Chain shop again'})
        new_device = self.call('GET', '/api/licence')[1]['device']
        self.assertNotEqual(old_device, new_device)
        st, d = self.call('POST', '/api/licence/request', {'kind': 'trial'})
        self.assertEqual((d['status'], d['reason']), ('refused', 'already_used'), 'one trial per PC, even after a reinstall')
        self.assertEqual(self.studio.auto.cycle()['pulled'], 0, 'and the owner is not bothered')
        self.assertEqual(self.call('GET', '/api/licence')[1]['state'], 'none')

if __name__ == '__main__':
    unittest.main()
