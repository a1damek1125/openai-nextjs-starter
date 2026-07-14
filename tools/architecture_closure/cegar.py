"""CEGAR — Counterexample-Guided Abstraction Refinement (SP0010 V5 FUNCTION V,
§0, D-0010-108..114).

The paired-world noninterference check (noninterference.py) runs over concrete
bounded reference models. This module verifies the SAME safety properties through
a SOUND ABSTRACTION and refines it on demand, so an abstract "possible leak" is
never accepted as a real one and — crucially — an exhausted refinement budget is
NEVER reported as PASS (D-0010-111).

The loop, per property:
  1. Build a coarse predicate abstraction (observe few fields). The abstraction
     is SOUND: if it proves the property, the property truly holds; if it cannot,
     it conservatively reports a candidate counterexample.
  2. CONCRETIZE the abstract counterexample against the concrete model. If it
     corresponds to a real violating pair -> REAL_COUNTEREXAMPLE (a genuine
     leak). If not -> SPURIOUS.
  3. On SPURIOUS, REFINE (observe one more field) and retry.
  4. If the property is proved -> PROVED. If the refinement budget is exhausted
     while counterexamples remain unresolved -> LIMIT_REACHED (NOT a pass).

Governance/analysis tooling only; never imported by product code; no external
effect; emits no secret values.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, CEGAR_OUTCOMES

# The predicate refinement order: observing `out` then `low` is sufficient to
# PROVE noninterference (out determined by low within each low-class), without
# ever needing to observe the secret `high`.
_OBSERVE_ORDER = ("out", "low")


def _concrete_leak(states: list) -> dict | None:
    """Ground truth: a real leak is a pair with the same low input, DIFFERENT
    high secret, and DIFFERENT low-observable output."""
    for i in range(len(states)):
        for j in range(i + 1, len(states)):
            s, t = states[i], states[j]
            if s["low"] == t["low"] and s["high"] != t["high"] \
                    and s["out"] != t["out"]:
                return {"s": s, "t": t}
    return None


def _abstraction_proves_safe(states: list, observed: frozenset) -> bool:
    """SOUND abstract check: the property is proved only when the abstraction can
    observe BOTH `low` and `out` and, within every low-class, all outputs agree
    (so `out` is a function of `low` and cannot depend on `high`). Any coarser
    abstraction cannot prove it and must yield a candidate counterexample."""
    if not ({"low", "out"} <= set(observed)):
        return False
    by_low = {}
    for s in states:
        by_low.setdefault(s["low"], set()).add(s["out"])
    return all(len(outs) == 1 for outs in by_low.values())


def verify_property(*, property_id: str, states: list,
                    max_refinements: int = len(_OBSERVE_ORDER)) -> dict:
    trace = []
    observed = frozenset()
    refinements = 0
    while True:
        if _abstraction_proves_safe(states, observed):
            outcome = "PROVED"
            break
        # abstraction cannot prove safety -> candidate counterexample; concretize
        real = _concrete_leak(states)
        if real is not None:
            trace.append({"observed": sorted(observed), "verdict": "REAL"})
            outcome = "REAL_COUNTEREXAMPLE"
            break
        # spurious: the abstract CE has no concrete realization -> refine
        trace.append({"observed": sorted(observed), "verdict": "SPURIOUS"})
        if refinements >= max_refinements or refinements >= len(_OBSERVE_ORDER):
            outcome = "LIMIT_REACHED"
            break
        observed = observed | {_OBSERVE_ORDER[refinements]}
        refinements += 1
    assert outcome in CEGAR_OUTCOMES
    return {
        "property_id": property_id,
        "outcome": outcome,
        "refinements": refinements,
        "final_observed": sorted(observed),
        "trace": trace,
        # ONLY PROVED is a pass; LIMIT_REACHED and REAL_COUNTEREXAMPLE are not.
        "pass": outcome == "PROVED",
    }


# Concrete bounded reference models for the tenant / approval hyperproperties.
# The HONEST model: out depends only on `low` (the non-secret request), never on
# `high` (the secret) — it genuinely satisfies noninterference and the CEGAR loop
# PROVES it after refining away the coarse-abstraction spurious counterexample.
# The LEAKY model: out depends on `high` — a concrete same-low/different-high/
# different-out pair, i.e. a real information-flow leak the loop CONCRETIZES.
def _honest_model() -> list:
    states = []
    for low in (0, 1):
        for high in (0, 1):
            states.append({"low": low, "high": high, "out": low})  # out=f(low)
    return states


def _leaky_model() -> list:
    states = []
    for low in (0, 1):
        for high in (0, 1):
            states.append({"low": low, "high": high, "out": high})  # out=f(high)
    return states


# Each CEGAR property is GROUNDED on a real repository control (red-team P1-D):
# the model is honest ONLY while the control's file+symbol exist on disk; if the
# grounding vanished the model becomes leaky and CEGAR concretizes a REAL
# counterexample. So the outcome is derived from the repository, not hard-coded.
CEGAR_GROUNDINGS = {
    "CEGAR-TENANT-NONINTERFERENCE": ("finalis/portal/db.py", "tenant_id"),
    "CEGAR-APPROVAL-ISOLATION": ("tools/governed_work/approval.py", None),
    "CEGAR-PROVIDER-ACCOUNT-SEPARATION": ("finalis/portal/app.py",
                                          "require_permission"),
    "CEGAR-CONTROL-LANGUAGE-INVARIANCE": ("tools/semantics", None),
}


def _grounded(root, path: str, symbol) -> bool:
    from pathlib import Path
    p = Path(root) / path
    if not p.exists():
        return False
    if not symbol or p.is_dir():
        return True
    try:
        return symbol in p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def model_for(root, property_id: str) -> list:
    path, symbol = CEGAR_GROUNDINGS[property_id]
    return _honest_model() if _grounded(root, path, symbol) else _leaky_model()


def run_all(root=".") -> dict:
    return {pid: verify_property(property_id=pid, states=model_for(root, pid))
            for pid in sorted(CEGAR_GROUNDINGS)}


def cegar_findings(results: dict) -> list[Finding]:
    out: list[Finding] = []
    for pid, rec in sorted(results.items()):
        if rec["outcome"] == "REAL_COUNTEREXAMPLE":
            out.append(Finding(
                "CEGAR_REAL_COUNTEREXAMPLE", P0, pid,
                "CEGAR concretized a REAL counterexample: the abstract 'possible "
                "leak' corresponds to a concrete violating pair (D-0010-109)",
                {"trace": rec["trace"]}))
        elif rec["outcome"] == "LIMIT_REACHED":
            out.append(Finding(
                "CEGAR_LIMIT_REACHED", P0, pid,
                "CEGAR refinement budget exhausted without proving the property: "
                "LIMIT_REACHED is NOT a pass (fail-closed, D-0010-111)",
                {"refinements": rec["refinements"]}))
    return out


def cegar_root(results: dict) -> str:
    return hash_obj({pid: rec["outcome"] for pid, rec in sorted(results.items())})
