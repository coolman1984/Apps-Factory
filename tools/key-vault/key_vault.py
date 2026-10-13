#!/usr/bin/env python3
"""Vendor key vault: escrow blobs, encrypted SQLite, CLI (+ optional tkinter GUI)."""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sqlite3
import struct
import sys
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'packages' / 'af-atrest'))

from af_crypto_box import (  # noqa: E402
    SCRYPT_N,
    SCRYPT_P,
    SCRYPT_R,
    SCRYPT_SALT_LEN,
    build_recovered_key_package,
    escrow_binding_aad,
    generate_escrow_keypair,
    sealed_box_decrypt,
    _scrypt_key,
)

SCRYPT_N_MAX = 2 ** 20
SCRYPT_R_MAX = 32
SCRYPT_P_MAX = 8
from af_errors import AtRestError  # noqa: E402

MAGIC_VAULT = b'AFVAULT1'
PLAIN_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS escrow_keys (
  id INTEGER PRIMARY KEY,
  label TEXT NOT NULL,
  public_key_hex TEXT NOT NULL,
  private_key_sealed BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS escrow_imports (
  id INTEGER PRIMARY KEY,
  company_id TEXT NOT NULL,
  device_code TEXT NOT NULL,
  sealed_key TEXT NOT NULL,
  imported_at TEXT NOT NULL,
  UNIQUE(company_id, device_code)
);
"""


def _vault_aad(meta: dict) -> bytes:
    return json.dumps(
        {
            'v': meta['v'],
            'vault_id': meta['vault_id'],
            'kdf': meta['kdf'],
            'salt': meta['salt'],
        },
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    ).encode('utf-8')


def _check_kdf_params(kdf: dict) -> None:
    try:
        n = int(kdf['n'])
        r = int(kdf['r'])
        p = int(kdf['p'])
    except (KeyError, TypeError, ValueError):
        raise AtRestError('ATREST_VAULT_TAMPERED', 'kdf') from None
    if n <= 0 or r <= 0 or p <= 0:
        raise AtRestError('ATREST_VAULT_TAMPERED', 'kdf')
    if n > SCRYPT_N_MAX or r > SCRYPT_R_MAX or p > SCRYPT_P_MAX:
        raise AtRestError('ATREST_VAULT_TAMPERED', 'kdf cap')


def _atomic_write_bytes(path: str, blob: bytes) -> None:
    directory = os.path.dirname(os.path.abspath(path)) or '.'
    fd, tmp = tempfile.mkstemp(prefix='af-vault-', suffix='.tmp', dir=directory)
    try:
        written = 0
        while written < len(blob):
            chunk = os.write(fd, blob[written:])
            if chunk <= 0:
                raise OSError('short write')
            written += chunk
        os.fsync(fd)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    else:
        os.close(fd)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def seal_vault_db(plain_db_path: str, out_path: str, password: str) -> None:
    salt = secrets.token_bytes(SCRYPT_SALT_LEN)
    vault_id = secrets.token_hex(8)
    meta = {
        'v': 1,
        'kdf': {'name': 'scrypt', 'n': SCRYPT_N, 'r': SCRYPT_R, 'p': SCRYPT_P},
        'vault_id': vault_id,
        'salt': salt.hex(),
    }
    key = _scrypt_key(password.encode('utf-8'), salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    with open(plain_db_path, 'rb') as f:
        plain = f.read()
    nonce = secrets.token_bytes(12)
    ct = ChaCha20Poly1305(key).encrypt(nonce, plain, _vault_aad(meta))
    header = json.dumps(meta, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    blob = MAGIC_VAULT + struct.pack('>I', len(header)) + header + nonce + ct
    _atomic_write_bytes(out_path, blob)


def open_vault_db(path: str, password: str) -> tuple[sqlite3.Connection, str]:
    with open(path, 'rb') as f:
        blob = f.read()
    if not blob.startswith(MAGIC_VAULT):
        raise AtRestError('ATREST_VAULT_TAMPERED', 'magic')
    hlen = struct.unpack('>I', blob[len(MAGIC_VAULT):len(MAGIC_VAULT) + 4])[0]
    start = len(MAGIC_VAULT) + 4
    meta = json.loads(blob[start:start + hlen].decode('utf-8'))
    kdf = meta['kdf']
    _check_kdf_params(kdf)
    salt = bytes.fromhex(meta['salt'])
    key = _scrypt_key(password.encode('utf-8'), salt, int(kdf['n']), int(kdf['r']), int(kdf['p']))
    nonce = blob[start + hlen:start + hlen + 12]
    ct = blob[start + hlen + 12:]
    try:
        plain = ChaCha20Poly1305(key).decrypt(nonce, ct, _vault_aad(meta))
    except Exception:
        raise AtRestError('ATREST_VAULT_WRONG_PASSWORD') from None
    tmp = tempfile.NamedTemporaryFile(prefix='af-vault-', suffix='.db', delete=False)
    tmp.write(plain)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.row_factory = sqlite3.Row
    conn.executescript(PLAIN_SCHEMA)
    return conn, tmp.name


def init_vault(path: str, password: str) -> None:
    tmp = tempfile.NamedTemporaryFile(prefix='af-vault-init-', suffix='.db', delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.executescript(PLAIN_SCHEMA)
    conn.execute('INSERT INTO meta(k,v) VALUES(?,?)', ('created', '1'))
    conn.commit()
    conn.close()
    seal_vault_db(tmp.name, path, password)
    os.unlink(tmp.name)


def _seal_private(priv: bytes, password: str) -> bytes:
    salt = secrets.token_bytes(16)
    key = _scrypt_key(password.encode('utf-8'), salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    nonce = secrets.token_bytes(12)
    ct = ChaCha20Poly1305(key).encrypt(nonce, priv, b'af-vault-escrow-priv-v1')
    return salt + nonce + ct


def _open_private(blob: bytes, password: str) -> bytes:
    salt, nonce, ct = blob[:16], blob[16:28], blob[28:]
    key = _scrypt_key(password.encode('utf-8'), salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return ChaCha20Poly1305(key).decrypt(nonce, ct, b'af-vault-escrow-priv-v1')


def cmd_gen_escrow(args: argparse.Namespace) -> int:
    priv, pub = generate_escrow_keypair()
    if args.vault:
        conn, tmp = open_vault_db(args.vault, args.password)
        try:
            sealed = _seal_private(priv, args.password)
            conn.execute(
                'INSERT INTO escrow_keys(label, public_key_hex, private_key_sealed) VALUES (?,?,?)',
                (args.label or 'default', pub.hex(), sealed),
            )
            conn.commit()
            conn.close()
            seal_vault_db(tmp, args.vault, args.password)
        finally:
            try:
                conn.close()
            except Exception:
                pass
            os.unlink(tmp)
    elif args.private_out:
        with open(args.private_out, 'wb') as f:
            f.write(priv)
        os.chmod(args.private_out, 0o600)
    print(pub.hex())
    return 0


def cmd_import_escrow(args: argparse.Namespace) -> int:
    with open(args.json_path, 'rb') as f:
        pkg = json.load(f)
    company_id = str(pkg.get('company_id', ''))
    device_code = str(pkg.get('device_code', ''))
    sealed_key = pkg.get('sealed_key')
    if not company_id or not device_code or not isinstance(sealed_key, str):
        raise AtRestError('ATREST_VAULT_UNSEAL_FAILED', 'package fields')
    conn, tmp = open_vault_db(args.vault, args.password)
    try:
        priv = _load_escrow_private(conn, args.password, getattr(args, 'escrow_label', None))
        bind = escrow_binding_aad(company_id, device_code)
        sealed = base64.b64decode(sealed_key)
        try:
            sealed_box_decrypt(sealed, priv, bind)
        except ValueError:
            raise AtRestError('ATREST_VAULT_UNSEAL_FAILED', 'metadata binding') from None
        conn.execute(
            'INSERT INTO escrow_imports(company_id, device_code, sealed_key, imported_at) VALUES (?,?,?,datetime("now")) '
            'ON CONFLICT(company_id, device_code) DO UPDATE SET sealed_key=excluded.sealed_key, imported_at=excluded.imported_at',
            (company_id, device_code, sealed_key),
        )
        conn.commit()
        conn.close()
        seal_vault_db(tmp, args.vault, args.password)
    finally:
        try:
            conn.close()
        except Exception:
            pass
        os.unlink(tmp)
    return 0


def _load_escrow_private(conn: sqlite3.Connection, password: str, label: str | None) -> bytes:
    if label:
        row = conn.execute('SELECT private_key_sealed FROM escrow_keys WHERE label = ?', (label,)).fetchone()
    else:
        row = conn.execute('SELECT private_key_sealed FROM escrow_keys ORDER BY id DESC LIMIT 1').fetchone()
    if not row:
        raise AtRestError('ATREST_VAULT_NO_ESCROW_KEY')
    return _open_private(row[0], password)


def cmd_make_recovery_package(args: argparse.Namespace) -> int:
    """Owner-only: decrypt escrow, re-seal data key for the target device's transfer public key."""
    target_hex = args.target_public_hex.strip()
    if target_hex.startswith('0x'):
        target_hex = target_hex[2:]
    try:
        target_pub = bytes.fromhex(target_hex)
    except ValueError:
        raise AtRestError('ATREST_VAULT_BAD_TARGET_KEY', 'hex') from None
    if len(target_pub) != 32:
        raise AtRestError('ATREST_VAULT_BAD_TARGET_KEY', 'length')
    conn, tmp = open_vault_db(args.vault, args.password)
    try:
        row = conn.execute(
            'SELECT sealed_key FROM escrow_imports WHERE company_id = ? AND device_code = ?',
            (args.company_id, args.source_device_code),
        ).fetchone()
        if not row:
            raise AtRestError('ATREST_VAULT_ESCROW_NOT_FOUND')
        priv = _load_escrow_private(conn, args.password, args.escrow_label)
        sealed = base64.b64decode(row['sealed_key'])
        bind = escrow_binding_aad(args.company_id, args.source_device_code)
        try:
            data_key = sealed_box_decrypt(sealed, priv, bind)
        except ValueError:
            raise AtRestError('ATREST_VAULT_UNSEAL_FAILED') from None
        pkg = build_recovered_key_package(
            data_key,
            target_pub,
            args.company_id,
            args.source_device_code,
            args.target_device_code,
        )
        if args.out:
            fd = os.open(args.out, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
            try:
                os.write(fd, pkg)
            finally:
                os.close(fd)
        else:
            sys.stdout.write(pkg.decode('utf-8'))
            sys.stdout.write('\n')
    finally:
        conn.close()
        os.unlink(tmp)
    return 0


def cmd_decrypt_data_key(args: argparse.Namespace) -> int:
    conn, tmp = open_vault_db(args.vault, args.password)
    try:
        row = conn.execute(
            'SELECT sealed_key FROM escrow_imports WHERE company_id = ? AND device_code = ?',
            (args.company_id, args.device_code),
        ).fetchone()
        if not row:
            raise AtRestError('ATREST_VAULT_ESCROW_NOT_FOUND')
        priv = _load_escrow_private(conn, args.password, args.escrow_label)
        sealed = base64.b64decode(row['sealed_key'])
        bind = escrow_binding_aad(args.company_id, args.device_code)
        data_key = sealed_box_decrypt(sealed, priv, bind)
        if args.out:
            with open(args.out, 'wb') as f:
                f.write(data_key)
            os.chmod(args.out, 0o600)
        else:
            print(data_key.hex())
    finally:
        conn.close()
        os.unlink(tmp)
    return 0


def cmd_export_encrypted(args: argparse.Namespace) -> int:
    """Write encrypted vault file for manual upload (e.g. Google Drive)."""
    shutil_copy = __import__('shutil').copy2
    shutil_copy(args.vault, args.out)
    os.chmod(args.out, 0o600)
    print(args.out)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    conn, tmp = open_vault_db(args.vault, args.password)
    try:
        q = 'SELECT company_id, device_code, imported_at FROM escrow_imports WHERE 1=1'
        params: list = []
        if args.company_id:
            q += ' AND company_id LIKE ?'
            params.append('%' + args.company_id + '%')
        if args.device_code:
            q += ' AND device_code LIKE ?'
            params.append('%' + args.device_code + '%')
        for row in conn.execute(q, params):
            print(f"{row['company_id']}\t{row['device_code']}\t{row['imported_at']}")
    finally:
        conn.close()
        os.unlink(tmp)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='af-atrest vendor key vault')
    sub = p.add_subparsers(dest='cmd', required=True)
    sp = sub.add_parser('init', help='create encrypted vault file')
    sp.add_argument('vault')
    sp.add_argument('--password', required=True)
    sp.set_defaults(func=lambda a: (init_vault(a.vault, a.password), 0)[1])

    sp = sub.add_parser('gen-escrow-key', help='generate X25519 escrow keypair')
    sp.add_argument('--vault')
    sp.add_argument('--password')
    sp.add_argument('--label', default='default')
    sp.add_argument('--private-out', help='write raw private key to path (owner choice)')
    sp.set_defaults(func=cmd_gen_escrow)

    sp = sub.add_parser('import-escrow', help='import escrow JSON blob')
    sp.add_argument('vault')
    sp.add_argument('json_path')
    sp.add_argument('--password', required=True)
    sp.set_defaults(func=cmd_import_escrow)

    sp = sub.add_parser('search', help='search imported escrow rows')
    sp.add_argument('vault')
    sp.add_argument('--password', required=True)
    sp.add_argument('--company-id')
    sp.add_argument('--device-code')
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser(
        'make-recovery-package',
        help='build recovered-key package for a new device (vendor owner only)',
    )
    sp.add_argument('vault')
    sp.add_argument('--password', required=True)
    sp.add_argument('--company-id', required=True)
    sp.add_argument('--source-device-code', required=True)
    sp.add_argument('--target-device-code', required=True)
    sp.add_argument('--target-public-hex', required=True, help='from new device transfer key')
    sp.add_argument('--escrow-label')
    sp.add_argument('--out')
    sp.set_defaults(func=cmd_make_recovery_package)

    sp = sub.add_parser('decrypt-data-key', help='decrypt escrow sealed data key')
    sp.add_argument('vault')
    sp.add_argument('--password', required=True)
    sp.add_argument('--company-id', required=True)
    sp.add_argument('--device-code', required=True)
    sp.add_argument('--escrow-label')
    sp.add_argument('--out')
    sp.set_defaults(func=cmd_decrypt_data_key)

    sp = sub.add_parser('export-encrypted', help='copy vault file for manual cloud upload')
    sp.add_argument('vault')
    sp.add_argument('out')
    sp.set_defaults(func=cmd_export_encrypted)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except AtRestError as e:
        print(e.message('en'), file=sys.stderr)
        return 1


def run_gui() -> None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog
    except ImportError:
        raise SystemExit('tkinter not available') from None

    root = tk.Tk()
    root.title('af-atrest Key Vault')
    root.geometry('420x200')

    def do_init():
        path = filedialog.asksaveasfilename(title='Vault file')
        if not path:
            return
        pw = simpledialog.askstring('Password', 'Master password', show='*')
        if not pw:
            return
        init_vault(path, pw)
        messagebox.showinfo('OK', 'Vault created')

    tk.Button(root, text='Create vault…', command=do_init).pack(pady=12)
    tk.Label(root, text='CLI: key_vault.py --help').pack()
    root.mainloop()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--gui':
        run_gui()
    else:
        raise SystemExit(main())
