"""Sync the GitHub backlog with backlog/backlog.csv (Part 2, item 1). Safe to re-run.

The repo already has one issue per FR/NFR (#1-#23). This script:
  1. creates the missing issues (the security requirements VPS-SR-001..005), never duplicates;
  2. adds to every backlog issue: assignee (owner), labels (area + story points), milestone (sprint);
  3. creates/links a GitHub Project with "Story Points" (number) and "Sprint" (single select) fields
     and fills them in for every issue;
  4. writes PR_DESCRIPTIONS.md: the title + body (with the right "Closes #n" lines) for every PR.

Requires the GitHub CLI:  gh auth login   then   gh auth refresh -s project

    python3 scripts/github_setup.py                  # do it
    python3 scripts/github_setup.py --dry-run        # just print what it would do
    python3 scripts/github_setup.py --akarsh <github-username>
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import stage_contribution as sc  # noqa: E402

REPO = "aivillio/se-mini_project"
USERS = {"Angelo": "aivillio", "Himansh": "HimanshAhuja", "Shweta": "shwetapatil7", "Akarsh": ""}
SPRINTS = {"Sprint 1": ("2026-10-23", "19-23 Oct: drive in, pay, drive out (working product)"),
           "Sprint 2": ("2026-10-30", "26-30 Oct: reservations, admin, reports, receipts, offline mode, TLS"),
           "Sprint 3": ("2026-11-06", "2-6 Nov: test hardening, performance, test reports")}
AREA = {"VPS-F-00": "functional", "VPS-NF": "non-functional", "VPS-SR": "security"}
PROJECT_TITLE = "VPS Sprint Backlog"


class GH:
    def __init__(self, dry: bool):
        self.dry = dry

    def __call__(self, *args: str, read: bool = False) -> str:
        if self.dry and not read:
            print("$ gh", " ".join(f"'{a}'" if " " in a else a for a in args))
            return ""
        res = subprocess.run(["gh", *args], text=True, capture_output=True, check=False)
        if res.returncode != 0:
            msg = (res.stderr or res.stdout).strip()
            if "already exists" not in msg and "Name has already been taken" not in msg:
                print(f"  ! gh {' '.join(args[:3])}: {msg[:200]}", file=sys.stderr)
            return ""
        return res.stdout.strip()


def req_key(title: str) -> str | None:
    """'VPS-F-005 - ...' -> VPS-F-005 ; 'NFR-004 - ...' -> VPS-NF-004 ; 'VPS-SR-001: ...' -> VPS-SR-001."""
    m = re.search(r"(VPS-F|VPS-NF|NFR|VPS-SR|SR)-(\d{3})", title)
    if not m:
        return None
    prefix = {"NFR": "VPS-NF", "SR": "VPS-SR"}.get(m.group(1), m.group(1))
    return f"{prefix}-{m.group(2)}"


def area(rid: str) -> str:
    return next(v for k, v in AREA.items() if rid.startswith(k[:6]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--akarsh", default="", help="Akarsh's GitHub username (leave out to skip assigning him)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    gh = GH(a.dry_run)
    users = {**USERS, "Akarsh": a.akarsh}
    with open(ROOT / "backlog" / "backlog.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    repo_owner = a.repo.split("/")[0]

    # ---- 1. labels + milestones -------------------------------------------------------------
    for name, colour in (("functional", "1d76db"), ("non-functional", "5319e7"), ("security", "b60205"),
                         ("process", "c5def5")):
        gh("label", "create", name, "--repo", a.repo, "--color", colour, "--force")
    for sp in sorted({r["story_points"] for r in rows}, key=int):
        gh("label", "create", f"sp:{sp}", "--repo", a.repo, "--color", "f9d0c4", "--force",
           "--description", f"{sp} story points")
    existing_ms = {m["title"] for m in json.loads(gh("api", f"repos/{a.repo}/milestones?state=all", read=True) or "[]")}
    for title, (due, desc) in SPRINTS.items():
        if title not in existing_ms:
            gh("api", f"repos/{a.repo}/milestones", "-f", f"title={title}", "-f", f"due_on={due}T18:00:00Z",
               "-f", f"description={desc}")

    # ---- 2. issues: find or create, then label / assign / milestone ------------------------
    found = {}
    for it in json.loads(gh("issue", "list", "--repo", a.repo, "--state", "all", "--limit", "300",
                            "--json", "number,title,url", read=True) or "[]"):
        key = req_key(it["title"])
        if key and key not in found:
            found[key] = it
    for r in rows:
        rid = r["id"]
        if rid not in found:
            body = (f"Requirement ID: {rid}\n\n{r['title']} (see SRS v1.0, section 5).\n\n"
                    f"Test case(s): {r['test_cases'].replace(';', ', ')}\n\nPriority: High")
            url = gh("issue", "create", "--repo", a.repo, "--title", f"{rid} – {r['title']}", "--body", body)
            num = url.rstrip("/").rsplit("/", 1)[-1] if url else f"<new:{rid}>"
            found[rid] = {"number": num, "title": f"{rid} – {r['title']}", "url": url or f"<{rid}-url>"}
            print(f"created {rid} -> #{num}")
        r["number"] = str(found[rid]["number"])
        args = ["issue", "edit", r["number"], "--repo", a.repo, "--add-label", f"{area(rid)},sp:{r['story_points']}",
                "--milestone", r["sprint"]]
        if users.get(r["owner"]):
            args += ["--add-assignee", users[r["owner"]]]
        gh(*args)
        print(f"#{r['number']:<4} {rid:<11} {r['owner']:<8} {r['story_points']:>2} SP  {r['sprint']}")

    # ---- 3. project ------------------------------------------------------------------------
    me = gh("api", "user", "--jq", ".login", read=True) or "@me"
    owner = repo_owner if me == repo_owner else "@me"
    projects = json.loads(gh("project", "list", "--owner", owner, "--format", "json", read=True) or "{}").get("projects", [])
    proj = next((p for p in projects if p["title"] == PROJECT_TITLE), None)
    if not proj:
        proj = json.loads(gh("project", "create", "--owner", owner, "--title", PROJECT_TITLE, "--format", "json") or "{}")
    number = str(proj.get("number", "<N>"))
    gh("project", "link", number, "--owner", owner, "--repo", a.repo)
    fields = json.loads(gh("project", "field-list", number, "--owner", owner, "--format", "json", read=True) or "{}")
    names = {f["name"] for f in fields.get("fields", [])}
    if "Story Points" not in names:
        gh("project", "field-create", number, "--owner", owner, "--name", "Story Points", "--data-type", "NUMBER")
    if "Sprint" not in names:
        gh("project", "field-create", number, "--owner", owner, "--name", "Sprint", "--data-type", "SINGLE_SELECT",
           "--single-select-options", ",".join(SPRINTS))
    fields = json.loads(gh("project", "field-list", number, "--owner", owner, "--format", "json", read=True) or "{}")
    sp_f = next((f for f in fields.get("fields", []) if f["name"] == "Story Points"), {"id": "<SP>"})
    sprint_f = next((f for f in fields.get("fields", []) if f["name"] == "Sprint"), {"id": "<SPRINT>", "options": []})
    for r in rows:
        item = json.loads(gh("project", "item-add", number, "--owner", owner, "--url", found[r["id"]]["url"],
                             "--format", "json") or "{}")
        if not item.get("id"):
            continue
        gh("project", "item-edit", "--id", item["id"], "--project-id", proj["id"], "--field-id", sp_f["id"],
           "--number", r["story_points"])
        opt = next((o["id"] for o in sprint_f.get("options", []) if o["name"] == r["sprint"]), None)
        if opt:
            gh("project", "item-edit", "--id", item["id"], "--project-id", proj["id"], "--field-id", sprint_f["id"],
               "--single-select-option-id", opt)

    # ---- 4. PR descriptions ---------------------------------------------------------------
    num_of = {r["id"]: r["number"] for r in rows}
    out = ["# PR titles and descriptions\n", "Open the PRs in this order. Base: `main`. Copy the title and the body.\n"]
    for pr in sc.PLAN:
        ids = [x.strip() for x in pr["closes"].split(",") if x.strip()]
        lines = [f"Closes #{num_of[i]} ({i})" for i in ids]
        if not lines:
            lines = {"PR-02": ["Sets up the sprint backlog for issues #1-#23 and the security requirement issues."],
                     "PR-12": ["Validates the functional requirements #1-#18 end to end (TC-SYS-01..05)."],
                     "PR-13": [f"Validates the security requirements {', '.join('#' + num_of[k] for k in num_of if k.startswith('VPS-SR'))}."]}[pr["pr"]]
        files = sc.pr_files(pr)
        body = "\n".join(lines) + f"\n\n**{pr['sprint']}** · owner: {pr['owner']} · {len(files)} files\n\n" \
               "- [x] `ruff check .` passes\n- [x] `pytest tests --ignore=tests/perf` passes\n"
        out.append(f"\n## {pr['pr']} — {pr['owner']} — branch `{pr['branch']}`\n\n**Title:** {pr['title']}\n\n"
                   f"**Body:**\n```\n{body}```\n")
    Path("PR_DESCRIPTIONS.md").write_text("".join(out))
    print("\nwrote PR_DESCRIPTIONS.md")
    if owner == "@me":
        print(f"Project created under {me}; if 'project link' failed, ask {repo_owner} to link it (Projects tab > Link a project).")


if __name__ == "__main__":
    main()
