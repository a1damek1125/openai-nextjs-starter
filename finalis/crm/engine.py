"""RelationshipEngine — graph + consent + promises + memory in one
case-first service. Consent is non-overrideable; every consent change is
a domain event.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .graph import RelationshipGraph
from .memory import CustomerMemory
from .models import (ConsentRecord, CustomerActivity, CustomerPreference,
                     CustomerPromise, Party)


@dataclass
class OutreachDecision:
    allowed: bool
    requires_review: bool = False
    reasons: list[str] = field(default_factory=list)


@dataclass
class ConsentPolicy:
    """Tenant policy knobs (conservative defaults)."""
    service_updates_on_unknown: bool = True    # transactional msgs OK
    marketing_on_unknown: bool = False         # marketing never implied


class RelationshipEngine:
    def __init__(self, audit=None,
                 policy: Optional[ConsentPolicy] = None) -> None:
        self.audit = audit
        self.policy = policy or ConsentPolicy()
        self.graph = RelationshipGraph()
        self.memory = CustomerMemory(audit)
        self.consents: list[ConsentRecord] = []
        self.promises: list[CustomerPromise] = []
        self.preferences: list[CustomerPreference] = []
        self.activities: list[CustomerActivity] = []

    # -- consent -----------------------------------------------------------------
    def record_consent(self, record: ConsentRecord) -> ConsentRecord:
        self.consents.append(record)
        if self.audit is not None:
            self.audit.append(event_type="CRM_CONSENT_CHANGED",
                              actor=record.recorded_by,
                              payload={"party_id": record.party_id,
                                       "channel": record.channel,
                                       "status": record.status,
                                       "source": record.source})
        return record

    def _latest_consent(self, party_id: str, channel: str, *,
                        tenant_id: str) -> Optional[ConsentRecord]:
        matches = [c for c in self.consents
                   if c.party_id == party_id and c.channel == channel
                   and c.tenant_id == tenant_id]
        return matches[-1] if matches else None

    def can_contact(self, party: Party, *, channel: str,
                    purpose: str = "service") -> OutreachDecision:
        """purpose: service | marketing | document_request."""
        consent = self._latest_consent(party.id, channel,
                                       tenant_id=party.tenant_id)
        status = consent.status if consent else "UNKNOWN"
        if status in ("DENIED", "REVOKED"):
            return OutreachDecision(
                False, reasons=[f"{channel} consent is {status} — "
                                "non-overrideable, no outreach"])
        # Marketing needs explicit MARKETING consent on top of channel.
        if purpose == "marketing":
            marketing = self._latest_consent(party.id, "MARKETING",
                                             tenant_id=party.tenant_id)
            mstatus = marketing.status if marketing else "UNKNOWN"
            if mstatus in ("DENIED", "REVOKED"):
                return OutreachDecision(
                    False, reasons=["marketing consent denied/revoked"])
            if mstatus == "UNKNOWN":
                if self.policy.marketing_on_unknown:
                    return OutreachDecision(True)
                return OutreachDecision(
                    False, requires_review=True,
                    reasons=["marketing without recorded consent needs "
                             "human review"])
        if status == "UNKNOWN" and purpose == "service" \
                and not self.policy.service_updates_on_unknown:
            return OutreachDecision(False, requires_review=True,
                                    reasons=["service outreach on unknown "
                                             "consent needs review under "
                                             "tenant policy"])
        return OutreachDecision(True, reasons=["consent permits outreach"])

    # -- promises & preferences --------------------------------------------------
    def record_promise(self, promise: CustomerPromise) -> CustomerPromise:
        if promise.promisor not in ("customer", "finalis"):
            raise ValueError("promisor must be customer or finalis")
        self.promises.append(promise)
        if self.audit is not None:
            self.audit.append(event_type="CRM_PROMISE_RECORDED",
                              actor=promise.promisor,
                              payload={"party_id": promise.party_id,
                                       "what": promise.what,
                                       "case_id": promise.case_id})
        return promise

    def open_promises(self, party_id: str, *,
                      tenant_id: str,
                      promisor: Optional[str] = None
                      ) -> list[CustomerPromise]:
        return [p for p in self.promises
                if p.party_id == party_id and p.tenant_id == tenant_id
                and p.status == "open"
                and (promisor is None or p.promisor == promisor)]

    def record_preference(self,
                          pref: CustomerPreference) -> CustomerPreference:
        self.preferences.append(pref)
        return pref

    def record_activity(self,
                        activity: CustomerActivity) -> CustomerActivity:
        self.activities.append(activity)
        return activity

    def timeline(self, party_id: str, *,
                 tenant_id: str) -> list[CustomerActivity]:
        return sorted((a for a in self.activities
                       if a.party_id == party_id
                       and a.tenant_id == tenant_id),
                      key=lambda a: a.occurred_at)
