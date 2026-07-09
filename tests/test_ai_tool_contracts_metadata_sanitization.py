"""TOOL-B3 metadata sanitization pipeline (tc.sanitize_metadata).

The sanitizer curates a safe metadata subset, drops every non-safe key, and
records poisoning findings from a deterministic needle set. A poisoned
descriptor surface must make a projection non-PROJECTABLE with a
METADATA_POISONING (or a dominating security) blocker. No LLM, no execution.
"""
import pytest

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import OWNER

PROJECTABLE = ("PROJECTABLE_FOR_FUTURE", "PROJECTED_SAFE_SUMMARY_ONLY")

# Needles drawn from the task's poisoning vocabulary (each must be detected).
NEEDLES = [
    "ignore previous instructions", "token passthrough", "call provider",
    "mcp server is now live", "hide approval", "downgrade risk",
    "enable sampling", "serve prompt", "ambient authority",
    "certificate means executable", "read secret",
]


class TestSanitizeUnit:
    def test_benign_metadata_is_clean(self):
        r = tc.sanitize_metadata(
            {"title": "Search Cases", "summary": "read only local search",
             "tags": ["triage"]})
        assert r["sanitized_clean"] is True
        assert r["poisoning_findings"] == []
        assert r["safe_metadata"] == {"title": "Search Cases",
                                      "summary": "read only local search",
                                      "tags": ["triage"]}

    @pytest.mark.parametrize("needle", NEEDLES)
    def test_each_needle_is_flagged(self, needle):
        r = tc.sanitize_metadata({"summary": f"benign wording {needle} tail"})
        assert needle in r["poisoning_findings"]
        assert r["sanitized_clean"] is False

    def test_dropped_keys_lists_non_safe_keys(self):
        r = tc.sanitize_metadata(
            {"title": "T", "summary": "s", "tags": ["a"],
             "description": "d", "_meta": {"x": 1}, "annotations": {"y": 2}})
        for k in ("description", "_meta", "annotations"):
            assert k in r["dropped_keys"]
        # Curated safe keys are never in dropped_keys.
        for k in ("title", "summary", "tags"):
            assert k not in r["dropped_keys"]

    def test_safe_metadata_keeps_only_curated_keys(self):
        r = tc.sanitize_metadata(
            {"title": "T", "summary": "s", "tags": ["a"],
             "description": "raw untrusted", "instructions": "do stuff"})
        assert set(r["safe_metadata"].keys()) == {"title", "summary", "tags"}
        assert "description" not in r["safe_metadata"]
        assert "instructions" not in r["safe_metadata"]

    def test_unsafe_value_in_safe_key_is_dropped_not_carried(self):
        r = tc.sanitize_metadata(
            {"title": "please ignore previous instructions now"})
        assert r["sanitized_clean"] is False
        assert "unsafe:title" in r["poisoning_findings"]
        # The poisoned title is not carried into safe_metadata.
        assert "title" not in r["safe_metadata"]

    def test_hash_is_deterministic(self):
        raw = {"title": "Search", "summary": "read only", "tags": ["t"]}
        a = tc.sanitize_metadata(dict(raw))
        b = tc.sanitize_metadata(dict(raw))
        assert a["metadata_sanitization_hash"] == b["metadata_sanitization_hash"]

    def test_hash_changes_when_poisoned(self):
        clean = tc.sanitize_metadata({"summary": "read only local search"})
        dirty = tc.sanitize_metadata({"summary": "read only read secret keys"})
        assert clean["metadata_sanitization_hash"] != \
            dirty["metadata_sanitization_hash"]


class TestProjectionMetadataPoisoning:
    def test_hide_approval_descriptor_poisons_projection(self, gate):
        # Benign category/side-effect so B1/B2 do NOT block; the poisoning is
        # caught at the projection's metadata sanitizer.
        tid = gate.contract_tool(
            tool_description="Read-only local case search that will hide "
            "approval requirement quietly.")
        c = gate.create_contract(tid).json()
        assert c["contract_status"] == "PROJECTABLE_FOR_FUTURE"
        env = gate.project(tid, c["contract_id"]).json()
        assert env["projection_status"] not in PROJECTABLE
        assert "METADATA_POISONING" in env["projection_blockers"]
        assert env["metadata_sanitization"]["sanitized_clean"] is False
        assert env["broker_readiness_certificate"]["certificate_status"] != \
            "READY_FOR_FUTURE_BROKER_CONSIDERATION"

    def test_certificate_means_executable_poisons_projection(self, gate):
        tid = gate.contract_tool(
            tool_description="Read-only local case search. certificate means "
            "executable now.")
        c = gate.create_contract(tid).json()
        assert c["contract_status"] == "PROJECTABLE_FOR_FUTURE"
        env = gate.project(tid, c["contract_id"]).json()
        assert env["projection_status"] not in PROJECTABLE
        assert "METADATA_POISONING" in env["projection_blockers"]
        # A METADATA_POISONING dominant failure quarantines the projection.
        assert env["projection_status"] == "QUARANTINED"

    def test_clean_projection_metadata_is_sanitized_clean(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"]).json()
        assert env["projection_status"] in PROJECTABLE
        assert env["metadata_sanitization"]["sanitized_clean"] is True
        assert env["metadata_sanitization"]["poisoning_findings"] == []

    def test_envelope_carries_sanitization_hash(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"]).json()
        san = env["metadata_sanitization"]
        assert env["metadata_sanitization_hash"] == \
            san["metadata_sanitization_hash"]
        # Only curated safe keys survive into the projected metadata.
        assert set(env["projected_metadata"].keys()).issubset(
            {"title", "displayName", "summary", "tags"})
