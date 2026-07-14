"""Value-of-Information engine (SP0003 D-0003-35/36/37, §11.22/§11.23,
INV-0003-18).

VOI(q) = ExpectedLoss_current - ExpectedLoss_after_info - Cost(q).

VOI is computed ONLY where a grounded probability model, a grounded loss model
and a research cost all exist. Otherwise it returns VOI_NOT_CALIBRATED — numbers
are never invented (D-0003-35). VOI may never justify skipping mandatory safety,
security, tenant-isolation, human-oversight, regulatory or hard-architecture work
(INV-0003-18, §17.4): those are flagged non-bypassable regardless of economics.
"""
from __future__ import annotations

from .model import DECISION_IMPACT

# Non-bypassable by VOI (INV-0003-18). EXTERNAL_EFFECT_PRECONDITION is included so
# regulatory / real-external-effect approvals cannot be economically waived
# (red-team SWARM-L P2 observation; aligns code with the docstring).
MANDATORY_TYPES = {"SAFETY_PRECONDITION", "AUTHORITY_PRECONDITION",
                   "TENANT_ISOLATION_PRECONDITION",
                   "HUMAN_OVERSIGHT_PRECONDITION",
                   "ARCHITECTURE_PRECONDITION",
                   "EXTERNAL_EFFECT_PRECONDITION"}


def evaluate_voi(uncertainty: dict) -> dict:
    """Return a VOI evaluation. Requires probability_model + loss_model + cost.
    Missing any -> VOI_NOT_CALIBRATED (never fabricated)."""
    if uncertainty.get("mandatory") or \
            uncertainty.get("dependency_type") in MANDATORY_TYPES:
        return {"status": "MANDATORY_NON_BYPASSABLE",
                "message": "mandatory safety/authority/isolation/oversight/"
                           "architecture work — VOI cannot gate it",
                "bypassable": False}
    pm = uncertainty.get("probability_model")
    lm = uncertainty.get("loss_model")
    cost = uncertainty.get("research_cost")
    if pm is None or lm is None or cost is None:
        return {"status": "VOI_NOT_CALIBRATED",
                "message": "probability/loss/cost model incomplete",
                "bypassable": False}
    # grounded expected-loss form: loss = P(bad) * impact_loss
    p_bad_now = float(pm.get("p_wrong_now", 0.0))
    p_bad_after = float(pm.get("p_wrong_after", 0.0))
    impact_loss = float(lm.get("impact_loss", 0.0))
    el_now = p_bad_now * impact_loss
    el_after = p_bad_after * impact_loss
    voi = el_now - el_after - float(cost)
    return {"status": "CALIBRATED",
            "expected_loss_now": round(el_now, 6),
            "expected_loss_after": round(el_after, 6),
            "research_cost": float(cost),
            "voi": round(voi, 6),
            "recommend_research_first": voi > 0,
            "bypassable": True}


def research_priority(uncertainty: dict) -> dict:
    """Non-authoritative candidate priority (§11.23). Safety research is never
    deprioritized purely on weak short-term economics."""
    impact = uncertainty.get("decision_impact", "LOW")
    weight = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}.get(impact, 1)
    mandatory = uncertainty.get("mandatory") or \
        uncertainty.get("dependency_type") in MANDATORY_TYPES
    return {"decision_impact": impact, "priority_weight": weight,
            "safety_protected": bool(mandatory)}
