"""Performance & scalability validation (VPS-NF-001, VPS-NF-003, VPS-F-018) against a real HTTP server.
Owner: Himansh Ahuja (QA Lead). The Test Plan named JMeter; this pytest + httpx harness produces the same
latency percentiles inside CI (see docs/Deviations.md DEV-06). Set VPS_PERF_OUT=<file> to save metrics."""

import json
import os
import statistics
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from tests.conftest import free_port, make_settings
from vps.allocation import get_allocation
from vps.context import Context
from vps.reports import get_reports

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.perf
METRICS: dict = {}


def pct(values, p):
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


def save(name, data):
    METRICS[name] = data
    out = os.getenv("VPS_PERF_OUT")
    if out:
        with open(out, "w") as fh:
            json.dump(METRICS, fh, indent=2)


@pytest.fixture(scope="module")
def big_server(tmp_path_factory):
    """10,000 slots and 50 gate lanes (VPS-NF-003 sizing), served by a separate uvicorn process so the
    load generator does not share the server's interpreter."""
    tmp = tmp_path_factory.mktemp("perf")
    db, edge = str(tmp / "vps.db"), str(tmp / "edge.db")
    seed = Context(make_settings(db_path=db, edge_db_path=edge, seed_default_layout=False))
    alloc = get_allocation(seed)
    for level in range(1, 11):                                   # 10 levels x 1,000 bays
        alloc.add_slots(level, "4W", 700)
        alloc.add_slots(level, "2W", 200)
        alloc.add_slots(level, "EV", 60)
        alloc.add_slots(level, "HANDICAP", 40)
    seed.close()
    port = free_port()
    env = {**os.environ, "VPS_DB_PATH": db, "VPS_EDGE_DB_PATH": edge, "VPS_LANE_PAIRS": "25",
           "PYTHONPATH": str(ROOT)}
    proc = subprocess.Popen([sys.executable, "-m", "vps", "--port", str(port)], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    while True:
        try:
            if httpx.get(base + "/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if time.time() > deadline:  # pragma: no cover
            proc.kill()
            raise RuntimeError("perf server did not start")
        time.sleep(0.2)
    yield base
    proc.terminate()
    proc.wait(timeout=10)


_local = threading.local()


def _client() -> httpx.Client:
    """One persistent connection per load-generator thread (like a gate controller)."""
    if not hasattr(_local, "c"):
        _local.c = httpx.Client(timeout=10)
    return _local.c


@pytest.mark.tc("TC-Perf-01")
@pytest.mark.req("VPS-NF-001")
def test_ingress_p90_under_3s(big_server):
    url = f"{big_server}/api/v1/ingress/ticket"
    lat, server_total = [], []
    with httpx.Client(timeout=10) as c:
        for i in range(200):
            body = {"plate_number": f"KA{10 + i % 80:02d}PF{1000 + i}", "vehicle_category": "4W",
                    "lane_id": f"ENTRY-{1 + i % 2}"}
            t0 = time.perf_counter()
            r = c.post(url, json=body)
            lat.append((time.perf_counter() - t0) * 1000)
            assert r.status_code == 201, r.text
            server_total.append(r.json()["timings_ms"]["total"])
    p90 = pct(lat, 90)
    save("ingress", {"transactions": 200, "p50_ms": round(pct(lat, 50), 2), "p90_ms": round(p90, 2),
                     "p99_ms": round(pct(lat, 99), 2), "max_ms": round(max(lat), 2),
                     "server_side_p90_ms": round(pct(server_total, 90), 2), "target_p90_ms": 3000})
    assert p90 <= 3000


@pytest.mark.tc("TC-Scale-01")
@pytest.mark.req("VPS-NF-003")
def test_api_latency_under_load_10k_slots_50_lanes(big_server):
    base = big_server
    assert httpx.get(f"{base}/api/v1/slots/summary").json()["capacity"] == 10_000
    lanes = httpx.get(f"{base}/api/v1/lanes").json()
    assert len(lanes) == 50
    entry_lanes = [lane["lane_id"] for lane in lanes if lane["direction"] == "ENTRY"]

    def one(i):
        c = _client()
        t0 = time.perf_counter()
        if i % 4 == 0:
            r = c.post(f"{base}/api/v1/ingress/ticket", json={
                "plate_number": f"MH{10 + i % 80:02d}LD{1000 + i}", "vehicle_category": "2W",
                "lane_id": entry_lanes[i % len(entry_lanes)]})
        elif i % 4 == 1:
            r = c.post(f"{base}/api/v1/sensors/L{1 + i % 10}-C{1 + i % 700:03d}/event", json={"occupied": bool(i % 2)})
        elif i % 4 == 2:
            r = c.get(f"{base}/api/v1/vms")
        else:
            r = c.get(f"{base}/api/v1/slots/nearest/4W")
        return (time.perf_counter() - t0) * 1000, r.status_code, i % 4

    n = 1000
    with ThreadPoolExecutor(max_workers=25) as pool:
        # warm-up: every worker opens its keep-alive connection first (excluded from the measurement)
        list(pool.map(lambda _: _client().get(f"{base}/health"), range(100)))
        t_start = time.perf_counter()
        results = list(pool.map(one, range(n)))
        wall = time.perf_counter() - t_start
    lat = [r[0] for r in results]
    errors = [r[1] for r in results if r[1] >= 500]
    p95 = pct(lat, 95)
    kinds = {0: "ingress", 1: "sensor_event", 2: "vms", 3: "nearest_slot"}
    by_kind = {kinds[k]: round(pct([r[0] for r in results if r[2] == k], 95), 2) for k in kinds}
    save("scale", {"p95_by_endpoint_ms": by_kind, "requests": n, "concurrency": 25, "slots": 10_000, "lanes": 50,
                   "throughput_rps": round(n / wall, 1), "p50_ms": round(pct(lat, 50), 2),
                   "p95_ms": round(p95, 2), "p99_ms": round(pct(lat, 99), 2), "max_ms": round(max(lat), 2),
                   "server_errors": len(errors), "target_p95_ms": 200})
    assert not errors
    assert p95 < 200


@pytest.mark.tc("TC-ADM-02")
@pytest.mark.req("VPS-F-018")
def test_export_large_month_under_5s():
    ctx = Context(make_settings())
    get_allocation(ctx)
    get_reports(ctx)
    t0 = datetime(2026, 10, 1, 4, 0, tzinfo=timezone.utc)
    fare = json.dumps({"taxable_amount": 100.0, "cgst": 9.0, "sgst": 9.0})
    tickets, payments = [], []
    for i in range(5000):
        tid = str(uuid.uuid4())
        entry = t0 + timedelta(minutes=8 * i)
        exit_ = entry + timedelta(minutes=90)
        tickets.append((tid, "v1:x", f"fp{i}", "4W", "L1-C001", "ENTRY-1", entry.isoformat(), exit_.isoformat(), "PAID",
                        "qr", 118.0, entry.isoformat()))
        payments.append((f"order_{i}", tid, 118.0, "upi", "CAPTURED", fare, exit_.isoformat(), exit_.isoformat()))
    ctx.db.executemany("INSERT INTO tickets (id, plate_enc, plate_fp, category, slot_id, entry_lane, entry_time, exit_time,"
                       " status, qr_payload, amount, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", tickets)
    ctx.db.executemany("INSERT INTO payments (id, ticket_id, amount, method, status, fare_json, created_at, updated_at)"
                       " VALUES (?,?,?,?,?,?,?,?)", payments)
    times = {}
    for kind in ("revenue", "turnaround", "occupancy"):
        for fmt in ("csv", "pdf"):
            data, _, _, ms = get_reports(ctx).export(kind, "daily", fmt, "2026-10-01", "2026-10-31")
            times[f"{kind}.{fmt}"] = ms
            assert data and ms <= 5000
    save("exports", {"rows": 5000, "times_ms": times, "max_ms": max(times.values()), "target_ms": 5000})
    ctx.close()
    assert statistics.mean(times.values()) < 5000
