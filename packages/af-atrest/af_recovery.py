"""Vendor-mediated restore on a new device (Key Vault recovered-key package)."""

from __future__ import annotations

import os

import af_atrest as core
from af_crypto_box import (
    build_recovered_key_package,
    parse_recovered_key_package,
    unwrap_recovered_key_package,
    load_x25519_private,
    generate_escrow_keypair,
)
from af_errors import AtRestError

TRANSFER_KEY_NAME = 'atrest.device-transfer.key'


def _transfer_key_path(data_dir: str) -> str:
    return os.path.join(os.path.abspath(data_dir), TRANSFER_KEY_NAME)


def _read_transfer_private(path: str) -> bytes:
    try:
        with open(path, 'rb') as f:
            blob = f.read()
    except OSError as e:
        raise AtRestError('ATREST_DEVICE_TRANSFER_KEY_BAD', str(e)) from None
    if blob.startswith(core.MAGIC_DEVICE_TRANSFER):
        try:
            return core.unwrap_device_transfer_private(blob)
        except ValueError as e:
            raise AtRestError('ATREST_DEVICE_TRANSFER_KEY_BAD', str(e)) from None
    if len(blob) == 32:
        wrapped = core.wrap_device_transfer_private(blob)
        core._write_0600(path, wrapped)
        return blob
    raise AtRestError('ATREST_DEVICE_TRANSFER_KEY_BAD', 'length')


def ensure_device_transfer_key(data_dir: str) -> tuple[bytes, bytes]:
    """Create or load the one-time X25519 keypair for vendor recovery packages."""
    path = _transfer_key_path(data_dir)
    if os.path.isfile(path):
        priv = _read_transfer_private(path)
        pub = load_x25519_private(priv).public_key().public_bytes_raw()
        return priv, pub
    priv, pub = generate_escrow_keypair()
    core._write_0600(path, core.wrap_device_transfer_private(priv))
    return priv, pub


def device_transfer_public_hex(data_dir: str) -> str:
    _, pub = ensure_device_transfer_key(data_dir)
    return pub.hex()


def verify_backup_with_data_key(backup_path: str, data_key: bytes) -> None:
    """Decrypt backup archive with raw key; raises AtRestError on failure."""
    if not os.path.isfile(backup_path):
        raise AtRestError('ATREST_BACKUP_MISMATCH', backup_path)
    if not core.is_aead(backup_path):
        raise AtRestError('ATREST_BACKUP_NOT_ENCRYPTED')
    try:
        info = core._read_header(backup_path)
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

        with open(backup_path, 'rb') as f:
            blob = f.read()
        nonce, meta, ct = core._split_sealed(blob)
        if meta != info['_meta_bytes']:
            raise AtRestError('ATREST_BACKUP_MISMATCH')
        ChaCha20Poly1305(data_key).decrypt(nonce, ct, meta)
    except AtRestError:
        raise
    except Exception:
        raise AtRestError('ATREST_BACKUP_AUTH_FAILED') from None


def _load_package(recovered_key_package: str | bytes) -> dict:
    if isinstance(recovered_key_package, (bytes, bytearray)):
        raw = bytes(recovered_key_package)
    else:
        try:
            with open(recovered_key_package, 'rb') as f:
                raw = f.read()
        except OSError as e:
            raise AtRestError('ATREST_RECOVERED_PACKAGE_BAD_FORMAT', str(e)) from None
    try:
        return parse_recovered_key_package(raw)
    except ValueError as e:
        raise AtRestError('ATREST_RECOVERED_PACKAGE_BAD_FORMAT', str(e)) from None


def restore_on_new_device(
    data_dir: str,
    backup_path: str,
    recovered_key_package: str | bytes,
) -> None:
    """
    Apply a vendor Key Vault recovered-key package on a new device, verify backup,
    and install the data key under local DPAPI wrap.
    """
    pkg = _load_package(recovered_key_package)
    priv, _pub = ensure_device_transfer_key(data_dir)
    try:
        data_key = unwrap_recovered_key_package(pkg, priv)
    except ValueError as e:
        msg = str(e)
        if 'sealed decrypt' in msg:
            raise AtRestError('ATREST_RECOVERED_PACKAGE_TAMPERED', msg) from None
        raise AtRestError('ATREST_RECOVERED_PACKAGE_BAD_FORMAT', msg) from None
    verify_backup_with_data_key(backup_path, data_key)
    core.install_recovered_data_key(data_dir, data_key)


# Re-export for Key Vault and tests
__all__ = [
    'build_recovered_key_package',
    'device_transfer_public_hex',
    'ensure_device_transfer_key',
    'restore_on_new_device',
    'verify_backup_with_data_key',
]
