"""TOOL-B9.2 v5: Governed Work Lineage Observatory — full HTTP API surface.

Every observability endpoint is LOCAL-ONLY, READ-ONLY over B9/B9.1 and
DERIVED-EVIDENCE-ONLY: it grants no authority, produces no external effect and
delivers nothing externally. These tests drive the /policy, /registry,
/work-runs, the POST observe/verify/rebuild/canary/drill actions, the per-run
work-run / events / subfield views and the 404 behaviour for unknown work runs.
"""
from finalis.ai_employee import tool_work_observability as wo
from tests.conftest import OWNER

_BASE = "/ai-tools/local-transactions/observability"

# The 23 work-lineage subfield view slugs (GET /{slug}/{work_run_id}).
_WOAPI_SUBFIELD_SLUGS = (
    "origin", "principal-continuity", "context", "memory", "delegation",
    "approval", "gateway-boundary", "transaction", "recovery",
    "artifact-lineage", "delivery-intent", "schedule-lineage", "revocation",
    "causal-graph", "missing-evidence", "twin", "proof-of-work-outcome",
    "decision-basis", "otel-adapter", "a2a-boundary", "consistent-cut",
    "no-external-effect", "observer-health-detail",
)


# --- /policy ---------------------------------------------------------------
def test_woapi_policy_core_flags(gate):
    pol = gate.c.get(_BASE + "/policy", headers=gate.h(OWNER)).json()
    assert pol["b92_model_version"]
    assert pol["local_work_observability_only"] is True
    assert pol["read_only_over_b9_and_b9_1"] is True
    assert pol["derived_evidence_only"] is True
    assert pol["external_effect"] is False
    assert pol["execution_authority"] is False
    assert pol["recovery_authority"] is False
    assert pol["production_ready"] is False


def test_woapi_policy_every_has_endpoint_flag_false(gate):
    pol = gate.c.get(_BASE + "/policy", headers=gate.h(OWNER)).json()
    flags = {k: v for k, v in pol.items()
             if k.startswith("has_") and k.endswith("_endpoint")}
    assert flags, "expected has_*_endpoint forbidden flags in /policy"
    for name, val in flags.items():
        assert val is False, name


def test_woapi_policy_no_authorization_flags(gate):
    pol = gate.c.get(_BASE + "/policy", headers=gate.h(OWNER)).json()
    for f in ("authorizes_execution", "authorizes_commit",
              "authorizes_recovery", "authorizes_delivery", "releases_outbox",
              "stores_secret", "stores_chain_of_thought"):
        assert pol[f] is False, f


# --- /registry -------------------------------------------------------------
def test_woapi_registry_zero_before_any_run(gate):
    reg = gate.c.get(_BASE + "/registry", headers=gate.h(OWNER)).json()
    assert reg["work_run_count"] == 0
    assert reg["outcomes_by_state"] == {}
    assert reg["outcomes_by_truth_state"] == {}


def test_woapi_registry_counts_certified_run(gate):
    gate.observed_work()
    reg = gate.c.get(_BASE + "/registry", headers=gate.h(OWNER)).json()
    assert reg["work_run_count"] >= 1
    assert reg["outcomes_by_state"].get("WORK_OUTCOME_CERTIFIED", 0) >= 1
    assert reg["outcomes_by_truth_state"].get("PROVEN", 0) >= 1


def test_woapi_registry_honesty_labels(gate):
    reg = gate.c.get(_BASE + "/registry", headers=gate.h(OWNER)).json()
    assert reg["honesty_labels"]


# --- /work-runs ------------------------------------------------------------
def test_woapi_work_runs_returns_created_run(gate):
    wrid, _ = gate.observed_work()
    rows = gate.c.get(_BASE + "/work-runs", headers=gate.h(OWNER)).json()
    ids = {r["work_run_id"] for r in rows}
    assert wrid in ids
    row = next(r for r in rows if r["work_run_id"] == wrid)
    assert row["work_run_state"] == "WORK_OUTCOME_CERTIFIED"
    assert row["work_outcome_truth_state"] == "PROVEN"
    assert row["proof_of_work_outcome_valid"] is True


# --- POST observe / verify / rebuild / canary / drill ----------------------
def test_woapi_observe_work_run_happy_path(gate):
    wrid, o = gate.observed_work()
    assert wrid
    assert o["work_run_state"] == "WORK_OUTCOME_CERTIFIED"
    assert o["work_outcome_truth_state"] == "PROVEN"
    assert o["proof_of_work_outcome_valid"] is True
    assert o["no_external_effect"] is True


def test_woapi_verify_work_run_hash_valid(gate):
    wrid, _ = gate.observed_work()
    v = gate.c.post(_BASE + "/verify-work-run", json={"work_run_id": wrid},
                    headers=gate.h(OWNER)).json()
    assert v["b92_decision_hash_valid"] is True
    assert v["verification_status"] == "VALID"
    assert v["stored_b92_decision_hash"] == v["recomputed_b92_decision_hash"]


def test_woapi_rebuild_local_observation_deterministic(gate):
    wrid, _ = gate.observed_work()
    r = gate.c.post(_BASE + "/rebuild-local-observation",
                    json={"work_run_id": wrid}, headers=gate.h(OWNER)).json()
    assert r["rebuilt_from_work_run_id"] == wrid
    assert r["deterministic"] is True
    rebuilt = r["rebuilt"]
    # A rebuilt observation is a fresh derived read of the stored request; it is
    # a real work outcome (its own decision hash + a valid lifecycle state) and
    # is never certified into an authority.
    assert rebuilt["b92_decision_hash"]
    assert rebuilt["work_run_state"] in wo.WORK_RUN_STATES
    assert rebuilt["is_authority"] is False
    assert rebuilt["no_external_effect"] is True


def test_woapi_run_local_canary_all_safe(gate):
    r = gate.observe_work(action="run-local-canary").json()
    assert r["all_canaries_safe"] is True
    h = r["canary_harness"]
    assert h["canary_count"] == 15
    assert h["all_canaries_safe"] is True


def test_woapi_work_observability_drill_safe(gate):
    r = gate.observe_work(action="work-observability-drill").json()
    assert r["drill_status"] == "SAFE"
    assert r["no_external_effect"] is True
    assert r["canary_harness"]["all_canaries_safe"] is True


# --- GET /work-run/{id}, /events/{id} --------------------------------------
def test_woapi_get_work_run_full_outcome(gate):
    wrid, _ = gate.observed_work()
    o = gate.c.get(_BASE + "/work-run/" + wrid, headers=gate.h(OWNER)).json()
    assert o["work_run_id"] == wrid
    assert o["work_run_state"] == "WORK_OUTCOME_CERTIFIED"
    assert o["b92_decision_hash"]


def test_woapi_events_hash_chained(gate):
    wrid, _ = gate.observed_work()
    body = gate.c.get(_BASE + "/events/" + wrid, headers=gate.h(OWNER)).json()
    assert body["work_run_id"] == wrid
    events = body["events"]
    assert isinstance(events, list) and events
    for ev in events:
        assert ev["event_hash"]
        assert "previous_event_hash" in ev
    assert body["honesty_labels"]


# --- GET /signals, /observer-health, /recurring-drift ----------------------
def test_woapi_signals_endpoint(gate):
    gate.observed_work()
    sig = gate.c.get(_BASE + "/signals", headers=gate.h(OWNER)).json()
    assert isinstance(sig["signal_counts"], dict)
    assert sig["honesty_labels"]


def test_woapi_observer_health_endpoint(gate):
    gate.observed_work()
    oh = gate.c.get(_BASE + "/observer-health", headers=gate.h(OWNER)).json()
    assert oh["observer_health_by_state"].get("OBSERVER_HEALTHY", 0) >= 1
    assert oh["observer_health_states"]


def test_woapi_recurring_drift_endpoint(gate):
    r = gate.c.get(_BASE + "/recurring-drift/wd-1", headers=gate.h(OWNER))
    assert r.status_code == 200
    body = r.json()
    assert body["work_definition_id"] == "wd-1"
    assert "recurring_drift" in body
    assert body["honesty_labels"]


# --- subfield views --------------------------------------------------------
def test_woapi_subfield_slug_count_is_23(gate):
    assert len(_WOAPI_SUBFIELD_SLUGS) == 23


def test_woapi_all_subfields_return_labeled_view(gate):
    wrid, _ = gate.observed_work()
    for slug in _WOAPI_SUBFIELD_SLUGS:
        r = gate.wo(wrid, slug)
        assert r.status_code == 200, slug
        body = r.json()
        assert body["work_run_id"] == wrid, slug
        assert body["honesty_labels"], slug


def test_woapi_twin_subfield_proven(gate):
    wrid, _ = gate.observed_work()
    twin = gate.wo(wrid, "twin").json()["work_observation_twin"]
    assert twin["work_outcome_truth_state"] == "PROVEN"
    assert twin["non_authoritative"] is True


def test_woapi_powo_subfield_valid(gate):
    wrid, _ = gate.observed_work()
    powo = gate.wo(wrid, "proof-of-work-outcome").json()[
        "proof_of_work_outcome"]
    assert powo["proof_of_work_outcome_valid"] is True
    assert powo["verification_status"] == "VALID"


def test_woapi_missing_evidence_subfield_no_critical(gate):
    wrid, _ = gate.observed_work()
    neg = gate.wo(wrid, "missing-evidence").json()["negative_space"]
    assert neg["no_critical_missing"] is True


def test_woapi_no_external_effect_subfield(gate):
    wrid, _ = gate.observed_work()
    body = gate.wo(wrid, "no-external-effect").json()
    assert body["work_run_id"] == wrid
    assert "NO_EXTERNAL_EFFECT" in body["honesty_labels"]


# --- 404 for unknown work runs ---------------------------------------------
def test_woapi_unknown_work_run_404(gate):
    assert gate.c.get(_BASE + "/work-run/nope",
                      headers=gate.h(OWNER)).status_code == 404


def test_woapi_unknown_verify_404(gate):
    r = gate.c.post(_BASE + "/verify-work-run", json={"work_run_id": "nope"},
                    headers=gate.h(OWNER))
    assert r.status_code == 404


def test_woapi_unknown_events_404(gate):
    assert gate.c.get(_BASE + "/events/nope",
                      headers=gate.h(OWNER)).status_code == 404


def test_woapi_unknown_subfields_404(gate):
    for slug in _WOAPI_SUBFIELD_SLUGS:
        assert gate.wo("nope", slug).status_code == 404, slug
