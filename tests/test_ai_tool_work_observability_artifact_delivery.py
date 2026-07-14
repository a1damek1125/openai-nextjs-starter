"""TOOL-B9.2 v5: Artifact Lineage DAG (section 16) and Delivery Intent record
(section 17).

Every result artifact must record its sources (a DERIVED_FROM edge); a missing
artifact is made explicit rather than silently absent, and unaffected branches are
preserved. Delivery is LOCAL-INTENT-ONLY and strictly SEPARATE from artifact
creation: no Slack/Teams/email/webhook call may occur, the inert outbox is never
released, and an external delivery route is rejected (DELIVERED_EXTERNALLY is
forbidden). All observations are derived evidence and grant no authority.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_work_observability as wo
from tests import _b92_kernel as k


def _ad_degrades(over, expected_signal):
    o = k.prepare(**over)
    assert o["work_run_state"] == "OBSERVATION_COMPLETE"
    assert o["work_outcome_truth_state"] == "PARTIAL"
    assert o["proof_of_work_outcome_valid"] is False
    assert expected_signal in o["all_signals"]
    # Delivery never produces an external effect, even on a degraded outcome.
    assert o["delivered_externally"] is False
    assert o["outbox_released"] is False
    return o


# --- kernel layer: artifact lineage DAG ------------------------------------
def test_art_clean_lineage_valid_with_derived_edge():
    al = k.clean_outcome()["artifact_lineage"]
    assert al["lineage_status"] == "VALID"
    assert al["artifact_expected"] is True
    # The expected REPORT result artifact exists with recorded sources.
    assert al["node_count"] == 1
    node = al["nodes"][0]
    assert node["artifact_id"] == "a1"
    assert node["artifact_type"] == "REPORT"
    # Every result has source lineage: a DERIVED_FROM edge from its source.
    assert al["edges"] == [{"from": "s1", "to": "a1", "edge": "DERIVED_FROM"}]


def test_art_lineage_types_from_constant():
    al = k.clean_outcome()["artifact_lineage"]
    assert al["artifact_types"] == wo.ARTIFACT_TYPES
    assert "REPORT" in al["artifact_types"]
    assert "NO_ARTIFACT_EXPECTED" in al["artifact_types"]


def test_art_source_missing_signal():
    # A REPORT artifact with no recorded sources has missing source lineage.
    o = _ad_degrades({"artifacts": [{"id": "a1", "type": "REPORT",
                                     "sources": []}]},
                     "ARTIFACT_SOURCE_MISSING")
    assert o["artifact_lineage"]["lineage_valid"] is False


def test_art_lineage_missing_is_explicit():
    # An expected-but-absent artifact is made explicit, not silently missing.
    o = _ad_degrades({"artifacts": []}, "ARTIFACT_LINEAGE_MISSING")
    al = o["artifact_lineage"]
    assert al["artifact_expected"] is True
    assert al["node_count"] == 0


def test_art_no_artifact_expected_still_proves():
    o = k.prepare(artifact_expected=False, artifacts=[])
    al = o["artifact_lineage"]
    assert al["artifact_expected"] is False
    assert al["node_count"] == 0
    # No artifact expected and none produced -> the run still PROVES.
    assert o["work_outcome_truth_state"] == "PROVEN"
    assert o["work_run_state"] == "WORK_OUTCOME_CERTIFIED"
    assert o["proof_of_work_outcome_valid"] is True


def test_art_unaffected_branch_preserved_when_clean():
    al = k.clean_outcome()["artifact_lineage"]
    assert al["unaffected_branch_preserved"] is True


def test_art_unrelated_branch_changed_signal():
    # A change to an unrelated (unaffected) branch breaks preservation.
    o = _ad_degrades({"unrelated_branch_changed": True},
                     "ARTIFACT_UNRELATED_BRANCH_CHANGED")
    assert o["artifact_lineage"]["unaffected_branch_preserved"] is False


def test_art_lineage_hash_recompute():
    al = k.clean_outcome()["artifact_lineage"]
    assert _core_hash(al, "artifact_lineage_hash", "signal") == \
        al["artifact_lineage_hash"]


# --- kernel layer: delivery intent -----------------------------------------
def test_del_clean_local_intent_only():
    di = k.clean_outcome()["delivery_intent"]
    assert di["delivery_status"] == "LOCAL_INTENT_ONLY"
    assert di["delivered_externally"] is False
    assert di["outbox_released"] is False
    assert di["intent_status"] == "VALID"


def test_del_external_route_rejected_and_blocked():
    # An external delivery route is rejected; DELIVERED_EXTERNALLY is forbidden.
    o = _ad_degrades({"external_delivery": True},
                     "EXTERNAL_DELIVERY_ROUTE_REJECTED")
    di = o["delivery_intent"]
    assert di["delivery_status"] == "DELIVERY_BLOCKED"
    assert di["delivered_externally"] is False
    assert di["intent_status"] == "BLOCKED"
    # No Slack/Teams/email/webhook/payment call may ever occur.
    assert o["message_sent"] is False
    assert o["provider_called"] is False
    assert o["external_crm_mutated"] is False


def test_del_intent_missing_signal():
    o = _ad_degrades({"delivery_missing": True}, "DELIVERY_INTENT_MISSING")
    assert o["delivery_intent"]["intent_status"] == "BLOCKED"


def test_del_separate_from_artifact_creation():
    # Delivery is a distinct report from artifact creation.
    o = k.clean_outcome()
    al = o["artifact_lineage"]
    di = o["delivery_intent"]
    assert al is not di
    assert "artifact_lineage_version" in al
    assert "delivery_intent_version" in di
    assert al["artifact_lineage_hash"] != di["delivery_intent_hash"]


def test_del_intent_hash_recompute():
    di = k.clean_outcome()["delivery_intent"]
    assert _core_hash(di, "delivery_intent_hash", "signal") == \
        di["delivery_intent_hash"]


def test_ad_no_authority_or_external_effect():
    o = k.clean_outcome()
    assert o["is_authority"] is False
    assert o["authorizes_delivery"] is False
    assert o["no_external_effect"] is True
    assert o["delivered_externally"] is False
    assert o["outbox_released"] is False


# --- API layer -------------------------------------------------------------
def test_api_art_lineage_endpoint_clean(gate):
    wrid, _ = gate.observed_work()
    al = gate.wo(wrid, "artifact-lineage").json()["artifact_lineage"]
    assert al["lineage_status"] == "VALID"
    assert al["edges"] == [{"from": "s1", "to": "a1", "edge": "DERIVED_FROM"}]


def test_api_del_intent_endpoint_clean(gate):
    wrid, _ = gate.observed_work()
    di = gate.wo(wrid, "delivery-intent").json()["delivery_intent"]
    assert di["delivery_status"] == "LOCAL_INTENT_ONLY"
    assert di["delivered_externally"] is False
    assert di["outbox_released"] is False


def test_api_art_lineage_missing_partial(gate):
    wrid, o = gate.observed_work(artifacts=[])
    assert o["work_outcome_truth_state"] == "PARTIAL"
    assert "ARTIFACT_LINEAGE_MISSING" in o["all_signals"]
    al = gate.wo(wrid, "artifact-lineage").json()["artifact_lineage"]
    assert al["node_count"] == 0


def test_api_del_external_route_blocked(gate):
    wrid, o = gate.observed_work(external_delivery=True)
    assert "EXTERNAL_DELIVERY_ROUTE_REJECTED" in o["all_signals"]
    assert o["delivered_externally"] is False
    di = gate.wo(wrid, "delivery-intent").json()["delivery_intent"]
    assert di["delivery_status"] == "DELIVERY_BLOCKED"


def test_api_ad_reports_distinct(gate):
    wrid, _ = gate.observed_work()
    al = gate.wo(wrid, "artifact-lineage").json()["artifact_lineage"]
    di = gate.wo(wrid, "delivery-intent").json()["delivery_intent"]
    assert al["artifact_lineage_hash"] != di["delivery_intent_hash"]
