"""Verify signed hub calendar responses from the licence Worker (/licence/time).

v1 (``allow_v1`` only, deprecated): never advances ``sealed_day``. Without ``sealed_day``, always
returns ``None`` (never trust an unsealed v1 day). With ``sealed_day``, returns ``sealed_day`` only
when the signed day is on or after ``sealed_day``; never advances. v1 never returns ``server_time``
and must not be used to advance ``last_server_time``.

v2: ``AF-LICENCE-HUB-TIME/2|<day>|<server_time>|<kid>`` or with ``|<nonce>`` in ``sig2``.

Client persistence (required for safe expiry):

- ``last_server_time``: maximum ``server_time`` from any **accepted** v2 response. Update after
  each successful verify to the returned ``server_time`` (when not ``None``).
- ``sealed_day`` (``licence_hub_sealed_calendar_max``): maximum **business calendar day** ever
  applied to licensing. After each successful verify, set
  ``sealed_day = max(sealed_day, accepted_calendar_day)`` when ``sealable`` is true.

v2 is required unless ``allow_v1=True``.

**Nonce mode (recommended):** the client sends a fresh random ``nonce`` on each request; the response
``nonce`` must match (additional binding, not a replay bypass). When ``last_server_time`` is known,
``server_time`` must still be **strictly greater** than ``last_server_time`` in both nonce and
no-nonce modes. Re-verifying the same v2 body after persisting fails for that reason. Calendar day is
clamped to ``[sealed_day, sealed_day + max_jump_days]`` when ``sealed_day`` is set. Returns
``server_time`` for persistence.

**No-nonce mode:** same ``server_time`` strict-increase rule; there is **no** upper bound on the gap
so honest clients offline for weeks can recover. Day clamped the same way. Persist the returned
``server_time``. A far-future ``server_time`` can only be produced with the hub private key.
"""
from __future__ import annotations

import base64
import re
from datetime import date, timedelta
from typing import NamedTuple

from .ed25519_verify import verify as ed25519_verify

_NONCE_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


class HubTimeVerifyResult(NamedTuple):
    calendar_day: str
    server_time: int | None
    day_jump_capped: bool
    version: int
    sealable: bool


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


def _parse_calendar_day(day: str) -> date | None:
    try:
        return date.fromisoformat(day)
    except ValueError:
        return None


def _apply_sealed_day(day: str, sealed_day: str | None, max_jump_days: int) -> tuple[str, bool] | None:
    if not sealed_day:
        return day, False
    sealed = _parse_calendar_day(sealed_day)
    parsed = _parse_calendar_day(day)
    if sealed is None or parsed is None:
        return None
    if parsed < sealed:
        return None
    cap = sealed + timedelta(days=max_jump_days)
    if parsed > cap:
        return cap.isoformat(), True
    return day, False


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
    *,
    last_server_time: int | None = None,
    sealed_day: str | None = None,
    max_jump_days: int = 7,
    nonce: str | None = None,
    allow_v1: bool = False,
) -> HubTimeVerifyResult | None:
    """Verify hub time JSON; return ``HubTimeVerifyResult`` or ``None``.

    See module docstring for ``last_server_time`` / ``sealed_day`` persistence rules.
    """
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
        if last_server_time is not None:
            lst = int(last_server_time)
            if server_time <= lst:
                return None
        if nonce is not None:
            if not _NONCE_RE.match(nonce) or resp_nonce != nonce:
                return None
            msg = hub_time_message_v2(day, server_time, kid, nonce)
        else:
            msg = hub_time_message_v2(day, server_time, kid, resp_nonce if resp_nonce else None)
        sig_bytes = _b64url_decode(str(sig2))
        if not sig_bytes or len(sig_bytes) != 64:
            return None
        if not ed25519_verify(pub, msg, sig_bytes):
            return None
        sealed = _apply_sealed_day(day, sealed_day, max_jump_days)
        if sealed is None:
            return None
        out_day, capped = sealed
        return HubTimeVerifyResult(out_day, server_time, capped, 2, True)

    if not allow_v1:
        return None

    sig = data.get('sig')
    if not sig:
        return None
    sig_bytes = _b64url_decode(str(sig))
    if not sig_bytes or len(sig_bytes) != 64:
        return None
    if not ed25519_verify(pub, hub_time_message_v1(day, kid), sig_bytes):
        return None
    if sealed_day:
        sealed = _parse_calendar_day(sealed_day)
        parsed = _parse_calendar_day(day)
        if sealed is None or parsed is None or parsed < sealed:
            return None
        return HubTimeVerifyResult(sealed.isoformat(), None, False, 1, False)
    return None
