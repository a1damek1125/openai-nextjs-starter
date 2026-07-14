"""TOOL-B2 planner selection boundary.

Exercises ``build_selection_boundary`` status resolution, exposure-budget
ordering, allowed-field shrinkage, hash determinism, and the
``/quality/selection-boundary`` endpoint.
"""
from finalis.ai_employee import tool_quality as tq


def _boundary(**over):
    base = dict(tool_id="tool-1", tenant_id="tenant-1", b1_status="ADMITTED",
                b1_risk="LOW", quarantined=False,
                prompt_exposure="NAME_AND_SUMMARY", ir_mismatch=False)
    base.update(over)
    return tq.build_selection_boundary(**base)


class TestStatusResolution:
    def test_never_expose_when_quarantined(self):
        b = _boundary(quarantined=True)
        assert b["minimal_context_status"] == "NEVER_EXPOSE"
        assert b["selection_boundary_status"] == "NEVER_EXPOSE"

    def test_never_expose_when_b1_status_tampered(self):
        assert _boundary(b1_status="TAMPERED")[
            "minimal_context_status"] == "NEVER_EXPOSE"

    def test_never_expose_for_all_blocked_statuses(self):
        for st in ("QUARANTINED", "TAMPERED", "RUG_PULL_DETECTED",
                   "DRIFT_DETECTED", "FORBIDDEN_CAPABILITY",
                   "CROSS_TENANT_REJECTED"):
            assert _boundary(b1_status=st)[
                "minimal_context_status"] == "NEVER_EXPOSE", st

    def test_requires_redaction_for_ir_mismatch(self):
        b = _boundary(ir_mismatch=True)
        assert b["minimal_context_status"] == "REQUIRES_REDACTION"
        assert b["context_exposure_budget"] == 2

    def test_summary_only_for_high_risk(self):
        assert _boundary(b1_risk="HIGH")[
            "minimal_context_status"] == "SUMMARY_ONLY"

    def test_summary_only_for_critical_risk(self):
        assert _boundary(b1_risk="CRITICAL")[
            "minimal_context_status"] == "SUMMARY_ONLY"

    def test_summary_only_for_prompt_exposure_never_expose(self):
        assert _boundary(prompt_exposure="NEVER_EXPOSE")[
            "minimal_context_status"] == "SUMMARY_ONLY"

    def test_summary_only_for_prompt_exposure_name_only(self):
        assert _boundary(prompt_exposure="NAME_ONLY")[
            "minimal_context_status"] == "SUMMARY_ONLY"

    def test_minimal_for_clean_low_risk(self):
        b = _boundary()
        assert b["minimal_context_status"] == "MINIMAL"
        assert b["context_exposure_budget"] == 5

    def test_quarantine_dominates_ir_mismatch_and_risk(self):
        b = _boundary(quarantined=True, ir_mismatch=True, b1_risk="HIGH")
        assert b["minimal_context_status"] == "NEVER_EXPOSE"


class TestBudgetAndFields:
    def test_context_exposure_budget_ordering(self):
        minimal = _boundary()["context_exposure_budget"]
        summary = _boundary(b1_risk="HIGH")["context_exposure_budget"]
        redaction = _boundary(ir_mismatch=True)["context_exposure_budget"]
        never = _boundary(quarantined=True)["context_exposure_budget"]
        assert minimal > summary > redaction > never
        assert (minimal, summary, redaction, never) == (5, 3, 2, 0)

    def test_allowed_fields_shrink_as_exposure_tightens(self):
        minimal = _boundary()["allowed_descriptor_fields_for_planner"]
        summary = _boundary(b1_risk="HIGH")[
            "allowed_descriptor_fields_for_planner"]
        never = _boundary(quarantined=True)[
            "allowed_descriptor_fields_for_planner"]
        assert len(minimal) > len(summary) > len(never)
        assert never == ["tool_id"]
        # tighter exposure never grants a field a looser one withheld.
        assert set(summary) <= set(minimal)
        assert set(never) <= set(summary)

    def test_never_expose_fields_always_listed(self):
        for b in (_boundary(), _boundary(quarantined=True)):
            assert b["never_expose_fields"] == [
                "input_schema", "output_schema", "declared_provider", "aliases"]

    def test_minimal_has_no_redacted_fields(self):
        assert _boundary()["redacted_fields"] == []
        assert _boundary(b1_risk="HIGH")["redacted_fields"]


class TestHashDeterminism:
    def test_hash_deterministic_for_identical_inputs(self):
        assert _boundary()["selection_boundary_hash"] == _boundary()[
            "selection_boundary_hash"]

    def test_hash_differs_for_different_status(self):
        assert _boundary()["selection_boundary_hash"] != _boundary(
            quarantined=True)["selection_boundary_hash"]


class TestSelectionBoundaryEndpoint:
    def test_endpoint_returns_minimal_for_clean_tool(self, gate):
        tid, _ = gate.checked_quality_tool()
        r = gate.q(tid, "/selection-boundary")
        assert r.status_code == 200
        b = r.json()["planner_selection_boundary"]
        assert b["minimal_context_status"] == "MINIMAL"

    def test_endpoint_matches_stored_report_boundary(self, gate):
        tid, rep = gate.checked_quality_tool()
        b = gate.q(tid, "/selection-boundary").json()[
            "planner_selection_boundary"]
        assert b["selection_boundary_hash"] == rep[
            "planner_selection_boundary"]["selection_boundary_hash"]
