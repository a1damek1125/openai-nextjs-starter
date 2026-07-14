"""Detector registry, capability matrix, and common-mode / diversity analysis
(SP0008 §7, D-0008-09/10).

A detector is not merely a function; it is a declared instrument with a KNOWN
method, a set of surface kinds it can see, and declared blind spots. When two
detectors agree on a surface, that agreement only COUNTS as corroboration if the
detectors are genuinely independent — different methods with different blind
spots (DIVERSITY_REAL). Two detectors sharing a method (both pure-AST-literal,
say) that agree tell you nothing new (DIVERSITY_COSMETIC). This module makes the
distinction explicit so the residual estimator and the confidence story are not
fooled by correlated instruments.
"""
from __future__ import annotations

from typing import Iterable

from .discover import DETECTORS, BLIND_SPOTS
from .model import (Finding, P2, DIVERSITY_REAL, DIVERSITY_PARTIAL,
                    DIVERSITY_COSMETIC, DETECTOR_COMMON_MODE)

# capability matrix: detector -> (method, surface kinds it can materialize)
CAPABILITY = {
    "http_routes": {"method": "AST_DECORATOR_AND_CALL",
                    "kinds": ("HTTP_ROUTE",)},
    "db_migrations": {"method": "AST_LIST_PLUS_SQL_REGEX",
                      "kinds": ("DB_MIGRATION", "DB_TABLE")},
    "run_ledger_events": {"method": "AST_DICT_KEYS",
                          "kinds": ("RUN_LEDGER_EVENT",)},
    "audit_events": {"method": "AST_CALL_KWARG_LITERAL",
                     "kinds": ("AUDIT_EVENT",)},
    "state_machines": {"method": "AST_ENUM_CLASS",
                       "kinds": ("STATE_MACHINE", "STATE_TRANSITION")},
    "proof_artifacts": {"method": "AST_FUNCTION_NAME",
                        "kinds": ("PROOF_ARTIFACT",)},
    "proof_versions": {"method": "AST_ASSIGN_STRING_REGEX",
                       "kinds": ("PROOF_ARTIFACT",)},
    "config_keys": {"method": "AST_ENV_ACCESS",
                    "kinds": ("CONFIG_KEY",)},
    "declared_config": {"method": "TEXT_ENV_FILE",
                        "kinds": ("CONFIG_KEY",)},
    "cli_commands": {"method": "AST_ADD_PARSER",
                     "kinds": ("CLI_COMMAND",)},
}


def detector_names() -> list:
    return [name for name, _ in DETECTORS]


def blind_spots() -> list:
    return list(BLIND_SPOTS)


def _blind_by_detector() -> dict:
    out: dict[str, list] = {}
    for bs in BLIND_SPOTS:
        out.setdefault(bs["detector"], []).append(bs["blind_to"])
    return out


def diversity(det_a: str, det_b: str) -> str:
    """Grade the diversity of two detectors. Same method => COSMETIC; same kinds
    but different method with overlapping blind spots => PARTIAL; genuinely
    different method and disjoint blind spots => REAL."""
    ca, cb = CAPABILITY.get(det_a, {}), CAPABILITY.get(det_b, {})
    if not ca or not cb:
        return DIVERSITY_PARTIAL
    if ca["method"] == cb["method"]:
        return DIVERSITY_COSMETIC
    # different methods: REAL unless they share every kind AND both under-report
    blind = _blind_by_detector()
    a_blind = bool(blind.get(det_a))
    b_blind = bool(blind.get(det_b))
    shared_kinds = set(ca["kinds"]) & set(cb["kinds"])
    if shared_kinds and a_blind and b_blind:
        return DIVERSITY_PARTIAL
    return DIVERSITY_REAL


def corroboration(observations: Iterable, *, surface_id: str) -> dict:
    """For a surface, classify the detectors that saw it and whether their
    agreement is real corroboration or common-mode."""
    dets = sorted({o.detector for o in observations
                   if o.surface_id == surface_id})
    if len(dets) < 2:
        return {"detectors": dets, "corroboration": "SINGLE_DETECTOR",
                "diversity": None}
    grades = set()
    for i in range(len(dets)):
        for j in range(i + 1, len(dets)):
            grades.add(diversity(dets[i], dets[j]))
    if DIVERSITY_REAL in grades:
        level = "REAL_CORROBORATION"
    elif DIVERSITY_PARTIAL in grades:
        level = "PARTIAL_CORROBORATION"
    else:
        level = "COMMON_MODE_ONLY"
    return {"detectors": dets, "corroboration": level,
            "diversity": sorted(grades)}


def common_mode_findings(observations: Iterable, surfaces) -> list[Finding]:
    """Flag surfaces whose ONLY corroboration is common-mode (agreement that is
    not independent evidence)."""
    out: list[Finding] = []
    obs = list(observations)
    for s in surfaces:
        c = corroboration(obs, surface_id=s.surface_id)
        if c["corroboration"] == "COMMON_MODE_ONLY":
            out.append(Finding(
                DETECTOR_COMMON_MODE, P2, s.surface_id,
                "surface seen by multiple detectors that share a method; their "
                "agreement is common-mode, not independent corroboration",
                {"detectors": c["detectors"]}))
    return out


def global_diversity_ok(observations: Iterable) -> bool:
    """The detector fleet as a whole is diverse enough for capture-recapture if
    at least one pair of active detectors is DIVERSITY_REAL."""
    active = sorted({o.detector for o in observations})
    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            if diversity(active[i], active[j]) == DIVERSITY_REAL:
                return True
    return False
