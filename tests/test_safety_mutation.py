"""SP0005 adversarial safety-mutation campaign (§20.31, AC-0005-227).

Each mutation injects one violation of a safety invariant into an otherwise-clean
copy of the real program and asserts the kernel *kills* it (raises the expected
hard finding). A surviving mutant means the corresponding check is vacuous.

The campaign is the dual of the green baseline: `test_safety_baseline` proves the
real program passes; this proves the gate is not passing everything.
"""
from __future__ import annotations

import copy

import pytest

from tools.safety.loader import load_program
from tools.safety.validate import validate_all
from tools.safety.regulatory import check_binding_claims
from tools.safety.barriers import independence_findings, shared_failure_domains
from tools.safety.hazards import traceability
from tools.safety.obligations import closure
from tools.safety.automaton import validate_run
from tools.safety.lease import issue_lease, revalidate
from tools.safety.statevector import control_class, evaluate
from tools.safety.assurance import open_defeaters, stale_critical_evidence
from tools.safety.oracle import validate_hard_property
from tools.safety.model import (
    UNCONTROLLED_CRITICAL_HAZARD, CONTROL_INDEPENDENCE_NOT_ESTABLISHED,
    DRAFT_SOURCE_USED_AS_BINDING, POLITICAL_AGREEMENT_USED_AS_ENACTED_LAW,
    PROOF_OBLIGATION_UNKNOWN, PROOF_OBLIGATION_FAILED, TRAJECTORY_SAFETY_VIOLATION,
    SAFETY_TOCTOU_MISMATCH, CRITICAL_DEFEATER_OPEN, ASSURANCE_EVIDENCE_STALE,
    SELF_REPORT_AS_SOLE_ORACLE, PROHIBITED_ACTION,
)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


@pytest.fixture()
def prog():
    return load_program()


def _first_active_critical(prog):
    for h in prog["hazards"]:
        if h.get("status") == "ACTIVE" and h.get("criticality") == "CRITICAL":
            return h
    # fall back: promote one so the mutation is meaningful
    prog["hazards"][0].update(status="ACTIVE", criticality="CRITICAL")
    return prog["hazards"][0]


# ---- baseline sanity: the un-mutated program is clean ----------------------
def test_unmutated_program_is_clean(prog):
    assert validate_all(prog).valid


# ---- M1: strip all controls + hard_block from a critical hazard ------------
def test_mutant_uncontrolled_critical_hazard_is_killed(prog):
    m = copy.deepcopy(prog)
    h = _first_active_critical(m)
    hid = h["hazard_id"]
    h.pop("hard_block", None)
    for c in m["controls"]:
        c["hazard_refs"] = [r for r in c.get("hazard_refs", []) if r != hid]
    assert UNCONTROLLED_CRITICAL_HAZARD in _k(traceability(m))
    assert not validate_all(m).valid


# ---- M2: make two barrier controls share a failure domain, keep claim ------
def test_mutant_control_independence_broken_is_killed(prog):
    m = copy.deepcopy(prog)
    if len(m["controls"]) < 2:
        pytest.skip("need >=2 controls")
    a, b = m["controls"][0], m["controls"][1]
    a["failure_domains"] = {"model": "gpt-x"}
    b["failure_domains"] = {"model": "gpt-x"}
    m["independence_claims"] = [{"control_a": a["control_id"],
                                 "control_b": b["control_id"]}]
    assert shared_failure_domains(a, b) == ["model"]
    assert CONTROL_INDEPENDENCE_NOT_ESTABLISHED in _k(independence_findings(m))


# ---- M3: use a DRAFT guidance as BINDING law -------------------------------
def test_mutant_draft_as_binding_is_killed(prog):
    m = copy.deepcopy(prog)
    src = next((s for s in m["sources"]
                if s.get("source_status", "").startswith("DRAFT")), None)
    if src is None:
        m["sources"].append({"source_id": "MUT", "official_url": "u",
                              "source_status": "DRAFT_OFFICIAL_GUIDANCE"})
        src = m["sources"][-1]
    src["used_as"] = "BINDING"
    assert DRAFT_SOURCE_USED_AS_BINDING in _k(check_binding_claims(m))


# ---- M4: political agreement treated as enacted law ------------------------
def test_mutant_political_agreement_as_law_is_killed(prog):
    m = copy.deepcopy(prog)
    m["sources"].append({"source_id": "MUT-POL", "official_url": "u",
                         "source_status": "POLITICAL_AGREEMENT_NOT_YET_ENACTED",
                         "used_as": "BINDING"})
    assert POLITICAL_AGREEMENT_USED_AS_ENACTED_LAW in _k(check_binding_claims(m))


# ---- M5: an UNKNOWN proof obligation must never satisfy ---------------------
def test_mutant_unknown_obligation_is_killed():
    ok, f = closure([{"obligation_type": "PO-AUTHORITY", "status": "UNKNOWN"}])
    assert not ok and PROOF_OBLIGATION_UNKNOWN in _k(f)
    ok2, f2 = closure([{"obligation_type": "PO-TENANT", "status": "UNSATISFIED"}])
    assert not ok2 and PROOF_OBLIGATION_FAILED in _k(f2)


# ---- M6: effect before verification in a trajectory ------------------------
def test_mutant_unsafe_trajectory_is_killed():
    au = {"automaton_id": "A",
          "transitions": [{"from": "UNVERIFIED", "action": "verify",
                           "to": "APPROVED"},
                          {"from": "APPROVED", "action": "effect", "to": "EFFECT"}],
          "forbidden_transitions": [["UNVERIFIED", "effect"]]}
    assert TRAJECTORY_SAFETY_VIOLATION in _k(
        validate_run(au, ["UNVERIFIED", "EFFECT"], ["effect"]))


# ---- M7: safety-context TOCTOU — target changes between lease and effect ----
def test_mutant_toctou_target_change_is_killed():
    action = {"action_type": "send", "target": {"target_id": "X"},
              "parameters": {}, "tenant": "t", "authority": "a",
              "policy_version": "1", "safety_context": {}}
    L = issue_lease(action=action, tenant="t", actor="u", authority={"r": 1},
                    context={"target": "X", "consent": "yes"},
                    trajectory_state={"s": 1}, policy_version="1",
                    semantic_epoch="e1", issued_at="2026-01-01",
                    expires_at="2026-12-31")
    changed = dict(action, target={"target_id": "Y"})
    ok, f = revalidate(L, action=changed, tenant="t", actor="u",
                       authority={"r": 1}, context={"target": "X", "consent": "yes"},
                       trajectory_state={"s": 1}, now="2026-06-01")
    assert not ok and SAFETY_TOCTOU_MISMATCH in _k(f)


# ---- M8: an open CRITICAL defeater on a SUPPORTED_CURRENT claim -------------
def test_mutant_open_critical_defeater_is_killed():
    reg = {"claims": [{"claim_id": "C", "status": "SUPPORTED_CURRENT",
                       "defeater_refs": ["D"]}],
           "defeaters": [{"defeater_id": "D", "severity": "CRITICAL",
                          "status": "OPEN"}]}
    assert CRITICAL_DEFEATER_OPEN in _k(open_defeaters(reg))


# ---- M9: stale critical evidence still backing a current claim -------------
def test_mutant_stale_critical_evidence_is_killed():
    reg = {"claims": [{"claim_id": "C", "status": "SUPPORTED_CURRENT",
                       "critical": True, "evidence_refs": ["E"]}],
           "evidence": [{"evidence_id": "E", "status": "EVIDENCE_STALE"}]}
    assert ASSURANCE_EVIDENCE_STALE in _k(stale_critical_evidence(reg))


# ---- M10: agent self-report as the sole oracle for a hard property ---------
def test_mutant_self_report_sole_oracle_is_killed():
    assert SELF_REPORT_AS_SOLE_ORACLE in _k(validate_hard_property(
        {"property_id": "P", "oracles": ["AGENT_SELF_REPORT"]}))


# ---- M11: a low-score vector must not launder a hard prohibition -----------
def test_mutant_score_cannot_override_hard_prohibition():
    action = {"action_type": "send", "target": {"target_id": "X"},
              "parameters": {}, "tenant": "t", "authority": "a",
              "policy_version": "1", "safety_context": {}}
    d, f = evaluate(action, {"consequence": "LOW"}, prohibited=True)
    assert d == "DENY" and PROHIBITED_ACTION in _k(f)


# ---- M12: UNKNOWN dimension must escalate, never relax to LOW ---------------
def test_mutant_unknown_dimension_never_low():
    assert control_class({"consequence": "UNKNOWN"}) == "CC3"
    assert control_class({"irreversibility": "CRITICAL", "consequence": "LOW"}) \
        == "CC4"


# ---- campaign summary: every mutant above is killed (kill-rate 100%) --------
def test_mutation_campaign_kill_rate_is_total(prog):
    # Re-run the structural mutants through the *whole* validator to prove the
    # gate — not just a single checker — rejects each. Point mutants (M5..M12)
    # are unit-verified above.
    killed = 0
    total = 0

    # M1
    total += 1
    m = copy.deepcopy(prog)
    h = _first_active_critical(m)
    hid = h["hazard_id"]
    h.pop("hard_block", None)
    for c in m["controls"]:
        c["hazard_refs"] = [r for r in c.get("hazard_refs", []) if r != hid]
    if not validate_all(m).valid:
        killed += 1

    # M3 (draft-as-binding through full validator)
    total += 1
    m = copy.deepcopy(prog)
    m["sources"].append({"source_id": "MUT-D", "official_url": "u",
                         "source_status": "DRAFT_OFFICIAL_GUIDANCE",
                         "used_as": "BINDING"})
    if not validate_all(m).valid:
        killed += 1

    # M4 (political-as-law through full validator)
    total += 1
    m = copy.deepcopy(prog)
    m["sources"].append({"source_id": "MUT-P", "official_url": "u",
                         "source_status": "POLITICAL_AGREEMENT_NOT_YET_ENACTED",
                         "used_as": "BINDING"})
    if not validate_all(m).valid:
        killed += 1

    assert killed == total, f"surviving mutants: {total - killed}/{total}"
