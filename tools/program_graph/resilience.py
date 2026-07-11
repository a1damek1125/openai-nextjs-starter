"""Program Dominators + Milestone Cut-Set / Resilience (SP0003 D-0003-29/30/31,
§11.14/§11.15).

Dominators find unavoidable INDIVIDUAL nodes (single points of program failure).
Cut-set analysis finds minimum SETS of alternative blockers. Both respect the
AND/OR/threshold hypergraph semantics (hyperreach) rather than naive pairwise
reachability, so a JOINT prerequisite is not silently treated as OR-reachable.
They operate ONLY on a well-defined COMPILED scenario graph; if a scenario fails
to compile the honest answer is CUT_ANALYSIS_REQUIRES_SCENARIO (D-0003-30,
AC-0003-60). The resilience index is DESCRIPTIVE, never a production gate
(D-0003-31).
"""
from __future__ import annotations

from .scenario import compile_scenario
from .hyperreach import hyper_dominators, hyper_min_cut, is_achievable


def program_dominators(program: dict, target: str,
                       scenario_id: str = "BASELINE") -> dict:
    active, findings = compile_scenario(program, scenario_id)
    if any(f.severity == "P0" for f in findings):
        return {"error": "SCENARIO_COMPILATION_ERROR",
                "findings": [f.to_dict() for f in findings]}
    known = {n["node_id"] for n in program.get("nodes", [])}
    if target not in known:
        return {"error": "UNKNOWN_NODE", "target": target}
    doms = hyper_dominators(program, target, active)
    return {"target": target, "scenario": scenario_id,
            "achievable": is_achievable(program, target, active=active),
            "dominators": doms, "single_point_count": len(doms)}


def milestone_cut_set(program: dict, target: str,
                      scenario_id: str = "BASELINE", *, max_size: int = 3) -> dict:
    active, findings = compile_scenario(program, scenario_id)
    if any(f.severity == "P0" for f in findings):
        return {"error": "CUT_ANALYSIS_REQUIRES_SCENARIO",
                "message": "scenario did not compile; cut-set needs a "
                           "well-defined compiled graph",
                "findings": [f.to_dict() for f in findings]}
    known = {n["node_id"] for n in program.get("nodes", [])}
    if target not in known:
        return {"error": "UNKNOWN_NODE", "target": target}
    res = hyper_min_cut(program, target, max_size=max_size, active=active)
    res.update({"target": target, "scenario": scenario_id,
                "resilience_index": res.get("min_cut_size")})
    return res
