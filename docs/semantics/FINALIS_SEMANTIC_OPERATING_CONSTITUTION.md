# FINALIS SEMANTIC OPERATING CONSTITUTION (SP0002)

**Program:** FINALIS_1000 · **Position:** after SP0000 (Architecture Lock) and
SP0001 (Architecture Immune System) · **Type:** semantic architecture + tooling ·
**Runtime business feature:** none · **Migration:** none.

> **Core principle:** *One concept may have many representations. It may have only
> one authoritative meaning per semantic epoch.*
> **Final principle:** *One shared world of meaning. Many agents, languages,
> models, channels and representations.*

## 0. Baseline (verified at execution)

| Field | Value |
|---|---|
| EXECUTION_DATE | 2026-07-11 |
| BRANCH | `claude/finalis-ai-casewoker-blueprint-f1huse` |
| STARTING_HEAD | `19413f2` (SP0001) |
| SP0000 | COMPLETE (25/25) · SP0001 | baseline VALID (50/50) |
| LATEST_MIGRATION | v27 (unchanged) |
| CURRENT_RUNTIME_FRONTIER | EMP-A1 |

Precondition (§2.2) satisfied: SP0000 + SP0001 both complete. Not BLOCKED.

## 1. The problem this solves (not a glossary)

Five deeper problems (SP0002 §2.1), all evidenced in the repo (see
`FINALIS_SEMANTIC_COLLISION_REPORT.md`):

- **A — lexical ambiguity.** `completed` means ≥9 different things
  (`WON_COMPLETED` outcome vs `TASK_COMPLETED_NO_SIDE_EFFECTS` run-terminal vs
  `RUNTIME_READ_ONLY_COMPLETED` vs `CALL_COMPLETED` …).
- **B — epistemic ambiguity.** `claim`/`fact`/`verified` conflate assertion,
  admitted fact, and a numeric confidence.
- **C — temporal ambiguity.** A concept may change meaning; historical records
  must remain interpretable under the epoch active when created.
- **D — multi-agent drift.** Different workers must not privately reinterpret the
  same term.
- **E — interoperability contamination.** MCP/A2A/OpenAPI/provider vocab must not
  silently redefine internal concepts.

## 2. Semantic philosophy (locked walls)

`WORLD STATE ≠ SEMANTIC DEFINITION` · `CLAIM ≠ FACT` · `FACT ≠ CERTIFIED
CONCLUSION` · `CERTIFIED CONCLUSION ≠ AUTHORITY` · `NAME ≠ IDENTITY` · `SCHEMA ≠
MEANING` · `TRANSLATION ≠ NEW CONCEPT` · `EXTERNAL VOCABULARY ≠ INTERNAL
CANONICAL VOCABULARY`.

## 3. What was built (`tools/semantics/`, stdlib-only, deterministic)

Canonical Concept Registry (`registry.py` + `concepts.py`, **33 concepts**) ·
Meaning Contracts + **Meaning Hash** (`canon.py`; excludes labels/formatting/
timestamps so a translation never changes the hash, D-0002-13) · **Epistemic Type
System** (`epistemic.py`; SIGNAL→…→CERTIFIED_CONCLUSION status lattice, orthogonal
to confidence) · **World Assumption** contracts (`world.py`; OPEN/CLOSED/PARTIAL) ·
**Semantic Epochs** bitemporal (`epochs.py`) · **Compatibility Algebra**
(`compatibility.py`; denotational model-set classification where decidable, else
REVIEW_REQUIRED) · semantic relationship graph + impact cone (`graph.py`,
`impact.py`) · concept **resolution** + ambiguity → **Quarantine** (`resolve.py`,
`quarantine.py`) · **Semantic Transaction** (`transaction.py`; breaking→new epoch,
no partial rollout) · **Dual-Semantics Shadow Evaluation** (`shadow.py`) ·
**Historical Semantic Replay** (`replay.py`) · **Protocol Anti-Corruption**
projections (`projections.py`) · **Agent Semantic Capsule** + progressive
disclosure (`capsule.py`) · **LGGT Semantic Bridge** (`lggt_bridge.py`) ·
**multilingual** labels PL/EN/DE/ES (`multilingual.py`) · **Proof-Carrying
Semantic Change Envelope** (`envelope.py`) · Change Intent (`intent.py`) · **Drift
Observatory** (`drift.py`) · CLI (`cli.py`). Product code never imports it.

## 4. Three distinct twins (§9.1 — do not merge)

| Twin | Answers | Where |
|---|---|---|
| Architecture Digital Twin (SP0001) | *Where does capability X live?* | `docs/architecture/…_TWIN.json` |
| **Semantic Domain Twin (SP0002)** | *What does concept X mean?* | `docs/semantics/…_REGISTRY.json` |
| Future Operational World State | *What is currently true about case X?* | future runtime |

## 5. Epistemic type system (D-0002-07/08)

`SIGNAL → OBSERVATION → CLAIM → CORROBORATED_CLAIM → ADMITTED_FACT →
DERIVED_CONCLUSION → CERTIFIED_CONCLUSION`. This is a **status lattice, not a
truth ladder**: `epistemic_status` is stored separately from `confidence`,
`source_reliability`, `evidence_strength`, `truth_degree` and never collapsed
(SP0002 §12.2). LLM/model/external output enters **only** as `CLAIM` (INV-0002-13);
`CERTIFIED_CONCLUSION` is certified relative to premises, not "more true than an
observed fact", and is never execution authority (INV-0002-06/07).

## 6. World assumptions (D-0002-09)

`OPEN_WORLD` (absence ≠ false) · `CLOSED_WORLD` (bounded scope: not-known ⇒ false)
· `PARTIAL_WORLD` (completeness conditional; needs a declared scope). Applied to
`outcome.business_outcome` (CLOSED — not-verified ⇒ not achieved), `effect.effect`
(CLOSED), `evidence.fact` (PARTIAL), `provider.provider` (OPEN).

## 7. Invariants (INV-0002-01 … 16)

01 one concept = one immutable id · 02 one authoritative meaning per epoch · 03
label ≠ identity · 04 schema ≠ meaning · 05 claim ≠ fact · 06 certified ≠
external-world truth · 07 certified ≠ execution authority · 08 translation cannot
redefine semantics · 09 external protocol cannot become internal authority · 10
breaking change requires a new epoch · 11 partial rollout forbidden · 12
historical record interpretable under its original epoch · 13 LLM output cannot
create authoritative concept by itself · 14 unknown/ambiguous → quarantine · 15
LGGT predicate mapping must be explicit · 16 proof envelope is evidence not
authority. Hard validity: `ValidSemanticEpoch ⟺ P0=0 ∧ P1=0` (no score overrides).

## 8. Standards posture (all projections/adapters, never authority)

Verified 2026 status (`FINALIS_SP0002_RESEARCH_REGISTER.md`): OpenAPI 3.2.0
(2025-09), Overlay 1.1.0 (2026-01), MCP ratified 2025-11-25 (07-28 = RC), A2A
Agent Card (v0.3.0 confirmed; v1.0 secondary), AsyncAPI 3.0/3.1, CloudEvents
1.0.2, JSON Schema 2020-12 (structure only — schema-valid ≠ semantic-valid), SKOS/
PROV/JSON-LD (optional projections; no mandatory RDF/SPARQL runtime), **SHACL 1.2
= Working Draft → adapter boundary only**, BCP 47 (language identity; label ≠
meaning), RFC 3339 + RFC 9557 (instant vs named-zone vs local-business-time).
Each maps through an **anti-corruption adapter**; none is internal authority.

## 9. Non-goals / do-not-rebuild (§7/§8)

No renaming of existing code/tables, no Event Fabric, no memory runtime, no LGGT
change, no RDF/SPARQL/SHACL-1.2 mandatory dependency, no real providers, no
migration, no business behavior change. Existing meanings from CORE-A2..A6, Case
Graph, Universal Lifecycle, Evidence, CRM, EMP-A1 are **discovered then
canonicalized**, not overwritten; legacy terms map to canonical concepts.

## 10. Verification

See `FINALIS_SEMANTIC_SWARM_REVIEW.md` for the 87-criterion acceptance matrix,
mutation campaign, red-team, and independent verification. Classification:
**IMPLEMENTED_AND_TESTED** (semantic infrastructure); overall product remains
**NOT_PRODUCTION_READY** (SP0002 opens no providers).
