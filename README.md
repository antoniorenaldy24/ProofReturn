# ProofReturn

> **Fair, evidence-based returns — speed earned through trust and proof. Agent-ready, PayPal-native.**

ProofReturn is a fair, evidence-based returns engine built on PayPal Sandbox and multi-model AI. It creates a signed, hash-chained **Condition Passport** at packing (`F-01`), lets shoppers or AI shopping agents declare condition with value-scaled challenge-response capture (`F-03`, `F-04`), and uses a deterministic **Policy Engine** (`F-05`, `INV-05`) to compute:

1. **How much to refund**: Condition-Indexed Refund Curve (`CIRC`, `F-02`).
2. **When money may move**: release timing `R0` (at approval), `R1` (at carrier first scan of the sealed return), or `R2` (after check-in), determined by trust tier and item value band.
3. **How much may move before check-in**: the dynamic pre-check-in amount `X_max`, bounded so that under calibrated assumptions, declaring truthfully maximizes expected payoff for gross condition overclaims inside the feasible region, while outside the feasible region the engine verifies before paying.

---

## Core Capabilities & Honest Boundaries

- **Feasibility-Aware Release Engine (`F-05`)**: Routing semantics (`INV-17` — an intake exclusion only routes to `STANDARD`, cancellation is free, and re-filed returns are forced to `STANDARD`), dynamic pre-check-in amount `X_max`, one-grade holdback `H`, universal low-cost Dock Quick-Check plus sampled full audit with a shopper-co-seeded commit–reveal draw (`FR-95`, `INV-16`), and value-weighted trust tiers and exposure caps (`FR-91`–`FR-93`, `INV-14`).
- **Two-Way Fairness & Protection (`F-07`, `F-15`)**: Honest shoppers are never accused or penalized on a single adjacent-grade mismatch (`INV-15`). Status-affecting findings require one-sided conformal exclusion at `α_accuse = 0.02` on check-in/audit evidence **plus** human confirmation (`INV-10`). Shoppers receive signed receipts (`FR-76`) and have appeal rights with compensating decisions (`FR-69`).
- **Agent-Ready Condition Evidence (`F-10`)**: Machine-readable **Condition Passport** (`schemas/condition-passport.v1.json`), return declaration (`schemas/return-declaration.v1.json`), and single posted-price keep-offers (`schemas/keep-offer.v1.json`, accept or decline only, `FR-78`) exposed via an MCP server and REST API.
- **What ProofReturn Does Not Claim**:
  - Incentives address gross condition overclaims inside the feasible region; custody fraud (empty box, item swap, not shipping) is bounded by release timing, seals, weight checks, and exposure caps (`Section 8.1`).
  - Adjacent one-grade overclaims are not punished per return; they are settled at the verified grade, budgeted as leakage at `ρ_stress = 0.30`, and monitored across returns (`Section 8.10`).
  - Refunds are **initiated** in seconds via PayPal partial refunds on the original capture (`NFR-01`); statement visibility depends on the buyer's funding source.
  - The **Condition Passport** is item-condition evidence for returns and certified resale, distinct from the EU Digital Product Passport (ESPR).

---

## Quick Start (Judge Mode — CPU-Only, `F-16`, `NFR-15`)

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Start the Lite Docker Compose profile (PostgreSQL 16 + pgvector, Redis, MinIO, and FastAPI service):
   ```bash
   docker compose -f infra/docker-compose.yml --profile lite up -d --build
   ```
   *(Or using the Makefile shortcut: `make up COMPOSE_PROFILE=lite`)*

3. Verify service readiness probe:
   ```bash
   curl -s http://localhost:8000/v1/ready
   ```
   Expected output:
   ```json
   {
     "status": "ready",
     "database_connected": true,
     "active_alerts_count": 0,
     "demo_mode": true
   }
   ```

4. Alternatively, run locally on bare-metal with Python 3.12 and `uv`:
   ```bash
   make bootstrap
   make check-refs
   make gate
   make test
   make sim
   make run
   ```

---

## Demo Boundaries & Known Limitations (`Section 48`, `Section 16`)

- **Calibration Profile**: The demo uses an illustrative calibration profile (`CALIBRATION_PROFILE=illustrative`), visibly badged in the UI and simulator (`Section 8.8`).
- **Seeded Demo Accounts**: Demo `TRUSTED` and `ESTABLISHED` shopper profiles use seeded history (`SIMULATED`) and are labeled in the UI.
- **Carrier Events**: Carrier first-scan and exception events in the demo use a labeled mock stand-in (`MOCK`, `FR-96`).
- **Authentication Outside DEMO_MODE (`RV3-05`, `API-04`)**:
  - The hackathon release is declared strictly as **DEMO_MODE only**.
  - **Status**: `DEFERRED`
  - **Reason**: Production identity provider integration (staff login via external SSO/OAuth2/OIDC with MFA) and transactional email infrastructure (shopper magic-link delivery via SMTP/SES with single-use hashed tokens) are out of scope for the hackathon prototype release.
  - **Date**: 2026-11-07
  - **Owner**: Security & Identity Workstream
  - **Runtime Behavior**: When `DEMO_MODE=false`, the application logs startup warning `AUTH_NOT_AVAILABLE_OUTSIDE_DEMO`, reports `"auth": "demo_only"` on `GET /v1/ready`, and fails closed without returning any authentication tokens.
- **Residual Risks (`R-15`–`R-26`)**: Long-con custody exposure is bounded (not eliminated) by value-weighted caps (`R-15`); small adjacent biases are detected gradually by the CUSUM monitor (`R-16`, `R-26`); keep-offer harvesting is bounded by `(1 - θ_h) * k_max` and frequency caps (`R-17`); network-wide trust across merchants (`RM-01`) is a roadmap item (`NOT-AVAILABLE`).

---

## License

MIT License — see [LICENSE](LICENSE).
