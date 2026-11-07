"""Initialize and synchronize docs/rtm.csv from docs/SSOT.md (Sections 20, 23 & 46).

Adheres strictly to Section 20.1 (SI-01..SI-05), Independent Technical Audit findings (J-02, DOC-01..DOC-04),
and Task T7 (DOC-01..04):
- VERIFIED: Only requirements where a named test (file::test) proves the behavior through the API
  or the system AND the SSOT required evidence type for that row exists.
- IMPLEMENTED / PARTIAL: Requirements where unit/property test code exists, but full API/system test is pending.
- SPECIFIED: Requirements documented with test criteria whose implementation or integration is scheduled.
- Column 'evidence' explicitly records the named test ID (file::test) for VERIFIED rows, or '-' otherwise.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSOT_PATH = ROOT / "docs" / "SSOT.md"
RTM_CSV_PATH = ROOT / "docs" / "rtm.csv"

EV_S1 = "docs/evidence/session-01-policy-engine.md"
EV_S2 = "docs/evidence/session-02-state-payments-api.md"
EV_S3 = "docs/evidence/session-03-db-mechanism-journeys.md"
EV_S4 = "docs/evidence/session-04-gemini-free-tier.md"
EV_S5 = "docs/evidence/session-05-live-sandbox-ai-pipeline.md"
EV_S6 = "docs/evidence/session-06-privacy-ops-release-gates.md"
EV_R1 = "docs/evidence/session-08-remediation-fase-1.md"
EV_R2 = "docs/evidence/session-09-remediation-fase-2.md"
EV_R3 = "docs/evidence/session-10-remediation-fase-3.md"
EV_R4 = "docs/evidence/session-11-remediation-fase-4.md"
EV_R5 = "docs/evidence/session-12-remediation-fase-5.md"

# Status mapping aligned with Task T7 and Section 20.1: (status, evidence_test_id, evidence_links, test_ids, notes)
STATUS_UPDATES: dict[str, tuple[str, str, str, str, str]] = {
    # =========================================================================
    # VERIFIED: Proved through API or system test AND SSOT evidence exists
    # =========================================================================
    "FR-09": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_fase4_ai_and_calibration.py::test_aud10_refund_curve_reconciled_across_api_mcp_defaults",
        f"{EV_S1};{EV_R4}",
        "test_order_snapshot_decision_replay_and_receipts;test_aud10_refund_curve_reconciled_across_api_mcp_defaults",
        "Verified: canonical refund curve snapshot enforced across policy engine, API, and MCP gateway without discrepancies (AUD-10, FR-09)",
    ),
    "FR-12": (
        "VERIFIED",
        "backend/tests/api/test_api_authz_and_mcp.py::test_api_contracts_idempotency_judge_mode_and_demo_guards",
        f"{EV_S2};{EV_R2}",
        "test_api_contracts_idempotency_judge_mode_and_demo_guards;test_order_passport_declaration_evidence_dropoff_and_receipts_flow",
        "Verified: return declaration validation, signed shopper tokens, and idempotency enforced via API (J-03)",
    ),
    "FR-37": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_fase5_observability_and_security.py::test_aud40_declaration_and_keep_offer_schema_alignment",
        f"{EV_S1};{EV_R5}",
        "test_mv18_keep_offer_posted_price_and_no_bounds;test_aud40_declaration_and_keep_offer_schema_alignment",
        "Verified: keep-offer posted-price formula and JSON schema alignment enforced across REST API (AUD-40, FR-37)",
    ),
    "FR-43": (
        "VERIFIED",
        "backend/tests/ops/test_privacy_observability_and_ops.py::test_client_side_face_blur_and_frontend_ux_a11y_gates",
        f"{EV_S2};{EV_S6}",
        "test_schemas_and_policy_config_validation;test_client_side_face_blur_and_frontend_ux_a11y_gates",
        "Verified: public view restricts condition facts; denylist strips buyer/owner PII",
    ),
    "FR-44": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_fase5_observability_and_security.py::test_aud40_declaration_and_keep_offer_schema_alignment",
        f"{EV_S1};{EV_R5}",
        "test_schemas_and_policy_config_validation;test_aud40_declaration_and_keep_offer_schema_alignment",
        "Verified: JSON Schema 2020-12 valid and published, API endpoints strictly aligned (AUD-40, FR-44)",
    ),
    "FR-45": (
        "VERIFIED",
        "backend/tests/api/test_api_authz_and_mcp.py::test_agent_token_issuance_and_operational_endpoint_guards",
        f"{EV_S2};{EV_R2}",
        "test_agent_token_issuance_and_operational_endpoint_guards;test_mcp_server_agent_journey_j05",
        "Verified: POST /v1/agent/tokens issues scoped HS256 signed agent tokens enforced across REST API and MCP gateway (AUD-41, FR-45)",
    ),
    "FR-61": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_fase5_observability_and_security.py::test_aud28_cryptographic_receipts_commitment_and_passport_chain",
        f"{EV_S2};{EV_R5}",
        "test_aud28_cryptographic_receipts_commitment_and_passport_chain;test_passport_signing_hash_chain_crypto_shred_and_transfer",
        "Verified: real Ed25519 platform signatures on condition receipts at intake verified cryptographically (AUD-28, FR-61)",
    ),
    "FR-69": (
        "VERIFIED",
        "backend/tests/api/test_full_rest_api_v1.py::test_appeals_resale_policies_and_simulator_views",
        f"{EV_S3};{EV_R2}",
        "test_appeals_resale_policies_and_simulator_views;test_f13_f14_f15_rental_cap_sla_credit_and_appeals",
        "Verified: independent reviewer rule and appeals filing/decision flow verified across REST API (AUD-29, FR-69)",
    ),
    "FR-72": (
        "VERIFIED",
        "backend/tests/api/test_remediation_fase3_persistence_and_concurrency.py::test_aud05_api_enforces_return_state_machine_guard",
        f"{EV_S2};{EV_R3}",
        "test_all_35_allowed_transitions_t_sm01_to_t_sm35;test_aud05_api_enforces_return_state_machine_guard",
        "Verified: 35 allowed return state transitions verified and enforced in API handlers (AUD-05, FR-72)",
    ),
    "FR-74": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_fase4_ai_and_calibration.py::test_aud17_no_passport_lane_reported_explicitly",
        f"{EV_S1};{EV_R4}",
        "test_fr13_evidence_scaling_and_fr74_no_passport_rules;test_aud17_no_passport_lane_reported_explicitly",
        "Verified: orders without origin passport explicitly report lane NO_PASSPORT with R1 timing (AUD-17, FR-74)",
    ),
    "FR-76": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_fase5_observability_and_security.py::test_aud28_cryptographic_receipts_commitment_and_passport_chain",
        f"{EV_S1};{EV_R5}",
        "test_passport_signing_hash_chain_crypto_shred_and_transfer;test_aud28_cryptographic_receipts_commitment_and_passport_chain",
        "Verified: verifiable condition receipts with passport hash chain and Ed25519 signatures (AUD-28, FR-76)",
    ),
    "FR-80": (
        "VERIFIED",
        "backend/tests/api/test_api_authz_and_mcp.py::test_api_contracts_idempotency_judge_mode_and_demo_guards",
        f"{EV_S2};{EV_R3}",
        "test_api_contracts_idempotency_judge_mode_and_demo_guards;test_aud05_api_enforces_return_state_machine_guard",
        "Verified: RFC 9457 error contracts verified across 401, 403, 404, 409, 422 errors",
    ),
    "FR-82": (
        "VERIFIED",
        "backend/tests/ops/test_privacy_observability_and_ops.py::test_privacy_deletion_request_flow_and_fraud_flag_retention",
        f"{EV_S1};{EV_S6};{EV_R5}",
        "test_passport_signing_hash_chain_crypto_shred_and_transfer;test_privacy_deletion_request_flow_and_fraud_flag_retention;test_aud27_aead_crypto_shredding_tamper_resistance",
        "Verified: authenticated encryption AEAD (XSalsa20-Poly1305) with tamper rejection and crypto-shred key destruction (AUD-27, FR-82)",
    ),
    "FR-91": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_tahap13_guards_and_caps.py::test_decide_release_receives_account_and_merchant_caps",
        f"{EV_S1};{EV_R4}",
        "test_mv23_and_mv25_identity_groups_and_value_weighted_promotion;test_aud13_single_step_trust_promotion;test_decide_release_receives_account_and_merchant_caps",
        "Verified: value-weighted, age-gated promotion strictly enforces single-step tier progression and cap scaling in release decisions (AUD-13, FR-91, RV2-03)",
    ),
    "FR-97": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_tahap12_schedulers.py::test_registered_jobs_include_sla_keep_offer_cusum_alerts_outbox",
        f"{EV_S2}",
        "test_all_35_allowed_transitions_t_sm01_to_t_sm35;test_registered_jobs_include_sla_keep_offer_cusum_alerts_outbox",
        "Verified: ESCALATED SLA auto-release job registered and executed by BackgroundAutomationScheduler (FR-97, RV2-02)",
    ),
    "NFR-04": (
        "VERIFIED",
        "backend/tests/api/test_remediation_fase3_persistence_and_concurrency.py::test_aud12_webhook_processor_atomic_deduplication_and_retry",
        f"{EV_S2};{EV_R3}",
        "test_webhook_deduplication_monotonicity_and_dispute_freeze;test_aud12_webhook_processor_atomic_deduplication_and_retry",
        "Verified: PayPal webhook deduplication and dispute freeze processed atomically without premature seen marking (AUD-12, NFR-04)",
    ),
    "NFR-08": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_fase5_observability_and_security.py::test_aud37_observability_middleware_headers_metrics_and_readiness",
        f"{EV_S2};{EV_R5}",
        "test_inv13_log_scrubber_removes_serials_and_pii;test_aud37_observability_middleware_headers_metrics_and_readiness",
        "Verified: runtime observability middleware with X-Request-Id, X-Trace-Id, structured scrubbed logs, Prometheus /v1/metrics and /v1/ready probe (AUD-37, NFR-08)",
    ),
    "NFR-11": (
        "VERIFIED",
        "backend/tests/api/test_api_authz_and_mcp.py::test_authorization_matrix_az01_to_az10",
        f"{EV_S2};{EV_R2}",
        "test_authorization_matrix_az01_to_az10",
        "Verified: zero trust tenant isolation with HMAC-SHA256 bearer tokens and object-level scoping (TZ-01, TZ-04, TZ-06); production external IdP login DEFERRED per RV3-05/API-04",
    ),
    "INV-01": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_tahap10_transactional_money_path.py::test_over_refund_via_evidence_endpoint_returns_409_and_persists_nothing",
        f"{EV_S2};{EV_R3}",
        "test_refund_ledger_outbox_idempotency_and_sandbox_guard;test_aud11_refund_ledger_prevents_concurrent_over_refund;test_over_refund_via_evidence_endpoint_returns_409_and_persists_nothing",
        "Verified: cumulative refund <= capture amount minor enforced under concurrent multi-threaded access via DB row locking and atomic pending balance (AUD-11, INV-01, RV2-04)",
    ),
    "INV-03": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_tahap11_outbox_executor.py::test_executor_confirms_refund_and_moves_pending_to_confirmed",
        EV_S2,
        "test_refund_ledger_outbox_idempotency_and_sandbox_guard;test_executor_confirms_refund_and_moves_pending_to_confirmed",
        "Verified: deterministic UUIDv5 request_id outbox dispatch to payment provider (INV-03, AUD-02)",
    ),
    "INV-04": (
        "VERIFIED",
        "backend/tests/api/test_remediation_fase3_persistence_and_concurrency.py::test_aud05_api_enforces_return_state_machine_guard",
        f"{EV_S2};{EV_R3}",
        "test_all_35_allowed_transitions_t_sm01_to_t_sm35;test_aud05_api_enforces_return_state_machine_guard",
        "Verified: 35 state machine transitions and forbidden transition matrix enforced through ReturnStateMachine across domain and REST API (AUD-05, INV-04)",
    ),
    "INV-07": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_tahap11_outbox_executor.py::test_executor_without_credentials_leaves_planned_and_never_reports_completed",
        f"{EV_S2};{EV_S5}",
        "test_refund_ledger_outbox_idempotency_and_sandbox_guard;test_executor_without_credentials_leaves_planned_and_never_reports_completed",
        "Verified: non-custodial architecture without PayPal Payouts or fund pooling; production client never fabricates success (INV-07, AUD-02)",
    ),
    "INV-10": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_fase4_ai_and_calibration.py::test_aud08_gross_misdeclaration_escalates_and_freezes_tranches",
        f"{EV_S1};{EV_R4}",
        "test_mv13_and_mv15_jurisdiction_caps_and_adjacent_no_penalty;test_aud08_gross_misdeclaration_escalates_and_freezes_tranches;test_aud09_protective_settlement_defaults_and_inv10_conformal_requirement;test_conformal_calibration_quantiles_and_gate_ag01",
        "Verified: gross misdeclaration penalties require statistical conformal exclusion at alpha_accuse and human confirmation; unreviewed discrepancies freeze tranches and route to ESCALATED (AUD-08, AUD-09, INV-10, ADR-017, AG-01)",
    ),
    "INV-12": (
        "VERIFIED",
        "backend/tests/api/test_api_authz_and_mcp.py::test_authorization_matrix_az01_to_az10",
        f"{EV_S2};{EV_R2}",
        "test_authorization_matrix_az01_to_az10;test_agent_token_issuance_and_operational_endpoint_guards",
        "Verified: cryptographically signed token engine (HS256) enforcing tenant isolation, role matrix AZ-01..AZ-10, BOLA guards, and signature verification (AUD-21, AUD-22, AUD-25, AUD-41); non-demo staff login and magic-link delivery DEFERRED (RV3-05, API-04)",
    ),
    "INV-16": (
        "VERIFIED",
        "backend/tests/remediation/test_remediation_fase5_observability_and_security.py::test_aud28_cryptographic_receipts_commitment_and_passport_chain",
        f"{EV_S1};{EV_R5}",
        "test_mv08_and_mv16_determinism_and_commit_reveal;test_aud28_cryptographic_receipts_commitment_and_passport_chain",
        "Verified: commit-reveal random audit draw with verifiable SHA-256 platform commitments and pre-intake commitments (AUD-28, INV-16)",
    ),

    # =========================================================================
    # IMPLEMENTED / PARTIAL: Unit/property test passing; integration/live pending
    # =========================================================================
    "FR-04": ("IMPLEMENTED", "-", EV_S1, "test_passport_signing_hash_chain_crypto_shred_and_transfer", "Unit: cryptographically secure nonce implemented; API wiring pending"),
    "FR-05": ("IMPLEMENTED", "-", EV_S1, "test_passport_signing_hash_chain_crypto_shred_and_transfer", "Unit: Ed25519 signing and hash chain implemented; API wiring pending"),
    "FR-06": ("IMPLEMENTED", "-", EV_S1, "test_passport_signing_hash_chain_crypto_shred_and_transfer", "Unit: origin grade records implemented; accessories checklist pending"),
    "FR-10": ("IMPLEMENTED", "-", EV_S1, "test_mv13_and_mv15_jurisdiction_caps_and_adjacent_no_penalty", "Unit: jurisdiction cap resolver implemented; storefront pending"),
    "FR-13": ("IMPLEMENTED", "-", EV_S1, "test_fr13_evidence_scaling_and_fr74_no_passport_rules", "Unit: evidence scaling rules implemented"),
    "FR-15": ("IMPLEMENTED", "-", EV_S5, "test_ocr_forensics_nonce_retakes_and_output_guard", "Unit: output guard implemented; agent intake integration pending"),
    "FR-18": ("IMPLEMENTED", "-", EV_S5, "test_ocr_forensics_nonce_retakes_and_output_guard", "Unit: rule-based forensics implemented; full media layer pending"),
    "FR-19": ("IMPLEMENTED", "-", EV_S1, "test_mv19_and_mv22_standard_routing_and_refile", "Unit: hard failure ESCALATED routing implemented in engine"),
    "FR-21": ("IMPLEMENTED", "-", EV_S1, "test_mv01_fast_output_satisfies_safety_condition;test_mv02_minimal_p", "Unit: minimal audit probability p computed matching Section 8.8"),
    "FR-23": ("IMPLEMENTED", "-", EV_S1, "test_mv04_mv05_mv06_settlement_tranches_and_bounds", "Unit: settlement tranche math implemented; gross review pending J-08"),
    "FR-24": ("IMPLEMENTED", "-", EV_S1, "test_mv13_and_mv15_jurisdiction_caps_and_adjacent_no_penalty", "Unit: jurisdiction holdback tables implemented"),
    "FR-25": ("IMPLEMENTED", "-", EV_S1, "test_mv13_and_mv15_jurisdiction_caps_and_adjacent_no_penalty", "Unit: gross misdeclaration flag logic implemented; conformal test pending J-08"),
    "FR-26": ("IMPLEMENTED", "-", EV_S1, "test_mv13_and_mv15_jurisdiction_caps_and_adjacent_no_penalty", "Unit: single grade difference settled without penalty"),
    "FR-27": ("IMPLEMENTED", "-", EV_S1, "test_order_snapshot_decision_replay_and_receipts", "Unit: decision record builder implemented"),
    "FR-28": ("IMPLEMENTED", "-", EV_S1, "test_mv04_mv05_mv06_settlement_tranches_and_bounds", "Unit: under-declaration top-up tranche math implemented"),
    "FR-30": ("IMPLEMENTED", "-", EV_S2, "test_custody_ledger_attribution_and_records_only", "Unit: custody attribution to earliest interval implemented"),
    "FR-31": ("IMPLEMENTED", "-", EV_S2, "test_custody_ledger_attribution_and_records_only;test_inv05_ai_packages_never_import_payments", "Unit: custody liability is records-only, no money transfer"),
    "FR-42": ("IMPLEMENTED", "-", EV_S1, "test_passport_signing_hash_chain_crypto_shred_and_transfer", "Unit: passport transfer signature chain implemented"),
    "FR-53": ("IMPLEMENTED", "-", EV_S3, "test_f12_serial_registry_keyed_hmac_and_swap_detection", "Unit: keyed HMAC serial swap detection implemented"),
    "FR-55": ("IMPLEMENTED", "-", EV_S3, "test_f13_f14_f15_rental_cap_sla_credit_and_appeals", "Unit: rental cap <= 3 days implemented"),
    "FR-57": ("IMPLEMENTED", "-", EV_S1, "test_mv23_and_mv25_identity_groups_and_value_weighted_promotion", "Unit: identity velocity groups implemented"),
    "FR-58": ("IMPLEMENTED", "-", EV_S1, "test_golden_e1_trusted_r0_declared_b", "Unit: golden E1 instant release tranche math implemented"),
    "FR-60": ("IMPLEMENTED", "-", EV_S1, "test_golden_e5_eu_new_infeasible_routes_standard", "Unit: EU new customer standard routing implemented"),
    "FR-62": ("IMPLEMENTED", "-", EV_S1, "test_mv17_cusum_account_monitor", "Unit: CUSUM account monitoring implemented"),
    "FR-65": ("IMPLEMENTED", "-", EV_S5, "test_ocr_forensics_nonce_retakes_and_output_guard", "Unit: unreadable vs mismatched nonce handled differently"),
    "FR-78": ("IMPLEMENTED", "-", EV_S1, "test_mv18_keep_offer_posted_price_and_no_bounds", "Unit: keep-offer inventory release implemented"),
    "FR-81": ("DEFERRED", "-", EV_S2, "test_api_contracts_idempotency_judge_mode_and_demo_guards", "DEFERRED: Non-demo authentication (staff login & magic link) deferred per RV3-05/API-04; demo clock active in DEMO_MODE"),
    "FR-84": ("IMPLEMENTED", "-", EV_S1, "test_golden_e5_eu_new_infeasible_routes_standard", "Unit: jurisdiction tables for F and curves implemented"),
    "FR-87": ("IMPLEMENTED", "-", EV_S1, "test_golden_e1_trusted_r0_declared_b", "Unit: closed-form X_max constraint solver implemented"),
    "FR-88": ("IMPLEMENTED", "-", EV_S1, "test_mv19_and_mv22_standard_routing_and_refile", "Unit: standard routing and refile rules implemented"),
    "FR-89": ("IMPLEMENTED", "-", EV_S1, "test_mv01_fast_output_satisfies_safety_condition", "Unit: relative safety margin mu satisfied on X_max across grid"),
    "FR-90": ("IMPLEMENTED", "-", EV_S1, "test_schemas_and_policy_config_validation", "Unit: typed policy configuration validation implemented"),
    "FR-92": ("IMPLEMENTED", "-", EV_S1, "test_mv14_caps_never_exceeded", "Unit: exposure caps binding logic implemented"),
    "FR-93": ("IMPLEMENTED", "-", EV_S1, "test_mv23_and_mv25_identity_groups_and_value_weighted_promotion", "Unit: identity velocity groups implemented"),
    "FR-94": ("IMPLEMENTED", "-", EV_S6, "test_privacy_deletion_request_flow_and_fraud_flag_retention;test_fraud_flag_registry_salt_guard_and_retention", "Unit: persistent pseudonymized fraud flags surviving deletion implemented with >=32 byte salt guard"),
    "FR-95": ("IMPLEMENTED", "-", EV_S1, "test_mv08_and_mv16_determinism_and_commit_reveal", "Unit: audit commitment and reveal implemented"),
    "FR-100": ("IMPLEMENTED", "-", EV_S1, "test_mv20_fifth_percentile_conservative_vs_mean", "Unit: conservative 5th percentile calibration bounds implemented"),
    "FR-102": ("IMPLEMENTED", "-", EV_S1, "test_mv12_rule_based_simulator_analytic_agreement", "Unit: rule-based simulator and analytic solver implemented"),
    "FR-103": ("IMPLEMENTED", "-", EV_S1, "test_mv17_cusum_account_monitor", "Unit: CUSUM drift detection implemented"),
    "INV-02": ("IMPLEMENTED", "-", EV_S2, "test_refund_ledger_outbox_idempotency_and_sandbox_guard", "Unit: merchant/capture binding implemented in ledger"),
    "INV-05": ("IMPLEMENTED", "-", EV_S1, "test_inv05_ai_packages_never_import_payments", "Unit: static AST check confirms backend.ai never imports backend.payments"),
    "INV-08": ("IMPLEMENTED", "-", EV_S2, "test_schemas_and_policy_config_validation", "Unit: records-only custody without insurance or loss-pooling constructs"),
    "INV-09": ("IMPLEMENTED", "-", EV_S1, "test_passport_signing_hash_chain_crypto_shred_and_transfer", "Unit: hash chain tamper evidence and salt length checks implemented"),
    "INV-11": ("IMPLEMENTED", "-", EV_S1, "test_mv13_and_mv15_jurisdiction_caps_and_adjacent_no_penalty", "Unit: refund timeline bounded by jurisdiction caps"),
    "INV-13": ("IMPLEMENTED", "-", f"{EV_S2};{EV_S5}", "test_inv13_log_scrubber_removes_serials_and_pii;test_config_registry_loads_and_masks_secrets", "Unit: log scrubber and >=32 byte salt guards implemented"),
    "INV-14": ("IMPLEMENTED", "-", EV_S1, "test_mv14_caps_never_exceeded", "Unit: exposure caps never exceeded in release solver"),
    "INV-15": ("IMPLEMENTED", "-", EV_S1, "test_mv13_and_mv15_jurisdiction_caps_and_adjacent_no_penalty", "Unit: adjacent grade difference carries zero penalty"),
    "INV-17": ("IMPLEMENTED", "-", EV_S1, "test_mv19_and_mv22_standard_routing_and_refile", "Unit: re-filed returns routed to STANDARD implemented"),
    "INV-18": ("IMPLEMENTED", "-", EV_S1, "test_mv24_degraded_modes_never_increase_x_or_advance_timing", "Unit: degraded modes FB-01..FB-07 never increase X or advance timing"),
    "NFR-12": ("IMPLEMENTED", "-", EV_S5, "test_config_registry_loads_and_masks_secrets", "Unit: uv.lock and compose configured; SecretStr masking verified"),
}


def parse_markdown_table(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        s = line.strip()
        if not s.startswith("|") or not s.endswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(re.match(r"^:?-{2,}:?$", c) for c in cells):
            continue
        rows.append(cells)
    return rows


def extract_section(text: str, heading_prefix: str) -> list[str]:
    lines = text.splitlines()
    in_sec = False
    out: list[str] = []
    level = len(heading_prefix.split()[0])
    for line in lines:
        if line.startswith(heading_prefix):
            in_sec = True
            continue
        if in_sec and re.match(rf"^#{{1,{level}}}\s+", line):
            break
        if in_sec:
            out.append(line)
    return out


def generate_rtm_csv(ssot_text: str) -> int:
    sec_fr = extract_section(ssot_text, "### 23.2 Functional requirements")
    sec_nfr = extract_section(ssot_text, "### 23.3 Non-functional requirements")
    sec_inv = extract_section(ssot_text, "### 23.4 Invariants")

    fr_rows = parse_markdown_table(sec_fr)[1:]
    nfr_rows = parse_markdown_table(sec_nfr)[1:]
    inv_rows = parse_markdown_table(sec_inv)[1:]

    RTM_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with RTM_CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "kind",
                "feature",
                "implementation",
                "required_evidence",
                "acceptance_reference",
                "status",
                "evidence",
                "evidence_links",
                "test_ids",
                "notes",
            ]
        )
        for r in fr_rows:
            req_id, feat, impl, evid, acc, default_status = r[0], r[1], r[2], r[3], r[4], r[5]
            st, evid_test, ev_link, tids, notes = STATUS_UPDATES.get(
                req_id,
                ("SPECIFIED", "-", "", "", "Awaiting milestone implementation per Section 14.1"),
            )
            writer.writerow([req_id, "FR", feat, impl, evid, acc, st, evid_test, ev_link, tids, notes])
            total += 1
        for r in nfr_rows:
            req_id, impl, evid, acc, default_status = r[0], r[1], r[2], r[3], r[4]
            st, evid_test, ev_link, tids, notes = STATUS_UPDATES.get(
                req_id,
                ("SPECIFIED", "-", "", "", "Awaiting milestone implementation per Section 14.1"),
            )
            writer.writerow([req_id, "NFR", "ALL", impl, evid, acc, st, evid_test, ev_link, tids, notes])
            total += 1
        for r in inv_rows:
            inv_id, impl, evid, default_status = r[0], r[1], r[2], r[3]
            st, evid_test, ev_link, tids, notes = STATUS_UPDATES.get(
                inv_id,
                ("SPECIFIED", "-", "", "", "Awaiting milestone implementation per Section 14.1"),
            )
            writer.writerow([inv_id, "INV", "ALL", impl, evid, "Section 9", st, evid_test, ev_link, tids, notes])
            total += 1
    return total


def main() -> None:
    text = SSOT_PATH.read_text(encoding="utf-8")
    n_rtm = generate_rtm_csv(text)
    print(f"Synchronized {n_rtm} RTM rows in {RTM_CSV_PATH}.")


if __name__ == "__main__":
    main()
