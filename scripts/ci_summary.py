"""Write GitHub Actions job summaries (the tables shown on a workflow run's Summary page).

Each CI job calls one sub-command after it runs. Output goes to ``$GITHUB_STEP_SUMMARY`` when it is
set (inside GitHub Actions) and to stdout otherwise, so every command can be tried locally:

    python scripts/ci_summary.py lint ruff.txt 0
    python scripts/ci_summary.py tests junit.xml coverage.xml 3.12
    python scripts/ci_summary.py frontend
    python scripts/ci_summary.py security bandit.json pip-audit.json
    python scripts/ci_summary.py perf perf-metrics.json
    python scripts/ci_summary.py pipeline artifacts/        # reads JOB_<NAME>=<result> env vars
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

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
    out = [f"## {mark(ok)} Lint (ruff)", "",
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


def tests(junit: str, coverage: str, py: str) -> None:
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
    cov = ET.parse(coverage).getroot()
    line_pct = float(cov.get("line-rate", 0)) * 100
    branch_pct = float(cov.get("branch-rate", 0)) * 100
    ok = total["failed"] == 0 and line_pct >= COVERAGE_GATE
    out = [f"## {mark(ok)} Unit + system tests (Python {py})", "",
           *table(["Suite", "Tests", "Passed", "Failed", "Skipped", "Time (s)"],
                  [[name, s["total"], s["passed"], s["failed"], s["skipped"], f"{s['time']:.1f}"]
                   for name, s in sorted(suites.items())]
                  + [["**Total**", f"**{total['total']}**", f"**{total['passed']}**", f"**{total['failed']}**",
                      f"**{total['skipped']}**", f"**{total['time']:.1f}**"]]),
           "### Coverage", "",
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


# ------------------------------------------------------------------ frontend
def frontend() -> None:
    rows, ok = [], True
    for js in sorted((ROOT / "web" / "static").glob("*.js")):
        r = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True)
        good = r.returncode == 0
        ok &= good
        rows.append([f"`web/static/{js.name}`", "JS syntax (node --check)", mark(good),
                     "" if good else r.stderr.strip().splitlines()[-1]])
    for page in sorted((ROOT / "web").glob("*.html")):
        refs = re.findall(r'(?:src|href)="([^"#:]+\.(?:js|css|html))"', page.read_text())
        missing = [ref for ref in refs if not (page.parent / ref.lstrip("/").removeprefix("ui/")).exists()]
        ok &= not missing
        rows.append([f"`web/{page.name}`", f"{len(refs)} linked files exist", mark(not missing), ", ".join(missing)])
    emit([f"## {mark(ok)} Frontend checks", "", *table(["File", "Check", "Result", "Detail"], rows)])
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
    out = [f"## {mark(not blocking)} Security scan", "",
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
    names = {"LINT": "Lint (ruff)", "FRONTEND": "Frontend checks", "SECURITY": "Security scan (bandit + pip-audit)",
             "CODEQL": "CodeQL security analysis", "TESTS": "Unit + system tests (Python 3.11 and 3.12)",
             "PERFORMANCE": "Performance & scalability (non-blocking)"}
    icon = {"success": OK, "failure": BAD, "cancelled": WARN, "skipped": SKIP}
    jobs = [(label, os.environ[f"JOB_{key}"]) for key, label in names.items() if f"JOB_{key}" in os.environ]
    gating = [r for n, r in jobs if not n.startswith("Performance")]
    ok = all(r == "success" for r in gating)
    out = [f"# {mark(ok)} VPS pipeline summary", "",
           f"Commit `{os.environ.get('GITHUB_SHA', 'local')[:7]}` on `{os.environ.get('GITHUB_REF_NAME', 'local')}`", "",
           *table(["Stage", "Result"], [[n, f"{icon.get(r, '❔')} {r}"] for n, r in jobs])]

    headline = []
    base = Path(artifacts)
    for cov_file in sorted(base.glob("**/coverage.xml"))[:1]:
        c = ET.parse(cov_file).getroot()
        headline += [["Statement coverage", f"{float(c.get('line-rate', 0)) * 100:.2f}%"],
                     ["Branch coverage", f"{float(c.get('branch-rate', 0)) * 100:.2f}%"]]
    for junit in sorted(base.glob("**/junit.xml"))[:1]:
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
    cmds = {"lint": lint, "tests": tests, "frontend": frontend, "security": security, "perf": perf, "pipeline": pipeline}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]](*sys.argv[2:])


if __name__ == "__main__":
    main()
