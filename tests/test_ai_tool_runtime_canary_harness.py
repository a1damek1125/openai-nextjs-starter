"""TOOL-B6 v5 exfiltration-defense: synthetic canary harness (build_canary_harness).

The harness injects synthetic canaries into a LOCAL copy of the snapshot only.
It never mutates the real snapshot / production and cannot claim production DLP.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _snap(gate):
    return rt.build_snapshot(snapshot_id="snap1", tenant_id=gate.tid, epoch="5",
                             scope="case", fields=k.clean_fields())


def test_harness_ready_local_only_and_no_production_mutation(gate):
    h = rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                                snapshot=_snap(gate))
    assert h["harness_status"] == "CANARY_HARNESS_READY"
    assert h["mutates_production"] is False
    assert h["canary_scope"] == "SYNTHETIC_LOCAL_ONLY"


def test_harness_exposes_canary_fields_values_hashes(gate):
    h = rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                                snapshot=_snap(gate))
    assert h["canary_fields"] and h["canary_values"] and h["canary_hashes"]
    # values / hashes align 1:1 with the injected canary fields.
    assert len(h["canary_values"]) == len(h["canary_fields"])
    assert len(h["canary_hashes"]) == len(h["canary_fields"])


def test_harness_does_not_modify_real_snapshot(gate):
    snap = _snap(gate)
    before_fields = {k2: dict(v) for k2, v in snap["fields"].items()}
    before_hash = snap["snapshot_hash"]
    rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                            snapshot=snap)
    # The passed snapshot is untouched: canaries live only in the LOCAL twin.
    assert snap["fields"] == before_fields
    assert snap["snapshot_hash"] == before_hash
    assert all(not f.startswith("__canary") for f in snap["fields"])


def test_harness_cannot_claim_production_dlp(gate):
    h = rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                                snapshot=_snap(gate))
    # A synthetic local harness makes no production-DLP claim.
    assert h["mutates_production"] is False
    assert h["canary_scope"] == "SYNTHETIC_LOCAL_ONLY"
    assert h["_canary_snapshot"]["synthetic"] is True


def test_canary_twin_is_local_synthetic_copy_with_forbidden_canaries(gate):
    h = rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                                snapshot=_snap(gate))
    twin = h["_canary_snapshot"]
    assert twin["snapshot_id"].endswith("-canary")
    for name in h["canary_fields"]:
        assert twin["fields"][name]["data_class"] == "CANARY_FIELD"


def test_harness_hash_deterministic(gate):
    a = rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                                snapshot=_snap(gate))
    b = rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                                snapshot=_snap(gate))
    assert a["synthetic_canary_harness_hash"] == \
        b["synthetic_canary_harness_hash"]


def test_harness_hash_excludes_internal_canary_snapshot(gate):
    h = rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                                snapshot=_snap(gate))
    stored = h["synthetic_canary_harness_hash"]
    # Mutating the internal twin must not change the (self- and twin-excluding)
    # hash.
    h["_canary_snapshot"]["fields"]["__canary_secret"]["value"] = "MUTATED"
    recomputed = rt._core_hash(h, "synthetic_canary_harness_hash",
                               "_canary_snapshot")
    assert recomputed == stored
