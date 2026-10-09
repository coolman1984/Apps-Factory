import hashlib
import os
import sys
import unittest
from datetime import date
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
from af_license import generate_keypair  # noqa: E402
from af_license import codes  # noqa: E402
from af_license.ed25519_verify import verify as stdlib_verify  # noqa: E402

TODAY = date(2026, 10, 8)


class CodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pem, cls.pub, cls.kid = generate_keypair()
        cls.other_pem, cls.other_pub, _ = generate_keypair()
        cls.device = codes.device_code('machine-guid-123', 'install-abc')

    def trial(self, **kw):
        args = dict(private_pem=self.pem, product_id='al-store', edition='trial', first_day=TODAY, days=14, device=self.device,
                    issued=TODAY)
        args.update(kw)
        return codes.issue_code(**args)

    def read(self, code, today=TODAY, device=None, product='al-store', keys=None):
        return codes.read_code(code, keys or [self.pub], product, device or self.device, today)

    def test_reading_a_non_text_value_never_raises(self):
        for junk in (None, 1, 1.5, True, [], ['a'], {}, b'bytes'):
            result = codes.read_code(junk, ['AAAA'], 'al-store', 'ABCDE-FGHJK')
            self.assertFalse(result.full_access)
            self.assertEqual(result.state, 'invalid')

    def test_trial_is_fourteen_days_inclusive(self):
        c = self.trial()
        self.assertEqual(c['last_day'], '2026-10-21')
        r = self.read(c['code'])
        self.assertTrue(r.full_access)
        self.assertEqual(r.terms['edition'], 'trial')
        self.assertEqual(r.terms['days_left'], 14)
        self.assertTrue(self.read(c['code'], date(2026, 10, 21)).full_access)
        late = self.read(c['code'], date(2026, 10, 22))
        self.assertEqual(late.state, 'expired')
        self.assertFalse(late.full_access)

    def test_code_shape_is_pasteable(self):
        code = self.trial()['code']
        self.assertEqual(len(codes.normalize(code)), 144)
        self.assertTrue(set(codes.normalize(code)) <= set(codes.ALPHABET))
        messy = code.lower().replace('-', ' ').replace('0', 'o').replace('1', 'l')  # how people retype codes
        self.assertTrue(self.read(messy).full_access)

    def test_any_changed_letter_is_refused(self):
        code = codes.normalize(self.trial()['code'])
        for i in (0, 10, 30, 41, 60, 100, 143):
            ch = '2' if code[i] != '2' else '3'
            changed = code[:i] + ch + code[i + 1:]
            self.assertFalse(self.read(changed).valid, i)

    def test_bound_to_device_product_and_key(self):
        c = self.trial()['code']
        self.assertEqual(self.read(c, device=codes.device_code('another-pc')).reason, 'other_device')
        self.assertEqual(self.read(c, product='hessa-centre').reason, 'wrong_product')
        self.assertEqual(self.read(c, keys=[self.other_pub]).reason, 'unknown_key')

    def test_unbound_code_works_on_any_device(self):
        c = self.trial(device=None)['code']
        r = self.read(c, device=codes.device_code('any-pc'))
        self.assertTrue(r.full_access)
        self.assertFalse(r.terms['device_bound'])

    def test_future_start_and_grace(self):
        c = self.trial(first_day=date(2026, 10, 10), days=30, grace_days=5, edition='standard')['code']
        self.assertEqual(self.read(c).state, 'not_yet_valid')
        self.assertEqual(self.read(c, date(2026, 11, 10)).state, 'grace')
        self.assertEqual(self.read(c, date(2026, 11, 15)).state, 'expired')

    def test_monthly_code_is_thirty_days_and_cannot_be_extended_silently(self):
        c = codes.issue_code(self.pem, 'al-store', 'monthly', TODAY, 30, self.device, issued=TODAY)
        self.assertEqual(c['last_day'], (TODAY + __import__('datetime').timedelta(days=29)).isoformat())
        self.assertTrue(self.read(c['code'], TODAY + __import__('datetime').timedelta(days=29)).full_access)
        self.assertEqual(self.read(c['code'], TODAY + __import__('datetime').timedelta(days=30)).state, 'expired')
        with self.assertRaisesRegex(ValueError, 'monthly_is_30_days'):
            codes.issue_code(self.pem, 'al-store', 'monthly', TODAY, 365, self.device)

    def test_lifetime_never_expires_but_is_signed_and_device_bound(self):
        c = codes.issue_code(self.pem, 'al-store', 'lifetime', TODAY, 1, self.device, issued=TODAY)
        self.assertIsNone(c['last_day'])
        self.assertTrue(c['permanent'])
        for on_day in (TODAY, date(2099, 12, 31), date(9999, 12, 31)):
            r = self.read(c['code'], on_day)
            self.assertTrue(r.full_access)
            self.assertTrue(r.terms['permanent'])
            self.assertIsNone(r.terms['days_left'])
            self.assertIsNone(r.terms['last_day'])
        self.assertEqual(self.read(c['code'], device=codes.device_code('other-device')).reason, 'other_device')
        with self.assertRaisesRegex(ValueError, 'lifetime_requires_device'):
            codes.issue_code(self.pem, 'al-store', 'lifetime', TODAY, 1, None)
        wrong = codes.normalize(c['code'])
        altered = ('2' if wrong[45] != '2' else '3')
        self.assertFalse(self.read(wrong[:45] + altered + wrong[46:]).valid)

    def test_garbage_never_raises(self):
        for text in ('', 'hello world', '!' * 144, 'Z' * 144, '0' * 143, None):
            r = codes.read_code(text or '', [self.pub], 'al-store', self.device, TODAY)
            self.assertFalse(r.valid)

    def test_stdlib_verifier_matches_cryptography(self):
        from cryptography.hazmat.primitives import serialization
        private = serialization.load_pem_private_key(self.pem, password=None)
        public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        for n in range(20):
            msg = os.urandom(n * 7)
            sig = private.sign(msg)
            self.assertTrue(stdlib_verify(public, msg, sig))
            self.assertFalse(stdlib_verify(public, msg + b'x', sig))
            bad = bytearray(sig)
            bad[n % 64] ^= 1
            self.assertFalse(stdlib_verify(public, msg, bytes(bad)))

    def test_rfc8032_vector(self):
        # RFC 8032 §7.1 TEST 1 (empty message)
        pub = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
        sig = bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
        self.assertTrue(stdlib_verify(pub, b'', sig))

    def test_device_code_is_stable_and_short(self):
        a = codes.device_code('GUID', 'install')
        self.assertEqual(a, codes.device_code(' guid ', 'INSTALL'))
        self.assertRegex(a, r'^[0-9A-HJKMNP-TV-Z]{5}-[0-9A-HJKMNP-TV-Z]{5}$')
        self.assertNotEqual(a, codes.device_code('GUID', 'install2'))

    def test_vendored_copy_in_known_products_matches(self):
        """Products copy codes.py and ed25519_verify.py; a stale copy is a release blocker."""
        src = hashlib.sha256((PKG / 'af_license' / 'codes.py').read_bytes()).hexdigest()
        for product in (Path(os.environ.get('AF_STORE_REPO', PKG.parents[2] / 'Store')),):
            copy = product / 'server' / 'afcodes.py'
            if copy.exists():
                body = copy.read_bytes().split(b'\n', 2)[2]  # skip the two-line vendoring header
                self.assertEqual(hashlib.sha256(body).hexdigest(), src, f'{copy} is stale: run scripts/vendor_licence.py')


if __name__ == '__main__':
    unittest.main()
