"""EMP-A1 v1: Employee Work Inbox — route-topology guard, RBAC, tenant isolation,
and the Employee-OS do-not-rebuild guarantee (+ roadmap lock).

EMP-A1 adds ONLY the /ai-employee/work-inbox namespace and reused the existing
runtimes; it has NO external-effect surface. No endpoint creates/consumes an
EMP-A2 run or executes work: every run/execute/provider/send/payment/recover/
rollback/webhook/mcp/llm route is absent. Reads need case.read; submits and
mutations need case.update; every item is strictly tenant-scoped. Do NOT modify
product code.
"""
import json

from finalis.admin.rbac import ROLE_PERMISSIONS
from tests.conftest import OWNER, VIEWER, OTHER_OWNER

_BASE = "/ai-employee/work-inbox"

# Slugs that MUST NOT EXIST as EMP-A1 routes (no execution/effect surface).
_FORBIDDEN_SLUGS = (
    "run", "execute", "execute-tool", "provider-call", "send", "dispatch",
    "payment", "refund", "recover", "rollback", "release-effects", "start-run",
    "create-run", "consume-handoff", "webhook", "mcp-run", "llm-run",
    "commit-b9")
# B9 / B9.1 / B9.2 forbidden routes that must remain absent elsewhere.
_FORBIDDEN_B9_ROUTES = (
    "/ai-tools/local-transactions/recovery/external-rollback",
    "/ai-tools/local-transactions/recovery/external-recover",
    "/ai-tools/local-transactions/release-effects",
    "/ai-tools/local-transactions/provider-call")

ACCOUNTANT = "accountant-empa1@demo.finalis"  # lacks case.read AND case.update


def _accountant(gate):
    """Seed a user then set its server-side RBAC role to `accountant`, which the
    RBAC catalog grants neither case.read nor case.update, yielding a deny."""
    assert "case.read" not in ROLE_PERMISSIONS["accountant"]
    gate.add_user(ACCOUNTANT, "viewer")
    gate.db.conn.execute("UPDATE users SET role='accountant' WHERE email=?",
                         (ACCOUNTANT,))
    gate.db.conn.commit()
    return ACCOUNTANT


# --- route topology: forbidden EMP-A1 routes MUST NOT EXIST -----------------
def test_rbacroutes_forbidden_slugs_get_and_post_absent(gate):
    wid, _ = gate.admitted_work()
    for slug in _FORBIDDEN_SLUGS:
        g = gate.c.get(_BASE + "/" + slug, headers=gate.h(OWNER))
        p = gate.c.post(_BASE + "/items/" + wid + "/" + slug, json={},
                        headers=gate.h(OWNER))
        assert g.status_code in (404, 405), "GET " + slug
        assert p.status_code in (404, 405), "POST " + slug


def test_rbacroutes_forbidden_namespace_run_and_execute_absent(gate):
    for slug in ("run", "execute", "start-run", "create-run"):
        g = gate.c.get(_BASE + "/" + slug, headers=gate.h(OWNER))
        p = gate.c.post(_BASE + "/" + slug, json={}, headers=gate.h(OWNER))
        assert g.status_code in (404, 405), "GET " + slug
        assert p.status_code in (404, 405), "POST " + slug


def test_rbacroutes_b9_level_forbidden_still_absent(gate):
    for url in _FORBIDDEN_B9_ROUTES:
        g = gate.c.get(url, headers=gate.h(OWNER))
        p = gate.c.post(url, json={}, headers=gate.h(OWNER))
        assert g.status_code in (404, 405), "GET " + url
        assert p.status_code in (404, 405), "POST " + url


# --- RBAC: case.read gate (role lacking case.read) --------------------------
def test_rbac_no_case_read_cannot_get_policy(gate):
    acct = _accountant(gate)
    assert gate.c.get(_BASE + "/policy",
                      headers=gate.h(acct)).status_code == 403


def test_rbac_no_case_read_cannot_get_registry(gate):
    acct = _accountant(gate)
    assert gate.c.get(_BASE + "/registry",
                      headers=gate.h(acct)).status_code == 403


def test_rbac_no_case_read_cannot_get_counts(gate):
    acct = _accountant(gate)
    assert gate.c.get(_BASE + "/counts",
                      headers=gate.h(acct)).status_code == 403


def test_rbac_no_case_read_cannot_get_items(gate):
    acct = _accountant(gate)
    assert gate.c.get(_BASE + "/items",
                      headers=gate.h(acct)).status_code == 403


# --- RBAC: viewer (case.read, not case.update) ------------------------------
def test_rbac_viewer_can_get_policy(gate):
    assert "case.read" in ROLE_PERMISSIONS["viewer"]
    assert gate.c.get(_BASE + "/policy",
                      headers=gate.h(VIEWER)).status_code == 200


def test_rbac_viewer_can_get_items(gate):
    assert gate.c.get(_BASE + "/items",
                      headers=gate.h(VIEWER)).status_code == 200


def test_rbac_viewer_cannot_submit_items(gate):
    assert "case.update" not in ROLE_PERMISSIONS["viewer"]
    r = gate.c.post(_BASE + "/items", json=gate.clean_work_intake(),
                    headers=gate.h(VIEWER))
    assert r.status_code == 403


def test_rbac_viewer_cannot_claim(gate):
    wid, _ = gate.admitted_work()
    assert gate.wi(wid, "/claim", actor=VIEWER,
                   method="POST").status_code == 403


def test_rbac_viewer_cannot_reprioritize(gate):
    wid, _ = gate.admitted_work()
    assert gate.wi(wid, "/reprioritize", actor=VIEWER, method="POST",
                   priority_class="HIGH").status_code == 403


def test_rbac_viewer_cannot_cancel(gate):
    wid, _ = gate.admitted_work()
    assert gate.wi(wid, "/cancel", actor=VIEWER,
                   method="POST").status_code == 403


# --- tenant isolation -------------------------------------------------------
def test_tenant_other_cannot_get_item(gate):
    wid, _ = gate.admitted_work()
    assert gate.c.get(_BASE + "/items/" + wid,
                      headers=gate.h(OTHER_OWNER)).status_code == 404


def test_tenant_other_cannot_get_subfield(gate):
    wid, _ = gate.admitted_work()
    for sf in ("/intent", "/admission", "/events"):
        assert gate.wi(wid, sf, actor=OTHER_OWNER).status_code == 404, sf


def test_tenant_other_items_list_empty(gate):
    gate.admitted_work()
    rows = gate.c.get(_BASE + "/items", headers=gate.h(OTHER_OWNER)).json()
    assert rows == []


def test_tenant_other_counts_zeroed(gate):
    gate.admitted_work()
    counts = gate.c.get(_BASE + "/counts",
                        headers=gate.h(OTHER_OWNER)).json()["counts_by_state"]
    assert counts == {} or all(v == 0 for v in counts.values())


# --- honesty labels never empty / hidden -----------------------------------
def test_honesty_labels_present_on_policy(gate):
    labels = gate.c.get(_BASE + "/policy",
                        headers=gate.h(OWNER)).json()["honesty_labels"]
    assert labels
    for want in ("INBOX_AND_ADMISSION_ONLY", "NO_EMP_A2_RUN_CREATED",
                 "NO_EXTERNAL_EFFECT", "NOT_PRODUCTION_READY"):
        assert want in labels, want


# --- do-not-rebuild: EMP-A1 only ADDED a namespace, broke nothing -----------
def test_donotrebuild_core_cases_ok(gate):
    assert gate.c.get("/cases", headers=gate.h(OWNER)).status_code == 200


def test_donotrebuild_b9_policy_ok(gate):
    assert gate.c.get("/ai-tools/local-transactions/policy",
                      headers=gate.h(OWNER)).status_code == 200


def test_donotrebuild_b91_recovery_policy_ok(gate):
    assert gate.c.get("/ai-tools/local-transactions/recovery/policy",
                      headers=gate.h(OWNER)).status_code == 200


def test_donotrebuild_b92_observability_policy_ok(gate):
    assert gate.c.get("/ai-tools/local-transactions/observability/policy",
                      headers=gate.h(OWNER)).status_code == 200


def test_donotrebuild_emp_a1_policy_ok(gate):
    assert gate.c.get(_BASE + "/policy",
                      headers=gate.h(OWNER)).status_code == 200


def test_donotrebuild_all_prior_policies_ok_for_owner(gate):
    for url in ("/ai-tools/local-transactions/policy",
                "/ai-tools/local-transactions/recovery/policy",
                "/ai-tools/local-transactions/observability/policy",
                _BASE + "/policy"):
        assert gate.c.get(url, headers=gate.h(OWNER)).status_code == 200, url


# --- roadmap lock: EMP-A1 sequenced after TOOL-B9.2 -------------------------
def test_roadmap_lock_emp_a1_after_b92():
    with open("docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json") as f:
        seq = json.load(f)["sequence"]
    ids = [s["id"] for s in seq]
    assert "TOOL-B9.2" in ids
    assert "EMP-A1" in ids
    assert ids.index("EMP-A1") > ids.index("TOOL-B9.2")
