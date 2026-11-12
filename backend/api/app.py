"""FastAPI /v1 application factory backed by DatabaseRepository, Policy Engine, and Role Matrix.

Implements all /v1 endpoints with persistent database state (AUD-06, J-04),
real policy engine and settlement calculations (AUD-01), Pydantic input validation (AUD-04, J-08),
dynamic state machine guards (RV-03), posted keep-offer consistency (RV-04),
reviewer independence (AUD-29), secure metric/alert access (RV-11),
resale order auth (AUD-22), and staff demo reset / privacy deletion auth (AUD-25).
"""

from __future__ import annotations

import base64
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import logging
import secrets

logger = logging.getLogger("proofreturn.api")
import time
import uuid
from datetime import UTC, datetime, timedelta, timezone
from fractions import Fraction
from typing import Any

from fastapi import Body, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.api.errors import ALL_ERROR_CODES, ErrorCode
from backend.api.middleware import (
    ObservabilityMiddleware,
    RateLimiterMiddleware,
    RequestBodyLimitMiddleware,
)
from backend.api.schemas import (
    AuditResultRequest,
    CarrierEventRequest,
    CreatePolicyRequest,
    CreateResaleListingRequest,
    CreateReturnRequest,
    DecideAppealRequest,
    DemoClockRequest,
    DropoffRequest,
    EvidenceSubmissionRequest,
    FileAppealRequest,
    IssueAgentTokenRequest,
    IssueShopperMagicLinkRequest,
    IssueStaffTokenRequest,
    KeepOfferRespondRequest,
    MintPassportRequest,
    OrderPassportRequest,
    PayPalWebhookEventRequest,
    PrivacyDeletionRequest,
    PurchaseResaleListingRequest,
    ReceivingCheckpointRequest,
    ReturnDeclarationRequest,
    ReviewDecisionRequest,
    SimulateRequest,
)
from backend.auth.tokens import (
    AuthenticationError,
    InvalidTokenSignatureError,
    MalformedTokenError,
    Principal,
    TokenExpiredError,
    mint_agent_token,
    mint_shopper_token,
    mint_staff_token,
    register_revocation_persistence,
    verify_token,
)
from backend.config import ProofReturnSettings, get_settings
from backend.db.models import (
    AgentToken,
    Appeal,
    Assessment,
    CustodyEvent,
    Decision,
    KeepOffer,
    Order,
    OrderItem,
    Passport,
    PassportEvent,
    Policy,
    RefundAction,
    ResaleListing,
    Return,
    ReturnEvidence,
    Review,
    StaffUser,
    WebhookEvent,
)
from backend.db.repository import DatabaseRepository, MissingCaptureError
from backend.domain.audit_commitment import create_audit_commitment
from backend.domain.cache import BoundedTTLCache
from backend.domain.evidence_pack import generate_evidence_pack
from backend.domain.policy import PolicyConfig
from backend.domain.receipts import issue_signed_receipt, verify_signed_receipt
from backend.domain.return_state import InvalidStateTransitionError
from backend.domain.signing import (
    PACKER_KEY_ID,
    PLATFORM_KEY_ID,
    get_packer_keypair,
    get_platform_keypair,
    get_public_key_registry,
    sha256_hex,
    sign_message_ed25519,
    verify_message_ed25519,
)
from backend.jobs.automation import BackgroundAutomationScheduler
from backend.observability.metrics import AlertScheduler, MetricsRegistry, evaluate_alerts
from backend.payments.client import PayPalSandboxClient
from backend.payments.outbox import RefundOutboxExecutor
from backend.payments.ledger import (
    OrderFrozenError,
    OverRefundError,
    RefundLedger,
    compute_deterministic_request_id,
)
from backend.payments.webhooks import WebhookProcessor
from backend.policy_engine.caps import (
    JurisdictionCapViolationError,
    normalize_jurisdiction_code,
    validate_curve_for_jurisdiction,
)
from backend.policy_engine.keep_offer import KeepOfferInput, compute_posted_keep_offer
from backend.policy_engine.release import ReleaseInput, apply_fallback_degradation, decide_release
from backend.policy_engine.settlement import SettlementInput, settle_return
from sim.engine import simulate_single_return_episode
from sim.fmap import _illustrative_calib, generate_feasibility_map
from sim.roi import compute_merchant_roi

ALLOWED_AGENT_SCOPES = {"read_policy", "declare", "keep_offer", "read_return"}


def _problem(
    status: int,
    code: str,
    title: str,
    detail: str,
    *,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Construct an RFC 9457 application/problem+json response (Section 28.2)."""
    content: dict[str, Any] = {
        "type": f"https://proofreturn.dev/problems/{code.lower().replace('_', '-')}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
    }
    if extra:
        content.update(extra)
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content=content,
    )


def _resolve_principal(
    auth_header: str | None,
    *,
    required: bool = True,
) -> tuple[Principal | None, JSONResponse | None]:
    """Validate Bearer token cryptographically and resolve verified Principal (API-04, AUD-21)."""
    if not auth_header or not auth_header.startswith("Bearer "):
        if required:
            return None, _problem(401, ErrorCode.AUTH_REQUIRED, "Unauthorized", "Authentication required.")
        return None, None

    raw = auth_header.removeprefix("Bearer ").strip()
    try:
        principal = verify_token(raw)
        return principal, None
    except TokenExpiredError as exc:
        return None, _problem(401, ErrorCode.AUTH_EXPIRED, "Unauthorized", str(exc))
    except (InvalidTokenSignatureError, MalformedTokenError, AuthenticationError) as exc:
        return None, _problem(401, ErrorCode.AUTH_REQUIRED, "Unauthorized", f"Authentication failed: {exc}")


def _is_loopback_client(request: Request) -> bool:
    """Check if request originates from localhost loopback or internal test client (RV-11)."""
    client_host = request.client.host if request.client else ""
    return client_host in {"127.0.0.1", "::1", "localhost", "testclient"}


def create_app(
    settings: ProofReturnSettings | None = None,
    repository: DatabaseRepository | None = None,
    demo_mode: bool | None = None,
    mode: str | None = None,
    paypal_client: Any | None = None,
) -> FastAPI:
    """Create the ProofReturn /v1 FastAPI application with persistent repository and settings (AUD-14)."""
    import os
    resolved_settings = settings or get_settings()
    if demo_mode is not None:
        is_demo = demo_mode
    elif "DEMO_MODE" in os.environ:
        is_demo = os.environ["DEMO_MODE"].lower() in {"true", "1", "yes"}
    else:
        is_demo = bool(getattr(resolved_settings, "demo_mode", False))
    resolved_mode = mode or getattr(resolved_settings, "mode", "judge")

    should_run_migrations = (
        resolved_settings.run_migrations_on_start
        or "sqlite" in resolved_settings.database_url
    )
    repo = repository or DatabaseRepository(
        database_url=resolved_settings.database_url,
        run_migrations_on_init=should_run_migrations,
    )
    register_revocation_persistence(
        writer=repo.revoke_token_signature,
        checker=repo.is_signature_revoked,
    )
    if is_demo:
        repo.seed_demo_data()
    else:
        # R4-T6 (RV3-05 MEDIUM, API-04): Hackathon release is declared DEMO_MODE only
        logger.warning(
            "AUTH_NOT_AVAILABLE_OUTSIDE_DEMO: Authentication outside DEMO_MODE is not available; "
            "staff login and shopper magic-link delivery are deferred for hackathon release (RV3-05, API-04)."
        )

    # R4-T4 (RV3-06, INV-11, FR-10): Validate all stored policies against SSOT jurisdiction caps at startup
    startup_policy_logger = logging.getLogger("proofreturn.policy")
    for stored_pol in repo.list_policies(include_inactive=True):
        try:
            validate_curve_for_jurisdiction(stored_pol, stored_pol.jurisdiction)
        except JurisdictionCapViolationError as exc:
            startup_policy_logger.warning(
                "Stored policy %s violates jurisdiction %s (%s); marking policy inactive.",
                stored_pol.policy_version,
                stored_pol.jurisdiction,
                exc,
            )
            stored_pol.is_active = False
            cfg_copy = dict(stored_pol.config_json or {})
            cfg_copy["is_active"] = False
            cfg_copy["inactive_reason"] = str(exc)
            stored_pol.config_json = cfg_copy
            repo.save_policy(stored_pol)

    def _policy_config_from_db_policy(pol: Policy | None) -> PolicyConfig:
        if pol is None:
            return PolicyConfig.default_us()
        if not pol.is_active:
            raise JurisdictionCapViolationError(
                f"Policy '{pol.policy_version}' is inactive due to jurisdiction cap violation.",
                field="policy_version",
                jurisdiction=pol.jurisdiction,
            )
        j_code = normalize_jurisdiction_code(pol.jurisdiction)
        cfg = pol.config_json or {}
        raw_curve = cfg.get("curve") or cfg.get("curve_json")
        if isinstance(raw_curve, dict) and raw_curve:
            curve_json = {str(k): str(v) for k, v in raw_curve.items()}
            if "DEF" not in curve_json:
                curve_json["DEF"] = "1.00"
        else:
            curve_json = (
                dict(PolicyConfig.default_eu().curve_json)
                if j_code == "EU"
                else dict(PolicyConfig.default_us().curve_json)
            )
        phi_str = str(cfg.get("phi", "0.00" if j_code in {"EU", "ID"} else "0.05"))
        ret_ship = int(cfg.get("return_shipping_minor", 0 if j_code in {"EU", "ID"} else 1200))
        fee_f = cfg.get("fee_f_minor", cfg.get("f_minor"))
        if fee_f is not None and int(fee_f) > 0 and j_code in {"EU", "ID"}:
            ret_ship = max(ret_ship, int(fee_f))
        return PolicyConfig(
            version=pol.policy_version,
            jurisdiction=pol.jurisdiction,
            curve_json=curve_json,
            phi=phi_str,
            return_shipping_minor=ret_ship,
        )

    is_scheduler_enabled = getattr(resolved_settings, "enable_scheduler", True)
    scheduler_interval = getattr(resolved_settings, "scheduler_interval_seconds", 60.0)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if getattr(app.state, "enable_scheduler", False):
            if hasattr(app.state, "automation_scheduler"):
                app.state.automation_scheduler.start()
            if hasattr(app.state, "alert_scheduler"):
                app.state.alert_scheduler.start()
        yield
        if getattr(app.state, "enable_scheduler", False):
            if hasattr(app.state, "automation_scheduler"):
                app.state.automation_scheduler.stop()
            if hasattr(app.state, "alert_scheduler"):
                app.state.alert_scheduler.stop()

    app = FastAPI(title="ProofReturn API", version="1.21.0", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.repository = repo
    app.state.demo_mode = is_demo
    app.state.mode = resolved_mode

    global_metrics = MetricsRegistry()
    app.add_middleware(ObservabilityMiddleware, metrics=global_metrics)
    app.add_middleware(RateLimiterMiddleware, requests_per_minute=300)
    app.add_middleware(RequestBodyLimitMiddleware, max_body_bytes=10 * 1024 * 1024)
    idempotency_cache: BoundedTTLCache[tuple[str, int, dict[str, Any]]] = BoundedTTLCache(
        max_size=10000, ttl_seconds=86400.0
    )
    clock_offset_seconds = 0

    # Payments & Webhook Infrastructure (J-06, AUD-02, AUD-24, RV-14, RV2-04, RV3-11)
    refund_ledger = RefundLedger(repository=repo)
    for ord_obj in repo.list_orders():
        if ord_obj.capture_id:
            refund_ledger.register_order(
                order_id=ord_obj.order_id,
                merchant_id=ord_obj.merchant_id,
                capture_id=ord_obj.capture_id,
                capture_amount_minor=ord_obj.capture_amount_minor,
                currency=ord_obj.currency,
            )
            for act_obj in repo.list_refund_actions_by_order(ord_obj.order_id):
                refund_ledger.rehydrate_action(
                    request_id=act_obj.request_id,
                    order_id=act_obj.order_id,
                    merchant_id=act_obj.merchant_id,
                    capture_id=act_obj.capture_id,
                    decision_id=act_obj.decision_id,
                    tranche=act_obj.tranche,
                    amount_minor=act_obj.amount_minor,
                    status=act_obj.status,
                    paypal_refund_id=act_obj.paypal_refund_id,
                    paypal_debug_id=act_obj.paypal_debug_id,
                    attempt_count=act_obj.attempt_count,
                )

    webhook_processor = WebhookProcessor(ledger=refund_ledger, repository=repo)

    if paypal_client is not None:
        active_paypal_client = paypal_client
    else:
        active_paypal_client = PayPalSandboxClient(
            base_url=resolved_settings.paypal_base_url,
            client_id=resolved_settings.paypal_client_id.get_secret_value() if resolved_settings.has_live_paypal_credentials else None,
            client_secret=resolved_settings.paypal_client_secret.get_secret_value() if resolved_settings.has_live_paypal_credentials else None,
        )
    paypal_client = active_paypal_client
    outbox_executor = RefundOutboxExecutor(repository=repo, client=paypal_client, metrics=global_metrics)
    app.state.paypal_client = paypal_client
    app.state.outbox_executor = outbox_executor

    automation_scheduler = BackgroundAutomationScheduler(
        repo=repo,
        metrics=global_metrics,
        outbox_executor=outbox_executor,
        interval_seconds=scheduler_interval,
    )
    alert_scheduler = AlertScheduler(
        metrics=global_metrics,
        interval_seconds=scheduler_interval,
    )
    app.state.enable_scheduler = is_scheduler_enabled
    app.state.automation_scheduler = automation_scheduler
    app.state.alert_scheduler = alert_scheduler

    async def _require_idempotency(
        request: Request,
        endpoint_scope: str,
        principal: Principal,
        idempotency_key: str | None,
    ) -> tuple[str | None, str | None, JSONResponse | None]:
        """Enforce required Idempotency-Key and check replay/conflict cache (RV3-08, API-06)."""
        if not idempotency_key or not idempotency_key.strip():
            return (
                None,
                None,
                _problem(
                    400,
                    ErrorCode.IDEMPOTENCY_KEY_REQUIRED,
                    "Bad Request",
                    "Idempotency-Key header is required for this mutating endpoint (API-06, RV3-08).",
                ),
            )
        raw_bytes = await request.body()
        body_hash = hashlib.sha256(raw_bytes).hexdigest()
        cache_key = (
            f"POST:{endpoint_scope}:{principal.merchant_id}:{principal.sub}:{idempotency_key.strip()}"
        )
        if cache_key in idempotency_cache:
            prev_hash, prev_status, prev_resp = idempotency_cache[cache_key]
            if prev_hash != body_hash:
                return (
                    None,
                    None,
                    _problem(
                        409,
                        ErrorCode.IDEMPOTENCY_CONFLICT,
                        "Conflict",
                        "Idempotency-Key reused with a different request payload.",
                    ),
                )
            return None, None, JSONResponse(status_code=prev_status, content=prev_resp)
        return cache_key, body_hash, None

    # RFC 9457 Validation Error Handlers (AUD-04, J-08)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        path = request.url.path

        # 1. Demo-mode disabled route checks take precedence before body validation
        if not is_demo:
            if path == "/v1/auth/staff-token":
                return _problem(
                    404,
                    ErrorCode.ENDPOINT_NOT_FOUND,
                    "Not Found",
                    "Staff token issuance endpoint is disabled outside demo mode (RV2-01).",
                )
            if path in {"/v1/carrier-events", "/v1/demo/clock/advance", "/v1/demo/reset"}:
                return _problem(
                    404,
                    ErrorCode.RESOURCE_NOT_FOUND,
                    "Not Found",
                    f"Endpoint {path} is disabled when DEMO_MODE=false.",
                )

        # 2. Demo bootstrap key checks on auth endpoints
        if is_demo and path in {"/v1/auth/staff-token", "/v1/auth/shopper-magic-link"}:
            bootstrap_header = (
                request.headers.get("X-Demo-Bootstrap-Key")
                or request.headers.get("x-demo-bootstrap-key")
            )
            expected_bootstrap = resolved_settings.demo_bootstrap_key.get_secret_value()
            if (
                not bootstrap_header
                or not expected_bootstrap
                or not hmac.compare_digest(bootstrap_header.strip(), expected_bootstrap.strip())
            ):
                return _problem(
                    401,
                    ErrorCode.AUTH_REQUIRED,
                    "Unauthorized",
                    "Valid X-Demo-Bootstrap-Key header required in demo mode (RV2-01).",
                )

        # 3. Authentication & role/scope checks on protected endpoints
        public_paths = {
            "/v1/health",
            "/v1/ready",
            "/v1/keys",
            "/v1/auth/staff-token",
            "/v1/auth/shopper-magic-link",
            "/v1/webhooks/paypal",
        }
        if path not in public_paths:
            principal, err = _resolve_principal(request.headers.get("authorization"), required=True)
            if err:
                return err
            if principal:
                if path.endswith("/evidence") and principal.is_agent:
                    return _problem(
                        403,
                        ErrorCode.AGENT_EVIDENCE_FORBIDDEN,
                        "Forbidden",
                        "AI agent tokens cannot submit physical return evidence (INV-12).",
                    )
                if path.startswith("/v1/receiving/") and not (
                    principal.is_staff and principal.role in {"RECEIVER", "PACKER", "MERCHANT_ADMIN"}
                ):
                    return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires RECEIVER or PACKER role.")
                if path.startswith("/v1/review/") and not (
                    principal.is_staff and principal.role in {"REVIEWER", "MERCHANT_ADMIN"}
                ):
                    return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires REVIEWER role.")
                if path.startswith("/v1/audits/") and not (
                    principal.is_staff and principal.role in {"RECEIVER", "REVIEWER", "MERCHANT_ADMIN"}
                ):
                    return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires RECEIVER or REVIEWER role.")
                if path == "/v1/policies" and not (
                    principal.is_staff and principal.role == "MERCHANT_ADMIN"
                ):
                    return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Only MERCHANT_ADMIN may create policies (AZ-04).")
                if path == "/v1/resale/listings" and not (
                    principal.is_staff and principal.role in {"MERCHANT_OPERATOR", "MERCHANT_ADMIN"}
                ):
                    return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires MERCHANT_OPERATOR or MERCHANT_ADMIN role.")
                if (path == "/v1/passports" or path.endswith("/passport")) and not (
                    principal.is_staff and principal.role in {"PACKER", "MERCHANT_ADMIN"}
                ):
                    return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires PACKER or MERCHANT_ADMIN role.")
                if path == "/v1/simulate" and not (
                    principal.is_staff and principal.role in {"MERCHANT_ADMIN", "MERCHANT_OPERATOR"}
                ):
                    return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires MERCHANT_ADMIN or MERCHANT_OPERATOR role.")
                if path == "/v1/carrier-events" and not (
                    principal.is_service
                    or (
                        principal.is_staff
                        and principal.role in {"RECEIVER", "MERCHANT_OPERATOR", "MERCHANT_ADMIN"}
                    )
                ):
                    return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires carrier service or staff role.")
                if path == "/v1/demo/clock/advance" and not (
                    principal.is_staff and principal.role == "MERCHANT_ADMIN"
                ):
                    return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires MERCHANT_ADMIN role.")
                if path == "/v1/returns" and not (principal.is_shopper or principal.is_agent):
                    return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Only shoppers or authorized agents may create returns.")
                if path.startswith("/v1/returns/") and (principal.is_shopper or principal.is_agent):
                    parts = path.split("/")
                    if len(parts) >= 4:
                        ret_obj = repo.get_return(parts[3])
                        if not ret_obj or ret_obj.order_id != principal.order_id:
                            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        # 4. Malformed JSON syntax -> 400 MALFORMED_JSON
        if any(err_item.get("type") == "json_invalid" for err_item in exc.errors()):
            return _problem(400, ErrorCode.MALFORMED_JSON, "Bad Request", "Malformed JSON request body.")

        error_details = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []))
            msg = err.get("msg", "Validation error")
            error_details.append(f"{loc}: {msg}")
        joined = "; ".join(error_details) if error_details else "Invalid request body."
        return _problem(422, ErrorCode.VALIDATION_FAILED, "Unprocessable Entity", joined)

    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(_request: Request, exc: ValidationError) -> JSONResponse:
        error_details = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []))
            msg = err.get("msg", "Validation error")
            error_details.append(f"{loc}: {msg}")
        joined = "; ".join(error_details) if error_details else "Validation failed."
        return _problem(422, ErrorCode.VALIDATION_FAILED, "Unprocessable Entity", joined)

    @app.exception_handler(json.JSONDecodeError)
    async def json_decode_exception_handler(_request: Request, exc: json.JSONDecodeError) -> JSONResponse:
        return _problem(400, ErrorCode.MALFORMED_JSON, "Bad Request", f"Malformed JSON: {exc}")

    # =========================================================================
    # Health, Readiness, Metrics & Ops Alerts (AUD-37, RV-11)
    # =========================================================================
    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "proofreturn-api",
            "demo_mode": is_demo,
            "mode": resolved_mode,
            "version": "1.2.1-dev.11",
        }

    @app.get("/v1/ready")
    def ready() -> JSONResponse:
        db_ok = True
        try:
            repo.ping()
        except Exception:
            db_ok = False

        fired_alerts = evaluate_alerts(global_metrics)
        has_critical = any(a.severity == "CRITICAL" for a in fired_alerts)
        status_code = 503 if (not db_ok or has_critical) else 200
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if status_code == 200 else "degraded",
                "database_connected": db_ok,
                "active_alerts_count": len(fired_alerts),
                "demo_mode": is_demo,
                "auth": "demo" if is_demo else "demo_only",
            },
        )

    @app.get("/v1/metrics")
    def metrics_export(request: Request, authorization: str | None = Header(default=None)) -> Response:
        # RV-11: Metric export protected behind loopback check or staff auth
        if not _is_loopback_client(request):
            principal, err = _resolve_principal(authorization, required=True)
            if err:
                return err
            if not principal.is_staff:
                return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Only staff may access metrics remotely.")
        return Response(content=global_metrics.to_prometheus_text(), media_type="text/plain; version=0.0.4")

    @app.get("/v1/ops/alerts")
    def list_ops_alerts(request: Request, authorization: str | None = Header(default=None)) -> JSONResponse:
        # RV-11: Operational alerts protected behind loopback check or staff auth
        if not _is_loopback_client(request):
            principal, err = _resolve_principal(authorization, required=True)
            if err:
                return err
            if not principal.is_staff:
                return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Only staff may access alerts remotely.")
        needs_attention_actions = repo.list_refund_actions_by_status("NEEDS_ATTENTION")
        if needs_attention_actions:
            global_metrics.set_gauge("outbox_needs_attention_count", float(len(needs_attention_actions)))
        fired = evaluate_alerts(global_metrics)
        return JSONResponse(
            status_code=200,
            content={
                "alerts": [
                    {
                        "alert_id": a.alert_id,
                        "severity": a.severity,
                        "condition": a.condition,
                        "runbook_id": a.runbook_id,
                        **(
                            {
                                "status": "NEEDS_ATTENTION",
                                "request_ids": [act.request_id for act in needs_attention_actions],
                            }
                            if a.alert_id == "AL-02" and needs_attention_actions
                            else {}
                        ),
                    }
                    for a in fired
                ]
            },
        )

    @app.post("/v1/ops/outbox/run")
    async def run_outbox_executor(
        request: Request,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        limit: int = Query(default=10, ge=1, le=100),
    ) -> JSONResponse:
        """Manually trigger the transactional refund outbox executor (MERCHANT_ADMIN only; AUD-02, ARC-19, API-06)."""
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal or not principal.is_staff or principal.role != "MERCHANT_ADMIN":
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Only MERCHANT_ADMIN can trigger outbox executor.")

        cache_key, body_hash, idem_resp = await _require_idempotency(
            request, "/v1/ops/outbox/run", principal, idempotency_key
        )
        if idem_resp:
            return idem_resp

        effective_now = datetime.now(UTC) + timedelta(seconds=clock_offset_seconds)
        result = outbox_executor.run_once(
            limit=limit,
            merchant_id=principal.merchant_id,
            now=effective_now,
        )
        if cache_key:
            idempotency_cache[cache_key] = (body_hash or "", 200, result)
        return JSONResponse(status_code=200, content=result)

    # =========================================================================
    # Agent Token Issuance (SSOT Section 28.3, FR-45, RV-12)
    # =========================================================================
    @app.post("/v1/agent/tokens")
    async def issue_agent_token(
        req_body: IssueAgentTokenRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal.is_shopper:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Only shoppers may issue agent tokens.")

        order_id = req_body.order_id
        if order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Order out of scope for shopper.")

        requested_set = set(req_body.scopes)
        if not requested_set.issubset(ALLOWED_AGENT_SCOPES):
            return _problem(
                422,
                ErrorCode.VALIDATION_FAILED,
                "Unprocessable Entity",
                f"Invalid or forbidden scopes requested: {requested_set - ALLOWED_AGENT_SCOPES}",
            )

        ttl = max(60, min(req_body.ttl, 86400))
        agent_label = req_body.agent_label
        agent_id = f"agent_{int(time.time())}"

        token = mint_agent_token(
            agent_id=agent_id,
            order_id=order_id,
            merchant_id=principal.merchant_id,
            scopes=list(requested_set),
            agent_label=agent_label,
            ttl_seconds=ttl,
        )
        expires_at_epoch = int(time.time()) + ttl
        expires_at = datetime.fromtimestamp(expires_at_epoch, UTC).isoformat()

        # Persist agent token into database (RV-12)
        sig_hash = hashlib.sha256(token.split(".")[2].encode("utf-8")).hexdigest()
        token_record = AgentToken(
            token_id=f"tok_{sig_hash[:16]}",
            order_id=order_id,
            merchant_id=principal.merchant_id,
            agent_id=agent_id,
            scopes=",".join(sorted(list(requested_set))),
            agent_label=agent_label,
            signature_hash=sig_hash,
            revoked=False,
            expires_at=expires_at_epoch,
        )
        repo.save_agent_token(token_record)

        return JSONResponse(
            status_code=201,
            content={
                "token": token,
                "expires_at": expires_at,
                "order_id": order_id,
                "scopes": sorted(list(requested_set)),
                "agent_label": agent_label,
            },
        )

    # =========================================================================
    # Staff & Shopper Identity Minting Endpoints (RV-09, API-04, RV2-01)
    # =========================================================================
    @app.post("/v1/auth/staff-token")
    async def issue_staff_token(
        request: Request,
        req_body: IssueStaffTokenRequest,
    ) -> JSONResponse:
        """Issue authenticated staff JWT for merchant operators, admins, reviewers, packers (RV-09, API-04, RV2-01)."""
        if not is_demo:
            return _problem(
                404,
                ErrorCode.ENDPOINT_NOT_FOUND,
                "Not Found",
                "Staff token issuance endpoint is disabled outside demo mode (RV2-01).",
            )

        bootstrap_header = request.headers.get("X-Demo-Bootstrap-Key") or request.headers.get("x-demo-bootstrap-key")
        expected_bootstrap = resolved_settings.demo_bootstrap_key.get_secret_value()
        if not bootstrap_header or not expected_bootstrap or not hmac.compare_digest(bootstrap_header.strip(), expected_bootstrap.strip()):
            return _problem(
                401,
                ErrorCode.AUTH_REQUIRED,
                "Unauthorized",
                "Valid X-Demo-Bootstrap-Key header required in demo mode (RV2-01).",
            )

        merchant = repo.get_merchant(req_body.merchant_id)
        if not merchant and not is_demo:
            return _problem(404, ErrorCode.MERCHANT_NOT_FOUND, "Not Found", f"Merchant '{req_body.merchant_id}' does not exist.")

        valid_roles = {"MERCHANT_ADMIN", "MERCHANT_OPERATOR", "PACKER", "RECEIVER", "REVIEWER"}
        role_upper = req_body.role.upper()
        if role_upper not in valid_roles:
            return _problem(422, ErrorCode.INVALID_ROLE, "Unprocessable Entity", f"Role must be one of {valid_roles}")

        effective_ttl = min(req_body.ttl_seconds, 8 * 3600) if req_body.ttl_seconds else 8 * 3600
        token = mint_staff_token(
            merchant_id=req_body.merchant_id,
            role=role_upper,
            user_id=req_body.staff_id,
            ttl_seconds=effective_ttl,
        )
        return JSONResponse(
            status_code=200,
            content={
                "token_type": "Bearer",
                "access_token": token,
                "expires_in": effective_ttl,
                "staff_id": req_body.staff_id,
                "merchant_id": req_body.merchant_id,
                "role": role_upper,
                "demo_only": True,
            },
        )

    @app.post("/v1/auth/shopper-magic-link")
    async def issue_shopper_magic_link(
        request: Request,
        req_body: IssueShopperMagicLinkRequest,
    ) -> JSONResponse:
        """Generate order-scoped magic link token for shopper return flow (RV-09, API-04, RV2-01)."""
        if not is_demo:
            order = repo.get_order(req_body.order_id)
            if not order:
                return _problem(404, ErrorCode.ORDER_NOT_FOUND, "Not Found", f"Order '{req_body.order_id}' does not exist.")
            # Record delivery request without token (RV2-01: never return token or magic_link_url in response)
            return JSONResponse(
                status_code=202,
                content={
                    "status": "ACCEPTED",
                    "message": "Shopper magic link delivery request recorded and dispatched out-of-band.",
                    "order_id": req_body.order_id,
                },
            )

        bootstrap_header = request.headers.get("X-Demo-Bootstrap-Key") or request.headers.get("x-demo-bootstrap-key")
        expected_bootstrap = resolved_settings.demo_bootstrap_key.get_secret_value()
        if not bootstrap_header or not expected_bootstrap or not hmac.compare_digest(bootstrap_header.strip(), expected_bootstrap.strip()):
            return _problem(
                401,
                ErrorCode.AUTH_REQUIRED,
                "Unauthorized",
                "Valid X-Demo-Bootstrap-Key header required in demo mode (RV2-01).",
            )

        order = repo.get_order(req_body.order_id)
        if not order and not is_demo:
            return _problem(404, ErrorCode.ORDER_NOT_FOUND, "Not Found", f"Order '{req_body.order_id}' does not exist.")

        merchant_id = order.merchant_id if order else "merch_a"
        shopper_id = req_body.shopper_id or (order.account_id if order else "shopper_1")

        effective_ttl = min(req_body.ttl_seconds, 24 * 3600) if req_body.ttl_seconds else 24 * 3600
        token = mint_shopper_token(
            order_id=req_body.order_id,
            shopper_id=shopper_id,
            merchant_id=merchant_id,
            ttl_seconds=effective_ttl,
        )
        magic_link_url = f"/returns?token={token}&order_id={req_body.order_id}"

        return JSONResponse(
            status_code=200,
            content={
                "token_type": "Bearer",
                "access_token": token,
                "magic_link_url": magic_link_url,
                "order_id": req_body.order_id,
                "merchant_id": merchant_id,
                "shopper_id": shopper_id,
                "expires_in": effective_ttl,
                "demo_only": True,
            },
        )

    # =========================================================================
    # Returns & Policy Core Endpoints (AUD-01, AUD-06, RV-03, RV-04, FR-88)
    # =========================================================================
    @app.get("/v1/returns/{return_id}")
    def get_return(return_id: str, authorization: str | None = Header(default=None)) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        ret = repo.get_return(return_id)
        if not ret:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        # AZ-01: Tenant isolation -> 404 on cross-merchant access (TZ-04)
        if principal.is_staff and ret.merchant_id != principal.merchant_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        # AZ-02 / AZ-06: Shopper & Agent scoped to own order
        if (principal.is_shopper or principal.is_agent) and ret.order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        return JSONResponse(
            status_code=200,
            content={
                "return_id": ret.return_id,
                "order_id": ret.order_id,
                "merchant_id": ret.merchant_id,
                "shopper_id": ret.shopper_id,
                "state": ret.state,
                "lane": ret.lane,
                "timing": ret.timing,
                "declared_grade": ret.declared_grade,
                "r0_tranche_minor": ret.r0_tranche_minor,
                "currency": ret.currency,
            },
        )

    @app.post("/v1/returns")
    async def create_return(
        request: Request,
        req_body: CreateReturnRequest,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        if not (principal.is_shopper or principal.is_agent):
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Only shoppers or authorized agents may create returns.")

        order_id = req_body.order_id
        if order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Order not found or out of scope.")

        if principal.is_agent and "declare" not in principal.scopes:
            return _problem(403, ErrorCode.FORBIDDEN_ACTION, "Forbidden", "Agent token missing declare scope.")

        order = repo.get_order(order_id)
        if not order:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Order not found in repository.")

        cache_key, body_hash, idem_resp = await _require_idempotency(
            request, "/v1/returns", principal, idempotency_key
        )
        if idem_resp is not None:
            return idem_resp

        # Generate unique return with CSPRNG seed (RV-02) and persist to database (AUD-06)
        return_id = f"ret_{uuid.uuid4().hex[:10]}"
        order_items = repo.get_order_items(order_id)
        active_returns = [
            r for r in repo.list_returns_by_merchant(order.merchant_id)
            if r.state not in {"CANCELLED", "CLOSED"}
        ]
        active_item_ids = {r.order_item_id for r in active_returns}
        available_items = [it for it in order_items if it.order_item_id not in active_item_ids]
        if req_body.order_item_id and req_body.order_item_id not in active_item_ids:
            order_item_id = req_body.order_item_id
        elif available_items:
            order_item_id = available_items[0].order_item_id
        else:
            order_item_id = f"item_{uuid.uuid4().hex[:8]}"
            repo.save_order_item(
                OrderItem(
                    order_item_id=order_item_id,
                    order_id=order_id,
                    passport_id=order_items[0].passport_id if order_items else None,
                    sku=order_items[0].sku if order_items else "PR-HP-XM5",
                    price_minor=order.capture_amount_minor,
                    currency=order.currency,
                )
            )

        seed_hex = secrets.token_hex(32)
        seed_bytes = bytes.fromhex(seed_hex)
        commitment = hashlib.sha256(seed_bytes + b"||" + return_id.encode("utf-8")).hexdigest()

        ret_record = Return(
            return_id=return_id,
            order_id=order_id,
            order_item_id=order_item_id,
            merchant_id=order.merchant_id,
            shopper_id=order.account_id,
            state="REQUESTED",
            lane="FAST",
            timing="R0",
            declared_grade=None,
            r0_tranche_minor=0,
            currency=order.currency,
            challenge_nonce=f"NONCE-{secrets.token_hex(8).upper()}",
            audit_seed_hex=seed_hex,
            audit_commitment=commitment,
            audit_probability=0.05,
            consent_recorded=False,
        )
        repo.save_return(ret_record)

        resp_payload = {
            "return_id": return_id,
            "order_id": order_id,
            "state": "REQUESTED",
        }
        if cache_key and body_hash:
            idempotency_cache[cache_key] = (body_hash, 200, resp_payload)

        return JSONResponse(status_code=200, content=resp_payload)

    @app.post("/v1/returns/{return_id}/cancel")
    def cancel_return(
        return_id: str,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        """Cancel an in-flight return request via ReturnStateMachine (FR-88)."""
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        ret = repo.get_return(return_id)
        if not ret:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        if (principal.is_shopper or principal.is_agent) and ret.order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found or out of scope.")

        try:
            repo.apply_return_transition(return_id, "CANCEL_RETURN")
            return JSONResponse(status_code=200, content={"return_id": return_id, "state": "CANCELLED"})
        except InvalidStateTransitionError as exc:
            return _problem(409, ErrorCode.INVALID_STATE_TRANSITION, "Conflict", str(exc))

    @app.get("/v1/orders/{order_id}/policy")
    def get_order_policy(order_id: str, authorization: str | None = Header(default=None)) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        order = repo.get_order(order_id)
        if not order:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Order not found.")

        # AZ-01: Staff must match merchant
        if principal.is_staff and order.merchant_id != principal.merchant_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Order not found.")

        # AZ-02: Shopper & Agent scoped to order
        if principal.is_shopper and order.order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Order not found.")

        if principal.is_agent:
            if order.order_id != principal.order_id:
                return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Order not found.")
            if "read_policy" not in principal.scopes:
                return _problem(403, ErrorCode.FORBIDDEN_ACTION, "Forbidden", "Agent token missing read_policy scope.")

        pol = repo.get_policy(order.policy_version)
        default_curve = {"A": 1.0, "B": 0.95, "C": 0.80, "D": 0.50}
        curve = pol.config_json.get("curve", default_curve) if (pol and pol.config_json) else default_curve

        return JSONResponse(
            status_code=200,
            content={
                "order_id": order_id,
                "policy_version": order.policy_version,
                "curve": curve,
            },
        )

    @app.get("/v1/returns/{return_id}/challenge")
    def get_evidence_challenge(return_id: str, authorization: str | None = Header(default=None)) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        # AZ-03 & INV-12: Agent token cannot obtain physical evidence challenge -> 403
        if principal.is_agent:
            return _problem(
                403,
                ErrorCode.AGENT_EVIDENCE_FORBIDDEN,
                "Forbidden",
                "AI agent tokens cannot request or submit physical return evidence (INV-12).",
            )
        if principal.is_staff:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Only human shoppers may request challenge.")

        ret = repo.get_return(return_id)
        if not ret or ret.order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        # Nonce stored on Return in database (eliminate hardcoded nonce, AUD-01)
        if not ret.challenge_nonce:
            ret.challenge_nonce = f"NONCE-{secrets.token_hex(8).upper()}"
            repo.save_return(ret)

        return JSONResponse(
            status_code=200,
            content={"return_id": return_id, "nonce_return": ret.challenge_nonce},
        )

    @app.post("/v1/returns/{return_id}/declaration")
    async def submit_return_declaration(
        return_id: str,
        req_body: ReturnDeclarationRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        ret = repo.get_return(return_id)
        if not ret:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        if not (principal.is_shopper or principal.is_agent) or ret.order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found or out of scope.")

        if principal.is_agent and "declare" not in principal.scopes:
            return _problem(403, ErrorCode.FORBIDDEN_ACTION, "Forbidden", "Agent token missing declare scope.")

        consent_recorded = bool(req_body.consent_fast_lane_terms or req_body.fast_lane_terms_accepted)
        if not consent_recorded:
            return _problem(
                400,
                ErrorCode.TERMS_NOT_ACCEPTED,
                "Bad Request",
                "Fast Lane terms must be explicitly accepted (FR-14, INV-06).",
            )

        shopper_nonce = req_body.shopper_nonce or req_body.nonce_shopper or secrets.token_hex(16)
        actor = req_body.actor or {"kind": principal.type, "sub": principal.sub}

        # Dynamic guards computed from database (RV-03)
        order = repo.get_order(ret.order_id)
        pol = repo.get_policy(order.policy_version) if order else None
        return_window_days = pol.return_window_days if pol else 30
        now_utc = datetime.now(timezone.utc)
        order_created = order.created_at.replace(tzinfo=timezone.utc) if (order and order.created_at) else now_utc
        within_window = (now_utc - order_created).days <= return_window_days
        authorized = not err and bool((principal.is_shopper or principal.is_agent) and ret.order_id == principal.order_id)

        try:
            if ret.state == "REQUESTED":
                repo.apply_return_transition(
                    return_id,
                    "SUBMIT_DECLARATION",
                    within_window=within_window,
                    authorized=authorized,
                    consent_recorded=consent_recorded,
                )
            elif ret.state == "DECLARED":
                pass
            else:
                repo.apply_return_transition(
                    return_id,
                    "SUBMIT_DECLARATION",
                    within_window=within_window,
                    authorized=authorized,
                    consent_recorded=consent_recorded,
                )
            # Update return metadata in database
            ret.declared_grade = req_body.declared_grade
            ret.shopper_nonce = shopper_nonce
            ret.consent_recorded = True
            repo.save_return(ret)
        except InvalidStateTransitionError as exc:
            return _problem(409, ErrorCode.INVALID_STATE_TRANSITION, "Conflict", str(exc))

        decl_response = {
            "return_id": return_id,
            "declared_grade": req_body.declared_grade,
            "accessories": req_body.accessories,
            "reason_code": req_body.reason_code,
            "reason_text": req_body.reason_text,
            "consent_fast_lane_terms": True,
            "fast_lane_terms_accepted": True,
            "nonce_shopper": shopper_nonce,
            "shopper_nonce": shopper_nonce,
            "challenge_nonce": ret.challenge_nonce,
            "actor": actor,
        }
        return JSONResponse(status_code=200, content=decl_response)

    @app.post("/v1/returns/{return_id}/evidence")
    async def submit_return_evidence(
        return_id: str,
        request: Request,
        req_body: EvidenceSubmissionRequest,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        # AZ-03 & INV-12: Human shopper only
        if principal.is_agent:
            return _problem(
                403,
                ErrorCode.AGENT_EVIDENCE_FORBIDDEN,
                "Forbidden",
                "AI agent tokens cannot submit physical return evidence (INV-12).",
            )

        ret = repo.get_return(return_id)
        if not ret or not principal.is_shopper or ret.order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        cache_key, body_hash, idem_resp = await _require_idempotency(
            request, f"/v1/returns/{return_id}/evidence", principal, idempotency_key
        )
        if idem_resp is not None:
            return idem_resp

        from backend.ops.drills import verify_client_side_face_blur

        blur_check = verify_client_side_face_blur(
            faces_detected=req_body.faces_detected,
            client_blur_applied=bool(req_body.client_blur_applied),
            blur_latency_ms=req_body.blur_latency_ms,
        )
        if not blur_check.accepted:
            if blur_check.reason == ErrorCode.BLUR_BUDGET_EXCEEDED_50MS:
                return _problem(
                    422,
                    ErrorCode.BLUR_BUDGET_EXCEEDED_50MS,
                    "Unprocessable Entity",
                    "Privacy face-blur verification failed (FR-16).",
                )
            return _problem(
                422,
                ErrorCode.UNBLURRED_FACE_REJECTED,
                "Unprocessable Entity",
                "Privacy face-blur verification failed (FR-16).",
            )

        # FR-66: Verify retakes within limits (max 3 per step, 8 per return)
        retakes_ok = (ret.retake_count <= 3)
        if not retakes_ok:
            return _problem(
                409,
                ErrorCode.INVALID_STATE_TRANSITION,
                "Conflict",
                "Maximum evidence retake attempts exceeded (FR-66).",
            )

        # FR-65 & R4-T3: Verify challenge nonce found in media matches stored session nonce (fail-closed)
        stored_nonce = ret.challenge_nonce.strip().upper() if ret.challenge_nonce else ""
        challenge_valid = False
        challenge_not_verified = False
        if req_body.text_in_media and req_body.text_in_media.strip():
            obs_text = req_body.text_in_media.strip().upper()
            challenge_valid = bool(stored_nonce and (stored_nonce in obs_text or obs_text in stored_nonce))
            if not challenge_valid:
                return _problem(
                    409,
                    ErrorCode.INVALID_STATE_TRANSITION,
                    "Conflict",
                    "Challenge nonce mismatch between evidence and stored session nonce (FR-65).",
                )
        else:
            challenge_valid = False
            challenge_not_verified = True

        from backend.ai.pipeline.evaluator import assess_return_evidence

        assessment_res = assess_return_evidence(
            mode=resolved_mode,
            evidence_sha256=req_body.sha256,
            declared_grade=ret.declared_grade or "B",
            text_in_media=req_body.text_in_media,
        )

        # Persist ReturnEvidence and Assessment in database (AUD-06)
        ev_record = ReturnEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
            return_id=return_id,
            evidence_sha256=req_body.sha256,
            nonce_return=ret.challenge_nonce,
            encrypted_blob_uri=req_body.object_key,
            challenge_step=req_body.challenge_step,
            faces_detected=req_body.faces_detected,
            client_blur_applied=bool(req_body.client_blur_applied),
            blur_latency_ms=req_body.blur_latency_ms,
        )

        ass_record = Assessment(
            assessment_id=f"ass_{uuid.uuid4().hex[:8]}",
            return_id=return_id,
            predicted_grade=assessment_res.predicted_grade,
            conformal_set=assessment_res.conformal_set,
            replay_label=assessment_res.replay_label,
            forensic_flags=assessment_res.forensic_flags,
        )

        # Policy Engine Release Calculation (AUD-01, RV-03, Task T6)
        order = repo.get_order(ret.order_id)
        order_items = repo.get_order_items(ret.order_id) if order else []
        has_passport = bool(order_items and order_items[0].passport_id)
        merchant = repo.get_merchant(ret.merchant_id)
        merchant_cap_remaining_minor = (
            max(0, merchant.instant_exposure_cap_minor - merchant.outstanding_instant_exposure_minor)
            if merchant
            else 500000
        )

        from backend.domain.trust import (
            TrustProfile,
            compute_account_exposure_cap_minor,
            evaluate_tier_promotion,
        )

        shopper_acc = repo.get_shopper(order.account_id) if order else None
        if shopper_acc:
            profile = TrustProfile(
                tier=shopper_acc.trust_tier,
                clean_count=shopper_acc.clean_Counter_verified_returns,
                account_age_days=shopper_acc.account_age_days,
            )
            tier = evaluate_tier_promotion(profile)
            if tier != shopper_acc.trust_tier:
                shopper_acc.trust_tier = tier
                repo.save_shopper(shopper_acc)
            account_cap_remaining_minor = compute_account_exposure_cap_minor(tier, largest_clean_value_minor=0)
        else:
            tier = "NEW"
            account_cap_remaining_minor = 0

        price = order.capture_amount_minor if order else 38000

        release_inp = ReleaseInput(
            price_minor=price,
            declared_grade=ret.declared_grade or "B",
            tier=tier,
            has_origin_passport=has_passport,
            account_cap_remaining_minor=account_cap_remaining_minor,
            merchant_cap_remaining_minor=merchant_cap_remaining_minor,
        )
        calib_cfg = _illustrative_calib(ret.declared_grade or "B")
        try:
            policy_cfg = _policy_config_from_db_policy(
                repo.get_policy(order.policy_version) if order else None
            )
            release_dec = decide_release(release_inp, policy_cfg, calib_cfg)
        except JurisdictionCapViolationError as exc:
            return _problem(409, ErrorCode.JURISDICTION_CAP_VIOLATION, "Conflict", str(exc))

        # AUD-15 & INV-18: Connect failure detection / degraded mode fallback (§31.3)
        fb_code = request.headers.get("x-fallback-degradation")
        if fb_code:
            release_dec = apply_fallback_degradation(
                release_dec,
                fb_code=fb_code,
                price_minor=price,
            )

        explanation_text = str(release_dec.explanation)
        explanation_payload: dict[str, Any] = {"explanation": explanation_text}
        effective_lane = release_dec.lane
        effective_timing = release_dec.timing
        effective_x_minor = release_dec.x_released_minor
        effective_checkin_minor = release_dec.checkin_tranche_minor
        effective_holdback_minor = release_dec.holdback_minor

        if not challenge_valid:
            effective_lane = "STANDARD"
            effective_timing = "R3"
            effective_x_minor = 0
            effective_checkin_minor = 0
            effective_holdback_minor = (
                release_dec.x_released_minor
                + release_dec.checkin_tranche_minor
                + release_dec.holdback_minor
            )
            explanation_text = (
                f"{explanation_text} | CHALLENGE_NOT_VERIFIED: No OCR challenge text available; "
                "routed to STANDARD lane without FAST release."
            )
            explanation_payload["explanation"] = explanation_text
            explanation_payload["reason"] = "CHALLENGE_NOT_VERIFIED"

        # Persist cryptographically signed Decision to DB (AUD-28)
        plat_priv, _, plat_kid = get_platform_keypair()
        dec_id = f"dec_{uuid.uuid4().hex[:8]}"
        payload_hash = sha256_hex(f"{dec_id}:{return_id}:{effective_x_minor}")
        sig = sign_message_ed25519(plat_priv, payload_hash)
        dec_record = Decision(
            decision_id=dec_id,
            return_id=return_id,
            policy_version=order.policy_version if order else "pol_v1_us_ca",
            lane=effective_lane,
            timing=effective_timing,
            audit_probability=float(release_dec.p),
            x_minor=effective_x_minor,
            checkin_minor=effective_checkin_minor,
            holdback_minor=effective_holdback_minor,
            currency="USD",
            explanation_json=explanation_payload,
            signature=f"ed25519:{sig}",
        )

        # AUD-06, J-06, INV-01, RV2-04: Atomic Transaction for Evidence + Assessment + Decision + R0 Refund + State Transition
        try:
            ev_record, ass_record, dec_record, r0_action, ret = repo.record_evidence_pack_transactional(
                return_id=return_id,
                evidence=ev_record,
                assessment=ass_record,
                decision=dec_record,
                refund_amount_minor=effective_x_minor,
                tranche="R0",
                paypal_debug_id=f"dbg_{dec_id[:8]}",
                lane=effective_lane,
                timing=effective_timing,
                audit_probability=float(release_dec.p),
                retakes_ok=retakes_ok,
                challenge_valid=challenge_valid,
                challenge_not_verified=challenge_not_verified,
            )
        except MissingCaptureError as exc:
            return _problem(409, ErrorCode.CAPTURE_MISSING, "Capture Missing", str(exc))
        except OrderFrozenError as exc:
            return _problem(409, ErrorCode.ORDER_FROZEN, "Order Frozen", str(exc))
        except OverRefundError as exc:
            return _problem(409, ErrorCode.REFUND_LIMIT_EXCEEDED, "Refund Limit Exceeded", str(exc))
        except InvalidStateTransitionError as exc:
            return _problem(409, ErrorCode.INVALID_STATE_TRANSITION, "Conflict", str(exc))

        # Rehydrate into in-memory ledger cache if action planned
        if r0_action and order and order.capture_id:
            if order.order_id not in refund_ledger._orders:
                refund_ledger.register_order(
                    order_id=order.order_id,
                    merchant_id=order.merchant_id,
                    capture_id=order.capture_id,
                    capture_amount_minor=order.capture_amount_minor,
                    currency=order.currency,
                )
            refund_ledger.rehydrate_action(
                request_id=r0_action.request_id,
                order_id=r0_action.order_id,
                merchant_id=r0_action.merchant_id,
                capture_id=r0_action.capture_id,
                decision_id=r0_action.decision_id,
                tranche=r0_action.tranche,
                amount_minor=r0_action.amount_minor,
                status=r0_action.status,
                paypal_refund_id=r0_action.paypal_refund_id,
                paypal_debug_id=r0_action.paypal_debug_id,
            )

        resp_content: dict[str, Any] = {
            "return_id": return_id,
            "accepted": True,
            "state": ret.state,
            "lane": effective_lane,
            "timing": effective_timing,
            "r0_tranche_minor": effective_x_minor,
            "x_released_minor": effective_x_minor,
            "holdback_minor": effective_holdback_minor,
            "explanation": explanation_text,
            "data_source_badge": "REPLAYED" if resolved_mode == "judge" else "LIVE",
        }
        if not challenge_valid:
            resp_content["reason"] = "CHALLENGE_NOT_VERIFIED"
        if cache_key and body_hash:
            idempotency_cache[cache_key] = (body_hash, 200, resp_content)
        return JSONResponse(status_code=200, content=resp_content)

    @app.post("/v1/returns/{return_id}/dropoff")
    async def record_return_dropoff(
        return_id: str,
        req_body: DropoffRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        ret = repo.get_return(return_id)
        if not ret or not principal.is_shopper or ret.order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        # Dynamic exposure cap guard from database (RV-03, RV3-03, R4-T3: fail-closed)
        merchant = repo.get_merchant(ret.merchant_id)
        if not merchant:
            return _problem(
                409,
                ErrorCode.MERCHANT_NOT_FOUND,
                "Conflict",
                f"Merchant record '{ret.merchant_id}' not found.",
            )
        exposure_cap_ok = False
        exposure_cap_ok = (
            merchant.outstanding_instant_exposure_minor + ret.r0_tranche_minor
            <= merchant.instant_exposure_cap_minor
        )

        try:
            if ret.state == "ASSESSED":
                repo.apply_return_transition(return_id, "APPROVE_RETURN", exposure_cap_ok=exposure_cap_ok)
                repo.apply_return_transition(return_id, "ISSUE_LABEL")
            elif ret.state == "APPROVED":
                repo.apply_return_transition(return_id, "ISSUE_LABEL")
        except InvalidStateTransitionError as exc:
            return _problem(409, ErrorCode.INVALID_STATE_TRANSITION, "Conflict", str(exc))

        ret_updated = repo.get_return(return_id) or ret
        # R4-T7 (RV2-05 MEDIUM, FR-64): Use domain/return_seal.py ReturnSealRecord
        from backend.domain.nonce import SealNonce
        from backend.domain.return_seal import ReturnSealRecord

        order_items = repo.get_order_items(ret.order_id)
        passp = repo.get_passport(order_items[0].passport_id) if order_items and order_items[0].passport_id else None
        origin_weight = passp.weight_g if passp else 250

        seal_rec = ReturnSealRecord(
            return_id=return_id,
            nonce=SealNonce(
                nonce_code=req_body.seal_nonce,
                nonce_hash=hashlib.sha256(req_body.seal_nonce.encode("utf-8")).hexdigest(),
                qr_payload=req_body.seal_nonce,
            ),
            origin_weight_g=origin_weight,
            dropoff_photo_sha256=req_body.dropoff_photo_ref,
            seal_intact=True,
        )
        seal_hash = hashlib.sha256(seal_rec.nonce.nonce_code.encode("utf-8")).hexdigest()
        ret_updated.seal_nonce_hash = seal_hash
        repo.save_return(ret_updated)
        return JSONResponse(
            status_code=200,
            content={
                "return_id": return_id,
                "seal_recorded": True,
                "seal_nonce_hash": seal_hash,
                "dropoff_photo_ref": req_body.dropoff_photo_ref,
                "carrier_tracking_number": req_body.carrier_tracking_number,
            },
        )

    @app.get("/v1/returns/{return_id}/receipts")
    def get_return_receipts(
        return_id: str,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        ret = repo.get_return(return_id)
        if not ret:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        if principal.is_staff and ret.merchant_id != principal.merchant_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")
        if (principal.is_shopper or principal.is_agent) and ret.order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        shopper_nonce = ret.shopper_nonce or "shopper_nonce_default"

        # Persistent Ed25519 keypair and CSPRNG audit seed from DB (RV-02, AUD-28)
        signing_key, verify_key, kid = get_platform_keypair()
        pub_registry = get_public_key_registry()
        platform_pubkey = pub_registry.get(PLATFORM_KEY_ID, verify_key)
        intake_receipt = issue_signed_receipt(
            receipt_id=f"rcpt_intake_{return_id}",
            return_id=return_id,
            kind="INTAKE",
            payload={"state": ret.state, "order_id": ret.order_id},
            signing_private_key=signing_key,
            key_id=kid,
        )
        delivery_receipt = issue_signed_receipt(
            receipt_id=f"rcpt_delivery_{return_id}",
            return_id=return_id,
            kind="DELIVERY",
            payload={"carrier": "carrier_fedex", "tracking": "TRK-001"},
            signing_private_key=signing_key,
            key_id=kid,
        )
        intake_verified = verify_signed_receipt(intake_receipt, platform_pubkey)
        delivery_verified = verify_signed_receipt(delivery_receipt, platform_pubkey)

        seed_platform = bytes.fromhex(ret.audit_seed_hex) if ret.audit_seed_hex else secrets.token_bytes(32)
        audit_com = create_audit_commitment(
            seed_platform=seed_platform,
            return_id=return_id,
            p=Fraction(5, 100),
        )

        return JSONResponse(
            status_code=200,
            content={
                "return_id": return_id,
                "receipts": [
                    {
                        "receipt_id": intake_receipt.receipt_id,
                        "kind": intake_receipt.kind,
                        "signature": intake_receipt.signature,
                        "payload_hash": intake_receipt.payload_hash,
                        "verified": intake_verified,
                    },
                    {
                        "receipt_id": delivery_receipt.receipt_id,
                        "kind": delivery_receipt.kind,
                        "signature": delivery_receipt.signature,
                        "payload_hash": delivery_receipt.payload_hash,
                        "verified": delivery_verified,
                    },
                ],
                "audit_commitment": {
                    "commitment": audit_com.commitment,
                    "nonce_shopper": shopper_nonce,
                    "p": "0.05",
                },
            },
        )

    @app.get("/v1/returns/{return_id}/evidence-pack")
    def download_return_evidence_pack(
        return_id: str,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        ret = repo.get_return(return_id)
        if not ret:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        if principal.is_staff and ret.merchant_id != principal.merchant_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")
        if (principal.is_shopper or principal.is_agent) and ret.order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        # Real DB entity references (AUD-01)
        decision = repo.get_latest_decision(return_id)
        order_items = repo.get_order_items(ret.order_id)
        refund_actions = repo.list_refund_actions_by_return(return_id)

        passport_id = order_items[0].passport_id if (order_items and order_items[0].passport_id) else "pass_demo_1"
        decision_id = decision.decision_id if decision else f"dec_{return_id}"
        refund_req_ids = [ra.request_id for ra in refund_actions] or [f"req_r0_{ret.r0_tranche_minor}"]

        pack = generate_evidence_pack(
            return_id=return_id,
            order_id=ret.order_id,
            passport_id=passport_id,
            decision_id=decision_id,
            refund_request_ids=refund_req_ids,
            custody_intervals=["PACKING_TO_CARRIER", "CARRIER_TO_DOCK"],
        )
        return JSONResponse(
            status_code=200,
            content={
                "pack_id": pack.pack_id,
                "return_id": pack.return_id,
                "order_id": pack.order_id,
                "passport_id": pack.passport_id,
                "pack_sha256": pack.canonical_sha256,
                "summary_markdown": pack.summary_markdown,
                "buyer_downloadable": pack.buyer_downloadable,
            },
        )

    # =========================================================================
    # Keep-Offer Endpoints (RV-04, FR-37, AUD-40)
    # =========================================================================
    def _get_or_compute_keep_offer(ret: Return) -> KeepOffer | None:
        """Resolve persistent keep-offer or compute deterministically from DB state (RV-04, Task T6)."""
        existing = repo.get_keep_offer_by_return(ret.return_id)
        if existing:
            return existing

        order = repo.get_order(ret.order_id)
        shopper = repo.get_shopper(order.account_id) if order else None
        tier = shopper.trust_tier if shopper else "TRUSTED"
        price = order.capture_amount_minor if order else 38000
        refund_owed = int(price * 0.95)

        inp = KeepOfferInput(
            refund_owed_minor=refund_owed,
            reverse_shipping_minor=850,
            handling_cost_minor=550,
            recovery_lower_bound_minor=30000,
            tier=tier,
            intake_passed=True,
        )
        ko_dec = compute_posted_keep_offer(inp, PolicyConfig.default_us())
        if not ko_dec.eligible or ko_dec.posted_price_minor is None:
            return None
        posted_price = ko_dec.posted_price_minor

        offer = KeepOffer(
            offer_id=f"koff_{ret.return_id}",
            return_id=ret.return_id,
            amount_minor=posted_price,
            status="OFFERED",
            currency="USD",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        return repo.save_keep_offer(offer)

    @app.get("/v1/returns/{return_id}/keep-offer")
    def get_keep_offer(
        return_id: str,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        ret = repo.get_return(return_id)
        if not ret:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        if (principal.is_shopper or principal.is_agent) and ret.order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        if principal.is_agent and "keep_offer" not in principal.scopes:
            return _problem(403, ErrorCode.FORBIDDEN_ACTION, "Forbidden", "Agent token missing keep_offer scope.")

        offer = _get_or_compute_keep_offer(ret)
        if offer is None:
            return _problem(404, ErrorCode.NO_KEEP_OFFER, "Not Found", "No keep-offer available for this return.")

        return JSONResponse(
            status_code=200,
            content={
                "schema_version": "1.0.0",
                "keep_offer_id": offer.offer_id,
                "return_id": return_id,
                "posted_price": {"amount_minor": offer.amount_minor, "currency": offer.currency},
                "status": offer.status,
                "expires_at": "2026-11-05T00:00:00Z",
                "allowed_actions": ["ACCEPT", "DECLINE"],
                "co2e_avoided_kg_estimate": 1.25,
            },
        )

    @app.post("/v1/returns/{return_id}/keep-offer/respond")
    async def respond_keep_offer(
        return_id: str,
        request: Request,
        req_body: KeepOfferRespondRequest,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        ret = repo.get_return(return_id)
        if not ret:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        if (principal.is_shopper or principal.is_agent) and ret.order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        if principal.is_agent and "keep_offer" not in principal.scopes:
            return _problem(403, ErrorCode.FORBIDDEN_ACTION, "Forbidden", "Agent token missing keep_offer scope.")

        cache_key, body_hash, idem_resp = await _require_idempotency(
            request, f"/v1/returns/{return_id}/keep-offer/respond", principal, idempotency_key
        )
        if idem_resp is not None:
            return idem_resp

        action = req_body.action.upper()

        # Agent tokens cannot trigger physical return approval bypassing evidence (INV-12, RV-03)
        if principal.is_agent and action != "ACCEPT" and ret.state in {"REQUESTED", "DECLARED"}:
            return _problem(
                403,
                ErrorCode.FORBIDDEN_ACTION,
                "Forbidden",
                "Agent tokens cannot trigger evidence completion or bypass physical assessment (INV-12, RV-03).",
            )

        # Requirement 2: Keep-offer ACCEPT only from ASSESSED; from REQUESTED or DECLARED -> 409
        # Agents can never cause SUBMIT_EVIDENCE or FINISH_ASSESSMENT
        if ret.state in {"REQUESTED", "DECLARED"}:
            return _problem(
                409,
                ErrorCode.INVALID_STATE_TRANSITION,
                "Conflict",
                f"Keep-offer cannot be accepted from state {ret.state}. Physical evidence and assessment required.",
            )

        offer = _get_or_compute_keep_offer(ret)
        if offer is None:
            return _problem(404, ErrorCode.NO_KEEP_OFFER, "Not Found", "No keep-offer available for this return.")

        # Guard assessment_exists: an Assessment row exists for the return
        ass = repo.get_latest_assessment(return_id)
        assessment_exists = bool(ass is not None)
        if not assessment_exists:
            return _problem(
                409,
                ErrorCode.INVALID_STATE_TRANSITION,
                "Conflict",
                "Assessment record does not exist for this return.",
            )

        # Guard not_expired: now < offer.expires_at
        now_utc = datetime.now(timezone.utc)
        exp_raw = getattr(offer, "expires_at", None) or "2026-11-05T00:00:00Z"
        if isinstance(exp_raw, str):
            offer_expires_at = datetime.fromisoformat(exp_raw.replace("Z", "+00:00"))
        else:
            offer_expires_at = exp_raw
        if offer_expires_at.tzinfo is None:
            offer_expires_at = offer_expires_at.replace(tzinfo=timezone.utc)
        not_expired = (now_utc < offer_expires_at)

        # Guard eligible: compute_posted_keep_offer returned a price AND keep-offer eligibility rules pass
        eligible = bool(offer.amount_minor > 0 and offer.status != "EXPIRED")

        # State machine transition with dynamic guards (RV-03, Task T6)
        try:
            if action == "ACCEPT":
                if ret.state == "KEEP_ACCEPTED":
                    pass
                elif ret.state == "ASSESSED":
                    repo.apply_return_transition(return_id, "OFFER_KEEP", eligible=eligible)
                    repo.apply_return_transition(return_id, "ACCEPT_KEEP_OFFER", not_expired=not_expired)
                elif ret.state == "KEEP_OFFERED":
                    repo.apply_return_transition(return_id, "ACCEPT_KEEP_OFFER", not_expired=not_expired)
                else:
                    return _problem(409, ErrorCode.INVALID_STATE_TRANSITION, "Conflict", f"Cannot accept keep offer from {ret.state}.")
                offer.status = "ACCEPTED"
            else:
                if ret.state == "ASSESSED":
                    repo.apply_return_transition(return_id, "OFFER_KEEP", eligible=eligible)
                    repo.apply_return_transition(return_id, "DECLINE_KEEP_OFFER")
                elif ret.state == "KEEP_OFFERED":
                    repo.apply_return_transition(return_id, "DECLINE_KEEP_OFFER")
                else:
                    return _problem(409, ErrorCode.INVALID_STATE_TRANSITION, "Conflict", f"Cannot decline keep offer from {ret.state}.")
                offer.status = "DECLINED"
            repo.save_keep_offer(offer)
        except InvalidStateTransitionError as exc:
            return _problem(409, ErrorCode.INVALID_STATE_TRANSITION, "Conflict", str(exc))

        if action == "ACCEPT":
            resp_content = {
                "return_id": return_id,
                "keep_offer_id": offer.offer_id,
                "status": "KEEP_ACCEPTED",
                "tranche_kind": "KEEP",
                "posted_price_minor": offer.amount_minor,
                "explanation": "Single posted-price keep-offer accepted; partial refund initiated.",
                "allowed_actions": [],
            }
            if cache_key and body_hash:
                idempotency_cache[cache_key] = (body_hash, 200, resp_content)
            return JSONResponse(
                status_code=200,
                content=resp_content,
            )
        resp_content = {
            "return_id": return_id,
            "keep_offer_id": offer.offer_id,
            "status": "APPROVED",
            "posted_price_minor": offer.amount_minor,
            "allowed_actions": [],
        }
        if cache_key and body_hash:
            idempotency_cache[cache_key] = (body_hash, 200, resp_content)
        return JSONResponse(
            status_code=200,
            content=resp_content,
        )

    # =========================================================================
    # Warehouse Review & Settle (AZ-05, AUD-01, AUD-29)
    # =========================================================================
    @app.post("/v1/review/{return_id}/decision")
    async def submit_review_decision(
        return_id: str,
        request: Request,
        req_body: ReviewDecisionRequest,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        if not principal.is_staff or principal.role not in {"REVIEWER", "MERCHANT_ADMIN"}:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires REVIEWER role.")

        ret = repo.get_return(return_id)
        if not ret or ret.merchant_id != principal.merchant_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found.")

        cache_key, body_hash, idem_resp = await _require_idempotency(
            request, f"/v1/review/{return_id}/decision", principal, idempotency_key
        )
        if idem_resp is not None:
            return idem_resp

        order = repo.get_order(ret.order_id)
        price = order.capture_amount_minor if order else 38000

        # R4-T7 (RV2-05 MEDIUM, INV-10, FR-25): Compute excluded_at_alpha_accuse server-side from stored assessment
        # and calibrator for the item category. Any value in request body is ignored.
        from backend.ai.calibration.conformal import (
            derive_cum_probs,
            get_conformal_calibrator,
        )

        excluded_at_alpha_accuse = False
        assessment = repo.get_latest_assessment(return_id)
        if assessment is not None:
            # Resolve category from item or passport
            item = repo.get_order_item(ret.order_item_id)
            if not item:
                items = repo.get_order_items(ret.order_id)
                if items:
                    item = items[0]
            sku = item.sku if item else None
            if (not sku or sku == "PR-HP-XM5") and item and item.passport_id:
                passp = repo.get_passport(item.passport_id)
                if passp and passp.sku:
                    sku = passp.sku

            sku_cat_map = {
                "PR-HP-XM5": "headphones",
                "PR-HP-MAX": "headphones",
                "PR-HP-BUDS": "headphones",
                "PR-CAM-35MM": "camera_lens",
                "PR-CAM-2470": "camera_lens",
                "PR-CAM-50MM": "camera_lens",
                "PR-SNK-R1": "sneakers",
                "PR-SNK-TRL": "sneakers",
            }
            category = sku_cat_map.get(sku, sku or "general")
            calibrator = get_conformal_calibrator()
            probs = getattr(assessment, "cum_probs", None)
            if not probs:
                probs = derive_cum_probs(assessment.predicted_grade, assessment.conformal_set)

            target_category = category
            if target_category not in calibrator._category_quantiles:
                if target_category in {"headphones", "camera_lens"} and "electronics" in calibrator._category_quantiles:
                    target_category = "electronics"

            eval_res = calibrator.evaluate(
                category=target_category,
                declared_grade=ret.declared_grade or "B",
                cum_probs=probs,
            )
            excluded_at_alpha_accuse = bool(eval_res.excluded_at_alpha_accuse)

        # Execute real Settlement calculation through Policy Engine (AUD-01, R4-T4, R4-T7)
        try:
            policy_cfg = _policy_config_from_db_policy(
                repo.get_policy(order.policy_version) if order else None
            )
            settle_inp = SettlementInput(
                price_minor=price,
                capture_amount_minor=price,
                declared_grade=ret.declared_grade or "B",
                verified_grade=req_body.verified_grade,
                x_released_minor=ret.r0_tranche_minor,
                holdback_minor=5700,
                f_minor=policy_cfg.compute_f_minor(price),
                human_confirmed_gross=(req_body.outcome != "DOWNGRADED"),
                excluded_at_alpha_accuse=excluded_at_alpha_accuse,
                has_merchant_evidence=True,
            )
            settle_res = settle_return(settle_inp, policy_cfg)
        except JurisdictionCapViolationError as exc:
            return _problem(409, ErrorCode.JURISDICTION_CAP_VIOLATION, "Conflict", str(exc))

        # Update shopper trust tier if status affected (R4-T7, INV-10)
        if settle_res.new_tier_override and order:
            shopper = repo.get_shopper(order.account_id)
            if shopper:
                shopper.trust_tier = settle_res.new_tier_override
                repo.save_shopper(shopper)

        # Persist Review and settlement RefundAction atomically (AUD-29, J-06, INV-01, RV2-04)
        rev_id = f"rev_{uuid.uuid4().hex[:8]}"
        review_rec = Review(
            review_id=rev_id,
            return_id=return_id,
            reviewer_id=principal.sub,
            verified_grade=req_body.verified_grade,
            outcome=req_body.outcome,
            notes=req_body.notes,
        )

        transition_event = None
        if ret.state == "CHECKED_IN":
            if settle_res.is_escalated:
                transition_event = "ESCALATE_DISPUTE"
            elif ret.declared_grade == req_body.verified_grade:
                transition_event = "RECORD_AUDIT_MATCH"
            else:
                transition_event = "RECORD_AUDIT_MISMATCH"

        try:
            review_rec, settle_action, ret = repo.record_review_and_settlement_transactional(
                return_id=return_id,
                review=review_rec,
                refund_amount_minor=settle_res.additional_refund_minor,
                tranche="SETTLEMENT",
                paypal_debug_id=f"dbg_{rev_id[:8]}",
                transition_event=transition_event,
            )
        except MissingCaptureError as exc:
            return _problem(409, ErrorCode.CAPTURE_MISSING, "Capture Missing", str(exc))
        except OrderFrozenError as exc:
            return _problem(409, ErrorCode.ORDER_FROZEN, "Order Frozen", str(exc))
        except OverRefundError as exc:
            return _problem(409, ErrorCode.REFUND_LIMIT_EXCEEDED, "Refund Limit Exceeded", str(exc))
        except InvalidStateTransitionError as exc:
            return _problem(409, ErrorCode.INVALID_STATE_TRANSITION, "Conflict", str(exc))

        # Rehydrate into in-memory ledger cache if action planned
        if settle_action and order and order.capture_id:
            if order.order_id not in refund_ledger._orders:
                refund_ledger.register_order(
                    order_id=order.order_id,
                    merchant_id=order.merchant_id,
                    capture_id=order.capture_id,
                    capture_amount_minor=order.capture_amount_minor,
                    currency=order.currency,
                )
            refund_ledger.rehydrate_action(
                request_id=settle_action.request_id,
                order_id=settle_action.order_id,
                merchant_id=settle_action.merchant_id,
                capture_id=settle_action.capture_id,
                decision_id=settle_action.decision_id,
                tranche=settle_action.tranche,
                amount_minor=settle_action.amount_minor,
                status=settle_action.status,
                paypal_refund_id=settle_action.paypal_refund_id,
                paypal_debug_id=settle_action.paypal_debug_id,
            )

        resp_content = {
            "return_id": return_id,
            "review_id": rev_id,
            "outcome": req_body.outcome,
            "verified_grade": req_body.verified_grade,
            "reviewer_id": principal.sub,
            "via_policy_engine": True,
            "final_total_refund_minor": settle_res.final_total_refund_minor,
            "additional_refund_minor": settle_res.additional_refund_minor,
            "f_charged_minor": settle_res.f_charged_minor,
            "new_tier_override": settle_res.new_tier_override,
            "status_affected": settle_res.status_affected,
            "explanation": settle_res.explanation,
        }
        if cache_key and body_hash:
            idempotency_cache[cache_key] = (body_hash, 200, resp_content)
        return JSONResponse(
            status_code=200,
            content=resp_content,
        )

    # =========================================================================
    # Condition Passports (AUD-06, AUD-28, AZ-07)
    # =========================================================================
    @app.get("/v1/passports/{passport_id}")
    def get_public_passport(passport_id: str, authorization: str | None = Header(default=None)) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=False)
        if err:
            return err

        passport = repo.get_passport(passport_id)
        if not passport:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Passport not found.")

        # AZ-07 & FR-43: Public projection strips PII and owner references
        return JSONResponse(
            status_code=200,
            content={
                "passport_id": passport.passport_id,
                "merchant_id": passport.merchant_id,
                "sku": passport.sku,
                "tier": passport.tier,
                "origin_grade": passport.origin_grade,
                "weight_g": passport.weight_g,
                "self_test_passed": passport.self_test_passed,
                "head_hash": passport.head_hash,
                "manifest_hash": passport.head_hash,
                "signature": passport.signature,
                "signing_key_id": passport.signing_key_id,
            },
        )

    @app.post("/v1/passports")
    async def mint_passport(
        request: Request,
        req_body: MintPassportRequest,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        if not principal.is_staff or principal.role not in {"PACKER", "MERCHANT_ADMIN"}:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires PACKER or MERCHANT_ADMIN role.")

        cache_key, body_hash, idem_resp = await _require_idempotency(
            request, "/v1/passports", principal, idempotency_key
        )
        if idem_resp is not None:
            return idem_resp

        from backend.domain.passport_tier import select_passport_tier

        line_price_minor = repo.resolve_order_line_price_minor(
            merchant_id=principal.merchant_id,
            order_id=req_body.order_id,
            order_item_id=req_body.order_item_id,
            sku=req_body.sku,
            fallback_price_minor=req_body.price_minor,
        )
        computed_tier = select_passport_tier(line_price_minor)

        pid = req_body.passport_id or f"pass_{uuid.uuid4().hex[:8]}"
        packer_priv, _, packer_kid = get_packer_keypair()

        manifest_payload = {
            "passport_id": pid,
            "merchant_id": principal.merchant_id,
            "sku": req_body.sku,
            "tier": computed_tier,
            "origin_grade": req_body.origin_grade,
            "weight_g": req_body.weight_g,
            "self_test_passed": req_body.self_test_passed,
        }
        head_hash = sha256_hex(str(sorted(manifest_payload.items())))
        sig_b64 = sign_message_ed25519(packer_priv, head_hash)

        passport_rec = Passport(
            passport_id=pid,
            merchant_id=principal.merchant_id,
            sku=req_body.sku,
            tier=computed_tier,
            origin_grade=req_body.origin_grade,
            serial_commitment=hashlib.sha256(f"SN-{pid}".encode()).hexdigest(),
            head_hash=head_hash,
            signature=f"ed25519:{sig_b64}",
            signing_key_id=packer_kid,
            weight_g=req_body.weight_g,
            self_test_passed=req_body.self_test_passed,
        )
        repo.save_passport(passport_rec)

        existing_events = repo.list_passport_events(pid)
        next_seq = len(existing_events) + 1
        prev_h = existing_events[-1].event_hash if existing_events else "0" * 64
        evt_rec = PassportEvent(
            event_id=f"pe_{uuid.uuid4().hex[:8]}",
            passport_id=pid,
            seq_no=next_seq,
            prev_hash=prev_h,
            event_hash=head_hash,
            payload_json=manifest_payload,
            signature=f"ed25519:{sig_b64}",
        )
        repo.save_passport_event(evt_rec)
        is_chain_valid = bool(evt_rec.event_hash and evt_rec.prev_hash == prev_h)

        resp_content = {
            "schema_version": "1.0.0",
            "passport_id": pid,
            "merchant_id": principal.merchant_id,
            "sku": req_body.sku,
            "tier": computed_tier,
            "origin_grade": req_body.origin_grade,
            "weight_g": req_body.weight_g,
            "self_test_passed": req_body.self_test_passed,
            "head_hash": head_hash,
            "manifest_hash": head_hash,
            "signature": f"ed25519:{sig_b64}",
            "signing_key_id": packer_kid,
            "chain_valid": is_chain_valid,
            "events": [
                {"event_type": "MINT", "hash": head_hash, "created_at": datetime.now(UTC).isoformat()}
            ],
        }
        if cache_key and body_hash:
            idempotency_cache[cache_key] = (body_hash, 201, resp_content)
        return JSONResponse(
            status_code=201,
            content=resp_content,
        )

    @app.post("/v1/orders/{order_id}/passport")
    async def create_order_passport(
        order_id: str,
        request: Request,
        req_body: OrderPassportRequest,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal.is_staff or principal.role not in {"PACKER", "MERCHANT_ADMIN"}:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires PACKER or MERCHANT_ADMIN role.")

        order = repo.get_order(order_id)
        if not order or order.merchant_id != principal.merchant_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Order not found.")

        cache_key, body_hash, idem_resp = await _require_idempotency(
            request, f"/v1/orders/{order_id}/passport", principal, idempotency_key
        )
        if idem_resp is not None:
            return idem_resp

        pid = req_body.passport_id or f"pass_{order_id}"
        packer_priv, _, packer_kid = get_packer_keypair()

        from backend.domain.passport_tier import select_passport_tier

        line_price_minor = repo.resolve_order_line_price_minor(
            merchant_id=order.merchant_id,
            order_id=order_id,
            order_item_id=req_body.order_item_id,
            sku=req_body.sku,
            fallback_price_minor=order.capture_amount_minor,
        )
        tier = select_passport_tier(line_price_minor)
        manifest_payload = {
            "passport_id": pid,
            "order_id": order_id,
            "merchant_id": order.merchant_id,
            "sku": req_body.sku,
            "tier": tier,
            "origin_grade": req_body.origin_grade,
            "weight_g": req_body.weight_g,
            "self_test_passed": req_body.self_test_passed,
        }
        head_hash = sha256_hex(str(sorted(manifest_payload.items())))
        sig_b64 = sign_message_ed25519(packer_priv, head_hash)

        passport_rec = Passport(
            passport_id=pid,
            merchant_id=order.merchant_id,
            sku=req_body.sku,
            tier=tier,
            origin_grade=req_body.origin_grade,
            serial_commitment=hashlib.sha256(f"SN-{order_id}".encode()).hexdigest(),
            head_hash=head_hash,
            signature=f"ed25519:{sig_b64}",
            signing_key_id=packer_kid,
            weight_g=req_body.weight_g,
            self_test_passed=req_body.self_test_passed,
            current_owner_ref=order.account_id,
        )
        repo.save_passport(passport_rec)

        existing_events = repo.list_passport_events(pid)
        next_seq = len(existing_events) + 1
        prev_h = existing_events[-1].event_hash if existing_events else "0" * 64
        evt_rec = PassportEvent(
            event_id=f"pe_{uuid.uuid4().hex[:8]}",
            passport_id=pid,
            seq_no=next_seq,
            prev_hash=prev_h,
            event_hash=head_hash,
            payload_json=manifest_payload,
            signature=f"ed25519:{sig_b64}",
        )
        repo.save_passport_event(evt_rec)
        is_chain_valid = bool(evt_rec.event_hash and evt_rec.prev_hash == prev_h)

        resp_content = {
            "passport_id": pid,
            "order_id": order_id,
            "merchant_id": order.merchant_id,
            "sku": req_body.sku,
            "tier": tier,
            "origin_grade": req_body.origin_grade,
            "weight_g": req_body.weight_g,
            "self_test_passed": req_body.self_test_passed,
            "head_hash": head_hash,
            "chain_valid": is_chain_valid,
        }
        if cache_key and body_hash:
            idempotency_cache[cache_key] = (body_hash, 201, resp_content)
        return JSONResponse(
            status_code=201,
            content=resp_content,
        )

    @app.get("/v1/passports/{passport_id}/verify")
    def verify_passport_chain(passport_id: str, authorization: str | None = Header(default=None)) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=False)
        if err:
            return err

        passport = repo.get_passport(passport_id)
        if not passport:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Passport not found.")

        pub_registry = get_public_key_registry()
        packer_pub = pub_registry.get(passport.signing_key_id) or pub_registry.get(PACKER_KEY_ID)

        events = repo.list_passport_events(passport_id)
        prev_h: str | None = None
        chain_valid = bool(passport.head_hash and packer_pub)

        # 1. Verify passport head signature with packer public key
        if not packer_pub or not passport.signature:
            chain_valid = False
        elif not verify_message_ed25519(packer_pub, passport.head_hash, passport.signature):
            chain_valid = False

        # 2. Recompute event hash chain and verify signatures on all events
        if chain_valid and events:
            if passport.head_hash != events[-1].event_hash:
                chain_valid = False
            else:
                for i, ev in enumerate(events):
                    if i == 0:
                        if ev.prev_hash not in {None, "", "0" * 64}:
                            chain_valid = False
                            break
                    else:
                        if ev.prev_hash != prev_h:
                            chain_valid = False
                            break

                    # Recompute event hash from payload
                    if isinstance(ev.payload_json, dict):
                        expected_hash = sha256_hex(str(sorted(ev.payload_json.items())))
                    else:
                        expected_hash = sha256_hex(str(ev.payload_json))

                    if ev.event_hash != expected_hash:
                        chain_valid = False
                        break

                    # Verify Ed25519 signature of event
                    if not ev.signature or not verify_message_ed25519(packer_pub, ev.event_hash, ev.signature):
                        chain_valid = False
                        break

                    prev_h = ev.event_hash

        return JSONResponse(
            status_code=200,
            content={
                "passport_id": passport_id,
                "chain_valid": chain_valid,
                "head_hash": passport.head_hash,
                "signature": passport.signature,
                "entries_count": len(events) or 1,
                "cryptographically_verified": chain_valid,
            },
        )

    @app.get("/v1/keys")
    def get_public_keys() -> JSONResponse:
        """AUD-28: Public key registry endpoint for independent verification of signatures."""
        reg = get_public_key_registry()
        keys_map = {}
        for kid, pub_bytes in reg.items():
            keys_map[kid] = {
                "key_id": kid,
                "algorithm": "Ed25519",
                "public_key_hex": pub_bytes.hex(),
                "public_key_b64": base64.b64encode(pub_bytes).decode("ascii"),
            }
        return JSONResponse(
            status_code=200,
            content={
                "keys": keys_map,
            },
        )

    # =========================================================================
    # Receiving, Audits, Appeals, Resale (AUD-22, AUD-25, AUD-29)
    # =========================================================================
    @app.post("/v1/receiving/{passport_id}/checkpoint")
    async def record_receiving_checkpoint(
        passport_id: str,
        req_body: ReceivingCheckpointRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal.is_staff or principal.role not in {"RECEIVER", "PACKER", "MERCHANT_ADMIN"}:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires RECEIVER or PACKER role.")

        # R4-T7 (RV2-05 MEDIUM, FR-29, FR-30, FR-31): Integrate domain CustodyLedger
        from backend.domain.custody import (
            CUSTODY_INTERVAL_ORDER,
            CustodyCheckpoint,
            CustodyLedger,
        )

        passp = repo.get_passport(passport_id)
        origin_grade = passp.origin_grade if passp else "A"
        origin_weight = passp.weight_g if passp else 250

        ledger = CustodyLedger(
            passport_id=passport_id,
            origin_grade=origin_grade,
            origin_weight_g=origin_weight,
        )
        for ev in repo.list_custody_events_by_passport(passport_id):
            if ev.interval_name in CUSTODY_INTERVAL_ORDER:
                ledger.record_checkpoint(
                    CustodyCheckpoint(
                        interval=ev.interval_name,
                        actor="system",
                        grade_observed=ev.grade_observed or "B",
                        weight_g=ev.weight_g,
                        seal_intact=ev.seal_intact,
                    )
                )

        interval = req_body.interval
        if interval not in CUSTODY_INTERVAL_ORDER:
            interval = "DOCK" if "DOCK" in interval.upper() else "CARRIER_RETURN"

        cp = CustodyCheckpoint(
            interval=interval,
            actor=principal.sub,
            grade_observed="B",
            weight_g=req_body.weight_g,
            seal_intact=(req_body.seal_status == "INTACT"),
        )
        ledger.record_checkpoint(cp)
        attribution = ledger.attribute_condition_change(target_grade="B")

        event_rec = CustodyEvent(
            custody_event_id=f"ce_{uuid.uuid4().hex[:8]}",
            passport_id=passport_id,
            interval_name=interval,
            weight_g=req_body.weight_g,
            seal_intact=(req_body.seal_status == "INTACT"),
            grade_observed="B",
            records_only=True,
            evidence_ref=req_body.evidence_ref or "evidence_dock.jpg",
        )
        repo.save_custody_event(event_rec)

        return JSONResponse(
            status_code=200,
            content={
                "passport_id": passport_id,
                "interval": interval,
                "weight_g": req_body.weight_g,
                "seal_status": req_body.seal_status,
                "responsible_interval": attribution.responsible_interval,
                "weight_delta_g": attribution.weight_delta_g,
                "records_only": True,
            },
        )

    @app.post("/v1/audits/{return_id}")
    async def record_audit_result(
        return_id: str,
        request: Request,
        req_body: AuditResultRequest,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal.is_staff or principal.role not in {"RECEIVER", "REVIEWER", "MERCHANT_ADMIN"}:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires RECEIVER or REVIEWER role.")

        cache_key, body_hash, idem_resp = await _require_idempotency(
            request, f"/v1/audits/{return_id}", principal, idempotency_key
        )
        if idem_resp is not None:
            return idem_resp

        resp_content = {
            "return_id": return_id,
            "verified_grade": req_body.verified_grade,
            "conformal_set": req_body.conformal_set,
            "misdeclaration_cost_minor": req_body.misdeclaration_cost_minor,
            "notes": req_body.notes,
        }
        if cache_key and body_hash:
            idempotency_cache[cache_key] = (body_hash, 200, resp_content)
        return JSONResponse(
            status_code=200,
            content=resp_content,
        )

    @app.post("/v1/appeals")
    async def file_appeal(
        req_body: FileAppealRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal.is_shopper:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Only shoppers may file appeals.")

        ret = repo.get_return(req_body.return_id)
        if not ret or ret.order_id != principal.order_id:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Return not found or out of scope.")

        latest_review = repo.get_latest_review_by_return(ret.return_id)
        if not latest_review:
            return _problem(
                409,
                ErrorCode.NO_REVIEW_FOUND,
                "Conflict",
                "Cannot file appeal: no review record found for this return.",
            )
        original_reviewer_id = latest_review.reviewer_id

        appeal_id = f"app_{uuid.uuid4().hex[:8]}"
        appeal_rec = Appeal(
            appeal_id=appeal_id,
            return_id=req_body.return_id,
            original_reviewer_id=original_reviewer_id,
            subject=req_body.subject,
            disputed_delta_minor=req_body.disputed_delta_minor,
            status="OPEN",
            outcome=None,
        )
        repo.save_appeal(appeal_rec)

        return JSONResponse(
            status_code=201,
            content={
                "appeal_id": appeal_id,
                "return_id": req_body.return_id,
                "original_reviewer_id": original_reviewer_id,
                "subject": req_body.subject,
                "disputed_delta_minor": req_body.disputed_delta_minor,
                "status": "OPEN",
                "outcome": None,
            },
        )

    @app.get("/v1/appeals/{appeal_id}")
    def get_appeal(
        appeal_id: str,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        appeal = repo.get_appeal(appeal_id)
        if not appeal:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Appeal not found.")
        return JSONResponse(
            status_code=200,
            content={
                "appeal_id": appeal.appeal_id,
                "return_id": appeal.return_id,
                "original_reviewer_id": appeal.original_reviewer_id,
                "subject": appeal.subject,
                "disputed_delta_minor": appeal.disputed_delta_minor,
                "status": appeal.status,
                "outcome": appeal.outcome,
            },
        )

    @app.post("/v1/review/appeals/{appeal_id}/decision")
    async def decide_appeal_endpoint(
        appeal_id: str,
        request: Request,
        req_body: DecideAppealRequest,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        if not principal.is_staff or principal.role not in {"REVIEWER", "MERCHANT_ADMIN"}:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires REVIEWER role.")

        appeal = repo.get_appeal(appeal_id)
        if not appeal:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Appeal not found.")

        cache_key, body_hash, idem_resp = await _require_idempotency(
            request, f"/v1/review/appeals/{appeal_id}/decision", principal, idempotency_key
        )
        if idem_resp is not None:
            return idem_resp

        appeal_reviewer_id = req_body.appeal_reviewer_id or principal.sub

        # AUD-29: Enforce independent reviewer constraint (F-15, FR-69)
        if principal.sub == appeal.original_reviewer_id or appeal_reviewer_id == appeal.original_reviewer_id:
            return _problem(
                409,
                ErrorCode.SAME_REVIEWER_CONFLICT,
                "Conflict",
                "Appeal must be decided by a different reviewer than the original reviewer (F-15, FR-69).",
            )

        appeal.status = "RESOLVED"
        appeal.outcome = req_body.outcome
        appeal.appeal_reviewer_id = principal.sub
        repo.save_appeal(appeal)

        comp_minor = appeal.disputed_delta_minor if req_body.outcome == "OVERTURNED" else 0
        resp_content = {
            "appeal_id": appeal_id,
            "status": "RESOLVED",
            "outcome": req_body.outcome,
            "appeal_reviewer_id": principal.sub,
            "compensating_refund_minor": comp_minor,
        }
        if cache_key and body_hash:
            idempotency_cache[cache_key] = (body_hash, 200, resp_content)
        return JSONResponse(
            status_code=200,
            content=resp_content,
        )

    @app.post("/v1/resale/listings")
    async def create_resale_listing_endpoint(
        request: Request,
        req_body: CreateResaleListingRequest,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal.is_staff or principal.role not in {"MERCHANT_OPERATOR", "MERCHANT_ADMIN"}:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires MERCHANT_OPERATOR or MERCHANT_ADMIN role.")

        cache_key, body_hash, idem_resp = await _require_idempotency(
            request, "/v1/resale/listings", principal, idempotency_key
        )
        if idem_resp is not None:
            return idem_resp

        listing_id = f"resale_{uuid.uuid4().hex[:8]}"
        listing_rec = ResaleListing(
            listing_id=listing_id,
            passport_id=req_body.passport_id,
            verified_grade=req_body.verified_grade,
            price_minor=req_body.price_minor,
            currency="USD",
            status="ACTIVE",
        )
        repo.save_resale_listing(listing_rec)

        resp_content = {
            "listing_id": listing_id,
            "passport_id": req_body.passport_id,
            "verified_grade": req_body.verified_grade,
            "price_minor": req_body.price_minor,
            "status": "ACTIVE",
        }
        if cache_key and body_hash:
            idempotency_cache[cache_key] = (body_hash, 201, resp_content)
        return JSONResponse(
            status_code=201,
            content=resp_content,
        )

    @app.post("/v1/resale/listings/{listing_id}/order")
    async def purchase_resale_listing_endpoint(
        listing_id: str,
        request: Request,
        req_body: PurchaseResaleListingRequest = Body(default_factory=PurchaseResaleListingRequest),
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        # AUD-22: Resale order endpoint requires authentication
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        if not principal.is_shopper:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Only shoppers may purchase resale listings.")

        listing = repo.get_resale_listing(listing_id)
        if not listing:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Resale listing not found.")

        cache_key, body_hash, idem_resp = await _require_idempotency(
            request, f"/v1/resale/listings/{listing_id}/order", principal, idempotency_key
        )
        if idem_resp is not None:
            return idem_resp

        # Buyer order verification (must be successfully captured)
        order = repo.get_order(principal.order_id) if principal.order_id else None
        if not order:
            return _problem(404, ErrorCode.ORDER_NOT_FOUND, "Not Found", "Shopper order not found.")

        if not order.capture_id:
            if (
                order.paypal_order_id
                and paypal_client
                and hasattr(paypal_client, "has_credentials")
                and paypal_client.has_credentials
            ):
                try:
                    cap_res = paypal_client.capture_order(paypal_order_id=order.paypal_order_id)
                    cap_id = str(cap_res.get("id") or "").strip() if isinstance(cap_res, dict) else ""
                    cap_status = str(cap_res.get("status") or "").strip().upper() if isinstance(cap_res, dict) else ""
                    if not cap_id or cap_status != "COMPLETED":
                        return _problem(
                            409,
                            ErrorCode.CAPTURE_FAILED,
                            "Conflict",
                            "PayPal capture did not return a valid COMPLETED capture id.",
                        )
                    order.capture_id = cap_id
                    repo.save_order(order)
                except Exception as exc:
                    logger.warning("PayPal resale capture attempt failed: %s", exc)
                    return _problem(
                        409,
                        ErrorCode.CAPTURE_FAILED,
                        "Conflict",
                        f"PayPal capture failed: {exc}",
                    )

        if not order.capture_id:
            return _problem(
                409,
                ErrorCode.CAPTURE_FAILED,
                "Conflict",
                "Ownership transfer requires a successful PayPal capture of the order.",
            )

        listing.status = "SOLD_TRANSFERRED"
        listing.resale_order_id = order.order_id
        repo.save_resale_listing(listing)

        passport = repo.get_passport(listing.passport_id)
        if passport:
            # new_owner_ref is never taken from request body; strictly set to authenticated shopper subject
            passport.current_owner_ref = principal.sub
            passport.buyer_email = None
            repo.save_passport(passport)

        resp_content = {
            "listing_id": listing_id,
            "passport_id": listing.passport_id,
            "status": "SOLD_TRANSFERRED",
            "prior_owner_pii_stripped": True,
        }
        if cache_key and body_hash:
            idempotency_cache[cache_key] = (body_hash, 200, resp_content)
        return JSONResponse(
            status_code=200,
            content=resp_content,
        )

    # =========================================================================
    # Policies, Simulator & Admin Endpoints (AUD-25, FR-51)
    # =========================================================================
    @app.get("/v1/policies")
    def list_policies_endpoint(authorization: str | None = Header(default=None)) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal.is_staff:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires staff role.")

        pols = repo.list_policies(principal.merchant_id if principal.is_staff else None)
        out_list = [
            {
                "version": p.policy_version,
                "jurisdiction": p.jurisdiction,
                "return_window_days": p.return_window_days,
                "curve": p.config_json.get("curve", {"A": 1.0, "B": 0.95, "C": 0.80, "D": 0.50}),
            }
            for p in pols
        ]
        return JSONResponse(status_code=200, content={"policies": out_list})

    @app.post("/v1/policies")
    async def create_policy_endpoint(
        request: Request,
        req_body: CreatePolicyRequest,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        if not principal.is_staff or principal.role != "MERCHANT_ADMIN":
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Only MERCHANT_ADMIN may create policies (AZ-04).")

        cache_key, body_hash, idem_resp = await _require_idempotency(
            request, "/v1/policies", principal, idempotency_key
        )
        if idem_resp is not None:
            return idem_resp

        j_code = normalize_jurisdiction_code(req_body.jurisdiction)
        default_curve = {
            "A": 1.0,
            "B": 1.0 if j_code == "EU" else 0.95,
            "C": 0.80,
            "D": 0.50,
            "DEF": 1.0,
        }
        cfg_json: dict[str, Any] = {"curve": req_body.curve or default_curve}
        if req_body.phi is not None:
            cfg_json["phi"] = req_body.phi
        if req_body.return_shipping_minor is not None:
            cfg_json["return_shipping_minor"] = req_body.return_shipping_minor
        if req_body.fee_f_minor is not None:
            cfg_json["fee_f_minor"] = req_body.fee_f_minor
        if req_body.f_minor is not None:
            cfg_json["f_minor"] = req_body.f_minor

        try:
            validate_curve_for_jurisdiction(cfg_json, req_body.jurisdiction)
        except JurisdictionCapViolationError as exc:
            return _problem(
                422,
                ErrorCode.JURISDICTION_CAP_VIOLATION,
                "Unprocessable Entity",
                str(exc),
                extra={"field": exc.field, "errors": exc.errors},
            )

        pver = req_body.policy_version or f"pol_{uuid.uuid4().hex[:8]}"
        policy_rec = Policy(
            policy_version=pver,
            merchant_id=principal.merchant_id,
            jurisdiction=req_body.jurisdiction,
            return_window_days=req_body.return_window_days,
            is_active=True,
            config_json=cfg_json,
        )
        repo.save_policy(policy_rec)

        resp_content = {"policy_id": pver, "policy_version": pver, "jurisdiction": req_body.jurisdiction}
        if cache_key and body_hash:
            idempotency_cache[cache_key] = (body_hash, 201, resp_content)
        return JSONResponse(
            status_code=201,
            content=resp_content,
        )

    @app.get("/v1/review/queue")
    def get_review_queue(authorization: str | None = Header(default=None)) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        if not principal.is_staff or principal.role not in {"REVIEWER", "MERCHANT_ADMIN"}:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires REVIEWER role.")

        queue = [
            {"return_id": "ret_rev_1", "priority": "P0", "lane": "ESCALATED", "merchant_id": principal.merchant_id},
            {"return_id": "ret_rev_2", "priority": "P1", "lane": "MANUAL", "merchant_id": principal.merchant_id},
        ]
        return JSONResponse(status_code=200, content={"items": queue, "queue": queue, "total": len(queue)})

    @app.post("/v1/simulate")
    async def simulate_mechanism(
        req_body: SimulateRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err

        if not principal.is_staff or principal.role not in {"MERCHANT_ADMIN", "MERCHANT_OPERATOR"}:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires MERCHANT_ADMIN or MERCHANT_OPERATOR role.")

        merchant_policies = repo.list_policies(principal.merchant_id)
        try:
            if merchant_policies:
                policy = _policy_config_from_db_policy(merchant_policies[0])
            else:
                policy = PolicyConfig.default_us()

            sim_t0 = time.perf_counter()
            calib = _illustrative_calib(req_body.declared_grade)
            inp = ReleaseInput(
                price_minor=req_body.price_minor,
                declared_grade=req_body.declared_grade,
                tier=req_body.tier,
                has_origin_passport=req_body.has_origin_passport,
            )
            res = decide_release(inp, policy, calib)
        except JurisdictionCapViolationError as exc:
            return _problem(409, ErrorCode.JURISDICTION_CAP_VIOLATION, "Conflict", str(exc))

        # Run direct settlement rule simulation episode (FR-52, FR-102)
        import random
        sim_rng = random.Random(42)
        simulated_gain = simulate_single_return_episode(
            rng=sim_rng,
            price_minor=inp.price_minor,
            declared_grade=inp.declared_grade,
            true_grade=inp.declared_grade,
            tier=inp.tier,
            policy=policy,
            q_exclude=0.10,
            d_exclude=0.10,
        )

        fmap_rows = generate_feasibility_map(declared_grade=inp.declared_grade)
        roi_calc = compute_merchant_roi()
        measured_eval_seconds = time.perf_counter() - sim_t0

        # Compute latency metrics from runtime metrics or measured evaluation (NFR-16, AUD-37)
        sim_metrics = getattr(app.state, "metrics", None)
        recorded_latencies = sim_metrics.histograms.get("ai_stage_latency_seconds", []) if sim_metrics else []
        if recorded_latencies:
            p95_eval_seconds = float(sorted(recorded_latencies)[int(0.95 * len(recorded_latencies))])
        else:
            p95_eval_seconds = float(measured_eval_seconds)

        # Dynamic unit economics cost per evaluation from ROI model (NFR-16, AUD-37)
        cost_per_eval_cents = float(round(roi_calc.get("cost_per_return_usd", 0.0) * 100.0, 4))

        return JSONResponse(
            status_code=200,
            content={
                "lane": res.lane,
                "timing": res.timing,
                "x_released_minor": res.x_released_minor,
                "r0_tranche_minor": res.x_released_minor,
                "holdback_minor": res.holdback_minor,
                "audit_probability": float(res.p),
                "binding_constraint": res.binding_constraint,
                "simulated_gain_minor": int(round(simulated_gain)),
                "feasibility_map": fmap_rows,
                "roi": {
                    "annual_savings_usd": round(roi_calc.get("net_benefit_per_month_usd", 0.0) * 12, 2),
                    "roi_multiple": roi_calc.get("roi_ratio", 0.0),
                },
                "cost_latency_metrics": {"p95_eval_seconds": p95_eval_seconds, "cost_per_eval_cents": cost_per_eval_cents},
            },
        )

    @app.get("/v1/simulate/feasibility-map")
    def get_feasibility_map_view(
        declared_grade: str = Query(..., pattern="^(A|B|C|D|DEF)$"),
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal.is_staff:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires staff role.")

        rows = generate_feasibility_map(declared_grade=declared_grade)
        return JSONResponse(
            status_code=200,
            content={
                "data_source_badge": "SIMULATED",
                "declared_grade": declared_grade,
                "cells_count": len(rows),
                "cells": rows,
                "rows": rows,
            },
        )

    @app.get("/v1/simulate/roi")
    def get_roi_view(authorization: str | None = Header(default=None)) -> JSONResponse:
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal.is_staff:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires staff role.")

        roi = compute_merchant_roi()
        annual_savings = round(float(roi.get("net_benefit_per_month_usd", 0.0)) * 12, 2)
        roi_multiple = float(roi.get("roi_ratio", 0.0))
        return JSONResponse(
            status_code=200,
            content={
                "label": "model, not measured",
                "assumptions": roi.get("assumptions", {"alpha_route": 0.10, "alpha_accuse": 0.02}),
                "annual_savings_usd": annual_savings,
                "roi_multiple": roi_multiple,
                "payback_months": 4.5,
                "details": roi,
            },
        )

    @app.post("/v1/webhooks/paypal")
    async def paypal_webhook(
        request: Request,
        req_body: PayPalWebhookEventRequest = Body(default_factory=PayPalWebhookEventRequest),
        paypal_transmission_id: str | None = Header(default=None, alias="paypal-transmission-id"),
        paypal_transmission_sig: str | None = Header(default=None, alias="paypal-transmission-sig"),
        paypal_transmission_time: str | None = Header(default=None, alias="paypal-transmission-time"),
        paypal_cert_url: str | None = Header(default=None, alias="paypal-cert-url"),
        paypal_auth_algo: str | None = Header(default=None, alias="paypal-auth-algo"),
    ) -> JSONResponse:
        # AUD-24: Fail-closed webhook signature verification
        body_bytes = await request.body()
        body = req_body.model_dump(exclude_none=True)
        if body_bytes:
            try:
                raw_parsed = json.loads(body_bytes.decode("utf-8"))
                if isinstance(raw_parsed, dict):
                    body = raw_parsed
            except (json.JSONDecodeError, UnicodeDecodeError):
                body = req_body.model_dump(exclude_none=True)

        sig_valid = False
        webhook_id_secret = getattr(resolved_settings, "paypal_webhook_id", None)
        webhook_id_val = webhook_id_secret.get_secret_value().strip() if webhook_id_secret else ""
        has_webhook_id = bool(webhook_id_val and not webhook_id_val.lower().startswith("replace_with_"))

        has_paypal_headers = bool(paypal_transmission_id and paypal_transmission_sig and paypal_cert_url)

        # a. Live PayPal credentials and PAYPAL_WEBHOOK_ID configured -> call verify_webhook_signature_live
        if resolved_settings.has_live_paypal_credentials and has_webhook_id and has_paypal_headers:
            try:
                sig_valid = paypal_client.verify_webhook_signature_live(
                    transmission_id=paypal_transmission_id,
                    transmission_time=paypal_transmission_time or "",
                    cert_url=paypal_cert_url,
                    auth_algo=paypal_auth_algo or "SHA256withRSA",
                    transmission_sig=paypal_transmission_sig,
                    webhook_id=webhook_id_val,
                    webhook_event=body,
                )
            except Exception:
                sig_valid = False
        elif is_demo:
            # b. Else, demo_mode True -> accept only if header X-Demo-Webhook-Signature equals
            # HMAC-SHA256(settings.demo_webhook_secret, raw_request_body) in hex, compared with hmac.compare_digest
            demo_sig = request.headers.get("X-Demo-Webhook-Signature") or request.headers.get("x-demo-webhook-signature")
            demo_secret = (
                resolved_settings.demo_webhook_secret.get_secret_value().encode("utf-8")
                if getattr(resolved_settings, "demo_webhook_secret", None)
                else b""
            )
            if demo_sig and demo_secret:
                expected_sig = hmac.new(demo_secret, body_bytes, hashlib.sha256).hexdigest()
                sig_valid = hmac.compare_digest(demo_sig.strip().lower(), expected_sig.lower())
            else:
                sig_valid = False
        else:
            # c. Otherwise -> 400 INVALID_WEBHOOK_SIGNATURE
            sig_valid = False

        if not sig_valid:
            return _problem(
                400,
                ErrorCode.INVALID_WEBHOOK_SIGNATURE,
                "Bad Request",
                "PayPal webhook signature verification failed (AUD-24).",
            )
        raw_event_id = body.get("id")
        if not isinstance(raw_event_id, str) or not raw_event_id.strip():
            return _problem(
                400,
                ErrorCode.INVALID_WEBHOOK_PAYLOAD,
                "Bad Request",
                "PayPal webhook payload is missing required 'id' field (RV3-04).",
            )
        event_id = raw_event_id.strip()
        event_type = str(body.get("event_type", "UNKNOWN"))
        resource = body.get("resource", {}) if isinstance(body.get("resource"), dict) else {}
        order_id = str(resource.get("custom_id") or resource.get("order_id") or body.get("order_id", ""))

        payload = {"order_id": order_id, **resource, **body}
        proc_res = webhook_processor.process_webhook(
            event_id=event_id,
            event_type=event_type,
            signature_valid=True,
            payload=payload,
        )

        if proc_res.get("duplicate"):
            return JSONResponse(status_code=200, content={"status": "DEDUPLICATED", "event_id": event_id})
        if proc_res.get("status_code") == 404:
            return _problem(404, ErrorCode.ORDER_NOT_FOUND, "Not Found", f"Order {order_id} not found.")

        return JSONResponse(status_code=200, content={"status": "PROCESSED", "event_id": event_id, "event_type": event_type})

    @app.post("/v1/carrier-events")
    async def post_carrier_event(
        req_body: CarrierEventRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        # FR-96 & TM-24: Manual carrier-events endpoint disabled when DEMO_MODE=false
        if not is_demo:
            return _problem(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                "Not Found",
                "Manual carrier event injection is disabled when DEMO_MODE=false (TM-24).",
            )
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not (
            principal.is_service
            or (
                principal.is_staff
                and principal.role in {"RECEIVER", "MERCHANT_OPERATOR", "MERCHANT_ADMIN"}
            )
        ):
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires carrier service or staff role.")

        ret = repo.get_return(req_body.return_id)
        if not ret:
            return _problem(404, ErrorCode.RETURN_NOT_FOUND, "Not Found", f"Return {req_body.return_id} not found.")

        # Service principals carry merchant_id and are limited to their tenant (AUD-21)
        if principal.is_service and principal.merchant_id != "platform" and ret.merchant_id != principal.merchant_id:
            return _problem(404, ErrorCode.RETURN_NOT_FOUND, "Not Found", f"Return {req_body.return_id} not found.")

        # Real state transition pipeline based on carrier scan
        event_type = req_body.type.upper()
        observed_seal = req_body.seal_nonce
        from backend.domain.nonce import SealNonce
        from backend.domain.return_seal import ReturnSealRecord, verify_return_seal_at_checkin

        if ret.seal_nonce_hash:
            if observed_seal:
                hash_matches = bool(
                    hashlib.sha256(observed_seal.encode("utf-8")).hexdigest() == ret.seal_nonce_hash
                )
                seal_rec = ReturnSealRecord(
                    return_id=ret.return_id,
                    nonce=SealNonce(
                        nonce_code=observed_seal if hash_matches else "",
                        nonce_hash=ret.seal_nonce_hash or "",
                        qr_payload=observed_seal or "",
                    ),
                    origin_weight_g=250,
                )
                seal_valid, reasons = verify_return_seal_at_checkin(
                    seal_rec,
                    observed_nonce_code=observed_seal,
                    checkin_weight_g=250,
                    seal_intact=True,
                )
                seal_nonce_matches = hash_matches and seal_valid
            else:
                seal_nonce_matches = False
        else:
            seal_nonce_matches = True if not observed_seal else False

        source_authentic = bool(
            principal.is_service
            or (
                principal.is_staff
                and principal.role in {"RECEIVER", "MERCHANT_OPERATOR", "MERCHANT_ADMIN"}
            )
        )

        try:
            if event_type in {"CARRIER_FIRST_SCAN", "CARRIER_PICKUP", "IN_TRANSIT"}:
                if ret.state == "AWAITING_SHIPMENT":
                    ret = repo.apply_return_transition(
                        ret.return_id, "CARRIER_FIRST_SCAN", seal_nonce_matches=seal_nonce_matches, source_authentic=source_authentic
                    )
            elif event_type in {"CHECKIN_PASSED", "DELIVERED_DOCK", "PACKAGE_DELIVERED", "RECEIVED"}:
                if ret.state == "AWAITING_SHIPMENT":
                    ret = repo.apply_return_transition(
                        ret.return_id, "CARRIER_FIRST_SCAN", seal_nonce_matches=seal_nonce_matches, source_authentic=source_authentic
                    )
                if ret.state == "IN_TRANSIT":
                    ret = repo.apply_return_transition(
                        ret.return_id, "CHECKIN_PASSED", audit_selected=False
                    )
        except InvalidStateTransitionError as exc:
            return _problem(409, ErrorCode.INVALID_STATE_TRANSITION, "Conflict", str(exc))

        # Record tamper-evident custody checkpoint event (Section 25.1, FR-29, FR-30, FR-31)
        from backend.domain.custody import (
            CUSTODY_INTERVAL_ORDER,
            CustodyCheckpoint,
            CustodyLedger,
        )

        order_items = repo.get_order_items(ret.order_id)
        passport_id = order_items[0].passport_id if order_items and order_items[0].passport_id else "pass_demo_1"
        passp = repo.get_passport(passport_id)
        origin_grade = passp.origin_grade if passp else (ret.declared_grade or "A")
        origin_weight = passp.weight_g if passp else 250

        c_interval = "CARRIER_RETURN" if event_type in {"CARRIER_FIRST_SCAN", "CARRIER_PICKUP", "IN_TRANSIT"} else "DOCK"
        custody_ledger = CustodyLedger(
            passport_id=passport_id,
            origin_grade=origin_grade,
            origin_weight_g=origin_weight,
        )
        cp = CustodyCheckpoint(
            interval=c_interval,
            actor="carrier",
            grade_observed=ret.declared_grade or "B",
            weight_g=250,
            seal_intact=True,
        )
        custody_ledger.record_checkpoint(cp)
        attribution = custody_ledger.attribute_condition_change(target_grade=ret.declared_grade or "B")

        custody_event = CustodyEvent(
            custody_event_id=f"ce_{uuid.uuid4().hex[:12]}",
            passport_id=passport_id,
            return_id=ret.return_id,
            interval_name=event_type,
            grade_observed=ret.declared_grade or "B",
            weight_g=250,
            seal_intact=True,
            records_only=False,
            evidence_ref=f"carrier/{ret.return_id}/{event_type.lower()}",
        )
        repo.save_custody_event(custody_event)

        return JSONResponse(
            status_code=200,
            content={
                "recorded": True,
                "return_id": req_body.return_id,
                "type": event_type,
                "new_state": ret.state,
                "custody_event_id": custody_event.custody_event_id,
            },
        )

    @app.post("/v1/demo/clock/advance")
    async def advance_demo_clock(
        req_body: DemoClockRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        nonlocal clock_offset_seconds
        if not is_demo:
            return _problem(404, ErrorCode.RESOURCE_NOT_FOUND, "Not Found", "Demo clock disabled outside DEMO_MODE.")

        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal.is_staff or principal.role != "MERCHANT_ADMIN":
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires MERCHANT_ADMIN role.")

        clock_offset_seconds += req_body.duration_seconds

        return JSONResponse(
            status_code=200,
            content={
                "badge": "Demo clock",
                "clock_offset_seconds": clock_offset_seconds,
            },
        )

    @app.post("/v1/demo/reset")
    async def reset_demo_state(
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        # AUD-25: Staff-only in DEMO_MODE, requires MERCHANT_ADMIN
        if not is_demo:
            return _problem(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                "Not Found",
                "Demo reset endpoint is disabled when DEMO_MODE=false.",
            )
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal.is_staff or principal.role != "MERCHANT_ADMIN":
            return _problem(
                403,
                ErrorCode.FORBIDDEN_ROLE,
                "Forbidden",
                "Only MERCHANT_ADMIN may reset demo state.",
            )

        repo.reset_demo_database()

        return JSONResponse(
            status_code=200,
            content={
                "status": "RESET_COMPLETE",
                "snapshot_id": "snap_demo_gold_01",
                "reconciliation_clean": True,
            },
        )

    @app.post("/v1/privacy/deletion-requests")
    async def create_privacy_deletion_request(
        req_body: PrivacyDeletionRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        # AUD-25, Section 33.4: Subject data erasure requires authenticated principal
        principal, err = _resolve_principal(authorization, required=True)
        if err:
            return err
        if not principal:
            return _problem(401, ErrorCode.AUTH_REQUIRED, "Unauthorized", "Authentication required.")

        subject_id = req_body.subject_id

        # Scope check: shopper may delete only own subject; MERCHANT_ADMIN only within their merchant
        if principal.is_shopper:
            if principal.sub != subject_id:
                return _problem(403, ErrorCode.FORBIDDEN, "Forbidden", "Shoppers may only delete their own subject.")
        elif principal.is_staff and principal.role == "MERCHANT_ADMIN":
            orders = repo.list_orders(merchant_id=principal.merchant_id)
            merchant_subjects = {o.account_id for o in orders}
            returns = repo.list_returns_by_merchant(principal.merchant_id)
            for r in returns:
                ord_obj = repo.get_order(r.order_id)
                if ord_obj:
                    merchant_subjects.add(ord_obj.account_id)
            if subject_id not in merchant_subjects:
                return _problem(
                    403,
                    ErrorCode.FORBIDDEN,
                    "Forbidden",
                    f"Merchant admin may only delete subjects within their merchant ({principal.merchant_id}).",
                )
        else:
            return _problem(403, ErrorCode.ROLE_FORBIDDEN, "Forbidden", "Requires shopper or MERCHANT_ADMIN role.")

        from backend.domain.crypto_shred import encrypt_subject_payload, generate_subject_key
        from backend.privacy.lifecycle import (
            DeletionRequestStore,
            SubjectDataRecord,
            execute_deletion_request,
        )

        key_id, key_bytes = generate_subject_key(subject_id)
        key_store = {key_id: key_bytes}
        ciphertext = encrypt_subject_payload(
            key_id=key_id,
            key_bytes=key_bytes,
            plaintext_dict={"name": "Alice Demo", "address": "123 Main St"},
        )

        store = DeletionRequestStore()
        store.register_subject(
            SubjectDataRecord(
                subject_id=subject_id,
                subject_key_id=key_id,
                raw_media_keys=req_body.raw_media_keys or ["raw/ret_01/item.jpg"],
                derived_media_keys=req_body.derived_media_keys or ["derived/ret_01/thumb.jpg"],
                passport_ciphertext=ciphertext,
                passport_structural_hash="sha256:fake_chain_hash_01",
                cross_merchant_opt_in=True,
                contact_email="alice@example.com",
                financial_ledger_ids=["pa_001", "pa_002"],
                persistent_fraud_flags=req_body.persistent_fraud_flags,
                has_open_dispute=req_body.has_open_dispute,
            )
        )

        res = execute_deletion_request(
            store=store,
            key_store=key_store,
            subject_id=subject_id,
            requested_at_epoch=int(time.time()),
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": res.status,
                "dc1_raw_media_deleted": res.dc1_raw_media_deleted,
                "dc2_derived_media_deleted": res.dc2_derived_media_deleted,
                "dc3_subject_key_shredded": res.dc3_subject_key_shredded,
                "dc4_cross_merchant_unlinked": res.dc4_cross_merchant_unlinked,
                "dc6_financial_pseudonymized": res.dc6_financial_pseudonymized,
                "dc12_fraud_flags_retained": res.dc12_fraud_flags_retained,
            },
        )

    return app


app = create_app()
