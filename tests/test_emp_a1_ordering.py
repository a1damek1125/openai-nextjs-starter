"""EMP-A1 v1: R-FSAFEQ ordering (section 29), hysteresis (section 29.5) and
monotonic safety of the advisory order kernel.

Ordering is ORDER_RECOMMENDATION_ONLY: rank_items produces a recommendation over
hard-eligible READY items using fixed-point virtual deadlines. It never mutates
work-item state and can never make an item READY or grant it authority.
"""
from finalis.ai_employee import employee_work_inbox as wi


def _item(work_item_id="wi-1", state="READY", weight=1, priority="NORMAL",
          seq=1, floor=None, upper=None, **over):
    item = {
        "work_item_id": work_item_id, "work_item_state": state,
        "tenant_id": "t1", "effective_weight": weight,
        "priority_class": priority, "created_sequence": seq,
        "missing_input_fields": [], "required_capabilities": ["case.read"],
        "approval_requirement": "NONE", "assignment_valid": True,
        "revoked": False, "demand_envelope_valid": True,
        "calibration_fallback_valid": True,
        "active_eligible_age": 0, "aging_horizon": 100,
        "work_demand_envelope": {
            "deterministic_floor": floor or {"A": 1, "B": 1},
            "safety_upper": upper or {"A": 4, "B": 4}},
    }
    item.update(over)
    return item


# --- hard eligibility (section 29) -----------------------------------------
def test_hard_eligible_clean():
    assert wi.hard_eligible(item=_item())["hard_eligible"] is True


def test_hard_eligible_requires_state_ready():
    r = wi.hard_eligible(item=_item(state="NEEDS_APPROVAL"))
    assert r["hard_eligible"] is False
    assert r["checks"]["state_ready"] is False


def test_hard_eligible_requires_inputs_complete():
    r = wi.hard_eligible(item=_item(missing_input_fields=["message_intent"]))
    assert r["hard_eligible"] is False
    assert r["checks"]["inputs_complete"] is False


def test_hard_eligible_requires_approval_ok():
    r = wi.hard_eligible(item=_item(approval_requirement="STANDARD",
                                    approval_valid=False))
    assert r["hard_eligible"] is False
    assert r["checks"]["approval_ok"] is False


def test_hard_eligible_requires_not_revoked():
    r = wi.hard_eligible(item=_item(revoked=True))
    assert r["hard_eligible"] is False
    assert r["checks"]["not_revoked"] is False


def test_hard_eligible_requires_not_quarantined():
    r = wi.hard_eligible(item=_item(state="QUARANTINED"))
    assert r["hard_eligible"] is False
    assert r["checks"]["not_quarantined"] is False


def test_hard_eligible_requires_valid_demand():
    r = wi.hard_eligible(item=_item(demand_envelope_valid=False))
    assert r["hard_eligible"] is False
    assert r["checks"]["demand_envelope_valid"] is False


# --- virtual deadlines (section 29) ----------------------------------------
def test_virtual_deadlines_fixed_point_integers():
    vd = wi.virtual_deadlines(item=_item(), flow_virtual_time=0)
    assert isinstance(vd["vd_lower"], int)
    assert isinstance(vd["vd_upper"], int)


def test_virtual_deadlines_lower_le_upper():
    vd = wi.virtual_deadlines(item=_item(), flow_virtual_time=0)
    assert vd["vd_lower"] <= vd["vd_upper"]


def test_virtual_deadlines_weight_tightens():
    light = wi.virtual_deadlines(item=_item(weight=1), flow_virtual_time=0)
    heavy = wi.virtual_deadlines(item=_item(weight=8), flow_virtual_time=0)
    # A higher effective weight shrinks the virtual deadline (earlier service).
    assert heavy["vd_upper"] <= light["vd_upper"]


# --- certain order (section 29) --------------------------------------------
def test_certain_order_non_overlapping_a_before_b():
    a = wi.virtual_deadlines(item=_item(upper={"A": 1}, floor={"A": 1}),
                             flow_virtual_time=0)
    b = wi.virtual_deadlines(item=_item(upper={"A": 60}, floor={"A": 50}),
                             flow_virtual_time=0)
    assert wi.certain_order(a=a, b=b) == "A_BEFORE_B"


def test_certain_order_reverse_b_before_a():
    a = wi.virtual_deadlines(item=_item(upper={"A": 60}, floor={"A": 50}),
                             flow_virtual_time=0)
    b = wi.virtual_deadlines(item=_item(upper={"A": 1}, floor={"A": 1}),
                             flow_virtual_time=0)
    assert wi.certain_order(a=a, b=b) == "B_BEFORE_A"


def test_certain_order_overlap_is_uncertain():
    a = wi.virtual_deadlines(item=_item(floor={"A": 1}, upper={"A": 40}),
                             flow_virtual_time=0)
    b = wi.virtual_deadlines(item=_item(floor={"A": 20}, upper={"A": 60}),
                             flow_virtual_time=0)
    assert wi.certain_order(a=a, b=b) == "ORDER_INTERVAL_OVERLAP"


def test_certain_order_margin_expands_overlap():
    a = wi.virtual_deadlines(item=_item(floor={"A": 1}, upper={"A": 10}),
                             flow_virtual_time=0)
    b = wi.virtual_deadlines(item=_item(floor={"A": 11}, upper={"A": 20}),
                             flow_virtual_time=0)
    assert wi.certain_order(a=a, b=b) == "A_BEFORE_B"
    # A large stability margin removes the certainty -> overlap.
    assert wi.certain_order(a=a, b=b, stability_margin=10 ** 9) == \
        "ORDER_INTERVAL_OVERLAP"


# --- rank_items (section 29) -----------------------------------------------
def test_rank_items_recommendation_only():
    r = wi.rank_items(items=[_item()])
    assert r["recommendation_only"] is True
    assert r["signal"] == "ORDER_RECOMMENDATION_ONLY"


def test_rank_items_orders_by_virtual_deadline():
    early = _item(work_item_id="EARLY", floor={"A": 1}, upper={"A": 2})
    late = _item(work_item_id="LATE", floor={"A": 50}, upper={"A": 60})
    ranked = wi.rank_items(items=[late, early])["ranked"]
    assert [x["work_item_id"] for x in ranked] == ["EARLY", "LATE"]


def test_rank_items_excludes_non_hard_eligible():
    ready = _item(work_item_id="R")
    blocked = _item(work_item_id="B", state="NEEDS_APPROVAL")
    ranked = wi.rank_items(items=[ready, blocked])["ranked"]
    assert [x["work_item_id"] for x in ranked] == ["R"]


def test_rank_items_priority_class_wins():
    # CRITICAL outranks NORMAL even with a later virtual deadline.
    crit = _item(work_item_id="CRIT", priority="CRITICAL",
                 floor={"A": 50}, upper={"A": 60})
    norm = _item(work_item_id="NORM", priority="NORMAL",
                 floor={"A": 1}, upper={"A": 2})
    ranked = wi.rank_items(items=[norm, crit])["ranked"]
    assert [x["work_item_id"] for x in ranked] == ["CRIT", "NORM"]


def test_rank_items_stable_when_previous_matches():
    a = _item(work_item_id="A", floor={"A": 1}, upper={"A": 2})
    b = _item(work_item_id="B", floor={"A": 50}, upper={"A": 60})
    r = wi.rank_items(items=[a, b], previous_order=["A", "B"])
    assert r["rank_stability_status"] == "STABLE"


def test_rank_items_reordered_when_previous_differs():
    a = _item(work_item_id="A", floor={"A": 1}, upper={"A": 2})
    b = _item(work_item_id="B", floor={"A": 50}, upper={"A": 60})
    r = wi.rank_items(items=[a, b], previous_order=["B", "A"])
    assert r["rank_stability_status"] == "REORDERED"


# --- hysteresis (section 29.5) ---------------------------------------------
def test_hysteresis_preserves_order_under_overlap():
    # Two items with overlapping virtual-deadline intervals: passing the prior
    # relative order keeps the ranking STABLE (no churn from ties).
    a = _item(work_item_id="A", floor={"A": 10}, upper={"A": 40})
    b = _item(work_item_id="B", floor={"A": 10}, upper={"A": 40}, seq=2)
    prev = [x["work_item_id"] for x in wi.rank_items(items=[a, b])["ranked"]]
    r = wi.rank_items(items=[a, b], previous_order=prev)
    assert r["rank_stability_status"] == "STABLE"


# --- monotonic safety: ordering is advisory only ---------------------------
def test_ordering_never_mutates_item_state():
    a = _item(work_item_id="A")
    b = _item(work_item_id="B", state="NEEDS_APPROVAL")
    before = (a["work_item_state"], b["work_item_state"])
    r = wi.rank_items(items=[a, b])
    assert r["recommendation_only"] is True
    assert (a["work_item_state"], b["work_item_state"]) == before
    assert b["work_item_state"] == "NEEDS_APPROVAL"


def test_ordering_cannot_make_item_ready():
    # A non-READY item is excluded and stays non-READY — priority cannot admit.
    blocked = _item(work_item_id="X", state="NEEDS_APPROVAL",
                    priority="CRITICAL")
    ranked = wi.rank_items(items=[blocked])["ranked"]
    assert ranked == []
    assert blocked["work_item_state"] == "NEEDS_APPROVAL"


# --- API layer -------------------------------------------------------------
def test_api_priority_explanation_advisory(gate):
    wid, _ = gate.admitted_work()
    pe = gate.wki(wid, "/priority-explanation").json()
    assert pe["priority_class"] == "NORMAL"
    assert "ORDER_RECOMMENDATION_ONLY" in pe["honesty_labels"]


def test_api_admission_ready_no_execution(gate):
    wid, _ = gate.admitted_work()
    adm = gate.wki(wid, "/admission").json()
    assert adm["work_item_state"] == "READY"
    assert "ORDER_RECOMMENDATION_ONLY" in adm["honesty_labels"]
