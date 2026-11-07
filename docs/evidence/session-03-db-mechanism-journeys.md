# Evidence Report — Session 03: Database Schema, Minimum Shippable Mechanism (`F-07`..`F-15`), Frontend Monorepo & Critical Journeys (`J-01`..`J-14`)

- **Date**: 2026-10-30
- **Task ID**: `SESSION-03-DB-MECHANISM-JOURNEYS`
- **Risk Class**: `HIGH` (TDD Red-Green-Refactor executed per `DUR-01`)
- **SSOT Sections Covered**: Sections 10.1, 10.4, 14.4, 22, 30, 35.1

## 1. Test Execution Summary

Command:
```powershell
uv run pytest -v
```
Result: **50 passed in 2.06s**

### New Test Suites Verified in Session 03

1. `backend/tests/mechanism/test_minimum_shippable_and_journeys.py`
   - `test_canonical_database_schema_20_tables_and_constraints`: Verifies all 20 canonical PostgreSQL tables (`Section 10.4` & `30.1`), `chk_inv01_cumulative_refund` (`INV-01`), `trg_passport_events_append_only` (`INV-09`), and `idx_returns_one_active_per_order_item` (`CT-01`).
   - `test_f07_evidence_pack_generation_and_hash`: Verifies `F-07` Evidence Pack generation (`FR-32`, `FR-33`, `FR-34`, `FR-35`), canonical SHA-256 hash, and buyer downloadability.
   - `test_f08_disposition_and_f09_certified_open_box_resale`: Verifies `F-08` 5-path disposition engine (`FR-38`) and `F-09` Certified Open-Box resale listing with prior-owner PII stripped (`FR-40`–`FR-43`).
   - `test_f12_serial_registry_keyed_hmac_and_swap_detection`: Verifies `F-12` per-merchant keyed `HMAC-SHA256` serial commitment (`FR-53`, `INV-13`), swap detection (`SERIAL_MISMATCH`), and repeat-refund block (`SERIAL_ALREADY_REFUNDED`).
   - `test_f13_f14_f15_rental_cap_sla_credit_and_appeals`: Verifies `F-13` 3-day rental cap (`FR-55`), `F-14` SLA breach credit calculation (`FR-56`), and `F-15` Appeal Portal enforcing `appeal_reviewer_id != original_reviewer_id` (`FR-69`, `FR-70`).
   - `test_all_14_critical_journeys_j01_to_j14`: Executes and verifies all 14 critical end-to-end journeys (`J-01` through `J-14`, `Section 35.1`).
