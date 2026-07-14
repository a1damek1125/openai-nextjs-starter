"""Residual unseen-surface estimation via capture-recapture (SP0008 §residual,
D-0008-34/35).

Multiple independent detectors are the "capture occasions". A surface seen by
many detectors is like a re-captured animal; a surface seen by exactly one is a
singleton. The Chao1 lower-bound estimator uses the singleton (Q1) and doubleton
(Q2) counts to estimate the number of surfaces NOT seen by any detector:

    S_hat = S_obs + Q1*(Q1-1) / (2*(Q2+1))

This is ADVISORY ONLY (D-0008-35): it is a lower bound on richness, never a proof
of completeness. The inventory reports S_obs, the estimate, and the residual gap,
and explicitly labels it non-authoritative. Detector diversity is a precondition
— if detectors are not independent (common-mode), the estimate is unreliable and
that caveat is emitted alongside it.
"""
from __future__ import annotations

from typing import Iterable

from .model import Finding, P2, RESIDUAL_SURFACE_ESTIMATED


def detection_frequencies(observations: Iterable) -> dict:
    """For each surface_id, how many DISTINCT detectors saw it."""
    by_surface: dict[str, set] = {}
    for o in observations:
        by_surface.setdefault(o.surface_id, set()).add(o.detector)
    return {sid: len(dets) for sid, dets in by_surface.items()}


def _estimable_kinds(observations: Iterable) -> tuple:
    """A surface KIND is estimable by capture-recapture only if >=2 DISTINCT
    detectors are capable of observing it — otherwise a surface seen by one
    detector is not a statistical 'singleton', it was simply seen by the only
    instrument that could see it, and Chao1's assumptions are violated."""
    det_by_kind: dict[str, set] = {}
    kind_by_surface: dict[str, str] = {}
    for o in observations:
        det_by_kind.setdefault(o.surface_kind, set()).add(o.detector)
        kind_by_surface[o.surface_id] = o.surface_kind
    estimable = {k for k, dets in det_by_kind.items() if len(dets) >= 2}
    excluded = {k for k in det_by_kind if k not in estimable}
    return estimable, excluded, kind_by_surface


# minimum fraction of the population that must be RECAPTURED (seen by >=2
# detectors) for Chao1 to have a controlled variance. Below this the estimator
# is degenerate and the residual is honestly reported as NOT estimable.
MIN_RECAPTURE_FRACTION = 0.05


def chao1(observations: Iterable) -> dict:
    """Chao1 lower-bound richness estimate — but ONLY when the detector fleet
    actually produces recaptures.

    Capture-recapture is meaningful only if some surfaces are observed by >=2
    INDEPENDENT detectors. When detectors partition the surface space (each
    surface seen by exactly one detector, as a kind-specialized fleet does),
    there is no recapture, Chao1 is undefined/unbounded, and the residual is
    genuinely UNKNOWN — we say so rather than emit a spurious number
    (D-0008-35; UNKNOWN is a first-class result)."""
    observations = list(observations)
    freq = detection_frequencies(observations)
    s_obs = len(freq)
    recaptured = sum(1 for c in freq.values() if c >= 2)
    recapture_fraction = (recaptured / s_obs) if s_obs else 0.0
    q1 = sum(1 for c in freq.values() if c == 1)
    q2 = sum(1 for c in freq.values() if c == 2)

    estimable = recapture_fraction >= MIN_RECAPTURE_FRACTION
    if estimable:
        residual = q1 * (q1 - 1) / (2 * (q2 + 1))
        s_hat = s_obs + residual
    else:
        residual = None
        s_hat = None

    return {
        "s_observed": s_obs,
        "recaptured_surfaces": recaptured,
        "recapture_fraction": round(recapture_fraction, 4),
        "singletons_q1": q1,
        "doubletons_q2": q2,
        "estimable": estimable,
        "estimated_residual_unseen": residual,
        "s_hat_lower_bound": s_hat,
        "advisory_only": True,
        "note": ("Chao1 lower bound (advisory, not a completeness proof, "
                 "D-0008-35)" if estimable else
                 "NOT ESTIMABLE: detector fleet is kind-partitioned with "
                 f"effective recapture {recapture_fraction:.1%} < "
                 f"{MIN_RECAPTURE_FRACTION:.0%}; residual is UNKNOWN, not zero"),
    }


def saturation_curve(observations: Iterable, detector_order: list) -> list:
    """Discovery saturation: cumulative distinct surfaces as detectors are added
    in a fixed order. A curve still climbing at the last detector is evidence the
    universe is not yet saturated."""
    seen: set = set()
    curve = []
    per_detector: dict[str, set] = {}
    for o in observations:
        per_detector.setdefault(o.detector, set()).add(o.surface_id)
    for det in detector_order:
        seen |= per_detector.get(det, set())
        curve.append({"detector": det, "cumulative_surfaces": len(seen)})
    return curve


def residual_findings(estimate: dict, *, diversity_ok: bool) -> list[Finding]:
    out: list[Finding] = []
    if estimate["estimable"] and (estimate["estimated_residual_unseen"] or 0) > 0:
        out.append(Finding(
            RESIDUAL_SURFACE_ESTIMATED, P2, "INVENTORY",
            f"capture-recapture estimates ~"
            f"{estimate['estimated_residual_unseen']:.1f} unseen surface(s) "
            f"beyond the {estimate['s_observed']} observed (advisory lower "
            "bound, not a completeness proof)",
            {"estimate": estimate, "detector_diversity_ok": diversity_ok}))
    elif not estimate["estimable"]:
        out.append(Finding(
            RESIDUAL_SURFACE_ESTIMATED, P2, "INVENTORY",
            "residual unseen-surface count is NOT estimable: the detector fleet "
            f"is kind-partitioned (effective recapture "
            f"{estimate['recapture_fraction']:.1%}); the residual is UNKNOWN, "
            "not zero — completeness must be argued from the declared universe "
            "and blind-spot registry, not from capture-recapture",
            {"estimate": estimate}))
    if not diversity_ok:
        out.append(Finding(
            RESIDUAL_SURFACE_ESTIMATED, P2, "INVENTORY",
            "detectors are not sufficiently independent (common-mode); the "
            "capture-recapture estimate is unreliable and must not be read as "
            "a bound", {"estimate": estimate}))
    return out
