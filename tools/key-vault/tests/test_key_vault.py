import base64
import io
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'key-vault'))
sys.path.insert(0, str(ROOT.parent / 'packages' / 'af-atrest'))

from af_escrow import escrow_package  # noqa: E402
from af_crypto_box import generate_escrow_keypair  # noqa: E402
from key_vault import (  # noqa: E402
    cmd_decrypt_data_key,
    cmd_gen_escrow,
    cmd_import_escrow,
    cmd_make_recovery_package,
    init_vault,
    open_vault_db,
    seal_vault_db,
)


class KeyVault(unittest.TestCase):
    def test_init_import_decrypt(self):
        with tempfile.TemporaryDirectory() as d:
            vault = os.path.join(d, 'vault.afvault')
            init_vault(vault, 'master')
            args = type('A', (), {
                'vault': vault,
                'password': 'master',
                'label': 'main',
                'private_out': None,
            })()
            with redirect_stdout(io.StringIO()) as out:
                cmd_gen_escrow(args)
            pub = bytes.fromhex(out.getvalue().strip())
            data_key = os.urandom(32)
            pkg = escrow_package(data_key, pub, 'co-x', 'PC-9')
            jp = os.path.join(d, 'pkg.json')
            with open(jp, 'w', encoding='utf-8') as f:
                json.dump(pkg, f)
            cmd_import_escrow(type('A', (), {'vault': vault, 'json_path': jp, 'password': 'master'})())
            out = os.path.join(d, 'dk.bin')
            cmd_decrypt_data_key(type('A', (), {
                'vault': vault,
                'password': 'master',
                'company_id': 'co-x',
                'device_code': 'PC-9',
                'escrow_label': 'main',
                'out': out,
            })())
            with open(out, 'rb') as f:
                self.assertEqual(f.read(), data_key)

    def test_make_recovery_package(self):
        with tempfile.TemporaryDirectory() as d:
            vault = os.path.join(d, 'vault.afvault')
            init_vault(vault, 'master')
            args = type('A', (), {
                'vault': vault,
                'password': 'master',
                'label': 'main',
                'private_out': None,
            })()
            with redirect_stdout(io.StringIO()) as out:
                cmd_gen_escrow(args)
            pub = bytes.fromhex(out.getvalue().strip())
            data_key = os.urandom(32)
            pkg = escrow_package(data_key, pub, 'co-x', 'OLD')
            jp = os.path.join(d, 'pkg.json')
            with open(jp, 'w', encoding='utf-8') as f:
                json.dump(pkg, f)
            cmd_import_escrow(type('A', (), {'vault': vault, 'json_path': jp, 'password': 'master'})())
            target_priv, target_pub = generate_escrow_keypair()
            rp = os.path.join(d, 'recovered.json')
            cmd_make_recovery_package(type('A', (), {
                'vault': vault,
                'password': 'master',
                'company_id': 'co-x',
                'source_device_code': 'OLD',
                'target_device_code': 'NEW',
                'target_public_hex': target_pub.hex(),
                'escrow_label': 'main',
                'out': rp,
            })())
            sys.path.insert(0, str(ROOT.parent / 'packages' / 'af-atrest'))
            from af_crypto_box import parse_recovered_key_package, unwrap_recovered_key_package  # noqa: E402

            with open(rp, 'rb') as f:
                doc = parse_recovered_key_package(f.read())
            self.assertEqual(unwrap_recovered_key_package(doc, target_priv), data_key)

    def test_import_rejects_relabeled_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            vault = os.path.join(d, 'vault.afvault')
            init_vault(vault, 'master')
            args = type('A', (), {
                'vault': vault,
                'password': 'master',
                'label': 'main',
                'private_out': None,
            })()
            with redirect_stdout(io.StringIO()) as out:
                cmd_gen_escrow(args)
            pub = bytes.fromhex(out.getvalue().strip())
            pkg = escrow_package(os.urandom(32), pub, 'co-x', 'PC-9')
            pkg['company_id'] = 'co-evil'
            jp = os.path.join(d, 'bad.json')
            with open(jp, 'w', encoding='utf-8') as f:
                json.dump(pkg, f)
            from af_errors import AtRestError  # noqa: E402

            with self.assertRaises(AtRestError) as ctx:
                cmd_import_escrow(type('A', (), {'vault': vault, 'json_path': jp, 'password': 'master'})())
            self.assertEqual(ctx.exception.code, 'ATREST_VAULT_UNSEAL_FAILED')

    def test_vault_atomic_write_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as d:
            vault = os.path.join(d, 'vault.afvault')
            init_vault(vault, 'master')
            before = open(vault, 'rb').read()
            real_write = os.write

            def flaky_write(fd, data):
                if flaky_write.calls == 0:
                    flaky_write.calls += 1
                    return real_write(fd, data[: max(1, len(data) // 2)])
                raise OSError('simulated short write')

            flaky_write.calls = 0
            plain = os.path.join(d, 'plain.db')
            conn = __import__('sqlite3').connect(plain)
            conn.execute('CREATE TABLE t(x)')
            conn.commit()
            conn.close()
            with unittest.mock.patch('os.write', flaky_write):
                with self.assertRaises(OSError):
                    seal_vault_db(plain, vault, 'master')
            after = open(vault, 'rb').read()
            self.assertEqual(before, after)
            conn, tmp = open_vault_db(vault, 'master')
            conn.close()
            os.unlink(tmp)


if __name__ == '__main__':
    unittest.main()
