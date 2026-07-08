"""Agent Runtime Governance tests — the 15 mandated enforcement checks."""
import pytest

from finalis.audit import AuditLog
from finalis.governance.runtime import (AgentTrace, AutonomyBudget,
                                        FeatureFlags, GovernedRuntime,
                                        evidence_coverage_score, redact,
                                        tool_call_risk_score,
                                        workflow_waste_score)


def runtime(**kw):
    return GovernedRuntime(AuditLog(), **kw)


class TestTraces:
    def test_1_every_tool_call_creates_trace_and_audit(self):
        rt = runtime()
        trace = rt.execute(tenant_id="t1", agent_name="followup-agent",
                           action="send_reminder", tool_name="messaging",
                           fn=lambda: "sent")
        assert trace.status == "COMPLETED"
        assert trace.audit_event_id
        assert rt.audit.events(event_type="AGENT_TRACE")
        assert rt.audit.verify_chain()

    def test_9_secrets_never_in_traces(self):
        rt = runtime()
        trace = rt.execute(
            tenant_id="t1", agent_name="a", action="send_reminder",
            tool_name="messaging",
            input_summary="calling api_key=sk-abc123def456ghi789 now",
            fn=lambda: "used Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9x")
        assert "sk-abc123" not in trace.input_summary
        assert "[REDACTED]" in trace.input_summary
        assert "eyJhbGci" not in trace.output_summary
        # And nothing secret in the audit payload either.
        for ev in rt.audit.events():
            assert "sk-abc123" not in str(ev.payload)

    def test_redact_patterns(self):
        assert "[REDACTED]" in redact("password: hunter2")
        assert "[REDACTED]" in redact("API_KEY=abcd1234efgh5678")


class TestPolicyGate:
    def test_2_gate_runs_before_provider_action(self):
        rt = runtime()
        executed = []
        trace = rt.execute(tenant_id="t1", agent_name="a",
                           action="send_reminder", tool_name="messaging",
                           hard_blockers=["client_opted_out"],
                           fn=lambda: executed.append(1))
        assert trace.status == "BLOCKED_BY_HARD_BLOCKER"
        assert executed == []                      # fn never ran

    def test_14_agent_cannot_bypass_permission_gate(self):
        rt = runtime()
        executed = []
        trace = rt.execute(tenant_id="t1", agent_name="a",
                           action="send_reminder", tool_name="messaging",
                           has_permission=False,
                           fn=lambda: executed.append(1))
        assert trace.status == "BLOCKED_BY_PERMISSION"
        assert executed == []

    def test_3_11_critical_action_blocked_without_evidence(self):
        rt = runtime()
        executed = []
        trace = rt.execute(tenant_id="t1", agent_name="a",
                           action="close_won", tool_name="case",
                           evidence_coverage=0.4, approval_granted=True,
                           fn=lambda: executed.append(1))
        assert trace.status == "HUMAN_REVIEW_REQUIRED"
        assert trace.policy_decision == "REQUIRE_MORE_EVIDENCE"
        assert executed == []

    def test_10_high_tool_risk_requires_approval(self):
        rt = runtime()
        trace = rt.execute(tenant_id="t1", agent_name="a",
                           action="send_reminder", tool_name="payment-api",
                           tool_risk=0.9, fn=lambda: "x")
        assert trace.status == "HUMAN_REVIEW_REQUIRED"
        assert trace.policy_decision == "REQUIRE_HUMAN_APPROVAL"
        # With approval granted, the same call executes.
        trace2 = rt.execute(tenant_id="t1", agent_name="a",
                            action="send_reminder", tool_name="payment-api",
                            tool_risk=0.9, approval_granted=True,
                            fn=lambda: "ok")
        assert trace2.status == "COMPLETED"


class TestBudgetsAndWaste:
    def test_5_budget_stops_runaway_workflow(self):
        rt = runtime(budget=AutonomyBudget(max_tool_calls=2))
        r1 = rt.execute(tenant_id="t1", agent_name="a", action="x1",
                        tool_name="t", fn=lambda: 1)
        r2 = rt.execute(tenant_id="t1", agent_name="a", action="x2",
                        tool_name="t", fn=lambda: 2)
        r3 = rt.execute(tenant_id="t1", agent_name="a", action="x3",
                        tool_name="t", fn=lambda: 3)
        assert r1.status == r2.status == "COMPLETED"
        assert r3.status == "CANCELLED"
        assert r3.failure_reason == "autonomy_budget_exceeded"

    def test_4_hard_blocker_beats_budget(self):
        rt = runtime(budget=AutonomyBudget(max_tool_calls=100))
        trace = rt.execute(tenant_id="t1", agent_name="a", action="x",
                           tool_name="t", hard_blockers=["opt_out"],
                           fn=lambda: 1)
        assert trace.status == "BLOCKED_BY_HARD_BLOCKER"
        assert rt.budget.tool_calls == 0     # blocked BEFORE spending

    def test_6_7_waste_score_stops_workflow(self):
        rt = runtime()
        high = workflow_waste_score(repeated_action=1,
                                    tool_failure_streak=1,
                                    no_new_information=1, cost_pressure=1,
                                    retry_count=3, time_without_progress=1,
                                    policy_denial_rate=1)
        assert high == 1.0
        assert rt.waste_check(score=high, case_id="c1") is False
        assert rt.audit.events(event_type="WORKFLOW_STOPPED_WASTE")
        low = workflow_waste_score(repeated_action=0,
                                   tool_failure_streak=0,
                                   no_new_information=0, cost_pressure=0,
                                   retry_count=0, time_without_progress=0,
                                   policy_denial_rate=0)
        assert rt.waste_check(score=low) is True


class TestShadowMode:
    def test_8_shadow_mode_never_executes(self):
        rt = runtime()
        executed = []
        trace = rt.execute(tenant_id="t1", agent_name="a",
                           action="send_reminder", tool_name="messaging",
                           shadow=True, fn=lambda: executed.append(1))
        assert trace.status == "SHADOW_ONLY"
        assert executed == []
        assert rt.shadow_results[0]["would_execute"] is True

    def test_critical_actions_default_to_shadow_without_approval(self):
        rt = runtime()
        executed = []
        trace = rt.execute(tenant_id="t1", agent_name="a",
                           action="send_offer", tool_name="messaging",
                           evidence_coverage=0.9,
                           fn=lambda: executed.append(1))
        assert trace.status == "SHADOW_ONLY"      # flag-driven default
        assert executed == []
        # Approved → executes for real.
        trace2 = rt.execute(tenant_id="t1", agent_name="a",
                            action="send_offer", tool_name="messaging",
                            evidence_coverage=0.9, approval_granted=True,
                            fn=lambda: "sent")
        assert trace2.status == "COMPLETED"


class TestFeatureFlags:
    def test_13_flag_disables_risky_automation(self):
        rt = runtime()
        executed = []
        trace = rt.execute(tenant_id="t1", agent_name="a",
                           action="auto_call", tool_name="telephony",
                           feature_flag="ai_auto_call_enabled",
                           fn=lambda: executed.append(1))
        assert trace.status == "BLOCKED_BY_POLICY"    # off by default
        assert executed == []
        rt2 = runtime(flags=FeatureFlags({"ai_auto_call_enabled": True}))
        trace2 = rt2.execute(tenant_id="t1", agent_name="a",
                             action="auto_call", tool_name="telephony",
                             feature_flag="ai_auto_call_enabled",
                             fn=lambda: "dialed")
        assert trace2.status == "COMPLETED"

    def test_unknown_flag_is_off(self):
        assert not FeatureFlags().enabled("nonexistent_flag")

    def test_risky_defaults_are_off(self):
        f = FeatureFlags()
        for flag in ["ai_auto_call_enabled", "ai_auto_invoice_enabled",
                     "ai_auto_payment_update_enabled",
                     "ai_auto_upsell_enabled"]:
            assert not f.enabled(flag), flag


class TestScoresAndDashboard:
    def test_scores_bounded(self):
        assert 0 <= evidence_coverage_score(
            required_facts_covered=1, source_reliability=1, recency=1,
            consistency=1, human_verified=1) <= 1
        assert tool_call_risk_score(
            resource_sensitivity=1, action_impact=1, data_exposure=1,
            provider_risk=1, autonomy_level=1, reversibility_risk=1,
            cost_risk=1) == 1.0

    def test_15_blocked_action_explainable(self):
        rt = runtime()
        rt.execute(tenant_id="t1", agent_name="a", action="send_reminder",
                   tool_name="messaging", hard_blockers=["client_opted_out"],
                   fn=lambda: 1)
        ev = rt.audit.events(event_type="AGENT_TRACE")[-1]
        assert ev.payload["status"] == "BLOCKED_BY_HARD_BLOCKER"
        assert ev.payload["reason"] == "policy_denied"
        # Business-language rendering is a UI concern; the payload carries
        # everything needed: action, tool, status, policy, reason.
        assert {"action", "tool", "status", "policy"} <= set(ev.payload)

    def test_12_failed_execution_recorded_not_hidden(self):
        rt = runtime()
        def boom():
            raise RuntimeError("provider exploded")
        trace = rt.execute(tenant_id="t1", agent_name="a", action="x",
                           tool_name="t", fn=boom)
        assert trace.status == "FAILED"
        assert "provider exploded" in trace.failure_reason
        assert rt.audit.verify_chain()
