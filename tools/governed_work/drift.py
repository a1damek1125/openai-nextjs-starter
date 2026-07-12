"""Hard Goal-Drift Predicates + Soft Goal-Drift Metric (SP0006 §9.9, §11.10,
D-0006-42..45, INV-0006-28/29).

Goal drift is split into two non-fungible layers. HARD drift is a set of boolean
predicates over invariant anchors — tenant, purpose, target, forbidden scope,
capability ceiling, outcome contract, hard constraints, approval context; ANY of
them flipping is HARD_GOAL_DRIFT (P0) and immediately blocks (D-0006-42/43). SOFT
drift is a bounded weighted metric D = Σ wᵢ·dᵢ (Σwᵢ = 1) over continuous signals,
placed in a band via versioned thresholds (D-0006-44).

The two layers are strictly ordered (INV-0006-28/29): a LOW soft score can NEVER
override a hard block, and a HIGH soft score can NEVER by itself create authority
to proceed — it only demands a pause/replan/escalation. `drift_findings` therefore
ALWAYS runs the hard predicates first. Weights and thresholds are explicit
arguments (versioned config), never hardcoded policy.

Governance tooling only; product runtime must never import it (INV-0006-46).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, DRIFT_BANDS, HARD_DRIFT_TRIGGERS,
                    GOAL_DRIFT_OBSERVED, HARD_GOAL_DRIFT)
from .canon import core_hash, target_fingerprint

DEFAULT_THRESHOLDS = {"DRIFT_OBSERVED": 0.1, "PAUSE_AND_REPLAN": 0.3,
                      "BLOCK_AND_ESCALATE": 0.6}
_SOFT_COMPONENTS = ("scope", "constraint", "outcome_predicate", "capability",
                    "dependency", "budget", "purpose_context")
_BAND_RANK = {b: i for i, b in enumerate(DRIFT_BANDS)}


def _as_set(v) -> set:
    if isinstance(v, (list, set, tuple)):
        return {str(x) for x in v}
    if v is None:
        return set()
    return {str(v)}


def scope_jaccard(s0, st) -> float:
    """Jaccard DISTANCE 1 - |∩|/|∪| between two scope sets. Both-empty is 0.0 by
    definition (identical, no drift) rather than an undefined 0/0 (D-0006-45)."""
    a, b = _as_set(s0), _as_set(st)
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return 1.0 - len(a & b) / len(union)


def _hard(trigger: str, subject: str, message: str, details: dict) -> Finding:
    d = {"trigger": trigger}
    d.update(details)
    return Finding(HARD_GOAL_DRIFT, P0, subject, message, d)


def hard_drift(baseline: dict, current: dict) -> list[Finding]:
    """Evaluate every HARD_DRIFT_TRIGGER. Each fired trigger yields a
    HARD_GOAL_DRIFT (P0) naming the trigger in details."""
    baseline = baseline or {}
    current = current or {}
    subj = str(current.get("work_order_id") or baseline.get("work_order_id")
               or "-")
    out: list[Finding] = []

    # tenant
    if baseline.get("tenant_id") != current.get("tenant_id"):
        out.append(_hard("tenant", subj, "tenant identity changed",
                         {"baseline": baseline.get("tenant_id"),
                          "current": current.get("tenant_id")}))
    # privacy purpose
    if baseline.get("privacy_purpose") != current.get("privacy_purpose"):
        out.append(_hard("purpose", subj, "privacy purpose changed",
                         {"baseline": baseline.get("privacy_purpose"),
                          "current": current.get("privacy_purpose")}))
    # target (material fingerprint)
    if target_fingerprint(baseline) != target_fingerprint(current):
        out.append(_hard("target", subj, "action target materially changed", {}))
    # forbidden-scope entry: current scope intersects baseline forbidden scope
    cur_scope = _as_set(current.get("allowed_scope")
                        or current.get("scope"))
    forbidden = _as_set(baseline.get("forbidden_scope"))
    breach = cur_scope & forbidden
    if breach:
        out.append(_hard("forbidden_scope", subj,
                         "current scope entered baseline forbidden scope",
                         {"entered": sorted(breach)}))
    # capability ceiling exceeded
    exceeded = _as_set(current.get("capability_ceiling")) \
        - _as_set(baseline.get("capability_ceiling"))
    if _as_set(baseline.get("capability_ceiling")) and exceeded:
        out.append(_hard("capability_ceiling", subj,
                         "requested capability exceeds baseline ceiling",
                         {"exceeded": sorted(exceeded)}))
    # silent outcome redefinition: contract hash changed without approved replan
    if core_hash(baseline.get("outcome_contract")) \
            != core_hash(current.get("outcome_contract")):
        # only an explicit boolean True is an approved replan; a truthy string
        # like "false" must NOT suppress the trigger (SWARM-M E5)
        if current.get("approved_replan") is not True:
            out.append(_hard("outcome_redefinition", subj,
                             "outcome contract redefined without approved replan",
                             {}))
    # hard constraint removed
    removed = _as_set(baseline.get("hard_constraints")) \
        - _as_set(current.get("hard_constraints"))
    if removed:
        out.append(_hard("hard_constraint_removed", subj,
                         "a hard constraint was removed",
                         {"removed": sorted(removed)}))
    # approval context changed
    if baseline.get("approval_context") != current.get("approval_context"):
        out.append(_hard("approval_context", subj,
                         "approval context changed", {}))
    return out


def _constraint_deviation(baseline, current) -> float:
    return scope_jaccard(baseline.get("constraints"), current.get("constraints"))


def _outcome_predicate_distance(baseline, current) -> float:
    def preds(w):
        return {core_hash(p) for p in (w.get("outcome_predicates") or [])}
    a, b = preds(baseline), preds(current)
    if not a and not b:
        return 0.0
    return 1.0 - len(a & b) / len(a | b)


def _capability_expansion(baseline, current) -> float:
    base = _as_set(baseline.get("capability_ceiling"))
    cur = _as_set(current.get("capability_ceiling"))
    added = cur - base
    union = base | cur
    if not union:
        return 0.0
    return len(added) / len(union)


def _dependency_edit_ratio(baseline, current) -> float:
    a = _as_set(baseline.get("dependency_edges"))
    b = _as_set(current.get("dependency_edges"))
    if not a and not b:
        return 0.0
    return len(a ^ b) / len(a | b)


def _budget_deviation(baseline, current) -> float:
    bb = baseline.get("budget") or {}
    cb = current.get("budget") or {}
    if not isinstance(bb, dict) or not isinstance(cb, dict):
        return 0.0
    keys = set(bb) | set(cb)
    if not keys:
        return 0.0
    total = 0.0
    for k in keys:
        b0 = bb.get(k)
        b1 = cb.get(k)
        if isinstance(b0, (int, float)) and isinstance(b1, (int, float)):
            denom = max(abs(b0), abs(b1), 1.0)
            total += min(abs(b1 - b0) / denom, 1.0)
        elif b0 != b1:
            total += 1.0
    return total / len(keys)


def _purpose_context_deviation(baseline, current) -> float:
    if baseline.get("privacy_purpose") != current.get("privacy_purpose"):
        return 1.0
    return scope_jaccard(baseline.get("purpose_context"),
                         current.get("purpose_context"))


def _normalize_weights(weights) -> dict:
    if weights is None:
        n = len(_SOFT_COMPONENTS)
        return {k: 1.0 / n for k in _SOFT_COMPONENTS}
    w = {k: float(weights.get(k, 0.0)) for k in _SOFT_COMPONENTS}
    for k, v in w.items():
        if v < 0:
            raise ValueError(f"weight {k} must be >= 0, got {v}")
    total = sum(w.values())
    if total <= 0:
        raise ValueError("weights sum must be > 0")
    return {k: v / total for k, v in w.items()}   # enforce Σwᵢ = 1


def _band_for(score: float, thresholds: dict) -> str:
    if score >= thresholds["BLOCK_AND_ESCALATE"]:
        return "BLOCK_AND_ESCALATE"
    if score >= thresholds["PAUSE_AND_REPLAN"]:
        return "PAUSE_AND_REPLAN"
    if score >= thresholds["DRIFT_OBSERVED"]:
        return "DRIFT_OBSERVED"
    return "ALIGNED"


def soft_drift(baseline: dict, current: dict, *, weights: dict | None = None,
               thresholds: dict | None = None) -> dict:
    """Bounded weighted soft-drift metric D = Σ wᵢ·dᵢ with Σwᵢ = 1, wᵢ >= 0
    (D-0006-44). Returns {score, band, components}. Thresholds are versioned
    config; the default band edges are DEFAULT_THRESHOLDS."""
    baseline = baseline or {}
    current = current or {}
    thresholds = thresholds or DEFAULT_THRESHOLDS
    w = _normalize_weights(weights)
    components = {
        "scope": scope_jaccard(baseline.get("allowed_scope"),
                               current.get("allowed_scope")),
        "constraint": _constraint_deviation(baseline, current),
        "outcome_predicate": _outcome_predicate_distance(baseline, current),
        "capability": _capability_expansion(baseline, current),
        "dependency": _dependency_edit_ratio(baseline, current),
        "budget": _budget_deviation(baseline, current),
        "purpose_context": _purpose_context_deviation(baseline, current),
    }
    score = sum(w[k] * components[k] for k in _SOFT_COMPONENTS)
    return {"score": score, "band": _band_for(score, thresholds),
            "components": components, "weights": w}


def drift_findings(baseline: dict, current: dict, *, weights: dict | None = None,
                   thresholds: dict | None = None) -> list[Finding]:
    """Hard predicates FIRST (P0), then the soft metric. A soft score can neither
    clear a hard block nor, on its own, authorize continuation (INV-0006-28/29):
    it maps only to advisory (P2) or, at PAUSE_AND_REPLAN and above, a blocking
    P1 demand to stop and replan."""
    out: list[Finding] = list(hard_drift(baseline, current))
    soft = soft_drift(baseline, current, weights=weights, thresholds=thresholds)
    band = soft["band"]
    subj = str((current or {}).get("work_order_id")
               or (baseline or {}).get("work_order_id") or "-")
    if band != "ALIGNED":
        sev = P1 if _BAND_RANK[band] >= _BAND_RANK["PAUSE_AND_REPLAN"] else P2
        out.append(Finding(GOAL_DRIFT_OBSERVED, sev, subj,
                           f"soft goal drift {soft['score']:.3f} in band {band}",
                           {"score": soft["score"], "band": band,
                            "components": soft["components"]}))
    return out
