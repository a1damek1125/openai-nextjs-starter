"""Top-level technology-model validation (SP0004 §15/§18).

Combines inventory, strategic-IP, dependency-graph, TDR, evidence, provider
contract, exit-readiness, protocol, supply-chain and fitness validation. A hard
finding (P0/P1) can never be offset by a score (§12.6); the Report is valid only
when zero P0 and zero P1 remain.
"""
from __future__ import annotations

from .model import Report
from .inventory import validate_inventory
from .strategic import validate_boundaries
from .depgraph import validate_graph, detect_common_mode
from .decisions import validate_registry, freshness_findings
from .evidence import validate_evidence
from .constraints import evaluate_hard_constraints
from .pareto import dominated_findings
from .sensitivity import sensitivity_findings
from .reversibility import validate_reversibility
from .contracts import validate_contract, validate_profile
from .exit_readiness import evaluate_exit
from .protocols import validate_protocols, deprecation_findings, validate_radar
from .supplychain import validate_strategy
from .fitness import evaluate_fitness, validate_fitness_defs


def validate_all(program: dict, *, today: str = "2026-07-11") -> Report:
    rep = Report()
    inv = program.get("inventory", {})
    rep.extend(validate_inventory(inv))
    rep.extend(validate_boundaries(program.get("strategic_map", {})))

    graph = program.get("dependency_graph", {})
    rep.extend(validate_graph(graph))
    rep.extend(detect_common_mode(graph, program.get("provider_groups", [])))

    reg = program.get("decision_registry", {})
    rep.extend(validate_registry(reg))
    rep.extend(freshness_findings(reg, today=today))
    for d in reg.get("decisions", []):
        rep.extend(evaluate_hard_constraints(d))
        rep.extend(dominated_findings(d))
        rep.extend(sensitivity_findings(d))
        rep.extend(validate_reversibility(d))

    rep.extend(validate_evidence(program.get("evidence_registry", {})))

    contracts = program.get("contracts", {})
    for c in contracts.get("contracts", []):
        rep.extend(validate_contract(c))
    for p in program.get("provider_profiles", []):
        rep.extend(validate_profile(p, contracts))

    rep.extend(evaluate_exit(inv, program.get("exit_profiles", [])))

    protos = program.get("protocols", {})
    rep.extend(validate_protocols(protos))
    rep.extend(deprecation_findings(protos, today=today))
    rep.extend(validate_radar(program.get("radar", {})))

    rep.extend(validate_strategy(program.get("supply_chain", {})))
    rep.extend(validate_fitness_defs(program.get("fitness_defs", [])))
    rep.extend(evaluate_fitness(program, today=today))

    rep.metrics.update({
        "technologies": len(inv.get("technologies", [])),
        "decisions": len(reg.get("decisions", [])),
        "contracts": len(contracts.get("contracts", [])),
        "graph_nodes": len(graph.get("nodes", [])),
    })
    return rep
