"""Signed licence and update-manifest documents (Ed25519 via the vetted `cryptography` library).

Vendor side: issue() with the private key, which never ships.
Customer app: verify() with embedded public keys only.
Failure never touches customer data: the app maps "expired" and invalid results to read/export/backup mode.
"""
from __future__ import annotations
import base64
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

FORMAT = "af-signed/1"
ALG = "Ed25519"  # fixed here, never read from the document (blocks algorithm downgrade)
PURPOSES = {"licence", "update"}  # separate keys per purpose: a leaked update key cannot mint licences
REQUIRED_LICENCE_CLAIMS = ("licence_id", "product", "customer", "edition", "features", "issued", "expires")


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def key_id(public_raw: bytes) -> str:
    return hashlib.sha256(public_raw).hexdigest()[:16]


def generate_keypair() -> tuple[bytes, str, str]:
    """Return (private_pem, public_key_b64, kid). Store the PEM offline; embed only the public key."""
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return pem, _b64(raw), key_id(raw)


def issue(private_pem: bytes, purpose: str, payload: dict) -> dict:
    if purpose not in PURPOSES:
        raise ValueError("Unknown purpose")
    if purpose == "licence":
        missing = [k for k in REQUIRED_LICENCE_CLAIMS if k not in payload]
        if missing:
            raise ValueError("Missing licence claims: " + ", ".join(missing))
    private = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError("Signing key must be Ed25519")
    raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    kid = key_id(raw)
    signature = private.sign(canonical({"format": FORMAT, "kid": kid, "purpose": purpose, "payload": payload}))
    return {"format": FORMAT, "alg": ALG, "kid": kid, "purpose": purpose, "payload": payload, "sig": _b64(signature)}


@dataclass
class Result:
    valid: bool
    state: str  # active | grace | expired | not_yet_valid | invalid
    reason: str = ""
    claims: dict = field(default_factory=dict)

    @property
    def full_access(self) -> bool:
        return self.valid and self.state in {"active", "grace"}


def _when(value: str) -> datetime:
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def verify(document: dict, trusted_keys: dict[str, str], purpose: str, product: str,
           now: datetime | None = None, device_id: str | None = None) -> Result:
    """trusted_keys maps kid -> public key (base64url raw). Never raises on bad input."""
    bad = lambda reason: Result(False, "invalid", reason)  # noqa: E731
    try:
        if not isinstance(document, dict) or document.get("format") != FORMAT:
            return bad("unknown_format")
        if document.get("alg") != ALG:
            return bad("unexpected_algorithm")
        if document.get("purpose") != purpose:
            return bad("wrong_purpose")
        kid, payload = document.get("kid"), document.get("payload")
        if kid not in trusted_keys:
            return bad("unknown_key")
        if not isinstance(payload, dict):
            return bad("bad_payload")
        public = Ed25519PublicKey.from_public_bytes(_unb64(trusted_keys[kid]))
        public.verify(_unb64(document.get("sig", "")),
                      canonical({"format": FORMAT, "kid": kid, "purpose": purpose, "payload": payload}))
    except (InvalidSignature, ValueError, TypeError, KeyError):
        return bad("bad_signature")
    if payload.get("product") != product:
        return Result(False, "invalid", "wrong_product")
    if purpose == "update":
        return Result(True, "active", claims=payload)
    devices = payload.get("devices")
    if devices is not None and not isinstance(devices, list):
        return Result(False, "invalid", "bad_devices", payload)
    if devices and device_id not in devices:
        return Result(False, "invalid", "device_not_licensed", payload)
    try:
        now = now or datetime.now(timezone.utc)
        if "not_before" in payload and now < _when(payload["not_before"]):
            return Result(True, "not_yet_valid", claims=payload)
        expires = _when(payload["expires"])
        grace = timedelta(days=int(payload.get("grace_days", 0)))
    except (ValueError, TypeError, KeyError):
        return Result(False, "invalid", "bad_dates", payload)
    if now <= expires:
        return Result(True, "active", claims=payload)
    if now <= expires + grace:
        return Result(True, "grace", claims=payload)
    return Result(True, "expired", "renew_to_unlock_paid_actions", payload)


def clock_rolled_back(now: datetime, last_seen: datetime, tolerance_hours: int = 24) -> bool:
    """The app stores the latest time it has seen (in its database); a big step back means a tampered clock."""
    return now < last_seen - timedelta(hours=tolerance_hours)


def fingerprint(*parts: str) -> str:
    """Stable device ID from values the app chooses (e.g. Windows MachineGuid + install ID). Never personal data."""
    cleaned = [p.strip().lower() for p in parts if p and p.strip()]
    if not cleaned:
        raise ValueError("fingerprint needs at least one stable value")
    return hashlib.sha256("|".join(cleaned).encode("utf-8")).hexdigest()[:32]
