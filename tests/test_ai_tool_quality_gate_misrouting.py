"""TOOL-B2 tool-selection misrouting / planner confusion.

The planner confusion matrix scores name/alias/purpose overlap between a
candidate descriptor and its TENANT-SCOPED peers. Confusion with a MORE
privileged peer is a misrouting hazard; a high enough hazard is a BLOCKER, a
smaller one a WARNING. Peers from another tenant never count.

Deterministic token-overlap only; no tool executes and no model is called.
"""
import pytest

from finalis.ai_employee import tool_quality as tq
from tests.conftest import Gate, OWNER, OTHER_OWNER

PASS = ("QUALITY_PASS", "QUALITY_PASS_WITH_WARNINGS")

CANDIDATE = {"tool_id": "cand", "tool_key": "case_search",
             "tool_name": "Case Search", "aliases": ["case lookup"],
             "purpose": ["CASE_TRIAGE"], "risk_rank": 1, "side_effect_rank": 0}
PRIV_PEER = {"tool_id": "peer_priv", "tool_key": "case_payment_search",
             "tool_name": "Case Payment Search", "aliases": ["case pay lookup"],
             "purpose": ["CASE_TRIAGE"], "risk_rank": 3, "side_effect_rank": 7,
             "category": "PAYMENT"}


class TestConfusionMatrixScoring:
    def test_no_peers_zero_misrouting(self):
        m = tq.build_planner_confusion_matrix(
            tool_id="cand", tenant_id="T", candidate=CANDIDATE, existing=[])
        assert m["misrouting_risk"] == 0.0
        assert m["confusable_tool_ids"] == []
        assert m["name_overlap_score"] == 0.0

    def test_name_alias_purpose_overlap_scored(self):
        m = tq.build_planner_confusion_matrix(
            tool_id="cand", tenant_id="T", candidate=CANDIDATE,
            existing=[PRIV_PEER])
        assert m["name_overlap_score"] > 0
        assert m["alias_overlap_score"] > 0
        # identical allowed-purpose lists → full purpose overlap.
        assert m["purpose_overlap_score"] == 1.0

    def test_more_privileged_peer_raises_misrouting(self):
        m = tq.build_planner_confusion_matrix(
            tool_id="cand", tenant_id="T", candidate=CANDIDATE,
            existing=[PRIV_PEER])
        assert m["misrouting_risk"] > 0
        assert "peer_priv" in m["confusable_tool_ids"]
        assert any("more-privileged" in r for r in m["misrouting_reasons"])

    def test_equal_or_lower_privilege_peer_no_misrouting(self):
        peer = dict(PRIV_PEER, tool_id="peer_low", risk_rank=0,
                    side_effect_rank=0)
        m = tq.build_planner_confusion_matrix(
            tool_id="cand", tenant_id="T", candidate=CANDIDATE, existing=[peer])
        # Still confusable by name/purpose, but no privilege gap → no hazard.
        assert m["misrouting_risk"] == 0.0
        assert "peer_low" in m["confusable_tool_ids"]

    def test_candidate_excludes_itself(self):
        self_peer = dict(PRIV_PEER, tool_id="cand")
        m = tq.build_planner_confusion_matrix(
            tool_id="cand", tenant_id="T", candidate=CANDIDATE,
            existing=[self_peer])
        assert m["confusable_tool_ids"] == []
        assert m["misrouting_risk"] == 0.0

    def test_confusion_hash_deterministic(self):
        a = tq.build_planner_confusion_matrix(
            tool_id="cand", tenant_id="T", candidate=CANDIDATE,
            existing=[PRIV_PEER])
        b = tq.build_planner_confusion_matrix(
            tool_id="cand", tenant_id="T", candidate=CANDIDATE,
            existing=[PRIV_PEER])
        assert a["planner_confusion_hash"] == b["planner_confusion_hash"]


class TestMisroutingThresholds:
    def test_high_risk_is_blocker(self):
        f = tq.detect_tool_selection_misrouting(
            {"misrouting_risk": 0.7}, {"misrouting_detected": False})
        assert ("planner_misrouting", "BLOCKER") in [
            (x["code"], x["severity"]) for x in f]

    def test_at_half_threshold_is_blocker(self):
        f = tq.detect_tool_selection_misrouting(
            {"misrouting_risk": 0.5}, {"misrouting_detected": False})
        codes = {(x["code"], x["severity"]) for x in f}
        assert ("planner_misrouting", "BLOCKER") in codes

    def test_low_positive_risk_is_warning(self):
        f = tq.detect_tool_selection_misrouting(
            {"misrouting_risk": 0.3}, {"misrouting_detected": False})
        codes = {(x["code"], x["severity"]) for x in f}
        assert ("planner_misrouting_warn", "WARNING") in codes
        assert ("planner_misrouting", "BLOCKER") not in codes

    def test_zero_risk_no_finding(self):
        f = tq.detect_tool_selection_misrouting(
            {"misrouting_risk": 0.0}, {"misrouting_detected": False})
        assert f == []

    def test_counterfactual_detected_is_blocker(self):
        f = tq.detect_tool_selection_misrouting(
            {"misrouting_risk": 0.0}, {"misrouting_detected": True})
        assert ("counterfactual_misrouting", "BLOCKER") in [
            (x["code"], x["severity"]) for x in f]


class TestMisroutingEndToEnd:
    def _register_pair(self, gate):
        """A more-privileged PAYMENT peer plus a similar-named read tool in the
        SAME tenant. Distinct normalized names avoid a TOOL-B1 collision."""
        priv = gate.register_quality_tool(
            tool_name="Case Payment Search", category="PAYMENT",
            side_effect_class="PAYMENT_MOVEMENT",
            declared_side_effects=["PAYMENT_MOVEMENT"], touches_payment=True,
            tool_summary="search case payment records",
            tool_description="Search over case payment records by keyword.")
        assert priv.status_code == 200
        less = gate.register_quality_tool(
            tool_name="Case Search", tool_summary="search case records",
            tool_description="Read only search over local case records by "
            "keyword; returns case ids and titles. No side effects.")
        return priv.json()["tool_id"], less.json()["tool_id"]

    def test_similar_named_tools_raise_confusion(self, gate):
        priv_id, less_id = self._register_pair(gate)
        rep = gate.quality_check(less_id).json()
        m = rep["planner_confusion_matrix"]
        assert m["misrouting_risk"] >= 0.5
        assert priv_id in m["confusable_tool_ids"]
        assert priv_id in rep["descriptor_confusion_set"]

    def test_misrouting_flag_in_report(self, gate):
        _, less_id = self._register_pair(gate)
        rep = gate.quality_check(less_id).json()
        assert "planner_misrouting" in rep["tool_selection_misrouting_flags"]
        assert rep["quality_status"] not in PASS

    def test_confusion_endpoint_returns_matrix(self, gate):
        priv_id, less_id = self._register_pair(gate)
        gate.quality_check(less_id)
        body = gate.q(less_id, "/confusion", actor=OWNER).json()
        assert "planner_confusion_matrix" in body
        assert "descriptor_confusion_set" in body
        assert body["planner_confusion_matrix"]["misrouting_risk"] >= 0.5
        assert priv_id in body["descriptor_confusion_set"]

    def test_peer_from_other_tenant_does_not_count(self, gate):
        # OTHER_OWNER registers a similar privileged tool in a DIFFERENT tenant.
        gate.register_quality_tool(
            requester=OTHER_OWNER, tool_name="Case Payment Search",
            category="PAYMENT", side_effect_class="PAYMENT_MOVEMENT",
            declared_side_effects=["PAYMENT_MOVEMENT"], touches_payment=True,
            tool_summary="search case payment records",
            tool_description="Search over case payment records by keyword.")
        # The demo-tenant read tool has NO local peer.
        less_id = gate.register_quality_tool(
            requester=OWNER, tool_name="Case Search",
            tool_summary="search case records",
            tool_description="Read only search over local case records by "
            "keyword; returns case ids.").json()["tool_id"]
        rep = gate.quality_check(less_id, actor=OWNER).json()
        m = rep["planner_confusion_matrix"]
        assert m["misrouting_risk"] == 0.0
        assert m["confusable_tool_ids"] == []
        assert rep["quality_status"] == "QUALITY_PASS"
