"""Deterministic scoring layer — executable form of docs/finalis-ai/05.

All functions are pure. Inputs are validated and clamped to their documented
ranges so no formula can produce an out-of-bounds or NaN result (fixes flagged
in doc 26): MIS guards Σw=0; StuckScore normalizes days and is bounded;
FollowUpPriority uses LeadScore/100 so all factors share the [0,1] scale.
"""
from __future__ import annotations

from dataclasses import dataclass


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# --- 05 §1 -----------------------------------------------------------------
def lead_score(v: float, u: float, f: float, c: float, d: float, r: float,
               weights: dict[str, float] | None = None) -> float:
    """LeadScore in [0,100]. Inputs are clamped to [0,1]."""
    w = weights or {"V": 0.30, "U": 0.20, "F": 0.15, "C": 0.15, "D": 0.10, "R": 0.10}
    total = sum(w.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"lead_score weights must sum to 1.0, got {total}")
    vals = {"V": v, "U": u, "F": f, "C": c, "D": d, "R": r}
    return 100.0 * sum(w[k] * _clamp(vals[k]) for k in w)


# --- 05 §2 -----------------------------------------------------------------
def mis(missing_flags: list[int], weights: list[float]) -> tuple[float, float]:
    """Returns (MIS, MIS_normalized). Guards the Σw=0 edge case → (0, 0)."""
    if len(missing_flags) != len(weights):
        raise ValueError("missing_flags and weights length mismatch")
    if any(w < 0 for w in weights):
        raise ValueError("weights must be non-negative")
    total_w = sum(weights)
    raw = sum(w * (1 if m else 0) for m, w in zip(missing_flags, weights))
    return raw, (raw / total_w if total_w > 0 else 0.0)


# --- 05 §3 -----------------------------------------------------------------
@dataclass
class ActionCandidate:
    name: str
    p_close: float        # [0,1]
    cost: float           # same currency unit as value
    risk: float           # currency-equivalent expected loss
    delay_penalty: float  # currency-equivalent


def nba_utility(a: ActionCandidate, value: float) -> float:
    return _clamp(a.p_close) * max(0.0, value) - a.cost - a.risk - a.delay_penalty


def next_best_action(candidates: list[ActionCandidate], value: float) -> ActionCandidate:
    if not candidates:
        raise ValueError("no candidate actions")
    # Ties break toward lower cost then lower risk (05 §3 policy).
    return max(candidates, key=lambda a: (nba_utility(a, value), -a.cost, -a.risk))


# --- 05 §4 -----------------------------------------------------------------
def followup_priority(lead: float, time_decay: float, intent_signal: float,
                      annoyance_risk: float) -> float:
    """All factors on [0,1] (lead is LeadScore/100). Output in [-1, 1]."""
    return (_clamp(lead / 100.0) * _clamp(time_decay) * _clamp(intent_signal)
            - _clamp(annoyance_risk))


# --- 05 §5 -----------------------------------------------------------------
def doc_risk(a: float, m: float, c: float, p: float, l: float, q: float) -> float:
    """DocRisk in [0,100]."""
    return 100.0 * (0.25 * _clamp(a) + 0.20 * _clamp(m) + 0.20 * _clamp(c)
                    + 0.15 * _clamp(p) + 0.10 * _clamp(l) + 0.10 * _clamp(q))


# --- 05 §6 -----------------------------------------------------------------
def evidence_confidence(ocr_q: float, extraction_q: float, source_q: float,
                        consistency_q: float) -> float:
    return (_clamp(ocr_q) * _clamp(extraction_q) * _clamp(source_q)
            * _clamp(consistency_q))


# --- 05 §7 -----------------------------------------------------------------
OFFER_WEIGHTS_DEFAULT = {"price": 0.25, "scope": 0.20, "warranty": 0.15,
                         "time": 0.15, "payment": 0.10, "risk": 0.10,
                         "service": 0.05}


def offer_score(axes: dict[str, float],
                weights: dict[str, float] | None = None) -> float:
    """OfferScore in [0,100]; missing axes score 0 (worst) rather than crash."""
    w = weights or OFFER_WEIGHTS_DEFAULT
    total = sum(w.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"offer weights must sum to 1.0, got {total}")
    return 100.0 * sum(w[k] * _clamp(axes.get(k, 0.0)) for k in w)


def normalize_prices(prices: list[float]) -> list[float]:
    """Price axis within a comparison set: cheapest→1.0. Guards single/zero."""
    if not prices:
        return []
    positive = [p for p in prices if p > 0]
    if not positive:
        return [0.0 for _ in prices]
    cheapest = min(positive)
    return [(cheapest / p) if p > 0 else 0.0 for p in prices]


# --- 05 §8 -----------------------------------------------------------------
def escalation_score(risk: float, value_criticality: float, low_confidence: float,
                     client_emotion: float, legal_sensitivity: float,
                     unusual_request: float) -> float:
    """Additive severity accumulator; each term clamped to [0,1]; range [0,6]."""
    return sum(_clamp(t) for t in (risk, value_criticality, low_confidence,
                                   client_emotion, legal_sensitivity,
                                   unusual_request))


def must_escalate(score: float, *, theta: float = 1.5,
                  legal_signing: bool = False,
                  safety_emergency: bool = False) -> bool:
    """05 §8 threshold + the two hard overrides (13 §2)."""
    return legal_signing or safety_emergency or score >= theta


# --- 05 §9 -----------------------------------------------------------------
def stuck_score(days_since_progress: float, lead: float,
                missing_blocker_weight: float, *,
                days_cap: float = 30.0) -> float:
    """Bounded StuckScore in [0,100]: days normalized by cap (doc 26 fix)."""
    d = _clamp(days_since_progress / days_cap) if days_cap > 0 else 1.0
    return 100.0 * d * _clamp(lead / 100.0) * _clamp(missing_blocker_weight)


# --- 05 §10 ----------------------------------------------------------------
def promise_breach_score(importance: float, delay_hours: float,
                         dependency_impact: float, *,
                         expected_window_hours: float = 72.0) -> float:
    """Bounded in [0,1]: delay normalized by expected window (doc 26 fix)."""
    delay_n = _clamp(delay_hours / expected_window_hours) \
        if expected_window_hours > 0 else 1.0
    return _clamp(importance) * delay_n * _clamp(dependency_impact)


# --- 05 §11 ----------------------------------------------------------------
def source_trust(authority: float, recency: float, corroboration: float,
                 directness: float, transparency: float) -> float:
    """SourceTrust in [0,100]."""
    return 100.0 * (0.35 * _clamp(authority) + 0.25 * _clamp(recency)
                    + 0.20 * _clamp(corroboration) + 0.15 * _clamp(directness)
                    + 0.05 * _clamp(transparency))


# --- 05 §10b ---------------------------------------------------------------
def case_risk_score(max_open_riskflag_severity: float, doc_risk_max: float,
                    escalation: float, *, theta_escalate: float = 1.5) -> float:
    """CaseRiskScore in [0,100] — roll-up per 05 §10b."""
    return 100.0 * max(
        0.6 * _clamp(max_open_riskflag_severity),
        0.4 * _clamp(doc_risk_max / 100.0),
        _clamp(escalation / theta_escalate),
    )
