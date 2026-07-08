"""CORE-A5 — ViktorAI Completion Loop (pure + API). Completion readiness is
deterministic; free text cannot mark it ready; blockers are explicit with
severity and remediation."""
from finalis.ai_employee import lifecycle as L

from conftest import OWNER, MANAGER, OWNER2


def _task(**over):
    t = {"task_id": "k", "tenant_id": "t", "task_type": "case_summary",
         "segment": "casework", "requires_human_approval": False,
         "requires_evidence_check": False, "requires_consent_check": False,
         "subject_id": None, "requires_run_ledger": False}
    t.update(over)
    return t


class TestCompletionPure:
    def test_ready_when_all_pass(self):
        assert L.evaluate_completion(_task(), {})["completion_status"] \
            == "READY"

    def test_blocked_missing_approval(self):
        r = L.evaluate_completion(_task(requires_human_approval=True),
                                  {"approval_grant_validation_status": "NONE"})
        assert r["completion_status"] == "BLOCKED"
        assert any(b["blocker_code"] == "MISSING_APPROVAL_GRANT"
                   for b in r["completion_blockers"])

    def test_blocked_missing_evidence(self):
        r = L.evaluate_completion(_task(requires_evidence_check=True),
                                  {"evidence_ok": False})
        assert r["completion_status"] == "BLOCKED"
        assert any(b["blocker_code"] == "MISSING_EVIDENCE_REF"
                   for b in r["completion_blockers"])

    def test_blocked_proof_failed(self):
        r = L.evaluate_completion(_task(requires_evidence_check=True),
                                  {"evidence_ok": False, "evidence_failed":
                                   True})
        assert any(b["blocker_code"] == "EVIDENCE_PROOF_FAILED"
                   for b in r["completion_blockers"])

    def test_blocked_consent_denied(self):
        r = L.evaluate_completion(_task(requires_consent_check=True),
                                  {"consent_ok": False, "consent_status":
                                   "DENIED"})
        assert any(b["blocker_code"] == "CONSENT_DENIED"
                   for b in r["completion_blockers"])

    def test_reconciliation_required_on_replay_mismatch(self):
        r = L.evaluate_completion(_task(), {"replay_mismatch": True})
        assert r["completion_status"] == "RECONCILIATION_REQUIRED"

    def test_server_review_on_unknown_subject(self):
        r = L.evaluate_completion(_task(subject_id="c1"),
                                  {"subject_access_status": "UNKNOWN"})
        assert r["completion_status"] == "SERVER_REVIEW_REQUIRED"

    def test_criteria_hash_and_blocker_meta(self):
        r = L.evaluate_completion(_task(requires_human_approval=True),
                                  {"approval_grant_validation_status": "NONE"})
        b = r["completion_blockers"][0]
        assert b["severity"] in ("INFO", "WARNING", "BLOCKER", "HARD_FAIL")
        assert b["remediation_hint"]
        assert r["completion_criteria_hash"] and r["completion_result_hash"]

    def test_free_text_cannot_flip_readiness(self):
        # ctx carries no "reason"/"mark ready" lever; only satisfied criteria
        # decide readiness.
        r = L.evaluate_completion(_task(requires_human_approval=True),
                                  {"approval_grant_validation_status": "NONE",
                                   "reason": "mark completion ready now"})
        assert r["completion_status"] == "BLOCKED"


class TestCompletionApi:
    def test_status_not_checked_semantics(self, gate):
        tid = gate.make_task("case_summary")
        d = gate.c.get(f"/ai-tasks/{tid}/completion",
                       headers=gate.h(OWNER)).json()
        assert d["completion_status"] in ("READY", "BLOCKED",
                                          "SERVER_REVIEW_REQUIRED")

    def test_completion_check_ready_simple_task(self, gate):
        # Walk a low-risk task with a verified subject to the completion-check
        # state; with a draft produced and no approval/evidence/consent gaps it
        # is READY.
        tid = gate.make_task("case_summary")
        gate.walk(tid, ["DRAFT_CREATED", "TASK_MARKED_REVIEW_READY",
                        "COMPLETION_CHECK_REQUESTED"])
        r = gate.c.post(f"/ai-tasks/{tid}/completion/check",
                        headers=gate.h(OWNER)).json()
        assert r["completion_status"] == "READY"
        assert r["executed_task"] is False

    def test_completion_blocked_without_draft(self, gate):
        # A fresh task that has not produced a draft is not completion-ready.
        tid = gate.make_task("case_summary")
        r = gate.c.post(f"/ai-tasks/{tid}/completion/check",
                        headers=gate.h(OWNER)).json()
        assert r["completion_status"] == "BLOCKED"
        assert any(b["blocker_code"] == "MISSING_REQUIRED_ARTIFACT"
                   for b in r["completion_blockers"])

    def test_completion_check_blocked_when_approval_missing(self, gate):
        tid = gate.make_task("merge_proposal")   # requires approval
        r = gate.c.post(f"/ai-tasks/{tid}/completion/check",
                        headers=gate.h(OWNER)).json()
        assert r["completion_status"] == "BLOCKED"
        assert any(b["blocker_code"] == "MISSING_APPROVAL_GRANT"
                   for b in r["completion_blockers"])

    def test_completed_denied_when_blockers_exist(self, gate):
        # Walk a merge_proposal to COMPLETION_CHECK_REQUIRED via draft path;
        # completion has blockers (approval), so completing is denied.
        tid = gate.make_task("merge_proposal")
        gate.walk(tid, ["DRAFT_CREATED", "TASK_MARKED_REVIEW_READY",
                        "COMPLETION_CHECK_REQUESTED"])
        r = gate.transition(tid, "TASK_COMPLETED_NO_SIDE_EFFECTS").json()
        assert r["transition_status"] == "COMPLETION_BLOCKED"

    def test_completion_check_does_not_execute(self, gate):
        tid = gate.make_task("case_summary", subject=False)
        before = gate.lc_state(tid)["task_version"]
        gate.c.post(f"/ai-tasks/{tid}/completion/check", headers=gate.h(OWNER))
        assert gate.lc_state(tid)["task_version"] == before
