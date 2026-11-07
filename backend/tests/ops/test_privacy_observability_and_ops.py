"""Tests for Privacy Lifecycle (Section 33), Observability & Runbooks (Section 34),
Backup/Restore & Clean-Env Drills (Sections 35-36), Frontend UX/A11y/Perf Budgets (Sections 39-43),
and Release Gate Evaluators (Section 27 & 49).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.domain.crypto_shred import encrypt_subject_payload, generate_subject_key
from backend.domain.fraud_flags import FraudFlagRegistry
from backend.observability.metrics import (
    MetricsRegistry,
    evaluate_alerts,
    format_structured_log,
    get_runbook,
)
from backend.ops.drills import (
    evaluate_release_gates,
    run_backup_restore_drill,
    run_clean_env_judge_mode_check,
    verify_client_side_face_blur,
    verify_frontend_ux_and_a11y_gates,
)
from backend.privacy.lifecycle import (
    DeletionRequestStore,
    SubjectDataRecord,
    execute_deletion_request,
)


def test_privacy_deletion_request_flow_and_fraud_flag_retention() -> None:
    """Section 33.4, NFR-05, FR-82, FR-94, TM-25:
    - Deletes DC-1 (raw media), DC-2 (derived media), DC-5 (contact data)
    - Crypto-shreds subject key (FR-82) so DC-3 payload_ciphertext is unreadable while item hash remains
    - Unlinks DC-4 (cross-merchant registry)
    - Pseudonymizes DC-6 (financial records kept 7 years)
    - Retains DC-12 (persistent fraud flags under legitimate-interest fraud prevention)
    """
    key_id, key_bytes = generate_subject_key("subj_del_01")
    key_store = {key_id: key_bytes}
    ciphertext = encrypt_subject_payload(
        key_id=key_id,
        key_bytes=key_bytes,
        plaintext_dict={"buyer_email": "alice@example.com", "serial": "SN-900"},
    )

    store = DeletionRequestStore()
    store.register_subject(
        SubjectDataRecord(
            subject_id="subj_del_01",
            subject_key_id=key_id,
            raw_media_keys=["raw/ret_01/video.mp4", "raw/ret_01/photo1.jpg"],
            derived_media_keys=["derived/ret_01/thumb1.jpg"],
            passport_ciphertext=ciphertext,
            passport_structural_hash="sha256:structural_chain_hash_01",
            cross_merchant_opt_in=True,
            contact_email="alice@example.com",
            financial_ledger_ids=["pa_001", "pa_002"],
            persistent_fraud_flags=["CONFIRMED_GROSS_MISDECLARATION"],
            has_open_dispute=False,
        )
    )

    result = execute_deletion_request(
        store=store,
        key_store=key_store,
        subject_id="subj_del_01",
        requested_at_epoch=1761900000,
    )

    assert result.status == "COMPLETED"
    assert result.dc1_raw_media_deleted is True
    assert result.dc2_derived_media_deleted is True
    assert result.dc3_subject_key_shredded is True
    assert result.dc3_structural_hash_preserved == "sha256:structural_chain_hash_01"
    assert result.dc4_cross_merchant_unlinked is True
    assert result.dc5_contact_deleted is True
    assert result.dc6_financial_pseudonymized is True
    assert result.dc12_fraud_flags_retained == ["CONFIRMED_GROSS_MISDECLARATION"]
    assert key_id not in key_store


def test_privacy_deletion_blocked_under_open_dispute_legal_hold() -> None:
    """Section 33.4 step 6: Legal hold blocks deletion of DC-1, DC-2, DC-3, DC-6 when an open PayPal dispute exists."""
    key_id, key_bytes = generate_subject_key("subj_hold_01")
    key_store = {key_id: key_bytes}
    ciphertext = encrypt_subject_payload(
        key_id=key_id,
        key_bytes=key_bytes,
        plaintext_dict={"buyer_email": "dispute@example.com"},
    )

    store = DeletionRequestStore()
    store.register_subject(
        SubjectDataRecord(
            subject_id="subj_hold_01",
            subject_key_id=key_id,
            raw_media_keys=["raw/ret_02/video.mp4"],
            derived_media_keys=["derived/ret_02/thumb1.jpg"],
            passport_ciphertext=ciphertext,
            passport_structural_hash="sha256:structural_chain_hash_02",
            cross_merchant_opt_in=True,
            contact_email="dispute@example.com",
            financial_ledger_ids=["pa_003"],
            persistent_fraud_flags=[],
            has_open_dispute=True,
        )
    )

    result = execute_deletion_request(
        store=store,
        key_store=key_store,
        subject_id="subj_hold_01",
        requested_at_epoch=1761900000,
    )

    assert result.status == "LEGAL_HOLD_ACTIVE"
    assert result.dc1_raw_media_deleted is False
    assert result.dc3_subject_key_shredded is False
    assert key_id in key_store
    # Contact marketing/cross-merchant opt-in can still be unlinked immediately
    assert result.dc4_cross_merchant_unlinked is True


def test_fraud_flag_registry_salt_guard_and_retention() -> None:
    """FR-94 & INV-13: FraudFlagRegistry requires >= 32-byte salt and retains flags for 24 months."""
    import pytest

    with pytest.raises(ValueError, match="INV-13"):
        FraudFlagRegistry(salt="too_short_salt")

    valid_salt = "proper_32_bytes_salt_for_fraud_flag_01"
    reg = FraudFlagRegistry(salt=valid_salt)
    flag = reg.record_confirmed_fraud(
        flag_id="flg_01",
        merchant_id="m_01",
        raw_identifier="shopper@example.com",
        flag_type="GROSS_MISDECLARATION",
        source_decision_id="dec_01",
    )
    assert flag.flag_id == "flg_01"
    assert len(flag.salted_hash) == 64
    assert flag.retained_until > "2028-01-01"
    assert reg.is_flagged("shopper@example.com") is True
    assert reg.is_flagged("clean@example.com") is False


def test_observability_metrics_alerts_and_runbooks() -> None:
    """Section 34 (NFR-08, AL-01..AL-07, RB-01..RB-06):
    Structured JSON logs, metric counters/histograms, alert firing rules, and runbook lookup.
    """
    log_entry = format_structured_log(
        level="INFO",
        service="proofreturn-api",
        message="Refund tranche R0 confirmed",
        request_id="req_101",
        trace_id="tr_202",
        merchant_id="m_001",
        return_id="ret_303",
        decision_id="dec_404",
        payment_action_id="pa_505",
        paypal_debug_id="pp_dbg_606",
        model_id="gemini-3-flash-preview",
        prompt_id="condition_grading_v1",
    )
    assert log_entry["service"] == "proofreturn-api"
    assert log_entry["payment_action_id"] == "pa_505"
    assert log_entry["paypal_debug_id"] == "pp_dbg_606"

    metrics = MetricsRegistry()
    metrics.observe_histogram("refund_latency_seconds", 4.2, labels={"lane": "FAST"})
    metrics.inc_counter("payment_actions", labels={"action_type": "REFUND", "status": "CONFIRMED"})
    metrics.set_gauge("reconciliation_mismatches", 1)
    metrics.set_gauge("unknown_payment_action_max_age_minutes", 20)
    metrics.set_gauge("webhook_verify_failures_5m", 15)
    metrics.set_gauge("grading_model_error_rate_10m", 0.08)
    metrics.set_gauge("review_queue_backlog", 55)
    metrics.set_gauge("audit_rate_deviation_sigma", 3.5)
    metrics.set_gauge("escalated_within_24h_of_deadline", 2)

    fired_alerts = evaluate_alerts(metrics)
    fired_ids = {a.alert_id for a in fired_alerts}
    assert fired_ids == {"AL-01", "AL-02", "AL-03", "AL-04", "AL-05", "AL-06", "AL-07"}

    for rb_id in ("RB-01", "RB-02", "RB-03", "RB-04", "RB-05", "RB-06"):
        rb = get_runbook(rb_id)
        assert rb.runbook_id == rb_id
        assert len(rb.steps) >= 3


def test_backup_restore_drill_and_clean_env_judge_mode() -> None:
    """Sections 35.4, 36 (BK-01..BK-07, NFR-07, NFR-13, NFR-15):
    Deterministic snapshot + restore drill with REC-01..REC-03 reconciliation and Judge Mode check.
    """
    drill = run_backup_restore_drill(
        snapshot_id="snap_demo_gold_01",
        simulated_rpo_seconds=120,
        simulated_rto_seconds=180,
    )
    assert drill.passed is True
    assert drill.rpo_seconds <= 86400  # <= 24h (NFR-13)
    assert drill.rto_seconds <= 3600   # <= 1h (NFR-13)
    assert drill.post_restore_reconciliation_clean is True
    assert drill.money_actions_reenabled is True

    # Failed RPO drill blocks money actions re-enabling
    failed_rpo_drill = run_backup_restore_drill(
        snapshot_id="snap_failed_01",
        simulated_rpo_seconds=90000,
        simulated_rto_seconds=180,
    )
    assert failed_rpo_drill.passed is False
    assert failed_rpo_drill.money_actions_reenabled is False

    # Dirty post-restore reconciliation blocks money actions re-enabling (BK-07)
    failed_rec_drill = run_backup_restore_drill(
        snapshot_id="snap_dirty_rec",
        simulated_rpo_seconds=120,
        simulated_rto_seconds=180,
        reconciliation_report={"REC-01": {"passed": False}},
    )
    assert failed_rec_drill.passed is False
    assert failed_rec_drill.post_restore_reconciliation_clean is False
    assert failed_rec_drill.money_actions_reenabled is False

    judge_check = run_clean_env_judge_mode_check()
    assert judge_check.passed is True
    assert judge_check.requires_gpu is False
    assert judge_check.requires_external_llm_keys is False
    assert judge_check.bootstrap_under_20_minutes is True

    # Clean-env bootstrap exceeding 20m fails
    slow_bootstrap_check = run_clean_env_judge_mode_check(bootstrap_duration_minutes=25.0)
    assert slow_bootstrap_check.passed is False
    assert slow_bootstrap_check.bootstrap_under_20_minutes is False


def test_client_side_face_blur_and_frontend_ux_a11y_gates() -> None:
    """FR-16, TM-12, Sections 39-43 (NFR-06, NFR-09, NFR-10, VA-01..VA-09, A11Y-01..A11Y-09):
    Verifies client-side face blur guard, CSS tokens, WCAG 2.2 AA contrast, and frontend bundle budgets.
    """
    # Reject unblurred frame containing detected face
    rejected = verify_client_side_face_blur(
        faces_detected=1,
        client_blur_applied=False,
        blur_latency_ms=18.0,
    )
    assert rejected.accepted is False
    assert rejected.reason == "UNBLURRED_FACE_REJECTED"

    # Accept blurred frame within 50ms budget (Section 43)
    accepted = verify_client_side_face_blur(
        faces_detected=1,
        client_blur_applied=True,
        blur_latency_ms=22.5,
    )
    assert accepted.accepted is True

    ux_report = verify_frontend_ux_and_a11y_gates()
    assert ux_report.passed is True
    assert ux_report.wcag_aa_contrast_passed is True
    assert ux_report.performance_budgets_passed is True
    assert ux_report.shared_components_count >= 21


def test_release_gates_g0_through_g5_and_api_endpoints() -> None:
    """Section 27 (G0..G5), Section 36 (POST /v1/demo/reset), Section 33 (POST /v1/privacy/deletion-requests)."""
    gates = evaluate_release_gates()
    assert all(g.passed for g in gates)
    assert [g.gate_id for g in gates] == ["G0", "G1", "G2", "G3", "G4", "G5"]

    client = TestClient(app)

    # Test POST /v1/demo/reset (staff-only in DEMO_MODE, AUD-25 signed token)
    shopper_tok = mint_shopper_token(shopper_id="shopper_01", order_id="ord_demo_1", merchant_id="m_001")
    admin_tok = mint_staff_token(user_id="admin_01", merchant_id="m_001", role="MERCHANT_ADMIN")

    resp_forbidden = client.post(
        "/v1/demo/reset",
        headers={"Authorization": f"Bearer {shopper_tok}"},
    )
    assert resp_forbidden.status_code == 403

    resp_ok = client.post(
        "/v1/demo/reset",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert resp_ok.status_code == 200
    data = resp_ok.json()
    assert data["status"] == "RESET_COMPLETE"
    assert data["reconciliation_clean"] is True

    # Test POST /v1/privacy/deletion-requests
    shopper_del_tok = mint_shopper_token(shopper_id="subj_api_01", order_id="ord_demo_1", merchant_id="m_001")
    del_resp = client.post(
        "/v1/privacy/deletion-requests",
        json={"subject_id": "subj_api_01", "has_open_dispute": False},
        headers={"Authorization": f"Bearer {shopper_del_tok}"},
    )
    assert del_resp.status_code == 200
    del_data = del_resp.json()
    assert del_data["status"] == "COMPLETED"
    assert del_data["dc3_subject_key_shredded"] is True
