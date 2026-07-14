"""Relationship Core persistence (migration v6) — write-through store +
startup hydration. Every read is tenant-scoped; merges tombstone, never
delete.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from typing import Optional

from ..crm.engine import RelationshipEngine
from ..crm.models import (Address, ConsentRecord, ContactPoint,
                          CustomerMemoryItem, CustomerPromise,
                          ExternalCrmReference, ExternalSyncEvent,
                          HouseholdProfile, MergeDecision,
                          OrganizationProfile, Party, PersonProfile,
                          RelationshipRole)
from .db import Database, utcnow


def _dt(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


class CrmStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    # -- parties -------------------------------------------------------------------
    def save_party(self, p: Party) -> None:
        row = {
            "id": p.id, "tenant_id": p.tenant_id, "kind": p.kind,
            "display_name": p.display_name,
            "roles_json": json.dumps(sorted(p.roles)),
            "person_json": json.dumps(dataclasses.asdict(p.person))
            if p.person else None,
            "organization_json": json.dumps(
                dataclasses.asdict(p.organization))
            if p.organization else None,
            "household_json": json.dumps(dataclasses.asdict(p.household))
            if p.household else None,
            "addresses_json": json.dumps(
                [dataclasses.asdict(a) for a in p.addresses]),
            "merged_into_id": p.merged_into_id,
            "updated_at": utcnow(),
        }
        if self.db.one("SELECT id FROM crm_parties WHERE id=?", p.id):
            self.db.update("crm_parties", p.id, row)
        else:
            self.db.insert("crm_parties", row)
        self.db.conn.execute(
            "DELETE FROM crm_contact_points WHERE party_id=?", (p.id,))
        self.db.conn.commit()
        for cp in p.contact_points:
            self.db.insert("crm_contact_points", {
                "id": cp.id, "tenant_id": p.tenant_id, "party_id": p.id,
                "kind": cp.kind, "value": cp.value, "label": cp.label,
                "verified": int(cp.verified),
                "preferred": int(cp.preferred)})

    def load_party(self, party_id: str, *,
                   tenant_id: str) -> Optional[Party]:
        r = self.db.one("SELECT * FROM crm_parties WHERE id=? AND "
                        "tenant_id=?", party_id, tenant_id)
        if r is None:
            return None
        p = Party(
            tenant_id=r["tenant_id"], kind=r["kind"],
            display_name=r["display_name"],
            person=PersonProfile(**json.loads(r["person_json"]))
            if r["person_json"] else None,
            organization=OrganizationProfile(
                **json.loads(r["organization_json"]))
            if r["organization_json"] else None,
            household=HouseholdProfile(**json.loads(r["household_json"]))
            if r["household_json"] else None,
            roles=set(json.loads(r["roles_json"])),
            addresses=[Address(**a)
                       for a in json.loads(r["addresses_json"])],
            merged_into_id=r["merged_into_id"], id=r["id"])
        p.contact_points = [
            ContactPoint(kind=c["kind"], value=c["value"],
                         label=c["label"], verified=bool(c["verified"]),
                         preferred=bool(c["preferred"]), id=c["id"])
            for c in self.db.all(
                "SELECT * FROM crm_contact_points WHERE party_id=?",
                party_id)]
        return p

    def list_parties(self, *, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT id, kind, display_name, roles_json, merged_into_id "
            "FROM crm_parties WHERE tenant_id=? ORDER BY created_at",
            tenant_id)]

    # -- edges / consents / promises / memory ----------------------------------
    def save_edge(self, e: RelationshipRole) -> None:
        self.db.insert("crm_relationship_edges", {
            "id": e.id, "tenant_id": e.tenant_id, "from_id": e.from_id,
            "to_id": e.to_id, "to_kind": e.to_kind, "role": e.role,
            "created_at": e.created_at.isoformat()})

    def save_consent(self, c: ConsentRecord) -> None:
        self.db.insert("crm_consent_records", {
            "id": c.id, "tenant_id": c.tenant_id, "party_id": c.party_id,
            "channel": c.channel, "status": c.status, "source": c.source,
            "recorded_by": c.recorded_by,
            "recorded_at": c.recorded_at.isoformat()})

    def save_promise(self, p: CustomerPromise) -> None:
        self.db.insert("crm_promises", {
            "id": p.id, "tenant_id": p.tenant_id, "party_id": p.party_id,
            "promisor": p.promisor, "what": p.what,
            "due_at": p.due_at.isoformat() if p.due_at else None,
            "status": p.status, "case_id": p.case_id})

    def save_memory(self, m: CustomerMemoryItem) -> None:
        row = {
            "id": m.id, "tenant_id": m.tenant_id, "party_id": m.party_id,
            "memory_type": m.memory_type,
            "content_json": json.dumps(m.content, default=str),
            "source": m.source, "confidence": m.confidence,
            "scope": m.scope, "sensitive": int(m.sensitive),
            "recorded_at": m.recorded_at.isoformat(),
            "verified_by": m.verified_by}
        if self.db.one("SELECT id FROM crm_memory_items WHERE id=?", m.id):
            self.db.update("crm_memory_items", m.id, row)
        else:
            self.db.insert("crm_memory_items", row)

    def save_merge_decision(self, d: MergeDecision) -> None:
        self.db.insert("crm_merge_decisions", {
            "id": d.id, "tenant_id": d.tenant_id,
            "surviving_party_id": d.surviving_party_id,
            "merged_party_ids_json": json.dumps(d.merged_party_ids),
            "decided_by": d.decided_by, "reason": d.reason,
            "decided_at": d.decided_at.isoformat()})

    def save_external_ref(self, ref: ExternalCrmReference) -> None:
        self.db.insert("crm_external_references", {
            "id": ref.id, "tenant_id": ref.tenant_id,
            "party_id": ref.party_id, "provider": ref.provider,
            "object_kind": ref.object_kind,
            "external_id": ref.external_id})

    def external_refs(self, party_id: str, *,
                      tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM crm_external_references WHERE party_id=? AND "
            "tenant_id=?", party_id, tenant_id)]

    def save_sync_event(self, e: ExternalSyncEvent) -> None:
        self.db.insert("crm_external_sync_events", {
            "id": e.id, "tenant_id": e.tenant_id, "provider": e.provider,
            "direction": e.direction, "object_kind": e.object_kind,
            "decision": e.decision,
            "detail_json": json.dumps(e.detail, default=str),
            "idempotency_key": e.idempotency_key,
            "created_at": e.created_at.isoformat()})

    def sync_events(self, *, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM crm_external_sync_events WHERE tenant_id=?",
            tenant_id)]

    # -- hydration ------------------------------------------------------------------
    def hydrate(self, engine: RelationshipEngine) -> int:
        """Rebuild the engine's in-memory state from the DB at startup."""
        count = 0
        for r in self.db.all("SELECT id, tenant_id FROM crm_parties"):
            p = self.load_party(r["id"], tenant_id=r["tenant_id"])
            if p is not None:
                engine.graph.add_party(p)
                count += 1
        for r in self.db.all("SELECT * FROM crm_relationship_edges"):
            engine.graph.edges.append(RelationshipRole(
                tenant_id=r["tenant_id"], from_id=r["from_id"],
                to_id=r["to_id"], to_kind=r["to_kind"], role=r["role"],
                created_at=_dt(r["created_at"]), id=r["id"]))
        for r in self.db.all("SELECT * FROM crm_consent_records "
                             "ORDER BY recorded_at"):
            engine.consents.append(ConsentRecord(
                tenant_id=r["tenant_id"], party_id=r["party_id"],
                channel=r["channel"], status=r["status"],
                source=r["source"], recorded_by=r["recorded_by"],
                recorded_at=_dt(r["recorded_at"]), id=r["id"]))
        for r in self.db.all("SELECT * FROM crm_promises"):
            engine.promises.append(CustomerPromise(
                tenant_id=r["tenant_id"], party_id=r["party_id"],
                promisor=r["promisor"], what=r["what"],
                due_at=_dt(r["due_at"]), status=r["status"],
                case_id=r["case_id"], id=r["id"]))
        for r in self.db.all("SELECT * FROM crm_memory_items"):
            engine.memory.items.append(CustomerMemoryItem(
                tenant_id=r["tenant_id"], party_id=r["party_id"],
                memory_type=r["memory_type"],
                content=json.loads(r["content_json"]),
                source=r["source"], confidence=r["confidence"],
                scope=r["scope"], sensitive=bool(r["sensitive"]),
                recorded_at=_dt(r["recorded_at"]),
                verified_by=r["verified_by"], id=r["id"]))
        return count
