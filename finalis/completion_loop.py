"""Completion Loop Engine — executable form of docs/finalis-ai/09.

Simulated clock (no wall time) so tests are deterministic and 'restart
survival' is provable: the scheduler state is plain data that can be dropped
and rebuilt from case rows, exactly like a durable queue would.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from . import scoring
from .audit import AuditLog
from .models import Case
from .state_machine import ACTIVE_STATES, CaseState, transition


@dataclass
class FollowUpPolicy:
    """Anti-spam hard guarantees (05 §4 / 09 §2)."""
    max_attempts: int = 3
    min_interval: timedelta = timedelta(hours=20)
    quiet_hours: tuple[int, int] = (21, 8)   # local hours: no contact 21:00-08:00
    cadence: tuple[timedelta, ...] = (
        timedelta(hours=24), timedelta(hours=48), timedelta(hours=72),
    )


@dataclass
class FollowUpState:
    attempts: int = 0
    last_touch_at: Optional[datetime] = None
    exhausted: bool = False


class CompletionLoop:
    """Owns the invariant: every active case always has a next action + due time."""

    def __init__(self, audit: AuditLog, policy: FollowUpPolicy | None = None) -> None:
        self.audit = audit
        self.policy = policy or FollowUpPolicy()
        self.followups: dict[str, FollowUpState] = {}

    # -- invariants ----------------------------------------------------------
    def check_invariants(self, cases: list[Case]) -> list[str]:
        """Returns violations (empty list == healthy). 03 §2 invariant 1."""
        violations = []
        for c in cases:
            if c.is_active() and (c.next_best_action is None
                                  or c.next_action_due_at is None):
                violations.append(f"case {c.id} in {c.state.value} has no next action")
        return violations

    # -- follow-up scheduling (anti-spam) -------------------------------------
    def can_touch(self, case: Case, now: datetime) -> tuple[bool, str]:
        if case.opted_out:
            return False, "opted_out"
        st = self.followups.setdefault(case.id, FollowUpState())
        if st.exhausted:
            return False, "exhausted"
        if st.attempts >= self.policy.max_attempts:
            return False, "max_attempts"
        q_start, q_end = self.policy.quiet_hours
        in_quiet = (now.hour >= q_start or now.hour < q_end) if q_start > q_end \
            else (q_start <= now.hour < q_end)
        if in_quiet:
            return False, "quiet_hours"
        if st.last_touch_at is not None and \
                now - st.last_touch_at < self.policy.min_interval:
            return False, "min_interval"
        return True, "ok"

    def send_followup(self, case: Case, now: datetime, *, channel: str) -> bool:
        ok, reason = self.can_touch(case, now)
        if not ok:
            self.audit.append(event_type="followup.suppressed", actor="ai",
                              case_id=case.id, payload={"reason": reason})
            return False
        st = self.followups[case.id]
        st.attempts += 1
        st.last_touch_at = now
        self.audit.append(event_type="followup.sent", actor="ai", case_id=case.id,
                          payload={"channel": channel, "attempt": st.attempts})
        # Schedule the next step or exhaust.
        if st.attempts >= self.policy.max_attempts:
            st.exhausted = True
            self.audit.append(event_type="followup.exhausted", actor="system",
                              case_id=case.id, payload={})
        else:
            step = self.policy.cadence[min(st.attempts, len(self.policy.cadence) - 1)]
            case.next_best_action = {"type": "send_standard_followup",
                                     "channel": channel}
            case.next_action_due_at = now + step
        return True

    def park_exhausted(self, case: Case, now: datetime) -> None:
        """Exhausted follow-ups → RECOVERY_LATER with a wake time (no spam loop)."""
        transition(case, CaseState.RECOVERY_LATER, actor="system",
                   reason="followup_exhausted", audit_log=self.audit)
        case.next_best_action = {"type": "wake", "at": str(now + timedelta(days=30))}
        case.next_action_due_at = now + timedelta(days=30)

    # -- nightly stuck sweep ---------------------------------------------------
    def stuck_sweep(self, cases: list[Case], now: datetime,
                    *, theta_stuck: float = 40.0) -> list[dict]:
        """Recompute scores for active cases; return the prioritized work queue."""
        queue = []
        for c in cases:
            if not c.is_active():
                continue
            days = 0.0
            if c.last_progress_at is not None:
                days = (now - c.last_progress_at).total_seconds() / 86400.0
            blocker_w = max((m.weight for m in c.missing_items
                             if m.status == "missing"), default=0.0) or \
                (1.0 if days > 0 else 0.0)
            s = scoring.stuck_score(days, c.lead_score, blocker_w)
            self.audit.append(event_type="scores.recomputed", actor="system",
                              case_id=c.id,
                              payload={"stuck_score": s, "lead_score": c.lead_score,
                                       "mis_score": c.mis_score})
            if s >= theta_stuck:
                queue.append({"case_id": c.id, "stuck_score": s,
                              "action": "followup_or_owner_alert"})
        queue.sort(key=lambda x: -x["stuck_score"])
        return queue

    # -- promise breach check --------------------------------------------------
    def promise_check(self, case: Case, now: datetime,
                      *, theta_breach: float = 0.3) -> list[dict]:
        triggered = []
        for p in case.promises:
            if p.status != "open" or now <= p.due_at:
                continue
            delay_h = (now - p.due_at).total_seconds() / 3600.0
            score = scoring.promise_breach_score(p.importance, delay_h,
                                                 p.dependency_impact)
            if score >= theta_breach:
                p.status = "broken"
                self.audit.append(event_type="promise.breached", actor="system",
                                  case_id=case.id,
                                  payload={"promise": p.what, "score": score})
                triggered.append({"promise_id": p.id, "breach_score": score})
        return triggered
