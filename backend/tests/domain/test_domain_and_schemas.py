"""Unit and property tests for Domain Models, Passport Signing, Crypto-Shredding, Receipts, Decisions, and Schemas."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import jsonschema
import pytest

from backend.domain.crypto_shred import CryptoShredStore
from backend.domain.decision import build_decision_record, verify_decision_chain
from backend.domain.nonce import generate_seal_nonce
from backend.domain.order import OrderSnapshot
from backend.domain.passport import (
    create_origin_passport,
    transfer_passport_ownership,
)
from backend.domain.passport_tier import select_passport_tier
from backend.domain.policy import PolicyConfig
from backend.domain.receipts import issue_signed_receipt, verify_signed_receipt
from backend.domain.signing import generate_ed25519_keypair

ROOT = Path(__file__).resolve().parent.parent.parent.parent


@pytest.mark.req("FR-44", "FR-90")
def test_schemas_and_policy_config_validation() -> None:
    """FR-44 & FR-90: Validate JSON schemas and typed PolicyConfig."""
    for name in ["condition-passport.v1.json", "return-declaration.v1.json", "keep-offer.v1.json"]:
        schema_path = ROOT / "schemas" / name
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)

    policy = PolicyConfig.default_us()
    assert policy.version == "v2.1-default-us"
    assert policy.grade_fraction("B") == Fraction(95, 100)


@pytest.mark.req("FR-01", "FR-04", "FR-05", "FR-06", "FR-42", "FR-63", "FR-82", "INV-09")
def test_passport_signing_hash_chain_crypto_shred_and_transfer() -> None:
    """FR-01, FR-04, FR-05, FR-06, FR-42, FR-63, FR-82, INV-09."""
    assert select_passport_tier(10000) == "NONE"
    assert select_passport_tier(30000) == "LITE"
    assert select_passport_tier(80000) == "FULL"

    n1 = generate_seal_nonce()
    n2 = generate_seal_nonce()
    assert n1.nonce_code != n2.nonce_code and len(n1.nonce_hash) == 64

    priv_key, pub_key = generate_ed25519_keypair()
    shred_store = CryptoShredStore()
    subject_ref = "shopper_subj_01"

    passport = create_origin_passport(
        passport_id="pass_01",
        order_id="ord_01",
        paypal_order_id="PP-ORD-01",
        capture_id="PP-CAP-01",
        sku="SONY-XM5",
        category="headphones",
        price_minor=40000,
        serial_raw="SN-99887766",
        serial_salt="salt_32_bytes_minimum_length_xyz123",
        weight_g=250,
        media_hashes=["a" * 64, "b" * 64],
        signing_private_key=priv_key,
        signing_key_id="key_merch_01",
        subject_ref=subject_ref,
        personal_payload={"buyer_note": "leave at front door"},
        shred_store=shred_store,
    )
    assert passport.origin_grade == "A"
    assert passport.verify_manifest_signature(pub_key)
    assert passport.verify_event_chain()
    assert "SN-99887766" not in passport.serial_hash

    # FR-82: Crypto-shredding destroys personal data key while keeping hash chain valid
    shred_store.destroy_subject_key(subject_ref)
    assert shred_store.decrypt_for_subject(subject_ref, passport.events[0].payload_ciphertext) is None
    assert passport.verify_event_chain()

    # FR-42: Ownership transfer removes prior owner reference and appends chain event
    transferred = transfer_passport_ownership(passport, new_owner_ref="resale_buyer_02", signing_private_key=priv_key)
    assert transferred.current_owner_ref == "resale_buyer_02"
    assert transferred.verify_event_chain()
    public_view = transferred.to_public_dict()
    assert "current_owner_ref" not in public_view


@pytest.mark.req("FR-09", "FR-27", "FR-76", "INV-06", "INV-09")
def test_order_snapshot_decision_replay_and_receipts() -> None:
    """FR-09 (curve snapshot immutable), FR-27 (decision replay), FR-76 (signed receipts), INV-06."""
    policy = PolicyConfig.default_us()
    snap = OrderSnapshot.create(order_id="ord_01", price_minor=40000, policy=policy)
    assert snap.refund_for_grade("B") == 38000

    priv_key, pub_key = generate_ed25519_keypair()
    d1 = build_decision_record(
        decision_id="dec_01",
        return_id="ret_01",
        policy_version_id=policy.version,
        inputs_payload={"declared_grade": "B", "price_minor": 40000},
        lane="FAST",
        timing="R0",
        x_max_minor=22157,
        x_released_minor=22157,
        holdback_minor=6000,
        binding_constraint="X_MAX_GAP_D",
        p=Fraction(5, 100),
        audit_commitment="c" * 64,
        nonce_shopper="nonce_123",
        explanation="Initiated $221.57 immediately based on your TRUSTED status and Grade B declaration.",
        prev_hash=None,
    )
    d2 = build_decision_record(
        decision_id="dec_02",
        return_id="ret_01",
        policy_version_id=policy.version,
        inputs_payload={"verified_grade": "B", "price_minor": 40000},
        lane="FAST",
        timing="R0",
        x_max_minor=22157,
        x_released_minor=22157,
        holdback_minor=6000,
        binding_constraint="X_MAX_GAP_D",
        p=Fraction(5, 100),
        audit_commitment="c" * 64,
        nonce_shopper="nonce_123",
        explanation="Check-in confirmed Grade B; released remaining $98.43 and $60.00 holdback.",
        prev_hash=d1.hash,
    )
    assert verify_decision_chain([d1, d2])

    receipt = issue_signed_receipt(
        receipt_id="rcpt_01",
        return_id="ret_01",
        kind="INTAKE",
        payload={"decision_hash": d1.hash, "commitment": d1.audit_commitment, "p": str(d1.p)},
        signing_private_key=priv_key,
        key_id="platform_key_01",
    )
    assert verify_signed_receipt(receipt, pub_key)


@pytest.mark.req("INV-05")
def test_inv05_ai_packages_never_import_payments() -> None:
    """INV-05: Static import boundary check ensuring backend/ai never imports backend/payments."""
    import ast

    ai_dir = ROOT / "backend" / "ai"
    if ai_dir.exists():
        for py_file in ai_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert "payments" not in alias.name
                elif isinstance(node, ast.ImportFrom) and node.module:
                    assert "payments" not in node.module
