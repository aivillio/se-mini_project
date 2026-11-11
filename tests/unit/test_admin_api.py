"""Unit tests - admin console API (VPS-F-017, VPS-SR-003, VPS-SR-005). Owner: Himansh Ahuja."""

import pytest


@pytest.mark.tc("TC-ADM-01")
@pytest.mark.req("VPS-F-017")
class TestTariffAdmin:
    def test_update_tariff_live(self, client, admin_headers, clock):
        t = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA01AB1234", "vehicle_category": "4W"}).json()
        clock.advance(minutes=50)
        r = client.put("/api/v1/admin/tariffs/4W", json={"first_hour": 60, "per_hour": 35, "daily_cap": 500},
                       headers=admin_headers)
        assert r.status_code == 200 and r.json()["first_hour"] == 60
        inv = client.post("/api/v1/egress/lookup", json={"qr_payload": t["qr_payload"]}).json()["invoice"]
        assert inv["base_amount"] == 60.0                       # no restart needed

    def test_manager_read_only(self, client, manager_headers):
        assert len(client.get("/api/v1/admin/tariffs", headers=manager_headers).json()) == 4
        r = client.put("/api/v1/admin/tariffs/4W", json={"first_hour": 1, "per_hour": 1, "daily_cap": 5},
                       headers=manager_headers)
        assert r.status_code == 403

    def test_invalid_tariff(self, client, admin_headers):
        r = client.put("/api/v1/admin/tariffs/4W", json={"first_hour": 100, "per_hour": 1, "daily_cap": 5},
                       headers=admin_headers)
        assert r.status_code == 400

    def test_surge_and_coupons(self, client, admin_headers, manager_headers):
        r = client.post("/api/v1/admin/surge", json={"name": "Lunch", "start_hour": 12, "end_hour": 14, "multiplier": 1.1},
                        headers=admin_headers)
        assert r.status_code == 201
        rid = r.json()["id"]
        r = client.patch(f"/api/v1/admin/surge/{rid}", json={"active": False}, headers=admin_headers)
        assert r.json()["active"] == 0
        assert len(client.get("/api/v1/admin/surge", headers=manager_headers).json()) == 2
        c = client.post("/api/v1/admin/coupons", json={"code": "FEST15", "kind": "PERCENT", "value": 15},
                        headers=admin_headers)
        assert c.status_code == 201
        assert "FEST15" in [x["code"] for x in client.get("/api/v1/admin/coupons", headers=manager_headers).json()]


@pytest.mark.tc("TC-ADM-01")
class TestLayoutAdmin:
    def test_add_slots_and_status(self, client, admin_headers):
        r = client.post("/api/v1/admin/slots", json={"level": 4, "category": "EV", "count": 5}, headers=admin_headers)
        assert r.status_code == 201 and len(r.json()["created"]) == 5
        assert client.get("/api/v1/vms").json()["entrance"]["vacant"] == 105
        assert client.patch("/api/v1/admin/slots/L4-E001", json={"status": "DISABLED"},
                            headers=admin_headers).json()["status"] == "DISABLED"
        assert client.patch("/api/v1/admin/slots/L4-E001", json={"status": "OCCUPIED"},
                            headers=admin_headers).status_code == 400


@pytest.mark.tc("TC-SEC-05")
@pytest.mark.req("VPS-SR-005")
class TestOverrideAndAudit:
    def test_override_is_audited(self, client, attendant_headers, admin_headers):
        r = client.post("/api/v1/admin/barrier-override", json={"lane_id": "EXIT-1", "action": "RAISE",
                                                                "reason": "Ambulance access"}, headers=attendant_headers)
        assert r.status_code == 200 and r.json()["barrier"] == "UP"
        entry = client.get("/api/v1/admin/audit", params={"action": "BARRIER_OVERRIDE"}, headers=admin_headers).json()[0]
        assert entry["id"] == r.json()["audit_id"] and entry["actor"] == "attendant"
        assert entry["details"]["reason"] == "Ambulance access"
        low = client.post("/api/v1/admin/barrier-override", json={"lane_id": "EXIT-1", "action": "LOWER",
                                                                  "reason": "Ambulance left"}, headers=attendant_headers)
        assert low.json()["barrier"] == "DOWN"

    def test_override_validation(self, client, attendant_headers):
        url = "/api/v1/admin/barrier-override"
        spin = {"lane_id": "EXIT-1", "action": "SPIN", "reason": "testing"}
        assert client.post(url, json=spin, headers=attendant_headers).status_code == 400
        short = {"lane_id": "EXIT-1", "reason": "x"}
        assert client.post(url, json=short, headers=attendant_headers).status_code == 422      # reason too short
        assert client.post(url, json={"lane_id": "EXIT-1", "reason": "no auth"}).status_code == 401

    def test_audit_verify_endpoint(self, client, admin_headers, manager_headers, attendant_headers):
        v = client.get("/api/v1/admin/audit/verify", headers=manager_headers).json()
        assert v["valid"] is True and v["entries"] >= 2
        assert client.get("/api/v1/admin/audit", headers=attendant_headers).status_code == 403
