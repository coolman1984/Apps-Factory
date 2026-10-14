import base64
import sys
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
from af_license import generate_keypair  # noqa: E402
from af_license.hub_time import (  # noqa: E402
    HubTimeVerifyResult,
    hub_time_message_v1,
    hub_time_message_v2,
    verify_hub_time,
)


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


class HubTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pem, cls.pub_b64, cls.kid = generate_keypair()
        cls.private = serialization.load_pem_private_key(cls.pem, password=None)
        cls.trusted = {cls.kid: cls.pub_b64}

    def _sign(self, msg: bytes) -> str:
        return _b64url(self.private.sign(msg))

    def _pack_v1(self, day='2026-10-14'):
        return {
            'calendar_day': day,
            'kid': self.kid,
            'sig': self._sign(hub_time_message_v1(day, self.kid)),
            'signed': True,
        }

    def _pack_v2(self, day='2026-10-14', server_time=1_700_000_000, nonce=None):
        msg = hub_time_message_v2(day, server_time, self.kid, nonce)
        out = {
            'calendar_day': day,
            'kid': self.kid,
            'sig': self._sign(hub_time_message_v1(day, self.kid)),
            'server_time': server_time,
            'sig2': self._sign(msg),
            'signed': True,
        }
        if nonce:
            out['nonce'] = nonce
        return out

    def test_unsigned_response_rejected(self):
        self.assertIsNone(verify_hub_time({'calendar_day': '2026-01-01', 'signed': False}, self.trusted))

    def test_v1_disabled_by_default(self):
        data = self._pack_v1()
        self.assertIsNone(verify_hub_time(data, self.trusted))

    def test_v1_without_seal_rejected(self):
        data = self._pack_v1()
        self.assertIsNone(verify_hub_time(data, self.trusted, allow_v1=True))

    def test_v1_far_future_without_seal_rejected(self):
        data = self._pack_v1(day='2099-12-31')
        self.assertIsNone(verify_hub_time(data, self.trusted, allow_v1=True))

    def test_v2_good_first_poll(self):
        nonce = 'first-poll1'
        data = self._pack_v2(server_time=1_700_000_100, nonce=nonce)
        self.assertEqual(
            verify_hub_time(data, self.trusted, nonce=nonce),
            HubTimeVerifyResult('2026-10-14', 1_700_000_100, False, 2, True),
        )

    def test_v2_first_contact_without_nonce_rejected(self):
        data = self._pack_v2(server_time=1_700_000_100)
        self.assertIsNone(verify_hub_time(data, self.trusted))

    def test_v2_replay_older_server_time_rejected(self):
        data = self._pack_v2(server_time=1_700_000_050)
        self.assertIsNone(verify_hub_time(data, self.trusted, last_server_time=1_700_000_100))

    def test_v2_replay_equal_server_time_rejected_without_nonce(self):
        data = self._pack_v2(server_time=1_700_000_100)
        self.assertIsNone(verify_hub_time(data, self.trusted, last_server_time=1_700_000_100))

    def test_v2_nonce_mismatch_rejected(self):
        data = self._pack_v2(server_time=1_700_000_200, nonce='abc')
        self.assertIsNone(verify_hub_time(data, self.trusted, nonce='xyz'))

    def test_v2_nonce_match_accepted(self):
        data = self._pack_v2(server_time=1_700_000_010, nonce='n-once1')
        self.assertEqual(
            verify_hub_time(data, self.trusted, nonce='n-once1'),
            HubTimeVerifyResult('2026-10-14', 1_700_000_010, False, 2, True),
        )

    def test_v2_nonce_rejects_below_last_server_time(self):
        data = self._pack_v2(server_time=1_700_000_050, nonce='n-once1')
        self.assertIsNone(
            verify_hub_time(data, self.trusted, nonce='n-once1', last_server_time=1_700_000_100),
        )

    def test_v2_nonce_rejects_equal_server_time(self):
        data = self._pack_v2(server_time=1_700_000_100, nonce='n-once1')
        self.assertIsNone(
            verify_hub_time(data, self.trusted, nonce='n-once1', last_server_time=1_700_000_100),
        )

    def test_older_day_than_sealed_rejected(self):
        data = self._pack_v2(day='2026-10-10', server_time=1_700_000_200)
        self.assertIsNone(verify_hub_time(data, self.trusted, sealed_day='2026-10-14'))

    def test_day_jump_capped(self):
        data = self._pack_v2(day='2026-10-30', server_time=1_700_000_300)
        self.assertEqual(
            verify_hub_time(data, self.trusted, sealed_day='2026-10-14', max_jump_days=7),
            HubTimeVerifyResult('2026-10-21', 1_700_000_300, True, 2, True),
        )

    def test_v1_before_sealed_rejected(self):
        data = self._pack_v1(day='2026-10-10')
        self.assertIsNone(verify_hub_time(data, self.trusted, sealed_day='2026-10-14', allow_v1=True))

    def test_tamper_rejected(self):
        data = self._pack_v2()
        data['calendar_day'] = '2020-01-01'
        self.assertIsNone(verify_hub_time(data, self.trusted))

    def test_v1_poisoned_server_time_ignored(self):
        data = self._pack_v1()
        data['server_time'] = 9_999_999_999_999
        self.assertIsNone(verify_hub_time(data, self.trusted, allow_v1=True))

    def test_v1_day_equal_sealed_returns_seal_without_advancing(self):
        data = self._pack_v1(day='2026-10-14')
        self.assertEqual(
            verify_hub_time(data, self.trusted, sealed_day='2026-10-14', allow_v1=True),
            HubTimeVerifyResult('2026-10-14', None, False, 1, False),
        )

    def test_v1_future_signed_day_with_seal_returns_sealed_not_advancing(self):
        data = self._pack_v1(day='2026-12-01')
        self.assertEqual(
            verify_hub_time(data, self.trusted, sealed_day='2026-10-14', allow_v1=True, max_jump_days=7),
            HubTimeVerifyResult('2026-10-14', None, False, 1, False),
        )

    def test_v2_accepts_server_time_far_ahead_of_last_without_nonce(self):
        last = 1_700_000_100
        far = last + 30 * 86400
        data = self._pack_v2(server_time=far)
        self.assertEqual(
            verify_hub_time(data, self.trusted, last_server_time=last, max_jump_days=7),
            HubTimeVerifyResult('2026-10-14', far, False, 2, True),
        )

    def test_v2_same_sig2_rejected_after_persisting_server_time(self):
        server_time = 1_700_000_500
        data = self._pack_v2(server_time=server_time)
        first = verify_hub_time(data, self.trusted, last_server_time=1_700_000_100)
        self.assertEqual(first, HubTimeVerifyResult('2026-10-14', server_time, False, 2, True))
        self.assertIsNone(verify_hub_time(data, self.trusted, last_server_time=server_time))

    def test_v2_same_sig2_with_nonce_rejected_after_persisting(self):
        server_time = 1_700_000_500
        nonce = 'once-only1'
        data = self._pack_v2(server_time=server_time, nonce=nonce)
        sealed = '2026-10-14'
        far_day = '2026-10-30'
        data['calendar_day'] = far_day
        data['sig2'] = self._sign(hub_time_message_v2(far_day, server_time, self.kid, nonce))
        first = verify_hub_time(
            data, self.trusted, sealed_day=sealed, max_jump_days=7, nonce=nonce,
        )
        self.assertEqual(first, HubTimeVerifyResult('2026-10-21', server_time, True, 2, True))
        self.assertIsNone(
            verify_hub_time(
                data,
                self.trusted,
                sealed_day='2026-10-21',
                max_jump_days=7,
                nonce=nonce,
                last_server_time=server_time,
            ),
        )


if __name__ == '__main__':
    unittest.main()
