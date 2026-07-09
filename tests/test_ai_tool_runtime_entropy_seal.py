"""TOOL-B6: determinism entropy seal. Any nondeterministic entropy source blocks
trusted runtime output; the seal failure changes the runtime decision hash."""
import pytest
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _seal(gate, declared):
    return rt.build_entropy_seal(tenant_id=gate.tid, runtime_request_id="r",
                                 declared_entropy=declared)


def test_clean_no_entropy_sealed(gate):
    seal = _seal(gate, None)
    assert seal["seal_status"] == "ENTROPY_SEALED"
    assert seal["signal"] is None
    assert seal["detected_entropy_sources"] == []


@pytest.mark.parametrize("source", ["wall_clock", "random", "uuid", "pid",
                                    "thread_id", "network_time",
                                    "system_entropy"])
def test_declared_entropy_unseals(gate, source):
    """Any nondeterministic entropy source blocks trusted runtime output."""
    seal = _seal(gate, [source])
    assert seal["seal_status"] == "ENTROPY_UNSEALED"
    assert seal["signal"] == "DETERMINISM_ENTROPY_UNSEALED"
    assert source in seal["detected_entropy_sources"]


def test_entropy_source_detected_flag(gate):
    seal = _seal(gate, ["random"])
    assert seal["entropy_sealed"] is False
    assert "random" in seal["watched_entropy_sources"]


def test_prepare_random_entropy_blocked(gate):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap, declared_entropy=["random"])
    assert o["runtime_status"] == "RUNTIME_BLOCKED"
    assert o["dominant_signal"] == "DETERMINISM_ENTROPY_UNSEALED"


def test_entropy_seal_failure_changes_decision_hash(gate):
    """An entropy seal failure changes the runtime decision hash."""
    b5, b5r, snap = k.setup(gate)
    clean = k.prepare(gate, b5, b5r, snap)
    tainted = k.prepare(gate, b5, b5r, snap, declared_entropy=["random"])
    assert clean["runtime_decision_hash"] != tainted["runtime_decision_hash"]
    assert clean["determinism_entropy_seal"]["seal_status"] == "ENTROPY_SEALED"
    assert tainted["determinism_entropy_seal"]["seal_status"] == \
        "ENTROPY_UNSEALED"


def test_entropy_seal_deterministic(gate):
    a = _seal(gate, ["random", "uuid"])
    b = _seal(gate, ["uuid", "random"])
    assert a["determinism_entropy_seal_hash"] == \
        b["determinism_entropy_seal_hash"]
    clean_a = _seal(gate, None)
    clean_b = _seal(gate, None)
    assert clean_a["determinism_entropy_seal_hash"] == \
        clean_b["determinism_entropy_seal_hash"]
