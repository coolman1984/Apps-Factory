"""af-guide in a real browser (HELP-08, HELP-10, HELP-12): the demo shop under a strict CSP, every role course walked
by testing/walk_guides.py, progress kept on the server per person, resume after reload, language switch, per-page
"?" and error -> problem links. Skipped when Playwright is not installed (CI installs it).
CHROME_PATH=/usr/bin/google-chrome uses an installed Chrome instead of Playwright's Chromium."""
import json
import os
import sys
import unittest
import urllib.request
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PKG), str(PKG / 'demo'), str(PKG / 'testing')]
try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

# a missing value printed as text, also a run of them («nullnull»): a \b boundary would miss that
STRAY = r'(?<![A-Za-z])(?:null|undefined|NaN)+(?![A-Za-z])|\[object '
CAT = json.loads((PKG / 'examples' / 'shop' / 'catalogue.json').read_text(encoding='utf-8'))


@unittest.skipIf(sync_playwright is None, 'playwright is not installed')
class Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        from walk_guides import walk
        cls.walk = staticmethod(walk)
        cls.srv = server.serve(0)
        cls.url = f'http://127.0.0.1:{cls.srv.server_address[1]}/'
        cls.pw = sync_playwright().start()
        kw = {'executable_path': os.environ['CHROME_PATH']} if os.environ.get('CHROME_PATH') else {}
        cls.browser = cls.pw.chromium.launch(**kw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.srv.shutdown()

    def page(self, user, role='cashier'):
        ctx = self.browser.new_context(viewport={'width': 1280, 'height': 800})
        ctx.add_cookies([{'name': 'demo_user', 'value': user, 'url': self.url},
                         {'name': 'demo_role', 'value': role, 'url': self.url}])
        page = ctx.new_page()
        page.problems = []
        page.on('console', lambda m: m.type == 'error' and page.problems.append(m.text))
        page.on('pageerror', lambda e: page.problems.append(str(e)))
        page.goto(self.url)
        page.wait_for_function('() => window.__afguide && document.querySelector(".afg-fab")')
        page.evaluate('() => window.__afguide.ready')
        self.addCleanup(ctx.close)
        return page

    def state(self, page):
        return page.evaluate('() => fetch("/api/guide/state").then(r => r.json())')

    def test_every_course_walks_and_is_saved_on_the_server(self):
        for user, role in (('walker-c', 'cashier'), ('walker-o', 'owner')):
            with self.subTest(role=role):
                page = self.page(user, role)
                path = next(r['path'] for r in CAT['roles'] if r['id'] == role)
                self.assertEqual(self.walk(page, CAT, only=path), [])
                st = self.state(page)
                self.assertEqual(set(st['progress']['done']), set(path))
                self.assertEqual(st['course']['done'], len(path))
                self.assertEqual(page.text_content('.afg-badge'), f'{len(path)}/{len(path)}')
                self.assertEqual(page.problems, [])
                kinds = [e['type'] for e in page.evaluate('() => window.__events')]
                self.assertIn('guide.start', kinds)
                self.assertIn('guide.done', kinds)

    def test_a_role_without_a_course_shows_no_badge(self):
        """Regression: the button read «الدليلnull» on Store's sign-in page (replaceChildren printed the missing badge)."""
        page = self.page('nobody', role='guest')
        self.assertIsNone(page.query_selector('.afg-badge'))
        self.assertNotIn('null', page.text_content('.afg-fab'))
        self.assertEqual(page.problems, [])

    def test_the_coach_and_the_panel_never_print_a_missing_value(self):
        """Regression: every coach step showed «nullnull» (replaceChildren printed the absent paragraphs); the walker now fails on it."""
        page = self.page('talker', role='cashier')
        path = next(r['path'] for r in CAT['roles'] if r['id'] == 'cashier')
        page.click('.afg-fab')
        self.assertNotRegex(page.inner_text('.afg-panel'), STRAY)
        page.keyboard.press('Escape')
        self.walk(page, CAT, only=path[:1])  # the first lesson, step by step
        page.evaluate('() => window.__afguide.start(%s)' % json.dumps(path[0]))
        page.wait_for_selector('[data-afg="coach"]:not([hidden])')
        self.assertNotRegex(page.inner_text('[data-afg="coach"]'), STRAY)
        self.assertEqual(page.problems, [])

    def test_walker_needs_no_eval_under_a_strict_csp(self):
        """Regression: walk_guides used wait_for_function, whose polling runs eval in the page; Store's policy refuses it."""
        page = self.page('csp-walker')
        csp = page.evaluate('() => fetch("/").then(r => r.headers.get("content-security-policy"))')
        self.assertNotIn('unsafe-eval', csp)
        self.assertIn("base-uri 'none'", csp)

        def refuse(*a, **k):
            raise AssertionError('the walker must not use wait_for_function')
        page.wait_for_function = refuse
        self.assertEqual(self.walk(page, CAT, only=['open-shift'], handle='__afguide'), [])
        self.assertEqual(page.problems, [])

    def test_progress_follows_the_person_not_the_browser(self):
        page = self.page('roaming')
        page.evaluate('() => window.__afguide.start("open-shift")')
        page.click('[data-afg="there"]')
        page.wait_for_selector('[data-afg="coach"] .afg-bar[aria-valuenow="2"]')
        other = self.page('roaming')   # a new browser context: no localStorage, same person
        other.wait_for_selector('[data-afg="resume"]')
        other.click('[data-afg="resume"]')
        other.wait_for_selector('[data-afg="coach"] .afg-bar[aria-valuenow="2"]')
        self.assertIn('افتح الوردية', other.text_content('[data-afg="say"]'))
        stranger = self.page('someone-else')
        self.assertEqual(stranger.locator('[data-afg="resume"]').count(), 0)

    def test_language_switch_is_per_guide_and_saved(self):
        page = self.page('bilingual')
        page.click('.afg-fab')
        self.assertEqual(page.get_attribute('[data-afg="panel"]', 'dir'), 'rtl')
        page.click('[data-afg="lang"]')
        self.assertEqual(page.get_attribute('[data-afg="panel"]', 'dir'), 'ltr')
        self.assertIn('Your path', page.text_content('[data-afg="panel"]').replace('Cashier path', 'Your path'))
        self.assertEqual(self.state(page)['progress']['lang'], 'en')
        page.evaluate('() => window.__afguide.start("open-shift")')
        self.assertEqual(page.get_attribute('[data-afg="coach"]', 'dir'), 'ltr')
        say = page.text_content('[data-afg="say"]')
        self.assertIn('Open the', say)
        self.assertIn('«الخزنة والوردية»', say, 'button names stay as the screen shows them (UI language)')
        self.assertEqual(page.get_attribute('html', 'dir'), 'rtl', 'the app itself does not change language')

    def test_page_help_and_error_links(self):
        page = self.page('helper')
        page.goto(self.url + '#shift')
        page.click('[data-afg="help"]')
        panel = page.text_content('[data-afg="panel"]')
        self.assertIn('افتح ورديتك', panel)
        self.assertIn('المبلغ في الدرج لا يساوي', panel)
        page.keyboard.press('Escape')
        self.assertTrue(page.is_hidden('[data-afg="panel"]'))
        page.goto(self.url + '#home')
        page.click('#sell-without-shift')
        page.click('[data-afg="explain"]')
        self.assertTrue(page.locator('[data-problem-id="no-shift"][open]').is_visible())
        self.assertIn({'type': 'problem.open', 'data': {'problem': 'no-shift', 'error': 'sale.no_shift'}},
                      page.evaluate('() => window.__events'))
        page.click('[data-afg="report"]')
        self.assertEqual(page.evaluate('() => window.__report.page'), 'home')
        self.assertEqual(page.problems, [])

    def test_bad_progress_update_is_refused(self):
        req = urllib.request.Request(self.url + 'api/guide/progress', data=b'{"update": {"op": "fly"}}', method='POST',
                                     headers={'Content-Type': 'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        self.assertEqual(e.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
