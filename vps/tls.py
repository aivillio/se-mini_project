"""TLS 1.3-only server runner (VPS-SR-001).

uvicorn builds its SSLContext in ``Config.load()``; we load the config, then pin
``minimum_version = TLSv1_3`` before serving, so TLS 1.2 and older handshakes
(and plain HTTP) are refused at the socket.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import ssl
from pathlib import Path

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def make_self_signed(cert_dir: str | Path, host: str = "localhost") -> tuple[str, str]:
    """Development certificate (use a CA-issued certificate in production)."""
    cert_dir = Path(cert_dir)
    cert_dir.mkdir(parents=True, exist_ok=True)
    key_path, cert_path = cert_dir / "vps-key.pem", cert_dir / "vps-cert.pem"
    if key_path.exists() and cert_path.exists():
        return str(cert_path), str(key_path)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "VPS Dev")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(minutes=5))
            .not_valid_after(now + dt.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(host),
                                                        x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
                           critical=False)
            .sign(key, hashes.SHA256()))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(cert_path), str(key_path)


def tls13_config(app, host: str, port: int, certfile: str, keyfile: str, **kw) -> uvicorn.Config:
    config = uvicorn.Config(app, host=host, port=port, ssl_certfile=certfile, ssl_keyfile=keyfile, **kw)
    config.load()
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_3
    return config


def serve_tls(app, host: str = "127.0.0.1", port: int = 8443, cert_dir: str = "certs") -> None:  # pragma: no cover
    cert, key = make_self_signed(cert_dir)
    uvicorn.Server(tls13_config(app, host, port, cert, key)).run()
