"""Bayesian / empirical forecast layer + Monte Carlo criticality (SP0003
D-0003-18..23, §11.9..§11.13).

This layer is SEPARATE from canonical hard dependencies (D-0003-21, INV-0003-13):
it may update duration distributions, rework probability and criticality index
from new execution evidence, but it can NEVER create/remove a hard dependency or
change a gate. Bayesian updates admit ONLY comparable, provenance-backed
observations of the same similarity class (D-0003-19, §11.10) — otherwise
OBSERVATION_NOT_COMPARABLE. Monte Carlo is advisory and fully reproducible from a
declared seed (D-0003-22/§11.11, AC-0003-52).
"""
from __future__ import annotations

import random

from .model import (Finding, P1, DURATION_MODES, ESTIMATED_MODES,
                    INVALID_DURATION_MODEL, INCOMPARABLE_DURATION_EVIDENCE,
                    FORECAST_MODEL_STALE)
from .graphalgo import precedence_pairs, node_ids, topo_order, adjacency
from .hypergraph import default_active
from .criticality import cpm


def validate_duration_model(dm: dict) -> list[Finding]:
    out: list[Finding] = []
    mid = dm.get("duration_model_id", "-")
    mode = dm.get("mode")
    if mode not in DURATION_MODES:
        out.append(Finding(INVALID_DURATION_MODEL, P1, mid,
                           f"invalid duration mode {mode!r}", {}))
    if mode in ESTIMATED_MODES and not dm.get("parameters"):
        out.append(Finding(INVALID_DURATION_MODEL, P1, mid,
                           f"mode {mode} requires parameters", {}))
    return out


def observation_comparable(model: dict, obs: dict) -> tuple[bool, str]:
    """Admission gate for a Bayesian/empirical update (§11.10). An observation may
    update a model only if same similarity class, defined provenance, and defined
    duration boundaries + blocked-time treatment."""
    if not obs.get("provenance"):
        return False, "missing provenance"
    if obs.get("similarity_class") != model.get("similarity_class"):
        return False, "similarity class mismatch"
    if obs.get("boundary") != model.get("boundary", obs.get("boundary")):
        # boundaries must be consistently defined; if model declares one, match it
        if model.get("boundary") is not None and \
                obs.get("boundary") != model.get("boundary"):
            return False, "duration boundary definition mismatch"
    if "blocked_time_policy" in model and \
            obs.get("blocked_time_policy") != model.get("blocked_time_policy"):
        return False, "blocked-time treatment mismatch"
    return True, "ok"


def admit_observations(model: dict, observations: list[dict]):
    """Return (admitted, findings). Incomparable observations are rejected with
    INCOMPARABLE_DURATION_EVIDENCE (AC-0003-48) — never silently folded in."""
    admitted: list[dict] = []
    findings: list[Finding] = []
    for obs in observations:
        ok, why = observation_comparable(model, obs)
        if ok:
            admitted.append(obs)
        else:
            findings.append(Finding(INCOMPARABLE_DURATION_EVIDENCE, P1,
                                    model.get("duration_model_id", "-"),
                                    f"observation rejected: {why}",
                                    {"observation": obs}))
    return admitted, findings


def numeric_durations(program: dict) -> dict[str, float]:
    """Point durations for nodes that carry a real estimate; UNKNOWN excluded
    (never fabricated, D-0003-11)."""
    out: dict[str, float] = {}
    for dm in program.get("duration_models", []):
        if dm.get("mode") in ESTIMATED_MODES:
            p = dm.get("parameters", {})
            val = p.get("mode") or p.get("mean") or p.get("point")
            if val is not None and dm.get("node_id"):
                out[dm["node_id"]] = float(val)
    return out


def _sample_duration(dm: dict, rng: random.Random) -> float:
    p = dm.get("parameters", {})
    mode = dm.get("mode")
    if mode == "THREE_POINT_ESTIMATE":
        a = float(p.get("optimistic", p.get("min", 1)))
        m = float(p.get("mode", p.get("most_likely", a)))
        b = float(p.get("pessimistic", p.get("max", m)))
        # PERT-ish triangular sample (deterministic given rng)
        return rng.triangular(a, b, m)
    if mode in ("EXPERT_POINT_ESTIMATE",):
        return float(p.get("point", p.get("mode", 1)))
    if mode in ("EMPIRICAL_DISTRIBUTION", "BAYESIAN_POSTERIOR"):
        obs = p.get("observations")
        if obs:
            return float(rng.choice(obs))
        return float(p.get("mean", 1))
    return float(p.get("mode", p.get("point", 1)))


def monte_carlo_criticality(program: dict, *, samples: int, seed: int,
                            active=default_active) -> dict:
    """Sample durations, compute the critical set each draw, and return the
    Criticality Index CI(v) = (1/N) sum I(v in CriticalSet_s) (§11.11/§11.12).
    Fully reproducible from (samples, seed, inputs) — reports all three
    (AC-0003-52)."""
    dms = {dm["node_id"]: dm for dm in program.get("duration_models", [])
           if dm.get("node_id")}
    counts = {n["node_id"]: 0 for n in program.get("nodes", [])}
    completion: list[float] = []
    for s in range(samples):
        rng = random.Random((seed << 20) ^ s)   # per-draw deterministic stream
        durs = {nid: _sample_duration(dm, rng) for nid, dm in dms.items()}
        res = cpm(program, durs, active)
        if "error" in res:
            return {"error": res["error"]}
        for n in res["critical_nodes"]:
            counts[n] += 1
        completion.append(res["project_duration"])
    ci = {n: round(c / samples, 6) for n, c in counts.items()} if samples else {}
    completion_sorted = sorted(completion)
    return {
        "samples": samples, "seed": seed,
        "input_model_version": program.get("duration_model_version", "1"),
        "criticality_index": ci,
        "completion_min": round(min(completion), 6) if completion else None,
        "completion_max": round(max(completion), 6) if completion else None,
        "completion_p50": round(completion_sorted[len(completion_sorted)//2], 6)
        if completion else None,
        "criticality_concentration": _entropy(ci),
    }


def _entropy(ci: dict) -> float | None:
    """Descriptive concentration measure (§11.13) — NOT a gate."""
    import math
    total = sum(ci.values())
    if total <= 0:
        return None
    h = 0.0
    for v in ci.values():
        if v > 0:
            p = v / total
            h -= p * math.log(p)
    return round(h, 6)


def forecast_staleness(program: dict) -> list[Finding]:
    """A forecast model flagged STALE surfaces an advisory (never a hard block,
    D-0003-42)."""
    out: list[Finding] = []
    for dm in program.get("duration_models", []):
        if dm.get("lifecycle") == "STALE":
            out.append(Finding(FORECAST_MODEL_STALE, P1,
                               dm.get("duration_model_id", "-"),
                               "forecast model is STALE (advisory)", {}))
    return out
