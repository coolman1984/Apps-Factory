"""X25519 sealed-box for vendor escrow and recovered-key packages; scrypt helpers for the vault."""

from __future__ import annotations

import base64
import json
import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC_SEALED = b'AFSEAL1'
SCRYPT_N = 2 ** 17
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_SALT_LEN = 16
RECOVERED_KEY_V = 1
SEALED_V = 1


def _scrypt_key(password: bytes, salt: bytes, n: int, r: int, p: int) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=n, r=r, p=p)
    return kdf.derive(password)


def load_x25519_public(raw: bytes) -> X25519PublicKey:
    if len(raw) != 32:
        raise ValueError('public key must be 32 bytes')
    return X25519PublicKey.from_public_bytes(raw)


def load_x25519_private(raw: bytes) -> X25519PrivateKey:
    if len(raw) != 32:
        raise ValueError('private key must be 32 bytes')
    return X25519PrivateKey.from_private_bytes(raw)


def escrow_binding_aad(company_id: str, device_code: str) -> bytes:
    """Authenticated metadata bound into vendor escrow sealed boxes."""
    return json.dumps(
        {'company_id': str(company_id), 'device_code': str(device_code)},
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    ).encode('utf-8')


def _sealed_aad(eph_pub: bytes, binding_aad: bytes | None) -> bytes:
    extra = binding_aad if binding_aad is not None else b''
    return MAGIC_SEALED + eph_pub + extra


def sealed_box_encrypt(
    plaintext: bytes,
    recipient_public: bytes,
    binding_aad: bytes | None = None,
) -> bytes:
    """Seal ``plaintext`` to a 32-byte X25519 public key (NaCl-style, no PyNaCl)."""
    pub = load_x25519_public(recipient_public)
    ephemeral = X25519PrivateKey.generate()
    eph_pub = ephemeral.public_key().public_bytes_raw()
    shared = ephemeral.exchange(pub)
    dk = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=eph_pub,
        info=b'af-atrest-sealed-box-v1',
    )
    sym = dk.derive(shared)
    aad = _sealed_aad(eph_pub, binding_aad)
    nonce = secrets.token_bytes(12)
    ct = ChaCha20Poly1305(sym).encrypt(nonce, plaintext, aad)
    return MAGIC_SEALED + eph_pub + nonce + ct


def sealed_box_decrypt(
    blob: bytes,
    recipient_private: bytes,
    binding_aad: bytes | None = None,
) -> bytes:
    blob = bytes(blob)
    if not blob.startswith(MAGIC_SEALED) or len(blob) < len(MAGIC_SEALED) + 32 + 12 + 16:
        raise ValueError('bad sealed blob')
    eph_pub = blob[len(MAGIC_SEALED):len(MAGIC_SEALED) + 32]
    nonce = blob[len(MAGIC_SEALED) + 32:len(MAGIC_SEALED) + 32 + 12]
    ct = blob[len(MAGIC_SEALED) + 32 + 12:]
    priv = load_x25519_private(recipient_private)
    pub = load_x25519_public(eph_pub)
    shared = priv.exchange(pub)
    dk = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=eph_pub,
        info=b'af-atrest-sealed-box-v1',
    )
    sym = dk.derive(shared)
    aad = _sealed_aad(eph_pub, binding_aad)
    try:
        return ChaCha20Poly1305(sym).decrypt(nonce, ct, aad)
    except Exception:
        raise ValueError('sealed decrypt failed') from None


def generate_escrow_keypair() -> tuple[bytes, bytes]:
    priv = X25519PrivateKey.generate()
    return priv.private_bytes_raw(), priv.public_key().public_bytes_raw()


def build_recovered_key_package(
    data_key: bytes,
    target_public: bytes,
    company_id: str,
    source_device_code: str,
    target_device_code: str,
) -> bytes:
    """JSON package sealed to the new device's transfer public key (vendor Key Vault output)."""
    if len(data_key) != 32:
        raise ValueError('data_key must be 32 bytes')
    sealed = sealed_box_encrypt(data_key, target_public)
    doc = {
        'v': RECOVERED_KEY_V,
        'kind': 'af-atrest-recovered-key',
        'company_id': str(company_id),
        'source_device_code': str(source_device_code),
        'target_device_code': str(target_device_code),
        'sealed_key': base64.b64encode(sealed).decode('ascii'),
    }
    return json.dumps(doc, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def parse_recovered_key_package(blob: bytes) -> dict:
    try:
        doc = json.loads(blob.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError('bad json') from None
    if not isinstance(doc, dict) or doc.get('kind') != 'af-atrest-recovered-key':
        raise ValueError('bad kind')
    if int(doc.get('v', 0)) != RECOVERED_KEY_V:
        raise ValueError('bad version')
    if not doc.get('sealed_key'):
        raise ValueError('missing sealed_key')
    return doc


def unwrap_recovered_key_package(pkg: dict, target_private: bytes) -> bytes:
    sealed = base64.b64decode(pkg['sealed_key'])
    plain = sealed_box_decrypt(sealed, target_private)
    if len(plain) != 32:
        raise ValueError('bad key length')
    return plain
