"""TOOL-B10 evidence: evidence-first, four-valued claims, provenance, common-mode,
taint, authority air-gap, memory-writeback quarantine."""
from tools.context_governance import evidence as ev
from tests._b10_ctxgov_kernel import make_evidence, make_claim


def test_evidence_is_content_addressed_and_information_channel():
    e = make_evidence(content="hello")
    assert e["channel"] == "INFORMATION"
    assert e["content_hash"] == make_evidence(content="hello")["content_hash"]
    assert e["evidence_id"].startswith("EV-")


def test_evidence_default_taint_external():
    assert make_evidence()["taint"] == "EXTERNAL"


def test_claim_four_valued_state():
    e = make_evidence()
    assert make_claim(e, support=True, refute=False)["support_state"] \
        == "SUPPORTED_ONLY"
    assert make_claim(e, support=True, refute=True)["support_state"] == "BOTH"
    assert make_claim(e, support=False, refute=False)["support_state"] == "NEITHER"


def test_critical_both_neither_visible_as_p1():
    e = make_evidence()
    both = make_claim(e, support=True, refute=True)
    neither = make_claim(e, support=False, refute=False)
    fs = ev.claim_findings([both, neither],
                           critical_ids={both["claim_id"], neither["claim_id"]})
    kinds = {f.kind for f in fs}
    assert kinds == {"CLAIM_BOTH", "CLAIM_NEITHER"}
    assert all(f.severity == "P1" for f in fs)


def test_supported_only_critical_has_no_finding():
    e = make_evidence()
    ok = make_claim(e, support=True, refute=False)
    assert ev.claim_findings([ok], critical_ids={ok["claim_id"]}) == []


def test_common_mode_graph_groups_shared_provider():
    a = make_evidence(source_id="s1", provider="P", origin="oa")
    b = make_evidence(source_id="s2", provider="P", origin="ob")
    g = ev.common_mode_graph([a, b])
    assert "provider" in g and "P" in g["provider"]


def test_independence_class_common_mode_vs_independent():
    a = make_evidence(source_id="s1", provider="P")
    b = make_evidence(source_id="s2", provider="P")
    c = make_evidence(source_id="s3", provider="Q")
    by_id = {x["evidence_id"]: x for x in (a, b, c)}
    assert ev.independence_class([a["evidence_id"], b["evidence_id"]], by_id) \
        == "COMMON_MODE"
    assert ev.independence_class([a["evidence_id"], c["evidence_id"]], by_id) \
        == "INDEPENDENT"
    assert ev.independence_class([a["evidence_id"]], by_id) == "SINGLE_SOURCE"


def test_taint_survives_transformation_unless_proven():
    assert ev.propagate_taint(["EXTERNAL", "QUARANTINED"]) == "QUARANTINED"
    assert ev.propagate_taint(["EXTERNAL", "QUARANTINED"],
                              removal_proven=True) == "UNTAINTED"


def test_taint_findings_flag_unremoved_injection():
    e = make_evidence()
    c = make_claim(e, taint_refs=["SUSPECTED_INJECTION"])
    fs = ev.taint_findings([c], critical_ids={c["claim_id"]})
    assert fs and fs[0].kind == "TAINT_REMOVAL_UNPROVEN" and fs[0].severity == "P0"


def test_authority_air_gap_rejects_information_authority():
    e = make_evidence()
    e["asserts_authority"] = True
    fs = ev.authority_air_gap([e])
    assert fs and fs[0].kind == "AUTHORITY_INFERENCE_REJECTED"


def test_memory_candidate_starts_quarantined_not_auto_admitted():
    cand = ev.memory_candidate(proposed_fact={"x": 1}, evidence_refs=["EV-1"],
                               work_succeeded=True)
    assert cand["state"] == "QUARANTINED" and cand["auto_admitted"] is False
    assert ev.memory_findings([cand]) == []


def test_memory_auto_admit_is_forbidden():
    cand = ev.memory_candidate(proposed_fact={"x": 1}, evidence_refs=[],
                               work_succeeded=True)
    cand["auto_admitted"] = True
    fs = ev.memory_findings([cand])
    assert fs and fs[0].kind == "MEMORY_WRITEBACK_QUARANTINED"
