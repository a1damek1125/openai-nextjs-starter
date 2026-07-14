"""TOOL-B3 schema closure gate (tc.build_schema_closure).

A clean closed input/output schema is MATCHED; an object schema with no
declared properties, or unrestricted additionalProperties on a MEDIUM+-risk
schema, is an open-world hazard flagged NEEDS_REVIEW. The contract carries the
schema_closure sub-object; its hash is deterministic.
"""
import pytest

from finalis.ai_employee import tool_contracts as tc

CLEAN_ENV = {
    "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
    "output_schema": {"type": "object",
                      "properties": {"rows": {"type": "array"}}},
}


def closure(env, risk="LOW"):
    return tc.build_schema_closure(tenant_id="t", contract_id="c", tool_id="x",
                                   schema_envelope=env, risk_class=risk)


class TestSchemaClosureUnit:
    def test_clean_closed_schema_matched(self):
        g = closure(CLEAN_ENV)
        assert g["schema_closure_status"] == "MATCHED"
        assert g["input_schema_closed"] is True
        assert g["output_schema_closed"] is True
        assert g["open_world_fields"] == []

    def test_object_without_properties_needs_review(self):
        g = closure({"input_schema": {"type": "object"},
                     "output_schema": CLEAN_ENV["output_schema"]})
        assert g["schema_closure_status"] == "NEEDS_REVIEW"
        assert g["input_schema_closed"] is False
        assert any("no properties" in f for f in g["open_world_fields"])

    def test_high_risk_additional_properties_needs_review(self):
        env = {"input_schema": {"type": "object", "additionalProperties": True,
                                "properties": {"q": {"type": "string"}}},
               "output_schema": CLEAN_ENV["output_schema"]}
        g = closure(env, risk="HIGH")
        assert g["schema_closure_status"] == "NEEDS_REVIEW"
        assert any("additionalProperties" in f for f in g["open_world_fields"])

    def test_medium_risk_additional_properties_needs_review(self):
        env = {"input_schema": {"type": "object", "additionalProperties": True,
                                "properties": {"q": {"type": "string"}}},
               "output_schema": CLEAN_ENV["output_schema"]}
        assert closure(env, risk="MEDIUM")["schema_closure_status"] == \
            "NEEDS_REVIEW"

    def test_low_risk_additional_properties_is_tolerated(self):
        # additionalProperties is only an open-world hazard at MEDIUM+ risk.
        env = {"input_schema": {"type": "object", "additionalProperties": True,
                                "properties": {"q": {"type": "string"}}},
               "output_schema": CLEAN_ENV["output_schema"]}
        assert closure(env, risk="LOW")["schema_closure_status"] == "MATCHED"

    def test_empty_schema_not_closed(self):
        g = closure({"input_schema": {}, "output_schema": {}})
        assert g["input_schema_closed"] is False
        assert g["output_schema_closed"] is False
        assert g["schema_closure_status"] == "NEEDS_REVIEW"

    def test_output_schema_open_world_flagged(self):
        g = closure({"input_schema": CLEAN_ENV["input_schema"],
                     "output_schema": {"type": "object"}}, risk="HIGH")
        assert g["output_schema_closed"] is False
        assert g["schema_closure_status"] == "NEEDS_REVIEW"

    def test_hash_deterministic(self):
        assert closure(CLEAN_ENV)["schema_closure_hash"] == \
            closure(CLEAN_ENV)["schema_closure_hash"]

    def test_hash_changes_with_status(self):
        clean = closure(CLEAN_ENV)["schema_closure_hash"]
        open_world = closure({"input_schema": {"type": "object"},
                              "output_schema": CLEAN_ENV["output_schema"]})[
            "schema_closure_hash"]
        assert clean != open_world


class TestSchemaClosureOnContract:
    def test_clean_contract_carries_matched_closure(self, gate):
        tid, c = gate.contracted_tool()
        sc = c["schema_closure"]
        assert sc["schema_closure_status"] == "MATCHED"
        assert sc["input_schema_closed"] is True

    def test_object_no_properties_contract_needs_review(self, gate):
        # An object input schema with no properties trips the closure gate on
        # the stored contract, independent of the overall contract status.
        tid = gate.contract_tool(input_schema={"type": "object"})
        c = gate.create_contract(tid).json()
        sc = c["schema_closure"]
        assert sc["schema_closure_status"] == "NEEDS_REVIEW"
        assert sc["input_schema_closed"] is False
        assert sc["open_world_fields"]

    def test_contract_closure_hash_matches_recompute(self, gate):
        tid, c = gate.contracted_tool()
        sc = c["schema_closure"]
        assert sc["schema_closure_hash"] == tc._core_hash(
            sc, "schema_closure_hash")
