"""Create the GitHub backlog for the mini-project (Part 2, item 1) from backlog/backlog.csv.

What it does (uses the GitHub CLI, so run `gh auth login` first and add the `project` scope:
`gh auth refresh -s project`):
  1. labels (areas + story-point labels) and milestones Sprint 1 / Sprint 2 / Sprint 3
  2. one issue per backlog row, assigned to its owner, labelled, in the sprint milestone
  3. a GitHub Project linked to the repo, with "Story Points" (number) and "Sprint" (single select)
     fields filled in for every issue

Usage:
  python scripts/github_setup.py --repo OWNER/REPO \
      --users Angelo=gh_user1,Shweta=gh_user2,Akarsh=gh_user3,Himansh=gh_user4 [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPRINTS = {"Sprint 1": ("2026-10-23", "19-23 Oct: walking skeleton - entry, slots, billing, payment, exit"),
           "Sprint 2": ("2026-10-30", "26-30 Oct: reservations, admin, reports, receipts, UIs, edge API"),
           "Sprint 3": ("2026-11-06", "2-6 Nov (optional): test hardening, reports, spill-over")}
AREA_COLOURS = {"ci": "6e7781", "infra": "6e7781", "security": "b60205", "process": "c5def5", "docs": "0075ca",
                "slots-and-sensors": "0e8a16", "edge-controller": "5319e7", "ingress": "1d76db",
                "billing-and-payments": "fbca04", "reservations": "d93f0b", "admin-and-reports": "006b75",
                "attendant": "bfd4f2", "tests": "e4e669", "story": "ededed"}


def run(cmd: list[str], dry: bool, capture: bool = False) -> str:
    print("$", " ".join(f"'{c}'" if " " in c else c for c in cmd))
    if dry:
        return "{}" if capture else ""
    res = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if res.returncode != 0 and "already exists" not in (res.stderr or ""):
        print(res.stderr.strip(), file=sys.stderr)
    return res.stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="OWNER/REPO")
    ap.add_argument("--users", required=True, help="Name=githubLogin,... for Angelo, Shweta, Akarsh, Himansh")
    ap.add_argument("--project-title", default="VPS - Mini Project Backlog")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    owner = a.repo.split("/")[0]
    users = dict(kv.split("=", 1) for kv in a.users.split(","))
    rows = list(csv.DictReader(open(ROOT / "backlog" / "backlog.csv", newline="")))

    # 1. labels + milestones
    for name, colour in AREA_COLOURS.items():
        run(["gh", "label", "create", name, "--repo", a.repo, "--color", colour, "--force"], a.dry_run)
    for sp in sorted({r["story_points"] for r in rows}, key=int):
        run(["gh", "label", "create", f"sp:{sp}", "--repo", a.repo, "--color", "f9d0c4", "--force"], a.dry_run)
    for title, (due, desc) in SPRINTS.items():
        run(["gh", "api", f"repos/{a.repo}/milestones", "-f", f"title={title}", "-f", f"due_on={due}T18:00:00Z",
             "-f", f"description={desc}"], a.dry_run)

    # 2. project + fields
    proj = json.loads(run(["gh", "project", "create", "--owner", owner, "--title", a.project_title, "--format", "json"],
                          a.dry_run, capture=True) or "{}")
    number = str(proj.get("number", "<PROJECT_NUMBER>"))
    run(["gh", "project", "link", number, "--owner", owner, "--repo", a.repo], a.dry_run)
    run(["gh", "project", "field-create", number, "--owner", owner, "--name", "Story Points", "--data-type", "NUMBER"],
        a.dry_run)
    run(["gh", "project", "field-create", number, "--owner", owner, "--name", "Sprint", "--data-type",
         "SINGLE_SELECT", "--single-select-options", ",".join(SPRINTS)], a.dry_run)
    fields = json.loads(run(["gh", "project", "field-list", number, "--owner", owner, "--format", "json"],
                            a.dry_run, capture=True) or "{}").get("fields", [])
    sp_field = next((f for f in fields if f["name"] == "Story Points"), {"id": "<SP_FIELD>"})
    sprint_field = next((f for f in fields if f["name"] == "Sprint"), {"id": "<SPRINT_FIELD>", "options": []})
    project_id = proj.get("id", "<PROJECT_ID>")

    # 3. issues -> project items
    for r in rows:
        body = (f"**User story:** {r['user_story']}\n\n**SRS requirements:** {r['requirements']}\n\n"
                f"**Test cases:** {r['test_cases']}\n\n**Story points:** {r['story_points']}\n\n"
                f"**Planned PR:** {r['pr']} (see CONTRIBUTIONS.md)")
        labels = ",".join([*(x.strip() for x in r["labels"].split(",")), "story", f"sp:{r['story_points']}"])
        url = run(["gh", "issue", "create", "--repo", a.repo, "--title", f"{r['id']}: {r['title']}", "--body", body,
                   "--label", labels, "--milestone", r["sprint"], "--assignee", users.get(r["owner"], "")],
                  a.dry_run, capture=True) or f"<{r['id']}-url>"
        item = json.loads(run(["gh", "project", "item-add", number, "--owner", owner, "--url", url, "--format", "json"],
                              a.dry_run, capture=True) or "{}")
        item_id = item.get("id", "<ITEM_ID>")
        run(["gh", "project", "item-edit", "--id", item_id, "--project-id", project_id, "--field-id", sp_field["id"],
             "--number", r["story_points"]], a.dry_run)
        opt = next((o["id"] for o in sprint_field.get("options", []) if o["name"] == r["sprint"]), "<OPTION_ID>")
        run(["gh", "project", "item-edit", "--id", item_id, "--project-id", project_id, "--field-id",
             sprint_field["id"], "--single-select-option-id", opt], a.dry_run)
    print(f"\nDone: {len(rows)} stories. Set repo variable PROJECT_URL (Settings > Variables) to auto-add PRs.")


if __name__ == "__main__":
    main()
