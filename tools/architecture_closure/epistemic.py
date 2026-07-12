"""Four-valued epistemic closure (SP0010 FUNCTION E, §11.3/11.4, §12.1,
D-0010-02/03/04, AC-0010-044..053).

Every claim tracks positive support and refuting support INDEPENDENTLY; they are
never subtracted or averaged (D-0010-04). The state is (support, refute) ->
SUPPORTED_ONLY / REFUTED_ONLY / BOTH / NEITHER. A CRITICAL claim is closure-
admissible ONLY in SUPPORTED_ONLY: BOTH is a contradiction, NEITHER is
unresolved, REFUTED_ONLY is refuted — none may become PASS (INV-0010-8/9/10).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import (Finding, P0, P1, epistemic_state, SUPPORTED_ONLY,
                    REFUTED_ONLY, BOTH, NEITHER)


def refutation_closure(refuting_atoms: set, refutation_edges: list) -> dict:
    """Least fixed point over refutation propagation (§11.3): starts from
    verified refuting atoms; propagates through rebuttal/undercut/contradiction
    edges {premises} -> refuted_claim."""
    refuted = set(refuting_atoms)
    iterations = 0
    changed = True
    while changed:
        changed = False
        iterations += 1
        for e in refutation_edges:
            tgt = e["refutes"]
            if tgt in refuted:
                continue
            if all(p in refuted for p in e.get("premises", [])):
                refuted.add(tgt)
                changed = True
        if iterations > 1000:
            break
    return {"refuted": sorted(refuted), "iterations": iterations}


def classify(claims: set, supported: set, refuted: set,
             critical: set) -> dict:
    """Assign each claim its four-valued state + closure admissibility."""
    states = {}
    for c in sorted(claims):
        st = epistemic_state(c in supported, c in refuted)
        states[c] = {
            "state": st,
            "critical": c in critical,
            "closure_admissible": (st == SUPPORTED_ONLY) if c in critical
            else st in (SUPPORTED_ONLY, NEITHER),
        }
    return states


def epistemic_findings(states: dict) -> list[Finding]:
    out: list[Finding] = []
    for c, rec in sorted(states.items()):
        if not rec["critical"]:
            continue
        st = rec["state"]
        if st == BOTH:
            out.append(Finding(
                "CRITICAL_CLAIM_BOTH", P0, c,
                "critical claim has BOTH support and refutation: a "
                "contradiction is never PASS (D-0010-03, INV-0010-8)", {}))
        elif st == NEITHER:
            out.append(Finding(
                "CRITICAL_CLAIM_NEITHER", P0, c,
                "critical claim has NEITHER support nor refutation: absence of "
                "support is not satisfaction (D-0010-06, INV-0010-9)", {}))
        elif st == REFUTED_ONLY:
            out.append(Finding(
                "CRITICAL_CLAIM_REFUTED", P0, c,
                "critical claim is refuted", {}))
    return out


def epistemic_root(states: dict) -> str:
    return hash_obj({c: rec["state"] for c, rec in sorted(states.items())})


def summary(states: dict) -> dict:
    counts = {SUPPORTED_ONLY: 0, REFUTED_ONLY: 0, BOTH: 0, NEITHER: 0}
    crit = {SUPPORTED_ONLY: 0, REFUTED_ONLY: 0, BOTH: 0, NEITHER: 0}
    for rec in states.values():
        counts[rec["state"]] += 1
        if rec["critical"]:
            crit[rec["state"]] += 1
    return {"all": counts, "critical": crit,
            "critical_both": crit[BOTH], "critical_neither": crit[NEITHER]}
