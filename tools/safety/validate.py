"""Top-level safety-model validation (SP0005 §15/§18).

Combines loss/hazard/threat/UCA/constraint/control/contract/assurance/evidence/
regulatory/use-case/incident validation with hazard-traceability closure, control
independence, open-defeater and stale-critical-evidence checks. A hard finding
(P0/P1) can never be offset by a score (§12.2, D-0005-78); the Report is valid
only when zero P0 and zero P1 remain.
"""
from __future__ import annotations

from .model import Report
from .losses import validate_losses
from .hazards import validate_hazards, traceability
from .threats import validate_threats
from .uca import validate_ucas
from .constraints import validate_constraints
from .barriers import validate_controls, independence_findings
from .contracts import validate_action_contract, validate_trajectory_contract
from .obligations import validate_obligation
from .assurance import (validate_claims, open_defeaters, stale_critical_evidence)
from .evidence import validate_evidence
from .regulatory import validate_sources, check_binding_claims
from .usecases import validate_usecases
from .oversight import validate_review_packet
from .incidents import validate_incidents, near_miss_findings
from .scenarios import validate_scenario


def validate_all(program: dict) -> Report:
    rep = Report()
    rep.extend(validate_losses(program))
    rep.extend(validate_hazards(program))
    rep.extend(validate_threats(program))
    rep.extend(validate_ucas(program))
    rep.extend(validate_constraints(program))
    rep.extend(validate_controls(program))
    rep.extend(traceability(program))
    rep.extend(independence_findings(program))
    for c in program.get("action_contracts", []):
        rep.extend(validate_action_contract(c))
    for c in program.get("trajectory_contracts", []):
        rep.extend(validate_trajectory_contract(c))
    for o in program.get("proof_obligations", []):
        rep.extend(validate_obligation(o))
    rep.extend(validate_claims(program))
    rep.extend(open_defeaters(program))
    rep.extend(stale_critical_evidence(program))
    rep.extend(validate_evidence(program))
    rep.extend(validate_sources(program))
    rep.extend(check_binding_claims(program))
    rep.extend(validate_usecases(program))
    for p in program.get("review_packets", []):
        rep.extend(validate_review_packet(p))
    rep.extend(validate_incidents(program))
    rep.extend(near_miss_findings(program))
    # committed scenarios are static artifacts — gate their well-formedness too
    # (SWARM-O gap 1); runtime-only checkers stay out of the static sweep
    for s in program.get("scenarios", []):
        rep.extend(validate_scenario(s))

    rep.metrics.update({
        "losses": len(program.get("losses", [])),
        "hazards": len(program.get("hazards", [])),
        "controls": len(program.get("controls", [])),
        "claims": len(program.get("claims", [])),
        "regulatory_sources": len(program.get("sources", [])),
    })
    return rep
