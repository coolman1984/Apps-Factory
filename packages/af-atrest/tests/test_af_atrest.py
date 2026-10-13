"""af-atrest: off by default, backup crypto, keys, sqlcipher refusal when enabled."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
import af_atrest as A  # noqa: E402

try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305  # noqa: F401

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class OffByDefault(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {}, clear=True)
        self._env.start()
        A._DRIVER_TRIED = False
        A._DRIVER = None
        A._MASTER = None
        A._DATA_KEYS.clear()

    def tearDown(self):
        self._env.stop()

    def test_disabled_without_flag(self):
        self.assertFalse(A.enabled())
        self.assertEqual(A.backend(), 'off')
        conn = A.connect(':memory:')
        conn.execute('CREATE TABLE t(x)')
        conn.close()

    def test_backend_off_ignores_missing_sqlcipher(self):
        with patch.object(A, '_sqlcipher', return_value=None):
            self.assertEqual(A.backend(), 'off')


class BackupCrypto(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(
            os.environ,
            {'AF_ENCRYPT': '1', 'AF_DPAPI_DIR': tempfile.mkdtemp()},
            clear=False,
        )
        self._env.start()
        A._MASTER = None
        A._DATA_KEYS.clear()

    def tearDown(self):
        self._env.stop()

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_seal_unseal_roundtrip(self):
        with tempfile.TemporaryDirectory() as data:
            db = os.path.join(data, 'shop.db')
            plain = sqlite3.connect(db)
            plain.executescript('CREATE TABLE meta(k,v); INSERT INTO meta VALUES("a","1");')
            plain.close()
            A.seal_sqlite_file(db, data, {'part': 'main', 'name': 'shop.db'})
            self.assertTrue(A.is_aead(db))
            self.assertFalse(A.is_plain_sqlite(db))
            out = A.unseal_bytes(db)
            self.assertIn(b'SQLite format 3', out[:16])

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_tamper_detected(self):
        with tempfile.TemporaryDirectory() as data:
            db = os.path.join(data, 'shop.db')
            sqlite3.connect(db).close()
            A.seal_sqlite_file(db, data, {})
            with open(db, 'rb') as f:
                blob = bytearray(f.read())
            blob[-1] ^= 0xFF
            with open(db, 'wb') as f:
                f.write(blob)
            with self.assertRaises(sqlite3.DatabaseError):
                A.unseal_bytes(db)


class KeyFile(unittest.TestCase):
    def setUp(self):
        self.prof = tempfile.mkdtemp()
        self._env = patch.dict(os.environ, {'AF_DPAPI_DIR': self.prof}, clear=False)
        self._env.start()
        A._MASTER = None
        A._DATA_KEYS.clear()

    def tearDown(self):
        self._env.stop()

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_key_created_and_reused(self):
        with tempfile.TemporaryDirectory() as data:
            k1 = A.data_key(data)
            path = A._key_path(data)
            self.assertTrue(os.path.exists(path))
            k2 = A.data_key(data)
            self.assertEqual(k1, k2)


class SqlcipherRequired(unittest.TestCase):
    def test_refuses_when_enabled_and_missing(self):
        env = patch.dict(os.environ, {'AF_ENCRYPT': '1'}, clear=False)
        with env:
            A._DRIVER_TRIED = False
            A._DRIVER = None
            with patch.object(A, '_sqlcipher', return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    A.backend()
                self.assertIn('sqlcipher3', str(ctx.exception))

    def test_file_backend_refused(self):
        env = patch.dict(os.environ, {'AF_ENCRYPT': '1', 'AF_ENCRYPT_BACKEND': 'file'}, clear=False)
        with env:
            with self.assertRaises(RuntimeError) as ctx:
                A.backend()
            self.assertIn('not supported', str(ctx.exception))


class PlaintextRefused(unittest.TestCase):
    def test_connect_refuses_plaintext_when_enabled(self):
        with tempfile.TemporaryDirectory() as data:
            db = os.path.join(data, 'x.db')
            sqlite3.connect(db).close()
            env = patch.dict(
                os.environ,
                {'AF_ENCRYPT': '1', 'AF_DPAPI_DIR': tempfile.mkdtemp()},
                clear=False,
            )
            with env, patch.object(A, '_sqlcipher') as sc:
                sc.return_value = None
                with self.assertRaises(RuntimeError):
                    A.connect(db)


if __name__ == '__main__':
    unittest.main()
