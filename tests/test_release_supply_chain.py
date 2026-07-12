"""SP0009 supply-chain, trust, transparency, build and CI-security coverage.

Exercises the artifact closure, provenance/trust/transparency, SBOM/VEX,
reproducible + diverse builds, and agentic-CI taint layers against the
acceptance criteria (AC-0009-121..205).
"""
from __future__ import annotations

from pathlib import Path

from tools.release import (build as build_mod, artifacts, trust, transparency,
                           sbom as sbom_mod, ci_security, canon, model)

NOW = "2026-07-12"
FUT = "2027-07-12"
G = "genome"


def _root(**kw):
    base = dict(trust_root_id="R", version=2, trust_domain="dom-a",
                threshold=1, authorized_signers=["s1"],
                valid_from="2026-01-01", expires_at=FUT)
    base.update(kw)
    return trust.trust_root(**base)


# --- build hermeticity + reproducibility + quorum ------------------------------------
def test_hermeticity_detects_undeclared_network():
    m = build_mod.build_manifest(
        candidate_genome=G, source_commit="c", builder_identity="b",
        builder_trust_domain="d", builder_version="1", toolchain=["t"],
        dependency_lock_hash="h", environment_inputs={}, commands=[],
        declared_network_access=[], declared_time_inputs=[])
    fs = build_mod.hermeticity_findings(m, {"network_access":
                                            ["https://evil.example"]})
    assert any(f.kind == "BUILD_INPUT_UNDECLARED" and f.severity == model.P0
               for f in fs)


def test_reproducibility_byte_equal():
    a = {"input_hash": "i", "artifact_digest": "d1"}
    b = {"input_hash": "i", "artifact_digest": "d1"}
    r = build_mod.reproducibility(a, b)
    assert r["byte_equal"] and r["reproducible"]


def test_reproducibility_mismatch_flagged():
    a = {"input_hash": "i", "artifact_digest": "d1"}
    b = {"input_hash": "i", "artifact_digest": "d2"}
    r = build_mod.reproducibility(a, b)
    assert not r["reproducible"]
    assert build_mod.reproducibility_findings(r, "A")


def test_builder_quorum_requires_domain_diversity():
    builds = [{"builder_identity": "b1", "builder_trust_domain": "d1",
               "artifact_digest": "same"},
              {"builder_identity": "b2", "builder_trust_domain": "d1",
               "artifact_digest": "same"}]
    q = build_mod.builder_quorum(builds)
    assert not q["quorum"]              # one domain => not diverse
    builds[1]["builder_trust_domain"] = "d2"
    assert build_mod.builder_quorum(builds)["quorum"]


def test_builder_quorum_rejects_divergent_artifacts():
    builds = [{"builder_identity": "b1", "builder_trust_domain": "d1",
               "artifact_digest": "x"},
              {"builder_identity": "b2", "builder_trust_domain": "d2",
               "artifact_digest": "y"}]
    assert not build_mod.builder_quorum(builds)["quorum"]


# --- artifacts / closure -------------------------------------------------------------
def test_artifact_seal_and_mutation_detection():
    a = artifacts.seal(artifacts.artifact_manifest(
        candidate_genome=G, artifact_type="X", digest="sha", size_bytes=10,
        build_ref="b"))
    assert artifacts.verify_seal(a) == []
    tampered = dict(a, digest="other")
    assert any(f.kind == "ARTIFACT_SEALED_MUTATION"
               for f in artifacts.verify_seal(tampered))


def test_artifact_substitution_detected():
    a = artifacts.artifact_manifest(candidate_genome=G, artifact_type="X",
                                    digest="sha", size_bytes=1, build_ref="b")
    fs = artifacts.substitution_findings(a, {"digest": "other"})
    assert any(f.kind == "ARTIFACT_SUBSTITUTION" for f in fs)


def test_closure_incomplete_blocks_protected():
    a = artifacts.artifact_manifest(candidate_genome=G, artifact_type="X",
                                    digest="sha", size_bytes=1, build_ref="b")
    c = artifacts.closure(artifact=a)     # no evidence
    assert c["closure_status"] == "INCOMPLETE"
    assert any(f.severity == model.P0
               for f in artifacts.closure_findings(c, protected=True))


def test_closure_subject_binding():
    a = artifacts.artifact_manifest(candidate_genome=G, artifact_type="X",
                                    digest="sha-A", size_bytes=1,
                                    build_ref="b")
    c = artifacts.closure(artifact=a, sbom_refs=["s"], attestation_refs=["at"],
                          trust_root_refs=["r"],
                          verification_summary_refs=["v"])
    fs = artifacts.subject_bound_findings(
        c, [{"kind": "SBOM", "ref": "s", "subject_digest": "sha-B"}])
    assert any(f.kind == "SBOM_SUBJECT_MISMATCH" for f in fs)


# --- trust / attestation -------------------------------------------------------------
def test_revoked_signer_root_rejected():
    fs = trust.validate_root(_root(revoked_at="2026-05-01"), now=NOW)
    assert any(f.kind == "TRUST_ROOT_REVOKED" for f in fs)


def test_attestation_valid_path():
    art_digest = "sha"
    att = trust.attestation(subject_digest=art_digest,
                            predicate_type="https://slsa.dev/provenance/v1",
                            predicate={}, signer="s1", signing_time=NOW,
                            candidate_genome=G)
    fs = trust.verify_attestation(att, artifact_digest=art_digest,
                                  candidate_genome=G, roots=[_root()], now=NOW)
    assert fs == []


def test_unknown_predicate_fails_closed_when_protected():
    att = trust.attestation(subject_digest="sha", predicate_type="mystery/v9",
                            predicate={}, signer="s1", signing_time=NOW,
                            candidate_genome=G)
    fs = trust.verify_attestation(att, artifact_digest="sha",
                                  candidate_genome=G, roots=[_root()],
                                  now=NOW, protected=True)
    assert any(f.kind == "UNKNOWN_PREDICATE_REJECTED" and f.severity == model.P0
               for f in fs)


def test_slsa_projection_claims_no_level():
    m = {"source_commit": "c", "dependency_lock_hash": "h",
         "builder_identity": "b"}
    proj = trust.slsa_projection(m, {"digest": "sha"})
    assert "level" not in str(proj["predicate"]).lower() or "no SLSA level" \
        in proj["note"]


# --- transparency --------------------------------------------------------------------
def test_transparency_inclusion_and_forgery():
    log = canon.MerkleLog()
    for s in ("a", "b", "c"):
        log.append(s)
    r = transparency.register(log, subject_digest="sha", claim_kind="ev",
                              log_identity="log-1")
    pinned = log.checkpoint()
    assert transparency.verify_receipt(
        r, expected_subject="sha", expected_log_identity="log-1",
        pinned_checkpoint=pinned) == []
    # wrong subject
    fs = transparency.verify_receipt(r, expected_subject="other",
                                     expected_log_identity="log-1",
                                     pinned_checkpoint=pinned)
    assert any(f.kind == "TRANSPARENCY_RECEIPT_INVALID" for f in fs)


def test_transparency_self_asserted_checkpoint_rejected():
    # a forged size-1 receipt (empty proof, self-asserted root) must not verify
    # against a DIFFERENT pinned checkpoint
    log = canon.MerkleLog()
    for s in ("a", "b"):
        log.append(s)
    pinned = log.checkpoint()
    forged = {"receipt_id": "TR-x", "subject_digest": "sha",
              "claim_kind": "ev", "log_identity": "log-1",
              "log_checkpoint": {"size": 1,
                                 "root": canon.sha256_hex("L\x00ev:sha")},
              "inclusion_proof": []}
    fs = transparency.verify_receipt(forged, expected_subject="sha",
                                     expected_log_identity="log-1",
                                     pinned_checkpoint=pinned)
    assert any(f.kind == "TRANSPARENCY_RECEIPT_INVALID" and f.severity ==
               model.P0 for f in fs)


def test_transparency_tampered_proof_fails():
    log = canon.MerkleLog()
    for i in range(4):
        log.append(f"e{i}")
    r = transparency.register(log, subject_digest="sha", claim_kind="ev",
                              log_identity="log-1")
    r["inclusion_proof"] = [("R", "deadbeef")]     # forged path
    fs = transparency.verify_receipt(r, expected_subject="sha",
                                     expected_log_identity="log-1")
    assert any(f.kind == "TRANSPARENCY_RECEIPT_INVALID" for f in fs)


# --- sbom / vex / scanners -----------------------------------------------------------
def test_sbom_completeness_recorded_not_hidden():
    s = sbom_mod.sbom(subject_digest="sha", components=["a"],
                      completeness="INCOMPLETE_THIRD_PARTY")
    fs = sbom_mod.validate_sbom(s, artifact_digest="sha")
    assert all(f.severity != model.P0 for f in fs)   # subject matches
    assert any(f.kind == "SBOM_INCOMPLETE" for f in fs)


def test_spdx_and_cyclonedx_projections():
    s = sbom_mod.sbom(subject_digest="sha", components=["a"],
                      completeness="COMPLETE")
    assert sbom_mod.spdx_projection(s)["spdxVersion"] == "SPDX-3.0"
    assert sbom_mod.cyclonedx_projection(s)["specVersion"] == "1.7"


def test_vex_cannot_auto_waive_policy():
    c = sbom_mod.vex_claim(subject_digest="sha", vulnerability_id="CVE-1",
                           status="not_affected", justification="not reachable",
                           evidence_refs=["ev"], author="a", observed_at=NOW,
                           expires_at=FUT)
    assert sbom_mod.validate_vex(c, artifact_digest="sha", now=NOW) == []
    fs = sbom_mod.vex_cannot_waive(True, [c])
    assert any(f.kind == "VULNERABILITY_POLICY_FAILED" for f in fs)


def test_scanner_disagreement_preserved():
    results = [{"subject_digest": "sha", "vulnerability_id": "CVE-1",
                "verdict": "affected", "scanner_id": "a"},
               {"subject_digest": "sha", "vulnerability_id": "CVE-1",
                "verdict": "not_affected", "scanner_id": "b"}]
    fs = sbom_mod.disagreement_findings(results)
    assert any(f.kind == "SCANNER_COMMON_MODE_RISK" for f in fs)


def test_vulnerability_evidence_time_bound():
    v = sbom_mod.vulnerability_evidence(
        subject_digest="sha", scanner_id="osv", scanner_version="1",
        db_snapshot="2026-06-01", findings=[], observed_at="2026-01-01",
        expires_at="2026-02-01")
    fs = sbom_mod.validate_vuln_evidence(v, artifact_digest="sha", now=NOW)
    assert any(f.kind == "VULNERABILITY_EVIDENCE_STALE" for f in fs)


# --- CI security ---------------------------------------------------------------------
def test_privileged_untrusted_checkout_detected():
    wf = {"on": "pull_request_target", "permissions": {"contents": "read"},
          "jobs": {"j": {"steps": [
              {"uses": "actions/checkout@abcdef0123456789012345678901234567890123",
               "with": {"ref": "${{ github.event.pull_request.head.sha }}"}}]}}}
    fs = ci_security.workflow_findings(wf, path="wf.yml")
    assert any(f.kind == "DANGEROUS_CI_WORKFLOW" and f.severity == model.P0
               for f in fs)


def test_verified_transformation_resolves_prompt_taint():
    flow = ci_security.analyze_flow(ci_security.taint_flow(
        source_kind="ISSUE_BODY", source_ref="i", sink_kind="AGENT_PROMPT",
        sink_ref="agent",
        sanitization_claims=[{"transform": "strip-to-quoted-data",
                              "verified": True}]))
    assert flow["status"] == "SAFE_TRANSFORMED"
    assert ci_security.flow_findings(flow) == []


def test_scanner_diversity_independent():
    d = sbom_mod.scanner_diversity([
        {"scanner_id": "a", "parser": "p1", "rule_source": "r1",
         "input_representation": "i1"},
        {"scanner_id": "b", "parser": "p2", "rule_source": "r2",
         "input_representation": "i2"}])
    assert d["classification"] == "INDEPENDENT_ENOUGH"
