# Contributions — Group 6, Vehicle Parking System

| Member | SRN | Role | Story points | PRs |
|---|---|---|---|---|
| Angelo Arakal | PES2UG24CS062 | Repo owner, tech lead, security | 40 | PR-01, PR-04, PR-08, PR-13 |
| Akarsh Parashuram | PES2UG24CS040 | Developer: billing, payments, receipts, demo videos | 36 | PR-05, PR-09, PR-12 |
| Himansh Ahuja | PES2UG24CS923 | QA lead, scrum master: reservations, admin, reports, testing docs | 33 | PR-02, PR-07, PR-14 |
| Shweta Mailaragouda Patil | PES2UG25CS825 | Developer: hardware, slots, sensors, edge queue, UI design system | 32 | PR-03, PR-06, PR-10, PR-11 |

## What each member built

**Angelo Arakal: core platform and security**

* Project scaffold, configuration, database schema, app factory with auto-discovered routers, CI pipeline
* Security core: HMAC-SHA256 ticket signing, AES-256-GCM PII vault, Argon2id passwords, RFC 6238 TOTP (SR-002, SR-004)
* Authentication with RBAC, admin MFA, lockout and sessions (SR-003); hash-chained write-once audit log (SR-005)
* Ingress module: ANPR → slot → signed QR → barrier, anti-passback, manual entry, lane safety API (F-001 to F-004, NF-001)
* TLS 1.3-only server runner (SR-001); entry kiosk and overview screens
* Tests: security, auth, audit, app/middleware, ingress, TLS unit tests; security validation suite (TLS handshake, RBAC matrix, PII at rest)

**Shweta Mailaragouda Patil: slots, sensors, edge and UI design system**

* Gate hardware simulators: ANPR camera, boom barrier, ground loop, printer, lane registry
* Nearest-slot allocation engine with transactional locking and versioned caching (F-005)
* Sensor hub with LED states and replay protection; VMS signage (F-006, F-007)
* Edge store-and-forward queue with 72 h budget and idempotent sync, plus its API (NF-005)
* Shared UI design system (`style.css`, `app.js`); live display and attendant POS screens
* Tests: hardware, allocation (including 90-thread concurrency), sensors, edge queue and API; resilience suite (WAN outage, controller and gateway outage, soak)

**Akarsh Parashuram: billing, payments and exit**

* Tariff engine: tiered rates, daily caps, 15-min grace, surge rules, coupons, GST split (F-008 to F-010)
* Payment gateway adapter: UPI QR orders, Luhn-checked cards (last 4 digits only), signed webhooks (F-012, NF-004)
* Egress flow: QR/plate lookup, checkout, webhook settlement, barrier on PAID only, cash desk (F-011, F-013)
* GST receipts: invoice numbering, thermal PDF, SMS/e-mail outbox (F-014); exit and payment screen
* Deviation log; demo recorder and both sprint demo videos
* Tests: tariff, payment, egress and receipt unit tests; end-to-end journey suite

**Himansh Ahuja: reservations, admin, reports and QA**

* Backlog with story points, GitHub Project setup script, PR/issue templates, PR automation, sprint plan
* Reservations with check-in rules and the no-show scheduler (F-015, F-016)
* Admin console API (tariffs, surge, coupons, layout, overrides, audit) and reports with CSV/PDF export (F-017, F-018)
* Booking and admin screens
* Test Plan v1.1, Test Case Specification v1.1 (38 cases), report generator; Unit Test, System Validation, Code Coverage and Branch Coverage reports
* Tests: reservation, reports, admin API unit tests; performance suite (NF-001, NF-003, F-018 volume)

## Share of the hand-written work

| Member | Story points | Application code | UI | Tests | Docs & tooling | Total lines | Share of lines |
|---|---|---|---|---|---|---|---|
| Angelo Arakal | 40 (28 %) | 1082 | 203 | 673 | 434 | 2392 | 32 % |
| Akarsh Parashuram | 36 (26 %) | 603 | 165 | 457 | 235 | 1460 | 19 % |
| Himansh Ahuja | 33 (23 %) | 486 | 313 | 430 | 1163 | 2392 | 32 % |
| Shweta Mailaragouda Patil | 32 (23 %) | 514 | 423 | 381 | 0 | 1318 | 17 % |

Lines are non-blank lines in the files each member commits. Generated output (reports, coverage HTML, PDFs, videos) is excluded.

## PR plan (merge in this order)

| # | Sprint | Owner | Branch | PR title | Files |
|---|---|---|---|---|---|
| PR-01 | Sprint 1 | Angelo | `feature/VPS-US-01-core-security` | VPS-US-01..04: project scaffold, CI, security core, audit log, RBAC + MFA | 29 |
| PR-02 | Sprint 1 | Himansh | `process/VPS-US-05-backlog` | VPS-US-05: backlog, GitHub project setup, PR/issue templates, PR automation | 7 |
| PR-03 | Sprint 1 | Shweta | `feature/VPS-US-06-slots-sensors` | VPS-US-06..10: hardware simulators, slot allocation, sensors + VMS, edge queue, UI design system | 13 |
| PR-04 | Sprint 1 | Angelo | `feature/VPS-US-11-entry` | VPS-US-11..13: vehicle entry + signed QR ticket, lane safety API, entry kiosk and overview UI | 8 |
| PR-05 | Sprint 1 | Akarsh | `feature/VPS-US-14-billing-payment` | VPS-US-14..19: tariff engine, surge + coupons, exit scan, cashless payment, exit barrier, exit UI | 9 |
| PR-06 | Sprint 1 | Shweta | `feature/VPS-US-35-live-display` | VPS-US-35: live display UI (VMS boards + slot map with sensor LEDs) | 2 |
| PR-07 | Sprint 2 | Himansh | `feature/VPS-US-20-reservations-admin` | VPS-US-20..24: 48 h reservations, no-show scheduler, admin console, reports, booking + admin UI | 13 |
| PR-08 | Sprint 2 | Angelo | `feature/VPS-US-30-tls` | VPS-US-30: TLS 1.3-only server runner and TOTP dev helper | 3 |
| PR-09 | Sprint 2 | Akarsh | `feature/VPS-US-25-receipts` | VPS-US-25..27: GST receipts (PDF/SMS/e-mail), deviation log, Sprint 1 demo video | 6 |
| PR-10 | Sprint 2 | Shweta | `feature/VPS-US-28-edge-attendant` | VPS-US-28..29: edge controller API + WAN simulation, attendant POS UI | 4 |
| PR-11 | Sprint 3 | Shweta | `test/VPS-US-31-resilience` | VPS-US-31: resilience and reliability tests (NF-005, NF-002) | 2 |
| PR-12 | Sprint 3 | Akarsh | `test/VPS-US-32-e2e` | VPS-US-32: end-to-end journey tests and Sprint 2 demo video | 2 |
| PR-13 | Sprint 3 | Angelo | `test/VPS-US-33-security-validation` | VPS-US-33: security validation suite (SR-001..005, NF-004) + contribution plan | 3 |
| PR-14 | Sprint 3 | Himansh | `test/VPS-US-34-perf-reports` | VPS-US-34: performance tests, test plan v1.1, test case specification, all test reports | 65 |

## How to commit (everyone)

Every member commits their own files from their own GitHub account and raises their own PR. Angelo
(repo owner) reviews and merges. Each PR passes CI on its own if PRs are merged **in the order above**
(this was checked by replaying all 14 PRs into an empty repo).

### Step 0: once, by Angelo

1. Create the GitHub repo **with "Add a README" ticked**, so `main` exists. Add Shweta, Akarsh and Himansh as collaborators.
2. Settings → Branches → protect `main`: require a PR, 1 approval and the `CI` checks.
3. Settings → Actions → General: allow GitHub Actions; workflow permissions "Read and write".
4. Himansh creates the backlog and the Project. This only needs the repo to exist:
   ```bash
   gh auth login && gh auth refresh -s project
   python scripts/github_setup.py --repo OWNER/REPO --users Angelo=<login>,Shweta=<login>,Akarsh=<login>,Himansh=<login>
   ```
   Then set the repo variable `PROJECT_URL` (Settings → Variables) so PRs are added to the board automatically.

### Every PR: by its owner

```bash
git clone https://github.com/OWNER/REPO.git && cd REPO
git config user.name  "Your Name"
git config user.email "the-email-on-your-GitHub-account"      # otherwise GitHub won't credit the commit to you

git checkout main && git pull                                 # always start from the latest main
python /path/to/vehicle-parking-system/scripts/stage_contribution.py copy PR-03 --to .   # use your PR number
git checkout -b feature/VPS-US-06-slots-sensors               # the branch name the script prints
pip install -r requirements-dev.txt && ruff check . && pytest tests --ignore=tests/perf   # optional local check
git add -A
git commit -m "VPS-US-06..10: hardware simulators, slot allocation, sensors + VMS, edge queue, UI design system"
git push -u origin feature/VPS-US-06-slots-sensors
```

Open the PR on GitHub. The template asks for the story ID; add `Closes #<issue>` for each story in it.
Wait for CI to go green, then ask Angelo to review.

* `/path/to/vehicle-parking-system` is the full project folder from the zip. `copy` puts exactly your PR's files into your clone.
* Splitting a PR into several commits (for example code first, then tests) is fine. Keep the same branch.
* **Angelo's own PRs** (PR-01, 04, 08, 13): GitHub doesn't let you approve your own PR. Himansh reviews and approves those, and Angelo merges.
* **Merge with "Create a merge commit"** (not squash), so each member's original commit stays in the history under their name.
* `.github/CODEOWNERS` lists the GitHub usernames (add Akarsh's once known).

### Before the last PR: Himansh

The reports in `docs/reports/` are already generated. To stamp them with the final commit hash, regenerate them on the merged `main` before committing PR-14:

```bash
python scripts/generate_reports.py      # runs all suites; rewrites docs/reports/* and docs/testing/*
```

### Demo videos

`demo/sprint1_demo.mp4` (≈ 1 min) and `demo/sprint2_demo.mp4` (≈ 2 min) were recorded from the code as it stands after
PR-06 (end of Sprint 1) and PR-10 (end of Sprint 2). They are screen recordings with on-screen captions. If you want
narration, record over them, or re-run `python demo/record_demo.py sprint1 --repo <checkout at PR-06>`.

## File list per member

<details><summary><b>Angelo Arakal (PES2UG24CS062)</b> — 43 files</summary>

| PR | File |
|---|---|
| PR-01 | `.gitignore` |
| PR-01 | `README.md` |
| PR-01 | `requirements.txt` |
| PR-01 | `requirements-dev.txt` |
| PR-01 | `pyproject.toml` |
| PR-01 | `.github/workflows/ci.yml` |
| PR-01 | `.github/CODEOWNERS` |
| PR-01 | `docs/part1/SRS_Vehicle_Parking_System.pdf` |
| PR-01 | `docs/part1/SAD_Vehicle_Parking_System.pdf` |
| PR-01 | `docs/part1/Software_Test_Plan_VPS_v1.0.pdf` |
| PR-01 | `vps/__init__.py` |
| PR-01 | `vps/config.py` |
| PR-01 | `vps/errors.py` |
| PR-01 | `vps/db.py` |
| PR-01 | `vps/context.py` |
| PR-01 | `vps/security.py` |
| PR-01 | `vps/audit.py` |
| PR-01 | `vps/auth.py` |
| PR-01 | `vps/main.py` |
| PR-01 | `vps/api/__init__.py` |
| PR-01 | `vps/api/deps.py` |
| PR-01 | `vps/api/auth.py` |
| PR-01 | `tests/__init__.py` |
| PR-01 | `tests/conftest.py` |
| PR-01 | `tests/unit/__init__.py` |
| PR-01 | `tests/unit/test_security.py` |
| PR-01 | `tests/unit/test_auth.py` |
| PR-01 | `tests/unit/test_audit.py` |
| PR-01 | `tests/unit/test_app.py` |
| PR-04 | `vps/ingress.py` |
| PR-04 | `vps/api/ingress.py` |
| PR-04 | `vps/__main__.py` |
| PR-04 | `web/index.html` |
| PR-04 | `web/entry.html` |
| PR-04 | `web/static/index.js` |
| PR-04 | `web/static/entry.js` |
| PR-04 | `tests/unit/test_ingress.py` |
| PR-08 | `vps/tls.py` |
| PR-08 | `scripts/totp.py` |
| PR-08 | `tests/unit/test_tls.py` |
| PR-13 | `tests/system/test_security_validation.py` |
| PR-13 | `CONTRIBUTIONS.md` |
| PR-13 | `scripts/stage_contribution.py` |

</details>

<details><summary><b>Akarsh Parashuram (PES2UG24CS040)</b> — 17 files</summary>

| PR | File |
|---|---|
| PR-05 | `vps/tariff.py` |
| PR-05 | `vps/payment.py` |
| PR-05 | `vps/egress.py` |
| PR-05 | `vps/api/egress.py` |
| PR-05 | `web/exit.html` |
| PR-05 | `web/static/exit.js` |
| PR-05 | `tests/unit/test_tariff.py` |
| PR-05 | `tests/unit/test_payment.py` |
| PR-05 | `tests/unit/test_egress.py` |
| PR-09 | `vps/receipt.py` |
| PR-09 | `vps/api/receipts.py` |
| PR-09 | `tests/unit/test_receipt.py` |
| PR-09 | `docs/Deviations.md` |
| PR-09 | `demo/record_demo.py` |
| PR-09 | `demo/sprint1_demo.mp4` |
| PR-12 | `tests/system/test_end_to_end.py` |
| PR-12 | `demo/sprint2_demo.mp4` |

</details>

<details><summary><b>Himansh Ahuja (PES2UG24CS923)</b> — 85 files</summary>

| PR | File |
|---|---|
| PR-02 | `backlog/backlog.csv` |
| PR-02 | `scripts/github_setup.py` |
| PR-02 | `.github/pull_request_template.md` |
| PR-02 | `.github/ISSUE_TEMPLATE/user_story.md` |
| PR-02 | `.github/labeler.yml` |
| PR-02 | `.github/workflows/pr-automation.yml` |
| PR-02 | `docs/sprints/Sprint_Plan.md` |
| PR-07 | `vps/reservation.py` |
| PR-07 | `vps/scheduler.py` |
| PR-07 | `vps/reports.py` |
| PR-07 | `vps/api/reservations.py` |
| PR-07 | `vps/api/admin.py` |
| PR-07 | `vps/api/reports.py` |
| PR-07 | `web/booking.html` |
| PR-07 | `web/admin.html` |
| PR-07 | `web/static/booking.js` |
| PR-07 | `web/static/admin.js` |
| PR-07 | `tests/unit/test_reservation.py` |
| PR-07 | `tests/unit/test_reports.py` |
| PR-07 | `tests/unit/test_admin_api.py` |
| PR-14 | `tests/perf/__init__.py` |
| PR-14 | `tests/perf/test_performance.py` |
| PR-14 | `scripts/test_catalog.py` |
| PR-14 | `scripts/generate_reports.py` |
| PR-14 | `scripts/md2pdf.py` |
| PR-14 | `docs/testing/Software_Test_Plan_v1.1.md` |
| PR-14 | `docs/testing/Software_Test_Plan_v1.1.pdf` |
| PR-14 | `docs/testing/Test_Case_Specification.md` |
| PR-14 | `docs/testing/Test_Case_Specification.pdf` |
| PR-14 | `docs/reports/Branch_Coverage_Report.md` |
| PR-14 | `docs/reports/Branch_Coverage_Report.pdf` |
| PR-14 | `docs/reports/Code_Coverage_Report.md` |
| PR-14 | `docs/reports/Code_Coverage_Report.pdf` |
| PR-14 | `docs/reports/System_Validation_Report.md` |
| PR-14 | `docs/reports/System_Validation_Report.pdf` |
| PR-14 | `docs/reports/Unit_Test_Report.md` |
| PR-14 | `docs/reports/Unit_Test_Report.pdf` |
| PR-14 | `docs/reports/coverage.xml` |
| PR-14 | `docs/reports/perf-metrics.json` |
| PR-14 | `docs/reports/html/**` (generated HTML reports) |

</details>

<details><summary><b>Shweta Mailaragouda Patil (PES2UG25CS825)</b> — 21 files</summary>

| PR | File |
|---|---|
| PR-03 | `vps/plates.py` |
| PR-03 | `vps/hardware.py` |
| PR-03 | `vps/alerts.py` |
| PR-03 | `vps/allocation.py` |
| PR-03 | `vps/sensors.py` |
| PR-03 | `vps/edge_queue.py` |
| PR-03 | `vps/api/slots.py` |
| PR-03 | `web/static/style.css` |
| PR-03 | `web/static/app.js` |
| PR-03 | `tests/unit/test_hardware.py` |
| PR-03 | `tests/unit/test_allocation.py` |
| PR-03 | `tests/unit/test_sensors.py` |
| PR-03 | `tests/unit/test_edge.py` |
| PR-06 | `web/display.html` |
| PR-06 | `web/static/display.js` |
| PR-10 | `vps/api/edge.py` |
| PR-10 | `tests/unit/test_edge_api.py` |
| PR-10 | `web/attendant.html` |
| PR-10 | `web/static/attendant.js` |
| PR-11 | `tests/system/__init__.py` |
| PR-11 | `tests/system/test_resilience.py` |

</details>
