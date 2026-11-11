"""Unit tests - edge controller API (VPS-NF-005). Owner: Shweta Mailaragouda Patil."""

import pytest


@pytest.mark.tc("TC-Fault-01")
@pytest.mark.req("VPS-NF-005")
def test_edge_api(client, admin_headers):
    assert client.post("/api/v1/edge/network", json={"online": False}).status_code == 401
    assert client.post("/api/v1/edge/network", json={"online": False}, headers=admin_headers).json()["online"] is False
    assert client.post("/api/v1/edge/sync", headers=admin_headers).json()["synced"] == 0
    assert client.get("/api/v1/edge/status").json()["online"] is False
    assert client.post("/api/v1/edge/network", json={"online": True}, headers=admin_headers).json()["online"] is True


