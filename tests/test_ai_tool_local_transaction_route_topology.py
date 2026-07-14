"""TOOL-B9 v5: route topology guard. B9 adds ONLY local, non-executing routes.

No B9 route may exist that could produce an external effect — there is no
external-execute, release-effects, provider-call, send, dispatch, webhook-send,
llm-run, mcp-run, grant-authority, commit-lease or payment endpoint (GET/POST
both 404/405). The ALLOWED local, read-only / verification routes DO exist and
respond 200. API-only file using the `gate` fixture.
"""
from tests.conftest import OWNER


def _forbidden(gate, tid, slug):
    """Both GET and POST to a forbidden B9 slug must not exist."""
    url = f"/ai-tools/local-transactions/{tid}/{slug}"
    get = gate.c.get(url, headers=gate.h(OWNER)).status_code
    post = gate.c.post(url, json={}, headers=gate.h(OWNER)).status_code
    assert get in (404, 405), f"GET {slug} exists (status {get})"
    assert post in (404, 405), f"POST {slug} exists (status {post})"


# --- forbidden execution routes (must NOT exist) ---------------------------
def test_topology_no_external_execute_route(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    _forbidden(gate, tid, "external-execute")


def test_topology_no_release_effects_route(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    _forbidden(gate, tid, "release-effects")


def test_topology_no_provider_call_route(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    _forbidden(gate, tid, "provider-call")


def test_topology_no_send_route(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    _forbidden(gate, tid, "send")


def test_topology_no_dispatch_route(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    _forbidden(gate, tid, "dispatch")


def test_topology_no_webhook_send_route(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    _forbidden(gate, tid, "webhook-send")


def test_topology_no_llm_run_route(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    _forbidden(gate, tid, "llm-run")


def test_topology_no_mcp_run_route(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    _forbidden(gate, tid, "mcp-run")


def test_topology_no_grant_authority_route(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    _forbidden(gate, tid, "grant-authority")


def test_topology_no_commit_lease_route(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    _forbidden(gate, tid, "commit-lease")


def test_topology_no_payment_route(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    _forbidden(gate, tid, "payment")


# --- allowed local, non-executing routes (must exist, 200/valid) -----------
def test_topology_allowed_read_routes_exist(gate):
    # A single prepared tx reused across GET-only asserts (read-only endpoints).
    tid, _ = gate.prepared_local_tx(op="commit-local")
    for slug in ("twin", "outcome", "certificate", "events"):
        r = gate.c.get(f"/ai-tools/local-transactions/{tid}/{slug}",
                       headers=gate.h(OWNER))
        assert r.status_code == 200, f"GET {slug} -> {r.status_code}"


def test_topology_allowed_verify_route_valid(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.c.post(f"/ai-tools/local-transactions/{tid}/verify",
                    json={}, headers=gate.h(OWNER))
    assert r.status_code == 200
    body = r.json()
    assert body["b9_decision_hash_valid"] is True
    assert body["verification_status"] == "VALID"


def test_topology_allowed_registry_route(gate):
    r = gate.c.get("/ai-tools/local-transactions/registry",
                   headers=gate.h(OWNER))
    assert r.status_code == 200
    assert "outcomes_by_status" in r.json()


def test_topology_allowed_policy_route(gate):
    r = gate.c.get("/ai-tools/local-transactions/policy",
                   headers=gate.h(OWNER))
    assert r.status_code == 200
    pol = r.json()
    assert pol["local_reversible_commit_only"] is True
    assert pol["external_effect"] is False


def test_topology_policy_declares_no_forbidden_endpoints(gate):
    pol = gate.c.get("/ai-tools/local-transactions/policy",
                     headers=gate.h(OWNER)).json()
    assert pol["has_external_execute_endpoint"] is False
    assert pol["has_release_effects_endpoint"] is False
    assert pol["has_provider_call_endpoint"] is False
    assert pol["has_send_endpoint"] is False
    assert pol["has_grant_authority_endpoint"] is False
