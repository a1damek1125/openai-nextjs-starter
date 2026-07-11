"""EMP-A1 v1: bounded OPTIMIZATION kernel — flow-fairness deficit (section 26),
active eligible age (section 27) and deterministic shuffle sharding (section 28).

The optimization kernel is advisory only: it may reorder/shard/age work but can
NEVER bypass a safety denial or grant authority. Fairness deficit, age credit
and shard placement are pure, deterministic and carry no runtime randomness.
"""
from finalis.ai_employee import employee_work_inbox as wi
from tests import _emp_a1_kernel as k


def _fair(deficit=0, entitled=1, governed=0, mode=None):
    req = {"entitled_service": entitled, "governed_service": governed}
    if mode is not None:
        req["fairness_mode"] = mode
    return wi.evaluate_fairness(flow_state={"fairness_deficit": deficit},
                               req=req, policy={})


def _flow_key(principal="user:1", work_type="case_summary", target="case:1",
              queue_group="g"):
    return wi.compute_flow_key(
        tenant_id="t1", req={"source_principal_id": principal},
        intent={"work_type": work_type, "canonical_target_refs": [target]},
        queue_group=queue_group)


# --- flow fairness deficit (section 26) ------------------------------------
def test_fairness_deficit_positive_is_owed():
    f = _fair(deficit=0, entitled=5, governed=1)
    assert f["fairness_deficit"] > 0
    assert f["fairness_deficit_class"] == "OWED"


def test_fairness_deficit_negative_is_overserved():
    f = _fair(deficit=0, entitled=0, governed=5)
    assert f["fairness_deficit"] < 0
    assert f["fairness_deficit_class"] == "OVERSERVED"


def test_fairness_deficit_zero_is_even():
    f = _fair(deficit=0, entitled=3, governed=3)
    assert f["fairness_deficit"] == 0
    assert f["fairness_deficit_class"] == "EVEN"


def test_fairness_never_bypasses_safety():
    assert _fair(deficit=100000)["bypasses_safety"] is False


def test_fairness_survives_retry():
    assert _fair()["survives_retry"] is True


def test_fairness_discounted_history_halves_prior():
    # DISCOUNTED_HISTORY (default): rho=0.5 -> (prev // 2) + entitled - governed.
    f = _fair(deficit=10, entitled=1, governed=0, mode="DISCOUNTED_HISTORY")
    assert f["fairness_deficit"] == (10 // 2) + 1 - 0
    assert f["fairness_mode"] == "DISCOUNTED_HISTORY"


def test_fairness_full_history_adds_prior():
    # FULL_HISTORY: prev + entitled - governed (prior fully retained).
    f = _fair(deficit=10, entitled=1, governed=0, mode="FULL_HISTORY")
    assert f["fairness_deficit"] == 10 + 1 - 0


def test_fairness_bounded_window_ignores_prior():
    # BOUNDED_WINDOW: entitled - governed (prior ignored entirely).
    f = _fair(deficit=10, entitled=1, governed=0, mode="BOUNDED_WINDOW")
    assert f["fairness_deficit"] == 1 - 0


def test_fairness_deficit_cannot_bypass_approval():
    # A large positive (OWED) fairness deficit cannot admit an item that the
    # safety kernel says NEEDS_APPROVAL — optimization never overrides safety.
    o = k.evaluate(snapshot={"tenant_id": "t1",
                             "flow_state": {"fairness_deficit": 500000}},
                   work_type="compliance_escalation",
                   canonical_parameters={"target": "case:E-1"})
    assert o["fairness"]["fairness_deficit_class"] == "OWED"
    assert o["fairness"]["fairness_deficit"] > 0
    assert o["disposition"] == "NEEDS_APPROVAL"
    assert o["resulting_state"] != "READY"
    assert "APPROVAL_REQUIRED" in o["reason_codes"]


def test_fairness_deficit_does_not_bypass_disabled_source():
    o = k.evaluate(snapshot={"tenant_id": "t1",
                             "flow_state": {"fairness_deficit": 500000}},
                   source_type="SLACK")
    assert o["safety_denied"] is True
    assert o["disposition"] == "REJECTED"


# --- active eligible age (section 27) --------------------------------------
def test_age_accrues_only_in_ready():
    a = wi.age_credit(state="READY", active_eligible_age=50, aging_horizon=100)
    assert a["accrues_age"] is True
    assert a["age_credit"] > 0


def test_age_does_not_accrue_outside_ready():
    for st in ("NEEDS_APPROVAL", "RESERVED", "CLAIMED", "DEFERRED_RISK",
               "QUARANTINED", "BLOCKED"):
        a = wi.age_credit(state=st, active_eligible_age=999, aging_horizon=100)
        assert a["accrues_age"] is False
        assert a["age_credit"] == 0


def test_age_credit_is_bounded():
    # Fixed-point credit is capped at 1000 no matter how old the item is.
    a = wi.age_credit(state="READY", active_eligible_age=10 ** 9,
                      aging_horizon=100)
    assert a["age_credit"] <= 1000


def test_age_credit_monotonic_in_age():
    horizon = 100
    prev = -1
    for age in (0, 10, 25, 50, 75, 100, 200):
        c = wi.age_credit(state="READY", active_eligible_age=age,
                          aging_horizon=horizon)["age_credit"]
        assert c >= prev
        prev = c


def test_age_cannot_grant_authority():
    # A non-hard-eligible item (missing inputs) never becomes eligible via age.
    item = {"work_item_state": "READY", "tenant_id": "t1",
            "required_capabilities": ["case.read"],
            "missing_input_fields": ["message_intent"],
            "active_eligible_age": 10 ** 9, "aging_horizon": 1,
            "effective_weight": 1, "priority_class": "NORMAL",
            "work_item_id": "wi-x", "created_sequence": 1,
            "work_demand_envelope": {"deterministic_floor": {"A": 1},
                                     "safety_upper": {"A": 4}}}
    assert wi.age_credit(state="READY", active_eligible_age=10 ** 9,
                         aging_horizon=1)["age_credit"] <= 1000
    assert wi.hard_eligible(item=item)["hard_eligible"] is False
    assert wi.rank_items(items=[item])["ranked"] == []


# --- deterministic shuffle sharding (section 28) ---------------------------
def test_flow_key_deterministic():
    assert _flow_key() == _flow_key()


def test_flow_key_changes_with_inputs():
    assert _flow_key(principal="user:1") != _flow_key(principal="user:2")
    assert _flow_key(work_type="case_summary") != _flow_key(
        work_type="evidence_review")


def test_placement_no_runtime_randomness():
    p = wi.place_shard(flow_key=_flow_key(),
                       policy={"queue_count": 8, "shuffle_hand_size": 3},
                       shard_pressures={})
    assert p["no_runtime_randomness"] is True
    assert p["signal"] == "QUEUE_PLACED"


def test_placement_is_deterministic():
    fk = _flow_key()
    pol = {"queue_count": 8, "shuffle_hand_size": 3}
    p1 = wi.place_shard(flow_key=fk, policy=pol, shard_pressures={})
    p2 = wi.place_shard(flow_key=fk, policy=pol, shard_pressures={})
    assert p1["queue_shard"] == p2["queue_shard"]
    assert p1["candidate_shards"] == p2["candidate_shards"]


def test_queue_shard_within_bounds():
    for qc in (4, 8, 16, 32):
        p = wi.place_shard(flow_key=_flow_key(),
                           policy={"queue_count": qc, "shuffle_hand_size": 3},
                           shard_pressures={})
        assert 0 <= p["queue_shard"] < qc
        for c in p["candidate_shards"]:
            assert 0 <= c < qc


def test_placement_prefers_lowest_pressure():
    # Selection sorts by (pressure, flows, items, shard); loading the default
    # winner with high pressure forces a different candidate to be chosen.
    fk = _flow_key()
    pol = {"queue_count": 8, "shuffle_hand_size": 3}
    base = wi.place_shard(flow_key=fk, policy=pol, shard_pressures={})
    winner = base["queue_shard"]
    alt = next(c for c in base["candidate_shards"] if c != winner)
    forced = wi.place_shard(flow_key=fk, policy=pol,
                            shard_pressures={winner: {"pressure": 999,
                                                      "flows": 0, "items": 0}})
    assert forced["queue_shard"] == alt
    assert forced["queue_shard"] != winner


def test_placement_prefers_lowest_shard_on_tie():
    # With equal pressure across all candidates the lowest shard index wins.
    p = wi.place_shard(flow_key=_flow_key(),
                       policy={"queue_count": 8, "shuffle_hand_size": 3},
                       shard_pressures={})
    assert p["queue_shard"] == min(p["candidate_shards"])


def test_placement_queue_count_and_hand_from_policy():
    p = wi.place_shard(flow_key=_flow_key(),
                       policy={"queue_count": 16, "shuffle_hand_size": 5},
                       shard_pressures={})
    assert p["queue_count"] == 16
    assert p["hand_size"] == 5
    assert len(p["candidate_shards"]) == 5


def test_placement_versioned_shuffle_changes_candidates():
    # The placement policy version is a versioned input to the shuffle hash;
    # different versions produce a different (still deterministic) candidate set.
    fk = _flow_key()
    a = wi.place_shard(flow_key=fk, policy={
        "queue_count": 32, "shuffle_hand_size": 4,
        "placement_policy_version": "ppv-1"}, shard_pressures={})
    b = wi.place_shard(flow_key=fk, policy={
        "queue_count": 32, "shuffle_hand_size": 4,
        "placement_policy_version": "ppv-2"}, shard_pressures={})
    assert a["candidate_shards"] != b["candidate_shards"]


# --- API layer -------------------------------------------------------------
def test_api_priority_explanation_shard_and_fairness(gate):
    wid, _ = gate.admitted_work()
    pe = gate.wi(wid, "/priority-explanation").json()
    assert 0 <= pe["queue_shard"] < 8
    assert pe["fairness_deficit_class"] in ("OWED", "EVEN", "OVERSERVED")


def test_api_flow_key_present_and_shard_bounded(gate):
    wid, _ = gate.admitted_work()
    item = gate.wi(wid).json()
    assert item["flow_key"]
    assert 0 <= item["queue_shard"] < 8
