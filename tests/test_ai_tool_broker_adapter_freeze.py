"""TOOL-B5 adapter manifest freeze + adapter non-resolution.

The null broker freezes the adapter manifest at prepare-time and proves the
adapter is never resolved. A clean (null-placeholder) manifest freezes cleanly;
a callable manifest drifts and blocks; a resolvable/endpoint/provider manifest
is a real-adapter-resolution attempt and quarantines. Executes nothing.
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k


def test_clean_manifest_freezes_and_adapter_not_resolved(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert)
    assert o["broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    freeze = o["adapter_manifest_freeze"]
    assert freeze["freeze_status"] == "MANIFEST_FROZEN"
    assert freeze["callable_adapter_detected"] is False
    assert freeze["manifest_drift_detected"] is False
    assert freeze["signal"] is None
    nonres = o["adapter_non_resolution"]
    assert nonres["non_resolution_status"] == "NULL_ADAPTER_ONLY"
    assert nonres["adapter_resolved"] is False
    assert nonres["signal"] is None


def test_callable_adapter_manifest_drifts_and_blocks(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  adapter_manifest={"callable": True})
    assert o["broker_status"] == "BLOCKED"
    assert o["dominant_signal"] == "ADAPTER_MANIFEST_DRIFT"
    assert o["adapter_manifest_freeze"]["callable_adapter_detected"] is True


def test_resolved_adapter_manifest_quarantines(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  adapter_manifest={"resolved": True})
    assert o["broker_status"] == "QUARANTINED"
    assert o["dominant_signal"] == "REAL_ADAPTER_RESOLUTION_ATTEMPT"
    nonres = o["adapter_non_resolution"]
    assert nonres["non_resolution_status"] == "REAL_ADAPTER_RESOLUTION_DETECTED"
    assert nonres["adapter_resolved"] is True


def test_endpoint_adapter_manifest_quarantines(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  adapter_manifest={"endpoint": "http://x"})
    assert o["broker_status"] == "QUARANTINED"
    assert o["dominant_signal"] == "REAL_ADAPTER_RESOLUTION_ATTEMPT"
    assert "ADAPTER_HAS_ENDPOINT" in o["adapter_non_resolution"][
        "quarantine_findings"]


def test_provider_url_adapter_manifest_quarantines(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  adapter_manifest={"provider_url": "http://x"})
    assert o["broker_status"] == "QUARANTINED"
    assert o["dominant_signal"] == "REAL_ADAPTER_RESOLUTION_ATTEMPT"


def test_freeze_hash_deterministic():
    kw = dict(tenant_id="t", broker_request_id="r",
              adapter_manifest={"adapter_kind": "NULL_PLACEHOLDER"},
              sealed_manifest_hash=None)
    a = b.build_adapter_manifest_freeze(**kw)
    a2 = b.build_adapter_manifest_freeze(**kw)
    assert a["adapter_manifest_freeze_hash"] == a2[
        "adapter_manifest_freeze_hash"]
    assert a["freeze_status"] == "MANIFEST_FROZEN"


def test_manifest_drift_from_sealed_hash_detected():
    # Seal against one manifest, then present a different (still non-callable)
    # manifest -> drift is detected even without any callable flag.
    sealed = b.build_adapter_manifest_freeze(
        tenant_id="t", broker_request_id="r",
        adapter_manifest={"adapter_kind": "OTHER", "callable": False,
                          "resolvable": False},
        sealed_manifest_hash=None)["frozen_manifest_hash"]
    drift = b.build_adapter_manifest_freeze(
        tenant_id="t", broker_request_id="r", adapter_manifest=None,
        sealed_manifest_hash=sealed)
    assert drift["manifest_drift_detected"] is True
    assert drift["callable_adapter_detected"] is False
    assert drift["freeze_status"] == "ADAPTER_MANIFEST_DRIFT"
    assert drift["signal"] == "ADAPTER_MANIFEST_DRIFT"


def test_adapter_non_resolution_builder_direct():
    clean = b.build_adapter_non_resolution(
        tenant_id="t", broker_request_id="r", adapter_manifest=None)
    assert clean["non_resolution_status"] == "NULL_ADAPTER_ONLY"
    assert clean["signal"] is None
    resolved = b.build_adapter_non_resolution(
        tenant_id="t", broker_request_id="r",
        adapter_manifest={"resolved": True})
    assert resolved["non_resolution_status"] == \
        "REAL_ADAPTER_RESOLUTION_DETECTED"
    assert resolved["signal"] == "REAL_ADAPTER_RESOLUTION_ATTEMPT"
    assert "ADAPTER_RESOLVED" in resolved["quarantine_findings"]
