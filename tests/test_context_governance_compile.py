"""TOOL-B10 compile: claim-preserving compaction, conflict-preserving merge,
least-privilege views, noninterference, non-compensatory privacy, ABI render,
consumption receipt / truncation, proof-of-non-use."""
from tools.context_governance import compile as c
from tools.context_governance import capsule as cap
from tests._b10_ctxgov_kernel import make_evidence, make_claim


def test_compaction_preserves_critical_claim():
    e = make_evidence()
    cl = make_claim(e, support=True)
    cert = c.compaction(original_claims=[cl], retained_claims=[cl],
                        critical_ids={cl["claim_id"]})
    assert cert["preserved"] is True and cert["violations"] == []


def test_compaction_flags_dropped_critical_claim():
    e = make_evidence()
    cl = make_claim(e, support=True)
    cert = c.compaction(original_claims=[cl], retained_claims=[],
                        critical_ids={cl["claim_id"]})
    fs = c.compaction_findings(cert)
    assert any(f.kind == "COMPRESSION_CLAIM_LOSS" for f in fs)


def test_compaction_flags_polarity_flip():
    e = make_evidence()
    orig = make_claim(e, support=True)
    flipped = dict(orig); flipped["polarity"] = "NEG"
    cert = c.compaction(original_claims=[orig], retained_claims=[flipped],
                        critical_ids={orig["claim_id"]})
    kinds = {v[0] for v in cert["violations"]}
    assert "COMPRESSION_NEGATION_CHANGED" in kinds


def test_merge_preserves_critical_conflict():
    e = make_evidence()
    supp = make_claim(e, discharges=["atom_a"], support=True)
    refu = make_claim(e, discharges=["atom_a"], support=False, refute=True,
                      predicate="denies")
    by_id = {supp["claim_id"]: supp, refu["claim_id"]: refu}
    b1 = c.branch(base_snapshot_root="S", hypothesis="h1",
                  claim_refs=[supp["claim_id"]], tenant_id="t1")
    b2 = c.branch(base_snapshot_root="S", hypothesis="h2",
                  claim_refs=[refu["claim_id"]], tenant_id="t1")
    merge = c.merge_branches([b1, b2], by_id, critical_ids={"atom_a"})
    assert "atom_a" in merge["critical_conflicts"]
    assert merge["merged_consensus"] is False
    fs = c.merge_findings(merge)
    assert any(f.kind == "MERGE_CRITICAL_CONFLICT" for f in fs)


def test_merge_base_mismatch_flagged():
    e = make_evidence()
    cl = make_claim(e, support=True)
    by_id = {cl["claim_id"]: cl}
    b1 = c.branch(base_snapshot_root="S1", hypothesis="h",
                  claim_refs=[cl["claim_id"]], tenant_id="t")
    b2 = c.branch(base_snapshot_root="S2", hypothesis="h",
                  claim_refs=[cl["claim_id"]], tenant_id="t")
    merge = c.merge_branches([b1, b2], by_id, critical_ids=set())
    assert any(f.kind == "BRANCH_BASE_MISMATCH" for f in c.merge_findings(merge))


def test_view_drops_out_of_grant_fields():
    v = c.compile_view({"claims": [], "receipts": [], "entitlement_scope": {}},
                       view_class="DOWNSTREAM_AGENT_VIEW")
    assert v["fields"] == ["claims"]        # downstream agent sees claims only


def test_view_never_leaks_forbidden_field():
    v = c.compile_view({"provider_token": "sk-xxx", "claims": []},
                       view_class="AUDITOR_VIEW")
    assert "provider_token" not in v["fields"]
    assert v["leaked_forbidden"] == ["provider_token"]
    assert any(f.kind == "VIEW_LEAKAGE" for f in c.view_findings([v]))


def test_noninterference_detects_low_view_change():
    hi = {"view_bytes_hash": "A"}
    lo = {"view_bytes_hash": "B"}
    ni = c.noninterference(low_view_high=hi, low_view_low=lo)
    assert ni["noninterference_ok"] is False
    assert any(f.kind == "NONINTERFERENCE_FAILED"
               for f in c.view_findings([], ni))


def test_privacy_budget_is_non_compensatory():
    b = c.privacy_budget({"pii": 5, "financial": 0})
    exp = c.privacy_exposure({"pii": 0, "financial": 1}, b)   # slack pii, over fin
    assert exp["within_budget"] is False
    assert any(f.kind == "PRIVACY_EXPOSURE_EXCEEDED"
               for f in c.privacy_findings(exp))


def test_privacy_within_budget_passes():
    b = c.privacy_budget({"pii": 5, "financial": 5})
    exp = c.privacy_exposure({"pii": 2, "financial": 1}, b)
    assert exp["within_budget"] is True


def test_abi_render_is_deterministic():
    v = c.compile_view({"claims": []}, view_class="REASONING_MODEL_VIEW")
    r1 = c.render_abi(v)
    r2 = c.render_abi(v)
    assert r1["byte_hash"] == r2["byte_hash"] and r1["supported"]


def test_receipt_detects_truncation():
    v = c.compile_view({"claims": []}, view_class="REASONING_MODEL_VIEW")
    r = c.render_abi(v)
    reval = {"verdict": "VALID"}
    rec = c.consumption_receipt(render=r, lease_revalidation=reval,
                               provider_reported_len=r["byte_len"] - 1)
    assert rec["truncation"] == "DETECTED"
    assert any(f.kind == "PROVIDER_TRUNCATION_DETECTED"
               for f in c.receipt_findings(rec))


def test_receipt_unknown_length_fails_closed():
    v = c.compile_view({"claims": []}, view_class="REASONING_MODEL_VIEW")
    r = c.render_abi(v)
    rec = c.consumption_receipt(render=r, lease_revalidation={"verdict": "VALID"},
                               provider_reported_len=None)
    assert rec["truncation"] == "UNKNOWN"
    assert any(f.kind == "PROVIDER_TRUNCATION_UNKNOWN"
               for f in c.receipt_findings(rec))


def test_receipt_none_truncation_when_lengths_match():
    v = c.compile_view({"claims": []}, view_class="REASONING_MODEL_VIEW")
    r = c.render_abi(v)
    rec = c.consumption_receipt(render=r, lease_revalidation={"verdict": "VALID"},
                               provider_reported_len=r["byte_len"])
    assert rec["truncation"] == "NONE" and rec["state"] == "CONSUMED"
    assert c.receipt_findings(rec) == []


def test_proof_of_non_use_success_and_failure():
    ok = c.proof_of_non_use(excluded_ref="X", output_hash="h",
                            output_without_excluded_hash="h")
    assert ok["non_use_proven"] is True and c.non_use_findings([ok]) == []
    bad = c.proof_of_non_use(excluded_ref="X", output_hash="h",
                             output_without_excluded_hash="different")
    assert any(f.kind == "PROOF_OF_NON_USE_FAILED" for f in c.non_use_findings([bad]))
