"""Semantic Drift Observatory (SP0002 D-0002-25, §19).

Longitudinal advisory metrics over registry snapshots. Hard invariants stay
Boolean (INV-0002-04); drift metrics never silently become an uncalibrated hard
blocker (advisory until explicitly promoted, AC-0002-74).
"""
from __future__ import annotations

from typing import Any

METRIC_KEYS = ["concepts", "active_revisions", "aliases", "forbidden_aliases",
               "ambiguities", "quarantine_count", "epistemic_violations",
               "unmapped_projections", "translation_conflicts",
               "lggt_conflicts", "breaking_changes", "p2_findings"]


def snapshot_vector(registry: dict, conformance: dict, *,
                    epoch_id: str | None = None,
                    quarantine_count: int = 0,
                    breaking_changes: int = 0) -> dict[str, Any]:
    concepts = registry.get("concepts", [])
    findings = conformance.get("findings", [])

    def n(kind):
        return sum(1 for f in findings if f["kind"] == kind)

    return {
        "semantic_epoch_id": epoch_id,
        "concepts": len(concepts),
        "active_revisions": sum(1 for c in concepts if c.get("status") == "ACTIVE"),
        "aliases": sum(len(c.get("aliases", [])) for c in concepts),
        "forbidden_aliases": sum(len(c.get("forbidden_aliases", [])) for c in concepts),
        "ambiguities": n("AMBIGUOUS_CONCEPT"),
        "quarantine_count": quarantine_count,
        "epistemic_violations": n("INVALID_EPISTEMIC_TRANSITION") + n("LLM_CONCEPT_ADMISSION"),
        "unmapped_projections": n("UNMAPPED_PROJECTION"),
        "translation_conflicts": n("TRANSLATION_SEMANTIC_CONFLICT"),
        "lggt_conflicts": n("LGGT_MAPPING_COLLISION"),
        "breaking_changes": breaking_changes,
        "p2_findings": conformance.get("counts", {}).get("P2", 0),
    }


def delta(prev: dict, cur: dict) -> dict[str, Any]:
    out = {"changes": {}}
    for k in METRIC_KEYS:
        d = cur.get(k, 0) - prev.get(k, 0)
        if d != 0:
            out["changes"][k] = {"prev": prev.get(k, 0), "cur": cur.get(k, 0),
                                 "delta": d}
    return out
