"""TOOL-B1 — schema envelope (pure kernel + endpoint).

build_schema_envelope wraps a DECLARED, untrusted JSON-schema shape with content
hashes. It never validates by execution. Tests cover determinism, parameter
normalization, schema-hash sensitivity, the always-False execution flag, and the
fact that a registered tool's version carries a schema_envelope whose hash
recomputes with tr._core_hash.
"""
from finalis.ai_employee import tool_registry as tr
from tests.conftest import gate  # noqa: F401


def _env(**over):
    kw = dict(input_schema={"type": "object"}, output_schema={"type": "string"},
              parameters=[{"name": "q", "type": "string", "required": True,
                           "description": "query", "data_class": "INTERNAL",
                           "sensitive": False}])
    kw.update(over)
    return tr.build_schema_envelope(**kw)


class TestDeterminism:
    def test_same_input_same_hash(self):
        assert _env()["schema_envelope_hash"] == _env()["schema_envelope_hash"]

    def test_hash_recomputes_via_core_hash(self):
        e = _env()
        assert tr._core_hash(e, "schema_envelope_hash") \
            == e["schema_envelope_hash"]

    def test_hash_excludes_itself(self):
        e = _env()
        e2 = dict(e, schema_envelope_hash="tampered")
        assert tr._core_hash(e2, "schema_envelope_hash") \
            == e["schema_envelope_hash"]

    def test_version_string_present(self):
        assert _env()["schema_envelope_version"] == tr.SCHEMA_ENVELOPE_VERSION


class TestParameterNormalization:
    def test_defaults_filled(self):
        e = tr.build_schema_envelope(input_schema={}, output_schema={},
                                     parameters=[{"name": "p"}])
        p = e["parameters"][0]
        assert p == {"name": "p", "type": "string", "required": False,
                     "description": "", "data_class": "INTERNAL",
                     "sensitive": False, "default": None, "example": None}

    def test_sensitive_flag_preserved(self):
        e = tr.build_schema_envelope(input_schema={}, output_schema={},
                                     parameters=[{"name": "secret",
                                                  "sensitive": True}])
        assert e["parameters"][0]["sensitive"] is True

    def test_data_class_preserved(self):
        e = tr.build_schema_envelope(
            input_schema={}, output_schema={},
            parameters=[{"name": "c", "data_class": "CREDENTIALS"}])
        assert e["parameters"][0]["data_class"] == "CREDENTIALS"

    def test_required_and_type_coerced(self):
        e = tr.build_schema_envelope(
            input_schema={}, output_schema={},
            parameters=[{"name": "n", "type": "integer", "required": 1}])
        assert e["parameters"][0]["type"] == "integer"
        assert e["parameters"][0]["required"] is True

    def test_empty_parameters_ok(self):
        e = tr.build_schema_envelope(input_schema={}, output_schema={})
        assert e["parameters"] == []

    def test_changing_param_changes_hash(self):
        a = _env(parameters=[{"name": "a"}])
        b = _env(parameters=[{"name": "b"}])
        assert a["schema_envelope_hash"] != b["schema_envelope_hash"]

    def test_sensitive_flag_changes_hash(self):
        a = _env(parameters=[{"name": "x", "sensitive": False}])
        b = _env(parameters=[{"name": "x", "sensitive": True}])
        assert a["schema_envelope_hash"] != b["schema_envelope_hash"]


class TestSchemaHashes:
    def test_input_schema_hash_is_content_sha(self):
        e = _env(input_schema={"type": "object"})
        assert e["input_schema_hash"] == tr._sha({"type": "object"})

    def test_output_schema_hash_is_content_sha(self):
        e = _env(output_schema={"type": "string"})
        assert e["output_schema_hash"] == tr._sha({"type": "string"})

    def test_input_schema_change_changes_envelope_hash(self):
        a = _env(input_schema={"type": "object"})
        b = _env(input_schema={"type": "array"})
        assert a["input_schema_hash"] != b["input_schema_hash"]
        assert a["schema_envelope_hash"] != b["schema_envelope_hash"]

    def test_output_schema_change_changes_envelope_hash(self):
        a = _env(output_schema={"type": "string"})
        b = _env(output_schema={"type": "number"})
        assert a["output_schema_hash"] != b["output_schema_hash"]
        assert a["schema_envelope_hash"] != b["schema_envelope_hash"]

    def test_none_schemas_normalize_to_empty(self):
        e = tr.build_schema_envelope(input_schema=None, output_schema=None)
        assert e["input_schema_hash"] == tr._sha({})
        assert e["output_schema_hash"] == tr._sha({})

    def test_declared_sets_sorted_and_deduped(self):
        e = tr.build_schema_envelope(
            input_schema={}, output_schema={},
            declared_side_effects=["PURE_READ", "PURE_READ"],
            declared_data_reads=["INTERNAL", "PUBLIC", "INTERNAL"])
        assert e["declared_side_effects"] == ["PURE_READ"]
        assert e["declared_data_reads"] == ["INTERNAL", "PUBLIC"]


class TestValidatedByExecution:
    def test_always_false(self):
        assert _env()["validated_by_execution"] is False

    def test_false_even_with_writes_declared(self):
        e = tr.build_schema_envelope(
            input_schema={}, output_schema={},
            declared_data_writes=["INTERNAL"],
            declared_side_effects=["INTERNAL_WRITE"])
        assert e["validated_by_execution"] is False


class TestRegisteredToolEnvelope:
    def test_version_carries_matching_envelope_hash(self, gate):
        r = gate.register_tool(
            input_schema={"type": "object"},
            output_schema={"type": "array"},
            parameters=[{"name": "q", "sensitive": True,
                         "data_class": "INTERNAL"}])
        assert r.status_code == 200
        tool_id = r.json()["tool_id"]
        lv = gate.latest_tool_version(tool_id)
        env = lv["schema_envelope"]
        assert env["validated_by_execution"] is False
        assert tr._core_hash(env, "schema_envelope_hash") \
            == env["schema_envelope_hash"]

    def test_registered_param_sensitive_flag_preserved(self, gate):
        r = gate.register_tool(parameters=[{"name": "token",
                                            "sensitive": True}])
        tool_id = r.json()["tool_id"]
        env = gate.latest_tool_version(tool_id)["schema_envelope"]
        assert env["parameters"][0]["sensitive"] is True
