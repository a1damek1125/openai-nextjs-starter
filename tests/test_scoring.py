"""Scoring tests — canonical vectors per docs/finalis-ai/05 + 26 (defect fixes)."""
import math

import pytest

from finalis.scoring import (
    ActionCandidate, case_risk_score, doc_risk, escalation_score,
    evidence_confidence, followup_priority, lead_score, mis, must_escalate,
    next_best_action, normalize_prices, offer_score, promise_breach_score,
    source_trust, stuck_score,
)


class TestLeadScore:
    def test_hot_hvac_emergency(self):
        # V=0.6 U=1.0 F=0.8 C=1.0 D=0.9 R=0.5 →
        # 100*(0.18+0.20+0.12+0.15+0.09+0.05) = 79.0
        assert lead_score(0.6, 1.0, 0.8, 1.0, 0.9, 0.5) == pytest.approx(79.0)

    def test_all_zero(self):
        assert lead_score(0, 0, 0, 0, 0, 0) == 0.0

    def test_all_max_bounded_100(self):
        assert lead_score(1, 1, 1, 1, 1, 1) == pytest.approx(100.0)

    def test_out_of_range_inputs_clamped(self):
        assert lead_score(5.0, -3.0, 1, 1, 1, 1) == pytest.approx(
            lead_score(1.0, 0.0, 1, 1, 1, 1))

    def test_bad_weights_rejected(self):
        with pytest.raises(ValueError):
            lead_score(1, 1, 1, 1, 1, 1, weights={"V": 0.9, "U": 0.9, "F": 0,
                                                  "C": 0, "D": 0, "R": 0})


class TestMIS:
    def test_hvac_example(self):
        # missing: photo(0.7) + dimensions(0.6); present: address(0.9),
        # time(0.5), budget(0.3), decision(0.4). Σw=3.4, raw=1.3
        raw, norm = mis([0, 1, 0, 1, 0, 0], [0.9, 0.7, 0.5, 0.6, 0.3, 0.4])
        assert raw == pytest.approx(1.3)
        assert norm == pytest.approx(1.3 / 3.4)

    def test_sigma_w_zero_guard(self):
        raw, norm = mis([], [])
        assert (raw, norm) == (0.0, 0.0)

    def test_negative_weight_rejected(self):
        with pytest.raises(ValueError):
            mis([1], [-0.5])

    def test_nothing_missing(self):
        assert mis([0, 0], [0.9, 0.7]) == (0.0, 0.0)


class TestNBA:
    def test_hot_call_beats_cold_email(self):
        call = ActionCandidate("call_hot_lead", p_close=0.4, cost=5,
                               risk=2, delay_penalty=0)
        email = ActionCandidate("email_cold_lead", p_close=0.02, cost=0,
                                risk=0, delay_penalty=0)
        best = next_best_action([call, email], value=8000)
        assert best.name == "call_hot_lead"  # 0.4*8000-7=3193 vs 160

    def test_wait_costs_delay(self):
        wait = ActionCandidate("wait", p_close=0.0, cost=0, risk=0,
                               delay_penalty=50)
        nudge = ActionCandidate("whatsapp", p_close=0.05, cost=0.1, risk=1,
                                delay_penalty=0)
        assert next_best_action([wait, nudge], value=1000).name == "whatsapp"

    def test_empty_candidates_rejected(self):
        with pytest.raises(ValueError):
            next_best_action([], value=100)

    def test_tie_breaks_to_lower_cost(self):
        a = ActionCandidate("a", p_close=0.1, cost=10, risk=0, delay_penalty=0)
        b = ActionCandidate("b", p_close=0.1, cost=0, risk=0, delay_penalty=10)
        assert next_best_action([a, b], value=0).name == "b"


class TestFollowUpPriority:
    def test_unit_coherence(self):
        """Doc 26 fix: all factors on [0,1]; output bounded [-1,1]."""
        assert followup_priority(100, 1, 1, 0) == pytest.approx(1.0)
        assert followup_priority(0, 1, 1, 1) == pytest.approx(-1.0)

    def test_annoyance_dominates_low_lead(self):
        assert followup_priority(30, 0.5, 0.5, 0.5) < 0


class TestDocRisk:
    def test_risky_contract(self):
        # A=.8 M=.6 C=.7 P=.9 L=.5 Q=.2 →
        # 100*(.20+.12+.14+.135+.05+.02)=66.5 ≥ θ_docrisk 60
        assert doc_risk(.8, .6, .7, .9, .5, .2) == pytest.approx(66.5)

    def test_bounds(self):
        assert doc_risk(0, 0, 0, 0, 0, 0) == 0.0
        assert doc_risk(1, 1, 1, 1, 1, 1) == pytest.approx(100.0)


class TestEvidenceConfidence:
    def test_multiplicative(self):
        assert evidence_confidence(.9, .9, .9, .9) == pytest.approx(0.6561)

    def test_below_theta_conf(self):
        # Four .87 factors ≈ .573 < 0.6 → abstain regime (doc 26 harshness note)
        assert evidence_confidence(.87, .87, .87, .87) < 0.6

    def test_any_zero_kills_confidence(self):
        assert evidence_confidence(0, 1, 1, 1) == 0.0


class TestOfferScore:
    def test_full_axes(self):
        axes = {"price": 1.0, "scope": 0.8, "warranty": 1.0, "time": 0.6,
                "payment": 0.5, "risk": 0.9, "service": 1.0}
        # 25+16+15+9+5+9+5 = 84
        assert offer_score(axes) == pytest.approx(84.0)

    def test_missing_axis_scores_zero_not_crash(self):
        assert offer_score({"price": 1.0}) == pytest.approx(25.0)

    def test_price_normalization_guards(self):
        assert normalize_prices([]) == []
        assert normalize_prices([0.0]) == [0.0]
        assert normalize_prices([1000.0]) == [1.0]
        out = normalize_prices([1000.0, 2000.0])
        assert out == [pytest.approx(1.0), pytest.approx(0.5)]


class TestEscalation:
    def test_threshold(self):
        s = escalation_score(.5, .4, .3, .2, .0, .0)  # = 1.4 < 1.5
        assert not must_escalate(s)
        s2 = escalation_score(.5, .4, .3, .2, .2, .0)  # = 1.6
        assert must_escalate(s2)

    def test_hard_overrides_ignore_threshold(self):
        assert must_escalate(0.0, legal_signing=True)
        assert must_escalate(0.0, safety_emergency=True)

    def test_bounds(self):
        assert escalation_score(1, 1, 1, 1, 1, 1) == 6.0
        assert escalation_score(9, 9, 9, 9, 9, 9) == 6.0  # clamped


class TestStuckScore:
    def test_bounded_at_100(self):
        """Doc 26 defect fix: no unbounded growth."""
        assert stuck_score(3650.0, 100.0, 1.0) == pytest.approx(100.0)

    def test_typical(self):
        # 6 days / cap 30 = 0.2, lead 0.8, blocker 0.7 → 11.2
        assert stuck_score(6, 80, 0.7) == pytest.approx(11.2)

    def test_zero_days(self):
        assert stuck_score(0, 100, 1.0) == 0.0


class TestPromiseBreach:
    def test_bounded_0_1(self):
        """Doc 26 defect fix: delay normalized by expected window (72h)."""
        assert promise_breach_score(1.0, 100000.0, 1.0) == pytest.approx(1.0)

    def test_typical(self):
        # importance .8, 36h late of 72h window (.5), impact .6 → .24
        assert promise_breach_score(.8, 36.0, .6) == pytest.approx(0.24)

    def test_not_yet_late(self):
        assert promise_breach_score(1.0, 0.0, 1.0) == 0.0


class TestSourceTrust:
    def test_manufacturer_pdf(self):
        # A=.9 R=.8 Co=.5 D=1.0 T=1.0 → 100*(.315+.2+.1+.15+.05)=81.5
        assert source_trust(.9, .8, .5, 1.0, 1.0) == pytest.approx(81.5)

    def test_corroboration_must_be_normalized(self):
        """Doc 26 finding: raw counts would explode; inputs are clamped."""
        assert source_trust(1, 1, 7, 1, 1) == pytest.approx(100.0)


class TestCaseRisk:
    def test_rollup_takes_max_branch(self):
        # riskflag .9 → 54; docrisk 66.5 → 26.6; esc 1.6/1.5→clamp 1 → 100
        assert case_risk_score(.9, 66.5, 1.6) == pytest.approx(100.0)

    def test_empty_case(self):
        assert case_risk_score(0, 0, 0) == 0.0

    def test_bounds(self):
        assert 0 <= case_risk_score(1, 100, 9) <= 100
