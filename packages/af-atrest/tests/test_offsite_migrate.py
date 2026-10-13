import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
import af_atrest as A  # noqa: E402
from af_errors import AtRestError  # noqa: E402
from af_migrate import migrate_to_encrypted, rollback_migration  # noqa: E402
from af_offsite import upload_offsite_backup  # noqa: E402
from af_offsite import DEFAULT_SETTINGS, business_date_today, load_settings, offsite_due_today, run_offsite_if_due, save_settings  # noqa: E402

try:
    HAS_CRYPTO = True
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305  # noqa: F401
except ImportError:
    HAS_CRYPTO = False


class Offsite(unittest.TestCase):
    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_default_enabled(self):
        with tempfile.TemporaryDirectory() as d:
            s = load_settings(os.path.join(d, 'missing.json'))
            self.assertTrue(s['enabled'])
            self.assertTrue(DEFAULT_SETTINGS['enabled'])

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_due_once_per_day(self):
        settings = {'enabled': True, 'timezone': 'UTC', 'last_upload_date': None}
        self.assertTrue(offsite_due_today(settings, 'UTC'))
        settings['last_upload_date'] = business_date_today('UTC')
        self.assertFalse(offsite_due_today(settings, 'UTC'))

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_upload_marks_date(self):
        with tempfile.TemporaryDirectory() as d:
            settings_path = os.path.join(d, 'offsite.json')
            save_settings(settings_path, {'enabled': True, 'timezone': 'UTC', 'last_upload_date': None})
            backup = os.path.join(d, 'b.db')
            with open(backup, 'wb') as f:
                f.write(b'AFAEAD1' + b'0' * 32)

            class T:
                def post(self, url, headers, body):
                    return 201, b'{}'

            run_offsite_if_due(settings_path, 'https://x', 't', 'c', 'dev', backup, T())
            with open(settings_path, encoding='utf-8') as f:
                s = json.load(f)
            self.assertIsNotNone(s.get('last_upload_date'))


class MigrateOrchestration(unittest.TestCase):
    def test_missing_sqlcipher(self):
        with tempfile.TemporaryDirectory() as data:
            db = os.path.join(data, 'a.db')
            c = sqlite3.connect(db)
            c.execute('CREATE TABLE t(x)')
            c.commit()
            c.close()
            with patch.object(A, '_sqlcipher', return_value=None):
                with self.assertRaises(AtRestError) as ctx:
                    migrate_to_encrypted(data)
                self.assertEqual(ctx.exception.code, 'ATREST_MIGRATE_SQLCIPHER_MISSING')

    def test_idempotent_when_key_exists(self):
        with tempfile.TemporaryDirectory() as data:
            os.makedirs(data, exist_ok=True)
            with open(A._key_path(data), 'wb') as f:
                f.write(b'AFDPK1' + b'0' * 28)
            migrate_to_encrypted(data)

    def test_offsite_rejects_plaintext_sqlite(self):
        with tempfile.TemporaryDirectory() as d:
            plain = os.path.join(d, 'shop.db')
            sqlite3.connect(plain).close()

            class T:
                def post(self, url, headers, body):
                    return 201, b'{}'

            with self.assertRaises(AtRestError) as ctx:
                upload_offsite_backup('https://x', 'tok', 'co', 'dev', plain, T())
            self.assertEqual(ctx.exception.code, 'ATREST_BACKUP_NOT_ENCRYPTED')

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_migrate_all_plaintext_dbs(self):
        class FakeConn:
            def __init__(self, path):
                self.path = path
                self._plain = None
                self._db = None

            def execute(self, sql, params=()):
                if 'ATTACH' in sql.upper():
                    self._plain = params[0]
                    return self
                if 'sqlcipher_export' in sql:
                    shutil.copy2(self._plain, self.path)
                    return type('R', (), {'fetchone': lambda self: (1,)})()
                if 'DETACH' in sql.upper():
                    return self
                if 'PRAGMA journal_mode' in sql:
                    return self
                if 'PRAGMA key' in sql:
                    return self
                if self._db is None:
                    self._db = sqlite3.connect(self.path)
                if params:
                    return self._db.execute(sql, params)
                return self._db.execute(sql)

            def commit(self):
                if self._db is not None:
                    self._db.commit()

            def close(self):
                if self._db is not None:
                    self._db.close()

        class FakeDriver:
            @staticmethod
            def connect(path):
                return FakeConn(path)

        with tempfile.TemporaryDirectory() as data:
            for name in ('a.db', 'b.db'):
                p = os.path.join(data, name)
                c = sqlite3.connect(p)
                c.execute('CREATE TABLE t(x)')
                c.execute('INSERT INTO t VALUES(1)')
                c.commit()
                c.close()
            with patch.dict(os.environ, {'AF_ENCRYPT': '1', 'AF_DPAPI_DIR': tempfile.mkdtemp()}, clear=False):
                A._MASTER = None
                A._DATA_KEYS.clear()
                migrate_to_encrypted(data, sqlcipher_driver=FakeDriver)
            self.assertTrue(os.path.isfile(A._key_path(data)))
            self.assertFalse(os.path.exists(os.path.join(data, '.af-migrate-plain-backup')))
            for name in ('a.db', 'b.db'):
                path = os.path.join(data, name)
                self.assertTrue(os.path.isfile(path))
                c = sqlite3.connect(path)
                self.assertEqual(c.execute('SELECT COUNT(*) FROM t').fetchone()[0], 1)
                c.close()

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_migrate_failure_keeps_plaintext(self):
        class FailConn:
            def __init__(self, path):
                self.path = path

            def execute(self, sql, params=()):
                if 'sqlcipher_export' in sql:
                    raise RuntimeError('export failed')
                return self

            def commit(self):
                pass

            def close(self):
                pass

        class FailDriver:
            @staticmethod
            def connect(path):
                return FailConn(path)

        with tempfile.TemporaryDirectory() as data:
            db = os.path.join(data, 'only.db')
            c = sqlite3.connect(db)
            c.execute('CREATE TABLE t(x)')
            c.execute('INSERT INTO t VALUES(42)')
            c.commit()
            c.close()
            with patch.dict(os.environ, {'AF_ENCRYPT': '1', 'AF_DPAPI_DIR': tempfile.mkdtemp()}, clear=False):
                A._MASTER = None
                A._DATA_KEYS.clear()
                with self.assertRaises(RuntimeError):
                    migrate_to_encrypted(data, sqlcipher_driver=FailDriver)
            self.assertTrue(A.is_plain_sqlite(db))
            c = sqlite3.connect(db)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM t').fetchone()[0], 1)
            c.close()
            self.assertFalse(os.path.exists(os.path.join(data, '.af-migrate-plain-backup')))

    @unittest.skipUnless(HAS_CRYPTO, 'cryptography not installed')
    def test_rollback_from_marker(self):
        with tempfile.TemporaryDirectory() as data:
            db = os.path.join(data, 'x.db')
            c = sqlite3.connect(db)
            c.execute('CREATE TABLE t(x)')
            c.execute('INSERT INTO t VALUES(1)')
            c.commit()
            c.close()
            backup = db + '.plaintext-safety'
            shutil.copy2(db, backup)
            marker = os.path.join(data, '.af-migrate-plain-backup')
            with open(marker, 'w', encoding='utf-8') as f:
                f.write(json.dumps({'v': 1, 'backups': {'x.db': backup}, 'temp_files': []}))
            with open(db, 'wb') as f:
                f.write(b'corrupt')
            self.assertTrue(rollback_migration(data))
            c = sqlite3.connect(db)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM t').fetchone()[0], 1)
            c.close()


if __name__ == '__main__':
    unittest.main()
