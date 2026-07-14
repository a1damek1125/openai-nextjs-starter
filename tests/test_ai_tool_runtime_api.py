"""TOOL-B6 Verifiable Read-Path Runtime Microkernel: endpoint / HTTP surface.

Snapshots freeze immutably; a runtime request over a B5 broker outcome + a
frozen snapshot yields a local read-only outcome; every read sub-view is 200;
and no write/external/execute endpoint exists.
"""
from tests.conftest import OWNER

# Every read-only sub-view slug exposed under /requests/{id}/<slug>.
SUB_SLUGS = [
    "adapter", "capability-calculus", "adapter-firewall",
    "snapshot-epoch-vector", "temporal-snapshot-isolation", "snapshot-seal",
    "snapshot-twin", "snapshot-provenance", "query-plan-normal-form",
    "semantic-read-firewall", "microkernel", "operation-ledger", "path-policy",
    "authority-freeze", "read-set-ledger", "read-set-completeness",
    "read-set-attestation", "read-output-provenance",
    "output-provenance-bisimulation", "semantic-non-interference",
    "synthetic-canary-harness", "canary-non-leakage", "information-budget",
    "information-usage-proof", "read-amplification", "side-channel-budget",
    "resource-budget", "resource-usage-proof", "entropy-seal", "replay-twin",
    "output-taint", "output-non-exfiltration", "safe-output-projection",
    "data-diode", "effect-ledger", "surface-diff", "no-effect-proofs",
    "escape-sentinel", "non-escalation", "output-provenance-certificate",
    "fault-injection", "release-gate", "conformance-vector", "proof-bundle",
]


def test_post_snapshot_freezes_immutable(gate):
    snap = gate.runtime_snapshot()
    assert snap["immutable"] is True
    assert snap["snapshot_hash"]
    assert snap["epoch"] == "1"
    assert snap["scope"] == "case"


def test_post_runtime_request_returns_read_only_outcome(gate):
    rid, o = gate.prepared_runtime()
    assert o["runtime_request_id"] == rid
    assert o["runtime_status"] == "RUNTIME_READ_ONLY_COMPLETED"
    assert o["runtime_outcome_kind"] == "READ_ONLY_LOCAL_RESULT"
    assert o["read_only"] is True
    assert o["is_external"] is False
    assert o["produced_external_effect"] is False


def test_list_runtime_requests(gate):
    rid, _ = gate.prepared_runtime()
    rows = gate.c.get("/ai-tools/runtime/requests", headers=gate.h()).json()
    assert any(r["runtime_request_id"] == rid for r in rows)


def test_get_request_envelope(gate):
    rid, _ = gate.prepared_runtime()
    r = gate.rt(rid, "")
    assert r.status_code == 200
    env = r.json()
    assert env["runtime_request_id"] == rid
    assert env["read_only_local_only"] is True


def test_get_request_outcome(gate):
    rid, _ = gate.prepared_runtime()
    r = gate.rt(rid, "/outcome")
    assert r.status_code == 200
    assert r.json()["runtime_status"] == "RUNTIME_READ_ONLY_COMPLETED"


def test_unknown_request_id_404(gate):
    assert gate.rt("does-not-exist", "").status_code == 404
    assert gate.rt("does-not-exist", "/outcome").status_code == 404


def test_runtime_policy_endpoint(gate):
    r = gate.c.get("/ai-tools/runtime/policy", headers=gate.h())
    assert r.status_code == 200
    p = r.json()
    assert p["writes"] is False
    assert p["calls_network"] is False
    assert p["has_write_endpoint"] is False
    assert p["most_permissive_outcome"] == "RUNTIME_READ_ONLY_COMPLETED"


def test_registry_adapters_endpoints(gate):
    assert gate.c.get("/ai-tools/runtime/registry",
                      headers=gate.h()).status_code == 200
    assert gate.c.get("/ai-tools/runtime/adapters",
                      headers=gate.h()).status_code == 200


def test_snapshots_endpoints(gate):
    snap = gate.runtime_snapshot()
    lst = gate.c.get("/ai-tools/runtime/snapshots", headers=gate.h())
    assert lst.status_code == 200
    assert any(s["snapshot_id"] == snap["snapshot_id"] for s in lst.json())
    one = gate.c.get(f"/ai-tools/runtime/snapshots/{snap['snapshot_id']}",
                     headers=gate.h())
    assert one.status_code == 200
    assert one.json()["snapshot_id"] == snap["snapshot_id"]


def test_all_sub_read_slugs_200(gate):
    rid, _ = gate.prepared_runtime()
    for slug in SUB_SLUGS:
        r = gate.rt(rid, "/" + slug)
        assert r.status_code == 200, slug
        assert "honesty_labels" in r.json(), slug


def test_no_write_or_external_endpoints(gate):
    h = gate.h(OWNER)
    for path in ("/ai-tools/runtime/write", "/ai-tools/runtime/network",
                 "/ai-tools/runtime/provider", "/ai-tools/runtime/mcp",
                 "/ai-tools/runtime/llm", "/ai-tools/runtime/execute"):
        assert gate.c.post(path, json={}, headers=h).status_code in (404, 405)


def test_no_per_request_execute_endpoint(gate):
    rid, _ = gate.prepared_runtime()
    r = gate.c.post(f"/ai-tools/runtime/requests/{rid}/execute", json={},
                    headers=gate.h())
    assert r.status_code in (404, 405)
