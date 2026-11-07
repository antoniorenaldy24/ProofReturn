# ADR-007: Deterministic Policy Engine separated from AI

- Status: Accepted
- Date: 2026-10-27
- Related IDs: INV-05

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `INV-05`.

## Decision

Deterministic Policy Engine separated from AI

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Auditability; injection resistance
- **Traceability**: Enforced via `INV-05` and verified at release gates (Section 27).
