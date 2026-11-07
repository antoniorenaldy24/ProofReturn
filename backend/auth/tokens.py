"""Cryptographically Signed Token Engine (Section 28.1 API-04, Section 28.3, Section 29, AUD-21, RV-01, RV-12).

Implements fail-closed HMAC-SHA256 (HS256) signed tokens with mandatory expiration (exp > 0),
issuer (iss) and audience (aud) validation, key separation from pseudonymization salts,
persistent database-backed revocation, tenant scoping, and scoped agent capabilities.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from backend.config import COMPROMISED_OR_PLACEHOLDER_SECRETS, get_settings

TOKEN_ISSUER = "proofreturn-api"
TOKEN_AUDIENCE = "proofreturn-v1"


class AuthenticationError(Exception):
    """Base exception for authentication failures."""


class TokenExpiredError(AuthenticationError):
    """Raised when token expiration timestamp (exp) has passed."""


class InvalidTokenSignatureError(AuthenticationError):
    """Raised when token signature is invalid or forged."""


class MalformedTokenError(AuthenticationError):
    """Raised when token format or payload is invalid."""


_REVOKED_SIGNATURES: set[str] = set()
_DB_REVOKE_WRITER: Callable[[str], None] | None = None
_DB_REVOKE_CHECKER: Callable[[str], bool] | None = None


def register_revocation_persistence(
    writer: Callable[[str], None] | None,
    checker: Callable[[str], bool] | None,
) -> None:
    """Register database-backed revocation callbacks so revocations survive restarts (RV-12)."""
    global _DB_REVOKE_WRITER, _DB_REVOKE_CHECKER
    _DB_REVOKE_WRITER = writer
    _DB_REVOKE_CHECKER = checker


def _get_signing_secret(override_secret: bytes | None = None) -> bytes:
    """Resolve token signing key strictly fail-closed without fallback constants (RV-01)."""
    if override_secret is not None:
        if not isinstance(override_secret, bytes) or len(override_secret) < 32:
            raise AuthenticationError("RV-01 fail-closed: signing secret must be at least 32 bytes.")
        try:
            decoded = override_secret.decode("utf-8")
            if decoded in COMPROMISED_OR_PLACEHOLDER_SECRETS:
                raise AuthenticationError("RV-01 fail-closed: compromised or placeholder secret rejected.")
        except UnicodeDecodeError:
            pass
        return override_secret

    try:
        settings = get_settings()
    except Exception as exc:
        raise AuthenticationError(
            f"RV-01 fail-closed: authentication configuration failed to load: {exc}"
        ) from exc

    raw = settings.auth_signing_key.get_secret_value()
    raw_bytes = raw.encode("utf-8")
    if len(raw_bytes) < 32:
        raise AuthenticationError("RV-01 fail-closed: AUTH_SIGNING_KEY is shorter than 32 bytes.")
    if raw in COMPROMISED_OR_PLACEHOLDER_SECRETS or raw.lower().startswith("replace_with_"):
        raise AuthenticationError("RV-01 fail-closed: AUTH_SIGNING_KEY uses a compromised or placeholder value.")
    if raw == settings.serial_hash_salt.get_secret_value() or raw == settings.payer_hash_salt.get_secret_value():
        raise AuthenticationError("RV-01 fail-closed: AUTH_SIGNING_KEY must not reuse pseudonymization salts.")
    return raw_bytes


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padded = s + "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


@dataclass(frozen=True)
class Principal:
    """Authenticated entity with verified identity, tenant scope, and roles/scopes."""

    sub: str
    type: str  # "staff" | "shopper" | "agent" | "service"
    merchant_id: str
    role: str | None = None
    order_id: str | None = None
    scopes: set[str] = field(default_factory=set)
    agent_label: str | None = None
    exp: int = 0
    iss: str = TOKEN_ISSUER
    aud: str = TOKEN_AUDIENCE
    jti: str = ""
    raw_token: str = ""

    @property
    def is_staff(self) -> bool:
        return self.type == "staff"

    @property
    def is_shopper(self) -> bool:
        return self.type == "shopper"

    @property
    def is_agent(self) -> bool:
        return self.type == "agent"

    @property
    def is_service(self) -> bool:
        return self.type == "service"


def _extract_sig(token_or_sig: str) -> str:
    if "." in token_or_sig:
        parts = token_or_sig.split(".")
        if len(parts) == 3:
            return parts[2]
    return token_or_sig


def revoke_token(token_or_sig: str) -> None:
    """Add a token signature to the in-memory and persistent DB revocation store (RV-12)."""
    sig = _extract_sig(token_or_sig)
    _REVOKED_SIGNATURES.add(sig)
    if _DB_REVOKE_WRITER is not None:
        _DB_REVOKE_WRITER(sig)


def is_token_revoked(token_or_sig: str) -> bool:
    """Check if token signature is revoked in memory or persistent DB store (RV-12)."""
    sig = _extract_sig(token_or_sig)
    if sig in _REVOKED_SIGNATURES:
        return True
    if _DB_REVOKE_CHECKER is not None and _DB_REVOKE_CHECKER(sig):
        _REVOKED_SIGNATURES.add(sig)
        return True
    return False


def sign_token(payload: dict[str, Any], secret: bytes | None = None) -> str:
    """Sign a JWT-compatible dictionary payload using HMAC-SHA256 (HS256) with mandatory claims."""
    key = _get_signing_secret(secret)

    raw_exp = payload.get("exp")
    if raw_exp is None or isinstance(raw_exp, bool) or not isinstance(raw_exp, int) or raw_exp <= 0:
        raise MalformedTokenError("RV-01 violation: Token payload must contain a positive integer 'exp' claim.")

    now = int(time.time())
    full_payload = dict(payload)
    full_payload.setdefault("iss", TOKEN_ISSUER)
    full_payload.setdefault("aud", TOKEN_AUDIENCE)
    full_payload.setdefault("iat", now)
    full_payload.setdefault("jti", secrets.token_hex(16))

    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(full_payload, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(key, signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def verify_token(raw_token: str, secret: bytes | None = None) -> Principal:
    """Verify cryptographic signature, mandatory expiration, issuer/audience, and format (AUD-21, RV-01, RV-12)."""
    if not raw_token or not isinstance(raw_token, str):
        raise MalformedTokenError("Missing or empty token string.")

    token = raw_token.removeprefix("Bearer ").strip()
    parts = token.split(".")
    if len(parts) != 3:
        raise MalformedTokenError("Invalid token format: expected header.payload.signature (HS256).")

    header_b64, payload_b64, sig_b64 = parts

    if is_token_revoked(sig_b64):
        raise AuthenticationError("Token has been revoked.")

    key = _get_signing_secret(secret)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(key, signing_input, hashlib.sha256).digest()
    expected_sig_b64 = _b64url_encode(expected_sig)

    if not hmac.compare_digest(sig_b64, expected_sig_b64):
        raise InvalidTokenSignatureError("Cryptographic signature verification failed.")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise MalformedTokenError(f"Malformed token JSON payload: {exc}") from exc

    if not isinstance(payload, dict):
        raise MalformedTokenError("Token payload must be a JSON object.")

    # RV-01: Mandatory positive integer exp claim (reject missing exp or exp <= 0)
    raw_exp = payload.get("exp")
    if raw_exp is None or isinstance(raw_exp, bool) or not isinstance(raw_exp, int) or raw_exp <= 0:
        raise MalformedTokenError("Token missing mandatory positive 'exp' claim (RV-01).")

    now = int(time.time())
    if raw_exp < now:
        raise TokenExpiredError(f"Token expired at epoch {raw_exp} (current time {now}).")

    # RV-12: Mandatory issuer (iss) and audience (aud) validation
    iss = payload.get("iss")
    aud = payload.get("aud")
    if iss != TOKEN_ISSUER or aud != TOKEN_AUDIENCE:
        raise MalformedTokenError(
            f"Token has invalid issuer or audience (expected iss='{TOKEN_ISSUER}', aud='{TOKEN_AUDIENCE}')."
        )

    sub = str(payload.get("sub", ""))
    token_type = str(payload.get("type", ""))
    merchant_id = str(payload.get("merchant_id", ""))

    if not sub or not token_type or not merchant_id:
        raise MalformedTokenError("Token missing mandatory claims: sub, type, or merchant_id.")

    raw_scopes = payload.get("scopes", [])
    scopes_set = set(raw_scopes) if isinstance(raw_scopes, list) else set()

    return Principal(
        sub=sub,
        type=token_type,
        merchant_id=merchant_id,
        role=payload.get("role"),
        order_id=payload.get("order_id"),
        scopes=scopes_set,
        agent_label=payload.get("agent_label"),
        exp=raw_exp,
        iss=str(iss),
        aud=str(aud),
        jti=str(payload.get("jti", "")),
        raw_token=token,
    )


def mint_staff_token(
    merchant_id: str = "merch_a",
    role: str = "MERCHANT_ADMIN",
    user_id: str | None = None,
    *,
    sub: str | None = None,
    ttl_seconds: int = 86400,
    secret: bytes | None = None,
    **kwargs: Any,
) -> str:
    """Mint signed staff token (roles: MERCHANT_ADMIN, MERCHANT_OPERATOR, PACKER, RECEIVER, REVIEWER)."""
    actual_user_id = sub or user_id or kwargs.get("user_id") or f"user_{role.lower()}"
    actual_merchant_id = merchant_id or kwargs.get("merchant_id", "merch_a")
    actual_role = (role or kwargs.get("role", "MERCHANT_ADMIN")).upper()

    now = int(time.time())
    payload = {
        "sub": actual_user_id,
        "type": "staff",
        "merchant_id": actual_merchant_id,
        "role": actual_role,
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": secrets.token_hex(16),
    }
    return sign_token(payload, secret)


def mint_shopper_token(
    order_id: str = "ord_demo_1",
    shopper_id: str = "shopper_1",
    merchant_id: str = "merch_a",
    *,
    sub: str | None = None,
    ttl_seconds: int = 86400,
    secret: bytes | None = None,
    **kwargs: Any,
) -> str:
    """Mint signed shopper order token (scoped to order_id and merchant_id)."""
    actual_shopper_id = sub or shopper_id or kwargs.get("shopper_id", "shopper_1")
    actual_order_id = order_id or kwargs.get("order_id", "ord_demo_1")
    actual_merchant_id = merchant_id or kwargs.get("merchant_id", "merch_a")

    now = int(time.time())
    payload = {
        "sub": actual_shopper_id,
        "type": "shopper",
        "order_id": actual_order_id,
        "merchant_id": actual_merchant_id,
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": secrets.token_hex(16),
    }
    return sign_token(payload, secret)


def mint_agent_token(
    agent_id: str = "bot_agent",
    order_id: str = "ord_demo_1",
    merchant_id: str = "merch_a",
    scopes: list[str] | None = None,
    *,
    agent_label: str = "assistant",
    sub: str | None = None,
    ttl_seconds: int = 3600,
    secret: bytes | None = None,
    **kwargs: Any,
) -> str:
    """Mint signed shopper agent token (Section 28.3: POST /v1/agent/tokens, FR-45)."""
    actual_agent_id = sub or agent_id or kwargs.get("agent_id", "bot_agent")
    actual_order_id = order_id or kwargs.get("order_id", "ord_demo_1")
    actual_merchant_id = merchant_id or kwargs.get("merchant_id", "merch_a")
    actual_scopes = scopes or kwargs.get("scopes", ["read_policy", "declare"])

    now = int(time.time())
    payload = {
        "sub": actual_agent_id,
        "type": "agent",
        "order_id": actual_order_id,
        "merchant_id": actual_merchant_id,
        "scopes": sorted(list(set(actual_scopes))),
        "agent_label": agent_label,
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": secrets.token_hex(16),
    }
    return sign_token(payload, secret)


def mint_service_token(
    *,
    service_id: str,
    merchant_id: str = "platform",
    scopes: list[str] | None = None,
    ttl_seconds: int = 86400,
    secret: bytes | None = None,
) -> str:
    """Mint signed internal service token (workers, Temporal, carrier adapters)."""
    now = int(time.time())
    payload = {
        "sub": service_id,
        "type": "service",
        "merchant_id": merchant_id,
        "role": "SERVICE",
        "scopes": scopes or ["carrier_events", "reconciliation"],
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": secrets.token_hex(16),
    }
    return sign_token(payload, secret)
