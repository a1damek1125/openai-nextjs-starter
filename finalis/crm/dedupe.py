"""Deterministic duplicate detection + explicit merge decisions.

No silent merges: scoring only nominates candidates; merging requires a
human MergeDecision, never crosses tenants, and never proceeds over
conflicting verified facts.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Optional

from .models import CustomerFact, MergeCandidate, MergeDecision, Party

DUPLICATE_VERDICTS = {"NOT_DUPLICATE", "POSSIBLE_DUPLICATE",
                      "LIKELY_DUPLICATE", "MERGE_REQUIRES_REVIEW",
                      "DO_NOT_MERGE"}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _norm_name(name: str) -> str:
    return " ".join(name.lower().split())


def duplicate_candidate(a: Party, b: Party, *,
                        facts_a: Optional[list[CustomerFact]] = None,
                        facts_b: Optional[list[CustomerFact]] = None,
                        shared_case_history: bool = False,
                        same_external_crm_id: bool = False
                        ) -> MergeCandidate:
    signals: list[str] = []
    # Tenant boundary first — no score can cross it.
    if a.tenant_id != b.tenant_id:
        return MergeCandidate(tenant_id=a.tenant_id, party_a_id=a.id,
                              party_b_id=b.id, score=0.0,
                              verdict="DO_NOT_MERGE",
                              signals=["cross-tenant — never merged"])
    score = 0.0
    email_a, email_b = a.contact("EMAIL"), b.contact("EMAIL")
    if email_a and email_a == email_b:
        score += 0.45
        signals.append("same email")
    for kind in ("PHONE", "MOBILE", "WHATSAPP"):
        pa, pb = a.contact(kind), b.contact(kind)
        if pa and pa == pb:
            score += 0.35
            signals.append("same phone")
            break
    name_sim = SequenceMatcher(None, _norm_name(a.display_name),
                               _norm_name(b.display_name)).ratio()
    if name_sim > 0.85:
        score += 0.20 * name_sim
        signals.append(f"name similarity {name_sim:.2f}")
    if a.organization and b.organization \
            and a.organization.domain \
            and a.organization.domain == b.organization.domain:
        score += 0.15
        signals.append("same company domain")
    if a.addresses and b.addresses and \
            a.addresses[0] == b.addresses[0]:
        score += 0.10
        signals.append("same address")
    if same_external_crm_id:
        score += 0.50           # raises confidence, never bypasses tenant
        signals.append("same external CRM id")
    if shared_case_history:
        score += 0.10
        signals.append("shared case history")
    score = _clamp(score)

    # Conflicting VERIFIED facts block auto-merge regardless of score.
    conflict = False
    by_key = {f.key: f for f in (facts_a or []) if f.verified}
    for f in (facts_b or []):
        if f.verified and f.key in by_key \
                and by_key[f.key].value != f.value:
            conflict = True
            signals.append(f"conflicting verified fact: {f.key}")
    if conflict:
        verdict = "MERGE_REQUIRES_REVIEW"
    elif score >= 0.8:
        verdict = "LIKELY_DUPLICATE"
    elif score >= 0.4:
        verdict = "POSSIBLE_DUPLICATE"
    else:
        verdict = "NOT_DUPLICATE"
    return MergeCandidate(tenant_id=a.tenant_id, party_a_id=a.id,
                          party_b_id=b.id, score=round(score, 4),
                          verdict=verdict, signals=signals)


def merge_parties(candidate: MergeCandidate, *, surviving: Party,
                  merged: Party, decided_by: str,
                  actor_kind: str = "human", reason: str = "",
                  audit=None) -> MergeDecision:
    """Explicit, human, audited — the only way two parties become one.
    History is preserved: the merged party is tombstoned, not deleted."""
    if actor_kind != "human":
        raise PermissionError("merges require a human decision")
    if candidate.verdict == "DO_NOT_MERGE":
        raise PermissionError("candidate is marked DO_NOT_MERGE")
    if surviving.tenant_id != merged.tenant_id:
        raise PermissionError("cross-tenant merge is never allowed")
    if candidate.verdict == "MERGE_REQUIRES_REVIEW" and not reason:
        raise PermissionError("conflicting verified facts: a written "
                              "reason is required to merge")
    merged.merged_into_id = surviving.id       # tombstone, keeps history
    decision = MergeDecision(tenant_id=surviving.tenant_id,
                             surviving_party_id=surviving.id,
                             merged_party_ids=[merged.id],
                             decided_by=decided_by, reason=reason)
    if audit is not None:
        audit.append(event_type="CRM_PARTIES_MERGED", actor=decided_by,
                     payload={"surviving": surviving.id,
                              "merged": [merged.id], "reason": reason,
                              "signals": candidate.signals})
    return decision
