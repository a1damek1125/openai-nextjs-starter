"""Case Graph service-layer tests + the 23-step E2E HVAC lifecycle."""
from datetime import datetime, timedelta

import pytest

from finalis.audit import AuditLog
from finalis.case_services import (ActionGateService, CaseGraphService,
                                   CompletionLoopService, MissingInfoService,
                                   NextBestActionService,
                                   PromiseTrackerService)
from finalis.models import Case, EvidenceReference, Party, Promise
from finalis.state_machine import CaseState, IllegalTransition, transition

T0 = datetime(2026, 7, 7, 10, 0)


@pytest.fixture()
def audit():
    return AuditLog()


@pytest.fixture()
def graph(audit):
    return CaseGraphService(audit)


class TestCaseGraphService:
    def test_create_case_writes_audit(self, graph, audit):
        case = graph.create_case(tenant_id="t1", title="Heat pump quote",
                                 source_channel="voice")
        assert case.id in graph.cases
        assert len(audit.events(event_type="CASE_CREATED")) == 1
        # Freshly created active case has a next action + due (invariant).
        assert case.next_best_action and case.next_action_due_at

    def test_attach_entities_and_read_graph(self, graph, audit):
        case = graph.create_case(tenant_id="t1")
        party = Party(tenant_id="t1", type="client",
                      display_name="Jan Kowalski")
        graph.attach_entity(case, party, edge_type="PARTY")
        ev = EvidenceReference(source_type="call_segment", source_id="seg1",
                               locator={"ms": [1000, 4000]},
                               snippet="I need a quote", confidence=0.9)
        graph.attach_entity(case, ev, edge_type="EVIDENCE")
        g = graph.get_case_graph(case.id, tenant_id="t1")
        assert party in g["nodes"] and ev in g["nodes"]
        assert {e["type"] for e in g["edges"]} == {"PARTY", "EVIDENCE"}
        assert len(audit.events(event_type="PARTY_ATTACHED")) == 1
        assert len(audit.events(event_type="EVIDENCE_CREATED")) == 1

    def test_tenant_isolation_on_graph_read(self, graph):
        case = graph.create_case(tenant_id="t1")
        with pytest.raises(PermissionError):
            graph.get_case_graph(case.id, tenant_id="t2")

    def test_tenant_isolation_on_attach(self, graph):
        case = graph.create_case(tenant_id="t1")
        foreign = Party(tenant_id="t2", type="client", display_name="X")
        with pytest.raises(PermissionError):
            graph.attach_entity(case, foreign, edge_type="PARTY")


class TestMissingInfoService:
    def test_detect_from_hvac_profile(self, graph, audit):
        case = graph.create_case(tenant_id="t1")
        svc = MissingInfoService()
        created = svc.detect(case, {"client_contact": "+48600100200",
                                    "service_type": "heat_pump_quote"},
                             audit=audit)
        keys = {m.field_key for m in created}
        assert keys == {"address", "installation_photo", "urgency",
                        "preferred_date"}
        assert len(audit.events(event_type="MISSING_INFO_DETECTED")) == 1

    def test_blockers_block_and_resolution_unblocks(self, graph, audit):
        case = graph.create_case(tenant_id="t1")
        svc = MissingInfoService()
        svc.detect(case, {}, audit=audit)
        blockers = {m.field_key for m in svc.open_blockers(case)}
        assert {"address", "installation_photo"} <= blockers
        assert svc.resolve(case, "address", audit=audit)
        assert svc.resolve(case, "installation_photo", audit=audit)
        assert svc.resolve(case, "service_type", audit=audit)
        remaining = {m.field_key for m in svc.open_blockers(case)}
        assert "address" not in remaining
        assert len(audit.events(event_type="MISSING_INFO_RESOLVED")) == 3

    def test_no_duplicate_detection(self, graph, audit):
        case = graph.create_case(tenant_id="t1")
        svc = MissingInfoService()
        first = svc.detect(case, {}, audit=audit)
        second = svc.detect(case, {}, audit=audit)
        assert first and second == []


class TestPromiseTracker:
    def test_statuses(self, audit):
        case = Case(tenant_id="t1")
        tracker = PromiseTrackerService()
        case.promises = [
            Promise(promisor="client", what="send photos",
                    due_at=T0 + timedelta(hours=3), importance=.7,
                    dependency_impact=.8),                       # DUE_SOON
            Promise(promisor="client", what="send address",
                    due_at=T0 - timedelta(hours=1), importance=.3,
                    dependency_impact=.3),                       # OVERDUE (low)
            Promise(promisor="technician", what="prepare quote",
                    due_at=T0 - timedelta(hours=72), importance=.9,
                    dependency_impact=.9),                       # BREACHED
        ]
        report = tracker.evaluate(case, T0, audit=audit)
        assert [p.what for p in report["DUE_SOON"]] == ["send photos"]
        assert [p.what for p in report["OVERDUE"]] == ["send address"]
        assert [p.what for p in report["BREACHED"]] == ["prepare quote"]
        assert case.promises[2].status == "broken"
        assert len(audit.events(event_type="PROMISE_BREACHED")) == 1
        assert len(audit.events(event_type="PROMISE_DUE")) == 1

    def test_fulfill(self, audit):
        case = Case(tenant_id="t1")
        case.promises = [Promise(promisor="client", what="send photos",
                                 due_at=T0 + timedelta(days=1),
                                 importance=.7, dependency_impact=.8)]
        assert PromiseTrackerService.fulfill(case, "send photos", audit=audit)
        assert case.promises[0].status == "fulfilled"


class TestActionGate:
    def make_case(self, level=3):
        return Case(tenant_id="t1", autonomy_level=level)

    def test_allow_low_risk(self, audit):
        d = ActionGateService().evaluate(self.make_case(),
                                         "send_photo_request", audit=audit)
        assert d.outcome == "ALLOW" and d.audit_id

    def test_require_human_for_high_risk(self, audit):
        for action in ["close_won", "sign_contract", "take_payment"]:
            d = ActionGateService().evaluate(self.make_case(5), action,
                                             audit=audit)
            assert d.outcome == "REQUIRE_HUMAN_APPROVAL", action
        assert len(audit.events(event_type="HUMAN_REVIEW_REQUESTED")) == 3

    def test_block_on_optout(self, audit):
        case = self.make_case(5)
        case.opted_out = True
        d = ActionGateService().evaluate(case, "send_follow_up", audit=audit)
        assert d.outcome == "BLOCK"
        assert len(audit.events(event_type="ACTION_BLOCKED")) == 1

    def test_abstain_on_low_confidence(self, audit):
        d = ActionGateService().evaluate(self.make_case(),
                                         "send_follow_up",
                                         confidence=0.3, audit=audit)
        assert d.outcome == "ABSTAIN_MISSING_DATA"

    def test_frozen_autonomy_requires_human(self, audit):
        case = self.make_case(4)
        case.autonomy_frozen_at = 2      # in HUMAN_REVIEW_REQUIRED
        d = ActionGateService().evaluate(case, "send_follow_up", audit=audit)
        assert d.outcome == "REQUIRE_HUMAN_APPROVAL"

    def test_unknown_action_conservative(self, audit):
        d = ActionGateService().evaluate(self.make_case(5),
                                         "novel_dangerous_thing", audit=audit)
        assert d.outcome == "REQUIRE_HUMAN_APPROVAL"


class TestCompletionLoopService:
    def test_run_case_selects_action_and_respects_gate(self, graph, audit):
        case = graph.create_case(tenant_id="t1")
        case.state = CaseState.WAITING_FOR_CLIENT_INFO
        case.lead_score, case.value_estimate = 70, 9000
        MissingInfoService().detect(case, {}, audit=audit)
        svc = CompletionLoopService(audit)
        result = svc.run_case(case, now=T0)
        assert result["selected_action"] in ("send_photo_request",
                                             "ask_for_missing_info")
        assert result["gate"] == "ALLOW"
        assert result["actions"], "allowed follow-up should be sent"

    def test_duplicate_followup_prevented(self, graph, audit):
        case = graph.create_case(tenant_id="t1")
        case.state = CaseState.WAITING_FOR_CLIENT_INFO
        case.lead_score, case.value_estimate = 70, 9000
        MissingInfoService().detect(case, {}, audit=audit)
        svc = CompletionLoopService(audit)
        first = svc.run_case(case, now=T0)
        second = svc.run_case(case, now=T0 + timedelta(minutes=30))
        assert first["actions"]
        assert not second["actions"]
        assert ("duplicate_followup" in second["skipped"]
                or len(audit.events(
                    event_type="FOLLOW_UP_RATE_LIMITED")) >= 1
                or len(audit.events(
                    event_type="followup.suppressed")) >= 1)

    def test_final_case_skipped_never_dropped_silently(self, graph, audit):
        case = graph.create_case(tenant_id="t1")
        case.state = CaseState.WON
        result = CompletionLoopService(audit).run_case(case, now=T0)
        assert result["skipped"] == ["final_state"]


class TestE2EHvacLifecycle:
    """The mandated 23-step E2E: voice intake → photos → quote → offer →
    follow-up → WON, with every gate and audit verified."""

    def test_full_lifecycle(self, graph, audit):
        # 1-2: case from voice extraction payload + client party.
        case = graph.create_case(tenant_id="hvac-1", title="Heat pump quote",
                                 source_channel="voice")
        party = Party(tenant_id="hvac-1", type="client",
                      display_name="Jan Kowalski")
        graph.attach_entity(case, party, edge_type="PARTY")

        # 3: missing items (address + installation_photo among them).
        mi = MissingInfoService()
        mi.detect(case, {"client_contact": "+48600100200",
                         "service_type": "heat_pump_quote",
                         "urgency": "normal"}, audit=audit)
        assert {"address", "installation_photo"} <= {
            m.field_key for m in mi.open_blockers(case)}

        # 4: promise — photos tomorrow.
        case.promises.append(Promise(
            promisor="client", what="send photos",
            due_at=T0 + timedelta(days=1), importance=.7,
            dependency_impact=.8))
        audit.append(event_type="PROMISE_CREATED", actor="ai",
                     case_id=case.id, payload={"what": "send photos"})

        # 5: NEW_CONTACT → INTAKE_IN_PROGRESS → WAITING_FOR_CLIENT_INFO.
        transition(case, CaseState.INTAKE_IN_PROGRESS, actor="ai",
                   reason="intake", audit_log=audit)
        transition(case, CaseState.WAITING_FOR_CLIENT_INFO, actor="ai",
                   reason="blockers", audit_log=audit)

        # 6-9: loop run → NBA → gate allows → follow-up scheduled/sent.
        case.lead_score, case.value_estimate = 72, 10000
        loop = CompletionLoopService(audit)
        tick1 = loop.run_case(case, now=T0)
        assert tick1["selected_action"] in ("send_photo_request",
                                            "ask_for_missing_info")
        assert tick1["gate"] == "ALLOW" and tick1["actions"]

        # 10: audit so far.
        for ev in ["CASE_CREATED", "PARTY_ATTACHED", "MISSING_INFO_DETECTED",
                   "PROMISE_CREATED", "NEXT_ACTION_CREATED",
                   "ACTION_CREATED", "followup.sent"]:
            assert audit.events(event_type=ev), ev

        # 11-12: client sends photo → resolve missing item + fulfill promise.
        mi.resolve(case, "installation_photo", audit=audit)
        PromiseTrackerService.fulfill(case, "send photos", audit=audit)

        # 13: address still missing → stays WAITING_FOR_CLIENT_INFO.
        assert case.state is CaseState.WAITING_FOR_CLIENT_INFO
        assert {m.field_key for m in mi.open_blockers(case)} == {"address"}

        # 14-15: address arrives → QUALIFIED → QUOTE_PREPARATION.
        mi.resolve(case, "address", audit=audit)
        assert mi.open_blockers(case) == []
        transition(case, CaseState.QUALIFIED, actor="ai",
                   reason="all blockers resolved", audit_log=audit)
        transition(case, CaseState.QUOTE_PREPARATION, actor="ai",
                   reason="ready to quote", audit_log=audit)

        # 16: DecisionBrief (recorded via audit for the MVP scaffold).
        audit.append(event_type="DECISION_BRIEF_CREATED", actor="ai",
                     case_id=case.id,
                     payload={"summary": "Hot lead, €10k, quote ready",
                              "recommended_action": "send offer",
                              "requires_human_approval": True})

        # 17-18: offer sent (human approved) → OFFER_SENT.
        gate_d = ActionGateService().evaluate(case, "send_offer_commitment",
                                              audit=audit)
        assert gate_d.outcome == "REQUIRE_HUMAN_APPROVAL"
        audit.append(event_type="HUMAN_APPROVAL_GRANTED", actor="human",
                     case_id=case.id, payload={"action": "send_offer"})
        transition(case, CaseState.OFFER_SENT, actor="human",
                   reason="offer approved and sent", audit_log=audit)

        # 19-20: no response → loop schedules follow-up.
        case.next_best_action = {"type": "send_follow_up"}
        case.next_action_due_at = T0 + timedelta(days=2)
        case.last_progress_at = T0 + timedelta(days=1)
        tick2 = loop.run_case(case, now=T0 + timedelta(days=2))
        assert tick2["selected_action"] == "send_follow_up"

        # 21-22: client accepts → WON (final; exit requires human override).
        transition(case, CaseState.WON, actor="human",
                   reason="client accepted", audit_log=audit)
        assert case.state is CaseState.WON
        with pytest.raises(IllegalTransition):
            transition(case, CaseState.SCHEDULED, actor="ai",
                       reason="no override", audit_log=audit)
        transition(case, CaseState.SCHEDULED, actor="human",
                   reason="human schedules install", audit_log=audit,
                   human_override=True)

        # 23: timeline + audit chain.
        g = graph.get_case_graph(case.id, tenant_id="hvac-1")
        assert len(g["timeline"]) >= 15
        assert audit.verify_chain()
        state_changes = [e for e in g["timeline"]
                         if e.event_type == "case.state_changed"]
        assert len(state_changes) == 7   # every transition audited


class TestLGGTPlaceholderCallable:
    def test_placeholder_certifies_without_runtime(self, audit):
        from finalis.certainty_core import Fact, NullAdapter
        cert = NullAdapter(audit).certify(
            "case_transition:test", [Fact("state", "QUALIFIED", None, 0.9)],
            policy_version="v1")
        assert cert.verdict == "heuristic" and cert.audit_id
        assert len(audit.events(event_type="certainty.stamped")) == 1
