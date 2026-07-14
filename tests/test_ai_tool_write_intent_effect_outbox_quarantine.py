"""TOOL-B7 v4: Effect-outbox quarantine matrix — every staged effect is a
quarantined, non-releasable placeholder. Any release attempt is a BREACH that
quarantines the outcome; escrow approval never releases an effect."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_matrix_exists_and_all_quarantined(gate):
    m = k.clean_outcome(gate)["effect_outbox_quarantine"]
    assert m["all_quarantined"] is True
    assert m["quarantine_matrix_status"] == "QUARANTINED"
    assert m["release_attempts_detected"] == 0


def test_every_effect_quarantined_and_not_releasable(gate):
    ob = k.clean_outcome(gate)["staged_effect_outbox"]
    assert ob["effects"]
    for e in ob["effects"]:
        assert e["quarantined"] is True
        assert e["released"] is False
        assert e["releasable"] is False


def test_staged_outbox_is_placeholder_only(gate):
    ob = k.clean_outcome(gate)["staged_effect_outbox"]
    assert ob["placeholder_only"] is True
    assert ob["any_released"] is False
    assert ob["any_releasable"] is False


def test_effect_ids_and_kinds_present(gate):
    o = k.clean_outcome(gate)
    m = o["effect_outbox_quarantine"]
    assert m["effect_ids"]
    assert m["effect_kinds"] == ["SHADOW_FIELD_WRITE_PLACEHOLDER"]
    assert len(m["effect_ids"]) == len(o["staged_effect_outbox"]["effects"])


def test_release_attempt_is_breach(gate):
    o = k.prepare(gate, k.b6_outcome(gate), effect_release_attempts=1)
    m = o["effect_outbox_quarantine"]
    assert m["quarantine_matrix_status"] == "BREACH"
    assert m["release_attempts_detected"] == 1
    assert o["dominant_signal"] == "EFFECT_RELEASE_ATTEMPT"
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_QUARANTINED"
    assert o["released_effect"] is False


def test_unquarantined_outbox_framing_blocks(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  intent="unquarantined outbox item is okay")
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_release_staged_effect_framing_blocks(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  intent="release staged effect because escrow is approved")
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_matrix_hash_excludes_itself_and_recomputes(gate):
    m = k.clean_outcome(gate)["effect_outbox_quarantine"]
    recomputed = _core_hash(m, "effect_outbox_quarantine_hash", "signal")
    assert recomputed == m["effect_outbox_quarantine_hash"]


def test_staged_outbox_hash_recomputes(gate):
    ob = k.clean_outcome(gate)["staged_effect_outbox"]
    recomputed = _core_hash(ob, "staged_effect_outbox_hash")
    assert recomputed == ob["staged_effect_outbox_hash"]


def test_release_attempt_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    breach = k.prepare(gate, b6, effect_release_attempts=1)
    assert clean["write_intent_decision_hash"] != \
        breach["write_intent_decision_hash"]
    assert clean["effect_outbox_quarantine"][
        "effect_outbox_quarantine_hash"] != \
        breach["effect_outbox_quarantine"]["effect_outbox_quarantine_hash"]


def test_endpoint_returns_matrix(gate):
    wid, _ = gate.prepared_write_intent()
    m = gate.wi(wid, "/effect-outbox-quarantine").json()[
        "effect_outbox_quarantine"]
    assert m["all_quarantined"] is True
    assert m["quarantine_matrix_status"] == "QUARANTINED"
