# Evidence Report: Session 14 — Live Operational Validation (Gemini 3.6 Flash & PayPal Sandbox)

**Date**: 2026-11-02  
**Author**: Antigravity Assistant  
**Finding & SSOT References**: ST-01, ST-09, FR-18, NFR-02, NFR-03, TM-16, DB-01..DB-10, AUD-35, AUD-37, AUD-38  

---

## 1. Executive Summary

Session 14 performs live operational validation against real external endpoints and services as requested by the user and specified in the ProofReturn SSOT v1.21:
1. **Google Gemini Multimodal Vision API (`gemini-3.6-flash`) (`ST-01`, `FR-18`, `NFR-02`)**:
   - Live endpoint: `https://generativelanguage.googleapis.com/v1beta/models`.
   - Verified that the model catalog includes `models/gemini-3.6-flash` and is accessible with the configured API key.
   - Executed live multimodal grading with structured JSON schema (`RESPONSE_JSON_SCHEMA`), receiving valid parsed grades (`predicted_grade="DEF"`, `authenticity_score=0.15`, `tamper_score=0.85`, and vision reasoning rationale).
2. **PayPal Sandbox Live Integration (`ST-09`, `NFR-03`, `INV-03`, `INV-07`, `TM-16`)**:
   - Live endpoint: `https://api-m.sandbox.paypal.com`.
   - Verified live OAuth2 client credentials grant, negotiating bearer access tokens.
   - Verified idempotent order creation via `PayPal-Request-Id` (UUIDv5) preventing double-billing on retries.
3. **Database Migrations & Operational Seeding (`DB-01`..`DB-10`, `NFR-08`)**:
   - Ran `alembic upgrade head` confirming schema head at `0001_initial_schema` across all 22 tables.
   - Executed operational seeding injecting realistic demo merchants, staff users, shopper accounts, orders, condition passports, and returns.
4. **Runtime Readiness Probes & Observability (`AUD-37`, `NFR-08`)**:
   - Verified `GET /v1/ready` returns HTTP 200 with `database_connected: true` and `active_alerts_count: 0`.
   - Verified `GET /v1/metrics` exports standard Prometheus metrics streams.
   - Verified `GET /v1/ops/alerts` checks all operational alerts `AL-01`..`AL-07`.

---

## 2. Test Execution & Evidence

### 2.1 Live Gemini Vision Model Test (`gemini-3.6-flash`)
Command:
```powershell
uv run pytest backend/tests/ai/test_ai_pipeline_and_jobs.py -m live_model -v
```
Output:
```
============================= test session starts =============================
platform win32 -- Python 3.12.13, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\renal\Downloads\ProofReturn
configfile: pyproject.toml
testpaths: backend/tests
plugins: anyio-4.15.1, hypothesis-6.170.13
collected 12 items / 11 deselected / 1 selected

backend/tests/ai/test_ai_pipeline_and_jobs.py::test_live_gemini_multimodal_vision_real_call PASSED [100%]

======================= 1 passed, 11 deselected in 7.57s =======================
```

### 2.2 Live PayPal Sandbox OAuth2 & Idempotency Test
Command:
```powershell
uv run pytest backend/tests/payments/test_payments_and_failures.py -m sandbox -v
```
Output:
```
============================= test session starts =============================
platform win32 -- Python 3.12.13, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\renal\Downloads\ProofReturn
configfile: pyproject.toml
testpaths: backend/tests
plugins: anyio-4.15.1, hypothesis-6.170.13
collected 9 items / 8 deselected / 1 selected

backend/tests/payments/test_payments_and_failures.py::test_live_paypal_sandbox_oauth_and_order_creation PASSED [100%]

======================= 1 passed, 8 deselected in 4.26s =======================
```

### 2.3 Database Migrations & Runtime Probe Execution
Commands & Verification:
- `uv run alembic upgrade head`: Applied migration `0001_initial_schema`.
- Database Seed: Instantiated 1 merchant (`merch_demo_1`), 6 staff users across 5 roles, 2 shopper accounts, 2 orders, 1 origin passport, 1 return entity.
- Readiness Probe:
  ```json
  GET /v1/ready -> HTTP 200
  {
    "status": "ready",
    "database_connected": true,
    "active_alerts_count": 0
  }
  ```

### 2.4 Offline Safety Suite & Credential Scan
- Full Offline Pytest Suite: **96 passed, 2 deselected, 0 failed in 4.88s**.
- Secret Scanner (`scripts/scan_secrets.py`): Scanned 209 files across repository, **0 credentials or leaked keys detected**.
- Reference Checker (`scripts/check_refs.py`): **PASSED** (`XR-01`..`XR-10` verified).

---

## 3. RTM Alignment Status
- **`VERIFIED`**: 27 requirements & invariants with non-mocked evidence.
- **`IMPLEMENTED`**: 48 requirements & invariants with full codebase coverage.
- **`SPECIFIED`**: 62 requirements planned for subsequent phases.
- **Total**: 137 requirements tracked in `docs/rtm.csv`.
