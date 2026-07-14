"""TOOL-B6: snapshot twin recomputation + provenance DAG validity."""
import copy

from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _twin(snap):
    return rt.build_snapshot_twin(tenant_id="t", runtime_request_id="r",
                                  snapshot=snap)


def _dag(snap):
    return rt.build_snapshot_provenance_dag(tenant_id="t",
                                            runtime_request_id="r",
                                            snapshot=snap)


def test_twin_matches_clean_snapshot(gate):
    _, _, snap = k.setup(gate)
    twin = _twin(snap)
    assert twin["twin_matched"] is True
    assert twin["signal"] is None
    assert twin["recomputed_snapshot_hash"] == snap["snapshot_hash"]


def test_twin_mismatch_on_mutated_field_without_rehash(gate):
    _, _, snap = k.setup(gate)
    mutated = copy.deepcopy(snap)
    # Mutate a field value WITHOUT recomputing snapshot_hash.
    mutated["fields"]["case_id"]["value"] = "TAMPERED"
    twin = _twin(mutated)
    assert twin["twin_matched"] is False
    assert twin["signal"] == "SNAPSHOT_TWIN_MISMATCH"


def test_twin_hash_deterministic_and_self_excluding(gate):
    _, _, snap = k.setup(gate)
    t1 = _twin(snap)
    t2 = _twin(snap)
    assert t1["runtime_snapshot_twin_hash"] == t2["runtime_snapshot_twin_hash"]
    # self-excluding: recomputing over the dict minus its own hash key matches.
    assert t1["runtime_snapshot_twin_hash"] == rt._core_hash(
        t1, "runtime_snapshot_twin_hash")


def test_provenance_dag_valid_with_origin(gate):
    _, _, snap = k.setup(gate)
    dag = _dag(snap)
    assert dag["dag_valid"] is True
    assert dag["provenance_status"] == "DAG_VALID"
    assert dag["signal"] is None


def test_provenance_dag_invalid_when_origin_removed(gate):
    _, _, snap = k.setup(gate)
    broken = copy.deepcopy(snap)
    broken["provenance_dag"] = {"nodes": [], "edges": []}
    dag = _dag(broken)
    assert dag["dag_valid"] is False
    assert dag["signal"] == "SNAPSHOT_PROVENANCE_INVALID"


def test_provenance_dag_invalid_on_dangling_edge(gate):
    _, _, snap = k.setup(gate)
    broken = copy.deepcopy(snap)
    broken["provenance_dag"] = {"nodes": ["ORIGIN"],
                                "edges": [{"from": "ORIGIN", "to": "GHOST"}]}
    dag = _dag(broken)
    assert dag["signal"] == "SNAPSHOT_PROVENANCE_INVALID"


def test_dag_hash_deterministic_and_self_excluding(gate):
    _, _, snap = k.setup(gate)
    d1 = _dag(snap)
    d2 = _dag(snap)
    assert d1["snapshot_provenance_dag_hash"] == \
        d2["snapshot_provenance_dag_hash"]
    assert d1["snapshot_provenance_dag_hash"] == rt._core_hash(
        d1, "snapshot_provenance_dag_hash")
