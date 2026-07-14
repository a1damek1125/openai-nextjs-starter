"""CORE-A3 — causal event links: parents precede children, same run, exist,
and are bound into the event hash."""
from finalis.ai_employee import run_ledger as R


def _chain(types):
    return R.assemble_events(
        run_id="r1", tenant_id="t1", task_id="task1", trace_id="tr1",
        actor_id="sys", specs=[{"event_type": t} for t in types],
        id_factory=lambda i: f"e{i}")


def test_each_event_cites_prior_as_causal_parent():
    ev = _chain(["RUN_CREATED", "RUN_STARTED", "PLAN_DRAFTED"])
    assert ev[0]["causal_parent_event_ids"] == []
    assert ev[1]["causal_parent_event_ids"] == [ev[0]["event_id"]]
    assert ev[2]["causal_parent_event_ids"] == [ev[1]["event_id"]]


def test_causal_link_bound_into_hash():
    ev = _chain(["RUN_CREATED", "RUN_STARTED"])
    tampered = {**ev[1], "causal_parent_event_ids": ["someone_else"]}
    assert R.event_hash({k: v for k, v in tampered.items()
                         if k != "event_hash"}) != ev[1]["event_hash"]


def test_missing_causal_parent_flagged_in_verify():
    ev = _chain(["RUN_CREATED", "RUN_STARTED", "PLAN_DRAFTED"])
    ev[2]["causal_parent_event_ids"] = ["does_not_exist"]
    chk = R.verify_events(ev)
    assert chk["causal_link_status"] == "INVALID"
    assert any("causal parent" in r for r in chk["tamper_reasons"])


def test_causal_parent_must_precede():
    # A parent that only appears later (not in events[:i-1]) is invalid.
    ev = _chain(["RUN_CREATED", "RUN_STARTED", "PLAN_DRAFTED"])
    ev[1]["causal_parent_event_ids"] = [ev[2]["event_id"]]   # forward ref
    chk = R.verify_events(ev)
    assert chk["causal_link_status"] == "INVALID"


def test_reducer_flags_bad_causal_parent():
    ev = _chain(["RUN_CREATED", "RUN_STARTED"])
    ev[1]["causal_parent_event_ids"] = ["ghost"]
    st = R.reduce_run(ev)
    assert any("causal parent" in e for e in st["replay_errors"])
