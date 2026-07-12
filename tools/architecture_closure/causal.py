"""Causal + counterfactual control verification (SP0010 V5 FUNCTION U, §0,
D-0010-101..107).

counterfactual.py shows, in a bounded mutation model, that removing a control
makes a violation reachable. That is a *statistical* counterfactual. This module
adds the *causal* question: is the control's effect on the protected property
actually IDENTIFIABLE, or is the apparent necessity confounded? For each critical
control we build a small Structural Causal Model

    U -> C ,  U -> Y ,  C -> Y

(C = the control/intervention, Y = the protected property, U = context/confounder)
and test identifiability of P(Y | do(C)) by the BACKDOOR CRITERION: the effect is
IDENTIFIED iff every backdoor path C <- ... -> Y can be blocked by an adjustment
set drawn from the OBSERVED variables. A control grounded on disk makes its
enforcement point (and its context confounder) observed; an ungrounded control
leaves the intervention unobserved, so its effect is NOT_IDENTIFIED and its
counterfactual necessity is not causally supported (fail-closed). Only an
IDENTIFIED necessary control is counted (D-0010-103).

Governance/analysis tooling only; never imported by product code; no external
effect; emits no secret values.
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj
from .model import Finding, P0, P1, IDENTIFIABILITY
from . import counterfactual


# --------------------------------------------------------------------------- #
# generic backdoor-criterion identifiability over a small DAG                  #
# --------------------------------------------------------------------------- #
def _undirected_paths(edges: list, src: str, dst: str, max_len: int = 6):
    """All simple paths (ignoring direction) from src to dst, each as a list of
    (node, node, direction_forward) segments so colliders can be tested."""
    adj = {}
    for u, v in edges:
        adj.setdefault(u, []).append((v, True))
        adj.setdefault(v, []).append((u, False))
    paths = []

    def walk(node, visited, trail):
        if len(trail) > max_len:
            return
        if node == dst and trail:
            paths.append(list(trail))
            return
        for nxt, forward in adj.get(node, []):
            if nxt in visited:
                continue
            trail.append((node, nxt, forward))
            walk(nxt, visited | {nxt}, trail)
            trail.pop()

    walk(src, {src}, [])
    return paths


def _is_backdoor(path) -> bool:
    """A path from C is a backdoor path iff its first edge points INTO C
    (i.e. the first segment is traversed backwards: node<-C means forward=False
    from C's perspective). Our segments are (from,to,forward); the first segment
    starts at C, so forward=False means the arrow is to->from, i.e. into C."""
    if not path:
        return False
    _, _, forward = path[0]
    return forward is False


def _path_blocked(path, adjustment: set) -> bool:
    """A path is blocked (d-separated) given the adjustment set if it contains a
    non-collider in the adjustment set, OR a collider whose descendant is NOT in
    the adjustment set. Simplified for the small control SCMs used here."""
    for i in range(len(path) - 1):
        a, b, f1 = path[i]
        _, c, f2 = path[i + 1]
        # middle node is b; collider iff arrows meet head-to-head at b:
        # segment i points b<-... means into b when f1 True (a->b); next segment
        # points ...->b into b when f2 False (c->b). collider iff both into b.
        into_b_left = f1 is True
        into_b_right = f2 is False
        collider = into_b_left and into_b_right
        if not collider and b in adjustment:
            return True                      # blocked by conditioning on chain/fork
        if collider and b not in adjustment:
            return True                      # blocked: collider not conditioned
    return False


def identify_effect(edges: list, observed, treatment: str,
                    outcome: str) -> dict:
    """Backdoor identifiability of P(outcome | do(treatment)). IDENTIFIED iff
    every backdoor path is blocked by an adjustment set of OBSERVED nodes."""
    observed = set(observed)
    all_paths = _undirected_paths(edges, treatment, outcome)
    backdoor = [p for p in all_paths if _is_backdoor(p)]
    # candidate adjustment = observed non-treatment/outcome nodes
    adjustment = observed - {treatment, outcome}
    unblocked = [p for p in backdoor if not _path_blocked(p, adjustment)]
    if not backdoor:
        klass = "IDENTIFIED"
    elif not unblocked:
        klass = "IDENTIFIED"
    else:
        # any unblocked backdoor path through an UNOBSERVED confounder =>
        # not identifiable; if the blocker merely needs an unobserved node =>
        # partially identifiable
        needs_unobserved = any(
            any(seg[1] not in observed for seg in p) for p in unblocked)
        klass = "NOT_IDENTIFIED" if needs_unobserved else "PARTIALLY_IDENTIFIED"
    assert klass in IDENTIFIABILITY
    return {"identifiability": klass, "backdoor_paths": len(backdoor),
            "unblocked_backdoor_paths": len(unblocked),
            "adjustment_set": sorted(adjustment)}


# --------------------------------------------------------------------------- #
# per-control SCM                                                              #
# --------------------------------------------------------------------------- #
def _control_scm(control_id: str, grounded: bool) -> dict:
    """The canonical control SCM: U (context) -> C, U -> Y, C -> Y. Grounding on
    disk makes C and U OBSERVED (the enforcement + its request context are in
    the checked code path); an ungrounded control leaves C unobserved."""
    edges = [("U", "C"), ("U", "Y"), ("C", "Y")]
    observed = ["C", "U", "Y"] if grounded else ["Y"]
    return {"edges": [list(e) for e in edges], "observed": observed,
            "treatment": "C", "outcome": "Y"}


def analyze_control(control_id: str, *, root: Path = Path(".")) -> dict:
    spec = counterfactual.CONTROLS[control_id]
    grounded = counterfactual._grounded(root, spec)
    scm = _control_scm(control_id, grounded)
    ident = identify_effect(scm["edges"], scm["observed"],
                            scm["treatment"], scm["outcome"])
    cf = counterfactual.verify_control(control_id, root=root)
    # a control counts as CAUSALLY NECESSARY only if identified AND the bounded
    # counterfactual shows removal reaches a violation.
    causally_necessary = (ident["identifiability"] == "IDENTIFIED"
                          and cf["necessity_witness"]
                          ["reachable_violation_on_removal"])
    return {
        "control_id": control_id,
        "critical": spec["critical"],
        "grounded": grounded,
        "scm": scm,
        "identifiability": ident["identifiability"],
        "identification": ident,
        "counterfactual_class": cf["classification"],
        "causally_necessary": causally_necessary,
    }


def analyze_all(root: Path = Path(".")) -> dict:
    return {c: analyze_control(c, root=root)
            for c in sorted(counterfactual.CONTROLS)}


def causal_findings(results: dict) -> list[Finding]:
    out: list[Finding] = []
    for c, rec in sorted(results.items()):
        if not rec["critical"]:
            continue
        if rec["identifiability"] == "NOT_IDENTIFIED":
            out.append(Finding(
                "CONTROL_EFFECT_NOT_IDENTIFIED", P0, c,
                "critical control's causal effect is NOT identifiable (an "
                "unblocked backdoor path via an unobserved confounder): its "
                "counterfactual necessity is not causally supported "
                "(D-0010-103)", rec["identification"]))
        elif rec["identifiability"] == "PARTIALLY_IDENTIFIED":
            out.append(Finding(
                "CONTROL_EFFECT_PARTIALLY_IDENTIFIED", P1, c,
                "critical control's causal effect is only partially identified: "
                "disclosed, not counted as fully identified (D-0010-104)",
                rec["identification"]))
    return out


def causal_root(results: dict) -> str:
    return hash_obj({c: rec["identifiability"] for c, rec in sorted(
        results.items())})
