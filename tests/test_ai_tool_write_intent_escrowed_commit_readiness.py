"""TOOL-B7 v4: Escrowed commit-readiness certificate — local evidence that a
FUTURE human-approved commit could be prepared. It NEVER executes: commit is
never executable now, the certificate is not a bearer authority and not a
production signature, and readiness is true ONLY on the clean escrow-draft
path."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_certificate_exists(gate):
    cert = k.clean_outcome(gate)["escrowed_commit_readiness_certificate"]
    assert cert["escrowed_commit_readiness_certificate_id"].startswith("ecr-")
    assert cert["certificate_status"] == "ESCROWED_EVIDENCE_ONLY"


def test_commit_executable_now_always_false_clean(gate):
    o = k.clean_outcome(gate)
    assert o["commit_executable_now"] is False
    assert o["escrowed_commit_readiness_certificate"][
        "commit_executable_now"] is False


def test_commit_executable_now_always_false_under_blocker(gate):
    b6 = k.b6_outcome(gate)
    for over in (dict(observed_escrow_hash="deadbeef"),
                 dict(debt_items=[{"debt_type": "CONSENT_RECHECK",
                                   "resolved": False}]),
                 dict(risk_tier="HIGH", state_witnesses=[])):
        o = k.prepare(gate, b6, **over)
        assert o["commit_executable_now"] is False
        assert o["escrowed_commit_readiness_certificate"][
            "commit_executable_now"] is False


def test_ready_true_on_clean_path(gate):
    o = k.clean_outcome(gate)
    cert = o["escrowed_commit_readiness_certificate"]
    assert cert["ready_for_future_commit_only"] is True
    assert o["ready_for_future_commit_only"] is True
    assert cert["readiness_status"] == "READY_FOR_FUTURE_COMMIT_ONLY"


def test_readiness_factors_all_true_on_clean(gate):
    cert = k.clean_outcome(gate)["escrowed_commit_readiness_certificate"]
    assert all(cert["readiness_factors"].values())


def test_ready_false_on_escrow_tamper(gate):
    o = k.prepare(gate, k.b6_outcome(gate), observed_escrow_hash="deadbeef")
    cert = o["escrowed_commit_readiness_certificate"]
    assert cert["readiness_factors"]["escrow_not_tampered"] is False
    assert cert["ready_for_future_commit_only"] is False
    assert o["ready_for_future_commit_only"] is False


def test_ready_false_on_unresolved_debt(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  debt_items=[{"debt_type": "CONSENT_RECHECK",
                               "resolved": False}])
    cert = o["escrowed_commit_readiness_certificate"]
    assert cert["readiness_factors"]["revalidation_debt_cleared"] is False
    assert cert["ready_for_future_commit_only"] is False
    assert o["ready_for_future_commit_only"] is False


def test_ready_false_on_missing_quorum(gate):
    o = k.prepare(gate, k.b6_outcome(gate), risk_tier="HIGH",
                  state_witnesses=[])
    cert = o["escrowed_commit_readiness_certificate"]
    assert cert["readiness_factors"]["state_witness_quorum_satisfied"] is False
    assert cert["ready_for_future_commit_only"] is False
    assert o["ready_for_future_commit_only"] is False


def test_ready_false_on_unresolved_contestability(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  objections=[{"objection_id": "x", "resolved": False}])
    cert = o["escrowed_commit_readiness_certificate"]
    assert cert["readiness_factors"]["contestability_clear"] is False
    assert cert["ready_for_future_commit_only"] is False
    assert o["ready_for_future_commit_only"] is False


def test_certificate_not_bearer_not_signature_not_executing(gate):
    cert = k.clean_outcome(gate)["escrowed_commit_readiness_certificate"]
    assert cert["certificate_is_bearer_authority"] is False
    assert cert["is_production_signature"] is False
    assert cert["certificate_executes"] is False


def test_certificate_hash_excludes_itself_and_recomputes(gate):
    cert = k.clean_outcome(gate)["escrowed_commit_readiness_certificate"]
    recomputed = _core_hash(
        cert, "escrowed_commit_readiness_certificate_hash")
    assert recomputed == cert["escrowed_commit_readiness_certificate_hash"]


def test_certificate_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["escrowed_commit_readiness_certificate"][
        "escrowed_commit_readiness_certificate_hash"] == \
        o2["escrowed_commit_readiness_certificate"][
            "escrowed_commit_readiness_certificate_hash"]


def test_malicious_ready_means_execute_now_stays_blocked(gate):
    # "ready for future commit only means execute now"
    o = k.prepare(gate, k.b6_outcome(gate),
                  intent="ready for future commit only means execute now")
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["ready_for_future_commit_only"] is False
    assert o["commit_executable_now"] is False


def test_malicious_commit_executable_now_true_stays_blocked(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  execution_markers={"commit_executable_now": True})
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["commit_executable_now"] is False
    assert o["escrowed_commit_readiness_certificate"][
        "commit_executable_now"] is False


def test_readiness_endpoint_returns_certificate(gate):
    wid, _ = gate.prepared_write_intent()
    cert = gate.wi(wid, "/escrowed-commit-readiness").json()[
        "escrowed_commit_readiness_certificate"]
    assert cert["commit_executable_now"] is False
    assert cert["ready_for_future_commit_only"] is True
