"""TOOL-B10 capsule: BOM, certificate, INDEPENDENT checker, self-cert rejection,
replay twin, TCB manifest, transparency, robustness frontier."""
from tools.context_governance import capsule as cap


def _body(**over):
    b = {"capsule_kind": "FINALIS_CONTEXT_CAPSULE",
         "informs_not_authorizes": True, "tenant_id": "t", "principal_id": "p",
         "purpose": "u", "operation_class": "o", "snapshot_root": "s",
         "version_vector_hash": "v", "entitlement_hash": "e", "claims": [],
         "support_bases": {}, "bom_root": "b", "risk_envelope_hash": "r",
         "tcb_root": "c", "compiler_version": "x"}
    b.update(over)
    return b


def test_bom_root_binds_entries():
    e1 = cap.bom_entry(ref="EV-1", kind="EVIDENCE", content_hash="h1",
                       provider_account="a", independence_class="INDEPENDENT",
                       taint="EXTERNAL", version="v1")
    e2 = cap.bom_entry(ref="EV-2", kind="EVIDENCE", content_hash="h2",
                       provider_account="a", independence_class="INDEPENDENT",
                       taint="EXTERNAL", version="v1")
    b1 = cap.context_bom([e1, e2])
    b2 = cap.context_bom([e1])
    assert b1["bom_root"] != b2["bom_root"]
    # order independent
    assert cap.context_bom([e1, e2])["bom_root"] == \
        cap.context_bom([e2, e1])["bom_root"]


def test_certificate_and_independent_checker_accept():
    capsule = cap.certify_capsule(_body(), generator_id="gen")
    chk = cap.check_capsule(capsule, checker_id="checker")
    assert chk["accepted"] is True
    assert cap.capsule_findings(chk) == []


def test_generator_cannot_self_certify():
    capsule = cap.certify_capsule(_body(), generator_id="same")
    chk = cap.check_capsule(capsule, checker_id="same")
    assert chk["accepted"] is False and chk["independent"] is False
    assert any(f.kind == "GENERATOR_SELF_CERTIFICATION"
               for f in cap.capsule_findings(chk))


def test_tampered_body_fails_checker():
    capsule = cap.certify_capsule(_body(), generator_id="gen")
    capsule["body"]["tenant_id"] = "EVIL"       # tamper after certification
    chk = cap.check_capsule(capsule, checker_id="checker")
    assert chk["accepted"] is False
    assert any(f.kind == "CAPSULE_CERTIFICATE_INVALID"
               for f in cap.capsule_findings(chk))


def test_secret_in_body_is_rejected():
    capsule = cap.certify_capsule(_body(provider_token="sk-xxx"),
                                  generator_id="gen")
    assert capsule["certificate"]["secret_free"] is False
    chk = cap.check_capsule(capsule, checker_id="checker")
    assert any(f.kind == "PROVIDER_TOKEN_IN_CAPSULE"
               for f in cap.capsule_findings(chk))


def test_capsule_asserting_authority_is_rejected():
    capsule = cap.certify_capsule(_body(informs_not_authorizes=False),
                                  generator_id="gen")
    chk = cap.check_capsule(capsule, checker_id="checker")
    assert chk["informs_only"] is False
    assert any(f.kind == "AUTHORITY_INFERENCE_REJECTED"
               for f in cap.capsule_findings(chk))


def test_replay_twin_matches_on_determinism():
    capsule = cap.certify_capsule(_body(), generator_id="gen")
    rep = cap.replay_twin(capsule, _body(), generator_id="gen")
    assert rep["diverged"] is False and cap.replay_findings(rep) == []


def test_replay_divergence_flagged():
    capsule = cap.certify_capsule(_body(), generator_id="gen")
    rep = cap.replay_twin(capsule, _body(tenant_id="OTHER"), generator_id="gen")
    assert rep["diverged"] is True
    assert cap.replay_findings(rep)[0].kind == "CAPSULE_REPLAY_DIVERGED"


def test_tcb_manifest_incomplete_when_component_missing():
    full = cap.tcb_manifest(present=list(cap.TCB_COMPONENTS))
    assert full["complete"] is True
    partial = cap.tcb_manifest(present=["canon", "model"])
    assert partial["complete"] is False and partial["missing"]


def test_transparency_receipt_binds_capsule_root():
    capsule = cap.certify_capsule(_body(), generator_id="gen")
    rec = cap.transparency_receipt(capsule, log_position=7)
    assert rec["capsule_root"] == capsule["certificate"]["capsule_root"]
    assert rec["log_position"] == 7


def test_robustness_frontier_partitions_scenarios():
    fr = cap.robustness_frontier(scenarios=[
        {"name": "source_stale", "certifies": True},
        {"name": "provider_truncates", "certifies": False}])
    assert fr["holds_under"] == ["source_stale"]
    assert fr["breaks_under"] == ["provider_truncates"]


def test_risk_envelope_is_hashed():
    env = cap.risk_envelope(taint_max="EXTERNAL", unresolved_conflicts=[],
                            common_mode_atoms=[], guarantee_active=True,
                            privacy_within_budget=True, truncation="NONE")
    assert "envelope_hash" in env and len(env["envelope_hash"]) == 64
