"""EMP-A1 v1: hash-chained event history + projection rebuild (sections 40-41),
the pure admission reference kernel (section 33), the bounded interleaving model
check (section 34), and the shadow-policy laboratory (section 35).

The reference kernel is PURE (no I/O, no clock, no randomness, no global
mutation); its committed decision hash equals the projection rebuild; the model
check proves the concurrency safety invariants; and the shadow lab evaluates a
candidate policy over an IMMUTABLE snapshot with no item/claim/handoff/run
effect. A candidate that would admit a baseline-safety-denied request is
ineligible.
"""
from finalis.ai_employee import employee_work_inbox as wi
from finalis.ai_employee.tool_contracts import _core_hash
from tests import _emp_a1_kernel as k


_SNAP = {"tenant_id": "t1", "existing_by_key": {}, "recent_fingerprints": [],
         "capacity_state": {r: 64 for r in wi.DEMAND_RESOURCES},
         "shard_pressures": {}}


def _ev(event_type, prev, seq):
    return wi.build_work_event(
        event_type=event_type, tenant_id="t1", work_item_id="w1", actor_id="u",
        actor_type="HUMAN_USER", decision_hash="dh-" + str(seq),
        previous_event_hash=prev, sequence=seq, detail={}, created_at="t")


# --- event chain + projection rebuild (sections 40-41) ---------------------
def test_erm_build_work_event_hash_recomputes():
    e = _ev("WORK_ITEM_RECEIVED", None, 1)
    # event_hash is the core hash of the event over itself.
    assert e["event_hash"] == _core_hash(e, "event_hash")


def test_erm_build_work_event_genesis_previous():
    e = _ev("WORK_ITEM_RECEIVED", None, 1)
    assert e["previous_event_hash"] == wi.GENESIS


def test_erm_build_work_event_chain_links():
    e0 = _ev("WORK_ITEM_RECEIVED", None, 1)
    e1 = _ev("WORK_ITEM_QUEUE_PLACED", e0["event_hash"], 2)
    assert e1["previous_event_hash"] == e0["event_hash"]
    rebuild = wi.rebuild_work_item_projection([e0, e1])
    assert rebuild["result"] == "PROJECTION_REBUILD_IDENTICAL"


def test_erm_rebuild_broken_chain_invalid():
    # A first event whose previous hash is not GENESIS breaks the chain.
    e = _ev("WORK_ITEM_RECEIVED", "deadbeef", 1)
    assert wi.rebuild_work_item_projection([e])["result"] == \
        "EVENT_CHAIN_INVALID"


def test_erm_rebuild_broken_link_mid_chain_invalid():
    e0 = _ev("WORK_ITEM_RECEIVED", None, 1)
    e1 = _ev("WORK_ITEM_QUEUE_PLACED", "not-the-prev-hash", 2)
    assert wi.rebuild_work_item_projection([e0, e1])["result"] == \
        "EVENT_CHAIN_INVALID"


def test_erm_rebuild_unknown_event_type():
    e = _ev("TOTALLY_UNKNOWN_EVENT", None, 1)
    assert wi.rebuild_work_item_projection([e])["result"] == "UNSUPPORTED_EVENT"


def test_erm_rebuild_empty_chain_invalid():
    assert wi.rebuild_work_item_projection([])["result"] == "EVENT_CHAIN_INVALID"


def test_erm_api_events_are_hash_chained(gate):
    wid, _ = gate.admitted_work()
    evs = gate.wki(wid, "/events").json()["events"]
    assert len(evs) >= 2
    prev = wi.GENESIS
    for e in evs:
        assert e["previous_event_hash"] == prev
        assert e["event_hash"] == _core_hash(e, "event_hash")
        prev = e["event_hash"]


def test_erm_api_events_projection_rebuild_identical(gate):
    wid, _ = gate.admitted_work()
    ev = gate.wki(wid, "/events").json()
    assert ev["projection_rebuild"]["result"] == "PROJECTION_REBUILD_IDENTICAL"


# --- pure reference kernel (section 33) ------------------------------------
def test_erm_reference_kernel_no_external_effect():
    o = k.clean()
    for f in ("run_created", "tool_transaction_started", "provider_called",
              "tool_called", "message_sent", "payment_executed",
              "external_crm_mutated", "outbox_released",
              "external_state_mutated"):
        assert o[f] is False


def test_erm_reference_kernel_no_snapshot_side_effect():
    snap = {"tenant_id": "t1"}
    before = dict(snap)
    wi.evaluate_admission(snap, k.req(), {})
    assert snap == before  # pure: no mutation of the input snapshot


def test_erm_reference_kernel_deterministic():
    assert k.clean()["decision_hash"] == k.clean()["decision_hash"]


def test_erm_api_decision_hash_equals_committed_item(gate):
    _, o = gate.admitted_work()
    assert o["decision_hash"] == o["work_item"]["decision_hash"]


# --- bounded model check (section 34) --------------------------------------
def test_erm_bounded_model_check_all_hold():
    mc = wi.run_bounded_model_check()
    assert mc["all_invariants_hold"] is True
    assert mc["violations"] == []


def test_erm_bounded_model_check_invariant_count():
    assert wi.run_bounded_model_check()["invariant_count"] >= 12


def test_erm_bounded_model_check_names_present():
    invs = wi.run_bounded_model_check()["invariants"]
    for name in ("at_most_one_active_claim", "monotonic_fencing_tokens",
                 "at_most_one_active_handoff", "aborted_txn_no_mutation",
                 "serial_order_equivalent", "no_cross_tenant_access"):
        assert name in invs


# --- shadow-policy laboratory (section 35) ---------------------------------
def test_erm_simulate_policy_has_no_effect():
    sim = wi.simulate_policy(snapshot=_SNAP, requests=[k.req()],
                             baseline_policy={}, candidate_policy={})
    assert sim["mutated_items"] is False
    assert sim["created_claim"] is False
    assert sim["created_handoff"] is False
    assert sim["created_run"] is False


def test_erm_simulate_policy_hard_safety_regression_ineligible():
    # Baseline denies (tiny payload limit -> PAYLOAD_LIMIT_EXCEEDED, a hard
    # safety denial); a looser candidate would admit it -> regression.
    big = {"blob": "x" * 2000}
    reqs = [k.req(raw_payload=big)]
    sim = wi.simulate_policy(
        snapshot=_SNAP, requests=reqs, baseline_policy={"max_payload_bytes": 50},
        candidate_policy={"max_payload_bytes": 65536})
    assert sim["hard_safety_regression"] is True
    assert sim["candidate_eligible"] is False


def test_erm_simulate_policy_baseline_safety_denied_request():
    # A SLACK (disabled-source) request is safety-denied at the baseline; an
    # identical candidate policy cannot re-admit it, so no regression.
    reqs = [k.req(source_type="SLACK")]
    base = wi.evaluate_admission(_SNAP, reqs[0], {})
    assert base["safety_denied"] is True
    sim = wi.simulate_policy(snapshot=_SNAP, requests=reqs, baseline_policy={},
                             candidate_policy={})
    assert sim["hard_safety_regression"] is False
    assert sim["candidate_eligible"] is True


# --- API drills: every drill proves no external effect ---------------------
def test_erm_api_simulate_policy_no_effect(gate):
    r = gate.c.post("/ai-employee/work-inbox/simulate-policy",
                    json={"requests": [k.req()], "candidate_policy": {}},
                    headers=gate.h())
    assert r.status_code == 200
    j = r.json()
    assert j["mutated_items"] is False and j["created_run"] is False
    assert j["created_claim"] is False and j["created_handoff"] is False


def test_erm_api_reference_kernel_drill(gate):
    r = gate.c.post("/ai-employee/work-inbox/run-reference-kernel-drill",
                    json={}, headers=gate.h())
    assert r.status_code == 200
    j = r.json()
    assert j["reference_kernel_deterministic"] is True
    assert j["run_created"] is False
    assert j["tool_transaction_started"] is False
    assert j["provider_called"] is False
    assert j["outbox_released"] is False


def test_erm_api_concurrency_drill(gate):
    r = gate.c.post("/ai-employee/work-inbox/run-concurrency-drill",
                    json={}, headers=gate.h())
    assert r.status_code == 200
    j = r.json()
    assert j["model_check"]["all_invariants_hold"] is True
    assert j["run_created"] is False
