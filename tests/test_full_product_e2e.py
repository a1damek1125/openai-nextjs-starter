"""FULL-PRODUCT E2E: every Finalis module in one flow, one audit chain.

Voice call (diarized transcript) → Conversation Intelligence → Case Graph →
Missing-Info Hunter → Completion Loop → Action & Communication Engine
(photo request + upload link, WhatsApp) → client uploads → item resolved →
quote → OWNER DASHBOARD approval → offer sent → silence → follow-up →
client accepts → WON. Every step audited on ONE hash chain.

This is the executable definition of "Finalis is an end-to-end product":
if this test passes, a case can travel from first contact to closure
through every module boundary with all gates enforced.
"""
from datetime import datetime, timedelta

from finalis.audit import AuditLog
from finalis.actions.engine import ActionCommunicationEngine
from finalis.actions.models import ActionRequest, ChannelPreference
from finalis.case_services import (CaseGraphService, CompletionLoopService,
                                   MissingInfoService,
                                   PromiseTrackerService)
from finalis.dashboard import DashboardService
from finalis.dashboard_html import render_dashboard
from finalis.models import Party
from finalis.state_machine import CaseState, transition
from finalis.voice.conversation_intelligence import (ConversationIntelligence,
                                                     DiarizedSegment)

T0 = datetime(2026, 7, 7, 9, 0)
TENANT = "hvac-1"


def seg(text, start, end, asr=0.94, diar=0.95):
    return DiarizedSegment(speaker="SPEAKER_00", text=text, start_ms=start,
                           end_ms=end, asr_confidence=asr,
                           diar_confidence=diar, language="en")


def test_full_product_lifecycle():
    audit = AuditLog()                      # ONE chain for everything

    # ── 1. VOICE: client calls asking for a heat-pump quote ────────────────
    ci = ConversationIntelligence(audit, tenant_id=TENANT)
    analysis = ci.analyze("vs-100", [
        seg("Hi, I'd like a quote for a heat pump installation.", 0, 3000),
        seg("My name is Jan Kowalski, the house is at ul. Kwiatowa 12.",
            3200, 7900),
        seg("I'll send you the photos tomorrow.", 8100, 10600),
    ])
    assert analysis.intent == "request_quote"
    assert analysis.promises[0]["what"] == "send photos"
    payload = analysis.case_update_payload

    # ── 2. CASE GRAPH: case created from the voice payload ─────────────────
    graph = CaseGraphService(audit)
    case = graph.create_case(tenant_id=TENANT, title="Heat pump install",
                             source_channel="voice")
    case.lead_score, case.value_estimate = 78, 11000
    case.last_progress_at = T0
    party = Party(tenant_id=TENANT, type="client",
                  display_name="Jan Kowalski", phone="+48600100200")
    graph.attach_entity(case, party, edge_type="PARTY")
    for ev_ref in analysis.evidence_references:
        graph.attach_entity(case, ev_ref, edge_type="EVIDENCE")

    mi = MissingInfoService()
    known = {f["key"]: f["value"] for f in payload["facts"]
             if f["status"] == "certain"}
    mi.detect(case, {"client_contact": party.phone,
                     "service_type": payload["case_type"],
                     "address": known.get("address"),
                     "urgency": "normal"}, audit=audit)
    from finalis.models import Promise
    case.promises.append(Promise(
        promisor="client", what="send photos",
        due_at=T0 + timedelta(hours=24), importance=.7,
        dependency_impact=.8))
    transition(case, CaseState.INTAKE_IN_PROGRESS, actor="ai",
               reason="voice intake", audit_log=audit)
    transition(case, CaseState.WAITING_FOR_DOCUMENTS, actor="ai",
               reason="photos promised", audit_log=audit)

    # ── 3. COMPLETION LOOP: next day, photos still missing ─────────────────
    loop = CompletionLoopService(audit)
    day1 = T0 + timedelta(days=1, hours=2)
    tick = loop.run_case(case, now=day1)
    assert tick["selected_action"] == "send_photo_request"
    assert tick["gate"] == "ALLOW"

    # ── 4. ACE: photo request with upload link, WhatsApp ────────────────────
    ace = ActionCommunicationEngine(audit)
    outcome = ace.handle(
        case, ActionRequest(tenant_id=TENANT, case_id=case.id,
                            action_type="send_photo_request",
                            reason="promise due, photos missing",
                            payload={"recipient": party.phone,
                                     "purpose": "installation_photo"}),
        prefs=ChannelPreference(tenant_id=TENANT, party_id=party.id),
        consents=[], now=day1)
    assert outcome.status == "executed"
    assert outcome.execution.channel == "whatsapp"
    assert outcome.upload_url in outcome.draft.final_text

    # ── 5. CLIENT uploads the photo → missing item resolved ─────────────────
    token = outcome.upload_url.rsplit("/", 1)[1]
    assert ace.uploads.use(token, day1 + timedelta(hours=5),
                           mime="image/jpeg", size_mb=2.8)
    assert mi.resolve(case, "installation_photo", audit=audit,
                      source="upload")
    PromiseTrackerService.fulfill(case, "send photos", audit=audit)
    mi.resolve(case, "preferred_date", audit=audit)  # confirmed via WhatsApp
    case.last_progress_at = day1 + timedelta(hours=5)
    assert mi.open_blockers(case) == []

    # ── 6. QUOTE: analysis → quote prep; offer needs approval ────────────────
    transition(case, CaseState.DOCUMENT_ANALYSIS, actor="ai",
               reason="photo received", audit_log=audit)
    transition(case, CaseState.QUOTE_PREPARATION, actor="ai",
               reason="all blockers cleared", audit_log=audit)
    audit.append(event_type="DECISION_BRIEF_CREATED", actor="ai",
                 case_id=case.id,
                 payload={"summary": "Hot lead €11k, quote ready",
                          "recommended_action": "send offer"})

    # ── 7. DASHBOARD: owner sees + approves the offer send ──────────────────
    dash = DashboardService(audit)
    dash.register_case(case, title="Heat pump install",
                       client_name="Jan Kowalski")
    ap_id = dash.register_approval(
        tenant_id=TENANT, case_id=case.id, action_type="send_offer",
        draft_message="Oferta: pompa ciepła 12kW — szczegóły w załączniku.",
        reason="offer commitment requires human sign-off",
        risk_level="high", created_at=day1 + timedelta(hours=6))
    html = render_dashboard(dash, tenant_id=TENANT,
                            now=day1 + timedelta(hours=6))
    assert "Waiting for Your Approval" in html and "send_offer" in html
    decided = dash.decide(ap_id, tenant_id=TENANT, role="owner",
                          user="owner-1", decision="approve")
    assert decided["approval_status"] == "APPROVED"

    # ── 8. OFFER SENT → silence → follow-up via loop + ACE ───────────────────
    transition(case, CaseState.OFFER_SENT, actor="human",
               reason="offer approved and sent", audit_log=audit)
    dash.offers_sent_at[case.id] = day1 + timedelta(hours=7)
    case.next_best_action = {"type": "send_follow_up"}
    case.next_action_due_at = day1 + timedelta(days=1)
    case.last_progress_at = day1 + timedelta(hours=7)

    day4 = day1 + timedelta(days=3)
    tick2 = loop.run_case(case, now=day4)
    assert tick2["selected_action"] == "send_follow_up"
    followup = ace.handle(
        case, ActionRequest(tenant_id=TENANT, case_id=case.id,
                            action_type="send_follow_up_after_offer",
                            reason="offer silent 3 days",
                            payload={"recipient": party.phone}),
        prefs=ChannelPreference(tenant_id=TENANT, party_id=party.id),
        consents=[], now=day4)
    assert followup.status == "executed"
    # Dashboard shows the offer at risk with a human recommendation.
    board = dash.offers_followup(TENANT, now=day4)
    assert board and board[0]["losing_risk"] == "medium"

    # ── 9. CLIENT accepts → WON ───────────────────────────────────────────────
    ace.record_delivery(followup.execution, status="replied",
                        provider_message_id="novu-2")
    transition(case, CaseState.WON, actor="human",
               reason="client accepted the offer", audit_log=audit)
    assert case.state is CaseState.WON

    # ── 10. THE PROOF: one intact audit chain across every module ────────────
    assert audit.verify_chain()
    # One audit log, one flow: every event on the chain belongs to this case's
    # journey (the voice analysis ran before the case id existed).
    types = {e.event_type for e in audit.events()}
    for expected in [
            "CONVERSATION_ANALYZED",        # voice
            "PROMISE_CREATED",              # promise tracker
            "CASE_CREATED", "PARTY_ATTACHED",       # case graph
            "MISSING_INFO_DETECTED", "MISSING_INFO_RESOLVED",
            "NEXT_ACTION_CREATED",          # completion loop / NBA
            "ACTION_REQUESTED", "UPLOAD_LINK_CREATED",
            "MESSAGE_DRAFT_CREATED", "MESSAGE_SENT",        # ACE
            "UPLOAD_LINK_USED", "PROMISE_FULFILLED",
            "DECISION_BRIEF_CREATED",
            "HUMAN_APPROVAL_GRANTED",       # dashboard
            "CLIENT_REPLIED",
            "case.state_changed",           # state machine
    ]:
        assert expected in types, f"missing audit event: {expected}"
    # Six lifecycle transitions audited: INTAKE, WAITING_DOCS, DOC_ANALYSIS,
    # QUOTE_PREP, OFFER_SENT, WON.
    assert len(audit.events(event_type="case.state_changed",
                            case_id=case.id)) == 6
    # The dashboard timeline shows the full story to the owner.
    timeline = graph.get_case_graph(case.id, tenant_id=TENANT)["timeline"]
    assert len(timeline) >= 20
