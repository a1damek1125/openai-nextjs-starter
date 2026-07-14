"""TOOL-B9.2 v5: Governed Work Lineage Observatory core — clean certified work
run, derived-evidence-only, no external effect, canaries, causal graph,
reproducibility.

The observatory is LOCAL-ONLY, READ-ONLY over B9/B9.1 and DERIVED-EVIDENCE-ONLY:
it grants no authority, produces no external effect, delivers nothing externally,
releases no outbox and stores no secret or chain of thought.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_work_observability as wo
from tests import _b92_kernel as k


# --- kernel layer ----------------------------------------------------------
def test_clean_work_run_certified():
    o = k.clean_outcome()
    assert o["work_run_state"] == "WORK_OUTCOME_CERTIFIED"
    assert o["work_outcome_truth_state"] == "PROVEN"
    assert o["proof_of_work_outcome_valid"] is True
    assert o["work_outcome_certified"] is True
    assert o["all_signals"] == []


def test_clean_no_external_effect_and_no_authority():
    o = k.clean_outcome()
    assert o["no_external_effect"] is True
    assert o["is_authority"] is False
    for f in ("authorizes_execution", "authorizes_commit", "authorizes_recovery",
              "authorizes_rollback", "authorizes_abort", "authorizes_delivery",
              "authorizes_provider"):
        assert o[f] is False
    assert o["read_only_over_b9_and_b9_1"] is True
    assert o["mutates_transaction"] is False and o["mutates_recovery"] is False


def test_clean_actual_effect_fields_always_false():
    for over in ({}, {"attempt_markers": {"provider_call": True}},
                 {"secret_exposed_to_model": True}, {"external_delivery": True}):
        o = k.prepare(**over)
        assert o["produced_external_effect"] is False
        assert o["provider_called"] is False and o["message_sent"] is False
        assert o["payment_executed"] is False
        assert o["external_crm_mutated"] is False
        assert o["delivered_externally"] is False
        assert o["outbox_released"] is False


def test_clean_stores_no_secret_or_chain_of_thought():
    o = k.clean_outcome()
    assert o["stores_secret"] is False
    assert o["stores_chain_of_thought"] is False
    assert o["gateway_boundary"]["secret_injection_occurred"] is False
    assert o["gateway_boundary"]["stores_secret"] is False
    assert o["memory_snapshot"]["stores_chain_of_thought"] is False


def test_canary_harness_all_safe():
    o = k.clean_outcome()
    h = o["b92_canary_harness"]
    assert h["canary_count"] == 15
    assert h["all_canaries_safe"] is True
    assert len(h["canaries"]) == 15
    for c in h["canaries"]:
        assert c["no_message_sent"] is True
        assert c["no_payment_executed"] is True
        assert c["no_external_crm_mutation"] is True
        assert c["no_webhook_dispatched"] is True
        assert c["no_outbox_released"] is True


def test_causal_work_graph_shape():
    g = k.clean_outcome()["causal_work_graph"]
    assert g["node_count"] == 15
    assert g["edge_count"] == 12


def test_proof_bundle_component_count():
    assert k.clean_outcome()["b92_work_proof_bundle"]["component_count"] == 23


def test_powo_warning_states_no_authority():
    powo = k.clean_outcome()["proof_of_work_outcome"]
    assert powo["warning"] == wo.POWO_WARNING
    assert powo["authorizes_execution"] is False
    assert powo["authorizes_commit"] is False


def test_decision_hash_reproducible():
    assert k.prepare()["b92_decision_hash"] == k.prepare()["b92_decision_hash"]


def test_powo_and_twin_hash_recompute():
    o = k.clean_outcome()
    powo = o["proof_of_work_outcome"]
    assert _core_hash(powo, "proof_of_work_outcome_hash", "signal",
                      "verification_status") == powo["proof_of_work_outcome_hash"]
    twin = o["work_observation_twin"]
    assert _core_hash(twin, "twin_hash") == twin["twin_hash"]


def test_decision_hash_verify():
    o = k.clean_outcome()
    assert _core_hash(o, "b92_decision_hash", "work_run_id", "actor_id",
                      "decided_by_actor_id", "decided_by_actor_type",
                      "b92_state_hash") == o["b92_decision_hash"]


def test_no_bound_transaction_not_certified():
    o = k.prepare(bind_b9=False)
    assert o["work_run_state"] != "WORK_OUTCOME_CERTIFIED"
    assert o["proof_of_work_outcome_valid"] is False
    assert "TRANSACTION_BINDING_MISSING" in o["all_signals"]


# --- API layer -------------------------------------------------------------
def test_api_clean_observation_certified(gate):
    wrid, o = gate.observed_work()
    assert o["work_run_state"] == "WORK_OUTCOME_CERTIFIED"
    assert o["work_outcome_truth_state"] == "PROVEN"
    assert o["no_external_effect"] is True


def test_api_verify_valid(gate):
    from tests.conftest import OWNER
    wrid, _ = gate.observed_work()
    v = gate.c.post(
        "/ai-tools/local-transactions/observability/verify-work-run",
        json={"work_run_id": wrid}, headers=gate.h(OWNER)).json()
    assert v["b92_decision_hash_valid"] is True
    assert v["verification_status"] == "VALID"


def test_api_twin_endpoint(gate):
    wrid, _ = gate.observed_work()
    twin = gate.wo(wrid, "twin").json()["work_observation_twin"]
    assert twin["work_outcome_truth_state"] == "PROVEN"
    assert twin["non_authoritative"] is True


def test_api_policy_flags(gate):
    from tests.conftest import OWNER
    pol = gate.c.get("/ai-tools/local-transactions/observability/policy",
                     headers=gate.h(OWNER)).json()
    assert pol["local_work_observability_only"] is True
    assert pol["read_only_over_b9_and_b9_1"] is True
    assert pol["external_effect"] is False
    assert pol["production_ready"] is False
    assert pol["authorizes_execution"] is False
