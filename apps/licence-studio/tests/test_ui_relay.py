"""The owner's page, clicked in a real browser: connect the relay, see a shop's request, switch the policy on, let a trial go out by itself,
and approve a paid request only after ticking that the payment arrived. Skipped without Playwright, Chromium or Node 22.13+."""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'packages' / 'af-license'))
sys.path.insert(0, str(HERE / 'tests'))
from test_relay_chain import ADMIN, PASS, SERVE, WEBHOOK, TelegramStub, machine_tag, node_ok  # noqa: E402
from af_license import codes  # noqa: E402
from licence_studio.server import serve  # noqa: E402
from licence_studio.service import Studio  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None
CHROMIUM = os.environ.get('AF_CHROMIUM') or ('/opt/pw-browsers/chromium' if os.path.exists('/opt/pw-browsers/chromium') else None)


@unittest.skipUnless(sync_playwright and node_ok(), 'Playwright and Node 22.13+ are needed')
class StudioPage(unittest.TestCase):
    def setUp(self):
        from http.server import HTTPServer
        TelegramStub.messages = []
        self.tg = HTTPServer(('127.0.0.1', 0), TelegramStub)
        threading.Thread(target=self.tg.serve_forever, daemon=True).start()
        os.environ.update(TELEGRAM_BOT_TOKEN='999:UI-BOT', TELEGRAM_OWNER_CHAT_ID='7', LS_TELEGRAM_API=f'http://127.0.0.1:{self.tg.server_port}', LS_RELAY_EVERY='0')
        self.relay = subprocess.Popen([shutil.which('node'), '--experimental-sqlite', str(SERVE)], stdout=subprocess.PIPE, text=True, cwd=str(SERVE.parent))
        self.relay_base = f"http://127.0.0.1:{json.loads(self.relay.stdout.readline())['port']}"
        self.dir = tempfile.mkdtemp()
        self.studio = Studio(self.dir)
        self.studio.create_key(PASS)
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        self.port = s.getsockname()[1]
        s.close()
        self.httpd, _ = serve(self.studio, self.port)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.public = self.studio.public_key().split(':', 1)[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.relay.terminate()
        self.relay.wait(10)
        self.relay.stdout.close()
        self.tg.shutdown()
        self.tg.server_close()
        for k in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_OWNER_CHAT_ID', 'LS_TELEGRAM_API', 'LS_RELAY_EVERY'):
            os.environ.pop(k, None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def until(self, pg, expression, seconds=10):
        """Poll an expression until it is truthy (the page's security policy forbids wait_for_function's string)."""
        import time
        end = time.time() + seconds
        while time.time() < end:
            if pg.evaluate(expression):
                return True
            pg.wait_for_timeout(100)
        self.fail('timed out waiting for ' + expression)

    def shop(self, method, path, body=None, token=None):
        req = urllib.request.Request(self.relay_base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + token} if token else {})})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    def ask(self, pc, kind='trial', **extra):
        device = codes.device_code(pc, 'i')
        body = {'product': 'al-store', 'kind': kind, 'device': device, 'nonce': str(uuid.uuid4()), 'shop': 'Pilot shop',
                **({'machine': machine_tag(pc)} if kind == 'trial' else {}), **extra}
        return device, self.shop('POST', '/licence/request', body)

    def test_the_owner_clicks_through_the_relay_policy_and_payment_gate(self):
        errors = []
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=CHROMIUM) if CHROMIUM else p.chromium.launch()
            pg = b.new_page(viewport={'width': 1366, 'height': 860})
            pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'status of 400' not in m.text else None)  # the refused approval is a 400 on purpose
            pg.on('pageerror', lambda e: errors.append(str(e)))
            pg.goto(f'http://127.0.0.1:{self.port}/')
            pg.wait_for_selector('#pp')
            pg.fill('#pp', PASS)
            pg.click('button.volt')
            pg.wait_for_selector('.shell')
            pg.goto(f'http://127.0.0.1:{self.port}/#/requests')
            pg.wait_for_selector('#rf')
            self.assertIn('لسه مش متظبط', pg.inner_text('#relay-box'))
            self.assertTrue(pg.is_disabled('#pull'))
            # connect the relay: the token is typed once and never shown again
            pg.fill('#ru', self.relay_base)
            pg.fill('#rt', ADMIN)
            pg.click('#rf button.primary')
            pg.wait_for_selector('#pull:not([disabled])')
            self.assertNotIn(ADMIN, pg.content())
            self.assertNotIn(ADMIN, pg.input_value('#rt'))
            # a shop asks for a trial and a monthly subscription
            trial_device, trial = self.ask('pc-ui-1')
            paid_device, paid = self.ask('pc-ui-2', kind='monthly', ref='InstaPay 77')
            pg.click('#pull')
            pg.wait_for_selector('[data-yes]')
            text = pg.inner_text('#page')
            self.assertIn('تجربة', text)
            self.assertIn('اشتراك شهري', text)
            self.assertIn('السياسة هتصدّره لوحدها', text)  # the policy's verdict is a hint: nothing was issued while it is off
            self.assertEqual(self.shop('GET', '/licence/status?id=' + trial['id'], token=trial['poll_token'])['status'], 'pending')
            # the owner switches the policy on and keeps the key open; the next round issues the trial by itself
            pg.check('#au')
            self.assertEqual(pg.input_value('#ad'), '14', 'the automatic trial cap shows 14 until the owner raises it')
            pg.fill('#ad', '99')
            pg.press('#ad', 'Tab')
            self.until(pg, "document.querySelector('#ad').value === '60'")   # the program holds it to the longest a product may be set to
            pg.fill('#ad', '14')
            pg.press('#ad', 'Tab')
            self.until(pg, "document.querySelector('#ad').value === '14'")
            pg.fill('#kh', '2')
            pg.click('#keep')
            self.until(pg, "document.querySelector('#relay-box').innerText.includes('مفتوح لحد')")
            pg.click('#pull')
            self.until(pg, "document.body.innerText.includes('اتوافق')")  # the list shows decided requests too, not only the waiting ones
            got = self.shop('GET', '/licence/status?id=' + trial['id'], token=trial['poll_token'])
            self.assertEqual(got['status'], 'issued')
            self.assertTrue(codes.read_code(got['code'], [self.public], 'al-store', trial_device).valid)
            # the paid request waits: approving without the tick is refused with a clear message, and nothing is signed
            self.assertEqual(self.shop('GET', '/licence/status?id=' + paid['id'], token=paid['poll_token'])['status'], 'pending')
            pg.click('[data-yes]')
            pg.wait_for_selector('.toast.bad')
            self.assertIn('الدفع وصل', pg.inner_text('.toasts'))
            self.assertEqual(self.shop('GET', '/licence/status?id=' + paid['id'], token=paid['poll_token'])['status'], 'pending')
            pg.check('[data-paid]')
            pg.fill('[data-ref]', 'InstaPay 77 / 350')
            pg.click('[data-yes]')
            self.until(pg, "(document.body.innerText.match(/اتوافق/g) || []).length >= 2")  # both are approved and the list is drawn again
            got = self.shop('GET', '/licence/status?id=' + paid['id'], token=paid['poll_token'])
            self.assertEqual(got['status'], 'issued')
            read = codes.read_code(got['code'], [self.public], 'al-store', paid_device)
            self.assertEqual((read.valid, read.terms['edition'], read.terms['grace_days']), (True, 'standard', 3))
            pg.screenshot(path=os.environ.get('AF_SHOT', os.path.join(self.dir, 'studio-requests.png')))
            b.close()
        self.assertEqual(errors, [])
        self.assertTrue(any('طلب' in m['text'] and 'تجربة' in m['text'] or '✅' in m['text'] for m in TelegramStub.messages))

    def test_a_button_pressed_on_the_phone_shows_on_the_page_and_the_trial_goes_out_without_the_policy(self):
        errors = []
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=CHROMIUM) if CHROMIUM else p.chromium.launch()
            pg = b.new_page(viewport={'width': 1366, 'height': 860})
            pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
            pg.on('pageerror', lambda e: errors.append(str(e)))
            pg.goto(f'http://127.0.0.1:{self.port}/')
            pg.wait_for_selector('#pp')
            pg.fill('#pp', PASS)
            pg.click('button.volt')
            pg.wait_for_selector('.shell')
            self.studio.relay.save(self.relay_base, ADMIN)
            device, trial = self.ask('pc-ui-3')
            _, refused = self.ask('pc-ui-4')

            def press(data, **kw):
                req = urllib.request.Request(self.relay_base + '/telegram', method='POST', headers={'Content-Type': 'application/json', 'X-Telegram-Bot-Api-Secret-Token': WEBHOOK},
                                             data=json.dumps({'update_id': 1, 'callback_query': {'id': 'c', 'from': {'id': 7}, 'message': {'message_id': 9, 'chat': {'id': 7}}, 'data': data}}).encode())
                urllib.request.urlopen(req, timeout=10).read()
            # the studio already holds both as waiting; then the owner agrees to one on the phone and refuses the other. The policy is OFF throughout.
            self.assertFalse(self.studio.policy()['auto_trials'])
            self.assertEqual(self.studio.auto.cycle()['pulled'], 2)
            press('no:' + refused['id'])
            press('ok:' + trial['id'])
            pg.goto(f'http://127.0.0.1:{self.port}/#/requests')
            pg.wait_for_selector('#rf')
            pg.click('#pull')
            self.until(pg, "document.body.innerText.includes('القرار من تليجرام')")
            text = pg.inner_text('#page')
            self.assertEqual(text.count('القرار من تليجرام'), 2, 'the approved trial and the refused one both say the decision came from the phone')
            got = self.shop('GET', '/licence/status?id=' + trial['id'], token=trial['poll_token'])
            self.assertEqual(got['status'], 'issued')
            self.assertTrue(codes.read_code(got['code'], [self.public], 'al-store', device).valid)
            self.assertEqual(self.shop('GET', '/licence/status?id=' + refused['id'], token=refused['poll_token'])['status'], 'refused')
            b.close()
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
