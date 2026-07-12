"""TOOL-B10 entitlement: fail-closed access, snapshot, lease, TOCTOU, cache."""
from tools.context_governance import entitlement as e
from tests._b10_ctxgov_kernel import (make_entitlement, make_version_vector,
                              make_evidence, make_claim, make_snapshot,
                              make_lease)


def _kinds(findings):
    return {f.kind for f in findings}


def test_missing_entitlement_blocks():
    fs = e.check_entitlement(None, tenant_id="t1", principal_id="p1",
                             provider_account_id="acc1", purpose="u",
                             operation_class="READ", now="t")
    assert "ENTITLEMENT_MISSING" in _kinds(fs)


def test_clean_entitlement_passes():
    ent = make_entitlement()
    fs = e.check_entitlement(ent, tenant_id="t1", principal_id="p1",
                             provider_account_id="acc1", purpose="draft_reply",
                             operation_class="READ", now="2026-07-12")
    assert fs == []


def test_cross_tenant_blocked():
    ent = make_entitlement()
    fs = e.check_entitlement(ent, tenant_id="OTHER", principal_id="p1",
                             provider_account_id="acc1", purpose="draft_reply",
                             operation_class="READ", now="2026-07-12")
    assert "SOURCE_TENANT_MISMATCH" in _kinds(fs)


def test_cross_account_and_purpose_blocked():
    ent = make_entitlement()
    fs = e.check_entitlement(ent, tenant_id="t1", principal_id="p1",
                             provider_account_id="OTHER", purpose="OTHER",
                             operation_class="READ", now="2026-07-12")
    assert {"SOURCE_ACCOUNT_MISMATCH", "SOURCE_PURPOSE_MISMATCH"} <= _kinds(fs)


def test_expired_entitlement_blocked():
    ent = make_entitlement(expires_at="2026-01-01")
    fs = e.check_entitlement(ent, tenant_id="t1", principal_id="p1",
                             provider_account_id="acc1", purpose="draft_reply",
                             operation_class="READ", now="2026-07-12")
    assert "ENTITLEMENT_EXPIRED" in _kinds(fs)


def test_snapshot_and_lease_ids_are_content_addressed():
    vv = make_version_vector()
    ev = make_evidence()
    cl = make_claim(ev)
    snap = make_snapshot(vv, ev, cl)
    assert snap["snapshot_id"].startswith("SNAP-")
    lease = make_lease(snap)
    assert lease["lease_id"].startswith("LEASE-")


def test_toctou_valid_when_no_change():
    vv = make_version_vector()
    ev = make_evidence(); cl = make_claim(ev)
    snap = make_snapshot(vv, ev, cl); lease = make_lease(snap)
    r = e.revalidate(lease, snapshot_vector=vv, current_vector=vv, now="2026-07-12")
    assert r["verdict"] == "VALID"


def test_toctou_material_source_change_recompiles():
    vv = make_version_vector()
    vv2 = make_version_vector(source_versions={"src1": "v2"})
    ev = make_evidence(); cl = make_claim(ev)
    snap = make_snapshot(vv, ev, cl); lease = make_lease(snap)
    r = e.revalidate(lease, snapshot_vector=vv, current_vector=vv2, now="2026-07-12")
    assert r["verdict"] == "RECOMPILE_REQUIRED"


def test_toctou_unknown_component_fails_closed():
    vv = make_version_vector()
    vv2 = dict(vv); vv2["mystery_component"] = "surprise"
    ev = make_evidence(); cl = make_claim(ev)
    snap = make_snapshot(vv, ev, cl); lease = make_lease(snap)
    r = e.revalidate(lease, snapshot_vector=vv, current_vector=vv2, now="2026-07-12")
    assert r["verdict"] == "BLOCKED"
    assert e.toctou_findings(r)[0].kind == "TOCTOU_REVALIDATION_FAILED"


def test_toctou_expired_lease_blocks():
    vv = make_version_vector()
    ev = make_evidence(); cl = make_claim(ev)
    snap = make_snapshot(vv, ev, cl)
    lease = make_lease(snap, expires_at="2026-01-01")
    r = e.revalidate(lease, snapshot_vector=vv, current_vector=vv, now="2026-07-12")
    assert r["verdict"] == "BLOCKED"


def test_nonmaterial_allowed_when_lease_permits():
    vv = make_version_vector()
    vv2 = make_version_vector(memory_versions={"m": "1"})
    ev = make_evidence(); cl = make_claim(ev)
    snap = make_snapshot(vv, ev, cl)
    lease = make_lease(snap, allowed_delta_classes=["memory_versions"])
    r = e.revalidate(lease, snapshot_vector=vv, current_vector=vv2, now="2026-07-12")
    assert r["verdict"] == "VALID_WITH_NONMATERIAL_DELTA"


def test_cache_reuse_requires_exact_scope():
    k1 = e.cache_key(tenant_id="t1", principal_id="p1", provider_account_id="a",
                     purpose="u", operation_class="R", vector_hash="v",
                     policy_epoch="pe", semantic_epoch="se")
    k_other_tenant = e.cache_key(tenant_id="t2", principal_id="p1",
                                 provider_account_id="a", purpose="u",
                                 operation_class="R", vector_hash="v",
                                 policy_epoch="pe", semantic_epoch="se")
    assert k1 != k_other_tenant
    lease = {"state": "ACTIVE", "expires_at": "2027-01-01"}
    assert e.cache_reusable(k1, request_key=k1, lease=lease, now="2026-07-12")
    assert not e.cache_reusable(k1, request_key=k_other_tenant, lease=lease,
                                now="2026-07-12")
