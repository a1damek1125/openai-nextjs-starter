"""TOOL-B9.1 v4: Recovery runtime HTTP API surface — /policy, /registry, /list,
the 8 recovery action POSTs, /outcome, /verify, /events (hash-chained), and every
recovery subfield view.

The recovery runtime is LOCAL-ONLY: every endpoint records local recovery/
rollback/abort/quarantine/stuck/crash-drill EVIDENCE and produces NO external
effect. B8 stays evidence only; the B9 certificate, Proof-of-Recovery and
Recovery Safety Case are proof, NOT authority. Do NOT modify product code.
"""
from tests.conftest import OWNER

_BASE = "/ai-tools/local-transactions/recovery"

# The 8 recovery action POST slugs and every read subfield slug (cheatsheet).
_ACTION_SLUGS = ("status", "plan", "run", "rollback-local", "abort",
                 "quarantine", "stuck", "crash-drill")
_SUBFIELD_SLUGS = (
    "twin", "certificate", "safety-case", "proof-of-recovery", "reconciliation",
    "authority-firewall", "lifecycle-checkpoints", "monotonicity",
    "poe-recovery", "contract", "rollback", "partial-commit", "quarantine",
    "stuck", "abort", "conflict", "inert-outbox", "no-external-effect",
    "por-stream", "chaos-drill", "release-gate", "proof-bundle")
# The has_*_endpoint flags the policy advertises for forbidden routes.
_FORBIDDEN_ENDPOINT_FLAGS = (
    "has_external_rollback_endpoint", "has_external_recover_endpoint",
    "has_release_effects_endpoint", "has_activate_provider_endpoint",
    "has_provider_retry_endpoint", "has_payment_refund_endpoint",
    "has_webhook_dispatch_endpoint", "has_job_release_endpoint")


def _api_policy(gate):
    return gate.c.get(_BASE + "/policy", headers=gate.h(OWNER)).json()


# --- /policy ---------------------------------------------------------------
def test_api_policy_local_recovery_only_flags(gate):
    pol = _api_policy(gate)
    assert pol["b91_model_version"]
    assert pol["local_recovery_only"] is True
    assert pol["external_effect"] is False
    assert pol["calls_providers"] is False
    assert pol["b8_is_evidence_only"] is True
    assert pol["b9_certificate_is_authority"] is False
    assert pol["production_ready"] is False


def test_api_policy_proof_is_not_authority(gate):
    pol = _api_policy(gate)
    assert pol["proof_of_recovery_is_authority"] is False
    assert pol["recovery_safety_case_is_authority"] is False


def test_api_policy_forbidden_endpoint_flags_all_false(gate):
    pol = _api_policy(gate)
    for flag in _FORBIDDEN_ENDPOINT_FLAGS:
        assert pol[flag] is False, flag


def test_api_policy_honesty_labels_present(gate):
    labels = _api_policy(gate)["honesty_labels"]
    assert labels
    assert "LOCAL_RECOVERY_ONLY" in labels
    assert "NO_EXTERNAL_EFFECT" in labels
    assert "NOT_PRODUCTION_READY" in labels


# --- /registry + /list -----------------------------------------------------
def test_api_registry_counts_and_outcomes_by_state(gate):
    gate.prepared_recovery(action="run")
    reg = gate.c.get(_BASE + "/registry", headers=gate.h(OWNER)).json()
    assert reg["recovery_outcome_count"] >= 1
    assert reg["recovery_request_count"] >= 1
    assert isinstance(reg["outcomes_by_state"], dict)
    assert reg["outcomes_by_state"].get("RECOVERED", 0) >= 1
    assert sum(reg["outcomes_by_state"].values()) == reg[
        "recovery_outcome_count"]


def test_api_list_returns_created_recoveries(gate):
    rid, _ = gate.prepared_recovery(action="run")
    rows = gate.c.get(_BASE + "/list", headers=gate.h(OWNER)).json()
    match = [r for r in rows if r["recovery_id"] == rid]
    assert len(match) == 1
    assert match[0]["final_recovery_state"] == "RECOVERED"
    assert match[0]["desired_recovery_action"] == "RECOVER"


# --- the 8 recovery action POST endpoints ----------------------------------
def test_api_action_run_returns_recovered_outcome(gate):
    txid, _ = gate.committed_local_tx()
    r = gate.recover(txid, action="run")
    assert r.status_code == 200
    o = r.json()
    assert o["recovery_id"]
    assert o["transaction_id"] == txid
    assert o["final_recovery_state"] == "RECOVERED"
    assert o["recovery_applied"] is True
    assert o["no_external_effect"] is True


def test_api_action_status_returns_clean(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="status").json()
    assert o["final_recovery_state"] == "CLEAN"


def test_api_action_plan_returns_planned(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="plan").json()
    assert o["final_recovery_state"] == "RECOVERY_PLANNED"


def test_api_action_rollback_local_returns_applied_local(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="rollback-local").json()
    assert o["final_recovery_state"] == "ROLLBACK_APPLIED_LOCAL"


def test_api_action_abort_returns_aborted_pre_commit(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="abort").json()
    assert o["final_recovery_state"] == "ABORTED_PRE_COMMIT"
    assert o["dominant_signal"] == "USER_ABORT_REQUESTED"
    assert o["recovery_applied"] is False


def test_api_action_quarantine_returns_quarantined(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="quarantine").json()
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["quarantine_required"] is True


def test_api_action_stuck_returns_clean_when_healthy(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="stuck").json()
    assert o["final_recovery_state"] == "CLEAN"


def test_api_action_crash_drill_returns_recovery_required(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="crash-drill").json()
    assert o["final_recovery_state"] == "RECOVERY_REQUIRED"


def test_api_all_eight_actions_return_200(gate):
    for slug in _ACTION_SLUGS:
        txid, _ = gate.committed_local_tx()
        r = gate.recover(txid, action=slug)
        assert r.status_code == 200, slug
        o = r.json()
        assert o["recovery_id"], slug
        assert o["transaction_id"] == txid, slug
        assert o["no_external_effect"] is True, slug
        assert o["produced_external_effect"] is False, slug


# --- /outcome --------------------------------------------------------------
def test_api_outcome_returns_full_outcome(gate):
    rid, _ = gate.prepared_recovery(action="run")
    o = gate.c.get(_BASE + "/outcome?recovery_id=" + rid,
                   headers=gate.h(OWNER)).json()
    assert o["recovery_id"] == rid
    assert o["final_recovery_state"] == "RECOVERED"
    assert o["b91_decision_hash"]
    assert o["recovery_certificate"]["recovery_certificate_hash"]
    assert o["b91_recovery_proof_bundle"]["component_count"] == 24


def test_api_outcome_unknown_recovery_id_404(gate):
    r = gate.c.get(_BASE + "/outcome?recovery_id=does-not-exist",
                   headers=gate.h(OWNER))
    assert r.status_code == 404


# --- /verify ---------------------------------------------------------------
def test_api_verify_decision_hash_valid(gate):
    rid, _ = gate.prepared_recovery(action="run")
    v = gate.c.post(_BASE + "/verify?recovery_id=" + rid,
                    headers=gate.h(OWNER)).json()
    assert v["b91_decision_hash_valid"] is True
    assert v["verification_status"] == "VALID"


def test_api_verify_unknown_recovery_id_404(gate):
    r = gate.c.post(_BASE + "/verify?recovery_id=nope",
                    headers=gate.h(OWNER))
    assert r.status_code == 404


# --- /events (hash-chained) ------------------------------------------------
def test_api_events_global_chain_valid(gate):
    gate.prepared_recovery(action="run")
    ev = gate.c.get(_BASE + "/events", headers=gate.h(OWNER)).json()
    assert ev["event_count"] >= 2
    assert ev["event_chain_valid"] is True


def test_api_events_filtered_by_recovery_id(gate):
    rid, _ = gate.prepared_recovery(action="run")
    ev = gate.c.get(_BASE + "/events?recovery_id=" + rid,
                    headers=gate.h(OWNER)).json()
    assert ev["event_count"] >= 2
    assert ev["event_chain_valid"] is True
    assert all(e["recovery_id"] == rid for e in ev["events"])


# --- subfield views --------------------------------------------------------
def test_api_all_subfield_views_return_200(gate):
    rid, _ = gate.prepared_recovery(action="run")
    for slug in _SUBFIELD_SLUGS:
        r = gate.rc(rid, slug)
        assert r.status_code == 200, slug
        body = r.json()
        assert body["recovery_id"] == rid, slug
        assert body["transaction_id"], slug
        assert body["honesty_labels"], slug


def test_api_subfield_unknown_recovery_id_404(gate):
    for slug in ("twin", "certificate", "safety-case", "proof-bundle"):
        r = gate.rc("missing-id", slug)
        assert r.status_code == 404, slug


def test_api_subfield_twin_hash_present(gate):
    rid, _ = gate.prepared_recovery(action="run")
    twin = gate.rc(rid, "twin").json()["twin"]
    assert twin["recovery_twin_hash"]
