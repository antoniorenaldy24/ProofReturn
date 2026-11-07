"""Crypto-shredding per data subject for Passport payloads using XSalsa20-Poly1305 AEAD (FR-82, Section 33, AUD-27)."""

from __future__ import annotations

import base64
import json
import secrets
from typing import Any

import nacl.exceptions
import nacl.secret
import nacl.utils


class CryptoShredStore:
    """Manages per-subject data keys so destroying a key erases personal data while preserving ciphertext hashes (FR-82, AUD-27)."""

    # ASSUMPTION(A-24): Crypto-shredding satisfies erasure obligations for chain payloads
    def __init__(self) -> None:
        self._keys: dict[str, bytes] = {}
        self._destroyed: set[str] = set()

    def get_or_create_key(self, subject_ref: str) -> bytes:
        if subject_ref in self._destroyed:
            raise ValueError(f"Subject key for {subject_ref} has been destroyed.")
        if subject_ref not in self._keys:
            self._keys[subject_ref] = nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE)
        return self._keys[subject_ref]

    def encrypt_for_subject(self, subject_ref: str, payload: dict[str, Any]) -> str:
        """Encrypt payload with per-subject SecretBox AEAD (XSalsa20-Poly1305)."""
        key = self.get_or_create_key(subject_ref)
        box = nacl.secret.SecretBox(key)
        plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        encrypted = box.encrypt(plaintext)
        return base64.b64encode(encrypted).decode("ascii")

    def decrypt_for_subject(self, subject_ref: str, ciphertext_b64: str) -> dict[str, Any] | None:
        """Decrypt payload; returns None if key destroyed, not found, or ciphertext tampered."""
        if subject_ref in self._destroyed or subject_ref not in self._keys:
            return None
        key = self._keys[subject_ref]
        box = nacl.secret.SecretBox(key)
        try:
            raw = base64.b64decode(ciphertext_b64)
            plaintext = box.decrypt(raw)
            return json.loads(plaintext.decode("utf-8"))
        except (nacl.exceptions.CryptoError, ValueError, json.JSONDecodeError):
            return None

    def destroy_subject_key(self, subject_ref: str) -> None:
        self._keys.pop(subject_ref, None)
        self._destroyed.add(subject_ref)


def generate_subject_key(subject_ref: str) -> tuple[str, bytes]:
    """Generate a new per-subject key ID and 32-byte key."""
    key_id = f"skey_{subject_ref}"
    return key_id, nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE)


def encrypt_subject_payload(
    *, key_id: str, key_bytes: bytes, plaintext_dict: dict[str, Any]
) -> dict[str, str]:
    """Encrypt subject-specific payload fields with authenticated XSalsa20-Poly1305 AEAD (FR-82, AUD-27)."""
    box = nacl.secret.SecretBox(key_bytes)
    plaintext = json.dumps(plaintext_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encrypted = box.encrypt(plaintext)
    return {
        "key_id": key_id,
        "ciphertext_b64": base64.b64encode(encrypted).decode("ascii"),
    }


def decrypt_subject_payload(
    *, key_bytes: bytes, ciphertext_b64: str
) -> dict[str, Any] | None:
    """Decrypt subject-specific payload; returns None on key mismatch or ciphertext tampering (AUD-27)."""
    box = nacl.secret.SecretBox(key_bytes)
    try:
        raw = base64.b64decode(ciphertext_b64)
        plaintext = box.decrypt(raw)
        return json.loads(plaintext.decode("utf-8"))
    except (nacl.exceptions.CryptoError, ValueError, json.JSONDecodeError):
        return None


def shred_subject_key(key_store: dict[str, bytes], key_id: str) -> None:
    """Destroy a per-subject encryption key from key_store (FR-82)."""
    key_store.pop(key_id, None)
