"""E2E MVP flow simulation — docs/finalis-ai/38.

Proves the exact 20-step HVAC scenario end-to-end on the executable scaffold:
contact → intake → case + graph → missing info → follow-up → document →
evidence → quote gating → offer comparison → decision brief → human approval →
offer sent → completion-loop follow-up → closure — with audit events and the
autonomy/confidence gates enforced at every step.
"""
from datetime import datetime, timedelta

from finalis import scoring
from finalis.audit import AuditLog
from finalis.autonomy import gate
from finalis.certainty_core import NullAdapter, build_facts
from finalis.completion_loop import CompletionLoop
from finalis.documents import ingest_document
from finalis.models import (
    Case, Document, EvidenceReference, ExtractedField, MissingItem, Offer,
    Promise,
)
from finalis.state_machine import CaseState, transition

T0 = datetime(2026, 7, 7, 9, 30)

# Step 1 fixture: mock inbound call transcript (web-form equivalent).
TRANSCRIPT = {
    "channel": "phone",
    "utterances": [
        {"speaker": "client", "text": "Hi, I need a quote for installing "
         "air conditioning in my house in Poznań, Kwiatowa 12."},
        {"speaker": "ai", "text": "Happy to help — how urgent is it, and "
         "when would suit you for a visit?"},
        {"speaker": "client", "text": "This month would be great. I can do "
         "Thursday afternoons. I'll send photos of the rooms later today."},
    ],
    # Step 2: what the Intake Worker extracts (mocked extraction output).
    "extracted": {
        "client_name": "Jan Nowak", "phone": "+48600100200",
        "address": "Kwiatowa 12, Poznań", "service_type": "ac_install",
        "urgency": "this_month", "preferred_date": "thursday_pm",
    },
    "promises": [{"promisor": "client", "what": "send room photos",
                  "due_hours": 8, "importance": 0.7, "dependency_impact": 0.8}],
    "missing": [
        {"key": "room_photos", "label": "photos of rooms", "weight": 0.7,
         "blocks_quote": True},
        {"key": "device_info", "label": "current device / nameplate", "weight": 0.6,
         "blocks_quote": False},
    ],
}


def test_e2e_hvac_quote_flow():
    audit = AuditLog()
    loop = CompletionLoop(audit)
    certainty = NullAdapter(audit)

    # -- Steps 1-4: contact arrives → intake → case created → graph stored --
    case = Case(tenant_id="hvac-tenant-1", autonomy_level=3)
    audit.append(event_type="contact.inbound_received", actor="system",
                 case_id=case.id, payload={"channel": TRANSCRIPT["channel"]})
    intake = TRANSCRIPT["extracted"]
    assert intake["address"] and intake["service_type"]
    for p in TRANSCRIPT["promises"]:
        case.promises.append(Promise(
            promisor=p["promisor"], what=p["what"],
            due_at=T0 + timedelta(hours=p["due_hours"]),
            importance=p["importance"],
            dependency_impact=p["dependency_impact"]))
    for m in TRANSCRIPT["missing"]:
        case.missing_items.append(MissingItem(
            field_key=m["key"], label=m["label"], weight=m["weight"],
            blocks_quote=m["blocks_quote"]))

    # -- Step 5: NEW_CONTACT → INTAKE_IN_PROGRESS → WAITING_FOR_CLIENT_INFO --
    transition(case, CaseState.INTAKE_IN_PROGRESS, actor="ai",
               reason="serviceable request", audit_log=audit)
    case.lead_score = scoring.lead_score(0.5, 0.4, 0.6, 1.0, 0.8, 0.5)
    _, mis_norm = scoring.mis(
        [1, 1], [m.weight for m in case.missing_items])
    case.mis_score = mis_norm
    transition(case, CaseState.WAITING_FOR_CLIENT_INFO, actor="ai",
               reason="photos block quote", audit_log=audit)
    case.next_best_action = {"type": "send_missing_info_request"}
    case.next_action_due_at = T0 + timedelta(hours=2)

    # -- Step 6: Missing Information Hunter detected blockers --
    assert any(m.blocks_quote for m in case.missing_items)
    assert case.mis_score == 1.0          # everything still missing

    # -- Step 7: Follow-up Worker sends the request (autonomy-gated, L3 ok) --
    g = gate(case, "send_missing_info_request")
    assert g.allowed
    assert loop.send_followup(case, T0 + timedelta(hours=2), channel="whatsapp")

    # -- Step 8-10: client sends photo/doc → OCR mock → evidence created --
    doc = Document(doc_type="nameplate_photo", ocr_quality=0.85, fields=[
        ExtractedField(field_key="device_model", field_value="Midea X12",
                       page=1, ocr_q=0.9, extraction_q=0.9, source_q=1.0,
                       consistency_q=1.0),
        ExtractedField(field_key="room_area_m2", field_value=28,
                       page=1, ocr_q=0.7, extraction_q=0.6, source_q=1.0,
                       consistency_q=0.9),   # conf 0.378 → gated
    ])
    transition(case, CaseState.WAITING_FOR_DOCUMENTS, actor="ai",
               reason="client says photos incoming", audit_log=audit)
    decisions = ingest_document(case, doc, audit,
                                critical_fields={"room_area_m2"})
    case.evidence.append(EvidenceReference(
        source_type="document_region", source_id=doc.id,
        locator={"page": 1}, snippet="Midea X12", confidence=0.81))
    for m in case.missing_items:
        m.status = "received"
    case.promises[0].status = "fulfilled"

    # -- Step 11: low confidence on a quote-critical field → human review --
    outcomes = {d.field.field_key: d.outcome for d in decisions}
    assert outcomes["device_model"] == "accepted"
    assert outcomes["room_area_m2"] == "human_review"   # 0.378 < 0.6, critical
    transition(case, CaseState.DOCUMENT_ANALYSIS, actor="ai",
               reason="docs received", audit_log=audit)
    esc = scoring.escalation_score(0.2, 0.3, 1 - 0.378, 0.0, 0.0, 0.0)
    assert not scoring.must_escalate(esc)     # 1.12 < 1.5: gated field only,
    # so the case proceeds while THAT FIELD waits for human verification.

    # -- Step 12: Offer Comparator on two mock offers --
    ours = Offer(origin="ours", price=8400, axes={
        "scope": 0.9, "warranty": 1.0, "time": 0.8, "payment": 0.7,
        "risk": 0.9, "service": 1.0})
    competitor = Offer(origin="competitor", price=7700, axes={
        "scope": 0.7, "warranty": 0.4, "time": 0.5, "payment": 0.7,
        "risk": 0.6, "service": 0.3})
    p_ours, p_comp = scoring.normalize_prices([ours.price, competitor.price])
    ours.axes["price"], competitor.axes["price"] = p_ours, p_comp
    s_ours = scoring.offer_score(ours.axes)
    s_comp = scoring.offer_score(competitor.axes)
    assert s_ours > s_comp                   # value beats cheapest here
    case.offers += [ours, competitor]

    # -- Step 13: Decision Brief (stamped LGGT-compatible) --
    facts = build_facts([f for f in doc.fields])
    cert = certainty.certify("decision_brief:" + case.id, facts,
                             policy_version="hvac-playbook-v1")
    assert cert.verdict == "heuristic" and cert.audit_id
    brief = {"value_range": "€7.7k-8.4k", "edge": "warranty+service",
             "next_step": "call after 16:00, offer premium variant",
             "certificate_id": cert.id}

    # -- Step 14-15: risky outgoing quote needs approval; approved → send --
    transition(case, CaseState.QUOTE_PREPARATION, actor="ai",
               reason="analysis done", audit_log=audit)
    g2 = gate(case, "send_rule_covered_quote")     # L3 < L4 → approval
    assert not g2.allowed and g2.approval is not None
    g2.approval.decision, g2.approval.decided_by = "approved", "owner-1"
    audit.append(event_type="approval.decided", actor="human",
                 case_id=case.id, payload={"decision": "approved"})

    # -- Step 16: OFFER_SENT --
    transition(case, CaseState.OFFER_SENT, actor="human", reason="approved",
               audit_log=audit)
    case.next_best_action = {"type": "send_standard_followup"}
    case.next_action_due_at = T0 + timedelta(days=1)
    case.last_progress_at = T0

    # -- Step 17: no response → completion loop follows up (rate-limited) --
    transition(case, CaseState.FOLLOW_UP_ACTIVE, actor="system",
               reason="no reply after 24h", audit_log=audit)
    t = T0 + timedelta(days=1, hours=1)
    assert loop.send_followup(case, t, channel="whatsapp")
    assert not loop.send_followup(case, t + timedelta(hours=1),
                                  channel="sms")    # min interval blocks spam
    # At day 6 the case is not yet stuck (12.0 < θ_stuck 40); at day 21 it is:
    # 21/30 · 0.60 lead · 1.0 blocker · 100 = 42.0 ≥ 40 → surfaces in queue.
    assert loop.stuck_sweep([case], T0 + timedelta(days=6)) == []
    queue = loop.stuck_sweep([case], T0 + timedelta(days=21))
    assert queue and queue[0]["case_id"] == case.id  # stuck case surfaces

    # -- Step 18: client accepts → WON --
    transition(case, CaseState.WON, actor="human", reason="client accepted",
               audit_log=audit)
    assert case.state is CaseState.WON

    # -- Steps 19-20: audit completeness + metrics emitted --
    assert audit.verify_chain()
    types = {e.event_type for e in audit.events()}
    for expected in ["contact.inbound_received", "case.state_changed",
                     "followup.sent", "document.analysis_completed",
                     "approval.requested", "approval.decided",
                     "scores.recomputed", "certainty.stamped"]:
        assert expected in types, f"missing audit event: {expected}"
    state_changes = audit.events(event_type="case.state_changed")
    assert len(state_changes) == 8           # every transition audited
    # Invariant: the WON case no longer needs a next action; while active it
    # always had one (spot-check: violations list is empty now).
    assert loop.check_invariants([case]) == []


def test_e2e_escalation_and_recovery_paths():
    """Variant: angry client → HUMAN_REVIEW_REQUIRED; silent → RECOVERY_LATER."""
    audit = AuditLog()
    loop = CompletionLoop(audit)

    angry = Case(tenant_id="t1", autonomy_level=4,
                 state=CaseState.NEGOTIATION)
    angry.next_best_action = {"type": "noop"}
    angry.next_action_due_at = T0
    esc = scoring.escalation_score(0.4, 0.6, 0.3, 0.9, 0.0, 0.2)  # 2.4
    assert scoring.must_escalate(esc)
    transition(angry, CaseState.HUMAN_REVIEW_REQUIRED, actor="system",
               reason=f"escalation_score={esc}", audit_log=audit,
               escalation_interrupt=True)
    assert angry.effective_autonomy == 2      # frozen: prepare-only
    assert not gate(angry, "send_reminder").allowed

    silent = Case(tenant_id="t1", state=CaseState.FOLLOW_UP_ACTIVE)
    silent.next_best_action = {"type": "send_standard_followup"}
    silent.next_action_due_at = T0
    t = T0
    for _ in range(3):
        loop.send_followup(silent, t, channel="whatsapp")
        t += timedelta(hours=25)
    loop.park_exhausted(silent, t)
    assert silent.state is CaseState.RECOVERY_LATER
    # Wake later → back to FOLLOW_UP_ACTIVE (legal transition).
    transition(silent, CaseState.FOLLOW_UP_ACTIVE, actor="system",
               reason="wake", audit_log=audit)
    assert audit.verify_chain()
