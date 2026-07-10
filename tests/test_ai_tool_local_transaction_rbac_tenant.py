"""TOOL-B9 v5: Finalis Transaction Twin — RBAC, tenant isolation, and the
Employee-OS do-not-rebuild compatibility guarantee.

Reads need case.read; prepare/commit-local need case.update; every request and
outcome is strictly tenant-scoped. B9 ONLY ADDED /ai-tools/local-transactions/*
routes and rebuilt nothing: the existing core endpoints still work and no
duplicate CRM/Evidence/Case-Graph route was introduced. Do NOT modify product
code.
"""
from finalis.admin.rbac import ROLE_PERMISSIONS
from tests.conftest import OWNER, VIEWER, OTHER_OWNER

ACCOUNTANT = "accountant-b9@demo.finalis"  # lacks case.read AND case.update


def _accountant(gate):
    """No portal-creatable role lacks case.read, so seed a user then set its
    RBAC role (server-side, via the users table) to `accountant`, which the
    RBAC catalog grants neither case.read nor case.update. require_permission
    maps the token role straight into the RbacEngine, yielding a deny."""
    assert "case.read" not in ROLE_PERMISSIONS["accountant"]
    gate.add_user(ACCOUNTANT, "viewer")
    gate.db.conn.execute("UPDATE users SET role='accountant' WHERE email=?",
                         (ACCOUNTANT,))
    gate.db.conn.commit()
    return ACCOUNTANT


# --- case.read gate --------------------------------------------------------
def test_rbac_no_case_read_cannot_get_policy(gate):
    acct = _accountant(gate)
    assert gate.c.get("/ai-tools/local-transactions/policy",
                      headers=gate.h(acct)).status_code == 403


def test_rbac_no_case_read_cannot_get_registry(gate):
    acct = _accountant(gate)
    assert gate.c.get("/ai-tools/local-transactions/registry",
                      headers=gate.h(acct)).status_code == 403


def test_rbac_no_case_read_cannot_get_events(gate):
    acct = _accountant(gate)
    assert gate.c.get("/ai-tools/local-transactions/events",
                      headers=gate.h(acct)).status_code == 403


def test_rbac_no_case_read_cannot_list(gate):
    acct = _accountant(gate)
    assert gate.c.get("/ai-tools/local-transactions",
                      headers=gate.h(acct)).status_code == 403


# --- case.update gate ------------------------------------------------------
def test_rbac_viewer_can_read_policy_and_registry(gate):
    assert "case.read" in ROLE_PERMISSIONS["viewer"]
    assert gate.c.get("/ai-tools/local-transactions/policy",
                      headers=gate.h(VIEWER)).status_code == 200
    assert gate.c.get("/ai-tools/local-transactions/registry",
                      headers=gate.h(VIEWER)).status_code == 200


def test_rbac_viewer_cannot_prepare(gate):
    assert "case.update" not in ROLE_PERMISSIONS["viewer"]
    b8id, _ = gate.b8_accepted_outcome()
    assert gate.local_tx(b8id, op="prepare", actor=VIEWER).status_code == 403


def test_rbac_viewer_cannot_commit_local(gate):
    b8id, _ = gate.b8_accepted_outcome()
    assert gate.local_tx(b8id, op="commit-local",
                         actor=VIEWER).status_code == 403


def test_rbac_viewer_cannot_validate(gate):
    b8id, _ = gate.b8_accepted_outcome()
    assert gate.local_tx(b8id, op="validate", actor=VIEWER).status_code == 403


# --- tenant isolation ------------------------------------------------------
def test_tenant_other_cannot_open_transaction(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    assert gate.lt(tid, actor=OTHER_OWNER).status_code == 404
    assert gate.lt(tid, "/outcome", actor=OTHER_OWNER).status_code == 404
    assert gate.lt(tid, "/twin", actor=OTHER_OWNER).status_code == 404
    assert gate.lt(tid, "/events", actor=OTHER_OWNER).status_code == 404


def test_tenant_other_cannot_verify_or_open_subfield(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    assert gate.lt(tid, "/verify", method="POST",
                   actor=OTHER_OWNER).status_code == 404
    assert gate.lt(tid, "/certificate", actor=OTHER_OWNER).status_code == 404


def test_tenant_other_list_does_not_leak(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    other = gate.c.get("/ai-tools/local-transactions",
                       headers=gate.h(OTHER_OWNER)).json()
    assert all(r.get("transaction_id") != tid for r in other)


def test_tenant_other_registry_and_events_empty(gate):
    gate.prepared_local_tx(op="commit-local")
    reg = gate.c.get("/ai-tools/local-transactions/registry",
                     headers=gate.h(OTHER_OWNER)).json()
    assert reg["local_transaction_request_count"] == 0
    assert reg["local_transaction_outcome_count"] == 0
    ev = gate.c.get("/ai-tools/local-transactions/events",
                    headers=gate.h(OTHER_OWNER)).json()
    assert ev["event_count"] == 0


# --- honesty labels never empty / hidden -----------------------------------
def test_honesty_labels_present_and_nonempty_on_policy(gate):
    labels = gate.c.get("/ai-tools/local-transactions/policy",
                        headers=gate.h()).json()["honesty_labels"]
    assert labels
    assert "NOT_PRODUCTION_READY" in labels
    assert "NO_EXTERNAL_EFFECT" in labels


def test_honesty_labels_present_and_nonempty_on_twin(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    labels = gate.lt(tid, "/twin").json()["honesty_labels"]
    assert labels
    assert "NOT_PRODUCTION_READY" in labels
    assert "NO_EXTERNAL_EFFECT" in labels


def test_honesty_labels_present_and_nonempty_on_subfield(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    labels = gate.lt(tid, "/no-external-effect").json()["honesty_labels"]
    assert labels
    assert "B8_EVIDENCE_ONLY" in labels


# --- Employee-OS do-not-rebuild: B9 only ADDED, broke nothing --------------
def test_b9_did_not_break_core_cases_endpoint(gate):
    # B9 added local-transactions/* and rebuilt no CRM/Case-Graph route:
    # the pre-existing core cases endpoint still serves OWNER.
    assert gate.c.get("/cases", headers=gate.h(OWNER)).status_code == 200


def test_b9_did_not_break_core_commit_simulation_policy(gate):
    # The upstream B8 (evidence-only) policy route is untouched by B9.
    r = gate.c.get("/ai-tools/commit-simulations/policy", headers=gate.h())
    assert r.status_code == 200
    assert r.json()["simulation_only"] is True


def test_b9_added_only_local_transaction_routes(gate):
    # No duplicate provider/CRM/evidence execution route was smuggled in under
    # the B9 namespace; the forbidden routes simply do not exist.
    tid, _ = gate.prepared_local_tx(op="commit-local")
    for bad in ("/external-execute", "/release-effects", "/provider-call",
                "/send", "/dispatch", "/webhook-send", "/grant-authority",
                "/payment"):
        r = gate.lt(tid, bad, method="POST")
        assert r.status_code in (404, 405), bad
