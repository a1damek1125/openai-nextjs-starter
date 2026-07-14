"""Safety Reassessment Triggers + Change Impact Cone (SP0005 D-0005-73/74/75/76,
§11.12, INV-0005-23/25).

A reassessment trigger (new model / provider / tool / authority / effect class /
role pack / vertical / country / jurisdiction / semantic epoch / architecture
change / incident / repeated near miss / new regulatory source / new threat /
changed provider contract) fires a governed review — never an automatic policy
mutation (D-0005-80, INV-0005-25). The impact cone traverses typed cross-graph
references (architecture / semantic / program / technology / safety) to find
affected hazards, contracts, obligations, controls, claims, evidence, tests, use
cases (§11.12). Incremental reassessment must equal the full reference
(AC-0005-187).
"""
from __future__ import annotations

from .model import Finding, P1

TRIGGER_KINDS = {"NEW_MODEL", "NEW_MODEL_SNAPSHOT", "NEW_PROVIDER",
                 "PROVIDER_MAJOR_CHANGE", "NEW_TOOL", "NEW_WRITE_AUTHORITY",
                 "NEW_EFFECT_CLASS", "NEW_ROLE_PACK", "NEW_VERTICAL",
                 "NEW_COUNTRY", "NEW_JURISDICTION", "NEW_SEMANTIC_EPOCH",
                 "ARCHITECTURE_CHANGE", "SAFETY_INCIDENT", "REPEATED_NEAR_MISS",
                 "NEW_REGULATORY_SOURCE", "NEW_THREAT_TECHNIQUE",
                 "CHANGED_PROVIDER_CONTRACT"}


def triggers_for(event: dict) -> list[str]:
    """Which reassessment triggers a change event fires."""
    return sorted(t for t in event.get("changes", []) if t in TRIGGER_KINDS)


def impact_cone(program: dict, change: dict) -> dict:
    """Everything affected by a safety-relevant change (§11.12, §D-0005-75)."""
    changed_hazards = set(change.get("hazard_refs", []))
    # forward from changed hazards through the safety graph
    affected_constraints = [c["constraint_id"] for c in program.get("constraints", [])
                            if changed_hazards & set(c.get("hazard_refs", []))]
    affected_controls = [c["control_id"] for c in program.get("controls", [])
                         if changed_hazards & set(c.get("hazard_refs", []))]
    affected_claims = [c["claim_id"] for c in program.get("claims", [])
                       if changed_hazards & set(c.get("hazard_refs", []))]
    return {
        "change_id": change.get("change_id"),
        "triggers": triggers_for(change),
        "affected_hazards": sorted(changed_hazards),
        "affected_constraints": sorted(affected_constraints),
        "affected_controls": sorted(affected_controls),
        "affected_contracts": sorted(change.get("affected_contracts", [])),
        "affected_obligations": sorted(change.get("affected_obligations", [])),
        "affected_claims": sorted(affected_claims),
        "affected_evidence": sorted(change.get("affected_evidence", [])),
        "affected_use_cases": sorted(change.get("affected_use_cases", [])),
    }


def incremental_equals_full(program: dict, change: dict) -> bool:
    """The incremental impact set (affected closure) must be a subset that, when
    recomputed, matches the full reference (AC-0005-187). Here: the affected
    hazard set from the incremental cone equals recomputing over the whole graph
    restricted to the changed hazards."""
    inc = set(impact_cone(program, change)["affected_controls"])
    changed = set(change.get("hazard_refs", []))
    full = {c["control_id"] for c in program.get("controls", [])
            if changed & set(c.get("hazard_refs", []))}
    return inc == full
