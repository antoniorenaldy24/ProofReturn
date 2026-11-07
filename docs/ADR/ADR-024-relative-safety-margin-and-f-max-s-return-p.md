# ADR-024: Relative safety margin `μ` and `F = max(S_return, φ·P)`

- Status: Accepted
- Date: 2026-10-27
- Related IDs: FR-89, FR-59

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `FR-89, FR-59`.

## Decision

Relative safety margin `μ` and `F = max(S_return, φ·P)`

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Absolute margins are infeasible under routing semantics; proportional `F` keeps NEW floor feasible in US demo
- **Traceability**: Enforced via `FR-89, FR-59` and verified at release gates (Section 27).
