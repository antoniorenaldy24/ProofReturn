"""Persistent pseudonymized fraud flags that survive deletion requests (FR-94, Section 33 DC-12)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from backend.domain.signing import sha256_hex


@dataclass(frozen=True)
class FraudFlag:
    flag_id: str
    merchant_id: str
    salted_hash: str
    flag_type: str
    source_decision_id: str
    retained_until: str


class FraudFlagRegistry:
    """FR-94: Retains pseudonymized fraud flags for 24 months, including after personal-data deletion requests."""

    # ASSUMPTION(A-30): Retaining pseudonymized fraud flags after deletion is permitted under fraud-prevention interest
    def __init__(self, salt: str) -> None:
        if not salt or len(salt.encode("utf-8")) < 32:
            raise ValueError("INV-13 violation: salt must be at least 32 bytes.")
        self._salt = salt
        self._flags: dict[str, FraudFlag] = {}

    def _hash_identifier(self, raw_id: str) -> str:
        return sha256_hex(f"{self._salt}:{raw_id.strip().lower()}")

    def record_confirmed_fraud(
        self,
        *,
        flag_id: str,
        merchant_id: str,
        raw_identifier: str,
        flag_type: str,
        source_decision_id: str,
    ) -> FraudFlag:
        s_hash = self._hash_identifier(raw_identifier)
        retained_until = (datetime.now(UTC) + timedelta(days=730)).isoformat()
        flag = FraudFlag(
            flag_id=flag_id,
            merchant_id=merchant_id,
            salted_hash=s_hash,
            flag_type=flag_type,
            source_decision_id=source_decision_id,
            retained_until=retained_until,
        )
        self._flags[s_hash] = flag
        return flag

    def is_flagged(self, raw_identifier: str) -> bool:
        s_hash = self._hash_identifier(raw_identifier)
        return s_hash in self._flags

    def handle_personal_data_deletion(self, _subject_ref: str) -> None:
        """FR-94 & TM-25: Deletion requests erase personal data (DC-1/DC-2/DC-5) but never erase DC-12 fraud flags."""
        return
