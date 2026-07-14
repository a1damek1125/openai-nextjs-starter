"""Autonomy levels & action gating — executable form of docs/finalis-ai/13.

L1 Observe · L2 Prepare · L3 Communicate · L4 Execute Low Risk ·
L5 Conditional Autopilot. `min_level_required` transcribes 13 §6 / 12 §4:
informational sends and inbound answering = L3; bookings and rule-covered
standard quotes = L4; out-of-rule pricing / discounts / legal = human approval
regardless of level.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import Case, HumanApproval

MIN_LEVEL: dict[str, int] = {
    "summarize": 1,
    "prepare_draft": 2,
    "send_reminder": 3,
    "send_missing_info_request": 3,
    "send_confirmation": 3,
    "answer_inbound": 3,          # inbound-answer action class (03 §3.1 note)
    "ai_voice_call_outbound": 3,
    "book_appointment": 4,
    "send_rule_covered_quote": 4,
    "send_standard_followup": 4,
    "full_workflow": 5,
}

# Actions that ALWAYS require human approval regardless of level (13 §1/§6).
ALWAYS_HITL = {
    "send_out_of_rule_price",
    "grant_discount_beyond_bound",
    "send_legal_content",
    "sign_contract",
    "take_payment",
}


@dataclass
class GateResult:
    allowed: bool
    approval: Optional[HumanApproval] = None
    reason: str = ""


def gate(case: Case, action_type: str, *, context: dict | None = None) -> GateResult:
    """Decide: execute autonomously, or emit a HumanApproval (never silently drop).

    Hard blocks (opt-out) refuse outright — no approval minted (22 §1.4 rule).
    """
    if case.opted_out and action_type.startswith(("send_", "ai_voice_call")):
        return GateResult(False, reason="hard_block:client_opted_out")

    if action_type in ALWAYS_HITL:
        approval = HumanApproval(action_type=action_type,
                                 context=context or {},
                                 recommended_option="review")
        case.approvals.append(approval)
        return GateResult(False, approval=approval,
                          reason="always_requires_human_approval")

    required = MIN_LEVEL.get(action_type)
    if required is None:
        raise ValueError(f"unknown action type: {action_type}")

    if case.effective_autonomy >= required:
        return GateResult(True, reason=f"L{case.effective_autonomy}>=L{required}")

    approval = HumanApproval(action_type=action_type, context=context or {},
                             recommended_option="approve")
    case.approvals.append(approval)
    return GateResult(False, approval=approval,
                      reason=f"below_level:L{case.effective_autonomy}<L{required}")
