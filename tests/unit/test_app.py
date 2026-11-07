"""Unit tests - app factory, middleware, RBAC guards, config. Owner: Angelo Arakal."""

import pytest

from tests.conftest import make_settings
from vps.config import Settings
from vps.context import Context, parse_ts
from vps.main import create_app, discover_api_modules


def test_health_and_modules(client):
    r = client.get("/health").json()
    assert r["status"] == "ok"
    assert "auth" in r["modules"]


@pytest.mark.tc("TC-SEC-01")
@pytest.mark.req("VPS-SR-001")
def test_security_headers(client):
    h = client.get("/health").headers
    assert "max-age" in h["strict-transport-security"]
    assert h["x-frame-options"] == "DENY" and h["x-content-type-options"] == "nosniff"
    assert float(h["x-response-time-ms"]) >= 0


@pytest.mark.tc("TC-SEC-01")
@pytest.mark.req("VPS-SR-001")
def test_plain_http_refused_when_tls_required(clock):
    from fastapi.testclient import TestClient
    ctx = Context(make_settings(require_tls=True), clock=clock)
    with TestClient(create_app(ctx=ctx)) as c:
        r = c.get("/api/v1/auth/me")
        assert r.status_code == 426 and r.json()["error"]["code"] == "TLS_REQUIRED"
        assert c.get("/api/v1/auth/me", headers={"X-Forwarded-Proto": "https"}).status_code == 401   # past TLS gate
        assert c.get("/health").status_code == 200       # load-balancer probe allowed


@pytest.mark.tc("TC-SEC-03")
@pytest.mark.req("VPS-SR-003")
def test_rbac_guards(client, attendant_headers, admin_headers):
    assert client.get("/api/v1/auth/users").status_code == 401
    assert client.get("/api/v1/auth/users", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert client.get("/api/v1/auth/users", headers=attendant_headers).status_code == 403
    assert client.get("/api/v1/auth/users", headers=admin_headers).status_code == 200


def test_auth_api(client, admin_headers):
    assert client.get("/api/v1/auth/me", headers=admin_headers).json()["role"] == "ADMIN"
    r = client.post("/api/v1/auth/users", json={"username": "ops9", "password": "Shift@2026x"}, headers=admin_headers)
    assert r.status_code == 201
    assert any(u["username"] == "ops9" for u in client.get("/api/v1/auth/users", headers=admin_headers).json())
    assert client.patch("/api/v1/auth/users/ops9", json={"active": False}, headers=admin_headers).json()["active"] == 0
    assert client.post("/api/v1/auth/logout", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=admin_headers).status_code == 401


def test_discovery_skips_private_modules():
    names = [m.__name__ for m in discover_api_modules()]
    assert "vps.api.deps" not in names and all(hasattr(__import__(n, fromlist=["router"]), "router") for n in names)


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("VPS_MASTER_SECRET", "s3cret")
    monkeypatch.setenv("VPS_REQUIRE_TLS", "1")
    s = Settings.from_env()
    assert s.require_tls and s.ticket_hmac_key != Settings().ticket_hmac_key
    monkeypatch.delenv("VPS_MASTER_SECRET")
    monkeypatch.setenv("VPS_ENV", "production")
    with pytest.raises(RuntimeError):
        Settings.from_env()


def test_parse_ts_naive_is_utc():
    assert parse_ts("2026-10-20T06:00:00").utcoffset().total_seconds() == 0
    assert parse_ts("2026-10-20T06:00:00Z").hour == 6


def test_clock_override_and_nested_transaction(ctx):
    from datetime import datetime, timezone
    fixed = datetime(2030, 1, 1, tzinfo=timezone.utc)
    ctx.set_clock(lambda: fixed)
    assert ctx.now() == fixed
    ctx.set_clock(None)
    assert ctx.now().year >= 2026
    with ctx.db.transaction():
        with ctx.db.transaction():         # nested block joins the outer transaction
            ctx.db.execute("INSERT INTO alerts (ts, kind, severity, message) VALUES ('t', 'K', 'INFO', 'm')")
    assert ctx.db.scalar("SELECT COUNT(*) FROM alerts") == 1
