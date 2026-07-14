"""Case Command Center tests — the 13 mandated scenarios + E2E approve flow."""
from datetime import datetime, timedelta

import pytest

from finalis.audit import AuditLog
from finalis.dashboard import (DashboardService, PermissionDenied, explain)
from finalis.dashboard_html import COMPONENTS, render_dashboard
from finalis.models import Case, MissingItem, Promise
from finalis.state_machine import CaseState

T0 = datetime(2026, 7, 7, 12, 0)


def make_service():
    return DashboardService(AuditLog())


def hvac_fixture(svc: DashboardService):
    """Realistic HVAC tenant with a spread of case situations."""
    tid = "hvac-1"
    # Hot offer, 3 days silent, high value.
    hot = Case(tenant_id=tid, state=CaseState.OFFER_SENT,
               value_estimate=12000, lead_score=82)
    hot.last_progress_at = T0 - timedelta(days=3)
    hot.next_best_action = {"type": "send_follow_up"}
    hot.next_action_due_at = T0 - timedelta(hours=2)
    svc.register_case(hot, title="Heat pump install",
                      client_name="Jan Kowalski",
                      offer_sent_at=T0 - timedelta(days=3))
    # Stuck case missing photos, 8 days.
    stuck = Case(tenant_id=tid, state=CaseState.WAITING_FOR_DOCUMENTS,
                 value_estimate=6000, lead_score=55)
    stuck.last_progress_at = T0 - timedelta(days=8)
    stuck.next_best_action = {"type": "send_photo_request"}
    stuck.next_action_due_at = T0 + timedelta(hours=4)
    stuck.missing_items = [MissingItem("installation_photo", "photo", 0.9,
                                       blocks_quote=True)]
    stuck.promises = [Promise(promisor="client", what="send photos",
                              due_at=T0 - timedelta(days=6),
                              importance=.7, dependency_impact=.8)]
    svc.register_case(stuck, title="AC replacement",
                      client_name="Anna Nowak")
    # Fresh intake.
    fresh = Case(tenant_id=tid, state=CaseState.INTAKE_IN_PROGRESS,
                 value_estimate=3000, lead_score=45)
    fresh.last_progress_at = T0
    fresh.next_best_action = {"type": "ask_for_missing_info"}
    fresh.next_action_due_at = T0 + timedelta(hours=6)
    svc.register_case(fresh, title="Boiler service",
                      client_name="Piotr Wiśniewski")
    # Won + lost for period metrics.
    won = Case(tenant_id=tid, state=CaseState.WON, value_estimate=9000)
    svc.register_case(won, title="Split AC x2", client_name="Firma XYZ")
    lost = Case(tenant_id=tid, state=CaseState.LOST, value_estimate=4000)
    svc.register_case(lost, title="Radiator swap", client_name="M. Lis")
    # High-risk review case.
    risky = Case(tenant_id=tid, state=CaseState.HUMAN_REVIEW_REQUIRED,
                 value_estimate=20000, lead_score=70, risk_score=75)
    risky.last_progress_at = T0 - timedelta(days=1)
    risky.next_best_action = {"type": "request_human_review"}
    risky.next_action_due_at = T0
    svc.register_case(risky, title="Commercial HVAC contract",
                      client_name="Biuro ABC")
    # Pending approval.
    svc.register_approval(tenant_id=tid, case_id=hot.id,
                          action_type="send_price_negotiation",
                          draft_message="[SZKIC] wracam do tematu oferty...",
                          reason="high-value negotiation",
                          risk_level="high", created_at=T0)
    return tid, {"hot": hot, "stuck": stuck, "fresh": fresh, "won": won,
                 "lost": lost, "risky": risky}


class TestSummary:
    def test_1_summary_correct(self):
        svc = make_service()
        tid, cases = hvac_fixture(svc)
        s = svc.summary(tid, now=T0)
        assert s.active_cases_count == 4      # hot, stuck, fresh, risky
        assert s.pending_approvals_count == 1
        assert s.stuck_cases_count == 1       # only 8-day case >= 5d
        assert s.overdue_promises_count == 1
        assert s.pipeline_value == 12000 + 6000 + 3000 + 20000
        assert s.won_value_period == 9000
        assert s.lost_value_period == 4000
        assert s.attention_required_count >= 2

    def test_12_empty_state_clean(self):
        svc = make_service()
        s = svc.summary("empty-tenant", now=T0)
        assert s.active_cases_count == 0
        assert s.pipeline_value == 0.0
        html = render_dashboard(svc, tenant_id="empty-tenant", now=T0)
        assert "Nothing urgent" in html
        assert "No approvals pending" in html


class TestActionQueue:
    def test_2_sorted_by_urgency_value_risk_due(self):
        svc = make_service()
        tid, cases = hvac_fixture(svc)
        queue = svc.action_queue(tid, now=T0)
        # The €20k review case and €12k silent offer must outrank the fresh €3k.
        top_two = {q.case_id for q in queue[:2]}
        assert cases["risky"].id in top_two
        assert cases["hot"].id in top_two
        assert queue[-1].case_id == cases["fresh"].id
        # Business-language reasons, no raw scores anywhere (money like
        # "€3,000." is fine; bare decimals like "0.81" are not).
        import re
        for item in queue:
            assert item.reason
            assert not re.search(r"\b0\.\d+\b", item.reason)
            assert "score" not in item.reason.lower()

    def test_snoozed_case_leaves_queue(self):
        svc = make_service()
        tid, cases = hvac_fixture(svc)
        svc.snooze(cases["hot"].id, tenant_id=tid, role="owner",
                   until=T0 + timedelta(days=2))
        queue = svc.action_queue(tid, now=T0)
        assert cases["hot"].id not in [q.case_id for q in queue]


class TestApprovals:
    def test_3_pending_approvals_visible_with_options(self):
        svc = make_service()
        tid, _ = hvac_fixture(svc)
        queue = svc.approval_queue(tid)
        assert len(queue) == 1
        assert queue[0].approval_status == "PENDING"
        html = render_dashboard(svc, tenant_id=tid, now=T0)
        assert "data-approve" in html and "data-reject" in html \
            and "data-edit" in html

    def test_11_cannot_approve_other_tenant(self):
        svc = make_service()
        tid, _ = hvac_fixture(svc)
        ap_id = svc.approval_drafts[0]["id"]
        with pytest.raises(PermissionDenied):
            svc.decide(ap_id, tenant_id="other-tenant", role="owner",
                       user="intruder", decision="approve")

    def test_ai_worker_cannot_approve(self):
        svc = make_service()
        tid, _ = hvac_fixture(svc)
        ap_id = svc.approval_drafts[0]["id"]
        with pytest.raises(PermissionDenied):
            svc.decide(ap_id, tenant_id=tid, role="ai_worker",
                       user="ai", decision="approve")

    def test_viewer_cannot_approve(self):
        svc = make_service()
        tid, _ = hvac_fixture(svc)
        with pytest.raises(PermissionDenied):
            svc.decide(svc.approval_drafts[0]["id"], tenant_id=tid,
                       role="viewer", user="v", decision="approve")


class TestQueues:
    def test_4_stuck_cases_with_blocker(self):
        svc = make_service()
        tid, cases = hvac_fixture(svc)
        rows = svc.stuck_cases(tid, now=T0)
        assert len(rows) == 1
        row = rows[0]
        assert row["case_id"] == cases["stuck"].id
        assert row["blocker"] == "installation_photo"
        assert row["days_since_progress"] == 8.0
        assert row["overdue_promises"] == 1

    def test_5_missing_info_queue(self):
        svc = make_service()
        tid, cases = hvac_fixture(svc)
        rows = svc.missing_info(tid)
        assert len(rows) == 1
        assert rows[0]["items"][0] == {"type": "installation_photo",
                                       "blocks_quote": True}

    def test_6_overdue_promises_in_tracker(self):
        svc = make_service()
        tid, _ = hvac_fixture(svc)
        buckets = svc.promises(tid, now=T0)
        assert len(buckets["overdue"]) == 1
        assert buckets["overdue"][0]["what"] == "send photos"

    def test_7_offer_followup_board(self):
        svc = make_service()
        tid, cases = hvac_fixture(svc)
        rows = svc.offers_followup(tid, now=T0)
        assert len(rows) == 1
        row = rows[0]
        assert row["days_without_response"] == 3.0
        assert row["losing_risk"] == "medium"
        assert "call before the client books elsewhere" in row["recommendation"]

    def test_8_pipeline_grouped_by_state(self):
        svc = make_service()
        tid, _ = hvac_fixture(svc)
        p = svc.pipeline(tid)
        assert p["OFFER_SENT"] == {"count": 1, "value": 12000}
        assert p["WON"] == {"count": 1, "value": 9000}
        assert p["HUMAN_REVIEW_REQUIRED"]["count"] == 1

    def test_9_risk_alerts(self):
        svc = make_service()
        tid, cases = hvac_fixture(svc)
        alerts = svc.risk_alerts(tid, now=T0)
        types = {a["type"] for a in alerts}
        assert {"human_review", "high_risk_case", "high_value",
                "breached_promise"} <= types \
            or {"human_review", "high_risk_case",
                "high_value"} <= types

    def test_10_activity_timeline(self):
        svc = make_service()
        tid, cases = hvac_fixture(svc)
        svc.audit.append(event_type="MESSAGE_SENT", actor="ai",
                         case_id=cases["hot"].id, payload={})
        svc.audit.append(event_type="CLIENT_REPLIED", actor="provider",
                         case_id=cases["hot"].id, payload={})
        events = svc.activity(tid)
        assert [e.event_type for e in events[:2]] == ["CLIENT_REPLIED",
                                                      "MESSAGE_SENT"]
        # Cross-tenant events excluded.
        other = Case(tenant_id="other", state=CaseState.NEW_CONTACT)
        svc.audit.append(event_type="CASE_CREATED", actor="system",
                         case_id=other.id, payload={})
        assert all(e.case_id != other.id for e in svc.activity(tid))


class TestRenderAndE2E:
    def test_13_render_contains_all_components(self):
        svc = make_service()
        tid, _ = hvac_fixture(svc)
        html = render_dashboard(svc, tenant_id=tid, now=T0)
        for comp in COMPONENTS:
            assert f"component:{comp}" in html, comp
        assert "Jan Kowalski" in html
        assert "€12,000" in html or "12,000" in html
        assert "What should I do today" in html

    def test_e2e_owner_approves_from_dashboard(self):
        """E2E: open dashboard → see approval → approve → status changes →
        audit event written."""
        svc = make_service()
        tid, cases = hvac_fixture(svc)
        html_before = render_dashboard(svc, tenant_id=tid, now=T0)
        assert "data-approve" in html_before
        ap = svc.approval_queue(tid)[0]
        decided = svc.decide(ap.id, tenant_id=tid, role="owner",
                             user="owner-1", decision="approve",
                             edited_message="Dzień dobry, wracam do oferty…")
        assert decided["approval_status"] == "APPROVED"
        assert decided["edited_message"].startswith("Dzień dobry")
        assert svc.approval_queue(tid) == []          # left the queue
        events = svc.audit.events(event_type="HUMAN_APPROVAL_GRANTED")
        assert events and events[0].payload["via"] == "dashboard"
        assert events[0].payload["edited"] is True
        assert svc.audit.verify_chain()
        html_after = render_dashboard(svc, tenant_id=tid, now=T0)
        assert "No approvals pending" in html_after

    def test_explain_translates_scores_to_business_language(self):
        case = Case(tenant_id="t", value_estimate=8000, lead_score=82)
        case.missing_items = [MissingItem("installation_photo", "p", .9,
                                          blocks_quote=True)]
        text = explain(case, days_no_response=3)
        assert "high-priority client" in text.lower()
        assert "€8,000" in text
        assert "3 days" in text
        assert "installation photo" in text
        assert "0.8" not in text and "score" not in text.lower()

    def test_tenant_isolation_on_case_ops(self):
        svc = make_service()
        tid, cases = hvac_fixture(svc)
        with pytest.raises(PermissionDenied):
            svc.snooze(cases["hot"].id, tenant_id="other", role="owner",
                       until=T0 + timedelta(days=1))
        with pytest.raises(PermissionDenied):
            svc.assign(cases["hot"].id, tenant_id="other", role="manager",
                       assignee="tech-1")
        svc.assign(cases["hot"].id, tenant_id=tid, role="manager",
                   assignee="tech-1")
        assert svc.assignments[cases["hot"].id] == "tech-1"
        assert svc.audit.events(event_type="CASE_ASSIGNED")
