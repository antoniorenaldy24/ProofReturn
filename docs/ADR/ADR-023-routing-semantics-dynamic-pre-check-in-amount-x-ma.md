# ADR-023: Routing semantics + dynamic pre-check-in amount `X_max`; `R1h` removed

- Status: Accepted (amends ADR-015)
- Date: 2026-10-27
- Related IDs: Section 8, FR-87, FR-88

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `Section 8, FR-87, FR-88`.

## Decision

Routing semantics + dynamic pre-check-in amount `X_max`; `R1h` removed

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Closes second-audit V-01; preserves partial speed
- **Traceability**: Enforced via `Section 8, FR-87, FR-88` and verified at release gates (Section 27).
