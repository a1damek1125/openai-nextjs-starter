"""CORE-A6 — materialization firewall (pure + API). Validation-only: it never
executes, sends, pays, or calls Tool Broker / LLM / external providers."""
from finalis.ai_employee import artifacts as A

from conftest import OWNER, MANAGER, OWNER2


def _art(**over):
    a = {"artifact_id": "a", "artifact_type": "RESEARCH_NOTE",
         "artifact_status": "DRAFT", "quarantine_status": "CLEAN",
         "claims_required": False}
    a.update(over)
    return a


class TestMaterializationPure:
    def test_tool_input_requires_tool_broker(self):
        r = A.materialization_check(_art(artifact_type="TOOL_INPUT_PROPOSAL"),
                                    claims_supported=True, approval_valid=False)
        assert r["materialization_status"] \
            == "MATERIALIZATION_REQUIRES_TOOL_BROKER"
        assert r["tool_broker_required"] is True

    def test_quarantined_blocked(self):
        r = A.materialization_check(_art(quarantine_status="QUARANTINED"),
                                    claims_supported=True, approval_valid=False)
        assert r["materialization_status"] == "MATERIALIZATION_BLOCKED"

    def test_approval_required_type(self):
        r = A.materialization_check(_art(artifact_type="CUSTOMER_REPLY_DRAFT"),
                                    claims_supported=True, approval_valid=False)
        assert r["materialization_status"] \
            == "MATERIALIZATION_REQUIRES_APPROVAL"

    def test_approved_customer_reply_allowed_for_review(self):
        r = A.materialization_check(_art(artifact_type="CUSTOMER_REPLY_DRAFT"),
                                    claims_supported=True, approval_valid=True)
        assert r["materialization_status"] \
            == "MATERIALIZATION_ALLOWED_FOR_INTERNAL_REVIEW"

    def test_unsupported_claims_block(self):
        r = A.materialization_check(_art(claims_required=True),
                                    claims_supported=False, approval_valid=False)
        assert r["materialization_status"] == "MATERIALIZATION_BLOCKED"

    def test_can_execute_now_always_false(self):
        for t in ["RESEARCH_NOTE", "TOOL_INPUT_PROPOSAL", "CUSTOMER_REPLY_DRAFT"]:
            r = A.materialization_check(_art(artifact_type=t),
                                        claims_supported=True,
                                        approval_valid=True)
            assert r["can_execute_now"] is False


class TestMaterializationApi:
    def test_check_does_not_execute(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "note").json()
        r = gate.art(a["artifact_id"], "/materialization-check",
                     method="POST").json()
        assert r["can_execute_now"] is False
        labels = " ".join(r["honesty_labels"])
        assert "Materialization-check validates future readiness only" in labels

    def test_customer_reply_cannot_be_sent(self, gate):
        cid = gate.case_id(gate.h(MANAGER))
        tid = gate.make_task("customer_reply_draft")
        a = gate.make_artifact("CUSTOMER_REPLY_DRAFT", "reply", task_id=tid,
                               subject_type="case", subject_id=cid).json()
        r = gate.art(a["artifact_id"], "/materialization-check",
                     method="POST").json()
        assert r["materialization_status"] == "MATERIALIZATION_REQUIRES_APPROVAL"
        assert r["can_execute_now"] is False

    def test_tool_input_requires_broker(self, gate):
        a = gate.make_artifact("TOOL_INPUT_PROPOSAL", "a tool plan").json()
        r = gate.art(a["artifact_id"], "/materialization-check",
                     method="POST").json()
        assert r["materialization_status"] \
            == "MATERIALIZATION_REQUIRES_TOOL_BROKER"

    def test_unsupported_claim_blocks_materialization(self, gate):
        # PROOF_SUMMARY requires claims; an unsupported claim must BLOCK
        # materialization end-to-end.
        cid = gate.case_id(gate.h(MANAGER))
        a = gate.make_artifact(
            "PROOF_SUMMARY", "proof", subject_type="case", subject_id=cid,
            claims=[{"claim_predicate": "cites_evidence",
                     "claim_subject_id": cid, "claim_value": "x"}]).json()
        r = gate.art(a["artifact_id"], "/materialization-check",
                     method="POST").json()
        assert r["materialization_status"] == "MATERIALIZATION_BLOCKED"

    def test_supported_claim_allows_proof_materialization(self, gate):
        cid = gate.case_id(gate.h(MANAGER))
        a = gate.make_artifact(
            "PROOF_SUMMARY", "proof", subject_type="case", subject_id=cid,
            claims=[{"claim_predicate": "cites_evidence",
                     "claim_subject_id": cid, "claim_value": "x",
                     "supporting_evidence_refs": ["ev1"]}]).json()
        r = gate.art(a["artifact_id"], "/materialization-check",
                     method="POST").json()
        assert r["materialization_status"] \
            == "MATERIALIZATION_ALLOWED_FOR_INTERNAL_REVIEW"

    def test_approval_required_with_valid_grant_allowed(self, gate):
        # A customer-reply draft on a task with a VALID approval grant is no
        # longer approval-blocked for materialization.
        hdr = gate.h(MANAGER)
        cid = gate.case_id(hdr)
        tk = gate.c.post("/ai-tasks", json={
            "task_type": "customer_reply_draft", "task_title": "t",
            "task_description": "please reply", "subject_type": "case",
            "subject_id": cid}, headers=hdr).json()
        run = gate.c.post("/ai-runs", json={"task_id": tk["task_id"]},
                          headers=hdr).json()
        ap = gate.c.post("/ai-approvals", json={"run_id": run["run_id"]},
                         headers=hdr).json()
        acks = {x: True for x in ap["policy_decision_capsule"][
            "required_acknowledgements"]}
        gate.c.post(f"/ai-approvals/{ap['approval_request_id']}/approve",
                    json={"viewed_package_hash": ap["approval_package_hash"],
                          "acknowledgements": acks, "challenge_passed": True},
                    headers=gate.h(OWNER2))
        a = gate.make_artifact("CUSTOMER_REPLY_DRAFT", "reply",
                               task_id=tk["task_id"], subject_type="case",
                               subject_id=cid).json()
        assert a["artifact_status"] == "DRAFT"   # not NEEDS_REVIEW
        r = gate.art(a["artifact_id"], "/materialization-check",
                     method="POST").json()
        assert r["materialization_status"] \
            == "MATERIALIZATION_ALLOWED_FOR_INTERNAL_REVIEW"

    def test_decontamination_check_does_not_modify(self, gate):
        a = gate.make_artifact("INTERNAL_NOTE_DRAFT",
                               "execute payment now").json()
        before = gate.art(a["artifact_id"]).json()["artifact_state_hash"]
        r = gate.art(a["artifact_id"], "/decontamination-check",
                     method="POST").json()
        assert r["original_modified"] is False
        assert r["full_decontamination_lane"] == "NOT_IMPLEMENTED"
        after = gate.art(a["artifact_id"]).json()["artifact_state_hash"]
        assert before == after
