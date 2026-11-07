"""Custody-Interval Attribution Ledger (F-06: FR-29, FR-30, FR-31, INV-07, INV-08)."""

from __future__ import annotations

from dataclasses import dataclass, field

CUSTODY_INTERVAL_ORDER: tuple[str, ...] = (
    "ORIGIN",
    "CARRIER_OUT",
    "SHOPPER",
    "CARRIER_RETURN",
    "DOCK",
)

GRADE_SEVERITY: dict[str, int] = {
    "A": 0,
    "B": 1,
    "C": 2,
    "D": 3,
}


@dataclass(frozen=True)
class CustodyCheckpoint:
    """Single custody checkpoint observation along the 5-interval chain."""

    interval: str
    actor: str
    grade_observed: str
    weight_g: int
    seal_intact: bool


@dataclass(frozen=True)
class CustodyAttribution:
    """Attribution result pinpointing the earliest interval where condition worsened."""

    passport_id: str
    target_grade: str
    responsible_interval: str
    weight_delta_g: int
    seal_broken_in_interval: bool
    records_only: bool = True


@dataclass
class CustodyLedger:
    """Tracks custody checkpoints and attributes condition changes without moving carrier funds (INV-07, INV-08)."""

    passport_id: str
    origin_grade: str
    origin_weight_g: int
    checkpoints: list[CustodyCheckpoint] = field(default_factory=list)

    def record_checkpoint(self, checkpoint: CustodyCheckpoint) -> None:
        """Append a checkpoint in custody interval order."""
        if checkpoint.interval not in CUSTODY_INTERVAL_ORDER:
            raise ValueError(f"Invalid custody interval: {checkpoint.interval}")
        self.checkpoints.append(checkpoint)

    def attribute_condition_change(self, target_grade: str) -> CustodyAttribution:
        """Attribute condition degradation to the earliest interval reaching `target_grade` (FR-30, FR-31)."""
        target_sev = GRADE_SEVERITY[target_grade]
        for cp in self.checkpoints:
            if GRADE_SEVERITY.get(cp.grade_observed, 0) >= target_sev:
                return CustodyAttribution(
                    passport_id=self.passport_id,
                    target_grade=target_grade,
                    responsible_interval=cp.interval,
                    weight_delta_g=cp.weight_g - self.origin_weight_g,
                    seal_broken_in_interval=not cp.seal_intact,
                    records_only=True,
                )
        return CustodyAttribution(
            passport_id=self.passport_id,
            target_grade=target_grade,
            responsible_interval="UNDETERMINED",
            weight_delta_g=0,
            seal_broken_in_interval=False,
            records_only=True,
        )
