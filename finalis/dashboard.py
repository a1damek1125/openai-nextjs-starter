"""Finalis Case Command Center — dashboard service layer.

Computes every dashboard section from the real domain objects (Case,
MissingItem, Promise, drafts, audit events) — no fake aggregates. The UI
(Next.js later, server-rendered HTML now) is a thin view over these
contracts.

Design rule: NO unexplained AI scores. Every item carries a
business-language `reason` built by `explain()` — "High priority: client is
responsive, offer value is high, and no response after 3 days", never
"LeadScore 0.81".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from .audit import AuditLog
from .models import Case
from .state_machine import ACTIVE_STATES, FINAL_STATES, CaseState

ROLE_PERMISSIONS = {
    "owner": {"view_all", "approve", "assign", "snooze"},
    "manager": {"view_all", "approve", "assign", "snooze"},
    "operator": {"view_assigned", "snooze"},
    "viewer": {"view_all"},
    "ai_worker": set(),          # AI never approves via the UI
}


class PermissionDenied(Exception):
    pass


# --- Data contract objects ----------------------------------------------------
@dataclass
class DashboardSummary:
    active_cases_count: int
    attention_required_count: int
    pending_approvals_count: int
    stuck_cases_count: int
    overdue_promises_count: int
    pipeline_value: float
    expected_close_value: float
    won_value_period: float
    lost_value_period: float


@dataclass
class DashboardCaseCard:
    case_id: str
    tenant_id: str
    title: str
    client_name: str
    state: str
    priority: str                 # today | this_week | normal
    estimated_value: float
    risk_level: str
    next_action: Optional[str]
    next_action_reason: str
    due_at: Optional[datetime]
    last_activity_at: Optional[datetime]
    human_review_required: bool
    missing_items_count: int
    overdue_promises_count: int


@dataclass
class OwnerActionItem:
    id: str
    case_id: str
    type: str
    title: str
    reason: str                   # business language, always filled
    recommended_action: str
    urgency: float                # sort key (internal), never displayed raw
    risk_level: str
    value_impact: float
    confidence: str               # high | medium | low (translated)
    due_at: Optional[datetime]
    status: str = "open"


@dataclass
class ApprovalItem:
    id: str
    case_id: str
    action_type: str
    draft_message: str
    reason: str
    risk_level: str
    approval_status: str
    created_at: datetime
    expires_at: Optional[datetime] = None


@dataclass
class ActivityEvent:
    id: str
    case_id: Optional[str]
    event_type: str
    actor_type: str
    summary: str
    created_at: str


def _fmt_value(v: float) -> str:
    return f"€{v:,.0f}"


def explain(case: Case, *, days_no_response: float = 0,
            context: str = "") -> str:
    """Translate scores into business language. Never expose raw numbers."""
    parts = []
    if case.lead_score >= 70:
        parts.append("high-priority client")
    elif case.lead_score >= 45:
        parts.append("warm client")
    if case.value_estimate > 0:
        parts.append(f"job worth ~{_fmt_value(case.value_estimate)}")
    if days_no_response >= 3:
        parts.append(f"no response for {int(days_no_response)} days")
    elif days_no_response >= 1:
        parts.append(f"waiting {int(days_no_response)} day(s)")
    open_missing = [m for m in case.missing_items if m.status != "received"]
    if open_missing:
        parts.append("missing: " + ", ".join(
            m.field_key.replace("_", " ") for m in open_missing[:3]))
    if context:
        parts.append(context)
    return ("; ".join(parts).capitalize() + ".") if parts else \
        "Needs review."


class DashboardService:
    """Assembles all Command Center sections for one tenant."""

    def __init__(self, audit: AuditLog) -> None:
        self.audit = audit
        self.cases: dict[str, Case] = {}
        self.client_names: dict[str, str] = {}
        self.titles: dict[str, str] = {}
        self.offers_sent_at: dict[str, datetime] = {}
        self.approval_drafts: list[dict] = []   # {id, case_id, tenant_id, ...}
        self.snoozed: dict[str, datetime] = {}
        self.assignments: dict[str, str] = {}

    # -- registration (fed by Case Graph / ACE in production) -------------------
    def register_case(self, case: Case, *, title: str, client_name: str,
                      offer_sent_at: Optional[datetime] = None) -> None:
        self.cases[case.id] = case
        self.titles[case.id] = title
        self.client_names[case.id] = client_name
        if offer_sent_at:
            self.offers_sent_at[case.id] = offer_sent_at

    def register_approval(self, *, tenant_id: str, case_id: str,
                          action_type: str, draft_message: str, reason: str,
                          risk_level: str, created_at: datetime,
                          expires_at: Optional[datetime] = None) -> str:
        item = {"id": f"ap-{len(self.approval_drafts) + 1}",
                "tenant_id": tenant_id, "case_id": case_id,
                "action_type": action_type, "draft_message": draft_message,
                "reason": reason, "risk_level": risk_level,
                "approval_status": "PENDING", "created_at": created_at,
                "expires_at": expires_at}
        self.approval_drafts.append(item)
        return item["id"]

    def _tenant_cases(self, tenant_id: str) -> list[Case]:
        return [c for c in self.cases.values() if c.tenant_id == tenant_id]

    @staticmethod
    def _check(role: str, perm: str) -> None:
        if perm not in ROLE_PERMISSIONS.get(role, set()):
            raise PermissionDenied(f"role {role} lacks {perm}")

    # -- 1. Executive summary ----------------------------------------------------
    def summary(self, tenant_id: str, *, now: datetime) -> DashboardSummary:
        cases = self._tenant_cases(tenant_id)
        active = [c for c in cases if c.state in ACTIVE_STATES]
        overdue = sum(1 for c in cases for p in c.promises
                      if p.status == "open" and now > p.due_at)
        stuck = [c for c in active if self._days_stalled(c, now) >= 5]
        pending = [a for a in self.approval_drafts
                   if a["tenant_id"] == tenant_id
                   and a["approval_status"] == "PENDING"]
        attention = {c.id for c in stuck} \
            | {a["case_id"] for a in pending} \
            | {c.id for c in active if c.state is
               CaseState.HUMAN_REVIEW_REQUIRED}
        pipeline = sum(c.value_estimate for c in active)
        expected = sum(c.value_estimate * min(c.lead_score, 100) / 100.0
                       for c in active)
        won = sum(c.value_estimate for c in cases
                  if c.state is CaseState.WON)
        lost = sum(c.value_estimate for c in cases
                   if c.state is CaseState.LOST)
        return DashboardSummary(
            active_cases_count=len(active),
            attention_required_count=len(attention),
            pending_approvals_count=len(pending),
            stuck_cases_count=len(stuck),
            overdue_promises_count=overdue,
            pipeline_value=pipeline, expected_close_value=round(expected, 2),
            won_value_period=won, lost_value_period=lost)

    @staticmethod
    def _days_stalled(case: Case, now: datetime) -> float:
        if case.last_progress_at is None:
            return 0.0
        return (now - case.last_progress_at).total_seconds() / 86400.0

    # -- 2. Today's action queue ---------------------------------------------------
    def action_queue(self, tenant_id: str, *, now: datetime
                     ) -> list[OwnerActionItem]:
        items: list[OwnerActionItem] = []
        for c in self._tenant_cases(tenant_id):
            if c.state not in ACTIVE_STATES or c.id in self.snoozed \
                    and self.snoozed[c.id] > now:
                continue
            days = self._days_stalled(c, now)
            due = c.next_action_due_at
            overdue_p = sum(1 for p in c.promises
                            if p.status == "open" and now > p.due_at)
            base = (c.lead_score / 100.0) * max(c.value_estimate, 1)
            urgency = base * (1 + 0.2 * days) * (1 + 0.5 * overdue_p)
            if due and due <= now:
                urgency *= 1.5
            action = (c.next_best_action or {}).get("type", "review_case")
            risk = "high" if c.state is CaseState.HUMAN_REVIEW_REQUIRED \
                or c.risk_score >= 60 else ("medium" if days >= 3 else "low")
            conf = "high" if c.lead_score >= 60 else \
                ("medium" if c.lead_score >= 40 else "low")
            items.append(OwnerActionItem(
                id=f"act-{c.id[:8]}", case_id=c.id, type=action,
                title=f"{self.titles.get(c.id, 'Case')} — "
                      f"{self.client_names.get(c.id, '?')}",
                reason=explain(c, days_no_response=days),
                recommended_action=action.replace("_", " "),
                urgency=urgency, risk_level=risk,
                value_impact=c.value_estimate, confidence=conf,
                due_at=due))
        items.sort(key=lambda i: -i.urgency)
        return items

    # -- 3. Human approval queue ------------------------------------------------------
    def approval_queue(self, tenant_id: str) -> list[ApprovalItem]:
        return [ApprovalItem(id=a["id"], case_id=a["case_id"],
                             action_type=a["action_type"],
                             draft_message=a["draft_message"],
                             reason=a["reason"], risk_level=a["risk_level"],
                             approval_status=a["approval_status"],
                             created_at=a["created_at"],
                             expires_at=a["expires_at"])
                for a in self.approval_drafts
                if a["tenant_id"] == tenant_id
                and a["approval_status"] == "PENDING"]

    def decide(self, approval_id: str, *, tenant_id: str, role: str,
               user: str, decision: str,
               edited_message: Optional[str] = None) -> dict:
        self._check(role, "approve")
        item = next((a for a in self.approval_drafts
                     if a["id"] == approval_id), None)
        if item is None or item["tenant_id"] != tenant_id:
            raise PermissionDenied("approval not found for tenant")
        item["approval_status"] = ("APPROVED" if decision == "approve"
                                   else "REJECTED")
        if edited_message:
            item["edited_message"] = edited_message
        self.audit.append(
            event_type=("HUMAN_APPROVAL_GRANTED" if decision == "approve"
                        else "HUMAN_APPROVAL_REJECTED"),
            actor=user, case_id=item["case_id"],
            payload={"approval_id": approval_id,
                     "edited": bool(edited_message), "via": "dashboard"})
        return item

    # -- 4. Stuck cases ------------------------------------------------------------------
    def stuck_cases(self, tenant_id: str, *, now: datetime,
                    min_days: float = 5.0) -> list[dict]:
        rows = []
        for c in self._tenant_cases(tenant_id):
            if c.state not in ACTIVE_STATES:
                continue
            days = self._days_stalled(c, now)
            if days < min_days:
                continue
            open_missing = [m for m in c.missing_items
                            if m.status != "received"]
            blocker = (open_missing[0].field_key if open_missing
                       else "no client response")
            rows.append({"case_id": c.id, "state": c.state.value,
                         "days_since_progress": round(days, 1),
                         "blocker": blocker,
                         "missing_items": [m.field_key for m in open_missing],
                         "overdue_promises": sum(
                             1 for p in c.promises
                             if p.status == "open" and now > p.due_at),
                         "next_action": explain(c, days_no_response=days)})
        rows.sort(key=lambda r: -r["days_since_progress"])
        return rows

    # -- 5. Missing information queue -------------------------------------------------------
    def missing_info(self, tenant_id: str) -> list[dict]:
        rows = []
        for c in self._tenant_cases(tenant_id):
            open_missing = [m for m in c.missing_items
                            if m.status != "received"]
            if c.state in ACTIVE_STATES and open_missing:
                rows.append({"case_id": c.id,
                             "client": self.client_names.get(c.id, "?"),
                             "items": [{"type": m.field_key,
                                        "blocks_quote": m.blocks_quote}
                                       for m in open_missing]})
        return rows

    # -- 6. Promise & deadline tracker ---------------------------------------------------------
    def promises(self, tenant_id: str, *, now: datetime) -> dict:
        buckets = {"due_today": [], "overdue": [], "breached": [],
                   "fulfilled": []}
        for c in self._tenant_cases(tenant_id):
            for p in c.promises:
                entry = {"case_id": c.id, "who": p.promisor, "what": p.what,
                         "due_at": p.due_at}
                if p.status == "fulfilled":
                    buckets["fulfilled"].append(entry)
                elif p.status == "broken":
                    buckets["breached"].append(entry)
                elif p.status == "open" and now > p.due_at:
                    buckets["overdue"].append(entry)
                elif p.status == "open" and p.due_at.date() == now.date():
                    buckets["due_today"].append(entry)
        return buckets

    # -- 7. Offer follow-up board ------------------------------------------------------------------
    def offers_followup(self, tenant_id: str, *, now: datetime) -> list[dict]:
        rows = []
        for c in self._tenant_cases(tenant_id):
            sent = self.offers_sent_at.get(c.id)
            if sent is None or c.state not in (CaseState.OFFER_SENT,
                                               CaseState.FOLLOW_UP_ACTIVE,
                                               CaseState.NEGOTIATION):
                continue
            days = (now - sent).total_seconds() / 86400.0
            risk = "high" if days >= 5 else ("medium" if days >= 2 else "low")
            rows.append({"case_id": c.id,
                         "client": self.client_names.get(c.id, "?"),
                         "offer_sent_at": sent,
                         "value": c.value_estimate,
                         "days_without_response": round(days, 1),
                         "losing_risk": risk,
                         "recommendation": explain(
                             c, days_no_response=days,
                             context="call before the client books "
                                     "elsewhere" if days >= 3 else
                                     "light follow-up appropriate")})
        rows.sort(key=lambda r: -r["days_without_response"])
        return rows

    # -- 8. Pipeline by state -------------------------------------------------------------------------
    def pipeline(self, tenant_id: str) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for c in self._tenant_cases(tenant_id):
            bucket = out.setdefault(c.state.value, {"count": 0, "value": 0.0})
            bucket["count"] += 1
            bucket["value"] += c.value_estimate
        return out

    # -- 9. Risk alerts ----------------------------------------------------------------------------------
    def risk_alerts(self, tenant_id: str, *, now: datetime) -> list[dict]:
        alerts = []
        for c in self._tenant_cases(tenant_id):
            if c.state is CaseState.HUMAN_REVIEW_REQUIRED:
                alerts.append({"case_id": c.id, "type": "human_review",
                               "detail": "Case frozen for human review"})
            if c.risk_score >= 60:
                alerts.append({"case_id": c.id, "type": "high_risk_case",
                               "detail": "Elevated case risk — check "
                                         "documents and history"})
            if c.value_estimate >= 15000 and c.state in ACTIVE_STATES:
                alerts.append({"case_id": c.id, "type": "high_value",
                               "detail": f"High value "
                                         f"({_fmt_value(c.value_estimate)}) — "
                                         "handle personally"})
            for p in c.promises:
                if p.status == "broken":
                    alerts.append({"case_id": c.id,
                                   "type": "breached_promise",
                                   "detail": f"{p.promisor} did not deliver: "
                                             f"{p.what}"})
        return alerts

    # -- 10. Activity timeline ------------------------------------------------------------------------------
    def activity(self, tenant_id: str, *, limit: int = 20
                 ) -> list[ActivityEvent]:
        tenant_case_ids = {c.id for c in self._tenant_cases(tenant_id)}
        rows = []
        for e in reversed(self.audit.events()):
            if e.case_id is not None and e.case_id not in tenant_case_ids:
                continue
            rows.append(ActivityEvent(
                id=e.id, case_id=e.case_id, event_type=e.event_type,
                actor_type=e.actor,
                summary=e.event_type.replace("_", " ").replace(".", " ")
                .capitalize(),
                created_at=""))
            if len(rows) >= limit:
                break
        return rows

    # -- case ops -----------------------------------------------------------------------------------------------
    def snooze(self, case_id: str, *, tenant_id: str, role: str,
               until: datetime) -> None:
        self._check(role, "snooze")
        case = self.cases.get(case_id)
        if case is None or case.tenant_id != tenant_id:
            raise PermissionDenied("case not found for tenant")
        self.snoozed[case_id] = until

    def assign(self, case_id: str, *, tenant_id: str, role: str,
               assignee: str) -> None:
        self._check(role, "assign")
        case = self.cases.get(case_id)
        if case is None or case.tenant_id != tenant_id:
            raise PermissionDenied("case not found for tenant")
        self.assignments[case_id] = assignee
        self.audit.append(event_type="CASE_ASSIGNED", actor="human",
                          case_id=case_id, payload={"assignee": assignee})
