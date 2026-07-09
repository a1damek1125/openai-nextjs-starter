"""TOOL-B1 — TBOM (Tool Bill of Materials, NOT an SBOM).

build_tbom assembles local, deterministic tool-composition metadata. It never
executes, calls no external provider, and no LLM. Tests cover determinism, the
not_an_sbom disclaimer, the always-False execution/provider/llm flags, and that
tbom_hash excludes honesty_labels/timestamps. Via the endpoint, GET
/ai-tools/{id}/tbom returns a tbom with a matching hash and requires case.read
(a viewer, who has case.read, is allowed → 200).
"""
from finalis.ai_employee import tool_registry as tr
from tests.conftest import gate, VIEWER, OWNER  # noqa: F401


def _tbom(**over):
    kw = dict(tool_id="t1", tool_version_id="t1-v1", tenant_id="ten",
              tool_key="search-cases", category="DATA_SEARCH",
              side_effect_class="PURE_READ", risk_class="TRIVIAL",
              trust_tier="HUMAN_REVIEW_REQUIRED",
              schema_envelope_hash="se", effect_contract_hash="ec",
              data_flow_contract_hash="df", purpose_contract_hash="pu",
              consent_contract_hash="co", prompt_context_policy_hash="pc",
              declared_dependencies=["dep-a", "dep-b"],
              declared_provider="internal", declared_version="1.0.0",
              scanner_hash="sc")
    kw.update(over)
    return tr.build_tbom(**kw)


class TestDeterminism:
    def test_same_input_same_hash(self):
        assert _tbom()["tbom_hash"] == _tbom()["tbom_hash"]

    def test_hash_recomputes_via_core_hash(self):
        t = _tbom()
        assert tr._core_hash(t, "tbom_hash") == t["tbom_hash"]

    def test_changed_effect_hash_changes_tbom(self):
        assert _tbom(effect_contract_hash="a")["tbom_hash"] \
            != _tbom(effect_contract_hash="b")["tbom_hash"]

    def test_changed_data_flow_hash_changes_tbom(self):
        assert _tbom(data_flow_contract_hash="a")["tbom_hash"] \
            != _tbom(data_flow_contract_hash="b")["tbom_hash"]

    def test_changed_schema_hash_changes_tbom(self):
        assert _tbom(schema_envelope_hash="a")["tbom_hash"] \
            != _tbom(schema_envelope_hash="b")["tbom_hash"]

    def test_dependencies_sorted_and_deduped(self):
        t = _tbom(declared_dependencies=["z", "a", "z"])
        assert t["declared_dependencies"] == ["a", "z"]

    def test_version_string_present(self):
        assert _tbom()["tbom_version"] == tr.TBOM_VERSION


class TestNotAnSbom:
    def test_disclaimer_present(self):
        t = _tbom()
        assert "not an SBOM" in t["not_an_sbom"]

    def test_disclaimer_disclaims_standards(self):
        t = _tbom()
        assert "SPDX" in t["not_an_sbom"]
        assert "CycloneDX" in t["not_an_sbom"]

    def test_generation_method_local_deterministic(self):
        assert _tbom()["generation_method"] == "LOCAL_DETERMINISTIC"


class TestHonestyFlags:
    def test_external_provider_used_false(self):
        assert _tbom()["external_provider_used"] is False

    def test_llm_used_false(self):
        assert _tbom()["llm_used"] is False

    def test_tool_executed_false(self):
        assert _tbom()["tool_executed"] is False


class TestHashExclusions:
    def test_hash_excludes_honesty_labels(self):
        t = _tbom()
        t2 = dict(t, honesty_labels=["injected"])
        assert tr._core_hash(t2, "tbom_hash") == t["tbom_hash"]

    def test_hash_excludes_timestamps(self):
        t = _tbom()
        t2 = dict(t, created_at="2020-01-01", updated_at="2021-01-01")
        assert tr._core_hash(t2, "tbom_hash") == t["tbom_hash"]

    def test_hash_excludes_itself(self):
        t = _tbom()
        t2 = dict(t, tbom_hash="tampered")
        assert tr._core_hash(t2, "tbom_hash") == t["tbom_hash"]


class TestEndpoint:
    def test_tbom_endpoint_returns_matching_hash(self, gate):
        r = gate.register_tool()
        assert r.status_code == 200
        tool_id = r.json()["tool_id"]
        resp = gate.tool(tool_id, "/tbom", actor=OWNER)
        assert resp.status_code == 200
        j = resp.json()
        assert j["tool_id"] == tool_id
        tbom = j["tbom"]
        assert tr._core_hash(tbom, "tbom_hash") == tbom["tbom_hash"]
        assert tbom["tool_executed"] is False
        assert tbom["llm_used"] is False
        assert tbom["external_provider_used"] is False
        assert "not an SBOM" in tbom["not_an_sbom"]

    def test_tbom_endpoint_allows_viewer(self, gate):
        # Viewer has case.read, which /tbom requires.
        r = gate.register_tool()
        tool_id = r.json()["tool_id"]
        resp = gate.tool(tool_id, "/tbom", actor=VIEWER)
        assert resp.status_code == 200
        assert resp.json()["tbom"]["tbom_hash"]

    def test_tbom_endpoint_honesty_labels_present(self, gate):
        r = gate.register_tool()
        tool_id = r.json()["tool_id"]
        j = gate.tool(tool_id, "/tbom", actor=OWNER).json()
        assert j["honesty_labels"] == tr.HONESTY_LABELS
