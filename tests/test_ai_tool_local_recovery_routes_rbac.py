"""TOOL-B9.1 v4: Recovery route-topology guard, RBAC, tenant isolation, and the
Employee-OS do-not-rebuild guarantee.

The recovery runtime adds ONLY /ai-tools/local-transactions/recovery/* routes and
has NO external-effect surface: every external rollback/recover/release/provider/
payment/webhook/job/MCP/LLM route is absent. Reads need case.read; the state-
changing recovery actions need case.update; every recovery is strictly tenant-
scoped. Do NOT modify product code.
"""
from finalis.admin.rbac import ROLE_PERMISSIONS
from tests.conftest import OWNER, VIEWER, OTHER_OWNER

_BASE = "/ai-tools/local-transactions/recovery"
_LT = "/ai-tools/local-transactions"

# Recovery routes that MUST NOT EXIST at all.
_FORBIDDEN_RECOVERY_SLUGS = (
    "external-rollback", "external-recover", "release-effects",
    "activate-provider", "provider-retry", "send", "payment-refund",
    "webhook-dispatch", "job-release", "mcp-run", "llm-run")
# B9-level forbidden routes that must remain absent under local-transactions/.
_FORBIDDEN_B9_SLUGS = ("external-execute", "release-effects", "provider-call")
# Recovery actions requiring case.update (viewer must be denied).
_UPDATE_ACTIONS = ("run", "rollback-local", "abort", "quarantine", "stuck",
                   "crash-drill")

ACCOUNTANT = "accountant-b91@demo.finalis"  # lacks case.read AND case.update


def _accountant(gate):
    """Seed a user then set its server-side RBAC role to `accountant`, which the
    RBAC catalog grants neither case.read nor case.update, yielding a deny."""
    assert "case.read" not in ROLE_PERMISSIONS["accountant"]
    gate.add_user(ACCOUNTANT, "viewer")
    gate.db.conn.execute("UPDATE users SET role='accountant' WHERE email=?",
                         (ACCOUNTANT,))
    gate.db.conn.commit()
    return ACCOUNTANT


# --- route topology: forbidden recovery routes MUST NOT EXIST --------------
def test_routes_forbidden_recovery_slugs_get_and_post_absent(gate):
    for slug in _FORBIDDEN_RECOVERY_SLUGS:
        url = _BASE + "/" + slug
        g = gate.c.get(url, headers=gate.h(OWNER))
        p = gate.c.post(url, json={}, headers=gate.h(OWNER))
        assert g.status_code in (404, 405), "GET " + slug
        assert p.status_code in (404, 405), "POST " + slug


def test_routes_b9_level_forbidden_still_absent(gate):
    for slug in _FORBIDDEN_B9_SLUGS:
        url = _LT + "/" + slug
        g = gate.c.get(url, headers=gate.h(OWNER))
        p = gate.c.post(url, json={}, headers=gate.h(OWNER))
        assert g.status_code in (404, 405), "GET " + slug
        assert p.status_code in (404, 405), "POST " + slug


# --- RBAC: case.read gate --------------------------------------------------
def test_rbac_no_case_read_cannot_get_policy(gate):
    acct = _accountant(gate)
    assert gate.c.get(_BASE + "/policy",
                      headers=gate.h(acct)).status_code == 403


def test_rbac_no_case_read_cannot_get_registry(gate):
    acct = _accountant(gate)
    assert gate.c.get(_BASE + "/registry",
                      headers=gate.h(acct)).status_code == 403


def test_rbac_no_case_read_cannot_get_list(gate):
    acct = _accountant(gate)
    assert gate.c.get(_BASE + "/list",
                      headers=gate.h(acct)).status_code == 403


def test_rbac_no_case_read_cannot_get_events(gate):
    acct = _accountant(gate)
    assert gate.c.get(_BASE + "/events",
                      headers=gate.h(acct)).status_code == 403


# --- RBAC: viewer (case.read, not case.update) -----------------------------
def test_rbac_viewer_can_post_status(gate):
    assert "case.read" in ROLE_PERMISSIONS["viewer"]
    txid, _ = gate.committed_local_tx()
    r = gate.recover(txid, action="status", actor=VIEWER)
    assert r.status_code == 200
    assert r.json()["final_recovery_state"] == "CLEAN"


def test_rbac_viewer_can_post_plan(gate):
    txid, _ = gate.committed_local_tx()
    r = gate.recover(txid, action="plan", actor=VIEWER)
    assert r.status_code == 200
    assert r.json()["final_recovery_state"] == "RECOVERY_PLANNED"


def test_rbac_viewer_cannot_post_run(gate):
    assert "case.update" not in ROLE_PERMISSIONS["viewer"]
    txid, _ = gate.committed_local_tx()
    assert gate.recover(txid, action="run", actor=VIEWER).status_code == 403


def test_rbac_viewer_cannot_post_rollback_local(gate):
    txid, _ = gate.committed_local_tx()
    assert gate.recover(txid, action="rollback-local",
                        actor=VIEWER).status_code == 403


def test_rbac_viewer_cannot_post_abort(gate):
    txid, _ = gate.committed_local_tx()
    assert gate.recover(txid, action="abort", actor=VIEWER).status_code == 403


def test_rbac_viewer_cannot_post_quarantine(gate):
    txid, _ = gate.committed_local_tx()
    assert gate.recover(txid, action="quarantine",
                        actor=VIEWER).status_code == 403


def test_rbac_viewer_cannot_post_stuck(gate):
    txid, _ = gate.committed_local_tx()
    assert gate.recover(txid, action="stuck", actor=VIEWER).status_code == 403


def test_rbac_viewer_cannot_post_crash_drill(gate):
    txid, _ = gate.committed_local_tx()
    assert gate.recover(txid, action="crash-drill",
                        actor=VIEWER).status_code == 403


def test_rbac_viewer_denied_all_update_actions(gate):
    for action in _UPDATE_ACTIONS:
        txid, _ = gate.committed_local_tx()
        assert gate.recover(txid, action=action,
                            actor=VIEWER).status_code == 403, action


# --- tenant isolation ------------------------------------------------------
def test_tenant_other_cannot_open_outcome(gate):
    rid, _ = gate.prepared_recovery(action="run")
    r = gate.c.get(_BASE + "/outcome?recovery_id=" + rid,
                   headers=gate.h(OTHER_OWNER))
    assert r.status_code == 404


def test_tenant_other_cannot_open_subfield(gate):
    rid, _ = gate.prepared_recovery(action="run")
    for slug in ("twin", "certificate", "safety-case"):
        assert gate.rc(rid, slug, actor=OTHER_OWNER).status_code == 404, slug


def test_tenant_other_cannot_verify(gate):
    rid, _ = gate.prepared_recovery(action="run")
    r = gate.c.post(_BASE + "/verify?recovery_id=" + rid,
                    headers=gate.h(OTHER_OWNER))
    assert r.status_code == 404


def test_tenant_other_list_is_empty(gate):
    gate.prepared_recovery(action="run")
    rows = gate.c.get(_BASE + "/list", headers=gate.h(OTHER_OWNER)).json()
    assert rows == []


def test_tenant_other_registry_zeroed(gate):
    gate.prepared_recovery(action="run")
    reg = gate.c.get(_BASE + "/registry", headers=gate.h(OTHER_OWNER)).json()
    assert reg["recovery_outcome_count"] == 0
    assert reg["recovery_request_count"] == 0
    assert reg["outcomes_by_state"] == {}


# --- honesty labels never empty / hidden -----------------------------------
def test_honesty_labels_present_on_policy(gate):
    labels = gate.c.get(_BASE + "/policy", headers=gate.h(OWNER)).json()[
        "honesty_labels"]
    assert labels
    assert "NOT_PRODUCTION_READY" in labels
    assert "NO_EXTERNAL_EFFECT" in labels


def test_honesty_labels_present_on_subfield(gate):
    rid, _ = gate.prepared_recovery(action="run")
    labels = gate.rc(rid, "no-external-effect").json()["honesty_labels"]
    assert labels
    assert "NOT_PRODUCTION_READY" in labels
    assert "NO_EXTERNAL_EFFECT" in labels


# --- Employee-OS do-not-rebuild: B9.1 only ADDED, broke nothing ------------
def test_donotrebuild_core_cases_still_ok(gate):
    assert gate.c.get("/cases", headers=gate.h(OWNER)).status_code == 200


def test_donotrebuild_b9_recovery_policy_ok_for_owner(gate):
    assert gate.c.get(_BASE + "/policy",
                      headers=gate.h(OWNER)).status_code == 200


def test_donotrebuild_no_recovery_route_outside_namespace(gate):
    # Every route mentioning "recovery" lives under the recovery namespace; no
    # duplicate CRM/recovery runtime route was smuggled in elsewhere.
    paths = {getattr(r, "path", "") for r in gate.app.router.routes}
    recovery_paths = {p for p in paths if "recovery" in p}
    assert recovery_paths
    for p in recovery_paths:
        assert p.startswith(_BASE), p
