"""TOOL-B2 counterfactual planner simulation.

A deterministic keyword planner is simulated over 8 canonical tasks. If a
descriptor's prose invites selection for a dangerous task whose safe home is
NOT the tool's declared category, misrouting is detected. A benign read tool is
never misrouted. No LLM is called (calls_llm is always False).
"""
import pytest

from finalis.ai_employee import tool_quality as tq
from tests.conftest import Gate, OWNER

CANONICAL_TASKS = [
    "read_only_information_request", "customer_message_request",
    "payment_request", "evidence_rewrite_request", "admin_permission_request",
    "external_api_request", "secret_read_request", "data_export_request",
]


def _ir(**over):
    """A minimal IR shell with all detector fields empty unless overridden."""
    base = {
        "detected_customer_visible_terms": [], "detected_side_effect_terms": [],
        "detected_payment_terms": [], "detected_evidence_terms": [],
        "detected_admin_terms": [], "detected_secret_terms": [],
        "detected_action_verbs": [], "detected_externality_terms": [],
    }
    base.update(over)
    return base


def _sim(ir, category="DATA_SEARCH", side_effect="PURE_READ"):
    return tq.counterfactual_planner_simulation(
        tool_id="t", tenant_id="T", category=category, ir=ir,
        b1_side_effect=side_effect)


class TestCanonicalTasks:
    def test_eight_canonical_tasks_present(self):
        cf = _sim(_ir())
        tasks = [t["task"] for t in cf["counterfactual_tasks"]]
        assert tasks == CANONICAL_TASKS

    def test_each_task_reports_safe_home_and_match(self):
        cf = _sim(_ir())
        for t in cf["counterfactual_tasks"]:
            assert "expected_safe_category" in t
            assert "safe_match" in t
            assert "selected_by_heuristic" in t


class TestMisroutingDetection:
    def test_clean_read_tool_not_misrouted(self):
        cf = _sim(_ir())
        assert cf["misrouting_detected"] is False
        assert cf["misrouting_reasons"] == []

    @pytest.mark.parametrize("ir_over,task", [
        ({"detected_payment_terms": ["payment"]}, "payment_request"),
        ({"detected_customer_visible_terms": ["customer"],
          "detected_side_effect_terms": ["send"]}, "customer_message_request"),
        ({"detected_evidence_terms": ["evidence"],
          "detected_side_effect_terms": ["delete"]},
         "evidence_rewrite_request"),
        ({"detected_admin_terms": ["admin"]}, "admin_permission_request"),
        ({"detected_action_verbs": ["export"]}, "data_export_request"),
        ({"detected_secret_terms": ["secret"]}, "secret_read_request"),
        ({"detected_externality_terms": ["external"]}, "external_api_request"),
    ])
    def test_dangerous_prose_on_data_search_is_misrouted(self, ir_over, task):
        cf = _sim(_ir(**ir_over), category="DATA_SEARCH")
        assert cf["misrouting_detected"] is True
        selected = {t["task"] for t in cf["counterfactual_tasks"]
                    if t["selected_by_heuristic"]}
        assert task in selected
        assert any(task in r for r in cf["misrouting_reasons"])

    def test_read_only_task_never_causes_misrouting(self):
        # read_only_information_request is always "selected" but is explicitly
        # exempt from misrouting even for a category that is not its safe home.
        cf = _sim(_ir(), category="PAYMENT", side_effect="PAYMENT_MOVEMENT")
        assert cf["misrouting_detected"] is False

    def test_payment_prose_on_payment_category_is_safe(self):
        # When the declared category IS the task's safe home, no misrouting.
        cf = _sim(_ir(detected_payment_terms=["payment"]), category="PAYMENT",
                  side_effect="PAYMENT_MOVEMENT")
        assert cf["misrouting_detected"] is False

    def test_proof_hash_deterministic(self):
        a = _sim(_ir(detected_payment_terms=["payment"]))
        b = _sim(_ir(detected_payment_terms=["payment"]))
        assert a["counterfactual_planner_proof_hash"] == b[
            "counterfactual_planner_proof_hash"]
        assert "counterfactual_planner_proof_hash" in a


class TestCounterfactualEndpoint:
    def test_endpoint_returns_proof_without_llm(self, gate):
        tid = gate.register_quality_tool(
            tool_name="Case Reader",
            tool_description="Read only local case search returns case ids and "
            "titles. No side effects.").json()["tool_id"]
        body = gate.q(tid, "/counterfactual-check", actor=OWNER,
                      method="POST").json()
        assert body["calls_llm"] is False
        cf = body["counterfactual_planner"]
        assert len(cf["counterfactual_tasks"]) == 8
        assert cf["misrouting_detected"] is False

    def test_endpoint_detects_payment_prose_on_read_tool(self, gate):
        tid = gate.register_quality_tool(
            tool_name="Case Lookup", tool_summary="look up cases",
            tool_description="Read local cases and charges customer payment for "
            "premium lookups.").json()["tool_id"]
        body = gate.q(tid, "/counterfactual-check", actor=OWNER,
                      method="POST").json()
        cf = body["counterfactual_planner"]
        assert cf["misrouting_detected"] is True
        assert body["calls_llm"] is False

    def test_report_carries_counterfactual_planner(self, gate):
        _, rep = gate.checked_quality_tool()
        cf = rep["counterfactual_planner"]
        assert [t["task"] for t in cf["counterfactual_tasks"]] == CANONICAL_TASKS
        assert cf["misrouting_detected"] is False
