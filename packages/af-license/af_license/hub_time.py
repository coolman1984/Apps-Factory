"""Verify signed hub calendar responses from the licence Worker (/licence/time).

v1: ``AF-LICENCE-HUB-TIME/1|<day>|<kid>`` in ``sig`` (legacy clients).
v2: ``AF-LICENCE-HUB-TIME/2|<day>|<server_time>|<kid>`` or with ``|<nonce>`` in ``sig2``.

Monotonic sealing (caller responsibility): keep ``sealed_calendar_max`` as the maximum
``calendar_day`` ever accepted for expiry. After a successful verify, set
``sealed_calendar_max = max(sealed_calendar_max, accepted_day)`` and never apply a
smaller day for licensing even if signatures verify (prevents replayed older hub days).

v2 freshness (no trust in local wall clock): when ``nonce`` is provided (client sent
``?nonce=`` on the request), the response ``nonce`` must match. Otherwise ``server_time``
must be ``>= last_server_time`` when ``last_server_time`` is set (monotonic high-water mark).
First accept with no nonce and no ``last_server_time`` only requires a valid ``sig2``.
"""
from __future__ import annotations

import base64
import re

from .ed25519_verify import verify as ed25519_verify

_NONCE_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def _b64url_decode(s: str) -> bytes | None:
    if not s or not isinstance(s, str):
        return None
    try:
        pad = '=' * (-len(s) % 4)
        return base64.urlsafe_b64decode(s + pad)
    except (ValueError, TypeError):
        return None


def _pub_bytes(trusted_entry) -> bytes | None:
    if isinstance(trusted_entry, (bytes, bytearray)) and len(trusted_entry) == 32:
        return bytes(trusted_entry)
    if not isinstance(trusted_entry, str):
        return None
    raw = _b64url_decode(trusted_entry)
    if raw and len(raw) == 32:
        return raw
    try:
        pad = '=' * (-len(trusted_entry) % 4)
        std = base64.b64decode(trusted_entry + pad)
        return std if len(std) == 32 else None
    except (ValueError, TypeError):
        return None


def hub_time_message_v1(calendar_day: str, kid: str) -> bytes:
    return f'AF-LICENCE-HUB-TIME/1|{calendar_day}|{kid}'.encode()


def hub_time_message_v2(calendar_day: str, server_time: int, kid: str, nonce: str | None = None) -> bytes:
    base = f'AF-LICENCE-HUB-TIME/2|{calendar_day}|{server_time}|{kid}'
    if nonce:
        base += f'|{nonce}'
    return base.encode()


def verify_hub_time(
    data,
    trusted_by_kid: dict,
    now=None,
    max_skew_s: int = 600,
    nonce: str | None = None,
    last_server_time: int | None = None,
):
    """Return ``(calendar_day, server_time)`` or ``None``. ``now`` / ``max_skew_s`` are reserved for callers."""
    if not data or not isinstance(data, dict):
        return None
    if data.get('signed') is False:
        return None
    day = str(data.get('calendar_day') or '').strip()
    kid = str(data.get('kid') or '').strip()
    if not day or not kid:
        return None
    pub = _pub_bytes(trusted_by_kid.get(kid))
    if pub is None:
        return None

    sig2 = data.get('sig2')
    server_time_raw = data.get('server_time')
    if sig2 is not None and server_time_raw is not None:
        try:
            server_time = int(server_time_raw)
        except (TypeError, ValueError):
            return None
        resp_nonce = data.get('nonce')
        if nonce is not None:
            if not _NONCE_RE.match(nonce) or resp_nonce != nonce:
                return None
            msg = hub_time_message_v2(day, server_time, kid, nonce)
        else:
            if last_server_time is not None and server_time < int(last_server_time):
                return None
            msg = hub_time_message_v2(day, server_time, kid, resp_nonce if resp_nonce else None)
        sig_bytes = _b64url_decode(str(sig2))
        if not sig_bytes or len(sig_bytes) != 64:
            return None
        if not ed25519_verify(pub, msg, sig_bytes):
            return None
        return day, server_time

    sig = data.get('sig')
    if not sig:
        return None
    sig_bytes = _b64url_decode(str(sig))
    if not sig_bytes or len(sig_bytes) != 64:
        return None
    if not ed25519_verify(pub, hub_time_message_v1(day, kid), sig_bytes):
        return None
    st = data.get('server_time')
    try:
        server_time = int(st) if st is not None else None
    except (TypeError, ValueError):
        server_time = None
    return day, server_time
