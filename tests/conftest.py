"""Shared fixtures. Every test gets an isolated in-memory database and a controllable clock."""

from __future__ import annotations

import socket
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
import uvicorn
from fastapi.testclient import TestClient

from vps.config import Settings
from vps.context import Context
from vps.main import create_app
from vps.security import totp

# 06:00 UTC = 11:30 IST: outside the default 17:00-20:00 IST surge window
T0 = datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, start: datetime = T0):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw) -> datetime:
        self.now += timedelta(**kw)
        return self.now

    def set(self, dt: datetime) -> None:
        self.now = dt


def make_settings(**overrides) -> Settings:
    s = Settings(db_path=":memory:", edge_db_path=":memory:")
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def ctx(settings, clock):
    c = Context(settings, clock=clock)
    yield c
    c.close()


@pytest.fixture
def client(ctx):
    with TestClient(create_app(ctx=ctx)) as c:
        yield c


def _login(client, ctx, username, password, secret=None):
    body = {"username": username, "password": password}
    if secret:
        body["totp"] = totp(secret, at=ctx.now().timestamp())
    r = client.post("/api/v1/auth/login", json=body)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def admin_headers(client, ctx):
    s = ctx.settings
    return _login(client, ctx, "admin", s.admin_password, s.admin_totp_secret)


@pytest.fixture
def manager_headers(client, ctx):
    s = ctx.settings
    return _login(client, ctx, "manager", s.manager_password, s.manager_totp_secret)


@pytest.fixture
def attendant_headers(client, ctx):
    return _login(client, ctx, "attendant", ctx.settings.attendant_password)


def issue(client, plate="KA01AB1234", category="4W", **extra) -> dict:
    r = client.post("/api/v1/ingress/ticket", json={"plate_number": plate, "vehicle_category": category, **extra})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- live server (perf / TLS tests)
def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LiveServer:
    def __init__(self, app, config: uvicorn.Config | None = None):
        self.port = config.port if config else free_port()
        self.config = config or uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        self.server = uvicorn.Server(self.config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        deadline = time.time() + 10
        while not self.server.started:
            if time.time() > deadline:  # pragma: no cover
                raise RuntimeError("server did not start")
            time.sleep(0.05)
        return self

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(timeout=5)


# ---------------------------------------------------------------- traceability hooks
def pytest_runtest_setup(item):
    """Copy @pytest.mark.tc / @pytest.mark.req ids into JUnit <properties> for the report generator."""
    for mark in item.iter_markers(name="tc"):
        for tc_id in mark.args:
            item.user_properties.append(("tc", tc_id))
    for mark in item.iter_markers(name="req"):
        for req_id in mark.args:
            item.user_properties.append(("req", req_id))
