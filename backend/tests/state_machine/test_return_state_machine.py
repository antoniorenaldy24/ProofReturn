"""Exhaustive tests for Return State Machine (#1-#35), Forbidden Transitions, Concurrency (CT-01..12), and Custody Ledger (Section 26, F-06)."""

from __future__ import annotations

import pytest

from backend.domain.custody import CustodyCheckpoint, CustodyLedger
from backend.domain.return_state import (
    ALL_RETURN_EVENTS,
    ALL_RETURN_STATES,
    InvalidStateTransitionError,
    ReturnEntity,
    ReturnStateMachine,
)
from backend.tests.support.concurrency import run_concurrency_scenario


@pytest.mark.req("INV-04", "FR-22", "FR-71", "FR-72", "FR-73", "FR-88", "FR-97")
def test_all_35_allowed_transitions_t_sm01_to_t_sm35() -> None:
    """Section 26.2: Verify every allowed transition #1..#35 (T-SM01..T-SM35)."""
    sm = ReturnStateMachine()

    # T-SM01..04: REQUESTED -> DECLARED -> EVIDENCE_SUBMITTED -> ASSESSED -> APPROVED (R0)
    r = ReturnEntity(return_id="ret_1", order_id="ord_1", state="REQUESTED", lane="FAST", timing="R0", x_minor=22157, checkin_minor=9843, holdback_minor=6000)
    sm.apply(r, "SUBMIT_DECLARATION", within_window=True, authorized=True, consent_recorded=True)  # T-SM01
    assert r.state == "DECLARED"
    sm.apply(r, "SUBMIT_EVIDENCE", evidence_complete=True, challenge_valid=True, retakes_ok=True)  # T-SM02
    assert r.state == "EVIDENCE_SUBMITTED"
    sm.apply(r, "FINISH_ASSESSMENT", assessment_exists=True)  # T-SM03
    assert r.state == "ASSESSED"
    sm.apply(r, "APPROVE_RETURN", exposure_cap_ok=True)  # T-SM04
    assert r.state == "APPROVED"
    assert "R0" in r.tranches and r.tranches["R0"] == "PLANNED"

    # T-SM10..11: APPROVED -> AWAITING_SHIPMENT -> IN_TRANSIT (R1 scan tranche when timing=R1)
    r_r1 = ReturnEntity(return_id="ret_r1", order_id="ord_2", state="APPROVED", lane="FAST", timing="R1", x_minor=15618, checkin_minor=9882, holdback_minor=4500)
    sm.apply(r_r1, "ISSUE_LABEL")  # T-SM10
    assert r_r1.state == "AWAITING_SHIPMENT"
    sm.apply(r_r1, "CARRIER_FIRST_SCAN", seal_nonce_matches=True, source_authentic=True)  # T-SM11
    assert r_r1.state == "IN_TRANSIT"
    assert r_r1.tranches.get("SCAN") == "PLANNED"

    # T-SM15, 21, 27, 28, 29: IN_TRANSIT -> RECEIVED (no audit) -> SETTLING -> SETTLED -> DISPOSED -> CLOSED
    sm.apply(r_r1, "CHECKIN_PASSED", audit_selected=False)  # T-SM15
    assert r_r1.state == "RECEIVED"
    assert r_r1.tranches.get("CHECKIN") == "PLANNED"
    sm.apply(r_r1, "START_SETTLEMENT_NO_AUDIT")  # T-SM21
    assert r_r1.state == "SETTLING"
    assert r_r1.tranches.get("HOLDBACK") == "PLANNED"
    r_r1.confirm_all_tranches()
    sm.apply(r_r1, "CONFIRM_SETTLEMENT")  # T-SM27
    assert r_r1.state == "SETTLED"
    sm.apply(r_r1, "CHOOSE_DISPOSITION")  # T-SM28
    assert r_r1.state == "DISPOSED"
    sm.apply(r_r1, "EXECUTE_DISPOSITION")  # T-SM29
    assert r_r1.state == "CLOSED"

    # T-SM19, 20, 22: RECEIVED -> AUDIT_SELECTED -> AUDITED -> SETTLING
    r_aud = ReturnEntity(return_id="ret_aud", order_id="ord_3", state="IN_TRANSIT", lane="FAST", timing="R2", x_minor=0, checkin_minor=32000, holdback_minor=6000)
    sm.apply(r_aud, "CHECKIN_PASSED", audit_selected=True)
    sm.apply(r_aud, "SELECT_FOR_AUDIT", audit_selected=True)  # T-SM19
    assert r_aud.state == "AUDIT_SELECTED"
    sm.apply(r_aud, "RECORD_AUDIT", inspector_authorized=True, photos_attached=True)  # T-SM20
    assert r_aud.state == "AUDITED"
    sm.apply(r_aud, "SETTLE_AUDITED", reviewer_confirmed=True)  # T-SM22
    assert r_aud.state == "SETTLING"

    # T-SM06, 07, 08 & T-SM09: KEEP_OFFERED -> KEEP_ACCEPTED -> SETTLED and KEEP_OFFERED -> APPROVED
    r_ko = ReturnEntity(return_id="ret_ko", order_id="ord_4", state="ASSESSED", lane="KEEP_OFFER")
    sm.apply(r_ko, "OFFER_KEEP", eligible=True)  # T-SM06
    assert r_ko.state == "KEEP_OFFERED"
    sm.apply(r_ko, "ACCEPT_KEEP_OFFER", not_expired=True)  # T-SM07
    assert r_ko.state == "KEEP_ACCEPTED"
    assert r_ko.tranches.get("KEEP") == "PLANNED"
    r_ko.confirm_all_tranches()
    sm.apply(r_ko, "CONFIRM_KEEP_REFUND")  # T-SM08
    assert r_ko.state == "SETTLED"

    r_ko_dec = ReturnEntity(return_id="ret_ko2", order_id="ord_5", state="KEEP_OFFERED", lane="FAST")
    r_ko_dec.keep_offered_once = True
    sm.apply(r_ko_dec, "DECLINE_KEEP_OFFER", re_evaluated_lane="APPROVED")  # T-SM09
    assert r_ko_dec.state == "APPROVED"

    # T-SM05, 23, 24, 25, 26, 30: ESCALATED -> REVIEWED -> APPROVED | SETTLING | REJECTED -> CLOSED
    r_esc = ReturnEntity(return_id="ret_esc", order_id="ord_6", state="ASSESSED", lane="ESCALATED")
    sm.apply(r_esc, "ESCALATE_ASSESSMENT")  # T-SM05
    assert r_esc.state == "ESCALATED" and len(r_esc.tranches) == 0
    sm.apply(r_esc, "COMPLETE_REVIEW", reviewer_authorized=True)  # T-SM23
    assert r_esc.state == "REVIEWED"
    sm.apply(r_esc, "REVIEW_APPROVE_PRESHIP", pre_shipment=True)  # T-SM24
    assert r_esc.state == "APPROVED"

    r_esc_post = ReturnEntity(return_id="ret_esc_p", order_id="ord_7", state="IN_TRANSIT", lane="FAST")
    sm.apply(r_esc_post, "CHECKIN_DISCREPANCY")  # T-SM16
    assert r_esc_post.state == "ESCALATED"
    sm.apply(r_esc_post, "COMPLETE_REVIEW", reviewer_authorized=True)
    sm.apply(r_esc_post, "REVIEW_SETTLE_POSTRECEIPT", pre_shipment=False)  # T-SM25
    assert r_esc_post.state == "SETTLING"

    r_rej = ReturnEntity(return_id="ret_rej", order_id="ord_8", state="REVIEWED")
    sm.apply(r_rej, "REVIEW_REJECT")  # T-SM26
    assert r_rej.state == "REJECTED"
    sm.apply(r_rej, "CLOSE_REJECTED")  # T-SM30
    assert r_rej.state == "CLOSED"

    # T-SM12, 13, 14: AWAITING_SHIPMENT -> NOT_RECEIVED -> IN_TRANSIT (late scan) or CLOSED
    r_nr = ReturnEntity(return_id="ret_nr", order_id="ord_9", state="AWAITING_SHIPMENT")
    sm.apply(r_nr, "SHIP_DEADLINE_MISSED")  # T-SM12
    assert r_nr.state == "NOT_RECEIVED"
    sm.apply(r_nr, "LATE_CARRIER_SCAN", within_extended_grace=True)  # T-SM13
    assert r_nr.state == "IN_TRANSIT"

    r_nr2 = ReturnEntity(return_id="ret_nr2", order_id="ord_10", state="NOT_RECEIVED")
    sm.apply(r_nr2, "EXTENDED_GRACE_ELAPSED")  # T-SM14
    assert r_nr2.state == "CLOSED"

    # T-SM17, 18: IN_TRANSIT -> LOST_IN_TRANSIT -> SETTLING
    r_lost = ReturnEntity(return_id="ret_lost", order_id="ord_11", state="IN_TRANSIT")
    sm.apply(r_lost, "CARRIER_EXCEPTION", scan_existed=True)  # T-SM17
    assert r_lost.state == "LOST_IN_TRANSIT"
    sm.apply(r_lost, "SETTLE_LOST_IN_TRANSIT")  # T-SM18
    assert r_lost.state == "SETTLING"

    # T-SM31, 32, 33, 34, 35: Cancel, Disputed flag, Appeal flag, Deadline auto-release, Refiled return
    r_can = ReturnEntity(return_id="ret_can", order_id="ord_12", state="APPROVED")
    sm.apply(r_can, "CANCEL_RETURN")  # T-SM31
    assert r_can.state == "CANCELLED"

    r_disp = ReturnEntity(return_id="ret_disp", order_id="ord_13", state="IN_TRANSIT")
    sm.apply(r_disp, "OPEN_DISPUTE")  # T-SM32
    assert r_disp.disputed is True

    r_app = ReturnEntity(return_id="ret_app", order_id="ord_14", state="SETTLED")
    sm.apply(r_app, "FILE_APPEAL", within_appeal_window=True)  # T-SM33
    assert r_app.appeal_open is True

    r_sla = ReturnEntity(return_id="ret_sla", order_id="ord_15", state="ESCALATED")
    sm.apply(r_sla, "JURISDICTION_DEADLINE_REACHED", sla_exceeded=True)  # T-SM34
    assert r_sla.state == "SETTLING"
    assert r_sla.tranches.get("UNDISPUTED") == "PLANNED"

    r_refile = sm.create_refiled_return(return_id="ret_ref", order_id="ord_12", previous_cancelled_return_id="ret_can")  # T-SM35
    assert r_refile.state == "REQUESTED"
    assert r_refile.refiled is True
    assert r_refile.lane == "STANDARD"


@pytest.mark.req("INV-04", "INV-17")
def test_t_sm_forbidden_p1_exhaustive_and_high_risk() -> None:
    """Section 26.3 Rule SM-F: Every (state, event) pair not in 26.2 raises InvalidStateTransitionError and creates no tranche."""
    sm = ReturnStateMachine()
    for state in ALL_RETURN_STATES:
        for event in ALL_RETURN_EVENTS:
            if sm.is_pair_potentially_allowed(state, event):
                continue
            ent = ReturnEntity(return_id="ret_f", order_id="ord_f", state=state)
            before_tranches = dict(ent.tranches)
            with pytest.raises(InvalidStateTransitionError):
                sm.apply(ent, event)
            assert ent.state == state
            assert ent.tranches == before_tranches

    # Named high-risk forbidden transitions (Section 26.3):
    # 1. STANDARD lane tranche before RECEIVED
    r_std = ReturnEntity(return_id="ret_std", order_id="ord_s", state="ASSESSED", lane="STANDARD", timing="STANDARD", x_minor=10000)
    with pytest.raises(InvalidStateTransitionError):
        sm.apply(r_std, "APPROVE_RETURN", exposure_cap_ok=True)

    # 2. Re-filed return receiving any pre-check-in tranche
    r_ref = ReturnEntity(return_id="ret_rf", order_id="ord_rf", state="ASSESSED", lane="FAST", timing="R0", x_minor=5000, refiled=True)
    with pytest.raises(InvalidStateTransitionError):
        sm.apply(r_ref, "APPROVE_RETURN", exposure_cap_ok=True)

    # 3. KEEP_OFFERED reached twice for one return
    r_ko2 = ReturnEntity(return_id="ret_ko2", order_id="ord_k", state="ASSESSED", keep_offered_once=True)
    with pytest.raises(InvalidStateTransitionError):
        sm.apply(r_ko2, "OFFER_KEEP", eligible=True)

    # 4. Cancellation after a tranche is SUBMITTED
    r_sub = ReturnEntity(return_id="ret_sub", order_id="ord_sub", state="AWAITING_SHIPMENT")
    r_sub.tranches["R0"] = "SUBMITTED"
    with pytest.raises(InvalidStateTransitionError):
        sm.apply(r_sub, "CANCEL_RETURN")


@pytest.mark.req("INV-01", "INV-04", "INV-14")
def test_concurrency_scenarios_ct01_to_ct12() -> None:
    """Section 26.4: Verify all 12 concurrency scenarios CT-01..CT-12."""
    for ct_id in [
        "CT-01", "CT-02", "CT-03", "CT-04", "CT-05", "CT-06",
        "CT-07", "CT-08", "CT-09", "CT-10", "CT-11", "CT-12",
    ]:
        res = run_concurrency_scenario(ct_id)
        assert res["passed"] is True, f"{ct_id} failed: {res}"


@pytest.mark.req("FR-29", "FR-30", "FR-31", "INV-07", "INV-08")
def test_custody_ledger_attribution_and_records_only() -> None:
    """F-06 (FR-29, FR-30, FR-31): Attribution to earliest interval where condition worsened; records-only."""
    ledger = CustodyLedger(passport_id="pass_01", origin_grade="A", origin_weight_g=250)
    ledger.record_checkpoint(CustodyCheckpoint(interval="ORIGIN", actor="packer", grade_observed="A", weight_g=250, seal_intact=True))
    ledger.record_checkpoint(CustodyCheckpoint(interval="CARRIER_OUT", actor="carrier", grade_observed="A", weight_g=250, seal_intact=True))
    ledger.record_checkpoint(CustodyCheckpoint(interval="SHOPPER", actor="shopper", grade_observed="B", weight_g=250, seal_intact=True))
    ledger.record_checkpoint(CustodyCheckpoint(interval="CARRIER_RETURN", actor="carrier", grade_observed="D", weight_g=248, seal_intact=False))
    ledger.record_checkpoint(CustodyCheckpoint(interval="DOCK", actor="receiver", grade_observed="D", weight_g=248, seal_intact=False))

    attribution = ledger.attribute_condition_change(target_grade="D")
    assert attribution.responsible_interval == "CARRIER_RETURN"
    assert attribution.records_only is True
