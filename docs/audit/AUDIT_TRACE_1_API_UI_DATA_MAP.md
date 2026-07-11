# AUDIT-TRACE-1 — API / UI / Data Map

Anchored to `HEAD = 135de7b`. Routes counted in `finalis/portal/app.py`, UI
sections in `finalis/portal/ui.py`, tables in `finalis/portal/db.py`.

## API surface
- **402** route decorators (`@app.{get,post,put,delete,patch}`) in a single
  `create_app()` factory (`app.py`, 11895 lines).
- Route families (by namespace prefix, top of list):

| Namespace | Routes | Backing SP |
|---|---|---|
| `/ai-tools/{tool_id}/*` | 46 | TOOL-B1..B3 (registry/quality/contracts) |
| `/ai-tools/local-transactions/*` | 31 | TOOL-B9 / B9.1 / B9.2 (incl. `/observability/*`, `/recovery/*`) |
| `/ai-employee/work-inbox/*` | 30 | EMP-A1 |
| `/evidence/*` | ~40 | Evidence Trust Fabric (objects, proof-reports, merkle-roots, contracts, upload-sessions) |
| `/ai-artifacts/{artifact_id}/*` | 17 | CORE-A6 |
| `/quotes/*`, `/price-books/*`, `/pricing-rules/*`, `/offers/*` | ~26 | Quote CPQ |
| `/ai-tools/runtime/*` | 15 | TOOL-B6 |
| `/crm/*` (parties/memory/sync) | ~19 | Relationship CRM |
| `/cases/{case_id}/*` | 14 | Case Graph |
| `/ai-tools/actions/*` | 14 | TOOL-B4 guardrails / action decisions |
| `/ai-tasks/{task_id}/*` | 14 | CORE-A2 |
| `/ai-tools/broker/*` | 11 | TOOL-B5 |
| `/ai-approvals/{approval_id}/*` | 10 | CORE-A4 |
| `/ai-tools/write-intents/*` | 9 | TOOL-B7 |
| `/ai-tools/commit-simulations/*` | 9 | TOOL-B8 |
| `/ai-tools/registry/*` | 8 | TOOL-B1 |
| `/ai-runs/{run_id}/*` | 7 | CORE-A3 |
| `/scheduling/appointments/*` | ~4 | Scheduling |
| `/ai-employees/{id}/*` | 3 | CORE-A1 |

> **Monolith hazard (recorded, not fixed):** `create_app()` is one ~11.9k-line
> function. Endpoint blocks from different SPs share the closure scope, which has
> already produced real name-collision regressions (EMP-A1's `_wi` alias
> shadowing TOOL-B7's write-intent block — fixed in `c95fd27`/`135de7b` by
> re-prefixing to `_ewi`). Any future block must use uniquely-prefixed aliases;
> only the **full** suite catches these collisions.

## UI surface (`finalis/portal/ui.py`, 4058 lines)
Server-rendered. **23 section registries** (`*_SECTIONS`), one per domain:

`WIRING`, `QUOTES`, `EVIDENCE`, `CRM`, `WORKBENCH`, `AIEMP`, `TASKS`, `RUNS`,
`APPROVALS`, `LIFECYCLE`, `ARTIFACTS`, `TOOLS`, `QUALITY`, `CONTRACTS`,
`ACTIONS`, `BROKER`, `RUNTIME`, `WRITE_INTENT`, `COMMIT_SIM`, `LOCAL_TX`,
`LOCAL_RECOVERY`, `WORK_OBS`, `WORK_INBOX`.

Each governance SP that shipped a UI added exactly one section calling its own
tested API. **Provider honesty labels** (introduced at `7f3a1be`) surface mock
disclosure in the UI; `finalis/portal/app.py` references honesty/mock labelling
~217 times.

## Data model (SQLite migrations → tables)
27 contiguous migrations; representative table-to-SP mapping:

| Migration | Tables (representative) | SP |
|---|---|---|
| v1 | tenants, users, parties, cases, missing_items, promises, transcripts, action_requests, message_drafts, executions, documents, offers, audit_events | Portal core / product base |
| v2 | call_sessions | Telephony |
| v3 | quotes, quote_line_items, price_books, pricing_rules, quote_approvals, change_orders, acceptance_evidence, payment_requirements, quote_pdf_documents | Quote CPQ |
| v4 | scheduling_appointments, scheduling_appointment_events | Scheduling |
| v5 | evidence_objects, evidence_chain_events, evidence_decision_contracts, evidence_legal_holds | Evidence V-A |
| v6 | evidence_derivatives, evidence_retention_policies, evidence_merkle_roots, evidence_policy_versions | Evidence V-B/E |
| v7 | crm_parties, crm_contact_points, crm_consent_records, crm_relationship_edges, crm_activities, crm_memory_items, crm_external_sync_events, crm_external_sync_cursors | Relationship CRM |
| v8 | evidence_proof_reports | Evidence report package |
| v9 | ai_employees | CORE-A1 |
| v10 | ai_tasks, ai_task_intake_events | CORE-A2 |
| v11 | ai_runs, ai_run_events | CORE-A3 |
| v12–v13 | ai_approval_requests, ai_approval_decisions, ai_approval_grants | CORE-A4 |
| v14 | ai_task_transitions | CORE-A5 |
| v15 | ai_artifacts, ai_artifact_versions | CORE-A6 |
| v16 | ai_tools, ai_tool_versions, ai_tool_registry_events | TOOL-B1 |
| v17 | ai_tool_quality_reports, ai_tool_quality_events | TOOL-B2 |
| v18 | ai_tool_contracts, ai_tool_contract_versions/projections/events | TOOL-B3 |
| v19 | ai_action_proposals, ai_action_decisions, ai_action_circuit_breakers, ai_action_decision_events | TOOL-B4 |
| v20 | ai_broker_requests, ai_broker_outcomes, ai_broker_events | TOOL-B5 |
| v21 | ai_runtime_snapshots, ai_runtime_requests/outcomes/events | TOOL-B6 |
| v22 | ai_write_intent_requests/outcomes/events | TOOL-B7 |
| v23 | ai_commit_simulation_requests/outcomes/events | TOOL-B8 |
| v24 | ai_local_transactions, ai_local_transaction_outcomes/state/events | TOOL-B9 |
| v25 | ai_local_transaction_recovery_requests/outcomes/events | TOOL-B9.1 |
| v26 | ai_governed_work_runs, ai_work_outcome_proofs, ai_work_lineage_events | TOOL-B9.2 |
| v27 | ai_employee_work_items, _item_events, _bundles, _claims, _flow_state, _admission_receipts, _handoff_capabilities, _inbox_policies | EMP-A1 |

The migration ladder is a faithful mirror of the SP ladder: each governance SP
adds its own request/outcome/event triad (event-sourced), and EMP-A1 adds the 8
work-admission tables (unique `tenant+idempotency_key`, one active claim per
item, one active handoff per version+fence).
