# ADR-021: Judge mode with recorded AI outputs + lite profile

- Status: Accepted
- Date: 2026-10-27
- Related IDs: F-16

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `F-16`.

## Decision

Judge mode with recorded AI outputs + lite profile

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Reproducibility for judges without GPU or model keys
- **Traceability**: Enforced via `F-16` and verified at release gates (Section 27).
