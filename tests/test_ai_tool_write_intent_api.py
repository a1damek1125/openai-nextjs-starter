"""TOOL-B7 transaction-escrow write-intent: API surface + policy + no-commit
endpoints."""


def test_policy_declares_draft_only_no_commit(gate):
    p = gate.c.get("/ai-tools/write-intents/policy", headers=gate.h()).json()
    assert p["draft_only"] is True and p["escrow_only"] is True
    for k in ("commits", "executes", "releases_effects", "activates_commitment",
              "sends_customer_message", "executes_payment", "mutates_crm",
              "mutates_evidence", "exports_data", "calls_provider", "calls_mcp",
              "calls_llm", "issues_tokens", "derives_tokens",
              "reads_credentials", "has_commit_endpoint", "has_execute_endpoint",
              "has_effect_release_endpoint", "has_activate_commitment_endpoint",
              "has_escrow_commit_endpoint"):
        assert p[k] is False, k
    assert p["most_permissive_outcome"] == "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert p["approval_does_not_execute"] is True
    assert p["escrow_does_not_execute"] is True
    assert p["commit_readiness_does_not_execute"] is True


def test_create_returns_escrow_draft(gate):
    wid, o = gate.prepared_write_intent()
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["write_intent_decision_status"] == \
        "WRITE_INTENT_DECISION_ALLOW_DRAFT_ESCROW_ONLY"
    assert o["write_intent_outcome_kind"] == "TRANSACTION_ESCROW_ONLY"
    assert o["draft_only"] is True and o["is_commit"] is False
    assert o["produced_external_effect"] is False
    assert o["released_effect"] is False and o["activated_commitment"] is False
    assert o["commit_executable_now"] is False


def test_missing_b6_outcome_404(gate):
    r = gate.c.post("/ai-tools/write-intents",
                    json={"b6_runtime_request_id": "nope"}, headers=gate.h())
    assert r.status_code == 404


def test_list_and_get_roundtrip(gate):
    wid, o = gate.prepared_write_intent()
    lst = gate.c.get("/ai-tools/write-intents", headers=gate.h()).json()
    assert any(r["write_intent_id"] == wid for r in
               [x for x in lst]) or any(
        r.get("write_intent_id") == wid for r in lst)
    got = gate.wi(wid).json()
    assert got["write_intent_request_hash"]
    out = gate.wi(wid, "/outcome").json()
    assert out["write_intent_id"] == wid


def test_registry_counts(gate):
    gate.prepared_write_intent()
    reg = gate.c.get("/ai-tools/write-intents/registry",
                     headers=gate.h()).json()
    assert reg["write_intent_outcome_count"] >= 1
    assert "TRANSACTION_ESCROW_DRAFT_CREATED" in reg["outcomes_by_status"]


def test_all_v4_subfield_endpoints_exist(gate):
    wid, _ = gate.prepared_write_intent()
    for slug in ["transaction-escrow", "escrowed-commit-readiness",
                 "future-commit-gate-contract", "commit-gate-non-existence",
                 "revalidation-debt", "semantic-rollback-fence",
                 "action-replay-guard", "authority-resurrection-guard",
                 "rollback-replay-equivalence", "concurrent-draft-conflicts",
                 "transaction-conflict-oracle", "state-witness-quorum",
                 "effect-outbox-quarantine", "escrow-expiry",
                 "escrow-tamper-evidence", "readiness-non-execution",
                 "transaction-escrow-proof-extension"]:
        r = gate.wi(wid, "/" + slug)
        assert r.status_code == 200, slug
        assert r.json().get(list(r.json().keys())[1]) is not None, slug


def test_v3_subfield_endpoints_exist(gate):
    wid, _ = gate.prepared_write_intent()
    for slug in ["semantic-transaction", "transaction-boundary",
                 "shadow-state-delta-graph", "contestability",
                 "obligation-containment", "evidence-preservation",
                 "transaction-invariants", "semantic-transaction-replay"]:
        assert gate.wi(wid, "/" + slug).status_code == 200, slug


def test_no_commit_or_execute_endpoints(gate):
    wid, _ = gate.prepared_write_intent()
    for bad in ["/commit", "/execute", "/release-effects",
                "/activate-commitment", "/resolve-escrow-and-commit"]:
        r = gate.c.post("/ai-tools/write-intents/" + wid + bad, json={},
                        headers=gate.h())
        assert r.status_code in (404, 405), bad


def test_no_global_execute_endpoints(gate):
    for bad in ["/ai-tools/write-intents/commit",
                "/ai-tools/write-intents/execute",
                "/execute", "/run", "/mcp/call", "/provider/call",
                "/payment/execute", "/crm/mutate", "/evidence/mutate",
                "/message/send", "/export"]:
        r = gate.c.post(bad, json={}, headers=gate.h())
        assert r.status_code in (404, 405), bad


def test_verify_valid(gate):
    wid, _ = gate.prepared_write_intent()
    v = gate.wi(wid, "/verify", method="POST").json()
    assert v["verification_status"] == "VALID"
    assert v["write_intent_decision_hash_valid"] is True


def test_events_chain_valid(gate):
    wid, _ = gate.prepared_write_intent()
    ev = gate.wi(wid, "/events").json()
    assert ev["events"]
    all_ev = gate.c.get("/ai-tools/write-intents/events",
                        headers=gate.h()).json()
    assert all_ev["event_chain_valid"] is True
