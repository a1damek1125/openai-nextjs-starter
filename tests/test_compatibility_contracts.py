"""FINALIS SP0007 — acceptance criteria AC-0007-021..090.

Contract foundations, consumers, compatibility algebra, and contract
difference / evolution safety. Imports ONLY from tools.compatibility.*.
"""
from tools.compatibility import (model, contracts, vector, consumers, diff,
                                 policies, counterexample)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


def _sev(fs, kind):
    return {f.severity for f in (fs.findings if hasattr(fs, "findings") else fs)
            if f.kind == kind}


# --- fixtures --------------------------------------------------------------
def _field(type="string", required=False, nullable=False, default=None,
           enum=None, constraints=None, field_number=None,
           security_relevant=False):
    return {"type": type, "required": required, "nullable": nullable,
            "default": default, "enum": enum,
            "constraints": constraints or {}, "field_number": field_number,
            "security_relevant": security_relevant}


def _version(fields, **over):
    v = {"contract_id": "C1", "version": "1.0.0", "status": "DRAFT",
         "semantic_epoch": 1,
         "schema": {"fields": fields, "temporal": {}, "event_identity": {},
                    "idempotency": {}, "ordering": []},
         "behavior_contract": {}, "security_contract": {},
         "proof_contract": None}
    v.update(over)
    return v


def _descriptor(**over):
    d = {"contract_id": "C1", "contract_kind": "HTTP_API", "owner": "team-x",
         "stability": "STABLE", "criticality": "C3"}
    d.update(over)
    return d


def _all(state):
    return {d: state for d in model.COMPAT_DIMENSIONS}


def _claim(**over):
    kw = {"claim_id": "K1", "contract_id": "C1", "producer_version": "1.0.0",
          "consumer_id": "svc-a", "consumer_version": "3.0.0",
          "direction": model.DIRECTIONS[0], "scenario_scope": "checkout",
          "evidence_refs": ["fixture-1"], "validator_version": "v9",
          "tested_at": "2026-01-01", "compatibility_vector": _all("COMPATIBLE")}
    kw.update(over)
    return vector.build_claim(**kw)


# ===========================================================================
# AC-0007-021..030 — contract surfaces taxonomy
# ===========================================================================
def test_ac_021_030_contract_kinds_taxonomy():
    for kind in ("HTTP_API", "EVENT_MESSAGE", "STORED_DATA", "DB_SCHEMA",
                 "WORKFLOW_HISTORY", "SEMANTIC", "PROVIDER", "PROOF_HASH",
                 "CLI_CONFIG", "UI_PROJECTION"):
        assert kind in model.CONTRACT_KINDS


# ===========================================================================
# AC-0007-031..033 — descriptor validation / ownership
# ===========================================================================
def test_ac_031_descriptor_validates():
    assert contracts.validate_descriptor(_descriptor()) == []


def test_ac_032_ownerless_descriptor_flagged():
    d = _descriptor()
    d.pop("owner")
    assert model.CONTRACT_OWNER_MISSING in _k(contracts.validate_descriptor(d))


def test_ac_033_missing_contract_id_flagged():
    d = _descriptor(contract_id="")
    assert model.INVALID_COMPAT_SCHEMA in _k(contracts.validate_descriptor(d))


# ===========================================================================
# AC-0007-034..039 — version validation, sealing, mutation, identities
# ===========================================================================
def test_ac_034_version_validates_and_stability_criticality():
    sealed = contracts.release(_version({"a": _field(required=True)}))
    assert contracts.validate_version(sealed) == []
    # stability + criticality validated on the descriptor surface
    assert model.INVALID_COMPAT_SCHEMA in _k(
        contracts.validate_descriptor(_descriptor(stability="BOGUS")))
    assert model.INVALID_COMPAT_SCHEMA in _k(
        contracts.validate_descriptor(_descriptor(criticality="C9")))


def test_ac_035_release_seals_content_hash():
    sealed = contracts.release(_version({"a": _field()}))
    assert sealed["status"] == "RELEASED"
    assert sealed["content_hash"]


def test_ac_036_released_mutation_is_p0_via_validate_version():
    sealed = contracts.release(_version({"a": _field(required=True)}))
    mutated = dict(sealed)
    mutated["schema"] = {"fields": {"a": _field(required=False)}, "temporal": {},
                         "event_identity": {}, "idempotency": {}, "ordering": []}
    fs = contracts.validate_version(mutated)
    assert model.CONTRACT_VERSION_MUTATED in _k(fs)
    assert model.P0 in _sev(fs, model.CONTRACT_VERSION_MUTATED)


def test_ac_037_mutation_findings_detects_in_place_change():
    sealed = contracts.release(_version({"a": _field()}))
    current = _version({"a": _field(type="int")}, status="RELEASED")
    fs = contracts.mutation_findings(sealed, current)
    assert model.CONTRACT_VERSION_MUTATED in _k(fs)
    assert model.P0 in _sev(fs, model.CONTRACT_VERSION_MUTATED)


def test_ac_038_version_identities_kept_distinct():
    assert "contract_version" in model.VERSION_IDENTITIES
    assert "implementation_version" in model.VERSION_IDENTITIES


def test_ac_039_semver_is_declaration_not_proof():
    # breaking change hidden in a minor bump is a mismatch
    assert model.SEMVER_MISMATCH in _k(
        contracts.semver_declaration_findings("1.2.0", "1.3.0", True))
    # a major bump carrying the breaking change is consistent
    assert contracts.semver_declaration_findings("1.0.0", "2.0.0", True) == []


# ===========================================================================
# AC-0007-040/041/051..063 — compatibility vector & algebra
# ===========================================================================
def test_ac_040_new_vector_all_unknown():
    vec = vector.new_vector()
    assert set(vec.values()) == {"UNKNOWN"}
    assert set(vec) == set(model.COMPAT_DIMENSIONS)


def test_ac_051_hard_gate_unknown_by_default():
    assert vector.hard_gate(vector.new_vector()) == "UNKNOWN"


def test_ac_061_hard_gate_compatible_when_all_compatible():
    assert vector.hard_gate(_all("COMPATIBLE")) == "COMPATIBLE"


def test_ac_062_single_hard_incompatible_not_averaged_away():
    vec = _all("COMPATIBLE")
    vec["security"] = "INCOMPATIBLE"
    assert vector.hard_gate(vec) == "INCOMPATIBLE"
    assert vector.overall(vec) == "INCOMPATIBLE"


def test_ac_063_unknown_never_becomes_compatible():
    vec = _all("COMPATIBLE")
    vec["semantic"] = "UNKNOWN"
    assert vector.hard_gate(vec) != "COMPATIBLE"


# ===========================================================================
# AC-0007-047..050 — the four directions
# ===========================================================================
def test_ac_047_050_all_directions_validate():
    assert len(model.DIRECTIONS) == 4
    for direction in model.DIRECTIONS:
        claim = _claim(direction=direction)
        assert contracts is not None  # sanity
        assert vector.validate_claim(claim) == []


# ===========================================================================
# AC-0007-064..070 — consumer-specific claim binding, staleness
# ===========================================================================
def test_ac_064_claim_binds_all_dimensions():
    claim = _claim()
    for f in ("producer_version", "consumer_id", "scenario_scope",
              "evidence_refs", "validator_version", "direction"):
        assert claim.get(f)
    assert claim["claim_hash"]


def test_ac_065_claim_missing_direction_and_evidence_flagged():
    claim = {"claim_id": "K2", "contract_id": "C1", "producer_version": "1.0.0",
             "consumer_id": "svc-a", "consumer_version": "3.0.0",
             "scenario_scope": "checkout", "evidence_refs": [],
             "validator_version": "v9", "tested_at": "2026-01-01"}
    assert model.INVALID_COMPAT_SCHEMA in _k(vector.validate_claim(claim))


def test_ac_066_verified_without_compatible_vector_is_p0():
    claim = _claim()
    claim["compatibility_vector"]["security"] = "INCOMPATIBLE"
    claim["status"] = "VERIFIED"
    fs = vector.validate_claim(claim)
    assert model.CONSUMER_INCOMPATIBLE in _k(fs)
    assert model.P0 in _sev(fs, model.CONSUMER_INCOMPATIBLE)


def test_ac_070_staleness_on_producer_bump():
    claim = _claim(producer_version="1.0.0")
    assert vector.freshness(claim, producer_version="2.0.0") == "STALE"
    fs = vector.staleness_findings(claim, producer_version="2.0.0")
    assert model.COMPATIBILITY_EVIDENCE_STALE in _k(fs)


# ===========================================================================
# AC-0007-014 / D-0007-14 — transitivity is never assumed
# ===========================================================================
def test_ac_014_transitivity_assumed_flagged():
    c1 = _claim(claim_id="c1")
    c2 = _claim(claim_id="c2")
    inferred = {"claim_id": "c3", "evidence_refs": ["c1", "c2"]}
    fs = vector.transitive_inference_findings([c1, c2], inferred)
    assert model.TRANSITIVITY_ASSUMED in _k(fs)
    assert model.P0 in _sev(fs, model.TRANSITIVITY_ASSUMED)


# ===========================================================================
# AC-0007-041..046 — consumers, graph, blast radius, unknown consumers
# ===========================================================================
def test_ac_041_ownerless_binding_flagged():
    b = {"consumer_id": "svc-a", "contract_id": "C1", "version_range": ">=1.0",
         "usage_profile": {}, "unknown_field_policy": "PRESERVE"}
    assert model.CONTRACT_OWNER_MISSING in _k(consumers.validate_binding(b))


def test_ac_044_build_graph_and_blast_radius():
    descriptors = [_descriptor(contract_id="C1")]
    bindings = [{"consumer_id": "svc-a", "contract_id": "C1",
                 "version_range": ">=1.0", "usage_profile": {},
                 "unknown_field_policy": "PRESERVE", "owner": "team-a",
                 "criticality": "C4"}]
    graph = consumers.build_graph(descriptors, bindings)
    assert "svc-a" in graph["consumers_of"]["C1"]
    br = consumers.blast_radius(graph, "C1", bindings=bindings)
    assert br["direct_consumers"] == ["svc-a"]
    assert "svc-a" in br["critical_consumers"]


def test_ac_046_unknown_consumer_flagged():
    d = _descriptor(may_have_unknown_consumers=True)
    fs = consumers.unknown_consumer_findings(d, [])
    assert model.UNKNOWN_CONSUMER in _k(fs)


# ===========================================================================
# AC-0007-071..081 — diff engine & breaking-change classifier
# ===========================================================================
def test_ac_071_required_field_added_is_breaking():
    old = _version({"a": _field(required=True)})
    new = _version({"a": _field(required=True), "b": _field(required=True)})
    buckets = diff.classify(diff.diff_contracts(old, new))
    assert buckets["is_breaking"] is True
    assert model.BREAKING_CHANGE_DETECTED in _k(diff.breaking_findings(old, new))


def test_ac_075_field_removed_is_breaking():
    old = _version({"a": _field(), "b": _field()})
    new = _version({"a": _field()})
    assert diff.classify(diff.diff_contracts(old, new))["is_breaking"] is True
    assert model.BREAKING_CHANGE_DETECTED in _k(diff.breaking_findings(old, new))


def test_ac_076_type_narrowed_is_breaking():
    old = _version({"a": _field(type="float")})
    new = _version({"a": _field(type="int")})
    assert diff.classify(diff.diff_contracts(old, new))["is_breaking"] is True
    assert model.BREAKING_CHANGE_DETECTED in _k(diff.breaking_findings(old, new))


def test_ac_077_constraint_tightened_is_breaking():
    old = _version({"a": _field(constraints={"minimum": 0})})
    new = _version({"a": _field(constraints={"minimum": 5})})
    assert diff.classify(diff.diff_contracts(old, new))["is_breaking"] is True
    assert model.BREAKING_CHANGE_DETECTED in _k(diff.breaking_findings(old, new))


def test_ac_078_enum_evolution_world_aware():
    assert policies.enum_evolution(["A"], ["A", "B"], "CLOSED")[
        "classification"] == "BREAKING"
    assert policies.enum_evolution(["A"], ["A", "B"], "OPEN")[
        "classification"] != "BREAKING"


def test_ac_081_enum_removal_always_breaking():
    assert policies.enum_evolution(["A", "B"], ["A"], "OPEN")[
        "classification"] == "BREAKING"


# ===========================================================================
# AC-0007-082..084 — reserved identifiers
# ===========================================================================
def test_ac_082_reserved_field_number_reuse_is_p0():
    registry = {"reserved_field_numbers": [7]}
    candidate = {"schema": {"fields": {"newf": _field(field_number=7)}}}
    fs = policies.reserved_identifier_findings(registry, candidate)
    assert model.RESERVED_IDENTIFIER_REUSED in _k(fs)
    assert model.P0 in _sev(fs, model.RESERVED_IDENTIFIER_REUSED)


def test_ac_083_reserved_event_id_reuse_is_p0():
    registry = {"reserved_event_ids": ["evt-old"]}
    candidate = {"event_id": "evt-old"}
    fs = policies.reserved_identifier_findings(registry, candidate)
    assert model.RESERVED_IDENTIFIER_REUSED in _k(fs)
    assert model.P0 in _sev(fs, model.RESERVED_IDENTIFIER_REUSED)


# ===========================================================================
# AC-0007-085/086 — unknown-field policy preservation
# ===========================================================================
def test_ac_085_preserve_keeps_unknown_fields():
    processed, findings = policies.apply_unknown_field_policy(
        {"known": 1, "extra": 2}, ["known"], "PRESERVE")
    assert processed.get("extra") == 2
    assert findings == []


def test_ac_086_dropped_unknown_field_is_loss():
    fs = policies.preservation_findings(
        {"known": 1, "extra": 2}, {"known": 1}, ["known"], "PRESERVE")
    assert model.UNKNOWN_FIELD_LOSS in _k(fs)
    assert model.P0 in _sev(fs, model.UNKNOWN_FIELD_LOSS)


# ===========================================================================
# AC-0007-087 — temporal meaning changes
# ===========================================================================
def test_ac_087_temporal_change_flagged():
    fs = policies.temporal_findings({"timezone": "UTC"},
                                    {"timezone": "US/Pacific"})
    assert fs
    fs2 = policies.temporal_findings({"precision": "ms"}, {"precision": "s"})
    assert fs2


# ===========================================================================
# AC-0007-088 — event identity changes
# ===========================================================================
def test_ac_088_event_identity_change_unless_bridged():
    unbridged = policies.event_identity_findings({"dedup": "a"}, {"dedup": "b"})
    assert model.EVENT_IDENTITY_CHANGED in _k(unbridged)
    assert model.P0 in _sev(unbridged, model.EVENT_IDENTITY_CHANGED)
    # bridged with boolean True softens the hard break: no P0 remains
    bridged = policies.event_identity_findings(
        {"dedup": "a"}, {"dedup": "b", "bridged": True})
    assert model.P0 not in _sev(bridged, model.EVENT_IDENTITY_CHANGED)


# ===========================================================================
# AC-0007-089 — idempotency changes
# ===========================================================================
def test_ac_089_idempotency_change_unless_bridged():
    unbridged = policies.idempotency_findings(
        {"scope": "tenant"}, {"scope": "global"})
    assert model.IDEMPOTENCY_CONTRACT_CHANGED in _k(unbridged)
    assert model.P0 in _sev(unbridged, model.IDEMPOTENCY_CONTRACT_CHANGED)
    bridged = policies.idempotency_findings(
        {"scope": "tenant"}, {"scope": "global", "bridged": True})
    assert model.P0 not in _sev(bridged, model.IDEMPOTENCY_CONTRACT_CHANGED)


# ===========================================================================
# AC-0007-090 — security-relevant default change is P0
# ===========================================================================
def test_ac_090_security_default_change_is_p0():
    fs = policies.default_change_findings(
        _field(default=False, security_relevant=True),
        _field(default=True, security_relevant=True), name="allow_all")
    assert model.DEFAULT_VALUE_BEHAVIOR_CHANGED in _k(fs)
    assert model.P0 in _sev(fs, model.DEFAULT_VALUE_BEHAVIOR_CHANGED)


# ===========================================================================
# AC-0007-073 — minimal counterexample
# ===========================================================================
def test_ac_073_minimize_reduces_to_single_key():
    payload = {"a": 1, "b": 2, "bad": 3, "c": 4, "d": 5}
    result = counterexample.minimize(payload, lambda p: "bad" in p)
    assert result["minimal_witness"] == {"bad": 3}
