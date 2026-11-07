# Evidence Document — Session 10 (Remediation Fase R3: Database Persistence, State Machine Guard & Concurrency)

- **Date**: 2026-11-02
- **SSOT Version**: 1.2.1
- **Focus**: Audit Remediation Fase R3 — State Machine Integration, SQL Persistence, Alembic Migrations, and Concurrency Hardening
- **Audit Findings Remediated**: `AUD-05`, `AUD-06`, `AUD-07`, `AUD-11`, `AUD-12`, `AUD-42`
- **Requirements Progressed**: `INV-01` (VERIFIED), `INV-04` (VERIFIED), `FR-72` (VERIFIED), `FR-80` (VERIFIED), `NFR-04` (VERIFIED)

---

## 1. Executive Summary

Fase R3 resolves the reliability, concurrency, and persistence findings discovered in the independent technical audit (`AUD-05`, `AUD-06`, `AUD-07`, `AUD-11`, `AUD-12`, `AUD-42`):

1. **State Machine Enforcement in REST API (`AUD-05`, `INV-04`, `FR-72`)**:
   - Replaced direct `ret["state"]` assignments in `backend/api/app.py` with `ReturnStateMachine.apply(entity, event, **guards)` calls.
   - Illegal state jumps (e.g. attempting to submit declarations or keep offers on already settled returns) are strictly caught and returned as RFC 9457 HTTP `409 INVALID_STATE_TRANSITION`.
2. **Canonical 20-Table Database Models & Repository Layer (`AUD-06`, `Section 10.4`, `Section 30`)**:
   - Created typed SQLModel models in `backend/db/models.py` for all 20 canonical tables matching SSOT §10.4 and §30 integrity constraints (`DB-01`..`DB-10`).
   - Implemented `DatabaseRepository` in `backend/db/repository.py` providing transactional persistence, demo data seeding, and database reset routines.
   - Replaced naive `len(store) + 1` ID generation with collision-resistant UUIDs (`app_<hex>`, `resale_<hex>`), eliminating key collision risks under concurrent requests.
3. **Alembic Migration System (`AUD-42`, `MG-01`..`MG-04`)**:
   - Configured `alembic.ini` and `backend/migrations/env.py`.
   - Populated `backend/db/migrations/001_initial_schema.sql` with the full canonical PostgreSQL DDL.
   - Created `backend/migrations/versions/0001_initial_schema.py` defining all 20 canonical tables and indexes with full `upgrade()` and `downgrade()`.
   - Verified the `MG-04` idempotent cycle: `upgrade head` -> `downgrade base` -> `upgrade head` executed with zero errors against `data/proofreturn.db`.
4. **Concurrency & Atomicity Hardening (`AUD-11`, `AUD-12`, `INV-01`, `NFR-04`)**:
   - Added `threading.RLock()` across all mutating methods in `RefundLedger` (`backend/payments/ledger.py`).
   - Verified that concurrent multi-threaded refund planning strictly serializes and enforces `cumulative_refund_minor <= capture_amount_minor`, completely eliminating the race condition reported in `AUD-11`.
   - Hardened `WebhookProcessor` (`backend/payments/webhooks.py`) to atomically execute state changes before recording `event_id` as seen (`AUD-12`). Unregistered orders fail safely with 404 without poisoning the deduplication cache, allowing successful retries when the order is registered.
5. **ASGI Server & Docker Service Integration (`AUD-07`, `ARC-07`, `NFR-07`)**:
   - Added `uvicorn>=0.30.0` and `sqlmodel>=0.0.22` / `sqlalchemy>=2.0.0` to `pyproject.toml`.
   - Created `infra/Dockerfile` and added the `api` service to `infra/docker-compose.yml`.
   - Added `run` and `migrate` targets to `Makefile`.

---

## 2. Key Code Implementations

- **`backend/db/models.py`**:
  - Declares all 20 canonical SQLModel tables: `merchants`, `staff_users`, `shopper_accounts`, `identity_link_events`, `policies`, `passports`, `passport_events`, `serial_registry`, `orders`, `order_items`, `returns`, `return_evidence`, `assessments`, `decisions`, `keep_offers`, `refund_actions`, `custody_events`, `webhook_events`, `reviews`, `appeals`, and `agent_tokens`.
- **`backend/db/repository.py`**:
  - `DatabaseRepository(database_url)`: Engine initialization, table creation, seed management (`seed_demo_data`), and state machine integration.
- **`backend/migrations/versions/0001_initial_schema.py`**:
  - Alembic migration creating and dropping all 20 canonical tables and indexes per `MG-01`..`MG-04`.
- **`backend/payments/ledger.py`**:
  - Integrated `threading.RLock()` to ensure thread-safe serialized balance checks and atomic action inserts.
- **`backend/payments/webhooks.py`**:
  - Thread-safe `process_webhook` preventing event deduplication poisoning on transient failures.
- **`backend/api/app.py`**:
  - Wired `ReturnStateMachine.apply` to `POST /v1/returns/{id}/declaration`, `POST /v1/returns/{id}/evidence`, `POST /v1/returns/{id}/dropoff`, and `POST /v1/returns/{id}/keep-offer/respond`.
  - Replaced collision-prone integer counter IDs with `uuid.uuid4().hex[:8]`.

---

## 3. Automated Test Verification

All 77 active tests passed with zero failures (2 live/sandbox deselected by pyproject.toml):

```
backend/tests/ai/test_ai_pipeline_and_jobs.py PASSED (5/5)
backend/tests/ai/test_gemini_provider.py PASSED (5/5)
backend/tests/api/test_api_authz_and_mcp.py PASSED (5/5)
backend/tests/api/test_full_rest_api_v1.py PASSED (3/3)
backend/tests/api/test_remediation_fase3_persistence_and_concurrency.py PASSED (5/5)
backend/tests/domain/test_domain_and_schemas.py PASSED (4/4)
backend/tests/golden/test_golden_examples.py PASSED (10/10)
backend/tests/mechanism/test_minimum_shippable_and_journeys.py PASSED (6/6)
backend/tests/ops/test_privacy_observability_and_ops.py PASSED (7/7)
backend/tests/payments/test_payments_and_failures.py PASSED (5/5)
backend/tests/policy_engine/test_mechanism_verification.py PASSED (18/18)
backend/tests/state_machine/test_return_state_machine.py PASSED (4/4)

================= 77 passed, 2 deselected, 1 warning in 3.25s =================
```

Cross-reference verification:
```
uv run python scripts/check_refs.py -> check-refs PASSED (XR-01..XR-10 verified).
```

---

## 4. Requirements Traceability Matrix (RTM) Progress

- **Total Requirements**: 137
- **VERIFIED**: 17 (+5: `INV-01`, `INV-04`, `FR-72`, `FR-80`, `NFR-04`)
- **IMPLEMENTED**: 55
- **SPECIFIED**: 65
