# UCP / ACP Condition-Evidence & Keep-Offer Extension Mapping (FR-48)

> **Status**: Documented extension alignment (`[ASSUMPTION A-12]`, `Section 48.2` `NOT-AVAILABLE` for live external protocol transport; concrete hackathon transport is MCP + REST `/v1`).

## 1. Purpose

ProofReturn does not invent a competing commerce protocol. Instead, it defines a **Condition-Evidence and Posted-Price Keep-Offer Extension** (`com.proofreturn.condition_evidence.v1`) that plugs into:
- **UCP (Universal Commerce Protocol)** `Order` and post-purchase return capabilities.
- **ACP (Agentic Commerce Protocol)** post-purchase return initiation and refund settlement flows.

## 2. Concept & Field Mapping

| UCP / ACP Concept | ProofReturn Schema / Field | Notes |
|:--|--|--|
| `Order.id` / `OrderLineItem.id` | `ConditionPassport.order_id`, `ReturnDeclaration.order_id` | Binds the Condition Passport and return declaration to the original order line. |
| `Order.payment.capture_id` | `orders.paypal_order_id`, `orders.capture_id` | PayPal Orders v2 capture against which partial refund tranches are executed (`INV-02`). |
| `ReturnPolicy` capability | `GET /v1/orders/{id}/policy` / MCP `get_return_policy` | Exposes the snapshotted Condition-Indexed Refund Curve (`CIRC`), return window, jurisdiction rules, and evidence requirements. |
| `ReturnRequest` payload | `schemas/return-declaration.v1.json` (`start_return`) | Carries `declared_grade`, `accessories`, `reason_code`, `consent_fast_lane_terms`, `nonce_shopper`, and `actor` (`human` or `agent`). |
| Physical verification step | `GET /v1/returns/{id}/challenge` (`get_evidence_challenge`) | Enforces `INV-12`: agents can declare and query status, but a human session must perform the physical camera challenge. |
| Return resolution / alternative | `schemas/keep-offer.v1.json` (`get_keep_offer`, `respond_keep_offer`) | Exposes a single posted-price keep-offer (`posted_price.amount_minor`); only `accept` or `decline` actions are valid (`FR-46`, `FR-78`). |
| Refund execution | `ReturnStatus.amounts.tranches[]` (`R0`, `SCAN`, `CHECKIN`, `HOLDBACK`, `TOPUP`, `KEEP`, `COMP`) | Tracks deterministic partial refund tranches on the merchant's capture (`INV-01`, `INV-03`, `INV-05`). |
| Tamper-evident receipt | `GET /v1/returns/{id}/receipts` | Ed25519-signed `INTAKE`, `CHECKIN`, and `SETTLEMENT` receipts containing the audit commitment `c`, `nonce_shopper`, revealed seed, and PayPal refund IDs (`FR-76`, `FR-95`). |
