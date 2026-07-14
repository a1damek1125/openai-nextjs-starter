"""TOOL-B9.2 v5: Governed Work Lineage Observatory — OpenTelemetry adapter (26),
A2A compatibility boundary (27), observer self-health (28), local work canaries
(29) and decision basis (25).

The adapter and A2A boundary are mappings only: the canonical observation stays
authoritative, external transport/agent-card state grants no authority, and no
raw customer data or transaction id leaks into telemetry. Observer failure must
never appear as successful (certified) work. Every local canary proves no
external provider call, message, payment, CRM mutation, webhook or outbox release.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_work_observability as wo
from tests import _b92_kernel as k


# --- kernel layer: OpenTelemetry adapter (section 26) ----------------------
def test_adcan_otel_clean_instrumentation_and_guardrails():
    a = k.clean_outcome()["otel_adapter"]
    assert a["instrumentation_scope"] == "finalis.ai_employee.governed_work_lineage"
    assert a["supports_w3c_trace_context"] is True
    assert a["canonical_is_authoritative"] is True
    assert a["uses_external_semconv_as_truth"] is False
    assert a["critical_evidence_sampled"] is False
    assert a["no_transaction_id_in_metric_labels"] is True
    assert a["no_raw_customer_data_in_attributes"] is True
    assert a["cardinality_ok"] is True
    assert a["adapter_status"] == "HEALTHY"


def test_adcan_otel_hash_recompute():
    a = k.clean_outcome()["otel_adapter"]
    assert _core_hash(a, "otel_adapter_hash") == a["otel_adapter_hash"]


def test_adcan_otel_cardinality_over_max_not_certified():
    o = k.prepare(otel_attribute_count=9999)
    a = o["otel_adapter"]
    assert a["cardinality_ok"] is False
    assert a["adapter_status"] == "DEGRADED"
    # Telemetry cardinality rejection degrades the observer; the run must NOT be
    # certified even though the PoWO factors themselves may still pass.
    assert o["work_outcome_certified"] is False
    assert o["work_run_state"] != "WORK_OUTCOME_CERTIFIED"
    assert o["observer_health_state"] == "OBSERVER_DEGRADED"


# --- kernel layer: A2A compatibility boundary (section 27) -----------------
def test_adcan_a2a_boundary_grants_no_authority():
    b = k.clean_outcome()["a2a_boundary"]
    assert b["a2a_state_can_override_finalis"] is False
    assert b["agent_card_grants_authority"] is False
    assert b["a2a_message_proves_delivery"] is False


def test_adcan_a2a_untrusted_external_artifact_reflects_input():
    clean = k.clean_outcome()["a2a_boundary"]
    assert clean["untrusted_external_artifact"] is False
    tainted = k.prepare(a2a={"task_id": "t", "artifact": "x"})["a2a_boundary"]
    assert tainted["untrusted_external_artifact"] is True
    assert tainted["a2a_applicable"] is True
    assert tainted["a2a_state_can_override_finalis"] is False


def test_adcan_a2a_boundary_hash_recompute():
    b = k.clean_outcome()["a2a_boundary"]
    assert _core_hash(b, "a2a_boundary_hash", "signal") == b["a2a_boundary_hash"]


# --- kernel layer: observer self-health (section 28) -----------------------
def test_adcan_observer_health_clean_healthy():
    o = k.clean_outcome()
    h = o["observer_health"]
    assert h["observer_health_state"] == "OBSERVER_HEALTHY"
    assert h["observer_healthy"] is True
    assert h["failure_appears_as_success"] is False
    assert o["observer_health_state"] == "OBSERVER_HEALTHY"


def test_adcan_observer_unavailable_not_certified():
    o = k.prepare(observer_unavailable=True)
    assert o["observer_health_state"] == "OBSERVER_UNAVAILABLE"
    assert o["observer_health"]["failure_appears_as_success"] is False
    # Observer failure must never appear as successful (certified) work.
    assert o["work_outcome_certified"] is False
    assert o["work_run_state"] != "WORK_OUTCOME_CERTIFIED"
    assert "OBSERVER_UNHEALTHY" in o["all_signals"]


def test_adcan_observer_cross_tenant_query_poisoned():
    o = k.prepare(cross_tenant_query=True)
    assert o["observer_health_state"] == "OBSERVER_POISONED"
    assert o["work_outcome_certified"] is False
    assert "cross_tenant_query_block" in o["observer_health"]["problems"]


def test_adcan_observer_health_hash_recompute():
    h = k.clean_outcome()["observer_health"]
    assert _core_hash(h, "observer_health_hash", "signal") == h[
        "observer_health_hash"]


# --- kernel layer: local work canaries (section 29) ------------------------
def test_adcan_canary_cases_all_present_and_safe():
    h = k.clean_outcome()["b92_canary_harness"]
    assert h["canary_count"] == 15
    assert h["all_canaries_safe"] is True
    assert h["harness_status"] == "SAFE"
    names = [c["canary"] for c in h["canaries"]]
    assert names == wo.CANARY_CASES
    assert len(wo.CANARY_CASES) == 15


def test_adcan_every_canary_proves_no_external_effect():
    h = k.clean_outcome()["b92_canary_harness"]
    for c in h["canaries"]:
        assert c["no_external_provider_called"] is True
        assert c["no_message_sent"] is True
        assert c["no_payment_executed"] is True
        assert c["no_external_crm_mutation"] is True
        assert c["no_webhook_dispatched"] is True
        assert c["no_outbox_released"] is True
        assert c["safe"] is True


# --- kernel layer: decision basis (section 25) -----------------------------
def test_adcan_decision_basis_no_authority_no_chain_of_thought():
    d = k.clean_outcome()["decision_basis"]
    assert d["stores_chain_of_thought"] is False
    assert d["is_authority"] is False


def test_adcan_decision_basis_hash_recompute():
    d = k.clean_outcome()["decision_basis"]
    assert _core_hash(d, "deterministic_hash") == d["deterministic_hash"]


# --- API layer -------------------------------------------------------------
def test_adcan_api_otel_adapter_endpoint(gate):
    wrid, _ = gate.observed_work()
    r = gate.wo(wrid, "otel-adapter")
    assert r.status_code == 200
    a = r.json()["otel_adapter"]
    assert a["instrumentation_scope"] == "finalis.ai_employee.governed_work_lineage"
    assert a["canonical_is_authoritative"] is True


def test_adcan_api_a2a_boundary_endpoint(gate):
    wrid, _ = gate.observed_work()
    r = gate.wo(wrid, "a2a-boundary")
    assert r.status_code == 200
    b = r.json()["a2a_boundary"]
    assert b["agent_card_grants_authority"] is False
    assert b["a2a_message_proves_delivery"] is False


def test_adcan_api_observer_health_detail_endpoint(gate):
    wrid, _ = gate.observed_work()
    r = gate.wo(wrid, "observer-health-detail")
    assert r.status_code == 200
    h = r.json()["observer_health"]
    assert h["observer_health_state"] == "OBSERVER_HEALTHY"
    assert h["failure_appears_as_success"] is False


def test_adcan_api_decision_basis_endpoint(gate):
    wrid, _ = gate.observed_work()
    r = gate.wo(wrid, "decision-basis")
    assert r.status_code == 200
    d = r.json()["decision_basis"]
    assert d["stores_chain_of_thought"] is False
    assert d["is_authority"] is False


def test_adcan_api_run_local_canary(gate):
    from tests.conftest import OWNER
    b9id, _ = gate.committed_local_tx(requester=OWNER)
    body = gate.clean_work_body(b9_transaction_id=b9id)
    r = gate.observe_work(action="run-local-canary", actor=OWNER, body=body)
    assert r.status_code == 200
    j = r.json()
    assert j["all_canaries_safe"] is True
    assert j["canary_harness"]["canary_count"] == 15


def test_adcan_api_work_observability_drill(gate):
    from tests.conftest import OWNER
    b9id, _ = gate.committed_local_tx(requester=OWNER)
    body = gate.clean_work_body(b9_transaction_id=b9id)
    r = gate.observe_work(action="work-observability-drill", actor=OWNER,
                          body=body)
    assert r.status_code == 200
    j = r.json()
    assert j["drill_status"] == "SAFE"
    assert j["no_external_effect"] is True
    assert j["canary_harness"]["all_canaries_safe"] is True


def test_adcan_api_observer_health_summary(gate):
    from tests.conftest import OWNER
    gate.observed_work()
    r = gate.c.get(
        "/ai-tools/local-transactions/observability/observer-health",
        headers=gate.h(OWNER))
    assert r.status_code == 200
    j = r.json()
    assert j["observer_health_states"] == wo.OBSERVER_HEALTH_STATES
    assert "observer_health_by_state" in j
