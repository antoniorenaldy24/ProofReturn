"""Typed Configuration Registry (Section 35.1) with SecretStr masking and fail-closed startup guards (RV-01, TM-16, TM-24, INV-09, INV-13)."""

from __future__ import annotations

import secrets
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_PAYPAL_SANDBOX_HOSTS = {
    "api-m.sandbox.paypal.com",
    "api.sandbox.paypal.com",
    "localhost",
    "127.0.0.1",
}

COMPROMISED_OR_PLACEHOLDER_SECRETS = {
    "proofreturn_server_auth_secret_key_32_bytes_minimum!",
    "proofreturn_dev_serial_salt_32bytes_min_0123456789",
    "proofreturn_dev_payer_salt_32bytes_min_0123456789",
    "replace_with_at_least_32_bytes_random_hex_salt",
    "replace_with_at_least_32_bytes_random_hex_signing_key",
    "replace_with_at_least_32_bytes_random_hex_demo_bootstrap_key",
    "replace_with_at_least_32_bytes_random_hex_demo_webhook_secret",
}


def validate_sandbox_base_url(base_url: str) -> None:
    """Ensure PayPal base URL targets only approved Sandbox hosts (TM-16)."""
    parsed = urlparse(base_url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError(f"TM-16 violation: Invalid PayPal base URL '{base_url}'.")
    host = parsed.hostname.lower()
    if host not in ALLOWED_PAYPAL_SANDBOX_HOSTS:
        raise ValueError(
            f"TM-16 violation: PayPal host '{host}' is forbidden. Only Sandbox hosts {sorted(ALLOWED_PAYPAL_SANDBOX_HOSTS)} are permitted."
        )


class ProofReturnSettings(BaseSettings):
    """Validated startup configuration loaded from environment and .env without exposing secrets."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="local")
    demo_mode: bool = Field(default=False)
    demo_bootstrap_key: SecretStr = Field(default=SecretStr(""))
    demo_webhook_secret: SecretStr = Field(default=SecretStr(""))
    mode: str = Field(default="live")
    compose_profile: str = Field(default="lite")
    calibration_profile: str = Field(default="illustrative")
    database_url: str = Field(default="sqlite:///./data/proofreturn.db")
    run_migrations_on_start: bool = Field(default=False)

    # Schedulers & Background Automation (RV2-02)
    enable_scheduler: bool = Field(default=True)
    scheduler_interval_seconds: float = Field(default=60.0, ge=0.01)

    # PayPal Sandbox (TM-16 guard)
    paypal_base_url: str = Field(default="https://api-m.sandbox.paypal.com")
    paypal_client_id: SecretStr = Field(default=SecretStr("replace_with_paypal_sandbox_client_id"))
    paypal_client_secret: SecretStr = Field(default=SecretStr("replace_with_paypal_sandbox_client_secret"))
    paypal_webhook_id: SecretStr = Field(default=SecretStr("replace_with_paypal_sandbox_webhook_id"))
    idempotency_replay_window_days: int = Field(default=30, ge=1, le=90)

    # AI Provider & Model Keys (DOC-06 unified default: gemini-3.6-flash)
    ai_provider: str = Field(default="gemini")
    gemini_api_key: SecretStr = Field(default=SecretStr(""))
    gemini_model: str = Field(default="gemini-3.6-flash")
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    open_vlm_url: str = Field(default="http://localhost:8001/v1")
    model_config_path: str = Field(default="config/models.yaml")

    # Cryptography, Signing Keys & Privacy Salts (RV-01, AUD-28, INV-09, INV-13: >= 32 bytes, strictly separated)
    signing_key_path: str = Field(default="config/dev_signing_key.bin")
    auth_signing_key: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_hex(32))
    )
    platform_signing_seed_hex: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_hex(32))
    )
    packer_signing_seed_hex: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_hex(32))
    )
    serial_hash_salt: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_hex(32))
    )
    payer_hash_salt: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_hex(32))
    )
    media_retention_days: int = Field(default=90, ge=1, le=365)
    carrier_events_manual: bool = Field(default=False)

    @model_validator(mode="before")
    @classmethod
    def _normalize_paypal_base_url(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for k in ("paypal_base_url", "PAYPAL_BASE_URL"):
                val = data.get(k)
                if isinstance(val, str) and val.strip().rstrip("/") in {"https://sandbox.paypal.com", "http://sandbox.paypal.com"}:
                    data[k] = "https://api-m.sandbox.paypal.com"
        return data

    @model_validator(mode="after")
    def _validate_security_guards(self) -> ProofReturnSettings:
        # TM-16: PayPal base URL must be a valid Sandbox host
        validate_sandbox_base_url(self.paypal_base_url)

        # RV2-01: Fail-closed validation of DEMO_BOOTSTRAP_KEY when DEMO_MODE=true
        if self.demo_mode:
            raw_bootstrap = self.demo_bootstrap_key.get_secret_value().strip()
            if not raw_bootstrap:
                raise ValueError("RV2-01 violation: DEMO_BOOTSTRAP_KEY is required when DEMO_MODE=true (fail-closed).")
            if len(raw_bootstrap.encode("utf-8")) < 32:
                raise ValueError("RV2-01 violation: DEMO_BOOTSTRAP_KEY must be at least 32 bytes when DEMO_MODE=true.")
            if (
                raw_bootstrap in COMPROMISED_OR_PLACEHOLDER_SECRETS
                or raw_bootstrap.lower().startswith("replace_with_")
            ):
                raise ValueError("RV2-01 violation: DEMO_BOOTSTRAP_KEY uses a forbidden placeholder or compromised value.")

            raw_webhook_sec = self.demo_webhook_secret.get_secret_value().strip()
            if not raw_webhook_sec:
                raise ValueError("AUD-24 violation: DEMO_WEBHOOK_SECRET is required when DEMO_MODE=true (fail-closed).")
            if len(raw_webhook_sec.encode("utf-8")) < 32:
                raise ValueError("AUD-24 violation: DEMO_WEBHOOK_SECRET must be at least 32 bytes when DEMO_MODE=true.")
            if (
                raw_webhook_sec in COMPROMISED_OR_PLACEHOLDER_SECRETS
                or raw_webhook_sec.lower().startswith("replace_with_")
            ):
                raise ValueError("AUD-24 violation: DEMO_WEBHOOK_SECRET uses a forbidden placeholder or compromised value.")

        auth_key = self.auth_signing_key.get_secret_value()
        serial_salt = self.serial_hash_salt.get_secret_value()
        payer_salt = self.payer_hash_salt.get_secret_value()

        # RV-01: Fail-closed validation of AUTH_SIGNING_KEY
        if len(auth_key.encode("utf-8")) < 32:
            raise ValueError("RV-01 violation: AUTH_SIGNING_KEY must be at least 32 bytes (fail-closed).")
        if auth_key in COMPROMISED_OR_PLACEHOLDER_SECRETS or auth_key.lower().startswith("replace_with_"):
            raise ValueError("RV-01 violation: AUTH_SIGNING_KEY uses a forbidden placeholder or compromised value.")

        # INV-09 & INV-13: Salts must be at least 32 bytes
        if len(serial_salt.encode("utf-8")) < 32:
            raise ValueError("INV-13 violation: SERIAL_HASH_SALT must be at least 32 bytes.")
        if len(payer_salt.encode("utf-8")) < 32:
            raise ValueError("INV-13 violation: PAYER_HASH_SALT must be at least 32 bytes.")

        # RV-01: Strict cryptographic key separation between token signing and pseudonymization salts
        if auth_key == serial_salt or auth_key == payer_salt:
            raise ValueError(
                "RV-01 violation: AUTH_SIGNING_KEY must be cryptographically separate from SERIAL_HASH_SALT and PAYER_HASH_SALT."
            )

        # AUD-28: Validate Ed25519 32-byte seeds
        for label, seed_secret in [
            ("PLATFORM_SIGNING_SEED_HEX", self.platform_signing_seed_hex),
            ("PACKER_SIGNING_SEED_HEX", self.packer_signing_seed_hex),
        ]:
            raw_seed = seed_secret.get_secret_value().strip()
            try:
                seed_bytes = bytes.fromhex(raw_seed)
            except ValueError as exc:
                raise ValueError(f"AUD-28 violation: {label} must be valid hexadecimal.") from exc
            if len(seed_bytes) != 32:
                raise ValueError(f"AUD-28 violation: {label} must decode to exactly 32 bytes.")

        if self.platform_signing_seed_hex.get_secret_value() == self.packer_signing_seed_hex.get_secret_value():
            raise ValueError("AUD-28 violation: PLATFORM_SIGNING_SEED_HEX and PACKER_SIGNING_SEED_HEX must be distinct.")

        # TM-24: Manual carrier events allowed only when DEMO_MODE=true
        if self.carrier_events_manual and not self.demo_mode:
            raise ValueError("TM-24 violation: CARRIER_EVENTS_MANUAL cannot be true when DEMO_MODE=false.")
        return self

    @property
    def has_live_gemini_key(self) -> bool:
        """Return True if a non-placeholder GEMINI_API_KEY is configured."""
        raw = self.gemini_api_key.get_secret_value().strip()
        if not raw:
            return False
        lower = raw.lower()
        return not (
            lower.startswith(("replace_with_", "your_")) or lower == "placeholder"
        )

    @property
    def has_live_paypal_credentials(self) -> bool:
        """Return True if non-placeholder PayPal Sandbox client credentials are configured."""
        cid = self.paypal_client_id.get_secret_value().strip()
        csec = self.paypal_client_secret.get_secret_value().strip()
        if not cid or not csec:
            return False
        return not (
            cid.lower().startswith("replace_with_")
            or csec.lower().startswith("replace_with_")
            or cid.lower().startswith("your_")
            or csec.lower().startswith("your_")
        )


_SETTINGS_INSTANCE: ProofReturnSettings | None = None


def get_settings() -> ProofReturnSettings:
    """Return process-wide validated settings singleton. Fails closed if configuration is invalid."""
    global _SETTINGS_INSTANCE
    if _SETTINGS_INSTANCE is None:
        _SETTINGS_INSTANCE = ProofReturnSettings()
    return _SETTINGS_INSTANCE


def reset_settings_cache(new_settings: ProofReturnSettings | None = None) -> None:
    """Reset or inject settings instance for isolated testing."""
    global _SETTINGS_INSTANCE
    _SETTINGS_INSTANCE = new_settings
