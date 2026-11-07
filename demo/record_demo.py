"""Record the sprint demo videos (Part 2: 1-minute Sprint 1 video, 2-minute Sprint 2 video).

Starts a fresh VPS server, drives the real web UI in Chromium with on-screen captions, and writes
demo/sprint1_demo.mp4 and demo/sprint2_demo.mp4 (needs Playwright + Chromium, and ffmpeg for MP4).

    python demo/record_demo.py                         # both videos, server from this checkout
    python demo/record_demo.py sprint1 --repo ../snap  # run the server from another checkout (e.g. the
                                                       # repo as it was at the end of Sprint 1)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from vps.config import Settings  # noqa: E402
from vps.security import totp  # noqa: E402

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}/ui/"
CAPTION_JS = """(t) => {
  let el = document.getElementById('demo-caption');
  if (!el) {
    el = document.createElement('div'); el.id = 'demo-caption';
    el.style.cssText = 'position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:9999;max-width:82%;' +
      'background:rgba(19,35,58,.94);color:#fff;padding:12px 22px;border-radius:10px;' +
      'font:600 18px/1.35 Inter,system-ui,sans-serif;' +
      'box-shadow:0 8px 30px rgba(0,0,0,.35);text-align:center;border-left:5px solid #f2a900';
    document.body.appendChild(el);
  }
  el.textContent = t;
}"""


def start_server(tmp: Path, server_root: Path) -> subprocess.Popen:
    env = {**os.environ, "VPS_DB_PATH": str(tmp / "demo.db"), "VPS_EDGE_DB_PATH": str(tmp / "demo_edge.db"),
           "PYTHONPATH": str(server_root)}
    proc = subprocess.Popen([sys.executable, "-m", "vps", "--port", str(PORT)], cwd=server_root, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            if httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=1).status_code == 200:
                return proc
        except httpx.HTTPError:
            time.sleep(0.2)
    proc.kill()
    raise RuntimeError("server did not start")


class Demo:
    def __init__(self, page: Page, pace: float = 1.0):
        self.p = page
        self.pace = pace            # stretches every pause; tuned so the videos run ~1 min / ~2 min

    def _wait(self, seconds: float):
        self.p.wait_for_timeout(int(seconds * self.pace * 1000))

    def go(self, path: str, text: str, wait: float = 1.2):
        self.p.goto(BASE + path)
        self.say(text, wait)

    def say(self, text: str, wait: float = 2.2):
        self.p.evaluate(CAPTION_JS, text)
        self._wait(wait)

    def click(self, sel: str, wait: float = 0.9):
        self.p.click(sel)
        self._wait(wait)

    def type(self, sel: str, value: str):
        self.p.fill(sel, "")
        self.p.type(sel, value, delay=35)


def sprint1(d: Demo) -> None:
    d.go("index.html", "Sprint 1 demo · Vehicle Parking System · Group 6", 2.5)
    d.say("Overview: 100 bays on 3 levels, 2 entry + 2 exit lanes, edge link online", 2.5)
    d.go("entry.html", "Entry kiosk: the ANPR camera reads the plate (F-001)", 1.5)
    d.type("#plate", "KA 05 MN 4821")
    d.p.click("summary")
    d.p.select_option("#arr", "130")
    d.say("Simulation: car arrived 2 h 10 min ago, so the exit fare is realistic", 2.2)
    d.click("#go", 1.2)
    d.say("Nearest 4W bay allocated (F-005) + HMAC-signed QR ticket (F-002), barrier UP (F-003)", 3.5)
    d.say("Every step is timed against its SRS target: total well under 3 s (NF-001)", 3)
    d.click("#onloop", 1.0)
    d.click("#lower", 0.6)
    d.say("Safety: the barrier refuses to come down while the car is on the ground loop (F-004)", 3)
    d.click("#cleared", 1.6)
    d.go("display.html", "Live display: bay sensors drive LEDs and the VMS boards (F-006, F-007)", 2)
    d.p.click(".slot >> nth=30")
    d._wait(1.5)
    d.say("Sensor fired → bay turns red and the free-space counts drop within a second", 3)
    d.go("exit.html", "Exit: scan the ticket and fetch the invoice (F-011)", 1)
    d.click("#last", 0.5)
    d.type("#coupon", "WELCOME10")
    d.click("#scan", 1.2)
    d.say("3 billable hours: Rs 100, 10 % coupon, CGST + SGST 9 % each = Rs 106.20 (F-008, F-010)", 3.5)
    d.click("#pay", 1.2)
    d.say("Dynamic UPI QR from the payment gateway (F-012)", 2.2)
    d.click("#sim-ok", 1.5)
    d.say("Signed webhook verified → PAID → exit barrier opens (F-013)", 3)
    d.click("#tamper", 0.4)
    d.click("#scan", 1.2)
    d.say("A tampered QR ticket is rejected and raises a security alert (SR-004)", 3)


def sprint2(d: Demo) -> None:
    s = Settings()
    d.go("index.html", "Sprint 2 demo · reservations, admin console, reports, receipts, edge resilience", 3)
    d.go("booking.html", "Pre-book a bay up to 48 hours ahead (F-015)", 1)
    d.type("#plate", "MH12XY9090")
    d.p.select_option("#cat", "EV")
    d.click("#book", 1.2)
    d.say("Bay locked (blue LED) + reservation code; released automatically after a 30-min no-show (F-016)", 3.5)
    code = d.p.inner_text("#code").strip()
    d.go("entry.html", "Arrive with the code: the reserved bay is assigned", 0.8)
    d.type("#plate", "MH12XY9090")
    d.click("#cat button[data-v=EV]", 0.3)
    d.type("#res", code)
    d.click("#go", 2.5)
    d.go("admin.html", "Admin console: password + TOTP (RBAC + MFA, SR-003)", 1)
    d.type("#t", totp(s.admin_totp_secret))
    d.click("#signin", 1.5)
    d.say("Tariffs can be changed live, without a restart (F-017)", 1.2)
    d.p.fill("#tariffs tr:nth-child(2) td:nth-child(2) input", "45")
    d.click("#tariffs tr:nth-child(2) button", 2.0)
    d.click("#tabs button[data-v=pricing]", 1.2)
    d.say("Peak-hour surge rules and promo coupons (F-010)", 2.5)
    d.click("#c-add", 1.5)
    d.click("#tabs button[data-v=reports]", 1.0)
    d.click("#r-view", 1.0)
    d.say("Revenue, occupancy and turnaround reports, exportable as CSV / PDF in well under 5 s (F-018)", 3)
    d.p.select_option("#r-kind", "occupancy")
    d.click("#r-view", 2.0)
    d.click("#tabs button[data-v=audit]", 1.0)
    d.click("#a-check", 1.2)
    d.say("Write-once, hash-chained audit log; the chain verifies intact (SR-005)", 3.2)
    d.click("#tabs button[data-v=edge]", 1.0)
    d.click("#e-off", 1.2)
    d.say("Simulate a WAN outage: gate lanes keep working on the local queue (NF-005)", 2.5)
    page2 = d.p.context.new_page()
    page2.goto(BASE + "entry.html")
    page2.fill("#plate", "KA01AB7777")
    page2.click("#go")
    page2.wait_for_timeout(800)
    page2.close()
    d.p.reload()
    d.click("#tabs button[data-v=edge]", 1.2)
    d.say("1 transaction queued at the edge while offline", 2.2)
    d.click("#e-on", 1.5)
    d.say("Link restored → queued events synced to central in milliseconds", 2.8)
    d.click("#tabs button[data-v=logout]", 1.0)
    d.go("attendant.html", "Attendant fast-POS: alerts, manual entry, cash desk, audited overrides", 1)
    d.click("#signin", 1.5)
    d.say("Open alerts include the counterfeit-ticket alert raised at the exit", 2.5)
    d.type("#m-plate", "TN09BX7712")
    d.click("#manual", 1.5)
    d.say("Unreadable plate? The attendant types it in, and the entry is audited", 2.5)
    d.type("#c-plate", "KA51MC2024")
    d.click("#c-find", 1.0)
    d.click("#c-pay", 1.5)
    d.say("Cash settlement opens the exit barrier and is written to the audit log", 2.5)
    d.type("#o-reason", "Ambulance access")
    d.click("#override", 2.0)
    d.go("exit.html", "GST tax invoice: thermal-printer PDF, e-mail or SMS (F-014)", 0.8)
    d.type("#plate", "DL3CAF0001")
    d.click("#scan", 1.0)
    d.click("#pay", 1.0)
    d.click("#sim-ok", 1.5)
    d.type("#mobile", "9876543210")
    d.click("#sms", 1.5)
    d.say("Receipt queued by SMS; PDF available from the receipt link. End of Sprint 2 demo", 3.5)


PACE = {"sprint1": 1.25, "sprint2": 1.55}


def record(name: str, scenario, out_dir: Path, server_root: Path = ROOT) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="vps-demo-"))
    server = start_server(tmp, server_root)
    try:
        if name == "sprint2":                       # Sprint 2 starts from a car park with history
            with httpx.Client(base_url=f"http://127.0.0.1:{PORT}") as c:
                now = datetime.now(timezone.utc)
                c.post("/api/v1/ingress/ticket", json={"plate_number": "KA51MC2024", "vehicle_category": "2W",
                                                       "timestamp": (now - timedelta(hours=1, minutes=40)).isoformat()})
                stay = (now - timedelta(hours=3, minutes=15)).isoformat()
                t = c.post("/api/v1/ingress/ticket", json={"plate_number": "DL3CAF0001", "vehicle_category": "4W",
                                                           "timestamp": stay}).json()
                bad = t["qr_payload"][:5] + ("A" if t["qr_payload"][5] != "A" else "B") + t["qr_payload"][6:]
                c.post("/api/v1/egress/lookup", json={"qr_payload": bad})
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(tmp),
                                      record_video_size={"width": 1280, "height": 720}, bypass_csp=True)
            page = ctx.new_page()
            page.set_default_timeout(8000)
            scenario(Demo(page, PACE[name]))
            video = page.video.path()
            ctx.close()
            browser.close()
        out = out_dir / f"{name}_demo.mp4"
        if shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True)
        else:  # pragma: no cover
            out = out.with_suffix(".webm")
            shutil.copy(video, out)
        return out
    finally:
        server.terminate()
        server.wait(timeout=10)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="*", default=["sprint1", "sprint2"], choices=["sprint1", "sprint2"])
    ap.add_argument("--repo", type=Path, default=ROOT, help="checkout to run the server from")
    a = ap.parse_args()
    for name in a.videos:
        path = record(name, {"sprint1": sprint1, "sprint2": sprint2}[name], ROOT / "demo", a.repo.resolve())
        print("wrote", path.relative_to(ROOT))
