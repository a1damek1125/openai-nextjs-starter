"""TOOL-B2 metamorphic testing tests.

Metamorphic testing asserts that an equivalent dangerous intent stays detected
under transformation: a transform must never make a detected-dangerous phrase
'safe'. All relations are deterministic (no LLM). These tests assert ACTUAL
behavior and modify no product file.
"""
import pytest

from tests.conftest import OWNER
from finalis.ai_employee import tool_quality as tq

EXPECTED_RELATIONS = {
    "case_invariance", "whitespace_invariance", "politeness_invariance",
    "leet_invariance", "synonym_invariance", "broker_invariance",
    "secret_invariance", "downgrade_invariance", "injection_invariance",
    "prefer_invariance",
}


class TestMetamorphicKernel:
    def test_status_passed(self):
        mm = tq.metamorphic_testing(tool_id="t1", tenant_id="demo")
        assert mm["metamorphic_status"] == "PASSED"
        assert mm["metamorphic_failures"] == []

    def test_all_relations_present(self):
        mm = tq.metamorphic_testing(tool_id="t1", tenant_id="demo")
        relations = {c["relation"] for c in mm["metamorphic_cases"]}
        assert relations == EXPECTED_RELATIONS

    def test_every_case_held(self):
        mm = tq.metamorphic_testing(tool_id="t1", tenant_id="demo")
        for c in mm["metamorphic_cases"]:
            assert c["held"], c["relation"]

    def test_case_transform_detected(self):
        mm = tq.metamorphic_testing(tool_id="t1", tenant_id="demo")
        c = next(c for c in mm["metamorphic_cases"]
                 if c["relation"] == "case_invariance")
        assert c["base_detected"] and c["transformed_detected"]
        assert c["held"]

    def test_whitespace_transform_detected(self):
        mm = tq.metamorphic_testing(tool_id="t1", tenant_id="demo")
        c = next(c for c in mm["metamorphic_cases"]
                 if c["relation"] == "whitespace_invariance")
        assert c["base_detected"] and c["transformed_detected"]

    def test_politeness_transform_detected(self):
        mm = tq.metamorphic_testing(tool_id="t1", tenant_id="demo")
        c = next(c for c in mm["metamorphic_cases"]
                 if c["relation"] == "politeness_invariance")
        assert c["base_detected"] and c["transformed_detected"]

    def test_leet_transform_detected(self):
        mm = tq.metamorphic_testing(tool_id="t1", tenant_id="demo")
        c = next(c for c in mm["metamorphic_cases"]
                 if c["relation"] == "leet_invariance")
        assert c["base_detected"] and c["transformed_detected"]

    def test_downgrade_transform_detected(self):
        mm = tq.metamorphic_testing(tool_id="t1", tenant_id="demo")
        c = next(c for c in mm["metamorphic_cases"]
                 if c["relation"] == "downgrade_invariance")
        assert c["base_detected"] and c["transformed_detected"]

    def test_homoglyph_dangerous_phrase_stays_detected(self):
        # Not a named metamorphic relation, but the same invariance property:
        # a homoglyph transform of a dangerous phrase must stay detected once
        # the normalizer folds the look-alike glyphs back to latin.
        base = "bypass approval"
        homo = base.replace("a", "а").replace("o", "о")
        # The normalizer folds the homoglyphs so the phrase still matches the
        # execution/broker-claim table (the same detection the harness uses).
        assert tq._has_phrase(tq._blob(homo), tq._EXECUTION_CLAIM)

    def test_secret_relation_holds_when_base_undetected(self):
        # The 'read secret' base is not itself in the persuasion/injection
        # tables; when the base is undetected the relation holds vacuously.
        mm = tq.metamorphic_testing(tool_id="t1", tenant_id="demo")
        c = next(c for c in mm["metamorphic_cases"]
                 if c["relation"] == "secret_invariance")
        assert c["held"]

    def test_deterministic_hash(self):
        a = tq.metamorphic_testing(tool_id="t1", tenant_id="demo")
        b = tq.metamorphic_testing(tool_id="t1", tenant_id="demo")
        assert a == b
        assert a["metamorphic_test_hash"] == b["metamorphic_test_hash"]

    def test_hash_binds_identity(self):
        a = tq.metamorphic_testing(tool_id="t1", tenant_id="demo")
        b = tq.metamorphic_testing(tool_id="other", tenant_id="demo")
        assert a["metamorphic_test_hash"] != b["metamorphic_test_hash"]

    def test_hash_stable_across_many_calls(self):
        hashes = {tq.metamorphic_testing(tool_id="t1", tenant_id="demo")[
            "metamorphic_test_hash"] for _ in range(5)}
        assert len(hashes) == 1


class TestReportMetamorphicSummary:
    def test_report_carries_metamorphic_summary(self, gate):
        _, rep = gate.checked_quality_tool()
        summ = rep["metamorphic_test_summary"]
        assert summ["status"] == "PASSED"
        assert summ["failures"] == []

    def test_report_metamorphic_hash_matches_kernel(self, gate):
        _, rep = gate.checked_quality_tool()
        expected = tq.metamorphic_testing(
            tool_id=rep["tool_id"], tenant_id=rep["tenant_id"])[
            "metamorphic_test_hash"]
        assert rep["metamorphic_test_hash"] == expected

    def test_metamorphic_safety_dimension_scored_full(self, gate):
        _, rep = gate.checked_quality_tool()
        # PASSED metamorphic keeps the METAMORPHIC_SAFETY dimension at full.
        assert rep["quality_score_vector"]["METAMORPHIC_SAFETY"] == 5
