"""Write GitHub Actions job summaries (the tables shown on a workflow run's Summary page).

Each CI job calls one sub-command after it runs. Output goes to ``$GITHUB_STEP_SUMMARY`` when it is
set (inside GitHub Actions) and to stdout otherwise, so every command can be tried locally:

    python scripts/ci_summary.py build
    python scripts/ci_summary.py lint ruff.txt 0
    python scripts/ci_summary.py tests junit.xml coverage.xml "Backend Testing (Python 3.12)"
    python scripts/ci_summary.py tests junit-frontend.xml - "Frontend Testing"
    python scripts/ci_summary.py eslint eslint.json
    python scripts/ci_summary.py frontend-security
    python scripts/ci_summary.py security bandit.json pip-audit.json
    python scripts/ci_summary.py perf perf-metrics.json
    python scripts/ci_summary.py pipeline artifacts/        # reads JOB_<NAME>=<result> env vars
"""

from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

COVERAGE_GATE = 90.0
# reviewed bandit findings: why each one is not a vulnerability
REVIEWED = {
    "B608": "Only a fixed WHERE clause chosen in code is interpolated; user values are bound `?` parameters",
    "B105": "Development-only fallback secret; production sets VPS_MASTER_SECRET (see README)",
}
OK, BAD, WARN, SKIP = "✅", "❌", "⚠️", "⏭️"


def emit(lines: list[str]) -> None:
    text = "\n".join(lines) + "\n"
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


def table(headers: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out + [""]


def mark(ok: bool) -> str:
    return OK if ok else BAD


# ------------------------------------------------------------------ lint
def lint(report: str, exit_code: str) -> None:
    text = Path(report).read_text() if Path(report).exists() else ""
    issues = [ln for ln in text.splitlines() if re.match(r"^[^:\s]+:\d+:\d+:", ln)]
    files = len(list(ROOT.glob("vps/**/*.py")) + list(ROOT.glob("tests/**/*.py")) + list(ROOT.glob("scripts/*.py")))
    by_rule: dict[str, int] = defaultdict(int)
    for ln in issues:
        m = re.search(r"\s([A-Z]+\d+)\s", ln)
        by_rule[m.group(1) if m else "?"] += 1
    ok = exit_code == "0"
    out = [f"## {mark(ok)} Backend Linting (ruff)", "",
           *table(["Check", "Result"], [["Python files checked", files], ["Issues found", len(issues)],
                                        ["Rules", "pycodestyle (E/W), pyflakes (F), isort (I), bugbear (B)"],
                                        ["Line length", "125"], ["Status", "Passed" if ok else "Failed"]])]
    if issues:
        out += ["### Issues by rule", "", *table(["Rule", "Count"], sorted(by_rule.items())),
                "<details><summary>All issues</summary>", "", "```", *issues[:200], "```", "</details>", ""]
    emit(out)


# ------------------------------------------------------------------ tests
def _suite(classname: str) -> str:
    parts = classname.split(".")
    return parts[1] if len(parts) > 1 and parts[0] == "tests" else "other"


def tests(junit: str, coverage: str, title: str) -> None:
    root = ET.parse(junit).getroot()
    suites: dict[str, dict] = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "time": 0.0})
    tc_map: dict[str, dict] = defaultdict(lambda: {"req": set(), "tests": 0, "failed": 0})
    failures = []
    for case in root.iter("testcase"):
        s = suites[_suite(case.get("classname", ""))]
        s["total"] += 1
        s["time"] += float(case.get("time") or 0)
        if case.find("failure") is not None or case.find("error") is not None:
            s["failed"] += 1
            failures.append(f"{case.get('classname')}::{case.get('name')}")
            outcome_failed = True
        elif case.find("skipped") is not None:
            s["skipped"] += 1
            outcome_failed = False
        else:
            s["passed"] += 1
            outcome_failed = False
        props = defaultdict(list)
        for p in case.iter("property"):
            props[p.get("name")].append(p.get("value"))
        for tc in props["tc"]:
            tc_map[tc]["tests"] += 1
            tc_map[tc]["failed"] += outcome_failed
            tc_map[tc]["req"].update(props["req"])

    total = {k: sum(s[k] for s in suites.values()) for k in ("total", "passed", "failed", "skipped", "time")}
    has_cov = coverage not in ("", "-") and Path(coverage).exists()
    line_pct = branch_pct = 0.0
    if has_cov:
        cov = ET.parse(coverage).getroot()
        line_pct = float(cov.get("line-rate", 0)) * 100
        branch_pct = float(cov.get("branch-rate", 0)) * 100
    ok = total["failed"] == 0 and (not has_cov or line_pct >= COVERAGE_GATE)
    out = [f"## {mark(ok)} {title}", "",
           *table(["Suite", "Tests", "Passed", "Failed", "Skipped", "Time (s)"],
                  [[name, s["total"], s["passed"], s["failed"], s["skipped"], f"{s['time']:.1f}"]
                   for name, s in sorted(suites.items())]
                  + [["**Total**", f"**{total['total']}**", f"**{total['passed']}**", f"**{total['failed']}**",
                      f"**{total['skipped']}**", f"**{total['time']:.1f}**"]])]
    if has_cov:
        out += ["### Coverage", "",
                *table(["Metric", "Value", f"Gate (≥ {COVERAGE_GATE:.0f}%)"],
                       [["Statement coverage", f"{line_pct:.2f}%", mark(line_pct >= COVERAGE_GATE)],
                        ["Branch coverage", f"{branch_pct:.2f}%", mark(branch_pct >= COVERAGE_GATE)]])]
        modules = []
        for cls in cov.iter("class"):
            fn = cls.get("filename", "")
            lines = cls.findall("./lines/line")
            branches = [ln for ln in lines if ln.get("branch") == "true"]
            modules.append([f"`vps/{fn}`", len(lines), f"{float(cls.get('line-rate', 0)) * 100:.1f}%",
                            f"{float(cls.get('branch-rate', 0)) * 100:.1f}%" if branches else "n/a"])
        out += ["<details><summary>Coverage by module</summary>", "",
                *table(["Module", "Statements", "Statement %", "Branch %"], sorted(modules)), "</details>", ""]
    else:
        names = sorted({c.get("name", "").split("[")[0] for c in root.iter("testcase")})
        out += ["### Checks", "", *[f"- `{n}`" for n in names], ""]

    if tc_map:
        try:
            import test_catalog
            titles = {c["id"]: c["title"] for c in test_catalog.TEST_CASES}
        except Exception:  # pragma: no cover - catalogue is optional for the summary
            titles = {}
        rows = [[tc, titles.get(tc, ""), ", ".join(sorted(d["req"])), d["tests"], mark(d["failed"] == 0)]
                for tc, d in sorted(tc_map.items())]
        passed_tc = sum(1 for d in tc_map.values() if d["failed"] == 0)
        out += [f"### Test cases (Test Case Specification): {passed_tc} / {len(tc_map)} passed", "",
                "<details><summary>Traceability: test case → requirement → automated tests</summary>", "",
                *table(["Test case", "Title", "Requirements", "Tests", "Result"], rows), "</details>", ""]
    if failures:
        out += ["### Failed tests", "", *[f"- `{f}`" for f in failures], ""]
    emit(out)


# ------------------------------------------------------------------ build
def build() -> None:
    import compileall
    import platform
    from importlib import metadata

    compiled = compileall.compile_dir(str(ROOT / "vps"), quiet=1) and compileall.compile_dir(str(ROOT / "scripts"), quiet=1)
    from fastapi.testclient import TestClient

    from vps import __version__
    from vps.config import Settings
    from vps.main import create_app

    client = TestClient(create_app(Settings(db_path=":memory:", edge_db_path=":memory:")))
    spec = client.get("/openapi.json", headers={"X-Forwarded-Proto": "https"}).json()
    endpoints = sum(len(ops) for ops in spec["paths"].values())
    health = client.get("/health").json()
    req = [ln.split(">=")[0].split("[")[0].strip() for ln in (ROOT / "requirements.txt").read_text().splitlines()
           if ln.strip() and not ln.startswith("#")]
    versions = []
    for name in req:
        try:
            versions.append([name, metadata.version(name)])
        except metadata.PackageNotFoundError:
            versions.append([name, "not installed"])
    ok = bool(compiled) and health.get("status") == "ok"
    emit([f"## {mark(ok)} Build and Setup", "",
          *table(["Step", "Result"], [
              ["Python", platform.python_version()],
              ["Dependencies installed", f"{len(req)} runtime packages from requirements.txt (+ dev tools)"],
              ["Byte-compile `vps/` and `scripts/`", mark(bool(compiled))],
              ["App starts (`create_app`)", f"{OK} VPS v{__version__}"],
              ["REST endpoints registered", endpoints],
              ["`/health`", f"{mark(health.get('status') == 'ok')} {health}"],
              ["UI pages", len(list((ROOT / "web").glob("*.html")))]]),
          "<details><summary>Runtime package versions</summary>", "", *table(["Package", "Version"], versions),
          "</details>", ""])
    if not ok:
        sys.exit(1)


# ------------------------------------------------------------------ eslint
def eslint(report: str) -> None:
    data = json.loads(Path(report).read_text()) if Path(report).exists() else []
    errors = sum(f["errorCount"] for f in data)
    warnings = sum(f["warningCount"] for f in data)
    rows = [[f"`{Path(f['filePath']).relative_to(ROOT)}`", f["errorCount"], f["warningCount"],
             mark(f["errorCount"] == 0)] for f in data]
    out = [f"## {mark(errors == 0)} Frontend Linting (ESLint)", "",
           *table(["Check", "Result"], [["Files linted", len(data)], ["Errors", errors], ["Warnings", warnings],
                                        ["Rules", "eslint:recommended + eqeqeq, no-eval, no-implied-eval, no-new-func, "
                                                  "no-script-url, no-unused-vars"]]),
           *table(["File", "Errors", "Warnings", "Result"], rows)]
    problems = [[f"`{Path(f['filePath']).name}:{m.get('line')}`", m.get("ruleId"), m.get("message")]
                for f in data for m in f["messages"]]
    if problems:
        out += table(["Location", "Rule", "Message"], problems[:100])
    emit(out)


# ------------------------------------------------------------------ frontend security
def frontend_security() -> None:
    js = {p.name: p.read_text() for p in sorted((ROOT / "web" / "static").glob("*.js"))}
    html = {p.name: p.read_text() for p in sorted((ROOT / "web").glob("*.html"))}
    checks = [
        ("HTML-injection sinks (innerHTML, outerHTML, insertAdjacentHTML, document.write)",
         r"\.(?:innerHTML|outerHTML)\s*[+]?=|insertAdjacentHTML|document\.write", js),
        ("Dynamic code execution (eval, new Function, string setTimeout/setInterval)",
         r"\beval\s*\(|new\s+Function\s*\(|set(?:Timeout|Interval)\s*\(\s*[\"'`]", js),
        ("javascript: URLs", r"javascript:", {**js, **html}),
        ("Inline scripts in pages (blocked by CSP script-src 'self')", r"<script(?![^>]*\bsrc=)[^>]*>", html),
        ("Inline event handlers in pages (onclick=...)", r"\son[a-z]+\s*=\s*[\"']", html),
        ("Third-party script or style sources", r"""(?:src|href)=["']https?://""", html),
        ("Hard-coded credentials or keys in browser code",
         r"""\b(?:password|passwd|secret|api[_-]?key|token)["']?\s*[:=]\s*["'][^"'\s]{4,}["']""", js),
        ("Session token kept in localStorage (should be sessionStorage)", r"localStorage\.setItem\(\s*[\"']vps_token", js),
    ]
    rows, ok = [], True
    for title, pattern, files in checks:
        hits = [f"{name}:{src[:m.start()].count(chr(10)) + 1}" for name, src in files.items()
                for m in re.finditer(pattern, src, re.I)]
        ok &= not hits
        rows.append([title, len(hits), mark(not hits), ", ".join(hits[:10])])
    from vps.main import SECURITY_HEADERS
    csp = SECURITY_HEADERS.get("Content-Security-Policy", "")
    header_rows = [[k, f"`{v}`"] for k, v in SECURITY_HEADERS.items()]
    csp_ok = "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
    ok &= csp_ok
    emit([f"## {mark(ok)} Frontend Security Scan", "",
          f"Scanned {len(js)} scripts and {len(html)} pages in `web/`.", "",
          *table(["Check", "Findings", "Result", "Where"], rows),
          f"### {mark(csp_ok)} Security headers sent with every page", "", *table(["Header", "Value"], header_rows),
          "The UI builds all DOM with `createElement` + `textContent` (helper `h()` in app.js), so API data is never "
          "parsed as HTML.", ""])
    if not ok:
        sys.exit(1)


# ------------------------------------------------------------------ security
def security(bandit_json: str, audit_json: str) -> None:
    b = json.loads(Path(bandit_json).read_text()) if Path(bandit_json).exists() else {"results": [], "metrics": {}}
    results = b.get("results", [])
    loc = b.get("metrics", {}).get("_totals", {}).get("loc", "?")
    sev: dict[str, int] = defaultdict(int)
    for r in results:
        sev[r["issue_severity"]] += 1
    blocking = [r for r in results if r["issue_severity"] in ("MEDIUM", "HIGH") and r["issue_confidence"] in ("MEDIUM", "HIGH")]
    out = [f"## {mark(not blocking)} Backend Security Scan", "",
           "### Static analysis (bandit) on `vps/`", "",
           *table(["Lines scanned", "High", "Medium", "Low", "Blocking (≥ medium severity and confidence)"],
                  [[loc, sev["HIGH"], sev["MEDIUM"], sev["LOW"], len(blocking)]])]
    if results:
        out += table(["Location", "Rule", "Severity / confidence", "Finding", "Assessment"],
                     [[f"`{r['filename']}:{r['line_number']}`", r["test_id"],
                       f"{r['issue_severity'].lower()} / {r['issue_confidence'].lower()}", r["issue_text"],
                       "**blocking**" if r in blocking else REVIEWED.get(r["test_id"], "non-blocking (low confidence)")] for r in results])
    deps: list = []
    if Path(audit_json).exists():
        data = json.loads(Path(audit_json).read_text() or "{}")
        deps = data.get("dependencies", data if isinstance(data, list) else [])
    vulns = [(d["name"], d.get("version", ""), v) for d in deps for v in d.get("vulns", [])]
    out += ["### Dependency audit (pip-audit) of `requirements.txt`", "",
            *table(["Packages audited", "Known vulnerabilities"], [[len(deps), len(vulns)]])]
    if vulns:
        out += table(["Package", "Version", "Advisory", "Fixed in"],
                     [[n, ver, v.get("id", ""), ", ".join(v.get("fix_versions", []))] for n, ver, v in vulns])
    out += ["Payment and PII controls (TLS 1.3, AES-256-GCM, Argon2id, HMAC tickets, audit chain) are verified "
            "functionally by `tests/system/test_security_validation.py` in the test job.", ""]
    emit(out)
    if blocking:
        sys.exit(1)


# ------------------------------------------------------------------ performance
def perf(metrics_json: str) -> None:
    if not Path(metrics_json).exists():
        emit(["## ⚠️ Performance & scalability", "", "No metrics file was produced.", ""])
        return
    m = json.loads(Path(metrics_json).read_text())
    out = ["## Performance & scalability (NF-001 / NF-003 / F-018)", ""]
    if "ingress" in m:
        i = m["ingress"]
        out += [f"### {mark(i['p90_ms'] <= i['target_p90_ms'])} NF-001 entry transaction latency "
                f"({i['transactions']} entries)", "",
                *table(["p50", "p90", "p99", "max", "server-side p90", "Target p90"],
                       [[f"{i['p50_ms']} ms", f"**{i['p90_ms']} ms**", f"{i['p99_ms']} ms", f"{i['max_ms']} ms",
                         f"{i['server_side_p90_ms']} ms", f"≤ {i['target_p90_ms'] / 1000:.0f} s"]])]
    if "scale" in m:
        s = m["scale"]
        good = s["p95_ms"] <= s["target_p95_ms"] and s["server_errors"] == 0
        out += [f"### {mark(good)} NF-003 scalability: {s['slots']:,} slots, {s['lanes']} lanes, "
                f"{s['concurrency']} concurrent clients, {s['requests']:,} requests", "",
                *table(["Throughput", "p50", "p95", "p99", "Server errors", "Target p95"],
                       [[f"**{s['throughput_rps']} req/s**", f"{s['p50_ms']} ms", f"**{s['p95_ms']} ms**",
                         f"{s['p99_ms']} ms", s["server_errors"], f"≤ {s['target_p95_ms']} ms"]]),
                *table(["Endpoint", "p95"], [[k, f"{v} ms"] for k, v in s["p95_by_endpoint_ms"].items()])]
    if "exports" in m:
        e = m["exports"]
        out += [f"### {mark(e['max_ms'] <= e['target_ms'])} F-018 report export ({e['rows']:,} rows)", "",
                *table(["Export", "Time"], [[k, f"{v} ms"] for k, v in e["times_ms"].items()]
                       + [["**Slowest**", f"**{e['max_ms']} ms** (target ≤ {e['target_ms'] / 1000:.0f} s)"]])]
    emit(out)


# ------------------------------------------------------------------ pipeline
def pipeline(artifacts: str) -> None:
    names = {"BUILD": "Build and Setup", "BACKEND_TESTS": "Backend Testing (Python 3.11 + 3.12)",
             "FRONTEND_TESTS": "Frontend Testing", "BACKEND_LINT": "Backend Linting (ruff)",
             "FRONTEND_LINT": "Frontend Linting (ESLint)", "BACKEND_SECURITY": "Backend Security Scan (bandit + pip-audit)",
             "FRONTEND_SECURITY": "Frontend Security Scan", "CODEQL": "CodeQL Security Analysis",
             "PERFORMANCE": "Performance & Scalability (non-blocking)"}
    icon = {"success": OK, "failure": BAD, "cancelled": WARN, "skipped": SKIP}
    jobs = [(label, os.environ[f"JOB_{key}"]) for key, label in names.items() if f"JOB_{key}" in os.environ]
    gating = [r for n, r in jobs if not n.startswith("Performance")]
    ok = all(r == "success" for r in gating)
    out = [f"# {mark(ok)} VPS pipeline summary", "",
           f"Commit `{os.environ.get('GITHUB_SHA', 'local')[:7]}` on `{os.environ.get('GITHUB_REF_NAME', 'local')}`", "",
           *table(["Stage", "Result"], [[n, f"{icon.get(r, '❔')} {r}"] for n, r in jobs])]

    headline = []
    base = Path(artifacts)
    for cov_file in sorted(base.glob("**/coverage.xml"))[-1:]:
        c = ET.parse(cov_file).getroot()
        headline += [["Statement coverage", f"{float(c.get('line-rate', 0)) * 100:.2f}%"],
                     ["Branch coverage", f"{float(c.get('branch-rate', 0)) * 100:.2f}%"]]
    for junit in sorted(base.glob("**/junit.xml"))[-1:]:
        cases = list(ET.parse(junit).getroot().iter("testcase"))
        failed = sum(1 for c in cases if c.find("failure") is not None or c.find("error") is not None)
        tcs = {p.get("value") for p in ET.parse(junit).getroot().iter("property") if p.get("name") == "tc"}
        headline += [["Automated tests (unit + system)", f"{len(cases) - failed} / {len(cases)} passed"],
                     ["Test cases covered", len(tcs)]]
    for pj in sorted(base.glob("**/perf-metrics.json"))[:1]:
        m = json.loads(pj.read_text())
        if "ingress" in m:
            headline.append(["NF-001 entry p90", f"{m['ingress']['p90_ms']} ms (target ≤ 3 s)"])
        if "scale" in m:
            s = m["scale"]
            headline.append(["NF-003 at 10k slots / 50 lanes", f"{s['throughput_rps']} req/s, p95 {s['p95_ms']} ms, "
                                                               f"{s['server_errors']} errors"])
        if "exports" in m:
            headline.append(["F-018 slowest export", f"{m['exports']['max_ms']} ms (target ≤ 5 s)"])
    if headline:
        out += ["### Key results", "", *table(["Metric", "Value"], headline)]
    out += ["Performance runs on shared runners, so it is reported but does not block merging.", ""]
    emit(out)


def main() -> None:
    cmds = {"build": build, "lint": lint, "tests": tests, "eslint": eslint, "frontend-security": frontend_security,
            "security": security, "perf": perf, "pipeline": pipeline}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]](*sys.argv[2:])


if __name__ == "__main__":
    main()
