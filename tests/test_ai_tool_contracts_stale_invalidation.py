"""TOOL-B3 staleness / invalidation / verify.

A fresh contract is not stale. Adding a new TOOL-B1 version drifts the source
descriptor + admission + freshness epoch, so invalidate-check reports stale
with reasons and flips the stored contract to STALE; a project after drift is
STALE (never PROJECTABLE); verify reports MATCHED when fresh, STALE on drift,
and MISMATCHED when a stored sub-object is tampered.
"""
import json

import pytest

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import OWNER


def add_drift_version(gate, tid, desc):
    """Append a new TOOL-B1 version with a changed descriptor so the source
    epoch changes."""
    return gate.tool(
        tid, "/versions", actor=OWNER, method="POST",
        tool_name="Search Local Cases", category="DATA_SEARCH",
        side_effect_class="PURE_READ", tool_summary="updated summary",
        tool_description=desc, reads_data_classes=["INTERNAL"],
        allowed_purposes=["CASE_TRIAGE"], declared_side_effects=["PURE_READ"],
        consent_requirement="NONE", prompt_context_exposure="NAME_AND_SUMMARY",
        input_schema={"type": "object",
                      "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object",
                       "properties": {"rows": {"type": "array"}}},
        parameters=[{"name": "query", "type": "string", "required": True,
                     "description": "kw", "data_class": "INTERNAL"}])


DRIFT = "Read-only local case search with TOTALLY DIFFERENT updated wording now"


class TestFresh:
    def test_fresh_contract_not_stale(self, gate):
        tid, c = gate.contracted_tool()
        inv = gate.ct(tid, c["contract_id"], "/invalidate-check",
                      method="POST").json()
        assert inv["stale"] is False
        assert inv["invalidation_reasons"] == []

    def test_fresh_epoch_matches_contract(self, gate):
        tid, c = gate.contracted_tool()
        inv = gate.ct(tid, c["contract_id"], "/invalidate-check",
                      method="POST").json()
        assert inv["current_source_freshness_epoch"] == \
            inv["contract_source_freshness_epoch"]
        assert "invalidation_hash" in inv

    def test_verify_fresh_matched(self, gate):
        tid, c = gate.contracted_tool()
        ver = gate.ct(tid, c["contract_id"], "/verify", method="POST").json()
        assert ver["verification_status"] == "MATCHED"
        assert ver["tamper_detected"] is False
        assert ver["stale"] is False


class TestSourceDrift:
    def test_new_version_makes_invalidate_check_stale(self, gate):
        tid, c = gate.contracted_tool()
        assert add_drift_version(gate, tid, DRIFT).status_code == 200
        inv = gate.ct(tid, c["contract_id"], "/invalidate-check",
                      method="POST").json()
        assert inv["stale"] is True
        assert inv["invalidation_reasons"]

    def test_invalidation_reasons_name_the_source_change(self, gate):
        tid, c = gate.contracted_tool()
        add_drift_version(gate, tid, DRIFT)
        inv = gate.ct(tid, c["contract_id"], "/invalidate-check",
                      method="POST").json()
        reasons = set(inv["invalidation_reasons"])
        assert "SOURCE_DESCRIPTOR_CHANGED" in reasons
        assert "SOURCE_FRESHNESS_EPOCH_CHANGED" in reasons

    def test_invalidate_check_flips_stored_contract_to_stale(self, gate):
        tid, c = gate.contracted_tool()
        add_drift_version(gate, tid, DRIFT)
        gate.ct(tid, c["contract_id"], "/invalidate-check", method="POST")
        stored = gate.ct(tid, c["contract_id"], "").json()
        assert stored["contract_status"] == "STALE"

    def test_project_after_drift_is_stale(self, gate):
        tid, c = gate.contracted_tool()
        add_drift_version(gate, tid, DRIFT)
        env = gate.project(tid, c["contract_id"]).json()
        assert env["projection_status"] == "STALE"
        assert "STALE_SOURCE" in env["projection_blockers"]

    def test_stale_projection_not_projectable(self, gate):
        tid, c = gate.contracted_tool()
        add_drift_version(gate, tid, DRIFT)
        env = gate.project(tid, c["contract_id"]).json()
        assert env["projection_status"] not in (
            "PROJECTABLE_FOR_FUTURE", "PROJECTED_SAFE_SUMMARY_ONLY")
        assert env["broker_readiness_certificate"][
            "certificate_status"] != "READY_FOR_FUTURE_BROKER_CONSIDERATION"

    def test_verify_after_drift_reports_stale(self, gate):
        # verify BEFORE any invalidate-check so the stored payload is untouched:
        # tamper hashing must still MATCH; only the source is stale.
        tid, c = gate.contracted_tool()
        add_drift_version(gate, tid, DRIFT)
        ver = gate.ct(tid, c["contract_id"], "/verify", method="POST").json()
        assert ver["stale"] is True
        assert ver["verification_status"] == "STALE"
        assert ver["tamper_detected"] is False


class TestTamperVsStale:
    def test_tampered_subobject_is_mismatched(self, gate):
        tid, c = gate.contracted_tool()
        cid = c["contract_id"]
        row = gate.db.one(
            "SELECT payload_json FROM ai_tool_contracts WHERE id=?", cid)
        p = json.loads(row["payload_json"])
        # Silently inject a forbidden effect into a stored sub-object.
        p["effect_trace_semantics"]["allowed_effects"] = [
            "NO_EFFECT", "PAYMENT_RELATED_EFFECT"]
        gate.db.conn.execute(
            "UPDATE ai_tool_contracts SET payload_json=? WHERE id=?",
            (json.dumps(p), cid))
        gate.db.conn.commit()
        ver = gate.ct(tid, cid, "/verify", method="POST").json()
        assert ver["verification_status"] == "MISMATCHED"
        assert ver["tamper_detected"] is True
        assert any("effect_trace_semantics" in r for r in ver["tamper_reasons"])


class TestInvalidationKernel:
    def test_kernel_fresh_contract_not_stale(self, gate):
        tid, c = gate.contracted_tool()
        head = gate.tool(tid, "").json()
        quality = gate.quality_check(tid).json()
        inv = tc.invalidation_check(contract=c, head=head,
                                    quality_report=quality)
        assert inv["stale"] is False
        assert inv["new_status"] == c["contract_status"]

    def test_kernel_reports_stale_when_epoch_mismatch(self, gate):
        tid, c = gate.contracted_tool()
        head = gate.tool(tid, "").json()
        quality = gate.quality_check(tid).json()
        forged = dict(c)
        forged["source_freshness_epoch"] = "deadbeef"
        inv = tc.invalidation_check(contract=forged, head=head,
                                    quality_report=quality)
        assert inv["stale"] is True
        assert "SOURCE_FRESHNESS_EPOCH_CHANGED" in inv["invalidation_reasons"]
        assert inv["new_status"] == "STALE"
