"""Configuration-level causal attribution (SP0011 §2.1.L, §11.19, §12.12/12.13,
D-0011-073..076, AC-0011-181..195).

Which configuration component CAUSED an outcome difference — and is that
attribution causal or only associational? Attribution is causal ONLY under a
supported design (randomized block > matched pair > factorial > controlled replay
> observational). An observational difference is ASSOCIATIONAL_ONLY (D-0011-074).
Identifiability is checked by the backdoor criterion; an unblocked backdoor path
through an unobserved confounder is NOT_IDENTIFIED and causal overclaim is blocked
(D-0011-076).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, IDENTIFIABILITY

DESIGN_STRENGTH = {"RANDOMIZED_BLOCK": 4, "MATCHED_PAIR": 3, "FACTORIAL": 3,
                   "CONTROLLED_REPLAY": 2, "OBSERVATIONAL": 0}


def identify(*, design: str, observed_confounders: list,
             known_confounders: list) -> str:
    """A design of strength >= 2 with all known confounders observed IDENTIFIES;
    strength >= 2 with some unobserved => PARTIALLY_IDENTIFIED; observational =>
    ASSOCIATIONAL_ONLY; a randomized design needs no confounder adjustment."""
    strength = DESIGN_STRENGTH.get(design, 0)
    if strength == 0:
        return "ASSOCIATIONAL_ONLY"
    if design == "RANDOMIZED_BLOCK":
        return "IDENTIFIED"
    unobserved = [c for c in known_confounders if c not in observed_confounders]
    if not unobserved:
        return "IDENTIFIED"
    if len(unobserved) < len(known_confounders):
        return "PARTIALLY_IDENTIFIED"
    return "NOT_IDENTIFIED"


def attribute(*, outcome_ref: str, treatment_component: str,
              reference_configuration: str, candidate_configuration: str,
              design: str, observed_confounders: list, known_confounders: list,
              effect_estimate: float | None) -> dict:
    ident = identify(design=design, observed_confounders=observed_confounders,
                     known_confounders=known_confounders)
    assert ident in IDENTIFIABILITY
    # causal effect reported only when IDENTIFIED; else state, no ATE
    state = "CAUSAL" if ident == "IDENTIFIED" else ident
    rec = {"attribution_id": "ATTR-" + hash_obj(
                {"o": outcome_ref, "t": treatment_component,
                 "r": reference_configuration, "c": candidate_configuration})[:16],
           "outcome_ref": outcome_ref, "treatment_component": treatment_component,
           "reference_configuration": reference_configuration,
           "candidate_configuration": candidate_configuration, "design": design,
           "confounder_refs": sorted(known_confounders),
           "identifiability": ident,
           "effect_estimate": effect_estimate if ident == "IDENTIFIED" else None,
           "state": "ASSOCIATIONAL_ONLY" if ident in
           ("ASSOCIATIONAL_ONLY", "NOT_IDENTIFIED", "PARTIALLY_IDENTIFIED")
           else state}
    return rec


def causal_findings(records: list, *, overclaim_attempts: list = None) -> list:
    out: list[Finding] = []
    for oc in (overclaim_attempts or []):
        out.append(Finding("CAUSAL_OVERCLAIM", P0, oc,
                           "causal claim made without identification: blocked "
                           "(D-0011-076)", {}))
    return out


def causal_root(records: list) -> str:
    return hash_obj(sorted((r["attribution_id"], r["identifiability"])
                           for r in records))
