"""Persistence layer — SQLite for dev (stdlib, zero deps), Postgres-ready SQL.

Versioned migrations, tenant_id + FKs + indexes on every tenant-scoped table,
append-only audit rows preserving the hash chain (verify reads from DB).
STATUS: Implemented and tested with SQLite; Postgres = connection/driver swap
(schema uses portable SQL) — marked Scaffolded for Postgres until exercised.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..audit import AuditEvent, AuditLog

MIGRATIONS: list[tuple[int, str]] = [
    (1, """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY, name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
  role TEXT NOT NULL, display_name TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_users_tenant ON users(tenant_id);

CREATE TABLE IF NOT EXISTS parties (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  type TEXT NOT NULL, display_name TEXT NOT NULL,
  phone TEXT, email TEXT, address TEXT,
  preferred_channel TEXT NOT NULL DEFAULT 'whatsapp',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_parties_tenant ON parties(tenant_id);

CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  title TEXT NOT NULL DEFAULT '', state TEXT NOT NULL,
  client_party_id TEXT REFERENCES parties(id),
  value_estimate REAL NOT NULL DEFAULT 0,
  lead_score REAL NOT NULL DEFAULT 0, risk_score REAL NOT NULL DEFAULT 0,
  autonomy_level INTEGER NOT NULL DEFAULT 3,
  opted_out INTEGER NOT NULL DEFAULT 0,
  autonomy_frozen_at INTEGER,
  next_best_action TEXT, next_action_due_at TEXT, last_progress_at TEXT,
  offer_sent_at TEXT, closed_reason TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_cases_tenant_state ON cases(tenant_id, state);
CREATE INDEX IF NOT EXISTS ix_cases_tenant_due ON cases(tenant_id, next_action_due_at);

CREATE TABLE IF NOT EXISTS missing_items (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  case_id TEXT NOT NULL REFERENCES cases(id),
  field_key TEXT NOT NULL, label TEXT NOT NULL DEFAULT '',
  weight REAL NOT NULL DEFAULT 0.5, blocks_quote INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'missing',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_missing_case ON missing_items(tenant_id, case_id, status);

CREATE TABLE IF NOT EXISTS promises (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  case_id TEXT NOT NULL REFERENCES cases(id),
  promisor TEXT NOT NULL, what TEXT NOT NULL, due_at TEXT NOT NULL,
  importance REAL NOT NULL DEFAULT 0.5,
  dependency_impact REAL NOT NULL DEFAULT 0.5,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_promises_case ON promises(tenant_id, case_id, status);

CREATE TABLE IF NOT EXISTS transcripts (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  case_id TEXT NOT NULL REFERENCES cases(id),
  segments_json TEXT NOT NULL, analysis_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_transcripts_case ON transcripts(tenant_id, case_id);

CREATE TABLE IF NOT EXISTS action_requests (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  case_id TEXT NOT NULL REFERENCES cases(id),
  action_type TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'api', risk_level TEXT NOT NULL DEFAULT 'low',
  payload_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'requested',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_actions_case ON action_requests(tenant_id, case_id, status);

CREATE TABLE IF NOT EXISTS message_drafts (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  case_id TEXT NOT NULL, action_request_id TEXT NOT NULL,
  language TEXT NOT NULL, channel TEXT NOT NULL, text TEXT NOT NULL,
  edited_text TEXT, risk_level TEXT NOT NULL DEFAULT 'low',
  approval_status TEXT NOT NULL DEFAULT 'NOT_REQUIRED',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_drafts_case ON message_drafts(tenant_id, case_id, approval_status);

CREATE TABLE IF NOT EXISTS executions (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  case_id TEXT NOT NULL, action_request_id TEXT NOT NULL,
  channel TEXT NOT NULL, provider TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'created',
  scheduled_at TEXT, executed_at TEXT, retry_count INTEGER DEFAULT 0,
  result_json TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS ix_exec_case ON executions(tenant_id, case_id);

CREATE TABLE IF NOT EXISTS delivery_events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, case_id TEXT NOT NULL,
  action_execution_id TEXT NOT NULL, provider TEXT NOT NULL,
  provider_message_id TEXT NOT NULL, status TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_delivery_case ON delivery_events(tenant_id, case_id);

CREATE TABLE IF NOT EXISTS upload_links (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  case_id TEXT NOT NULL REFERENCES cases(id),
  token_hash TEXT NOT NULL UNIQUE, purpose TEXT NOT NULL,
  expires_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'CREATED',
  used_at TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_upload_case ON upload_links(tenant_id, case_id);

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  case_id TEXT NOT NULL REFERENCES cases(id),
  doc_type TEXT NOT NULL DEFAULT 'photo', filename TEXT NOT NULL DEFAULT '',
  mime TEXT NOT NULL DEFAULT '', size_bytes INTEGER NOT NULL DEFAULT 0,
  storage_path TEXT NOT NULL DEFAULT '', ocr_quality REAL,
  status TEXT NOT NULL DEFAULT 'received',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_docs_case ON documents(tenant_id, case_id);

CREATE TABLE IF NOT EXISTS offers (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  case_id TEXT NOT NULL REFERENCES cases(id),
  origin TEXT NOT NULL DEFAULT 'ours', price REAL NOT NULL DEFAULT 0,
  scope TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'draft',
  sent_at TEXT, client_response TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_offers_case ON offers(tenant_id, case_id);

CREATE TABLE IF NOT EXISTS audit_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE, tenant_id TEXT,
  case_id TEXT, event_type TEXT NOT NULL, actor TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  hash_prev TEXT NOT NULL, hash_self TEXT NOT NULL,
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_audit_case ON audit_events(tenant_id, case_id);
"""),
    (2, """
-- v2: LifecycleVector persistence + call sessions.
ALTER TABLE cases ADD COLUMN lifecycle_json TEXT;

CREATE TABLE IF NOT EXISTS call_sessions (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  case_id TEXT, direction TEXT NOT NULL,
  source_number TEXT NOT NULL, destination_number TEXT NOT NULL,
  provider TEXT NOT NULL, status TEXT NOT NULL,
  outcome TEXT, outcome_reason TEXT,
  disposition_confidence REAL NOT NULL DEFAULT 0,
  recording_allowed INTEGER NOT NULL DEFAULT 0,
  human_handoff_required INTEGER NOT NULL DEFAULT 0,
  started_at TEXT, ended_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_calls_tenant ON call_sessions(tenant_id, case_id);
"""),
    (3, """
-- v3: Quote Builder persistence (money stored as TEXT-encoded Decimal —
-- SQLite REAL would reintroduce float drift the pricing math forbids).
CREATE TABLE IF NOT EXISTS quotes (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  case_id TEXT NOT NULL, customer_party_id TEXT,
  currency TEXT NOT NULL DEFAULT 'EUR',
  state TEXT NOT NULL DEFAULT 'DRAFT',
  version INTEGER NOT NULL DEFAULT 1, revised_from_id TEXT,
  created_by TEXT NOT NULL DEFAULT 'human',
  subtotal TEXT NOT NULL DEFAULT '0', tax_total TEXT NOT NULL DEFAULT '0',
  total TEXT NOT NULL DEFAULT '0',
  rounding_adjustment TEXT NOT NULL DEFAULT '0',
  valid_days INTEGER NOT NULL DEFAULT 30, valid_until TEXT,
  cost_volatility REAL NOT NULL DEFAULT 0,
  sent_at TEXT, accepted_at TEXT,
  assumptions_json TEXT NOT NULL DEFAULT '[]',
  exclusions_json TEXT NOT NULL DEFAULT '[]',
  terms_template_id TEXT, terms_template_approved INTEGER NOT NULL DEFAULT 0,
  custom_terms_text TEXT NOT NULL DEFAULT '',
  payment_schedule_json TEXT, evidence_json TEXT,
  acceptance_evidence_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_quotes_tenant ON quotes(tenant_id, case_id);
CREATE INDEX IF NOT EXISTS ix_quotes_state ON quotes(tenant_id, state);

CREATE TABLE IF NOT EXISTS quote_line_items (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  quote_id TEXT NOT NULL REFERENCES quotes(id),
  position INTEGER NOT NULL DEFAULT 0,
  description TEXT NOT NULL DEFAULT '', sku TEXT,
  line_total TEXT NOT NULL DEFAULT '0', margin_percent TEXT,
  body_json TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS ix_qlines_quote ON quote_line_items(tenant_id, quote_id);

CREATE TABLE IF NOT EXISTS price_books (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT 'default',
  currency TEXT NOT NULL DEFAULT 'EUR',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_pbooks_tenant ON price_books(tenant_id);

CREATE TABLE IF NOT EXISTS price_book_items (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  price_book_id TEXT NOT NULL REFERENCES price_books(id),
  sku TEXT NOT NULL, name TEXT NOT NULL DEFAULT '',
  list_price TEXT NOT NULL, cost_hint TEXT,
  tax_category TEXT NOT NULL DEFAULT 'standard');
CREATE INDEX IF NOT EXISTS ix_pbitems_book ON price_book_items(tenant_id, price_book_id, sku);

CREATE TABLE IF NOT EXISTS pricing_rules (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  name TEXT NOT NULL, applies_to_sku TEXT NOT NULL DEFAULT '*',
  min_quantity TEXT NOT NULL DEFAULT '0',
  discount_percent TEXT NOT NULL DEFAULT '0',
  priority INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS ix_prules_tenant ON pricing_rules(tenant_id, active);

CREATE TABLE IF NOT EXISTS quote_approvals (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  quote_id TEXT NOT NULL REFERENCES quotes(id),
  reason TEXT NOT NULL DEFAULT '', requested_by TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING', approver_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_qapprovals ON quote_approvals(tenant_id, quote_id, status);

CREATE TABLE IF NOT EXISTS change_orders (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  quote_id TEXT NOT NULL REFERENCES quotes(id),
  description TEXT NOT NULL, price_delta TEXT NOT NULL,
  cost_delta TEXT NOT NULL DEFAULT '0', margin_percent TEXT,
  reason TEXT NOT NULL DEFAULT '', requested_by TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL', approver_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_corders ON change_orders(tenant_id, quote_id);

CREATE TABLE IF NOT EXISTS acceptance_evidence (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  quote_id TEXT NOT NULL REFERENCES quotes(id),
  kind TEXT NOT NULL, reference_id TEXT NOT NULL,
  recorded_by TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_accev ON acceptance_evidence(tenant_id, quote_id);

CREATE TABLE IF NOT EXISTS payment_requirements (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  quote_id TEXT NOT NULL REFERENCES quotes(id),
  label TEXT NOT NULL, amount TEXT NOT NULL,
  trigger_event TEXT NOT NULL DEFAULT 'on_acceptance',
  blocks_fulfillment_until_paid INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'REQUIRED');
CREATE INDEX IF NOT EXISTS ix_payreqs ON payment_requirements(tenant_id, quote_id);

CREATE TABLE IF NOT EXISTS quote_pdf_documents (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  quote_id TEXT NOT NULL REFERENCES quotes(id),
  html TEXT NOT NULL, is_mock INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_qpdfs ON quote_pdf_documents(tenant_id, quote_id);
"""),
    (4, """
-- v4: Scheduling persistence — appointments + hashed confirmation tokens
-- survive restarts. Raw tokens are NEVER stored (hash + expiry only).
CREATE TABLE IF NOT EXISTS scheduling_appointments (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  case_id TEXT NOT NULL, appointment_type TEXT NOT NULL,
  status TEXT NOT NULL,
  assigned_user_id TEXT, resource_id TEXT,
  start_at TEXT NOT NULL, end_at TEXT NOT NULL,
  video_meeting_url TEXT,
  provider_name TEXT NOT NULL DEFAULT 'mock-calendar',
  provider_is_mock INTEGER NOT NULL DEFAULT 1,
  requires_confirmation INTEGER NOT NULL DEFAULT 0,
  confirmation_token_hash TEXT,
  confirmation_expires_at TEXT,
  confirmed_at TEXT, cancelled_at TEXT, cancellation_reason TEXT,
  completed_at TEXT, no_show_at TEXT,
  reschedule_count INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL DEFAULT 'system',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_sched_tenant_case
  ON scheduling_appointments(tenant_id, case_id);
CREATE INDEX IF NOT EXISTS ix_sched_tenant_status
  ON scheduling_appointments(tenant_id, status);
CREATE INDEX IF NOT EXISTS ix_sched_resource
  ON scheduling_appointments(tenant_id, resource_id, start_at);
CREATE INDEX IF NOT EXISTS ix_sched_token
  ON scheduling_appointments(confirmation_token_hash);

CREATE TABLE IF NOT EXISTS scheduling_appointment_events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  appointment_id TEXT NOT NULL REFERENCES scheduling_appointments(id),
  event_type TEXT NOT NULL, actor TEXT NOT NULL DEFAULT 'system',
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_sched_events
  ON scheduling_appointment_events(tenant_id, appointment_id);
"""),
    (5, """
-- v5: Evidence Trust Fabric metadata (bytes live in the storage
-- provider's vault — the DB stores pointer + hash, never raw content).
CREATE TABLE IF NOT EXISTS evidence_objects (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  case_id TEXT NOT NULL, evidence_type TEXT NOT NULL,
  state TEXT NOT NULL,
  original_filename TEXT NOT NULL DEFAULT '',
  declared_mime TEXT NOT NULL DEFAULT '', detected_mime TEXT,
  extension TEXT NOT NULL DEFAULT '',
  size_bytes INTEGER NOT NULL DEFAULT 0,
  mime_mismatch INTEGER NOT NULL DEFAULT 0,
  active_content INTEGER NOT NULL DEFAULT 0,
  storage_provider TEXT NOT NULL, storage_key TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  sensitivity TEXT NOT NULL DEFAULT 'normal',
  injection_risk REAL NOT NULL DEFAULT 0,
  symbols_json TEXT NOT NULL DEFAULT '[]',
  parser_kind TEXT NOT NULL DEFAULT 'OCR_NOT_RUN',
  human_verified INTEGER NOT NULL DEFAULT 0,
  legal_hold INTEGER NOT NULL DEFAULT 0,
  retention_until TEXT,
  uploaded_by TEXT NOT NULL, source_kind TEXT NOT NULL DEFAULT 'unknown',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_evidence_tenant_case
  ON evidence_objects(tenant_id, case_id);
CREATE INDEX IF NOT EXISTS ix_evidence_state
  ON evidence_objects(tenant_id, state);

CREATE TABLE IF NOT EXISTS evidence_chain_events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence_objects(id),
  event_type TEXT NOT NULL, actor TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  hash_prev TEXT NOT NULL, hash_self TEXT NOT NULL,
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_evchain
  ON evidence_chain_events(tenant_id, evidence_id);

CREATE TABLE IF NOT EXISTS evidence_access_events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL, actor_kind TEXT NOT NULL,
  actor_id TEXT NOT NULL, purpose TEXT NOT NULL,
  decision TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_evaccess
  ON evidence_access_events(tenant_id, evidence_id);

CREATE TABLE IF NOT EXISTS evidence_decision_contracts (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  case_id TEXT NOT NULL, decision_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  evidence_ids_json TEXT NOT NULL DEFAULT '[]',
  admissible_json TEXT NOT NULL DEFAULT '[]',
  rejected_json TEXT NOT NULL DEFAULT '[]',
  facts_json TEXT NOT NULL DEFAULT '{}',
  hard_blockers_json TEXT NOT NULL DEFAULT '[]',
  trust_summary REAL NOT NULL DEFAULT 0,
  ai_access_level TEXT NOT NULL DEFAULT 'none',
  human_verified INTEGER NOT NULL DEFAULT 0,
  final_decision TEXT NOT NULL,
  audit_event_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_evcontracts
  ON evidence_decision_contracts(tenant_id, case_id, decision_type);

CREATE TABLE IF NOT EXISTS evidence_legal_holds (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence_objects(id),
  reason TEXT NOT NULL, placed_by TEXT NOT NULL,
  released_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_evholds
  ON evidence_legal_holds(tenant_id, evidence_id);
"""),
    (6, """
-- v6: Evidence Trust Fabric production hardening (V-E). Consolidated:
-- the CRM tables that also claimed v6 on their branch now live in v7.
ALTER TABLE evidence_decision_contracts ADD COLUMN contract_hash TEXT;
ALTER TABLE evidence_decision_contracts ADD COLUMN policy_version TEXT;
ALTER TABLE evidence_decision_contracts ADD COLUMN requested_action TEXT;
ALTER TABLE evidence_decision_contracts ADD COLUMN causal_result TEXT;
ALTER TABLE evidence_decision_contracts ADD COLUMN user_intent_reference TEXT;
ALTER TABLE evidence_decision_contracts ADD COLUMN would_survive INTEGER;

CREATE TABLE IF NOT EXISTS evidence_derivatives (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence_objects(id),
  derivative_kind TEXT NOT NULL, policy_decision TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0, is_placeholder INTEGER NOT NULL DEFAULT 1,
  active_content_removed INTEGER NOT NULL DEFAULT 0,
  safe_text TEXT NOT NULL DEFAULT '', limitations_json TEXT NOT NULL DEFAULT '[]',
  manifest_hash TEXT NOT NULL, generated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_evderiv
  ON evidence_derivatives(tenant_id, evidence_id);

CREATE TABLE IF NOT EXISTS evidence_retention_policies (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence_objects(id),
  mode TEXT NOT NULL DEFAULT 'NONE', retention_until TEXT,
  native_worm INTEGER NOT NULL DEFAULT 0,
  policy_version TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_evret
  ON evidence_retention_policies(tenant_id, evidence_id);

CREATE TABLE IF NOT EXISTS evidence_merkle_roots (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  root TEXT NOT NULL, size INTEGER NOT NULL,
  leaves_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_evmroot ON evidence_merkle_roots(tenant_id);

CREATE TABLE IF NOT EXISTS evidence_policy_versions (
  id TEXT PRIMARY KEY, version TEXT NOT NULL,
  fingerprint TEXT NOT NULL, created_at TEXT NOT NULL);
"""),
    (7, """
-- v7: Relationship Core (CRM) persistence — RENUMBERED from v6 at
-- consolidation (Evidence hardening owns v6). Person/org/household
-- profiles and addresses live as JSON columns on crm_parties (folded,
-- disclosed); the legacy 'parties' table stays as case-contact storage
-- and is bridged read-only by the API.
CREATE TABLE IF NOT EXISTS crm_parties (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  kind TEXT NOT NULL, display_name TEXT NOT NULL,
  roles_json TEXT NOT NULL DEFAULT '[]',
  person_json TEXT, organization_json TEXT, household_json TEXT,
  addresses_json TEXT NOT NULL DEFAULT '[]',
  merged_into_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ix_crmp_tenant ON crm_parties(tenant_id);

CREATE TABLE IF NOT EXISTS crm_contact_points (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  party_id TEXT NOT NULL REFERENCES crm_parties(id),
  kind TEXT NOT NULL, value TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  verified INTEGER NOT NULL DEFAULT 0,
  preferred INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_crmcp ON crm_contact_points(tenant_id, party_id);
CREATE INDEX IF NOT EXISTS ix_crmcp_value ON crm_contact_points(tenant_id, kind, value);

CREATE TABLE IF NOT EXISTS crm_consent_records (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  party_id TEXT NOT NULL REFERENCES crm_parties(id),
  channel TEXT NOT NULL, status TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT '', recorded_by TEXT NOT NULL,
  recorded_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_crmconsent
  ON crm_consent_records(tenant_id, party_id, channel);

CREATE TABLE IF NOT EXISTS crm_relationship_edges (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  from_id TEXT NOT NULL, to_id TEXT NOT NULL,
  to_kind TEXT NOT NULL, role TEXT NOT NULL,
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_crmedge_from
  ON crm_relationship_edges(tenant_id, from_id);
CREATE INDEX IF NOT EXISTS ix_crmedge_to
  ON crm_relationship_edges(tenant_id, to_kind, to_id);

CREATE TABLE IF NOT EXISTS crm_activities (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  party_id TEXT NOT NULL, kind TEXT NOT NULL,
  summary TEXT NOT NULL, case_id TEXT, occurred_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_crmact ON crm_activities(tenant_id, party_id);

CREATE TABLE IF NOT EXISTS crm_promises (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  party_id TEXT NOT NULL, promisor TEXT NOT NULL,
  what TEXT NOT NULL, due_at TEXT, status TEXT NOT NULL DEFAULT 'open',
  case_id TEXT);
CREATE INDEX IF NOT EXISTS ix_crmprom
  ON crm_promises(tenant_id, party_id, status);

CREATE TABLE IF NOT EXISTS crm_preferences (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  party_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'stated');
CREATE INDEX IF NOT EXISTS ix_crmpref ON crm_preferences(tenant_id, party_id);

CREATE TABLE IF NOT EXISTS crm_facts (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  party_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
  verified INTEGER NOT NULL DEFAULT 0, verified_by TEXT,
  source TEXT NOT NULL DEFAULT 'unknown');
CREATE INDEX IF NOT EXISTS ix_crmfact ON crm_facts(tenant_id, party_id, key);

CREATE TABLE IF NOT EXISTS crm_memory_items (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  party_id TEXT NOT NULL, memory_type TEXT NOT NULL,
  content_json TEXT NOT NULL DEFAULT '{}', source TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0.5,
  scope TEXT NOT NULL DEFAULT 'tenant',
  sensitive INTEGER NOT NULL DEFAULT 0,
  recorded_at TEXT NOT NULL, verified_by TEXT);
CREATE INDEX IF NOT EXISTS ix_crmmem
  ON crm_memory_items(tenant_id, party_id, memory_type);

CREATE TABLE IF NOT EXISTS crm_merge_decisions (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  surviving_party_id TEXT NOT NULL,
  merged_party_ids_json TEXT NOT NULL,
  decided_by TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
  decided_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_crmmerge ON crm_merge_decisions(tenant_id);

CREATE TABLE IF NOT EXISTS crm_external_references (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  party_id TEXT NOT NULL REFERENCES crm_parties(id),
  provider TEXT NOT NULL, object_kind TEXT NOT NULL,
  external_id TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_crmext
  ON crm_external_references(tenant_id, provider, external_id);

CREATE TABLE IF NOT EXISTS crm_external_sync_events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  provider TEXT NOT NULL, direction TEXT NOT NULL,
  object_kind TEXT NOT NULL, decision TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}', idempotency_key TEXT,
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_crmsync
  ON crm_external_sync_events(tenant_id, provider);

CREATE TABLE IF NOT EXISTS crm_external_sync_cursors (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  provider TEXT NOT NULL, last_synced_at TEXT, cursor_token TEXT);
CREATE INDEX IF NOT EXISTS ix_crmcursor
  ON crm_external_sync_cursors(tenant_id, provider);
"""),
    (8, """
-- v8: Canonical Evidence Report Package registry (EVIDENCE-REPORT-C2).
-- Immutable-ish proof-report artifacts: the full canonical payload + package
-- are stored verbatim so a report is replayable/verifiable later. New reports
-- never overwrite prior ones (new id); supersedes/parent link the lineage.
CREATE TABLE IF NOT EXISTS evidence_proof_reports (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL, case_id TEXT,
  report_type TEXT NOT NULL, report_version INTEGER NOT NULL DEFAULT 1,
  report_status TEXT NOT NULL DEFAULT 'GENERATED',
  report_hash TEXT NOT NULL, package_hash TEXT NOT NULL,
  final_verdict TEXT NOT NULL,
  payload_json TEXT NOT NULL, package_json TEXT NOT NULL,
  parent_report_id TEXT, supersedes_report_id TEXT,
  generated_by TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_evreport
  ON evidence_proof_reports(tenant_id, evidence_id, created_at);
"""),
    (9, """
-- v9: Finalis AI Employee identity (CORE-A1). Tenant-scoped, non-autonomous
-- AI worker identity + authority boundary. No global unrestricted identity;
-- every dangerous capability is disabled and cannot be flipped by a prompt.
CREATE TABLE IF NOT EXISTS ai_employees (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  display_name TEXT NOT NULL DEFAULT 'Finalis AI Employee',
  internal_name TEXT NOT NULL DEFAULT 'finalis-ai-employee',
  identity_type TEXT NOT NULL DEFAULT 'AI_EMPLOYEE',
  role TEXT NOT NULL DEFAULT 'ai_worker',
  segment_capabilities_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  identity_version INTEGER NOT NULL DEFAULT 1,
  profile_version TEXT NOT NULL DEFAULT 'finalis-ai-employee-profile-v1',
  human_supervisor_required INTEGER NOT NULL DEFAULT 1,
  default_supervisor_role TEXT NOT NULL DEFAULT 'owner',
  created_by TEXT NOT NULL DEFAULT 'system',
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_employees ON ai_employees(tenant_id);
"""),
    (10, """
-- v10: Secure Work Intake Registry + Canonical Task Contract (CORE-A2).
-- Delegated work intake — NOT execution. Full canonical envelope + contract
-- are stored verbatim; task text is untrusted; append-only intake events.
CREATE TABLE IF NOT EXISTS ai_tasks (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  requester_user_id TEXT NOT NULL, requester_role TEXT NOT NULL DEFAULT '',
  assigned_ai_employee_id TEXT NOT NULL,
  capability_snapshot_hash TEXT NOT NULL DEFAULT '',
  source_channel TEXT NOT NULL DEFAULT 'WEB',
  idempotency_key TEXT, deduplication_key TEXT NOT NULL DEFAULT '',
  envelope_hash TEXT NOT NULL, contract_hash TEXT NOT NULL,
  task_type TEXT NOT NULL, segment TEXT NOT NULL DEFAULT '',
  task_status TEXT NOT NULL DEFAULT 'CREATED',
  task_version INTEGER NOT NULL DEFAULT 1,
  risk_level TEXT NOT NULL DEFAULT 'MEDIUM',
  authority_decision TEXT NOT NULL DEFAULT '',
  authority_hard_fail INTEGER NOT NULL DEFAULT 0,
  subject_type TEXT, subject_id TEXT,
  expires_at TEXT, stale_after TEXT,
  payload_json TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, cancelled_at TEXT);
CREATE INDEX IF NOT EXISTS ix_ai_tasks
  ON ai_tasks(tenant_id, created_at);
-- UNIQUE so a concurrent multi-worker retry cannot defeat idempotency; NULL
-- keys stay distinct in SQLite, so keyless tasks are never blocked.
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_tasks_idem
  ON ai_tasks(tenant_id, requester_user_id, idempotency_key);

CREATE TABLE IF NOT EXISTS ai_task_intake_events (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
  actor_id TEXT NOT NULL, actor_type TEXT NOT NULL DEFAULT 'human',
  event_type TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_task_events
  ON ai_task_intake_events(tenant_id, task_id, created_at);
"""),
    (11, """
-- v11: Causally Verifiable Run Ledger + Event-Sourced Replay (CORE-A3).
-- The forensic audit spine: hash-linked append-only run events, replayable to
-- recompute run state. Records what happened; grants no permission to act.
CREATE TABLE IF NOT EXISTS ai_runs (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, task_id TEXT NOT NULL,
  task_envelope_hash TEXT NOT NULL DEFAULT '',
  task_contract_hash TEXT NOT NULL DEFAULT '',
  requester_user_id TEXT NOT NULL, assigned_ai_employee_id TEXT NOT NULL,
  segment TEXT NOT NULL DEFAULT '', run_type TEXT NOT NULL DEFAULT 'task_run',
  run_status TEXT NOT NULL DEFAULT 'CREATED',
  run_version INTEGER NOT NULL DEFAULT 1, trace_id TEXT NOT NULL DEFAULT '',
  risk_level TEXT NOT NULL DEFAULT 'MEDIUM',
  authority_decision TEXT NOT NULL DEFAULT '',
  event_count INTEGER NOT NULL DEFAULT 0,
  latest_event_hash TEXT, run_chain_hash TEXT, run_state_hash TEXT,
  run_event_merkle_root TEXT,
  payload_json TEXT NOT NULL, created_by TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, cancelled_at TEXT);
CREATE INDEX IF NOT EXISTS ix_ai_runs ON ai_runs(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_runs_task ON ai_runs(tenant_id, task_id);

CREATE TABLE IF NOT EXISTS ai_run_events (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
  task_id TEXT NOT NULL, event_index INTEGER NOT NULL,
  event_type TEXT NOT NULL, event_status TEXT NOT NULL DEFAULT 'RECORDED',
  previous_event_hash TEXT, event_hash TEXT NOT NULL,
  envelope_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_run_events_idx
  ON ai_run_events(tenant_id, run_id, event_index);
CREATE INDEX IF NOT EXISTS ix_ai_run_events
  ON ai_run_events(tenant_id, run_id, event_index);
"""),
    (12, """
-- v12: Human Approval Gate Foundation (CORE-A4.1, PART 1). Scoped, policy-
-- bound approval REQUESTS only — no approve/reject/grant/consume here.
-- Creating an approval request approves and executes nothing.
CREATE TABLE IF NOT EXISTS ai_approval_requests (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, run_id TEXT NOT NULL,
  task_id TEXT NOT NULL, requester_user_id TEXT NOT NULL,
  assigned_ai_employee_id TEXT NOT NULL DEFAULT '',
  approval_action_type TEXT NOT NULL DEFAULT '',
  approval_status TEXT NOT NULL DEFAULT 'REQUESTED',
  approval_risk_level TEXT NOT NULL DEFAULT 'MEDIUM',
  required_approver_role TEXT NOT NULL DEFAULT 'owner',
  approval_request_hash TEXT NOT NULL, approval_package_hash TEXT NOT NULL,
  approval_challenge_hash TEXT, approval_precondition_hash TEXT NOT NULL,
  policy_decision_hash TEXT NOT NULL,
  task_contract_hash TEXT NOT NULL DEFAULT '',
  task_envelope_hash TEXT NOT NULL DEFAULT '',
  run_state_hash TEXT, run_chain_hash TEXT,
  expires_at TEXT, payload_json TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_approvals
  ON ai_approval_requests(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_approvals_run
  ON ai_approval_requests(tenant_id, run_id);
"""),
    (13, """
-- v13: Human Approval Gate Decisions + Non-Transferable Grants (CORE-A4.2,
-- PART 2). Records a scoped human decision and a local, non-transferable,
-- revalidate-before-use approval grant. An approval grant authorizes only a
-- future gated transition; it executes nothing and is not an OAuth/GNAP token.
CREATE TABLE IF NOT EXISTS ai_approval_decisions (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  approval_request_id TEXT NOT NULL, run_id TEXT NOT NULL,
  task_id TEXT NOT NULL, decider_user_id TEXT NOT NULL,
  decider_role TEXT NOT NULL,
  decider_actor_type TEXT NOT NULL DEFAULT 'HUMAN_USER',
  decision TEXT NOT NULL, decision_reason TEXT NOT NULL DEFAULT '',
  decision_hash TEXT NOT NULL, decision_chain_hash TEXT NOT NULL,
  viewed_package_hash TEXT NOT NULL DEFAULT '',
  challenge_passed INTEGER NOT NULL DEFAULT 0,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_appr_decisions
  ON ai_approval_decisions(tenant_id, approval_request_id, created_at);

CREATE TABLE IF NOT EXISTS ai_approval_grants (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  approval_request_id TEXT NOT NULL, approval_decision_id TEXT NOT NULL,
  run_id TEXT NOT NULL, task_id TEXT NOT NULL,
  approval_action_type TEXT NOT NULL DEFAULT '',
  grant_status TEXT NOT NULL DEFAULT 'ISSUED',
  grant_type TEXT NOT NULL DEFAULT 'LOCAL_NON_TRANSFERABLE_APPROVAL_GRANT',
  grant_usage_policy TEXT NOT NULL DEFAULT 'SINGLE_USE_READY',
  single_use INTEGER NOT NULL DEFAULT 1,
  approval_grant_hash TEXT NOT NULL, grant_nonce_hash TEXT NOT NULL,
  approval_decision_hash TEXT NOT NULL, policy_decision_hash TEXT NOT NULL,
  task_contract_hash TEXT NOT NULL DEFAULT '',
  task_envelope_hash TEXT NOT NULL DEFAULT '',
  run_state_hash TEXT, run_chain_hash TEXT,
  consume_check_count INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT, revoked_at TEXT, superseded_at TEXT, consumed_at TEXT,
  validated_at TEXT, last_validation_status TEXT, last_validation_reason TEXT,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_appr_grants
  ON ai_approval_grants(tenant_id, approval_request_id);
CREATE INDEX IF NOT EXISTS ix_ai_appr_grants_scope
  ON ai_approval_grants(tenant_id, run_id, task_id, approval_action_type);
"""),
    (14, """
-- v14: ViktorAI Deterministic Lifecycle Kernel (CORE-A5). Append-only task
-- transition ledger. The state machine controls lifecycle state ONLY; a
-- transition executes nothing (no Tool Broker, LLM, payment, message, CRM,
-- evidence rewrite or consent override). Server-side state is authoritative.
CREATE TABLE IF NOT EXISTS ai_task_transitions (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, task_id TEXT NOT NULL,
  run_id TEXT, approval_request_id TEXT, approval_grant_id TEXT,
  transition_index INTEGER NOT NULL,
  transition_idempotency_key TEXT,
  from_state TEXT NOT NULL, to_state TEXT NOT NULL,
  transition_event TEXT NOT NULL, transition_status TEXT NOT NULL,
  requested_by_actor_id TEXT NOT NULL, requested_by_actor_type TEXT NOT NULL,
  requested_by_role TEXT NOT NULL DEFAULT '',
  task_version_before INTEGER, task_version_after INTEGER,
  transition_hash TEXT NOT NULL, previous_transition_hash TEXT,
  transition_chain_hash TEXT NOT NULL,
  guard_vector_hash TEXT NOT NULL DEFAULT '',
  task_state_hash_after TEXT,
  input_hash TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_task_transitions
  ON ai_task_transitions(tenant_id, task_id, transition_index);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_task_transitions_idx
  ON ai_task_transitions(tenant_id, task_id, transition_index);
CREATE INDEX IF NOT EXISTS ix_ai_task_transitions_idem
  ON ai_task_transitions(tenant_id, task_id, transition_idempotency_key);
"""),
    (15, """
-- v15: ViktorAI Evidence-Grade Artifact System (CORE-A6). Formal, versioned,
-- hash-verifiable work products. The Artifact System records and versions
-- work products; it executes nothing (no send, tool, LLM, payment, CRM,
-- evidence rewrite, export or signing). Server-side artifact truth is
-- authoritative.
CREATE TABLE IF NOT EXISTS ai_artifacts (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  task_id TEXT, run_id TEXT, approval_request_id TEXT, approval_grant_id TEXT,
  created_by_actor_id TEXT NOT NULL, created_by_actor_type TEXT NOT NULL,
  assigned_ai_employee_id TEXT NOT NULL DEFAULT '',
  artifact_type TEXT NOT NULL, artifact_status TEXT NOT NULL DEFAULT 'DRAFT',
  artifact_trust_tier TEXT NOT NULL DEFAULT 'AI_DRAFT_UNVERIFIED',
  artifact_version INTEGER NOT NULL DEFAULT 1,
  latest_version_id TEXT NOT NULL,
  artifact_state_hash TEXT NOT NULL, artifact_manifest_hash TEXT NOT NULL,
  artifact_content_hash TEXT NOT NULL,
  quarantine_status TEXT NOT NULL DEFAULT 'CLEAN',
  materialization_status TEXT NOT NULL DEFAULT 'MATERIALIZATION_BLOCKED',
  supersedes_artifact_id TEXT,
  task_contract_hash TEXT NOT NULL DEFAULT '',
  subject_type TEXT, subject_id TEXT, case_id TEXT,
  payload_json TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  expires_at TEXT);
CREATE INDEX IF NOT EXISTS ix_ai_artifacts
  ON ai_artifacts(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_artifacts_task
  ON ai_artifacts(tenant_id, task_id);
CREATE INDEX IF NOT EXISTS ix_ai_artifacts_run
  ON ai_artifacts(tenant_id, run_id);

CREATE TABLE IF NOT EXISTS ai_artifact_versions (
  id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
  version_number INTEGER NOT NULL, version_status TEXT NOT NULL DEFAULT 'DRAFT',
  content_format TEXT NOT NULL DEFAULT 'TEXT',
  content_hash TEXT NOT NULL, manifest_hash TEXT NOT NULL,
  claim_graph_hash TEXT NOT NULL DEFAULT '',
  provenance_hash TEXT NOT NULL DEFAULT '', abom_hash TEXT NOT NULL DEFAULT '',
  version_hash TEXT NOT NULL, previous_version_hash TEXT,
  version_chain_hash TEXT NOT NULL,
  created_by_actor_id TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_artifact_versions_num
  ON ai_artifact_versions(tenant_id, artifact_id, version_number);
CREATE INDEX IF NOT EXISTS ix_ai_artifact_versions
  ON ai_artifact_versions(tenant_id, artifact_id, version_number);
"""),
    (16, """
-- v16: ViktorAI Zero-Trust Tool Capability Governance Registry (TOOL-B1). A
-- security-first internal registry of tool CAPABILITY DESCRIPTORS for a FUTURE
-- Tool Broker. This is NOT a Tool Broker and executes nothing: no tool call, no
-- MCP, no LLM, no external provider, no customer message, no payment, no CRM
-- write, no evidence rewrite, no export. There is NO execute endpoint. Admission
-- means only that a future broker MAY consider the tool. Server-side governance
-- truth is authoritative over untrusted declared descriptor content.
CREATE TABLE IF NOT EXISTS ai_tools (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  tool_key TEXT NOT NULL, tool_name TEXT NOT NULL,
  created_by_actor_id TEXT NOT NULL, created_by_actor_type TEXT NOT NULL,
  category TEXT NOT NULL, side_effect_class TEXT NOT NULL,
  risk_class TEXT NOT NULL DEFAULT 'MEDIUM',
  trust_tier TEXT NOT NULL DEFAULT 'AI_PROPOSED_UNVERIFIED',
  status TEXT NOT NULL DEFAULT 'DRAFT',
  tool_version INTEGER NOT NULL DEFAULT 1,
  latest_version_id TEXT NOT NULL,
  tool_state_hash TEXT NOT NULL, descriptor_hash TEXT NOT NULL,
  tbom_hash TEXT NOT NULL DEFAULT '',
  policy_capsule_hash TEXT NOT NULL DEFAULT '',
  risk_capsule_hash TEXT NOT NULL DEFAULT '',
  admission_package_hash TEXT NOT NULL DEFAULT '',
  quarantine_status TEXT NOT NULL DEFAULT 'CLEAN',
  admitted INTEGER NOT NULL DEFAULT 0,
  supersedes_tool_id TEXT,
  payload_json TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_tools
  ON ai_tools(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_tools_key
  ON ai_tools(tenant_id, tool_key);
CREATE INDEX IF NOT EXISTS ix_ai_tools_status
  ON ai_tools(tenant_id, status);

CREATE TABLE IF NOT EXISTS ai_tool_versions (
  id TEXT PRIMARY KEY, tool_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
  version_number INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'DRAFT',
  descriptor_hash TEXT NOT NULL, tbom_hash TEXT NOT NULL DEFAULT '',
  policy_capsule_hash TEXT NOT NULL DEFAULT '',
  admission_package_hash TEXT NOT NULL DEFAULT '',
  version_hash TEXT NOT NULL, previous_version_hash TEXT,
  version_chain_hash TEXT NOT NULL,
  created_by_actor_id TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_tool_versions_num
  ON ai_tool_versions(tenant_id, tool_id, version_number);
CREATE INDEX IF NOT EXISTS ix_ai_tool_versions
  ON ai_tool_versions(tenant_id, tool_id, version_number);

CREATE TABLE IF NOT EXISTS ai_tool_registry_events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, tool_id TEXT,
  event_type TEXT NOT NULL, sequence INTEGER NOT NULL,
  actor_id TEXT NOT NULL, actor_type TEXT NOT NULL,
  event_hash TEXT NOT NULL, previous_event_hash TEXT NOT NULL,
  tool_state_hash TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_tool_registry_events_seq
  ON ai_tool_registry_events(tenant_id, sequence);
CREATE INDEX IF NOT EXISTS ix_ai_tool_registry_events_tool
  ON ai_tool_registry_events(tenant_id, tool_id, sequence);
"""),
    (17, """
-- v17: ViktorAI Formal Tool Descriptor Assurance Graph (TOOL-B2). A
-- security-first, formal-quality, planner-safety and descriptor-assurance
-- module over the TOOL-B1 registry. It executes nothing: no tool call, no MCP,
-- no LLM, no external provider, no descriptor rewriting. Quality is deterministic
-- and local; a quality PASS does not mean executable and cannot override any
-- TOOL-B1 security/admission state. Server-side registry truth is authoritative.
CREATE TABLE IF NOT EXISTS ai_tool_quality_reports (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, tool_id TEXT NOT NULL,
  tool_version_id TEXT NOT NULL, seq INTEGER NOT NULL,
  quality_status TEXT NOT NULL, quality_score_total INTEGER NOT NULL DEFAULT 0,
  tool_descriptor_hash TEXT NOT NULL,
  quality_report_hash TEXT NOT NULL, quality_gate_state_hash TEXT NOT NULL,
  quality_decision_hash TEXT NOT NULL,
  formal_descriptor_ir_hash TEXT NOT NULL DEFAULT '',
  assurance_graph_hash TEXT NOT NULL DEFAULT '',
  score_vector_hash TEXT NOT NULL DEFAULT '',
  quality_evidence_package_hash TEXT NOT NULL DEFAULT '',
  quality_assurance_case_hash TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_tool_quality_reports
  ON ai_tool_quality_reports(tenant_id, tool_id, seq);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_tool_quality_reports_seq
  ON ai_tool_quality_reports(tenant_id, tool_id, seq);

CREATE TABLE IF NOT EXISTS ai_tool_quality_events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, tool_id TEXT,
  event_type TEXT NOT NULL, sequence INTEGER NOT NULL,
  actor_id TEXT NOT NULL, actor_type TEXT NOT NULL,
  event_hash TEXT NOT NULL, previous_event_hash TEXT NOT NULL,
  quality_gate_state_hash TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_tool_quality_events_seq
  ON ai_tool_quality_events(tenant_id, sequence);
CREATE INDEX IF NOT EXISTS ix_ai_tool_quality_events_tool
  ON ai_tool_quality_events(tenant_id, tool_id, sequence);
"""),
    (18, """
-- v18: ViktorAI Formal Protocol Contract Proof Kernel (TOOL-B3). Internal
-- protocol-aware contracts + validation-only projections (MCP-like /
-- Apps-SDK-like / OpenAPI-like / safe planner / trace-only) over the TOOL-B1
-- registry + TOOL-B2 quality gate. Executes nothing: no MCP server/client, no
-- tool execution, no Tool Broker/LLM/external-provider call, no OAuth/token
-- issuance, no sampling/elicitation/resource/prompt serving, no network side
-- effect. All runtime capabilities are denied. A projection is a derived view
-- and can never override any TOOL-B1/TOOL-B2 security state. Registry truth is
-- authoritative.
CREATE TABLE IF NOT EXISTS ai_tool_contracts (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, tool_id TEXT NOT NULL,
  tool_version_id TEXT NOT NULL, contract_version INTEGER NOT NULL DEFAULT 1,
  contract_status TEXT NOT NULL, contract_target TEXT NOT NULL,
  contract_risk_class TEXT NOT NULL DEFAULT 'MEDIUM',
  contract_side_effect_class TEXT NOT NULL DEFAULT 'PURE_READ',
  source_descriptor_hash TEXT NOT NULL,
  source_quality_report_hash TEXT,
  source_freshness_epoch TEXT NOT NULL, revocation_epoch TEXT NOT NULL,
  contract_hash TEXT NOT NULL, contract_abi_hash TEXT NOT NULL,
  contract_normal_form_hash TEXT NOT NULL DEFAULT '',
  contract_state_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_tool_contracts
  ON ai_tool_contracts(tenant_id, tool_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_tool_contracts_status
  ON ai_tool_contracts(tenant_id, contract_status);

CREATE TABLE IF NOT EXISTS ai_tool_contract_versions (
  id TEXT PRIMARY KEY, contract_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
  tool_id TEXT NOT NULL, tool_version_id TEXT NOT NULL,
  version_number INTEGER NOT NULL,
  contract_hash TEXT NOT NULL, contract_abi_hash TEXT NOT NULL,
  contract_version_hash TEXT NOT NULL, previous_contract_version_hash TEXT,
  contract_chain_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_tool_contract_versions_num
  ON ai_tool_contract_versions(tenant_id, contract_id, version_number);

CREATE TABLE IF NOT EXISTS ai_tool_contract_projections (
  id TEXT PRIMARY KEY, contract_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
  tool_id TEXT NOT NULL, projection_target TEXT NOT NULL,
  projection_status TEXT NOT NULL,
  projection_hash TEXT NOT NULL, projection_envelope_hash TEXT NOT NULL,
  broker_readiness_status TEXT NOT NULL DEFAULT 'NOT_READY',
  payload_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_tool_contract_projections
  ON ai_tool_contract_projections(tenant_id, contract_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_tool_contract_projections_target
  ON ai_tool_contract_projections(tenant_id, contract_id, projection_target);

CREATE TABLE IF NOT EXISTS ai_tool_contract_events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, contract_id TEXT,
  tool_id TEXT, event_type TEXT NOT NULL, sequence INTEGER NOT NULL,
  actor_id TEXT NOT NULL, actor_type TEXT NOT NULL,
  event_hash TEXT NOT NULL, previous_event_hash TEXT NOT NULL,
  contract_state_hash TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_tool_contract_events_seq
  ON ai_tool_contract_events(tenant_id, sequence);
CREATE INDEX IF NOT EXISTS ix_ai_tool_contract_events_contract
  ON ai_tool_contract_events(tenant_id, contract_id, sequence);
"""),
    (19, """
-- v19: ViktorAI Causal Pre-Action Reference Monitor (TOOL-B4). A deterministic,
-- NON-EXECUTING pre-action governance layer in front of a FUTURE Tool Broker.
-- It receives internal Tool Action Proposals and returns deterministic
-- pre-action decisions over the TOOL-B1 registry + TOOL-B2 quality gate +
-- TOOL-B3 contract/broker-readiness state (which only ever NARROW authority).
-- It executes nothing: no Tool Broker, no tool execution, no dry-run, no
-- MCP/LLM/external-provider call, no OAuth/token issuance, no payment, no
-- customer message, no CRM write, no evidence mutation, no export. The single
-- most permissive outcome is ALLOWED_FOR_FUTURE_BROKER_ONLY, which still runs
-- nothing. An Action Passport is not a token; a Governance Receipt is not
-- authority; a Future Execution Lease is a NOT_IMPLEMENTED placeholder.
-- Nondelegable decisions are human-only; the AI can never self-authorize.
CREATE TABLE IF NOT EXISTS ai_action_proposals (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, tool_id TEXT NOT NULL,
  contract_id TEXT NOT NULL, action_path TEXT NOT NULL DEFAULT '',
  intent TEXT NOT NULL DEFAULT '', idempotency_key TEXT NOT NULL DEFAULT '',
  logical_clock INTEGER NOT NULL DEFAULT 0,
  proposal_hash TEXT NOT NULL,
  proposed_by_actor_id TEXT NOT NULL, proposed_by_actor_type TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_action_proposals
  ON ai_action_proposals(tenant_id, tool_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_action_proposals_key
  ON ai_action_proposals(tenant_id, idempotency_key);

CREATE TABLE IF NOT EXISTS ai_action_decisions (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, tool_id TEXT NOT NULL,
  contract_id TEXT NOT NULL, proposal_id TEXT NOT NULL,
  proposal_hash TEXT NOT NULL,
  decision_status TEXT NOT NULL, dominant_signal TEXT NOT NULL,
  idempotency_key TEXT NOT NULL DEFAULT '',
  logical_clock INTEGER NOT NULL DEFAULT 0,
  source_freshness_epoch TEXT NOT NULL DEFAULT '',
  is_replay INTEGER NOT NULL DEFAULT 0,
  decision_hash TEXT NOT NULL, decision_state_hash TEXT NOT NULL,
  decided_by_actor_id TEXT NOT NULL, decided_by_actor_type TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_action_decisions
  ON ai_action_decisions(tenant_id, tool_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_action_decisions_proposal
  ON ai_action_decisions(tenant_id, proposal_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_action_decisions_key
  ON ai_action_decisions(tenant_id, idempotency_key, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_action_decisions_status
  ON ai_action_decisions(tenant_id, decision_status);

CREATE TABLE IF NOT EXISTS ai_action_circuit_breakers (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, tool_id TEXT NOT NULL,
  breaker_state TEXT NOT NULL DEFAULT 'CLOSED',
  reason_code TEXT NOT NULL DEFAULT '',
  circuit_breaker_hash TEXT NOT NULL DEFAULT '',
  set_by_actor_id TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_action_circuit_breakers
  ON ai_action_circuit_breakers(tenant_id, tool_id);

CREATE TABLE IF NOT EXISTS ai_action_decision_events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, proposal_id TEXT,
  decision_id TEXT, event_type TEXT NOT NULL, sequence INTEGER NOT NULL,
  actor_id TEXT NOT NULL, actor_type TEXT NOT NULL,
  event_hash TEXT NOT NULL, previous_event_hash TEXT NOT NULL,
  decision_state_hash TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_action_decision_events_seq
  ON ai_action_decision_events(tenant_id, sequence);
CREATE INDEX IF NOT EXISTS ix_ai_action_decision_events_proposal
  ON ai_action_decision_events(tenant_id, proposal_id, sequence);
"""),
    (20, """
-- v20: ViktorAI Adversarially Verified Four-Plane Proof-Carrying Null Broker
-- (TOOL-B5). A deterministic internal broker SKELETON with proof-carrying NULL
-- execution only, sitting between the TOOL-B4 pre-action monitor and a
-- hypothetical FUTURE real runtime. It consumes only B4-approved proposals and
-- produces only validation / NULL_EFFECT_ONLY outcomes. It executes NOTHING:
-- no tool run, no external provider, no MCP runtime/server/client, no LLM, no
-- OAuth/token issuance, no credential handling, no payment/message/CRM/evidence/
-- export. There is NO execute endpoint. The most permissive outcome is
-- BROKER_PREPARED_FOR_FUTURE_ONLY, which still runs nothing. No null output may
-- leak sensitive payload, secrets, credentials, approval/consent artifacts,
-- customer data or hidden execution authority. The whole skeleton fails closed
-- under deterministic fault injection.
CREATE TABLE IF NOT EXISTS ai_broker_requests (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, tool_id TEXT NOT NULL,
  contract_id TEXT NOT NULL DEFAULT '', b4_proposal_id TEXT NOT NULL DEFAULT '',
  b4_decision_id TEXT NOT NULL DEFAULT '',
  action_path TEXT NOT NULL DEFAULT '', idempotency_key TEXT NOT NULL DEFAULT '',
  batch_id TEXT NOT NULL DEFAULT '', task_id TEXT NOT NULL DEFAULT '',
  case_id TEXT NOT NULL DEFAULT '', customer_id TEXT NOT NULL DEFAULT '',
  broker_request_hash TEXT NOT NULL,
  requested_by TEXT NOT NULL, requested_by_actor_type TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_broker_requests
  ON ai_broker_requests(tenant_id, tool_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_broker_requests_batch
  ON ai_broker_requests(tenant_id, batch_id);
CREATE INDEX IF NOT EXISTS ix_ai_broker_requests_key
  ON ai_broker_requests(tenant_id, idempotency_key);

CREATE TABLE IF NOT EXISTS ai_broker_outcomes (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, broker_request_id TEXT NOT NULL,
  tool_id TEXT NOT NULL DEFAULT '', contract_id TEXT NOT NULL DEFAULT '',
  b4_decision_id TEXT NOT NULL DEFAULT '',
  broker_status TEXT NOT NULL, dominant_signal TEXT NOT NULL,
  effect_outcome TEXT NOT NULL DEFAULT 'NO_EFFECT_OUTCOME',
  broker_request_hash TEXT NOT NULL DEFAULT '',
  broker_decision_hash TEXT NOT NULL, broker_state_hash TEXT NOT NULL,
  broker_proof_bundle_hash TEXT NOT NULL DEFAULT '',
  release_gate_status TEXT NOT NULL DEFAULT '',
  decided_by TEXT NOT NULL, decided_by_actor_type TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_broker_outcomes
  ON ai_broker_outcomes(tenant_id, broker_request_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_broker_outcomes_status
  ON ai_broker_outcomes(tenant_id, broker_status);

CREATE TABLE IF NOT EXISTS ai_broker_events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, broker_request_id TEXT,
  event_type TEXT NOT NULL, sequence INTEGER NOT NULL,
  actor_id TEXT NOT NULL, actor_type TEXT NOT NULL,
  event_hash TEXT NOT NULL, previous_event_hash TEXT NOT NULL,
  broker_state_hash TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_broker_events_seq
  ON ai_broker_events(tenant_id, sequence);
CREATE INDEX IF NOT EXISTS ix_ai_broker_events_request
  ON ai_broker_events(tenant_id, broker_request_id, sequence);
"""),
    (21, """
-- v21: ViktorAI Verifiable Read-Path Runtime Microkernel (TOOL-B6). The first
-- controlled runtime layer, but strictly LOCAL, DETERMINISTIC and READ-ONLY. It
-- runs local deterministic read-only adapters over FROZEN local snapshots and
-- produces provenance-verifiable safe output. It is snapshot-bound, temporally
-- isolated, semantically read-filtered, read-set-attested, output-provenance-
-- verifiable, replay-verifiable, data-diode-output-filtered, resource-budgeted
-- and information-budgeted. It NEVER reads mutable production state, mutates a
-- source artifact, calls the network/provider/MCP/LLM, reads a secret/
-- credential, or issues/derives a token. There is NO write/external/execute
-- endpoint. The most permissive outcome is RUNTIME_READ_ONLY_COMPLETED, a local
-- read-only result — never an external effect.
CREATE TABLE IF NOT EXISTS ai_runtime_snapshots (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, epoch TEXT NOT NULL DEFAULT '0',
  scope TEXT NOT NULL DEFAULT '', field_count INTEGER NOT NULL DEFAULT 0,
  snapshot_hash TEXT NOT NULL,
  created_by TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_runtime_snapshots
  ON ai_runtime_snapshots(tenant_id, epoch, created_at);

CREATE TABLE IF NOT EXISTS ai_runtime_requests (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  b5_broker_request_id TEXT NOT NULL DEFAULT '',
  adapter_id TEXT NOT NULL DEFAULT '', snapshot_id TEXT NOT NULL DEFAULT '',
  requested_epoch TEXT NOT NULL DEFAULT '',
  runtime_request_hash TEXT NOT NULL,
  requested_by TEXT NOT NULL, requested_by_actor_type TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_runtime_requests
  ON ai_runtime_requests(tenant_id, snapshot_id, created_at);

CREATE TABLE IF NOT EXISTS ai_runtime_outcomes (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, runtime_request_id TEXT NOT NULL,
  b5_broker_request_id TEXT NOT NULL DEFAULT '',
  adapter_id TEXT NOT NULL DEFAULT '', snapshot_id TEXT NOT NULL DEFAULT '',
  runtime_status TEXT NOT NULL, runtime_decision_status TEXT NOT NULL,
  runtime_outcome_kind TEXT NOT NULL DEFAULT '',
  dominant_signal TEXT NOT NULL,
  safe_output_hash TEXT NOT NULL DEFAULT '',
  runtime_request_hash TEXT NOT NULL DEFAULT '',
  runtime_decision_hash TEXT NOT NULL, runtime_state_hash TEXT NOT NULL,
  runtime_proof_bundle_hash TEXT NOT NULL DEFAULT '',
  release_gate_status TEXT NOT NULL DEFAULT '',
  decided_by TEXT NOT NULL, decided_by_actor_type TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_runtime_outcomes
  ON ai_runtime_outcomes(tenant_id, runtime_request_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_runtime_outcomes_snapshot
  ON ai_runtime_outcomes(tenant_id, snapshot_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_runtime_outcomes_status
  ON ai_runtime_outcomes(tenant_id, runtime_status);

CREATE TABLE IF NOT EXISTS ai_runtime_events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, runtime_request_id TEXT,
  event_type TEXT NOT NULL, sequence INTEGER NOT NULL,
  actor_id TEXT NOT NULL, actor_type TEXT NOT NULL,
  event_hash TEXT NOT NULL, previous_event_hash TEXT NOT NULL,
  runtime_state_hash TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_runtime_events_seq
  ON ai_runtime_events(tenant_id, sequence);
CREATE INDEX IF NOT EXISTS ix_ai_runtime_events_request
  ON ai_runtime_events(tenant_id, runtime_request_id, sequence);
"""),
    (22, """
-- v22: ViktorAI Transaction-Escrow Write-Intent Draft Runtime (TOOL-B7). The
-- first write-INTENT layer, but strictly LOCAL, DETERMINISTIC and DRAFT-ONLY.
-- It models a FUTURE write: local write-intent draft records, semantic
-- transaction drafts, transaction escrow capsules, escrowed commit-readiness
-- certificates, a placeholder-only future commit gate contract, revalidation
-- debt ledgers, semantic rollback-attack fences, action-replay/authority-
-- resurrection guards, concurrent-draft conflict graphs, transaction conflict
-- oracles, state-witness quorum vectors and effect-outbox quarantine matrices.
-- It NEVER commits, sends, pays, mutates CRM/evidence/customer state, exports,
-- calls a provider/MCP/LLM, issues/derives a token, reads a credential,
-- releases a staged effect or activates a commitment record. Every effect is a
-- placeholder; every certificate is local evidence; approval/escrow/commit-
-- readiness do NOT execute. There is NO commit/execute/effect-release/
-- activate-commitment endpoint. The most permissive outcome is
-- TRANSACTION_ESCROW_DRAFT_CREATED, a local escrowed draft — never an external
-- effect.
CREATE TABLE IF NOT EXISTS ai_write_intent_requests (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  b6_runtime_request_id TEXT NOT NULL DEFAULT '',
  target_entity_type TEXT NOT NULL DEFAULT '',
  target_entity_id TEXT NOT NULL DEFAULT '',
  write_intent_request_hash TEXT NOT NULL,
  requested_by TEXT NOT NULL, requested_by_actor_type TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_write_intent_requests
  ON ai_write_intent_requests(tenant_id, target_entity_id, created_at);

CREATE TABLE IF NOT EXISTS ai_write_intent_outcomes (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, write_intent_id TEXT NOT NULL,
  b6_runtime_request_id TEXT NOT NULL DEFAULT '',
  target_entity_id TEXT NOT NULL DEFAULT '',
  write_intent_status TEXT NOT NULL, write_intent_decision_status TEXT NOT NULL,
  write_intent_outcome_kind TEXT NOT NULL DEFAULT '',
  dominant_signal TEXT NOT NULL,
  transaction_escrow_hash TEXT NOT NULL DEFAULT '',
  escrowed_commit_readiness_certificate_hash TEXT NOT NULL DEFAULT '',
  write_intent_request_hash TEXT NOT NULL DEFAULT '',
  write_intent_decision_hash TEXT NOT NULL,
  write_intent_state_hash TEXT NOT NULL,
  write_intent_proof_bundle_hash TEXT NOT NULL DEFAULT '',
  release_gate_status TEXT NOT NULL DEFAULT '',
  ready_for_future_commit_only INTEGER NOT NULL DEFAULT 0,
  decided_by TEXT NOT NULL, decided_by_actor_type TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ai_write_intent_outcomes
  ON ai_write_intent_outcomes(tenant_id, write_intent_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_write_intent_outcomes_entity
  ON ai_write_intent_outcomes(tenant_id, target_entity_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_write_intent_outcomes_status
  ON ai_write_intent_outcomes(tenant_id, write_intent_status);

CREATE TABLE IF NOT EXISTS ai_write_intent_events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, write_intent_id TEXT,
  event_type TEXT NOT NULL, sequence INTEGER NOT NULL,
  actor_id TEXT NOT NULL, actor_type TEXT NOT NULL,
  event_hash TEXT NOT NULL, previous_event_hash TEXT NOT NULL,
  write_intent_state_hash TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_write_intent_events_seq
  ON ai_write_intent_events(tenant_id, sequence);
CREATE INDEX IF NOT EXISTS ix_ai_write_intent_events_request
  ON ai_write_intent_events(tenant_id, write_intent_id, sequence);
"""),
]


def utcnow() -> str:
    return datetime.utcnow().isoformat()


class Database:
    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.migrate()

    def migrate(self) -> int:
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS schema_version "
                    "(version INTEGER NOT NULL)")
        row = cur.execute("SELECT MAX(version) v FROM schema_version"
                          ).fetchone()
        current = row["v"] or 0
        for version, sql in MIGRATIONS:
            if version > current:
                try:
                    cur.executescript(sql)
                except Exception as e:      # idempotent ALTERs on re-run
                    if "duplicate column" not in str(e):
                        raise
                cur.execute("INSERT INTO schema_version VALUES (?)",
                            (version,))
                current = version
        self.conn.commit()
        return current

    # -- tiny helpers ----------------------------------------------------------
    def insert(self, table: str, row: dict[str, Any]) -> None:
        keys = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        self.conn.execute(f"INSERT INTO {table} ({keys}) VALUES ({marks})",
                          tuple(row.values()))
        self.conn.commit()

    def update(self, table: str, row_id: str, fields: dict[str, Any]) -> None:
        sets = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE {table} SET {sets} WHERE id=?",
                          (*fields.values(), row_id))
        self.conn.commit()

    def all(self, sql: str, *params) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, *params) -> Optional[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchone()


class DbAuditLog(AuditLog):
    """AuditLog that writes through to the database, preserving the chain.

    The chain head is loaded from the DB on startup, so restarts continue the
    same chain and `verify_chain` validates rows read back from SQL.
    """

    def __init__(self, db: Database, tenant_id: Optional[str] = None) -> None:
        super().__init__()
        self.db = db
        self.tenant_id = tenant_id
        self._load()

    def _load(self) -> None:
        self._events = []
        for r in self.db.all(
                "SELECT * FROM audit_events ORDER BY seq"):
            ev = AuditEvent(event_type=r["event_type"], actor=r["actor"],
                            case_id=r["case_id"],
                            payload=json.loads(r["payload_json"]),
                            hash_prev=r["hash_prev"],
                            hash_self=r["hash_self"],
                            created_at=r["created_at"], id=r["id"])
            self._events.append(ev)

    def verify_chain(self) -> bool:
        # The DB is the source of truth: another writer (seeder, second app
        # instance) may have appended rows this instance never saw, so a
        # stale in-memory view would report a false chain break.
        self._load()
        return super().verify_chain()

    def append(self, *, event_type: str, actor: str,
               case_id: Optional[str] = None,
               payload: Optional[dict[str, Any]] = None) -> AuditEvent:
        # Chain from the DATABASE head, not the in-memory list — multiple
        # DbAuditLog instances (seeder, app, verifier) over one DB must form
        # a single chain. (Single-writer-per-DB assumption for the dev shell;
        # production serializes appends in a transaction.)
        last = self.db.one(
            "SELECT hash_self FROM audit_events ORDER BY seq DESC LIMIT 1")
        prev = last["hash_self"] if last else self.GENESIS
        # Normalize payload through JSON so the digest at append time equals
        # the digest of the row read back from SQL (datetimes -> str, etc.).
        normalized = json.loads(json.dumps(payload or {}, default=str))
        ev = AuditEvent(event_type=event_type, actor=actor, case_id=case_id,
                        payload=normalized, hash_prev=prev)
        ev.hash_self = self._digest(ev)
        self._events.append(ev)
        self.db.insert("audit_events", {
            "id": ev.id, "tenant_id": self.tenant_id, "case_id": ev.case_id,
            "event_type": ev.event_type, "actor": ev.actor,
            "payload_json": json.dumps(ev.payload),
            "hash_prev": ev.hash_prev, "hash_self": ev.hash_self,
            "created_at": ev.created_at})
        return ev
