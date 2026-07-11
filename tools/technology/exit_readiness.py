"""Exit Readiness + Provider Substitution Drills (SP0004 D-0004-38/39/40/41,
§10.7/§11.13, INV-0004-12/13).

Exit readiness is measured by EVIDENCE across eight dimensions (data/state export,
adapter portability, replacement availability, replay coverage, rollback,
operational, documentation) — never a bare `replaceable=true` (D-0004-39). A
critical (T3/T4) dependency without an exit plan FAILS (INV-0004-12,
AC-0004-079). A missing critical data export is a HARD blocker regardless of any
averaged score (D-0004-40, §12.6). Finalis-owned business state must never live
only in provider-owned history (INV-0004-13).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, EXIT_DIMENSIONS,
                    CRITICAL_DEPENDENCY_WITHOUT_EXIT_PLAN, DATA_EXPORT_GAP,
                    EXIT_PLAN_MISSING, BUSINESS_STATE_PROVIDER_ONLY)

# drill levels (D-0004-41) and the minimum level required per criticality
DRILL_LEVELS = ["D0", "D1", "D2", "D3", "D4", "D5"]
MIN_DRILL = {"T0": "D0", "T1": "D0", "T2": "D1", "T3": "D3", "T4": "D4"}

READINESS_ORDER = {"UNKNOWN": 0, "DOCUMENTED": 1, "EXPORT_VALIDATED": 2,
                   "SUBSTITUTE_VALIDATED": 3, "DRILLED": 4, "STALE": 0,
                   # per-dimension scalar states
                   "NONE": 0, "PARTIAL": 1, "FULL": 2, "VERIFIED": 3}

# an export dimension counts as a REAL export only when validated — a bare
# DOCUMENTED / PARTIAL / STALE / UNKNOWN / NONE is a gap (red-team F4,
# INV-0004-10: an interface on paper does not prove replaceability).
VALIDATED_EXPORT = {"EXPORT_VALIDATED", "SUBSTITUTE_VALIDATED", "DRILLED",
                    "FULL", "VERIFIED"}


def profile_for(profiles: list[dict], tech_id: str) -> dict | None:
    for p in profiles:
        if p.get("technology_id") == tech_id:
            return p
    return None


def evaluate_exit(inventory: dict, exit_profiles: list[dict]) -> list[Finding]:
    """Every T3/T4 technology must have an exit profile with, at minimum, a data
    export path (INV-0004-12/13)."""
    out: list[Finding] = []
    for t in inventory.get("technologies", []):
        if t.get("criticality") not in ("T3", "T4"):
            continue
        tid = t["technology_id"]
        prof = profile_for(exit_profiles, tid)
        if prof is None:
            out.append(Finding(CRITICAL_DEPENDENCY_WITHOUT_EXIT_PLAN, P0, tid,
                               f"critical dependency {tid!r} has no exit readiness "
                               "profile (AC-0004-079)", {}))
            continue
        if prof.get("data_export", "UNKNOWN") not in VALIDATED_EXPORT:
            out.append(Finding(DATA_EXPORT_GAP, P0, tid,
                               f"critical dependency {tid!r} has no VALIDATED data "
                               f"export (state={prof.get('data_export')!r}; "
                               "DOCUMENTED/PARTIAL/STALE is not enough, "
                               "AC-0004-080)", {}))
        # business-state-bearing tech must not be provider-only
        if t.get("holds_business_state") and \
                prof.get("state_export", "UNKNOWN") not in VALIDATED_EXPORT:
            out.append(Finding(BUSINESS_STATE_PROVIDER_ONLY, P0, tid,
                               f"{tid!r} holds Finalis business state but has no "
                               "VALIDATED state export (INV-0004-13)", {}))
        # T3/T4 must have a substitution drill at the required level (D-0004-41)
        drill = prof.get("last_drill_level", "D0")
        if not drill_sufficient(t["criticality"], drill):
            out.append(Finding(EXIT_PLAN_MISSING, P1, tid,
                               f"{tid!r} ({t['criticality']}) drill level {drill} "
                               f"below required {required_drill_level(t['criticality'])} "
                               "(D-0004-41)", {}))
    return out


def exit_readiness_index(profile: dict) -> dict:
    """Advisory normalized scalar (D-0004-40). A critical missing data export is
    still a hard blocker regardless of this average."""
    vals = [READINESS_ORDER.get(profile.get(d, "UNKNOWN"), 0)
            for d in EXIT_DIMENSIONS]
    max_per = 3
    eri = round(sum(vals) / (max_per * len(EXIT_DIMENSIONS)), 4) if vals else 0.0
    hard_blocker = profile.get("data_export", "UNKNOWN") in ("UNKNOWN", "NONE")
    return {"eri": eri, "hard_blocker_data_export": hard_blocker,
            "advisory_only": True}


def required_drill_level(criticality: str) -> str:
    return MIN_DRILL.get(criticality, "D0")


def drill_sufficient(criticality: str, drill_level: str) -> bool:
    need = DRILL_LEVELS.index(required_drill_level(criticality))
    have = DRILL_LEVELS.index(drill_level) if drill_level in DRILL_LEVELS else -1
    return have >= need
