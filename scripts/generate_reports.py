"""Generate the Part 3 test reports into docs/ (Unit Test, System Validation, Code Coverage, Branch Coverage)
and render the Test Case Specification from scripts/test_catalog.py.

    python scripts/generate_reports.py            # run all suites + write Markdown/HTML (+PDF if Playwright present)
    python scripts/generate_reports.py --no-pdf
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from test_catalog import REQUIREMENTS, TEST_CASES  # noqa: E402

TMP = ROOT / "reports-tmp"
REPORTS = ROOT / "docs" / "reports"
TESTING = ROOT / "docs" / "testing"
IST = ZoneInfo("Asia/Kolkata")

OWNERS = {
    "test_security": "Angelo", "test_auth": "Angelo", "test_audit": "Angelo", "test_ingress": "Angelo",
    "test_app": "Angelo", "test_security_validation": "Angelo",
    "test_hardware": "Shweta", "test_allocation": "Shweta", "test_sensors": "Shweta", "test_edge": "Shweta",
    "test_edge_api": "Shweta", "test_resilience": "Shweta",
    "test_tariff": "Akarsh", "test_payment": "Akarsh", "test_egress": "Akarsh", "test_receipt": "Akarsh",
    "test_end_to_end": "Akarsh",
    "test_reservation": "Himansh", "test_reports": "Himansh", "test_admin_api": "Himansh", "test_performance": "Himansh",
}
MODULE_OWNERS = {
    "config": "Angelo", "errors": "Angelo", "db": "Angelo", "context": "Angelo", "security": "Angelo",
    "audit": "Angelo", "auth": "Angelo", "ingress": "Angelo", "main": "Angelo", "tls": "Angelo",
    "api/deps": "Angelo", "api/auth": "Angelo", "api/ingress": "Angelo", "__init__": "Angelo", "api/__init__": "Angelo",
    "plates": "Shweta", "hardware": "Shweta", "alerts": "Shweta", "allocation": "Shweta", "sensors": "Shweta",
    "edge_queue": "Shweta", "api/slots": "Shweta", "api/edge": "Shweta",
    "tariff": "Akarsh", "payment": "Akarsh", "egress": "Akarsh", "receipt": "Akarsh", "api/egress": "Akarsh",
    "api/receipts": "Akarsh",
    "reservation": "Himansh", "scheduler": "Himansh", "reports": "Himansh", "api/reservations": "Himansh",
    "api/admin": "Himansh", "api/reports": "Himansh",
}
PARTIAL = {"VPS-NF-002": "Monthly uptime is measured in production; soak test with zero 5xx is the lab proxy (DEV-10).",
           "VPS-F-003": "RFID-triggered opening not implemented (DEV-07); ticket-triggered opening verified."}


# ------------------------------------------------------------------ running
def pytest(args: list[str], env_extra: dict | None = None) -> int:
    env = {**os.environ, "PYTHONPATH": str(ROOT), **(env_extra or {})}
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args]
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, env=env).returncode


def run_suites() -> None:
    TMP.mkdir(exist_ok=True)
    (REPORTS / "html").mkdir(parents=True, exist_ok=True)
    for f in TMP.glob(".coverage*"):
        f.unlink()
    cov = ["--cov=vps", "--cov-branch", "--cov-report="]
    env = {"COVERAGE_FILE": str(TMP / ".coverage")}
    pytest(["tests/unit", *cov, f"--junitxml={TMP / 'junit-unit.xml'}",
            f"--html={REPORTS / 'html' / 'unit-tests.html'}", "--self-contained-html"], env)
    subprocess.run([sys.executable, "-m", "coverage", "json", "-o", str(TMP / "coverage-unit.json")], cwd=ROOT,
                   env={**os.environ, **env}, check=True)
    pytest(["tests/system", "tests/perf", *cov, "--cov-append", f"--junitxml={TMP / 'junit-system.xml'}",
            f"--html={REPORTS / 'html' / 'system-tests.html'}", "--self-contained-html"],
           {**env, "VPS_PERF_OUT": str(TMP / "perf.json")})
    for fmt, out in (("json", TMP / "coverage-all.json"), ("xml", REPORTS / "coverage.xml"),
                     ("html", REPORTS / "html" / "coverage")):
        flag = "-d" if fmt == "html" else "-o"
        subprocess.run([sys.executable, "-m", "coverage", fmt, flag, str(out)], cwd=ROOT, env={**os.environ, **env},
                       check=True)


# ------------------------------------------------------------------ parsing
def parse_junit(path: Path) -> list[dict]:
    cases = []
    for tc in ET.parse(path).getroot().iter("testcase"):
        props = defaultdict(list)
        for p in tc.iter("property"):
            props[p.get("name")].append(p.get("value"))
        outcome = "passed"
        for tag in ("failure", "error", "skipped"):
            if tc.find(tag) is not None:
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
        cls = tc.get("classname", "")
        cases.append({"file": cls.split(".")[2] if cls.count(".") >= 2 else cls, "suite": cls.split(".")[1] if "." in cls else "",
                      "class": cls.split(".")[-1] if cls.count(".") >= 3 else "", "name": tc.get("name"),
                      "time": float(tc.get("time") or 0), "outcome": outcome, "tc": props["tc"], "req": props["req"]})
    return cases


def source_line(path: str, line: int) -> str:
    try:
        return (ROOT / path).read_text().splitlines()[line - 1].strip().replace("|", "\\|")
    except (OSError, IndexError):
        return "?"


def mod_name(path: str) -> str:
    return path.replace("vps/", "").replace(".py", "")


# ------------------------------------------------------------------ writers
def header(title: str, meta: dict) -> str:
    rows = "\n".join(f"| {k} | {v} |" for k, v in meta.items())
    return f"# {title}\n\n| Field | Detail |\n|---|---|\n{rows}\n"


def env_meta() -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:  # pragma: no cover
        commit = ""
    return {"Project": "Vehicle Parking System (VPS) v1.1 — Group 6", "Generated": datetime.now(IST).strftime("%d %b %Y, %H:%M IST"),
            "Environment": f"Python {platform.python_version()} · {platform.system()} {platform.machine()}",
            "Source revision": commit or "working tree", "Prepared by": "Himansh Ahuja (QA Lead) · generated by scripts/generate_reports.py"}


def unit_report(cases: list[dict], cov_unit: dict) -> str:
    total = len(cases)
    by = defaultdict(lambda: {"n": 0, "passed": 0, "failed": 0, "skipped": 0, "time": 0.0})
    for c in cases:
        b = by[c["file"]]
        b["n"] += 1
        b["time"] += c["time"]
        b["passed" if c["outcome"] == "passed" else "skipped" if c["outcome"] == "skipped" else "failed"] += 1
    passed = sum(b["passed"] for b in by.values())
    failed = sum(b["failed"] for b in by.values())
    skipped = sum(b["skipped"] for b in by.values())
    dur = sum(c["time"] for c in cases)
    t = cov_unit["totals"]
    md = header("Unit Test Report", env_meta())
    md += f"""
## 1. Summary

| Metric | Value |
|---|---|
| Test files | {len(by)} |
| Test cases executed | **{total}** |
| Passed | **{passed}** |
| Failed / errors | {failed} |
| Skipped | {skipped} |
| Pass rate | **{100 * passed / total:.1f} %** |
| Execution time | {dur:.2f} s |
| Statement coverage (unit tests only) | {t['percent_statements_covered']:.1f} % |
| Branch coverage (unit tests only) | {100 * t['covered_branches'] / max(1, t['num_branches']):.1f} % |

**Verdict:** {"all unit tests pass" if failed == 0 else f"{failed} unit test(s) failing - see section 4"}.

Scope: every module in `vps/` is tested in isolation against an in-memory database and a controllable
clock (`tests/conftest.py`). Hardware is replaced by the simulators in `vps/hardware.py`. Each test is
tagged with the Test Case ID(s) it implements, so results trace back to the Test Case Specification.

## 2. Results by test file

| Test file | Owner | Tests | Passed | Failed | Skipped | Time (s) |
|---|---|---|---|---|---|---|
"""
    for f in sorted(by):
        b = by[f]
        md += f"| `tests/unit/{f}.py` | {OWNERS.get(f, '-')} | {b['n']} | {b['passed']} | {b['failed']} | {b['skipped']} | {b['time']:.2f} |\n"
    md += f"| **Total** | | **{total}** | **{passed}** | **{failed}** | **{skipped}** | **{dur:.2f}** |\n"
    tc_counts = defaultdict(int)
    for c in cases:
        for tc in c["tc"]:
            tc_counts[tc] += 1
    md += "\n## 3. Test cases exercised by unit tests\n\n| Test case | Unit tests |\n|---|---|\n"
    for tc in sorted(tc_counts):
        md += f"| {tc} | {tc_counts[tc]} |\n"
    md += "\n## 4. Failures\n\n"
    fails = [c for c in cases if c["outcome"] in ("failed", "error")]
    md += "None.\n" if not fails else "\n".join(f"* `{c['file']}::{c['name']}`" for c in fails) + "\n"
    md += "\n## 5. Slowest tests\n\n| Test | Time (s) |\n|---|---|\n"
    for c in sorted(cases, key=lambda c: -c["time"])[:10]:
        name = f"{c['class']}::{c['name']}" if c["class"] else c["name"]
        md += f"| `{c['file']}::{name}` | {c['time']:.3f} |\n"
    md += "\n## 6. Artefacts\n\n* Interactive HTML report: `docs/reports/html/unit-tests.html`\n" \
          "* Raw JUnit XML is produced by CI (`junit.xml` build artefact)\n" \
          "* Re-run: `pytest tests/unit -v` or `python scripts/generate_reports.py`\n"
    return md


def validation_report(all_cases: list[dict], perf: dict) -> tuple[str, dict]:
    by_tc = defaultdict(list)
    for c in all_cases:
        for tc in c["tc"]:
            by_tc[tc].append(c)
    status = {}
    for t in TEST_CASES:
        runs = by_tc.get(t["id"], [])
        if not runs:
            status[t["id"]] = ("NOT RUN", 0, 0)
        else:
            ok = sum(r["outcome"] == "passed" for r in runs)
            status[t["id"]] = ("PASS" if ok == len(runs) else "FAIL", ok, len(runs))
    n_pass = sum(s[0] == "PASS" for s in status.values())
    sys_cases = [c for c in all_cases if c["suite"] in ("system", "perf")]
    sys_pass = sum(c["outcome"] == "passed" for c in sys_cases)
    md = header("System Validation Report", env_meta())
    md += f"""
## 1. Summary

| Metric | Value |
|---|---|
| Test cases in the Test Case Specification | {len(TEST_CASES)} |
| Test cases passed | **{n_pass} / {len(TEST_CASES)}** |
| Automated tests executed (unit + system + performance) | {len(all_cases)} |
| System & performance tests passed | {sys_pass} / {len(sys_cases)} |
| SRS requirements verified | {sum(1 for r in REQUIREMENTS if req_status(r, status)[0] == 'VERIFIED')} fully, {sum(1 for r in REQUIREMENTS if req_status(r, status)[0] == 'PARTIAL')} partially, of {len(REQUIREMENTS)} |
| Exit criteria (Test Plan 5.3) | {"MET" if n_pass == len(TEST_CASES) else "NOT MET"}: all planned cases executed, no open critical/high defects, security & performance NFRs pass |

Validation approach (Test Plan §5): system tests drive complete journeys through the HTTP API
(`tests/system`), security validation runs against a live TLS 1.3 server, and performance tests load a
separate server process sized to 10,000 bays and 50 lanes (`tests/perf`).

## 2. Results by test case

| Test case | Title | Requirement(s) | Automated tests | Result |
|---|---|---|---|---|
"""
    for t in TEST_CASES:
        s, ok, n = status[t["id"]]
        md += f"| {t['id']} | {t['title']} | {', '.join(t['req'])} | {ok}/{n} passed | **{s}** |\n"

    md += "\n## 3. Requirements traceability (updated RTM)\n\n| Requirement | Description | Test cases | Status |\n|---|---|---|---|\n"
    for r, desc in REQUIREMENTS.items():
        st, tcs = req_status(r, status)
        note = f" — {PARTIAL[r]}" if r in PARTIAL else ""
        md += f"| {r} | {desc} | {', '.join(tcs) or '-'} | **{st}**{note} |\n"

    if perf:
        ing, sc, ex = perf.get("ingress", {}), perf.get("scale", {}), perf.get("exports", {})
        md += "\n## 4. Performance & scalability measurements\n\n| Measure | Target | Measured | Result |\n|---|---|---|---|\n"
        if ing:
            md += f"| Ingress round trip p90 (200 tx, HTTP) — NF-001 | ≤ 3000 ms | {ing['p90_ms']} ms (p50 {ing['p50_ms']}, p99 {ing['p99_ms']}) | {'PASS' if ing['p90_ms'] <= 3000 else 'FAIL'} |\n"
            md += f"| Server-side ingress processing p90 | — | {ing['server_side_p90_ms']} ms | info |\n"
        if sc:
            md += f"| API latency p95 under load (10,000 bays, 50 lanes, 25 clients) — NF-003 | < 200 ms | {sc['p95_ms']} ms (p50 {sc['p50_ms']}, p99 {sc['p99_ms']}) | {'PASS' if sc['p95_ms'] < 200 else 'FAIL'} |\n"
            md += f"| Throughput (closed loop, 1,000 requests) — NF-003 | 500 req/s | {sc['throughput_rps']} req/s | {'PASS' if sc['throughput_rps'] >= 500 else 'BELOW TARGET'} |\n"
            md += f"| Server errors under load | 0 | {sc['server_errors']} | {'PASS' if sc['server_errors'] == 0 else 'FAIL'} |\n"
            pe = sc.get("p95_by_endpoint_ms", {})
            if pe:
                md += f"| p95 by endpoint | — | ingress {pe.get('ingress')} · sensor {pe.get('sensor_event')} · VMS {pe.get('vms')} · nearest-slot {pe.get('nearest_slot')} ms | info |\n"
        if ex:
            md += f"| Slowest report export, 5,000-row month — F-018 | ≤ 5000 ms | {ex['max_ms']} ms | {'PASS' if ex['max_ms'] <= 5000 else 'FAIL'} |\n"
        md += "\nMeasured on the build machine; CI re-runs the suite on every push and publishes `perf-metrics.json`.\n"

    md += "\n## 5. Security validation (Test Plan 5.4)\n\n| Requirement | Validation performed | Result |\n|---|---|---|\n"
    sec = [("VPS-SR-001", "TC-SEC-01", "TLS 1.3 handshake succeeds against live server; TLS 1.2 client refused; plain HTTP not served; HSTS sent"),
           ("VPS-SR-002", "TC-SEC-02", "Argon2id hashes; AES-256-GCM ciphertext for plates/contacts/TOTP; DB dump contains no plaintext PII"),
           ("VPS-SR-003", "TC-SEC-03", "RBAC matrix across 6 protected endpoints × 4 identities; admin login requires valid TOTP; lockout"),
           ("VPS-SR-004", "TC-SEC-04", "Single-character QR tamper and re-signed clone rejected (403) with CRITICAL alert + audit"),
           ("VPS-SR-005", "TC-SEC-05", "UPDATE/DELETE refused by DB triggers; out-of-band edit detected by hash-chain verification"),
           ("VPS-NF-004", "TC-SEC-06", "No PAN in storage (last-4 only); card numbers Luhn-validated")]
    for r, tc, what in sec:
        md += f"| {r} | {what} | **{status[tc][0]}** |\n"

    md += "\n## 6. Defects found and fixed during testing\n\n| # | Found by | Defect | Fix |\n|---|---|---|---|\n"
    for i, (tc, d, f) in enumerate([
        ("TC-Scale-01", "p95 latency 880 ms / 81 req/s at 10k bays: VMS summary recomputed on every request; BaseHTTPMiddleware overhead; fsync per commit",
         "Versioned summary/VMS cache, pure-ASGI middleware, WAL synchronous=NORMAL → > 500 req/s, p95 ≈ 100–120 ms"),
        ("TC-PAY-04", "`/receipts/{id}.pdf` captured by the JSON route (`{id}` matched `abc.pdf`)", "PDF route declared first"),
        ("TC-Rel-01", "Soak test exits silently failed with 401 after session expiry (test defect)", "Soak test uses the cashless path and asserts ≥ 100 exits"),
        ("TC-SLOT-03", "Level boards listed categories with no bays (e.g. '2W: 0' on level 3)", "Boards show only categories present on the level"),
    ], start=1):
        md += f"| {i} | {tc} | {d} | {f} |\n"
    md += "\nNo open defects at sign-off.\n"
    md += "\n## 7. Artefacts\n\n* System/perf HTML report: `docs/reports/html/system-tests.html`\n* Deviations: `docs/Deviations.md`\n" \
          "* Test Case Specification: `docs/testing/Test_Case_Specification.md`\n"
    return md, status


def req_status(req: str, status: dict) -> tuple[str, list[str]]:
    tcs = [t["id"] for t in TEST_CASES if req in t["req"]]
    if not tcs:
        return "NOT COVERED", []
    if any(status[t][0] != "PASS" for t in tcs):
        return "FAILED", tcs
    return ("PARTIAL" if req in PARTIAL else "VERIFIED"), tcs


def coverage_report(cov_all: dict, cov_unit: dict) -> str:
    t = cov_all["totals"]
    md = header("Code Coverage Report", env_meta())
    md += f"""
## 1. Summary

| Metric | All suites (unit + system + perf) | Unit tests only |
|---|---|---|
| Statements | {t['num_statements']} | {cov_unit['totals']['num_statements']} |
| Statements covered | {t['covered_lines']} | {cov_unit['totals']['covered_lines']} |
| **Statement coverage** | **{t['percent_statements_covered']:.2f} %** | {cov_unit['totals']['percent_statements_covered']:.2f} % |
| Combined (statement + branch) coverage | {t['percent_covered']:.2f} % | {cov_unit['totals']['percent_covered']:.2f} % |
| CI quality gate | ≥ 90 % (`--cov-fail-under=90`) | |

Tool: coverage.py (via pytest-cov) with branch measurement enabled. Excluded: `vps/__main__.py` (CLI wrapper,
exercised as a subprocess by the performance suite) and lines marked `# pragma: no cover` (defensive branches
that cannot be reached through the public API, e.g. after a MAC has already been verified).

## 2. Statement coverage by module

| Module | Owner | Statements | Missed | Coverage | Missing lines |
|---|---|---|---|---|---|
"""
    for path, f in sorted(cov_all["files"].items()):
        s = f["summary"]
        missing = ", ".join(str(x) for x in f["missing_lines"]) or "—"
        md += f"| `{path}` | {MODULE_OWNERS.get(mod_name(path), '-')} | {s['num_statements']} | {s['missing_lines']} | " \
              f"{s['percent_statements_covered']:.1f} % | {missing} |\n"
    md += f"| **Total** | | **{t['num_statements']}** | **{t['missing_lines']}** | **{t['percent_statements_covered']:.2f} %** | |\n"
    owners = defaultdict(lambda: [0, 0])
    for path, f in cov_all["files"].items():
        o = MODULE_OWNERS.get(mod_name(path), "-")
        owners[o][0] += f["summary"]["num_statements"]
        owners[o][1] += f["summary"]["covered_lines"]
    md += "\n## 3. Coverage by team member\n\n| Member | Statements owned | Covered | Coverage |\n|---|---|---|---|\n"
    for o, (n, c) in sorted(owners.items()):
        md += f"| {o} | {n} | {c} | {100 * c / max(1, n):.1f} % |\n"
    md += "\n## 4. Lines not executed\n\nSource of every statement no test reached (taken directly from the code):\n\n" \
          "| Module | Line | Source |\n|---|---|---|\n"
    gaps = False
    for path, f in sorted(cov_all["files"].items()):
        for ln in f["missing_lines"]:
            gaps = True
            md += f"| `{path}` | {ln} | `{source_line(path, ln)}` |\n"
    if not gaps:
        md += "| — | — | every statement executed |\n"
    md += "\n## 5. Artefacts\n\n* Line-by-line HTML: `docs/reports/html/coverage/index.html`\n* Cobertura XML: `docs/reports/coverage.xml`\n"
    return md


def branch_report(cov_all: dict) -> str:
    t = cov_all["totals"]
    pct = 100 * t["covered_branches"] / max(1, t["num_branches"])
    md = header("Branch Coverage Report", env_meta())
    md += f"""
## 1. Summary

| Metric | Value |
|---|---|
| Branch points (decision outcomes) | {t['num_branches']} |
| Branches taken | {t['covered_branches']} |
| Branches never taken | {t['missing_branches']} |
| Partially covered decisions | {t['num_partial_branches']} |
| **Branch coverage** | **{pct:.2f} %** |

A *branch* is one outcome of a decision (`if`, `while`, `for`, `try/except`, boolean short-circuit) as
measured by coverage.py's arc analysis. A decision is *partial* when at least one of its outcomes was
never executed.

## 2. Branch coverage by module

| Module | Owner | Branches | Taken | Partial decisions | Branch coverage |
|---|---|---|---|---|---|
"""
    for path, f in sorted(cov_all["files"].items()):
        s = f["summary"]
        nb = s["num_branches"]
        bp = 100 * s["covered_branches"] / nb if nb else 100.0
        md += f"| `{path}` | {MODULE_OWNERS.get(mod_name(path), '-')} | {nb} | {s['covered_branches']} | " \
              f"{s['num_partial_branches']} | {bp:.1f} % |\n"
    md += f"| **Total** | | **{t['num_branches']}** | **{t['covered_branches']}** | **{t['num_partial_branches']}** | **{pct:.2f} %** |\n"
    md += "\n## 3. Branches not taken\n\n| Module | From line → to line | Meaning (source of the decision) |\n|---|---|---|\n"
    any_missing = False
    for path, f in sorted(cov_all["files"].items()):
        for a, b in f.get("missing_branches", []):
            any_missing = True
            meaning = "exit path never taken" if b < 0 else f"jump to line {b} never taken"
            md += f"| `{path}` | {a} → {'exit' if b < 0 else b} | {meaning}: `{source_line(path, a)}` |\n"
    if not any_missing:
        md += "| — | — | every branch outcome was executed |\n"
    md += """
## 4. Branch-focused test design

Boundary and decision tests written specifically to drive both outcomes of key decisions:

| Decision | Tests driving each outcome |
|---|---|
| Grace period `minutes <= 15` | 0, 1, 15 → free; 16 → charged (`test_grace_period_boundary`) |
| Daily cap `min(tiered, cap)` and 24 h blocks | 3 h (under cap), 10 h/15 h (at cap), 26 h (1 day + 2 h) |
| Surge window `start <= hour < end` | exit 18:00 IST (in), 11:30 IST (out), rule disabled |
| Coupon kind / expiry / max uses | PERCENT, FLAT capped at gross, expired, exhausted, unknown |
| Reservation window | 47.9 h accepted, 48.1 h and past rejected; check-in early / on time / late |
| No-show cut-off | start + 29 min (kept) vs + 31 min (released) |
| Barrier lower vs. loop occupied | occupied → halted; clear → auto-lower |
| Webhook | valid, bad signature, missing signature, amount mismatch, re-delivery, payment.failed |
| Edge queue | online forward, offline queue, flush while offline (no-op), 71 h vs 73 h budget |
| TLS requirement | https scheme, X-Forwarded-Proto https, plain HTTP → 426, /health exempt |

## 5. Artefacts

* Annotated source with partial branches highlighted: `docs/reports/html/coverage/index.html`
"""
    return md


def spec(status: dict, by_tc: dict) -> str:
    md = header("Test Case Specification (v1.1)", {
        "Project": "Vehicle Parking System (VPS)", "Version": "1.1 — updated after Sprints 1–2 (Part 3)",
        "Supersedes": "Test cases in Software Test Plan v1.0 §13 (16-09-2026)",
        "Owner": "Himansh Ahuja (QA Lead)", "Generated": datetime.now(IST).strftime("%d %b %Y")})
    md += f"""
This specification lists every test case, the SRS requirement it verifies, the steps and expected
result, what changed during the sprints, and the automated tests that implement it. The status column
is taken from the latest run. Total: **{len(TEST_CASES)} test cases** ({sum(1 for t in TEST_CASES if t['req'][0].startswith('VPS-F'))} functional,
{sum(1 for t in TEST_CASES if t['req'][0].startswith(('VPS-NF', 'VPS-SR')))} non-functional / security).

## 1. Summary

| Test case | Title | Requirement(s) | Type | Priority | Status |
|---|---|---|---|---|---|
"""
    for t in TEST_CASES:
        md += f"| {t['id']} | {t['title']} | {', '.join(t['req'])} | {t['type']} | {t['priority']} | {status[t['id']][0]} |\n"
    md += "\n## 2. Test case details\n"
    for t in TEST_CASES:
        tests = sorted({f"{c['suite']}/{c['file']}.py::{(c['class'] + '::') if c['class'] else ''}{c['name'].split('[')[0]}"
                        for c in by_tc.get(t["id"], [])})
        auto = "<br>".join(f"`{x}`" for x in tests[:8]) + (f"<br>… +{len(tests) - 8} more" if len(tests) > 8 else "")
        md += f"""
### {t['id']} — {t['title']}

| Field | Detail |
|---|---|
| Requirement(s) | {', '.join(f"{r} ({REQUIREMENTS[r]})" for r in t['req'])} |
| Type / priority | {t['type']} / {t['priority']} |
| Preconditions | {t['pre']} |
| Steps | {t['steps']} |
| Expected result | {t['expected']} |
| Sprint update | {t['change']} |
| Automated by | {auto or '—'} |
| Latest result | **{status[t['id']][0]}** ({status[t['id']][1]}/{status[t['id']][2]} automated tests passed) |
"""
    return md


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-run", action="store_true", help="reuse results in reports-tmp/")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    if not a.no_run:
        run_suites()
    unit = parse_junit(TMP / "junit-unit.xml")
    system = parse_junit(TMP / "junit-system.xml")
    cov_unit = json.loads((TMP / "coverage-unit.json").read_text())
    cov_all = json.loads((TMP / "coverage-all.json").read_text())
    perf = json.loads((TMP / "perf.json").read_text()) if (TMP / "perf.json").exists() else {}
    all_cases = unit + system
    by_tc = defaultdict(list)
    for c in all_cases:
        for tc in c["tc"]:
            by_tc[tc].append(c)
    REPORTS.mkdir(parents=True, exist_ok=True)
    TESTING.mkdir(parents=True, exist_ok=True)
    val_md, status = validation_report(all_cases, perf)
    docs = {
        REPORTS / "Unit_Test_Report.md": unit_report(unit, cov_unit),
        REPORTS / "System_Validation_Report.md": val_md,
        REPORTS / "Code_Coverage_Report.md": coverage_report(cov_all, cov_unit),
        REPORTS / "Branch_Coverage_Report.md": branch_report(cov_all),
        TESTING / "Test_Case_Specification.md": spec(status, by_tc),
    }
    for path, text in docs.items():
        path.write_text(text, encoding="utf-8")
        print("wrote", path.relative_to(ROOT))
    (REPORTS / "perf-metrics.json").write_text(json.dumps(perf, indent=2))
    if not a.no_pdf:
        try:
            from md2pdf import render
            for pdf in render(list(docs) + [TESTING / "Software_Test_Plan_v1.1.md"]):
                print("wrote", pdf.relative_to(ROOT))
        except ImportError:
            print("Playwright not installed - skipped PDF rendering (Markdown + HTML written)")


if __name__ == "__main__":
    main()
