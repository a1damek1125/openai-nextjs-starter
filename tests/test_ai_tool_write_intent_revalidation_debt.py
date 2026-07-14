"""TOOL-B7 v4: Revalidation Debt Ledger — outstanding debt must be resolved
(with a server witness) before a draft can ever become future-commit ready.
The client cannot self-attest resolution."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k

CONSENT = {"debt_type": "CONSENT_RECHECK", "resolved": False}
CONSENT_SELF = {"debt_type": "CONSENT_RECHECK", "resolved": True,
                "server_verified_resolution": False}
CONSENT_OK = {"debt_type": "CONSENT_RECHECK", "resolved": True,
              "server_verified_resolution": True}


def test_ledger_exists_and_versioned(gate):
    led = k.clean_outcome(gate)["revalidation_debt_ledger"]
    assert led["revalidation_debt_ledger_id"].startswith("dbt-")
    assert led["revalidation_debt_ledger_version"]
    assert "debt_items" in led and "unresolved_debt_items" in led


def test_clean_debt_status_cleared_no_signal(gate):
    o = k.clean_outcome(gate)
    led = o["revalidation_debt_ledger"]
    assert led["debt_status"] == "CLEARED"
    assert led["unresolved_count"] == 0
    assert led["signal"] is None
    assert "REVALIDATION_DEBT_UNRESOLVED" not in o["all_signals"]


def test_unresolved_debt_blocks_with_needs_revalidation(gate):
    o = k.prepare(gate, k.b6_outcome(gate), debt_items=[CONSENT])
    assert o["dominant_signal"] == "REVALIDATION_DEBT_UNRESOLVED"
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_NEEDS_REVALIDATION"
    assert o["write_intent_decision_status"] == \
        "WRITE_INTENT_DECISION_NEEDS_REVALIDATION"
    led = o["revalidation_debt_ledger"]
    assert led["debt_status"] == "OUTSTANDING"
    assert led["unresolved_count"] == 1


def test_client_cannot_self_resolve_debt(gate):
    # resolved=True but server_verified_resolution missing -> still unresolved.
    o = k.prepare(gate, k.b6_outcome(gate), debt_items=[CONSENT_SELF])
    assert o["dominant_signal"] == "REVALIDATION_DEBT_UNRESOLVED"
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_NEEDS_REVALIDATION"


def test_server_verified_resolution_clears(gate):
    o = k.prepare(gate, k.b6_outcome(gate), debt_items=[CONSENT_OK])
    assert o["dominant_signal"] == "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["revalidation_debt_ledger"]["debt_status"] == "CLEARED"


def test_unresolved_debt_blocks_future_readiness(gate):
    o = k.prepare(gate, k.b6_outcome(gate), debt_items=[CONSENT])
    assert o["ready_for_future_commit_only"] is False
    assert o["commit_executable_now"] is False


def test_unresolved_required_before_future_commit_lists_type(gate):
    led = k.prepare(gate, k.b6_outcome(gate),
                    debt_items=[CONSENT])["revalidation_debt_ledger"]
    assert "CONSENT_RECHECK" in led["required_before_future_commit"]


def test_unresolved_debt_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    debt = k.prepare(gate, b6, debt_items=[CONSENT])
    assert clean["write_intent_decision_hash"] != \
        debt["write_intent_decision_hash"]


def test_unknown_debt_type_falls_back_not_crash(gate):
    # An unknown debt_type is coerced to a valid type (AUTHORITY_RECHECK).
    o = k.prepare(gate, k.b6_outcome(gate), debt_items=[{
        "debt_type": "NOT_A_REAL_TYPE", "resolved": True,
        "server_verified_resolution": True}])
    led = o["revalidation_debt_ledger"]
    assert led["debt_items"][0]["debt_type"] == "AUTHORITY_RECHECK"
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_ledger_hash_excludes_itself_and_recomputes(gate):
    led = k.clean_outcome(gate)["revalidation_debt_ledger"]
    recomputed = _core_hash(led, "revalidation_debt_ledger_hash", "signal")
    assert recomputed == led["revalidation_debt_ledger_hash"]


def test_ledger_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["revalidation_debt_ledger"]["revalidation_debt_ledger_hash"] == \
        o2["revalidation_debt_ledger"]["revalidation_debt_ledger_hash"]


def test_api_revalidation_debt_endpoint_clean(gate):
    wid, _ = gate.prepared_write_intent()
    led = gate.wi(wid, "/revalidation-debt").json()["revalidation_debt_ledger"]
    assert led["debt_status"] == "CLEARED"
    assert led["unresolved_count"] == 0


def test_api_unresolved_debt_needs_revalidation(gate):
    wid, o = gate.prepared_write_intent(debt_items=[CONSENT])
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_NEEDS_REVALIDATION"
    assert o["dominant_signal"] == "REVALIDATION_DEBT_UNRESOLVED"
