"""TOOL-B8 machine-checkable pre-B9 assurance: API surface + policy + no
commit/execute/activate-b9 endpoints."""


def test_policy_declares_simulation_only_no_commit(gate):
    p = gate.c.get("/ai-tools/commit-simulations/policy",
                   headers=gate.h()).json()
    assert p["simulation_only"] is True
    for k in ("performs_real_commit", "releases_effects",
              "activates_commitment", "activates_b9", "grants_b9_authority",
              "issues_commit_lease", "calls_provider", "calls_mcp", "calls_llm",
              "issues_tokens", "reads_credentials", "sends_messages",
              "executes_payment", "mutates_crm", "mutates_evidence",
              "exports_data", "artifacts_are_authority", "production_ready",
              "commit_executable_now", "has_commit_endpoint",
              "has_execute_endpoint", "has_effect_release_endpoint",
              "has_activate_commitment_endpoint", "has_activate_b9_endpoint",
              "has_grant_authority_endpoint", "has_commit_lease_endpoint"):
        assert p[k] is False, k
    assert p["b9_revalidation_required"] is True
    assert p["most_permissive_outcome"] == "B8_V5_ACCEPTED"


def test_create_returns_pre_b9_assurance(gate):
    sid, o = gate.prepared_commit_simulation()
    assert o["commit_simulation_status"] == "B8_V5_ACCEPTED"
    assert o["commit_simulation_decision_status"] == \
        "B8_V5_DECISION_ACCEPT_PRE_B9_ASSURANCE_ONLY"
    assert o["commit_simulation_outcome_kind"] == "PRE_B9_ASSURANCE_ONLY"
    assert o["simulation_only"] is True and o["is_real_commit"] is False
    assert o["produced_external_effect"] is False
    assert o["released_effect"] is False and o["activated_commitment"] is False
    assert o["activated_b9"] is False and o["commit_executable_now"] is False
    assert o["b9_revalidation_required"] is True


def test_missing_b7_outcome_404(gate):
    r = gate.c.post("/ai-tools/commit-simulations",
                    json={"b7_write_intent_id": "nope"}, headers=gate.h())
    assert r.status_code == 404


def test_list_registry_get_roundtrip(gate):
    sid, _ = gate.prepared_commit_simulation()
    lst = gate.c.get("/ai-tools/commit-simulations", headers=gate.h()).json()
    assert any(r.get("commit_simulation_id") == sid for r in lst)
    reg = gate.c.get("/ai-tools/commit-simulations/registry",
                     headers=gate.h()).json()
    assert reg["commit_simulation_outcome_count"] >= 1
    assert "B8_V5_ACCEPTED" in reg["outcomes_by_status"]
    assert gate.cs(sid, "/outcome").json()["commit_simulation_id"] == sid


def test_all_v5_subfield_endpoints_exist(gate):
    sid, _ = gate.prepared_commit_simulation()
    for slug in ["assurance-envelope", "evidence-closure-net",
                 "non-delegable-artifact-seal", "b9-negative-capability",
                 "cross-artifact-consistency", "route-topology-diff",
                 "trace-completeness-witness", "proof-obligation-matrix",
                 "production-claim-scanner", "final-ci-gate",
                 "v5-proof-extension"]:
        r = gate.cs(sid, "/" + slug)
        assert r.status_code == 200, slug
        keys = list(r.json().keys())
        assert r.json().get(keys[1]) is not None, slug


def test_base_subfield_endpoints_exist(gate):
    sid, _ = gate.prepared_commit_simulation()
    for slug in ["b7-consumption-gate", "state-witness-revalidation",
                 "shadow-dry-run", "effect-simulation", "no-commit-theorem",
                 "non-execution-certificate", "artifact-quarantine-vault",
                 "b9-firewall", "b9-revalidation-contract", "safety-case",
                 "proof-bundle", "fault-injection", "release-gate",
                 "conformance-vector"]:
        assert gate.cs(sid, "/" + slug).status_code == 200, slug


def test_no_commit_or_activate_endpoints(gate):
    sid, _ = gate.prepared_commit_simulation()
    for bad in ["/commit", "/execute", "/release-effects",
                "/activate-commitment", "/activate-b9", "/grant-b9-authority",
                "/issue-commit-lease"]:
        r = gate.c.post("/ai-tools/commit-simulations/" + sid + bad, json={},
                        headers=gate.h())
        assert r.status_code in (404, 405), bad


def test_no_global_execute_endpoints(gate):
    for bad in ["/mcp/call", "/provider/call", "/payment/execute",
                "/crm/mutate", "/evidence/mutate", "/message/send", "/export"]:
        r = gate.c.post(bad, json={}, headers=gate.h())
        assert r.status_code in (404, 405), bad


def test_verify_valid(gate):
    sid, _ = gate.prepared_commit_simulation()
    v = gate.cs(sid, "/verify", method="POST").json()
    assert v["verification_status"] == "VALID"
    assert v["commit_simulation_decision_hash_valid"] is True


def test_events_chain_valid(gate):
    sid, _ = gate.prepared_commit_simulation()
    ev = gate.cs(sid, "/events").json()
    assert ev["events"]
    allev = gate.c.get("/ai-tools/commit-simulations/events",
                       headers=gate.h()).json()
    assert allev["event_chain_valid"] is True


def test_ui_section_renders(gate):
    html = gate.c.get("/portal", headers=gate.h()).text
    assert "tool-commit-sim-section" in html
    assert "Machine-Checkable Pre-B9 Assurance Envelope" in html
    assert "LOCAL_COMMIT_SIMULATION_ONLY" in html
