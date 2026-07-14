"""TOOL-B1 — data-flow contract (pure kernel + endpoint).

build_data_flow_contract flags exfiltration hazards from a DECLARED data flow:
egress of any EGRESS_FORBIDDEN_DATA class, or a tenant-boundary crossing. Tests
cover the hazard truth table, egress_forbidden_data_flagged content, determinism,
and — via the endpoint — a tool declaring egress of credentials showing
exfiltration_hazard in its data_flow_contract plus elevated (CRITICAL) risk.
"""
from finalis.ai_employee import tool_registry as tr
from tests.conftest import gate, OWNER  # noqa: F401


def _df(**over):
    kw = dict(reads_data_classes=["INTERNAL"], writes_data_classes=[],
              egress_targets=[], ingress_sources=[],
              crosses_tenant_boundary=False, retains_data=False)
    kw.update(over)
    return tr.build_data_flow_contract(**kw)


class TestExfiltrationHazard:
    def test_credentials_egress_is_hazard(self):
        c = _df(reads_data_classes=["CREDENTIALS"], egress_targets=["http://x"])
        assert c["exfiltration_hazard"] is True
        assert c["egress_forbidden_data_flagged"] == ["CREDENTIALS"]

    def test_secret_egress_is_hazard(self):
        c = _df(reads_data_classes=["SECRET"], egress_targets=["http://x"])
        assert c["exfiltration_hazard"] is True
        assert "SECRET" in c["egress_forbidden_data_flagged"]

    def test_payment_data_write_egress_is_hazard(self):
        c = _df(writes_data_classes=["PAYMENT_DATA"],
                egress_targets=["queue://out"])
        assert c["exfiltration_hazard"] is True
        assert "PAYMENT_DATA" in c["egress_forbidden_data_flagged"]

    def test_internal_only_no_egress_is_safe(self):
        c = _df(reads_data_classes=["INTERNAL"], egress_targets=[])
        assert c["exfiltration_hazard"] is False
        assert c["egress_forbidden_data_flagged"] == []

    def test_forbidden_class_without_egress_not_flagged(self):
        # No egress target => nothing leaves => no flag even for CREDENTIALS.
        c = _df(reads_data_classes=["CREDENTIALS"], egress_targets=[])
        assert c["egress_forbidden_data_flagged"] == []
        assert c["exfiltration_hazard"] is False

    def test_non_forbidden_class_egress_not_hazard(self):
        c = _df(reads_data_classes=["INTERNAL", "PUBLIC"],
                egress_targets=["http://x"])
        assert c["exfiltration_hazard"] is False
        assert c["egress_forbidden_data_flagged"] == []

    def test_crosses_tenant_boundary_sets_hazard(self):
        c = _df(reads_data_classes=["INTERNAL"], crosses_tenant_boundary=True)
        assert c["exfiltration_hazard"] is True
        # No egress-forbidden data class leaves, so that list stays empty.
        assert c["egress_forbidden_data_flagged"] == []

    def test_multiple_forbidden_classes_sorted(self):
        c = _df(reads_data_classes=["SECRET", "CREDENTIALS"],
                writes_data_classes=["EVIDENCE"],
                egress_targets=["http://x"])
        assert c["egress_forbidden_data_flagged"] == [
            "CREDENTIALS", "EVIDENCE", "SECRET"]
        assert c["exfiltration_hazard"] is True


class TestNormalizationAndDeterminism:
    def test_reads_writes_egress_sorted_deduped(self):
        c = _df(reads_data_classes=["PUBLIC", "INTERNAL", "PUBLIC"],
                writes_data_classes=["INTERNAL"],
                egress_targets=["b", "a", "a"])
        assert c["reads_data_classes"] == ["INTERNAL", "PUBLIC"]
        assert c["writes_data_classes"] == ["INTERNAL"]
        assert c["egress_targets"] == ["a", "b"]

    def test_same_input_same_hash(self):
        assert _df()["data_flow_contract_hash"] \
            == _df()["data_flow_contract_hash"]

    def test_hash_recomputes_via_core_hash(self):
        c = _df()
        assert tr._core_hash(c, "data_flow_contract_hash") \
            == c["data_flow_contract_hash"]

    def test_changing_egress_changes_hash(self):
        assert _df(egress_targets=[])["data_flow_contract_hash"] \
            != _df(egress_targets=["http://x"])["data_flow_contract_hash"]

    def test_crosses_tenant_flag_changes_hash(self):
        assert _df(crosses_tenant_boundary=False)["data_flow_contract_hash"] \
            != _df(crosses_tenant_boundary=True)["data_flow_contract_hash"]

    def test_version_string_present(self):
        assert _df()["data_flow_contract_version"] \
            == tr.DATA_FLOW_CONTRACT_VERSION


class TestEndpoint:
    def test_credentials_egress_flags_hazard_and_critical_risk(self, gate):
        body = gate.clean_tool_body(
            side_effect_class="EXTERNAL_READ",
            reads_data_classes=["CREDENTIALS"],
            egress_targets=["http://exfil.example"])
        r = gate.register_tool(body=body)
        assert r.status_code == 200
        tool_id = r.json()["tool_id"]
        lv = gate.latest_tool_version(tool_id)
        dfc = lv["data_flow_contract"]
        assert dfc["exfiltration_hazard"] is True
        assert "CREDENTIALS" in dfc["egress_forbidden_data_flagged"]
        # Exfiltration hazard elevates risk to CRITICAL in compute_risk_class.
        assert lv["risk_class"] == "CRITICAL"
        risk = gate.tool(tool_id, "/risk", actor=OWNER).json()
        assert risk["risk_class"] == "CRITICAL"

    def test_clean_read_tool_no_hazard(self, gate):
        r = gate.register_tool()
        tool_id = r.json()["tool_id"]
        dfc = gate.latest_tool_version(tool_id)["data_flow_contract"]
        assert dfc["exfiltration_hazard"] is False
        assert dfc["egress_forbidden_data_flagged"] == []

    def test_data_flow_hash_verifies_on_registered_tool(self, gate):
        r = gate.register_tool()
        tool_id = r.json()["tool_id"]
        dfc = gate.latest_tool_version(tool_id)["data_flow_contract"]
        assert tr._core_hash(dfc, "data_flow_contract_hash") \
            == dfc["data_flow_contract_hash"]
