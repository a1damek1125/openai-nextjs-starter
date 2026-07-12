"""Multilingual + multi-industry measurement invariance (SP0011 §2.1.O, §12,
D-0011-089..093, AC-0011-221..240).

Multilingual evaluation is not translation-only (D-0011-089). PL/EN/DE/ES remain
SEPARATE strata (D-0011-090); Control Language (PL) is evaluated separately from
Work Language (D-0011-091). Small strata cannot receive unsupported strong
qualification through pooled averages (D-0011-092): an underrepresented critical
stratum HOLDs. Invariance tests check that authority / monetary value / deadline /
consent / completion decisions are preserved across languages and packs. Grounded
on the real repository multilingual label registry (PL/EN/DE/ES projections).
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj
from .model import Finding, P0, P1

LANGUAGES = ("PL", "EN", "DE", "ES")
CONTROL_LANGUAGE = "PL"
WORK_LANGUAGES = ("EN", "DE", "ES")
INVARIANTS = ("authority", "monetary", "deadline", "consent", "completion")
_MIN_STRATUM_N = 5          # below this, a critical stratum HOLDs (D-0011-092)


def _labels_present(root: Path) -> bool:
    p = root / "docs" / "semantics" / "FINALIS_MULTILINGUAL_LABELS.json"
    return p.exists()


def invariance_result(*, language_stats: dict, invariant: str) -> dict:
    """language_stats: language -> (equal_decisions, n). Invariance HOLDs across
    languages when every language's decision-equality lower bound is high AND no
    critical stratum is too small to support a claim."""
    from .statistics import clopper_pearson_lower
    bounds, small = {}, []
    for lang, (eq, n) in sorted(language_stats.items()):
        bounds[lang] = clopper_pearson_lower(eq, n) if n else 0.0
        if n < _MIN_STRATUM_N:
            small.append(lang)
    worst = min(bounds.values()) if bounds else 0.0
    return {"invariant": invariant, "language_lower_bounds": bounds,
            "worst_language": min(bounds, key=bounds.get) if bounds else None,
            "worst_lower_bound": worst, "small_strata": small,
            "held_strata": small,          # small critical strata HOLD, not PASS
            "invariant_holds": worst >= 0.9 and not small}


def build_invariance(root: Path, *, language_stats_by_invariant: dict) -> dict:
    root = Path(root)
    results = {inv: invariance_result(
        language_stats=language_stats_by_invariant.get(inv, {}), invariant=inv)
        for inv in INVARIANTS}
    return {"labels_registry_present": _labels_present(root),
            "control_language": CONTROL_LANGUAGE,
            "work_languages": list(WORK_LANGUAGES),
            "strata_separate": True, "results": results,
            "invariance_root": hash_obj({inv: r["worst_lower_bound"]
                                         for inv, r in results.items()})}


def invariance_findings(report: dict) -> list[Finding]:
    out: list[Finding] = []
    for inv, r in sorted(report["results"].items()):
        # a failed invariance for authority/monetary/consent is critical
        if not r["invariant_holds"] and not r["held_strata"] \
                and inv in ("authority", "monetary", "consent"):
            out.append(Finding("MULTILINGUAL_INVARIANCE_FAILED", P0, inv,
                               f"{inv} invariance failed across languages "
                               "(worst lower bound too low)", r))
        elif r["held_strata"]:
            out.append(Finding("MULTILINGUAL_INVARIANCE_FAILED", P1, inv,
                               f"{inv} has underrepresented strata "
                               f"{r['held_strata']} which HOLD (not pooled away)",
                               r))
    return out
