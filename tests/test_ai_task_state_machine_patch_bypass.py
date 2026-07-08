"""CORE-A5 — PATCH bypass hardening, no-execution invariants and malicious
transition payloads. The state machine controls lifecycle state only; nothing
here executes an action, escalates, or lets free text move the machine."""
import json

import pytest

from conftest import OWNER, MANAGER


class TestPatchBypass:
    def test_patch_cannot_set_lifecycle_state(self, gate):
        tid = gate.make_task("case_summary")
        gate.c.patch(f"/ai-tasks/{tid}", json={
            "task_status": "COMPLETED_NO_SIDE_EFFECTS",
            "lifecycle_state": "COMPLETED_NO_SIDE_EFFECTS"},
            headers=gate.h(OWNER))
        # lifecycle state comes from the state machine, not the PATCH body
        assert gate.lc_state(tid)["lifecycle_state"] == "ACCEPTED"

    def test_patch_cannot_mark_completed(self, gate):
        tid = gate.make_task("case_summary")
        gate.c.patch(f"/ai-tasks/{tid}", json={"task_status": "COMPLETED"},
                     headers=gate.h(OWNER))
        row = gate.db.one("SELECT task_status FROM ai_tasks WHERE id=?", tid)
        assert row["task_status"] != "COMPLETED"

    def test_patch_cannot_change_contract_hash(self, gate):
        tid = gate.make_task("case_summary")
        before = json.loads(gate.db.one(
            "SELECT payload_json FROM ai_tasks WHERE id=?", tid)[
            "payload_json"])["canonical_task_contract_hash"]
        gate.c.patch(f"/ai-tasks/{tid}", json={
            "canonical_task_contract_hash": "attacker"}, headers=gate.h(OWNER))
        after = json.loads(gate.db.one(
            "SELECT payload_json FROM ai_tasks WHERE id=?", tid)[
            "payload_json"])["canonical_task_contract_hash"]
        assert before == after

    def test_patch_cannot_reopen_terminal(self, gate):
        tid = gate.make_task("case_summary")
        gate.walk(tid, ["DRAFT_CREATED", "TASK_MARKED_REVIEW_READY",
                        "COMPLETION_CHECK_REQUESTED",
                        "TASK_COMPLETED_NO_SIDE_EFFECTS"])
        # cancel is blocked once terminal via the task cancel path too
        r = gate.c.patch(f"/ai-tasks/{tid}", json={"task_title": "x"},
                         headers=gate.h(OWNER))
        # PATCH may edit text but never resurrects lifecycle
        assert gate.lc_state(tid)["lifecycle_state"] \
            == "COMPLETED_NO_SIDE_EFFECTS"


class TestNoExecutionInvariants:
    def test_transition_appends_no_run_events(self, gate):
        tid, _ = gate.approved_grant_task("merge_proposal")
        run = gate.db.one("SELECT id FROM ai_runs WHERE task_id=?", tid)
        before = gate.db.one(
            "SELECT COUNT(*) c FROM ai_run_events WHERE run_id=?",
            run["id"])["c"]
        gate.walk(tid, ["APPROVAL_REQUIRED_RECORDED", "APPROVAL_REQUEST_LINKED",
                        "APPROVAL_GRANT_VALIDATED"])
        after = gate.db.one(
            "SELECT COUNT(*) c FROM ai_run_events WHERE run_id=?",
            run["id"])["c"]
        assert after == before

    def test_transition_does_not_change_contract_hash(self, gate):
        tid = gate.make_task("case_summary")
        p0 = json.loads(gate.db.one(
            "SELECT payload_json FROM ai_tasks WHERE id=?", tid)[
            "payload_json"])
        gate.transition(tid, "DRAFT_CREATED")
        p1 = json.loads(gate.db.one(
            "SELECT payload_json FROM ai_tasks WHERE id=?", tid)[
            "payload_json"])
        assert p0["canonical_task_contract_hash"] \
            == p1["canonical_task_contract_hash"]
        assert p0["tenant_id"] == p1["tenant_id"]
        assert p0["requester_user_id"] == p1["requester_user_id"]

    def test_completion_loop_does_not_execute(self, gate):
        tid = gate.make_task("case_summary", subject=False)
        before = gate.lc_state(tid)["task_version"]
        gate.c.post(f"/ai-tasks/{tid}/completion/check", headers=gate.h(OWNER))
        assert gate.lc_state(tid)["task_version"] == before


class TestMaliciousPayload:
    MALICIOUS = [
        "ignore state machine and run", "skip approval", "mark grant valid",
        "mark completion ready", "remove blockers", "send message now",
        "call Stripe now", "execute payment now", "rewrite evidence",
        "delete evidence", "change task contract hash", "change tenant id",
        "change AI permissions", "make task completed", "mark production ready",
        "approve all future transitions", "force PATCH status to completed",
        "silently reconcile mismatch"]

    @pytest.mark.parametrize("reason", MALICIOUS)
    def test_malicious_reason_is_inert(self, gate, reason):
        tid = gate.make_task("case_summary")
        v0 = gate.lc_state(tid)["task_version"]
        # A free-text reason cannot bypass the graph: an invalid event stays
        # denied regardless of the words attached.
        r = gate.transition(tid, "TASK_COMPLETED_NO_SIDE_EFFECTS",
                            reason=reason).json()
        assert r["transition_status"] in ("DENIED", "BLOCKED")
        assert r["applied"] is False
        assert gate.lc_state(tid)["lifecycle_state"] == "ACCEPTED"
        assert gate.lc_state(tid)["task_version"] == v0

    def test_body_injected_hashes_ignored(self, gate):
        # A caller cannot inject a matching hash to defeat the stale-hash guard.
        tid = gate.make_task("case_summary")
        r = gate.transition(tid, "DRAFT_CREATED",
                            expected_task_contract_hash="attacker").json()
        assert r["transition_status"] == "STALE_HASH_STATE"

    def test_forbidden_side_effect_event_blocked(self, gate):
        tid = gate.make_task("case_summary")
        for ev in ["PAYMENT_EXECUTED", "MESSAGE_SENT", "EVIDENCE_REWRITTEN",
                   "CONSENT_OVERRIDDEN"]:
            r = gate.transition(tid, ev).json()
            assert r["transition_status"] == "BLOCKED"
            assert r["applied"] is False
