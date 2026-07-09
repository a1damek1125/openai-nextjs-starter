"""TOOL-B5 null broker: four-plane integrity + plane non-interference."""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k


def _four_plane(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = k.make_env(gate, d, pobj, broker_request_id="brfp")
    fp = b.build_four_plane_model(tenant_id=gate.tid, broker_request_id="brfp",
                                  envelope=env, b4_decision=d)
    return fp


def test_clean_four_plane_integrity_matched(gate):
    fp = _four_plane(gate)
    assert fp["four_plane_integrity_status"] == "MATCHED"
    assert fp["signal"] is None


def test_clean_all_four_planes_cannot_execute(gate):
    fp = _four_plane(gate)
    for name in ("planner_plane", "enforcement_plane", "effect_plane",
                 "recordkeeping_plane"):
        assert fp[name]["can_execute"] is False


def test_clean_effect_plane_is_null(gate):
    fp = _four_plane(gate)
    eff = fp["effect_plane"]
    assert eff["effect_outcome"] == "NO_EFFECT_OUTCOME"
    assert eff["callable"] is False
    assert eff["adapter_resolved"] is False
    assert eff["provider_called"] is False
    assert eff["token_issued"] is False


def test_clean_recordkeeping_does_not_enable_effect(gate):
    fp = _four_plane(gate)
    assert fp["recordkeeping_plane"]["enables_effect_plane"] is False


def test_clean_plane_non_interference_matched(gate):
    fp = _four_plane(gate)
    ni = b.build_plane_non_interference(tenant_id=gate.tid,
                                        broker_request_id="brfp", four_plane=fp)
    assert ni["non_interference_status"] == "MATCHED"
    assert ni["signal"] is None
    assert ni["interference_findings"] == []


def test_recordkeeping_enabling_effect_is_interference(gate):
    fp = _four_plane(gate)
    tampered = {**fp, "recordkeeping_plane": {
        **fp["recordkeeping_plane"], "enables_effect_plane": True}}
    ni = b.build_plane_non_interference(tenant_id=gate.tid,
                                        broker_request_id="brfp",
                                        four_plane=tampered)
    assert ni["non_interference_status"] == "FAILED"
    assert ni["signal"] == "PLANE_INTERFERENCE_DETECTED"
    assert "RECORDKEEPING_ENABLES_EFFECT" in ni["interference_findings"]


def test_callable_effect_plane_is_interference(gate):
    fp = _four_plane(gate)
    tampered = {**fp, "effect_plane": {**fp["effect_plane"], "callable": True}}
    ni = b.build_plane_non_interference(tenant_id=gate.tid,
                                        broker_request_id="brfp",
                                        four_plane=tampered)
    assert ni["non_interference_status"] == "FAILED"
    assert ni["signal"] == "PLANE_INTERFERENCE_DETECTED"
    assert "EFFECT_PLANE_CALLABLE" in ni["interference_findings"]


def test_prepared_outcome_four_plane_and_non_interference_matched(gate):
    o = k.clean_outcome(gate)
    assert o["four_plane_model"]["four_plane_integrity_status"] == "MATCHED"
    assert o["plane_non_interference"]["non_interference_status"] == "MATCHED"
