"""Customer memory — structured, sourced, confidence-carrying items.

Never raw LLM prose. AI suggestions stay AI_SUGGESTED until a human
verifies them; stale memory cannot drive critical decisions alone;
disputed memory blocks automation; sensitive memory needs permission.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .models import CustomerMemoryItem

STALE_AFTER_DAYS = 180


@dataclass
class MemoryDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)


class CustomerMemory:
    def __init__(self, audit=None) -> None:
        self.items: list[CustomerMemoryItem] = []
        self.audit = audit

    def add(self, item: CustomerMemoryItem) -> CustomerMemoryItem:
        # AI can only ever SUGGEST facts — verification is a human act.
        if item.source == "ai_worker" \
                and item.memory_type == "VERIFIED_FACT":
            item.memory_type = "AI_SUGGESTED"
        self.items.append(item)
        if self.audit is not None:
            self.audit.append(event_type="CRM_MEMORY_ADDED",
                              actor=item.source,
                              payload={"party_id": item.party_id,
                                       "memory_type": item.memory_type,
                                       "sensitive": item.sensitive})
        return item

    def verify(self, item: CustomerMemoryItem, *, verified_by: str,
               actor_kind: str = "human") -> CustomerMemoryItem:
        if actor_kind != "human":
            raise PermissionError(
                "only a human can verify memory into a fact")
        item.memory_type = "VERIFIED_FACT"
        item.verified_by = verified_by
        item.confidence = max(item.confidence, 0.9)
        if self.audit is not None:
            self.audit.append(event_type="CRM_MEMORY_VERIFIED",
                              actor=verified_by,
                              payload={"item_id": item.id})
        return item

    def dispute(self, item: CustomerMemoryItem, *, by: str) -> None:
        item.memory_type = "DISPUTED_FACT"
        if self.audit is not None:
            self.audit.append(event_type="CRM_MEMORY_DISPUTED", actor=by,
                              payload={"item_id": item.id})

    def usable_for_critical_decision(
            self, item: CustomerMemoryItem, *,
            actor_has_sensitive_permission: bool = False,
            now: Optional[datetime] = None) -> MemoryDecision:
        now = now or datetime.utcnow()
        reasons = []
        if item.memory_type == "DISPUTED_FACT":
            return MemoryDecision(False, ["disputed memory cannot drive "
                                          "automation"])
        if item.memory_type == "AI_SUGGESTED":
            return MemoryDecision(False, ["AI-suggested memory needs "
                                          "human verification first"])
        stale = item.memory_type == "STALE_FACT" or \
            now - item.recorded_at > timedelta(days=STALE_AFTER_DAYS)
        if stale:
            return MemoryDecision(False, ["stale memory cannot drive a "
                                          "critical decision alone — "
                                          "re-verify first"])
        if item.sensitive and not actor_has_sensitive_permission:
            return MemoryDecision(False, ["sensitive memory requires "
                                          "permission"])
        if item.memory_type != "VERIFIED_FACT" and item.confidence < 0.6:
            reasons.append("low-confidence unverified memory — "
                           "supporting signal only")
            return MemoryDecision(False, reasons)
        return MemoryDecision(True, ["usable"])

    def for_party(self, party_id: str, *,
                  tenant_id: str) -> list[CustomerMemoryItem]:
        return [i for i in self.items
                if i.party_id == party_id and i.tenant_id == tenant_id]
