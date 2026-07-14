"""Outcome Contract Engine + Predicate Registry + Evidence + Verification +
Defeaters + Disputes + Partial + Supersession (SP0006 §9.4/9.12, §11.12,
D-0006-10/11/56..61, INV-0006-37..43).

Three separations are load-bearing: output is NOT outcome (INV-0006-37), claimed
is NOT verified (INV-0006-38), and partial is NOT complete (INV-0006-39). An
outcome contract enumerates expected_outcomes and acceptance_predicates; each
predicate is evaluated by a DETERMINISTIC evaluator that may return SATISFIED,
UNSATISFIED, or UNKNOWN — and UNKNOWN never counts as satisfied. A critical
outcome whose only oracle is a non-primary oracle (agent self-report / LLM judge)
can never verify itself (D-0006-57). Completed outcomes are immutable: a defeater
reopens via a LINKED successor, never by mutating the original record (D-0006-59),
and superseded work references its replacement and cannot resume (D-0006-61).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, OUTCOME_STATES, OUTCOME_PREDICATE_TYPES,
                    VERIFICATION_MODES, NON_PRIMARY_OUTCOME_ORACLES,
                    OUTCOME_EVIDENCE_INCOMPLETE, OUTCOME_DISPUTED,
                    OUTCOME_DEFEATER_OPEN, OUTPUT_NOT_OUTCOME,
                    SELF_REPORT_AS_SOLE_OUTCOME_ORACLE, INVALID_WORK_SCHEMA)

UNKNOWN = "UNKNOWN"
SATISFIED = "SATISFIED"
UNSATISFIED = "UNSATISFIED"

# recognized PRIMARY (world-grounded) outcome oracles — a critical outcome must
# be backed by at least one of these; anything else (self-report, LLM judge, or
# an unrecognized string) cannot solely verify it (SWARM-M E3, D-0006-57)
PRIMARY_OUTCOME_ORACLES = frozenset({
    "ENVIRONMENT_STATE", "ARTIFACT_CRYPTO_EVIDENCE",
    "INDEPENDENT_FORMAL_RULE_CHECKER", "CALIBRATED_STATISTICAL",
    "HUMAN_SPECIALIST", "DATABASE_STATE", "EFFECT_LEDGER", "EXTERNAL_ACK",
    "AUDIT_EVENT",
})

CONTRACT_REQUIRED = ("expected_outcomes", "acceptance_predicates",
                     "verification_mode", "completion_rule")


def validate_outcome_contract(contract: dict) -> list[Finding]:
    """An outcome contract must name expected outcomes, acceptance predicates (each
    of a known predicate_type), a verification mode and a completion rule
    (D-0006-10/11)."""
    out: list[Finding] = []
    cid = contract.get("contract_id", contract.get("work_order_id", "-"))
    for f in CONTRACT_REQUIRED:
        if contract.get(f) in (None, "", [], {}):
            out.append(Finding(INVALID_WORK_SCHEMA, P1, cid,
                               f"outcome contract missing {f} (D-0006-10)",
                               {"field": f}))
    for p in contract.get("acceptance_predicates", []) or []:
        ptype = p.get("predicate_type") if isinstance(p, dict) else None
        if ptype not in OUTCOME_PREDICATE_TYPES:
            out.append(Finding(INVALID_WORK_SCHEMA, P1, cid,
                               f"unknown acceptance predicate_type {ptype!r}",
                               {"predicate_id": p.get("predicate_id")
                                if isinstance(p, dict) else None,
                                "predicate_type": ptype}))
    mode = contract.get("verification_mode")
    if mode is not None and mode not in VERIFICATION_MODES:
        out.append(Finding(INVALID_WORK_SCHEMA, P1, cid,
                           f"unknown verification_mode {mode!r}",
                           {"verification_mode": mode}))
    return out


# --- deterministic predicate evaluators (§9.4) ------------------------------
# each takes (predicate, evidence) and returns SATISFIED / UNSATISFIED / UNKNOWN.
# missing / unusable evidence yields UNKNOWN (fail-closed), never SATISFIED.
def _ev_artifact_exists(pred, evidence):
    if not evidence:
        return UNKNOWN
    return SATISFIED if evidence.get("artifact_present") is True else UNSATISFIED


def _ev_artifact_hash(pred, evidence):
    expected = pred.get("expected_hash")
    actual = evidence.get("artifact_hash") if evidence else None
    if expected is None or actual is None:
        return UNKNOWN
    return SATISFIED if actual == expected else UNSATISFIED


def _ev_schema_valid(pred, evidence):
    if not evidence or "schema_valid" not in evidence:
        return UNKNOWN
    return SATISFIED if evidence.get("schema_valid") is True else UNSATISFIED


def _ev_source_complete(pred, evidence):
    if not evidence:
        return UNKNOWN
    required = pred.get("required_sources")
    present = evidence.get("present_sources")
    if required is None or present is None:
        if "sources_complete" in (evidence or {}):
            return SATISFIED if evidence["sources_complete"] is True else UNSATISFIED
        return UNKNOWN
    missing = set(map(str, required)) - set(map(str, present))
    return SATISFIED if not missing else UNSATISFIED


def _ev_numerical_reconciliation(pred, evidence):
    if not evidence:
        return UNKNOWN
    expected = evidence.get("expected_total")
    actual = evidence.get("actual_total")
    if expected is None or actual is None:
        return UNKNOWN
    tol = pred.get("tolerance", 0)
    try:
        return SATISFIED if abs(float(actual) - float(expected)) <= float(tol) \
            else UNSATISFIED
    except (TypeError, ValueError):
        return UNKNOWN


def _ev_target_state_equals(pred, evidence):
    expected = pred.get("expected_state")
    observed = evidence.get("observed_state") if evidence else None
    if expected is None or observed is None:
        return UNKNOWN
    return SATISFIED if observed == expected else UNSATISFIED


def _ev_no_forbidden_effect(pred, evidence):
    if not evidence or "observed_effects" not in evidence:
        return UNKNOWN
    forbidden = set(map(str, pred.get("forbidden_effects", [])))
    observed = set(map(str, evidence.get("observed_effects", [])))
    return SATISFIED if not (forbidden & observed) else UNSATISFIED


PREDICATE_EVALUATORS = {
    "ARTIFACT_EXISTS": _ev_artifact_exists,
    "ARTIFACT_HASH": _ev_artifact_hash,
    "SCHEMA_VALID": _ev_schema_valid,
    "SOURCE_COMPLETE": _ev_source_complete,
    "NUMERICAL_RECONCILIATION": _ev_numerical_reconciliation,
    "TARGET_STATE_EQUALS": _ev_target_state_equals,
    "NO_FORBIDDEN_EFFECT": _ev_no_forbidden_effect,
}


def _match_evidence(pred, evidence_list):
    """Load the evidence item bound to this predicate by predicate_id, else the
    first item whose evidence_type matches the predicate_type."""
    pid = pred.get("predicate_id")
    ptype = pred.get("predicate_type")
    for e in evidence_list:
        if pid and e.get("predicate_id") == pid:
            return e
    for e in evidence_list:
        if e.get("predicate_type") == ptype or e.get("evidence_type") == ptype:
            return e
    return None


def _lineage_ok(evidence) -> bool:
    """Evidence must carry lineage (a source/provenance) and a verifier identity
    (INV-0006-40); unverified or unsourced evidence cannot satisfy a predicate."""
    if not evidence:
        return False
    has_lineage = bool(evidence.get("lineage") or evidence.get("source")
                       or evidence.get("provenance"))
    has_verifier = bool(evidence.get("verifier") or evidence.get("verifier_id"))
    return has_lineage and has_verifier


def _oracles(contract, evidence_list) -> set:
    oracles = set()
    for e in evidence_list:
        o = e.get("oracle") or e.get("verifier_type")
        if o:
            oracles.add(str(o))
    for o in contract.get("oracles", []) or []:
        oracles.add(str(o))
    return oracles


def verify_outcome(contract: dict, evidence: list[dict], *,
                   defeaters: list[dict] | None = None) -> dict:
    """Deterministically verify an outcome contract against evidence. Each
    acceptance predicate resolves to SATISFIED / UNSATISFIED / UNKNOWN via its
    deterministic evaluator (after lineage + verifier checks). Completion follows
    the contract completion_rule (default: ALL predicates SATISFIED). All satisfied
    -> VERIFIED; some satisfied but others UNKNOWN/UNSATISFIED -> PARTIALLY_VERIFIED
    (INV-0006-39); an open critical defeater -> DISPUTED (D-0006-58). A critical
    outcome whose only oracle is non-primary -> SELF_REPORT_AS_SOLE_OUTCOME_ORACLE
    P0 (D-0006-57, AC-0006-174)."""
    evidence = list(evidence or [])
    defeaters = list(defeaters or [])
    findings: list[Finding] = []
    subject = contract.get("contract_id", contract.get("work_order_id", "-"))
    predicates = contract.get("acceptance_predicates", []) or []
    critical = bool(contract.get("critical"))

    # a critical outcome cannot rest solely on a non-primary oracle (D-0006-57).
    # a critical outcome needs at least one RECOGNIZED primary oracle; an
    # allowlist (not a blacklist subset test) so a junk oracle cannot mask
    # self-report as sufficient (SWARM-M E3; D-0006-57)
    oracles = _oracles(contract, evidence)
    has_primary = any(o in PRIMARY_OUTCOME_ORACLES for o in oracles)
    if critical and oracles and not has_primary:
        findings.append(Finding(
            SELF_REPORT_AS_SOLE_OUTCOME_ORACLE, P0, subject,
            "critical outcome verified only by a non-primary oracle "
            f"({sorted(oracles)}) — self-report / LLM-judge cannot be the sole "
            "oracle (D-0006-57, AC-0006-174)", {"oracles": sorted(oracles)}))

    predicate_results = []
    unresolved = []
    for pred in predicates:
        pid = pred.get("predicate_id", pred.get("predicate_type", "-"))
        ptype = pred.get("predicate_type")
        ev = _match_evidence(pred, evidence)
        status = _evaluate(pred, ptype, ev, subject, findings)
        predicate_results.append({"predicate_id": pid, "predicate_type": ptype,
                                  "status": status})
        if status != SATISFIED:
            unresolved.append(pid)

    # open critical defeaters take precedence (D-0006-58).
    open_critical_defeaters = [d for d in defeaters
                               if _is_open(d) and d.get("critical")]
    for d in open_critical_defeaters:
        findings.append(Finding(
            OUTCOME_DEFEATER_OPEN, P1, subject,
            "open critical defeater against outcome (D-0006-58)",
            {"defeater_id": d.get("defeater_id")}))

    total = len(predicate_results)
    satisfied = sum(1 for r in predicate_results if r["status"] == SATISFIED)

    state = _decide_state(contract, predicate_results, satisfied, total,
                          open_critical_defeaters, findings, subject)

    return {"state": state, "predicate_results": predicate_results,
            "unresolved_predicates": unresolved,
            "findings": findings}


def _evaluate(pred, ptype, ev, subject, findings) -> str:
    evaluator = PREDICATE_EVALUATORS.get(ptype)
    if evaluator is None:
        # a predicate with no deterministic evaluator cannot be auto-satisfied.
        return UNKNOWN
    # lineage / verifier gate: unsourced or unverified evidence is unusable.
    if ev is not None and not _lineage_ok(ev):
        findings.append(Finding(
            OUTCOME_EVIDENCE_INCOMPLETE, P1, subject,
            f"evidence for predicate {pred.get('predicate_id', ptype)} lacks "
            "lineage or verifier (INV-0006-40)",
            {"predicate_id": pred.get("predicate_id"), "predicate_type": ptype}))
        return UNKNOWN
    result = evaluator(pred, ev or {})
    if result not in (SATISFIED, UNSATISFIED, UNKNOWN):
        return UNKNOWN
    if result == UNKNOWN and ev is None:
        findings.append(Finding(
            OUTCOME_EVIDENCE_INCOMPLETE, P1, subject,
            f"no evidence supplied for predicate "
            f"{pred.get('predicate_id', ptype)} (INV-0006-38)",
            {"predicate_id": pred.get("predicate_id"), "predicate_type": ptype}))
    return result


def _decide_state(contract, predicate_results, satisfied, total,
                  open_critical_defeaters, findings, subject) -> str:
    if open_critical_defeaters:
        return "DISPUTED"
    if total == 0:
        # nothing verifiable claimed: claimed is not verified (INV-0006-38).
        return "CLAIMED"
    rule = str(contract.get("completion_rule", "ALL")).upper()
    all_satisfied = satisfied == total
    if rule in ("ALL", "ALL_SATISFIED", "") and all_satisfied:
        return "VERIFIED"
    if rule not in ("ALL", "ALL_SATISFIED", "") and _rule_met(contract, rule,
                                                              predicate_results):
        return "VERIFIED"
    if satisfied > 0:
        return "PARTIALLY_VERIFIED"
    return "EVIDENCED" if _any_evidence(predicate_results) else "CLAIMED"


def _rule_met(contract, rule, predicate_results) -> bool:
    """Support a THRESHOLD:n completion rule; otherwise require ALL satisfied."""
    if rule.startswith("THRESHOLD"):
        try:
            n = int(rule.split(":", 1)[1])
        except (IndexError, ValueError):
            return False
        # a threshold must require at least one predicate and cannot exceed the
        # predicate count — THRESHOLD:0 / negative is never vacuously met
        # (SWARM-M E8; INV-0006-39)
        if n < 1 or n > len(predicate_results):
            return False
        return sum(1 for r in predicate_results
                   if r["status"] == SATISFIED) >= n
    return bool(predicate_results) and \
        all(r["status"] == SATISFIED for r in predicate_results)


def _any_evidence(predicate_results) -> bool:
    return any(r["status"] in (SATISFIED, UNSATISFIED) for r in predicate_results)


def _is_open(d) -> bool:
    return bool(d.get("open")) or str(d.get("status", "")).upper() == "OPEN"


def artifact_vs_outcome_findings(claim: dict) -> list[Finding]:
    """Output is not outcome (INV-0006-37). A completion claim backed only by
    ARTIFACT_PRODUCED, with no verified acceptance predicate, is OUTPUT_NOT_OUTCOME
    (P1)."""
    out: list[Finding] = []
    subject = claim.get("work_order_id", "-")
    if not claim.get("claims_completion", True):
        return out
    evidence_kinds = {str(k).upper() for k in claim.get("evidence_kinds", [])}
    verified = claim.get("verified_predicates") or []
    only_artifact = evidence_kinds <= {"ARTIFACT_PRODUCED"} and evidence_kinds
    if only_artifact and not verified:
        out.append(Finding(
            OUTPUT_NOT_OUTCOME, P1, subject,
            "completion claimed with only ARTIFACT_PRODUCED and no verified "
            "acceptance predicate — output is not outcome (INV-0006-37)",
            {"evidence_kinds": sorted(evidence_kinds)}))
    return out


def defeater_findings(defeaters: list[dict]) -> list[Finding]:
    """An OPEN defeater against a VERIFIED outcome reopens accountability
    (INV-0006-41): OUTCOME_DEFEATER_OPEN (P1) for each."""
    out: list[Finding] = []
    for d in defeaters or []:
        if _is_open(d) and str(d.get("outcome_state", "")).upper() == "VERIFIED":
            out.append(Finding(
                OUTCOME_DEFEATER_OPEN, P1,
                d.get("outcome_id", d.get("defeater_id", "-")),
                "open defeater against a verified outcome (D-0006-58, "
                "INV-0006-41)", {"defeater_id": d.get("defeater_id")}))
    return out


def reopen_by_defeater(work_order: dict, defeater: dict) -> dict:
    """Reopen a completed outcome via a LINKED revision/successor. The original
    completion record stays immutable; the successor references it and the
    defeater (D-0006-59, INV-0006-41)."""
    return {
        "work_order_id": f"{work_order.get('work_order_id', '-')}"
                         f"~r{work_order.get('work_version', 1) + 1}",
        "reopened_by_defeater": defeater.get("defeater_id"),
        "successor_of": work_order.get("work_order_id"),
        "original_completion_immutable": True,
        "status": "DRAFT",
    }


def supersede(work_order: dict, replacement_id: str) -> dict:
    """Supersede a work order: it references its replacement and can never resume
    (D-0006-61, INV-0006-42)."""
    return {
        "work_order_id": work_order.get("work_order_id"),
        "status": "SUPERSEDED",
        "superseded_by": replacement_id,
        "can_resume": False,
    }


def dispute_findings(disputes: list[dict]) -> list[Finding]:
    """Each OPEN dispute against an outcome is OUTCOME_DISPUTED (P1) (D-0006-60)."""
    out: list[Finding] = []
    for d in disputes or []:
        if _is_open(d):
            out.append(Finding(
                OUTCOME_DISPUTED, P1,
                d.get("outcome_id", d.get("dispute_id", "-")),
                "open dispute against outcome (D-0006-60, §11.12)",
                {"dispute_id": d.get("dispute_id")}))
    return out
