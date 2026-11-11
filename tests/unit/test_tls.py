"""Unit tests - TLS 1.3 server configuration (VPS-SR-001). Owner: Angelo Arakal."""

import ssl

import pytest

from vps.tls import make_self_signed, tls13_config


@pytest.mark.tc("TC-SEC-01")
@pytest.mark.req("VPS-SR-001")
def test_self_signed_cert_created_once(tmp_path):
    cert, key = make_self_signed(tmp_path)
    mtime = (tmp_path / "vps-cert.pem").stat().st_mtime_ns
    assert make_self_signed(tmp_path) == (cert, key)              # re-used, not regenerated
    assert (tmp_path / "vps-cert.pem").stat().st_mtime_ns == mtime


@pytest.mark.tc("TC-SEC-01")
def test_config_pins_tls13(tmp_path):
    cert, key = make_self_signed(tmp_path)
    cfg = tls13_config(lambda *a: None, "127.0.0.1", 0, cert, key)
    assert cfg.ssl.minimum_version == ssl.TLSVersion.TLSv1_3
