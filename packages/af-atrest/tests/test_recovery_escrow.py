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
from af_activation import activate_encrypted_storage  # noqa: E402
from af_crypto_box import (  # noqa: E402
    build_recovered_key_package,
    escrow_binding_aad,
    generate_escrow_keypair,
    sealed_box_decrypt,
)
from af_errors import AtRestError  # noqa: E402
from af_escrow import escrow_package, upload_escrow  # noqa: E402
from af_recovery import (  # noqa: E402
    TRANSFER_KEY_NAME,
    device_transfer_public_hex,
    restore_on_new_device,
    verify_backup_with_data_key,
)
from af_sync import enqueue_escrow, flush_sync_queue, load_sync_state, outbox_pending, save_sync_state, sync_warning  # noqa: E402

try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305  # noqa: F401

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class RecoveryFlow(unittest.TestCase):
    def setUp(self):
        self.prof = tempfile.mkdtemp()
        self._env = patch.dict(
            os.environ,
            {'AF_ENCRYPT': '1', 'AF_DPAPI_DIR': self.prof},
            clear=False,
        )
        self._env.start()
        A._MASTER = None
        A._DATA_KEYS.clear()

    def tearDown(self):
        self._env.stop()

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_vendor_recovery_roundtrip_new_device(self):
        with tempfile.TemporaryDirectory() as data_a, tempfile.TemporaryDirectory() as data_b:
            db = os.path.join(data_a, 'shop.db')
            c = sqlite3.connect(db)
            c.execute('CREATE TABLE t(x)')
            c.execute('INSERT INTO t VALUES(1)')
            c.close()
            A.seal_sqlite_file(db, data_a, {'name': 'shop.db'})
            dk_a = A.data_key(data_a)
            target_pub_hex = device_transfer_public_hex(data_b)
            target_pub = bytes.fromhex(target_pub_hex)
            pkg_bytes = build_recovered_key_package(
                dk_a, target_pub, 'co-1', 'OLD-PC', 'NEW-PC',
            )
            A._DATA_KEYS.clear()
            restore_on_new_device(data_b, db, pkg_bytes)
            self.assertTrue(os.path.exists(A._key_path(data_b)))
            verify_backup_with_data_key(db, A.data_key(data_b))

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_wrong_device_package(self):
        with tempfile.TemporaryDirectory() as data_a, tempfile.TemporaryDirectory() as data_b:
            db = os.path.join(data_a, 'x.db')
            sqlite3.connect(db).close()
            A.seal_sqlite_file(db, data_a, {})
            other_pub = bytes.fromhex(device_transfer_public_hex(tempfile.mkdtemp()))
            pkg = build_recovered_key_package(A.data_key(data_a), other_pub, 'c', 's', 't')
            device_transfer_public_hex(data_b)
            with self.assertRaises(AtRestError) as ctx:
                restore_on_new_device(data_b, db, pkg)
            self.assertEqual(ctx.exception.code, 'ATREST_RECOVERED_PACKAGE_TAMPERED')

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_restore_refuses_conflicting_nonempty_key(self):
        with tempfile.TemporaryDirectory() as data_a, tempfile.TemporaryDirectory() as data_b:
            db = os.path.join(data_a, 'shop.db')
            c = sqlite3.connect(db)
            c.execute('CREATE TABLE t(x)')
            c.execute('INSERT INTO t VALUES(1)')
            c.close()
            A.seal_sqlite_file(db, data_a, {})
            target_pub = bytes.fromhex(device_transfer_public_hex(data_b))
            pkg_bytes = build_recovered_key_package(
                A.data_key(data_a), target_pub, 'co-1', 'OLD', 'NEW',
            )
            local_db = os.path.join(data_b, 'shop.db')
            c = sqlite3.connect(local_db)
            c.execute('CREATE TABLE t(x)')
            c.execute('INSERT INTO t VALUES(99)')
            c.commit()
            c.close()
            A.data_key(data_b)
            with self.assertRaises(AtRestError) as ctx:
                restore_on_new_device(data_b, db, pkg_bytes)
            self.assertEqual(ctx.exception.code, 'ATREST_RECOVERED_KEY_CONFLICT')
            self.assertTrue(ctx.exception.message('ar'))

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_restore_replaces_empty_conflicting_key(self):
        with tempfile.TemporaryDirectory() as data_a, tempfile.TemporaryDirectory() as data_b:
            db = os.path.join(data_a, 'shop.db')
            sqlite3.connect(db).close()
            A.seal_sqlite_file(db, data_a, {})
            dk_a = A.data_key(data_a)
            target_pub = bytes.fromhex(device_transfer_public_hex(data_b))
            pkg_bytes = build_recovered_key_package(dk_a, target_pub, 'c', 's', 't')
            A.data_key(data_b)
            restore_on_new_device(data_b, db, pkg_bytes)
            self.assertEqual(A.data_key(data_b), dk_a)

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_device_transfer_key_is_dpapi_wrapped(self):
        with tempfile.TemporaryDirectory() as data:
            device_transfer_public_hex(data)
            path = os.path.join(data, TRANSFER_KEY_NAME)
            with open(path, 'rb') as f:
                blob = f.read()
            self.assertTrue(blob.startswith(A.MAGIC_DEVICE_TRANSFER))


class EscrowFlow(unittest.TestCase):
    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_escrow_seal_and_upload(self):
        priv, pub = generate_escrow_keypair()
        key = os.urandom(32)
        pkg = escrow_package(key, pub, 'co', 'dev-1')
        bind = escrow_binding_aad('co', 'dev-1')
        got = sealed_box_decrypt(__import__('base64').b64decode(pkg['sealed_key']), priv, bind)
        self.assertEqual(got, key)

        class T:
            def post(self, url, headers, body):
                self.url = url
                self.headers = headers
                return 201, b'{}'

        t = T()
        upload_escrow('https://worker.example', 'tok', 'co', pkg, transport=t)
        self.assertIn('/escrow', t.url)
        self.assertEqual(t.headers.get('x-af-company-id'), 'co')

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_escrow_binding_rejects_relabel(self):
        priv, pub = generate_escrow_keypair()
        key = os.urandom(32)
        pkg = escrow_package(key, pub, 'real-co', 'dev-1')
        sealed = __import__('base64').b64decode(pkg['sealed_key'])
        with self.assertRaises(ValueError):
            sealed_box_decrypt(sealed, priv, escrow_binding_aad('fake-co', 'dev-1'))

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_activation_enqueues_escrow(self):
        _priv, pub = generate_escrow_keypair()
        with tempfile.TemporaryDirectory() as data:
            activate_encrypted_storage(
                data, pub, 'co', 'dev', 'https://w', 'tok', migrate_plaintext=False,
            )
            self.assertEqual(outbox_pending(data, 'escrow'), 1)


class SyncFlow(unittest.TestCase):
    def setUp(self):
        self.prof = tempfile.mkdtemp()
        self._env = patch.dict(
            os.environ,
            {'AF_ENCRYPT': '1', 'AF_DPAPI_DIR': self.prof},
            clear=False,
        )
        self._env.start()
        A._MASTER = None
        A._DATA_KEYS.clear()

    def tearDown(self):
        self._env.stop()

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_outbox_encrypted_token_and_mode(self):
        with tempfile.TemporaryDirectory() as data:
            A.data_key(data)
            pkg = escrow_package(os.urandom(32), generate_escrow_keypair()[1], 'c', 'd')
            enqueue_escrow(data, 'https://w', 'secret-token-value', pkg, now=1.0)
            conn = sqlite3.connect(os.path.join(data, 'af-atrest-sync.sqlite'))
            row = conn.execute('SELECT payload FROM outbox').fetchone()
            conn.close()
            self.assertNotIn('secret-token-value', row[0])
            self.assertIn('company_token_enc', row[0])
            mode = os.stat(os.path.join(data, 'af-atrest-sync.sqlite')).st_mode & 0o777
            self.assertEqual(mode, 0o600)

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_offline_queue_retry_and_success(self):
        priv, pub = generate_escrow_keypair()
        with tempfile.TemporaryDirectory() as data:
            A.data_key(data)
            pkg = escrow_package(os.urandom(32), pub, 'c', 'd')
            enqueue_escrow(data, 'https://worker.example', 'tok', pkg, now=1000.0)
            self.assertEqual(outbox_pending(data), 1)
            warn = sync_warning(data, now=1000.0, warn_after_days=3)
            self.assertIsNotNone(warn)
            self.assertIn('escrow', warn['en'].lower())

            class Fail:
                def post(self, url, headers, body):
                    return 503, b''

            sent, failed = flush_sync_queue(data, Fail(), now=1000.0)
            self.assertEqual(sent, 0)
            self.assertEqual(failed, 1)
            self.assertEqual(outbox_pending(data), 1)

            class Ok:
                def post(self, url, headers, body):
                    return 201, b'{}'

            sent, failed = flush_sync_queue(data, Ok(), now=2000.0)
            self.assertEqual(sent, 1)
            self.assertEqual(outbox_pending(data), 0)
            state = load_sync_state(data)
            self.assertEqual(state['escrow'], 2000.0)
            state['backup'] = 2000.0
            save_sync_state(data, state)
            self.assertIsNone(sync_warning(data, now=2000.0, warn_after_days=3))

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_sync_warning_after_threshold(self):
        with tempfile.TemporaryDirectory() as data:
            state_path = os.path.join(data, 'af-atrest-sync-state.json')
            with open(state_path, 'w', encoding='utf-8') as f:
                f.write('{"backup": null, "escrow": 0.0}\n')
            now = 4 * 86400.0
            warn = sync_warning(data, now=now, warn_after_days=3)
            self.assertIsNotNone(warn)
            self.assertTrue(warn['ar'])


if __name__ == '__main__':
    unittest.main()
