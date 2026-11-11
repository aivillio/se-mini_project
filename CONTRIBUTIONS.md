# Contributions — Group 6, Vehicle Parking System

| Member | SRN | Role | Story points | PRs |
|---|---|---|---|---|
| Angelo Arakal | PES2UG24CS062 | Repo owner, tech lead, security | 39 | PR-01, PR-04, PR-08, PR-13 |
| Akarsh Parashuram | PES2UG24CS040 | Developer: billing, payments, receipts, demo videos | 33 | PR-05, PR-09, PR-12 |
| Himansh Ahuja | PES2UG24CS923 | QA lead, scrum master: reservations, admin, reports, testing docs | 29 | PR-02, PR-07, PR-14 |
| Shweta Mailaragouda Patil | PES2UG25CS825 | Developer: hardware, slots, sensors, edge queue, UI design system | 26 | PR-03, PR-06, PR-10, PR-11 |

## Backlog items owned

| Member | Requirements (GitHub issue) |
|---|---|
| Angelo Arakal | VPS-SR-002, VPS-SR-003, VPS-SR-004, VPS-SR-005, VPS-F-001 (#1), VPS-F-002 (#2), VPS-F-003 (#3), VPS-F-004 (#4), VPS-SR-001 |
| Akarsh Parashuram | VPS-F-008 (#8), VPS-F-009 (#9), VPS-F-010 (#10), VPS-F-011 (#11), VPS-F-012 (#12), VPS-F-013 (#13), VPS-NF-004 (#22), VPS-F-014 (#14) |
| Himansh Ahuja | VPS-F-015 (#15), VPS-F-016 (#16), VPS-F-017 (#17), VPS-F-018 (#18), VPS-NF-001 (#19), VPS-NF-003 (#21) |
| Shweta Mailaragouda Patil | VPS-F-005 (#5), VPS-F-006 (#6), VPS-F-007 (#7), VPS-NF-005 (#23), VPS-NF-002 (#20) |

The five security requirements (VPS-SR-001…005) get new issues from `scripts/github_setup.py`.

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

* Backlog sync (story points, owners, sprints, Project board on the requirement issues), PR/issue templates, PR automation, sprint plan
* Reservations with check-in rules and the no-show scheduler (F-015, F-016)
* Admin console API (tariffs, surge, coupons, layout, overrides, audit) and reports with CSV/PDF export (F-017, F-018)
* Booking and admin screens
* Test Plan v1.1, Test Case Specification v1.1 (38 cases), report generator; Unit Test, System Validation, Code Coverage and Branch Coverage reports
* Tests: reservation, reports, admin API unit tests; performance suite (NF-001, NF-003, F-018 volume)

## Share of the hand-written work

| Member | Story points | Application code | UI | Tests | Docs & tooling | Total lines | Share of lines |
|---|---|---|---|---|---|---|---|
| Angelo Arakal | 39 (31 %) | 1082 | 203 | 673 | 680 | 2638 | 34 % |
| Akarsh Parashuram | 33 (26 %) | 603 | 165 | 457 | 242 | 1467 | 19 % |
| Himansh Ahuja | 29 (23 %) | 486 | 313 | 430 | 1211 | 2440 | 31 % |
| Shweta Mailaragouda Patil | 26 (20 %) | 514 | 423 | 381 | 0 | 1318 | 17 % |

Lines are non-blank lines in the files each member commits. Generated output (reports, coverage HTML, PDFs, videos) is excluded.

## PR plan (merge in this order)

| # | Sprint | Owner | Branch | PR title | Closes | Files |
|---|---|---|---|---|---|---|
| PR-01 | Sprint 1 | Angelo | `feature/core-security` | Project scaffold, CI, security core, audit log, RBAC + MFA | VPS-SR-002, VPS-SR-003, VPS-SR-004, VPS-SR-005 | 29 |
| PR-02 | Sprint 1 | Himansh | `process/backlog-sprint-plan` | Backlog sync script, sprint plan, PR/issue templates, PR automation | — | 7 |
| PR-03 | Sprint 1 | Shweta | `feature/slots-sensors-edge` | Hardware simulators, slot allocation, occupancy sensors, edge queue, UI design system | VPS-F-005, VPS-F-006 | 13 |
| PR-04 | Sprint 1 | Angelo | `feature/vehicle-entry` | Vehicle entry: ANPR, signed QR ticket, entry barrier, ground-loop safety, entry kiosk UI | VPS-F-001, VPS-F-002, VPS-F-003, VPS-F-004 | 8 |
| PR-05 | Sprint 1 | Akarsh | `feature/billing-payment-exit` | Tariff engine, grace period, surge + coupons, exit scan, cashless payment, exit barrier, exit UI | VPS-F-008, VPS-F-009, VPS-F-010, VPS-F-011, VPS-F-012, VPS-F-013, VPS-NF-004 | 9 |
| PR-06 | Sprint 1 | Shweta | `feature/live-vacancy-display` | Real-time vacancy display: VMS boards and slot map with sensor LEDs | VPS-F-007 | 2 |
| PR-07 | Sprint 2 | Himansh | `feature/reservations-admin-reports` | Reservations, no-show release, admin console, reports + booking and admin UI | VPS-F-015, VPS-F-016, VPS-F-017, VPS-F-018 | 13 |
| PR-08 | Sprint 2 | Angelo | `feature/tls13` | TLS 1.3-only server runner and TOTP dev helper | VPS-SR-001 | 3 |
| PR-09 | Sprint 2 | Akarsh | `feature/gst-receipts` | GST receipts (PDF/SMS/e-mail), deviation log, Sprint 1 demo video | VPS-F-014 | 6 |
| PR-10 | Sprint 2 | Shweta | `feature/edge-api-attendant` | Edge controller API + WAN simulation, attendant POS UI | VPS-NF-005 | 4 |
| PR-11 | Sprint 3 | Shweta | `test/resilience` | Resilience and reliability tests (offline, outages, soak) | VPS-NF-002 | 2 |
| PR-12 | Sprint 3 | Akarsh | `test/end-to-end` | End-to-end journey tests and Sprint 2 demo video | — | 2 |
| PR-13 | Sprint 3 | Angelo | `test/security-validation` | Security validation suite and contribution plan | — | 3 |
| PR-14 | Sprint 3 | Himansh | `test/performance-reports` | Performance tests, Test Plan v1.1, Test Case Specification, test reports | VPS-NF-001, VPS-NF-003 | 65 |

## How the PRs are raised and merged

Every branch is already on GitHub with its owner's commit. The branches form a chain, so each one
contains the work of the PRs before it. Merging in order makes every PR show only its owner's commit.

1. **Angelo** (board owner) runs `python3 scripts/github_setup.py` once. This fills in the backlog
   and writes `PR_DESCRIPTIONS.md`, which has the title and body (with `Closes #n`) for every PR.
2. **Each member, from their own GitHub account,** opens their PRs. Go to *Pull requests → New pull request*,
   set base `main` and compare `<your branch>`, then paste the title and body from `PR_DESCRIPTIONS.md`.
   Open a PR only after the previous one in the table is merged, so its diff shows just your work.
3. **Review:** Angelo (repo owner) reviews and approves every PR. Angelo's own PRs (PR-01, 04, 08, 13) are
   approved by Himansh, because GitHub doesn't let you approve your own PR.
4. **Angelo merges** with **"Create a merge commit"** (not squash or rebase) once CI is green. The `Closes #n`
   lines close the issues automatically, and the Project cards move to *Done*.

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
