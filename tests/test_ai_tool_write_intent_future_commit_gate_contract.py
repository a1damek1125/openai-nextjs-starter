"""TOOL-B7 v4: Future commit gate contract — a PLACEHOLDER-only description of
what a future human-approved commit would require. It has no commit endpoint,
no commit capability and never executes. Any endpoint/capability presence
blocks."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_contract_exists_placeholder_only(gate):
    c = k.clean_outcome(gate)["future_commit_gate_contract"]
    assert c["future_commit_gate_contract_id"].startswith("fcg-")
    assert c["placeholder_only"] is True
    assert c["contract_status"] == "PLACEHOLDER"


def test_no_commit_endpoint_or_capability_on_clean(gate):
    c = k.clean_outcome(gate)["future_commit_gate_contract"]
    assert c["commit_endpoint_present"] is False
    assert c["commit_capability_present"] is False


def test_contract_does_not_execute(gate):
    c = k.clean_outcome(gate)["future_commit_gate_contract"]
    assert c["contract_executes"] is False


def test_required_fields_present(gate):
    c = k.clean_outcome(gate)["future_commit_gate_contract"]
    for f in ("required_revalidations", "required_approvals",
              "required_state_witness_quorum", "required_conflict_check",
              "required_contestability_state", "required_obligation_state"):
        assert f in c, f
    assert "INDEPENDENT_HUMAN_APPROVAL" in c["required_approvals"]
    assert "MEANINGFUL_JUDGMENT" in c["required_approvals"]


def test_commit_endpoint_present_blocks(gate):
    o = k.prepare(gate, k.b6_outcome(gate), commit_endpoint_present=True)
    assert o["dominant_signal"] == "COMMIT_GATE_ENDPOINT_PRESENT"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["future_commit_gate_contract"]["contract_status"] == "INVALID"


def test_commit_capability_present_blocks(gate):
    o = k.prepare(gate, k.b6_outcome(gate), commit_capability_present=True)
    assert o["dominant_signal"] == "COMMIT_GATE_ENDPOINT_PRESENT"
    c = o["future_commit_gate_contract"]
    assert c["commit_capability_present"] is True
    assert c["contract_executes"] is False


def test_endpoint_present_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    present = k.prepare(gate, b6, commit_endpoint_present=True)
    assert clean["write_intent_decision_hash"] != \
        present["write_intent_decision_hash"]


def test_contract_hash_excludes_itself_and_recomputes(gate):
    c = k.clean_outcome(gate)["future_commit_gate_contract"]
    recomputed = _core_hash(c, "future_commit_gate_contract_hash", "signal")
    assert recomputed == c["future_commit_gate_contract_hash"]


def test_contract_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["future_commit_gate_contract"][
        "future_commit_gate_contract_hash"] == \
        o2["future_commit_gate_contract"]["future_commit_gate_contract_hash"]


def test_contract_endpoint_returns_placeholder(gate):
    wid, _ = gate.prepared_write_intent()
    c = gate.wi(wid, "/future-commit-gate-contract").json()[
        "future_commit_gate_contract"]
    assert c["placeholder_only"] is True
    assert c["commit_endpoint_present"] is False
    assert c["contract_executes"] is False
