# ADR-026: Shopper nonce in audit seed; optional public beacon

- Status: Accepted (amends ADR-018)
- Date: 2026-10-27
- Related IDs: FR-95

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `FR-95`.

## Decision

Shopper nonce in audit seed; optional public beacon

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Prevents platform seed grinding
- **Traceability**: Enforced via `FR-95` and verified at release gates (Section 27).
