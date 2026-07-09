"""TOOL-B3 field provenance + taint (tc.build_field_provenance).

Every projected field must carry a source_hash back to the contract normal
form (provenance complete), a taint label, and — for a model-facing projection
over a constrained descriptor — a redaction/label so untrusted text never
reaches a future model. No execution.
"""
import pytest

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import OWNER


class TestProvenanceUnit:
    def test_complete_when_every_field_has_source_hash(self):
        fp = tc.build_field_provenance(
            tenant_id="t", contract_id="c", projection_id="p",
            fields=[("name", "contract_normal_form", "normalized_name",
                     "abc123", "projected", "SAFE_INTERNAL"),
                    ("description", "contract_normal_form",
                     "normalized_description", "def456", "projected",
                     "SAFE_INTERNAL")],
            quarantined=False)
        assert fp["all_fields_have_provenance"] is True

    def test_incomplete_when_a_field_missing_source_hash(self):
        fp = tc.build_field_provenance(
            tenant_id="t", contract_id="c", projection_id="p",
            fields=[("name", "contract_normal_form", "normalized_name",
                     "", "projected", "SAFE_INTERNAL")],
            quarantined=False)
        assert fp["all_fields_have_provenance"] is False

    def test_taint_labels_collected(self):
        fp = tc.build_field_provenance(
            tenant_id="t", contract_id="c", projection_id="p",
            fields=[("a", "contract_normal_form", "normalized_a", "h1",
                     "projected", "SAFE_INTERNAL"),
                    ("b", "contract_normal_form", "normalized_b", "h2",
                     "projected", "REDACTED")],
            quarantined=False)
        assert set(fp["taint_labels"]) == {"SAFE_INTERNAL", "REDACTED"}

    def test_redaction_applied_flag_tracks_taint(self):
        fp = tc.build_field_provenance(
            tenant_id="t", contract_id="c", projection_id="p",
            fields=[("b", "contract_normal_form", "normalized_b", "h2",
                     "projected", "NEVER_EXPOSE_TO_MODEL")],
            quarantined=True)
        assert fp["fields"][0]["redaction_applied"] is True

    def test_hash_deterministic(self):
        args = dict(tenant_id="t", contract_id="c", projection_id="p",
                    fields=[("name", "contract_normal_form", "normalized_name",
                             "abc123", "projected", "SAFE_INTERNAL")],
                    quarantined=False)
        a = tc.build_field_provenance(**args)
        b = tc.build_field_provenance(**args)
        assert a["field_provenance_hash"] == b["field_provenance_hash"]

    def test_hash_changes_with_fields(self):
        a = tc.build_field_provenance(
            tenant_id="t", contract_id="c", projection_id="p",
            fields=[("name", "m", "sf", "h1", "projected", "SAFE_INTERNAL")],
            quarantined=False)
        b = tc.build_field_provenance(
            tenant_id="t", contract_id="c", projection_id="p",
            fields=[("name", "m", "sf", "h2", "projected", "SAFE_INTERNAL")],
            quarantined=False)
        assert a["field_provenance_hash"] != b["field_provenance_hash"]


class TestProvenanceOverProjection:
    def test_every_projected_field_has_provenance(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"]).json()
        fp = env["field_provenance"]
        assert fp["all_fields_have_provenance"] is True
        assert all(f["source_hash"] for f in fp["fields"])

    def test_projected_fields_reference_normal_form(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"]).json()
        for f in env["field_provenance"]["fields"]:
            assert f["source_model"] == "contract_normal_form"
            assert f["source_field_path"].startswith("normalized_")

    def test_taint_labels_present_on_envelope(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"]).json()
        assert env["projection_taint_labels"]
        assert "SAFE_INTERNAL" in env["projection_taint_labels"]

    def test_get_provenance_endpoint(self, gate):
        tid, c = gate.contracted_tool()
        # A default INTERNAL_TOOL_BROKER projection is stored at create time.
        r = gate.ct(tid, c["contract_id"], "/provenance")
        assert r.status_code == 200
        fp = r.json()["field_provenance"]
        assert fp["all_fields_have_provenance"] is True
        assert fp["taint_labels"]

    def test_model_facing_summary_only_redacts_description(self, gate):
        # NAME_ONLY exposure → SUMMARY_ONLY minimal status → a model-facing
        # MCP-like projection must REDACT the description field.
        tid, c = gate.contracted_tool(prompt_context_exposure="NAME_ONLY")
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        desc = [f for f in env["field_provenance"]["fields"]
                if f["field_path"] == "description"]
        assert desc, "expected a description field in the MCP-like shape"
        assert desc[0]["taint"] == "REDACTED"
        assert desc[0]["redaction_applied"] is True
        assert "REDACTED" in env["projection_taint_labels"]
        assert env["projected_shape"]["description"] == \
            "[SUMMARY WITHHELD — exposure constrained]"

    def test_provenance_hash_matches_recompute(self, gate):
        # The per-projection field_provenance_hash binds the projection_id, so
        # it is unique per projection; it must still verify against its content.
        tid, c = gate.contracted_tool()
        fp = gate.project(tid, c["contract_id"]).json()["field_provenance"]
        assert fp["field_provenance_hash"] == tc._core_hash(
            fp, "field_provenance_hash")
