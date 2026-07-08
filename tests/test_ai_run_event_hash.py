"""CORE-A3 — run-event hash: deterministic, excludes itself + volatile time,
changes on any identity/index/chain/causal/payload change."""
import pytest

from finalis.ai_employee import run_ledger as R


def _env(**over):
    base = dict(
        event_id="e1", run_id="r1", tenant_id="t1", task_id="task1",
        event_index=1, event_type="RUN_CREATED", event_status="RECORDED",
        actor_id="sys", actor_type="SYSTEM", trace_id="tr1", span_id="s1",
        parent_span_id=None, event_source="finalis/run", event_subject="r1",
        previous_event_hash=R.GENESIS, causal_parent_event_ids=[],
        event_payload={"k": "v"})
    base.update(over)
    return R.build_event_envelope(**base)


def _h(**over):
    return R.event_hash(_env(**over))


def test_same_event_same_hash():
    assert _h() == _h()


def test_key_order_independent():
    import json
    e = _env()
    assert R.event_hash(json.loads(json.dumps(e))) == R.event_hash(e)


def test_hash_excludes_itself_and_time():
    e = _env()
    h = R.event_hash(e)
    e2 = {**e, "event_hash": "injected", "event_time": "2020-01-01",
          "created_at": "2020-01-01"}
    assert R.event_hash(e2) == h


@pytest.mark.parametrize("field,value", [
    ("event_payload", {"k": "other"}),
    ("event_type", "RUN_STARTED"),
    ("event_index", 2),
    ("previous_event_hash", "deadbeef"),
    ("causal_parent_event_ids", ["x"]),
    ("tenant_id", "t2"),
    ("run_id", "r2"),
    ("task_id", "task2"),
])
def test_change_changes_hash(field, value):
    assert _h(**{field: value}) != _h()


def test_payload_hash_bound_in():
    # event_payload_hash is derived from payload and is part of the envelope,
    # so a payload change is doubly bound into the event hash.
    e = _env()
    assert e["event_payload_hash"] == R.payload_hash({"k": "v"})


def test_nan_infinity_rejected():
    with pytest.raises(ValueError):
        R.canonical_json({"x": float("nan")})
    with pytest.raises(ValueError):
        R.canonical_json({"x": float("inf")})
