"""SP0009 mutation campaign — the 32 constitutional mutants (§20).

Each test injects one release-assurance violation and asserts the kernel KILLS
it. These are the regression locks proving the gates are not vacuous: if a
hardening is reverted, the corresponding lock fails. House root causes guarded
throughout: truthy-string coercion (fix: `is True` / literal comparison) and
missing-is-permissive (fix: allowlist + fail-closed).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.release import (model, candidate, gates, evidence, obligations,
                            waivers, attempts, flakes, build as build_mod,
                            artifacts, trust, transparency, sbom as sbom_mod,
                            ci_security, ai_closure, flags, delivery,
                            defeaters, qualify, envelope as envelope_mod,
                            canon, boundary)

ROOT = Path(__file__).resolve().parents[1]
G = "test-genome"
NOW = "2026-07-12"
FUT = "2027-07-12"


def _root(**kw):
    base = dict(trust_root_id="R", version=2, trust_domain="dom-a",
                threshold=1, authorized_signers=["s1"],
                valid_from="2026-01-01", expires_at=FUT)
    base.update(kw)
    return trust.trust_root(**base)


# M1 — truthy-string gate pass
def test_m01_truthy_string_never_passes_gate():
    plan = {"GATE_TENANT_ISOLATION": "REQUIRED"}
    for sneaky in ("true", "pass", "Pass", "PASSED", 1, True):
        v = gates.hard_verdict(plan, {"GATE_TENANT_ISOLATION": sneaky})
        assert not v["qualifiable"], sneaky


# M2 — missing gate treated as PASS
def test_m02_missing_gate_blocks():
    plan = {"GATE_TENANT_ISOLATION": "REQUIRED"}
    v = gates.hard_verdict(plan, {})
    assert not v["qualifiable"]
    assert v["blocking"][0]["reason"] == "MISSING"


# M3 — rerun erases failure
def test_m03_rerun_cannot_erase_failure():
    led = attempts.ExecutionLedger()
    led.record(candidate_genome=G, test_id="t", result="FAIL",
               environment_fingerprint="e")
    led.record(candidate_genome=G, test_id="t", result="PASS",
               environment_fingerprint="e")
    fs = attempts.anti_laundering_findings(led, reported_failures=[],
                                           candidate_genome=G)
    assert any(f.severity == model.P0 for f in fs)


# M4 — stale result reused
def test_m04_stale_result_rejected():
    e = evidence.evidence_record(
        candidate_genome=G, gate_id="GATE_UNIT_TESTS",
        configuration_fingerprint=gates.gate_configuration_fingerprint(
            "GATE_UNIT_TESTS"), environment={}, tool_version="1",
        result="PASS", valid_from="2026-01-01", valid_to="2026-02-01")
    fs = evidence.validate_for_candidate(e, candidate_genome=G,
                                         gate_id="GATE_UNIT_TESTS", now=NOW)
    assert any(f.kind == "GATE_STALE" for f in fs)


# M5 — candidate changed after approval
def test_m05_candidate_change_invalidates_approval():
    rc = candidate.new_candidate("RC", {f: "v" for f in
                                        candidate.GENOME_FIELDS})
    a = waivers.approval(candidate_genome=rc["candidate_genome"],
                         approver="bob", scope="release")
    mutated_genome = candidate.candidate_genome(
        {**{f: "v" for f in candidate.GENOME_FIELDS},
         "source_commit": "changed"})
    fs = waivers.validate_approval(a, candidate_genome=mutated_genome,
                                   author="alice", now=NOW)
    assert any(f.severity == model.P0 for f in fs)


# M6 — artifact digest omitted
def test_m06_artifact_requires_digest():
    with pytest.raises(ValueError):
        artifacts.artifact_manifest(candidate_genome=G, artifact_type="X",
                                    digest="", size_bytes=0, build_ref="b")


# M7 — different artifact marked promotable
def test_m07_promote_different_bytes_rejected():
    fs = artifacts.promote_same_bytes("sha-verified", "sha-other", "A")
    assert any(f.kind == "ARTIFACT_DIGEST_MISMATCH"
               and f.severity == model.P0 for f in fs)


# M8 — provenance subject mismatch hidden
def test_m08_provenance_subject_mismatch_detected():
    att = trust.attestation(subject_digest="sha-A",
                            predicate_type="finalis/release-evidence/v1",
                            predicate={}, signer="s1", signing_time=NOW,
                            candidate_genome=G)
    fs = trust.verify_attestation(att, artifact_digest="sha-B",
                                  candidate_genome=G, roots=[_root()],
                                  now=NOW)
    assert any(f.kind == "PROVENANCE_SUBJECT_MISMATCH" for f in fs)


# M9 — unknown signer accepted
def test_m09_unknown_signer_rejected():
    att = trust.attestation(subject_digest="sha", predicate_type=
                            "finalis/release-evidence/v1", predicate={},
                            signer="mallory", signing_time=NOW,
                            candidate_genome=G)
    fs = trust.verify_attestation(att, artifact_digest="sha",
                                  candidate_genome=G, roots=[_root()],
                                  now=NOW)
    assert any(f.kind == "ATTESTATION_INVALID" for f in fs)


# M10 — expired root accepted
def test_m10_expired_root_rejected():
    fs = trust.validate_root(_root(expires_at="2026-01-02"), now=NOW)
    assert any(f.kind == "TRUST_ROOT_EXPIRED" and f.severity == model.P0
               for f in fs)


# M11 — root version rollback accepted
def test_m11_root_rollback_detected():
    fs = trust.validate_root(_root(version=1), now=NOW,
                             known_versions={"R": 3})
    assert any(f.kind == "TRUST_ROOT_ROLLBACK_DETECTED" for f in fs)


# M12 — duplicate signatures counted as quorum
def test_m12_duplicate_signatures_not_quorum():
    r = _root(threshold=2, authorized_signers=["s1", "s2"])
    q = trust.threshold_quorum([{"signer": "s1"}, {"signer": "s1"}], [r],
                               now=NOW)
    assert not q["quorum"]


# M13 — transparency receipt omitted
def test_m13_receipt_required_by_policy():
    fs = transparency.policy_findings([], required=True, subject_digest="sha")
    assert any(f.kind == "TRANSPARENCY_RECEIPT_MISSING"
               and f.severity == model.P0 for f in fs)


# M14 — wrong SBOM accepted
def test_m14_wrong_artifact_sbom_rejected():
    s = sbom_mod.sbom(subject_digest="sha-A", components=[],
                      completeness="COMPLETE")
    fs = sbom_mod.validate_sbom(s, artifact_digest="sha-B")
    assert any(f.kind == "SBOM_SUBJECT_MISMATCH" and f.severity == model.P0
               for f in fs)


# M15 — incomplete SBOM labeled complete
def test_m15_sbom_completeness_explicit():
    with pytest.raises(ValueError):
        sbom_mod.sbom(subject_digest="s", components=[],
                      completeness="MOSTLY_DONE")


# M16 — unsupported VEX accepted
def test_m16_vex_not_affected_needs_evidence():
    c = sbom_mod.vex_claim(subject_digest="s", vulnerability_id="CVE-1",
                           status="not_affected", justification="",
                           evidence_refs=[], author="a", observed_at=NOW,
                           expires_at=FUT)
    fs = sbom_mod.validate_vex(c, artifact_digest="s", now=NOW)
    assert any(f.kind == "VEX_EVIDENCE_INSUFFICIENT"
               and f.severity == model.P0 for f in fs)


# M17 — unpinned dependency accepted
def test_m17_unpinned_action_flagged():
    wf = {"permissions": {"contents": "read"},
          "jobs": {"j": {"steps": [{"uses": "actions/checkout@v4"}]}}}
    fs = ci_security.workflow_findings(wf, path="wf.yml")
    assert any(f.kind == "DEPENDENCY_NOT_PINNED" for f in fs)


# M18 — overprivileged token accepted
def test_m18_missing_permissions_flagged():
    fs = ci_security.workflow_findings({"jobs": {}}, path="wf.yml")
    assert any(f.kind == "CI_TOKEN_OVERPRIVILEGED" for f in fs)


# M19 — PR text injected into shell
def test_m19_pr_body_to_shell_detected():
    wf = {"permissions": {"contents": "read"},
          "jobs": {"j": {"steps": [
              {"run": 'echo "${{ github.event.pull_request.body }}"'}]}}}
    fs = ci_security.workflow_findings(wf, path="wf.yml")
    assert any(f.kind == "DANGEROUS_CI_WORKFLOW" and f.severity == model.P0
               for f in fs)


# M20 — PR text injected into agent prompt
def test_m20_pr_body_to_prompt_unresolved_blocks():
    flow = ci_security.analyze_flow(ci_security.taint_flow(
        source_kind="PR_BODY", source_ref="pr-1", sink_kind="AGENT_PROMPT",
        sink_ref="agent"))
    fs = ci_security.flow_findings(flow)
    assert any(f.kind == "CI_TAINT_UNRESOLVED" for f in fs)
    # comment -> prompt likewise
    flow2 = ci_security.analyze_flow(ci_security.taint_flow(
        source_kind="PR_COMMENT", source_ref="c-1", sink_kind="SHELL",
        sink_ref="run"))
    fs2 = ci_security.flow_findings(flow2)
    assert any(f.severity == model.P0 for f in fs2)


# M21 — model output treated as approval
def test_m21_model_output_cannot_approve():
    flow = ci_security.analyze_flow(ci_security.taint_flow(
        source_kind="MODEL_OUTPUT", source_ref="llm",
        sink_kind="RELEASE_DECISION", sink_ref="qualify",
        sanitization_claims=[{"transform": "reviewed", "verified": True}]))
    assert flow["status"] == "BLOCKED"     # even 'verified' cannot authorize
    fs = ci_security.flow_findings(flow)
    assert any(f.kind == "EXTERNAL_CONTENT_AUTHORITY_REJECTED"
               and f.severity == model.P0 for f in fs)


# M22 — scanner shared parser hidden
def test_m22_scanner_common_mode_visible():
    d = sbom_mod.scanner_diversity([
        {"scanner_id": "a", "parser": "libP", "rule_source": "R1",
         "input_representation": "sarif"},
        {"scanner_id": "b", "parser": "libP", "rule_source": "R1",
         "input_representation": "sarif"}])
    assert d["classification"] == "COMMON_MODE_DOMINATED"
    assert d["shared"]


# M23 — flake failure removed
def test_m23_flake_not_reproduced_stays_visible():
    reg = flakes.observe([], test_id="t", env_fingerprint="e", result="PASS")
    cls = flakes.classify(reg, test_id="t")
    assert cls["classification"] == "NOT_REPRODUCED"   # recorded, not deleted


# M24 — critical test quarantined
def test_m24_critical_quarantine_blocked():
    q = flakes.quarantine(test_id="test_rbac_authority", owner="o",
                          expires_at=FUT,
                          equivalent_control={"verified": "true"})   # string!
    fs = flakes.validate_quarantine(q)
    assert any(f.kind == "CRITICAL_TEST_QUARANTINE_BLOCKED" for f in fs)


# M25 — provider accounts merged
def test_m25_provider_account_merge_detected():
    a = ai_closure.ai_release_closure(
        candidate_genome=G, model_identity={"name": "m", "version": "1"},
        provider_identity={"provider": "p1"}, provider_account_ref="acct-1",
        fallback_chain=["x"], prompt_hashes=["h"], skill_hashes=["h"],
        tool_contract_hashes=["h"], retrieval_configuration_hash="h",
        policy_pack_hash="h", router_hash="h", safety_configuration_hash="h",
        generation_parameters={"t": 0}, evaluation_set_hash="h",
        known_limitations=[])
    b = ai_closure.ai_release_closure(
        candidate_genome=G, model_identity={"name": "m2", "version": "1"},
        provider_identity={"provider": "p2"}, provider_account_ref="acct-1",
        fallback_chain=["x"], prompt_hashes=["h"], skill_hashes=["h"],
        tool_contract_hashes=["h"], retrieval_configuration_hash="h",
        policy_pack_hash="h", router_hash="h", safety_configuration_hash="h",
        generation_parameters={"t": 0}, evaluation_set_hash="h",
        known_limitations=[])
    fs = ai_closure.account_separation_findings([a, b])
    assert fs


# M26 — fallback chain omitted / changed silently
def test_m26_fallback_chain_is_material():
    kw = dict(candidate_genome=G, model_identity={"name": "m", "version": "1"},
              provider_identity={"provider": "p"},
              provider_account_ref="acct", prompt_hashes=["h"],
              skill_hashes=["h"], tool_contract_hashes=["h"],
              retrieval_configuration_hash="h", policy_pack_hash="h",
              router_hash="h", safety_configuration_hash="h",
              generation_parameters={"t": 0}, evaluation_set_hash="h",
              known_limitations=[])
    a = ai_closure.ai_release_closure(fallback_chain=["p1", "p2"], **kw)
    b = ai_closure.ai_release_closure(fallback_chain=["p2", "p1"], **kw)
    assert ai_closure.material_change(a, b)     # ORDER is material
    c = ai_closure.ai_release_closure(fallback_chain=[], **kw)
    assert c["closure_status"] == "INCOMPLETE"
    assert any(f.severity == model.P0
               for f in ai_closure.closure_findings(c, protected=True))


# M27 — feature flag widens authority
def test_m27_flag_authority_widening_rejected():
    f = flags.flag(flag_id="F", owner="o", scope="tenant-1",
                   flag_type="release", safe_default=False, expires_at=FUT,
                   widens_authority=True)
    fs = flags.validate_flag(f, now=NOW)
    assert any(f2.kind == "FEATURE_FLAG_AUTHORITY_VIOLATION"
               and f2.severity == model.P0 for f2 in fs)
    # missing flag data fails SAFE
    f2 = flags.flag(flag_id="F2", owner="o", scope="s", flag_type="r",
                    safe_default=False, expires_at=FUT)
    ev = flags.evaluate(f2, requested_state="on")     # not a bool
    assert ev["value"] is False and ev["fail_safe_applied"]


# M28 — emergency path skips audit (candidate transitions must be legal)
def test_m28_no_transition_skips_verification():
    rc = candidate.new_candidate("RC", {f: "v" for f in
                                        candidate.GENOME_FIELDS})
    with pytest.raises(ValueError):
        candidate.transition(rc, "QUALIFIED")    # DRAFT -> QUALIFIED illegal


# M29 — open DoD obligation ignored
def test_m29_open_obligation_blocks_qualification():
    q = qualify.qualify(
        gate_verdict={"qualifiable": True},
        dod_closure={"done": False, "open_hard": ["OB-SAFETY"]},
        unknown_budget={"hard_scope_count": 0},
        artifact_closures=[{"closure_status": "COMPLETE"}],
        open_defeaters=[])
    assert not q["qualifiable"]


# M30 — blocking defeater ignored
def test_m30_blocking_defeater_suspends():
    rc = candidate.new_candidate("RC", {f: "v" for f in
                                        candidate.GENOME_FIELDS})
    for s in ("CLASSIFIED", "IMPACT_ANALYZED", "SLICE_CLOSED",
              "GATES_PLANNED", "VERIFYING", "QUALIFIED"):
        rc = candidate.transition(rc, s)
    d = defeaters.validate_defeater(defeaters.defeater(
        candidate_genome=rc["candidate_genome"],
        defeater_type="TRUST_ROOT_REVOKED",
        claim_invalidated="attestation quorum",
        evidence_refs=["revocation-record"]))
    after, fs = defeaters.apply_to_candidate(rc, [d])
    assert after["status"] == "SUSPENDED_BY_DEFEATER"
    assert any(f.kind == "DEFEATER_BLOCKING" for f in fs)
    assert defeaters.historical_qualified_visible(after)
    req = defeaters.require_requalification(after)
    assert req["status"] == "REQUALIFICATION_REQUIRED"


# M31 — proof hash omits failure ledger
def test_m31_envelope_missing_ledger_hash_rejected():
    env = envelope_mod.release_envelope(
        {f: "h" for f in envelope_mod.HASH_FIELDS})
    stripped = {k: v for k, v in env.items()
                if k != "test_execution_ledger_hash"}
    stripped["content_digest"] = canon.core_hash(
        {k: stripped[k] for k in stripped if k != "content_digest"})
    fs = envelope_mod.validate_envelope(stripped)
    assert any("test_execution_ledger_hash" in str(f.details)
               and f.severity == model.P0 for f in fs)
    # and altering the ledger hash changes the digest (tamper evidence)
    tampered = dict(env, test_execution_ledger_hash="other")
    fs2 = envelope_mod.validate_envelope(tampered)
    assert any(f.kind == "RELEASE_PROOF_MISMATCH" for f in fs2)


# M32 — AI closure change does not change candidate
def test_m32_ai_closure_change_changes_candidate():
    base = {f: "v" for f in candidate.GENOME_FIELDS}
    g1 = candidate.candidate_genome(base)
    g2 = candidate.candidate_genome(
        {**base, "ai_release_closure_hash": "different"})
    assert g1 != g2


# supplementary locks — anytime-valid delivery + SRM + hard abort
def test_supp_sequential_policy_must_be_predeclared():
    with pytest.raises(ValueError):
        delivery.sequential_verdict([0, 1], policy={"alpha": 0.05,
                                                    "p0": 0.01, "p1": 0.05})


def test_supp_eprocess_crosses_on_bad_stream():
    policy = {"predeclared": True, "alpha": 0.05, "p0": 0.01, "p1": 0.2}
    v = delivery.sequential_verdict([1] * 3, policy=policy)
    assert v["verdict"] == "ABORT" and v["anytime_valid"]
    v2 = delivery.sequential_verdict([0] * 10, policy=policy)
    assert v2["verdict"] == "CONTINUE"


def test_supp_srm_blocks_interpretation():
    chk = delivery.sample_ratio_check(expected_ratio=0.5, treatment_n=900,
                                      control_n=100)
    assert chk["blocks"]
    assert any(f.severity == model.P0
               for f in delivery.srm_findings(chk, "canary"))


def test_supp_hard_abort_immediate():
    r = delivery.hard_abort(["SAFETY_VIOLATION"])
    assert r["abort"] and r["immediate"]


def test_supp_sp0011_fabrication_rejected():
    bad = {"qualification": "PENDING_SP0011", "evidence": {"score": 1000}}
    fs = ai_closure.validate_sp0011(bad)
    assert any(f.kind == "SP0011_EVIDENCE_FABRICATION_REJECTED"
               and f.severity == model.P0 for f in fs)


# --- red-team regression locks (SWARM-O escapes #1-#8) -----------------------------
# R1 — a stale / cross-candidate waiver never passes a hard gate
def test_r1_stale_cross_candidate_waiver_rejected():
    plan = {"GATE_SUPPLY_CHAIN": "REQUIRED"}
    # expired + wrong genome, but status ACTIVE
    w = {"GATE_SUPPLY_CHAIN": {"status": "ACTIVE",
                               "candidate_genome": "OTHER",
                               "expires_at": "2000-01-01"}}
    v = gates.hard_verdict(plan, {"GATE_SUPPLY_CHAIN": "WAIVED"}, waivers=w,
                           candidate_genome="THIS", now=NOW)
    assert not v["qualifiable"]
    # even a valid-status waiver with no now/genome context fails closed
    v2 = gates.hard_verdict(plan, {"GATE_SUPPLY_CHAIN": "WAIVED"},
                            waivers={"GATE_SUPPLY_CHAIN":
                                     {"status": "ACTIVE"}})
    assert not v2["qualifiable"]
    # a fully valid waiver passes
    good = {"GATE_SUPPLY_CHAIN": {"status": "ACTIVE",
                                  "candidate_genome": "THIS",
                                  "expires_at": FUT}}
    v3 = gates.hard_verdict(plan, {"GATE_SUPPLY_CHAIN": "WAIVED"},
                            waivers=good, candidate_genome="THIS", now=NOW)
    assert v3["qualifiable"]


# R2 — an illegally-WAIVED non-waivable obligation cannot qualify
def test_r2_invalid_waiver_blocks_qualification():
    q = qualify.qualify(
        gate_verdict={"qualifiable": True},
        dod_closure={"done": False, "open_hard": [],
                     "invalid_waivers": ["OB-AUTHORITY"]},
        unknown_budget={"hard_scope_count": 0},
        artifact_closures=[{"closure_status": "COMPLETE"}],
        open_defeaters=[])
    assert not q["qualifiable"]


# R3 — an OMITTED ledger hash (ABSENT sentinel) is rejected
def test_r3_absent_ledger_hash_rejected():
    hashes = {f: "h" for f in envelope_mod.HASH_FIELDS}
    del hashes["test_execution_ledger_hash"]     # omit -> ABSENT sentinel
    env = envelope_mod.release_envelope(hashes)
    assert env["test_execution_ledger_hash"] == "ABSENT"
    fs = envelope_mod.validate_envelope(env)
    assert any(f.kind == "RELEASE_PROOF_MISMATCH" and f.severity == model.P0
               for f in fs)


# R4 — boundary import allowlist has no os exemption
def test_r4_boundary_rejects_os_import(tmp_path):
    pkg = tmp_path / "tools" / "release"
    pkg.mkdir(parents=True)
    (pkg / "evil.py").write_text("import os\nos.execlp('sh', 'sh')\n")
    fs = boundary.check_no_external_effect(tmp_path)
    assert any(f.kind == "BOUNDARY_VIOLATION" and f.severity == model.P0
               for f in fs)


# R6 — only an ACTIVE trust root authorizes; SUPERSEDED/ROTATING rejected
def test_r6_non_active_root_rejected():
    for status in ("SUPERSEDED", "ROTATING", "EXPIRED", "REVOKED"):
        r = _root()
        r["status"] = status
        fs = trust.validate_root(r, now=NOW)
        assert any(f.kind == "TRUST_ROOT_INVALID" for f in fs), status


# R7 — single dangerous write scope flagged; broad untrusted context caught
def test_r7_single_write_scope_and_broad_context():
    wf = {"permissions": {"id-token": "write"}, "jobs": {}}
    fs = ci_security.workflow_findings(wf, path="wf.yml")
    assert any(f.kind == "CI_TOKEN_OVERPRIVILEGED" for f in fs)
    wf2 = {"permissions": {"contents": "read"},
           "jobs": {"j": {"steps": [
               {"run": 'echo ${{ github.event.pull_request.head.repo.'
                       'description }}'}]}}}
    fs2 = ci_security.workflow_findings(wf2, path="wf.yml")
    assert any(f.kind == "DANGEROUS_CI_WORKFLOW" and f.severity == model.P0
               for f in fs2)


# R8 — resume requires a PAUSED candidate (no illegal jump to VERIFYING)
def test_r8_resume_requires_paused():
    rc = candidate.new_candidate("RC", {f: "v" for f in
                                        candidate.GENOME_FIELDS})
    with pytest.raises(ValueError):
        candidate.resume(rc, evidence_records=[], now=NOW)


def test_r_boundary_and_trust_imports_available():
    from tools.release import boundary as _b, trust as _t   # noqa
    assert _b and _t
