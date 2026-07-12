"""Multi-fidelity + adaptive evaluation (SP0011 §2.1.Q, §11.23/11.24, §12.13,
D-0011-095..100, AC-0011-261..280).

Evaluation escalates through fidelities STATIC→UNIT→REPLAY→SANDBOX→FIELD→
PRODUCTION (M0→M5). A low-fidelity FAIL may stop escalation; a low-fidelity PASS
can NEVER grant a higher-maturity credit (D-0011-099, the multi-fidelity evidence
firewall). Adaptive scenario selection runs ONLY after mandatory critical
coverage, records every selection probability (D-0011-096), and estimates use
inverse-propensity correction (§12.13). Critical scenarios cannot be sampled away
(D-0011-094) and a known weak stratum cannot be eliminated by racing (D-0011-100).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, FIDELITY_LEVELS, FIDELITY_TO_MATURITY


def fidelity_registry() -> dict:
    return {lvl: {"fidelity": lvl, "grants_maturity": FIDELITY_TO_MATURITY[lvl]}
            for lvl in FIDELITY_LEVELS}


def promotion_allowed(evidence_fidelity: str, required_maturity: str) -> bool:
    """A credit at required_maturity may be granted only by evidence whose
    fidelity maps to at least that maturity (the firewall)."""
    from .model import maturity_meets
    return maturity_meets(FIDELITY_TO_MATURITY.get(evidence_fidelity, "M0"),
                          required_maturity)


def adaptive_plan(*, mandatory_covered: bool, candidates: list) -> dict:
    """Adaptive selection only AFTER mandatory coverage. Each selected candidate
    records its selection probability. Mandatory-critical candidates always have
    selection probability 1.0 (never sampled away)."""
    selections = []
    for c in candidates:
        prob = 1.0 if c.get("mandatory_critical") else c.get("selection_prob", 0.5)
        selections.append({"scenario_ref": c["scenario_ref"],
                           "selection_probability": prob,
                           "mandatory_critical": bool(c.get("mandatory_critical"))})
    return {"mandatory_coverage_complete": mandatory_covered,
            "selections": selections,
            "all_probabilities_logged": all("selection_probability" in s
                                            for s in selections),
            "critical_omitted": [s["scenario_ref"] for s in selections
                                 if s["mandatory_critical"]
                                 and s["selection_probability"] < 1.0],
            "adaptive_root": hash_obj(sorted(
                (s["scenario_ref"], s["selection_probability"])
                for s in selections))}


def inverse_propensity(observations: list) -> dict:
    """μ_hat = Σ(Y_i/π_i) / Σ(1/π_i) over adaptively-selected runs (§12.13)."""
    num = sum(y / p for y, p in observations if p > 0)
    den = sum(1 / p for _, p in observations if p > 0)
    return {"ipw_estimate": num / den if den else None, "n": len(observations)}


def fidelity_findings(*, plan: dict, low_fidelity_promotions: list = None,
                      before_mandatory: bool = False) -> list[Finding]:
    out: list[Finding] = []
    for cid in (low_fidelity_promotions or []):
        out.append(Finding("LOW_FIDELITY_EVIDENCE_PROMOTION", P0, cid,
                           "low-fidelity evidence promoted to a higher maturity "
                           "credit (D-0011-099)", {}))
    if plan["critical_omitted"]:
        out.append(Finding("CRITICAL_SCENARIO_OMITTED", P0, "adaptive",
                           f"mandatory-critical scenarios adaptively omitted: "
                           f"{plan['critical_omitted']} (D-0011-094)", {}))
    if not plan["all_probabilities_logged"]:
        out.append(Finding("ADAPTIVE_SELECTION_LOG_MISSING", P0, "adaptive",
                           "adaptive selection probabilities not logged "
                           "(D-0011-096)", {}))
    return out
