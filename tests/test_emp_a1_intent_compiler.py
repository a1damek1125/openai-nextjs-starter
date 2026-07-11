"""EMP-A1 v1: deterministic intent compiler (section 9) + canonical work-unit
registry (section 10).

The intent compiler is pure and deterministic: it never guesses critical
values, produces a stable canonical business key and compiled-intent hash for a
given request, and fails closed on unregistered work types, invalid targets, and
missing required fields. The registry is the sole authority for split policy,
approval class, and the deterministic demand floor/upper vectors.
"""
from finalis.ai_employee import employee_work_inbox as wi
from tests import _emp_a1_kernel as k


def _compile(**over):
    """Compile the intent for a canonical request via the pure compiler."""
    r = k.req(**over)
    return wi.compile_intent(tenant_id=r["tenant_id"], req=r, policy={})


# --- kernel layer: intent compiler -----------------------------------------
def test_intent_compiler_clean_status_compiled():
    i = _compile()
    assert i["intent_status"] == "INTENT_COMPILED"
    assert i["signal"] == "INTENT_COMPILED"
    assert i["missing_fields"] == []


def test_intent_compiler_never_guesses_critical_values():
    assert _compile()["guesses_critical_values"] is False
    # Even a clarification-blocked intent never fabricates values.
    blocked = _compile(work_type="customer_reply_draft",
                       canonical_parameters={"target": "case:E-1"})
    assert blocked["guesses_critical_values"] is False


def test_intent_compiler_business_key_deterministic():
    assert _compile()["canonical_business_key"] == \
        _compile()["canonical_business_key"]


def test_intent_compiler_business_key_varies_by_target():
    a = _compile()["canonical_business_key"]
    b = _compile(requested_target_refs=["case:OTHER"],
                 canonical_parameters={"target": "case:OTHER"})[
                     "canonical_business_key"]
    assert a != b


def test_intent_compiler_hash_deterministic():
    assert _compile()["compiled_intent_hash"] == \
        _compile()["compiled_intent_hash"]


def test_intent_compiler_hash_deterministic_via_evaluate():
    # Two independent full evaluations yield an identical compiled-intent hash.
    a = k.evaluate()["intent"]["compiled_intent_hash"]
    b = k.evaluate()["intent"]["compiled_intent_hash"]
    assert a == b and a


def test_intent_compiler_unregistered_status():
    assert _compile(work_type="nope")["intent_status"] == \
        "INTENT_WORK_TYPE_UNREGISTERED"


def test_intent_compiler_unregistered_rejected():
    o = k.evaluate(work_type="nope")
    assert o["disposition"] == "REJECTED"
    assert o["resulting_state"] == "REJECTED"
    assert "INTENT_WORK_TYPE_UNREGISTERED" in o["reason_codes"]


def test_intent_compiler_invalid_target_type_status():
    # A well-formed target ref whose type is not allowed for this work type.
    i = _compile(requested_target_refs=["task:1"],
                 canonical_parameters={"target": "task:1"})
    assert i["intent_status"] == "INTENT_TARGET_INVALID"


def test_intent_compiler_invalid_target_type_rejected():
    o = k.evaluate(requested_target_refs=["task:1"],
                   canonical_parameters={"target": "task:1"})
    assert o["disposition"] == "REJECTED"
    assert "INTENT_TARGET_INVALID" in o["reason_codes"]


def test_intent_compiler_too_many_targets_status():
    # case_summary maximum_target_count is 8; nine valid case refs overflow it.
    over = ["case:E-%d" % n for n in range(9)]
    i = _compile(requested_target_refs=over)
    assert i["intent_status"] == "INTENT_TARGET_INVALID"


def test_intent_compiler_too_many_targets_rejected():
    over = ["case:E-%d" % n for n in range(9)]
    o = k.evaluate(requested_target_refs=over)
    assert o["disposition"] == "REJECTED"
    assert "INTENT_TARGET_INVALID" in o["reason_codes"]


def test_intent_compiler_missing_field_populated():
    i = _compile(work_type="customer_reply_draft",
                 canonical_parameters={"target": "case:E-1"})
    assert i["missing_fields"] == ["message_intent"]
    assert i["intent_status"] == "INTENT_NEEDS_CLARIFICATION"


def test_intent_compiler_missing_field_needs_clarification():
    o = k.evaluate(work_type="customer_reply_draft",
                   canonical_parameters={"target": "case:E-1"})
    assert o["disposition"] == "NEEDS_CLARIFICATION"
    assert o["resulting_state"] == "NEEDS_CLARIFICATION"
    assert "INTENT_NEEDS_CLARIFICATION" in o["reason_codes"]


def test_intent_compiler_surfaces_registry_capabilities_and_approval():
    i = _compile()
    assert i["required_capabilities"] == ["case.read"]
    assert i["approval_class"] == "NONE"
    reply = _compile(work_type="customer_reply_draft",
                     canonical_parameters={"target": "case:E-1",
                                           "message_intent": "x"})
    assert reply["approval_class"] == "STANDARD"


# --- kernel layer: canonical work-unit registry ----------------------------
def test_registry_entries_have_required_fields():
    for name, e in wi.WORK_TYPE_REGISTRY.items():
        assert e["registry_hash"], name
        assert e["split_policy"] in wi.SPLIT_POLICIES, name
        assert e["approval_class"] in wi.APPROVAL_CLASSES, name


def test_registry_entries_have_demand_floor_and_upper():
    for name, e in wi.WORK_TYPE_REGISTRY.items():
        floor = e["deterministic_demand_floor"]
        upper = e["deterministic_demand_upper"]
        for r in wi.DEMAND_RESOURCES:
            assert 0 <= floor[r] <= upper[r], (name, r)


def test_registry_hash_recomputes_deterministically():
    for name, e in wi.WORK_TYPE_REGISTRY.items():
        recomputed = wi._sha({kk: vv for kk, vv in e.items()
                              if kk != "registry_hash"})
        assert recomputed == e["registry_hash"], name


def test_registry_split_policies_cover_expected_work_types():
    reg = wi.WORK_TYPE_REGISTRY
    assert reg["case_summary"]["split_policy"] == "SINGLE_ITEM_ONLY"
    assert reg["evidence_review"]["split_policy"] == \
        "DETERMINISTIC_SPLIT_ALLOWED"
    assert reg["compliance_escalation"]["approval_class"] == "DUAL_CONTROL"


# --- API layer -------------------------------------------------------------
def test_intent_api_subfield_returns_intent_shape(gate):
    wid, _ = gate.admitted_work()
    r = gate.wki(wid, "/intent")
    assert r.status_code == 200
    j = r.json()
    assert j["work_type"] == "case_summary"
    assert j["target_refs"] == ["case:E-1"]
    assert j["missing_input_fields"] == []


def test_intent_api_subfield_missing_fields_for_reply_draft(gate):
    # A customer_reply_draft with no message_intent surfaces the missing field.
    wid, _ = gate.admitted_work(work_type="customer_reply_draft",
                                canonical_parameters={"target": "case:E-1"})
    r = gate.wki(wid, "/intent")
    assert r.status_code == 200
    assert "message_intent" in (r.json()["missing_input_fields"] or [])
