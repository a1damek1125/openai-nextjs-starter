"""Relationship graph — tenant-scoped edges, case-first queries.

Every edge check starts with the tenant boundary; a cross-tenant link
raises instead of silently linking (property-tested).
"""
from __future__ import annotations

from typing import Optional

from .models import Party, RelationshipRole


class CrossTenantLinkError(Exception):
    pass


class RelationshipGraph:
    def __init__(self) -> None:
        self.parties: dict[str, Party] = {}
        self.edges: list[RelationshipRole] = []

    def add_party(self, party: Party) -> Party:
        self.parties[party.id] = party
        return party

    def _party(self, party_id: str, tenant_id: str) -> Party:
        p = self.parties.get(party_id)
        if p is None or p.tenant_id != tenant_id:
            raise CrossTenantLinkError(
                "party not found in this tenant")     # safe denial
        return p

    def link_parties(self, *, tenant_id: str, from_id: str, to_id: str,
                     role: str) -> RelationshipRole:
        """person→organization (member_of/employed_by), person→household…"""
        a = self._party(from_id, tenant_id)
        b = self._party(to_id, tenant_id)
        if a.tenant_id != b.tenant_id:
            raise CrossTenantLinkError("cross-tenant party link denied")
        edge = RelationshipRole(tenant_id=tenant_id, from_id=from_id,
                                to_id=to_id, to_kind="party", role=role)
        self.edges.append(edge)
        return edge

    def link(self, *, tenant_id: str, party_id: str, to_id: str,
             to_kind: str, role: str = "customer") -> RelationshipRole:
        """party → case/quote/appointment/evidence, tenant-scoped."""
        self._party(party_id, tenant_id)
        edge = RelationshipRole(tenant_id=tenant_id, from_id=party_id,
                                to_id=to_id, to_kind=to_kind, role=role)
        self.edges.append(edge)
        return edge

    # -- queries (always tenant-scoped) ------------------------------------------
    def edges_of(self, party_id: str, *, tenant_id: str,
                 to_kind: Optional[str] = None) -> list[RelationshipRole]:
        return [e for e in self.edges
                if e.tenant_id == tenant_id and e.from_id == party_id
                and (to_kind is None or e.to_kind == to_kind)]

    def cases_of(self, party_id: str, *, tenant_id: str) -> list[str]:
        return [e.to_id for e in self.edges_of(party_id,
                                               tenant_id=tenant_id,
                                               to_kind="case")]

    def parties_of_case(self, case_id: str, *,
                        tenant_id: str) -> list[tuple[Party, str]]:
        out = []
        for e in self.edges:
            if e.tenant_id == tenant_id and e.to_kind == "case" \
                    and e.to_id == case_id:
                p = self.parties.get(e.from_id)
                if p is not None and p.tenant_id == tenant_id:
                    out.append((p, e.role))
        return out

    def organization_of(self, person_id: str, *,
                        tenant_id: str) -> Optional[Party]:
        for e in self.edges_of(person_id, tenant_id=tenant_id,
                               to_kind="party"):
            target = self.parties.get(e.to_id)
            if target and target.kind == "organization":
                return target
        return None
