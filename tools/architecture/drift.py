"""Architecture Drift Observatory (SP0001 D-0001-10, §11.8).

Records longitudinal architecture snapshots and computes deltas. Drift metrics
are ADVISORY (P2) and never silently become an uncalibrated hard blocker
(INV-0001-14, D-0001-09). Hard rules stay separate in conformance.
"""
from __future__ import annotations

from typing import Any

METRIC_KEYS = [
    "capabilities", "capability_edges", "sccs", "cyclic_sccs", "unowned_nodes",
    "active_waivers", "routes", "tables", "migrations", "effect_observations",
    "p2_findings",
]


def snapshot_vector(conformance: dict, observed: dict,
                    active_waivers: int = 0) -> dict[str, Any]:
    m = conformance.get("metrics", {})
    counts = conformance.get("counts", {})
    findings = conformance.get("findings", [])
    return {
        "commit": observed.get("commit", "UNKNOWN"),
        "capabilities": m.get("capabilities", 0),
        "capability_edges": m.get("capability_edges", 0),
        "sccs": m.get("sccs", 0),
        "cyclic_sccs": m.get("cyclic_sccs", 0),
        "unowned_nodes": sum(1 for f in findings if f["kind"] == "UNOWNED_NODE"),
        "active_waivers": active_waivers,
        "routes": m.get("routes", 0),
        "tables": m.get("tables", 0),
        "migrations": m.get("migrations", 0),
        "effect_observations": m.get("effect_observations", 0),
        "p2_findings": counts.get("P2", 0),
    }


def delta(prev: dict, cur: dict) -> dict[str, Any]:
    out: dict[str, Any] = {"from": prev.get("commit"), "to": cur.get("commit"),
                           "changes": {}}
    for k in METRIC_KEYS:
        d = cur.get(k, 0) - prev.get(k, 0)
        if d != 0:
            out["changes"][k] = {"prev": prev.get(k, 0), "cur": cur.get(k, 0),
                                 "delta": d}
    return out


def ewma(series: list[float], alpha: float = 0.3) -> float:
    """Advisory smoothing for change detection AFTER enough data exists."""
    if not series:
        return 0.0
    acc = series[0]
    for x in series[1:]:
        acc = alpha * x + (1 - alpha) * acc
    return round(acc, 6)


def append_history(history: list[dict], vector: dict) -> list[dict]:
    """Append a snapshot, replacing any existing vector for the same commit."""
    out = [h for h in history if h.get("commit") != vector.get("commit")]
    out.append(vector)
    return out
