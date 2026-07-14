"""TOOL-B5 null-broker HTTP API surface: create/list/get/outcome, all the
sub-read projections, policy/registry, and proof that there is NO execute
endpoint anywhere. All GREEN — verified against live app behavior."""
from finalis.ai_employee import tool_broker as b
from tests.conftest import OWNER


# slug -> response key that the sub-read endpoint returns (mirrors the server's
# _BROKER_SUBFIELDS mapping; kept in the test to lock the contract).
SUB_READS = {
    "four-plane": "four_plane_model",
    "plane-non-interference": "plane_non_interference",
    "open-checkpoint": "broker_open_checkpoint",
    "assumption-ledger": "assumption_capture_ledger",
    "safety-lattice": "broker_safety_lattice",
    "multi-request-ledger": "multi_request_safety_ledger",
    "cross-request-effect-conservation": "cross_request_effect_conservation",
    "cumulative-risk-conservation": "cumulative_risk_conservation",
    "null-output-non-exfiltration": "null_output_non_exfiltration",
    "safe-output-projection": "safe_output_projection",
    "credential-free-corridor": "credential_free_corridor",
    "token-non-derivation": "token_non_derivation",
    "adapter-manifest-freeze": "adapter_manifest_freeze",
    "adapter-non-resolution": "adapter_non_resolution",
    "runtime-surface-diff": "runtime_surface_diff",
    "capability-identity-seal": "capability_identity_seal",
    "certificate-chain-closure": "certificate_chain_closure",
    "null-effector": "null_effector",
    "side-effect-zero": "side_effect_zero",
    "absence-proofs": "absence_proofs",
    "bypass-sentinel": "broker_bypass_sentinel",
    "broker-non-execution": "broker_non_execution_proof",
    "negative-execution-certificate": "negative_execution_certificate",
    "proof-carrying-certificate": "proof_carrying_broker_action_certificate",
    "outcome-closure": "outcome_closure_checkpoint",
    "fault-injection": "fault_injection_harness",
    "release-gate": "broker_release_gate_report",
    "conformance-vector": "broker_conformance_vector",
    "proof-bundle": "broker_proof_bundle",
}


def test_create_from_b4_decision_returns_prepared_outcome(gate):
    _, _, d = gate.b4_decision()
    r = gate.broker_request(d["decision_id"])
    assert r.status_code == 200
    o = r.json()
    assert o["broker_request_id"]
    assert o["broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    assert o["dominant_signal"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    assert o["effect_outcome"] == "NO_EFFECT_OUTCOME"
    assert o["executes_nothing"] is True
    assert o["is_execution"] is False
    assert o["null_effect_only"] is True
    assert o["requires_future_runtime"] is True


def test_create_from_proposal_id(gate):
    _, _, d = gate.b4_decision()
    r = gate.broker_request(body={"proposal_id": d["proposal_id"]})
    assert r.status_code == 200
    assert r.json()["broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"


def test_list_broker_requests(gate):
    rid, _ = gate.prepared_broker()
    lst = gate.c.get("/ai-tools/broker/requests", headers=gate.h()).json()
    assert isinstance(lst, list)
    assert any(row.get("broker_request_envelope_id") == rid for row in lst)


def test_get_request_envelope(gate):
    rid, _ = gate.prepared_broker()
    env = gate.br(rid).json()
    assert env["broker_request_hash"]
    assert env["broker_request_envelope_id"]


def test_get_outcome(gate):
    rid, _ = gate.prepared_broker()
    oc = gate.br(rid, "/outcome").json()
    assert oc["broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    assert oc["broker_request_id"] == rid


def test_unknown_request_id_is_404(gate):
    assert gate.br("no-such-id").status_code == 404
    assert gate.br("no-such-id", "/outcome").status_code == 404


def test_policy_endpoint(gate):
    p = gate.c.get("/ai-tools/broker/policy", headers=gate.h()).json()
    assert p["executes_tools"] is False
    assert p["has_execute_endpoint"] is False
    assert p["issues_tokens"] is False
    assert p["derives_tokens"] is False
    assert p["reads_credentials"] is False
    assert p["calls_external_provider"] is False
    assert p["resolves_real_adapter"] is False
    assert p["most_permissive_outcome"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"


def test_registry_endpoint(gate):
    rid, _ = gate.prepared_broker()
    reg = gate.c.get("/ai-tools/broker/registry", headers=gate.h()).json()
    assert reg["broker_request_count"] >= 1
    assert reg["broker_outcome_count"] >= 1
    assert reg["outcomes_by_status"].get("BROKER_PREPARED_FOR_FUTURE_ONLY") >= 1


def test_all_sub_reads_return_expected_key(gate):
    rid, _ = gate.prepared_broker()
    for slug, key in SUB_READS.items():
        r = gate.br(rid, "/" + slug)
        assert r.status_code == 200, f"{slug} -> {r.status_code}"
        body = r.json()
        assert key in body, f"{slug} missing key {key}"
        assert body["broker_request_id"] == rid


def test_no_execute_endpoint_anywhere(gate):
    rid, _ = gate.prepared_broker()
    # Global execute/run routes do not exist.
    for path in ("/ai-tools/broker/execute", "/ai-tools/broker/run"):
        assert gate.c.post(path, json={}, headers=gate.h()).status_code in (
            404, 405)
        assert gate.c.get(path, headers=gate.h()).status_code in (404, 405)
    # Per-request execute route does not exist.
    assert gate.br(rid, "/execute", method="POST").status_code in (404, 405)
    assert gate.br(rid, "/run", method="POST").status_code in (404, 405)
