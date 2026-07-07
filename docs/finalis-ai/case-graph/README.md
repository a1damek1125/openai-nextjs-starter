# Finalis Case Graph — Core Module Documentation

> **Mission**: the Case Graph is the operational brain of Finalis — **Case Graph +
> State Machine + Completion Loop**. Every lead becomes a `Case`; every fact, document,
> promise, and conversation attaches to it as an evidence-linked graph node; the state
> machine constrains what may happen next; and the Completion Loop guarantees that no
> active case is ever silently dropped.

## Status (honest)

| Layer | Status | Proof |
|---|---|---|
| Service layer (`finalis/case_services.py`: CaseGraphService, MissingInfoService, PromiseTrackerService, NextBestActionService, ActionGateService, CompletionLoopService) | **Implemented and tested** | 20 tests in `tests/test_case_graph_services.py`, incl. the 23-step E2E HVAC lifecycle |
| State machine (`finalis/state_machine.py`: 17 states, 5 final states, human_override rule, scheduled_wake exception) | **Implemented and tested** | 19 tests in `tests/test_state_machine.py`, incl. JSON-spec consistency checks against `state-machine.finalis.json` v1.1 |
| Completion loop core (`finalis/completion_loop.py`: invariants, anti-spam, stuck sweep, promise breach) | **Implemented and tested** | 13 tests in `tests/test_completion_loop.py` |
| Persistence (PostgreSQL relational graph per doc 04) | **Designed** — in-memory dataclasses today; field names match doc 04 so the schema is generated from the same shapes | doc 04, doc 33 |
| HTTP API (`openapi.finalis.yaml`) | **Designed** — services expose the contracts; no HTTP layer wired yet | doc 22 |
| Durable scheduler (Temporal / Postgres queue) | **Designed** — simulated clock proven restart-rebuildable | doc 18, `TestDurability` |

**Test command and result** (branch `claude/finalis-case-graph-completion-loop`):

```
$ python3 -m pytest tests/ -q
160 passed in 0.22s
```

## The 15-file case-graph doc set

Five module docs (this directory) plus the ten canonical specs they refine:

| # | File | What it is |
|---|---|---|
| 1 | `case-graph/README.md` | This index: mission, status, integration map |
| 2 | `case-graph/architecture.md` | Service layer over the tested core; method signatures; loop-tick event flow; persistence plan |
| 3 | `case-graph/data-model.md` | Scaffold entities vs doc 04 canon; required-entity checklist with honest gaps |
| 4 | `case-graph/state-machine.md` | Authoritative module doc: 17 states, v1.1 transitions, final-state rule, open timeout decisions |
| 5 | `case-graph/completion-loop.md` | The loop contract: tick steps, never-drop guarantee, anti-spam, durability plan |
| 6 | `../03-case-lifecycle-state-machine.md` | Canonical lifecycle spec (states, invariants, per-state action catalog §3, transition table §4) |
| 7 | `../04-data-model.md` | Canonical data model (entities, `graph_edges`, retention) |
| 8 | `../05-algorithms-and-scoring.md` | Scoring formulas (LeadScore, MIS, NBA utility, StuckScore, PromiseBreachScore...) |
| 9 | `../09-completion-loop-followup-promises.md` | Canonical Completion Loop / Follow-up / Promise / Missing-Info spec |
| 10 | `../13-autonomy-and-safety.md` | Autonomy levels L1–L5, always-HITL actions, escalation |
| 11 | `../27-state-machine-verification.md` | State-machine verification findings (issues A–F) |
| 12 | `../31-completion-loop-verification.md` | Completion-loop verification plan |
| 13 | `../33-data-model-and-api-verification.md` | Data-model/API audit (incl. the PlaybookVersion gap) |
| 14 | `../39-state-machine-autofix-report.md` | Autofix report: what the scaffold fixed, which design decisions remain open |
| 15 | `../state-machine.finalis.json` | Machine-readable state machine, **v1.1, 71 transition rows** — validated against the code by `tests/test_state_machine.py::TestJsonConsistency` |

The case-graph docs **refine** the numbered docs; where a numbered doc is canonical
(03 for lifecycle, 04 for schema, 09 for the loop), these docs cross-reference it and
document only what the executable scaffold adds, implements, or deliberately deviates
from (there is exactly one documented deviation: the `scheduled_wake` exception, see
`state-machine.md`).

## How the other modules connect

**Voice.** The Voice engine's post-call `ConversationIntelligence` produces a
`ConversationAnalysis` (`finalis/voice/conversation_intelligence.py`) whose
`case_update_payload: dict` is the hand-off contract into the Case Graph: extracted
facts, missing items, promises, objections, next action, and `human_review_required`
arrive in one payload, each fact carrying an `evidence_ref_id` pointing at a timed,
speaker-attributed transcript segment. The service layer consumes it by attaching the
voice session and its `EvidenceReference`s via `CaseGraphService.attach_entity(...,
edge_type="VOICE_SESSION" / "EVIDENCE")`, feeding facts to `MissingInfoService.detect`
/ `.resolve`, and appending detected `Promise`s to the case — exactly what the 23-step
E2E test does in its first steps (Implemented and tested).

**OCR / Document Intelligence.** Documents enter as `Document` records with
`ExtractedField`s whose confidence is the multiplicative Evidence Confidence
(`ocr_q · extraction_q · source_q · consistency_q`, doc 05 §6, implemented as
`ExtractedField.confidence` in `finalis/models.py`). `finalis/documents.py::
ingest_document` applies the confidence gate per field: at or above θ_conf a field is
accepted evidence-linked; below it there are exactly three exits — abstain, request a
re-scan, or human review — never a silent low-confidence write into the graph.
Accepted fields resolve `MissingItem`s (e.g. `installation_photo`), which unblocks
`QUOTE_PREPARATION` (Implemented and tested in `tests/test_documents_webscout_ocr.py`).

**WebScout.** Web research lands in the graph as `Source` records
(`finalis/models.py`, per doc 04 `Source` and the doc 08 §5 contract) carrying `url`,
`snippet`, `trust_score` (0–100, doc 05 §11 `source_trust`), `relevance`, and
`confidence`. Sources attach to a case like any other node and back
`EvidenceReference`s of `source_type="web_source"`, so a claim such as "competitor
quotes ~9 500 zł for this pump" is citable down to the URL and snippet. WebScout never
mutates case state directly — it only contributes evidence the NBA and gate reason
over (models Implemented and tested; live fetching is a separate module).

**Dashboard.** The dashboard's case view is a single read:
`CaseGraphService.get_case_graph(case_id, tenant_id=...)` returns the case, all
attached nodes, the typed edges, open `missing_items`, `promises`, and — crucially —
`timeline`: the hash-chained audit events for the case (every state change, follow-up,
gate decision, and score recompute). Tenant isolation is enforced at this boundary
(`PermissionError` on cross-tenant reads — Implemented and tested). The doc 11
dashboard renders this payload; no separate timeline store exists or is needed.

**LGGT (Certainty Core).** Action gating is Phase-1 rule-based today
(`ActionGateService`), but every gate decision already writes an auditable outcome, and
`finalis/certainty_core.py` defines the `CertaintyCoreAdapter` protocol
(`certify(decision_ref, facts, policy_version) -> Certificate`) that LGGT plugs into.
The shipped `NullAdapter` stamps `verdict="heuristic"` certificates into the same audit
log, so the integration seam is executable now (Implemented and tested,
`TestLGGTPlaceholderCallable`); the real LGGT runtime replaces the adapter without
touching the services (Designed — docs 32/44).
