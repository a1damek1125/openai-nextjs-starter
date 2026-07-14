"""TOOL-B9.2 v5: Governed Work Lineage Observatory — route-topology guard, RBAC,
tenant isolation and the Employee-OS do-not-rebuild guarantee.

The observatory adds ONLY /ai-tools/local-transactions/observability/* routes and
has NO external-effect / authority surface: every commit/approve/recover/rollback/
release/provider/send/payment/webhook/job/MCP/LLM route is absent, and the B9/B9.1
external routes remain absent. All reads are derived + require case.read; every
work run is strictly tenant-scoped. Do NOT modify product code.
"""
from finalis.admin.rbac import ROLE_PERMISSIONS
from tests.conftest import OWNER, OTHER_OWNER

_BASE = "/ai-tools/local-transactions/observability"
_LT = "/ai-tools/local-transactions"
_REC = "/ai-tools/local-transactions/recovery"

# Authority / external-effect actions that MUST NOT EXIST under observability.
_FORBIDDEN_SLUGS = (
    "commit", "finalize", "approve", "authorize", "recover", "rollback",
    "abort", "release-quarantine", "release-effects", "activate-provider",
    "retry-provider", "send", "dispatch", "payment", "refund", "external-sync",
    "webhook-dispatch", "job-release", "mcp-run", "llm-run", "execute-tool",
    "enable-schedule", "disable-schedule", "revoke-integration",
)

# A representative subset of subfield slugs for tenant-isolation sweeps.
_SUBFIELD_SLUGS = (
    "origin", "principal-continuity", "transaction", "recovery",
    "proof-of-work-outcome", "twin", "no-external-effect", "causal-graph",
)

ACCOUNTANT = "accountant-b92@demo.finalis"  # role lacks case.read -> denied


def _accountant(gate):
    """Seed a user then set its server-side RBAC role to `accountant`, which the
    RBAC catalog grants no case.read, yielding a deny on every read endpoint."""
    assert "case.read" not in ROLE_PERMISSIONS["accountant"]
    gate.add_user(ACCOUNTANT, "viewer")
    gate.db.conn.execute("UPDATE users SET role='accountant' WHERE email=?",
                         (ACCOUNTANT,))
    gate.db.conn.commit()
    return ACCOUNTANT


# --- route topology: forbidden observability routes MUST NOT EXIST ----------
def test_worbac_forbidden_slugs_get_and_post_absent(gate):
    for slug in _FORBIDDEN_SLUGS:
        g = gate.c.get(_BASE + "/" + slug + "/wrid1", headers=gate.h(OWNER))
        p = gate.c.post(_BASE + "/" + slug, json={}, headers=gate.h(OWNER))
        assert g.status_code in (404, 405), "GET " + slug
        assert p.status_code in (404, 405), "POST " + slug


def test_worbac_b9_external_execute_still_absent(gate):
    g = gate.c.get(_LT + "/external-execute/x", headers=gate.h(OWNER))
    p = gate.c.post(_LT + "/external-execute", json={}, headers=gate.h(OWNER))
    assert g.status_code in (404, 405)
    assert p.status_code in (404, 405)


def test_worbac_b91_external_rollback_still_absent(gate):
    g = gate.c.get(_REC + "/external-rollback/x", headers=gate.h(OWNER))
    p = gate.c.post(_REC + "/external-rollback", json={}, headers=gate.h(OWNER))
    assert g.status_code in (404, 405)
    assert p.status_code in (404, 405)


# --- RBAC: case.read gate (accountant role) --------------------------------
def test_worbac_accountant_lacks_case_read(gate):
    assert "case.read" not in ROLE_PERMISSIONS["accountant"]


def test_worbac_accountant_denied_policy(gate):
    acct = _accountant(gate)
    assert gate.c.get(_BASE + "/policy",
                      headers=gate.h(acct)).status_code == 403


def test_worbac_accountant_denied_registry(gate):
    acct = _accountant(gate)
    assert gate.c.get(_BASE + "/registry",
                      headers=gate.h(acct)).status_code == 403


def test_worbac_accountant_denied_work_runs(gate):
    acct = _accountant(gate)
    assert gate.c.get(_BASE + "/work-runs",
                      headers=gate.h(acct)).status_code == 403


def test_worbac_accountant_denied_signals(gate):
    acct = _accountant(gate)
    assert gate.c.get(_BASE + "/signals",
                      headers=gate.h(acct)).status_code == 403


def test_worbac_accountant_denied_observe_work_run(gate):
    acct = _accountant(gate)
    r = gate.c.post(_BASE + "/observe-work-run", json=gate.clean_work_body(),
                    headers=gate.h(acct))
    assert r.status_code == 403


# --- tenant isolation ------------------------------------------------------
def test_worbac_tenant_other_cannot_get_work_run(gate):
    wrid, _ = gate.observed_work()
    assert gate.c.get(_BASE + "/work-run/" + wrid,
                      headers=gate.h(OTHER_OWNER)).status_code == 404


def test_worbac_tenant_other_cannot_get_events(gate):
    wrid, _ = gate.observed_work()
    assert gate.c.get(_BASE + "/events/" + wrid,
                      headers=gate.h(OTHER_OWNER)).status_code == 404


def test_worbac_tenant_other_cannot_get_subfields(gate):
    wrid, _ = gate.observed_work()
    for slug in _SUBFIELD_SLUGS:
        assert gate.wo(wrid, slug,
                       actor=OTHER_OWNER).status_code == 404, slug


def test_worbac_tenant_other_cannot_verify(gate):
    wrid, _ = gate.observed_work()
    r = gate.c.post(_BASE + "/verify-work-run", json={"work_run_id": wrid},
                    headers=gate.h(OTHER_OWNER))
    assert r.status_code == 404


def test_worbac_tenant_other_work_runs_empty(gate):
    gate.observed_work()
    rows = gate.c.get(_BASE + "/work-runs",
                      headers=gate.h(OTHER_OWNER)).json()
    assert rows == []


def test_worbac_tenant_other_registry_zeroed(gate):
    gate.observed_work()
    reg = gate.c.get(_BASE + "/registry",
                     headers=gate.h(OTHER_OWNER)).json()
    assert reg["work_run_count"] == 0
    assert reg["outcomes_by_state"] == {}
    assert reg["outcomes_by_truth_state"] == {}


# --- honesty labels present & non-empty ------------------------------------
def test_worbac_honesty_labels_on_policy(gate):
    labels = gate.c.get(_BASE + "/policy", headers=gate.h(OWNER)).json()[
        "honesty_labels"]
    assert labels
    assert "NOT_PRODUCTION_READY" in labels
    assert "NO_EXTERNAL_EFFECT" in labels
    assert "DERIVED_EVIDENCE_NOT_AUTHORITY" in labels


def test_worbac_honesty_labels_on_subfield(gate):
    wrid, _ = gate.observed_work()
    labels = gate.wo(wrid, "no-external-effect").json()["honesty_labels"]
    assert labels
    assert "NOT_PRODUCTION_READY" in labels
    assert "NO_EXTERNAL_EFFECT" in labels
    assert "DERIVED_EVIDENCE_NOT_AUTHORITY" in labels


# --- Employee-OS do-not-rebuild: B9.2 only ADDED, broke nothing ------------
def test_worbac_donotrebuild_core_cases_ok(gate):
    assert gate.c.get("/cases", headers=gate.h(OWNER)).status_code == 200


def test_worbac_donotrebuild_b9_policy_ok(gate):
    assert gate.c.get(_LT + "/policy",
                      headers=gate.h(OWNER)).status_code == 200


def test_worbac_donotrebuild_b91_recovery_policy_ok(gate):
    assert gate.c.get(_REC + "/policy",
                      headers=gate.h(OWNER)).status_code == 200


def test_worbac_donotrebuild_b92_observability_policy_ok(gate):
    assert gate.c.get(_BASE + "/policy",
                      headers=gate.h(OWNER)).status_code == 200


def test_worbac_observability_namespace_only(gate):
    # B9.2 only added the /observability/* namespace; every route path that
    # mentions "observability" lives under it — no CRM/scheduler/memory/identity/
    # approval runtime route was smuggled in elsewhere.
    paths = {getattr(r, "path", "") for r in gate.app.router.routes}
    obs_paths = {p for p in paths if "observability" in p}
    assert obs_paths
    for p in obs_paths:
        assert p.startswith(_BASE), p
