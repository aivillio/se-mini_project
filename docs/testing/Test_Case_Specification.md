# Test Case Specification (v1.1)

| Field | Detail |
|---|---|
| Project | Vehicle Parking System (VPS) |
| Version | 1.1 — updated after Sprints 1–2 (Part 3) |
| Supersedes | Test cases in Software Test Plan v1.0 §13 (16-09-2026) |
| Owner | Himansh Ahuja (QA Lead) |
| Generated | 11 Nov 2026 |

This specification lists every test case, the SRS requirement it verifies, the steps and expected
result, what changed during the sprints, and the automated tests that implement it. The status column
is taken from the latest run. Total: **38 test cases** (28 functional,
10 non-functional / security).

## 1. Summary

| Test case | Title | Requirement(s) | Type | Priority | Status |
|---|---|---|---|---|---|
| TC-ENT-01 | ANPR plate capture | VPS-F-001 | Functional / Performance | High | PASS |
| TC-ENT-02 | QR ticket issue | VPS-F-002, VPS-SR-004 | Functional | High | PASS |
| TC-ENT-03 | Entry barrier raise | VPS-F-003 | Functional / Performance | High | PASS |
| TC-ENT-04 | Ground-loop safety halt | VPS-F-004 | Functional / Safety | High | PASS |
| TC-ENT-05 | Anti-passback | VPS-F-002 | Functional | Medium | PASS |
| TC-ENT-06 | Invalid / unreadable plate | VPS-F-001 | Negative | High | PASS |
| TC-SLOT-01 | Nearest vacant slot by category | VPS-F-005 | Functional | High | PASS |
| TC-SLOT-02 | Sensor → Occupied + red LED | VPS-F-006 | Functional / Performance | High | PASS |
| TC-SLOT-03 | VMS boards match database | VPS-F-007 | Functional | Medium | PASS |
| TC-SLOT-04 | Lot full / concurrent allocation | VPS-F-005 | Negative / Concurrency | High | PASS |
| TC-BILL-01 | Tiered fare computation | VPS-F-008 | Functional | High | PASS |
| TC-BILL-02 | 15-minute grace period | VPS-F-009 | Boundary | Medium | PASS |
| TC-BILL-03 | Surge and coupons | VPS-F-010 | Functional | Medium | PASS |
| TC-PAY-01 | Exit scan retrieves invoice | VPS-F-011 | Functional / Performance | High | PASS |
| TC-PAY-02 | Cashless payment | VPS-F-012 | Functional / Integration | High | PASS |
| TC-PAY-03 | Exit barrier on PAID only | VPS-F-013 | Functional / Security | High | PASS |
| TC-PAY-04 | GST tax receipt | VPS-F-014 | Functional | Medium | PASS |
| TC-PAY-05 | Payment failure & webhook security | VPS-F-012, VPS-F-013 | Negative / Security | High | PASS |
| TC-RES-01 | 48-hour advance reservation | VPS-F-015 | Functional / Boundary | High | PASS |
| TC-RES-02 | No-show auto-release | VPS-F-016 | Functional / Boundary | Medium | PASS |
| TC-RES-03 | Reservation check-in at entry | VPS-F-015 | Functional / Negative | Medium | PASS |
| TC-ADM-01 | Admin configuration without restart | VPS-F-017 | Functional | High | PASS |
| TC-ADM-02 | Report export <= 5 s | VPS-F-018 | Functional / Performance | Medium | PASS |
| TC-Perf-01 | Ingress latency p90 | VPS-NF-001 | Performance | High | PASS |
| TC-Rel-01 | Availability proxy (soak) | VPS-NF-002 | Reliability | High | PASS |
| TC-Scale-01 | Scale: 10k slots / 50 lanes | VPS-NF-003 | Performance / Load | High | PASS |
| TC-SEC-06 | PCI-DSS: no plaintext card data | VPS-NF-004 | Security | High | PASS |
| TC-Fault-01 | Edge offline resilience | VPS-NF-005 | Resilience | High | PASS |
| TC-SEC-01 | TLS 1.3 enforced | VPS-SR-001 | Security | High | PASS |
| TC-SEC-02 | Password hashing & PII encryption | VPS-SR-002 | Security | High | PASS |
| TC-SEC-03 | RBAC + MFA | VPS-SR-003 | Security | High | PASS |
| TC-SEC-04 | Counterfeit QR rejected | VPS-SR-004 | Security | High | PASS |
| TC-SEC-05 | Immutable audit log | VPS-SR-005 | Security | High | PASS |
| TC-SYS-01 | Walk-in car, UPI payment | VPS-F-001, VPS-F-005, VPS-F-008, VPS-F-012, VPS-F-013 | System (E2E) | High | PASS |
| TC-SYS-02 | Reserved EV, short visit | VPS-F-015, VPS-F-009 | System (E2E) | Medium | PASS |
| TC-SYS-03 | Peak-hour card payment with coupon | VPS-F-010, VPS-F-012 | System (E2E) | Medium | PASS |
| TC-SYS-04 | Unreadable plate, cash exit | VPS-F-001, VPS-F-012 | System (E2E) | Medium | PASS |
| TC-SYS-05 | Admin day | VPS-F-017, VPS-F-018 | System (E2E) | Medium | PASS |

## 2. Test case details

### TC-ENT-01 — ANPR plate capture

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-001 (Capture vehicle plate via ANPR within 1.5 s (>= 95 % OCR accuracy)) |
| Type / priority | Functional / Performance / High |
| Preconditions | Entry lane ENTRY-1 online; camera online |
| Steps | 1. Vehicle arrives with plate 'ka-01 ab 1234'. 2. Camera reads plate at confidence 0.97. 3. Observe the read. |
| Expected result | Plate normalised to KA01AB1234 and validated against Indian formats (incl. BH series); capture <= 1500 ms. |
| Sprint update | Added normalisation of spaces/hyphens and BH-series plates. |
| Automated by | `unit/test_hardware.py::TestCamera::test_capture_ok`<br>`unit/test_hardware.py::TestCamera::test_confidence_range`<br>`unit/test_hardware.py::TestCamera::test_low_confidence`<br>`unit/test_hardware.py::TestCamera::test_offline`<br>`unit/test_hardware.py::test_plate_normalisation`<br>`unit/test_ingress.py::test_plate_capture_normalised_and_fast` |
| Latest result | **PASS** (9/9 automated tests passed) |

### TC-ENT-02 — QR ticket issue

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-002 (Issue entry ticket with unique QR, signed session ID and timestamp within 2 s), VPS-SR-004 (HMAC-SHA256 signed QR tickets; tampered tickets rejected) |
| Type / priority | Functional / High |
| Preconditions | Valid plate read; vacant slot of the category |
| Steps | 1. POST /api/v1/ingress/ticket {plate_number, vehicle_category, timestamp}. 2. Verify QR signature. 3. Inspect DB row. |
| Expected result | 201 with ticket_id (unique UUID), qr_payload (HMAC-SHA256 signed: ticket id, slot, timestamp), allocated_slot; issued <= 2000 ms; plate stored AES-encrypted; ticket printed. |
| Sprint update | Response shape aligned with SAD 4.3; printer-fault fallback to digital ticket added. |
| Automated by | `unit/test_ingress.py::test_api_matches_sad_contract`<br>`unit/test_ingress.py::test_ticket_has_signed_qr_and_encrypted_plate`<br>`unit/test_ingress.py::test_ticket_ids_unique` |
| Latest result | **PASS** (3/3 automated tests passed) |

### TC-ENT-03 — Entry barrier raise

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-003 (Raise entry barrier within 500 ms on valid ticket) |
| Type / priority | Functional / Performance / High |
| Preconditions | Ticket issued |
| Steps | 1. Issue ticket. 2. Read barrier state and relay latency. |
| Expected result | Barrier UP; relay command <= 500 ms; total ingress <= 3000 ms. |
| Sprint update | RFID path deferred (DEV-07). |
| Automated by | `unit/test_hardware.py::TestBarrier::test_halt_on_loop`<br>`unit/test_hardware.py::TestBarrier::test_lane_auto_lower_after_vehicle_clears`<br>`unit/test_hardware.py::TestBarrier::test_raise_and_lower`<br>`unit/test_hardware.py::TestBarrier::test_relay_fault`<br>`unit/test_ingress.py::test_barrier_raised_within_500ms` |
| Latest result | **PASS** (5/5 automated tests passed) |

### TC-ENT-04 — Ground-loop safety halt

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-004 (Prevent barrier descent while vehicle on ground loop) |
| Type / priority | Functional / Safety / High |
| Preconditions | Barrier UP after a ticket |
| Steps | 1. Loop reports vehicle present. 2. Command barrier down. 3. Loop clears. |
| Expected result | Step 2: descent halted (reason VEHICLE_ON_LOOP), barrier stays UP. Step 3: barrier lowers automatically. |
| Sprint update | Auto-lower on loop clear added. |
| Automated by | `unit/test_hardware.py::TestBarrier::test_halt_on_loop`<br>`unit/test_hardware.py::TestBarrier::test_lane_auto_lower_after_vehicle_clears`<br>`unit/test_hardware.py::TestBarrier::test_raise_and_lower`<br>`unit/test_hardware.py::TestBarrier::test_relay_fault`<br>`unit/test_ingress.py::test_api_loop_safety` |
| Latest result | **PASS** (5/5 automated tests passed) |

### TC-ENT-05 — Anti-passback

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-002 (Issue entry ticket with unique QR, signed session ID and timestamp within 2 s) |
| Type / priority | Functional / Medium |
| Preconditions | Vehicle KA01AB1234 already inside |
| Steps | 1. Same plate arrives at ENTRY-2. |
| Expected result | 409 VEHICLE_ALREADY_INSIDE; no second ticket. |
| Sprint update | New case (Sprint 1). |
| Automated by | `unit/test_ingress.py::test_anti_passback` |
| Latest result | **PASS** (1/1 automated tests passed) |

### TC-ENT-06 — Invalid / unreadable plate

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-001 (Capture vehicle plate via ANPR within 1.5 s (>= 95 % OCR accuracy)) |
| Type / priority | Negative / High |
| Preconditions | Entry lane online |
| Steps | 1. Submit malformed plates ('', 'HELLO', 'KA01AB12345'). 2. Submit valid plate with confidence 0.5. 3. Attendant enters plate manually. |
| Expected result | 1: 400 INVALID_PLATE. 2: 422 PLATE_UNREADABLE (routed to attendant). 3: ticket with entry_mode MANUAL, audited. |
| Sprint update | New case (Sprint 1): attendant manual-entry path. |
| Automated by | `unit/test_ingress.py::test_invalid_plate`<br>`unit/test_ingress.py::test_low_confidence_routes_to_attendant` |
| Latest result | **PASS** (5/5 automated tests passed) |

### TC-SLOT-01 — Nearest vacant slot by category

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-005 (Designate nearest vacant slot by vehicle category) |
| Type / priority | Functional / High |
| Preconditions | Default layout seeded (100 bays, 3 levels) |
| Steps | 1. Allocate one slot for each of 2W, 4W, EV, HANDICAP. 2. Allocate twice more; release first; allocate again. 3. Exhaust level-1 EV bays. |
| Expected result | Slot category matches; chosen slot has the lowest (level, distance); released slot is reused first; allocation spills to level 2. |
| Sprint update | Unchanged. |
| Automated by | `unit/test_allocation.py::test_allocation_moves_to_next_nearest`<br>`unit/test_allocation.py::test_nearest_slot_matches_category`<br>`unit/test_allocation.py::test_spills_to_next_level` |
| Latest result | **PASS** (6/6 automated tests passed) |

### TC-SLOT-02 — Sensor → Occupied + red LED

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-006 (Slot status Occupied + LED red within 2 s of sensor trigger) |
| Type / priority | Functional / Performance / High |
| Preconditions | Slot L1-C001 vacant |
| Steps | 1. POST sensor event occupied=true. 2. POST occupied=false. 3. Replay an old sequence number. |
| Expected result | 1: status OCCUPIED, LED RED within 2000 ms. 2: VACANT, GREEN. 3: 409 SENSOR_REPLAY. |
| Sprint update | Replay protection added (security objective 3). |
| Automated by | `unit/test_sensors.py::test_clear_event_sets_green`<br>`unit/test_sensors.py::test_occupied_event_sets_red_led_within_2s` |
| Latest result | **PASS** (2/2 automated tests passed) |

### TC-SLOT-03 — VMS boards match database

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-007 (Refresh VMS vacancy counts within 1 s) |
| Type / priority | Functional / Medium |
| Preconditions | Default layout |
| Steps | 1. Occupy 3 bays via sensors. 2. Read /api/v1/vms. 3. Fill every bay. |
| Expected result | Entrance count equals DB vacant count; version increments per change; boards show 'FULL' when full. |
| Sprint update | Boards cached per slot-state version (performance). |
| Automated by | `unit/test_sensors.py::test_vms_counts_match_database`<br>`unit/test_sensors.py::test_vms_full_text` |
| Latest result | **PASS** (2/2 automated tests passed) |

### TC-SLOT-04 — Lot full / concurrent allocation

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-005 (Designate nearest vacant slot by vehicle category) |
| Type / priority | Negative / Concurrency / High |
| Preconditions | Default layout |
| Steps | 1. Fill all 4 HANDICAP bays, request a 5th. 2. 90 threads allocate 4W concurrently. |
| Expected result | 1: 409 LOT_FULL. 2: exactly 68 distinct slots allocated, 22 LOT_FULL, no double booking. |
| Sprint update | New case (Sprint 1). |
| Automated by | `system/test_end_to_end.py::test_full_category_rejected_cleanly`<br>`unit/test_allocation.py::test_concurrent_allocation_never_double_books`<br>`unit/test_allocation.py::test_lot_full`<br>`unit/test_ingress.py::test_lot_full` |
| Latest result | **PASS** (4/4 automated tests passed) |

### TC-BILL-01 — Tiered fare computation

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-008 (Fee by duration, category and tiered rate tables) |
| Type / priority | Functional / High |
| Preconditions | Default tariffs (4W: Rs 40 first hour, Rs 30/h, cap Rs 400) |
| Steps | Compute fares for 60, 61, 180 min, 24 h, 26 h (4W) and 2W/EV/HANDICAP samples. |
| Expected result | Base = first_hour + (h-1) x per_hour, capped per 24 h block; CGST = SGST = 9 %; total = base x 1.18. |
| Sprint update | Multi-day blocks and GST split clarified. |
| Automated by | `unit/test_tariff.py::test_exit_before_entry`<br>`unit/test_tariff.py::test_tiered_rates_and_daily_cap` |
| Latest result | **PASS** (10/10 automated tests passed) |

### TC-BILL-02 — 15-minute grace period

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-009 (15-minute grace period at zero charge) |
| Type / priority | Boundary / Medium |
| Preconditions | Ticket issued |
| Steps | Exit at 0, 1, 15 and 16 minutes. |
| Expected result | 0-15 min: Rs 0, no payment needed, barrier opens; 16 min: one hour charged. |
| Sprint update | Zero-fare exit bypasses the gateway (Sprint 1). |
| Automated by | `unit/test_egress.py::test_grace_period_exit_needs_no_payment`<br>`unit/test_tariff.py::test_grace_period_boundary` |
| Latest result | **PASS** (5/5 automated tests passed) |

### TC-BILL-03 — Surge and coupons

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-010 (Peak-hour surge rates and promo coupons) |
| Type / priority | Functional / Medium |
| Preconditions | Surge rule 17:00-20:00 IST x1.25; coupons WELCOME10 (10 %), FLAT50 (Rs 50) |
| Steps | 1. Exit at 18:00 IST. 2. Apply WELCOME10. 3. Apply FLAT50 to a Rs 20 fare. 4. Expired / exhausted / unknown coupon. |
| Expected result | 1: surge = 25 % of base. 2: 10 % off (base + surge). 3: never below zero. 4: 400 INVALID_COUPON. |
| Sprint update | Coupon usage limits and expiry added. |
| Automated by | `unit/test_tariff.py::TestSurgeAndCoupons::test_coupon_creation_rules`<br>`unit/test_tariff.py::TestSurgeAndCoupons::test_flat_coupon_never_negative`<br>`unit/test_tariff.py::TestSurgeAndCoupons::test_invalid_expired_exhausted`<br>`unit/test_tariff.py::TestSurgeAndCoupons::test_no_surge_outside_window`<br>`unit/test_tariff.py::TestSurgeAndCoupons::test_percent_coupon`<br>`unit/test_tariff.py::TestSurgeAndCoupons::test_surge_in_peak_window`<br>`unit/test_tariff.py::TestSurgeAndCoupons::test_surge_rule_management` |
| Latest result | **PASS** (7/7 automated tests passed) |

### TC-PAY-01 — Exit scan retrieves invoice

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-011 (Exit QR / plate scan retrieves invoice within 1 s) |
| Type / priority | Functional / Performance / High |
| Preconditions | Vehicle parked 2 h 10 min |
| Steps | 1. Scan QR at EXIT-1. 2. Look up by plate. 3. Unknown plate. |
| Expected result | Invoice (3 billable hours, Rs 118.00) in <= 1000 ms; plate lookup finds the same ticket; unknown → 404. |
| Sprint update | Unchanged. |
| Automated by | `unit/test_egress.py::test_lookup_by_qr_and_plate` |
| Latest result | **PASS** (1/1 automated tests passed) |

### TC-PAY-02 — Cashless payment

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-012 (Cashless payment (UPI QR, cards, wallets); webhook PAID within 3 s) |
| Type / priority | Functional / Integration / High |
| Preconditions | Invoice retrieved |
| Steps | 1. Checkout with UPI → order + dynamic UPI QR. 2. Gateway sends signed webhook payment.captured. |
| Expected result | Order CREATED with upi:// URI; webhook verified → ticket PAID within 3 s. |
| Sprint update | Async PENDING → PAID flow (DEV-05). |
| Automated by | `unit/test_egress.py::test_upi_payment_opens_barrier_and_releases_slot`<br>`unit/test_payment.py::test_upi_order_has_dynamic_qr` |
| Latest result | **PASS** (2/2 automated tests passed) |

### TC-PAY-03 — Exit barrier on PAID only

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-013 (Raise exit barrier only on verified payment) |
| Type / priority | Functional / Security / High |
| Preconditions | Vehicle parked, unpaid |
| Steps | 1. Try to open exit barrier. 2. Pay. 3. Observe barrier and slot. |
| Expected result | 1: 403 UNPAID_TICKET, barrier DOWN. 3: barrier UP, slot VACANT, EXIT event queued to central. |
| Sprint update | Unchanged. |
| Automated by | `unit/test_egress.py::test_barrier_never_opens_unpaid`<br>`unit/test_egress.py::test_upi_payment_opens_barrier_and_releases_slot` |
| Latest result | **PASS** (2/2 automated tests passed) |

### TC-PAY-04 — GST tax receipt

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-014 (Itemised GST receipt via printer, e-mail or SMS) |
| Type / priority | Functional / Medium |
| Preconditions | Ticket PAID |
| Steps | 1. GET receipt JSON. 2. GET PDF. 3. Send by SMS / e-mail; invalid recipients. |
| Expected result | Invoice no. VPS/<FY>/<seq>, GSTIN, SAC 996743, CGST 9 % + SGST 9 %; valid PDF; SMS queued with masked recipient stored encrypted; invalid channel/recipient → 400. |
| Sprint update | Moved to Sprint 2. |
| Automated by | `unit/test_receipt.py::TestReceipts::test_grace_receipt_and_unpaid`<br>`unit/test_receipt.py::TestReceipts::test_gst_invoice`<br>`unit/test_receipt.py::TestReceipts::test_pdf_and_sms`<br>`unit/test_receipt.py::test_receipt_api` |
| Latest result | **PASS** (4/4 automated tests passed) |

### TC-PAY-05 — Payment failure & webhook security

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-012 (Cashless payment (UPI QR, cards, wallets); webhook PAID within 3 s), VPS-F-013 (Raise exit barrier only on verified payment) |
| Type / priority | Negative / Security / High |
| Preconditions | Order created |
| Steps | 1. Gateway reports payment.failed. 2. Retry. 3. Re-deliver the same webhook. 4. Tamper amount / bad signature. |
| Expected result | 1: FAILED, barrier stays DOWN, attendant alert. 2: PAID. 3: idempotent. 4: 403. |
| Sprint update | New case (Sprint 1). |
| Automated by | `unit/test_egress.py::test_failed_payment_keeps_barrier_closed`<br>`unit/test_egress.py::test_webhook_idempotent_and_amount_checked`<br>`unit/test_payment.py::test_webhook_signature` |
| Latest result | **PASS** (3/3 automated tests passed) |

### TC-RES-01 — 48-hour advance reservation

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-015 (Reserve a slot up to 48 h in advance) |
| Type / priority | Functional / Boundary / High |
| Preconditions | Vacant bay of the category |
| Steps | 1. Book 2 h ahead. 2. Book 47.9 h / 48.1 h / in the past. 3. Second booking for the same plate. |
| Expected result | 1: BOOKED, slot RESERVED (blue LED), 8-char code. 2: 47.9 h OK, others 400 INVALID_WINDOW. 3: 409. |
| Sprint update | One active booking per vehicle added. |
| Automated by | `unit/test_reservation.py::TestBooking::test_48_hour_window`<br>`unit/test_reservation.py::TestBooking::test_input_validation`<br>`unit/test_reservation.py::TestBooking::test_lookup_list_cancel`<br>`unit/test_reservation.py::TestBooking::test_one_active_booking_per_vehicle`<br>`unit/test_reservation.py::TestBooking::test_reserve_locks_slot_and_issues_code` |
| Latest result | **PASS** (5/5 automated tests passed) |

### TC-RES-02 — No-show auto-release

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-016 (Release reserved slot 30 min after start on no-show) |
| Type / priority | Functional / Boundary / Medium |
| Preconditions | Booking for T+1 h |
| Steps | 1. Run release at start+29 min. 2. Run at start+31 min. |
| Expected result | 1: nothing released. 2: reservation EXPIRED, slot VACANT, audit entry NO_SHOW_RELEASED. |
| Sprint update | Background scheduler every 60 s. |
| Automated by | `unit/test_reservation.py::TestNoShow::test_release_after_30_minutes`<br>`unit/test_reservation.py::TestNoShow::test_scheduler_tick_and_thread` |
| Latest result | **PASS** (2/2 automated tests passed) |

### TC-RES-03 — Reservation check-in at entry

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-015 (Reserve a slot up to 48 h in advance) |
| Type / priority | Functional / Negative / Medium |
| Preconditions | Booking exists |
| Steps | 1. Enter with code and matching plate. 2. Wrong plate / wrong category. 3. > 60 min early. 4. > 30 min late. |
| Expected result | 1: reserved slot assigned, CHECKED_IN. 2: 403 / 400. 3: 409 RESERVATION_TOO_EARLY. 4: 409 RESERVATION_EXPIRED. |
| Sprint update | New case (Sprint 2). |
| Automated by | `unit/test_reservation.py::TestCheckIn::test_entry_with_code_uses_reserved_slot`<br>`unit/test_reservation.py::TestCheckIn::test_late_arrival_expires`<br>`unit/test_reservation.py::TestCheckIn::test_plate_and_category_must_match`<br>`unit/test_reservation.py::TestCheckIn::test_too_early` |
| Latest result | **PASS** (4/4 automated tests passed) |

### TC-ADM-01 — Admin configuration without restart

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-017 (Admin console: tariffs, zones, attendant credentials; no restart) |
| Type / priority | Functional / High |
| Preconditions | Admin signed in with TOTP |
| Steps | 1. Change 4W tariff. 2. Look up an active ticket. 3. Add surge rule, coupon, slots; disable a bay; create attendant. |
| Expected result | New tariff applies immediately; all changes audited; manager is read-only (403 on writes). |
| Sprint update | Layout and credential management added. |
| Automated by | `unit/test_admin_api.py::TestLayoutAdmin::test_add_slots_and_status`<br>`unit/test_admin_api.py::TestTariffAdmin::test_invalid_tariff`<br>`unit/test_admin_api.py::TestTariffAdmin::test_manager_read_only`<br>`unit/test_admin_api.py::TestTariffAdmin::test_surge_and_coupons`<br>`unit/test_admin_api.py::TestTariffAdmin::test_update_tariff_live`<br>`unit/test_tariff.py::test_tariff_update_takes_effect_without_restart` |
| Latest result | **PASS** (6/6 automated tests passed) |

### TC-ADM-02 — Report export <= 5 s

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-018 (Revenue / turnaround / occupancy reports in CSV/PDF within 5 s) |
| Type / priority | Functional / Performance / Medium |
| Preconditions | Paid sessions exist (incl. 5,000-row month) |
| Steps | Export revenue, occupancy, turnaround as CSV, PDF, JSON (daily/monthly). |
| Expected result | Correct aggregates; every export <= 5000 ms; attendant gets 403. |
| Sprint update | 5,000-row volume test added. |
| Automated by | `perf/test_performance.py::test_export_large_month_under_5s`<br>`unit/test_reports.py::TestReports::test_bad_dates`<br>`unit/test_reports.py::TestReports::test_empty_exports`<br>`unit/test_reports.py::TestReports::test_export_under_5_seconds`<br>`unit/test_reports.py::TestReports::test_occupancy`<br>`unit/test_reports.py::TestReports::test_out_of_range_rows_excluded`<br>`unit/test_reports.py::TestReports::test_revenue_daily`<br>`unit/test_reports.py::TestReports::test_revenue_monthly_and_range`<br>… +2 more |
| Latest result | **PASS** (20/20 automated tests passed) |

### TC-Perf-01 — Ingress latency p90

| Field | Detail |
|---|---|
| Requirement(s) | VPS-NF-001 (Ingress transaction p90 <= 3 s) |
| Type / priority | Performance / High |
| Preconditions | Server process with 10,000 bays |
| Steps | 200 sequential HTTP ingress transactions; measure round trip. |
| Expected result | p90 <= 3000 ms. |
| Sprint update | JMeter replaced by pytest/httpx harness (DEV-06). |
| Automated by | `perf/test_performance.py::test_ingress_p90_under_3s` |
| Latest result | **PASS** (1/1 automated tests passed) |

### TC-Rel-01 — Availability proxy (soak)

| Field | Detail |
|---|---|
| Requirement(s) | VPS-NF-002 (99.9 % monthly availability) |
| Type / priority | Reliability / High |
| Preconditions | Fresh system |
| Steps | 600+ mixed entry/exit/display requests; check health. |
| Expected result | Zero 5xx responses; >= 100 completed exits; /health ok. |
| Sprint update | Lab proxy for monthly uptime (DEV-10). |
| Automated by | `system/test_resilience.py::test_soak_no_server_errors` |
| Latest result | **PASS** (1/1 automated tests passed) |

### TC-Scale-01 — Scale: 10k slots / 50 lanes

| Field | Detail |
|---|---|
| Requirement(s) | VPS-NF-003 (10,000 slots, 50 lanes, < 200 ms API latency at 500 req/s) |
| Type / priority | Performance / Load / High |
| Preconditions | Separate server process, 10,000 bays, 25 lane pairs |
| Steps | 1,000 mixed requests (ingress, sensor, VMS, nearest-slot) from 25 concurrent clients after warm-up. |
| Expected result | Zero 5xx; p95 < 200 ms; throughput reported (target 500 req/s). |
| Sprint update | Server run out-of-process. |
| Automated by | `perf/test_performance.py::test_api_latency_under_load_10k_slots_50_lanes` |
| Latest result | **PASS** (1/1 automated tests passed) |

### TC-SEC-06 — PCI-DSS: no plaintext card data

| Field | Detail |
|---|---|
| Requirement(s) | VPS-NF-004 (PCI-DSS: no plaintext card data or credentials) |
| Type / priority | Security / High |
| Preconditions | Card payment completed |
| Steps | Dump the database after card payment, SMS receipt, reservation with contact. |
| Expected result | No PAN, plate, phone, password or TOTP secret in plaintext; only card last-4 stored. |
| Sprint update | Renamed from TC-Sec-01 (DEV-08). |
| Automated by | `system/test_security_validation.py::test_database_dump_has_no_plaintext_pii_or_pan`<br>`unit/test_payment.py::test_card_pan_never_stored` |
| Latest result | **PASS** (2/2 automated tests passed) |

### TC-Fault-01 — Edge offline resilience

| Field | Detail |
|---|---|
| Requirement(s) | VPS-NF-005 (72 h autonomous edge queuing; auto-sync <= 5 min) |
| Type / priority | Resilience / High |
| Preconditions | WAN link online |
| Steps | 1. Cut WAN. 2. Run 30 entries + 20 exits over ~72 h. 3. Restore WAN. 4. Lane controller offline. 5. Gateway outage. |
| Expected result | 2: lanes keep working, 50 events queued, within 72 h budget. 3: all synced in order <= 5 min, no duplicates. 4: 503 EDGE_CONTROLLER_OFFLINE on that lane only. 5: 402 → cash fallback works. |
| Sprint update | Gateway outage scenario added. |
| Automated by | `system/test_resilience.py::test_lane_controller_offline_returns_503_and_other_lanes_continue`<br>`system/test_resilience.py::test_lanes_keep_working_through_72h_wan_outage`<br>`system/test_resilience.py::test_payment_gateway_outage_falls_back_to_cash`<br>`unit/test_edge.py::TestEdgeQueue::test_offline_budget_72h`<br>`unit/test_edge.py::TestEdgeQueue::test_offline_queues_then_syncs_in_order`<br>`unit/test_edge.py::TestEdgeQueue::test_online_forwards_immediately`<br>`unit/test_edge.py::TestEdgeQueue::test_replay_is_idempotent`<br>`unit/test_edge_api.py::test_edge_api` |
| Latest result | **PASS** (8/8 automated tests passed) |

### TC-SEC-01 — TLS 1.3 enforced

| Field | Detail |
|---|---|
| Requirement(s) | VPS-SR-001 (TLS 1.3+ mandatory on all connections) |
| Type / priority | Security / High |
| Preconditions | Server started with --tls |
| Steps | 1. HTTPS with TLS 1.3. 2. Client limited to TLS 1.2. 3. Plain HTTP. |
| Expected result | 1: 200, negotiated TLSv1.3, HSTS header. 2: handshake refused. 3: not served (426 behind proxy). |
| Sprint update | Real handshake test against a live server. |
| Automated by | `system/test_security_validation.py::TestTLS::test_older_tls_rejected`<br>`system/test_security_validation.py::TestTLS::test_plain_http_rejected`<br>`system/test_security_validation.py::TestTLS::test_tls13_handshake_succeeds`<br>`unit/test_app.py::test_plain_http_refused_when_tls_required`<br>`unit/test_app.py::test_security_headers`<br>`unit/test_tls.py::test_config_pins_tls13`<br>`unit/test_tls.py::test_self_signed_cert_created_once` |
| Latest result | **PASS** (7/7 automated tests passed) |

### TC-SEC-02 — Password hashing & PII encryption

| Field | Detail |
|---|---|
| Requirement(s) | VPS-SR-002 (Argon2id/bcrypt passwords; AES-256 PII at rest) |
| Type / priority | Security / High |
| Preconditions | Users seeded |
| Steps | Inspect stored password hashes, TOTP secrets, plates, contacts. |
| Expected result | Passwords $argon2id$; PII AES-256-GCM (random nonce); wrong key fails to decrypt. |
| Sprint update | Unchanged. |
| Automated by | `system/test_security_validation.py::test_database_dump_has_no_plaintext_pii_or_pan`<br>`unit/test_auth.py::test_secrets_not_stored_in_plaintext`<br>`unit/test_security.py::TestPIIVault::test_encrypt_decrypt`<br>`unit/test_security.py::TestPIIVault::test_fingerprint_deterministic_and_keyed`<br>`unit/test_security.py::TestPIIVault::test_key_must_be_256_bit`<br>`unit/test_security.py::TestPIIVault::test_nonce_is_random`<br>`unit/test_security.py::TestPIIVault::test_unknown_format`<br>`unit/test_security.py::TestPIIVault::test_wrong_key_cannot_decrypt`<br>… +3 more |
| Latest result | **PASS** (11/11 automated tests passed) |

### TC-SEC-03 — RBAC + MFA

| Field | Detail |
|---|---|
| Requirement(s) | VPS-SR-003 (RBAC + MFA for administrative accounts) |
| Type / priority | Security / High |
| Preconditions | admin/manager/attendant accounts |
| Steps | 1. Admin login without / with wrong / with valid TOTP. 2. RBAC matrix over protected endpoints. 3. 5 bad passwords. |
| Expected result | 1: MFA_REQUIRED / 401 / 200. 2: 401 anonymous, 403 wrong role. 3: ACCOUNT_LOCKED. |
| Sprint update | Lockout and session expiry added. |
| Automated by | `system/test_security_validation.py::test_mfa_enforced_over_api`<br>`system/test_security_validation.py::test_rbac_matrix`<br>`unit/test_app.py::test_rbac_guards`<br>`unit/test_auth.py::test_admin_login_with_totp`<br>`unit/test_auth.py::test_admin_requires_totp`<br>`unit/test_auth.py::test_attendant_password_only`<br>`unit/test_auth.py::test_authorize`<br>`unit/test_auth.py::test_create_user_rules`<br>… +14 more |
| Latest result | **PASS** (29/29 automated tests passed) |

### TC-SEC-04 — Counterfeit QR rejected

| Field | Detail |
|---|---|
| Requirement(s) | VPS-SR-004 (HMAC-SHA256 signed QR tickets; tampered tickets rejected) |
| Type / priority | Security / High |
| Preconditions | Ticket issued |
| Steps | 1. Modify one character of the QR body. 2. Re-sign a different slot with a guessed key. |
| Expected result | 403 TAMPERED_TICKET; CRITICAL alert to attendant; audit entry COUNTERFEIT_TICKET. |
| Sprint update | Unchanged. |
| Automated by | `system/test_security_validation.py::test_counterfeit_qr_rejected_with_alert`<br>`unit/test_egress.py::test_counterfeit_ticket_rejected_and_alerted`<br>`unit/test_security.py::TestTicketSigner::test_malformed_payload`<br>`unit/test_security.py::TestTicketSigner::test_other_key_rejected`<br>`unit/test_security.py::TestTicketSigner::test_roundtrip`<br>`unit/test_security.py::TestTicketSigner::test_signature_is_hmac_sha256_hex`<br>`unit/test_security.py::TestTicketSigner::test_tampered_body_rejected`<br>`unit/test_security.py::TestTicketSigner::test_tampered_signature_rejected` |
| Latest result | **PASS** (10/10 automated tests passed) |

### TC-SEC-05 — Immutable audit log

| Field | Detail |
|---|---|
| Requirement(s) | VPS-SR-005 (Immutable write-once audit log retained 3 years) |
| Type / priority | Security / High |
| Preconditions | Audited actions performed |
| Steps | 1. Verify chain. 2. UPDATE / DELETE an entry via SQL. 3. Drop the trigger and edit a row. |
| Expected result | 1: valid. 2: refused (write-once). 3: chain verification reports the broken entry. Retention >= 3 years. |
| Sprint update | Hash chain added on top of triggers. |
| Automated by | `system/test_security_validation.py::test_audit_log_tamper_evident`<br>`unit/test_admin_api.py::TestOverrideAndAudit::test_audit_verify_endpoint`<br>`unit/test_admin_api.py::TestOverrideAndAudit::test_override_is_audited`<br>`unit/test_admin_api.py::TestOverrideAndAudit::test_override_validation`<br>`unit/test_audit.py::TestAuditLog::test_entries_filter`<br>`unit/test_audit.py::TestAuditLog::test_hash_chain`<br>`unit/test_audit.py::TestAuditLog::test_out_of_band_tampering_detected`<br>`unit/test_audit.py::TestAuditLog::test_retention_three_years`<br>… +1 more |
| Latest result | **PASS** (9/9 automated tests passed) |

### TC-SYS-01 — Walk-in car, UPI payment

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-001 (Capture vehicle plate via ANPR within 1.5 s (>= 95 % OCR accuracy)), VPS-F-005 (Designate nearest vacant slot by vehicle category), VPS-F-008 (Fee by duration, category and tiered rate tables), VPS-F-012 (Cashless payment (UPI QR, cards, wallets); webhook PAID within 3 s), VPS-F-013 (Raise exit barrier only on verified payment) |
| Type / priority | System (E2E) / High |
| Preconditions | Empty car park |
| Steps | Enter → loop → park (sensor) → 2 h 10 min → scan → UPI → webhook → receipt. |
| Expected result | VMS decrements then restores; Rs 118.00 charged; barrier opens; receipt total matches. |
| Sprint update | New. |
| Automated by | `system/test_end_to_end.py::test_walk_in_car_pays_by_upi` |
| Latest result | **PASS** (1/1 automated tests passed) |

### TC-SYS-02 — Reserved EV, short visit

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-015 (Reserve a slot up to 48 h in advance), VPS-F-009 (15-minute grace period at zero charge) |
| Type / priority | System (E2E) / Medium |
| Preconditions | EV bay free |
| Steps | Book 20 min ahead → arrive at +25 min with code → leave after 14 min. |
| Expected result | Reserved bay used; exit free (grace). |
| Sprint update | New. |
| Automated by | `system/test_end_to_end.py::test_reserved_ev_short_visit_in_grace` |
| Latest result | **PASS** (1/1 automated tests passed) |

### TC-SYS-03 — Peak-hour card payment with coupon

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-010 (Peak-hour surge rates and promo coupons), VPS-F-012 (Cashless payment (UPI QR, cards, wallets); webhook PAID within 3 s) |
| Type / priority | System (E2E) / Medium |
| Preconditions | Surge rule active |
| Steps | Enter 16:00 IST → exit 18:30 IST → card + FLAT50. |
| Expected result | Base 100 + surge 25 − 50 = 75 taxable; total Rs 88.50. |
| Sprint update | New. |
| Automated by | `system/test_end_to_end.py::test_peak_hour_card_payment_with_coupon` |
| Latest result | **PASS** (1/1 automated tests passed) |

### TC-SYS-04 — Unreadable plate, cash exit

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-001 (Capture vehicle plate via ANPR within 1.5 s (>= 95 % OCR accuracy)), VPS-F-012 (Cashless payment (UPI QR, cards, wallets); webhook PAID within 3 s) |
| Type / priority | System (E2E) / Medium |
| Preconditions | Attendant signed in |
| Steps | Low-confidence read → attendant manual ticket → 50 min → cash. |
| Expected result | 422 then manual ticket; Rs 47.20 collected; audited. |
| Sprint update | New. |
| Automated by | `system/test_end_to_end.py::test_unreadable_plate_manual_entry_and_cash` |
| Latest result | **PASS** (1/1 automated tests passed) |

### TC-SYS-05 — Admin day

| Field | Detail |
|---|---|
| Requirement(s) | VPS-F-017 (Admin console: tariffs, zones, attendant credentials; no restart), VPS-F-018 (Revenue / turnaround / occupancy reports in CSV/PDF within 5 s) |
| Type / priority | System (E2E) / Medium |
| Preconditions | Admin signed in |
| Steps | Change 2W tariff mid-stay → exit → revenue report + CSV → audit verify. |
| Expected result | New tariff billed; report total Rs 29.50; audit chain valid. |
| Sprint update | New. |
| Automated by | `system/test_end_to_end.py::test_admin_day` |
| Latest result | **PASS** (1/1 automated tests passed) |
