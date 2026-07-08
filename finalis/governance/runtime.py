"""AgentTrace + PolicyEnforcementGate + budgets + waste/evidence/risk scores
+ shadow mode + feature flags + secret safety."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


def _uuid() -> str:
    return str(uuid.uuid4())


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


TRACE_STATUSES = {"STARTED", "COMPLETED", "FAILED", "BLOCKED_BY_POLICY",
                  "BLOCKED_BY_PERMISSION", "BLOCKED_BY_HARD_BLOCKER",
                  "HUMAN_REVIEW_REQUIRED", "CANCELLED", "TIMEOUT",
                  "RETRIED", "ROLLED_BACK", "SHADOW_ONLY"}

SECRET_PATTERNS = [re.compile(p, re.IGNORECASE) for p in
                   (r"sk-[A-Za-z0-9]{16,}", r"Bearer\s+[A-Za-z0-9._\-]{16,}",
                    r"password\s*[:=]\s*\S+", r"api[_-]?key\s*[:=]\s*\S+",
                    r"secret\s*[:=]\s*\S+")]


def redact(text: str) -> str:
    for pat in SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


@dataclass
class AgentTrace:
    tenant_id: str
    agent_name: str
    action_type: str
    case_id: Optional[str] = None
    workflow_id: Optional[str] = None
    tool_name: Optional[str] = None
    provider: Optional[str] = None
    status: str = "STARTED"
    input_summary: str = ""
    output_summary: str = ""
    evidence_reference_ids: list[str] = field(default_factory=list)
    policy_decision: Optional[str] = None
    human_approval_id: Optional[str] = None
    cost_tokens_input: int = 0
    cost_tokens_output: int = 0
    latency_ms: float = 0.0
    retry_count: int = 0
    failure_reason: Optional[str] = None
    audit_event_id: Optional[str] = None
    id: str = field(default_factory=_uuid)

    def __post_init__(self) -> None:
        # Secret safety: traces never carry raw secrets.
        self.input_summary = redact(self.input_summary)
        self.output_summary = redact(self.output_summary)


# --- Feature flags (OpenFeature-compatible shape) ------------------------------
DEFAULT_FLAGS = {
    "telephony_outbound_enabled": True,     # gated by permission gate anyway
    "ai_auto_send_messages_enabled": True,
    "ai_auto_call_enabled": False,          # risky → off by default
    "ai_auto_invoice_enabled": False,
    "ai_auto_payment_update_enabled": False,
    "ai_auto_upsell_enabled": False,
    "ai_web_search_enabled": False,
    "ocr_auto_extract_enabled": True,
    "video_analysis_enabled": False,
    "human_override_enabled": True,
    "shadow_mode_enabled": True,
}


class FeatureFlags:
    def __init__(self, overrides: Optional[dict] = None) -> None:
        self.flags = {**DEFAULT_FLAGS, **(overrides or {})}

    def enabled(self, flag: str) -> bool:
        return bool(self.flags.get(flag, False))    # unknown flag = off


# --- Autonomy budget --------------------------------------------------------------
@dataclass
class AutonomyBudget:
    max_tool_calls: int = 20
    max_retries: int = 3
    max_tokens: int = 200_000
    max_outbound_messages: int = 5
    max_calls: int = 2
    tool_calls: int = 0
    retries: int = 0
    tokens: int = 0
    outbound_messages: int = 0
    calls: int = 0

    def spend(self, *, tool_calls: int = 0, retries: int = 0,
              tokens: int = 0, outbound: int = 0, calls: int = 0) -> bool:
        """Returns False (and stops the workflow) when any budget exceeds."""
        self.tool_calls += tool_calls
        self.retries += retries
        self.tokens += tokens
        self.outbound_messages += outbound
        self.calls += calls
        return (self.tool_calls <= self.max_tool_calls
                and self.retries <= self.max_retries
                and self.tokens <= self.max_tokens
                and self.outbound_messages <= self.max_outbound_messages
                and self.calls <= self.max_calls)


# --- Scores ------------------------------------------------------------------------
def workflow_waste_score(*, repeated_action: float, tool_failure_streak: float,
                         no_new_information: float, cost_pressure: float,
                         retry_count: int, time_without_progress: float,
                         policy_denial_rate: float) -> float:
    return _clamp(0.20 * _clamp(repeated_action)
                  + 0.20 * _clamp(tool_failure_streak)
                  + 0.15 * _clamp(no_new_information)
                  + 0.15 * _clamp(cost_pressure)
                  + 0.10 * _clamp(retry_count / 3.0)
                  + 0.10 * _clamp(time_without_progress)
                  + 0.10 * _clamp(policy_denial_rate))


def evidence_coverage_score(*, required_facts_covered: float,
                            source_reliability: float, recency: float,
                            consistency: float,
                            human_verified: float) -> float:
    return _clamp(0.30 * _clamp(required_facts_covered)
                  + 0.20 * _clamp(source_reliability)
                  + 0.20 * _clamp(recency) + 0.15 * _clamp(consistency)
                  + 0.15 * _clamp(human_verified))


def tool_call_risk_score(*, resource_sensitivity: float, action_impact: float,
                         data_exposure: float, provider_risk: float,
                         autonomy_level: float, reversibility_risk: float,
                         cost_risk: float) -> float:
    return _clamp(0.25 * _clamp(resource_sensitivity)
                  + 0.20 * _clamp(action_impact)
                  + 0.15 * _clamp(data_exposure)
                  + 0.15 * _clamp(provider_risk)
                  + 0.10 * _clamp(autonomy_level)
                  + 0.10 * _clamp(reversibility_risk)
                  + 0.05 * _clamp(cost_risk))


CRITICAL_ACTIONS = {"close_won", "close_lost", "mark_payment_paid",
                    "issue_invoice", "send_offer", "send_high_risk_message",
                    "create_upsell", "recovery_followup",
                    "legal_sensitive_reply"}


class GovernedRuntime:
    """Wraps every tool/provider call: trace + policy gate + budget + shadow."""

    def __init__(self, audit, *, flags: Optional[FeatureFlags] = None,
                 budget: Optional[AutonomyBudget] = None) -> None:
        self.audit = audit
        self.flags = flags or FeatureFlags()
        self.budget = budget or AutonomyBudget()
        self.traces: list[AgentTrace] = []
        self.shadow_results: list[dict] = []

    def policy_gate(self, *, action: str, hard_blockers: list[str],
                    has_permission: bool, consent_ok: bool,
                    evidence_coverage: float = 1.0,
                    tool_risk: float = 0.0,
                    approval_granted: bool = False) -> str:
        """ALLOW | DENY | REQUIRE_HUMAN_APPROVAL | REQUIRE_MORE_EVIDENCE."""
        if hard_blockers:
            return "DENY"
        if not has_permission or not consent_ok:
            return "DENY"
        if action in CRITICAL_ACTIONS and evidence_coverage < 0.6:
            return "REQUIRE_MORE_EVIDENCE"
        if tool_risk >= 0.7 and not approval_granted:
            return "REQUIRE_HUMAN_APPROVAL"
        return "ALLOW"

    def execute(self, *, tenant_id: str, agent_name: str, action: str,
                tool_name: str, fn: Callable[[], Any],
                case_id: Optional[str] = None,
                hard_blockers: Optional[list[str]] = None,
                has_permission: bool = True, consent_ok: bool = True,
                evidence_coverage: float = 1.0, tool_risk: float = 0.0,
                approval_granted: bool = False,
                feature_flag: Optional[str] = None,
                shadow: bool = False,
                input_summary: str = "",
                is_outbound: bool = False) -> AgentTrace:
        trace = AgentTrace(tenant_id=tenant_id, agent_name=agent_name,
                           action_type=action, tool_name=tool_name,
                           case_id=case_id, input_summary=input_summary)
        self.traces.append(trace)

        # Feature flag kill switch.
        if feature_flag and not self.flags.enabled(feature_flag):
            trace.status = "BLOCKED_BY_POLICY"
            trace.policy_decision = "FLAG_DISABLED"
            self._audit(trace, "flag_disabled")
            return trace
        # Policy gate — no tool call may bypass it.
        decision = self.policy_gate(
            action=action, hard_blockers=hard_blockers or [],
            has_permission=has_permission, consent_ok=consent_ok,
            evidence_coverage=evidence_coverage, tool_risk=tool_risk,
            approval_granted=approval_granted)
        trace.policy_decision = decision
        if decision == "DENY":
            trace.status = ("BLOCKED_BY_HARD_BLOCKER" if hard_blockers
                            else "BLOCKED_BY_PERMISSION")
            self._audit(trace, "policy_denied")
            return trace
        if decision in ("REQUIRE_HUMAN_APPROVAL", "REQUIRE_MORE_EVIDENCE"):
            trace.status = "HUMAN_REVIEW_REQUIRED"
            self._audit(trace, decision.lower())
            return trace
        # Autonomy budget.
        if not self.budget.spend(tool_calls=1,
                                 outbound=1 if is_outbound else 0):
            trace.status = "CANCELLED"
            trace.failure_reason = "autonomy_budget_exceeded"
            self._audit(trace, "budget_exceeded")
            return trace
        # Shadow mode: compute, trace, never execute externally.
        if shadow or (self.flags.enabled("shadow_mode_enabled")
                      and action in CRITICAL_ACTIONS
                      and not approval_granted):
            trace.status = "SHADOW_ONLY"
            self.shadow_results.append({"trace_id": trace.id,
                                        "action": action,
                                        "would_execute": True})
            self._audit(trace, "shadow_only")
            return trace
        # Real execution.
        try:
            result = fn()
            trace.status = "COMPLETED"
            trace.output_summary = redact(str(result)[:200])
        except Exception as e:
            trace.status = "FAILED"
            trace.failure_reason = str(e)[:200]
        self._audit(trace, trace.status.lower())
        return trace

    def _audit(self, trace: AgentTrace, reason: str) -> None:
        ev = self.audit.append(
            event_type="AGENT_TRACE", actor=trace.agent_name,
            case_id=trace.case_id,
            payload={"trace_id": trace.id, "action": trace.action_type,
                     "tool": trace.tool_name, "status": trace.status,
                     "policy": trace.policy_decision, "reason": reason})
        trace.audit_event_id = ev.id

    def waste_check(self, *, score: float, case_id: Optional[str] = None
                    ) -> bool:
        """score >= 0.70 stops autonomous work + creates human review."""
        if score >= 0.70:
            self.audit.append(event_type="WORKFLOW_STOPPED_WASTE",
                              actor="governance", case_id=case_id,
                              payload={"waste_score": round(score, 2),
                                       "action": "human_review_created"})
            return False
        return True
