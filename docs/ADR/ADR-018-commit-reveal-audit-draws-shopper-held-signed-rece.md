# ADR-018: Commit–reveal audit draws + shopper-held signed receipts

- Status: Amended by ADR-026
- Date: 2026-10-27
- Related IDs: FR-61, FR-76, INV-16

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `FR-61, FR-76, INV-16`.

## Decision

Commit–reveal audit draws + shopper-held signed receipts

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Verifiable randomness; tamper evidence
- **Traceability**: Enforced via `FR-61, FR-76, INV-16` and verified at release gates (Section 27).
