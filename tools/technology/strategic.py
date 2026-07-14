"""Strategic-IP Boundary Map (SP0004 D-0004-61/62/63, §2).

Classifies every major technology domain as OWN / ADAPT / BUY / STANDARDIZE /
DEFER. Finalis OWNS strategic differentiation (employee logic, memory, learning
governance, skills, authority, outcomes, certified-reasoning integration) and
ADAPTS commodity infrastructure (database, telephony, cloud, object store,
tracing) — INV-0004-01/02. A DEFER requires reason + trigger + last responsible
decision point + safe default (D-0004-04).
"""
from __future__ import annotations

from .model import Finding, P1, STRATEGIC_CLASSES, INVALID_TDR

# domains Finalis should OWN unless a superseding decision says otherwise
OWN_DEFAULT = {"employee_logic", "memory_architecture", "learning_governance",
               "skills", "authority", "outcome_intelligence",
               "certified_reasoning_integration", "case_ownership",
               "governance", "evidence"}


def validate_boundaries(smap: dict) -> list[Finding]:
    out: list[Finding] = []
    for b in smap.get("boundaries", []):
        did = b.get("domain", "-")
        cls = b.get("strategic_class")
        if cls not in STRATEGIC_CLASSES:
            out.append(Finding(INVALID_TDR, P1, did,
                               f"invalid strategic_class {cls!r}", {}))
        if cls == "DEFER":
            # a deferred decision must be auditable (D-0004-04)
            for req in ("reason", "decision_trigger",
                        "last_responsible_moment", "safe_default"):
                if not b.get(req):
                    out.append(Finding(INVALID_TDR, P1, did,
                                       f"DEFER boundary missing {req}", {}))
        # a strategic-differentiation domain classified away from OWN needs a
        # rationale (never silently outsource the core)
        if did in OWN_DEFAULT and cls not in ("OWN",) and not b.get("rationale"):
            out.append(Finding(INVALID_TDR, P1, did,
                               f"strategic domain {did!r} classified {cls} "
                               "without rationale", {}))
    return out


def by_class(smap: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {c: [] for c in sorted(STRATEGIC_CLASSES)}
    for b in smap.get("boundaries", []):
        out.setdefault(b.get("strategic_class", "?"), []).append(
            b.get("domain", "?"))
    return {k: sorted(v) for k, v in out.items()}
