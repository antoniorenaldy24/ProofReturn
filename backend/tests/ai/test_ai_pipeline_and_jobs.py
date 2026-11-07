"""Tests for Config Registry (Section 35.1), AI Pipeline Modules (FR-03, FR-15, FR-18, FR-20, FR-36, FR-65, FR-66), Jobs (FR-83, NFR-05), and API Extensions (FR-02, FR-50, FR-51, FR-52, FR-98, NFR-02, NFR-16)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.ai.pipeline.forensics import evaluate_media_forensics, run_redteam_suite
from backend.ai.pipeline.nonce_checker import RetakeTracker, verify_challenge_nonce
from backend.ai.pipeline.ocr import extract_and_match_serial
from backend.ai.pipeline.output_guard import validate_intake_explanation
from backend.ai.valuation.resale_model import evaluate_valuation_mape, predict_resale_value_minor
from backend.api.app import create_app
from backend.auth.tokens import mint_staff_token
from backend.config import ProofReturnSettings
from backend.jobs.anchor import create_daily_anchor_token
from backend.jobs.retention import run_media_retention_job


@pytest.mark.req("NFR-12", "INV-07", "INV-13", "FR-96")
def test_config_registry_loads_and_masks_secrets() -> None:
    """Section 35.1: ProofReturnSettings loads from environment/.env, enforces TM-16/TM-24/salt guards, and masks SecretStr."""
    settings = ProofReturnSettings()
    assert settings.paypal_base_url.startswith("https://api")
    assert "sandbox.paypal.com" in settings.paypal_base_url
    assert len(settings.serial_hash_salt.get_secret_value()) >= 32
    assert len(settings.payer_hash_salt.get_secret_value()) >= 32
    # SecretStr never leaks in repr/str
    repr_str = repr(settings)
    assert settings.serial_hash_salt.get_secret_value() not in repr_str

    # TM-24 guard: carrier_events_manual=True with demo_mode=False must fail validation
    with pytest.raises(ValueError, match="TM-24"):
        ProofReturnSettings(demo_mode=False, carrier_events_manual=True)


@pytest.mark.req("FR-03", "FR-15", "FR-18", "FR-20", "FR-65", "FR-66", "NFR-02")
def test_ocr_forensics_nonce_retakes_and_output_guard() -> None:
    """FR-03, FR-15, FR-18, FR-20, FR-65, FR-66: OCR match on >=3 products, forensics, red-team, nonce vs unreadable, output guard."""
    # FR-03: Serial OCR match across >= 3 demo products
    for sku, raw_text, expected_sn in [
        ("PR-HP-XM5", "Model WH-1000XM5 S/N: SN-XM5-0001 Made in Malaysia", "SN-XM5-0001"),
        ("PR-KB-Q1P", "Keychron Q1 Pro Serial# KC-Q1P-8821", "KC-Q1P-8821"),
        ("PR-CM-A67", "Sony Alpha 6700 Body SN: SONY-A67-4410", "SONY-A67-4410"),
    ]:
        ocr_res = extract_and_match_serial(sku=sku, ocr_text=raw_text, expected_serial=expected_sn)
        assert ocr_res.matched is True
        assert ocr_res.extracted_serial == expected_sn

    # FR-15: Intake explanation guard blocks outcome promises
    ok_msg = validate_intake_explanation(
        "Thank you for submitting your evidence. Our policy engine will now calculate your release schedule."
    )
    assert ok_msg["valid"] is True
    bad_msg = validate_intake_explanation(
        "You are guaranteed an instant refund right now with zero inspection!"
    )
    assert bad_msg["valid"] is False
    assert bad_msg["violation"] == "OUTCOME_PROMISE_FORBIDDEN"

    # FR-18 & FR-20: Forensics scorer and offline red-team evaluation
    for_res = evaluate_media_forensics(
        evidence_sha256="a" * 64,
        exif_present=True,
        ela_anomaly_score=0.04,
        nonce_matched=True,
    )
    assert for_res.authenticity_score >= 0.90
    assert for_res.hard_fail is False

    rt_report = run_redteam_suite()
    assert rt_report["total_cases"] >= 6
    assert rt_report["false_fast_lane_approvals"] == 0
    assert rt_report["p95_latency_seconds"] <= 20.0

    # FR-65: Unreadable nonce vs mismatched nonce handled differently
    unread = verify_challenge_nonce(expected_nonce="PR-9482", observed_text="", blur_score=0.85)
    assert unread.status == "NONCE_UNREADABLE"
    assert unread.allow_retake is True
    assert unread.escalate_immediately is False

    mismatch = verify_challenge_nonce(expected_nonce="PR-9482", observed_text="PR-1111", blur_score=0.10)
    assert mismatch.status == "NONCE_MISMATCH"
    assert mismatch.allow_retake is False
    assert mismatch.escalate_immediately is True

    # FR-66: Retake limits (3 per step, 8 per return) & generic feedback without threshold leakage
    tracker = RetakeTracker(max_per_step=3, max_per_return=8)
    for _ in range(3):
        fb = tracker.record_retake(step="photo_front")
        assert fb["allowed"] is True
        assert "threshold" not in fb["user_message"].lower()
    fb_exceeded = tracker.record_retake(step="photo_front")
    assert fb_exceeded["allowed"] is False
    assert fb_exceeded["route_to"] == "STANDARD"


@pytest.mark.req("FR-36")
def test_f08_valuation_model_and_mape_target() -> None:
    """FR-36 & Section 11.4: Valuation model predicts open-box resale value and meets MAPE <= 12% on curated comps."""
    pred = predict_resale_value_minor(sku="PR-HP-XM5", retail_price_minor=38000, verified_grade="B", age_days=14)
    assert 25000 <= pred <= 36000
    metrics = evaluate_valuation_mape()
    assert metrics["mape"] <= 0.12


@pytest.mark.req("FR-83", "NFR-05")
def test_retention_job_and_daily_anchor_token() -> None:
    """NFR-05 & FR-83: Retention job shreds expired media while preserving hashes; anchor job creates signed daily root."""
    ret_res = run_media_retention_job(
        records=[
            {"evidence_id": "ev_old", "age_days": 95, "evidence_sha256": "1" * 64, "blob_uri": "s3://media/ev_old.jpg"},
            {"evidence_id": "ev_new", "age_days": 10, "evidence_sha256": "2" * 64, "blob_uri": "s3://media/ev_new.jpg"},
        ],
        retention_days=90,
    )
    assert ret_res["shredded_count"] == 1
    assert ret_res["preserved_hashes_count"] == 2

    with pytest.raises(ValueError, match="INV-13"):
        create_daily_anchor_token(date_str="2026-10-31", head_hashes=["a" * 64], signing_seed=b"short_seed")

    test_seed = b"test_signing_seed_for_anchor_01!"
    anchor = create_daily_anchor_token(date_str="2026-10-31", head_hashes=["a" * 64, "b" * 64], signing_seed=test_seed)
    assert anchor["date"] == "2026-10-31"
    assert len(anchor["merkle_root"]) == 64
    assert len(anchor["signature"]) > 0


@pytest.mark.req("FR-02", "FR-50", "FR-51", "FR-52", "FR-66", "FR-98", "NFR-16")
def test_api_passports_review_queue_and_simulator_endpoints() -> None:
    """FR-02, FR-50, FR-51, FR-52, FR-98, NFR-16: Verify passport mint/verify, review queue, and /v1/simulate."""
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    packer_tok = mint_staff_token(user_id="packer_01", merchant_id="merch_a", role="PACKER")
    reviewer_tok = mint_staff_token(user_id="rev_01", merchant_id="merch_a", role="REVIEWER")
    operator_tok = mint_staff_token(user_id="op_01", merchant_id="merch_a", role="MERCHANT_OPERATOR")

    # FR-02 & FR-98: Mint FULL electronics passport with functional baseline and verify hash chain
    r_mint = client.post(
        "/v1/passports",
        headers={"Authorization": f"Bearer {packer_tok}", "Idempotency-Key": "idem_mint_01"},
        json={
            "passport_id": "pass_minted_01",
            "sku": "PR-HP-XM5",
            "tier": "FULL",
            "origin_grade": "A",
            "weight_g": 250,
            "self_test_passed": True,
        },
    )
    assert r_mint.status_code == 201
    mint_data = r_mint.json()
    assert mint_data["self_test_passed"] is True
    assert len(mint_data["head_hash"]) == 64

    r_ver = client.get("/v1/passports/pass_minted_01/verify")
    assert r_ver.status_code == 200
    assert r_ver.json()["chain_valid"] is True

    # FR-50: Review queue lists escalated returns
    r_queue = client.get(
        "/v1/review/queue",
        headers={"Authorization": f"Bearer {reviewer_tok}"},
    )
    assert r_queue.status_code == 200
    assert len(r_queue.json()["items"]) >= 1

    # FR-52 & NFR-16: Simulator endpoint returns feasibility map, ROI, and cost/latency metrics
    r_sim = client.post(
        "/v1/simulate",
        headers={"Authorization": f"Bearer {operator_tok}"},
        json={"declared_grade": "B", "monthly_returns": 1000},
    )
    assert r_sim.status_code == 200
    sim_data = r_sim.json()
    assert "feasibility_map" in sim_data
    assert "roi" in sim_data
    assert "cost_latency_metrics" in sim_data


@pytest.mark.live_model
@pytest.mark.req("FR-18", "NFR-02")
def test_live_gemini_assessment_if_configured() -> None:
    """Run a real live multimodal grading check via Gemini API if GEMINI_API_KEY is configured in .env."""
    import time
    from backend.ai.pipeline.evaluator import assess_return_evidence

    settings = ProofReturnSettings()
    if not settings.has_live_gemini_key:
        pytest.skip("Live GEMINI_API_KEY not configured; skipping live call.")

    dummy_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    res = None
    for attempt in range(3):
        res = assess_return_evidence(
            mode="live",
            evidence_sha256="9" * 64,
            declared_grade="B",
            text_in_media="WH-1000XM5 minor scuff on headband, case included",
            provider="gemini",
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            image_base64=dummy_png_b64,
        )
        if "DEGRADED_FB01_VLM_FALLBACK" not in res.forensic_flags:
            break
        time.sleep(2.0)

    assert res is not None
    assert res.predicted_grade in {"A", "B", "C", "D", "DEF"}
    assert res.replay_label.startswith("LIVE (")
    assert 0.0 <= res.authenticity_score <= 1.0
    assert "DEGRADED_FB01_VLM_FALLBACK" not in res.forensic_flags
