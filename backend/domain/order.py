"""Immutable order and Condition-Indexed Refund Curve (CIRC) snapshot at purchase (F-02, FR-09)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType

from backend.domain.policy import PolicyConfig


@dataclass(frozen=True)
class OrderSnapshot:
    order_id: str
    price_minor: int
    currency: str
    policy_version: str
    jurisdiction: str
    curve_snapshot: Mapping[str, str]
    f_minor: int

    @classmethod
    def create(
        cls,
        *,
        order_id: str,
        price_minor: int,
        policy: PolicyConfig,
        currency: str = "USD",
    ) -> OrderSnapshot:
        """FR-09: Snapshot curve version into the order at purchase so later edits never apply retroactively."""
        return cls(
            order_id=order_id,
            price_minor=price_minor,
            currency=currency,
            policy_version=policy.version,
            jurisdiction=policy.jurisdiction,
            curve_snapshot=MappingProxyType(dict(policy.curve_json)),
            f_minor=policy.compute_f_minor(price_minor),
        )

    def refund_for_grade(self, grade: str) -> int:
        r_g = Fraction(self.curve_snapshot[grade])
        return int(Fraction(self.price_minor) * r_g)
