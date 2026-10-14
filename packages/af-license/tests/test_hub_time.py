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

    def test_v1_compat(self):
        data = self._pack_v1()
        self.assertEqual(verify_hub_time(data, self.trusted), ('2026-10-14', None))

    def test_v2_good_first_poll(self):
        data = self._pack_v2(server_time=1_700_000_100)
        self.assertEqual(verify_hub_time(data, self.trusted), ('2026-10-14', 1_700_000_100))

    def test_v2_replay_older_server_time_rejected(self):
        data = self._pack_v2(server_time=1_700_000_050)
        self.assertIsNone(verify_hub_time(data, self.trusted, last_server_time=1_700_000_100))

    def test_v2_nonce_mismatch_rejected(self):
        data = self._pack_v2(server_time=1_700_000_200, nonce='abc')
        self.assertIsNone(verify_hub_time(data, self.trusted, nonce='xyz'))

    def test_v2_nonce_match_accepted(self):
        data = self._pack_v2(server_time=1_700_000_010, nonce='n-once1')
        self.assertEqual(
            verify_hub_time(data, self.trusted, nonce='n-once1'),
            ('2026-10-14', 1_700_000_010),
        )

    def test_tamper_rejected(self):
        data = self._pack_v2()
        data['calendar_day'] = '2020-01-01'
        self.assertIsNone(verify_hub_time(data, self.trusted))


if __name__ == '__main__':
    unittest.main()
