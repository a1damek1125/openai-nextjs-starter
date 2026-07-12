"""SP0005 red-team regression locks (SWARM-N).

Each test pins shut a confirmed false-negative escape the red-team found — a way
an unsafe condition was admitted as SAFE. These are the dual of the mutation
campaign: they must FAIL if the corresponding hardening is ever reverted.

E1  hazards: a truthy-string `hard_block` must not suppress UNCONTROLLED_CRITICAL.
E2  oracle: an unrecognized/typeless oracle must not count as a strong primary.
E3  regulatory: `used_as` must be case/whitespace-normalized before the gate.
E4  obligations: a duplicate same-type SATISFIED must not mask an UNKNOWN.
E5  regulatory: any non-applicability date as the applicable date is ambiguous.
E6  canon: a material field at the action root must change the fingerprint.
"""
from __future__ import annotations

from tools.safety.hazards import traceability
from tools.safety.oracle import validate_hard_property
from tools.safety.regulatory import check_binding_claims
from tools.safety.obligations import closure
from tools.safety.canon import action_fingerprint
from tools.safety.validate import validate_all
from tools.safety.model import (UNCONTROLLED_CRITICAL_HAZARD,
                                SELF_REPORT_AS_SOLE_ORACLE, INVALID_SAFETY_SCHEMA,
                                DRAFT_SOURCE_USED_AS_BINDING,
                                LEGAL_TIMELINE_STATE_AMBIGUOUS,
                                PROOF_OBLIGATION_UNKNOWN)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# ---- E1: truthy-string hard_block must not count as a real block -----------
def _uncontrolled(hard_block):
    h = {"hazard_id": "H1", "criticality": "CRITICAL", "status": "ACTIVE",
         "loss_refs": ["L1"]}
    if hard_block is not None:
        h["hard_block"] = hard_block
    return {"losses": [{"loss_id": "L1"}], "hazards": [h],
            "constraints": [{"constraint_id": "C1", "hazard_refs": ["H1"]}],
            "controls": [], "claims": []}


def test_e1_string_hard_block_does_not_suppress():
    for bad in ("false", "no", "TODO", "pending", "0"):
        prog = _uncontrolled(bad)
        assert UNCONTROLLED_CRITICAL_HAZARD in _k(traceability(prog)), bad
        assert not validate_all(prog).valid, bad


def test_e1_real_bool_hard_block_still_blocks():
    prog = _uncontrolled(True)
    assert UNCONTROLLED_CRITICAL_HAZARD not in _k(traceability(prog))


# ---- E2: junk oracle must not launder self-report --------------------------
def test_e2_junk_oracle_not_primary():
    assert SELF_REPORT_AS_SOLE_ORACLE in _k(validate_hard_property(
        {"property_id": "P", "oracles": [{"foo": "bar"}, "AGENT_SELF_REPORT"]}))
    assert SELF_REPORT_AS_SOLE_ORACLE in _k(validate_hard_property(
        {"property_id": "P", "oracles": ["MAGIC_ORACLE"]}))
    assert INVALID_SAFETY_SCHEMA in _k(validate_hard_property(
        {"property_id": "P", "oracles": ["MAGIC_ORACLE"]}))


def test_e2_real_env_oracle_still_ok():
    assert not [f for f in validate_hard_property(
        {"property_id": "P", "oracles": ["ENVIRONMENT_STATE"]})
        if f.kind == SELF_REPORT_AS_SOLE_ORACLE]


# ---- E3: used_as casing / whitespace bypass --------------------------------
def test_e3_used_as_case_and_whitespace_normalized():
    for u in ("binding", "Binding", "BINDING ", " binding "):
        reg = {"sources": [{"source_id": "S", "official_url": "u",
                            "source_status": "DRAFT_OFFICIAL_GUIDANCE",
                            "used_as": u}]}
        assert DRAFT_SOURCE_USED_AS_BINDING in _k(check_binding_claims(reg)), u


# ---- E4: duplicate obligation type masking UNKNOWN -------------------------
def test_e4_duplicate_type_cannot_mask_unknown():
    for pair in ([{"obligation_type": "PO-CONSENT", "status": "UNKNOWN"},
                  {"obligation_type": "PO-CONSENT", "status": "SATISFIED"}],
                 [{"obligation_type": "PO-CONSENT", "status": "SATISFIED"},
                  {"obligation_type": "PO-CONSENT", "status": "UNKNOWN"}]):
        ok, f = closure(pair)
        assert not ok and PROOF_OBLIGATION_UNKNOWN in _k(f)


# ---- E5: non-applicability date as applicable date -------------------------
def test_e5_preenactment_date_as_applicable_flagged():
    for bad in ("proposal_date", "political_agreement_date",
                "consultation_close_date", "publication_date"):
        reg = {"sources": [{"source_id": "S", "official_url": "u",
                            "source_status": "BINDING_LAW",
                            "applicable_date_source": bad}]}
        assert LEGAL_TIMELINE_STATE_AMBIGUOUS in _k(check_binding_claims(reg)), bad


def test_e5_real_applicability_date_clean():
    for good in ("entry_into_force_date", "general_application_date",
                 "special_application_dates"):
        reg = {"sources": [{"source_id": "S", "official_url": "u",
                            "source_status": "BINDING_LAW",
                            "applicable_date_source": good}]}
        assert LEGAL_TIMELINE_STATE_AMBIGUOUS not in _k(check_binding_claims(reg))


# ---- E6: material field at the action root ---------------------------------
def _act(**kw):
    a = {"action_type": "send", "target": {"target_id": "X"}, "parameters": {},
         "tenant": "t", "authority": "a", "policy_version": "1",
         "safety_context": {}}
    a.update(kw)
    return a


def test_e6_root_material_field_changes_fingerprint():
    assert action_fingerprint(_act(amount=100)) != action_fingerprint(
        _act(amount=9999999))
    assert action_fingerprint(_act(scope="tenant")) != action_fingerprint(
        _act(scope="global"))


def test_e6_volatile_field_ignored():
    assert action_fingerprint(_act()) == action_fingerprint(
        _act(display_name="pretty"))
