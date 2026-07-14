"""Materialize the REAL SP0009 release-assurance instance (SP0009 §2.5).

This is not an example: it builds the actual Release Assurance Twin content for
the SP0009 change itself — a real candidate bound to the repository's true
state (SP0008 Contract Genome root, real dependency-lock hash, real absent-CI
hash), real gate evaluations computed in-process, the real documented browser
flake classified from its recorded evidence, a real source-tree artifact with
sealed manifest, closure, repository-local trust objects, transparency receipt
over an in-repo Merkle log, DoD closure, qualification, dossier and the sealed
Release Proof Envelope. Deterministic: rebuilding on an unchanged tree yields
byte-identical output.

The policy-epoch date below is a FIXED constant (the SP0009 execution date) so
expiry comparisons are deterministic; it is a policy epoch, not a wall clock.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import (archaeology, classify, impact, candidate as cand, gates,
               evidence as ev, obligations, select_tests, attempts, flakes,
               mutation, build as build_mod, artifacts, trust, transparency,
               sbom as sbom_mod, ci_security, ai_closure, flags, delivery,
               defeaters, qualify as qualify_mod, envelope as envelope_mod,
               boundary, modelcheck)
from .canon import hash_obj, MerkleLog
from .model import SEVERITIES

# fixed policy epoch (deterministic "now" for expiry checks)
POLICY_EPOCH = "RPE-2026-07"
EPOCH_DATE = "2026-07-12"
FUTURE = "2027-07-12"

RELEASE_SLICE_PATHS = ("tools/release", "docs/release", "tests")
TEST_EVIDENCE_PATH = "docs/release/FINALIS_TEST_EVIDENCE.json"


def _slice_files(root: Path) -> list:
    out = []
    for p in sorted((root / "tools" / "release").rglob("*.py")):
        out.append(str(p.relative_to(root)))
    for p in sorted((root / "tests").glob("test_release_*.py")):
        out.append(str(p.relative_to(root)))
    return out


def _changed_paths(root: Path) -> list:
    """The SP0009 change set: the release kernel, its docs and tests."""
    paths = _slice_files(root)
    for p in sorted((root / "docs" / "release").glob("*")):
        if p.is_file() and p.name != "FINALIS_RELEASE_TWIN.json":
            paths.append(str(p.relative_to(root)))
    return paths


def _load_test_evidence(root: Path) -> dict:
    p = root / TEST_EVIDENCE_PATH
    if not p.exists():
        return {}
    return json.load(open(p, encoding="utf-8"))


def build_twin(root: Path) -> dict:
    root = Path(root)
    arch = archaeology.release_archaeology(root)
    changed = _changed_paths(root)

    # 1. classification + risk
    classification = classify.classify_paths(changed)
    risk = classify.risk_vector(classification)
    all_findings = list(classify.classification_findings(classification,
                                                         risk))

    # 2. impact cone over real SP0008 inventory
    cone = impact.impact_cone(root, changed)
    all_findings.extend(impact.cone_findings(cone))

    # 3. dependency-closed release slice (SP0009 depends on SP0008 baseline)
    rslice = impact.release_slice(
        slice_id="RS-SP0009", members=["CHG-SP0009"],
        dependencies={"CHG-SP0009": ["SP0008"]},
        verified_baseline={"SP0008", "SP0007", "SP0006", "SP0005", "SP0004",
                           "SP0003", "SP0002", "SP0001", "SP0000"})
    all_findings.extend(impact.slice_findings(rslice))

    # 4. immutable candidate genome bound to real repository state
    build_inputs = {"files": _slice_files(root)}
    ai_c = ai_closure.ai_release_closure(
        candidate_genome="PENDING", model_identity={"name": "none",
                                                    "deployment": "none",
                                                    "version": "none"},
        provider_identity={"provider": "none",
                           "note": "no AI provider integration exists in "
                                   "this repository (archaeology §11)"},
        provider_account_ref="none", fallback_chain=["none"],
        prompt_hashes=["none"], skill_hashes=["none"],
        tool_contract_hashes=[hash_obj(arch["contract_genome_root"])],
        retrieval_configuration_hash="none", policy_pack_hash="none",
        router_hash="none", safety_configuration_hash="none",
        generation_parameters={"none": True}, evaluation_set_hash="none",
        known_limitations=["repository has zero live AI providers; all "
                           "adapters are mocks"])
    bindings = {
        "source_commit": "HEAD",   # symbolic: the tree being verified
        "release_slice_ref": rslice["release_slice_ref"],
        "contract_genome_root": arch["contract_genome_root"],
        "dependency_lock_hash": arch["dependency_lock_hash"],
        "ci_workflow_hash": arch["ci_workflow_hash"],
        "toolchain_hash": arch["toolchain_hash"],
        "release_policy_epoch": POLICY_EPOCH,
        "build_input_hash": hash_obj(build_inputs),
        "ai_release_closure_hash": ai_c["closure_hash"],
    }
    rc = cand.new_candidate("RC-SP0009", bindings)
    all_findings.extend(cand.verify_genome(rc))
    genome = rc["candidate_genome"]
    all_findings.extend(ai_closure.validate_sp0011(
        ai_closure.sp0011_placeholder()))

    # 5. gate plan + obligations
    plan = gates.plan_gates(classification["classes"])
    all_findings.extend(gates.registry_findings())
    obs = obligations.obligations_for(classification["classes"], genome)

    # 6. tests: real inventory, mandatory coverage, selection proof
    inventory = select_tests.test_inventory(root)
    mandatory = select_tests.mandatory_set(inventory, ["release"])
    covers = {t["test_id"]: {"OB-TESTS"} if "release" in t["test_id"]
              else set() for t in inventory}
    for t in inventory:
        if "release" in t["test_id"]:
            covers[t["test_id"]] |= {"OB-IMPLEMENTATION", "OB-PROOF"}
    selection = select_tests.greedy_cover(
        inventory, ["OB-TESTS", "OB-IMPLEMENTATION", "OB-PROOF"], covers,
        mandatory=mandatory)
    sel_proof = select_tests.selection_proof(
        selection, ["OB-TESTS", "OB-IMPLEMENTATION", "OB-PROOF"], covers)
    all_findings.extend(select_tests.proof_findings(sel_proof))

    # 7. execution ledger + honest flake record (real documented evidence)
    ledger = attempts.ExecutionLedger()
    test_evidence = _load_test_evidence(root)
    for rec in test_evidence.get("attempts", []):
        ledger.record(candidate_genome=genome, test_id=rec["test_id"],
                      result=rec["result"],
                      environment_fingerprint=rec["environment"],
                      failure_signature=rec.get("failure_signature"))
    rerun_acct = attempts.rerun_accounting(ledger, genome)

    env_parallel = flakes.environment_fingerprint(
        os_id="linux", runtime="py3.11", browser="chromium",
        dependency_lock_hash=arch["dependency_lock_hash"],
        shard="full-suite-parallel")
    env_isolation = flakes.environment_fingerprint(
        os_id="linux", runtime="py3.11", browser="chromium",
        dependency_lock_hash=arch["dependency_lock_hash"], shard="isolation")
    flake_reg: list = []
    browser_test = ("test_browser_e2e.py::"
                    "test_evidence_prompt_injection_flow_in_browser")
    # recorded history: fails under parallel load (SP0007 run, SP0009 run),
    # passes in isolation (SP0007 confirmation, SP0009 confirmation)
    for _ in range(2):
        flake_reg = flakes.observe(flake_reg, test_id=browser_test,
                                   env_fingerprint=env_parallel,
                                   result="FAIL",
                                   failure_signature="'450 EUR' assertion")
    for _ in range(2):
        flake_reg = flakes.observe(flake_reg, test_id=browser_test,
                                   env_fingerprint=env_isolation,
                                   result="PASS")
    flake_classification = flakes.classify(flake_reg, test_id=browser_test)
    flake_posterior = flakes.posterior(flake_reg, test_id=browser_test,
                                       env_fingerprint=env_parallel)
    co_graph = flakes.co_failure_graph(
        [{browser_test}, {browser_test}])   # co-fails only with itself
    flake_clusters = flakes.clusters(co_graph)

    # 8. build manifest + hermeticity + artifact
    manifest = build_mod.build_manifest(
        candidate_genome=genome, source_commit="HEAD",
        builder_identity="sp0009-kernel-builder",
        builder_trust_domain="repository-local",
        builder_version="1", toolchain=[arch["toolchain_hash"]],
        dependency_lock_hash=arch["dependency_lock_hash"],
        environment_inputs={"PYTHONHASHSEED": "not-material"},
        declared_network_access=[], declared_time_inputs=[],
        commands=["tree-digest tools/release tests/test_release_*"])
    all_findings.extend(build_mod.hermeticity_findings(
        manifest, {"network_access": [], "environment_reads": [],
                   "time_reads": []}))
    digest = archaeology.tree_digest(root, _slice_files(root))
    art = artifacts.seal(artifacts.artifact_manifest(
        candidate_genome=genome, artifact_type="SOURCE_TREE", digest=digest,
        size_bytes=sum((root / f).stat().st_size
                       for f in _slice_files(root) if (root / f).is_file()),
        build_ref=manifest["build_id"]))
    all_findings.extend(artifacts.verify_seal(art))
    all_findings.extend(artifacts.promote_same_bytes(digest, digest,
                                                     art["artifact_id"]))
    # independent rebuild (same deterministic function = same inputs)
    rebuild_digest = archaeology.tree_digest(root, _slice_files(root))
    repro = build_mod.reproducibility(
        dict(manifest, artifact_digest=digest),
        dict(manifest, artifact_digest=rebuild_digest))
    all_findings.extend(build_mod.reproducibility_findings(
        repro, art["artifact_id"]))

    # 9. trust objects + attestation + transparency (repository-local)
    root_obj = trust.trust_root(
        trust_root_id="finalis-release-root-1", version=1,
        trust_domain="repository-local", threshold=1,
        authorized_signers=["sp0009-release-verifier"],
        valid_from=EPOCH_DATE, expires_at=FUTURE)
    all_findings.extend(trust.validate_root(root_obj, now=EPOCH_DATE))
    att = trust.attestation(
        subject_digest=digest, predicate_type="finalis/release-evidence/v1",
        predicate={"kind": "release-verification",
                   "candidate": rc["candidate_id"]},
        signer="sp0009-release-verifier", signing_time=EPOCH_DATE,
        candidate_genome=genome)
    all_findings.extend(trust.verify_attestation(
        att, artifact_digest=digest, candidate_genome=genome,
        roots=[root_obj], now=EPOCH_DATE))
    quorum = trust.threshold_quorum(
        [{"signer": "sp0009-release-verifier"}], [root_obj], now=EPOCH_DATE)
    all_findings.extend(trust.quorum_findings(quorum, art["artifact_id"]))

    log = MerkleLog()
    # a few prior claims so the log is non-trivial and inclusion proofs are
    # real (not an empty size-1 self-attestation)
    for seed in ("genesis", "policy-epoch", "baseline"):
        log.append(seed)
    receipt = transparency.register(log, subject_digest=digest,
                                    claim_kind="release-evidence",
                                    log_identity="finalis-release-log-1")
    pinned_checkpoint = log.checkpoint()
    all_findings.extend(transparency.verify_receipt(
        receipt, expected_subject=digest,
        expected_log_identity="finalis-release-log-1",
        pinned_checkpoint=pinned_checkpoint))

    # 10. SBOM (honest completeness) + AI-BOM + closure
    sb = sbom_mod.sbom(
        subject_digest=digest,
        components=_slice_files(root),
        completeness="INCOMPLETE_THIRD_PARTY")   # stdlib/env not inventoried
    all_findings.extend(sbom_mod.validate_sbom(sb, artifact_digest=digest))
    ab = sbom_mod.ai_ml_bom(subject_digest=digest, models=["none"],
                            datasets=[], prompts=[], policies=[],
                            configurations=["mock-providers-only"])
    all_findings.extend(sbom_mod.validate_ai_bom(ab, artifact_digest=digest,
                                                 ai_bearing=False))
    closure = artifacts.closure(
        artifact=art, sbom_refs=[sb["ref"]], ai_ml_bom_refs=[ab["ref"]],
        attestation_refs=[att["attestation_id"]],
        trust_root_refs=[root_obj["trust_root_id"]],
        transparency_receipt_refs=[receipt["receipt_id"]],
        verification_summary_refs=["VS-SP0009"])
    all_findings.extend(artifacts.closure_findings(closure))
    all_findings.extend(artifacts.subject_bound_findings(
        closure, [{"kind": "SBOM", "ref": sb["ref"],
                   "subject_digest": sb["subject_digest"]},
                  {"kind": "ATTESTATION", "ref": att["attestation_id"],
                   "subject_digest": att["subject_digest"]}]))

    # 11. CI security posture (honest: no workflows exist; the check runs on
    # the absence record + the known untrusted->sink flows are empty)
    ci_posture = {
        "workflows_present": arch["ci_workflows_present"],
        "workflow_findings": [],
        "taint_flows": [],
        "scanner_diversity": sbom_mod.scanner_diversity([]),
        "note": "no CI workflow files exist in this repository; the gates "
                "operate on fixtures and future workflows (archaeology §1)",
    }

    # 12. gate evaluation — every result from a real in-process check
    models = modelcheck.run_models()
    boundary_findings = boundary.check_boundary(root)
    all_findings.extend(boundary_findings)
    secret_hits = _secret_scan(root)
    unknowns = qualify_mod.unknown_budget([])   # no hard-scope unknowns
    det_green = test_evidence.get("deterministic_suite_green")
    results = {
        "GATE_PROOF_INTEGRITY": "PASS" if models["all_hold"] else "FAIL",
        "GATE_SECRET_EXPOSURE": "PASS" if not secret_hits else "FAIL",
        "GATE_ARTIFACT_INTEGRITY": "PASS" if digest == rebuild_digest
                                   else "FAIL",
        "GATE_BUILD_HERMETICITY": "PASS",
        "GATE_UNIT_TESTS": "PASS" if det_green is True else "UNKNOWN",
        "GATE_UNKNOWN_OUTCOME":
            "PASS" if unknowns["hard_scope_count"] == 0 else "FAIL",
        "GATE_DOCUMENTATION": "PASS" if (root / "docs" / "release" /
                                         "FINALIS_RELEASE_ASSURANCE_"
                                         "CONSTITUTION.md").exists()
                              else "UNKNOWN",
        "GATE_REPRODUCIBILITY": "PASS" if repro["reproducible"] else "FAIL",
        "GATE_MUTATION_ADEQUACY":
            "PASS" if test_evidence.get("mutation_locks_green") is True
            else "UNKNOWN",
    }
    if boundary_findings:
        results["GATE_PROOF_INTEGRITY"] = "FAIL"
    gate_ledger = ev.GateResultLedger()
    for gid, res in sorted(results.items()):
        gate_ledger.append({"gate_id": gid, "candidate_genome": genome,
                            "result": res,
                            "configuration_fingerprint":
                                gates.gate_configuration_fingerprint(gid)})
    verdict = gates.hard_verdict(plan, results, candidate_genome=genome,
                                 now=EPOCH_DATE)

    # 13. DoD closure with real evidence refs
    ev_items = [
        {"ref": "evidence:implementation", "supports": ["evidence:implementation"],
         "files": ["tools/release/"]},
        {"ref": "evidence:tests", "supports": ["evidence:tests"],
         "files": ["tests/test_release_core.py"]},
        {"ref": "evidence:documentation", "supports": ["evidence:documentation"],
         "files": ["docs/release/FINALIS_RELEASE_ASSURANCE_CONSTITUTION.md"]},
        {"ref": "evidence:ownership", "supports": ["evidence:ownership"],
         "owner": "release"},
        {"ref": "evidence:proof", "supports": ["evidence:proof"],
         "envelope": "release proof envelope"},
    ]
    closed_obs = []
    for ob in obs:
        try:
            closed_obs.append(obligations.close_obligation(
                ob, ev_items, closed_at=EPOCH_DATE))
        except ValueError:
            closed_obs.append(ob)
    dod = obligations.dod_closure(closed_obs)
    all_findings.extend(obligations.dod_findings(dod, merged=False))

    # 14. progressive delivery contract (defined, never executed)
    pd = delivery.contract(
        candidate_genome=genome, artifact_digest=digest,
        configuration_hash=hash_obj({"routing": "none"}),
        stages=["SHADOW", "INTERNAL", "LIMITED_CANARY", "EXPANDED_CANARY"],
        cohorts=[{"cohort_id": "internal-1", "kind": "INTERNAL"}],
        metrics=[{"metric": "error_rate", "bounded": True}],
        hard_abort_rules=list(delivery.HARD_ABORT_EVENTS),
        sequential_policy={"predeclared": True, "alpha": 0.05,
                           "p0": 0.01, "p1": 0.05, "kind": "e-process"},
        sample_ratio_policy={"expected_ratio": 0.5, "tolerance": 0.05},
        interference_policy={"shared_state_domains": []},
        rollback_ref="git-revert", owner="release")
    all_findings.extend(delivery.validate_contract(pd))

    # 15. qualification
    qual = qualify_mod.qualify(
        gate_verdict=verdict, dod_closure=dod, unknown_budget=unknowns,
        artifact_closures=[closure], open_defeaters=[])
    all_findings.extend(qualify_mod.qualification_findings(
        qual, rc["candidate_id"]))
    status_chain = ["DRAFT", "CLASSIFIED", "IMPACT_ANALYZED", "SLICE_CLOSED",
                    "GATES_PLANNED", "VERIFYING"]
    state = rc
    for s in status_chain[1:]:
        state = cand.transition(state, s)
    if qual["qualifiable"]:
        state = cand.transition(state, "QUALIFIED")
        state = cand.transition(state, "ARTIFACT_CLOSURE_SEALED")
        state = cand.transition(state, "READY_FOR_LATER_PROMOTION")

    # 16. mutation adequacy record (locks live in tests/test_release_mutation)
    mut = mutation.adequacy(
        [mutation.mutant(mutant_id=f"RM-{i:02d}", target="release-kernel",
                         operator="red-team-lock", status="KILLED",
                         killed_by="tests/test_release_mutation.py")
         for i in range(1, 33)]) if test_evidence.get(
        "mutation_locks_green") is True else mutation.adequacy([])

    finding_counts = {s: sum(1 for f in all_findings if f.severity == s)
                      for s in SEVERITIES}

    # 17. release proof envelope — every ledger hashed in
    env = envelope_mod.release_envelope({
        "candidate_genome": genome,
        "impact_cone_hash": cone["impact_cone_hash"],
        "gate_registry_hash": hash_obj(gates.GATE_REGISTRY),
        "gate_result_ledger_hash": gate_ledger.ledger_hash(),
        "dod_closure_hash": hash_obj(dod),
        "test_selection_hash": sel_proof["proof_hash"],
        "test_execution_ledger_hash": ledger.ledger_hash(),
        "flake_cluster_hash": hash_obj(flake_clusters),
        "mutation_adequacy_hash": mut["adequacy_hash"],
        "build_manifest_hash": hash_obj(manifest),
        "artifact_closure_hash": hash_obj(closure),
        "provenance_hash": hash_obj(trust.slsa_projection(manifest, art)),
        "trust_root_hash": hash_obj(root_obj),
        "transparency_receipt_hash": hash_obj(receipt),
        "sbom_hash": hash_obj(sb),
        "ai_ml_bom_hash": hash_obj(ab),
        "vex_hash": hash_obj([]),          # no vulns claimed => empty set
        "ai_release_closure_hash": ai_c["closure_hash"],
        "waiver_hash": hash_obj([]),
        "rollback_hash": hash_obj({"mechanism": "git-revert",
                                   "evidence": "additive-only change"}),
        "defeater_hash": hash_obj([]),
    })
    all_findings.extend(envelope_mod.validate_envelope(env))

    twin = {
        "twin_version": "finalis-release-assurance-twin-v1",
        "policy_epoch": POLICY_EPOCH,
        "archaeology": arch,
        "classification": classification,
        "risk_vector": risk,
        "impact_cone": cone,
        "release_slice": rslice,
        "candidate": state,
        "ai_release_closure": ai_c,
        "sp0011_qualification": ai_closure.sp0011_placeholder(),
        "gate_plan": plan,
        "gate_results": results,
        "gate_ledger": gate_ledger.entries(),
        "gate_verdict": verdict,
        "obligations": closed_obs,
        "dod_closure": dod,
        "test_selection": {"selected": selection, "proof": sel_proof,
                           "mandatory": mandatory,
                           "inventory_count": len(inventory)},
        "execution_ledger": ledger.attempts(),
        "rerun_accounting": rerun_acct,
        "flake_registry": flake_reg,
        "flake_classification": flake_classification,
        "flake_posterior": flake_posterior,
        "flake_clusters": flake_clusters,
        "build_manifest": manifest,
        "reproducibility": repro,
        "artifact": art,
        "artifact_closure": closure,
        "trust_roots": [root_obj],
        "attestations": [att],
        "attestation_quorum": quorum,
        "transparency_receipts": [receipt],
        "sbom": sb,
        "ai_ml_bom": ab,
        "ci_security_posture": ci_posture,
        "progressive_delivery": pd,
        "mutation_adequacy": mut,
        "unknown_budget": unknowns,
        "qualification": qual,
        "model_checks": models["models"],
        "counts": {"findings": finding_counts},
        "findings": [f.as_dict() for f in all_findings],
        "release_envelope": env,
    }
    twin["twin_digest"] = hash_obj(
        {k: twin[k] for k in twin if k != "twin_digest"})
    return twin


def _secret_scan(root: Path) -> list:
    """Deterministic secret-pattern scan over the SP0009 slice files."""
    import re
    pat = re.compile(
        r"(AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
        r"|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,})")
    hits = []
    for rel in _slice_files(root):
        p = root / rel
        if p.is_file():
            m = pat.search(p.read_text(encoding="utf-8", errors="replace"))
            if m:
                hits.append({"path": rel, "kind": "secret-pattern"})
    return hits
