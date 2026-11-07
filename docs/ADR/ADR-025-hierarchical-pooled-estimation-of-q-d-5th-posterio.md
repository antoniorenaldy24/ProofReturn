# ADR-025: Hierarchical pooled estimation of `q`/`d` (5th posterior percentile)

- Status: Accepted
- Date: 2026-10-27
- Related IDs: FR-100, Section 11.3

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `FR-100, Section 11.3`.

## Decision

Hierarchical pooled estimation of `q`/`d` (5th posterior percentile)

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Per-cell bounds collapse with feasible data sizes
- **Traceability**: Enforced via `FR-100, Section 11.3` and verified at release gates (Section 27).
