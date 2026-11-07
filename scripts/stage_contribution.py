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
    dict(pr="PR-01", sprint="Sprint 1", owner="Angelo", branch="feature/VPS-US-01-core-security",
         stories="VPS-US-01, 02, 03, 04",
         title="VPS-US-01..04: project scaffold, CI, security core, audit log, RBAC + MFA",
         files=[".gitignore", "README.md", "requirements.txt", "requirements-dev.txt", "pyproject.toml",
                ".github/workflows/ci.yml", ".github/CODEOWNERS",
                "docs/part1/SRS_Vehicle_Parking_System.pdf", "docs/part1/SAD_Vehicle_Parking_System.pdf",
                "docs/part1/Software_Test_Plan_VPS_v1.0.pdf",
                "vps/__init__.py", "vps/config.py", "vps/errors.py", "vps/db.py", "vps/context.py", "vps/security.py",
                "vps/audit.py", "vps/auth.py", "vps/main.py", "vps/api/__init__.py", "vps/api/deps.py", "vps/api/auth.py",
                "tests/__init__.py", "tests/conftest.py", "tests/unit/__init__.py", "tests/unit/test_security.py",
                "tests/unit/test_auth.py", "tests/unit/test_audit.py", "tests/unit/test_app.py"]),
    dict(pr="PR-02", sprint="Sprint 1", owner="Himansh", branch="process/VPS-US-05-backlog",
         stories="VPS-US-05", title="VPS-US-05: backlog, GitHub project setup, PR/issue templates, PR automation",
         files=["backlog/backlog.csv", "scripts/github_setup.py", ".github/pull_request_template.md",
                ".github/ISSUE_TEMPLATE/user_story.md", ".github/labeler.yml", ".github/workflows/pr-automation.yml",
                "docs/sprints/Sprint_Plan.md"]),
    dict(pr="PR-03", sprint="Sprint 1", owner="Shweta", branch="feature/VPS-US-06-slots-sensors",
         stories="VPS-US-06, 07, 08, 09, 10",
         title="VPS-US-06..10: hardware simulators, slot allocation, sensors + VMS, edge queue, UI design system",
         files=["vps/plates.py", "vps/hardware.py", "vps/alerts.py", "vps/allocation.py", "vps/sensors.py",
                "vps/edge_queue.py", "vps/api/slots.py", "web/static/style.css", "web/static/app.js",
                "tests/unit/test_hardware.py", "tests/unit/test_allocation.py",
                "tests/unit/test_sensors.py", "tests/unit/test_edge.py"]),
    dict(pr="PR-04", sprint="Sprint 1", owner="Angelo", branch="feature/VPS-US-11-entry",
         stories="VPS-US-11, 12, 13",
         title="VPS-US-11..13: vehicle entry + signed QR ticket, lane safety API, entry kiosk and overview UI",
         files=["vps/ingress.py", "vps/api/ingress.py", "vps/__main__.py", "web/index.html", "web/entry.html",
                "web/static/index.js", "web/static/entry.js",
                "tests/unit/test_ingress.py"]),
    dict(pr="PR-05", sprint="Sprint 1", owner="Akarsh", branch="feature/VPS-US-14-billing-payment",
         stories="VPS-US-14, 15, 16, 17, 18, 19",
         title="VPS-US-14..19: tariff engine, surge + coupons, exit scan, cashless payment, exit barrier, exit UI",
         files=["vps/tariff.py", "vps/payment.py", "vps/egress.py", "vps/api/egress.py", "web/exit.html",
                "web/static/exit.js", "tests/unit/test_tariff.py", "tests/unit/test_payment.py",
                "tests/unit/test_egress.py"]),
    dict(pr="PR-06", sprint="Sprint 1", owner="Shweta", branch="feature/VPS-US-35-live-display",
         stories="VPS-US-35", title="VPS-US-35: live display UI (VMS boards + slot map with sensor LEDs)",
         files=["web/display.html", "web/static/display.js"]),
    # ------------------------------------------------------------------ Sprint 2
    dict(pr="PR-07", sprint="Sprint 2", owner="Himansh", branch="feature/VPS-US-20-reservations-admin",
         stories="VPS-US-20, 21, 22, 23, 24",
         title="VPS-US-20..24: 48 h reservations, no-show scheduler, admin console, reports, booking + admin UI",
         files=["vps/reservation.py", "vps/scheduler.py", "vps/reports.py", "vps/api/reservations.py",
                "vps/api/admin.py", "vps/api/reports.py", "web/booking.html", "web/admin.html", "web/static/booking.js",
                "web/static/admin.js", "tests/unit/test_reservation.py", "tests/unit/test_reports.py",
                "tests/unit/test_admin_api.py"]),
    dict(pr="PR-08", sprint="Sprint 2", owner="Angelo", branch="feature/VPS-US-30-tls",
         stories="VPS-US-30", title="VPS-US-30: TLS 1.3-only server runner and TOTP dev helper",
         files=["vps/tls.py", "scripts/totp.py", "tests/unit/test_tls.py"]),
    dict(pr="PR-09", sprint="Sprint 2", owner="Akarsh", branch="feature/VPS-US-25-receipts",
         stories="VPS-US-25, 26, 27",
         title="VPS-US-25..27: GST receipts (PDF/SMS/e-mail), deviation log, Sprint 1 demo video",
         files=["vps/receipt.py", "vps/api/receipts.py", "tests/unit/test_receipt.py", "docs/Deviations.md",
                "demo/record_demo.py", "demo/sprint1_demo.mp4"]),
    dict(pr="PR-10", sprint="Sprint 2", owner="Shweta", branch="feature/VPS-US-28-edge-attendant",
         stories="VPS-US-28, 29", title="VPS-US-28..29: edge controller API + WAN simulation, attendant POS UI",
         files=["vps/api/edge.py", "tests/unit/test_edge_api.py", "web/attendant.html", "web/static/attendant.js"]),
    # ------------------------------------------------------------------ Sprint 3 (testing)
    dict(pr="PR-11", sprint="Sprint 3", owner="Shweta", branch="test/VPS-US-31-resilience",
         stories="VPS-US-31", title="VPS-US-31: resilience and reliability tests (NF-005, NF-002)",
         files=["tests/system/__init__.py", "tests/system/test_resilience.py"]),
    dict(pr="PR-12", sprint="Sprint 3", owner="Akarsh", branch="test/VPS-US-32-e2e",
         stories="VPS-US-32", title="VPS-US-32: end-to-end journey tests and Sprint 2 demo video",
         files=["tests/system/test_end_to_end.py", "demo/sprint2_demo.mp4"]),
    dict(pr="PR-13", sprint="Sprint 3", owner="Angelo", branch="test/VPS-US-33-security-validation",
         stories="VPS-US-33", title="VPS-US-33: security validation suite (SR-001..005, NF-004) + contribution plan",
         files=["tests/system/test_security_validation.py", "CONTRIBUTIONS.md", "scripts/stage_contribution.py"]),
    dict(pr="PR-14", sprint="Sprint 3", owner="Himansh", branch="test/VPS-US-34-perf-reports",
         stories="VPS-US-34",
         title="VPS-US-34: performance tests, test plan v1.1, test case specification, all test reports",
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
