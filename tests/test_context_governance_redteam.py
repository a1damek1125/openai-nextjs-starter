"""TOOL-B10 red-team regression: each test pins a hole an adversarial audit found,
so a future refactor that reopens it fails CI. All of these MUST fail closed."""
from tools.context_governance import (model, evidence, compile as comp,
                                       capsule as cap, boundary)


def _body(**over):
    b = {"capsule_kind": "FINALIS_CONTEXT_CAPSULE",
         "informs_not_authorizes": True, "tenant_id": "t", "principal_id": "p",
         "purpose": "u", "operation_class": "o", "snapshot_root": "s",
         "version_vector_hash": "v", "entitlement_hash": "e", "claims": [],
         "support_bases": {}, "bom_root": "b", "risk_envelope_hash": "r",
         "tcb_root": "c", "compiler_version": "x"}
    b.update(over)
    return b


# defect 5: certificate must bind the ENTIRE body, incl. support_bases / compiler
def test_certificate_binds_support_bases():
    capsule = cap.certify_capsule(_body(), generator_id="gen")
    # forge the minimal-support proof after certification
    capsule["body"]["support_bases"] = {"R": [["CL-FORGED"]]}
    chk = cap.check_capsule(capsule, checker_id="checker")
    assert chk["accepted"] is False
    assert any(f.kind == "CAPSULE_CERTIFICATE_INVALID"
               for f in cap.capsule_findings(chk))


def test_certificate_binds_compiler_version():
    capsule = cap.certify_capsule(_body(), generator_id="gen")
    capsule["body"]["compiler_version"] = "EVIL"
    chk = cap.check_capsule(capsule, checker_id="checker")
    assert chk["accepted"] is False


def test_forged_body_root_is_distinct():
    clean = cap.certify_capsule(_body(), generator_id="gen")
    forged = cap.certify_capsule(
        _body(support_bases={"R": [["CL-FORGED"]]}, compiler_version="EVIL"),
        generator_id="gen")
    assert clean["certificate"]["capsule_root"] != \
        forged["certificate"]["capsule_root"]


# defect 2: an injected authority key must be refused (closed allowlist)
def test_injected_authority_key_rejected():
    capsule = cap.certify_capsule(_body(), generator_id="gen")
    capsule["body"]["authority"] = {"grant": "APPROVE_PAYMENT", "role": "admin"}
    chk = cap.check_capsule(capsule, checker_id="checker")
    assert chk["accepted"] is False
    assert chk["well_formed"] is False


def test_authority_key_at_build_is_not_well_formed():
    capsule = cap.certify_capsule(_body(grant_of_authority="admin"),
                                  generator_id="gen")
    assert capsule["certificate"]["well_formed"] is False
    chk = cap.check_capsule(capsule, checker_id="checker")
    assert chk["accepted"] is False


# defect (secret as value): secret hidden under an innocuous key must be caught
def test_secret_value_under_innocuous_key_rejected():
    capsule = cap.certify_capsule(_body(compiler_version="token sk-live-DEADBEEF"),
                                  generator_id="gen")
    assert capsule["certificate"]["secret_free"] is False
    chk = cap.check_capsule(capsule, checker_id="checker")
    assert any(f.kind == "PROVIDER_TOKEN_IN_CAPSULE"
               for f in cap.capsule_findings(chk))


# defect 4: an unrecognized taint label must NOT collapse to UNTAINTED
def test_unknown_taint_label_is_most_severe():
    assert model.taint_join("UNTAINTED", "MALWARE") == "MALWARE"
    assert model.taint_join("EXTERNAL", "MALWARE") == "MALWARE"
    assert evidence.propagate_taint(["MALWARE"]) == "MALWARE"


def test_unknown_taint_not_cleared_without_proof():
    assert evidence.propagate_taint(["MALWARE"], removal_proven=False) == "MALWARE"


# compaction taint-laundering: stripping taint off a critical claim is a violation
def test_compaction_flags_taint_stripping():
    from tests._b10_ctxgov_kernel import make_evidence, make_claim
    e = make_evidence()
    orig = make_claim(e, support=True, taint_refs=["QUARANTINED"])
    laundered = dict(orig); laundered["taint_refs"] = []
    cert = comp.compaction(original_claims=[orig], retained_claims=[laundered],
                           critical_ids={orig["claim_id"]})
    kinds = {v[0] for v in cert["violations"]}
    assert "COMPRESSION_TAINT_STRIPPED" in kinds


# privacy: an exposure on an unknown axis has no budget -> fails closed
def test_privacy_unknown_axis_fails_closed():
    b = comp.privacy_budget({"pii": 5})
    exp = comp.privacy_exposure({"genetic": 9999}, b)
    assert exp["within_budget"] is False
    assert any(o["axis"] == "genetic" for o in exp["overruns"])


# authority air-gap: missing/unknown channel asserting authority is rejected
def test_air_gap_missing_channel_fails_closed():
    rec = {"evidence_id": "EV-1", "asserts_authority": True}   # no channel
    assert evidence.authority_air_gap([rec])[0].kind == \
        "AUTHORITY_INFERENCE_REJECTED"


# boundary: a non-string operation must classify UNKNOWN, not crash
def test_boundary_non_string_op_fails_closed():
    assert boundary.classify_effect(123) == "UNKNOWN"
    assert boundary.classify_effect(None) == "UNKNOWN"


# taint gate consistency: an UNKNOWN taint label on a critical claim must block
# (consistent with the taint_join fail-closed lattice), not just the two known ones
def test_unknown_taint_label_blocks_critical_claim():
    from tests._b10_ctxgov_kernel import make_evidence, make_claim
    e = make_evidence()
    c = make_claim(e, taint_refs=["MALWARE_UNKNOWN"])
    fs = evidence.taint_findings([c], critical_ids={c["claim_id"]})
    assert fs and fs[0].kind == "TAINT_REMOVAL_UNPROVEN" and fs[0].severity == "P0"


def test_benign_taint_does_not_block():
    from tests._b10_ctxgov_kernel import make_evidence, make_claim
    e = make_evidence()
    c = make_claim(e, taint_refs=["EXTERNAL"])
    assert evidence.taint_findings([c], critical_ids={c["claim_id"]}) == []
