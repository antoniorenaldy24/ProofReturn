# Evidence Document — Session 09 (Remediation Fase R2: Auth, Token & Authorization Hardening)

- **Date**: 2026-11-02
- **SSOT Version**: 1.2.1
- **Focus**: Audit Remediation Fase R2 (J-03) — Cryptographic Token Engine, BOLA Mitigation, Endpoint Protection, MCP Gateway Unified Auth
- **Audit Findings Remediated**: `AUD-21`, `AUD-22`, `AUD-25`, `AUD-29`, `AUD-41`
- **Requirements Progressed**: `FR-45` (VERIFIED), `INV-12` (VERIFIED), `NFR-11` (VERIFIED), `FR-12` (IMPLEMENTED), `FR-69` (IMPLEMENTED)

---

## 1. Executive Summary

Fase R2 eliminates the fundamental authorization vulnerabilities discovered in the independent technical audit (`AUD-21`, `AUD-22`, `AUD-25`, `AUD-29`, `AUD-41`):
1. **Cryptographic Token Verification (`AUD-21`, `INV-12`, `TZ-01`, `TZ-06`)**: Replaced unverified colon-separated string tokens (`staff:merch_a:PACKER`) with HMAC-SHA256 (HS256) cryptographically signed tokens containing standard claims (`sub`, `type`, `role`, `tenant_id`/`merchant_id`, `order_id`, `scopes`, `iat`, `exp`). Tampered signatures, expired tokens, or forged strings are strictly rejected with HTTP 401 (`AUTH_REQUIRED` / `AUTH_EXPIRED`).
2. **Broken Object-Level Authorization (BOLA) Mitigation (`AUD-22`, `TZ-04`)**: Added strict tenant and resource scoping in `backend/api/app.py`. A shopper token scoped to `ord_demo_1` cannot view or act on other returns or orders. Out-of-scope access returns HTTP 404 per `TZ-04` so as not to disclose resource existence.
3. **Operational Endpoints Protection (`AUD-25`)**: Removed the spoofable `X-Actor-Role` header from `POST /v1/demo/reset` and `POST /v1/demo/clock/advance`. These endpoints now require a verified `MERCHANT_ADMIN` token with valid cryptographic signature.
4. **Appeals Reviewer Independence (`AUD-29`, `FR-69`, `F-15`)**: Appeals decided via `POST /v1/review/appeals/{id}/decision` verify that `principal.sub` does not match the stored `original_reviewer_id`. Any attempt by the original reviewer to decide the appeal is rejected with HTTP 409 (`SAME_REVIEWER_CONFLICT`).
5. **Unified MCP Server & REST Token Verification (`AUD-41`, `FR-45`)**: Integrated `verify_token` inside `backend/agent_gateway/mcp_server.py`. MCP tools reject unsigned tokens and verify that the token holds the necessary scope (`read_policy`, `declare`, `keep_offer`). Implemented `POST /v1/agent/tokens` per SSOT §28.3.

---

## 2. Key Code Implementations

- **`backend/auth/tokens.py`**:
  - `sign_token(payload, secret)`: Encodes base64url header and payload, signs with HMAC-SHA256.
  - `verify_token(raw_token, secret)`: Parses, verifies signature with constant-time comparison, validates `exp`, checks in-memory revocation list, returns typed `Principal`.
  - `mint_staff_token(...)`, `mint_shopper_token(...)`, `mint_agent_token(...)`, `mint_service_token(...)`.
  - `revoke_token(sig)` and `is_token_revoked(sig)`.
- **`backend/api/app.py`**:
  - `_resolve_principal(authorization, required)`: Helper extracting and verifying Bearer tokens, mapping errors to RFC 9457 `401 AUTH_REQUIRED` or `401 AUTH_EXPIRED`.
  - Scoped resource checks in `/v1/returns/{id}/*`, `/v1/orders/{id}/*`, `/v1/passports/{id}`, `/v1/resale/listings/{id}`.
  - Protected `POST /v1/demo/reset` requiring `principal.is_staff and principal.role == "MERCHANT_ADMIN"`.
  - Enforced reviewer independence in `POST /v1/review/appeals/{id}/decision`.
  - Implemented `POST /v1/agent/tokens` issuing scoped tokens for agents.
- **`backend/agent_gateway/mcp_server.py`**:
  - Integrated `verify_token(token)` in `_parse_and_verify_agent_token`.
  - Enforces scope checking (`"declare"`, `"keep_offer"`) against verified agent principal.

---

## 3. Automated Test Verification

All 71 active tests passed with zero failures (2 live/sandbox deselected by pyproject.toml):

```
backend/tests/ai/test_ai_pipeline_and_jobs.py PASSED (5/5)
backend/tests/ai/test_gemini_provider.py PASSED (5/5)
backend/tests/api/test_api_authz_and_mcp.py PASSED (5/5)
backend/tests/api/test_full_rest_api_v1.py PASSED (3/3)
backend/tests/domain/test_domain_and_schemas.py PASSED (4/4)
backend/tests/golden/test_golden_examples.py PASSED (10/10)
backend/tests/mechanism/test_minimum_shippable_and_journeys.py PASSED (6/6)
backend/tests/ops/test_privacy_observability_and_ops.py PASSED (7/7)
backend/tests/payments/test_payments_and_failures.py PASSED (4/4)
backend/tests/policy_engine/test_mechanism_verification.py PASSED (18/18)
backend/tests/state_machine/test_return_state_machine.py PASSED (4/4)

================= 71 passed, 2 deselected, 1 warning in 2.76s =================
```

Cross-reference verification:
```
uv run python scripts/check_refs.py -> check-refs PASSED (XR-01..XR-10 verified).
```

---

## 4. Requirements Traceability Matrix (RTM) Progress

- **Total Requirements**: 137
- **VERIFIED**: 12 (+3: `FR-45`, `INV-12`, `NFR-11`)
- **IMPLEMENTED**: 59
- **SPECIFIED**: 66
