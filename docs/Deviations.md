# Deviations from the submitted SRS, SAD and Test Plan

Part 2 of the mini-project requires every deviation from the Part 1 documents to be recorded and
explained at the final demo. Each entry says what the document specified, what was built, and why.

| ID | Document / section | Specified | Implemented | Reason / impact |
|---|---|---|---|---|
| DEV-01 | SAD 3.5, SRS 2.4 | PostgreSQL central DB + Redis cache | SQLite (WAL mode) for the central store; slot summary and VMS boards cached in-process, invalidated by a slot-state version counter | Runs on any laptop and in CI with zero setup. SQL is ANSI and ports to PostgreSQL; the cache layer is where Redis would plug in. |
| DEV-02 | SRS 3.2, Test Plan §10 | Physical ANPR cameras, boom barriers, ground loops, printers, slot sensors | Software simulators with the same interface (`vps/hardware.py`); UI buttons and API calls drive them | Hardware not available. The Test Plan already listed "mock hardware stubs" as the mitigation. |
| DEV-03 | SRS 3.4, SAD 3.5 | MQTT / WebSocket slot telemetry | Sensors post HTTP events (`POST /api/v1/sensors/{slot}/event`); displays poll `/api/v1/vms` every 1 s using a version number | Avoids running an MQTT broker. Latency targets (≤ 2 s LED, ≤ 1 s VMS) are still met and tested. |
| DEV-04 | SRS 3.3 | Razorpay / Stripe gateway; Twilio SMS / e-mail | Sandbox gateway implementing the same pattern (order → UPI QR → HMAC-signed webhook → verify). SMS/e-mail are queued in a `notifications` outbox table | No merchant account. Signature verification, idempotent re-delivery and amount checks are real and tested; swapping in Razorpay means changing one adapter class. |
| DEV-05 | SAD 4.3 `/egress/checkout` | Response `{status: "PAID", receipt_url, barrier_action: "OPEN"}` | Checkout returns `PENDING` + order and UPI QR; the webhook (or sandbox-pay) returns `PAID` with `receipt_url` and `barrier_action: "OPEN"`. Zero-fare exits return `PAID` immediately | A real gateway confirms payment asynchronously. This matches SAD sequence diagram 2 ("Webhook: PAID → Raise Barrier"); the synchronous response in 4.3 was a simplification. |
| DEV-06 | Test Plan §6 | JMeter, Selenium/Cypress, Postman/REST-Assured, Jira, MQTTX | pytest + httpx load harness (`tests/perf`), FastAPI TestClient API tests, GitHub Issues/Projects, Playwright for demo recording; UI checked manually | One toolchain that runs in GitHub Actions. Load results (p90/p95, throughput) are equivalent to a JMeter summary. |
| DEV-07 | SRS VPS-F-003 | Raise barrier on valid ticket **or RFID scan** | Ticket path only; RFID pass holders not implemented | No RFID reader or pass-holder data in scope for the build. The barrier/ticket path is fully covered. |
| DEV-08 | SRS RTM / Test Plan §13 | NF-004 used `TC-Sec-01`, SR-001 used `TC-SEC-01` | NF-004 renamed **TC-SEC-06**. New cases: TC-ENT-05/06, TC-SLOT-04, TC-PAY-05, TC-RES-03, TC-SYS-01…05 | The two IDs differ only by case. The new cases cover behaviour found during the sprints (anti-passback, unreadable plates, lot full, payment failure, reservation check-in, end-to-end journeys). |
| DEV-09 | SAD 4.5, SRS 3.1 | Sunlight-readable kiosk with multilingual audio-visual prompts | Responsive English web UI for kiosk, exit, display, attendant, booking and admin | Physical kiosk and audio out of scope; i18n left as future work. |
| DEV-10 | SRS VPS-NF-002 | 99.9 % monthly availability | `/health` endpoint + 600-operation soak test with zero 5xx errors (TC-Rel-01) | Monthly uptime can only be measured in production; the soak test is the lab proxy. Reported as *partially verified*. |
| DEV-11 | SRS VPS-F-002 | Ticket with "encrypted session ID" | Ticket ID (UUID4) signed with HMAC-SHA256; the QR contains no PII (only a 12-char keyed fingerprint prefix) | Integrity is what prevents counterfeits (VPS-SR-004); there is nothing confidential left in the QR to encrypt. |
| DEV-12 | SRS VPS-SR-003 | MFA for administrative accounts | MFA (TOTP) required for ADMIN **and** MANAGER roles; attendants use password only | Managers can read revenue and audit data, so they are treated as administrative. |
| DEV-13 | SAD 3.4 | Separate edge controllers syncing to a cloud backend | Edge queue is a separate SQLite file inside the same process; "central" events land in the main DB's `central_events` table | Single deployable for the mini-project. Queue semantics (ordering, idempotency, 72 h budget, ≤ 5 min sync) are implemented and tested. |
| DEV-14 | Test Plan §7 | Test schedule 20 Sep – 10 Oct | Testing ran inside the sprints (19 Oct – 6 Nov) per the Part 2/3 calendar | The course calendar moved implementation after the Test Plan was written. |
| DEV-15 | SRS RTM status column | All rows marked "P" (passed) before implementation | Real execution results are in `docs/reports/System_Validation_Report.md` | The Part 1 RTM was a template; the report replaces it with measured outcomes. |

## Additions beyond the documents

These do not contradict the documents. They were added during the sprints and are tested:

* **Anti-passback:** a plate with an active ticket cannot enter again (TC-ENT-05).
* **Attendant path for unreadable plates:** OCR confidence < 0.80 → HTTP 422 → audited manual entry (TC-ENT-06).
* **Sensor replay protection:** per-sensor sequence numbers (SRS security objective 3).
* **Account lockout** after 5 failed logins; session tokens stored only as SHA-256 hashes.
* **Hash-chained audit log** on top of the write-once database triggers, so out-of-band edits are detected.
* **Payment webhook amount check** and idempotent re-delivery; card numbers Luhn-checked and only the last 4 digits stored.
* **TLS 1.3-only server runner** (`python -m vps --tls`) and a 426 response for plain HTTP when TLS is required.
* **Back-dated entry timestamps** (≤ 72 h) accepted so edge controllers can replay offline transactions.
* **Configurable number of lanes** (`VPS_LANE_PAIRS`), used to size the NF-003 test at 50 lanes.
* **Performance tuning:** pure-ASGI middleware, `synchronous=NORMAL` WAL, versioned caches. These took NF-003 from ~80 req/s to > 500 req/s.
