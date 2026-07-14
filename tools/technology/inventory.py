"""Canonical Technology Inventory (SP0004 §4.2/§10.1, D-0004-15).

Each technology dependency records identity, version, criticality (T0..T4),
strategic class (OWN/ADAPT/BUY/STANDARDIZE/DEFER), runtime scope, owner
capability, upstream dependencies, provider-specific leakage, and a decision ref.
Direct AND transitive dependencies are representable (AC-0004-007/008).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, TECH_STATUS, CRITICALITY, STRATEGIC_CLASSES,
                    RUNTIME_SCOPES, INVALID_TDR)


def tech_index(inv: dict) -> dict[str, dict]:
    return {t["technology_id"]: t for t in inv.get("technologies", [])}


def validate_inventory(inv: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for t in inv.get("technologies", []):
        tid = t.get("technology_id")
        if not tid:
            out.append(Finding(INVALID_TDR, P0, "-",
                               "technology missing technology_id", {}))
            continue
        if tid in seen:
            out.append(Finding(INVALID_TDR, P0, tid,
                               "duplicate technology_id", {}))
        seen.add(tid)
        if t.get("status") not in TECH_STATUS:
            out.append(Finding(INVALID_TDR, P1, tid,
                               f"invalid status {t.get('status')!r}", {}))
        if t.get("criticality") not in CRITICALITY:
            out.append(Finding(INVALID_TDR, P1, tid,
                               f"invalid criticality {t.get('criticality')!r}",
                               {}))
        if t.get("strategic_class") not in STRATEGIC_CLASSES:
            out.append(Finding(INVALID_TDR, P1, tid,
                               f"invalid strategic_class "
                               f"{t.get('strategic_class')!r}", {}))
        rs = t.get("runtime_scope")
        if rs is not None and rs not in RUNTIME_SCOPES:
            out.append(Finding(INVALID_TDR, P1, tid,
                               f"invalid runtime_scope {rs!r}", {}))
    return out


def direct(inv: dict) -> list[dict]:
    return [t for t in inv.get("technologies", [])
            if t.get("direct_or_transitive") == "DIRECT"]


def transitive(inv: dict) -> list[dict]:
    return [t for t in inv.get("technologies", [])
            if t.get("direct_or_transitive") == "TRANSITIVE"]


def critical(inv: dict) -> list[dict]:
    return [t for t in inv.get("technologies", [])
            if t.get("criticality") in ("T3", "T4")]


def provider_leakage(inv: dict) -> list[dict]:
    """Technologies that report provider-specific leakage (advisory surface)."""
    return [t for t in inv.get("technologies", [])
            if t.get("provider_specific_leakage")]


def inventory_stats(inv: dict) -> dict:
    techs = inv.get("technologies", [])
    return {"total": len(techs),
            "direct": len(direct(inv)),
            "transitive": len(transitive(inv)),
            "critical_t3_t4": len(critical(inv)),
            "with_leakage": len(provider_leakage(inv))}
