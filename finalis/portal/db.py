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
