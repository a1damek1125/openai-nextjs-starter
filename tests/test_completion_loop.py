"""Completion Loop tests — the 11 assertions of docs/finalis-ai/31."""
from datetime import datetime, timedelta

from finalis.audit import AuditLog
from finalis.completion_loop import CompletionLoop, FollowUpPolicy
from finalis.models import Case, MissingItem, Promise
from finalis.state_machine import CaseState, transition

T0 = datetime(2026, 7, 7, 10, 0)  # 10:00, outside quiet hours


def make_case(**kw) -> Case:
    c = Case(tenant_id="t1", **kw)
    c.next_best_action = {"type": "noop"}
    c.next_action_due_at = T0
    return c


class TestInvariants:
    def test_active_case_without_next_action_is_flagged(self):
        loop = CompletionLoop(AuditLog())
        bad = Case(tenant_id="t1", state=CaseState.OFFER_SENT)  # no next action
        good = make_case(state=CaseState.OFFER_SENT)
        violations = loop.check_invariants([bad, good])
        assert len(violations) == 1 and bad.id in violations[0]

    def test_terminal_case_needs_no_next_action(self):
        loop = CompletionLoop(AuditLog())
        done = Case(tenant_id="t1", state=CaseState.COMPLETED)
        assert loop.check_invariants([done]) == []


class TestAntiSpam:
    def test_rate_limit_10_sends_yield_1(self):
        """Adversarial: try 10 sends in a row → exactly 1 goes out."""
        audit = AuditLog()
        loop = CompletionLoop(audit)
        case = make_case(state=CaseState.FOLLOW_UP_ACTIVE)
        sent = sum(loop.send_followup(case, T0 + timedelta(minutes=i),
                                      channel="whatsapp") for i in range(10))
        assert sent == 1
        assert len(audit.events(event_type="followup.suppressed")) == 9

    def test_max_attempts_then_exhausted(self):
        audit = AuditLog()
        loop = CompletionLoop(audit, FollowUpPolicy(max_attempts=3))
        case = make_case(state=CaseState.FOLLOW_UP_ACTIVE)
        t = T0
        sends = 0
        for _ in range(6):
            if loop.send_followup(case, t, channel="whatsapp"):
                sends += 1
            t += timedelta(hours=24)
        assert sends == 3
        assert len(audit.events(event_type="followup.exhausted")) == 1
        # No spam loop: further attempts stay suppressed even after long waits.
        assert not loop.send_followup(case, t + timedelta(days=99),
                                      channel="whatsapp")

    def test_quiet_hours_blocked(self):
        loop = CompletionLoop(AuditLog())
        case = make_case(state=CaseState.FOLLOW_UP_ACTIVE)
        night = datetime(2026, 7, 7, 23, 30)
        ok, reason = loop.can_touch(case, night)
        assert not ok and reason == "quiet_hours"

    def test_optout_blocked(self):
        loop = CompletionLoop(AuditLog())
        case = make_case(state=CaseState.FOLLOW_UP_ACTIVE)
        case.opted_out = True
        ok, reason = loop.can_touch(case, T0)
        assert not ok and reason == "opted_out"

    def test_exhausted_parks_to_recovery_later(self):
        audit = AuditLog()
        loop = CompletionLoop(audit)
        case = make_case(state=CaseState.FOLLOW_UP_ACTIVE)
        loop.park_exhausted(case, T0)
        assert case.state is CaseState.RECOVERY_LATER
        assert case.next_action_due_at == T0 + timedelta(days=30)  # wake_at


class TestStuckSweep:
    def test_stuck_high_value_case_floats_to_top(self):
        loop = CompletionLoop(AuditLog())
        hot_stuck = make_case(state=CaseState.WAITING_FOR_DOCUMENTS,
                              lead_score=85.0)
        hot_stuck.last_progress_at = T0 - timedelta(days=20)
        hot_stuck.missing_items = [MissingItem("photo", "nameplate", 0.9,
                                               blocks_quote=True)]
        fresh = make_case(state=CaseState.OFFER_SENT, lead_score=90.0)
        fresh.last_progress_at = T0

        queue = loop.stuck_sweep([hot_stuck, fresh], T0)
        assert [q["case_id"] for q in queue] == [hot_stuck.id]
        # 20/30 · 0.85 · 0.9 · 100 = 51.0 (float-tolerant)
        import pytest
        assert queue[0]["stuck_score"] == pytest.approx(51.0)

    def test_sweep_writes_score_audit_for_every_active_case(self):
        audit = AuditLog()
        loop = CompletionLoop(audit)
        cases = [make_case(state=CaseState.OFFER_SENT) for _ in range(3)]
        for c in cases:
            c.last_progress_at = T0
        loop.stuck_sweep(cases, T0)
        assert len(audit.events(event_type="scores.recomputed")) == 3


class TestPromiseTracker:
    def test_overdue_promise_breaches(self):
        audit = AuditLog()
        loop = CompletionLoop(audit)
        case = make_case(state=CaseState.WAITING_FOR_CLIENT_INFO)
        case.promises.append(Promise(
            promisor="client", what="send boiler photos",
            due_at=T0 - timedelta(hours=72), importance=0.9,
            dependency_impact=0.6))
        triggered = loop.promise_check(case, T0)
        # 0.9 · (72/72=1.0) · 0.6 = 0.54 ≥ θ_breach 0.3 → breached
        assert len(triggered) == 1
        assert case.promises[0].status == "broken"
        assert triggered[0]["breach_score"] == 0.54

    def test_slightly_overdue_low_impact_does_not_breach(self):
        loop = CompletionLoop(AuditLog())
        case = make_case(state=CaseState.WAITING_FOR_CLIENT_INFO)
        case.promises.append(Promise(
            promisor="client", what="send photos",
            due_at=T0 - timedelta(hours=36), importance=0.8,
            dependency_impact=0.6))
        # 0.8 · 0.5 · 0.6 = 0.24 < θ_breach 0.3 → stays open, no nag
        assert loop.promise_check(case, T0) == []
        assert case.promises[0].status == "open"

    def test_promise_not_yet_due_untouched(self):
        loop = CompletionLoop(AuditLog())
        case = make_case(state=CaseState.WAITING_FOR_CLIENT_INFO)
        case.promises.append(Promise(
            promisor="client", what="send photos",
            due_at=T0 + timedelta(days=1), importance=1.0,
            dependency_impact=1.0))
        assert loop.promise_check(case, T0) == []
        assert case.promises[0].status == "open"


class TestDurability:
    def test_restart_survival_scheduler_state_rebuildable(self):
        """Kill the loop object; rebuild from case rows; due follow-up fires."""
        audit = AuditLog()
        loop1 = CompletionLoop(audit)
        case = make_case(state=CaseState.FOLLOW_UP_ACTIVE)
        assert loop1.send_followup(case, T0, channel="whatsapp")
        del loop1                                    # "process crash"

        loop2 = CompletionLoop(audit)                # restart: fresh state
        # The case row itself carries next_action_due_at → schedule rebuilds.
        assert case.next_action_due_at is not None
        due = case.next_action_due_at
        assert loop2.send_followup(case, due, channel="whatsapp")
