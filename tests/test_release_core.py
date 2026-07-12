"""SP0009 Release Assurance — core invariants.

Pins the load-bearing properties: immutable candidate identity, the
non-compensatory fail-closed gate lattice, candidate-bound bitemporal evidence,
append-only ledgers (failure permanence), DoD closure (merged != done), honest
flake classification, dependency-closed slices, and the change boundary.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.release import (canon, model, candidate, classify, gates, evidence,
                            obligations, waivers, impact, select_tests,
                            attempts, flakes, mutation, boundary, modelcheck,
                            archaeology)

ROOT = Path(__file__).resolve().parents[1]

BINDINGS = {f: f"v-{f}" for f in candidate.GENOME_FIELDS}


# --- canon -------------------------------------------------------------------
def test_canonical_json_and_merkle_log():
    assert canon.canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    log = canon.MerkleLog()
    idx = log.append("claim-1")
    log.append("claim-2")
    cp = log.checkpoint()
    proof = log.inclusion_proof(idx)
    assert canon.verify_inclusion("claim-1", proof, cp)
    assert not canon.verify_inclusion("forged", proof, cp)


# --- candidate identity ---------------------------------------------------------
def test_candidate_genome_deterministic_and_material():
    a = candidate.candidate_genome(BINDINGS)
    assert a == candidate.candidate_genome(dict(BINDINGS))
    for f in candidate.GENOME_FIELDS:
        assert candidate.candidate_genome({**BINDINGS, f: "X"}) != a, f


def test_candidate_mutation_detected():
    rc = candidate.new_candidate("RC-T", BINDINGS)
    assert candidate.verify_genome(rc) == []
    mutated = dict(rc, source_commit="tampered")
    assert any(f.severity == model.P0 for f in candidate.verify_genome(mutated))


def test_supersession_preserves_history():
    rc = candidate.new_candidate("RC-T", BINDINGS)
    old, new = candidate.supersede(rc, "RC-T2", {"source_commit": "new"})
    assert old["status"] == "SUPERSEDED"
    assert old["superseded_by"] == "RC-T2"
    assert new["candidate_genome"] != rc["candidate_genome"]
    assert any(h["event"] == "CANDIDATE_SUPERSEDED" for h in old["history"])


def test_pause_resume_revalidates_stale_evidence():
    rc = candidate.new_candidate("RC-T", BINDINGS)
    rc = candidate.transition(rc, "CLASSIFIED")
    paused = candidate.pause(rc, next_action="run gates",
                             open_obligations=["OB-TESTS"])
    assert paused["status"] == "PAUSED"
    assert paused["pause_context"]["next_action"] == "run gates"
    resumed, stale = candidate.resume(
        paused, evidence_records=[{"evidence_id": "E1",
                                   "valid_to": "2026-01-01"}],
        now="2026-06-01")
    assert resumed["status"] == "CLASSIFIED"
    assert stale and stale[0].kind == "GATE_STALE"


# --- classification ---------------------------------------------------------------
def test_one_line_authority_change_is_high_risk():
    c = classify.classify_paths(["finalis/portal/auth.py"])
    v = classify.risk_vector(c)
    assert "AUTHORITY_CHANGE" in c["classes"]
    assert v["authority"] == "HIGH" and "authority" in v["hard_flags"]


def test_multi_label_classification():
    c = classify.classify_paths(["finalis/portal/db.py", "pyproject.toml",
                                 "tests/test_x.py", "docs/y.md"])
    assert {"MIGRATION_CHANGE", "DEPENDENCY_CHANGE", "TEST_CHANGE",
            "DOCS_CHANGE"} <= set(c["classes"])


# --- gate lattice -----------------------------------------------------------------
def test_gate_registry_valid_and_dag_acyclic():
    assert gates.registry_findings() == []


def test_gate_cycle_rejected():
    fs = gates.dag_findings({"A": ["B"], "B": ["A"]})
    assert any(f.kind == "GATE_DEPENDENCY_CYCLE" for f in fs)


def test_unknown_hard_gate_blocks():
    plan = {"GATE_TENANT_ISOLATION": "REQUIRED"}
    for bad in ("UNKNOWN", "FAIL", "STALE", "INVALID", None):
        v = gates.hard_verdict(plan, {"GATE_TENANT_ISOLATION": bad})
        assert not v["qualifiable"], bad


def test_non_waivable_gate_rejects_waived_result():
    plan = {"GATE_TENANT_ISOLATION": "REQUIRED"}
    v = gates.hard_verdict(plan, {"GATE_TENANT_ISOLATION": "WAIVED"},
                           waivers={"GATE_TENANT_ISOLATION":
                                    {"status": "ACTIVE"}})
    assert not v["qualifiable"]
    assert v["blocking"][0]["reason"] == "NON_WAIVABLE_WAIVER_REJECTED"


def test_advisory_gate_never_blocks():
    plan = {"GATE_MUTATION_ADEQUACY": "REQUIRED",
            "GATE_UNIT_TESTS": "REQUIRED"}
    v = gates.hard_verdict(plan, {"GATE_MUTATION_ADEQUACY": "FAIL",
                                  "GATE_UNIT_TESTS": "PASS"})
    assert v["qualifiable"] and v["advisory"]


def test_most_restrictive_policy_wins():
    agg = gates.most_restrictive([
        {"G": {"required": False, "waivable": True, "evidence_ttl": "P90D"}},
        {"G": {"required": True, "waivable": False, "evidence_ttl": "P30D"}},
    ])
    assert agg["G"]["required"] is True
    assert agg["G"]["waivable"] is False
    assert agg["G"]["evidence_ttl"] == "P30D"


# --- evidence ----------------------------------------------------------------------
def test_cross_candidate_evidence_rejected():
    e = evidence.evidence_record(
        candidate_genome="genome-A", gate_id="GATE_UNIT_TESTS",
        configuration_fingerprint=gates.gate_configuration_fingerprint(
            "GATE_UNIT_TESTS"),
        environment={}, tool_version="1", result="PASS",
        valid_from="2026-01-01")
    fs = evidence.validate_for_candidate(
        e, candidate_genome="genome-B", gate_id="GATE_UNIT_TESTS",
        now="2026-06-01")
    assert any(f.severity == model.P0 for f in fs)


def test_stale_evidence_cannot_pass():
    e = evidence.evidence_record(
        candidate_genome="g", gate_id="GATE_UNIT_TESTS",
        configuration_fingerprint=gates.gate_configuration_fingerprint(
            "GATE_UNIT_TESTS"),
        environment={}, tool_version="1", result="PASS",
        valid_from="2026-01-01", valid_to="2026-02-01")
    fs = evidence.validate_for_candidate(
        e, candidate_genome="g", gate_id="GATE_UNIT_TESTS", now="2026-06-01")
    assert any(f.kind == "GATE_STALE" for f in fs)


def test_gate_ledger_append_only_failure_persists():
    led = evidence.GateResultLedger()
    led.append({"gate_id": "G", "candidate_genome": "g", "result": "FAIL"})
    led.append({"gate_id": "G", "candidate_genome": "g", "result": "PASS"})
    assert len(led.failures_ever("G", "g")) == 1
    assert led.latest("G", "g")["result"] == "PASS"
    assert led.entries()[1]["rerun_of"] == led.entries()[0]["entry_id"]


# --- waivers / approvals -------------------------------------------------------------
def test_waiver_requires_expiry_owner_control():
    w = waivers.waiver(gate_id="GATE_BROWSER_E2E", candidate_genome="g",
                       risk_owner="", compensating_control="",
                       expires_at="", approved_by="alice")
    fs = waivers.validate_waiver(w, candidate_genome="g", now="2026-06-01")
    kinds = {f.kind for f in fs}
    assert "WAIVER_INVALID" in kinds


def test_self_approval_rejected():
    a = waivers.approval(candidate_genome="g", approver="alice",
                         scope="release")
    fs = waivers.validate_approval(a, candidate_genome="g", author="alice",
                                   now="2026-06-01")
    assert any(f.kind == "SELF_APPROVAL_REJECTED" for f in fs)


# --- DoD ------------------------------------------------------------------------------
def test_merge_does_not_imply_done():
    obs = obligations.obligations_for(["CONTRACT_CHANGE"], "g")
    closure = obligations.dod_closure(obs)
    assert not closure["done"]
    fs = obligations.dod_findings(closure, merged=True)
    assert any(f.severity in (model.P0, model.P1) for f in fs)


def test_obligation_closes_only_with_own_evidence():
    obs = obligations.obligations_for(["DOCS_CHANGE"], "g")
    doc_ob = next(o for o in obs if o["obligation_type"] == "DOCUMENTATION")
    with pytest.raises(ValueError):
        obligations.close_obligation(doc_ob, [{"ref": "evidence:tests",
                                               "supports": ["evidence:tests"]}],
                                     closed_at="2026-06-01")


# --- test selection --------------------------------------------------------------------
def test_exact_set_cover_minimal():
    tests = [{"test_id": "a", "cost": 1}, {"test_id": "b", "cost": 1},
             {"test_id": "c", "cost": 3}]
    covers = {"a": {"u1"}, "b": {"u2"}, "c": {"u1", "u2"}}
    sel, cost = select_tests.exact_set_cover(tests, ["u1", "u2"], covers)
    assert sel == ["a", "b"] and cost == 2


def test_greedy_preserves_mandatory():
    tests = [{"test_id": "m", "cost": 100}, {"test_id": "x", "cost": 1}]
    covers = {"m": {"u1"}, "x": {"u1"}}
    sel = select_tests.greedy_cover(tests, ["u1"], covers, mandatory=["m"])
    assert "m" in sel


def test_selection_proof_gap_is_p0():
    proof = select_tests.selection_proof([], ["u1"], {})
    assert proof["gaps"] == ["u1"]
    assert any(f.severity == model.P0
               for f in select_tests.proof_findings(proof))


# --- attempts / flakes -------------------------------------------------------------------
def test_rerun_never_erases_failure():
    led = attempts.ExecutionLedger()
    f1 = led.record(candidate_genome="g", test_id="t", result="FAIL",
                    environment_fingerprint="e")
    led.record(candidate_genome="g", test_id="t", result="PASS",
               environment_fingerprint="e", rerun_of=f1["attempt_id"])
    st = led.effective_state("t", "g")
    assert st["ever_failed"] and st["rerun_passed_after_failure"]
    acct = attempts.rerun_accounting(led, "g")
    assert acct["tests_with_failure_then_pass"] == ["t"]


def test_single_rerun_cannot_confirm_flake():
    reg: list = []
    reg = flakes.observe(reg, test_id="t", env_fingerprint="e", result="FAIL")
    reg = flakes.observe(reg, test_id="t", env_fingerprint="e", result="PASS")
    cls = flakes.classify(reg, test_id="t")
    assert cls["classification"] == "UNKNOWN"


def test_environment_instability_classification():
    reg: list = []
    for _ in range(2):
        reg = flakes.observe(reg, test_id="t", env_fingerprint="parallel",
                             result="FAIL")
    for _ in range(2):
        reg = flakes.observe(reg, test_id="t", env_fingerprint="isolation",
                             result="PASS")
    cls = flakes.classify(reg, test_id="t")
    assert cls["classification"] == "ENVIRONMENT_INSTABILITY"


def test_critical_quarantine_blocked_without_equivalent_control():
    q = flakes.quarantine(test_id="test_tenant_isolation", owner="o",
                          expires_at="2027-01-01")
    fs = flakes.validate_quarantine(q)
    assert any(f.kind == "CRITICAL_TEST_QUARANTINE_BLOCKED"
               and f.severity == model.P0 for f in fs)
    q2 = flakes.quarantine(test_id="test_tenant_isolation", owner="o",
                           expires_at="2027-01-01",
                           equivalent_control={"verified": True,
                                               "control": "gate"})
    assert not any(f.severity == model.P0
                   for f in flakes.validate_quarantine(q2))


# --- mutation accounting ---------------------------------------------------------------
def test_mutation_adequacy_excludes_equivalents():
    ms = [mutation.mutant(mutant_id="m1", target="t", operator="o",
                          status="KILLED"),
          mutation.mutant(mutant_id="m2", target="t", operator="o",
                          status="EQUIVALENT",
                          equivalent_reason="same semantics"),
          mutation.mutant(mutant_id="m3", target="t", operator="o",
                          status="SURVIVED")]
    a = mutation.adequacy(ms)
    assert a["non_equivalent_total"] == 2       # equivalent excluded
    assert a["survived"] == ["m3"] and not a["adequate"]


# --- slice / impact ---------------------------------------------------------------------
def test_slice_missing_dependency_rejected():
    s = impact.release_slice(slice_id="S", members=["A"],
                             dependencies={"A": ["B"]},
                             verified_baseline=set())
    assert not s["closed"]
    assert any(f.kind == "RELEASE_SLICE_NOT_CLOSED" and f.severity == model.P0
               for f in impact.slice_findings(s))


def test_impact_cone_over_real_inventory():
    cone = impact.impact_cone(ROOT, ["finalis/portal/app.py"])
    assert cone["direct_impacts"]           # app.py hosts real surfaces
    assert cone["impacted_contracts"]


# --- boundary / models -------------------------------------------------------------------
def test_boundary_clean():
    assert boundary.check_boundary(ROOT) == []


def test_all_bounded_models_hold():
    res = modelcheck.run_models()
    assert res["all_hold"], res["models"]


def test_archaeology_honest_absences():
    arch = archaeology.release_archaeology(ROOT)
    assert arch["ci_workflow_hash"] == "ABSENT"
    assert arch["ci_workflows_present"] is False
    assert arch["browser_e2e_present"] is True
    assert arch["known_flakes"][0]["passes_in_isolation"] is True
