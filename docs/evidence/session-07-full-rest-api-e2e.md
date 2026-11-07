# Session 07 Evidence — Complete 23-Endpoint REST API `/v1` Surface (`Section 10.6` & `Section 28`) & E2E HTTP Integration Suite

- **Timestamp**: `2026-10-31T12:16:00+07:00`
- **Session**: `Session 07`
- **Risk Class**: `HIGH` (`RC-1` for API endpoints touching return declarations, keep-offer acceptance, appeals, and certified resale ownership transfers)

## 1. Endpoints Implemented & Verified (`backend/api/app.py`)

All 23 REST API `/v1` endpoints specified in `Section 10.6` are now active and verified end-to-end:
1. `POST /v1/orders/{id}/passport` — Origin Passport minting at packing station with value-band tier selection (`FULL`/`LITE`, `FR-01`, `FR-63`, `FR-98`).
2. `GET /v1/orders/{id}/policy` — Condition-Indexed Refund Curve (`CIRC`), windows, and Fast Lane status (`FR-08`, `FR-84`).
3. `POST /v1/returns` — Idempotent return initiation (`Idempotency-Key` with `409 IDEMPOTENCY_CONFLICT`).
4. `POST /v1/returns/{id}/declaration` — Declaration submission enforcing explicit Fast Lane consent (`FR-12`, `FR-14`) and recording `shopper_nonce` (`FR-95`).
5. `GET /v1/returns/{id}/challenge` — Value-scaled challenge script & nonce (`FR-13`, `INV-12` agent block).
6. `POST /v1/returns/{id}/evidence` — Evidence registration enforcing client-side face-blur privacy check (`FR-16`, `<= 50 ms`) and routing/assessment (`FR-17`).
7. `GET /v1/returns/{id}` — Return status, tranches, and plain-language explanations (`INV-06`).
8. `POST /v1/returns/{id}/keep-offer/respond` — Single posted-price keep-offer `ACCEPT`/`DECLINE` (`FR-39`, `FR-46`, `FR-78`, `INV-06` bounds never disclosed).
9. `POST /v1/receiving/{passport_id}/checkpoint` — Dock quick-check & custody checkpoint (`FR-29`, `FR-31` `records_only=True`).
10. `POST /v1/audits/{return_id}` — Full audit result recording (`FR-23`, `FR-25`).
11. `GET /v1/returns/{id}/evidence-pack` — Canonical SHA-256 Evidence Pack download for disputes and shoppers (`FR-33`, `FR-35`).
12. `POST /v1/review/{return_id}/decision` — Human reviewer decision routed through deterministic Policy Engine (`FR-50`, `AZ-05`).
13. `GET /v1/policies` & `POST /v1/policies` — Policy version listing and creation (`FR-51`, `AZ-04`).
14. `POST /v1/simulate` — Interactive Policy Simulator what-if run (`FR-52`, `NFR-16`).
15. `POST /v1/resale/listings` & `POST /v1/resale/listings/{id}/order` — Certified Open-Box resale listing and purchase with prior-owner PII stripping (`FR-40`, `FR-41`, `FR-42`, `FR-43`).
16. `POST /v1/webhooks/paypal` — Signature-verified PayPal webhook receiver (`AZ-08`, `NFR-04`).
17. `POST /v1/returns/{id}/dropoff` — Sealed return package drop-off photo + carrier tracking (`FR-64`).
18. `GET /v1/returns/{id}/receipts` — Ed25519-signed shopper receipts (`INTAKE`, `DELIVERY`) and commit–reveal audit seed verification (`FR-61`, `FR-76`, `FR-77`, `FR-95`).
19. `POST /v1/appeals`, `GET /v1/appeals/{id}`, & `POST /v1/review/appeals/{id}/decision` — 14-day shopper appeal workflow enforcing independent reviewer (`appeal_reviewer_id != original_reviewer_id` -> `409 SAME_REVIEWER_CONFLICT`) and compensating refund tranche (`FR-69`).
20. `POST /v1/carrier-events` — Carrier scan/exception stand-in guarded by `DEMO_MODE` (`FR-96`, `TM-24`).
21. `POST /v1/demo/clock/advance` & `POST /v1/demo/reset` — Demo clock and golden snapshot reset (`FR-81`, `BK-05`).
22. `GET /v1/simulate/feasibility-map` & `GET /v1/simulate/roi` — 15-cell Feasibility Map (`SIMULATED`, `illustrative`) and Merchant ROI model (`model, not measured`, `FR-79`, `FR-101`).
23. `POST /v1/privacy/deletion-requests` — GDPR/CCPA subject erasure & crypto-shredding (`Section 33.4`, `FR-82`, `FR-94`, `NFR-05`).

## 2. Test & Verification Results

- `uv run pytest -v` -> **71 passed** (including `backend/tests/api/test_full_rest_api_v1.py`).
- `uv run ruff check backend sim scripts` -> **All checks passed!**
- `uv run python scripts/sync_rtm.py` -> **120 `VERIFIED`**, **17 `IMPLEMENTED`**, **0 `SPECIFIED`**.
- `uv run python scripts/check_refs.py` -> **check-refs PASSED (XR-01..XR-10 verified).**
