"""Condition Passport domain model, hash-chained events, and ownership transfer (F-01, F-09, INV-09, INV-13)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.domain.crypto_shred import CryptoShredStore
from backend.domain.passport_tier import select_passport_tier
from backend.domain.signing import (
    canonical_json_bytes,
    sha256_hex,
    sign_message_ed25519,
    verify_message_ed25519,
)


@dataclass(frozen=True)
class PassportEvent:
    event_id: str
    passport_id: str
    event_type: str
    payload_ciphertext: str
    data_key_ref: str
    payload_hash: str
    prev_hash: str | None
    hash: str
    created_at: str


@dataclass
class PassportManifest:
    passport_id: str
    order_id: str
    paypal_order_id: str
    capture_id: str
    sku: str
    category: str
    tier: str
    serial_hash: str
    origin_grade: str
    current_grade: str
    origin_weight_g: int
    media_hashes: list[str]
    functional_baseline_recorded: bool
    manifest_hash: str
    signature: str
    signing_key_id: str
    current_owner_ref: str
    events: list[PassportEvent] = field(default_factory=list)

    def verify_manifest_signature(self, public_key_bytes: bytes) -> bool:
        return verify_message_ed25519(public_key_bytes, self.manifest_hash, self.signature)

    def verify_event_chain(self) -> bool:
        """INV-09: Verify append-only hash chain over payload_hash."""
        prev: str | None = None
        for ev in self.events:
            if ev.prev_hash != prev:
                return False
            expected = sha256_hex(f"{ev.passport_id}:{ev.event_type}:{ev.payload_hash}:{ev.prev_hash or ''}")
            if ev.hash != expected:
                return False
            prev = ev.hash
        return True

    def to_public_dict(self) -> dict[str, Any]:
        """FR-43: Public passport view shows condition facts only, never personal data or owner refs."""
        return {
            "schema_version": "1.0.0",
            "passport_id": self.passport_id,
            "tier": self.tier,
            "product": {
                "sku": self.sku,
                "category": self.category,
                "serialized": bool(self.serial_hash),
                "serial_hash": self.serial_hash,
            },
            "origin_grade": self.origin_grade,
            "current_grade": self.current_grade,
            "origin_weight_g": self.origin_weight_g,
            "functional_baseline_recorded": self.functional_baseline_recorded,
            "manifest_hash": self.manifest_hash,
            "signature": self.signature,
            "signing_key_id": self.signing_key_id,
            "events": [
                {
                    "event_id": e.event_id,
                    "type": e.event_type,
                    "payload_hash": e.payload_hash,
                    "prev_hash": e.prev_hash,
                    "hash": e.hash,
                    "created_at": e.created_at,
                }
                for e in self.events
            ],
        }


def hash_serial(serial_raw: str, serial_salt: str) -> str:
    """FR-03 & INV-13: Store salted hash of serial/IMEI, never plaintext."""
    if len(serial_salt) < 16:
        raise ValueError("Serial salt must be at least 16 characters.")
    return sha256_hex(f"{serial_salt}:{serial_raw.strip().upper()}")


def create_origin_passport(
    *,
    passport_id: str,
    order_id: str,
    paypal_order_id: str,
    capture_id: str,
    sku: str,
    category: str,
    price_minor: int,
    serial_raw: str,
    serial_salt: str,
    weight_g: int,
    media_hashes: list[str],
    signing_private_key: bytes,
    signing_key_id: str,
    subject_ref: str,
    personal_payload: dict[str, Any],
    shred_store: CryptoShredStore,
    origin_grade: str = "A",
    functional_baseline_recorded: bool = True,
) -> PassportManifest:
    tier = select_passport_tier(price_minor)
    s_hash = hash_serial(serial_raw, serial_salt)
    manifest_core = {
        "passport_id": passport_id,
        "order_id": order_id,
        "paypal_order_id": paypal_order_id,
        "capture_id": capture_id,
        "sku": sku,
        "category": category,
        "tier": tier,
        "serial_hash": s_hash,
        "origin_grade": origin_grade,
        "origin_weight_g": weight_g,
        "media_hashes": sorted(media_hashes),
        "functional_baseline_recorded": functional_baseline_recorded,
    }
    m_hash = sha256_hex(canonical_json_bytes(manifest_core))
    sig = sign_message_ed25519(signing_private_key, m_hash)

    ciphertext = shred_store.encrypt_for_subject(subject_ref, personal_payload)
    payload_hash = sha256_hex(ciphertext)
    ev_hash = sha256_hex(f"{passport_id}:ORIGIN_PACKED:{payload_hash}:")
    now_iso = datetime.now(UTC).isoformat()
    origin_event = PassportEvent(
        event_id=f"{passport_id}_ev_1",
        passport_id=passport_id,
        event_type="ORIGIN_PACKED",
        payload_ciphertext=ciphertext,
        data_key_ref=subject_ref,
        payload_hash=payload_hash,
        prev_hash=None,
        hash=ev_hash,
        created_at=now_iso,
    )
    return PassportManifest(
        passport_id=passport_id,
        order_id=order_id,
        paypal_order_id=paypal_order_id,
        capture_id=capture_id,
        sku=sku,
        category=category,
        tier=tier,
        serial_hash=s_hash,
        origin_grade=origin_grade,
        current_grade=origin_grade,
        origin_weight_g=weight_g,
        media_hashes=list(media_hashes),
        functional_baseline_recorded=functional_baseline_recorded,
        manifest_hash=m_hash,
        signature=sig,
        signing_key_id=signing_key_id,
        current_owner_ref=subject_ref,
        events=[origin_event],
    )


def transfer_passport_ownership(
    passport: PassportManifest,
    *,
    new_owner_ref: str,
    signing_private_key: bytes,
) -> PassportManifest:
    """FR-42: Transfer passport ownership on certified resale; remove prior owner reference."""
    prev_hash = passport.events[-1].hash if passport.events else None
    transfer_meta = f"TRANSFER_TO:{sha256_hex(new_owner_ref)}"
    payload_hash = sha256_hex(transfer_meta)
    ev_hash = sha256_hex(f"{passport.passport_id}:OWNERSHIP_TRANSFERRED:{payload_hash}:{prev_hash or ''}")
    new_ev = PassportEvent(
        event_id=f"{passport.passport_id}_ev_{len(passport.events) + 1}",
        passport_id=passport.passport_id,
        event_type="OWNERSHIP_TRANSFERRED",
        payload_ciphertext=transfer_meta,
        data_key_ref=new_owner_ref,
        payload_hash=payload_hash,
        prev_hash=prev_hash,
        hash=ev_hash,
        created_at=datetime.now(UTC).isoformat(),
    )
    passport.current_owner_ref = new_owner_ref
    passport.events.append(new_ev)
    return passport
