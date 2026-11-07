"""Ed25519 signing, persistent key registry, and SHA-256 canonical hashing utilities (FR-05, FR-76, INV-09, AUD-28)."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

PLATFORM_KEY_ID = "platform_key_v1"
PACKER_KEY_ID = "key_packer_origin_01"


def canonical_json_bytes(payload: Any) -> bytes:
    """Serialize payload into deterministic canonical JSON bytes."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def generate_ed25519_keypair() -> tuple[bytes, bytes]:
    """Return (private_seed_32_bytes, public_key_32_bytes)."""
    sk = SigningKey.generate()
    return bytes(sk), bytes(sk.verify_key)


def get_platform_keypair() -> tuple[bytes, bytes, str]:
    """Return persistent (private_seed_32b, public_key_32b, key_id) for platform receipts & decisions (AUD-28)."""
    from backend.config import get_settings

    seed_hex = get_settings().platform_signing_seed_hex.get_secret_value().strip()
    sk = SigningKey(bytes.fromhex(seed_hex))
    return bytes(sk), bytes(sk.verify_key), PLATFORM_KEY_ID


def get_packer_keypair() -> tuple[bytes, bytes, str]:
    """Return persistent (private_seed_32b, public_key_32b, key_id) for origin condition passports (AUD-28)."""
    from backend.config import get_settings

    seed_hex = get_settings().packer_signing_seed_hex.get_secret_value().strip()
    sk = SigningKey(bytes.fromhex(seed_hex))
    return bytes(sk), bytes(sk.verify_key), PACKER_KEY_ID


def get_public_key_registry() -> dict[str, bytes]:
    """Return mapping of key_id -> 32-byte Ed25519 public key for signature verification (AUD-28)."""
    _, plat_pub, plat_id = get_platform_keypair()
    _, pack_pub, pack_id = get_packer_keypair()
    return {
        plat_id: plat_pub,
        pack_id: pack_pub,
    }


def sign_message_ed25519(private_key_bytes: bytes, message: bytes | str) -> str:
    """Sign message with Ed25519 and return base64 signature."""
    if isinstance(message, str):
        message = data_bytes = message.encode("utf-8")
    else:
        data_bytes = message
    sk = SigningKey(private_key_bytes)
    signed = sk.sign(data_bytes)
    return base64.b64encode(signed.signature).decode("ascii")


def verify_message_ed25519(public_key_bytes: bytes, message: bytes | str, signature_b64: str) -> bool:
    """Verify base64 Ed25519 signature over message."""
    if isinstance(message, str):
        data_bytes = message.encode("utf-8")
    else:
        data_bytes = message
    try:
        raw_sig = signature_b64.removeprefix("ed25519:")
        sig = base64.b64decode(raw_sig)
        vk = VerifyKey(public_key_bytes)
        vk.verify(data_bytes, sig)
        return True
    except (BadSignatureError, ValueError):
        return False
