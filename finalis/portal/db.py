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
