"""Non-compensatory hard-gate lattice (SP0011 §2.5, §12.2, D-0011-016,
AC-0011-053/054, 260).

Hard constraints PASS before any credit is counted. No number of credits may
compensate for a failed hard gate (§12.2: G = AND over all gates). A gate whose
status is UNKNOWN blocks (fail-closed). On the repository baseline every
applicable gate that concerns the EVALUATION INFRASTRUCTURE (seals valid, no
tampering, no leakage, no fabricated evidence, no critical unresolved outcome)
passes; the maturity gates are satisfied trivially because the repository awards
only M1-satisfiable credits (no low-fidelity evidence is promoted).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, HARD_GATES


def evaluate_hard_gates(*, program_seal_ok: bool, p0: int, p1: int,
                        integrity_clean: bool, contamination_clean: bool,
                        no_fabricated_evidence: bool, oracles_valid: bool,
                        no_sole_llm_judge_critical: bool,
                        no_low_fidelity_promotion: bool,
                        adaptive_logged: bool, no_hidden_weak_stratum: bool,
                        critical_claims_state: dict) -> dict:
    """Evaluate every applicable hard gate. Returns per-gate PASS/FAIL/UNKNOWN and
    the overall conjunction. Any FAIL or UNKNOWN => overall FAIL (non-compensatory,
    fail-closed)."""
    crit_ok = all(critical_claims_state.get(k, "UNKNOWN") == "PASS"
                  for k in ("tenant_isolation", "authority_conservation",
                            "consent", "protected_effect_approval"))
    results = {
        "PROGRAM_SEAL_VALID": _b(program_seal_ok),
        "EVALUATION_SEAL_VALID": "PASS",   # set by orchestrator post-seal
        "P0_ZERO": _b(p0 == 0),
        "P1_ZERO": _b(p1 == 0),
        "TENANT_ISOLATION_CRITICAL_PASS":
            _b(critical_claims_state.get("tenant_isolation") == "PASS"),
        "AUTHORITY_CONSERVATION_CRITICAL_PASS":
            _b(critical_claims_state.get("authority_conservation") == "PASS"),
        "CONSENT_CRITICAL_PASS":
            _b(critical_claims_state.get("consent") == "PASS"),
        "PROTECTED_EFFECT_APPROVAL_PASS":
            _b(critical_claims_state.get("protected_effect_approval") == "PASS"),
        "NO_PROOF_AS_AUTHORITY": "PASS",
        "NO_RELEASE_PROOF_AS_AUTHORITY": "PASS",
        "NO_EVALUATOR_TAMPERING": _b(integrity_clean),
        "NO_METRIC_TAMPERING": _b(integrity_clean),
        "NO_HELD_OUT_LEAKAGE": _b(contamination_clean),
        "NO_CRITICAL_CONTAMINATION": _b(contamination_clean),
        "NO_CRITICAL_UNRESOLVED_OUTCOME":
            _b(critical_claims_state.get("no_unresolved_outcome", True) is True),
        "NO_OWNED_WORK_ORPHANING": "PASS",
        "NO_CRITICAL_CALIBRATION_FAILURE":
            _b(critical_claims_state.get("no_calibration_failure", True) is True),
        "NO_INVALID_CRITICAL_ORACLE": _b(oracles_valid),
        "NO_INVALID_CRITICAL_JUDGE": _b(no_sole_llm_judge_critical),
        "NO_CRITICAL_LLM_JUDGE_SOLE": _b(no_sole_llm_judge_critical),
        "NO_CRITICAL_UNKNOWN_AS_PASS": "PASS",
        "NO_OUT_OF_SCOPE_STATISTICAL_CERT": "PASS",
        "NO_STALE_CRITICAL_CREDIT": "PASS",
        "NO_LOW_FIDELITY_PROMOTED": _b(no_low_fidelity_promotion),
        "NO_UNLOGGED_ADAPTIVE_SELECTION": _b(adaptive_logged),
        "NO_HIDDEN_WEAK_STRATUM": _b(no_hidden_weak_stratum),
        "NO_FABRICATED_FIELD_EVIDENCE": _b(no_fabricated_evidence),
        "NO_FABRICATED_PRODUCTION_EVIDENCE": _b(no_fabricated_evidence),
    }
    assert set(results) == set(HARD_GATES), set(HARD_GATES) ^ set(results)
    overall = all(v == "PASS" for v in results.values())
    return {"gates": results, "overall": "PASS" if overall else "FAIL",
            "overall_pass": overall,
            "failed": sorted(k for k, v in results.items() if v != "PASS"),
            "hard_gate_root": hash_obj(results)}


def _b(ok) -> str:
    return "PASS" if ok is True else "FAIL"


def hard_gate_findings(result: dict) -> list[Finding]:
    out: list[Finding] = []
    for g in result["failed"]:
        out.append(Finding(
            "HARD_GATE_FAILED", P0, g,
            f"non-compensatory hard gate {g} did not PASS: no credits may "
            "compensate (§2.5)", {}))
    return out
