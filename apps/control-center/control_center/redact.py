"""Removes personal data and secrets from diagnostic text before storage or any AI use (SUP-01, AI-04).
The customer app also previews the bundle before sending; this is the server-side second line."""
from __future__ import annotations
import re

PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?20|0)?1[0125]\d{8}(?!\d)"), "[PHONE]"),          # Egyptian mobiles
    (re.compile(r"(?<!\d)[23]\d{13}(?!\d)"), "[NATIONAL_ID]"),                 # Egyptian national ID
    (re.compile(r"(?i)\b(bearer|token|password|passwd|secret|api[_-]?key)\b\s*[:=]\s*\S+"), r"\1=[SECRET]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[PRIVATE_KEY]"),
    (re.compile(r"\b(?:cc|ins|ven)_[A-Za-z0-9_-]{20,}"), "[TOKEN]"),
]


def redact(value):
    if isinstance(value, str):
        for pattern, replacement in PATTERNS:
            value = pattern.sub(replacement, value)
        return value
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    return value
