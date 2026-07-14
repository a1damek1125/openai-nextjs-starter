"""TOOL-B2 non-regression proof tests.

The non-regression proof compares the current quality report against the prior
one for the same tool: it computes new/removed blockers and score/risk deltas,
and flags NEEDS_REVIEW when a blocker is removed WITHOUT evidence (the local
gate treats a genuine descriptor edit as the only evidence). It also enforces
no-Goodhart: a high numeric score can never yield PASS when a critical blocker
exists. These tests assert ACTUAL behavior; no product file is modified.
"""
import pytest

from tests.conftest import OWNER
from finalis.ai_employee import tool_quality as tq

PASS_STATUSES = ("QUALITY_PASS", "QUALITY_PASS_WITH_WARNINGS")


class TestNonRegressionKernel:
    def test_first_check_matched(self):
        p = tq.non_regression_proof(
            tenant_id="demo", tool_id="t1", tool_version_id="t1-v1",
            previous=None, current_blockers=[], current_report_hash="rh",
            current_score_total=155, current_risk="TRIVIAL",
            current_descriptor_hash="h1")
        assert p["non_regression_status"] == "MATCHED"
        assert p["new_blockers"] == []
        assert p["removed_blockers"] == []

    def test_first_check_score_delta_none(self):
        p = tq.non_regression_proof(
            tenant_id="demo", tool_id="t1", tool_version_id="t1-v1",
            previous=None, current_blockers=[], current_report_hash="rh",
            current_score_total=155, current_risk="TRIVIAL",
            current_descriptor_hash="h1")
        # No prior score -> delta is None (nothing to regress against).
        assert p["score_delta"] is None
        assert p["risk_delta"] == 0

    def test_new_blocker_computed(self):
        prev = {"quality_blockers": [], "quality_score_total": 155,
                "quality_report_hash": "prev", "tool_descriptor_hash": "h0"}
        p = tq.non_regression_proof(
            tenant_id="demo", tool_id="t1", tool_version_id="t1-v2",
            previous=prev, current_blockers=[{"code": "overclaim"}],
            current_report_hash="rh2", current_score_total=140,
            current_risk="TRIVIAL", current_descriptor_hash="h1")
        assert p["new_blockers"] == ["overclaim"]
        assert p["removed_blockers"] == []

    def test_removed_blocker_without_evidence_needs_review(self):
        # previous had a blocker the current lacks while the descriptor hash is
        # UNCHANGED (prev tool_descriptor_hash == current_descriptor_hash) -> the
        # removal is unevidenced -> NEEDS_REVIEW.
        prev = {"quality_blockers": [{"code": "some_blocker"}],
                "quality_score_total": 100, "quality_report_hash": "prev",
                "tool_descriptor_hash": "SAME"}
        p = tq.non_regression_proof(
            tenant_id="demo", tool_id="t1", tool_version_id="t1-v2",
            previous=prev, current_blockers=[], current_report_hash="rh2",
            current_score_total=155, current_risk="TRIVIAL",
            current_descriptor_hash="SAME")
        assert p["removed_blockers"] == ["some_blocker"]
        assert p["removed_blockers_have_evidence"] is False
        assert p["non_regression_status"] == "NEEDS_REVIEW"

    def test_removed_blocker_with_evidence_matched(self):
        # A genuine descriptor edit (prev hash != current hash) evidences the
        # removal -> MATCHED.
        prev = {"quality_blockers": [{"code": "some_blocker"}],
                "quality_score_total": 100, "quality_report_hash": "prev",
                "tool_descriptor_hash": "OLD_HASH"}
        p = tq.non_regression_proof(
            tenant_id="demo", tool_id="t1", tool_version_id="t1-v2",
            previous=prev, current_blockers=[], current_report_hash="rh2",
            current_score_total=155, current_risk="TRIVIAL",
            current_descriptor_hash="NEW_HASH")
        assert p["removed_blockers"] == ["some_blocker"]
        assert p["removed_blockers_have_evidence"] is True
        assert p["non_regression_status"] == "MATCHED"

    def test_score_and_risk_delta_present(self):
        prev = {"quality_blockers": [], "quality_score_total": 155,
                "quality_report_hash": "prev", "tool_descriptor_hash": "h0",
                "monotonic_detected_risk": "LOW"}
        p = tq.non_regression_proof(
            tenant_id="demo", tool_id="t1", tool_version_id="t1-v2",
            previous=prev, current_blockers=[], current_report_hash="rh2",
            current_score_total=150, current_risk="HIGH",
            current_descriptor_hash="h1")
        assert p["score_delta"] == -5
        # risk escalated LOW(1) -> HIGH(3).
        assert p["risk_delta"] == 2

    def test_deterministic_hash(self):
        kw = dict(tenant_id="demo", tool_id="t1", tool_version_id="t1-v1",
                  previous=None, current_blockers=[], current_report_hash="rh",
                  current_score_total=155, current_risk="TRIVIAL",
                  current_descriptor_hash="h1")
        a = tq.non_regression_proof(**kw)
        b = tq.non_regression_proof(**kw)
        assert a == b
        assert a["non_regression_proof_hash"] == b["non_regression_proof_hash"]


class TestNonRegressionEndpointAndReport:
    def test_first_report_non_regression_matched(self, gate):
        _, rep = gate.checked_quality_tool()
        summ = rep["non_regression_summary"]
        assert summ["non_regression_status"] == "MATCHED"
        assert summ["score_delta"] is None

    def test_non_regression_endpoint(self, gate):
        tid, _ = gate.checked_quality_tool()
        r = gate.q(tid, "/non-regression", actor=OWNER)
        assert r.status_code == 200
        body = r.json()
        assert body["tool_id"] == tid
        assert body["non_regression_summary"][
            "non_regression_status"] == "MATCHED"

    def test_second_version_compares_previous_current(self, gate):
        tid, rep1 = gate.checked_quality_tool()
        # TOOL-B1 add-version with a changed descriptor, then re-check.
        body = gate.quality_tool_body(
            tool_description="Read-only search over local case records by "
            "keyword; returns matching case ids. No side effects, no external "
            "calls, no writes. Second revision with different wording.")
        av = gate.c.post(f"/ai-tools/{tid}/versions", json=body,
                         headers=gate.h(OWNER))
        assert av.status_code == 200
        rep2 = gate.quality_check(tid, actor=OWNER).json()
        summ = rep2["non_regression_summary"]
        # The proof now references the prior report and computes deltas.
        assert summ["previous_quality_report_hash"] is not None
        assert isinstance(summ["new_blockers"], list)
        assert isinstance(summ["removed_blockers"], list)
        assert isinstance(summ["score_delta"], int)
        assert summ["score_delta"] == rep2["quality_score_total"] - rep1[
            "quality_score_total"]
        assert isinstance(summ["risk_delta"], int)


class TestNoGoodhart:
    def test_kernel_single_blocker_beats_high_score(self):
        # A single BLOCKER zeros only its dimension: the total stays HIGH, yet
        # the dominant status is non-pass. Score cannot buy a PASS.
        findings = [{"code": "overclaim", "severity": "BLOCKER",
                     "category": "OVERCLAIM", "dimension": "OVERCLAIM_RESISTANCE",
                     "detail": "d"}]
        sv = tq.compute_score_vector(
            findings=findings, ir={"ir_matches_tool_b1_truth": True},
            assurance_graph={"assurance_graph_status": "MATCHED",
                             "unsupported_claims": []},
            mutation={"mutation_harness_status": "CLEAR"},
            metamorphic={"metamorphic_status": "PASSED"},
            monotonic={"monotonicity_status": "MATCHED"},
            non_regression=None, boundary={"minimal_context_status": "MINIMAL"},
            confusion={"misrouting_risk": 0.0})
        assert sv["scores"]["OVERCLAIM_RESISTANCE"] == 0
        assert sv["total"] >= 150            # still a HIGH score
        status, cat = tq.quality_dominant_status(findings)
        assert status not in PASS_STATUSES
        assert cat == "OVERCLAIM"

    def test_tool_with_one_blocker_high_score_not_pass(self, gate):
        # An otherwise-clean descriptor that adds a single overclaim phrase: the
        # score stays high but the report can never PASS.
        body = gate.quality_tool_body(
            tool_description="Read-only local case search by keyword. This tool "
            "is completely safe and cannot cause harm.")
        tid = gate.register_quality_tool(body=body).json()["tool_id"]
        rep = gate.quality_check(tid, actor=OWNER).json()
        assert rep["quality_blockers"], "expected at least one blocker"
        assert rep["quality_status"] not in PASS_STATUSES
        # despite the blocker, the numeric score remains high (no total wipe).
        assert rep["quality_score_total"] > 100

    def test_dominant_status_prefers_most_dominant_blocker(self):
        findings = [
            {"code": "a", "severity": "BLOCKER", "category": "OVERCLAIM",
             "dimension": "OVERCLAIM_RESISTANCE", "detail": "d"},
            {"code": "b", "severity": "BLOCKER", "category": "POISONED",
             "dimension": "PROMPT_CONTEXT_SAFETY", "detail": "d"}]
        status, cat = tq.quality_dominant_status(findings)
        # POISONED dominates OVERCLAIM in BLOCKER_DOMINANCE.
        assert cat == "POISONED"
        assert status == "QUALITY_QUARANTINED"
