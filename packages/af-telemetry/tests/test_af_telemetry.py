"""af-telemetry: the firm limits hold in code (only ids and counts, never-list, consent, purge), problem reports work
without consent and exactly as previewed, the outbox stays bounded, batches are signed, fresh copies."""
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PKG), str(PKG.parent / 'af-consent')]
import af_consent as C  # noqa: E402
import af_telemetry as T  # noqa: E402

AR = 'consent.help.remote.ar.v1'


class Clock:
    def __init__(self, t=1_791_500_000.0):
        self.t = t

    def __call__(self):
        return self.t


def setup(install=True, people=(), limits=None, clock=None):
    db = sqlite3.connect(':memory:')
    db.executescript(C.SQL)
    d = tempfile.mkdtemp()
    consent = C.Consent(db)
    tel = T.Telemetry(Path(d) / 'telemetry.db', 'ins_demo', 'pc1', 'al-store', '1.2.0', 'practice', 'install-secret',
                      consent, limits=limits, clock=clock or Clock())
    consent.on_change = tel.on_consent_change
    if install:
        consent.record('install', None, 'agree', AR, 'ar', by='owner')
    for u in people:
        consent.record('person', u, 'agree', AR, 'ar', by=u)
    return tel, consent


class FirmLimits(unittest.TestCase):
    def test_only_allowlisted_ids_and_counts(self):
        tel, _ = setup(people=['u1'])
        refused = [
            ('use.page', {'page': 'sell', 'name': 'Ahmed'}),            # never-list field
            ('use.page', {'page': 'sell', 'password': 'x'}),
            ('use.page', {'page': 'sell', 'amount': 150}),
            ('use.page', {'page': 'sell', 'screenshot': 'data'}),
            ('use.page', {'page': 'sell', 'keystrokes': 'abc'}),
            ('use.page', {'page': 'sell', 'extra': 'x'}),               # not allowlisted
            ('use.page', {'page': 'Ahmed Ali'}),                         # not a machine id
            ('use.page', {'page': '01012345678'}),                       # a phone in an id field
            ('use.page', {'page': 'cust-29801011234567'}),               # a national id inside an id
            ('use.page', {'page': 'a@b.com'}),
            ('use.page', {'page': 'sell', 'count': 'many'}),
            ('use.page', {'page': {'nested': 1}}),
            ('err.server', {'code': 'KeyError', 'message': 'customer Ahmed not found'}),
            ('fb.problem', {'text': 'x', 'diagnostics': {'customer_name': 'Ahmed'}}),
            ('fb.problem', {'text': 'x', 'diagnostics': {'version': '01012345678'}}),
            ('fb.problem', {'text': 'x', 'contact': '01012345678'}),
            ('made.up', {}),
        ]
        for etype, data in refused:
            with self.subTest(etype=etype, data=data), self.assertRaises(T.PrivacyError):
                tel.emit(etype, data, user='u1')
        with self.assertRaises(T.PrivacyError):
            tel.emit('use.page', {'page': 'sell'}, user='u1', page='Ahmed Ali')
        self.assertTrue(tel.emit('use.page', {'page': 'sell'}, user='u1'))

    def test_person_is_a_pseudonym(self):
        tel, _ = setup(people=['42'])
        tel.emit('use.page', {'page': 'sell'}, user='42', role='cashier')
        ev = tel.pending()[0]
        self.assertRegex(ev['subject'], r'^p_[0-9a-f]{16}$')
        self.assertNotIn('42', json.dumps(ev['subject']))
        self.assertEqual(ev['subject'], T.pseudonym('install-secret', '42'))
        self.assertNotEqual(ev['subject'], T.pseudonym('other-install', '42'), 'meaningless across installations')
        self.assertEqual(set(ev), {'v', 'id', 'install_id', 'node', 'product', 'version', 'env', 'ts', 'type', 'sev',
                                   'anon', 'subject', 'role', 'page', 'data'})
        self.assertEqual(ev['env'], 'practice')

    def test_taxonomy_cannot_be_extended_into_the_never_list(self):
        tax = json.loads(json.dumps(T.TAXONOMY))
        tax['types']['use.page']['data']['phone'] = {'type': 'id'}
        tax['types']['use.note'] = {'level': 'person', 'prio': 5, 'data': {'t': {'type': 'feedback_text'}}}
        problems = T.check_taxonomy(tax)
        self.assertTrue(any('never-collect' in p for p in problems))
        self.assertTrue(any('free text only in feedback' in p for p in problems))
        with self.assertRaises(T.PrivacyError):
            T.Telemetry(':memory:', 'i', 'n', 'p', '1', 'real', 's', setup()[1], taxonomy=tax)
        self.assertEqual(T.check_taxonomy(T.TAXONOMY), [])

    def test_errors_carry_no_message(self):
        tel, _ = setup()
        try:
            {}['customer Ahmed 01012345678']
        except KeyError as e:
            tel.capture(e, where='sales:checkout')
        ev = tel.pending()[0]
        self.assertEqual(ev['type'], 'err.server')
        self.assertEqual(ev['data']['code'], 'KeyError')
        self.assertNotIn('Ahmed', json.dumps(ev))
        self.assertNotIn('0101', json.dumps(ev))
        self.assertIsNone(ev['subject'])


class ConsentGate(unittest.TestCase):
    def test_no_installation_consent_no_events(self):
        tel, consent = setup(install=False)
        consent.record('person', 'u1', 'agree', AR, 'ar', by='u1')
        self.assertIsNone(tel.emit('hb', {'error_count': 0}))
        self.assertIsNone(tel.emit('use.page', {'page': 'sell'}, user='u1'))
        self.assertEqual(tel.pending(), [])
        self.assertEqual(tel.counters()['dropped.no_install_consent'], 2)

    def test_decline_means_zero_events_for_that_person(self):
        tel, consent = setup(people=['u1'])
        consent.record('person', 'u2', 'decline', AR, 'ar', by='u2')
        tel.emit('use.page', {'page': 'sell'}, user='u1')
        self.assertIsNone(tel.emit('use.page', {'page': 'sell'}, user='u2'))
        self.assertIsNone(tel.emit('guide.done', {'guide': 'open-shift'}, user='u3'), 'never asked = no')
        self.assertIsNone(tel.emit('use.page', {'page': 'sell'}), 'person events need a person')
        self.assertEqual([e['subject'] for e in tel.pending()], [T.pseudonym('install-secret', 'u1')])

    def test_withdraw_deletes_pending_events(self):
        tel, consent = setup(people=['u1', 'u2'])
        tel.emit('use.page', {'page': 'sell'}, user='u1')
        tel.emit('guide.start', {'guide': 'open-shift'}, user='u1')
        tel.emit('use.page', {'page': 'sell'}, user='u2')
        tel.feedback('problem', 'الطابعة لا تطبع', user='u1', page='sell')
        consent.record('person', 'u1', 'withdraw', AR, 'ar', by='u1')
        types = sorted((e['type'], e['subject'] == T.pseudonym('install-secret', 'u1')) for e in tel.pending())
        self.assertEqual(types, [('fb.problem', True), ('use.page', False)], 'only u2 and the report u1 sent remain')
        self.assertIsNone(tel.emit('use.page', {'page': 'sell'}, user='u1'))
        consent.record('install', None, 'withdraw', AR, 'ar', by='owner')
        self.assertEqual([e['type'] for e in tel.pending()], ['fb.problem'])

    def test_installation_events_carry_no_person(self):
        tel, _ = setup(people=['u1'])
        tel.emit('backup.ok', {'size_mb': 12, 'seconds': 3}, user='u1', role='owner')
        ev = tel.pending()[0]
        self.assertIsNone(ev['subject'])
        self.assertIsNone(ev['role'])
        self.assertTrue(ev['anon'])


class Feedback(unittest.TestCase):
    def test_allowed_without_any_consent_and_redacted(self):
        tel, _ = setup(install=False)
        p = tel.preview('problem', 'رقمي 01012345678 وبريدي a@b.com والرقم القومي 29801011234567 كلمة السر 1234',
                        page='sell', contact='whatsapp', diagnostics={'version': '1.2.0', 'error_count': 3})
        text = p['event']['data']['text']
        for leaked in ('01012345678', 'a@b.com', '29801011234567', '1234'):
            self.assertNotIn(leaked, text)
        self.assertIn('[PHONE]', text)
        eid = tel.feedback('problem', 'رقمي 01012345678 وبريدي a@b.com والرقم القومي 29801011234567 كلمة السر 1234',
                           page='sell', contact='whatsapp', diagnostics={'version': '1.2.0', 'error_count': 3},
                           user='u9', confirm=p['digest'])
        ev = tel.pending()[0]
        self.assertEqual(ev['id'], eid)
        self.assertIsNone(ev['subject'], 'no person reference without that person\'s consent')
        self.assertEqual(ev['data'], p['event']['data'], 'sent exactly as previewed')

    def test_changed_after_preview_is_refused(self):
        tel, _ = setup()
        p = tel.preview('idea', 'زر أكبر للدفع', page='sell')
        with self.assertRaises(T.PrivacyError):
            tel.feedback('idea', 'زر أكبر للدفع وأيضًا شيء آخر', page='sell', confirm=p['digest'])
        with self.assertRaises(T.PrivacyError):
            tel.feedback('idea', '   ')
        with self.assertRaises(T.PrivacyError):
            tel.feedback('rant', 'x')

    def test_person_reference_when_they_agreed(self):
        tel, _ = setup(people=['u1'])
        tel.feedback('question', 'كيف أطبع الملصقات؟', user='u1')
        self.assertEqual(tel.pending()[0]['subject'], T.pseudonym('install-secret', 'u1'))


class Outbox(unittest.TestCase):
    def test_hourly_merge(self):
        clock = Clock()
        tel, _ = setup(people=['u1'], clock=clock)
        for _ in range(5):
            tel.emit('use.page', {'page': 'sell'}, user='u1')
        tel.emit('use.page', {'page': 'stock'}, user='u1')
        for _ in range(3):
            tel.emit('err.server', {'code': 'KeyError', 'fingerprint': 'abc', 'where': 'x:y'})
        counts = sorted((e['type'], e['data'].get('page', e['data'].get('code')), e['data']['count']) for e in tel.pending())
        self.assertEqual(counts, [('err.server', 'KeyError', 3), ('use.page', 'sell', 5), ('use.page', 'stock', 1)])
        clock.t += 3600
        tel.emit('use.page', {'page': 'sell'}, user='u1')
        self.assertEqual(len(tel.pending()), 4, 'a new hour starts a new row')

    def test_bounds_drop_least_important_first(self):
        clock = Clock()
        tel, _ = setup(people=['u1'], limits={'max_events': 5}, clock=clock)
        tel.emit('upgrade.fail', {'from': '1.0', 'to': '1.1', 'code': 'disk'})
        for i in range(8):
            clock.t += 1
            tel.emit('guide.step', {'guide': 'g', 'step': i, 'kind': 'click', 'seconds': 1}, user='u1')
        kept = [e['type'] for e in tel.pending(50)]
        self.assertEqual(len(kept), 5)
        self.assertIn('upgrade.fail', kept)
        self.assertEqual(tel.counters()['dropped.full'], 4)

    def test_age_and_bytes(self):
        clock = Clock()
        tel, _ = setup(limits={'max_bytes': 2000}, clock=clock)
        tel.emit('hb', {'error_count': 1})
        clock.t += 31 * 86400
        tel.emit('hb', {'error_count': 2})
        self.assertEqual([e['data']['error_count'] for e in tel.pending()], [2])
        for i in range(20):
            tel.emit('backup.ok', {'size_mb': i})
        total = tel.db.execute('SELECT SUM(size) FROM outbox').fetchone()[0]
        self.assertLessEqual(total, 2000)


class Sending(unittest.TestCase):
    def test_signed_gzip_batches_and_backoff(self):
        clock = Clock()
        tel, _ = setup(people=['u1'], limits={'batch_bytes': 1500}, clock=clock)
        for i in range(10):
            tel.emit('guide.start', {'guide': f'g{i}'}, user='u1')
        tel.emit('upgrade.fail', {'from': '1', 'to': '2', 'code': 'x'})
        seen = []

        def ok(url, body, headers):
            seen.append((body, headers))
            return 202
        token = 'ins_' + 'x' * 30
        state, n = tel.send_once('https://relay.example/ingest', token, post=ok)
        self.assertEqual(state, 'sent')
        body, h = seen[0]
        events = json.loads(gzip.decompress(body))
        self.assertEqual(events[0]['type'], 'upgrade.fail', 'most important first')
        self.assertLessEqual(len(gzip.decompress(body)), 1500)
        self.assertTrue(T.verify(hashlib.sha256(token.encode()).hexdigest(), h['X-AF-Timestamp'], h['X-AF-Nonce'], body,
                                 h['X-AF-Signature'], now=clock.t))
        self.assertFalse(T.verify(hashlib.sha256(token.encode()).hexdigest(), h['X-AF-Timestamp'], h['X-AF-Nonce'],
                                  body + b'x', h['X-AF-Signature'], now=clock.t))
        self.assertFalse(T.verify(hashlib.sha256(token.encode()).hexdigest(), h['X-AF-Timestamp'], h['X-AF-Nonce'], body,
                                  h['X-AF-Signature'], now=clock.t + 301), 'five-minute window')
        self.assertEqual(len(tel.recent_sent()), n)
        left = len(tel.pending())
        self.assertEqual(tel.send_once('u', token, post=lambda *a: 503), ('failed', 503))
        self.assertEqual(tel.send_once('u', token, post=ok)[0], 'backoff')
        clock.t += 61
        self.assertEqual(tel.send_once('u', token, post=lambda *a: (_ for _ in ()).throw(OSError()))[0], 'failed')
        clock.t += 61
        self.assertEqual(tel.send_once('u', token, post=ok)[0], 'backoff', 'second failure waits 2 minutes')
        clock.t += 60
        self.assertEqual(tel.send_once('u', token, post=ok)[0], 'sent')
        self.assertLess(len(tel.pending()), left)
        while tel.send_once('u', token, post=ok)[0] == 'sent':
            pass
        self.assertEqual(tel.send_once('u', token, post=ok), ('idle', 0))

    def test_backoff_is_capped_at_six_hours(self):
        clock = Clock()
        tel, _ = setup(clock=clock)
        tel.emit('hb', {})
        for _ in range(15):
            clock.t = max(clock.t, tel._state('next_try', 0))
            tel.send_once('u', 't', post=lambda *a: 500)
        self.assertLessEqual(tel._state('next_try') - clock.t, 6 * 3600)

    def test_browser_events(self):
        tel, _ = setup(people=['u1'])
        out = tel.from_browser([
            {'type': 'use.action', 'data': {'action': 'sale.pay'}, 'page': 'sell'},
            {'type': 'guide.done', 'data': {'guide': 'open-shift'}},
            {'type': 'hb', 'data': {}},                                   # not a browser type
            {'type': 'use.page', 'data': {'page': 'sell', 'name': 'x'}},  # never-list
            'junk'], user='u1', role='cashier')
        self.assertEqual(out, {'queued': 2, 'dropped': 0, 'rejected': 3})
        self.assertEqual(tel.from_browser([{'type': 'use.page', 'data': {'page': 'x'}}], user='u2'),
                         {'queued': 0, 'dropped': 1, 'rejected': 0})


@unittest.skipUnless(shutil.which('node'), 'node is not installed')
class Js(unittest.TestCase):
    def test_node_tests(self):
        r = subprocess.run(['node', '--test', str(PKG / 'tests' / 'core.test.mjs')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        src = (PKG / 'af-telemetry.js').read_text(encoding='utf-8')
        for bad in ('innerHTML', 'insertAdjacentHTML', 'eval(', 'e.message', 'html2canvas', 'keydown'):
            if bad == 'keydown':
                self.assertEqual(src.count("'keydown'"), 1, 'the only key listener is Escape on the report dialog')
            else:
                self.assertFalse(bad in src, bad)


class VendoredCopies(unittest.TestCase):
    def test_known_products_hold_a_fresh_copy(self):
        sys.path.insert(0, str(PKG.parents[1] / 'scripts'))
        import vendor_telemetry as V
        root = PKG.parents[2]
        for name in ('Store', 'Teachers', 'Yousef-Transportation', 'Mr.Ayman-HR'):
            repo = Path(os.environ.get(f'AF_{name.upper().replace("-", "_").replace(".", "_")}_REPO', root / name))
            for src, dest, headed in V.destinations(repo):
                if dest.exists():
                    body = dest.read_bytes().split(b'\n', 2)[2] if headed else dest.read_bytes()
                    self.assertEqual(hashlib.sha256(body).hexdigest(), hashlib.sha256(src.read_bytes()).hexdigest(),
                                     f'{dest} is stale: run python scripts/vendor_telemetry.py <product repo>')


class FingerprintShape(unittest.TestCase):
    def test_fingerprint_is_letters_only(self):
        for n in range(3000):
            fp, _ = T.Telemetry.fingerprint(type("E%d" % n, (Exception,), {})())
            self.assertRegex(fp, r"^[a-p]{16}$")
            T.clean_data(T.TAXONOMY, "err.server", {"code": "E", "fingerprint": fp, "where": "a:b"})


if __name__ == '__main__':
    unittest.main()
