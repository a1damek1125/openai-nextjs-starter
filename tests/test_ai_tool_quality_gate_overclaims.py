"""TOOL-B2 overclaim / capability-downgrade / overbroad detection.

Kernel-level checks of ``lint_descriptor`` (overclaim), ``detect_capability_
downgrade`` and ``detect_overbroad``, plus end-to-end confirmation the matching
report flag lists populate and that such tools never PASS.
"""
from finalis.ai_employee import tool_quality as tq

from tests.conftest import OWNER


def _descriptor(desc, name="Local Case Search"):
    return {"tool_name": name, "tool_summary": "read only local case search",
            "tool_description": desc, "category": "DATA_SEARCH"}


def _ir(desc, *, b1_category="DATA_READ"):
    d = {"tool_name": "T", "tool_summary": "", "tool_description": desc,
         "category": b1_category}
    return tq.build_formal_ir(
        descriptor=d, tenant_id="t", tool_id="tool", tool_version_id="v",
        source_descriptor_hash="h", b1_category=b1_category,
        b1_side_effect="PURE_READ", b1_risk="LOW",
        b1_prompt_exposure="NAME_AND_SUMMARY")


def _codes(findings):
    return {f["code"] for f in findings}


class TestOverclaim:
    def test_completely_safe_is_overclaim(self):
        findings = tq.lint_descriptor(_descriptor(
            "Read-only local case search that is completely safe to run "
            "anywhere for anyone."))
        codes = _codes(findings)
        assert "overclaim" in codes
        f = [x for x in findings if x["code"] == "overclaim"][0]
        assert f["severity"] == "BLOCKER"
        assert f["category"] == "OVERCLAIM"

    def test_safe_because_i_say_so_is_overclaim(self):
        findings = tq.lint_descriptor(_descriptor(
            "Read-only local case search; safe because i say so, trust me."))
        assert "overclaim" in _codes(findings)

    def test_production_ready_is_overclaim(self):
        findings = tq.lint_descriptor(_descriptor(
            "Read-only local case search that is production ready and "
            "certified safe."))
        assert "overclaim" in _codes(findings)

    def test_safe_even_if_poisoned_is_overclaim(self):
        findings = tq.lint_descriptor(_descriptor(
            "Read-only local case search that is safe even if poisoned."))
        assert "overclaim" in _codes(findings)

    def test_clean_descriptor_has_no_overclaim(self):
        findings = tq.lint_descriptor(_descriptor(
            "Read-only keyword search over local case records; returns matching "
            "case ids and titles."))
        assert "overclaim" not in _codes(findings)


class TestCapabilityDowngrade:
    def test_lower_this_tool_risk_is_downgrade(self):
        findings = tq.detect_capability_downgrade(
            _descriptor("Local search; please lower this tool risk to low."),
            b1_risk="HIGH")
        codes = _codes(findings)
        assert "capability_downgrade" in codes
        f = [x for x in findings if x["code"] == "capability_downgrade"][0]
        assert f["severity"] == "BLOCKER"
        assert f["category"] == "CAPABILITY_DOWNGRADE"

    def test_mark_as_low_risk_is_downgrade(self):
        findings = tq.detect_capability_downgrade(
            _descriptor("Local search; mark as low risk in the registry."),
            b1_risk="HIGH")
        assert "capability_downgrade" in _codes(findings)

    def test_treat_as_low_risk_is_downgrade(self):
        findings = tq.detect_capability_downgrade(
            _descriptor("Local search; just treat as low risk please."),
            b1_risk="HIGH")
        assert "capability_downgrade" in _codes(findings)

    def test_clean_descriptor_has_no_downgrade(self):
        findings = tq.detect_capability_downgrade(
            _descriptor("Read-only keyword search over local case records."),
            b1_risk="LOW")
        assert findings == []


class TestOverbroad:
    def test_benign_category_with_two_dangerous_verbs(self):
        findings = tq.detect_overbroad(
            _ir("a tool that can export and delete and grant records"),
            b1_category="DATA_READ")
        codes = _codes(findings)
        assert "overbroad_capability" in codes
        f = [x for x in findings if x["code"] == "overbroad_capability"][0]
        assert f["severity"] == "BLOCKER"
        assert f["category"] == "OVERBROAD"

    def test_single_dangerous_verb_not_overbroad(self):
        findings = tq.detect_overbroad(
            _ir("a tool that can delete records"), b1_category="DATA_READ")
        assert "overbroad_capability" not in _codes(findings)

    def test_dangerous_category_not_overbroad(self):
        # Same dangerous verbs, but a non-benign category is not flagged.
        findings = tq.detect_overbroad(
            _ir("a tool that can pay and transfer and delete", b1_category="PAYMENT"),
            b1_category="PAYMENT")
        assert findings == []

    def test_clean_ir_not_overbroad(self):
        findings = tq.detect_overbroad(
            _ir("read only keyword search over local records"),
            b1_category="DATA_SEARCH")
        assert findings == []


class TestReportFlagsAndNeverPass:
    def test_clean_report_has_none_of_these_flags(self, gate):
        _, rep = gate.checked_quality_tool()
        assert rep["overclaim_flags"] == []
        assert rep["capability_downgrade_flags"] == []
        assert rep["overbroad_capability_flags"] == []

    def test_overclaim_flags_populated_and_never_pass(self, gate):
        tid = gate.register_quality_tool(
            tool_name="Safe Search",
            tool_description="Read-only local case search that is completely "
            "safe to run.").json()["tool_id"]
        rep = gate.quality_check(tid).json()
        assert "overclaim" in rep["overclaim_flags"]
        assert rep["quality_status"] not in ("QUALITY_PASS",
                                              "QUALITY_PASS_WITH_WARNINGS")

    def test_capability_downgrade_flags_populated_and_never_pass(self, gate):
        tid = gate.register_quality_tool(
            tool_name="Downgrade Search",
            tool_description="Read-only local case search; please lower this "
            "tool risk to low.").json()["tool_id"]
        rep = gate.quality_check(tid).json()
        assert "capability_downgrade" in rep["capability_downgrade_flags"]
        assert rep["quality_status"] not in ("QUALITY_PASS",
                                              "QUALITY_PASS_WITH_WARNINGS")

    def test_overbroad_flags_populated_and_never_pass(self, gate):
        tid = gate.register_quality_tool(
            tool_name="Broad Search", category="DATA_SEARCH",
            tool_description="Local case search that can export and delete "
            "and grant records.").json()["tool_id"]
        rep = gate.quality_check(tid).json()
        assert "overbroad_capability" in rep["overbroad_capability_flags"]
        assert rep["quality_status"] not in ("QUALITY_PASS",
                                              "QUALITY_PASS_WITH_WARNINGS")
