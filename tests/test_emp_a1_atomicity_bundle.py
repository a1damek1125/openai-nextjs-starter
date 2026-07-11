"""EMP-A1 v1: atomicity resolution (section 10) + admission bundles (section 11)
+ idempotency / fragmentation firewall (section 15).

Atomicity is deterministic: a single target is one canonical item; a
SINGLE_ITEM_ONLY work type collapses many targets to one; a
DETERMINISTIC_SPLIT_ALLOWED work type produces a bounded deterministic bundle
until it exceeds its child limit, at which point it needs atomicity review. The
structural fingerprint is a stable dedup key. The fragmentation firewall detects
exact duplicates, fragment families that share a single entitlement, and abusive
bursts that are quarantined — the child count of a bundle/family never multiplies
fairness, risk, or memory (one shared entitlement).
"""
from finalis.ai_employee import employee_work_inbox as wi
from tests import _emp_a1_kernel as k


def _atomicity(**over):
    r = k.req(**over)
    intent = wi.compile_intent(tenant_id=r["tenant_id"], req=r, policy={})
    return wi.resolve_atomicity(req=r, intent=intent)


def _fp(**over):
    return wi.structural_fingerprint(tenant_id="t1", req=k.req(**over))


def _recent(fingerprint, principal="user:1", work_type="case_summary",
            targets=("case:E-1",)):
    return {"fingerprint": fingerprint, "principal": principal,
            "work_type": work_type, "targets": list(targets)}


# --- kernel layer: atomicity resolution ------------------------------------
def test_atomicity_single_target_single_item():
    a = _atomicity()
    assert a["atomicity_outcome"] == "SINGLE_CANONICAL_ITEM"
    assert a["child_count"] == 1
    assert "SINGLE_CANONICAL_ITEM" in wi.REASON_CODES


def test_atomicity_single_item_only_collapses_multiple_targets():
    a = _atomicity(requested_target_refs=["case:E-1", "case:E-2", "case:E-3"])
    assert a["split_policy"] == "SINGLE_ITEM_ONLY"
    assert a["atomicity_outcome"] == "SINGLE_CANONICAL_ITEM"
    assert a["child_count"] == 1


def test_atomicity_deterministic_bundle_within_limit():
    ev = ["evidence:%d" % n for n in range(4)]
    a = _atomicity(work_type="evidence_review", requested_target_refs=ev,
                   canonical_parameters={"target": "b"})
    assert a["atomicity_outcome"] == "DETERMINISTIC_BUNDLE"
    assert a["child_count"] == 4


def test_atomicity_bundle_child_count_matches_targets():
    ev = ["evidence:%d" % n for n in range(6)]
    a = _atomicity(work_type="evidence_review", requested_target_refs=ev,
                   canonical_parameters={"target": "b"})
    assert a["atomicity_outcome"] == "DETERMINISTIC_BUNDLE"
    assert a["child_count"] == len(ev)


def test_atomicity_over_bundle_limit_review_required():
    cb = ["case:E-%d" % n for n in range(20)]
    a = _atomicity(work_type="case_batch_review", requested_target_refs=cb,
                   canonical_parameters={"target": "b"})
    assert a["atomicity_outcome"] == "ATOMICITY_REVIEW_REQUIRED"
    assert a["child_count"] == 20


def test_atomicity_is_deterministic():
    ev = ["evidence:%d" % n for n in range(4)]
    a = _atomicity(work_type="evidence_review", requested_target_refs=ev,
                   canonical_parameters={"target": "b"})
    b = _atomicity(work_type="evidence_review", requested_target_refs=ev,
                   canonical_parameters={"target": "b"})
    assert a == b and a["deterministic"] is True


def test_atomicity_evaluate_evidence_bundle_admits_ready():
    ev = ["evidence:%d" % n for n in range(4)]
    o = k.evaluate(work_type="evidence_review", requested_target_refs=ev,
                   canonical_parameters={"target": "b"})
    assert o["disposition"] == "ADMIT_READY"
    assert o["resulting_state"] == "READY"
    assert o["atomicity"]["atomicity_outcome"] == "DETERMINISTIC_BUNDLE"


def test_atomicity_evaluate_batch_needs_review():
    cb = ["case:E-%d" % n for n in range(20)]
    o = k.evaluate(work_type="case_batch_review", requested_target_refs=cb,
                   canonical_parameters={"target": "b"})
    assert o["disposition"] == "NEEDS_ATOMICITY_REVIEW"
    assert o["resulting_state"] == "NEEDS_ATOMICITY_REVIEW"
    assert "ATOMICITY_REVIEW_REQUIRED" in o["reason_codes"]


# --- kernel layer: structural fingerprint ----------------------------------
def test_fingerprint_deterministic_for_identical_requests():
    assert _fp() == _fp()


def test_fingerprint_differs_by_target():
    assert _fp() != _fp(requested_target_refs=["case:OTHER"],
                        canonical_parameters={"target": "case:OTHER"})


# --- kernel layer: fragmentation firewall ----------------------------------
def test_fragmentation_exact_fingerprint_is_duplicate_candidate():
    f = wi.check_fragmentation(tenant_id="t1", req=k.req(),
                               recent_fingerprints=[_recent(_fp())])
    assert f["fragmentation_result"] == "DUPLICATE_CANDIDATE"


def test_fragmentation_duplicate_evaluate_disposition():
    snap = {"tenant_id": "t1", "recent_fingerprints": [_recent(_fp())]}
    o = k.evaluate(snapshot=snap)
    assert o["disposition"] == "DUPLICATE"
    assert "DUPLICATE_CANDIDATE" in o["reason_codes"]


def test_fragmentation_burst_is_likely_abusive():
    recent = [_recent("fp-%d" % n) for n in range(6)]
    f = wi.check_fragmentation(tenant_id="t1", req=k.req(),
                               recent_fingerprints=recent)
    assert f["fragmentation_result"] == "LIKELY_ABUSIVE_FRAGMENTATION"
    assert f["family_size"] >= 6


def test_fragmentation_abusive_evaluate_quarantined():
    recent = [_recent("fp-%d" % n) for n in range(6)]
    snap = {"tenant_id": "t1", "recent_fingerprints": recent}
    o = k.evaluate(snapshot=snap)
    assert o["disposition"] == "QUARANTINED"
    assert o["resulting_state"] == "QUARANTINED"
    assert "LIKELY_ABUSIVE_FRAGMENTATION" in o["reason_codes"]


def test_fragmentation_family_shares_single_entitlement():
    # One overlapping prior -> a fragment family that shares ONE entitlement;
    # the child count never multiplies fairness/risk/memory.
    f = wi.check_fragmentation(tenant_id="t1", req=k.req(),
                               recent_fingerprints=[_recent("fp-x")])
    assert f["fragmentation_result"] == "FRAGMENT_FAMILY"
    assert f["shares_entitlement"] is True


def test_fragmentation_abusive_shares_single_entitlement():
    recent = [_recent("fp-%d" % n) for n in range(6)]
    f = wi.check_fragmentation(tenant_id="t1", req=k.req(),
                               recent_fingerprints=recent)
    assert f["shares_entitlement"] is True


def test_fragmentation_no_prior_is_independent_work():
    f = wi.check_fragmentation(tenant_id="t1", req=k.req(),
                               recent_fingerprints=[])
    assert f["fragmentation_result"] == "INDEPENDENT_WORK"
    assert f["shares_entitlement"] is False


# --- kernel layer: idempotency firewall ------------------------------------
def test_idempotency_exact_retry_no_charge():
    ex = {("t1", "idem-1"): {"work_item_id": "wi-1",
                             "canonical_request_hash": "H"}}
    f = wi.check_idempotency(tenant_id="t1",
                             req=k.req(canonical_request_hash="H"),
                             existing_by_key=ex)
    assert f["idempotency_status"] == "EXACT_RETRY"
    assert f["charge_allowed"] is False


def test_idempotency_conflict_same_key_different_hash():
    ex = {("t1", "idem-1"): {"work_item_id": "wi-1",
                             "canonical_request_hash": "H"}}
    f = wi.check_idempotency(tenant_id="t1",
                             req=k.req(canonical_request_hash="OTHER"),
                             existing_by_key=ex)
    assert f["idempotency_status"] == "CONFLICT"
    assert f["signal"] == "IDEMPOTENCY_PAYLOAD_CONFLICT"


def test_idempotency_new_key_charges():
    f = wi.check_idempotency(tenant_id="t1", req=k.req(),
                             existing_by_key={})
    assert f["idempotency_status"] == "NEW"
    assert f["charge_allowed"] is True
