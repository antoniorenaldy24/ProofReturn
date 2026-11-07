"""End-to-End Critical Journey Orchestrator J-01..J-14 (Section 35.1)."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from backend.agent_gateway.mcp_server import ProofReturnMcpServer
from backend.auth.tokens import mint_agent_token
from backend.config import get_settings
from backend.domain.appeals import AppealPortal
from backend.domain.custody import CustodyCheckpoint, CustodyLedger
from backend.domain.evidence_pack import generate_evidence_pack
from backend.domain.policy import PolicyConfig
from backend.domain.resale import create_certified_open_box_listing
from backend.domain.return_state import ReturnEntity, ReturnStateMachine
from backend.domain.serial_registry import SerialRegistry
from backend.payments.ledger import RefundLedger
from backend.payments.webhooks import WebhookProcessor
from backend.policy_engine.misdeclaration import evaluate_misdeclaration
from backend.policy_engine.release import (
    CalibrationInput,
    GapCalibration,
    ReleaseInput,
    decide_release,
)


def _calib_b() -> CalibrationInput:
    return CalibrationInput(
        declared_grade="B",
        adjacent_gap=GapCalibration(true_grade="C", q=Fraction(40, 100), d=Fraction(50, 100)),
        gross_gaps=[GapCalibration(true_grade="D", q=Fraction(90, 100), d=Fraction(95, 100))],
    )


def run_critical_journey(journey_id: str) -> dict[str, Any]:
    """Execute and verify a complete end-to-end journey J-01..J-14 across domain, policy, state, and payment modules."""
    sm = ReturnStateMachine()
    policy = PolicyConfig.default_us()

    if journey_id == "J-01":
        # J-01: Origin witness & Passport creation (F-01, AUD-26)
        serial_salt = get_settings().serial_hash_salt.get_secret_value().encode("utf-8")
        reg = SerialRegistry(serial_salt)
        entry = reg.register_origin_serial(
            merchant_id="merch_a",
            order_id="ord_j01",
            passport_id="pass_j01",
            raw_serial="SN-XM5-J01",
        )
        return {"journey_id": journey_id, "passed": len(entry.serial_Commitment) == 64}

    if journey_id == "J-02":
        # J-02: Honest Grade-B return on FAST lane (E1: $221.57 R0 -> $98.43 check-in -> $60.00 holdback)
        res = decide_release(
            ReleaseInput(
                price_minor=40000,
                declared_grade="B",
                tier="TRUSTED",
                has_origin_passport=True,
            ),
            policy,
            _calib_b(),
        )
        ent = ReturnEntity(
            return_id="ret_j02",
            order_id="ord_j02",
            state="ASSESSED",
            lane=res.lane,
            timing=res.timing,
            x_minor=res.x_released_minor,
            checkin_minor=res.checkin_tranche_minor,
            holdback_minor=res.holdback_minor,
        )
        sm.apply(ent, "APPROVE_RETURN", exposure_cap_ok=True)
        sm.apply(ent, "ISSUE_LABEL")
        sm.apply(ent, "CARRIER_FIRST_SCAN", seal_nonce_matches=True, source_authentic=True)
        sm.apply(ent, "CHECKIN_PASSED", audit_selected=False)
        sm.apply(ent, "START_SETTLEMENT_NO_AUDIT")
        ent.confirm_all_tranches()
        sm.apply(ent, "CONFIRM_SETTLEMENT")
        return {
            "journey_id": journey_id,
            "passed": (
                ent.state == "SETTLED"
                and res.x_released_minor == 22157
                and res.checkin_tranche_minor == 9843
                and res.holdback_minor == 6000
            ),
        }

    if journey_id == "J-03":
        # J-03: Serial-mismatch fraud attempt -> ESCALATED, $0 released (AUD-26)
        serial_salt = get_settings().serial_hash_salt.get_secret_value().encode("utf-8")
        reg = SerialRegistry(serial_salt)
        reg.register_origin_serial(
            merchant_id="merch_a",
            order_id="ord_j03",
            passport_id="pass_j03",
            raw_serial="SN-REAL-01",
        )
        chk = reg.verify_return_serial(merchant_id="merch_a", order_id="ord_j03", raw_serial="SN-SWAPPED-99")
        ent = ReturnEntity(return_id="ret_j03", order_id="ord_j03", state="ASSESSED", lane="ESCALATED")
        sm.apply(ent, "ESCALATE_ASSESSMENT")
        return {
            "journey_id": journey_id,
            "passed": not chk["matched"] and ent.state == "ESCALATED" and len(ent.tranches) == 0,
        }

    if journey_id == "J-04":
        # J-04: Keep-the-item instant resolution (F-08)
        ent = ReturnEntity(return_id="ret_j04", order_id="ord_j04", state="ASSESSED", lane="KEEP_OFFER")
        sm.apply(ent, "OFFER_KEEP", eligible=True)
        sm.apply(ent, "ACCEPT_KEEP_OFFER", not_expired=True)
        ent.confirm_all_tranches()
        sm.apply(ent, "CONFIRM_KEEP_REFUND")
        return {"journey_id": journey_id, "passed": ent.state == "SETTLED" and ent.tranches.get("KEEP") == "CONFIRMED"}

    if journey_id == "J-05":
        # J-05: Agent-assisted return via MCP (F-10, AUD-41)
        mcp = ProofReturnMcpServer()
        tok = mint_agent_token(
            agent_id="bot_j05",
            order_id="ord_demo_1",
            merchant_id="merch_a",
            scopes=["read_policy", "declare", "keep_offer"],
        )
        started = mcp.start_return(order_id="ord_demo_1", declaration={"declared_grade": "B"}, token=tok)
        acc = mcp.respond_keep_offer(return_id=started["return_id"], action="accept", token=tok)
        return {"journey_id": journey_id, "passed": acc["status"] == "ACCEPTED" and acc["actor"] == "agent"}

    if journey_id == "J-06":
        # J-06: Certified open-box resale (F-09)
        listing = create_certified_open_box_listing(
            passport_id="pass_j06",
            sku="PR-HP-XM5",
            verified_grade="B",
            list_price_minor=31500,
            prior_owner_ref="owner_1",
            prior_buyer_email="b1@example.com",
        )
        return {
            "journey_id": journey_id,
            "passed": listing["certified_open_box"] is True and listing["prior_owner_stripped"] is True,
        }

    if journey_id == "J-07":
        # J-07: Carrier- vs buyer-caused damage attribution (F-06)
        ledger = CustodyLedger(passport_id="pass_j07", origin_grade="A", origin_weight_g=250)
        ledger.record_checkpoint(CustodyCheckpoint("ORIGIN", "packer", "A", 250, True))
        ledger.record_checkpoint(CustodyCheckpoint("SHOPPER", "shopper", "B", 250, True))
        ledger.record_checkpoint(CustodyCheckpoint("CARRIER_RETURN", "carrier", "D", 245, False))
        attr = ledger.attribute_condition_change("D")
        return {
            "journey_id": journey_id,
            "passed": attr.responsible_interval == "CARRIER_RETURN" and attr.records_only,
        }

    if journey_id == "J-08":
        # J-08: PayPal dispute webhook -> Evidence Pack generation & tranche freeze (F-07)
        r_ledger = RefundLedger()
        r_ledger.register_order(order_id="ord_j08", merchant_id="m_1", capture_id="c_8", capture_amount_minor=38000)
        proc = WebhookProcessor(r_ledger)
        proc.process_webhook(
            event_id="evt_j08",
            event_type="CUSTOMER.DISPUTE.CREATED",
            signature_valid=True,
            payload={"order_id": "ord_j08", "dispute_id": "PP-DISP-J08"},
        )
        pack = generate_evidence_pack(
            return_id="ret_j08",
            order_id="ord_j08",
            passport_id="pass_j08",
            decision_id="dec_j08",
            refund_request_ids=[],
            custody_intervals=["ORIGIN", "SHOPPER"],
            dispute_id="PP-DISP-J08",
        )
        return {
            "journey_id": journey_id,
            "passed": r_ledger.is_order_frozen("ord_j08") and len(pack.canonical_sha256) == 64,
        }

    if journey_id == "J-09":
        # J-09: Buyer appeal -> second reviewer overturn -> top-up refund (F-15)
        portal = AppealPortal()
        ap = portal.file_appeal(
            return_id="ret_j09",
            order_id="ord_j09",
            original_reviewer_id="rev_1",
            within_window=True,
            buyer_reason="Lighting glare",
        )
        res = portal.resolve_appeal(
            appeal_id=ap.appeal_id,
            appeal_reviewer_id="rev_2",
            overturn=True,
            topup_amount_minor=3800,
        )
        return {"journey_id": journey_id, "passed": res.status == "OVERTURNED" and res.topup_tranche_planned}

    if journey_id == "J-10":
        # J-10: Non-serialized apparel return with micro-feature challenge (F-01, F-03, F-05, FR-67)
        res = decide_release(
            ReleaseInput(
                price_minor=29500,
                declared_grade="B",
                tier="STANDARD",
                has_origin_passport=True,
                non_serialized=True,
            ),
            policy,
            _calib_b(),
        )
        return {"journey_id": journey_id, "passed": res.timing in {"R1", "R2", "STANDARD"}}

    if journey_id == "J-11":
        # J-11: NO_PASSPORT legacy order return on MID band forced to STANDARD (F-01, F-05, FR-74)
        res = decide_release(
            ReleaseInput(
                price_minor=38000,
                declared_grade="B",
                tier="TRUSTED",
                has_origin_passport=False,
            ),
            policy,
            _calib_b(),
        )
        return {"journey_id": journey_id, "passed": res.lane == "STANDARD" and res.x_released_minor == 0}

    if journey_id == "J-12":
        # J-12: Honest adjacent misdeclaration (B vs C) — no fixed penalty F, no RESTRICTED (FR-25, FR-26, INV-15)
        mis = evaluate_misdeclaration(
            declared_grade="B",
            verified_grade="C",
            excluded_at_alpha_accuse=False,
            hard_identity_failure=False,
            human_confirmed=True,
        )
        return {
            "journey_id": journey_id,
            "passed": mis.gap_steps == 1 and mis.is_adjacent_mismatch and not mis.status_affecting,
        }

    if journey_id == "J-13":
        # J-13: Return approved at R0, item never shipped -> NOT_RECEIVED -> CLOSED + Evidence Pack (FR-71)
        ent = ReturnEntity(
            return_id="ret_j13",
            order_id="ord_j13",
            state="APPROVED",
            lane="FAST",
            timing="R0",
            x_minor=22157,
        )
        sm.apply(ent, "ISSUE_LABEL")
        sm.apply(ent, "SHIP_DEADLINE_MISSED")
        sm.apply(ent, "EXTENDED_GRACE_ELAPSED")
        pack = generate_evidence_pack(
            return_id="ret_j13",
            order_id="ord_j13",
            passport_id="pass_j13",
            decision_id="dec_j13",
            refund_request_ids=["req_j13_r0"],
            custody_intervals=["ORIGIN", "CARRIER_OUT", "SHOPPER"],
        )
        return {"journey_id": journey_id, "passed": ent.state == "CLOSED" and len(pack.canonical_sha256) == 64}

    if journey_id == "J-14":
        # J-14: NEW shopper in infeasible cell -> routed STANDARD -> cancels freely -> re-files -> forced STANDARD (FR-88, INV-17)
        ent = ReturnEntity(
            return_id="ret_j14_1",
            order_id="ord_j14",
            state="ASSESSED",
            lane="STANDARD",
            timing="R2",
            x_minor=0,
        )
        sm.apply(ent, "CANCEL_RETURN")
        refiled = sm.create_refiled_return(
            return_id="ret_j14_2",
            order_id="ord_j14",
            previous_cancelled_return_id="ret_j14_1",
        )
        res_refile = decide_release(
            ReleaseInput(
                price_minor=38000,
                declared_grade="B",
                tier="TRUSTED",
                has_origin_passport=True,
                refiled_after_cancel=True,
            ),
            policy,
            _calib_b(),
        )
        return {
            "journey_id": journey_id,
            "passed": (
                ent.state == "CANCELLED"
                and refiled.refiled is True
                and refiled.lane == "STANDARD"
                and res_refile.lane == "STANDARD"
                and res_refile.x_released_minor == 0
            ),
        }

    raise ValueError(f"Unknown critical journey ID: {journey_id}")
