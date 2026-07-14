"""TOOL-B8 v5: Machine-Checkable Pre-B9 Assurance Envelope — evidence only,
cannot authorize B9, cannot execute, hash binds every v5 component."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_envelope_exists_and_evidence_only(gate):
    e = k.clean_outcome(gate)["assurance_envelope"]
    assert e["assurance_envelope_id"].startswith("ae-")
    assert e["decision_status"] == "VALID"
    assert e["evidence_only"] is True and e["safe_viewable"] is True


def test_envelope_cannot_authorize_or_execute(gate):
    e = k.clean_outcome(gate)["assurance_envelope"]
    assert e["is_authority"] is False
    assert e["authorizes_b9"] is False
    assert e["executes"] is False
    assert e["b9_revalidation_required"] is True


def test_envelope_binds_all_v5_component_hashes(gate):
    e = k.clean_outcome(gate)["assurance_envelope"]
    for f in ("evidence_closure_net_hash", "non_delegable_artifact_seal_hash",
              "b9_negative_capability_hash", "cross_artifact_consistency_hash",
              "route_topology_diff_hash", "trace_completeness_witness_hash",
              "proof_obligation_matrix_hash", "production_claim_scanner_hash",
              "final_ci_gate_hash", "schema_version"):
        assert e[f], f


def test_envelope_hash_excludes_itself_and_recomputes(gate):
    e = k.clean_outcome(gate)["assurance_envelope"]
    recomputed = _core_hash(e, "assurance_envelope_hash", "dominant_reason_code")
    assert recomputed == e["assurance_envelope_hash"]


def test_envelope_hash_deterministic_across_actor(gate):
    b7 = k.b7_outcome(gate)
    a = k.prepare(gate, b7, actor_id="alice")["assurance_envelope"]
    b = k.prepare(gate, b7, actor_id="bob", actor_type="ai_employee")[
        "assurance_envelope"]
    assert a["assurance_envelope_hash"] == b["assurance_envelope_hash"]


def test_closure_failure_changes_envelope_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["assurance_envelope"]["assurance_envelope_hash"]
    broken = k.prepare(gate, b7, force_unclosed_claims=["X"])[
        "assurance_envelope"]["assurance_envelope_hash"]
    assert clean != broken


def test_production_claim_changes_envelope_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["assurance_envelope"]["assurance_envelope_hash"]
    poisoned = k.prepare(gate, b7, extra_claims={"production_ready": True})[
        "assurance_envelope"]["assurance_envelope_hash"]
    assert clean != poisoned


def test_forced_structural_invalid_blocks(gate):
    o = k.clean_outcome(gate, force_assurance_invalid=True)
    assert "ASSURANCE_ENVELOPE_INVALID" in o["all_signals"]
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_malicious_envelope_grants_commit_blocks(gate):
    # "assurance envelope grants commit" -> execution marker rejected
    o = k.clean_outcome(gate, execution_markers={"real_commit": True})
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"
    assert o["commit_executable_now"] is False


def test_envelope_endpoint_returns_envelope(gate):
    sid, _ = gate.prepared_commit_simulation()
    e = gate.cs(sid, "/assurance-envelope").json()["assurance_envelope"]
    assert e["decision_status"] == "VALID"
    assert e["is_authority"] is False
