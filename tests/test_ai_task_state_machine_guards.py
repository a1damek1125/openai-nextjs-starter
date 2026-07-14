"""CORE-A5 — explainable guard vector + side-effect firewall (pure + API).
Every transition yields a deterministic, explainable guard vector; hard-fail
guards block; the firewall refuses forbidden side-effect events."""
from finalis.ai_employee import lifecycle as L

from conftest import OWNER, MANAGER


def _ctx(frm="ACCEPTED", event="DRAFT_CREATED", **over):
    ctx = dict(tenant_match=True, actor_authorized=True, actor_type="human",
               actor_role="owner", from_state=frm, event=event, tenant_id="t",
               task_id="k", contract_hash_match=True, envelope_hash_match=True)
    ctx.update(over)
    return ctx


class TestGuardVectorPure:
    def test_all_required_guards_present(self):
        names = {g["guard_name"] for g in L.evaluate_guards(_ctx())["guards"]}
        for req in ["TENANT_SCOPE", "ACTOR_AUTHORIZED", "STATE_EDGE_ALLOWED",
                    "TASK_VERSION_MATCH", "TASK_CONTRACT_HASH_MATCH",
                    "TASK_ENVELOPE_HASH_MATCH", "NOT_TERMINAL", "NOT_EXPIRED",
                    "NOT_STALE", "AUTHORITY_NOT_BLOCKED", "SUBJECT_OWNERSHIP",
                    "APPROVAL_GRANT_VALID_IF_REQUIRED",
                    "CONSENT_VALID_IF_REQUIRED", "EVIDENCE_VALID_IF_REQUIRED",
                    "RUN_STATE_COMPATIBLE", "COMPLETION_READY_IF_COMPLETING",
                    "NO_FORBIDDEN_SIDE_EFFECT", "PATCH_BYPASS_BLOCKED"]:
            assert req in names

    def test_guard_vector_hash_deterministic(self):
        assert L.evaluate_guards(_ctx())["guard_vector_hash"] \
            == L.evaluate_guards(_ctx())["guard_vector_hash"]

    def test_failed_guards_listed(self):
        gv = L.evaluate_guards(_ctx(frm="CANCELLED"))
        assert "NOT_TERMINAL" in gv["failed_guards"]

    def test_each_guard_has_severity_and_remediation(self):
        for g in L.evaluate_guards(_ctx())["guards"]:
            assert g["guard_severity"] in ("INFO", "WARNING", "BLOCKER",
                                           "HARD_FAIL")
            assert "remediation_hint" in g
            assert g["guard_status"] in ("PASSED", "FAILED", "NOT_APPLICABLE",
                                         "NOT_IMPLEMENTED",
                                         "SERVER_REVIEW_REQUIRED")

    def test_hard_fail_guard_blocks(self):
        d = L.decide_transition(_ctx(actor_authorized=False))
        assert d["transition_status"] == "DENIED"
        assert "ACTOR_AUTHORIZED" in d["failed_guards"]

    def test_side_effect_firewall_blocks_forbidden_event(self):
        d = L.decide_transition(_ctx(event="TOOL_EXECUTED"))
        assert d["transition_status"] == "BLOCKED"

    def test_side_effect_attempt_flag_blocks(self):
        d = L.decide_transition(_ctx(side_effect_attempted=True))
        assert "NO_FORBIDDEN_SIDE_EFFECT" in d["failed_guards"]

    def test_not_stale_is_warning_not_blocking(self):
        d = L.decide_transition(_ctx(stale=True))
        # staleness alone (WARNING) does not block an otherwise-valid edge
        assert d["transition_status"] == "ALLOWED"

    def test_subject_unknown_is_server_review(self):
        d = L.decide_transition(_ctx(subject_required=True,
                                     subject_access_status="UNKNOWN"))
        assert d["transition_status"] == "SERVER_REVIEW_REQUIRED"

    def test_stale_version_blocks(self):
        d = L.decide_transition(_ctx(expected_version=1, version_match=False))
        assert d["transition_status"] == "STALE_VERSION"

    def test_stale_contract_hash_blocks(self):
        d = L.decide_transition(_ctx(contract_hash_match=False))
        assert d["transition_status"] == "STALE_HASH_STATE"

    def test_authority_blocked_blocks(self):
        d = L.decide_transition(_ctx(authority_blocked=True))
        assert d["transition_status"] == "BLOCKED"


class TestGuardVectorApi:
    def test_api_transition_returns_guard_vector(self, gate):
        tid = gate.make_task("case_summary")
        r = gate.dry_run(tid, "DRAFT_CREATED").json()
        assert r["guard_vector_hash"]
        assert any(g["guard_name"] == "STATE_EDGE_ALLOWED"
                   for g in r["guard_results"])

    def test_api_denied_lists_failed_guards(self, gate):
        tid = gate.make_task("case_summary")
        r = gate.dry_run(tid, "TASK_COMPLETED_NO_SIDE_EFFECTS").json()
        assert r["transition_status"] == "DENIED"
        assert "STATE_EDGE_ALLOWED" in r["failed_guards"]

    def test_api_side_effect_event_blocked(self, gate):
        tid = gate.make_task("case_summary")
        r = gate.transition(tid, "TOOL_EXECUTED").json()
        assert r["transition_status"] == "BLOCKED"
        assert r["applied"] is False
