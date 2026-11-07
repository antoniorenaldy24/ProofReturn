# Evidence Report — Session 02: Return State Machine, Custody, Payments, MCP & FastAPI `/v1`

- **Date**: 2026-10-30
- **Task ID**: `SESSION-02-STATE-PAYMENTS-API`
- **Risk Class**: `HIGH` (TDD Red-Green-Refactor executed per `DUR-01`)
- **SSOT Sections Covered**: Sections 9, 10.2, 24, 26, 28, 29

## 1. Test Execution Summary

Command:
```powershell
uv run pytest -v
```
Result: **44 passed in 2.29s**

### New Test Suites Verified in Session 02

1. `backend/tests/state_machine/test_return_state_machine.py`
   - `test_all_35_allowed_transitions_t_sm01_to_t_sm35`: Verifies all 35 allowed transitions (`#1`–`#35`, `T-SM01`–`T-SM35`) in Section 26.2.
   - `test_t_sm_forbidden_p1_exhaustive_and_high_risk`: Exhaustively verifies every `(state, event)` pair in `ALL_RETURN_STATES × ALL_RETURN_EVENTS` not in Section 26.2 raises `InvalidStateTransitionError` (`Rule SM-F`), plus the named high-risk forbidden transitions (`STANDARD` pre-check-in tranche, re-filed return pre-check-in tranche, duplicate `KEEP_OFFERED`, and cancellation after `SUBMITTED`).
   - `test_concurrency_scenarios_ct01_to_ct12`: Verifies all 12 concurrency scenarios (`CT-01`–`CT-12`) in Section 26.4.
   - `test_custody_ledger_attribution_and_records_only`: Verifies 5-interval custody chain (`ORIGIN -> CARRIER_OUT -> SHOPPER -> CARRIER_RETURN -> DOCK`), earliest-interval degradation attribution (`FR-30`), and `records_only=True` (`FR-31`, `INV-07`, `INV-08`).

2. `backend/tests/payments/test_payments_and_failures.py`
   - `test_refund_ledger_outbox_idempotency_and_sandbox_guard`: Verifies `TM-16` startup Sandbox URL guard, `INV-07` non-custodial client surface (no `create_payout`), `INV-02` merchant/capture binding, `INV-03` deterministic `UUIDv5(namespace, decision_id + ":" + tranche)`, and `INV-01` `OverRefundError` before any network call.
   - `test_all_20_financial_failure_modes_fx01_to_fx20`: Verifies `FX-01` through `FX-20` (Section 24.2).
   - `test_webhook_deduplication_monotonicity_and_dispute_freeze`: Verifies webhook signature check (`FX-16`), `event_id` deduplication (`FX-05`), `CUSTOMER.DISPUTE.CREATED` tranche freeze (`FR-75`, `FX-10`), and `PAYMENT.CAPTURE.REVERSED` zeroing `remaining_refundable` (`FX-19`).
   - `test_reconciliation_jobs_rec01_to_rec04`: Verifies `REC-01` through `REC-04` (Section 24.4).

3. `backend/tests/api/test_api_authz_and_mcp.py`
   - `test_authorization_matrix_az01_to_az10`: Verifies tenant isolation (`404` on cross-merchant), agent order scope (`404` on other order), agent physical evidence block (`403` on challenge/upload per `INV-12`), `PACKER` policy edit block (`403`), `REVIEWER` decision routing via Policy Engine (`AZ-05`), shopper isolation (`404`), public passport privacy stripping (`FR-43`), and webhook signature rejection (`400`).
   - `test_api_contracts_idempotency_judge_mode_and_demo_guards`: Verifies `Idempotency-Key` conflict (`409 IDEMPOTENCY_CONFLICT`), Judge Mode `REPLAYED` (`FR-80`) vs `MANUAL (no model keys)` + `STANDARD` (`FR-99`), prompt injection detection (`FR-86`), `Demo clock` (`FR-81`), and `TM-24` carrier-events guard when `DEMO_MODE=false` (`FR-96`).
   - `test_mcp_server_agent_journey_j05`: Verifies `J-05` agent journey (`get_return_policy`, `start_return`, `get_keep_offer`, `respond_keep_offer`) with `actor="agent"` audit logging and counter-offer rejection.
   - `test_inv13_log_scrubber_removes_serials_and_pii`: Verifies `INV-13` and `NFR-08` log scrubbing.
