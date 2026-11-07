# ADR-012: PostgreSQL Row-Level Security for tenant isolation

- Status: Accepted
- Date: 2026-10-27
- Related IDs: Section 29

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `Section 29`.

## Decision

PostgreSQL Row-Level Security for tenant isolation

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Defense in depth
- **Traceability**: Enforced via `Section 29` and verified at release gates (Section 27).
