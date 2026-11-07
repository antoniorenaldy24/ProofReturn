# ADR-006: Outbox pattern + deterministic `PayPal-Request-Id`

- Status: Accepted
- Date: 2026-10-27
- Related IDs: Section 24

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `Section 24`.

## Decision

Outbox pattern + deterministic `PayPal-Request-Id`

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Exactly-once money effects
- **Traceability**: Enforced via `Section 24` and verified at release gates (Section 27).
