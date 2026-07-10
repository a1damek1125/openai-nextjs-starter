"""TOOL-B9.1 v4: Recovery Safety Case (section 8), Transaction Recovery Twin
(section 1) and Proof-of-Recovery contract (section 6).

The Recovery Safety Case is a local VERIFICATION of recovery safety claims — it
is PROOF, never authority (is_authority False). The Recovery Twin binds the
original transaction / proof-of-execution / certificate / replay-context hashes
so recovery reasons over the real committed transaction. The recovery contract
forbids every external effect and every non-local recovery scope; a missing
contract or a forbidden scope fails closed.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_local_recovery as lr
from tests import _b91_kernel as k


# --- kernel layer: Recovery Safety Case (section 8) ------------------------
def test_sc_clean_safety_case_valid():
    sc = k.clean_outcome()["recovery_safety_case"]
    assert sc["verification_status"] == "VALID"
    assert sc["failed_predicates"] == []
    assert len(sc["passed_predicates"]) > 0


def test_sc_all_required_claims_present():
    sc = k.clean_outcome()["recovery_safety_case"]
    for claim in lr.REQUIRED_SAFETY_CLAIMS:
        assert claim in sc["claims"]
        assert sc["claim_evaluation"][claim] is True


def test_sc_safety_case_is_not_authority():
    sc = k.clean_outcome()["recovery_safety_case"]
    assert sc["is_authority"] is False
    # Reflected at the top level of the outcome too.
    assert k.clean_outcome()["recovery_safety_case_is_authority"] is False


def test_sc_passed_predicates_cover_required_claims():
    sc = k.clean_outcome()["recovery_safety_case"]
    for claim in lr.REQUIRED_SAFETY_CLAIMS:
        assert claim in sc["passed_predicates"]


def test_sc_safety_case_hash_recompute():
    sc = k.clean_outcome()["recovery_safety_case"]
    assert _core_hash(sc, "safety_case_hash", "signal", "verification_status") \
        == sc["safety_case_hash"]


# --- kernel layer: Transaction Recovery Twin (section 1) -------------------
def test_sc_twin_binds_original_hashes():
    tw = k.clean_outcome()["twin"]
    assert tw["original_transaction_hash"]
    assert tw["original_proof_of_execution_hash"]
    assert tw["original_certificate_hash"]
    assert tw["replay_context_hash"]


def test_sc_twin_no_missing_components_on_clean():
    tw = k.clean_outcome()["twin"]
    assert tw["missing_components"] == []
    assert tw["current_transaction_state"] == "B9_LOCAL_COMMIT_APPLIED"


def test_sc_twin_hash_deterministic():
    a = k.prepare()["twin"]["recovery_twin_hash"]
    b = k.prepare()["twin"]["recovery_twin_hash"]
    assert a == b


def test_sc_twin_hash_recompute():
    tw = k.clean_outcome()["twin"]
    assert _core_hash(tw, "recovery_twin_hash", "signal") \
        == tw["recovery_twin_hash"]


# --- kernel layer: recovery contract (section 6) ---------------------------
def test_sc_clean_contract_valid():
    ct = k.clean_outcome()["recovery_contract"]
    assert ct["contract_status"] == "VALID"


def test_sc_contract_forbids_external_effects():
    ct = k.clean_outcome()["recovery_contract"]
    for effect in ("provider_call", "message_send", "payment", "outbox_release"):
        assert effect in ct["forbidden_external_effects"]


def test_sc_contract_missing_fails_closed():
    o = k.prepare(desired_recovery_action="RECOVER", recovery_contract_missing=True)
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "RECOVERY_CONTRACT_MISSING"
    assert o["recovery_applied"] is False
    assert o["produced_external_effect"] is False


def test_sc_forbidden_recovery_scope_fails_closed():
    o = k.prepare(desired_recovery_action="RECOVER",
                  requested_recovery_scope=["external"])
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "FORBIDDEN_RECOVERY_SCOPE"
    assert o["recovery_applied"] is False
    assert o["outbox_released"] is False


def test_sc_contract_hash_recompute():
    ct = k.clean_outcome()["recovery_contract"]
    assert _core_hash(ct, "recovery_contract_hash", "signal") \
        == ct["recovery_contract_hash"]


# --- API layer -------------------------------------------------------------
def test_sc_api_safety_case_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="run")
    sc = gate.rc(rid, "safety-case").json()["recovery_safety_case"]
    assert sc["verification_status"] == "VALID"
    assert sc["is_authority"] is False
    for claim in lr.REQUIRED_SAFETY_CLAIMS:
        assert claim in sc["claims"]


def test_sc_api_twin_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="run")
    tw = gate.rc(rid, "twin").json()["twin"]
    assert tw["recovery_twin_hash"]
    assert tw["original_transaction_hash"]
    assert tw["original_certificate_hash"]


def test_sc_api_contract_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="run")
    ct = gate.rc(rid, "contract").json()["recovery_contract"]
    assert ct["contract_status"] == "VALID"
    for effect in ("provider_call", "message_send", "payment", "outbox_release"):
        assert effect in ct["forbidden_external_effects"]


def test_sc_api_forbidden_scope_fails_closed(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="run",
                     requested_recovery_scope=["external"]).json()
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "FORBIDDEN_RECOVERY_SCOPE"


def test_sc_api_contract_missing_fails_closed(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="run", recovery_contract_missing=True).json()
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "RECOVERY_CONTRACT_MISSING"
    assert o["produced_external_effect"] is False
