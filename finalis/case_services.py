"""Case Graph service layer — the operational brain's public interfaces.

Wraps the tested core (state_machine, scoring, completion_loop, autonomy,
audit) in the service contracts other modules (Voice, OCR, WebScout,
Dashboard, LGGT) connect to:

- CaseGraphService: create case, attach entities, read the graph.
- MissingInfoService: industry-aware required-info profiles (HVAC first).
- PromiseTrackerService: OPEN/DUE_SOON/OVERDUE/FULFILLED/BREACHED/CANCELLED.
- NextBestActionService: candidate actions -> utility -> selected action.
- ActionGateService: ALLOW / BLOCK / REQUIRE_HUMAN_APPROVAL / ABSTAIN_MISSING_DATA.
- CompletionLoopService: run_case — the per-case loop tick.

In-memory MVP; persistence lands behind these same signatures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from . import scoring
from .audit import AuditLog
from .autonomy import ALWAYS_HITL, MIN_LEVEL
from .completion_loop import CompletionLoop
from .models import Case, MissingItem, Promise
from .state_machine import (ACTIVE_STATES, FINAL_STATES, CaseState,
                            transition)

# --- Missing Information Hunter: industry profiles ---------------------------
HVAC_REQUIRED_INFO = [
    {"type": "client_contact", "severity": "high", "blocks_state": None,
     "recommended_question": "Jak możemy się z Panem/Panią skontaktować?",
     "recommended_channel": "phone", "auto_allowed": True},
    {"type": "address", "severity": "high",
     "blocks_state": "QUOTE_PREPARATION",
     "recommended_question": "Proszę o adres inwestycji do wyceny.",
     "recommended_channel": "sms_or_whatsapp", "auto_allowed": True},
    {"type": "service_type", "severity": "high",
     "blocks_state": "QUOTE_PREPARATION",
     "recommended_question": "Jakiej usługi dotyczy zapytanie?",
     "recommended_channel": "phone", "auto_allowed": True},
    {"type": "installation_photo", "severity": "high",
     "blocks_state": "QUOTE_PREPARATION",
     "recommended_question": "Proszę wysłać zdjęcie obecnej instalacji "
                             "i tabliczki znamionowej urządzenia.",
     "recommended_channel": "sms_or_whatsapp", "auto_allowed": True},
    {"type": "urgency", "severity": "medium", "blocks_state": None,
     "recommended_question": "Jak pilna jest sprawa?",
     "recommended_channel": "phone", "auto_allowed": True},
    {"type": "preferred_date", "severity": "medium", "blocks_state": None,
     "recommended_question": "Jaki termin by Panu/Pani odpowiadał?",
     "recommended_channel": "sms_or_whatsapp", "auto_allowed": True},
]

SEVERITY_WEIGHT = {"high": 0.9, "medium": 0.5, "low": 0.2}


class CaseGraphService:
    """Create cases and attach graph entities with typed edges + audit."""

    def __init__(self, audit: AuditLog) -> None:
        self.audit = audit
        self.cases: dict[str, Case] = {}
        self.edges: list[dict] = []          # typed graph edges
        self.attachments: dict[str, list] = {}  # case_id -> entities

    def create_case(self, *, tenant_id: str, title: str = "",
                    industry: str = "hvac", source_channel: str = "unknown",
                    autonomy_level: int = 3) -> Case:
        case = Case(tenant_id=tenant_id, autonomy_level=autonomy_level)
        case.next_best_action = {"type": "start_intake"}
        case.next_action_due_at = datetime.utcnow()
        case.last_progress_at = datetime.utcnow()
        self.cases[case.id] = case
        self.attachments[case.id] = []
        self.audit.append(event_type="CASE_CREATED", actor="system",
                          case_id=case.id,
                          payload={"tenant_id": tenant_id, "title": title,
                                   "industry": industry,
                                   "source_channel": source_channel})
        return case

    def attach_entity(self, case: Case, entity: Any, *, edge_type: str,
                      actor: str = "system") -> None:
        if getattr(entity, "tenant_id", case.tenant_id) != case.tenant_id:
            raise PermissionError("cross-tenant attachment refused")
        self.attachments[case.id].append(entity)
        self.edges.append({"from": case.id,
                           "to": getattr(entity, "id", repr(entity)),
                           "type": edge_type})
        event = {"VOICE_SESSION": "VOICE_SESSION_ATTACHED",
                 "DOCUMENT": "DOCUMENT_ATTACHED",
                 "PARTY": "PARTY_ATTACHED",
                 "MESSAGE": "MESSAGE_RECEIVED",
                 "EVIDENCE": "EVIDENCE_CREATED"}.get(edge_type,
                                                     "CASE_UPDATED")
        self.audit.append(event_type=event, actor=actor, case_id=case.id,
                          payload={"edge_type": edge_type,
                                   "entity_id": getattr(entity, "id", None)})

    def get_case_graph(self, case_id: str, *, tenant_id: str) -> dict:
        case = self.cases[case_id]
        if case.tenant_id != tenant_id:
            raise PermissionError("cross-tenant graph access refused")
        return {
            "case": case,
            "nodes": [case] + self.attachments[case_id],
            "edges": [e for e in self.edges if e["from"] == case_id],
            "missing_items": case.missing_items,
            "promises": case.promises,
            "timeline": self.audit.events(case_id=case_id),
        }


class MissingInfoService:
    """Industry-aware detection: known facts vs required profile."""

    PROFILES = {"hvac": HVAC_REQUIRED_INFO}

    def detect(self, case: Case, known_facts: dict[str, Any],
               *, industry: str = "hvac", audit: AuditLog) -> list[MissingItem]:
        profile = self.PROFILES[industry]
        created = []
        existing = {m.field_key for m in case.missing_items}
        for spec in profile:
            key = spec["type"]
            present = known_facts.get(key) not in (None, "", [], {})
            if not present and key not in existing:
                item = MissingItem(
                    field_key=key, label=spec["recommended_question"],
                    weight=SEVERITY_WEIGHT[spec["severity"]],
                    blocks_quote=(spec["blocks_state"] == "QUOTE_PREPARATION"))
                case.missing_items.append(item)
                created.append(item)
        if created:
            audit.append(event_type="MISSING_INFO_DETECTED", actor="ai",
                         case_id=case.id,
                         payload={"items": [m.field_key for m in created]})
        return created

    @staticmethod
    def resolve(case: Case, field_key: str, *, audit: AuditLog,
                source: str = "client") -> bool:
        for m in case.missing_items:
            if m.field_key == field_key and m.status != "received":
                m.status = "received"
                audit.append(event_type="MISSING_INFO_RESOLVED", actor=source,
                             case_id=case.id, payload={"item": field_key})
                case.last_progress_at = datetime.utcnow()
                return True
        return False

    @staticmethod
    def open_blockers(case: Case) -> list[MissingItem]:
        return [m for m in case.missing_items
                if m.status != "received" and m.blocks_quote]


class PromiseTrackerService:
    """Promise statuses: OPEN / DUE_SOON / OVERDUE / FULFILLED / BREACHED /
    CANCELLED, evaluated against a clock."""

    DUE_SOON_WINDOW = timedelta(hours=6)

    def evaluate(self, case: Case, now: datetime, *, audit: AuditLog,
                 theta_breach: float = 0.3) -> dict[str, list[Promise]]:
        out = {"DUE_SOON": [], "OVERDUE": [], "BREACHED": []}
        for p in case.promises:
            if p.status not in ("open",):
                continue
            if now >= p.due_at:
                delay_h = (now - p.due_at).total_seconds() / 3600.0
                score = scoring.promise_breach_score(
                    p.importance, delay_h, p.dependency_impact)
                if score >= theta_breach:
                    p.status = "broken"
                    out["BREACHED"].append(p)
                    audit.append(event_type="PROMISE_BREACHED", actor="system",
                                 case_id=case.id,
                                 payload={"what": p.what, "score": score})
                else:
                    out["OVERDUE"].append(p)
                    audit.append(event_type="PROMISE_DUE", actor="system",
                                 case_id=case.id, payload={"what": p.what})
            elif now >= p.due_at - self.DUE_SOON_WINDOW:
                out["DUE_SOON"].append(p)
        return out

    @staticmethod
    def fulfill(case: Case, what: str, *, audit: AuditLog) -> bool:
        for p in case.promises:
            if p.what == what and p.status == "open":
                p.status = "fulfilled"
                audit.append(event_type="PROMISE_FULFILLED", actor="system",
                             case_id=case.id, payload={"what": what})
                return True
        return False


@dataclass
class GateDecision:
    outcome: str          # ALLOW | BLOCK | REQUIRE_HUMAN_APPROVAL | ABSTAIN_MISSING_DATA
    reason: str
    audit_id: Optional[str] = None


class ActionGateService:
    """Rule-based gate (Phase-1; LGGT ProofGate strengthens it later)."""

    HIGH_RISK = ALWAYS_HITL | {"close_won", "close_lost",
                               "send_offer_commitment"}
    AUTO_OK = {"ask_for_missing_info", "send_photo_request",
               "send_document_request", "send_follow_up",
               "confirm_receipt", "create_quote_task", "analyze_document",
               "compare_offer", "do_nothing_wait", "mark_recovery_later",
               "request_human_review", "schedule_visit", "call_client"}

    def evaluate(self, case: Case, action_type: str, *,
                 confidence: float = 1.0, audit: AuditLog,
                 context: dict | None = None) -> GateDecision:
        if case.opted_out and action_type.startswith(("send_", "call_",
                                                      "ask_")):
            d = GateDecision("BLOCK", "client_opted_out")
        elif action_type in self.HIGH_RISK:
            d = GateDecision("REQUIRE_HUMAN_APPROVAL", "high_risk_action")
        elif confidence < 0.5:
            d = GateDecision("ABSTAIN_MISSING_DATA",
                             f"confidence={confidence:.2f}<0.5")
        elif case.effective_autonomy <= 2 and action_type.startswith(
                ("send_", "call_", "ask_")):
            d = GateDecision("REQUIRE_HUMAN_APPROVAL",
                             f"autonomy_L{case.effective_autonomy}")
        elif action_type in self.AUTO_OK:
            d = GateDecision("ALLOW", f"low_risk@L{case.effective_autonomy}")
        else:
            d = GateDecision("REQUIRE_HUMAN_APPROVAL",
                             "unknown_action_conservative_default")
        ev = audit.append(
            event_type={"ALLOW": "ACTION_CREATED",
                        "BLOCK": "ACTION_BLOCKED",
                        "REQUIRE_HUMAN_APPROVAL": "HUMAN_REVIEW_REQUESTED",
                        "ABSTAIN_MISSING_DATA": "ACTION_ABSTAINED"}[d.outcome],
            actor="ai", case_id=case.id,
            payload={"action": action_type, "outcome": d.outcome,
                     "reason": d.reason})
        d.audit_id = ev.id
        return d


@dataclass
class SelectedAction:
    action: str
    reason: str
    confidence: float
    requires_human_approval: bool
    utility: float


class NextBestActionService:
    """Deterministic candidate evaluation (05 §3). No fake ML."""

    def select(self, case: Case, *, now: datetime,
               audit: AuditLog) -> SelectedAction:
        open_missing = [m for m in case.missing_items
                        if m.status != "received"]
        value = max(case.value_estimate, 0.0) * max(case.lead_score, 1) / 100.0
        cands: list[scoring.ActionCandidate] = []

        if any(m.field_key == "installation_photo" for m in open_missing):
            cands.append(scoring.ActionCandidate(
                "send_photo_request", p_close=0.25, cost=0.1, risk=1,
                delay_penalty=0))
        if any(m.field_key == "address" for m in open_missing):
            cands.append(scoring.ActionCandidate(
                "ask_for_missing_info", p_close=0.25, cost=0.1, risk=1,
                delay_penalty=0))
        if not open_missing and case.state in (CaseState.QUALIFIED,
                                               CaseState.DOCUMENT_ANALYSIS,
                                               CaseState.INTAKE_IN_PROGRESS,
                                               CaseState.WAITING_FOR_CLIENT_INFO):
            cands.append(scoring.ActionCandidate(
                "create_quote_task", p_close=0.35, cost=1, risk=1,
                delay_penalty=0))
        if case.state in (CaseState.OFFER_SENT, CaseState.FOLLOW_UP_ACTIVE):
            cands.append(scoring.ActionCandidate(
                "send_follow_up", p_close=0.2, cost=0.1, risk=2,
                delay_penalty=0))
        if case.escalation_score >= 1.5:
            cands.append(scoring.ActionCandidate(
                "request_human_review", p_close=0.3, cost=5, risk=0,
                delay_penalty=0))
        cands.append(scoring.ActionCandidate(
            "do_nothing_wait", p_close=0.0, cost=0, risk=0,
            delay_penalty=0.02 * max(value, 1)))

        best = scoring.next_best_action(cands, value)
        sel = SelectedAction(
            action=best.name,
            reason=f"utility={scoring.nba_utility(best, value):.2f} over "
                   f"{len(cands)} candidates",
            confidence=0.8 if best.name != "do_nothing_wait" else 0.6,
            requires_human_approval=best.name in ActionGateService.HIGH_RISK,
            utility=scoring.nba_utility(best, value))
        case.next_best_action = {"type": sel.action}
        case.next_action_due_at = now + timedelta(hours=4)
        audit.append(event_type="NEXT_ACTION_CREATED", actor="ai",
                     case_id=case.id,
                     payload={"action": sel.action, "reason": sel.reason,
                              "utility": round(sel.utility, 2)})
        return sel


class CompletionLoopService:
    """Per-case loop tick: the 14-step check that no case is ever dropped."""

    def __init__(self, audit: AuditLog) -> None:
        self.audit = audit
        self.loop = CompletionLoop(audit)
        self.promises = PromiseTrackerService()
        self.nba = NextBestActionService()
        self.gate = ActionGateService()
        self._followup_sent_for: dict[str, set] = {}   # duplicate prevention

    def run_case(self, case: Case, *, now: datetime) -> dict:
        result: dict = {"case_id": case.id, "state": case.state.value,
                        "actions": [], "skipped": []}
        if case.state in FINAL_STATES:
            result["skipped"].append("final_state")
            return result

        promise_report = self.promises.evaluate(case, now, audit=self.audit)
        stuck_queue = self.loop.stuck_sweep([case], now)
        selected = self.nba.select(case, now=now, audit=self.audit)
        decision = self.gate.evaluate(case, selected.action,
                                      confidence=selected.confidence,
                                      audit=self.audit)
        result.update({"promises": {k: len(v) for k, v in
                                    promise_report.items()},
                       "stuck": bool(stuck_queue),
                       "selected_action": selected.action,
                       "gate": decision.outcome})

        if decision.outcome == "ALLOW" and selected.action in (
                "send_follow_up", "send_photo_request",
                "ask_for_missing_info"):
            # Duplicate prevention: one outstanding ask per item per cooldown.
            sent = self._followup_sent_for.setdefault(case.id, set())
            key = selected.action
            if key in sent:
                self.audit.append(event_type="FOLLOW_UP_RATE_LIMITED",
                                  actor="system", case_id=case.id,
                                  payload={"action": key,
                                           "reason": "duplicate_in_cooldown"})
                result["skipped"].append("duplicate_followup")
            elif self.loop.send_followup(case, now, channel="sms_or_whatsapp"):
                sent.add(key)
                result["actions"].append(key)
        # Invariant: an active case leaves the tick with a next action + due.
        assert case.next_best_action is not None
        assert case.next_action_due_at is not None
        return result
