"""af-consent: two levels, append-only history, exact text ids, the vendor name rule, purge callback, fresh copies."""
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
import af_consent as C  # noqa: E402

AR, EN = 'consent.help.remote.ar.v1', 'consent.help.remote.en.v1'


def fresh(on_change=None):
    db = sqlite3.connect(':memory:')
    db.executescript(C.SQL)
    return C.Consent(db, on_change=on_change)


class Levels(unittest.TestCase):
    def test_nothing_without_installation_consent(self):
        c = fresh()
        c.record('person', 'u1', 'agree', AR, 'ar', by='u1')
        self.assertFalse(c.allowed('u1'), 'person agreed but the installation did not')
        self.assertFalse(c.allowed())
        self.assertFalse(c.needs_prompt('u2'), 'do not ask people before the installation agreed')

    def test_both_levels(self):
        c = fresh()
        c.record('install', None, 'agree', EN, 'en', by='owner')
        self.assertTrue(c.allowed())
        self.assertTrue(c.needs_prompt('u1'))
        self.assertFalse(c.allowed('u1'))
        c.record('person', 'u1', 'agree', AR, 'ar', by='u1')
        self.assertTrue(c.allowed('u1'))
        self.assertFalse(c.needs_prompt('u1'))
        c.record('person', 'u2', 'decline', AR, 'ar', by='u2')
        self.assertFalse(c.allowed('u2'))
        self.assertFalse(c.needs_prompt('u2'), 'a decline is an answer: never nag')
        self.assertEqual(c.current('person', 'u2')['label'], 'لم يوافق')
        self.assertEqual(c.current('person', 'u1')['label'], 'وافق')

    def test_withdraw_is_recorded_and_triggers_purge(self):
        calls = []
        c = fresh(on_change=lambda *a: calls.append(a))
        c.record('install', None, 'agree', AR, 'ar', by='owner')
        c.record('person', 'u1', 'agree', AR, 'ar', by='u1')
        c.record('person', 'u1', 'withdraw', AR, 'ar', by='u1', at='2026-10-09T07:00:00Z')
        self.assertFalse(c.allowed('u1'))
        self.assertEqual(calls, [('person', 'u1', 'withdraw')])
        hist = c.history('person', 'u1')
        self.assertEqual([h['decision'] for h in hist], ['withdraw', 'agree'], 'append-only, newest first')
        self.assertEqual(hist[0]['at'], '2026-10-09T07:00:00Z')
        self.assertEqual(hist[0]['text_id'], AR)
        st = c.status('u1')
        self.assertFalse(st['tracking'])
        self.assertTrue(st['feedback_always_allowed'])

    def test_bad_records_refused(self):
        c = fresh()
        for args in [('person', 'u1', 'maybe', AR, 'ar'), ('team', 'u1', 'agree', AR, 'ar'),
                     ('person', 'u1', 'agree', 'consent.other.v1', 'ar'), ('person', 'u1', 'agree', AR, 'en'),
                     ('person', '', 'agree', AR, 'ar')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                c.record(*args, by='x')


class Prompt(unittest.TestCase):
    def test_vendor_name_rule(self):
        self.assertEqual(C.vendor_name({'vendor_display_name': ' محمد فوزي '}, 'Mohamed Fawzy'), 'محمد فوزي')
        self.assertEqual(C.vendor_name({}, 'Mohamed Fawzy'), 'Mohamed Fawzy')
        self.assertEqual(C.vendor_name({'vendor_display_name': ''}, None), 'coolman1984')
        self.assertEqual(C.vendor_name(None, '  '), 'coolman1984')

    def test_exact_texts(self):
        p = C.prompt('ar', 'Mohamed Fawzy')
        self.assertEqual(p['text'], 'أوافق حتى يستطيع Mohamed Fawzy مساعدتي عن بُعد.')
        self.assertEqual((p['agree'], p['decline'], p['text_id']), ('أوافق', 'لا أوافق', AR))
        self.assertEqual(C.prompt('en', 'X')['text'], 'I agree so that X can help me remotely.')
        self.assertEqual(C.prompt('fr', 'X')['lang'], 'ar')
        for t in C.TEXTS.values():
            self.assertIn('{vendor}', t['text'])
            self.assertEqual(set(t['recorded']), C.DECISIONS)

    def test_no_legal_wording(self):
        src = (PKG / 'af_consent.py').read_text(encoding='utf-8').lower()
        for word in ('law 151', 'gdpr', 'lawyer', 'قانون', 'محامي'):
            self.assertNotIn(word, src)


@unittest.skipUnless(shutil.which('node'), 'node is not installed')
class Js(unittest.TestCase):
    def test_syntax_and_no_html_injection(self):
        self.assertEqual(subprocess.run(['node', '--check', str(PKG / 'af-consent.js')]).returncode, 0)
        src = (PKG / 'af-consent.js').read_text(encoding='utf-8')
        for bad in ('innerHTML', 'insertAdjacentHTML', 'eval('):
            self.assertFalse(bad in src, bad)


class VendoredCopies(unittest.TestCase):
    def test_known_products_hold_a_fresh_copy(self):
        sys.path.insert(0, str(PKG.parents[1] / 'scripts'))
        import vendor_consent as V
        root = PKG.parents[2]
        for name in ('Store', 'Teachers', 'Yousef-Transportation', 'Mr.Ayman-HR'):
            repo = Path(os.environ.get(f'AF_{name.upper().replace("-", "_").replace(".", "_")}_REPO', root / name))
            for src, dest in V.destinations(repo):
                if dest.exists():
                    body = dest.read_bytes().split(b'\n', 2)[2]
                    self.assertEqual(hashlib.sha256(body).hexdigest(), hashlib.sha256(src.read_bytes()).hexdigest(),
                                     f'{dest} is stale: run python scripts/vendor_consent.py <product repo>')


if __name__ == '__main__':
    unittest.main()
