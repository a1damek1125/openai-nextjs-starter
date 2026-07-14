"""SP0007 red-team regression locks (SWARM-M).

Each test pins shut a confirmed false-negative escape — a way a breaking/unsafe
contract evolution or migration was admitted as SAFE. They must FAIL if the
hardening is reverted. Two systemic root causes were fixed kernel-wide: truthy-
string coercion of boolean flags (fix: strict boolean parse / `is True`), and
blacklist / "missing = permissive" logic (fix: allowlist + fail-closed).
"""
from __future__ import annotations

from tools.compatibility import (vector as V, deprecation as D, plan as PL,
                                 migration as MG, policies as PO, diff as DF,
                                 envelope as EN, negotiation as NG, corpus as CO)
from tools.compatibility.model import (ROLLBACK_NOT_AVAILABLE,
                                       RESERVED_IDENTIFIER_REUSED,
                                       DEPRECATION_WITH_ACTIVE_CONSUMER,
                                       CONSUMER_INCOMPATIBLE,
                                       BREAKING_CHANGE_DETECTED,
                                       PROOF_ENVELOPE_MISMATCH,
                                       SEMANTIC_COMPATIBILITY_REQUIRED,
                                       INVALID_COMPAT_SCHEMA)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


def _field(**kw):
    b = {"type": "string", "required": False, "nullable": False, "default": None,
         "enum": None, "constraints": {}, "field_number": 1,
         "security_relevant": False}
    b.update(kw)
    return b


def _ver(fields):
    return {"schema": {"fields": fields, "temporal": {}, "event_identity": {},
                       "idempotency": {}, "ordering": []}}


# E1 — a hard dimension marked NOT_APPLICABLE (or any non-COMPATIBLE state) must
# never let the hard gate pass to COMPATIBLE
def test_e1_hard_dimension_not_applicable_does_not_pass():
    for bad in ("NOT_APPLICABLE", "REVIEW_REQUIRED", "UNKNOWN"):
        vec = {d: "COMPATIBLE" for d in V.new_vector()}
        vec["security"] = bad
        assert V.hard_gate(vec) != "COMPATIBLE", bad
        assert V.overall(vec) != "COMPATIBLE", bad


def test_e1_all_compatible_still_passes():
    vec = {d: "COMPATIBLE" for d in V.new_vector()}
    assert V.hard_gate(vec) == "COMPATIBLE"


# E2 — deprecation removal: migrated truthy-string does not mark migrated
def test_e2_migrated_string_does_not_mark_migrated():
    notice = {"contract_id": "CT", "status": "RETIRED"}
    for val in ("false", "no", "0"):
        b = [{"contract_id": "CT", "active": True, "migrated": val}]
        assert DEPRECATION_WITH_ACTIVE_CONSUMER in _k(D.removal_findings(notice, b))


def test_e2_real_migrated_true_clears():
    notice = {"contract_id": "CT", "status": "RETIRED"}
    b = [{"contract_id": "CT", "active": True, "migrated": True}]
    assert DEPRECATION_WITH_ACTIVE_CONSUMER not in _k(D.removal_findings(notice, b))


# E3 — contract phase: migrated truthy-string does not clear the gate
def test_e3_contract_phase_migrated_string_blocks():
    f = PL.contract_phase_findings({"migration_plan_id": "P"},
                                   bindings=[{"criticality": "C4",
                                              "consumer_id": "c",
                                              "migrated": "false"}])
    assert CONSUMER_INCOMPATIBLE in _k(f)


# E10 — REVERSIBLE edge with an unverified inverse is not a proven rollback
def test_e10_reversible_unverified_inverse_rejected():
    e = {"migration_edge_id": "E", "contract_id": "C", "from_version": "1",
         "to_version": "2", "transformer_ref": "t",
         "inverse_transformer_ref": "inv", "inverse_verified": False,
         "preconditions": [], "postconditions": [], "loss_vector": {},
         "reversibility": "REVERSIBLE"}
    assert ROLLBACK_NOT_AVAILABLE in _k(MG.validate_edge(e))
    e2 = dict(e, inverse_verified=True)
    assert ROLLBACK_NOT_AVAILABLE not in _k(MG.validate_edge(e2))


# E5 — reserved identifier reuse via int/str type confusion
def test_e5_reserved_field_number_type_confusion():
    reg = {"reserved_field_numbers": [7]}
    cand = {"schema": {"fields": {"f": _field(field_number="7")}}}
    assert RESERVED_IDENTIFIER_REUSED in _k(PO.reserved_identifier_findings(reg,
                                                                           cand))


# E4 — nullable/required given as a truthy string
def test_e4_nullable_string_false_is_a_break():
    f = PO.nullability_findings({"nullable": True}, {"nullable": "false"},
                               name="f", direction="OLD_PRODUCER_TO_NEW_CONSUMER")
    assert BREAKING_CHANGE_DETECTED in _k(f)


def test_e4_diff_detects_string_false_nullability():
    old = _ver({"f": _field(nullable=True)})
    new = _ver({"f": _field(nullable="false")})
    kinds = {r["kind"] for r in DF.diff_contracts(old, new)}
    assert any("NULLABILITY" in k for k in kinds)


# E9 — an open/unknown-world enum addition still requires review (not silent)
def test_e9_enum_review_not_silently_dropped():
    old = _ver({"s": _field(enum=["A"])})
    new = _ver({"s": _field(enum=["A", "B"])})
    for consumer in ({"enum_world": "closed"}, None):   # lowercase / unknown
        assert SEMANTIC_COMPATIBILITY_REQUIRED in _k(
            DF.breaking_findings(old, new, consumer=consumer))


# E7 — envelope authority-synonym key rejected by the structural allowlist
def test_e7_envelope_rejects_nonstructural_keys():
    e = EN.migration_proof_envelope(migration_plan={"p": 1})
    for key in ("mandate", "ratifies", "sanctions", "empowers"):
        assert PROOF_ENVELOPE_MISMATCH in _k(EN.validate_envelope(
            dict(e, **{key: True})))


def test_e7_clean_envelope_still_valid():
    e = EN.migration_proof_envelope(migration_plan={"p": 1}, transformer={"t": 1})
    assert not EN.validate_envelope(e)


# E6 — negotiate rejects a floating token even if it is in `supported`
def test_e6_negotiate_rejects_floating_latest():
    assert NG.negotiate(["1.0", "latest"], "latest")["result"] == "FAIL_CLOSED"
    assert NG.negotiate(["1.0", "2.0"], "2.0")["result"] == "ACCEPTED"


# E8 — any non-SYNTHETIC/ANONYMIZED corpus tenant_class is a P0
def test_e8_production_family_corpus_is_p0():
    for tc in ("PRODUCTION", "PROD", "LIVE", "RAW", "PRODUCTION_RAW"):
        fx = {"fixture_id": "F", "contract_id": "C", "contract_version": "1",
              "fixture_kind": "REQUEST", "payload": {}, "semantic_epoch": "e",
              "corpus_class": "COMMON", "provenance": {"s": 1},
              "tenant_class": tc}
        assert any(f.severity == "P0" for f in CO.validate_fixture(fx)), tc
