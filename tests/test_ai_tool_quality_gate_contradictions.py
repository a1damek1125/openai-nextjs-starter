"""TOOL-B2 descriptor contradiction detection.

Exercises ``tool_quality.detect_contradictions`` for each BLOCKER code plus a
clean-tool negative, and confirms the CONTRADICTION-category codes surface in an
end-to-end quality report. Kernel-level construction is used for the precise
codes so the TOOL-B1 scanner cannot mask the specific finding.
"""
from finalis.ai_employee import tool_quality as tq

from tests.conftest import OWNER


def _ir(desc, *, name="Case Lookup", summary="", b1_category="DATA_SEARCH",
        b1_side_effect="PURE_READ", b1_risk="LOW",
        b1_prompt_exposure="NAME_AND_SUMMARY"):
    """Build a real formal IR from crafted prose so detected-term sets are the
    genuine deterministic output, not a hand-rolled dict."""
    descriptor = {"tool_name": name, "tool_summary": summary,
                  "tool_description": desc, "category": b1_category}
    ir = tq.build_formal_ir(
        descriptor=descriptor, tenant_id="t", tool_id="tool",
        tool_version_id="v", source_descriptor_hash="h",
        b1_category=b1_category, b1_side_effect=b1_side_effect,
        b1_risk=b1_risk, b1_prompt_exposure=b1_prompt_exposure)
    return descriptor, ir


def _effect(**over):
    base = {"touches_external": False, "touches_payment": False,
            "touches_customer": False, "touches_evidence": False,
            "side_effect_rank": 0}
    base.update(over)
    return base


def _codes(findings):
    return {f["code"] for f in findings}


class TestReadonlyButWrites:
    def test_readonly_but_writes_via_dataflow_write(self):
        descriptor, ir = _ir("read only local record lookup by keyword")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="PURE_READ",
            b1_category="DATA_SEARCH", b1_risk="LOW", effect_contract=_effect(),
            data_flow={"reads_data_classes": ["INTERNAL"],
                       "writes_data_classes": ["INTERNAL"]}, consent={})
        assert "readonly_but_writes" in _codes(findings)

    def test_readonly_but_writes_via_side_effect_class(self):
        descriptor, ir = _ir("read-only lookup of the local ledger",
                              b1_side_effect="INTERNAL_WRITE")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="INTERNAL_WRITE",
            b1_category="DATA_SEARCH", b1_risk="LOW", effect_contract=_effect(),
            data_flow={"reads_data_classes": ["INTERNAL"],
                       "writes_data_classes": []}, consent={})
        assert "readonly_but_writes" in _codes(findings)

    def test_readonly_but_writes_via_touches_external(self):
        descriptor, ir = _ir("readonly local record lookup")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="PURE_READ",
            b1_category="DATA_SEARCH", b1_risk="LOW",
            effect_contract=_effect(touches_external=True),
            data_flow={"reads_data_classes": ["INTERNAL"],
                       "writes_data_classes": []}, consent={})
        assert "readonly_but_writes" in _codes(findings)

    def test_readonly_but_writes_category_is_contradiction(self):
        descriptor, ir = _ir("read only local record lookup")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="INTERNAL_WRITE",
            b1_category="DATA_SEARCH", b1_risk="LOW", effect_contract=_effect(),
            data_flow={"reads_data_classes": [], "writes_data_classes": []},
            consent={})
        f = [x for x in findings if x["code"] == "readonly_but_writes"][0]
        assert f["severity"] == "BLOCKER"
        assert f["category"] == "CONTRADICTION"


class TestLowRiskDangerousEffect:
    def test_low_risk_with_payment_touch(self):
        descriptor, ir = _ir("process a settlement for the client account")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="PURE_READ", b1_category="DATA_SEARCH",
            b1_risk="LOW", effect_contract=_effect(touches_payment=True),
            data_flow={"reads_data_classes": ["INTERNAL"],
                       "writes_data_classes": []}, consent={})
        assert "low_risk_dangerous_effect" in _codes(findings)

    def test_low_risk_with_secret_prose(self):
        descriptor, ir = _ir("reads the stored secret token and returns it")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="PURE_READ", b1_category="DATA_SEARCH",
            b1_risk="LOW", effect_contract=_effect(),
            data_flow={"reads_data_classes": ["CREDENTIALS"],
                       "writes_data_classes": []}, consent={})
        # secret-dataclass present so secret_prose finding is suppressed, but the
        # low-risk-with-secret-prose contradiction still fires.
        assert "low_risk_dangerous_effect" in _codes(findings)

    def test_low_risk_with_forbidden_side_effect(self):
        descriptor, ir = _ir("mutate the archived evidence entry")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="EVIDENCE_MUTATION",
            b1_category="DATA_SEARCH", b1_risk="LOW",
            effect_contract=_effect(side_effect_rank=1),
            data_flow={"reads_data_classes": ["INTERNAL"],
                       "writes_data_classes": []}, consent={})
        assert "low_risk_dangerous_effect" in _codes(findings)


class TestExternalProseNoNetwork:
    def test_external_prose_but_no_network(self):
        descriptor, ir = _ir("fetch data from an external api over the network",
                             b1_risk="MEDIUM")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="PURE_READ", b1_category="DATA_SEARCH",
            b1_risk="MEDIUM", effect_contract=_effect(touches_external=False),
            data_flow={"reads_data_classes": ["INTERNAL"],
                       "writes_data_classes": []}, consent={})
        assert "external_prose_no_network" in _codes(findings)

    def test_external_prose_ok_when_touches_external(self):
        descriptor, ir = _ir("fetch data from an external api over the network",
                             b1_risk="MEDIUM")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="EXTERNAL_READ",
            b1_category="EXTERNAL_API_READ", b1_risk="MEDIUM",
            effect_contract=_effect(touches_external=True),
            data_flow={"reads_data_classes": ["INTERNAL"],
                       "writes_data_classes": []}, consent={})
        assert "external_prose_no_network" not in _codes(findings)


class TestNoApprovalHighEffect:
    def test_high_effect_without_approval_prose(self):
        descriptor, ir = _ir("send a bulk write to the storage layer",
                             b1_risk="MEDIUM")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="EXTERNAL_WRITE",
            b1_category="EXTERNAL_API_WRITE", b1_risk="MEDIUM",
            effect_contract=_effect(side_effect_rank=3),
            data_flow={"reads_data_classes": ["INTERNAL"],
                       "writes_data_classes": ["INTERNAL"]}, consent={})
        codes = _codes(findings)
        assert "no_approval_high_effect" in codes
        f = [x for x in findings if x["code"] == "no_approval_high_effect"][0]
        assert f["severity"] == "BLOCKER"
        assert f["category"] == "SIDE_EFFECT_MISMATCH"

    def test_high_effect_with_approval_prose_ok(self):
        descriptor, ir = _ir(
            "send a bulk write to storage after approval and sign off review",
            b1_risk="MEDIUM")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="EXTERNAL_WRITE",
            b1_category="EXTERNAL_API_WRITE", b1_risk="MEDIUM",
            effect_contract=_effect(side_effect_rank=3),
            data_flow={"reads_data_classes": ["INTERNAL"],
                       "writes_data_classes": ["INTERNAL"]}, consent={})
        assert "no_approval_high_effect" not in _codes(findings)


class TestSecretProseNoSecretDataclass:
    def test_secret_prose_without_secret_dataclass(self):
        descriptor, ir = _ir("reads the account secret token from storage",
                             b1_risk="MEDIUM")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="PURE_READ", b1_category="DATA_SEARCH",
            b1_risk="MEDIUM", effect_contract=_effect(),
            data_flow={"reads_data_classes": ["INTERNAL"],
                       "writes_data_classes": []}, consent={})
        codes = _codes(findings)
        assert "secret_prose_no_secret_dataclass" in codes
        f = [x for x in findings
             if x["code"] == "secret_prose_no_secret_dataclass"][0]
        assert f["category"] == "SIDE_EFFECT_MISMATCH"

    def test_secret_prose_ok_with_credentials_dataclass(self):
        descriptor, ir = _ir("reads the account secret token from storage",
                             b1_risk="MEDIUM")
        findings = tq.detect_contradictions(
            descriptor, ir, b1_side_effect="PURE_READ", b1_category="DATA_SEARCH",
            b1_risk="MEDIUM", effect_contract=_effect(),
            data_flow={"reads_data_classes": ["CREDENTIALS"],
                       "writes_data_classes": []}, consent={})
        assert "secret_prose_no_secret_dataclass" not in _codes(findings)


class TestCleanAndEndToEnd:
    def test_clean_tool_has_no_contradictions(self, gate):
        tid = gate.register_quality_tool().json()["tool_id"]
        v = gate.latest_tool_version(tid)
        ir = tq.build_formal_ir(
            descriptor=v["descriptor"], tenant_id=v["tenant_id"],
            tool_id=v["tool_id"], tool_version_id=v["tool_version_id"],
            source_descriptor_hash=v["descriptor_hash"],
            b1_category=v["descriptor"]["category"],
            b1_side_effect=v["effect_contract"]["side_effect_class"],
            b1_risk=v["risk_class"],
            b1_prompt_exposure=v["prompt_context_policy"]["effective_exposure"])
        findings = tq.detect_contradictions(
            v["descriptor"], ir,
            b1_side_effect=v["effect_contract"]["side_effect_class"],
            b1_category=v["descriptor"]["category"], b1_risk=v["risk_class"],
            effect_contract=v["effect_contract"],
            data_flow=v["data_flow_contract"], consent=v["consent_contract"])
        assert findings == []

    def test_clean_report_has_empty_contradiction_flags(self, gate):
        _, rep = gate.checked_quality_tool()
        assert rep["contradiction_flags"] == []

    def test_readonly_but_writes_surfaces_in_report(self, gate):
        # A descriptor that still declares read-only prose while the registered
        # side-effect class writes -> the contradiction flag surfaces regardless
        # of the dominant end-to-end status.
        body = gate.quality_tool_body(
            tool_name="Ledger Sync",
            tool_description="Read-only local ledger view; returns rows. "
            "read only, no external calls.",
            side_effect_class="INTERNAL_WRITE",
            declared_side_effects=["INTERNAL_WRITE"])
        tid = gate.register_quality_tool(body=body).json()["tool_id"]
        rep = gate.quality_check(tid).json()
        assert "readonly_but_writes" in rep["contradiction_flags"]
        assert rep["quality_status"] not in ("QUALITY_PASS",
                                              "QUALITY_PASS_WITH_WARNINGS")
