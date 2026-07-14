"""TOOL-B10 governance: end-to-end build_capsule pipeline (seal / block / determinism)."""
from tools.context_governance import governance as g
from tests._b10_ctxgov_kernel import (clean_request, make_entitlement, make_evidence,
                              make_claim)


def test_clean_request_seals_a_capsule():
    res = g.build_capsule(clean_request())
    assert res["valid"] is True and res["state"] == "SEALED"
    assert res["capsule"] is not None
    assert res["check"]["accepted"] is True
    assert res["report"]["counts"] == {"P0": 0, "P1": 0, "P2": 0}


def test_capsule_informs_not_authorizes():
    res = g.build_capsule(clean_request())
    body = res["capsule"]["body"]
    assert body["informs_not_authorizes"] is True
    assert "authority_grant" not in body


def test_build_is_deterministic():
    req = clean_request()
    a = g.build_capsule(req)
    b = g.build_capsule(req)
    assert a["capsule"]["certificate"]["capsule_root"] == \
        b["capsule"]["certificate"]["capsule_root"]
    assert a["result_hash"] == b["result_hash"]


def test_self_certification_blocks_seal():
    res = g.build_capsule(clean_request(), generator_id="x", checker_id="x")
    assert res["valid"] is False and res["capsule"] is None
    assert res["state"] == "CERTIFICATE_INVALID"


def test_cross_tenant_entitlement_blocks():
    req = clean_request(entitlement=make_entitlement(tenant_id="OTHER"))
    res = g.build_capsule(req)
    assert res["valid"] is False
    assert any(f["kind"] == "SOURCE_TENANT_MISMATCH"
               for f in res["report"]["findings"])


def test_forbidden_operation_blocks():
    req = clean_request(requested_operations=["PURE_COMPUTE", "EMAIL_SEND"])
    res = g.build_capsule(req)
    assert res["valid"] is False
    assert any(f["kind"] == "LIVE_EFFECT_ATTEMPTED"
               for f in res["report"]["findings"])


def test_mandatory_unmet_blocks_capsule():
    # requirement demands an atom no claim discharges
    from tests._b10_ctxgov_kernel import make_requirement
    req = clean_request(requirements=[make_requirement(atoms=["atom_missing"],
                                                       mandatory=True)])
    res = g.build_capsule(req)
    assert res["valid"] is False
    assert any(f["kind"] == "MANDATORY_REQUIREMENT_MISSING"
               for f in res["report"]["findings"])


def test_injection_taint_on_critical_claim_blocks():
    e = make_evidence()
    tainted = make_claim(e, taint_refs=["SUSPECTED_INJECTION"])
    req = clean_request(claims=[tainted],
                        critical_claim_ids={tainted["claim_id"]})
    res = g.build_capsule(req)
    assert res["valid"] is False
    assert any(f["kind"] == "TAINT_REMOVAL_UNPROVEN"
               for f in res["report"]["findings"])


def test_toctou_material_delta_blocks_via_receipt():
    # a blocked revalidation makes the consumption receipt invalid
    req = clean_request()
    req["revalidation"] = {"verdict": "BLOCKED",
                           "delta_certificate": {"classification": "BLOCKED"}}
    res = g.build_capsule(req)
    assert res["valid"] is False
    kinds = {f["kind"] for f in res["report"]["findings"]}
    assert "TOCTOU_REVALIDATION_FAILED" in kinds


def test_incomplete_when_snapshot_absent():
    req = clean_request()
    req.pop("snapshot")
    res = g.build_capsule(req)
    assert res["capsule"] is None
    assert res["state"] in ("INCOMPLETE", "CERTIFICATE_INVALID")
