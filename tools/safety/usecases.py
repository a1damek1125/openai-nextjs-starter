"""High-Impact Use-Case Taxonomy (SP0005 §10, D-0005-51/52, INV-0005-17).

Internal FINALIS_IMPACT_0..5 classes are DISTINCT from legal high-risk
classification (INV-0005-17): FINALIS_IMPACT_5 must NEVER auto-map to
EU_AI_ACT_HIGH_RISK (D-0005-51, AC-0005-122). Classification is by capability +
purpose + authority + affected subject + actual use, not industry (D-0005-52).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, IMPACT_CLASSES, INVALID_SAFETY_SCHEMA)


def validate_usecases(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for u in reg.get("use_cases", []):
        uid = u.get("use_case_id")
        if uid in seen:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, uid,
                               "duplicate use_case_id", {}))
        seen.add(uid)
        if u.get("finalis_impact_class") not in IMPACT_CLASSES:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, uid or "-",
                               f"invalid impact class "
                               f"{u.get('finalis_impact_class')!r}", {}))
        # an internal class that hard-codes a legal classification is forbidden
        if u.get("legal_classification") and \
                u.get("legal_classification_source") == "AUTO_FROM_IMPACT":
            out.append(Finding(INVALID_SAFETY_SCHEMA, P0, uid or "-",
                               "legal classification auto-derived from internal "
                               "impact class (INV-0005-17, AC-0005-122)", {}))
        # capability/purpose/subject required (use-case-specific, not industry)
        for k in ("capability", "purpose", "affected_subject"):
            if not u.get(k):
                out.append(Finding(INVALID_SAFETY_SCHEMA, P1, uid or "-",
                                   f"use case missing {k} (D-0005-52)", {}))
    return out
