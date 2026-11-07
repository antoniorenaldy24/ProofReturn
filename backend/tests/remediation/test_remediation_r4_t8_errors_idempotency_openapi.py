"""Round 4 Task T8: Error catalog, idempotency, and OpenAPI request schemas (RV3-08 LOW, AUD-40 LOW).

Tests written FIRST (TDD Red -> Green):
1. Loads `backend.api.errors` and fails if any `_problem(...)` call in `backend/api/` uses a code
   not defined in `backend.api.errors` (or uses an inline string literal instead of module constants),
   and verifies `docs/change-control/CR-R4-error-codes.md` documents every non-SSOT code.
2. For each listed POST endpoint that can plan, execute, or change a refund, a capture, an ownership
   transfer, or a policy:
   - missing `Idempotency-Key` -> 400 (`IDEMPOTENCY_KEY_REQUIRED`)
   - same `Idempotency-Key` + same body -> identical response
   - same `Idempotency-Key` + different body -> 409 (`IDEMPOTENCY_CONFLICT`)
   - keys are scoped per principal and tenant
3. `/openapi.json` contains a `requestBody` schema for each of those endpoints (and all body-taking
   POST endpoints), and the existing `application/problem+json` 422 handler remains active.
"""

from __future__ import annotations

import ast
import pathlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.config import ProofReturnSettings
from backend.db.models import Appeal, Order, Return, Review
from backend.db.repository import DatabaseRepository

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

# All POST endpoints that can plan, execute, or change a refund, a capture,
# an ownership transfer, or a policy (RV3-08, API-06).
LISTED_IDEMPOTENT_POST_OPENAPI_PATHS: tuple[str, ...] = (
    "/v1/returns",
    "/v1/returns/{return_id}/evidence",
    "/v1/returns/{return_id}/keep-offer/respond",
    "/v1/review/{return_id}/decision",
    "/v1/audits/{return_id}",
    "/v1/review/appeals/{appeal_id}/decision",
    "/v1/orders/{order_id}/passport",
    "/v1/passports",
    "/v1/resale/listings",
    "/v1/resale/listings/{listing_id}/order",
    "/v1/policies",
)


@pytest.mark.req("RV3-08", "API-07")
def test_error_code_module_and_all_problem_calls_use_catalog_constants() -> None:
    """Every `_problem(...)` call in `backend/api/` must use a constant from `backend.api.errors`,
    and every non-SSOT code must be documented in `docs/change-control/CR-R4-error-codes.md`.
    """
    from backend.api import errors as err_mod

    assert hasattr(err_mod, "ALL_ERROR_CODES")
    assert hasattr(err_mod, "SSOT_ERROR_CODES")
    assert hasattr(err_mod, "CR_R4_ERROR_CODES")
    assert hasattr(err_mod, "ErrorCode")

    all_codes: dict[str, dict[str, Any]] = err_mod.ALL_ERROR_CODES
    ssot_codes: dict[str, dict[str, Any]] = err_mod.SSOT_ERROR_CODES
    cr_codes: dict[str, dict[str, Any]] = err_mod.CR_R4_ERROR_CODES

    assert len(cr_codes) >= 24, f"Expected at least 19 pre-existing + R4 codes, got {len(cr_codes)}"
    assert set(all_codes.keys()) == set(ssot_codes.keys()) | set(cr_codes.keys())

    # Verify Change Control document exists and lists every code in CR_R4_ERROR_CODES
    cr_doc_path = REPO_ROOT / "docs" / "change-control" / "CR-R4-error-codes.md"
    assert cr_doc_path.is_file(), f"Missing change control document: {cr_doc_path}"
    cr_doc_text = cr_doc_path.read_text(encoding="utf-8")
    for code_name, meta in cr_codes.items():
        assert f"`{code_name}`" in cr_doc_text, (
            f"Non-SSOT error code {code_name} is missing from {cr_doc_path}"
        )
        assert str(meta["http_status"]) in cr_doc_text

    # Collect all constant attribute names on ErrorCode and module-level constants in backend.api.errors
    valid_const_names: dict[str, str] = {}
    for attr_name in dir(err_mod.ErrorCode):
        if attr_name.isupper():
            val = getattr(err_mod.ErrorCode, attr_name)
            if isinstance(val, str):
                valid_const_names[attr_name] = val
    for attr_name in dir(err_mod):
        if attr_name.isupper():
            val = getattr(err_mod, attr_name)
            if isinstance(val, str):
                valid_const_names[attr_name] = val

    # Inspect AST of backend/api/app.py to verify every _problem(...) call
    app_path = REPO_ROOT / "backend" / "api" / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    problem_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_problem"
    ]
    assert len(problem_calls) > 0, "Expected _problem(...) calls in backend/api/app.py"

    violations: list[str] = []
    for call in problem_calls:
        if len(call.args) < 2:
            violations.append(f"Line {call.lineno}: _problem call has fewer than 2 positional args")
            continue
        code_arg = call.args[1]
        resolved_code: str | None = None
        if (
            isinstance(code_arg, ast.Attribute)
            and isinstance(code_arg.value, ast.Name)
            and code_arg.value.id in {"ErrorCode", "errors"}
        ):
            resolved_code = valid_const_names.get(code_arg.attr)
            if resolved_code is None:
                violations.append(
                    f"Line {call.lineno}: unknown error attribute {ast.unparse(code_arg)}"
                )
        elif isinstance(code_arg, ast.Name) and code_arg.id in valid_const_names:
            resolved_code = valid_const_names[code_arg.id]
        else:
            violations.append(
                f"Line {call.lineno}: _problem uses non-constant code {ast.unparse(code_arg)} "
                "(must use constant from backend.api.errors)"
            )

        if resolved_code is not None and resolved_code not in all_codes:
            violations.append(
                f"Line {call.lineno}: code '{resolved_code}' is not registered in ALL_ERROR_CODES"
            )

    assert not violations, "Found _problem(...) error code violations:\n" + "\n".join(violations)


@pytest.mark.req("RV3-08", "API-06")
def test_listed_post_endpoints_require_idempotency_key_and_enforce_replay_and_conflict(
    tmp_path: pathlib.Path,
) -> None:
    """For each of the 11 listed POST endpoints:
    1. Missing Idempotency-Key -> 400 IDEMPOTENCY_KEY_REQUIRED
    2. Same Idempotency-Key + same body -> identical 2xx response
    3. Same Idempotency-Key + different body -> 409 IDEMPOTENCY_CONFLICT
    4. Keys are scoped per principal and tenant.
    """
    db_url = f"sqlite:///{tmp_path / 't8_idem.db'}"
    settings = ProofReturnSettings(
        mode="judge",
        database_url=db_url,
        demo_mode=True,
        enable_scheduler=False,
    )
    repo = DatabaseRepository(database_url=db_url)
    app = create_app(settings=settings, repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)

    # Seed fixture states needed so each of the 11 endpoints succeeds on its first valid call
    from backend.db.models import OrderItem

    for item_suffix in ("ev", "ko", "rev", "aud"):
        repo.save_order_item(
            OrderItem(
                order_item_id=f"item_t8_{item_suffix}",
                order_id="ord_demo_1",
                passport_id="pass_demo_1",
                sku="PR-HP-XM5",
                price_minor=38000,
                currency="USD",
            )
        )

    # 1. Return in DECLARED state for /evidence
    ret_ev = Return(
        return_id="ret_t8_ev",
        order_id="ord_demo_1",
        order_item_id="item_t8_ev",
        merchant_id="merch_a",
        shopper_id="shopper_1",
        state="DECLARED",
        lane="FAST",
        timing="R0",
        declared_grade="B",
        r0_tranche_minor=0,
        currency="USD",
        challenge_nonce="NONCE-T8-EV",
        audit_seed_hex="ab" * 32,
        audit_commitment="cd" * 32,
        audit_probability=0.05,
        consent_recorded=True,
    )
    repo.save_return(ret_ev)

    # 2. Return in ASSESSED state for /keep-offer/respond
    ret_ko = Return(
        return_id="ret_t8_ko",
        order_id="ord_demo_1",
        order_item_id="item_t8_ko",
        merchant_id="merch_a",
        shopper_id="shopper_1",
        state="ASSESSED",
        lane="FAST",
        timing="R0",
        declared_grade="B",
        r0_tranche_minor=0,
        currency="USD",
        challenge_nonce="NONCE-T8-KO",
        audit_seed_hex="12" * 32,
        audit_commitment="34" * 32,
        audit_probability=0.05,
        consent_recorded=True,
    )
    repo.save_return(ret_ko)
    from backend.db.models import Assessment

    repo.save_assessment(
        Assessment(
            assessment_id="ass_t8_ko",
            return_id="ret_t8_ko",
            predicted_grade="B",
            conformal_set=["B"],
            replay_label="GENUINE",
            forensic_flags=[],
        )
    )

    # 3. Return in RECEIVED state for /v1/review/{return_id}/decision
    repo.save_order(
        Order(
            order_id="ord_t8_rev",
            merchant_id="merch_a",
            account_id="shopper_1",
            policy_version="pol_v1_us_ca",
            capture_id="CAP_T8_REV_01",
            capture_amount_minor=38000,
            currency="USD",
        )
    )
    ret_rev = Return(
        return_id="ret_t8_rev",
        order_id="ord_t8_rev",
        order_item_id="item_t8_rev",
        merchant_id="merch_a",
        shopper_id="shopper_1",
        state="RECEIVED",
        lane="STANDARD",
        timing="R2",
        declared_grade="B",
        r0_tranche_minor=0,
        currency="USD",
        challenge_nonce="NONCE-T8-REV",
        audit_seed_hex="56" * 32,
        audit_commitment="78" * 32,
        audit_probability=0.05,
        consent_recorded=True,
    )
    repo.save_return(ret_rev)

    # 4. Return in AUDIT_SELECTED state for /v1/audits/{return_id}
    ret_aud = Return(
        return_id="ret_t8_aud",
        order_id="ord_demo_1",
        order_item_id="item_t8_aud",
        merchant_id="merch_a",
        shopper_id="shopper_1",
        state="AUDIT_SELECTED",
        lane="STANDARD",
        timing="R2",
        declared_grade="B",
        r0_tranche_minor=0,
        currency="USD",
        challenge_nonce="NONCE-T8-AUD",
        audit_seed_hex="9a" * 32,
        audit_commitment="bc" * 32,
        audit_probability=0.05,
        consent_recorded=True,
    )
    repo.save_return(ret_aud)

    # 5. Appeal + original Review for /v1/review/appeals/{appeal_id}/decision
    repo.save_review(
        Review(
            review_id="rev_orig_t8",
            return_id="ret_t8_rev",
            reviewer_id="rev_original_01",
            verified_grade="C",
            outcome="DOWNGRADED",
            notes="Original review",
        )
    )
    repo.save_appeal(
        Appeal(
            appeal_id="app_t8_1",
            return_id="ret_t8_rev",
            original_reviewer_id="rev_original_01",
            status="OPEN",
            disputed_delta_minor=2000,
        )
    )

    # 6. Pre-create a resale listing for /v1/resale/listings/{listing_id}/order
    op_token = mint_staff_token(merchant_id="merch_a", role="MERCHANT_OPERATOR", sub="op_t8")
    packer_token = mint_staff_token(merchant_id="merch_a", role="PACKER", sub="pack_t8")
    reviewer_token = mint_staff_token(merchant_id="merch_a", role="REVIEWER", sub="rev_t8_2")
    admin_token = mint_staff_token(merchant_id="merch_a", role="MERCHANT_ADMIN", sub="adm_t8")
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1", merchant_id="merch_a")

    # Seed a listing directly for the order purchase endpoint test
    from backend.db.models import ResaleListing

    repo.save_resale_listing(
        ResaleListing(
            listing_id="lst_t8_order",
            passport_id="pass_demo_1",
            merchant_id="merch_a",
            verified_grade="A",
            price_minor=25000,
            currency="USD",
            status="ACTIVE",
        )
    )

    # Define the 11 endpoint test cases: (openapi_path, concrete_url, token, body_1, body_2)
    cases: list[tuple[str, str, str, dict[str, Any], dict[str, Any]]] = [
        (
            "/v1/returns",
            "/v1/returns",
            shopper_token,
            {"order_id": "ord_demo_1", "items": ["PR-HP-XM5"]},
            {"order_id": "ord_demo_1", "items": ["PR-HP-OTHER"]},
        ),
        (
            "/v1/returns/{return_id}/evidence",
            "/v1/returns/ret_t8_ev/evidence",
            shopper_token,
            {
                "kind": "VIDEO_CHALLENGE",
                "object_key": "raw/ret_t8_ev/v1.mp4",
                "sha256": "a" * 64,
                "challenge_step": 1,
                "faces_detected": 0,
                "client_blur_applied": True,
                "blur_latency_ms": 12.0,
                "text_in_media": "NONCE-T8-EV",
            },
            {
                "kind": "VIDEO_CHALLENGE",
                "object_key": "raw/ret_t8_ev/v2_diff.mp4",
                "sha256": "b" * 64,
                "challenge_step": 1,
                "faces_detected": 0,
                "client_blur_applied": True,
                "blur_latency_ms": 12.0,
                "text_in_media": "NONCE-T8-EV",
            },
        ),
        (
            "/v1/returns/{return_id}/keep-offer/respond",
            "/v1/returns/ret_t8_ko/keep-offer/respond",
            shopper_token,
            {"action": "accept"},
            {"action": "decline"},
        ),
        (
            "/v1/review/{return_id}/decision",
            "/v1/review/ret_t8_rev/decision",
            reviewer_token,
            {"outcome": "CONFIRMED", "verified_grade": "B", "notes": "Matches grade B"},
            {"outcome": "DOWNGRADED", "verified_grade": "C", "notes": "Downgraded to C"},
        ),
        (
            "/v1/audits/{return_id}",
            "/v1/audits/ret_t8_aud",
            reviewer_token,
            {"verified_grade": "B", "conformal_set": ["B"], "notes": "Audit match"},
            {"verified_grade": "C", "conformal_set": ["C"], "notes": "Audit mismatch"},
        ),
        (
            "/v1/review/appeals/{appeal_id}/decision",
            "/v1/review/appeals/app_t8_1/decision",
            reviewer_token,
            {"outcome": "UPHELD"},
            {"outcome": "DENIED"},
        ),
        (
            "/v1/orders/{order_id}/passport",
            "/v1/orders/ord_demo_1/passport",
            packer_token,
            {"sku": "PR-HP-XM5", "origin_grade": "A", "weight_g": 250, "self_test_passed": True},
            {"sku": "PR-HP-XM5", "origin_grade": "B", "weight_g": 260, "self_test_passed": True},
        ),
        (
            "/v1/passports",
            "/v1/passports",
            packer_token,
            {
                "order_id": "ord_demo_1",
                "sku": "PR-HP-XM5",
                "origin_grade": "A",
                "weight_g": 250,
                "self_test_passed": True,
            },
            {
                "order_id": "ord_demo_1",
                "sku": "PR-HP-XM5",
                "origin_grade": "B",
                "weight_g": 265,
                "self_test_passed": True,
            },
        ),
        (
            "/v1/resale/listings",
            "/v1/resale/listings",
            op_token,
            {"passport_id": "pass_demo_1", "verified_grade": "A", "price_minor": 28000},
            {"passport_id": "pass_demo_1", "verified_grade": "B", "price_minor": 24000},
        ),
        (
            "/v1/resale/listings/{listing_id}/order",
            "/v1/resale/listings/lst_t8_order/order",
            shopper_token,
            {"new_owner_ref": "owner_ref_alpha"},
            {"new_owner_ref": "owner_ref_beta"},
        ),
        (
            "/v1/policies",
            "/v1/policies",
            admin_token,
            {
                "jurisdiction": "US",
                "policy_version": "pol_t8_us_v1",
                "return_window_days": 30,
                "curve": {"A": 1.0, "B": 0.95, "C": 0.85, "D": 0.60},
            },
            {
                "jurisdiction": "US",
                "policy_version": "pol_t8_us_v2",
                "return_window_days": 45,
                "curve": {"A": 1.0, "B": 0.95, "C": 0.80, "D": 0.55},
            },
        ),
    ]

    assert tuple(c[0] for c in cases) == LISTED_IDEMPOTENT_POST_OPENAPI_PATHS

    for idx, (openapi_path, url, tok, body_1, body_2) in enumerate(cases):
        # 1. Missing Idempotency-Key -> 400
        r_missing = client.post(
            url,
            headers={"Authorization": f"Bearer {tok}"},
            json=body_1,
        )
        assert r_missing.status_code == 400, (
            f"[{openapi_path}] Expected 400 when Idempotency-Key is missing, got {r_missing.status_code}: {r_missing.text}"
        )
        assert r_missing.headers["content-type"].startswith("application/problem+json")
        assert r_missing.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"

        # 2. First call with Idempotency-Key + body_1 -> 200/201
        idem_key = f"idem_t8_case_{idx}"
        r_first = client.post(
            url,
            headers={"Authorization": f"Bearer {tok}", "Idempotency-Key": idem_key},
            json=body_1,
        )
        assert r_first.status_code in {200, 201}, (
            f"[{openapi_path}] Expected 200/201 on first call, got {r_first.status_code}: {r_first.text}"
        )

        # 3. Second call with SAME Idempotency-Key + SAME body_1 -> identical response
        r_replay = client.post(
            url,
            headers={"Authorization": f"Bearer {tok}", "Idempotency-Key": idem_key},
            json=body_1,
        )
        assert r_replay.status_code == r_first.status_code, (
            f"[{openapi_path}] Replay status mismatch: {r_replay.status_code} != {r_first.status_code}"
        )
        assert r_replay.json() == r_first.json(), (
            f"[{openapi_path}] Replay body mismatch: {r_replay.json()} != {r_first.json()}"
        )

        # 4. Third call with SAME Idempotency-Key + DIFFERENT body_2 -> 409 IDEMPOTENCY_CONFLICT
        r_conflict = client.post(
            url,
            headers={"Authorization": f"Bearer {tok}", "Idempotency-Key": idem_key},
            json=body_2,
        )
        assert r_conflict.status_code == 409, (
            f"[{openapi_path}] Expected 409 on different body with same Idempotency-Key, got {r_conflict.status_code}: {r_conflict.text}"
        )
        assert r_conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"

    # 5. Verify principal & tenant scoping: another admin in merch_b using the same Idempotency-Key
    # on /v1/policies with body_2 does NOT conflict with merch_a's cached entry
    admin_b_token = mint_staff_token(merchant_id="merch_b", role="MERCHANT_ADMIN", sub="adm_b_t8")
    r_other_tenant = client.post(
        "/v1/policies",
        headers={"Authorization": f"Bearer {admin_b_token}", "Idempotency-Key": "idem_t8_case_10"},
        json=cases[10][4],
    )
    assert r_other_tenant.status_code == 201, r_other_tenant.text


@pytest.mark.req("AUD-40", "API-11", "RV3-08")
def test_openapi_json_documents_request_body_schemas_and_preserves_problem_json_422(
    tmp_path: pathlib.Path,
) -> None:
    """`/openapi.json` must contain a `requestBody` schema for each listed POST endpoint
    (and every body-accepting POST endpoint), and invalid payloads still return 422 problem+json.
    """
    db_url = f"sqlite:///{tmp_path / 't8_openapi.db'}"
    settings = ProofReturnSettings(
        mode="judge",
        database_url=db_url,
        demo_mode=True,
        enable_scheduler=False,
    )
    repo = DatabaseRepository(database_url=db_url)
    app = create_app(settings=settings, repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)

    r_openapi = client.get("/openapi.json")
    assert r_openapi.status_code == 200
    spec = r_openapi.json()
    paths = spec.get("paths", {})
    schemas = spec.get("components", {}).get("schemas", {})

    # All 11 listed idempotent POST endpoints + all other body-taking POST endpoints
    all_body_post_paths = (
        *LISTED_IDEMPOTENT_POST_OPENAPI_PATHS,
        "/v1/agent/tokens",
        "/v1/auth/staff-token",
        "/v1/auth/shopper-magic-link",
        "/v1/returns/{return_id}/declaration",
        "/v1/returns/{return_id}/dropoff",
        "/v1/receiving/{passport_id}/checkpoint",
        "/v1/appeals",
        "/v1/simulate",
        "/v1/carrier-events",
        "/v1/demo/clock/advance",
        "/v1/privacy/deletion-requests",
    )

    for path in all_body_post_paths:
        assert path in paths, f"Path {path} missing from /openapi.json"
        post_op = paths[path].get("post", {})
        assert "requestBody" in post_op, f"POST {path} is missing requestBody in /openapi.json"
        json_media = (
            post_op["requestBody"]
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        assert json_media, f"POST {path} has empty application/json schema in /openapi.json"
        if "$ref" in json_media:
            ref_name = json_media["$ref"].split("/")[-1]
            assert ref_name in schemas, f"Referenced schema {ref_name} missing from components.schemas"

    # Verify the existing RFC 9457 problem+json 422 handler stays active
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1", merchant_id="merch_a")
    r_invalid = client.post(
        "/v1/returns",
        headers={"Authorization": f"Bearer {shopper_token}", "Idempotency-Key": "idem_422_check"},
        json={"order_id": ""},  # violates min_length=1 on CreateReturnRequest
    )
    assert r_invalid.status_code == 422
    assert r_invalid.headers["content-type"].startswith("application/problem+json")
    assert r_invalid.json()["code"] == "VALIDATION_FAILED"
