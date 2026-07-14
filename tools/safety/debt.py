"""Assurance Debt vector + Safety Drift Observatory (SP0005 D-0005-77/78/79, §19,
INV-0005-10).

Assurance debt is a VECTOR (P0_OPEN, P1_OPEN, uncontrolled critical hazards, open
critical defeaters, stale critical evidence, uncertain high-impact applicability,
missing executable safety tests, expired critical admission evidence) — no average
safety score hides critical debt: P0_OPEN > 0 ⇒ SAFETY_GATE_FAIL (D-0005-78,
INV-0005-10). The drift observatory tracks safety metrics over time; uncalibrated
drift metrics are advisory, never automatic hard blockers.
"""
from __future__ import annotations

from .model import Finding, P0


def assurance_debt(report_dict: dict, program: dict) -> dict:
    counts = report_dict.get("counts", {})
    findings = report_dict.get("findings", [])
    kinds = [f["kind"] for f in findings]
    return {
        "P0_OPEN": counts.get("P0", 0),
        "P1_OPEN": counts.get("P1", 0),
        "UNCONTROLLED_CRITICAL_HAZARDS": kinds.count("UNCONTROLLED_CRITICAL_HAZARD"),
        "OPEN_CRITICAL_DEFEATERS": kinds.count("CRITICAL_DEFEATER_OPEN"),
        "STALE_CRITICAL_EVIDENCE": kinds.count("ASSURANCE_EVIDENCE_STALE"),
        "UNCERTAIN_HIGH_IMPACT_APPLICABILITY":
            kinds.count("LEGAL_APPLICABILITY_UNCERTAIN"),
        "ASSURANCE_COVERAGE_GAPS": kinds.count("ASSURANCE_COVERAGE_GAP"),
        "safety_gate": "FAIL" if counts.get("P0", 0) > 0 else "PASS",
    }


def gate_findings(report_dict: dict) -> list[Finding]:
    """P0_OPEN > 0 => SAFETY_GATE_FAIL (already surfaced as P0 findings; this makes
    the gate explicit for observability)."""
    if report_dict.get("counts", {}).get("P0", 0) > 0:
        return [Finding("SAFETY_GATE_FAIL", P0, "-",
                        "P0 safety debt open; no average score can pass the gate "
                        "(D-0005-78)", {})]
    return []


def drift_snapshot(program: dict, report_dict: dict) -> dict:
    counts = report_dict.get("counts", {})
    hazards = program.get("hazards", [])
    return {
        "classification": "ADVISORY_NOT_A_GATE",
        "loss_count": len(program.get("losses", [])),
        "hazard_count": len(hazards),
        "critical_hazards": sum(1 for h in hazards
                                if h.get("criticality") in ("HIGH", "CRITICAL")),
        "control_count": len(program.get("controls", [])),
        "claim_count": len(program.get("claims", [])),
        "defeater_count": len(program.get("defeaters", [])),
        "regulatory_source_count": len(program.get("sources", [])),
        "scenario_count": len(program.get("scenarios", [])),
        "incident_count": len(program.get("incidents", [])),
        "near_miss_count": len(program.get("near_misses", [])),
        "P0_open": counts.get("P0", 0),
        "P1_open": counts.get("P1", 0),
    }
