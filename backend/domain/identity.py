"""Identity groups and velocity limits across linked accounts (FR-93, Section 8.3 & 10.4)."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.domain.trust import compute_account_exposure_cap_minor

TIER_RANK = {"RESTRICTED": 0, "NEW": 1, "ESTABLISHED": 2, "TRUSTED": 3}
RANK_TO_TIER = {v: k for k, v in TIER_RANK.items()}


@dataclass
class IdentityGroup:
    group_id: str
    account_ids: set[str] = field(default_factory=set)
    payer_hashes: set[str] = field(default_factory=set)
    address_hashes: set[str] = field(default_factory=set)
    device_hashes: set[str] = field(default_factory=set)
    lowest_tier: str = "TRUSTED"
    shared_cap_minor: int = 0
    outstanding_pre_checkin_minor: int = 0
    open_pre_checkin_count: int = 0
    accounts_with_fast_30d: set[str] = field(default_factory=set)

    def remaining_cap_minor(self) -> int:
        return max(0, self.shared_cap_minor - self.outstanding_pre_checkin_minor)

    def can_use_fast_velocity(
        self,
        account_id: str,
        max_open_pre_checkin: int = 2,
        max_accounts_per_address_30d: int = 3,
    ) -> bool:
        """FR-93: <= 2 open pre-check-in releases per group; <= 3 accounts per address hash with FAST in 30 days."""
        if self.open_pre_checkin_count >= max_open_pre_checkin:
            return False
        candidate_set = set(self.accounts_with_fast_30d) | {account_id}
        return not len(candidate_set) > max_accounts_per_address_30d


class IdentityGroupManager:
    """Links accounts sharing salted payer, shipping-address, or device hashes into a single IdentityGroup (FR-93)."""

    def __init__(self) -> None:
        self._groups: dict[str, IdentityGroup] = {}
        self._hash_to_group: dict[str, str] = {}
        self._counter = 0

    def link_account(
        self,
        account_id: str,
        *,
        payer_hash: str,
        address_hash: str,
        device_hash: str,
        tier: str,
        largest_clean_minor: int,
    ) -> str:
        keys = [f"PAYER:{payer_hash}", f"ADDR:{address_hash}", f"DEV:{device_hash}"]
        existing_id: str | None = None
        for k in keys:
            if k in self._hash_to_group:
                existing_id = self._hash_to_group[k]
                break

        account_cap = compute_account_exposure_cap_minor(tier, largest_clean_minor)
        if existing_id is None:
            self._counter += 1
            gid = f"idgrp_{self._counter}"
            grp = IdentityGroup(
                group_id=gid,
                account_ids={account_id},
                payer_hashes={payer_hash},
                address_hashes={address_hash},
                device_hashes={device_hash},
                lowest_tier=tier,
                shared_cap_minor=account_cap,
            )
            self._groups[gid] = grp
            existing_id = gid
        else:
            grp = self._groups[existing_id]
            grp.account_ids.add(account_id)
            grp.payer_hashes.add(payer_hash)
            grp.address_hashes.add(address_hash)
            grp.device_hashes.add(device_hash)
            # FR-93: Linked accounts share the lowest tier and one exposure cap
            new_rank = min(TIER_RANK[grp.lowest_tier], TIER_RANK[tier])
            grp.lowest_tier = RANK_TO_TIER[new_rank]
            grp.shared_cap_minor = min(grp.shared_cap_minor, account_cap)

        for k in keys:
            self._hash_to_group[k] = existing_id
        return existing_id

    def get_group(self, group_id: str) -> IdentityGroup:
        return self._groups[group_id]
