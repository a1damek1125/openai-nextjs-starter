# FINALIS — Semantic Collision Report (SP0002, first deliverable)

Grounded in repository truth at HEAD `19413f2` (grep evidence over `finalis/`).
This is the input to canonicalization: **discover current meaning, then
canonicalize** (SP0002 §8) — never invent terminology and force the repo to match.

Columns: TERM · LOCATIONS · MEANINGS FOUND · CURRENT OWNER · SAME/DIFFERENT
CONCEPT · EPISTEMIC? · TEMPORAL? · DECISION.

## A. Lexical ambiguity (same word → different operational meaning)

### `completed` — **9+ distinct operational meanings** (the flagship collision)
| Meaning found | Evidence | Belongs to |
|---|---|---|
| business outcome verified (deal won) | `WON_COMPLETED` (8) | `outcome.business_outcome` / `lifecycle.completion` |
| fulfillment done | `FULFILLMENT_COMPLETED` (7), `SERVICE_COMPLETED` (3) | product lifecycle |
| run terminated with no side effect | `TASK_COMPLETED_NO_SIDE_EFFECTS` (2), `COMPLETED_NO_SIDE_EFFECTS` (17) | `run.run` (CORE-A3) |
| read-path runtime finished | `RUNTIME_READ_ONLY_COMPLETED` (10), `READ_ONLY_RUNTIME_COMPLETED` (5) | TOOL-B6 |
| call ended | `CALL_COMPLETED` (2) | telephony |
| gate/check passed | `QUALITY_CHECK_COMPLETED`, `AUTHORITY_CHECK_COMPLETED` | governance checks |
| inbound answered | `ANSWERED_COMPLETED` (3) | action/comms |
| generic status | `"completed"`, `"complete"`, `"done"`, `"terminal"` | mixed |
**Decision:** REQUIRES DECISION. Canonicalize a family: `activity.completed` ≠
`effect.effect` ≠ `outcome.business_outcome` ≠ `lifecycle.completion` (D-0002 §2.1
Problem A). Historical enum strings keep their meaning via alias mapping (do not
rename code, §22).

### `capability` — **triple-overloaded** (worsened by SP0001)
| Meaning | Evidence | Owner |
|---|---|---|
| RBAC permission/grantable capability | `capability` (307, mostly admin/governance) | `authority.permission` |
| tool capability (governed tool) | TOOL-B1 `ai_tools`, `tool_capability` | `tool.tool` |
| **architecture capability** (SP0001 ownership unit) | `tools/architecture` twin | SP0001 twin (NOT a business concept) |
**Decision:** REQUIRES DECISION. `authority.permission` vs `tool.tool` are
distinct canonical concepts; SP0001 "capability" is an *architecture-twin* term
and must be marked as a NON-business projection (forbidden alias for the business
concepts) to prevent Problem A across SPs.

## B. Different words → same concept (accidental duplicate risk)
| Cluster | Evidence | Decision |
|---|---|---|
| `verified` (242) vs evidence "admitted" vs `crm_facts` | epistemic terms scattered | Canonicalize `epistemic.admitted_fact`; `verified` is an alias for an epistemic *status*, not a concept |
| `ai_worker` (47) vs internal "worker" (19) vs "agent" (35) | RBAC AI-worker + specialist worker + agent | `employee.worker` (internal specialist) distinct from `employee.employee` (CORE-A1 identity) and `employee.agent` (generic) |

## C. Epistemic ambiguity (Problem B)
| Term | Conflated statuses found | Decision |
|---|---|---|
| `claim` (93) | CORE-A6 artifact claim vs "customer claim" vs unverified assertion | `evidence.claim` (an assertion with epistemic status), distinct from `evidence.fact` |
| `fact` | `crm_facts` (stored facts) vs "admitted fact" vs "verified" | `epistemic.admitted_fact` requires an admission process; a model guess is a `CLAIM`, never a `FACT` (INV-0002-05/13) |
| `verified` (242) | evidence-verified vs hash-verified vs business-verified | `verified` = an epistemic *status token*, never a concept; must not collapse into `confidence`/`truth_degree` (D-0002-08) |

## D. Concept distinctions the repo already encodes (must be preserved)
| Pair | Evidence they are DIFFERENT | Canonical |
|---|---|---|
| `task` vs `owned_work` | `ai_tasks` (12, CORE-A2 canonical task contract) vs `work_item`/`WORK_ITEM` (437, EMP-A1) | `work.task` ≠ `work.owned_work` (AC-0002-28) |
| `case` vs `run` | `case_id` (646, Case Graph) vs `run_id` (402, CORE-A3 run ledger) | `case.case` ≠ `run.run` (AC-0002-29) |
| `employee` vs `worker` vs `agent` | `ai_employee` (223) vs `ai_worker` (47) vs `agent` (35) | `employee.employee` ≠ `employee.worker` ≠ `employee.agent` (AC-0002-34) |
| `tool` vs `capability` | `ai_tools` (TOOL-B1) vs `capability` (RBAC) | `tool.tool` ≠ `authority.permission`; `skill` not yet in repo (future) (AC-0002-33) |
| `action`/`effect`/`outcome` | `action_requests`+`executions`+`delivery_events` vs outcome/WON | `action.action` ≠ `effect.effect` ≠ `outcome.business_outcome` (AC-0002-30) |
| `claim` vs `evidence` vs `artifact` | `claim_graph` (CORE-A6) vs `evidence_objects` vs `ai_artifacts` | `evidence.claim` ≠ `evidence.evidence` ≠ `artifact.artifact` (AC-0002-32) |

## E. Interoperability contamination risk (Problem E)
External vocabularies (MCP tool schema, A2A skills/Agent Card, OpenAPI, provider
fields, customer terminology) must map through anti-corruption adapters
(D-0002-19). E.g. an MCP `tool` or A2A `skill` field must NOT silently become the
Finalis `tool.tool` / future `skill.skill` — it is an *external projection*
mapped to a canonical concept, never a takeover (INV-0002-09).

## F. Temporal ambiguity (Problem C)
Any concept above whose meaning changes (e.g. tightening `outcome.completion` to
require payment) must not silently reinterpret historical records. Historical
rows/events are interpreted under the **semantic epoch active when created**
(INV-0002-12). No migration is added by SP0002; epoch references are metadata.

## Summary of decisions
- 1 flagship lexical collision (`completed`) → a canonical family + alias map.
- 1 cross-SP collision (`capability`) → distinct concepts + forbidden alias.
- Epistemic terms (`claim`/`fact`/`verified`) → epistemic type system, never one score.
- 6 existing concept distinctions → preserved as separate canonical concepts.
- All external protocol vocab → anti-corruption projections.
No code/table is renamed (§22); every legacy term maps to a canonical concept.
