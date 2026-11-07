# ADR-008: Split conformal prediction for grades

- Status: Superseded by ADR-017
- Date: 2026-10-27
- Related IDs: INV-10

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `INV-10`.

## Decision

Split conformal prediction for grades

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Bounded false-accusation rate
- **Traceability**: Enforced via `INV-10` and verified at release gates (Section 27).
