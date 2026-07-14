"""Action & Communication Engine — the safe execution path.

request → ActionGate → consent → rate limit → channel routing → compose →
(HumanApprovalQueue) → durable schedule (Temporal) → send (Novu/Chatwoot/
direct) → DeliveryTracker → Case Graph update → audit.

Every decision point writes an audit event; nothing sends without passing
the gate; a rejected/blocked action is never silent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from ..audit import AuditLog
from ..case_services import ActionGateService, MissingInfoService
from ..models import Case
from .adapters import ChatwootMock, NovuMock, TemporalMock
from .models import (ActionExecution, ActionRequest, ChannelPreference,
                     ConsentPreference, DeliveryEvent, MessageDraft)
from .services import (ChannelRouter, ConsentPermissionService,
                       MessageComposer, RateLimitSpamGuard,
                       UploadLinkGenerator)

HIGH_RISK_ACTION_TYPES = {"close_case_won", "close_case_lost",
                          "send_quote_status_update_with_price",
                          "send_price_negotiation", "send_contract_response"}
UPLOAD_ACTIONS = {"send_photo_request", "send_document_request",
                  "send_upload_link"}


@dataclass
class ExecutionOutcome:
    request: ActionRequest
    status: str                       # executed|scheduled|pending_approval|blocked|deferred
    reason: str
    draft: Optional[MessageDraft] = None
    execution: Optional[ActionExecution] = None
    upload_url: Optional[str] = None
    approval_id: Optional[str] = None


class ActionCommunicationEngine:
    def __init__(self, audit: AuditLog) -> None:
        self.audit = audit
        self.gate = ActionGateService()
        self.router = ChannelRouter()
        self.composer = MessageComposer()
        self.consent = ConsentPermissionService()
        self.rate = RateLimitSpamGuard()
        self.temporal = TemporalMock(audit)
        self.novu = NovuMock(audit)
        self.chatwoot = ChatwootMock(audit)
        self.uploads = UploadLinkGenerator(audit)
        self.approval_queue: list[dict] = []
        self.executions: list[ActionExecution] = []
        self.deliveries: list[DeliveryEvent] = []

    # -- entry point -----------------------------------------------------------
    def handle(self, case: Case, request: ActionRequest, *,
               prefs: ChannelPreference,
               consents: list[ConsentPreference],
               now: datetime, language: str = "pl") -> ExecutionOutcome:
        self.audit.append(event_type="ACTION_REQUESTED", actor=request.proposed_by,
                          case_id=case.id,
                          payload={"action_type": request.action_type,
                                   "reason": request.reason,
                                   "source": request.source,
                                   "risk_level": request.risk_level})

        # 1. Human handoff routes to Chatwoot regardless of message channels.
        if request.action_type == "handoff_to_human":
            return self._handoff(case, request, prefs, now, language)

        # 2. Internal actions (owner notify / internal task) skip client gates.
        if request.action_type in ("notify_owner", "create_internal_task"):
            return self._internal(case, request, now)

        # 3. ActionGate (brain safety layer).
        gate_action = ("send_out_of_rule_price"
                       if request.action_type in HIGH_RISK_ACTION_TYPES
                       else "send_follow_up")
        decision = self.gate.evaluate(case, gate_action,
                                      confidence=request.payload.get(
                                          "confidence", 1.0),
                                      audit=self.audit)
        if decision.outcome == "BLOCK":
            return ExecutionOutcome(request, "blocked", decision.reason)
        if decision.outcome == "ABSTAIN_MISSING_DATA":
            return ExecutionOutcome(request, "blocked",
                                    f"abstain:{decision.reason}")

        # 4. Channel routing (consent-aware ordering).
        route = self.router.route(request.action_type, prefs, consents)
        if route.channel is None:
            self.audit.append(event_type="ACTION_GATE_BLOCK", actor="system",
                              case_id=case.id,
                              payload={"reason": "no_permitted_channel"})
            return ExecutionOutcome(request, "blocked", "no_permitted_channel")

        # 5. Consent & business hours.
        consent = self.consent.check(prefs=prefs, consents=consents,
                                     channel=route.channel, now=now,
                                     urgent=request.payload.get("urgent",
                                                                False))
        if not consent.allowed and consent.defer_until is None:
            self.audit.append(event_type="ACTION_GATE_BLOCK", actor="system",
                              case_id=case.id,
                              payload={"reason": consent.reason})
            return ExecutionOutcome(request, "blocked", consent.reason)

        # 6. Rate limit / anti-spam.
        rate = self.rate.check(case_id=case.id,
                               action_type=request.action_type, now=now)
        if not rate.allowed:
            self.audit.append(event_type="FOLLOW_UP_RATE_LIMITED",
                              actor="system", case_id=case.id,
                              payload={"reason": rate.reason,
                                       "action_type": request.action_type})
            return ExecutionOutcome(request, "blocked",
                                    f"rate_limited:{rate.reason}")

        # 7. Upload link if the action carries one.
        upload_url = None
        variables = dict(request.payload.get("variables", {}))
        if request.action_type in UPLOAD_ACTIONS:
            _, upload_url = self.uploads.create(
                tenant_id=request.tenant_id, case_id=case.id,
                purpose=request.payload.get("purpose", "installation_photo"),
                now=now)
            variables["upload_link"] = upload_url

        # 8. Compose (stored before sending — always).
        draft = self.composer.compose(
            request.action_type, language=language, channel=route.channel,
            tenant_id=request.tenant_id, case_id=case.id,
            action_request_id=request.id, variables=variables,
            risk_level=request.risk_level)
        self.audit.append(event_type="MESSAGE_DRAFT_CREATED", actor="ai",
                          case_id=case.id,
                          payload={"draft_id": draft.id,
                                   "channel": draft.channel,
                                   "risk_level": draft.risk_level})

        # 9. Human approval for risky drafts.
        if decision.outcome == "REQUIRE_HUMAN_APPROVAL" \
                or request.risk_level == "high":
            draft.approval_status = "PENDING"
            entry = {"draft": draft, "request": request, "case": case,
                     "route": route, "requested_at": now}
            self.approval_queue.append(entry)
            self.audit.append(event_type="HUMAN_APPROVAL_REQUESTED",
                              actor="ai", case_id=case.id,
                              payload={"draft_id": draft.id})
            return ExecutionOutcome(request, "pending_approval",
                                    "awaiting_human", draft=draft,
                                    upload_url=upload_url,
                                    approval_id=draft.id)

        # 10. Deferred by business hours → durable schedule; else send now.
        if not consent.allowed and consent.defer_until is not None:
            self.temporal.schedule("FollowUpWorkflow",
                                   run_at=consent.defer_until,
                                   payload={"case_id": case.id,
                                            "draft_id": draft.id,
                                            "channel": route.channel})
            self.audit.append(event_type="ACTION_SCHEDULED", actor="system",
                              case_id=case.id,
                              payload={"run_at": str(consent.defer_until)})
            return ExecutionOutcome(request, "deferred",
                                    "outside_business_hours", draft=draft,
                                    upload_url=upload_url)

        return self._send(case, request, draft, route, prefs, now,
                          upload_url)

    # -- approval flow -----------------------------------------------------------
    def decide_approval(self, draft_id: str, *, approver: str,
                        decision: str, now: datetime,
                        edited_text: Optional[str] = None,
                        reason: str = "") -> Optional[ExecutionOutcome]:
        entry = next((e for e in self.approval_queue
                      if e["draft"].id == draft_id), None)
        if entry is None:
            return None
        draft: MessageDraft = entry["draft"]
        if decision == "approve":
            draft.approval_status = "APPROVED"
            if edited_text:
                draft.edited_text = edited_text
            self.audit.append(event_type="HUMAN_APPROVAL_GRANTED",
                              actor=approver, case_id=entry["case"].id,
                              payload={"draft_id": draft.id,
                                       "edited": bool(edited_text)})
            self.approval_queue.remove(entry)
            return self._send(entry["case"], entry["request"], draft,
                              entry["route"],
                              ChannelPreference(tenant_id=draft.tenant_id,
                                                party_id="approved"),
                              now, None)
        draft.approval_status = "REJECTED"
        self.audit.append(event_type="HUMAN_APPROVAL_REJECTED",
                          actor=approver, case_id=entry["case"].id,
                          payload={"draft_id": draft.id, "reason": reason})
        self.approval_queue.remove(entry)
        return ExecutionOutcome(entry["request"], "blocked",
                                f"rejected:{reason}", draft=draft)

    # -- delivery ------------------------------------------------------------------
    def _send(self, case, request, draft, route, prefs, now,
              upload_url) -> ExecutionOutcome:
        execution = ActionExecution(tenant_id=request.tenant_id,
                                    case_id=case.id,
                                    action_request_id=request.id,
                                    channel=route.channel,
                                    provider=self.novu.name,
                                    scheduled_at=now)
        result = self.novu.send(channel=route.channel,
                                recipient=request.payload.get("recipient",
                                                              "unknown"),
                                text=draft.final_text,
                                tenant_id=request.tenant_id)
        if not result["ok"] and route.fallback:
            execution.retry_count += 1
            execution.channel = route.fallback
            result = self.novu.send(channel=route.fallback,
                                    recipient=request.payload.get(
                                        "recipient", "unknown"),
                                    text=draft.final_text,
                                    tenant_id=request.tenant_id)
        if not result["ok"]:
            execution.status = "failed"
            self.executions.append(execution)
            self.audit.append(event_type="MESSAGE_FAILED", actor="system",
                              case_id=case.id,
                              payload={"execution_id": execution.id})
            return ExecutionOutcome(request, "blocked", "delivery_failed",
                                    draft=draft, execution=execution)

        execution.status = "sent"
        execution.executed_at = now
        self.executions.append(execution)
        self.rate.record(case_id=case.id, action_type=request.action_type,
                         now=now)
        self.audit.append(event_type="MESSAGE_SENT", actor="ai",
                          case_id=case.id,
                          payload={"execution_id": execution.id,
                                   "channel": execution.channel,
                                   "draft_id": draft.id})
        # Follow-up cadence: schedule the next check durably.
        self.temporal.schedule("FollowUpWorkflow",
                               run_at=now + timedelta(hours=24),
                               payload={"case_id": case.id,
                                        "action_type": request.action_type,
                                        "attempt_followup": True})
        return ExecutionOutcome(request, "executed", "sent", draft=draft,
                                execution=execution, upload_url=upload_url)

    def _handoff(self, case, request, prefs, now, language
                 ) -> ExecutionOutcome:
        conv = self.chatwoot.create_handoff(
            tenant_id=request.tenant_id, case_id=case.id,
            contact=request.payload.get("recipient", "unknown"),
            summary=request.payload.get("summary", "AI handoff"),
            labels=["finalis-handoff", request.reason])
        execution = ActionExecution(tenant_id=request.tenant_id,
                                    case_id=case.id,
                                    action_request_id=request.id,
                                    channel="chatwoot",
                                    provider=self.chatwoot.name,
                                    status="sent", executed_at=now,
                                    result={"conversation_id": conv["id"]})
        self.executions.append(execution)
        return ExecutionOutcome(request, "executed",
                                "handoff_conversation_created",
                                execution=execution)

    def _internal(self, case, request, now) -> ExecutionOutcome:
        result = self.novu.send(channel="inbox",
                                recipient=request.payload.get("owner",
                                                              "owner"),
                                text=request.reason,
                                tenant_id=request.tenant_id)
        execution = ActionExecution(tenant_id=request.tenant_id,
                                    case_id=case.id,
                                    action_request_id=request.id,
                                    channel="inbox", provider=self.novu.name,
                                    status="sent", executed_at=now)
        self.executions.append(execution)
        return ExecutionOutcome(request, "executed", "owner_notified",
                                execution=execution)

    # -- delivery tracking -----------------------------------------------------------
    def record_delivery(self, execution: ActionExecution, *, status: str,
                        provider_message_id: str,
                        payload: dict | None = None) -> DeliveryEvent:
        ev = DeliveryEvent(tenant_id=execution.tenant_id,
                           case_id=execution.case_id,
                           action_execution_id=execution.id,
                           provider=execution.provider,
                           provider_message_id=provider_message_id,
                           status=status, payload=payload or {})
        self.deliveries.append(ev)
        execution.status = status
        event = {"delivered": "MESSAGE_DELIVERED", "read": "MESSAGE_READ",
                 "replied": "CLIENT_REPLIED",
                 "failed": "MESSAGE_FAILED"}.get(status, "MESSAGE_DELIVERED")
        self.audit.append(event_type=event, actor="provider",
                          case_id=execution.case_id,
                          payload={"execution_id": execution.id,
                                   "status": status})
        if status == "replied":
            self.rate.client_replied(execution.case_id)
        return ev
