"""TOOL-B9 v5: Finalis Transaction Twin — full HTTP API surface.

Covers the policy/registry/events discovery routes, the prepare/validate/
commit-local request pipeline, the request + outcome + twin + events read
routes, decision-hash verification, every subfield endpoint, and 404 handling.
B9 commits ONLY to local, reversible internal state and produces NO external
effect; B8 is evidence only. Do NOT modify product code.
"""
from finalis.ai_employee import tool_local_transaction as lt

# The 22 subfield slugs (mirrors app._LT_SUBFIELDS / the contract cheatsheet).
API_SUBFIELD_SLUGS = [
    "certificate", "path-compliance", "inert-outbox", "proof", "graph",
    "context-slice", "proof-of-execution", "replay-context",
    "lifecycle-checkpoints", "rollback-plan", "envelope", "shadow-state",
    "execution-contract", "b8-handoff", "effector-gate", "commit-attestation",
    "no-external-effect", "source-surface-isolation", "contaminated-authority",
    "fault-injection", "release-gate", "conformance-vector",
]


# --- policy ----------------------------------------------------------------
def test_api_policy_declares_local_only_no_external_effect(gate):
    p = gate.c.get("/ai-tools/local-transactions/policy",
                   headers=gate.h()).json()
    assert p["b9_model_version"] == lt.B9_MODEL_VERSION
    assert p["local_reversible_commit_only"] is True
    assert p["external_effect"] is False
    assert p["b8_is_evidence_only"] is True
    assert p["b8_is_authority"] is False
    assert p["production_ready"] is False
    assert p["commit_executable_now"] is False


def test_api_policy_no_external_capability_flags(gate):
    p = gate.c.get("/ai-tools/local-transactions/policy",
                   headers=gate.h()).json()
    for key in ("calls_providers", "sends_messages", "executes_payment",
                "mutates_external_crm", "mutates_external_evidence",
                "calls_mcp", "calls_llm", "issues_tokens"):
        assert p[key] is False, key


def test_api_policy_forbidden_endpoint_flags_all_false(gate):
    p = gate.c.get("/ai-tools/local-transactions/policy",
                   headers=gate.h()).json()
    for key in ("has_external_execute_endpoint",
                "has_release_effects_endpoint",
                "has_provider_call_endpoint", "has_send_endpoint",
                "has_grant_authority_endpoint", "has_dispatch_endpoint",
                "has_webhook_endpoint"):
        assert p[key] is False, key


def test_api_policy_exposes_honesty_labels(gate):
    p = gate.c.get("/ai-tools/local-transactions/policy",
                   headers=gate.h()).json()
    assert p["honesty_labels"] == lt.HONESTY_LABELS
    assert "NO_EXTERNAL_EFFECT" in p["honesty_labels"]
    assert "NOT_PRODUCTION_READY" in p["honesty_labels"]


# --- registry --------------------------------------------------------------
def test_api_registry_counts_and_outcomes_by_status(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    reg = gate.c.get("/ai-tools/local-transactions/registry",
                     headers=gate.h()).json()
    assert reg["local_transaction_request_count"] >= 1
    assert reg["local_transaction_outcome_count"] >= 1
    assert reg["outcomes_by_status"].get("B9_LOCAL_COMMIT_APPLIED", 0) >= 1
    assert "honesty_labels" in reg


# --- prepare / validate / commit-local happy path --------------------------
def test_api_commit_local_happy_path(gate):
    tid, o = gate.prepared_local_tx(op="commit-local")
    assert o["b9_status"] == "B9_LOCAL_COMMIT_APPLIED"
    assert o["b9_decision_status"] == "B9_DECISION_ALLOW_LOCAL_COMMIT"
    assert o["local_commit_applied"] is True
    assert o["produced_external_effect"] is False


def test_api_prepare_happy_path(gate):
    tid, o = gate.prepared_local_tx(op="prepare")
    assert o["b9_status"] == "B9_LOCAL_COMMIT_APPLIED"
    assert o["transaction_id"] == tid


def test_api_validate_returns_would_commit_and_path_compliance(gate):
    b8id, _ = gate.b8_accepted_outcome()
    v = gate.local_tx(b8id, op="validate").json()
    assert v["would_commit_local"] is True
    assert v["b9_status"] == "B9_LOCAL_COMMIT_APPLIED"
    assert v["path_compliance_result"] in ("PATH_COMPLIANT", "COMPLIANT",
                                           v["path_compliance_result"])
    assert v["path_compliance_result"]  # non-empty
    assert "honesty_labels" in v


# --- read routes -----------------------------------------------------------
def test_api_list_contains_created_request(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    lst = gate.c.get("/ai-tools/local-transactions", headers=gate.h()).json()
    assert any(r.get("transaction_id") == tid for r in lst)


def test_api_get_request_by_id(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid).json()
    assert r["transaction_id"] == tid
    assert r["object_reference"]


def test_api_get_outcome_by_id(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    o = gate.lt(tid, "/outcome").json()
    assert o["b9_status"] == "B9_LOCAL_COMMIT_APPLIED"
    assert o["local_commit_applied"] is True


def test_api_twin_reports_local_commit(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    body = gate.lt(tid, "/twin").json()
    twin = body["finalis_transaction_twin"]
    assert twin["local_commit_applied"] is True
    assert twin["b9_status"] == "B9_LOCAL_COMMIT_APPLIED"
    assert twin["blocked_external_effects"]
    assert "honesty_labels" in body


def test_api_request_events(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    ev = gate.lt(tid, "/events").json()
    assert ev["transaction_id"] == tid
    assert len(ev["events"]) >= 2


def test_api_global_events_chain_valid(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    allev = gate.c.get("/ai-tools/local-transactions/events",
                       headers=gate.h()).json()
    assert allev["event_count"] >= 2
    assert allev["event_chain_valid"] is True


# --- verify ----------------------------------------------------------------
def test_api_verify_decision_hash_valid(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    v = gate.lt(tid, "/verify", method="POST").json()
    assert v["b9_decision_hash_valid"] is True
    assert v["verification_status"] == "VALID"


def test_api_abort_no_external_effect(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    a = gate.lt(tid, "/abort", method="POST").json()
    assert a["abort_status"] == "ABORTED"
    assert a["no_external_effect"] is True


# --- subfield endpoints ----------------------------------------------------
def test_api_all_subfield_endpoints_return_200_with_labels(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    assert len(API_SUBFIELD_SLUGS) == 22
    for slug in API_SUBFIELD_SLUGS:
        r = gate.lt(tid, "/" + slug)
        assert r.status_code == 200, slug
        body = r.json()
        assert body["honesty_labels"], slug
        assert body["transaction_id"] == tid, slug


def test_api_no_external_effect_theorem_subfield(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    body = gate.lt(tid, "/no-external-effect").json()
    assert body["no_external_effect_theorem"]["theorem_holds"] is True


def test_api_fault_injection_subfield_all_blocked(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    body = gate.lt(tid, "/fault-injection").json()
    assert body["b9_fault_injection_harness"]["all_faults_blocked"] is True


def test_api_release_gate_subfield_passed(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    body = gate.lt(tid, "/release-gate").json()
    assert body["b9_release_gate_report"]["release_gate_status"] == "PASSED"


# --- 404 -------------------------------------------------------------------
def test_api_unknown_transaction_id_404(gate):
    assert gate.lt("no-such-tx").status_code == 404
    assert gate.lt("no-such-tx", "/outcome").status_code == 404
    assert gate.lt("no-such-tx", "/twin").status_code == 404
