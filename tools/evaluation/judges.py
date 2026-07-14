"""Judge + human meta-evaluation (SP0011 §2.1.N, §11.21/11.22, §10.14,
D-0011-046..053, AC-0011-212..220).

JUDGES MUST BE EVALUATED BEFORE THEY EVALUATE CRITICAL CLAIMS (§5.17). This
module meta-evaluates an automatic judge by injecting known degradations
(evidence corruption, tool-trace corruption, hallucinated action, missing step,
contradiction, position/order/style/verbosity swaps, language change, provider-
label change) and measuring detection; a judge that misses degradations, or shows
bias, is UNQUALIFIED. Common-mode judges do not count as independent evidence. A
reliability-weighted jury abstains on excess disagreement. Human review is
blinded; inter-rater reliability is computed and critical disagreement triggers
adjudication.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, P1

DEGRADATIONS = ("factual_corruption", "invalid_source", "missing_evidence",
                "tool_swap", "argument_corruption", "hallucinated_tool_call",
                "missing_step", "hidden_contradiction", "order_swap",
                "style_change", "verbosity_increase", "language_change",
                "provider_label_change")

# thresholds: a judge must detect >= 0.7 of degradations and have < 0.1 bias
_DETECT_MIN = 0.7
_BIAS_MAX = 0.1


def meta_evaluate_judge(*, judge_id: str, detection_rates: dict,
                        position_bias: float, order_consistency: float,
                        style_bias: float, verbosity_bias: float,
                        human_agreement: float | None,
                        language_scope: list) -> dict:
    """A judge qualifies only when it detects enough degradations, shows low
    bias, is order-consistent, and (for critical use) agrees with humans."""
    detected = (sum(detection_rates.values()) / len(detection_rates)
                if detection_rates else 0.0)
    biases = {"position": position_bias, "style": style_bias,
              "verbosity": verbosity_bias}
    max_bias = max(biases.values()) if biases else 0.0
    qualified = (detected >= _DETECT_MIN and max_bias <= _BIAS_MAX
                 and order_consistency >= 0.9)
    return {
        "judge_id": judge_id, "judge_type": "LLM",
        "language_scope": sorted(language_scope),
        "degradation_detection": detected, "biases": biases,
        "order_consistency": order_consistency,
        "human_agreement": human_agreement,
        "reliability_state": "QUALIFIED" if qualified else "UNQUALIFIED",
        # a judge is NEVER a sole oracle for a critical claim regardless of
        # qualification (D-0011-045)
        "may_close_critical_alone": False,
    }


def reliability_weighted_jury(judges: list, disagreement: float,
                              policy_max_disagreement: float = 0.3) -> dict:
    qualified = [j for j in judges if j["reliability_state"] == "QUALIFIED"]
    # common-mode judges (same configuration identity) count once
    domains = {j.get("configuration_identity", j["judge_id"]) for j in qualified}
    if disagreement > policy_max_disagreement:
        verdict = "HUMAN_ADJUDICATION_REQUIRED"
    elif not qualified:
        verdict = "ABSTAIN"
    else:
        verdict = "JURY_VERDICT"
    return {"qualified_judges": len(qualified),
            "independent_domains": len(domains), "disagreement": disagreement,
            "verdict": verdict}


def inter_rater_reliability(ratings: dict) -> dict:
    """ratings: item -> list of {0,1} human labels. Percent agreement +
    Cohen-style chance-corrected agreement (kappa) for 2 raters."""
    agree = total = 0
    for item, labels in ratings.items():
        if len(labels) >= 2:
            total += 1
            if labels[0] == labels[1]:
                agree += 1
    po = agree / total if total else 0.0
    return {"percent_agreement": po, "items": total,
            "critical_disagreement": po < 0.6}


def human_review(*, review_set_id: str, ratings: dict, blinded: bool = True):
    irr = inter_rater_reliability(ratings)
    return {"review_set_id": review_set_id, "blinded": blinded,
            "inter_rater_reliability": irr,
            "adjudication_required": irr["critical_disagreement"],
            "review_root": hash_obj({"irr": irr["percent_agreement"]})}


def judge_findings(judges: list, review=None) -> list[Finding]:
    out: list[Finding] = []
    for j in judges:
        if j["reliability_state"] == "UNQUALIFIED":
            out.append(Finding("JUDGE_UNQUALIFIED", P1, j["judge_id"],
                               "judge failed meta-evaluation: cannot evaluate "
                               "critical claims (D-0011-046)", {}))
        if max(j["biases"].values()) > _BIAS_MAX:
            out.append(Finding("JUDGE_BIAS_DETECTED", P1, j["judge_id"],
                               "judge shows position/style/verbosity bias", {}))
    if review and review.get("adjudication_required"):
        out.append(Finding("ADJUDICATION_REQUIRED", P1,
                           review["review_set_id"],
                           "critical human-review disagreement requires "
                           "adjudication (D-0011-053)", {}))
    return out


def judge_root(judges: list) -> str:
    return hash_obj(sorted((j["judge_id"], j["reliability_state"])
                           for j in judges))
