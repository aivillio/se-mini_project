"""Contribution plan: which files each member commits, in which PR, in which order.

Each member commits **only their own files**, on their own branch, and raises the PR themselves; the repo
owner reviews and merges (Part 2, items 2c/2d). PRs must be merged in the order below. Each PR passes CI
on its own because everything it imports was merged earlier.

    python scripts/stage_contribution.py list                       # the whole plan
    python scripts/stage_contribution.py files PR-04                # files in one PR
    python scripts/stage_contribution.py copy PR-04 --to ../my-clone  # copy that PR's files into your clone
    python scripts/stage_contribution.py check                      # every repo file is in exactly one PR
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MEMBERS = {
    "Angelo": "Angelo Arakal (PES2UG24CS062)",
    "Shweta": "Shweta Mailaragouda Patil (PES2UG25CS825)",
    "Akarsh": "Akarsh Parashuram (PES2UG24CS040)",
    "Himansh": "Himansh Ahuja (PES2UG24CS923)",
}

PLAN = [
    # ------------------------------------------------------------------ Sprint 1
    dict(pr="PR-01", sprint="Sprint 1", owner="Angelo", branch="feature/core-security",
         closes="VPS-SR-002, VPS-SR-003, VPS-SR-004, VPS-SR-005",
         title="Project scaffold, CI, security core, audit log, RBAC + MFA",
         files=[".gitignore", "README.md", "requirements.txt", "requirements-dev.txt", "pyproject.toml",
                ".github/workflows/ci.yml", ".github/CODEOWNERS",
                "docs/part1/SRS_Vehicle_Parking_System.pdf", "docs/part1/SAD_Vehicle_Parking_System.pdf",
                "docs/part1/Software_Test_Plan_VPS_v1.0.pdf",
                "vps/__init__.py", "vps/config.py", "vps/errors.py", "vps/db.py", "vps/context.py", "vps/security.py",
                "vps/audit.py", "vps/auth.py", "vps/main.py", "vps/api/__init__.py", "vps/api/deps.py", "vps/api/auth.py",
                "tests/__init__.py", "tests/conftest.py", "tests/unit/__init__.py", "tests/unit/test_security.py",
                "tests/unit/test_auth.py", "tests/unit/test_audit.py", "tests/unit/test_app.py"]),
    dict(pr="PR-02", sprint="Sprint 1", owner="Himansh", branch="process/backlog-sprint-plan",
         closes="",
         title="Backlog sync script, sprint plan, PR/issue templates, PR automation",
         files=["backlog/backlog.csv", "scripts/github_setup.py", ".github/pull_request_template.md",
                ".github/ISSUE_TEMPLATE/user_story.md", ".github/labeler.yml", ".github/workflows/pr-automation.yml",
                "docs/sprints/Sprint_Plan.md", "scripts/stage_contribution.py"]),
    dict(pr="PR-03", sprint="Sprint 1", owner="Shweta", branch="feature/slots-sensors-edge",
         closes="VPS-F-005, VPS-F-006",
         title="Hardware simulators, slot allocation, occupancy sensors, edge queue, UI design system",
         files=["vps/plates.py", "vps/hardware.py", "vps/alerts.py", "vps/allocation.py", "vps/sensors.py",
                "vps/edge_queue.py", "vps/api/slots.py", "web/static/style.css", "web/static/app.js",
                "tests/unit/test_hardware.py", "tests/unit/test_allocation.py",
                "tests/unit/test_sensors.py", "tests/unit/test_edge.py"]),
    dict(pr="PR-04", sprint="Sprint 1", owner="Angelo", branch="feature/vehicle-entry",
         closes="VPS-F-001, VPS-F-002, VPS-F-003, VPS-F-004",
         title="Vehicle entry: ANPR, signed QR ticket, entry barrier, ground-loop safety, entry kiosk UI",
         files=["vps/ingress.py", "vps/api/ingress.py", "vps/__main__.py", "web/index.html", "web/entry.html",
                "web/static/index.js", "web/static/entry.js",
                "tests/unit/test_ingress.py"]),
    dict(pr="PR-05", sprint="Sprint 1", owner="Akarsh", branch="feature/billing-payment-exit",
         closes="VPS-F-008, VPS-F-009, VPS-F-010, VPS-F-011, VPS-F-012, VPS-F-013, VPS-NF-004",
         title="Tariff engine, grace period, surge + coupons, exit scan, cashless payment, exit barrier, exit UI",
         files=["vps/tariff.py", "vps/payment.py", "vps/egress.py", "vps/api/egress.py", "web/exit.html",
                "web/static/exit.js", "tests/unit/test_tariff.py", "tests/unit/test_payment.py",
                "tests/unit/test_egress.py"]),
    dict(pr="PR-06", sprint="Sprint 1", owner="Shweta", branch="feature/live-vacancy-display",
         closes="VPS-F-007",
         title="Real-time vacancy display: VMS boards and slot map with sensor LEDs",
         files=["web/display.html", "web/static/display.js"]),
    # ------------------------------------------------------------------ Sprint 2
    dict(pr="PR-07", sprint="Sprint 2", owner="Himansh", branch="feature/reservations-admin-reports",
         closes="VPS-F-015, VPS-F-016, VPS-F-017, VPS-F-018",
         title="Reservations, no-show release, admin console, reports + booking and admin UI",
         files=["vps/reservation.py", "vps/scheduler.py", "vps/reports.py", "vps/api/reservations.py",
                "vps/api/admin.py", "vps/api/reports.py", "web/booking.html", "web/admin.html", "web/static/booking.js",
                "web/static/admin.js", "tests/unit/test_reservation.py", "tests/unit/test_reports.py",
                "tests/unit/test_admin_api.py"]),
    dict(pr="PR-08", sprint="Sprint 2", owner="Angelo", branch="feature/tls13",
         closes="VPS-SR-001",
         title="TLS 1.3-only server runner and TOTP dev helper",
         files=["vps/tls.py", "scripts/totp.py", "tests/unit/test_tls.py"]),
    dict(pr="PR-09", sprint="Sprint 2", owner="Akarsh", branch="feature/gst-receipts",
         closes="VPS-F-014",
         title="GST receipts (PDF/SMS/e-mail), deviation log, Sprint 1 demo video",
         files=["vps/receipt.py", "vps/api/receipts.py", "tests/unit/test_receipt.py", "docs/Deviations.md",
                "demo/record_demo.py", "demo/sprint1_demo.mp4"]),
    dict(pr="PR-10", sprint="Sprint 2", owner="Shweta", branch="feature/edge-api-attendant",
         closes="VPS-NF-005",
         title="Edge controller API + WAN simulation, attendant POS UI",
         files=["vps/api/edge.py", "tests/unit/test_edge_api.py", "web/attendant.html", "web/static/attendant.js"]),
    # ------------------------------------------------------------------ Sprint 3 (testing)
    dict(pr="PR-11", sprint="Sprint 3", owner="Shweta", branch="test/resilience",
         closes="VPS-NF-002",
         title="Resilience and reliability tests (offline, outages, soak)",
         files=["tests/system/__init__.py", "tests/system/test_resilience.py"]),
    dict(pr="PR-12", sprint="Sprint 3", owner="Akarsh", branch="test/end-to-end",
         closes="",
         title="End-to-end journey tests and Sprint 2 demo video",
         files=["tests/system/test_end_to_end.py", "demo/sprint2_demo.mp4"]),
    dict(pr="PR-13", sprint="Sprint 3", owner="Angelo", branch="test/security-validation",
         closes="",
         title="Security validation suite and contribution plan",
         files=["tests/system/test_security_validation.py", "CONTRIBUTIONS.md"]),
    dict(pr="PR-14", sprint="Sprint 3", owner="Himansh", branch="test/performance-reports",
         closes="VPS-NF-001, VPS-NF-003",
         title="Performance tests, Test Plan v1.1, Test Case Specification, test reports",
         files=["tests/perf/__init__.py", "tests/perf/test_performance.py", "scripts/test_catalog.py",
                "scripts/generate_reports.py", "scripts/md2pdf.py", "docs/testing/", "docs/reports/"]),
]


def expand(entry: str, root: Path = ROOT) -> list[str]:
    """A trailing '/' means 'everything under this directory'."""
    if entry.endswith("/"):
        return sorted(str(p.relative_to(root)) for p in (root / entry).rglob("*") if p.is_file())
    return [entry]


def pr_files(pr: dict, root: Path = ROOT) -> list[str]:
    return [f for e in pr["files"] for f in expand(e, root)]


def get(pr_id: str) -> dict:
    for pr in PLAN:
        if pr["pr"].lower() == pr_id.lower():
            return pr
    sys.exit(f"unknown PR {pr_id}; run 'list'")


def tracked_files() -> list[str]:
    """Every file that belongs in the repo (honours .gitignore when git is available)."""
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.split()
        if out:
            return sorted(out)
    except (OSError, subprocess.CalledProcessError):
        pass
    skip = ("__pycache__", ".pytest_cache", ".ruff_cache", "reports-tmp", ".git/", "htmlcov")
    return sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file()
                  and not any(s in str(p) for s in skip) and not p.name.startswith(".coverage")
                  and not p.suffix.startswith(".db") and ".db-" not in p.name)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    f = sub.add_parser("files")
    f.add_argument("pr")
    c = sub.add_parser("copy")
    c.add_argument("pr")
    c.add_argument("--to", required=True, type=Path, help="your clone of the team repo")
    sub.add_parser("check")
    a = ap.parse_args()

    if a.cmd == "list":
        for pr in PLAN:
            print(f"{pr['pr']}  {pr['sprint']:<9} {pr['owner']:<8} {pr['branch']:<40} {len(pr_files(pr)):>3} files  {pr['title']}")
    elif a.cmd == "files":
        print("\n".join(pr_files(get(a.pr))))
    elif a.cmd == "copy":
        pr = get(a.pr)
        dest = a.to.resolve()
        if not (dest / ".git").exists():
            sys.exit(f"{dest} is not a git clone")
        for rel in pr_files(pr):
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dest / rel)
        print(f"copied {len(pr_files(pr))} files for {pr['pr']} into {dest}\nnext:\n"
              f"  git checkout -b {pr['branch']}\n  git add -A && git commit -m \"{pr['title']}\"\n"
              f"  git push -u origin {pr['branch']}   # then open the PR on GitHub")
    elif a.cmd == "check":
        planned = [x for pr in PLAN for x in pr_files(pr)]
        dupes = sorted({x for x in planned if planned.count(x) > 1})
        missing = sorted(set(tracked_files()) - set(planned))
        extra = sorted(x for x in set(planned) if not (ROOT / x).exists())
        for label, items in (("in more than one PR", dupes), ("not in any PR", missing), ("planned but missing", extra)):
            for x in items:
                print(f"{label}: {x}")
        ok = not (dupes or missing or extra)
        print("plan OK: every file is in exactly one PR" if ok else "plan has problems")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
