"""TOOL-B10 edge-case / boundary coverage: gaps not exercised by the other
test_context_governance_* files. Canon empty/single-leaf/unicode/nested-volatile,
entitlement multi-mismatch + lease limit + cache-key axes + requalify boundary,
evidence provenance/common-mode/independence corners, requirements antichain /
refutation / threshold / robust worst-case / e-process / empty conformal,
compile view-grants / ABI / receipt / non-use / three-branch merge, capsule
BOM/TCB/frontier/transparency corners, and governance P2-vs-P0 sealing."""
from fractions import Fraction
from itertools import permutations

from tools.context_governance import (canon, entitlement as ent,
                                       evidence as ev,
                                       requirements as reqs,
                                       compile as comp,
                                       capsule as cap,
                                       governance as gov)
from tests._b10_ctxgov_kernel import (clean_request, make_entitlement, make_evidence,
                              make_claim, make_requirement, make_version_vector,
                              make_snapshot, make_lease)


def _tok(c):
    return int(c.get("tokens", 1))


# --- canon: empty inputs ------------------------------------------------------
def test_canonical_json_empty_containers():
    assert canon.canonical_json({}) == "{}"
    assert canon.canonical_json([]) == "[]"
    assert canon.canonical_json("") == '""'


def test_hash_obj_distinguishes_empty_dict_from_empty_list():
    assert canon.hash_obj({}) != canon.hash_obj([])
    assert len(canon.hash_obj({})) == 64


def test_merkle_single_leaf_is_identity():
    # a one-leaf tree has no pairing rounds: the root IS the leaf
    assert canon.merkle_root(["only-leaf"]) == "only-leaf"
    assert canon.merkle_root(["only-leaf"]) != canon.merkle_root([])


def test_merkle_odd_leaves_duplicate_last():
    # three leaves: last leaf is paired with itself at the first level
    expected = canon._pair(canon._pair("a", "b"), canon._pair("c", "c"))
    assert canon.merkle_root(["a", "b", "c"]) == expected


def test_class_root_empty_matches_empty_sentinel():
    assert canon.class_root([]) == canon.sha256_hex("EMPTY_MERKLE")


def test_global_root_empty_is_deterministic():
    assert canon.global_root({}) == canon.sha256_hex(canon.canonical_json([]))
    assert canon.global_root({}) == canon.global_root({})


# --- canon: unicode determinism -----------------------------------------------
def test_canonical_json_unicode_exact_bytes_and_stable_hash():
    # ensure_ascii=False keeps raw unicode; serialization + hash are stable
    s = canon.canonical_json({"k": "żółć", "j": "日本語"})
    assert s == '{"j":"日本語","k":"żółć"}'
    assert canon.hash_obj({"k": "żółć", "j": "日本語"}) == \
        canon.hash_obj({"j": "日本語", "k": "żółć"})


def test_unicode_composed_vs_decomposed_hash_differently():
    composed = "é"          # é as one codepoint
    decomposed = "é"       # e + combining acute
    assert composed != decomposed
    assert canon.hash_obj({"k": composed}) != canon.hash_obj({"k": decomposed})


# --- canon: volatile stripping in nested lists ---------------------------------
def test_strip_volatile_inside_nested_lists():
    obj = {"items": [{"label": "x", "v": 1},
                     [{"notes": "n", "keep": 2}],
                     "created_at"]}
    stripped = canon.strip_volatile(obj)
    # volatile KEYS vanish at any depth; volatile-looking string VALUES survive
    assert stripped == {"items": [{"v": 1}, [{"keep": 2}], "created_at"]}


def test_core_hash_ignores_volatile_in_nested_lists():
    a = {"rows": [{"id": 1, "observed_at": "t1"}, {"id": 2, "label": "aa"}]}
    b = {"rows": [{"id": 1, "observed_at": "t9"}, {"id": 2, "label": "zz"}]}
    assert canon.core_hash(a) == canon.core_hash(b)
    c = {"rows": [{"id": 1}, {"id": 3}]}
    assert canon.core_hash(a) != canon.core_hash(c)


# --- entitlement: multiple simultaneous mismatches ------------------------------
def test_all_entitlement_mismatches_reported_together():
    e = make_entitlement(expires_at="2026-01-01")     # already expired
    fs = ent.check_entitlement(e, tenant_id="T2", principal_id="p2",
                               provider_account_id="accX", purpose="other",
                               operation_class="WRITE", now="2026-07-12")
    kinds = [f.kind for f in fs]
    assert len(fs) == 6                                # nothing masks anything
    assert set(kinds) == {"SOURCE_TENANT_MISMATCH", "ENTITLEMENT_MISSING",
                          "SOURCE_ACCOUNT_MISMATCH", "SOURCE_PURPOSE_MISMATCH",
                          "ENTITLEMENT_EXPIRED"}
    assert kinds.count("ENTITLEMENT_MISSING") == 2     # principal + op class
    assert all(f.severity == "P0" for f in fs)


# --- entitlement: lease consumption_limit ---------------------------------------
def test_lease_consumption_limit_recorded_and_hash_excludes_count():
    vv = make_version_vector()
    e = make_evidence(); c = make_claim(e)
    snap = make_snapshot(vv, e, c)
    lease = make_lease(snap, consumption_limit=3)
    assert lease["consumption_limit"] == 3
    assert lease["consumption_count"] == 0
    # a different limit changes the lease identity
    assert lease["lease_hash"] != make_lease(snap)["lease_hash"]
    # ...but the consumption COUNT is mutable state outside the hash
    hashed_fields = ("snapshot_root", "issued_at", "expires_at",
                     "allowed_delta_classes", "required_revalidations",
                     "consumption_limit", "state")
    expected = canon.hash_obj({k: lease[k] for k in hashed_fields})
    assert lease["lease_hash"] == expected
    lease["consumption_count"] = 2
    assert canon.hash_obj({k: lease[k] for k in hashed_fields}) == \
        lease["lease_hash"]


# --- entitlement: every cache_key component matters -----------------------------
def test_cache_key_each_component_changes_key():
    base = dict(tenant_id="t1", principal_id="p1", provider_account_id="a1",
                purpose="u1", operation_class="READ", vector_hash="v1",
                policy_epoch="pe1", semantic_epoch="se1")
    keys = [ent.cache_key(**base)]
    for field in base:
        variant = dict(base)
        variant[field] = variant[field] + "-X"
        keys.append(ent.cache_key(**variant))
    # baseline plus one variant per component: all nine keys are distinct
    assert len(set(keys)) == len(base) + 1


# --- entitlement: NONMATERIAL vs MATERIAL_REQUALIFY boundary --------------------
def test_adapter_versions_requalify_vs_nonmaterial_boundary():
    vv = make_version_vector()
    vv2 = make_version_vector(adapter_versions={"ocr": "2"})
    e = make_evidence(); c = make_claim(e)
    snap = make_snapshot(vv, e, c)
    # lease does NOT allow adapter deltas -> requalification required
    strict = make_lease(snap)
    r1 = ent.revalidate(strict, snapshot_vector=vv, current_vector=vv2,
                        now="2026-07-12")
    assert r1["verdict"] == "REQUALIFICATION_REQUIRED"
    assert r1["delta_certificate"]["requalification_required"] is True
    assert r1["delta_certificate"]["recompile_required"] is False
    assert r1["delta_certificate"]["material_changes"] == ["adapter_versions"]
    # the SAME delta under a lease that allows it is nonmaterial
    lenient = make_lease(snap, allowed_delta_classes=["adapter_versions"])
    r2 = ent.revalidate(lenient, snapshot_vector=vv, current_vector=vv2,
                        now="2026-07-12")
    assert r2["verdict"] == "VALID_WITH_NONMATERIAL_DELTA"
    assert r2["delta_certificate"]["nonmaterial_changes"] == ["adapter_versions"]
    # neither verdict is BLOCKED, so neither yields a TOCTOU finding
    assert ent.toctou_findings(r1) == [] and ent.toctou_findings(r2) == []


# --- evidence: provenance determinism -------------------------------------------
def test_provenance_root_is_order_independent_and_edge_sensitive():
    e1 = ev.provenance_edge(from_ref="EV-1", to_ref="CL-1",
                            relation="DERIVED_FROM")
    e2 = ev.provenance_edge(from_ref="CL-1", to_ref="OUT-1",
                            relation="INFLUENCED")
    assert ev.provenance_root([e1, e2]) == ev.provenance_root([e2, e1])
    # recreating the same edge is deterministic
    again = ev.provenance_edge(from_ref="EV-1", to_ref="CL-1",
                               relation="DERIVED_FROM")
    assert again["edge_hash"] == e1["edge_hash"]
    # changing only the relation moves the edge and the root
    other = ev.provenance_edge(from_ref="EV-1", to_ref="CL-1",
                               relation="TRANSFORMED_BY")
    assert other["edge_hash"] != e1["edge_hash"]
    assert ev.provenance_root([other, e2]) != ev.provenance_root([e1, e2])


# --- evidence: common-mode graph with three shared keys --------------------------
def test_common_mode_graph_three_shared_keys():
    a = make_evidence(source_id="s1", provider="P", origin="o")
    b = make_evidence(source_id="s2", provider="P", origin="o")
    a["extraction_model"] = "m1"
    b["extraction_model"] = "m1"
    g = ev.common_mode_graph([a, b])
    assert set(g) == {"origin", "extraction_model", "provider"}
    pair = sorted([a["evidence_id"], b["evidence_id"]])
    assert g["origin"]["o"] == pair
    assert g["extraction_model"]["m1"] == pair
    assert g["provider"]["P"] == pair


def test_common_mode_graph_ignores_missing_key_buckets():
    # two records both LACKING extraction_model must not group under None
    a = make_evidence(source_id="s1", provider="P", origin="o1")
    b = make_evidence(source_id="s2", provider="Q", origin="o2")
    g = ev.common_mode_graph([a, b])
    assert g == {}


# --- evidence: independence_class UNKNOWN ---------------------------------------
def test_independence_class_unknown_when_ids_absent():
    a = make_evidence()
    by_id = {a["evidence_id"]: a}
    assert ev.independence_class([], by_id) == "UNKNOWN"
    assert ev.independence_class(["EV-ghost"], {}) == "UNKNOWN"
    assert ev.independence_class(["EV-ghost", "EV-phantom"], by_id) == "UNKNOWN"


# --- requirements: multi-atom minimal bases (antichain) --------------------------
def test_multi_atom_minimal_bases_form_antichain():
    e = make_evidence()
    c_both = make_claim(e, discharges=("atom_a", "atom_b"), support=True,
                        predicate="covers_both")
    c_a = make_claim(e, discharges=("atom_a",), support=True)
    c_b = make_claim(e, discharges=("atom_b",), support=True,
                     predicate="covers_b")
    req = make_requirement(atoms=["atom_a", "atom_b"])
    res = reqs.evaluate_requirement(req, [c_both, c_a, c_b],
                                    evidence_by_id={e["evidence_id"]: e})
    assert res["satisfied"] is True
    bases = [frozenset(b) for b in res["minimal_support_bases"]]
    assert frozenset({c_both["claim_id"]}) in bases
    assert frozenset({c_a["claim_id"], c_b["claim_id"]}) in bases
    assert len(bases) == 2
    # antichain: no basis is a strict subset of another
    assert not any(x < y for x in bases for y in bases)


# --- requirements: refutation bases ----------------------------------------------
def test_refutation_bases_computed_for_refuted_atoms():
    e = make_evidence()
    denier = make_claim(e, discharges=("atom_a",), support=False, refute=True,
                        predicate="denies")
    req = make_requirement(atoms=["atom_a"])
    res = reqs.evaluate_requirement(req, [denier],
                                    evidence_by_id={e["evidence_id"]: e})
    assert res["satisfied"] is False
    assert res["refuted_atoms"] == ["atom_a"]
    assert res["minimal_refutation_bases"] == [[denier["claim_id"]]]
    assert res["minimal_support_bases"] == []          # no support at all
    assert res["missing_evidence_bases"] == [["atom_a"]]


# --- requirements: min_independent exactly at the threshold -----------------------
def test_min_independent_exactly_at_threshold():
    a = make_evidence(source_id="s1", provider="P")
    b = make_evidence(source_id="s2", provider="Q")
    c = make_evidence(source_id="s3", provider="R")
    by_id = {x["evidence_id"]: x for x in (a, b, c)}
    claims = [make_claim(x, discharges=("atom_a",), support=True)
              for x in (a, b, c)]
    # exactly 3 independent producers meets min_independent=3
    req3 = make_requirement(atoms=["atom_a"], min_independent=3)
    res3 = reqs.evaluate_requirement(req3, claims, evidence_by_id=by_id)
    assert res3["common_mode_short_atoms"] == []
    assert res3["satisfied"] is True
    # one producer fewer (drop R's claim) falls below the same floor
    res2 = reqs.evaluate_requirement(req3, claims[:2], evidence_by_id=by_id)
    assert res2["common_mode_short_atoms"] == ["atom_a"]
    assert res2["satisfied"] is False


# --- requirements: robust_select worst-case over drop scenarios -------------------
def test_robust_select_worst_case_drops_scenario_claims():
    e = make_evidence()
    c1 = make_claim(e, discharges=("atom_a",), support=True, tokens=2)
    c2 = make_claim(e, discharges=("atom_b",), support=True, tokens=2,
                    predicate="stable")
    by_id = {c1["claim_id"]: c1, c2["claim_id"]: c2}
    scenarios = [[c1["claim_id"]]]        # a plausible world where c1 vanishes
    sel = reqs.robust_select([c1["claim_id"], c2["claim_id"]], by_id,
                             budget=10, token_of=_tok, scenarios=scenarios)
    # c1's robust marginal value is zero (worst case drops it) -> never picked
    assert sel["selected_ids"] == [c2["claim_id"]]
    assert sel["value"] == "1" and sel["budget_ok"] is True
    # without scenarios the same pool selects both
    plain = reqs.robust_select([c1["claim_id"], c2["claim_id"]], by_id,
                               budget=10, token_of=_tok)
    assert sorted(plain["selected_ids"]) == sorted([c1["claim_id"],
                                                    c2["claim_id"]])
    assert plain["value"] == "2"


# --- requirements: e-process wealth product ---------------------------------------
def test_eprocess_wealth_is_product_of_bets():
    assert reqs.eprocess_wealth([]) == Fraction(1)
    assert reqs.eprocess_wealth([2, 3, Fraction(1, 2)]) == Fraction(3)
    assert reqs.eprocess_wealth([Fraction(1, 2), 0]) == Fraction(0)
    d = reqs.anytime_decision([2, 3, Fraction(1, 2)], alpha=Fraction(1, 20))
    assert d["final_wealth"] == "3" and d["reject_h0"] is False


# --- requirements: conformal with empty calibration --------------------------------
def test_conformal_empty_calibration_fails_closed():
    c = reqs.conformal_interval([], 7)
    assert c["covered"] is None and c["p_value"] is None
    assert c["guarantee_active"] is False
    assert c["reason"] == "NO_CALIBRATION"
    fs = reqs.statistics_findings(c)
    assert len(fs) == 1
    assert fs[0].kind == "CONFORMAL_GUARANTEE_DISABLED" and fs[0].severity == "P2"


# --- compile: every view class projects only its grant -----------------------------
def test_every_view_class_projects_only_its_grant():
    fields = {"claims": [], "requirements": [], "provenance": [],
              "uncertainty": {}, "contradictions": [], "receipts": [],
              "certificate": "x", "entitlement_scope": {},
              "operation_class": "READ", "evidence_lineage": []}
    hashes = {}
    for vc in comp.VIEW_CLASSES:
        v = comp.compile_view(fields, view_class=vc)
        assert v["view_class"] == vc
        assert v["leaked_forbidden"] == []
        grant = comp._VIEW_GRANTS[vc]
        assert set(v["fields"]) == grant & set(fields)
        assert len(v["view_bytes_hash"]) == 64
        hashes[vc] = v["view_bytes_hash"]
    # least privilege is real: e.g. the tool gateway sees no claims at all
    tool = comp.compile_view(fields, view_class="TOOL_GATEWAY_VIEW")
    assert "claims" not in tool["fields"]
    assert hashes["TOOL_GATEWAY_VIEW"] != hashes["AUDITOR_VIEW"]


# --- compile: unsupported ABI version fails closed ---------------------------------
def test_abi_unsupported_version_fails_closed():
    v = comp.compile_view({"claims": []}, view_class="REASONING_MODEL_VIEW")
    r = comp.render_abi(v, abi_version="ctxgov-abi-9.9")
    assert r["supported"] is False
    assert r["byte_hash"] is None and r["byte_len"] == 0
    rec = comp.consumption_receipt(render=r,
                                   lease_revalidation={"verdict": "VALID"},
                                   provider_reported_len=0)
    assert rec["truncation"] == "UNKNOWN"      # unsupported render is unprovable
    assert rec["state"] == "REJECTED"
    kinds = {f.kind for f in comp.receipt_findings(rec)}
    assert "ABI_VERSION_UNSUPPORTED" in kinds
    assert "PROVIDER_TRUNCATION_UNKNOWN" in kinds


# --- compile: receipt rejected when lease invalid ----------------------------------
def test_receipt_rejected_when_lease_invalid():
    v = comp.compile_view({"claims": []}, view_class="REASONING_MODEL_VIEW")
    r = comp.render_abi(v)
    rec = comp.consumption_receipt(
        render=r, lease_revalidation={"verdict": "RECOMPILE_REQUIRED"},
        provider_reported_len=r["byte_len"])       # byte-perfect delivery
    assert rec["truncation"] == "NONE"             # no truncation...
    assert rec["lease_valid"] is False             # ...but the lease is stale
    assert rec["state"] == "REJECTED"
    kinds = {f.kind for f in comp.receipt_findings(rec)}
    assert kinds == {"CONSUMPTION_RECEIPT_INVALID"}


# --- compile: non-use with multiple certificates -----------------------------------
def test_non_use_multiple_certs_flags_only_failures():
    ok = comp.proof_of_non_use(excluded_ref="EX-1", output_hash="h",
                               output_without_excluded_hash="h")
    bad = comp.proof_of_non_use(excluded_ref="EX-2", output_hash="h",
                                output_without_excluded_hash="different")
    ok2 = comp.proof_of_non_use(excluded_ref="EX-3", output_hash="h",
                                output_without_excluded_hash="h")
    fs = comp.non_use_findings([ok, bad, ok2])
    assert len(fs) == 1
    assert fs[0].kind == "PROOF_OF_NON_USE_FAILED"
    assert fs[0].subject == "EX-2"


# --- compile: three-branch merge with a shared base --------------------------------
def test_merge_three_branches_shared_base_preserves_conflict():
    e = make_evidence()
    s1 = make_claim(e, discharges=("atom_a",), support=True)
    s2 = make_claim(e, discharges=("atom_b",), support=True, predicate="b")
    r3 = make_claim(e, discharges=("atom_a",), support=False, refute=True,
                    predicate="denies")
    by_id = {c["claim_id"]: c for c in (s1, s2, r3)}
    branches = [comp.branch(base_snapshot_root="S", hypothesis=h,
                            claim_refs=[c["claim_id"]], tenant_id="t1")
                for h, c in (("h1", s1), ("h2", s2), ("h3", r3))]
    merge = comp.merge_branches(branches, by_id, critical_ids={"atom_a"})
    assert len(merge["branch_ids"]) == 3
    assert merge["shared_base"] is True
    assert merge["conflicts"] == ["atom_a"]        # atom_b is NOT a conflict
    assert merge["critical_conflicts"] == ["atom_a"]
    assert merge["merged_consensus"] is False
    kinds = [f.kind for f in comp.merge_findings(merge)]
    assert kinds == ["MERGE_CRITICAL_CONFLICT"]    # no base-mismatch finding


# --- capsule: BOM normalization / permutation invariance ----------------------------
def test_bom_entries_normalized_and_root_permutation_invariant():
    entries = [cap.bom_entry(ref=f"EV-{i}", kind="EVIDENCE",
                             content_hash=f"h{i}", provider_account="a",
                             independence_class="INDEPENDENT",
                             taint="EXTERNAL", version="v1")
               for i in range(3)]
    roots = {cap.context_bom(list(p))["bom_root"]
             for p in permutations(entries)}
    assert len(roots) == 1                          # all six orderings agree
    bom = cap.context_bom(entries[::-1])
    assert bom["entry_count"] == 3
    stored = [e["entry_hash"] for e in bom["entries"]]
    assert stored == sorted(stored)                 # normalized storage order


# --- capsule: TCB with multiple missing components ----------------------------------
def test_tcb_missing_multiple_components_enumerated():
    tcb = cap.tcb_manifest(present=["canon", "model", "governance"])
    assert tcb["complete"] is False
    expected_missing = sorted(c for c in cap.TCB_COMPONENTS
                              if c not in ("canon", "model", "governance"))
    assert tcb["missing"] == expected_missing
    assert len(tcb["missing"]) == len(cap.TCB_COMPONENTS) - 3
    full = cap.tcb_manifest(present=list(cap.TCB_COMPONENTS))
    assert tcb["tcb_root"] != full["tcb_root"]


# --- capsule: robustness frontier all-hold / all-break -------------------------------
def test_robustness_frontier_all_hold_and_all_break():
    names = ["s1", "s2", "s3"]
    all_hold = cap.robustness_frontier(
        scenarios=[{"name": n, "certifies": True} for n in names])
    assert all_hold["holds_under"] == names and all_hold["breaks_under"] == []
    all_break = cap.robustness_frontier(
        scenarios=[{"name": n, "certifies": False} for n in names])
    assert all_break["breaks_under"] == names and all_break["holds_under"] == []
    assert all_hold["frontier_hash"] != all_break["frontier_hash"]
    empty = cap.robustness_frontier(scenarios=[])
    assert empty["holds_under"] == [] and empty["breaks_under"] == []


# --- capsule: transparency receipt at log position zero -------------------------------
def test_transparency_receipt_at_position_zero():
    res = gov.build_capsule(clean_request())
    r0 = cap.transparency_receipt(res["capsule"], log_position=0)
    assert r0["log_position"] == 0
    assert r0["capsule_root"] == res["capsule"]["certificate"]["capsule_root"]
    r1 = cap.transparency_receipt(res["capsule"], log_position=1)
    assert r0["receipt_hash"] != r1["receipt_hash"]


# --- governance: a P2-only report still seals -----------------------------------------
def test_p2_only_finding_still_seals():
    # empty conformal calibration yields exactly one P2 (guarantee disabled)
    req = clean_request(conformal=reqs.conformal_interval([], 1))
    res = gov.build_capsule(req)
    assert res["report"]["counts"] == {"P0": 0, "P1": 0, "P2": 1}
    assert any(f["kind"] == "CONFORMAL_GUARANTEE_DISABLED"
               for f in res["report"]["findings"])
    assert res["valid"] is True                    # valid iff zero P0 and P1
    assert res["state"] == "SEALED"
    assert res["capsule"] is not None and res["check"]["accepted"] is True


# --- governance: privacy overrun blocks the capsule -----------------------------------
def test_privacy_overrun_blocks_capsule():
    req = clean_request(privacy={"exposures": {"pii": 5}, "limits": {"pii": 1}})
    res = gov.build_capsule(req)
    assert res["valid"] is False
    assert res["capsule"] is None and res["state"] == "INCOMPLETE"
    assert any(f["kind"] == "PRIVACY_EXPOSURE_EXCEEDED" and f["severity"] == "P0"
               for f in res["report"]["findings"])


# --- governance: a compaction violation blocks the capsule -----------------------------
def test_compaction_violation_blocks_capsule():
    req = clean_request()
    critical = req["claims"][0]                    # marked critical by builder
    req["compaction"] = {"original": [critical], "retained": []}
    res = gov.build_capsule(req)
    assert res["valid"] is False
    assert res["capsule"] is None
    assert any(f["kind"] == "COMPRESSION_CLAIM_LOSS" and f["severity"] == "P0"
               for f in res["report"]["findings"])
