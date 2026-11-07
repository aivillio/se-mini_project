"""Security primitives (SRS 5.1, SAD 3.8).

* VPS-SR-004  HMAC-SHA256 signed QR ticket payloads (TicketSigner)
* VPS-SR-002  AES-256-GCM encryption of PII at rest (PIIVault) and
              Argon2id password hashing (hash_password / verify_password)
* VPS-SR-003  RFC 6238 TOTP for multi-factor authentication
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from vps.errors import SecurityViolation


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# --------------------------------------------------------------------------- tickets
class TicketSigner:
    """Signs ticket payloads as ``<base64url(json)>.<hex hmac-sha256>``."""

    def __init__(self, key_hex: str):
        self._key = bytes.fromhex(key_hex)

    def _mac(self, body: str) -> str:
        return hmac.new(self._key, body.encode(), hashlib.sha256).hexdigest()

    def sign(self, fields: dict) -> str:
        body = _b64e(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode())
        return f"{body}.{self._mac(body)}"

    def verify(self, payload: str) -> dict:
        try:
            body, sig = payload.strip().rsplit(".", 1)
        except (ValueError, AttributeError):
            raise SecurityViolation("Malformed ticket QR payload", code="TAMPERED_TICKET") from None
        if not hmac.compare_digest(self._mac(body), sig):
            raise SecurityViolation("Ticket signature mismatch - possible counterfeit", code="TAMPERED_TICKET")
        try:
            return json.loads(_b64d(body))
        except (ValueError, json.JSONDecodeError):   # pragma: no cover - MAC already verified
            raise SecurityViolation("Undecodable ticket body", code="TAMPERED_TICKET") from None


# --------------------------------------------------------------------------- PII
class PIIVault:
    """AES-256-GCM encryption for PII plus a keyed fingerprint for equality lookups."""

    PREFIX = "v1:"

    def __init__(self, key_hex: str):
        key = bytes.fromhex(key_hex)
        if len(key) != 32:
            raise ValueError("PII key must be 256 bits (64 hex chars)")
        self._aead = AESGCM(key)
        self._fp_key = hashlib.sha256(b"fingerprint:" + key).digest()

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        ct = self._aead.encrypt(nonce, plaintext.encode(), b"vps-pii")
        return self.PREFIX + _b64e(nonce + ct)

    def decrypt(self, token: str) -> str:
        if not token.startswith(self.PREFIX):
            raise ValueError("Unknown ciphertext format")
        raw = _b64d(token[len(self.PREFIX):])
        return self._aead.decrypt(raw[:12], raw[12:], b"vps-pii").decode()

    def fingerprint(self, value: str) -> str:
        return hmac.new(self._fp_key, value.encode(), hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------- passwords
_hasher = PasswordHasher()  # Argon2id, RFC 9106 low-memory profile defaults


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    return _hasher.hash(password)


def verify_password(pw_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(pw_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# --------------------------------------------------------------------------- TOTP
def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp(secret_b32: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8), casefold=True)
    counter = int((time.time() if at is None else at) // step)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def verify_totp(secret_b32: str, code: str, at: float | None = None, window: int = 1, step: int = 30) -> bool:
    if not code or not code.isdigit():
        return False
    now = time.time() if at is None else at
    return any(
        hmac.compare_digest(totp(secret_b32, now + i * step, step), code) for i in range(-window, window + 1)
    )


def provisioning_uri(secret_b32: str, username: str, issuer: str = "VPS") -> str:
    return f"otpauth://totp/{issuer}:{username}?secret={secret_b32}&issuer={issuer}"


def token_hash(token: str) -> str:
    """Session tokens are stored hashed so a DB leak does not leak live sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


# --------------------------------------------------------------------------- service getters
def get_signer(ctx) -> TicketSigner:
    return ctx.service("signer", lambda c: TicketSigner(c.settings.ticket_hmac_key))


def get_vault(ctx) -> PIIVault:
    return ctx.service("vault", lambda c: PIIVault(c.settings.pii_aes_key))
