"""TOOL-B7 v4: Escrow expiry and renewal policy — an escrow past its TTL is
STALE and requires full revalidation before renewal; renewal itself never
executes."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_clean_escrow_valid_no_renewal(gate):
    ex = k.clean_outcome(gate)["escrow_expiry_policy"]
    assert ex["expiry_status"] == "VALID"
    assert ex["renewal_required"] is False
    assert ex["renewal_requirements"] == []


def test_expiry_policy_exists(gate):
    ex = k.clean_outcome(gate)["escrow_expiry_policy"]
    assert ex["escrow_expiry_policy_id"].startswith("exp-")
    assert "current_epoch" in ex


def test_expired_escrow_marks_stale(gate):
    o = k.prepare(gate, k.b6_outcome(gate), current_epoch=9999,
                  escrow_expires_epoch=1)
    assert o["dominant_signal"] == "ESCROW_EXPIRED"
    assert o["write_intent_status"] == "WRITE_INTENT_STALE"


def test_expired_escrow_requires_renewal(gate):
    ex = k.prepare(gate, k.b6_outcome(gate), current_epoch=9999,
                   escrow_expires_epoch=1)["escrow_expiry_policy"]
    assert ex["expiry_status"] == "EXPIRED"
    assert ex["renewal_required"] is True
    assert "FULL_REVALIDATION_BEFORE_RENEWAL" in ex["renewal_requirements"]


def test_renewal_does_not_execute(gate):
    ex = k.prepare(gate, k.b6_outcome(gate), current_epoch=9999,
                   escrow_expires_epoch=1)["escrow_expiry_policy"]
    assert ex["renewal_executes"] is False


def test_malicious_expired_but_still_valid_blocks(gate):
    # "escrow expired but still valid" — expiry must win.
    o = k.prepare(gate, k.b6_outcome(gate), current_epoch=9999,
                  escrow_expires_epoch=1,
                  intent="escrow expired but still valid")
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_expired_escrow_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    expired = k.prepare(gate, b6, current_epoch=9999, escrow_expires_epoch=1)
    assert clean["write_intent_decision_hash"] != \
        expired["write_intent_decision_hash"]


def test_not_yet_expired_stays_valid(gate):
    ex = k.prepare(gate, k.b6_outcome(gate), current_epoch=1,
                   escrow_expires_epoch=100)["escrow_expiry_policy"]
    assert ex["expiry_status"] == "VALID"
    assert ex["renewal_required"] is False


def test_expiry_hash_excludes_itself_and_recomputes(gate):
    ex = k.clean_outcome(gate)["escrow_expiry_policy"]
    recomputed = _core_hash(ex, "escrow_expiry_policy_hash", "signal")
    assert recomputed == ex["escrow_expiry_policy_hash"]


def test_expiry_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["escrow_expiry_policy"]["escrow_expiry_policy_hash"] == \
        o2["escrow_expiry_policy"]["escrow_expiry_policy_hash"]


def test_expiry_endpoint_returns_policy(gate):
    wid, _ = gate.prepared_write_intent()
    ex = gate.wi(wid, "/escrow-expiry").json()["escrow_expiry_policy"]
    assert ex["expiry_status"] == "VALID"
    assert ex["renewal_executes"] is False
