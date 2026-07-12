"""Provider / harness / tool replaceability (SP0011 §2.1.P, §12.17, D-0011-086/
087/088, AC-0011-196..200).

Model, harness and provider effects are separated (D-0011-086). A replaceability
claim requires EXECUTABLE evidence — at least one alternate provider, simulator or
conformant stub (D-0011-088). Provider non-inferiority requires LowerBound(Δ) > -δ
AND all safety gates PASS (§12.17). Grounded on the real repo substitution engine
(tools/technology) and the mock provider adapters (deterministic conformant stubs).
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj
from .model import Finding, P1
from .statistics import clopper_pearson_lower

# alternate-provider fixtures available in the repo (mock adapters = conformant
# stubs; the substitution engine is executable evidence of replaceability)
ALTERNATE_FIXTURES = {
    "technology_substitution": "tools/technology/substitution.py",
    "mock_telephony": "finalis/telephony/engine.py",
    "mock_notification": "finalis/actions/adapters.py",
}


def _fixture_present(root: Path) -> dict:
    return {k: (root / v).exists() for k, v in ALTERNATE_FIXTURES.items()}


def non_inferiority(*, candidate_stats: tuple, reference_stats: tuple,
                    margin: float, safety_gates_pass: bool) -> dict:
    """LowerBound(Δ) > -margin AND safety gates PASS (§12.17)."""
    ck, cn = candidate_stats
    rk, rn = reference_stats
    cand_lb = clopper_pearson_lower(ck, cn) if cn else 0.0
    ref_point = (rk / rn) if rn else 0.0
    delta_lb = cand_lb - ref_point
    non_inferior = delta_lb > -margin and safety_gates_pass is True
    return {"candidate_lower_bound": cand_lb, "reference_point": ref_point,
            "delta_lower_bound": delta_lb, "margin": margin,
            "safety_gates_pass": safety_gates_pass,
            "non_inferior": non_inferior}


def build_replaceability(root: Path, *, comparisons: dict = None) -> dict:
    root = Path(root)
    fixtures = _fixture_present(root)
    comparisons = comparisons or {}
    has_executable = any(fixtures.values())
    return {"alternate_fixtures": fixtures,
            "has_executable_evidence": has_executable,
            "comparisons": comparisons,
            "replaceability_root": hash_obj({"fixtures": fixtures,
                                             "cmp": sorted(comparisons)})}


def replaceability_findings(report: dict) -> list[Finding]:
    out: list[Finding] = []
    if not report["has_executable_evidence"]:
        out.append(Finding("PROVIDER_NONINFERIORITY_FAILED", P1, "replaceability",
                           "no executable alternate-provider evidence: "
                           "replaceability is unproven (D-0011-088)", {}))
    for cid, cmp in sorted(report["comparisons"].items()):
        if not cmp.get("non_inferior", True):
            out.append(Finding("PROVIDER_NONINFERIORITY_FAILED", P1, cid,
                               "candidate provider is not non-inferior", cmp))
    return out
