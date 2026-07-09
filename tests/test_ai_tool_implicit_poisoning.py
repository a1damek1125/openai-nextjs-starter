"""TOOL-B1 — implicit (cross-field) poisoning detector (SECURITY-CRITICAL).

detect_implicit_poisoning cross-checks DECLARED fields against each other to
find capability that no single-field scanner would catch: a PURE_READ that
writes/egresses, a description implying send/pay/delete the effect contract
does not declare, sensitive data with no consent, a sensitive param marked
PUBLIC, and a benign category with a dangerous effect. Each finding pushes a
registered tool to NEEDS_REVIEW (or worse) and out of clean admission.
"""
import pytest

from finalis.ai_employee import tool_registry as tr
from tests.conftest import gate, OWNER, MANAGER  # noqa: F401


def _ec(**o):
    kw = dict(side_effect_class="PURE_READ", reversibility="REVERSIBLE",
              idempotent=True, blast_radius="SELF", touches_external=False,
              touches_customer=False, touches_payment=False, touches_crm=False,
              touches_evidence=False)
    kw.update(o)
    return tr.build_effect_contract(**kw)


def _df(**o):
    kw = dict(reads_data_classes=[], writes_data_classes=[], egress_targets=[],
              ingress_sources=[], crosses_tenant_boundary=False,
              retains_data=False)
    kw.update(o)
    return tr.build_data_flow_contract(**kw)


def _se(parameters=None):
    return tr.build_schema_envelope(input_schema={}, output_schema={},
                                    parameters=parameters or [])


def _pc():
    return tr.build_purpose_contract(allowed_purposes=["CASE_TRIAGE"])


def _cc(req="NONE"):
    return tr.build_consent_contract(consent_requirement=req,
                                     non_overridable=False)


def _detect(**over):
    kw = dict(category="DATA_READ", effect_contract=_ec(), data_flow=_df(),
              schema_envelope=_se(), purpose_contract=_pc(),
              consent_contract=_cc(), tool_description="reads things")
    kw.update(over)
    return [f["code"] for f in tr.detect_implicit_poisoning(**kw)]


class TestEachImplicitCode:
    def test_read_declared_but_writes(self):
        codes = _detect(data_flow=_df(writes_data_classes=["INTERNAL"]))
        assert "read_declared_but_writes" in codes

    def test_read_declared_but_egresses(self):
        codes = _detect(data_flow=_df(egress_targets=["http://x"]))
        assert "read_declared_but_writes" in codes

    def test_undeclared_capability_in_description(self):
        codes = _detect(tool_description="this will send email to the user")
        assert "undeclared_capability_in_description" in codes

    def test_undeclared_delete_capability(self):
        codes = _detect(tool_description="will delete the record")
        assert "undeclared_capability_in_description" in codes

    def test_sensitive_data_without_consent(self):
        codes = _detect(data_flow=_df(reads_data_classes=["PII"]),
                        consent_contract=_cc("NONE"))
        assert "sensitive_data_without_consent" in codes

    def test_sensitive_param_marked_public(self):
        codes = _detect(schema_envelope=_se(parameters=[
            {"name": "token", "sensitive": True, "data_class": "PUBLIC"}]))
        assert "sensitive_param_marked_public" in codes

    def test_benign_category_dangerous_effect(self):
        codes = _detect(category="DATA_READ",
                        effect_contract=_ec(side_effect_class="EXTERNAL_WRITE"))
        assert "benign_category_dangerous_effect" in codes


class TestNegatives:
    def test_clean_descriptor_yields_no_findings(self):
        assert _detect(category="DATA_SEARCH",
                       data_flow=_df(reads_data_classes=["INTERNAL"]),
                       tool_description="read only local case search") == []

    def test_sensitive_data_with_consent_not_flagged(self):
        codes = _detect(data_flow=_df(reads_data_classes=["PII"]),
                        consent_contract=_cc("EXPLICIT_REQUIRED"))
        assert "sensitive_data_without_consent" not in codes

    def test_declared_send_not_flagged(self):
        # Description says send AND the effect contract declares touches_customer.
        codes = _detect(tool_description="will send updates",
                        effect_contract=_ec(touches_customer=True))
        assert "undeclared_capability_in_description" not in codes


class TestImplicitViaEndpoint:
    def test_implicit_pushes_registered_tool_to_needs_review(self, gate):
        r = gate.register_tool(category="DATA_SEARCH",
                               tool_description="this will send email to user")
        j = r.json()
        assert j["status"] == "NEEDS_REVIEW"
        assert not j["admitted"]

    def test_findings_recorded_on_version(self, gate):
        r = gate.register_tool(category="DATA_SEARCH",
                               tool_description="this will send email to user")
        lv = gate.latest_tool_version(r.json()["tool_id"])
        codes = [f["code"] for f in lv["implicit_findings"]]
        assert "undeclared_capability_in_description" in codes

    def test_admission_not_clean_with_implicit(self, gate):
        tid = gate.register_tool(
            category="DATA_SEARCH",
            tool_description="this will send email to user").json()["tool_id"]
        r = gate.admit_tool(tid, actor=OWNER)
        assert r.json()["admitted"] is False
        assert "NEEDS_REVIEW" in r.json()["hard_fail_signals"]

    def test_clean_tool_has_no_implicit_findings(self, gate):
        r = gate.register_tool()
        lv = gate.latest_tool_version(r.json()["tool_id"])
        assert lv["implicit_findings"] == []
