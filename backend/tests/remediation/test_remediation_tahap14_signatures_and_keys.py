"""Remediation tests for Task T8: Real signature and chain verification (AUD-28).

Verifies:
1. GET /v1/passports/{id}/verify recomputes event hash chain and verifies Ed25519 signatures
   against packer public key from get_public_key_registry().
2. Receipts 'verified' is computed by verifying the signature, never a literal.
3. GET /v1/keys returns public keys by key_id without private material.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.db.models import Passport, PassportEvent
from backend.domain.receipts import SignedReceipt, verify_signed_receipt
from backend.domain.signing import (
    generate_ed25519_keypair,
    get_public_key_registry,
    sha256_hex,
    sign_message_ed25519,
    verify_message_ed25519,
)


@pytest.mark.req("AUD-28", "FR-05", "INV-09")
def test_tampered_passport_event_makes_chain_invalid() -> None:
    """Tampering with an event payload or event hash must cause GET /v1/passports/{id}/verify to report chain_valid=False."""
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)
    packer_token = mint_staff_token("merch_a", "PACKER", sub="pack_01")
    pid = f"pass_tamper_{uuid.uuid4().hex[:8]}"

    # 1. Mint a valid passport
    mint_resp = client.post(
        "/v1/passports",
        headers={"Authorization": f"Bearer {packer_token}", "Idempotency-Key": f"ik-t14-mint-{pid}"},
        json={
            "passport_id": pid,
            "sku": "PR-HP-XM5",
            "tier": "FULL",
            "origin_grade": "A",
            "weight_g": 250,
            "self_test_passed": True,
        },
    )
    assert mint_resp.status_code == 201

    # Verify initial valid state
    ver_resp = client.get(f"/v1/passports/{pid}/verify")
    assert ver_resp.status_code == 200
    assert ver_resp.json()["chain_valid"] is True
    assert ver_resp.json()["cryptographically_verified"] is True

    # 2. Tamper with the event in the DB (change payload content)
    repo = app.state.repository
    events = repo.list_passport_events(pid)
    assert len(events) >= 1
    ev = events[0]
    
    # Tamper payload
    tampered_payload = copy.deepcopy(ev.payload_json)
    tampered_payload["origin_grade"] = "D"  # Malicious grade tampering
    
    with repo.get_session() as session:
        db_ev = session.get(PassportEvent, ev.event_id)
        assert db_ev is not None
        db_ev.payload_json = tampered_payload
        session.add(db_ev)
        session.commit()

    # 3. Verification must recompute the hash, detect payload discrepancy and reject
    ver_resp2 = client.get(f"/v1/passports/{pid}/verify")
    assert ver_resp2.status_code == 200
    assert ver_resp2.json()["chain_valid"] is False
    assert ver_resp2.json()["cryptographically_verified"] is False


@pytest.mark.req("AUD-28", "FR-05", "INV-09")
def test_signature_with_wrong_key_is_rejected() -> None:
    """An event signed with an unauthorized/wrong private key must cause verify to report chain_valid=False."""
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)
    packer_token = mint_staff_token("merch_a", "PACKER", sub="pack_01")
    pid = f"pass_wrong_{uuid.uuid4().hex[:8]}"

    # 1. Mint a valid passport
    mint_resp = client.post(
        "/v1/passports",
        headers={"Authorization": f"Bearer {packer_token}", "Idempotency-Key": f"ik-t14-mint-{pid}"},
        json={
            "passport_id": pid,
            "sku": "PR-HP-XM5",
            "tier": "FULL",
            "origin_grade": "A",
            "weight_g": 250,
            "self_test_passed": True,
        },
    )
    assert mint_resp.status_code == 201

    # 2. Forge a signature on the event using a rogue private key
    rogue_priv, _ = generate_ed25519_keypair()
    repo = app.state.repository
    events = repo.list_passport_events(pid)
    ev = events[0]
    
    rogue_sig = sign_message_ed25519(rogue_priv, ev.event_hash)
    with repo.get_session() as session:
        db_ev = session.get(PassportEvent, ev.event_id)
        assert db_ev is not None
        db_ev.signature = f"ed25519:{rogue_sig}"
        session.add(db_ev)
        session.commit()

    # 3. Verification must verify signature against packer public key and reject
    ver_resp = client.get(f"/v1/passports/{pid}/verify")
    assert ver_resp.status_code == 200
    assert ver_resp.json()["chain_valid"] is False
    assert ver_resp.json()["cryptographically_verified"] is False


@pytest.mark.req("AUD-28", "FR-76", "INV-16")
def test_receipt_verification_uses_published_public_key() -> None:
    """GET /v1/keys publishes public keys and verifies condition receipts independently without secrets."""
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    # 1. GET /v1/keys returns public keys without authentication and without private keys
    keys_resp = client.get("/v1/keys")
    assert keys_resp.status_code == 200
    keys_data = keys_resp.json()
    assert "keys" in keys_data
    keys_map = keys_data["keys"]

    assert "platform_key_v1" in keys_map
    assert "key_packer_origin_01" in keys_map
    
    # Confirm no private seeds or secrets are exposed
    keys_str = json.dumps(keys_data)
    assert "seed" not in keys_str.lower()
    assert "private" not in keys_str.lower()
    assert "secret" not in keys_str.lower()

    platform_key_info = keys_map["platform_key_v1"]
    assert platform_key_info["algorithm"] == "Ed25519"
    pub_key_hex = platform_key_info["public_key_hex"]
    assert len(pub_key_hex) == 64  # 32 bytes in hex
    pub_key_bytes = bytes.fromhex(pub_key_hex)

    # 2. Get receipts for a return
    shopper_token = mint_shopper_token("ord_demo_1", "shopper_1")
    rcpt_resp = client.get(
        "/v1/returns/ret_demo_1/receipts",
        headers={"Authorization": f"Bearer {shopper_token}"},
    )
    assert rcpt_resp.status_code == 200
    rcpt_data = rcpt_resp.json()
    receipts = rcpt_data["receipts"]
    assert len(receipts) >= 2

    # 3. Verify each receipt independently using the published public key
    for r in receipts:
        assert r["verified"] is True
        # Cryptographic verification using published public key
        sig_valid = verify_message_ed25519(
            pub_key_bytes,
            r["payload_hash"],
            r["signature"],
        )
        assert sig_valid is True

        # Tampering with payload hash fails verification
        tampered_hash = sha256_hex(b"tampered_payload_hash")
        assert verify_message_ed25519(pub_key_bytes, tampered_hash, r["signature"]) is False
