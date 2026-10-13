"""Escrow package sealing and upload client (transport injected in tests)."""

from __future__ import annotations

import base64
import json
import os
from typing import Callable, Protocol

from af_crypto_box import escrow_binding_aad, sealed_box_encrypt
from af_errors import AtRestError


class Transport(Protocol):
    def post(self, url: str, headers: dict, body: bytes) -> tuple[int, bytes]: ...


def escrow_package(
    data_key: bytes,
    vendor_public_key: bytes,
    company_id: str,
    device_code: str,
) -> dict:
    """JSON-serializable blob; data key sealed to vendor X25519 public key only."""
    if len(data_key) != 32:
        raise AtRestError('ATREST_ESCROW_SEAL_FAILED', 'key length')
    try:
        bind = escrow_binding_aad(company_id, device_code)
        sealed = sealed_box_encrypt(data_key, vendor_public_key, bind)
    except ValueError as e:
        raise AtRestError('ATREST_ESCROW_BAD_PUBLIC_KEY', str(e)) from None
    return {
        'v': 1,
        'company_id': str(company_id),
        'device_code': str(device_code),
        'sealed_key': base64.b64encode(sealed).decode('ascii'),
    }


def escrow_package_json(
    data_key: bytes,
    vendor_public_key: bytes,
    company_id: str,
    device_code: str,
) -> bytes:
    pkg = escrow_package(data_key, vendor_public_key, company_id, device_code)
    return json.dumps(pkg, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def upload_escrow(
    worker_url: str,
    company_token: str,
    company_id: str,
    package: dict,
    transport: Transport | None = None,
) -> None:
    """POST escrow JSON to worker ``/escrow``."""
    url = worker_url.rstrip('/') + '/escrow'
    body = json.dumps(package, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    headers = {
        'content-type': 'application/json',
        'x-af-company-token': company_token,
        'x-af-company-id': str(company_id),
    }
    if transport is None:
        raise AtRestError('ATREST_ESCROW_UPLOAD_FAILED', 'no transport')
    status, _resp = transport.post(url, headers, body)
    if status == 401 or status == 403:
        raise AtRestError('ATREST_ESCROW_UPLOAD_REJECTED', str(status))
    if status < 200 or status >= 300:
        raise AtRestError('ATREST_ESCROW_UPLOAD_FAILED', str(status))


def load_vendor_public_key_hex(path_or_hex: str) -> bytes:
    raw = path_or_hex.strip()
    if os.path.isfile(raw):
        with open(raw, 'rb') as f:
            raw = f.read().decode('utf-8').strip()
    if raw.startswith('0x'):
        raw = raw[2:]
    return bytes.fromhex(raw)
