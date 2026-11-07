# Software Test Plan (STP) — Vehicle Parking System (VPS)

| | |
|---|---|
| Project | Vehicle Parking System (VPS) |
| Version | **1.1** (updated after Sprints 1–2; supersedes v1.0 of 16-09-2026) |
| Authors | QA Team — Himansh Ahuja (QA Lead), Angelo Arakal, Shweta Mailaragouda Patil, Akarsh Parashuram |
| Date | 02-11-2026 |
| Status | Approved for Sprint 3 test execution |

### Revision history

| Version | Date | Author | Change summary |
|---|---|---|---|
| 1.0 | 16-09-2026 | QA Team | Initial test plan (Part 1) |
| 1.1 | 02-11-2026 | Himansh Ahuja | Test cases updated after the sprints (38 cases, was 16); tools aligned with the implementation; schedule moved to the sprint calendar; traceability regenerated from automated test tags; performance environment re-specified |

## 1. Introduction

### 1.1 Purpose
This plan defines the objectives, scope, strategy, environment, schedule and responsibilities for verifying
VPS v1.1 against SRS v1.0 and SAD v1.0, including functionality, performance, security and resilience.

### 1.2 Scope
Testing covers vehicle entry/exit automation (ANPR, signed QR tickets, barrier and ground-loop safety), slot
allocation and sensor-driven signage, dynamic fares (tiered rates, grace period, surge, coupons, GST),
cashless payments and receipts, 48-hour reservations with no-show release, the admin console, reports,
RBAC/MFA, audit logging and 72-hour edge offline operation.

**Excluded:** core banking switch clearing, physical enclosure durability, towing/clamping enforcement,
and physical hardware (replaced by simulators — see `docs/Deviations.md` DEV-02).

### 1.3 References
* VPS Software Requirements Specification v1.0 (09-09-2026)
* VPS Software Architecture and Design Specification v1.0 (09-09-2026)
* `docs/Deviations.md` — deviations recorded during the sprints
* `docs/testing/Test_Case_Specification.md` — detailed test cases (generated, v1.1)

### 1.4 Definitions
VPS, ANPR, VMS, RTM, POS, TOTP (time-based one-time password), WAL (SQLite write-ahead log), p90/p95
(90th/95th percentile latency), SUT (system under test).

## 2. Test items

| Item | Source | Owner |
|---|---|---|
| Ingress module, lane API, entry kiosk | `vps/ingress.py`, `vps/api/ingress.py`, `web/entry.html` | Angelo |
| Security core: signer, PII vault, Argon2id, TOTP, TLS runner | `vps/security.py`, `vps/tls.py` | Angelo |
| Authentication, RBAC, audit log | `vps/auth.py`, `vps/audit.py`, `vps/api/auth.py` | Angelo |
| Hardware simulators, slot allocation, sensor hub & VMS, alerts | `vps/hardware.py`, `vps/allocation.py`, `vps/sensors.py`, `vps/alerts.py` | Shweta |
| Edge store-and-forward controller | `vps/edge_queue.py`, `vps/api/edge.py` | Shweta |
| Tariff engine, payment gateway adapter, egress, receipts | `vps/tariff.py`, `vps/payment.py`, `vps/egress.py`, `vps/receipt.py` | Akarsh |
| Reservations, scheduler, admin console, reports | `vps/reservation.py`, `vps/scheduler.py`, `vps/api/admin.py`, `vps/reports.py` | Himansh |

## 3. Features to be tested

| Requirement | Feature | Test cases |
|---|---|---|
| VPS-F-001 | ANPR capture ≤ 1.5 s, normalisation, unreadable-plate path | TC-ENT-01, TC-ENT-06, TC-SYS-04 |
| VPS-F-002 | Signed QR ticket ≤ 2 s, unique IDs, anti-passback | TC-ENT-02, TC-ENT-05 |
| VPS-F-003 / F-004 | Barrier ≤ 500 ms; loop safety halt and auto-lower | TC-ENT-03, TC-ENT-04 |
| VPS-F-005 – F-007 | Nearest-slot allocation, lot full, concurrency; LED ≤ 2 s; VMS ≤ 1 s | TC-SLOT-01 … 04 |
| VPS-F-008 – F-010 | Tiered fares and caps; 15-min grace; surge and coupons | TC-BILL-01 … 03, TC-SYS-03 |
| VPS-F-011 – F-014 | Exit lookup ≤ 1 s; UPI/card/wallet; barrier on PAID only; GST receipts | TC-PAY-01 … 05, TC-SYS-01 |
| VPS-F-015 / F-016 | 48 h reservations, check-in rules, 30-min no-show release | TC-RES-01 … 03, TC-SYS-02 |
| VPS-F-017 / F-018 | Admin configuration without restart; exports ≤ 5 s | TC-ADM-01, TC-ADM-02, TC-SYS-05 |
| VPS-NF-001 | Ingress p90 ≤ 3 s | TC-Perf-01 |
| VPS-NF-002 | Availability (lab proxy: soak test) | TC-Rel-01 |
| VPS-NF-003 | 10,000 slots, 50 lanes, p95 < 200 ms at 500 req/s | TC-Scale-01 |
| VPS-NF-004 | No plaintext card data or credentials | TC-SEC-06 |
| VPS-NF-005 | 72 h offline queuing, ordered idempotent sync ≤ 5 min | TC-Fault-01 |
| VPS-SR-001 … 005 | TLS 1.3, Argon2id/AES-256, RBAC+MFA, HMAC QR, immutable audit | TC-SEC-01 … 05 |

## 4. Features not to be tested
* Core banking clearing (gateway partner responsibility); real Razorpay/Stripe settlement.
* Physical durability, weatherproofing, towing and clamping.
* RFID pass-holder opening (not implemented — DEV-07) and multilingual audio prompts (DEV-09).
* Real monthly uptime (production monitoring only — verified partially via TC-Rel-01, DEV-10).

## 5. Test approach / strategy

### 5.1 Levels

| Level | What | How | Location |
|---|---|---|---|
| Unit | Each module in isolation: fare rules, HMAC signing, allocation, queue semantics, RBAC, etc. | pytest, in-memory SQLite, fake clock, hardware simulators | `tests/unit` |
| Integration | API ↔ services ↔ DB; signed payment webhooks; lane hardware via API | FastAPI TestClient | `tests/unit/test_*_api.py`, API classes |
| System | Complete driver / attendant / admin journeys; security validation against a live TLS server; resilience | TestClient + live uvicorn TLS 1.3 server | `tests/system` |
| Performance | NF-001 latency, NF-003 load at 10k slots / 50 lanes, F-018 export volume | Separate server process + httpx thread pool | `tests/perf` |
| Acceptance (UAT) | Facility-manager and attendant walkthrough of the six web screens against the SRS acceptance criteria | Manual, recorded in the sprint demo videos | `demo/` |

### 5.2 Types
Functional, boundary-value (grace period, 48 h window, no-show cut-off, surge window, daily cap), negative
(invalid plates, counterfeit tickets, bad signatures), concurrency (90 parallel allocations), regression (full
suite on every push via GitHub Actions), performance/load, resilience/fault-injection (WAN loss, lane controller
loss, gateway outage), and security.

### 5.3 Entry and exit criteria
* **Entry:** story merged to `main`; CI green; test data and simulators available.
* **Exit:** 100 % of test cases executed; zero open critical/high defects; all security and performance NFR cases
  pass; statement and branch coverage ≥ 90 % (enforced in CI).

### 5.4 Security validation

| Requirement | Validation |
|---|---|
| VPS-SR-001 | Live server started with the TLS 1.3-only context; TLS 1.3 client succeeds, TLS 1.2 client refused, plain HTTP not served, HSTS present; 426 when TLS is required behind a proxy |
| VPS-SR-002 | Inspect stored hashes (`$argon2id$`) and ciphertexts; full database dump searched for plaintext plates, phones, card numbers, passwords and TOTP secrets |
| VPS-SR-003 | RBAC matrix (anonymous, attendant, manager, admin × protected endpoints); TOTP mandatory for admin/manager; lockout after 5 failures; session expiry |
| VPS-SR-004 | Tampered QR body, forged signature and re-signed clone rejected with a CRITICAL alert and an audit entry |
| VPS-SR-005 | Database refuses UPDATE/DELETE on the audit table; out-of-band edits detected by hash-chain verification; retention ≥ 3 years |

## 6. Test environment

| Category | Items |
|---|---|
| Hardware | Developer laptops and GitHub-hosted Ubuntu runners; gate hardware simulated (`vps/hardware.py`) |
| Software | Python 3.11/3.12, FastAPI, uvicorn (uvloop), SQLite 3 (WAL), Chromium (Playwright) for UI recording |
| Tools | pytest, pytest-cov (branch), pytest-html, httpx, ruff, GitHub Actions, GitHub Issues/Projects |
| Test data | Indian plate formats (incl. BH series), seeded tariffs/surge/coupons, test cards 4111…1111 / 5555…4444, sandbox webhooks signed with the test secret, 10,000-bay layout for load tests |

## 7. Test schedule

| Milestone | Date |
|---|---|
| Test cases updated for sprint changes (this plan + specification v1.1) | 02-Nov-2026 |
| Unit and integration execution (continuous in CI since Sprint 1) | 19-Oct → 06-Nov-2026 |
| System, security and resilience execution | 03-Nov-2026 |
| Performance and scalability execution | 04-Nov-2026 |
| Reports generated into `docs/reports/` | 05-Nov-2026 |
| Final test sign-off | 06-Nov-2026 |

## 8. Test deliverables
* This plan (v1.1) and the Test Case Specification v1.1
* Automated suites: `tests/unit`, `tests/system`, `tests/perf`
* **Unit Test Report**, **System Validation Report**, **Code Coverage Report**, **Branch Coverage Report** — `docs/reports/`
* HTML test reports and line-level coverage — `docs/reports/html/`
* Deviation log — `docs/Deviations.md`

## 9. Roles and responsibilities

| Role | Name | Responsibility |
|---|---|---|
| QA Lead | Himansh Ahuja | Test plan, test case specification, performance suite, report generation, sign-off coordination |
| Test Engineer | Angelo Arakal | Security validation suite; unit tests for security, auth, audit and ingress |
| Test Engineer | Shweta Mailaragouda Patil | Resilience suite (edge offline, controller and gateway outage, soak); unit tests for hardware, allocation, sensors and edge |
| Software Engineer | Akarsh Parashuram | End-to-end journey suite; unit tests for tariff, payment, egress and receipts; defect fixes |
| Evaluator | Prof. Pavithra | Review outcomes and approve sign-off readiness |

## 10. Risks and mitigation

| Risk | Mitigation |
|---|---|
| Physical gate hardware unavailable | Interface-compatible simulators; UI and API controls to inject loop, sensor and fault events |
| Flaky timing on shared CI runners | Business-rule tests use a fake clock; performance job publishes metrics but does not block merges |
| Payment gateway sandbox unavailable | In-repo sandbox with the same signed-webhook contract |
| Load generator skewing server measurements | Server runs as a separate process; warm-up phase excluded from measurement |

## 11. Assumptions and dependencies
* Course calendar: Sprint 1 19–23 Oct, Sprint 2 26–30 Oct, testing 2–6 Nov 2026.
* Production deployment would replace SQLite with PostgreSQL and the sandbox with Razorpay/Stripe (DEV-01, DEV-04).

## 12. Suspension and resumption criteria
* **Suspend** if CI is red on `main` for more than 4 hours, or blocking defects affect more than 30 % of ingress/egress cases.
* **Resume** once the blocking defect fix is merged and the smoke subset (`pytest tests/system -k walk_in`) passes.

## 13. Test case management and traceability
Test cases are maintained in `scripts/test_catalog.py` and rendered into the Test Case Specification. Every
automated test carries `@pytest.mark.tc("TC-…")` and `@pytest.mark.req("VPS-…")` markers. The report generator
reads these from the JUnit output to build the updated RTM in the System Validation Report.

| Area | Test cases | Count |
|---|---|---|
| Ingress | TC-ENT-01 … 06 | 6 |
| Slots & signage | TC-SLOT-01 … 04 | 4 |
| Billing | TC-BILL-01 … 03 | 3 |
| Payment & exit | TC-PAY-01 … 05 | 5 |
| Reservations | TC-RES-01 … 03 | 3 |
| Admin & reports | TC-ADM-01, 02 | 2 |
| Non-functional | TC-Perf-01, TC-Rel-01, TC-Scale-01, TC-SEC-06, TC-Fault-01 | 5 |
| Security | TC-SEC-01 … 05 | 5 |
| System journeys | TC-SYS-01 … 05 | 5 |
| **Total** | | **38** |

## 14. Test metrics and reporting
* Executed / passed / failed / skipped per suite and per test file.
* Test case pass rate and requirement verification status (verified / partial / failed).
* Statement and branch coverage per module and per team member.
* Latency percentiles (p50/p90/p95/p99), throughput and error count for performance runs.
* Defects found and fixed during testing.

## 15. Approvals
QA Lead (Himansh Ahuja): ________________________

Course Coordinator (Prof. Sheela Devi): ________________________

Project Evaluator / Guide (Prof. Pavithra): ________________________
