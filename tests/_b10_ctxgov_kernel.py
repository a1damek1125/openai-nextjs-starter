"""Shared (non-collected) builders for TOOL-B10 Context Governance kernel tests.

Leading underscore -> pytest does not collect this as a test module. TOOL-B10 is a
self-contained reference kernel (no product coupling), so these helpers construct
kernel objects directly and expose a one-shot ``clean_request`` that yields a
request which ``governance.build_capsule`` seals, plus small mutators each test
file can use to drive a single failure mode.
"""
from tools.context_governance import (entitlement as ent_mod,
                                       evidence as ev_mod,
                                       requirements as req_mod,
                                       capsule as cap_mod,
                                       compile as comp_mod)


def make_entitlement(**over):
    kw = dict(tenant_id="t1", principal_id="p1", provider_account_ids=["acc1"],
              purpose="draft_reply", operation_class="READ",
              data_classes=["pii"], jurisdiction="EU", policy_epoch="pe1",
              expires_at="2027-01-01")
    kw.update(over)
    return ent_mod.entitlement(**kw)


def make_evidence(*, provider="prov1", origin="o1", **over):
    kw = dict(source_id="src1", source_version="v1", tenant_id="t1",
              content="customer said x", observed_at="2026-07-12",
              taint="EXTERNAL")
    kw.update(over)
    e = ev_mod.evidence_record(**kw)
    e["provider"] = provider
    e["origin"] = origin
    return e


def make_claim(evidence, *, discharges=("atom_a",), tokens=5, support=True,
               refute=False, taint_refs=(), **over):
    kw = dict(evidence_refs=[evidence["evidence_id"]], tenant_id="t1",
              subject={"id": "cust"}, predicate="wants", obj={"v": "refund"},
              polarity="POS", support=support, refute=refute,
              taint_refs=list(taint_refs), observed_at="2026-07-12")
    kw.update(over)
    c = ev_mod.claim(**kw)
    c["discharges"] = list(discharges)
    c["tokens"] = tokens
    return c


def make_requirement(**over):
    kw = dict(req_id="R1", description="know intent", atoms=["atom_a"],
              critical=True, mandatory=True, min_independent=1)
    kw.update(over)
    return req_mod.requirement(**kw)


def make_version_vector(**over):
    kw = dict(tenant_id="t1", source_versions={"src1": "v1"},
              evidence_versions={}, memory_versions={}, approval_versions={},
              entitlement_version="ev1", policy_epoch="pe1",
              semantic_epoch="se1", adapter_versions={}, compiler_version="c1")
    kw.update(over)
    return ent_mod.version_vector(**kw)


def make_snapshot(vv, evidence, claim, **over):
    kw = dict(tenant_id="t1", principal_id="p1", provider_account_ids=["acc1"],
              work_id="w1", purpose="draft_reply", operation_class="READ",
              version_vector_ref=vv["vector_hash"],
              evidence_refs=[evidence["evidence_id"]],
              claim_refs=[claim["claim_id"]], created_at="2026-07-12")
    kw.update(over)
    return ent_mod.snapshot(**kw)


def make_lease(snap, **over):
    kw = dict(snapshot_root=snap["snapshot_root"], issued_at="2026-07-12",
              expires_at="2027-01-01", allowed_delta_classes=[],
              required_revalidations=[])
    kw.update(over)
    return ent_mod.issue_lease(**kw)


def clean_request(**over):
    """A fully clean request that build_capsule seals (zero P0/P1). ``over`` keys
    replace top-level request fields; use the mutators below for failure modes."""
    ent = make_entitlement()
    ev = make_evidence()
    cl = make_claim(ev)
    req = make_requirement()
    vv = make_version_vector()
    snap = make_snapshot(vv, ev, cl)
    lease = make_lease(snap)
    reval = ent_mod.revalidate(lease, snapshot_vector=vv, current_vector=vv,
                               now="2026-07-12")
    fields = {"claims": [], "certificate": "x"}
    view = comp_mod.compile_view(fields, view_class="AUDITOR_VIEW")
    rendered = comp_mod.render_abi(view)
    bom = [cap_mod.bom_entry(ref=ev["evidence_id"], kind="EVIDENCE",
                             content_hash=ev["content_hash"],
                             provider_account="acc1",
                             independence_class="SINGLE_SOURCE",
                             taint="EXTERNAL", version="v1")]
    request = dict(
        tenant_id="t1", principal_id="p1", provider_account_id="acc1",
        purpose="draft_reply", operation_class="READ", now="2026-07-12",
        requested_operations=["PURE_COMPUTE"], entitlement=ent,
        revalidation=reval, claims=[cl], critical_claim_ids={cl["claim_id"]},
        evidence=[ev], requirements=[req], token_budget=100, snapshot=snap,
        version_vector=vv, view_classes=["AUDITOR_VIEW"], capsule_fields=fields,
        bom_entries=bom, provider_reported_len=rendered["byte_len"],
        _lease=lease, _view=view, _rendered=rendered)
    request.update(over)
    return request
