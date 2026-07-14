# FINALIS 1000 — SP0002 Research Register

**Executed 2026-07-11.** RETRIEVAL LIMITATION: direct `WebFetch` returned HTTP 403
on every host (bot-protection; proxy healthy). All content corroborated via
WebSearch snippets from the same primary domains. All 2026-dated arXiv IDs
resolved to real, on-topic papers (none fabricated); items not corroborated are
flagged and excluded from evidentiary use.

## A. Academic — semantic grounding, world models, contract evolution

| Source | URL | Status | Implication |
|---|---|---|---|
| Ontology-grounded tool architectures / operational grounding + drift vectors | https://arxiv.org/abs/2605.11234 | CURRENT (via index) | Grounding is OPERATIONAL not lexical; drift vectors = tool-federation gap, ontology-version independence, free-text param variance → **canonical typed ids + version-pinned meaning (epochs) at the substrate, not "ask the LLM to be consistent"**. |
| World-centered multi-agent semantics (WMAS/Ontobox) | https://arxiv.org/pdf/2604.01359 | CURRENT (via index) | Structured domains need ONE explicit shared world model for consistency + verifiable behavior → **the canonical-meaning layer IS the shared world model; workers reference it**. |
| Ontology-constrained enterprise agents (role/domain/interaction) | https://arxiv.org/abs/2604.00555 · /html/2604.00555v2 | CURRENT (via index) | Role/domain/interaction semantics must be explicit + machine-enforced; input-only coupling insufficient → **validate OUTPUTS against canonical meaning (shadow eval/quarantine)**. Do not copy the 3-layer ontology literally. |
| Ontology-to-tools compilation | https://arxiv.org/abs/2602.03439 | CURRENT (via index) | Compile semantic constraints into executable tool interfaces (constraint-in-the-loop) → **future: Meaning Contract → Skill/Tool Contract compilable; meaning enforced at generation, not post-hoc**. |
| Executable Schema Contracts | https://arxiv.org/abs/2606.05415 · /html/2606.05415v1 | CURRENT (via index) | Closed-world field catalog (LLM may only reference attested identifiers) drives retrieval, +10.2 EM vs generic → **concept registry as closed-world catalog; LLM proposes, deterministic catalog constrains**. |
| ECM Contracts (governed capability interfaces) | https://arxiv.org/abs/2604.13097 | CURRENT (via index) | Contracts need behavioral assumptions + permissions + resources + recovery + **version compatibility**, checked BEFORE deployment → **template for the compatibility algebra + shadow/quarantine pre-flight**. |
| Mesh Memory Protocol (field-level acceptance, lineage) | https://arxiv.org/html/2604.19540v1 | CURRENT (via index) | Shared info must preserve semantic identity + provenance at the FIELD/signal level; detect "echo" → **granular provenance/lineage; semantic replay by storage semantics**. |
| Semantic view of agent communication (18 protocols) | https://arxiv.org/html/2604.02369v3 | CURRENT (via index; "silent drift" wording UNVERIFIED, thematically supported) | Transport/schema mature, clarification/alignment/verification pushed to prompts → **transport compatibility ≠ semantic compatibility; own a dedicated semantic layer + drift observatory**. |
| Contract-preserving role evolution (SERO) | https://arxiv.org/abs/2605.28433 | CURRENT (via index) | Evolve meaning WITHOUT breaking contracts: LLM proposes, deterministic gate commits only if invariants preserved + score improves → **blueprint for epoch transitions gated by shadow eval**. |
| Viktor (VENDOR CLAIMS) — shared memory/facts/preferences/lessons/SOPs/skills; "100k tools" lazy-loaded skills | https://viktor.com/ · https://viktor.com/blog/how-to-give-your-ai-employee-memory · https://viktor.com/blog/what-breaks-when-your-agent-has-100000-tools | CURRENT (vendor) | Persistent shared knowledge is essential but descriptive/heuristic — **no canonical semantics, versioned meaning, provenance, replay, or governed evolution; SP0002 adds exactly these** (vendor claims). Lazy-loaded skills ⇒ concepts should page in as governed capsules. |

## B. Standards — every one a PROJECTION or interop ADAPTER (never internal authority)

| Standard | URL | Status (2026) | Class |
|---|---|---|---|
| MCP | https://modelcontextprotocol.io/ · /specification/2025-11-25 | STABLE 2025-11-25 (07-28 = RC) | INTEROPERABILITY_ADAPTER (draft = EXPERIMENTAL) |
| A2A | https://a2a-protocol.org/latest/ · /specification/ · /definitions/ | v0.3.0 confirmed; v1.0 secondary-reported (UNVERIFIED via 403) | INTEROPERABILITY_ADAPTER (Agent Card projection) |
| OpenAPI | https://spec.openapis.org/oas/v3.2.0.html | STABLE 3.2.0 (2025-09) | PROJECTION |
| OpenAPI Overlay | https://spec.openapis.org/overlay/v1.1.0.html | STABLE 1.1.0 (2026-01-14) | PROJECTION |
| Arazzo | https://spec.openapis.org/arazzo/latest.html | STABLE (latest.html renders 1.1.0) | PROJECTION |
| AsyncAPI | https://www.asyncapi.com/docs/reference/specification/v3.0.0 | STABLE 3.0.0 (3.1.0 available) | PROJECTION |
| CloudEvents | https://cloudevents.io/ · https://github.com/cloudevents/spec | STABLE 1.0.2 (CNCF Graduated) | INTEROPERABILITY_ADAPTER (envelope) |
| JSON Schema | https://json-schema.org/draft/2020-12 | DRAFT 2020-12 (de-facto stable) | STRUCTURAL_ADAPTER (schema-valid ≠ semantic-valid) |
| SKOS | https://www.w3.org/TR/skos-reference/ | RECOMMENDATION (2009) | OPTIONAL_PROJECTION |
| PROV | https://www.w3.org/TR/prov-o/ | RECOMMENDATION (2013) | OPTIONAL_PROJECTION |
| JSON-LD 1.1 | https://www.w3.org/TR/json-ld11/ | RECOMMENDATION (2020) | OPTIONAL_PROJECTION |
| **SHACL 1.2** | https://www.w3.org/TR/shacl12-core/ | **WORKING DRAFT** (1.1 = Rec) | **EXPERIMENTAL_ADAPTER_BOUNDARY — not a mandatory dependency** |
| BCP 47 / RFC 5646 | https://www.rfc-editor.org/info/bcp47/ | STABLE (BCP, 2009) | IDENTITY_PRIMITIVE (label ≠ meaning) |
| RFC 3339 | https://www.rfc-editor.org/info/rfc3339/ | STABLE (2002) | TIME instant (UTC offset) |
| RFC 9557 | https://www.rfc-editor.org/info/rfc9557/ | STABLE (2024) | TIME extended — adds IANA zone name + calendar tags → **instant vs named-zone vs local-business-time distinction** |

## Consolidated implications (locked)
- Meaning authority is **external to the LLM/provider/schema**: "LLM proposes,
  deterministic substrate constrains/commits" (registry closed-world catalog,
  quarantine, shadow-eval commit gate).
- **One shared world model** (the registry); workers reference canonical concepts.
- **Versioned meaning** (epochs) + **compatibility algebra** prevent silent drift.
- **Validate outputs**, not only inputs (shadow eval + quarantine).
- **Field-level provenance/lineage**; semantic replay by storage semantics.
- **All standards are projections/adapters**; SHACL 1.2 stays an experimental
  boundary; RFC 3339+9557 preserve the time distinctions; BCP 47 is identity only.
- **Viktor** validates shared knowledge as essential but lacks canonical
  semantics/versioning/provenance/replay/governed evolution (vendor claims).

## Honesty
All content snippet-corroborated (WebFetch 403), not full-text. UNVERIFIED items
excluded from evidentiary use: A2A v1.0 exact version, "silent schema drift"
literal wording (2604.02369), exact Viktor `/research/...` path. Roadmaps/RCs
(MCP 07-28) not treated as shipped; SHACL 1.2 explicitly a Working Draft.
