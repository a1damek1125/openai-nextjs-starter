"""TOOL-B2 quality binding event ledger.

Each quality check appends a valid hash-chained trio of events
(STARTED / COMPLETED / a result event). The binding is metadata only: a failing
quality check records a readiness blocker but never mutates the TOOL-B1
admission/security state, and the ledger says so.
"""
from finalis.ai_employee import tool_quality as tq
from tests.conftest import OWNER


def _ledger(gate, tool_id, actor=OWNER):
    return gate.c.get(f"/ai-tools/{tool_id}/quality/binding-ledger",
                      headers=gate.h(actor)).json()


def _forbidden_payment_tool(gate):
    return gate.register_quality_tool(
        tool_name="Pay Vendor Now", category="PAYMENT",
        side_effect_class="PAYMENT_MOVEMENT",
        declared_side_effects=["PAYMENT_MOVEMENT"],
        touches_payment=True).json()["tool_id"]


class TestChainValidity:
    def test_chain_valid_after_check(self, gate):
        tid, _ = gate.checked_quality_tool()
        led = _ledger(gate, tid)
        assert led["event_chain_valid"] is True

    def test_first_event_links_to_genesis(self, gate):
        tid, _ = gate.checked_quality_tool()
        evs = _ledger(gate, tid)["events"]
        assert evs[0]["previous_event_hash"] == tq.GENESIS

    def test_sequences_are_strictly_increasing(self, gate):
        tid, _ = gate.checked_quality_tool()
        seqs = [e["sequence"] for e in _ledger(gate, tid)["events"]]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == len(seqs)

    def test_every_event_carries_actor_and_hash(self, gate):
        tid, _ = gate.checked_quality_tool()
        for e in _ledger(gate, tid)["events"]:
            assert e["actor_id"]
            assert e["event_hash"]
            assert e["quality_event_version"]

    def test_recheck_appends_events_chain_still_valid(self, gate):
        tid, _ = gate.checked_quality_tool()
        before = _ledger(gate, tid)["event_count"]
        gate.quality_check(tid)
        led = _ledger(gate, tid)
        assert led["event_count"] > before
        assert led["event_chain_valid"] is True


class TestEventTypes:
    def test_started_and_completed_present(self, gate):
        tid, _ = gate.checked_quality_tool()
        types = [e["event_type"] for e in _ledger(gate, tid)["events"]]
        assert "QUALITY_CHECK_STARTED" in types
        assert "QUALITY_CHECK_COMPLETED" in types
        # Ordered: STARTED comes before COMPLETED.
        assert types.index("QUALITY_CHECK_STARTED") < types.index(
            "QUALITY_CHECK_COMPLETED")

    def test_check_emits_at_least_three_events(self, gate):
        tid, _ = gate.checked_quality_tool()
        assert _ledger(gate, tid)["event_count"] >= 3

    def test_pass_tool_records_pass_event(self, gate):
        tid, _ = gate.checked_quality_tool()
        types = {e["event_type"] for e in _ledger(gate, tid)["events"]}
        assert "QUALITY_PASS_RECORDED" in types
        assert "QUALITY_FAIL_RECORDED" not in types

    def test_completed_event_carries_gate_state_hash(self, gate):
        tid, rep = gate.checked_quality_tool()
        completed = [e for e in _ledger(gate, tid)["events"]
                     if e["event_type"] == "QUALITY_CHECK_COMPLETED"][0]
        assert completed["quality_gate_state_hash"] == rep[
            "quality_gate_state_hash"]


class TestFailingToolBinding:
    def test_forbidden_payment_tool_records_fail_event(self, gate):
        tid = _forbidden_payment_tool(gate)
        rep = gate.quality_check(tid).json()
        assert rep["quality_status"] not in ("QUALITY_PASS",
                                             "QUALITY_PASS_WITH_WARNINGS")
        types = {e["event_type"] for e in _ledger(gate, tid)["events"]}
        assert "QUALITY_FAIL_RECORDED" in types
        assert "QUALITY_PASS_RECORDED" not in types


class TestMetadataOnly:
    def test_failing_check_does_not_change_b1_head_status(self, gate):
        tid = _forbidden_payment_tool(gate)
        before = gate.c.get(f"/ai-tools/{tid}",
                            headers=gate.h(OWNER)).json()["status"]
        gate.quality_check(tid)
        after = gate.c.get(f"/ai-tools/{tid}",
                           headers=gate.h(OWNER)).json()["status"]
        assert before == after == "FORBIDDEN_CAPABILITY"

    def test_passing_check_does_not_admit_tool(self, gate):
        reg = gate.register_quality_tool().json()
        assert reg["status"] == "DRAFT"
        assert reg["admitted"] is False
        gate.quality_check(reg["tool_id"])
        after = gate.c.get(f"/ai-tools/{reg['tool_id']}",
                           headers=gate.h(OWNER)).json()
        assert after["status"] == "DRAFT"
        assert after["admitted"] is False

    def test_binding_note_declares_admission_mutation_missing(self, gate):
        tid, _ = gate.checked_quality_tool()
        note = _ledger(gate, tid)["binding_note"]
        assert "MISSING/NEXT" in note
        assert "cannot itself flip a security state" in note
