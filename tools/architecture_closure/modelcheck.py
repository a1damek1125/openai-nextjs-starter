"""Bounded model checks over the closure kernel's core invariants (SP0010 §20
property tests, D-0010-02/03/07).

Small exhaustive checks that must HOLD: the four-valued lattice maps every
(support, refute) pair correctly and only SUPPORTED_ONLY closes a critical
claim; a conjunctive hyperedge fires only when ALL premises are supported;
an unsupported cycle is classified UNSUPPORTED; the Merkle global root is
deterministic and moves when any class root changes. A violation is P0.
"""
from __future__ import annotations

from .canon import global_root
from .model import (Finding, P0, epistemic_state, closes_critical,
                    SUPPORTED_ONLY, REFUTED_ONLY, BOTH, NEITHER)
from .hypergraph import positive_support_closure
from .circularity import analyze


def model_four_valued() -> list[Finding]:
    out = []
    expect = {(True, False): SUPPORTED_ONLY, (False, True): REFUTED_ONLY,
              (True, True): BOTH, (False, False): NEITHER}
    for (s, r), want in expect.items():
        got = epistemic_state(s, r)
        if got != want:
            out.append(Finding("CLAIM_NEITHER", P0, "MODEL/four_valued",
                               f"epistemic_state({s},{r})={got}, want {want}",
                               {}))
    # only SUPPORTED_ONLY closes a critical claim
    for st in (SUPPORTED_ONLY, REFUTED_ONLY, BOTH, NEITHER):
        if closes_critical(st) != (st == SUPPORTED_ONLY):
            out.append(Finding("CRITICAL_CLAIM_NOT_CLOSED", P0,
                               "MODEL/four_valued",
                               f"closes_critical({st}) wrong", {}))
    # truthy strings must not be treated as True
    if epistemic_state("true", "") != NEITHER:
        out.append(Finding("CLAIM_NEITHER", P0, "MODEL/four_valued",
                           "truthy string coerced to boolean support", {}))
    return out


def model_hyperedge_conjunctive() -> list[Finding]:
    out = []
    # a two-premise edge must NOT fire on one premise
    hg = {"anchored": ["A"],
          "edges": [{"conclusion_claim_ref": "G",
                     "premise_claim_refs": ["A", "B"], "conjunctive": True}]}
    sup = positive_support_closure(hg)
    if "G" in sup["supported"]:
        out.append(Finding("HYPEREDGE_PREMISE_MISSING", P0,
                           "MODEL/hyperedge",
                           "single premise activated a two-premise guarantee",
                           {}))
    # with both premises anchored, it fires
    hg2 = {"anchored": ["A", "B"],
           "edges": [{"conclusion_claim_ref": "G",
                      "premise_claim_refs": ["A", "B"], "conjunctive": True}]}
    if "G" not in positive_support_closure(hg2)["supported"]:
        out.append(Finding("HYPEREDGE_PREMISE_MISSING", P0,
                           "MODEL/hyperedge",
                           "conjunctive edge did not fire with all premises",
                           {}))
    return out


def model_unsupported_cycle() -> list[Finding]:
    out = []
    # X <-> Y with no external anchor is UNSUPPORTED
    res = analyze({"X": ["Y"], "Y": ["X"]}, anchored=set(), nodes={"X", "Y"})
    if not res["unsupported"]:
        out.append(Finding("UNSUPPORTED_CIRCULAR_ASSURANCE", P0,
                           "MODEL/cycle",
                           "two-node unsupported cycle not detected", {}))
    # anchored cycle: Z anchors X<->Y
    res2 = analyze({"X": ["Y"], "Y": ["X", "Z"], "Z": []},
                   anchored={"Z"}, nodes={"X", "Y", "Z"})
    if res2["unsupported"]:
        out.append(Finding("ANCHORED_ASSURANCE_CYCLE", P0, "MODEL/cycle",
                           "anchored cycle wrongly marked unsupported", {}))
    return out


def model_root_determinism() -> list[Finding]:
    out = []
    cr = {"a": "1", "b": "2", "c": "3"}
    if global_root(cr) != global_root(dict(cr)):
        out.append(Finding("ARCHITECTURE_GENOME_MISMATCH", P0, "MODEL/root",
                           "global_root not deterministic", {}))
    if global_root(cr) == global_root({**cr, "a": "CHANGED"}):
        out.append(Finding("ARCHITECTURE_GENOME_MISMATCH", P0, "MODEL/root",
                           "class-root change did not move global root", {}))
    return out


MODELS = (
    ("four_valued", model_four_valued),
    ("hyperedge_conjunctive", model_hyperedge_conjunctive),
    ("unsupported_cycle", model_unsupported_cycle),
    ("root_determinism", model_root_determinism),
)


def run_models() -> dict:
    results, findings = {}, []
    for name, fn in MODELS:
        fs = fn()
        results[name] = "HOLD" if not fs else "VIOLATED"
        findings.extend(fs)
    return {"models": results, "findings": findings,
            "all_hold": all(v == "HOLD" for v in results.values())}
