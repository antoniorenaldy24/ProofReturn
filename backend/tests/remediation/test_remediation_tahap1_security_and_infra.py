"""Remediation Tahap 1 (Re-Audit Section J.1): Fail-Closed Auth, Key Separation, CSPRNG Audit Seeds, Alembic 22-Table Sync & Postgres Driver (J-01, J-03, RV-01, RV-02, RV-08, RV-12, RV-13, AUD-07, AUD-28, AUD-31, AUD-42)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import pathlib
import time

import pytest
import sqlalchemy as sa
from pydantic import SecretStr
from sqlmodel import create_engine

import backend.auth.tokens as tokens_mod
from backend.auth.tokens import (
     TOKEN_AUDIENCE,
    TOKEN_ISSUER,
    AuthenticationError,
    InvalidTokenSignatureError,
    MalformedTokenError,
    _REVOKED_SIGNATURES,
    mint_staff_token,
    revoke_token,
    sign_token,
    verify_token,
)
from backend.config import ProofReturnSettings, get_settings, reset_settings_cache
from backend.db.models import RefundAction, Return
from backend.db.repository import DatabaseRepository, normalize_database_url
from backend.db.schema import CANONICAL_TABLES
from backend.domain.receipts import issue_signed_receipt, verify_signed_receipt
from backend.domain.signing import (
    PACKER_KEY_ID,
    PLATFORM_KEY_ID,
    get_packer_keypair,
    get_platform_keypair,
    get_public_key_registry,
    sign_message_ed25519,
    verify_message_ed25519,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def test_rv01_fail_closed_auth_and_key_separation(monkeypatch: pytest.MonkeyPatch) -> None:
    """RV-01 (CRITICAL): No DEFAULT_AUTH_SECRET, fail-closed on config error, key separation, mandatory positive exp."""
    # 1. DEFAULT_AUTH_SECRET constant must not exist in tokens module
    assert not hasattr(tokens_mod, "DEFAULT_AUTH_SECRET")

    # 2. Compromised legacy constant must be rejected immediately
    legacy_compromised = b"proofreturn_server_auth_secret_key_32_bytes_minimum!"
    with pytest.raises(AuthenticationError, match="RV-01 fail-closed"):
        sign_token({"sub": "admin", "type": "staff", "merchant_id": "merch_a", "exp": int(time.time()) + 3600}, secret=legacy_compromised)

    # 3. Forged token signed with legacy DEFAULT_AUTH_SECRET and exp=0 (auditor exploit scenario) must be rejected
    header_b64 = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode("ascii")
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps({"sub": "attacker", "type": "staff", "merchant_id": "merch_a", "role": "MERCHANT_ADMIN", "exp": 0}).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    sig = hmac.new(legacy_compromised, f"{header_b64}.{payload_b64}".encode("ascii"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
    forged_token = f"{header_b64}.{payload_b64}.{sig_b64}"

    with pytest.raises(InvalidTokenSignatureError):
        verify_token(forged_token)

    # 4. If get_settings() fails at runtime, verify_token and mint_staff_token fail-closed (never fall back)
    def _broken_settings() -> ProofReturnSettings:
        raise RuntimeError("Simulated settings load failure")

    monkeypatch.setattr(tokens_mod, "get_settings", _broken_settings)
    with pytest.raises(AuthenticationError, match="RV-01 fail-closed"):
        verify_token(forged_token)
    with pytest.raises(AuthenticationError, match="RV-01 fail-closed"):
        mint_staff_token()

    monkeypatch.undo()

    # 5. Key separation: AUTH_SIGNING_KEY cannot equal SERIAL_HASH_SALT
    same_val = "a" * 64
    with pytest.raises(ValueError, match="RV-01 violation"):
        ProofReturnSettings(
            auth_signing_key=SecretStr(same_val),
            serial_hash_salt=SecretStr(same_val),
        )

    # 6. Missing exp or exp <= 0 rejected even with valid key
    valid_secret = b"v" * 32
    with pytest.raises(MalformedTokenError, match="exp"):
        sign_token({"sub": "u1", "type": "staff", "merchant_id": "m1", "exp": 0}, secret=valid_secret)
    with pytest.raises(MalformedTokenError, match="exp"):
        sign_token({"sub": "u1", "type": "staff", "merchant_id": "m1"}, secret=valid_secret)


def test_rv12_mandatory_issuer_audience_and_persistent_db_revocation(tmp_path: pathlib.Path) -> None:
    """RV-12: Tokens enforce iss and aud claims, and token revocation persists in the database across memory clears."""
    db_file = tmp_path / "revocation_test.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}")
    repo.seed_demo_data()

    tok = mint_staff_token(merchant_id="merch_a", role="MERCHANT_ADMIN", user_id="staff_01")
    principal = verify_token(tok)
    assert principal.iss == TOKEN_ISSUER
    assert principal.aud == TOKEN_AUDIENCE
    assert principal.jti != ""

    # Token with wrong issuer or audience must be rejected
    secret = get_settings().auth_signing_key.get_secret_value().encode("utf-8")
    bad_iss_tok = sign_token(
        {
            "sub": "staff_01",
            "type": "staff",
            "merchant_id": "merch_a",
            "iss": "other-service",
            "aud": TOKEN_AUDIENCE,
            "exp": int(time.time()) + 3600,
        },
        secret=secret,
    )
    with pytest.raises(MalformedTokenError, match="issuer or audience"):
        verify_token(bad_iss_tok)

    # Revoke token and clear in-memory _REVOKED_SIGNATURES to simulate process restart
    revoke_token(tok)
    _REVOKED_SIGNATURES.clear()
    assert len(_REVOKED_SIGNATURES) == 0

    # Verification must still fail via persistent DB revocation check
    with pytest.raises(AuthenticationError, match="revoked"):
        verify_token(tok)


def test_rv02_and_aud28_csprng_audit_seed_and_persistent_ed25519_verification() -> None:
    """RV-02 & AUD-28: Audit seed is CSPRNG (never derived from return_id), and Ed25519 keys are persistent and verifiable."""
    r1 = Return(return_id="ret_test_predictable", order_id="ord_demo_1", order_item_id="item_demo_1", merchant_id="merch_a")
    r2 = Return(return_id="ret_test_predictable", order_id="ord_demo_1", order_item_id="item_demo_1", merchant_id="merch_a")
    c1 = r1.ensure_audit_commitment()
    c2 = r2.ensure_audit_commitment()

    predictable_seed = hashlib.sha256(b"seed_platform_ret_test_predictable").hexdigest()
    assert r1.audit_seed_hex != predictable_seed
    assert r1.audit_seed_hex != r2.audit_seed_hex
    assert c1 != c2

    # Persistent Ed25519 platform & packer keys
    plat_priv, plat_pub, plat_id = get_platform_keypair()
    pack_priv, pack_pub, pack_id = get_packer_keypair()
    registry = get_public_key_registry()

    assert registry[PLATFORM_KEY_ID] == plat_pub
    assert registry[PACKER_KEY_ID] == pack_pub
    assert plat_pub != pack_pub

    # Issue receipt and verify with published public key
    receipt = issue_signed_receipt(
        receipt_id="rcpt_test_01",
        return_id="ret_demo_1",
        kind="INTAKE",
        payload={"state": "DECLARED"},
        signing_private_key=plat_priv,
        key_id=plat_id,
    )
    assert verify_signed_receipt(receipt, registry[plat_id]) is True
    assert verify_signed_receipt(receipt, registry[pack_id]) is False

    # Verify packer signature
    msg = "manifest_hash_test_001"
    sig = sign_message_ed25519(pack_priv, msg)
    assert verify_message_ed25519(registry[pack_id], msg, f"ed25519:{sig}") is True
    assert verify_message_ed25519(registry[pack_id], "tampered", f"ed25519:{sig}") is False


def test_aud07_rv08_aud42_alembic_22_tables_psycopg_and_dockerfile_hardening(tmp_path: pathlib.Path) -> None:
    """AUD-07, RV-08, AUD-42, RV-13: Alembic migrates all 22 tables without create_all, psycopg loads, Dockerfile hardened."""
    # 1. PostgreSQL driver loads without ModuleNotFoundError
    pg_url = normalize_database_url("postgresql://proofreturn:secret@localhost:5432/proofreturn")
    assert pg_url.startswith("postgresql+psycopg://")
    pg_engine = create_engine(pg_url)
    assert pg_engine.dialect.driver == "psycopg"

    # 2. Fresh database migrated solely via Alembic (0001 -> 0002) has all 22 canonical tables + alembic_version
    db_file = tmp_path / "alembic_only.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}")
    insp = sa.inspect(repo.engine)
    table_names = set(insp.get_table_names())
    assert "alembic_version" in table_names
    for tbl in CANONICAL_TABLES:
        assert tbl in table_names, f"Missing canonical table {tbl} in Alembic migration"
    assert len(CANONICAL_TABLES) == 22

    with repo.engine.connect() as conn:
        ver = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        assert ver == "0003_order_dispute_and_reversal_freeze"

    # 3. Verify RefundAction has merchant_id, capture_id, paypal_debug_id, attempt_count, currency, version (AUD-42, DB-01, DB-07)
    ra_cols = {c["name"] for c in insp.get_columns("refund_actions")}
    for col in ("merchant_id", "capture_id", "paypal_debug_id", "attempt_count", "currency", "version"):
        assert col in ra_cols

    # 4. Seeded Passport uses canonical tier FULL (not ORIGIN_WITNESSED) and real Ed25519 signature (AUD-42, AUD-28)
    repo.seed_demo_data()
    seeded_pass = repo.get_passport("pass_demo_1")
    assert seeded_pass is not None
    assert seeded_pass.tier == "FULL"
    assert seeded_pass.signature.startswith("ed25519:")
    registry = get_public_key_registry()
    assert verify_message_ed25519(registry[seeded_pass.signing_key_id], seeded_pass.head_hash, seeded_pass.signature) is True

    # 5. Dockerfile & docker-compose hardening (RV-08, RV-13, AUD-31)
    dockerfile_text = (REPO_ROOT / "infra" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY data/" not in dockerfile_text
    assert "USER appuser" in dockerfile_text

    compose_text = (REPO_ROOT / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "127.0.0.1:5432:5432" in compose_text
    assert "proofreturn_dev_password" not in compose_text
