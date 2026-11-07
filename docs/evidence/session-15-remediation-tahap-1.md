# Evidence Report: Session 15 — Re-Audit Remediation Tahap 1 (Fail-Closed Auth, Key Separation, CSPRNG Audit Seeds, Alembic 22-Table Sync & Postgres Driver)

**Date**: 2026-11-02  
**Author**: Antigravity Assistant  
**Re-Audit Roadmap & Finding References**: J-01, J-03, RV-01 (CRITICAL), RV-02 (HIGH), AUD-07 (HIGH), RV-08 (MEDIUM), AUD-28 (MEDIUM), RV-12 (LOW), RV-13 (LOW), AUD-31 (LOW), AUD-42 (LOW), DOC-06, DB-01, DB-02, DB-07  

---

## 1. Executive Summary

Tahap 1 resolves the critical security and infrastructure findings from `Laporan Audit Ulang — ProofReturn (Versi Revisi).md`:

1. **`RV-01` (CRITICAL) & `RV-12` (LOW) & `J-01` — Fail-Closed Token Authentication & Key Separation**:
   - Deleted `DEFAULT_AUTH_SECRET` and removed the `except Exception: pass` fallback from [`backend/auth/tokens.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/auth/tokens.py).
   - Added a dedicated `auth_signing_key` in [`backend/config.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/config.py) strictly separated from `serial_hash_salt` and `payer_hash_salt`. If `auth_signing_key == serial_hash_salt` or uses a compromised/placeholder value or fails to load, the system fails closed immediately.
   - Enforced mandatory positive `exp > 0`, `iss="proofreturn-api"`, `aud="proofreturn-v1"`, and `jti` claims on every token (`sign_token` and `verify_token`).
   - Wired `revoke_token` and `is_token_revoked` to persist revocations into `DatabaseRepository` (`agent_tokens` table) so token revocations survive process restarts.

2. **`RV-02` (HIGH) & `AUD-28` (MEDIUM) — CSPRNG Audit Seeds & Persistent Ed25519 Key Registry**:
   - Eliminated predictable `SHA-256("seed_platform_" + return_id)` audit seed derivation. `Return.audit_seed_hex` now generates 32 bytes of CSPRNG entropy (`secrets.token_hex(32)`) at return creation time and commits `c = SHA-256(seed_bytes || b"||" || return_id)`.
   - Added persistent Ed25519 keypairs (`get_platform_keypair()`, `get_packer_keypair()`) and a public key verification registry (`get_public_key_registry()`) in [`backend/domain/signing.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/domain/signing.py) for `platform_key_v1` and `key_packer_origin_01`.

3. **`AUD-07` (HIGH), `RV-08` (MEDIUM), `AUD-42` (LOW), `DB-01`, `DB-02`, `DB-07` & `J-03` — Alembic 22-Table Synchronization, Postgres Driver & Docker Hardening**:
   - Added `psycopg[binary]>=3.2.0` to [`pyproject.toml`](file:///c:/Users/renal/Downloads/ProofReturn/pyproject.toml) and `normalize_database_url` in [`backend/db/repository.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/db/repository.py) so `postgresql://` URLs load cleanly with `psycopg`.
   - Removed `SQLModel.metadata.create_all` from [`backend/db/repository.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/db/repository.py). Schema creation is now managed 100% by Alembic migrations (`0001_initial_schema` -> `0002_complete_canonical_schema`) across all 22 canonical tables.
   - Aligned [`backend/db/models.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/db/models.py) and [`backend/migrations/versions/0002_complete_canonical_schema.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/migrations/versions/0002_complete_canonical_schema.py) with `BigInteger` monetary fields, `currency` columns (`DB-01`), `ondelete="RESTRICT"` foreign keys (`DB-02`), `version` columns (`DB-07`), and full `RefundAction` metadata (`merchant_id`, `capture_id`, `paypal_debug_id`, `attempt_count`, `AUD-42`).
   - Hardened [`infra/Dockerfile`](file:///c:/Users/renal/Downloads/ProofReturn/infra/Dockerfile) (removed `COPY data/`, added non-root `USER appuser`, pinned `uv:0.6.3`) and [`infra/docker-compose.yml`](file:///c:/Users/renal/Downloads/ProofReturn/infra/docker-compose.yml) (bound ports to `127.0.0.1`, removed hardcoded fallback passwords).

---

## 2. Verification & Test Evidence

### 2.1 Tahap 1 Regression Suite
Command:
```powershell
uv run pytest backend/tests/remediation/test_remediation_tahap1_security_and_infra.py -v
```
Output:
```
backend/tests/remediation/test_remediation_tahap1_security_and_infra.py::test_rv01_fail_closed_auth_and_key_separation PASSED [ 25%]
backend/tests/remediation/test_remediation_tahap1_security_and_infra.py::test_rv12_mandatory_issuer_audience_and_persistent_db_revocation PASSED [ 50%]
backend/tests/remediation/test_remediation_tahap1_security_and_infra.py::test_rv02_and_aud28_csprng_audit_seed_and_persistent_ed25519_verification PASSED [ 75%]
backend/tests/remediation/test_remediation_tahap1_security_and_infra.py::test_aud07_rv08_aud42_alembic_22_tables_psycopg_and_dockerfile_hardening PASSED [100%]
============================== 4 passed in 1.11s ==============================
```

### 2.2 Full Test Suite
Command:
```powershell
uv run pytest -v
```
Output:
```
100 passed, 2 deselected, 0 failed in 5.13s
```
