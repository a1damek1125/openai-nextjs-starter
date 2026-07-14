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

    def all_objects(self, *, tenant_id: Optional[str] = None) -> list[dict]:
        """Deterministic order for event-sourced rehydration."""
        if tenant_id is None:
            rows = self.db.all("SELECT * FROM evidence_objects "
                               "ORDER BY created_at, id")
        else:
            rows = self.db.all("SELECT * FROM evidence_objects WHERE "
                               "tenant_id=? ORDER BY created_at, id",
                               tenant_id)
        return [dict(r) for r in rows]

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
        # rowid preserves the true append order (deterministic even when
        # created_at ties at microsecond precision).
        return [dict(r) for r in self.db.all(
            "SELECT * FROM evidence_chain_events WHERE evidence_id=? AND "
            "tenant_id=? ORDER BY rowid", evidence_id, tenant_id)]

    def all_chain_events(self, *, tenant_id: str) -> list[dict]:
        """All chain events for a tenant in true global append order
        (rowid). Append-only: new events always extend the leaf list, so
        Merkle roots stay consistent across regenerations."""
        return [dict(r) for r in self.db.all(
            "SELECT * FROM evidence_chain_events WHERE tenant_id=? "
            "ORDER BY rowid", tenant_id)]

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

    def save_contract(self, c: EvidenceDecisionContract, *,
                      contract_hash: str = "", policy_version: str = "",
                      requested_action: str = "", causal_result: str = "",
                      user_intent_reference: Optional[str] = None,
                      would_survive: Optional[bool] = None) -> None:
        # Append-only: a contract id is written exactly once.
        if self.db.one("SELECT id FROM evidence_decision_contracts "
                       "WHERE id=?", c.id):
            return
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
            "audit_event_id": c.audit_event_id,
            "contract_hash": contract_hash,
            "policy_version": policy_version,
            "requested_action": requested_action,
            "causal_result": causal_result,
            "user_intent_reference": user_intent_reference,
            "would_survive": None if would_survive is None
            else int(would_survive)})

    def contracts(self, *, tenant_id: str,
                  case_id: Optional[str] = None,
                  evidence_id: Optional[str] = None) -> list[dict]:
        sql = ("SELECT * FROM evidence_decision_contracts WHERE "
               "tenant_id=?")
        params = [tenant_id]
        if case_id:
            sql += " AND case_id=?"
            params.append(case_id)
        rows = [dict(r) for r in self.db.all(
            sql + " ORDER BY created_at", *params)]
        if evidence_id:
            rows = [r for r in rows
                    if evidence_id in json.loads(r["evidence_ids_json"])]
        return rows

    def get_contract(self, contract_id: str, *,
                     tenant_id: str) -> Optional[dict]:
        r = self.db.one("SELECT * FROM evidence_decision_contracts WHERE "
                        "id=? AND tenant_id=?", contract_id, tenant_id)
        return dict(r) if r else None

    # -- V-E: derivatives / retention / merkle / policy versions -----------
    def save_derivative(self, tenant_id: str, m) -> None:
        self.db.insert("evidence_derivatives", {
            "id": m.id, "tenant_id": tenant_id,
            "evidence_id": m.source_evidence_id,
            "derivative_kind": m.derivative_kind,
            "policy_decision": m.policy_decision,
            "confidence": m.confidence,
            "is_placeholder": int(m.is_placeholder),
            "active_content_removed": int(m.active_content_removed),
            "safe_text": m.safe_text,
            "limitations_json": json.dumps(m.limitations),
            "manifest_hash": m.manifest_hash,
            "generated_at": m.generated_at})

    def derivatives(self, evidence_id: str, *, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM evidence_derivatives WHERE evidence_id=? AND "
            "tenant_id=? ORDER BY generated_at", evidence_id, tenant_id)]

    def save_retention_policy(self, p) -> None:
        self.db.insert("evidence_retention_policies", {
            "id": __import__("uuid").uuid4().hex,
            "tenant_id": p.tenant_id, "evidence_id": p.evidence_id,
            "mode": p.mode,
            "retention_until": p.retention_until.isoformat()
            if p.retention_until else None,
            "native_worm": int(p.native_worm),
            "policy_version": p.policy_version})

    def retention_policy(self, evidence_id: str, *,
                         tenant_id: str) -> Optional[dict]:
        r = self.db.one("SELECT * FROM evidence_retention_policies WHERE "
                        "evidence_id=? AND tenant_id=? ORDER BY created_at "
                        "DESC LIMIT 1", evidence_id, tenant_id)
        return dict(r) if r else None

    def save_merkle_root(self, root, leaves: list, *,
                         created_at: str) -> None:
        self.db.insert("evidence_merkle_roots", {
            "id": root.batch_id, "tenant_id": root.tenant_id,
            "root": root.root, "size": root.size,
            "leaves_json": json.dumps(leaves), "created_at": created_at})

    def merkle_roots(self, *, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM evidence_merkle_roots WHERE tenant_id=? "
            "ORDER BY created_at", tenant_id)]

    def get_merkle_root(self, root_id: str, *,
                        tenant_id: str) -> Optional[dict]:
        r = self.db.one("SELECT * FROM evidence_merkle_roots WHERE id=? "
                        "AND tenant_id=?", root_id, tenant_id)
        return dict(r) if r else None

    # -- Canonical Evidence Report Package registry (EVIDENCE-REPORT-C2) ----------
    def save_report(self, *, report_id: str, tenant_id: str, evidence_id: str,
                    case_id, report_type: str, report_version: int,
                    report_status: str, report_hash: str, package_hash: str,
                    final_verdict: str, payload_json: str, package_json: str,
                    parent_report_id, supersedes_report_id, generated_by: str,
                    created_at: str) -> None:
        self.db.insert("evidence_proof_reports", {
            "id": report_id, "tenant_id": tenant_id,
            "evidence_id": evidence_id, "case_id": case_id,
            "report_type": report_type, "report_version": report_version,
            "report_status": report_status, "report_hash": report_hash,
            "package_hash": package_hash, "final_verdict": final_verdict,
            "payload_json": payload_json, "package_json": package_json,
            "parent_report_id": parent_report_id,
            "supersedes_report_id": supersedes_report_id,
            "generated_by": generated_by, "created_at": created_at})

    def get_report(self, report_id: str, *,
                   tenant_id: str) -> Optional[dict]:
        r = self.db.one("SELECT * FROM evidence_proof_reports WHERE id=? "
                        "AND tenant_id=?", report_id, tenant_id)
        return dict(r) if r else None

    def reports_for_evidence(self, evidence_id: str, *,
                             tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM evidence_proof_reports WHERE evidence_id=? AND "
            "tenant_id=? ORDER BY created_at", evidence_id, tenant_id)]

    def latest_report_hash_for_evidence(self, evidence_id: str, *,
                                        tenant_id: str) -> Optional[str]:
        r = self.db.one(
            "SELECT report_hash FROM evidence_proof_reports WHERE "
            "evidence_id=? AND tenant_id=? ORDER BY created_at DESC LIMIT 1",
            evidence_id, tenant_id)
        return r["report_hash"] if r else None

    def save_policy_version(self, version: str, fingerprint: str, *,
                            created_at: str) -> None:
        if self.db.one("SELECT id FROM evidence_policy_versions WHERE "
                       "version=?", version):
            return
        self.db.insert("evidence_policy_versions", {
            "id": __import__("uuid").uuid4().hex, "version": version,
            "fingerprint": fingerprint, "created_at": created_at})

    def save_legal_hold(self, hold: LegalHoldRecord) -> None:
        self.db.insert("evidence_legal_holds", {
            "id": hold.id, "tenant_id": hold.tenant_id,
            "evidence_id": hold.evidence_id, "reason": hold.reason,
            "placed_by": hold.placed_by,
            "released_at": hold.released_at.isoformat()
            if hold.released_at else None})
