"""Control Barrier Graph + Control Independence + Common-Mode + Minimal Cut Sets
(SP0005 D-0005-34..39, §11.11, INV-0005-12/13).

Controls are typed (PREVENTIVE / DETECTIVE / CONTAINMENT / RECOVERY /
VERIFICATION) and their status distinguishes DECLARED from EFFECTIVE
(INV-0005-13). Two controls sharing a failure domain (same model, provider,
prompt, policy engine, data, human or code path) are NOT automatically independent
(INV-0005-12); independence must be established, else
INDEPENDENCE_NOT_ESTABLISHED / UNKNOWN — never assumed (D-0005-38, no naive
probability multiplication). Minimal cut sets are enumerated structurally on
bounded graphs; the search is bounded and reports its limit honestly (D-0005-39,
AC-0005-084).
"""
from __future__ import annotations

from itertools import combinations

from .model import (Finding, P1, P2, CONTROL_TYPES, CONTROL_STATUS,
                    EFFECTIVE_STATUS, SHARED_FAILURE_DOMAINS,
                    INVALID_SAFETY_SCHEMA, CONTROL_INDEPENDENCE_NOT_ESTABLISHED)


def control_index(reg: dict) -> dict[str, dict]:
    return {c["control_id"]: c for c in reg.get("controls", [])}


def validate_controls(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    hazards = {h["hazard_id"] for h in reg.get("hazards", [])}
    seen: set[str] = set()
    for c in reg.get("controls", []):
        cid = c.get("control_id")
        if cid in seen:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, cid,
                               "duplicate control_id", {}))
        seen.add(cid)
        if c.get("control_type") not in CONTROL_TYPES:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, cid or "-",
                               f"invalid control_type {c.get('control_type')!r}",
                               {}))
        if c.get("status") not in CONTROL_STATUS:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, cid or "-",
                               f"invalid control status {c.get('status')!r}", {}))
        for hz in c.get("hazard_refs", []):
            if hz not in hazards:
                out.append(Finding(INVALID_SAFETY_SCHEMA, P1, cid or "-",
                                   f"control references unknown hazard {hz!r}", {}))
    return out


def failure_domains(control: dict) -> dict:
    """The failure-domain attributes a control depends on; missing = UNKNOWN."""
    fd = control.get("failure_domains", {})
    return {k: fd.get(k, "UNKNOWN") for k in SHARED_FAILURE_DOMAINS}


def shared_failure_domains(a: dict, b: dict) -> list[str]:
    """Domains where BOTH controls depend on the SAME actual resource. "NONE"
    (control positively does not use that domain) is not a shared failure point,
    and UNKNOWN is not a proven share."""
    fa, fb = failure_domains(a), failure_domains(b)
    return sorted(k for k in SHARED_FAILURE_DOMAINS
                  if fa[k] not in ("UNKNOWN", "NONE") and fa[k] == fb[k])


def classify_independence(a: dict, b: dict) -> dict:
    """INDEPENDENCE_ESTABLISHED / PARTIALLY_INDEPENDENT /
    INDEPENDENCE_NOT_ESTABLISHED / UNKNOWN for two controls (D-0005-37). A domain
    a control positively declares NONE is neither shared nor unknown."""
    shared = shared_failure_domains(a, b)
    fa, fb = failure_domains(a), failure_domains(b)
    unknown = [k for k in SHARED_FAILURE_DOMAINS
               if fa[k] == "UNKNOWN" or fb[k] == "UNKNOWN"]
    if shared:
        cls = "INDEPENDENCE_NOT_ESTABLISHED"
    elif unknown:
        cls = "UNKNOWN"          # cannot prove independence -> not established
    else:
        cls = "INDEPENDENCE_ESTABLISHED"
    return {"control_a": a.get("control_id"), "control_b": b.get("control_id"),
            "classification": cls, "shared_failure_domains": shared,
            "unknown_dimensions": unknown}


def independence_findings(reg: dict) -> list[Finding]:
    """A hazard whose 'independent barriers' actually share a failure domain is a
    finding (INV-0005-12). Controls declared as an independence pair are checked."""
    out: list[Finding] = []
    idx = control_index(reg)
    for pair in reg.get("independence_claims", []):
        a, b = idx.get(pair.get("control_a")), idx.get(pair.get("control_b"))
        if not a or not b:
            continue
        d = classify_independence(a, b)
        if d["classification"] in ("INDEPENDENCE_NOT_ESTABLISHED", "UNKNOWN"):
            out.append(Finding(CONTROL_INDEPENDENCE_NOT_ESTABLISHED, P1,
                               f"{a['control_id']}|{b['control_id']}",
                               f"controls claimed independent are {d['classification']} "
                               f"(shared={d['shared_failure_domains']}, "
                               f"unknown={d['unknown_dimensions']})", d))
    return out


def effective_controls_for(reg: dict, hazard_id: str) -> list[str]:
    """Controls that are EFFECTIVE (evidenced) for a hazard — a declared-only
    control is not a real barrier (INV-0005-13)."""
    return sorted(c["control_id"] for c in reg.get("controls", [])
                  if hazard_id in c.get("hazard_refs", [])
                  and c.get("status") in EFFECTIVE_STATUS)


def minimal_cut_sets(reg: dict, hazard_id: str, *, max_size: int = 3) -> dict:
    """Minimal sets of barrier failures sufficient to expose a hazard, over the
    EFFECTIVE controls that guard it. Bounded search; reports the limit honestly
    (D-0005-39/AC-0005-084). A control set is a cut iff removing it leaves the
    hazard with no effective control on some required path — here modeled as: the
    hazard is exposed when every effective control guarding it has failed (AND of
    barriers), so the single minimal cut is the full effective-control set unless
    controls are grouped by 'barrier_path'."""
    controls = [c for c in reg.get("controls", [])
                if hazard_id in c.get("hazard_refs", [])
                and c.get("status") in EFFECTIVE_STATUS]
    if not controls:
        return {"hazard_id": hazard_id, "min_cut_size": 0, "example_cut": [],
                "note": "no effective control — hazard already exposed"}
    # group controls by independent barrier path; a cut must break every path
    paths: dict[str, list[str]] = {}
    for c in controls:
        paths.setdefault(c.get("barrier_path", c["control_id"]),
                         []).append(c["control_id"])
    # minimal cut = one control from each independent path (pick the smallest)
    if len(paths) > 12:
        return {"hazard_id": hazard_id, "min_cut_size": len(paths),
                "example_cut": [], "note": "ANALYSIS_LIMIT_REACHED",
                "paths": len(paths)}
    # smallest set that hits every path: one per path
    example = sorted(min(members) for members in paths.values())
    size = len(paths)
    bounded = size <= max_size
    return {"hazard_id": hazard_id, "min_cut_size": size,
            "example_cut": example if bounded else [],
            "independent_paths": size,
            "note": None if bounded else f"exact cut > {max_size}"}
