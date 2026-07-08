"""Evidence Trust Fabric metadata persistence (migration v5).

Stores evidence METADATA — pointer + hash + state + chain/access events +
decision contracts. Raw bytes live only in the storage provider's vault.
Tenant-scoped reads only; there is no query path without tenant_id.
"""
from __future__ import annotations

import json
from typing import Optional

from ..evidence.models import (EvidenceAccessEvent,
                               EvidenceDecisionContract, EvidenceObject,
                               LegalHoldRecord)
from .db import Database, utcnow


class EvidenceStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, ev: EvidenceObject) -> None:
        row = {
            "id": ev.id, "tenant_id": ev.tenant_id, "case_id": ev.case_id,
            "evidence_type": ev.evidence_type, "state": ev.state,
            "original_filename": ev.meta.original_filename,
            "declared_mime": ev.meta.declared_mime,
            "detected_mime": ev.meta.detected_mime,
            "extension": ev.meta.extension,
            "size_bytes": ev.meta.size_bytes,
            "mime_mismatch": int(ev.meta.mime_mismatch),
            "active_content": int(ev.meta.active_content),
            "storage_provider": ev.storage.provider if ev.storage else "",
            "storage_key": ev.storage.key if ev.storage else "",
            "sha256": ev.integrity.digest if ev.integrity else "",
            "sensitivity": ev.sensitivity,
            "injection_risk": ev.injection_risk,
            "symbols_json": json.dumps([
                {"id": s.id, "kind": s.kind, "trusted": s.trusted,
                 "human_verified_for": s.human_verified_for,
                 "origin": s.marker.origin, "reason": s.marker.reason}
                for s in ev.symbols]),
            "parser_kind": ev.parser_kind,
            "human_verified": int(ev.human_verified),
            "legal_hold": int(ev.legal_hold),
            "retention_until": ev.retention_until.isoformat()
            if ev.retention_until else None,
            "uploaded_by": ev.uploaded_by,
            "source_kind": ev.source.kind,
            "updated_at": utcnow(),
        }
        if self.db.one("SELECT id FROM evidence_objects WHERE id=?", ev.id):
            self.db.update("evidence_objects", ev.id, row)
        else:
            self.db.insert("evidence_objects", row)
        # Chain events are append-only: insert only the new tail.
        have = {r["id"] for r in self.db.all(
            "SELECT id FROM evidence_chain_events WHERE evidence_id=?",
            ev.id)}
        for ce in ev.chain.events:
            if ce.id not in have:
                self.db.insert("evidence_chain_events", {
                    "id": ce.id, "tenant_id": ev.tenant_id,
                    "evidence_id": ev.id, "event_type": ce.event_type,
                    "actor": ce.actor,
                    "payload_json": json.dumps(ce.payload, default=str),
                    "hash_prev": ce.hash_prev, "hash_self": ce.hash_self,
                    "created_at": ce.created_at.isoformat()})

    def load_symbols(self, evidence_id: str, *, tenant_id: str) -> list:
        """Rehydrate symbols with their sticky untrusted markers — a
        reread NEVER upgrades trust."""
        from ..evidence.models import (EvidenceSymbol,
                                       EvidenceUntrustedDataMarker)
        row = self.get(evidence_id, tenant_id=tenant_id)
        if row is None:
            return []
        return [EvidenceSymbol(
                    evidence_id=evidence_id, kind=s["kind"],
                    trusted=bool(s["trusted"]),
                    human_verified_for=s["human_verified_for"],
                    marker=EvidenceUntrustedDataMarker(
                        origin=s["origin"], reason=s["reason"]),
                    id=s["id"])
                for s in json.loads(row["symbols_json"])]

    def get(self, evidence_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one("SELECT * FROM evidence_objects WHERE id=? AND "
                        "tenant_id=?", evidence_id, tenant_id)
        return dict(r) if r else None

    def list(self, *, tenant_id: str,
             case_id: Optional[str] = None) -> list[dict]:
        sql = "SELECT * FROM evidence_objects WHERE tenant_id=?"
        params = [tenant_id]
        if case_id:
            sql += " AND case_id=?"
            params.append(case_id)
        return [dict(r) for r in self.db.all(
            sql + " ORDER BY created_at", *params)]

    def chain_events(self, evidence_id: str, *,
                     tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM evidence_chain_events WHERE evidence_id=? AND "
            "tenant_id=? ORDER BY created_at", evidence_id, tenant_id)]

    def save_access_event(self, event: EvidenceAccessEvent) -> None:
        self.db.insert("evidence_access_events", {
            "id": event.id, "tenant_id": event.tenant_id,
            "evidence_id": event.evidence_id,
            "actor_kind": event.actor_kind, "actor_id": event.actor_id,
            "purpose": event.purpose, "decision": event.decision})

    def access_events(self, evidence_id: str, *,
                      tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM evidence_access_events WHERE evidence_id=? "
            "AND tenant_id=?", evidence_id, tenant_id)]

    def save_contract(self, c: EvidenceDecisionContract) -> None:
        self.db.insert("evidence_decision_contracts", {
            "id": c.id, "tenant_id": c.tenant_id, "case_id": c.case_id,
            "decision_type": c.decision_type, "actor": c.actor,
            "evidence_ids_json": json.dumps(c.evidence_ids),
            "admissible_json": json.dumps(c.admissible_ids),
            "rejected_json": json.dumps(c.rejected_ids),
            "facts_json": json.dumps(c.facts, default=str),
            "hard_blockers_json": json.dumps(c.hard_blockers),
            "trust_summary": c.trust_summary,
            "ai_access_level": c.ai_access_level,
            "human_verified": int(c.human_verified),
            "final_decision": c.final_decision,
            "audit_event_id": c.audit_event_id})

    def contracts(self, *, tenant_id: str,
                  case_id: Optional[str] = None) -> list[dict]:
        sql = ("SELECT * FROM evidence_decision_contracts WHERE "
               "tenant_id=?")
        params = [tenant_id]
        if case_id:
            sql += " AND case_id=?"
            params.append(case_id)
        return [dict(r) for r in self.db.all(sql, *params)]

    def save_legal_hold(self, hold: LegalHoldRecord) -> None:
        self.db.insert("evidence_legal_holds", {
            "id": hold.id, "tenant_id": hold.tenant_id,
            "evidence_id": hold.evidence_id, "reason": hold.reason,
            "placed_by": hold.placed_by,
            "released_at": hold.released_at.isoformat()
            if hold.released_at else None})
