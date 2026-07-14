# Case Graph — Data Model

**Canonical reference: `docs/finalis-ai/04-data-model.md`.** That document defines the
full PostgreSQL schema (every entity, index, and retention rule). This document covers
the case-graph *view*: which subset the executable scaffold implements today
(`finalis/models.py` + service-layer structures — **Implemented and tested**), and
where every entity the case-graph spec requires lives or is designed
(**Designed** = doc 04 schema, no code yet).

Scaffold principle (from the `models.py` docstring): dataclasses, not ORM — the
scaffold proves logic, not persistence, and field names match doc 04 so the production
schema can be generated from the same shapes.

## What the scaffold implements

### `Case` — the node everything hangs off

Implemented with the doc 04 score columns **including `stuck_score` and
`escalation_score`**, which earlier drafts left off the entity and the scaffold added
(both are loop inputs: the stuck sweep writes `stuck_score`-relevant audit and the NBA
adds a `request_human_review` candidate at `escalation_score ≥ 1.5`).

```python
Case(tenant_id, state=CaseState.NEW_CONTACT,
     value_estimate=0.0, lead_score=0.0, risk_score=0.0, mis_score=0.0,
     stuck_score=0.0, escalation_score=0.0,
     autonomy_level=3, autonomy_frozen_at=None, opted_out=False,
     next_best_action=None, next_action_due_at=None,
     promises=[], missing_items=[], documents=[], offers=[],
     approvals=[], evidence=[], last_progress_at=None, id=<uuid>)
```

Behavioral members: `effective_autonomy` (property — `min(autonomy_level,
autonomy_frozen_at)` when frozen in HUMAN_REVIEW_REQUIRED, per doc 13 §1) and
`is_active()` (state ∈ `ACTIVE_STATES`).

### `Party` — as implemented

```python
Party(tenant_id="t1", type="client", display_name="Jan Kowalski",
      phone="+48600100200", email=None, address=None,
      preferred_channel="phone", notes="", id=<uuid>)
```

Note the honest delta vs doc 04: the scaffold carries scalar `phone`/`email`; the
canonical schema has `phones (jsonb)` / `emails (jsonb)` plus `whatsapp_id`,
`quiet_hours`, `contact_opt_outs`, and `deal_memory_embedding` (Designed — see the
ContactPoint row in the checklist below).

### `MissingItem`

```python
MissingItem(field_key="installation_photo",
            label="Proszę wysłać zdjęcie obecnej instalacji ...",
            weight=0.9, blocks_quote=True, status="missing", id=<uuid>)
# status: missing | requested | received | waived
```

Created by `MissingInfoService.detect` from the industry profile
(`HVAC_REQUIRED_INFO`); `weight` is the MIS w_i (severity-mapped 0.9/0.5/0.2);
`blocks_quote` items gate `QUOTE_PREPARATION`.

### `Promise`

```python
Promise(promisor="client", what="send photos",
        due_at=datetime(2026, 7, 8, 10, 0),
        importance=0.7, dependency_impact=0.8,
        status="open",           # open | fulfilled | broken | waived
        evidence=None, id=<uuid>)
```

Stored status is `open/fulfilled/broken/waived`; the tracker's *report* buckets open
promises into `DUE_SOON` / `OVERDUE` / `BREACHED` per tick (breach = doc 05 §10 score
≥ θ_breach 0.3).

### `EvidenceReference`

```python
EvidenceReference(source_type="call_segment",     # message | call_segment |
                  source_id="seg1",               # document_region | web_source
                  locator={"ms": [1000, 4000]},
                  snippet="I need a quote", confidence=0.9, id=<uuid>)
```

The universal citation object — attached to cases as graph nodes
(`edge_type="EVIDENCE"` → audit `EVIDENCE_CREATED`) and embedded in `Promise.evidence`.

### `HumanApproval`

```python
HumanApproval(action_type="send_offer_commitment",
              context={...}, recommended_option="approve",
              decision=None,        # approved | rejected | edited
              decided_by=None, id=<uuid>)
```

Minted by `finalis/autonomy.py::gate` when an action exceeds the case's autonomy
level (never silently dropped); the E2E records grant via a
`HUMAN_APPROVAL_GRANTED` audit event.

### `AuditEvent` — append-only, hash-chained

```python
AuditEvent(event_type="case.state_changed", actor="ai", case_id=<uuid>,
           payload={"from_state": "NEW_CONTACT",
                    "to_state": "INTAKE_IN_PROGRESS", "reason": "intake"},
           hash_prev=<sha256 of previous event>, hash_self=<sha256>, id=<uuid>)
```

`AuditLog` has no update/delete API; `verify_chain()` recomputes the hash chain and is
asserted in the 23-step E2E. This is the doc 04 `AuditEvent` executable form.

### Graph edges — `CaseGraphService.edges`

The scaffold realizes doc 04's `graph_edges` table as an in-memory list of typed
edges, written by every `attach_entity` call:

```python
{"from": "<case_id>", "to": "<party_id>", "type": "PARTY"}
{"from": "<case_id>", "to": "<evidence_id>", "type": "EVIDENCE"}
```

Edge types used by the scaffold's audit mapping: `VOICE_SESSION`, `DOCUMENT`, `PARTY`,
`MESSAGE`, `EVIDENCE` (others fall through to `CASE_UPDATED`). Doc 04 defines the
richer production edge vocabulary (`DOCUMENT_SATISFIES_MISSING_ITEM`,
`MISSING_PHOTO_BLOCKS_QUOTE`, `PROMISE_DUE`, ...) plus `weight` and
`evidence_ref_id` columns — Designed. `get_case_graph` returns the case's outgoing
edges alongside nodes and the audit timeline.

Also implemented (documented in the OCR/WebScout module docs, listed here because they
attach to the graph): `Document` (with `ocr_quality`, `status` incl. `needs_rescan`),
`ExtractedField` (with the multiplicative `confidence` property, doc 05 §6), `Offer`
(origin/price/axes), `Source` (WebScout record with `trust_score`/`relevance`/
`confidence`).

## Required-entity checklist (case-graph spec)

Where each required entity lives. "Implemented and tested" = executable in the
scaffold; "Designed" = specified in doc 04/22 with no code yet.

| Required entity | Maps to | Status |
|---|---|---|
| **Tenant** | `BusinessProfile` (doc 04 — the tenant root; every table carries `tenant_id FK BusinessProfile`). Scaffold: `tenant_id: str` on every model + tenant isolation enforced and tested at `CaseGraphService` (`PermissionError` on cross-tenant attach/read). | Isolation **Implemented and tested**; `BusinessProfile` entity itself **Designed** |
| **User / Role** | `UserRole` (doc 04 — owns Cases/Tasks, decides HumanApprovals). Scaffold has no user table; human actors appear as audit `actor` strings (`"human"`, `"ai"`, `"system"`) and `HumanApproval.decided_by`. | **Designed** (gap: no scaffold entity) |
| **ContactPoint** | `Party.phones` / `Party.emails` (jsonb, doc 04) — contact points are folded into Party rather than a separate table. Scaffold carries scalar `Party.phone` / `Party.email` + `preferred_channel`. | Doc 04 shape **Designed**; scalar subset **Implemented and tested** |
| **OfferLineItem** | `Offer.scope (jsonb)` (doc 04) — line items live inside the offer's scope JSON, not a child table. Scaffold `Offer` has `price` + normalized comparison `axes` only, no `scope`. | **Designed** (gap: scaffold Offer omits `scope`) |
| **PlaybookVersion** | **Flagged gap — doc 33 §2 / finding #1 (High)**: `IndustryPlaybook.version` is a scalar with *no version-history table*, while doc 22 promises immutable history on `PATCH /playbooks/{id}` and score reproducibility depends on resolving `weights_version`. Doc 33's recommendation: append-only `PlaybookVersion(playbook_id, version, snapshot jsonb, created_by, created_at)` written on every mutation. Not in doc 04 yet, not in the scaffold. | **Gap — Designed only as a doc 33 recommendation** |
| **LGGTCertificatePlaceholder** | `finalis/certainty_core.py::Certificate` (`decision_ref`, `facts`, `policy_version`, `verdict`, `audit_id`), produced by `NullAdapter.certify` behind the `CertaintyCoreAdapter` protocol and stamped into the audit log (`certainty.stamped`). | **Implemented and tested** (`TestLGGTPlaceholderCallable`); real LGGT runtime **Designed** (docs 32/44) |

Honest summary: the loop-critical entities (Case, Party, MissingItem, Promise,
EvidenceReference, HumanApproval, AuditEvent, edges) are executable and covered by the
160-test suite; org-structure entities (BusinessProfile, UserRole) and offer/playbook
detail (`Offer.scope`, `PlaybookVersion`) exist only on paper, and `PlaybookVersion`
is on paper only as an *unresolved* doc 33 finding — it must be added to doc 04 before
the persistence layer is generated.
