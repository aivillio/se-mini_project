# Sprint Plan — Vehicle Parking System (Group 6)

| | |
|---|---|
| Product owner / repo owner | Angelo Arakal (PES2UG24CS062) |
| QA lead / Scrum master | Himansh Ahuja (PES2UG24CS923) |
| Developers | Shweta Mailaragouda Patil (PES2UG25CS825), Akarsh Parashuram (PES2UG24CS040) |
| Backlog | `backlog/backlog.csv` → GitHub Issues + Project via `scripts/github_setup.py` |
| Estimation | Fibonacci story points (1, 2, 3, 5, 8); 1 point ≈ half a day for one person |

## Calendar

| Dates | Activity |
|---|---|
| by 12 Oct | Backlog created in GitHub from SRS FRs/NFRs/SRs, story points assigned, stories assigned to members, project linked to repo |
| 12–16 Oct | Sprint dry run (practice): branch → commit → PR → CI → review → merge on the scaffold PR |
| 19 Oct | Backlog refinement (last chance to change entries), Sprint 1 planning |
| 19–23 Oct | **Sprint 1** — walking skeleton: a car can enter, be allocated a bay, pay and leave |
| 23 Oct | Sprint 1 review + 1-minute demo video (`demo/sprint1_demo.mp4`) |
| 26–30 Oct | **Sprint 2** — reservations, admin console, reports, receipts, attendant desk, edge API, TLS |
| 30 Oct | Sprint 2 review + 2-minute demo video (`demo/sprint2_demo.mp4`), development freeze |
| 2–6 Nov | **Sprint 3 (optional, parallel)** — test hardening, performance tuning, test reports in `docs/reports/` |

## Sprint goals and committed stories

### Sprint 1 — "Drive in, pay, drive out" (85 points)

| Story | Title | Owner | SP | PR |
|---|---|---|---|---|
| VPS-US-01 | Project scaffold and CI pipeline | Angelo | 3 | PR-01 |
| VPS-US-02 | Security core: signed tickets and encrypted PII | Angelo | 5 | PR-01 |
| VPS-US-03 | Immutable audit log | Angelo | 5 | PR-01 |
| VPS-US-04 | Staff login with RBAC and admin MFA | Angelo | 8 | PR-01 |
| VPS-US-05 | Backlog GitHub project and PR process | Himansh | 2 | PR-02 |
| VPS-US-06 | Gate hardware simulators | Shweta | 5 | PR-03 |
| VPS-US-07 | Nearest vacant slot allocation | Shweta | 5 | PR-03 |
| VPS-US-08 | Slot occupancy sensors and LEDs | Shweta | 3 | PR-03 |
| VPS-US-09 | VMS availability boards | Shweta | 3 | PR-03 |
| VPS-US-10 | Edge store-and-forward queue | Shweta | 5 | PR-03 |
| VPS-US-11 | Vehicle entry and QR ticket | Angelo | 8 | PR-04 |
| VPS-US-12 | Lane safety loop and barrier API | Angelo | 2 | PR-04 |
| VPS-US-13 | Entry kiosk and overview UI | Angelo | 3 | PR-04 |
| VPS-US-14 | Tariff engine with grace period | Akarsh | 5 | PR-05 |
| VPS-US-15 | Exit scan and invoice | Akarsh | 3 | PR-05 |
| VPS-US-16 | Cashless payment via gateway webhook | Akarsh | 8 | PR-05 |
| VPS-US-17 | Exit barrier on PAID only | Akarsh | 2 | PR-05 |
| VPS-US-18 | Exit and payment UI | Akarsh | 3 | PR-05 |
| VPS-US-19 | Surge pricing and promo coupons | Akarsh | 5 | PR-05 |
| VPS-US-35 | Live display UI | Shweta | 2 | PR-06 |

Sprint 1 carries more points than Sprint 2 on purpose: everything else depends on the security core,
the slot engine and the entry/exit pipeline, so those had to land first for the Sprint 1 demo to be a
working product.

### Sprint 2 — "Run the car park" (42 points)

| Story | Title | Owner | SP | PR |
|---|---|---|---|---|
| VPS-US-20 | 48-hour slot pre-booking | Himansh | 5 | PR-07 |
| VPS-US-21 | No-show auto release | Himansh | 3 | PR-07 |
| VPS-US-22 | Admin console | Himansh | 8 | PR-07 |
| VPS-US-23 | Revenue occupancy and turnaround reports | Himansh | 5 | PR-07 |
| VPS-US-24 | Booking and admin UI | Himansh | 5 | PR-07 |
| VPS-US-30 | TLS 1.3 server and dev tooling | Angelo | 3 | PR-08 |
| VPS-US-25 | GST tax receipts | Akarsh | 5 | PR-09 |
| VPS-US-26 | Deviation log | Akarsh | 1 | PR-09 |
| VPS-US-27 | Sprint 1 demo video | Akarsh | 1 | PR-09 |
| VPS-US-28 | Edge controller API and WAN simulation | Shweta | 3 | PR-10 |
| VPS-US-29 | Attendant POS UI | Shweta | 3 | PR-10 |

### Sprint 3 (optional) — "Prove it" (14 points)

| Story | Title | Owner | SP | PR |
|---|---|---|---|---|
| VPS-US-31 | Resilience and reliability tests | Shweta | 3 | PR-11 |
| VPS-US-32 | End-to-end journey tests and Sprint 2 video | Akarsh | 3 | PR-12 |
| VPS-US-33 | Security validation suite | Angelo | 3 | PR-13 |
| VPS-US-34 | Performance tests and test reports | Himansh | 5 | PR-14 |

**Points per member:** Angelo 40 · Akarsh 36 · Himansh 33 · Shweta 32 (total 141).


## Definition of Done

1. Code merged to `main` through a PR raised by the story owner and approved by the repo owner.
2. CI green: ruff lint, unit + system tests on Python 3.11 and 3.12, branch coverage ≥ 90 %.
3. Every acceptance criterion has a test tagged `@pytest.mark.tc("TC-…")` that maps to the Test Case Specification.
4. Any deviation from the SRS / SAD / Test Plan is recorded in `docs/Deviations.md`.
5. The GitHub issue is closed by the PR (`Closes #n`) and its Project card is moved to *Done*.

## Workflow (GitHub)

```
main ──●──────────●──────────●── (protected: PR + 1 approval + CI green)
        \        /  \        /
         feature/VPS-US-11-entry   feature/VPS-US-14-tariff …
```

* Branch name: `feature/VPS-US-xx-short-name` (or `test/…`, `docs/…`).
* Commit messages: `VPS-US-xx: <what changed>`.
* PR automation (`.github/workflows/pr-automation.yml`) labels the PR by area, assigns the author,
  checks that the PR references a story, and adds it to the Project board.
* CI (`.github/workflows/ci.yml`) runs lint → tests with coverage → performance suite and uploads the
  JUnit, HTML test and coverage reports as build artefacts.

## Sprint review checklist

* Demo the increment against each story's acceptance criteria (use `demo/record_demo.py` to record).
* Update story status on the Project board; move unfinished stories to the next sprint and note them as spill-over.
* Record deviations discovered during the sprint in `docs/Deviations.md`.
* Retrospective: what went well / what to improve / one action item — written by the team after the review.
