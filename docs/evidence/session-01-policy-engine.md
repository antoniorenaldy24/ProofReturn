# Evidence Record — Session 01: Monorepo Scaffolding, Domain Core, Policy Engine v2.1 & Simulator

- **Date**: 2026-10-30
- **Milestone**: `MS-0` / `MS-1` / `MS-3` (Policy Engine & Formal Verification)
- **Risk Class**: `HIGH` (Policy Engine v2.1 & Money Arithmetic)
- **TDD Execution (`DUR-01`)**: Failing test suites (`test_golden_examples.py`, `test_mechanism_verification.py`, `test_domain_and_schemas.py`) authored and executed prior to implementation (3 collection errors on missing modules), followed by implementation and full green pass (32/32 tests passing).

## 1. Test Suites Executed

- **Command**: `uv run pytest -v`
- **Result**: `32 passed in 1.85s`
- **Lint / Typecheck**: `uv run ruff check backend sim scripts` -> `All checks passed!`
- **Cross-Reference Integrity**: `uv run python scripts/check_refs.py` -> `check-refs PASSED (XR-01..XR-10 verified).`

## 2. Verified Golden Examples (`Section 8.8 & 25.1`)

| Case | Description | Expected | Observed | Status |
|:--|:--|:--|:--|:-:|
| `E1` | `P=$400`, B, `TRUSTED`, `R0` | `p=0.05`, `X=$221.57`, `H=$60`, `G_D=-$0.90`, `Leak=$17.10` | Exact match | PASS |
| `E2` | v1.2 bug regression (`X=$320`) | `G_D(0.05)=+$8.475`, `G_D(1.0)=+$8.00` (rejected) | Exact match | PASS |
| `E3` | `P=$400`, B, `NEW`, `R2` | `p=0.05`, `X=$0.00`, `G_D=-$1.05` | Exact match | PASS |
| `E4` | `P=$2,000`, B, `TRUSTED`, `R1` | `F=$100`, `X=$947.87`, `G_D=-$4.50` | Exact match | PASS |
| `E5` | `P=$400`, B, `NEW`, EU (`F=0`) | `STANDARD` (`p=0.25`, `X=0`) | Exact match | PASS |
| `E6` | `P=$400`, A, `TRUSTED`, `R0` | `X=$225.93` (binding gap D), `H=$20`, `G=-$0.50` | Exact match | PASS |
| `E7` | `P=$300`, A, `NEW`, `R2` | `p=0.20`, `X=$0.00`, `G=-$0.62` | Exact match | PASS |
| `E8` | Low-data profile (`d_D=0.22`) | `STANDARD` (`p_req approx 0.73 > p_max`) | Exact match | PASS |
| `Legacy` | v1.1 §8.4 historical regression | `G_C=-4.57`, `G_D=-25.43` | Exact match | PASS |
| `Map B` | 15-cell Feasibility Map (Declared B) | All 15 cells match Section 8.8 table | Exact match | PASS |
| `Map A` | 15-cell Feasibility Map (Declared A) | All 15 cells match Section 8.8 table | Exact match | PASS |

## 3. Formal Mechanism Verification (`Section 25.2: MV-01..MV-26`)

- `MV-01`..`MV-09`: Property & unit tests verified via Hypothesis and pytest.
- `MV-10`: Independent brute-force oracle (`sim/oracle.py`, searching `p` step `1e-4` and `X` step `$0.01` without importing `backend.policy_engine`) matches closed-form solver across all price × tier × grade cells.
- `MV-11`: Symbolic derivation (`sim/verify_symbolic.py`, SymPy) confirms `G_k`, relative margin inequality, floor condition, and `X_max` from the settlement payoff tree.
- `MV-12`: Rule-based simulator (`sim/engine.py`, 4,000 Monte Carlo trials) agrees with analytic `G_k` within the 95% confidence interval.
- `MV-13`..`MV-26`: Jurisdiction caps, account/aggregate exposure caps, adjacent non-penalization (`INV-15`), commit–reveal with shopper nonce (`INV-16`), CUSUM monitor, posted-price keep-offer without bounds (`FR-78`), routing semantics (`INV-17`), 5th-percentile pooled calibration (`FR-100`), best-response attacker (`sim/attacker.py`), identity groups & value-weighted promotion (`FR-91`, `FR-93`), and fallback degradation (`INV-18`) all passing.
