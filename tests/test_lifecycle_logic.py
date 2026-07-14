"""Universal lifecycle logic tests — invariants, decision tables, scoring,
edge cases, seeded property tests, idempotency."""
import random

import pytest

from finalis.audit import AuditLog
from finalis.lifecycle.completion import (ActiveCaseStatus, CaseFacts,
                                          active_case_invariant, can_complete,
                                          close_case, hard_blockers)
from finalis.lifecycle.decisions import (ALLOW, BLOCK, REQUIRE_HUMAN_REVIEW,
                                         can_ai_send, case_readiness_score,
                                         churn_risk, clv_placeholder,
                                         deal_win_probability,
                                         expected_deal_value,
                                         followup_allowed, recovery_eligible,
                                         recovery_score,
                                         requires_human_approval,
                                         upsell_allowed, upsell_score)
from finalis.lifecycle.evidence import (EvidenceBundle, EvidenceError,
                                        UpsellOpportunity, record_decision)
from finalis.lifecycle.outcomes import (Outcome, OutcomeValidationError,
                                        outcome_reason_confidence,
                                        validate_outcome)
from finalis.lifecycle.playbooks import (B2B_SALES, BASE_PLAYBOOKS,
                                         HVAC_HOME_SERVICES,
                                         PROPERTY_MANAGEMENT, PRODUCT_SALE,
                                         PlaybookValidationError,
                                         VerticalPlaybook, activate_playbook,
                                         validate_playbook)
from finalis.lifecycle.vector import (DealState, FulfillmentState,
                                      LifecycleVector, SupportState,
                                      TransactionState)


def won_vector(**kw):
    return LifecycleVector(deal=DealState.WON,
                           transaction=kw.pop("transaction",
                                              TransactionState.PAID),
                           fulfillment=kw.pop("fulfillment",
                                              FulfillmentState.COMPLETED),
                           **kw)


def ready_facts(pb=HVAC_HOME_SERVICES, **kw):
    return CaseFacts(vector=kw.pop("vector", won_vector()),
                     closure_evidence_id=kw.pop("evidence", "ev-1"),
                     completion_confirmed=kw.pop("confirmed", True),
                     contract_signed=kw.pop("signed", True), **kw)


class TestDerivedOutcomeViews:
    def test_won_but_unpaid_is_not_completed(self):
        v = won_vector(transaction=TransactionState.PAYMENT_PENDING)
        assert v.derived_outcome_view() == "WON_NOT_FULFILLED"
        assert "payment is still pending" in v.business_language()

    def test_paid_but_undelivered(self):
        v = won_vector(fulfillment=FulfillmentState.SCHEDULED)
        assert v.derived_outcome_view() == "WON_PAID_NOT_DELIVERED"
        assert "not yet delivered" in v.business_language()

    def test_fully_settled_is_won_completed(self):
        assert won_vector().derived_outcome_view() == "WON_COMPLETED"

    def test_declined_maps_to_lost_view(self):
        v = LifecycleVector(deal=DealState.DECLINED_BY_CLIENT)
        assert v.derived_outcome_view() == "LOST_WITH_REASON"


class TestCompletionRule:
    def test_completes_when_everything_satisfied(self):
        check = can_complete(ready_facts(), HVAC_HOME_SERVICES)
        assert check.ok, check.blocked_reasons

    @pytest.mark.parametrize("facts,expected", [
        (ready_facts(vector=won_vector(
            transaction=TransactionState.PAYMENT_PENDING)),
         "payment not settled"),
        (ready_facts(vector=won_vector(
            fulfillment=FulfillmentState.IN_PROGRESS)),
         "fulfillment not completed"),
        (ready_facts(evidence=None), "closure evidence missing"),
        (ready_facts(confirmed=False), "completion confirmation required"),
        (ready_facts(missing_blocking_items=["address"]),
         "blocking missing items"),
    ])
    def test_each_condition_blocks_with_reason_and_nba(self, facts, expected):
        check = can_complete(facts, HVAC_HOME_SERVICES)
        assert not check.ok
        assert any(expected in r for r in check.blocked_reasons)
        assert check.next_best_action        # always explains what to do

    def test_b2b_requires_signed_contract(self):
        check = can_complete(ready_facts(signed=False), B2B_SALES)
        assert any("contract" in r for r in check.blocked_reasons)

    def test_property_mgmt_no_invoice_needed_but_confirmation_is(self):
        facts = ready_facts(
            vector=won_vector(
                transaction=TransactionState.NO_INVOICE_REQUIRED),
            confirmed=False)
        check = can_complete(facts, PROPERTY_MANAGEMENT)
        assert not check.ok
        assert any("confirmation" in r for r in check.blocked_reasons)
        # But payment is NOT among the blockers (playbook: not required).
        assert not any("payment" in r for r in check.blocked_reasons)

    def test_hard_blockers_override_everything(self):
        facts = ready_facts()
        facts.vector.opted_out = True
        assert hard_blockers(facts)
        assert not can_complete(facts, HVAC_HOME_SERVICES).ok
        facts2 = ready_facts(pending_high_risk_approvals=1)
        check2 = can_complete(facts2, HVAC_HOME_SERVICES)
        assert not check2.ok
        assert check2.next_best_action == "request_human_review"

    def test_open_complaint_blocks_closure(self):
        facts = ready_facts()
        facts.vector.support = SupportState.COMPLAINT_OPEN
        assert not can_complete(facts, HVAC_HOME_SERVICES).ok


class TestOutcomeInvariant:
    def test_lost_without_reason_rejected(self):
        with pytest.raises(OutcomeValidationError):
            validate_outcome(Outcome(outcome_type="LOST"))

    def test_lost_with_unknown_reason_string_rejected(self):
        with pytest.raises(OutcomeValidationError):
            validate_outcome(Outcome(outcome_type="LOST",
                                     outcome_reason="whatever",
                                     outcome_reason_category="price"))

    def test_lost_needs_evidence_or_override(self):
        with pytest.raises(OutcomeValidationError):
            validate_outcome(Outcome(
                outcome_type="LOST", outcome_reason="price_too_high",
                outcome_reason_category="commercial"))
        validate_outcome(Outcome(          # override path OK
            outcome_type="LOST", outcome_reason="price_too_high",
            outcome_reason_category="commercial", human_override=True))

    @pytest.mark.parametrize("otype", ["CANCELLED", "DISQUALIFIED",
                                       "ABANDONED", "RECOVERY_LATER"])
    def test_no_silent_closure_for_any_reason_required_type(self, otype):
        with pytest.raises(OutcomeValidationError):
            validate_outcome(Outcome(outcome_type=otype))

    def test_close_case_writes_outcome_audit(self):
        audit = AuditLog()
        view = close_case(ready_facts(), HVAC_HOME_SERVICES, Outcome(
            outcome_type="WON", outcome_reason="invoice_paid",
            outcome_reason_category="commercial",
            evidence_reference_id="ev-9"), audit)
        assert view == "WON_COMPLETED"
        assert audit.events(event_type="OUTCOME_REASON_SET")

    def test_completed_close_blocked_when_rule_fails(self):
        audit = AuditLog()
        facts = ready_facts(vector=won_vector(
            transaction=TransactionState.PAYMENT_PENDING))
        with pytest.raises(ValueError):
            close_case(facts, HVAC_HOME_SERVICES, Outcome(
                outcome_type="COMPLETED", outcome_reason=None), audit)
        assert audit.events(event_type="CASE_COMPLETION_BLOCKED")

    def test_reason_confidence_multiplicative(self):
        low = outcome_reason_confidence(
            evidence_quality=.9, source_reliability=.9, explicitness=.5,
            recency=.9, consistency=.9)
        assert low < 0.4                      # candidate only, not certain


class TestPlaybookValidation:
    def test_all_base_playbooks_valid_and_activatable(self):
        for pb in BASE_PLAYBOOKS:
            assert validate_playbook(pb) == [], pb.vertical_id
            activate_playbook(pb)

    def test_contradictory_playbook_refused(self):
        pb = VerticalPlaybook(
            vertical_id="bad", name="Bad", case_types=["x"],
            required_information=[{"key": "a", "weight": 0.5,
                                   "hard_required": True}],
            required_documents=[], invoice_required=False,
            payment_required=True)          # payment without invoice
        errors = validate_playbook(pb)
        assert any("contradiction" in e for e in errors)
        with pytest.raises(PlaybookValidationError):
            activate_playbook(pb)

    def test_spam_cadence_refused(self):
        pb = VerticalPlaybook(
            vertical_id="spam", name="Spam", case_types=["x"],
            required_information=[{"key": "a", "weight": 0.5,
                                   "hard_required": False}],
            required_documents=[], max_follow_up_attempts=50)
        assert any("spam" in e for e in validate_playbook(pb))

    def test_allowed_and_prohibited_overlap_refused(self):
        pb = VerticalPlaybook(
            vertical_id="ovl", name="Ovl", case_types=["x"],
            required_information=[{"key": "a", "weight": 0.5,
                                   "hard_required": False}],
            required_documents=[],
            allowed_ai_actions=["legal_advice"])   # also prohibited
        assert any("contradictory" in e for e in validate_playbook(pb))


class TestDecisionTables:
    def test_can_ai_send_matrix(self):
        v = LifecycleVector()
        assert can_ai_send("send_follow_up", HVAC_HOME_SERVICES, v) == ALLOW
        assert can_ai_send("legal_advice", HVAC_HOME_SERVICES, v) == BLOCK
        assert can_ai_send("novel_thing", HVAC_HOME_SERVICES, v) \
            == REQUIRE_HUMAN_REVIEW        # safe default
        v.opted_out = True
        assert can_ai_send("send_follow_up", HVAC_HOME_SERVICES, v) == BLOCK

    def test_human_approval_matrix(self):
        assert requires_human_approval("issue_invoice", HVAC_HOME_SERVICES)
        assert requires_human_approval("refund", HVAC_HOME_SERVICES)
        assert requires_human_approval("close_lost", HVAC_HOME_SERVICES,
                                       high_value=True)
        assert not requires_human_approval("close_lost", HVAC_HOME_SERVICES,
                                           high_value=False)
        assert requires_human_approval("anything", HVAC_HOME_SERVICES,
                                       low_confidence=True)

    def test_followup_blocked_after_optout_and_max(self):
        v = LifecycleVector()
        assert followup_allowed(v, attempts=1, max_attempts=3) == ALLOW
        assert followup_allowed(v, attempts=3, max_attempts=3) == BLOCK
        v.opted_out = True
        assert followup_allowed(v, attempts=0, max_attempts=3) == BLOCK


class TestUpsellLogic:
    def base(self):
        return won_vector()

    def test_upsell_blocked_by_open_complaint(self):
        v = self.base()
        v.support = SupportState.COMPLAINT_OPEN
        assert upsell_allowed(v, HVAC_HOME_SERVICES,
                              days_since_completion=30) == BLOCK
        assert upsell_score(need_fit=1, satisfaction=1, product_adjacency=1,
                            timing_fit=1, clv_score=1, response_propensity=1,
                            margin_potential=1, complaint_open=True) == 0.0

    def test_upsell_blocked_by_overdue_payment(self):
        v = self.base()
        v.transaction = TransactionState.PAYMENT_OVERDUE
        assert upsell_allowed(v, HVAC_HOME_SERVICES,
                              days_since_completion=30) == BLOCK

    def test_upsell_blocked_before_value_delivered(self):
        v = won_vector(fulfillment=FulfillmentState.IN_PROGRESS)
        assert upsell_allowed(v, HVAC_HOME_SERVICES,
                              days_since_completion=30) == BLOCK

    def test_upsell_cooldown_then_human_review(self):
        v = self.base()
        assert upsell_allowed(v, HVAC_HOME_SERVICES,
                              days_since_completion=3) == BLOCK   # cooldown
        assert upsell_allowed(v, HVAC_HOME_SERVICES,
                              days_since_completion=30) \
            == REQUIRE_HUMAN_REVIEW      # high-value rule → human signs off

    def test_complaint_resolved_reevaluates(self):
        v = self.base()
        v.support = SupportState.COMPLAINT_OPEN
        assert upsell_allowed(v, HVAC_HOME_SERVICES,
                              days_since_completion=30) == BLOCK
        v.support = SupportState.COMPLAINT_RESOLVED
        assert upsell_allowed(v, HVAC_HOME_SERVICES,
                              days_since_completion=30) != BLOCK

    def test_opportunity_status_machine(self):
        opp = UpsellOpportunity(
            tenant_id="t", customer_id="c", source_case_id="k",
            opportunity_type="upsell", reason="maintenance plan fits",
            recommended_offer="service plan", confidence=0.7,
            earliest_contact_at="2026-08-01")
        opp.set_status("READY")
        with pytest.raises(ValueError):
            opp.set_status("SENT")           # not a valid status


class TestRecoveryLogic:
    def test_eligible_reasons(self):
        v = LifecycleVector()
        assert recovery_eligible("timing_later", HVAC_HOME_SERVICES, v)
        assert not recovery_eligible("price_too_high",
                                     HVAC_HOME_SERVICES, v)

    def test_optout_and_anger_kill_recovery(self):
        v = LifecycleVector(opted_out=True)
        assert not recovery_eligible("timing_later", HVAC_HOME_SERVICES, v)
        v2 = LifecycleVector()
        assert not recovery_eligible("timing_later", HVAC_HOME_SERVICES, v2,
                                     angry_client=True)
        assert recovery_score(deal_value_score=1, service_fit=1,
                              positive_relationship=1, timing_later=1,
                              prior_engagement=1, margin_potential=1,
                              strategic_value=1, opted_out=True) == 0.0

    def test_consent_expiry_blocks_recovery(self):
        v = LifecycleVector(consent_valid=False)
        assert not recovery_eligible("timing_later", HVAC_HOME_SERVICES, v)


class TestScoringModels:
    def test_case_readiness(self):
        assert case_readiness_score([(0.9, False), (0.7, False)]) == 1.0
        assert case_readiness_score([(0.9, True), (0.7, True)]) == 0.0
        assert case_readiness_score([(0.3, True)]) == pytest.approx(0.7)

    def test_win_probability_clamped_heuristic(self):
        assert deal_win_probability(stage_base=0.9, responsiveness=1,
                                    completeness=1, fit=1, urgency=1) == 1.0
        assert deal_win_probability(stage_base=0.1, price_objection=1,
                                    no_response=1, risk=1) == 0.0

    def test_expected_value_marks_margin_assumption(self):
        value, assumed = expected_deal_value(0.5, 10000)
        assert value == 5000 and assumed is True
        value2, assumed2 = expected_deal_value(0.5, 10000,
                                               gross_margin_factor=0.4)
        assert value2 == 2000 and assumed2 is False

    def test_clv_partial_data_low_confidence(self):
        clv, conf = clv_placeholder(average_order_value=1000,
                                    purchase_frequency_per_year=None,
                                    gross_margin=None,
                                    expected_retention_years=None)
        assert conf == "low"
        clv2, conf2 = clv_placeholder(average_order_value=1000,
                                      purchase_frequency_per_year=2,
                                      gross_margin=0.3,
                                      expected_retention_years=5,
                                      service_cost=100)
        assert clv2 == pytest.approx(2900) and conf2 == "medium"

    def test_churn_risk_bounds(self):
        assert churn_risk(days_since_positive=365, complaint=1,
                          no_response=1, payment_issue=1,
                          low_satisfaction=1, competitor=1,
                          declining_engagement=1) == 1.0
        assert churn_risk(days_since_positive=0, complaint=0, no_response=0,
                          payment_issue=0, low_satisfaction=0, competitor=0,
                          declining_engagement=0) == 0.0


class TestEvidenceBundle:
    def test_state_changing_decision_requires_evidence(self):
        audit = AuditLog()
        bundle = EvidenceBundle(
            case_id="c", tenant_id="t", actor_type="ai", actor_id="ai-1",
            decision_type="close_won", pre_state={"deal": "OFFER_SENT"},
            post_state={"deal": "WON"}, input_facts={},
            evidence_references=[], rule_or_playbook_version="hvac-1.0",
            confidence=0.9, action_gate_result="ALLOW")
        with pytest.raises(EvidenceError):
            record_decision(bundle, audit)
        bundle.evidence_references = ["ev-1"]
        done = record_decision(bundle, audit)
        assert done.audit_event_id
        assert audit.events(event_type="LIFECYCLE_VECTOR_UPDATED")
        assert audit.verify_chain()


class TestActiveCaseInvariant:
    def test_silent_case_fails_invariant(self):
        assert not active_case_invariant(ActiveCaseStatus())
        assert active_case_invariant(ActiveCaseStatus(next_action="call"))
        assert active_case_invariant(ActiveCaseStatus(
            blocked_reason="waiting for payment"))
        assert active_case_invariant(ActiveCaseStatus(
            human_review_required=True))


class TestPropertySeeded:
    """Seeded randomized property tests (dependency-free hypothesis-style)."""

    def test_random_vectors_never_complete_with_hard_blocker(self):
        rng = random.Random(2026)
        for _ in range(300):
            v = LifecycleVector(
                deal=rng.choice(list(DealState)),
                transaction=rng.choice(list(TransactionState)),
                fulfillment=rng.choice(list(FulfillmentState)),
                support=rng.choice(list(SupportState)),
                opted_out=rng.random() < 0.3,
                consent_valid=rng.random() > 0.2)
            facts = CaseFacts(
                vector=v,
                missing_hard_required=(["x"] if rng.random() < 0.3 else []),
                pending_high_risk_approvals=rng.choice([0, 0, 1]),
                closure_evidence_id="ev" if rng.random() < 0.8 else None,
                completion_confirmed=rng.random() < 0.7,
                contract_signed=True)
            pb = rng.choice(BASE_PLAYBOOKS)
            check = can_complete(facts, pb)
            # Property 1: hard blocker ⇒ never completable.
            if hard_blockers(facts):
                assert not check.ok
            # Property 2: blocked ⇒ reasons + next action always present.
            if not check.ok:
                assert check.blocked_reasons and check.next_best_action
            # Property 3: ok ⇒ derived view is WON_COMPLETED.
            if check.ok:
                assert v.derived_outcome_view() == "WON_COMPLETED"

    def test_random_outcomes_never_close_silently(self):
        rng = random.Random(7)
        from finalis.lifecycle.outcomes import (OUTCOME_TYPES,
                                                REASON_REQUIRED)
        for _ in range(200):
            otype = rng.choice(sorted(OUTCOME_TYPES))
            outcome = Outcome(outcome_type=otype)
            if otype in REASON_REQUIRED:
                with pytest.raises(OutcomeValidationError):
                    validate_outcome(outcome)

    def test_upsell_never_fires_with_blockers(self):
        rng = random.Random(99)
        for _ in range(200):
            complaint = rng.random() < 0.5
            overdue = rng.random() < 0.5
            s = upsell_score(
                need_fit=rng.random(), satisfaction=rng.random(),
                product_adjacency=rng.random(), timing_fit=rng.random(),
                clv_score=rng.random(), response_propensity=rng.random(),
                margin_potential=rng.random(), complaint_open=complaint,
                payment_overdue=overdue, annoyance_risk=rng.random())
            if complaint or overdue:
                assert s == 0.0
            assert 0.0 <= s <= 1.0


class TestEdgeCases:
    """The mandated edge-case battery (grouped)."""

    def test_accepts_but_never_pays(self):
        v = won_vector(transaction=TransactionState.PAYMENT_PENDING)
        check = can_complete(ready_facts(vector=v), HVAC_HOME_SERVICES)
        assert not check.ok and check.next_best_action == "await_payment"

    def test_deposit_paid_then_cancelled(self):
        outcome = Outcome(outcome_type="CANCELLED",
                          outcome_reason="client_cancelled_after_acceptance",
                          outcome_reason_category="client",
                          evidence_reference_id="ev-2")
        validate_outcome(outcome)          # legal, with reason + evidence

    def test_paid_but_not_delivered_blocks_completion(self):
        v = won_vector(fulfillment=FulfillmentState.SCHEDULED)
        assert not can_complete(ready_facts(vector=v),
                                HVAC_HOME_SERVICES).ok

    def test_service_done_but_unpaid_blocks_completion(self):
        v = won_vector(transaction=TransactionState.INVOICE_ISSUED)
        check = can_complete(ready_facts(vector=v), HVAC_HOME_SERVICES)
        assert any("payment" in r for r in check.blocked_reasons)

    def test_payment_failed_next_action_is_retry(self):
        v = won_vector(transaction=TransactionState.PAYMENT_FAILED)
        check = can_complete(ready_facts(vector=v), HVAC_HOME_SERVICES)
        assert check.next_best_action == "retry_payment"

    def test_competitor_chosen_with_reason_recovery_possible(self):
        outcome = Outcome(outcome_type="LOST",
                          outcome_reason="competitor_chosen",
                          outcome_reason_category="commercial",
                          evidence_reference_id="ev-3",
                          recovery_eligible=False)
        validate_outcome(outcome)
        # friendly competitor loss → recovery via explicit reason only if
        # playbook allows; competitor_chosen is NOT in eligible list:
        assert not recovery_eligible("competitor_chosen",
                                     HVAC_HOME_SERVICES, LifecycleVector())

    def test_refuses_reason_falls_back_to_unknown(self):
        outcome = Outcome(outcome_type="LOST",
                          outcome_reason="unknown_reason",
                          outcome_reason_category="unknown",
                          human_override=True)
        validate_outcome(outcome)          # LOST_UNKNOWN_REASON path

    def test_product_sale_no_appointment_but_delivery_required(self):
        v = won_vector(fulfillment=FulfillmentState.DELIVERED)
        check = can_complete(
            ready_facts(vector=v, confirmed=True), PRODUCT_SALE)
        assert check.ok

    def test_playbook_version_recorded_in_closure_audit(self):
        audit = AuditLog()
        close_case(ready_facts(), HVAC_HOME_SERVICES, Outcome(
            outcome_type="WON", outcome_reason="invoice_paid",
            outcome_reason_category="commercial",
            evidence_reference_id="ev"), audit)
        ev = audit.events(event_type="OUTCOME_REASON_SET")[0]
        assert ev.payload["playbook_version"] == "1.0"

    def test_refund_after_completion_needs_human(self):
        assert requires_human_approval("refund", HVAC_HOME_SERVICES)

    def test_reopen_final_case_needs_human(self):
        assert requires_human_approval("reopen_final_case",
                                       HVAC_HOME_SERVICES)


class TestIdempotency:
    def test_same_decision_recorded_once_per_action_id(self):
        audit = AuditLog()
        seen: set = set()

        def idempotent_record(bundle):
            if bundle.action_id in seen:
                return None                      # duplicate suppressed
            seen.add(bundle.action_id)
            return record_decision(bundle, audit)

        bundle = EvidenceBundle(
            case_id="c", tenant_id="t", actor_type="ai", actor_id="ai-1",
            decision_type="close_won", pre_state={}, post_state={},
            input_facts={}, evidence_references=["ev"],
            rule_or_playbook_version="v1", confidence=1.0,
            action_gate_result="ALLOW")
        assert idempotent_record(bundle) is not None
        assert idempotent_record(bundle) is None       # second run: no-op
        assert len(audit.events(
            event_type="LIFECYCLE_VECTOR_UPDATED")) == 1
        assert audit.verify_chain()


class TestDashboardSemantics:
    def test_won_not_shown_as_finished(self):
        from finalis.lifecycle.dashboard_ext import lifecycle_alerts
        pending = ready_facts(vector=won_vector(
            transaction=TransactionState.PAYMENT_OVERDUE))
        undelivered = ready_facts(vector=won_vector(
            fulfillment=FulfillmentState.SCHEDULED))
        complaint = ready_facts()
        complaint.vector.support = SupportState.COMPLAINT_OPEN
        rows = lifecycle_alerts([
            ("c1", pending, HVAC_HOME_SERVICES),
            ("c2", undelivered, HVAC_HOME_SERVICES),
            ("c3", complaint, HVAC_HOME_SERVICES)])
        # Overdue money floats to the top.
        assert rows[0]["case_id"] == "c1" and rows[0]["priority"] == 1
        assert "overdue" in rows[0]["message"]
        assert rows[0]["next_best_action"]
        # Undelivered is plainly not finished.
        r2 = next(r for r in rows if r["case_id"] == "c2")
        assert r2["view"] == "WON_PAID_NOT_DELIVERED"
        assert "not yet delivered" in r2["message"]
        # No raw enum names leak into messages.
        for r in rows:
            assert "PAYMENT_PENDING" not in r["message"]
            assert "transaction_state" not in r["message"]
        # Complaint blocks upsell, visibly.
        r3 = next(r for r in rows if r["case_id"] == "c3")
        assert r3.get("upsell_blocked") is True
