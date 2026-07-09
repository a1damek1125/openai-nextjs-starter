"""TOOL-B6 read-path runtime: RBAC + tenant isolation.

Viewers may read but not freeze snapshots / prepare requests (case.update);
runtime requests, outcomes, events, snapshots and B5/snapshot references are all
tenant-scoped; restricted roles get a redacted safe view.
"""
from tests.conftest import OWNER, VIEWER, OTHER_OWNER


def test_viewer_can_read_but_not_prepare(gate):
    rid, _ = gate.prepared_runtime()
    # Read is fine.
    assert gate.rt(rid, "/outcome", actor=VIEWER).status_code == 200
    assert gate.c.get("/ai-tools/runtime/registry",
                      headers=gate.h(VIEWER)).status_code == 200
    # Preparing a request requires case.update.
    r = gate.c.post("/ai-tools/runtime/requests",
                    json={"b5_broker_request_id": "x", "snapshot_id": "y"},
                    headers=gate.h(VIEWER))
    assert r.status_code == 403


def test_viewer_cannot_freeze_snapshot(gate):
    r = gate.c.post("/ai-tools/runtime/snapshots",
                    json={"epoch": "1", "scope": "case", "fields": {}},
                    headers=gate.h(VIEWER))
    assert r.status_code == 403


def test_cross_tenant_request_is_404(gate):
    rid, _ = gate.prepared_runtime()
    assert gate.rt(rid, "", actor=OTHER_OWNER).status_code == 404
    assert gate.rt(rid, "/outcome", actor=OTHER_OWNER).status_code == 404
    assert gate.rt(rid, "/events", actor=OTHER_OWNER).status_code == 404


def test_b5_from_other_tenant_is_404(gate):
    # A B5 broker request created in the OTHER tenant is invisible here.
    b5rid_other, _ = gate.b5_broker_request(requester=OTHER_OWNER)
    snap = gate.runtime_snapshot(actor=OWNER)
    r = gate.runtime_request(b5rid_other, snap["snapshot_id"], actor=OWNER)
    assert r.status_code == 404


def test_snapshot_from_other_tenant_is_404(gate):
    snap_other = gate.runtime_snapshot(actor=OTHER_OWNER)
    b5rid, _ = gate.b5_broker_request(requester=OWNER)
    r = gate.runtime_request(b5rid, snap_other["snapshot_id"], actor=OWNER)
    assert r.status_code == 404


def test_safe_view_redacts_for_restricted_role(gate):
    rid, _ = gate.prepared_runtime()
    full = gate.rt(rid, "/safe", actor=OWNER).json()
    assert full["safe_output"] == {"case_id": "C-1", "status": "open"}
    assert full["all_signals"]
    restricted = gate.rt(rid, "/safe", actor=VIEWER).json()
    assert restricted["safe_output"] == {}
    assert restricted["all_signals"] == []


def test_tenant_isolation_on_snapshots_and_outcomes(gate):
    rid, _ = gate.prepared_runtime()
    snap = gate.runtime_snapshot(actor=OWNER)
    # Other tenant sees none of tenant A's snapshots / outcomes.
    other_snaps = gate.c.get("/ai-tools/runtime/snapshots",
                             headers=gate.h(OTHER_OWNER)).json()
    assert all(s["snapshot_id"] != snap["snapshot_id"] for s in other_snaps)
    other_reqs = gate.c.get("/ai-tools/runtime/requests",
                            headers=gate.h(OTHER_OWNER)).json()
    assert all(r["runtime_request_id"] != rid for r in other_reqs)
