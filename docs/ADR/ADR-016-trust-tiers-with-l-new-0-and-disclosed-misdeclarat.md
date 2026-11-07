# ADR-016: Trust tiers with `L_NEW = 0` and disclosed misdeclaration cost for gross gaps only

- Status: Accepted
- Date: 2026-10-27
- Related IDs: FR-57, FR-59, INV-15

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `FR-57, FR-59, INV-15`.

## Decision

Trust tiers with `L_NEW = 0` and disclosed misdeclaration cost for gross gaps only

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Honest incentives without punishing uncertainty
- **Traceability**: Enforced via `FR-57, FR-59, INV-15` and verified at release gates (Section 27).
