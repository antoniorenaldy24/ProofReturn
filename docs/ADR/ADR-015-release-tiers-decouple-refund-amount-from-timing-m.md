# ADR-015: Release tiers decouple refund amount from timing; money tracked as tranches

- Status: Amended by ADR-023
- Date: 2026-10-27
- Related IDs: FR-22, FR-58, Section 26

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `FR-22, FR-58, Section 26`.

## Decision

Release tiers decouple refund amount from timing; money tracked as tranches

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Closes W-01/W-03; avoids state explosion
- **Traceability**: Enforced via `FR-22, FR-58, Section 26` and verified at release gates (Section 27).
