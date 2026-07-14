# FINALIS 1000 — SP0004 Research Register (Source URLs)

Research corpus for the Continuous Technology Sovereignty Constitution, corroborated
by SWARM-C on execution day (2026-07-11) via web search. **Honesty note:**
`WebFetch` is blocked by bot-protection in this environment (HTTP 403); page bodies
could not be re-fetched, so URLs are recorded as provided and corroborated against
search snippets. Anything dated after 2026-07-11 is flagged future-dated and is
NOT adopted as finalized evidence (D-0004-49: release candidates are not finalized
specifications).

## Verified 2026 status (SWARM-C)
- **MCP** — finalized spec **2025-11-25** (current); a **2026-07-28 RC** exists but is
  future-dated and NOT adopted. Pinned as an interoperability boundary (TDR-0014).
- **A2A** — **v1.0** stable (Linux Foundation). Interop boundary (TDR-0015).
- **OpenTelemetry** — CNCF-graduated (May 2026); traces/metrics/logs stable, profiling RC. Standardize with replaceable backend (TDR-0013).
- **SLSA** — **v1.2** approved specification line. Supply-chain target (TDR-0016).
- **CycloneDX** — **1.7** (ECMA-424 2nd ed); AI/ML-BOM since 1.6. AI/ML-BOM target.
- **SPDX** — **3.0.1** finalized; 3.1 is RC. Evaluate.
- **Temporal** — durable-execution infrastructure, not business truth; no sunset. Durable-runtime candidate (TDR-0010, DEFERRED).
- **Python 3.11** — security-fix phase, **EOL 2027-10-31** (TDR-0001). **FastAPI** ~0.135 (still 0.x). **SQLite** — Postgres recommended for high-concurrency prod (TDR-0003).
- **Model silent-swap** — a live 2026 risk; no cryptographic provider-model identity proof exists → `PROVIDER_IMPLEMENTATION_IDENTITY_UNCERTAINTY` (D-0004-52, AC-0004-139).
- **Open source ≠ no lock-in** — arxiv 2409.01118 (soft lock-in) confirmed.

## Architecture Decision Records
- https://adr.github.io/
- https://github.com/architecture-decision-record/architecture-decision-record
- https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record
- https://www.gov.uk/government/publications/architectural-decision-record-framework/architectural-decision-record-framework

## Architecture Fitness Functions
- https://continuous-architecture.org/practices/fitness-functions/
- https://www.thoughtworks.com/insights/decoder/f/fitness-functions
- https://www.thoughtworks.com/en-us/insights/podcasts/technology-podcasts/how-fitness-functions-help-govern-measure-ai

## OpenAI agent / harness architecture
- https://openai.com/index/the-next-evolution-of-the-agents-sdk/
- https://openai.com/index/unlocking-the-codex-harness/
- https://openai.com/index/harness-engineering/
- https://developers.openai.com/api/docs/guides/agents
- https://developers.openai.com/tracks/building-agents

## MCP
- https://modelcontextprotocol.io/
- https://modelcontextprotocol.io/specification/2025-11-25
- https://modelcontextprotocol.io/development/roadmap
- https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/
- https://modelcontextprotocol.io/seps
- https://modelcontextprotocol.io/llms.txt

## A2A
- https://a2a-protocol.org/latest/
- https://a2a-protocol.org/latest/specification/
- https://a2a-protocol.org/latest/definitions/
- https://a2a-protocol.org/latest/announcing-1.0/
- https://a2a-protocol.org/latest/whats-new-v1/
- https://a2a-protocol.org/latest/roadmap/
- https://a2a-protocol.org/latest/sdk/

## Temporal / durable execution
- https://docs.temporal.io/temporal
- https://docs.temporal.io/evaluate/understanding-temporal
- https://docs.temporal.io/workflows
- https://docs.temporal.io/workflow-execution/continue-as-new

## OpenTelemetry
- https://opentelemetry.io/
- https://opentelemetry.io/docs/
- https://opentelemetry.io/docs/what-is-opentelemetry/
- https://opentelemetry.io/docs/specs/semconv/
- https://opentelemetry.io/docs/concepts/instrumentation/
- https://opentelemetry.io/docs/guidance/

## SLSA 1.2
- https://slsa.dev/
- https://slsa.dev/spec/v1.2/
- https://slsa.dev/spec/v1.2/build-track-basics
- https://slsa.dev/spec/v1.2/source-requirements
- https://slsa.dev/spec/v1.2/verifying-source
- https://slsa.dev/attestation-model

## CycloneDX
- https://cyclonedx.org/
- https://cyclonedx.org/docs/latest
- https://cyclonedx.org/tool-center/
- https://cyclonedx.org/guides/OWASP_CycloneDX-Authoritative-Guide-to-AI-ML-BOM-en.pdf
- https://cyclonedx.org/capabilities/mlbom/

## SPDX
- https://spdx.dev/
- https://spdx.dev/use/specifications/
- https://spdx.github.io/spdx-spec/v3.0.1/

## Research
- https://arxiv.org/abs/2409.01118  (open source / soft lock-in)
- https://arxiv.org/html/2606.31590v1  (digital sovereignty as architecture quality)
- https://arxiv.org/abs/2604.26482  (agentic build-vs-buy economics)
- https://openreview.net/forum?id=3DZeEUTwhq  (model substitution audit — research input only; no cryptographic provider-model identity claim)

## Viktor (vendor claims / product guidance)
- https://viktor.com/
- https://viktor.com/product
- https://viktor.com/integrations
- https://viktor.com/research
- https://viktor.com/research/what-breaks-when-your-agent-has-100000-tools
- https://viktor.com/compare/viktor-vs-openclaw
- https://viktor.com/compare/viktor-vs-chatgpt
- https://app.viktor.com/tos

Treated as vendor claims and product guidance, not independent proof of internal
architecture. Finalis extends Viktor's public lessons (scoped integrations,
controlled credentials, shared workspace) with proof-carrying authority,
tenant-scoped credential capability, conformance testing, canonical replay and
exit readiness.
