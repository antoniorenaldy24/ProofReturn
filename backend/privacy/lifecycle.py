"""Privacy and Data Lifecycle Deletion Request Flow (Section 33, NFR-05, FR-82, FR-94, TM-25).

Enforces purpose-based retention & GDPR/CCPA erasure while preserving:
- Immutable structural Passport hashes (DC-3) via crypto-shredding of subject keys (FR-82)
- Pseudonymized accounting/financial ledger records for 7 years (DC-6)
- Persistent fraud flags keyed by hashed payer/instrument IDs under legitimate-interest fraud prevention (DC-12, FR-94)
- Legal hold when an open PayPal dispute exists (Section 33.4 step 6)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.domain.crypto_shred import shred_subject_key
from backend.domain.signing import sha256_hex


@dataclass
class SubjectDataRecord:
    subject_id: str
    subject_key_id: str
    raw_media_keys: list[str] = field(default_factory=list)
    derived_media_keys: list[str] = field(default_factory=list)
    passport_ciphertext: dict[str, str] = field(default_factory=dict)
    passport_structural_hash: str = ""
    cross_merchant_opt_in: bool = False
    contact_email: str | None = None
    financial_ledger_ids: list[str] = field(default_factory=list)
    persistent_fraud_flags: list[str] = field(default_factory=list)
    has_open_dispute: bool = False
    pseudonymized_subject_ref: str | None = None


@dataclass(frozen=True)
class DeletionRequestResult:
    subject_id: str
    status: str  # "COMPLETED" | "LEGAL_HOLD_ACTIVE"
    dc1_raw_media_deleted: bool
    dc2_derived_media_deleted: bool
    dc3_subject_key_shredded: bool
    dc3_structural_hash_preserved: str
    dc4_cross_merchant_unlinked: bool
    dc5_contact_deleted: bool
    dc6_financial_pseudonymized: bool
    dc12_fraud_flags_retained: list[str]
    completed_at_epoch: int


class DeletionRequestStore:
    """In-memory / repository store for subject data lifecycle operations."""

    def __init__(self) -> None:
        self._records: dict[str, SubjectDataRecord] = {}

    def register_subject(self, record: SubjectDataRecord) -> None:
        self._records[record.subject_id] = record

    def get_subject(self, subject_id: str) -> SubjectDataRecord:
        if subject_id not in self._records:
            raise KeyError(f"Unknown subject_id: {subject_id}")
        return self._records[subject_id]


def execute_deletion_request(
    store: DeletionRequestStore,
    key_store: dict[str, bytes],
    subject_id: str,
    requested_at_epoch: int,
) -> DeletionRequestResult:
    """Execute Section 33.4 deletion request flow."""
    record = store.get_subject(subject_id)

    # Always unlink DC-4 cross-merchant registry opt-in immediately on request
    record.cross_merchant_opt_in = False

    if record.has_open_dispute:
        # Section 33.4 step 6: Legal hold blocks deletion of DC-1, DC-2, DC-3, DC-6 while dispute is open
        return DeletionRequestResult(
            subject_id=subject_id,
            status="LEGAL_HOLD_ACTIVE",
            dc1_raw_media_deleted=False,
            dc2_derived_media_deleted=False,
            dc3_subject_key_shredded=False,
            dc3_structural_hash_preserved=record.passport_structural_hash,
            dc4_cross_merchant_unlinked=True,
            dc5_contact_deleted=False,
            dc6_financial_pseudonymized=False,
            dc12_fraud_flags_retained=list(record.persistent_fraud_flags),
            completed_at_epoch=requested_at_epoch,
        )

    # Step 1: Delete DC-1 (raw media), DC-2 (derived media), DC-5 (contact data)
    record.raw_media_keys.clear()
    record.derived_media_keys.clear()
    record.contact_email = None

    # Step 2: Destroy subject key for DC-3 (FR-82 crypto-shredding); structural item hash remains verifiable
    shred_subject_key(key_store, record.subject_key_id)

    # Step 4: Pseudonymize DC-6 financial records (retained 7 years for accounting/tax)
    record.pseudonymized_subject_ref = f"pseudo_{sha256_hex(subject_id.encode('utf-8'))[:16]}"

    # Step 5: Keep DC-12 persistent fraud flags (hashed payer/instrument IDs) under legitimate-interest fraud prevention
    return DeletionRequestResult(
        subject_id=subject_id,
        status="COMPLETED",
        dc1_raw_media_deleted=True,
        dc2_derived_media_deleted=True,
        dc3_subject_key_shredded=True,
        dc3_structural_hash_preserved=record.passport_structural_hash,
        dc4_cross_merchant_unlinked=True,
        dc5_contact_deleted=True,
        dc6_financial_pseudonymized=True,
        dc12_fraud_flags_retained=list(record.persistent_fraud_flags),
        completed_at_epoch=requested_at_epoch,
    )
