"""Active discovery / Value-of-Information probe planning (SP0008 §probes,
D-0008-36/37).

When the inventory has unknowns (UNKNOWN effect reachability, UNKNOWN consumers,
unresolved hard criticality flags, ambiguous identity), it does not stop — it
PLANS the next probe that would most reduce uncertainty. Each probe is ranked by
a Value-of-Information score: how many unknowns it would resolve, weighted by the
criticality of the affected surfaces. This is a PLAN, not an action: the inventory
never executes anything against the running product (INV-0008-52). The plan is a
deterministic, ranked worklist a human or a future tool can act on.
"""
from __future__ import annotations

from typing import Iterable

# probe kinds and the unknown they target
PROBE_KINDS = {
    "STATIC_TRACE": "resolve UNKNOWN effect reachability by tracing a handler",
    "CONSUMER_SEARCH": "resolve UNKNOWN/dark consumers by a targeted search",
    "CRITICALITY_REVIEW": "resolve an unresolved hard criticality flag",
    "IDENTITY_ADJUDICATION": "resolve an AMBIGUOUS/DUPLICATE identity",
    "WITNESS_ELICITATION": "obtain a grounded behavioral witness",
}

# how much each hard-criticality context multiplies a probe's value
_CRIT_WEIGHT = {"CRITICAL": 3.0, "ELEVATED": 2.0, "STANDARD": 1.0,
                "UNKNOWN": 1.5}


def plan_probes(unknowns: Iterable[dict]) -> list[dict]:
    """Rank probes by Value-of-Information.

    Each unknown is {surface_id, probe_kind, unknown, criticality}. The VoI score
    is the criticality weight (a probe on a critical surface is worth more). Ties
    break deterministically by (−score, probe_kind, surface_id).
    """
    probes = []
    for u in unknowns:
        kind = u.get("probe_kind")
        if kind not in PROBE_KINDS:
            continue
        weight = _CRIT_WEIGHT.get(u.get("criticality", "UNKNOWN"), 1.0)
        probes.append({
            "surface_id": u.get("surface_id"),
            "probe_kind": kind,
            "targets_unknown": u.get("unknown"),
            "criticality": u.get("criticality", "UNKNOWN"),
            "voi_score": round(weight, 3),
            "rationale": PROBE_KINDS[kind],
            "executes_against_product": False,
        })
    probes.sort(key=lambda p: (-p["voi_score"], p["probe_kind"],
                               p["surface_id"] or ""))
    for i, p in enumerate(probes):
        p["rank"] = i + 1
    return probes


def collect_unknowns(reach: dict, consumers: dict, crit: dict,
                     surfaces) -> list[dict]:
    """Assemble the unknowns worklist from the analysis outputs."""
    verdict = {s.surface_id: crit.get(s.surface_id, {}).get("verdict", "UNKNOWN")
               for s in surfaces}
    kind = {s.surface_id: s.surface_kind for s in surfaces}
    out: list[dict] = []
    for sid, info in reach.items():
        if kind.get(sid) == "HTTP_ROUTE" and info.get("exactness") == "UNKNOWN":
            out.append({"surface_id": sid, "probe_kind": "STATIC_TRACE",
                        "unknown": "effect_reachability",
                        "criticality": verdict.get(sid, "UNKNOWN")})
    for sid, rec in consumers.items():
        if rec.get("certainty") == "UNKNOWN":
            out.append({"surface_id": sid, "probe_kind": "CONSUMER_SEARCH",
                        "unknown": "consumer_set",
                        "criticality": verdict.get(sid, "UNKNOWN")})
    for sid, rec in crit.items():
        if rec.get("verdict") == "ELEVATED":
            out.append({"surface_id": sid, "probe_kind": "CRITICALITY_REVIEW",
                        "unknown": "hard_criticality_flag",
                        "criticality": "ELEVATED"})
    for s in surfaces:
        if s.identity_outcome in ("AMBIGUOUS_IDENTITY", "DUPLICATE_CANDIDATE"):
            out.append({"surface_id": s.surface_id,
                        "probe_kind": "IDENTITY_ADJUDICATION",
                        "unknown": "identity",
                        "criticality": verdict.get(s.surface_id, "UNKNOWN")})
    return out
