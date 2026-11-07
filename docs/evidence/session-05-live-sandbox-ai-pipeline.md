# Evidence Report — Session 05: Config Registry, Complete AI Pipeline (`FR-03`, `FR-15`, `FR-18`, `FR-20`, `FR-36`, `FR-65`, `FR-66`), Maintenance Jobs (`FR-83`, `NFR-05`), and Live PayPal Sandbox & Gemini Verification

- **Date**: 2026-10-31
- **Task ID**: `SESSION-05-LIVE-SANDBOX-AI-PIPELINE`
- **Risk Class**: `HIGH` (TDD Red-Green-Refactor executed per `DUR-01`)
- **SSOT Sections Covered**: Sections 7.1, 10.2, 11.4, 24, 31.3, 35.1

## 1. Test Execution Summary

Command:
```powershell
uv run pytest -v
```
Result: **62 passed** (including `@pytest.mark.live_model` and `@pytest.mark.sandbox` live tests)

### New & Expanded Test Suites Verified in Session 05

1. `backend/tests/ai/test_ai_pipeline_and_jobs.py`
   - `test_config_registry_loads_and_masks_secrets`: Verifies `ProofReturnSettings` (`Section 35.1`) loads environment configuration with `SecretStr` masking, enforces `TM-16` (Sandbox URL guard), `TM-24` (`CARRIER_EVENTS_MANUAL` disabled when `DEMO_MODE=false`), and `>= 32`-byte salt checks (`INV-09`, `INV-13`).
   - `test_ocr_forensics_nonce_retakes_and_output_guard`:
     - `FR-03`: Serial extraction and normalized cross-check across 3 demo SKUs (`PR-HP-XM5`, `PR-KB-Q1P`, `PR-CM-A67`).
     - `FR-15`: Intake explanation output guard rejecting outcome promises (`OUTCOME_PROMISE_FORBIDDEN`).
     - `FR-18` & `FR-20`: Media forensics scorer and offline red-team suite (`0` false Fast Lane approvals, `p95_latency_seconds = 1.42s <= 20s` per `NFR-02`).
     - `FR-65`: Distinguishes `NONCE_UNREADABLE` (retake allowed) vs `NONCE_MISMATCH` (immediate escalation).
     - `FR-66`: Enforces retake limits (`3 per step / 8 per return`) with generic feedback.
   - `test_f08_valuation_model_and_mape_target`: Verifies resale valuation predictor and curated comps MAPE (`<= 12%` target in Section 11.4, `FR-36`).
   - `test_retention_job_and_daily_anchor_token`: Verifies `NFR-05` media retention crypto-shredding job and `FR-83` Ed25519-signed daily Merkle anchor token.
   - `test_api_passports_review_queue_and_simulator_endpoints`: Verifies `POST /v1/passports` (`FR-02`, `FR-98`), `GET /v1/passports/{id}/verify`, `GET /v1/review/queue` (`FR-50`), and `POST /v1/simulate` (`FR-52`, `NFR-16`).
   - `test_live_gemini_assessment_if_configured`: Executes live multimodal grading (`@pytest.mark.live_model`) against Google Generative Language API (`gemini-3-flash-preview`) with header-passed `x-goog-api-key` (`INV-13`), returning `HTTP 200 OK` and structured JSON output (`predicted_grade="B"`, `conformal_set=["B"]`, `authenticity_score=0.95`, `detected_defects=["minor surface scuff on headband"]`, `forensic_flags=[]`).

2. `backend/tests/payments/test_payments_and_failures.py`
   - `test_paypal_sandbox_live_oauth_and_idempotent_order`: Executes live OAuth2 client-credentials token exchange (`POST /v1/oauth2/token`) and live idempotent Order v2 creation (`POST /v2/checkout/orders` with `PayPal-Request-Id` replay returning the identical order ID, `ST-09`, `NFR-03`, `INV-03`, `INV-07`).
