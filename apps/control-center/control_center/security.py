"""Random high-entropy tokens, stored only as SHA-256 hashes (shown once at creation)."""
from __future__ import annotations
import hashlib
import hmac
import secrets


def new_token(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def same(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def grant_code() -> str:
    return "-".join(f"{secrets.randbelow(1000):03d}" for _ in range(3))
