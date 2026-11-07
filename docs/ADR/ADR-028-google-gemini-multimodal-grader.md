# ADR-028: Google Gemini Multimodal Grader with Generous Free-Tier Integration

- Status: Accepted
- Date: 2026-10-30
- Related IDs: Section 7.1, Section 10.2, Section 35.1, ADR-009, INV-05

## Context

In SSOT v1.2.1 Section 7.1 and ADR-009, Claude 3.5 Sonnet was specified as the recommended primary grader. However, conducting active live multimodal assessments on user-provided return photos and development testing incurred commercial API costs and required paid credits.
Google AI Studio offers Google Gemini (`gemini-3.6-flash`) with a free tier (15 RPM / 1,500 RPD) supporting fast multimodal vision reasoning and native structured JSON outputs.

## Decision

Support Google Gemini as a primary multimodal AI provider via a lightweight `httpx`-based REST client in `backend/ai/providers/gemini.py`:
1. Use `gemini-3.6-flash` by default with low temperature and native `response_schema` enforcement matching ProofReturn's condition assessment schema.
2. Maintain strict separation of concerns per `INV-05` (AI outputs are strictly advisory forensic observations; financial determinations and release timing are governed solely by `backend/policy_engine/`).
3. Ensure backwards compatibility with `F-16` Judge Mode: if no API key is provided, the system falls back to `REPLAYED` fixtures or routes unknown media to `STANDARD` (`FR-99`).

## Alternatives Considered

1. **Anthropic Claude Sonnet 3.5**: Strong reasoning but requires paid credits with no free tier.
2. **OpenAI GPT-4o-mini**: Inexpensive, but no persistent zero-cost tier for development.
3. **Local Self-Hosted VLM (Qwen2.5-VL via Ollama/vLLM)**: Fully offline and zero-cost, but requires a local GPU machine ($>= 8$ GB VRAM) which may not be available on all developer environments.

## Consequences

- **Positive**: Developers and users can run live end-to-end multimodal grading completely free of charge simply by supplying `GEMINI_API_KEY`.
- **Latency & Reliability**: Sub-2s evaluation latency on photo return submissions.
- **Traceability**: All evaluations record model ID (`gemini-3.6-flash`) in the assessment audit trail (`FR-80`, `INV-09`).
