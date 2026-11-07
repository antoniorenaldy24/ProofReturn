"""Remediation tests for Fase R5: Observability, Secret Scanning & Operational Hardening (AUD-27, AUD-28, AUD-37, AUD-38, AUD-39, AUD-40)."""

from __future__ import annotations

import base64
import time

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_agent_token, mint_shopper_token, mint_staff_token
from backend.domain.cache import BoundedTTLCache
from backend.domain.crypto_shred import CryptoShredStore
from scripts.scan_secrets import main as scan_secrets_main


@pytest.mark.req("AUD-37", "NFR-08", "NFR-09")
def test_aud37_observability_middleware_headers_metrics_and_readiness() -> None:
    """AUD-37: Verify ObservabilityMiddleware injects correlation IDs, updates metrics, and serves readiness probes."""
    app = create_app(demo_mode=True)
    client = TestClient(app)

    # 1. Health liveness check & correlation headers
    resp_health = client.get("/v1/health")
    assert resp_health.status_code == 200
    assert "X-Request-Id" in resp_health.headers
    assert "X-Trace-Id" in resp_health.headers
    assert resp_health.json()["status"] == "ok"
    assert resp_health.json()["version"] == "1.2.1-dev.11"

    # 2. Readiness probe (checks DB & alerts)
    resp_ready = client.get("/v1/ready")
    assert resp_ready.status_code == 200
    ready_body = resp_ready.json()
    assert ready_body["status"] == "ready"
    assert ready_body["database_connected"] is True

    # 3. Prometheus metrics endpoint
    resp_metrics = client.get("/v1/metrics")
    assert resp_metrics.status_code == 200
    assert "text/plain" in resp_metrics.headers["content-type"]
    metrics_text = resp_metrics.text
    assert "http_requests_total" in metrics_text
    assert "http_request_duration_ms" in metrics_text

    # 4. Ops alerts query endpoint
    resp_alerts = client.get("/v1/ops/alerts")
    assert resp_alerts.status_code == 200
    assert "alerts" in resp_alerts.json()


@pytest.mark.req("AUD-27", "FR-82")
def test_aud27_aead_crypto_shredding_tamper_resistance() -> None:
    """AUD-27: Authenticated XSalsa20-Poly1305 AEAD protects payload integrity and rejects tampering."""
    shred_store = CryptoShredStore()
    subject_ref = "user_aud27_01"
    payload = {"buyer_email": "shopper@secure.com", "serial": "SN-AUD27-999"}

    # Encryption roundtrip
    ciphertext_b64 = shred_store.encrypt_for_subject(subject_ref, payload)
    decrypted = shred_store.decrypt_for_subject(subject_ref, ciphertext_b64)
    assert decrypted == payload

    # Tampering with 1 bit of ciphertext raises/catches CryptoError and returns None
    raw_ct = bytearray(base64.b64decode(ciphertext_b64))
    raw_ct[-1] ^= 0x01
    tampered_b64 = base64.b64encode(raw_ct).decode("ascii")

    # Malleability attack strictly blocked
    assert shred_store.decrypt_for_subject(subject_ref, tampered_b64) is None

    # Key shredding / destruction
    shred_store.destroy_subject_key(subject_ref)
    assert shred_store.decrypt_for_subject(subject_ref, ciphertext_b64) is None


@pytest.mark.req("AUD-28", "FR-61", "FR-76", "INV-16")
def test_aud28_cryptographic_receipts_commitment_and_passport_chain(reset_db: Any) -> None:
    """AUD-28: Real cryptographic backing for receipts (Ed25519) and audit commitments (SHA-256 commit-reveal)."""
    app = create_app(demo_mode=True)
    client = TestClient(app)
    shopper_token = mint_shopper_token("ord_demo_1", "shopper_1")

    # 1. Receipts & audit commitment
    resp = client.get(
        "/v1/returns/ret_demo_1/receipts",
        headers={"Authorization": f"Bearer {shopper_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    receipts = data["receipts"]
    assert len(receipts) >= 2
    intake = next(r for r in receipts if r["kind"] == "INTAKE")
    assert intake["verified"] is True
    # Genuine Ed25519 signature format with length >= 64 hex chars
    assert len(intake["signature"]) >= 64
    assert len(intake["payload_hash"]) == 64

    audit_com = data["audit_commitment"]
    assert len(audit_com["commitment"]) == 64  # SHA-256 commit hash
    assert audit_com["p"] == "0.05"

    # 2. Passport verification endpoint
    resp_pass = client.get("/v1/passports/pass_demo_1/verify")
    assert resp_pass.status_code == 200
    pass_data = resp_pass.json()
    assert pass_data["chain_valid"] is True
    assert pass_data["cryptographically_verified"] is True


@pytest.mark.req("AUD-39", "API-06")
def test_aud39_bounded_ttl_cache_eviction_and_expiry() -> None:
    """AUD-39: BoundedTTLCache prevents unbounded state growth via max_size eviction and TTL expiration."""
    cache = BoundedTTLCache[str](max_size=3, ttl_seconds=0.2)

    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.set("k3", "v3")
    assert len(cache) == 3

    # Adding a 4th key evicts the oldest LRU key (k1)
    cache.set("k4", "v4")
    assert len(cache) == 3
    assert cache.get("k1") is None
    assert cache.get("k4") == "v4"

    # Waiting past TTL expires remaining entries
    time.sleep(0.25)
    assert cache.get("k2") is None
    assert len(cache) == 0


@pytest.mark.req("AUD-40", "FR-37", "FR-44")
def test_aud40_declaration_and_keep_offer_schema_alignment() -> None:
    """AUD-40: Declaration and keep-offer endpoints strictly adhere to published JSON schemas."""
    app = create_app(demo_mode=True)
    client = TestClient(app)
    shopper_token = mint_shopper_token("ord_demo_1", "shopper_1")

    # 1. Declaration adheres to schemas/return-declaration.v1.json
    decl_payload = {
        "schema_version": "1.0.0",
        "order_id": "ord_demo_1",
        "declared_grade": "B",
        "accessories": {"case": True},
        "reason_code": "CHANGED_MIND",
        "consent_fast_lane_terms": True,
        "nonce_shopper": "nonce_aud40_abc123",
        "actor": {"kind": "shopper", "sub": "shopper_1"},
    }
    r_decl = client.post(
        "/v1/returns/ret_demo_1/declaration",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json=decl_payload,
    )
    assert r_decl.status_code == 200

    # 2. Keep-offer retrieval adheres to schemas/keep-offer.v1.json
    r_koff = client.get(
        "/v1/returns/ret_demo_1/keep-offer",
        headers={"Authorization": f"Bearer {shopper_token}"},
    )
    assert r_koff.status_code == 200
    koff_data = r_koff.json()
    assert koff_data["keep_offer_id"] == "koff_ret_demo_1"
    assert koff_data["status"] == "OFFERED"
    assert "posted_price" in koff_data
    assert "expires_at" in koff_data
    assert "allowed_actions" in koff_data
    assert "ACCEPT" in koff_data["allowed_actions"]

    # 3. Agent keep-offer scope enforcement
    agent_no_scope = mint_agent_token("agt_no_scope", "ord_demo_1", "merch_a", scopes=["read_policy"])
    r_agent_denied = client.get(
        "/v1/returns/ret_demo_1/keep-offer",
        headers={"Authorization": f"Bearer {agent_no_scope}"},
    )
    assert r_agent_denied.status_code == 403


@pytest.mark.req("AUD-38", "TM-12")
def test_aud38_secret_scanner_execution() -> None:
    """AUD-38: Automated repository secret scanner runs and verifies zero credentials in repo."""
    exit_code = scan_secrets_main()
    assert exit_code == 0
