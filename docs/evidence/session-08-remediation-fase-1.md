# Remediation Fase R1 Evidence & Verification Record (`docs/evidence/session-08-remediation-fase-1.md`)

- **Date**: `2026-11-02`
- **Scope**: Fase R1 — Secret Hygiene, Tautological Stub Elimination, Pytest Configuration & Truthful Reset of RTM / Gates
- **SSOT Version**: `1.2.1`
- **Audit Findings Resolved**: `AUD-03`, `AUD-23`, `AUD-26`, `AUD-31`, `AUD-33`, `AUD-35`, `DOC-01`, `DOC-02`, `DOC-03`, `DOC-04`, `DOC-08`, `DUR-07`, `J-01`, `J-02`

---

## 1. Summary of Changes & Verifications

### 1.1 Pytest Configuration & Marker Deselection (`AUD-03`, `DUR-07`)
- **Action**: Edited `pyproject.toml` to remove non-existent `sim/tests` from `testpaths` and added `addopts = "-m 'not live_model and not sandbox'"`.
- **Verification**: `uv run pytest --collect-only` showed `collected 72 items / 2 deselected / 70 selected`.

### 1.2 Secret & Salt Hygiene (`AUD-23`, `AUD-26`, `AUD-31`, `J-01`, `INV-09`, `INV-13`)
- **`backend/config.py`**: Removed hardcoded static default salts. Added ephemeral dynamic generation for local non-prod fallback while strictly enforcing `>= 32` bytes.
- **`.env.example`**: Replaced static hex salts with placeholder strings.
- **`backend/domain/fraud_flags.py`**: Made `salt: str` a required parameter in `FraudFlagRegistry` and enforced `>= 32` bytes.
- **`backend/jobs/anchor.py`**: Made `signing_seed: bytes` a required parameter in `create_daily_anchor_token` with `>= 32` bytes validation.
- **`scripts/replay_decision.py`**: Replaced static platform seed with configurable parameter/env input.
- **`infra/docker-compose.yml`**: Parameterized passwords via `${POSTGRES_PASSWORD:-...}` and `${S3_ACCESS_KEY:-...}`.

### 1.3 Elimination of Fake Pass Stubs (`AUD-03`, `AUD-33`, `AUD-35`)
- **`backend/payments/reconciliation.py`**: Replaced constant return stubs with concrete audits over `RefundLedger` across `REC-01` (stuck sweeper), `REC-02` (cumulative refund <= capture cap, `INV-01`), `REC-03` (missing webhook gap), and `REC-04` (daily report).
- **`backend/ops/drills.py`**:
  - `run_backup_restore_drill` now verifies live reconciliation report and halts money actions (`money_actions_reenabled = False`) on dirty reconciliation or RPO/RTO violations (`BK-07`).
  - `run_clean_env_judge_mode_check` executes deterministic `decide_release` bit-for-bit check and evaluates bootstrap timing limits.
- **`backend/payments/failures.py`**: Removed fallthrough stub; explicitly implemented handling and assertions for all 20 modes (`FX-01`..`FX-20`).
- **`backend/ai/pipeline/forensics.py`**: Replaced hardcoded `1.42s` latency with dynamic execution time measurement.

### 1.4 Truthful Reset of RTM & Gate Records (`DOC-01`..`DOC-04`, `DOC-08`, `SI-01`..`SI-05`, `J-02`)
- **`docs/sandbox-tests.md`**: Removed `VERIFIED_CONTRACT`. Kept `ST-09` as `VERIFIED` (live OAuth and idempotent Order v2 verified), marked `ST-01`, `ST-06`, `ST-10`..`ST-13` as `IMPLEMENTED`, and `ST-02`..`ST-05`, `ST-07`, `ST-08` as `SPECIFIED`.
- **`docs/gates/final-acceptance.md`**: Aligned strictly to SSOT §27 timeline (G0 PASSED, G1/G2 IN PROGRESS, G3–G6 PENDING).
- **`scripts/sync_rtm.py` & `docs/rtm.csv`**:
  - `VERIFIED`: Exactly 9 requirements (`FR-31`, `FR-43`, `FR-44`, `FR-89`, `INV-05`, `INV-07`, `INV-08`, `INV-15`, `INV-18`).
  - `IMPLEMENTED`: 60 requirements (pure unit/property tested).
  - `SPECIFIED`: 68 requirements (awaiting upcoming milestone implementation).
  - Total: 137 requirements.

---

## 2. Test Execution Log
```
platform win32 -- Python 3.12.13, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\renal\Downloads\ProofReturn
configfile: pyproject.toml
testpaths: backend/tests
plugins: anyio-4.15.1, hypothesis-6.170.13
collected 72 items / 2 deselected / 70 selected

================= 70 passed, 2 deselected, 1 warning in 2.36s =================
```
