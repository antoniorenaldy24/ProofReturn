# ADR-011: Challenge-response as primary forensic defense

- Status: Accepted
- Date: 2026-10-27
- Related IDs: F-04

## Context

Documented in ProofReturn SSOT v1.2.1 (Section 46.2) to govern system architecture, mechanism integrity, and compliance for `F-04`.

## Decision

Challenge-response as primary forensic defense

## Alternatives considered

Evaluated against alternative architectural and mechanism options during SSOT v1.0, v1.1, v1.2, and v1.2.1 audits (see Appendices E and F).

## Consequences (positive, negative, follow-ups)

- **Key reason / positive impact**: Detectors are brittle
- **Traceability**: Enforced via `F-04` and verified at release gates (Section 27).
