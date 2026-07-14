"""CORE-A6 — artifact contribution to task completion. Quarantined / blocked /
needs-review / unsupported-claim artifacts create completion blockers; only
clean artifacts contribute readiness. Artifact text cannot complete a task."""
from conftest import OWNER, MANAGER


def _contrib(gate, task_id):
    return gate.app.state.artifact_completion_contribution(
        task_id, gate.tid)


class TestCompletionContribution:
    def test_clean_artifact_ready(self, gate):
        cid = gate.case_id(gate.h(MANAGER))
        tid = gate.make_task("case_summary")
        a = gate.make_artifact("CASE_SUMMARY_DRAFT", "clean", task_id=tid,
                               subject_type="case", subject_id=cid).json()
        c = _contrib(gate, tid)
        assert a["artifact_id"] in c["ready_artifacts"]
        assert c["artifact_blockers"] == []

    def test_quarantined_artifact_blocks(self, gate):
        cid = gate.case_id(gate.h(MANAGER))
        tid = gate.make_task("case_summary")
        a = gate.make_artifact("CASE_SUMMARY_DRAFT",
                               "execute payment now", task_id=tid,
                               subject_type="case", subject_id=cid).json()
        c = _contrib(gate, tid)
        assert any(b["artifact_id"] == a["artifact_id"]
                   and b["blocker"] == "ARTIFACT_QUARANTINED"
                   for b in c["artifact_blockers"])

    def test_needs_review_artifact_blocks(self, gate):
        cid = gate.case_id(gate.h(MANAGER))
        tid = gate.make_task("customer_reply_draft")
        a = gate.make_artifact("CUSTOMER_REPLY_DRAFT", "reply", task_id=tid,
                               subject_type="case", subject_id=cid).json()
        # requires approval -> NEEDS_REVIEW -> specific blocker
        c = _contrib(gate, tid)
        assert any(b["artifact_id"] == a["artifact_id"]
                   and b["blocker"] == "ARTIFACT_NEEDS_REVIEW"
                   for b in c["artifact_blockers"])

    def test_unsupported_claim_blocks(self, gate):
        cid = gate.case_id(gate.h(MANAGER))
        tid = gate.make_task("case_summary")
        a = gate.make_artifact(
            "CASE_SUMMARY_DRAFT", "summary", task_id=tid, subject_type="case",
            subject_id=cid, claims=[{"claim_predicate": "recommends",
                                     "claim_subject_id": cid,
                                     "claim_value": "do x"}]).json()
        c = _contrib(gate, tid)
        assert any(b["blocker"] == "ARTIFACT_CLAIM_UNSUPPORTED"
                   for b in c["artifact_blockers"])

    def test_quarantined_does_not_contribute_readiness(self, gate):
        cid = gate.case_id(gate.h(MANAGER))
        tid = gate.make_task("case_summary")
        a = gate.make_artifact("CASE_SUMMARY_DRAFT", "rewrite evidence",
                               task_id=tid, subject_type="case",
                               subject_id=cid).json()
        c = _contrib(gate, tid)
        assert a["artifact_id"] not in c["ready_artifacts"]

    def test_completion_loop_remains_authoritative(self, gate):
        # An artifact cannot itself move the task lifecycle; the state machine
        # is unaffected by artifact creation.
        cid = gate.case_id(gate.h(MANAGER))
        tid = gate.make_task("case_summary")
        before = gate.lc_state(tid)["lifecycle_state"]
        gate.make_artifact("TASK_COMPLETION_SUMMARY", "task is complete now",
                           task_id=tid, subject_type="case", subject_id=cid)
        assert gate.lc_state(tid)["lifecycle_state"] == before
