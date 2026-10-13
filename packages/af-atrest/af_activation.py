"""Activation: mandatory vendor escrow enqueue (offline-safe outbox)."""

from __future__ import annotations

import os

import af_atrest as core
from af_escrow import escrow_package, load_vendor_public_key_hex
from af_errors import AtRestError
from af_migrate import migrate_to_encrypted
from af_sync import enqueue_escrow


def activate_encrypted_storage(
    data_dir: str,
    vendor_public_key: str | bytes,
    company_id: str,
    device_code: str,
    worker_url: str,
    company_token: str,
    *,
    migrate_plaintext: bool = True,
    sqlcipher_driver=None,
) -> None:
    """
    Product activation hook after ``AF_ENCRYPT=1``: ensure encrypted data dir,
    then **mandatory** escrow of the data key to the vendor worker (queued if offline).
    """
    data_dir = os.path.abspath(data_dir)
    if migrate_plaintext:
        try:
            migrate_to_encrypted(data_dir, sqlcipher_driver=sqlcipher_driver)
        except AtRestError as e:
            if e.code != 'ATREST_MIGRATE_ALREADY_ENCRYPTED':
                raise
    if isinstance(vendor_public_key, (bytes, bytearray)):
        pub = bytes(vendor_public_key)
        if len(pub) != 32:
            raise AtRestError('ATREST_ESCROW_BAD_PUBLIC_KEY', 'length')
    else:
        pub = load_vendor_public_key_hex(str(vendor_public_key))
    data_key = core.data_key(data_dir)
    pkg = escrow_package(data_key, pub, company_id, device_code)
    enqueue_escrow(data_dir, worker_url, company_token, pkg)
