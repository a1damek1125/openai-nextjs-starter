"""Regression tests for the verification-pass bug fixes."""
from datetime import datetime, timedelta

from finalis.audit import AuditLog
from finalis.actions.models import RateLimitRule
from finalis.actions.services import RateLimitSpamGuard
from finalis.dashboard import DashboardService
from finalis.models import Case
from finalis.state_machine import CaseState

T0 = datetime(2026, 7, 7, 10, 0)


class TestAuditCreatedAt:
    def test_every_event_carries_timestamp_and_chain_holds(self):
        log = AuditLog()
        e = log.append(event_type="x", actor="t", payload={})
        assert e.created_at and "T" in e.created_at   # ISO-8601
        log.append(event_type="y", actor="t")
        assert log.verify_chain()

    def test_tampering_with_timestamp_detected(self):
        log = AuditLog()
        log.append(event_type="x", actor="t")
        log._events[0].created_at = "1970-01-01T00:00:00+00:00"
        assert not log.verify_chain()

    def test_dashboard_activity_has_timestamps(self):
        svc = DashboardService(AuditLog())
        case = Case(tenant_id="t1", state=CaseState.NEW_CONTACT)
        svc.register_case(case, title="T", client_name="C")
        svc.audit.append(event_type="MESSAGE_SENT", actor="ai",
                         case_id=case.id)
        events = svc.activity("t1")
        assert events and events[0].created_at != ""


class TestRateLimiterDailyCap:
    def test_daily_limit_enforced_across_action_types(self):
        """The daily cap counts ALL sends for the case, not per action type."""
        guard = RateLimitSpamGuard(RateLimitRule(
            tenant_id="t", max_per_day=2, cooldown_minutes=1,
            max_attempts=99))
        t = T0
        # Two different action types, same day → both count.
        guard.record(case_id="c1", action_type="a", now=t)
        guard.record(case_id="c1", action_type="b",
                     now=t + timedelta(minutes=5))
        third = guard.check(case_id="c1", action_type="c",
                            now=t + timedelta(minutes=10))
        assert not third.allowed and third.reason == "daily_limit"

    def test_daily_limit_is_per_case_not_global(self):
        guard = RateLimitSpamGuard(RateLimitRule(
            tenant_id="t", max_per_day=1, cooldown_minutes=1,
            max_attempts=99))
        guard.record(case_id="c1", action_type="a", now=T0)
        other = guard.check(case_id="c2", action_type="a",
                            now=T0 + timedelta(minutes=2))
        assert other.allowed

    def test_next_day_resets(self):
        guard = RateLimitSpamGuard(RateLimitRule(
            tenant_id="t", max_per_day=1, cooldown_minutes=1,
            max_attempts=99))
        guard.record(case_id="c1", action_type="a", now=T0)
        tomorrow = guard.check(case_id="c1", action_type="b",
                               now=T0 + timedelta(days=1))
        assert tomorrow.allowed


class TestSnoozePrecedence:
    def test_expired_snooze_returns_case_to_queue(self):
        svc = DashboardService(AuditLog())
        case = Case(tenant_id="t1", state=CaseState.OFFER_SENT,
                    value_estimate=5000, lead_score=60)
        case.last_progress_at = T0
        case.next_best_action = {"type": "send_follow_up"}
        case.next_action_due_at = T0
        svc.register_case(case, title="T", client_name="C")
        svc.snooze(case.id, tenant_id="t1", role="owner",
                   until=T0 + timedelta(hours=2))
        assert case.id not in [i.case_id for i in
                               svc.action_queue("t1", now=T0)]
        # After the snooze expires the case MUST come back.
        later = T0 + timedelta(hours=3)
        assert case.id in [i.case_id for i in
                           svc.action_queue("t1", now=later)]
