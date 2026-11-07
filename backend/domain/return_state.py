"""Return Lifecycle State Machine (#1-#35), Forbidden Transition Guard (Rule SM-F), and Concurrency Scenarios (CT-01..12) (Section 26)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class InvalidStateTransitionError(ValueError):
    """Raised when a state machine transition violates Section 26.2 or Section 26.3."""


ALL_RETURN_STATES: tuple[str, ...] = (
    "REQUESTED",
    "DECLARED",
    "EVIDENCE_SUBMITTED",
    "ASSESSED",
    "APPROVED",
    "KEEP_OFFERED",
    "KEEP_ACCEPTED",
    "AWAITING_SHIPMENT",
    "IN_TRANSIT",
    "NOT_RECEIVED",
    "LOST_IN_TRANSIT",
    "RECEIVED",
    "AUDIT_SELECTED",
    "AUDITED",
    "ESCALATED",
    "REVIEWED",
    "SETTLING",
    "SETTLED",
    "REJECTED",
    "DISPOSED",
    "CLOSED",
    "CANCELLED",
)

ALL_RETURN_EVENTS: tuple[str, ...] = (
    "SUBMIT_DECLARATION",
    "SUBMIT_EVIDENCE",
    "FINISH_ASSESSMENT",
    "APPROVE_RETURN",
    "ESCALATE_ASSESSMENT",
    "OFFER_KEEP",
    "ACCEPT_KEEP_OFFER",
    "CONFIRM_KEEP_REFUND",
    "DECLINE_KEEP_OFFER",
    "ISSUE_LABEL",
    "CARRIER_FIRST_SCAN",
    "SHIP_DEADLINE_MISSED",
    "LATE_CARRIER_SCAN",
    "EXTENDED_GRACE_ELAPSED",
    "CHECKIN_PASSED",
    "CHECKIN_DISCREPANCY",
    "CARRIER_EXCEPTION",
    "SETTLE_LOST_IN_TRANSIT",
    "SELECT_FOR_AUDIT",
    "RECORD_AUDIT",
    "START_SETTLEMENT_NO_AUDIT",
    "SETTLE_AUDITED",
    "COMPLETE_REVIEW",
    "REVIEW_APPROVE_PRESHIP",
    "REVIEW_SETTLE_POSTRECEIPT",
    "REVIEW_REJECT",
    "CONFIRM_SETTLEMENT",
    "CHOOSE_DISPOSITION",
    "EXECUTE_DISPOSITION",
    "CLOSE_REJECTED",
    "CANCEL_RETURN",
    "OPEN_DISPUTE",
    "FILE_APPEAL",
    "JURISDICTION_DEADLINE_REACHED",
)

# Section 26.2 allowed (from_state, event) pairs (#1..#35)
ALLOWED_STATE_EVENT_PAIRS: set[tuple[str, str]] = {
    ("REQUESTED", "SUBMIT_DECLARATION"),  # #1 T-SM01
    ("DECLARED", "SUBMIT_EVIDENCE"),  # #2 T-SM02
    ("EVIDENCE_SUBMITTED", "FINISH_ASSESSMENT"),  # #3 T-SM03
    ("ASSESSED", "APPROVE_RETURN"),  # #4 T-SM04
    ("ASSESSED", "ESCALATE_ASSESSMENT"),  # #5 T-SM05
    ("ASSESSED", "OFFER_KEEP"),  # #6 T-SM06
    ("KEEP_OFFERED", "ACCEPT_KEEP_OFFER"),  # #7 T-SM07
    ("KEEP_ACCEPTED", "CONFIRM_KEEP_REFUND"),  # #8 T-SM08
    ("KEEP_OFFERED", "DECLINE_KEEP_OFFER"),  # #9 T-SM09
    ("APPROVED", "ISSUE_LABEL"),  # #10 T-SM10
    ("AWAITING_SHIPMENT", "CARRIER_FIRST_SCAN"),  # #11 T-SM11
    ("AWAITING_SHIPMENT", "SHIP_DEADLINE_MISSED"),  # #12 T-SM12
    ("NOT_RECEIVED", "LATE_CARRIER_SCAN"),  # #13 T-SM13
    ("NOT_RECEIVED", "EXTENDED_GRACE_ELAPSED"),  # #14 T-SM14
    ("IN_TRANSIT", "CHECKIN_PASSED"),  # #15 T-SM15
    ("IN_TRANSIT", "CHECKIN_DISCREPANCY"),  # #16 T-SM16
    ("IN_TRANSIT", "CARRIER_EXCEPTION"),  # #17 T-SM17
    ("LOST_IN_TRANSIT", "SETTLE_LOST_IN_TRANSIT"),  # #18 T-SM18
    ("RECEIVED", "SELECT_FOR_AUDIT"),  # #19 T-SM19
    ("AUDIT_SELECTED", "RECORD_AUDIT"),  # #20 T-SM20
    ("RECEIVED", "START_SETTLEMENT_NO_AUDIT"),  # #21 T-SM21
    ("AUDITED", "SETTLE_AUDITED"),  # #22 T-SM22
    ("ESCALATED", "COMPLETE_REVIEW"),  # #23 T-SM23
    ("REVIEWED", "REVIEW_APPROVE_PRESHIP"),  # #24 T-SM24
    ("REVIEWED", "REVIEW_SETTLE_POSTRECEIPT"),  # #25 T-SM25
    ("REVIEWED", "REVIEW_REJECT"),  # #26 T-SM26
    ("SETTLING", "CONFIRM_SETTLEMENT"),  # #27 T-SM27
    ("SETTLED", "CHOOSE_DISPOSITION"),  # #28 T-SM28
    ("DISPOSED", "EXECUTE_DISPOSITION"),  # #29 T-SM29
    ("REJECTED", "CLOSE_REJECTED"),  # #30 T-SM30
    # #31 T-SM31 Cancel allowed from early pre-shipment states
    ("REQUESTED", "CANCEL_RETURN"),
    ("DECLARED", "CANCEL_RETURN"),
    ("EVIDENCE_SUBMITTED", "CANCEL_RETURN"),
    ("ASSESSED", "CANCEL_RETURN"),
    ("APPROVED", "CANCEL_RETURN"),
    ("AWAITING_SHIPMENT", "CANCEL_RETURN"),
    # #32 T-SM32 Open dispute flag allowed from active states
    ("APPROVED", "OPEN_DISPUTE"),
    ("AWAITING_SHIPMENT", "OPEN_DISPUTE"),
    ("IN_TRANSIT", "OPEN_DISPUTE"),
    ("RECEIVED", "OPEN_DISPUTE"),
    ("AUDIT_SELECTED", "OPEN_DISPUTE"),
    ("AUDITED", "OPEN_DISPUTE"),
    ("ESCALATED", "OPEN_DISPUTE"),
    ("SETTLING", "OPEN_DISPUTE"),
    # #33 T-SM33 Appeal flag allowed from SETTLED or REJECTED
    ("SETTLED", "FILE_APPEAL"),
    ("REJECTED", "FILE_APPEAL"),
    # #34 T-SM34 Jurisdiction deadline reached from ESCALATED or REVIEWED
    ("ESCALATED", "JURISDICTION_DEADLINE_REACHED"),
    ("REVIEWED", "JURISDICTION_DEADLINE_REACHED"),
}


@dataclass
class ReturnEntity:
    """In-memory domain model of a Return lifecycle entity."""

    return_id: str
    order_id: str
    state: str = "REQUESTED"
    lane: str = "FAST"
    timing: str = "R0"
    x_minor: int = 0
    checkin_minor: int = 0
    holdback_minor: int = 0
    tranches: dict[str, str] = field(default_factory=dict)
    keep_offered_once: bool = False
    disputed: bool = False
    appeal_open: bool = False
    refiled: bool = False
    version: int = 1
    history: list[tuple[str, str, str]] = field(default_factory=list)

    def confirm_all_tranches(self) -> None:
        """Mark all planned/submitted tranches as CONFIRMED."""
        for k in list(self.tranches.keys()):
            self.tranches[k] = "CONFIRMED"


class ReturnStateMachine:
    """Deterministic state machine enforcing Section 26.2 transitions and Section 26.3 forbidden guards."""

    def is_pair_potentially_allowed(self, state: str, event: str) -> bool:
        """Return True if (state, event) is in the Section 26.2 transition table."""
        return (state, event) in ALLOWED_STATE_EVENT_PAIRS

    def create_refiled_return(
        self,
        *,
        return_id: str,
        order_id: str,
        previous_cancelled_return_id: str,
    ) -> ReturnEntity:
        """Transition #35 (T-SM35): Refiled return after cancellation forces STANDARD lane (R2)."""
        if not previous_cancelled_return_id:
            raise InvalidStateTransitionError("Previous cancelled return_id required for refile.")
        return ReturnEntity(
            return_id=return_id,
            order_id=order_id,
            state="REQUESTED",
            lane="STANDARD",
            timing="R2",
            refiled=True,
        )

    def apply(self, entity: ReturnEntity, event: str, **guards: Any) -> ReturnEntity:
        """Apply an event to `entity` with guard checks; raise InvalidStateTransitionError on any violation."""
        if (entity.state, event) not in ALLOWED_STATE_EVENT_PAIRS:
            raise InvalidStateTransitionError(
                f"Forbidden transition ({entity.state}, {event}) per Rule SM-F."
            )

        old_state = entity.state

        if event == "SUBMIT_DECLARATION":  # #1 T-SM01
            if not (
                guards.get("within_window", False)
                and guards.get("authorized", False)
                and guards.get("consent_recorded", False)
            ):
                raise InvalidStateTransitionError("T-SM01 guards not satisfied.")
            entity.state = "DECLARED"

        elif event == "SUBMIT_EVIDENCE":  # #2 T-SM02
            if not (
                guards.get("evidence_complete", False)
                and (guards.get("challenge_valid", False) or (entity.lane == "STANDARD" and guards.get("challenge_not_verified", False)))
                and guards.get("retakes_ok", False)
            ):
                raise InvalidStateTransitionError("T-SM02 guards not satisfied.")
            entity.state = "EVIDENCE_SUBMITTED"

        elif event == "FINISH_ASSESSMENT":  # #3 T-SM03
            if not guards.get("assessment_exists", False):
                raise InvalidStateTransitionError("T-SM03 requires assessment_exists.")
            entity.state = "ASSESSED"

        elif event == "APPROVE_RETURN":  # #4 T-SM04
            if not guards.get("exposure_cap_ok", False):
                raise InvalidStateTransitionError("T-SM04 requires exposure_cap_ok.")
            # High-risk guard: STANDARD lane cannot have pre-check-in tranche
            if entity.lane == "STANDARD" and entity.x_minor > 0:
                raise InvalidStateTransitionError(
                    "Forbidden: STANDARD lane cannot schedule pre-check-in tranche."
                )
            # High-risk guard: Refiled return cannot receive pre-check-in tranche
            if entity.refiled and (entity.x_minor > 0 or entity.timing in {"R0", "R1"}):
                raise InvalidStateTransitionError(
                    "Forbidden: Refiled return cannot receive pre-check-in tranche."
                )
            entity.state = "APPROVED"
            if entity.lane == "FAST" and entity.timing == "R0" and entity.x_minor > 0 and not entity.disputed:
                entity.tranches["R0"] = "PLANNED"

        elif event == "ESCALATE_ASSESSMENT":  # #5 T-SM05
            entity.state = "ESCALATED"

        elif event == "OFFER_KEEP":  # #6 T-SM06
            if entity.keep_offered_once or not guards.get("eligible", False):
                raise InvalidStateTransitionError(
                    "Forbidden: KEEP_OFFERED cannot be reached twice or when ineligible."
                )
            entity.keep_offered_once = True
            entity.state = "KEEP_OFFERED"

        elif event == "ACCEPT_KEEP_OFFER":  # #7 T-SM07
            if not guards.get("not_expired", False):
                raise InvalidStateTransitionError("T-SM07 requires not_expired.")
            entity.state = "KEEP_ACCEPTED"
            if not entity.disputed:
                entity.tranches["KEEP"] = "PLANNED"

        elif event == "CONFIRM_KEEP_REFUND":  # #8 T-SM08
            if entity.tranches.get("KEEP") != "CONFIRMED":
                raise InvalidStateTransitionError("T-SM08 requires KEEP tranche CONFIRMED.")
            entity.state = "SETTLED"

        elif event == "DECLINE_KEEP_OFFER":  # #9 T-SM09
            target = guards.get("re_evaluated_lane", "APPROVED")
            if target not in {"APPROVED", "ESCALATED"}:
                raise InvalidStateTransitionError("T-SM09 target must be APPROVED or ESCALATED.")
            entity.state = target

        elif event == "ISSUE_LABEL":  # #10 T-SM10
            entity.state = "AWAITING_SHIPMENT"

        elif event == "CARRIER_FIRST_SCAN":  # #11 T-SM11
            if not (
                guards.get("seal_nonce_matches", False)
                and guards.get("source_authentic", False)
            ):
                raise InvalidStateTransitionError("T-SM11 requires matching seal nonce and authentic source.")
            entity.state = "IN_TRANSIT"
            if entity.lane == "FAST" and entity.timing == "R1" and entity.x_minor > 0 and not entity.disputed:
                entity.tranches["SCAN"] = "PLANNED"

        elif event == "SHIP_DEADLINE_MISSED":  # #12 T-SM12
            entity.state = "NOT_RECEIVED"

        elif event == "LATE_CARRIER_SCAN":  # #13 T-SM13
            if not guards.get("within_extended_grace", False):
                raise InvalidStateTransitionError("T-SM13 requires within_extended_grace.")
            entity.state = "IN_TRANSIT"

        elif event == "EXTENDED_GRACE_ELAPSED":  # #14 T-SM14
            entity.state = "CLOSED"

        elif event == "CHECKIN_PASSED":  # #15 T-SM15
            entity.state = "RECEIVED"
            if not guards.get("audit_selected", False) and not entity.disputed:
                entity.tranches["CHECKIN"] = "PLANNED"

        elif event == "CHECKIN_DISCREPANCY":  # #16 T-SM16
            entity.state = "ESCALATED"

        elif event == "CARRIER_EXCEPTION":  # #17 T-SM17
            if not guards.get("scan_existed", False):
                raise InvalidStateTransitionError("T-SM17 requires prior carrier scan.")
            entity.state = "LOST_IN_TRANSIT"

        elif event == "SETTLE_LOST_IN_TRANSIT":  # #18 T-SM18
            entity.state = "SETTLING"
            if not entity.disputed:
                entity.tranches["HOLDBACK"] = "PLANNED"

        elif event == "SELECT_FOR_AUDIT":  # #19 T-SM19
            if not guards.get("audit_selected", False):
                raise InvalidStateTransitionError("T-SM19 requires audit_selected=True.")
            entity.state = "AUDIT_SELECTED"

        elif event == "RECORD_AUDIT":  # #20 T-SM20
            if not (
                guards.get("inspector_authorized", False)
                and guards.get("photos_attached", False)
            ):
                raise InvalidStateTransitionError("T-SM20 requires authorized inspector and photos.")
            entity.state = "AUDITED"

        elif event == "START_SETTLEMENT_NO_AUDIT":  # #21 T-SM21
            entity.state = "SETTLING"
            if not entity.disputed:
                entity.tranches["HOLDBACK"] = "PLANNED"

        elif event == "SETTLE_AUDITED":  # #22 T-SM22
            if not guards.get("reviewer_confirmed", False):
                raise InvalidStateTransitionError("T-SM22 requires reviewer_confirmed.")
            entity.state = "SETTLING"
            if not entity.disputed:
                entity.tranches["FINAL"] = "PLANNED"

        elif event == "COMPLETE_REVIEW":  # #23 T-SM23
            if not guards.get("reviewer_authorized", False):
                raise InvalidStateTransitionError("T-SM23 requires reviewer_authorized.")
            entity.state = "REVIEWED"

        elif event == "REVIEW_APPROVE_PRESHIP":  # #24 T-SM24
            if not guards.get("pre_shipment", False):
                raise InvalidStateTransitionError("T-SM24 requires pre_shipment=True.")
            entity.state = "APPROVED"

        elif event == "REVIEW_SETTLE_POSTRECEIPT":  # #25 T-SM25
            if guards.get("pre_shipment", True):
                raise InvalidStateTransitionError("T-SM25 requires pre_shipment=False.")
            entity.state = "SETTLING"
            if not entity.disputed:
                entity.tranches["FINAL"] = "PLANNED"

        elif event == "REVIEW_REJECT":  # #26 T-SM26
            entity.state = "REJECTED"

        elif event == "CONFIRM_SETTLEMENT":  # #27 T-SM27
            if not entity.tranches or any(v != "CONFIRMED" for v in entity.tranches.values()):
                raise InvalidStateTransitionError("T-SM27 requires all scheduled tranches CONFIRMED.")
            entity.state = "SETTLED"

        elif event == "CHOOSE_DISPOSITION":  # #28 T-SM28
            entity.state = "DISPOSED"

        elif event == "EXECUTE_DISPOSITION" or event == "CLOSE_REJECTED":  # #29 T-SM29
            entity.state = "CLOSED"

        elif event == "CANCEL_RETURN":  # #31 T-SM31
            # High-risk guard: cannot cancel if any tranche is SUBMITTED or CONFIRMED
            for status in entity.tranches.values():
                if status in {"SUBMITTED", "CONFIRMED"}:
                    raise InvalidStateTransitionError(
                        "Forbidden: Cannot cancel return after a tranche is SUBMITTED or CONFIRMED."
                    )
            for k in list(entity.tranches.keys()):
                if entity.tranches[k] == "PLANNED":
                    entity.tranches[k] = "CANCELLED"
            entity.state = "CANCELLED"

        elif event == "OPEN_DISPUTE":  # #32 T-SM32
            entity.disputed = True

        elif event == "FILE_APPEAL":  # #33 T-SM33
            if not guards.get("within_appeal_window", False):
                raise InvalidStateTransitionError("T-SM33 requires within_appeal_window=True.")
            entity.appeal_open = True

        elif event == "JURISDICTION_DEADLINE_REACHED":  # #34 T-SM34
            if not guards.get("sla_exceeded", False):
                raise InvalidStateTransitionError("T-SM34 requires sla_exceeded=True.")
            entity.state = "SETTLING"
            if not entity.disputed:
                entity.tranches["UNDISPUTED"] = "PLANNED"

        entity.version += 1
        entity.history.append((old_state, event, entity.state))
        return entity
