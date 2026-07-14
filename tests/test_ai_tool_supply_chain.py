"""TOOL-B1 — supply-chain drift / rug-pull guard (SECURITY-CRITICAL).

supply_chain_guard compares a previously-admitted descriptor snapshot to a
proposed new version. Any change to a watched security hash is DRIFT; escalated
side-effect/risk, a newly forbidden category/capability, or a newly-tripped
scanner is a RUG_PULL — and rug-pull dominates drift. Missing new values fail
closed (treated as maximally dangerous). Endpoint tests exercise the versions,
drift-check and diff routes and the emitted rug-pull event.
"""
import pytest

from finalis.ai_employee import tool_registry as tr
from tests.conftest import gate, OWNER, MANAGER  # noqa: F401


def _snap(**o):
    kw = dict(descriptor_hash="d", effect_contract_hash="e",
              data_flow_contract_hash="f", side_effect_rank=0, risk_rank=0,
              category="DATA_READ", scanner_clean=True,
              forbidden_capability=False)
    kw.update(o)
    return kw


class TestGuardKernel:
    def test_identical_snapshot_is_stable(self):
        r = tr.supply_chain_guard(admitted_snapshot=_snap(),
                                  new_snapshot=_snap())
        assert r["verdict"] == "STABLE"
        assert not r["drift"] and not r["rug_pull"]

    def test_changed_descriptor_hash_is_drift(self):
        r = tr.supply_chain_guard(admitted_snapshot=_snap(),
                                  new_snapshot=_snap(descriptor_hash="x"))
        assert r["verdict"] == "DRIFT_DETECTED"
        assert r["drift"] and not r["rug_pull"]

    def test_changed_effect_hash_is_drift(self):
        r = tr.supply_chain_guard(admitted_snapshot=_snap(),
                                  new_snapshot=_snap(effect_contract_hash="x"))
        assert r["verdict"] == "DRIFT_DETECTED"

    def test_escalated_side_effect_is_rug_pull(self):
        r = tr.supply_chain_guard(admitted_snapshot=_snap(),
                                  new_snapshot=_snap(side_effect_rank=5))
        assert r["verdict"] == "RUG_PULL_DETECTED"

    def test_escalated_risk_is_rug_pull(self):
        r = tr.supply_chain_guard(admitted_snapshot=_snap(),
                                  new_snapshot=_snap(risk_rank=5))
        assert r["verdict"] == "RUG_PULL_DETECTED"

    def test_new_forbidden_category_is_rug_pull(self):
        r = tr.supply_chain_guard(admitted_snapshot=_snap(),
                                  new_snapshot=_snap(category="PAYMENT"))
        assert r["verdict"] == "RUG_PULL_DETECTED"

    def test_new_forbidden_capability_is_rug_pull(self):
        r = tr.supply_chain_guard(
            admitted_snapshot=_snap(),
            new_snapshot=_snap(forbidden_capability=True))
        assert r["verdict"] == "RUG_PULL_DETECTED"

    def test_newly_tripped_scanner_is_rug_pull(self):
        r = tr.supply_chain_guard(admitted_snapshot=_snap(),
                                  new_snapshot=_snap(scanner_clean=False))
        assert r["verdict"] == "RUG_PULL_DETECTED"

    def test_rug_pull_dominates_drift(self):
        r = tr.supply_chain_guard(
            admitted_snapshot=_snap(),
            new_snapshot=_snap(descriptor_hash="x", risk_rank=5))
        assert r["verdict"] == "RUG_PULL_DETECTED"
        assert r["drift"] and r["rug_pull"]

    def test_missing_new_fields_fail_closed(self):
        # A new snapshot missing rank fields is treated as maximally dangerous.
        r = tr.supply_chain_guard(
            admitted_snapshot=_snap(),
            new_snapshot={"descriptor_hash": "d", "effect_contract_hash": "e",
                          "data_flow_contract_hash": "f"})
        assert r["verdict"] == "RUG_PULL_DETECTED"
        assert r["rug_pull"]

    def test_de_escalation_is_not_rug_pull(self):
        # Lowering rank on an already-high snapshot is not an escalation.
        r = tr.supply_chain_guard(
            admitted_snapshot=_snap(side_effect_rank=5, risk_rank=3),
            new_snapshot=_snap(side_effect_rank=1, risk_rank=1))
        assert r["verdict"] == "STABLE"


class TestVersionsEndpoint:
    def test_identical_version_is_stable(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        r = gate.tool(tid, "/versions", actor=MANAGER, method="POST",
                      **gate.clean_tool_body())
        assert r.json()["supply_chain"]["verdict"] == "STABLE"

    def test_escalation_to_payment_is_rug_pull_and_emits_event(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        r = gate.tool(tid, "/versions", actor=MANAGER, method="POST",
                      **gate.clean_tool_body(category="PAYMENT",
                                             side_effect_class="PAYMENT_MOVEMENT",
                                             touches_payment=True))
        assert r.json()["supply_chain"]["verdict"] == "RUG_PULL_DETECTED"
        assert r.json()["tool_version"]["status"] == "RUG_PULL_DETECTED"
        evs = gate.c.get("/ai-tools/registry/events",
                         headers=gate.h(OWNER)).json()["events"]
        assert any(e["event_type"] == "TOOL_RUG_PULL_DETECTED" for e in evs)

    def test_description_change_is_drift_and_emits_event(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        r = gate.tool(tid, "/versions", actor=MANAGER, method="POST",
                      **gate.clean_tool_body(
                          tool_description="a different safe read only note"))
        assert r.json()["supply_chain"]["verdict"] == "DRIFT_DETECTED"
        evs = gate.c.get("/ai-tools/registry/events",
                         headers=gate.h(OWNER)).json()["events"]
        assert any(e["event_type"] == "TOOL_DRIFT_DETECTED" for e in evs)


class TestDriftCheckEndpoint:
    def test_self_compare_is_stable(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        r = gate.tool(tid, "/drift-check", actor=OWNER, method="POST")
        assert r.json()["supply_chain"]["verdict"] == "STABLE"

    def test_proposed_escalation_is_rug_pull(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        r = gate.tool(tid, "/drift-check", actor=OWNER, method="POST",
                      proposed_descriptor=gate.clean_tool_body(
                          category="PAYMENT",
                          side_effect_class="PAYMENT_MOVEMENT",
                          touches_payment=True))
        assert r.json()["supply_chain"]["verdict"] == "RUG_PULL_DETECTED"

    def test_proposed_description_change_is_drift(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        r = gate.tool(tid, "/drift-check", actor=OWNER, method="POST",
                      proposed_descriptor=gate.clean_tool_body(
                          tool_description="another safe read only phrasing"))
        assert r.json()["supply_chain"]["verdict"] == "DRIFT_DETECTED"


class TestDiffEndpoint:
    def test_diff_shows_changed_fields(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        gate.tool(tid, "/versions", actor=MANAGER, method="POST",
                  **gate.clean_tool_body(category="PAYMENT",
                                         side_effect_class="PAYMENT_MOVEMENT",
                                         touches_payment=True))
        vs = gate.c.get(f"/ai-tools/{tid}/versions",
                        headers=gate.h(OWNER)).json()["versions"]
        r = gate.tool(tid, "/diff", actor=OWNER, method="POST",
                      from_version_id=vs[0]["tool_version_id"],
                      to_version_id=vs[-1]["tool_version_id"])
        j = r.json()
        assert not j["identical"]
        assert "risk_class" in j["changed_fields"]
        assert "effect_contract_hash" in j["changed_fields"]

    def test_diff_identical_descriptor_content_unchanged(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        gate.tool(tid, "/versions", actor=MANAGER, method="POST",
                  **gate.clean_tool_body())
        vs = gate.c.get(f"/ai-tools/{tid}/versions",
                        headers=gate.h(OWNER)).json()["versions"]
        # v1 and v2 have byte-identical descriptor CONTENT, so content hashes do
        # not change; only tbom_hash differs (it binds the per-version id).
        r = gate.tool(tid, "/diff", actor=OWNER, method="POST",
                      from_version_id=vs[0]["tool_version_id"],
                      to_version_id=vs[1]["tool_version_id"])
        changed = r.json()["changed_fields"]
        assert "descriptor_hash" not in changed
        assert "effect_contract_hash" not in changed
        assert "data_flow_contract_hash" not in changed
        assert "risk_class" not in changed
