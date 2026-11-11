# Sprint Plan — Vehicle Parking System (Group 6)

| | |
|---|---|
| Product owner / repo owner | Angelo Arakal (PES2UG24CS062) |
| QA lead / Scrum master | Himansh Ahuja (PES2UG24CS923) |
| Developers | Shweta Mailaragouda Patil (PES2UG25CS825), Akarsh Parashuram (PES2UG24CS040) |
| Backlog | One GitHub issue per requirement (#1–#23 FR/NFR + security issues), synced from `backlog/backlog.csv` by `scripts/github_setup.py` |
| Estimation | Fibonacci story points (1, 2, 3, 5, 8); 1 point ≈ half a day for one person |

## Calendar

| Dates | Activity |
|---|---|
| by 12 Oct | Backlog created in GitHub: one issue per SRS requirement, story points, owners, sprint milestones, Project linked to repo |
| 12–16 Oct | Sprint dry run (practice): branch → commit → PR → CI → review → merge on the scaffold PR |
| 19 Oct | Backlog refinement (last chance to change entries), Sprint 1 planning |
| 19–23 Oct | **Sprint 1** — walking skeleton: a car can enter, be allocated a bay, pay and leave |
| 23 Oct | Sprint 1 review + 1-minute demo video (`demo/sprint1_demo.mp4`) |
| 26–30 Oct | **Sprint 2** — reservations, admin console, reports, receipts, attendant desk, edge API, TLS |
| 30 Oct | Sprint 2 review + 2-minute demo video (`demo/sprint2_demo.mp4`), development freeze |
| 2–6 Nov | **Sprint 3 (optional, parallel)** — test hardening, performance tuning, test reports in `docs/reports/` |

## Sprint goals and committed stories

### Sprint 1 — "Drive in, pay, drive out" (79 points)

| Issue | Requirement | Title | Owner | SP | Closed by |
|---|---|---|---|---|---|
| new | VPS-SR-002 | Password Hashing and PII Encryption at Rest | Angelo | 5 | PR-01 |
| new | VPS-SR-003 | Role-Based Access Control and Admin MFA | Angelo | 8 | PR-01 |
| new | VPS-SR-004 | HMAC-Signed QR Tickets | Angelo | 3 | PR-01 |
| new | VPS-SR-005 | Immutable Audit Log | Angelo | 5 | PR-01 |
| #5 | VPS-F-005 | Nearest Vacant Parking Slot Allocation | Shweta | 5 | PR-03 |
| #6 | VPS-F-006 | Real-Time Parking Slot Occupancy Detection | Shweta | 5 | PR-03 |
| #1 | VPS-F-001 | Vehicle Number Plate Recognition | Angelo | 5 | PR-04 |
| #2 | VPS-F-002 | QR Ticket Generation | Angelo | 5 | PR-04 |
| #3 | VPS-F-003 | Entry Boom Barrier Control | Angelo | 2 | PR-04 |
| #4 | VPS-F-004 | Ground Loop Safety Check | Angelo | 3 | PR-04 |
| #8 | VPS-F-008 | Dynamic Parking Fare Calculation | Akarsh | 5 | PR-05 |
| #9 | VPS-F-009 | 15-Minute Grace Period | Akarsh | 2 | PR-05 |
| #10 | VPS-F-010 | Peak-Hour Surge Pricing and Promotional Coupons | Akarsh | 5 | PR-05 |
| #11 | VPS-F-011 | Exit QR Code or Number Plate Scanning | Akarsh | 3 | PR-05 |
| #12 | VPS-F-012 | Cashless Parking Payment | Akarsh | 8 | PR-05 |
| #13 | VPS-F-013 | Exit Barrier Control | Akarsh | 2 | PR-05 |
| #22 | VPS-NF-004 | Data Security and Payment Compliance | Akarsh | 3 | PR-05 |
| #7 | VPS-F-007 | Real-Time Parking Vacancy Display | Shweta | 5 | PR-06 |

Sprint 1 carries more points than Sprint 2 on purpose: everything else depends on the security core,
the slot engine and the entry/exit pipeline, so those had to land first for the Sprint 1 demo to be a
working product.

### Sprint 2 — "Run the car park" (37 points)

| Issue | Requirement | Title | Owner | SP | Closed by |
|---|---|---|---|---|---|
| #15 | VPS-F-015 | Advance Parking Slot Reservation | Himansh | 5 | PR-07 |
| #16 | VPS-F-016 | Automatic Reservation Release | Himansh | 3 | PR-07 |
| #17 | VPS-F-017 | Admin Configuration Console | Himansh | 8 | PR-07 |
| #18 | VPS-F-018 | Parking Reports and Analytics | Himansh | 5 | PR-07 |
| new | VPS-SR-001 | TLS 1.3 Mandatory on All Connections | Angelo | 3 | PR-08 |
| #14 | VPS-F-014 | GST Invoice Generation | Akarsh | 5 | PR-09 |
| #23 | VPS-NF-005 | Offline Operation and Data Synchronization | Shweta | 8 | PR-10 |

### Sprint 3 (optional) — "Prove it" (11 points)

| Issue | Requirement | Title | Owner | SP | Closed by |
|---|---|---|---|---|---|
| #20 | VPS-NF-002 | System Availability | Shweta | 3 | PR-11 |
| #19 | VPS-NF-001 | System Performance | Himansh | 3 | PR-14 |
| #21 | VPS-NF-003 | System Scalability | Himansh | 5 | PR-14 |

**Points per member:** Angelo 39 · Akarsh 33 · Himansh 29 · Shweta 26 (total 127).


## Definition of Done

1. Code merged to `main` through a PR raised by the story owner and approved by the repo owner.
2. CI green: ruff lint, unit + system tests on Python 3.11 and 3.12, branch coverage ≥ 90 %.
3. Every acceptance criterion has a test tagged `@pytest.mark.tc("TC-…")` that maps to the Test Case Specification.
4. Any deviation from the SRS / SAD / Test Plan is recorded in `docs/Deviations.md`.
5. The PR body says `Closes #n` for every backlog issue it completes, so merging closes the issue and its Project card moves to *Done*.

## Workflow (GitHub)

```
main ──●──────────●──────────●── (protected: PR + 1 approval + CI green)
        \        /  \        /
         feature/vehicle-entry    feature/billing-payment-exit …
```

* Branch name: `feature/<short-name>` (or `test/…`, `process/…`).
* PR body: `Closes #<issue>` for each requirement completed.
* PR automation (`.github/workflows/pr-automation.yml`) labels the PR by area, assigns the author,
  checks that the PR references a story, and adds it to the Project board.
* CI (`.github/workflows/ci.yml`) runs lint → tests with coverage → performance suite and uploads the
  JUnit, HTML test and coverage reports as build artefacts.

## Sprint review checklist

* Demo the increment against each story's acceptance criteria (use `demo/record_demo.py` to record).
* Update story status on the Project board; move unfinished stories to the next sprint and note them as spill-over.
* Record deviations discovered during the sprint in `docs/Deviations.md`.
* Retrospective: what went well / what to improve / one action item — written by the team after the review.
