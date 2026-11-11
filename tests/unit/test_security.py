"""Unit tests - vps.security (VPS-SR-002, VPS-SR-003, VPS-SR-004). Owner: Angelo Arakal."""

import pytest
from cryptography.exceptions import InvalidTag

from vps.errors import SecurityViolation
from vps.security import (
    PIIVault,
    TicketSigner,
    hash_password,
    new_totp_secret,
    provisioning_uri,
    token_hash,
    totp,
    verify_password,
    verify_totp,
)

KEY = "11" * 32


@pytest.mark.tc("TC-SEC-04")
@pytest.mark.req("VPS-SR-004")
class TestTicketSigner:
    def test_roundtrip(self):
        s = TicketSigner(KEY)
        payload = s.sign({"tid": "abc", "slot": "L1-C001"})
        assert s.verify(payload) == {"tid": "abc", "slot": "L1-C001"}

    def test_signature_is_hmac_sha256_hex(self):
        sig = TicketSigner(KEY).sign({"a": 1}).rsplit(".", 1)[1]
        assert len(sig) == 64 and int(sig, 16) >= 0

    def test_tampered_body_rejected(self):
        s = TicketSigner(KEY)
        body, sig = s.sign({"tid": "abc"}).rsplit(".", 1)
        forged = s.sign({"tid": "xyz"}).rsplit(".", 1)[0]
        with pytest.raises(SecurityViolation) as e:
            s.verify(f"{forged}.{sig}")
        assert e.value.code == "TAMPERED_TICKET"

    def test_tampered_signature_rejected(self):
        s = TicketSigner(KEY)
        p = s.sign({"tid": "abc"})
        with pytest.raises(SecurityViolation):
            s.verify(p[:-1] + ("0" if p[-1] != "0" else "1"))

    def test_other_key_rejected(self):
        p = TicketSigner(KEY).sign({"tid": "abc"})
        with pytest.raises(SecurityViolation):
            TicketSigner("22" * 32).verify(p)

    @pytest.mark.parametrize("bad", ["", "no-dot-here", None])
    def test_malformed_payload(self, bad):
        with pytest.raises(SecurityViolation):
            TicketSigner(KEY).verify(bad)


@pytest.mark.tc("TC-SEC-02")
@pytest.mark.req("VPS-SR-002")
class TestPIIVault:
    def test_encrypt_decrypt(self):
        v = PIIVault(KEY)
        ct = v.encrypt("KA01AB1234")
        assert ct.startswith("v1:") and "KA01AB1234" not in ct
        assert v.decrypt(ct) == "KA01AB1234"

    def test_nonce_is_random(self):
        v = PIIVault(KEY)
        assert v.encrypt("same") != v.encrypt("same")

    def test_wrong_key_cannot_decrypt(self):
        ct = PIIVault(KEY).encrypt("secret")
        with pytest.raises(InvalidTag):
            PIIVault("22" * 32).decrypt(ct)

    def test_unknown_format(self):
        with pytest.raises(ValueError):
            PIIVault(KEY).decrypt("plain-text")

    def test_key_must_be_256_bit(self):
        with pytest.raises(ValueError):
            PIIVault("11" * 16)

    def test_fingerprint_deterministic_and_keyed(self):
        assert PIIVault(KEY).fingerprint("X") == PIIVault(KEY).fingerprint("X")
        assert PIIVault(KEY).fingerprint("X") != PIIVault("22" * 32).fingerprint("X")


@pytest.mark.tc("TC-SEC-02")
@pytest.mark.req("VPS-SR-002")
class TestPasswords:
    def test_argon2id_hash(self):
        h = hash_password("Correct#Horse1")
        assert h.startswith("$argon2id$")
        assert verify_password(h, "Correct#Horse1")
        assert not verify_password(h, "wrong-password")

    def test_short_password_rejected(self):
        with pytest.raises(ValueError):
            hash_password("short")

    def test_garbage_hash_is_false(self):
        assert verify_password("not-a-hash", "whatever1") is False


@pytest.mark.tc("TC-SEC-03")
@pytest.mark.req("VPS-SR-003")
class TestTOTP:
    # RFC 6238 Appendix B test vector (SHA1, T=59 s) -> 94287082; 6-digit form = 287082
    RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"

    def test_rfc6238_vector(self):
        assert totp(self.RFC_SECRET, at=59, digits=8) == "94287082"
        assert totp(self.RFC_SECRET, at=59) == "287082"

    def test_verify_window(self):
        s = new_totp_secret()
        code = totp(s, at=1_000_000)
        assert verify_totp(s, code, at=1_000_000)
        assert verify_totp(s, code, at=1_000_000 + 30)        # one step of clock drift
        assert not verify_totp(s, code, at=1_000_000 + 120)

    @pytest.mark.parametrize("bad", ["", None, "12ab56"])
    def test_non_numeric_rejected(self, bad):
        assert not verify_totp(new_totp_secret(), bad)

    def test_provisioning_uri(self):
        assert provisioning_uri("ABC", "admin").startswith("otpauth://totp/VPS:admin?secret=ABC")


def test_token_hash_is_sha256():
    assert len(token_hash("t")) == 64 and token_hash("t") != "t"
