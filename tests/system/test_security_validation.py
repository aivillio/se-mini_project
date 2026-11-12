"""Security validation (Test Plan 5.4: VPS-SR-001..005, VPS-NF-004). Owner: Himansh Ahuja (QA Lead)."""

import http.client
import socket
import ssl

import pytest

from tests.conftest import LiveServer, free_port
from vps.config import Settings
from vps.context import Context
from vps.main import create_app
from vps.tls import make_self_signed, tls13_config

pytestmark = pytest.mark.system


@pytest.fixture(scope="module")
def tls_server(tmp_path_factory):
    cert, key = make_self_signed(tmp_path_factory.mktemp("certs"))
    settings = Settings(db_path=":memory:", edge_db_path=":memory:", require_tls=True)
    app = create_app(ctx=Context(settings))
    port = free_port()
    with LiveServer(app, tls13_config(app, "127.0.0.1", port, cert, key, log_level="warning")) as srv:
        yield srv, cert


def _ctx(cert, max_version=None, min_version=None):
    c = ssl.create_default_context(cafile=cert)
    if max_version:
        c.maximum_version = max_version
    if min_version:
        c.minimum_version = min_version
    return c


@pytest.mark.tc("TC-SEC-01")
@pytest.mark.req("VPS-SR-001")
class TestTLS:
    def test_tls13_handshake_succeeds(self, tls_server):
        srv, cert = tls_server
        conn = http.client.HTTPSConnection("localhost", srv.port, context=_ctx(cert), timeout=5)
        conn.request("GET", "/api/v1/lanes")
        resp = conn.getresponse()
        assert resp.status == 200
        assert conn.sock.version() == "TLSv1.3"
        assert "max-age" in resp.getheader("Strict-Transport-Security")
        conn.close()

    @pytest.mark.parametrize("version", [ssl.TLSVersion.TLSv1_2])
    def test_older_tls_rejected(self, tls_server, version):
        srv, cert = tls_server
        ctx = _ctx(cert, max_version=version, min_version=ssl.TLSVersion.TLSv1_2)
        with pytest.raises(ssl.SSLError):
            with socket.create_connection(("127.0.0.1", srv.port), timeout=5) as raw:
                with ctx.wrap_socket(raw, server_hostname="localhost"):
                    pass

    def test_plain_http_rejected(self, tls_server):
        srv, _ = tls_server
        conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
        try:
            conn.request("GET", "/health")
            status = conn.getresponse().status
        except (ConnectionError, http.client.HTTPException, OSError):
            status = None
        assert status != 200        # handshake garbage -> connection dropped / 400 from TLS layer


@pytest.mark.tc("TC-SEC-02", "TC-SEC-06")
@pytest.mark.req("VPS-SR-002", "VPS-NF-004")
def test_database_dump_has_no_plaintext_pii_or_pan(client, ctx, clock, admin_headers):
    t = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA05MN4821", "vehicle_category": "4W"}).json()
    client.post("/api/v1/reservations", json={"plate_number": "MH12XY9090", "vehicle_category": "4W",
                                              "start_time": clock.advance(minutes=1).isoformat(), "contact": "9876543210"})
    clock.advance(hours=1)
    co = client.post("/api/v1/egress/checkout", json={"ticket_id": t["ticket_id"], "payment_method": "card",
                                                       "card_number": "4111 1111 1111 1111"}).json()
    client.post(f"/api/v1/payments/{co['order']['order_id']}/sandbox-pay", json={})
    client.post(f"/api/v1/receipts/{t['ticket_id']}/send", json={"channel": "SMS", "recipient": "9123456780"})
    dump = "\n".join(ctx.db._conn.iterdump())
    for secret in ("KA05MN4821", "MH12XY9090", "9876543210", "9123456780", "4111111111111111", "4111 1111 1111 1111",
                   ctx.settings.admin_password, ctx.settings.admin_totp_secret):
        assert secret not in dump, secret
    assert "$argon2id$" in dump


@pytest.mark.tc("TC-SEC-03")
@pytest.mark.req("VPS-SR-003")
@pytest.mark.parametrize("method,path,body,allowed", [
    ("PUT", "/api/v1/admin/tariffs/4W", {"first_hour": 40, "per_hour": 30, "daily_cap": 400}, {"admin"}),
    ("GET", "/api/v1/admin/audit", None, {"admin", "manager"}),
    ("GET", "/api/v1/reports/revenue", None, {"admin", "manager"}),
    ("POST", "/api/v1/auth/users", {"username": "x1", "password": "Passw0rd!x"}, {"admin"}),
    ("POST", "/api/v1/admin/barrier-override", {"lane_id": "EXIT-1", "reason": "rbac test"}, {"admin", "attendant"}),
    ("GET", "/api/v1/alerts", None, {"admin", "manager", "attendant"}),
])
def test_rbac_matrix(client, admin_headers, manager_headers, attendant_headers, method, path, body, allowed):
    roles = {"admin": admin_headers, "manager": manager_headers, "attendant": attendant_headers}
    assert client.request(method, path, json=body).status_code == 401
    for name, headers in roles.items():
        code = client.request(method, path, json=body, headers=headers).status_code
        assert (code < 400) == (name in allowed), (name, code)


@pytest.mark.tc("TC-SEC-03")
def test_mfa_enforced_over_api(client, ctx):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": ctx.settings.admin_password})
    assert r.status_code == 401 and r.json()["error"]["code"] == "MFA_REQUIRED"
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": ctx.settings.admin_password,
                                                 "totp": "123456"})
    assert r.status_code == 401


@pytest.mark.tc("TC-SEC-04")
@pytest.mark.req("VPS-SR-004")
def test_counterfeit_qr_rejected_with_alert(client, attendant_headers):
    t = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA05MN4821", "vehicle_category": "4W"}).json()
    body, sig = t["qr_payload"].rsplit(".", 1)
    forged = body[:-2] + ("AA" if body[-2:] != "AA" else "BB") + "." + sig
    r = client.post("/api/v1/egress/lookup", json={"qr_payload": forged})
    assert r.status_code == 403 and r.json()["error"]["code"] == "TAMPERED_TICKET"
    alerts = client.get("/api/v1/alerts", headers=attendant_headers).json()
    assert alerts[0]["kind"] == "COUNTERFEIT_TICKET" and alerts[0]["severity"] == "CRITICAL"


@pytest.mark.tc("TC-SEC-05")
@pytest.mark.req("VPS-SR-005")
def test_audit_log_tamper_evident(client, ctx, admin_headers):
    client.put("/api/v1/admin/tariffs/EV", json={"first_hour": 45, "per_hour": 25, "daily_cap": 350}, headers=admin_headers)
    client.post("/api/v1/admin/barrier-override", json={"lane_id": "EXIT-2", "reason": "fire drill"}, headers=admin_headers)
    assert client.get("/api/v1/admin/audit/verify", headers=admin_headers).json()["valid"] is True
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        ctx.db.execute("DELETE FROM audit_log WHERE action = 'BARRIER_OVERRIDE'")
    ctx.db.execute("DROP TRIGGER audit_no_update")
    ctx.db.execute("UPDATE audit_log SET actor = 'nobody' WHERE action = 'BARRIER_OVERRIDE'")
    v = client.get("/api/v1/admin/audit/verify", headers=admin_headers).json()
    assert v["valid"] is False and v["broken_at"] is not None
