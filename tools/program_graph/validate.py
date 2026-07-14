"""Top-level program validation (SP0003 §12.4, D-0003-09).

ValidScenarioProgram  <=>  HardGraphIsAcyclic
                          AND HardGatesValid
                          AND NoUnprovenActiveHardDependency

Combines registry/schema, gate, conflict, rework, risk, evidence and temporal
validation with the compiled-scenario hard-backbone acyclicity check. A partial
update can never be declared valid (INV-0003-19): the Report is valid only when
zero P0 and zero P1 remain.
"""
from __future__ import annotations

from .model import Finding, Report, P0, HARD_DEPENDENCY_CYCLE
from .registry import validate_registry
from .gates import validate_gates, detect_gate_bypass, validate_gate_bindings
from .conflict import validate_conflicts
from .rework import validate_rework, rework_cluster_findings
from .risk import validate_risk
from .evidence import validate_completion_evidence
from .temporal import check_temporal_consistency
from .scenario import compile_scenario
from .graphalgo import (precedence_pairs, mandatory_precedence_pairs, node_ids,
                        detect_cycle)


def validate_program(program: dict, scenario_id: str = "BASELINE",
                     *, include_rework_advisory: bool = True) -> Report:
    rep = Report()
    # canonical schema + evidence invariants
    reg = validate_registry(program)
    rep.extend(reg.findings)
    rep.extend(validate_gates(program))
    rep.extend(validate_gate_bindings(program))
    rep.extend(validate_conflicts(program))
    rep.extend(validate_rework(program))
    rep.extend(validate_risk(program))
    rep.extend(validate_completion_evidence(program))
    rep.extend(check_temporal_consistency(program))

    # scenario compilation (deterministic)
    active, sfindings = compile_scenario(program, scenario_id)
    rep.extend(sfindings)
    rep.extend(detect_gate_bypass(program, active))

    # hard execution backbone must be acyclic (D-0003-09). Only MANDATORY
    # (ALL_OF) prerequisites can form a hard cycle; ANY_OF/threshold tails are a
    # choice and must not raise a phantom cycle (red-team SWARM-L P2).
    mpairs = mandatory_precedence_pairs(program, active)
    cyc = detect_cycle(node_ids(program), mpairs)
    if cyc:
        rep.add(Finding(HARD_DEPENDENCY_CYCLE, P0, ",".join(cyc),
                        "active MANDATORY (ALL_OF) execution backbone contains a "
                        f"cycle under scenario {scenario_id!r}", {"cycle": cyc}))
    pairs = precedence_pairs(program, active)

    # rework feedback clusters are advisory (P1 informational, never blocking a
    # valid program by themselves — they are legal). Keep them OUT of the hard
    # validity signal by classifying them advisory-only.
    if include_rework_advisory:
        rep.metrics["rework_clusters"] = [
            f.detail.get("cluster") for f in rework_cluster_findings(program)]

    rep.metrics.update({
        "scenario": scenario_id,
        "node_count": len(program.get("nodes", [])),
        "hyperedge_count": len(program.get("hyperedges", [])),
        "active_precedence_edges": len(pairs),
        "hard_backbone_acyclic": not cyc,
    })
    return rep
