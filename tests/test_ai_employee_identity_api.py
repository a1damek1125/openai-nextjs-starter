"""CORE-A1 — Finalis AI Employee identity + authority pre-check API.

Tenant-scoped, non-autonomous AI worker identity; deterministic authority
boundary; RBAC + tenant isolation; honest labels. No LLM/external calls.
"""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def client():
    app = create_app(":memory:")
    seed(app.state.db)
    return TestClient(app)


def _login(client, email="owner@demo.finalis"):
    t = client.post("/auth/login", json={"email": email,
                                         "password": "demo1234"}).json()
    return {"Authorization": f"Bearer {t['token']}"}


def _emp(client, h):
    return client.get("/ai-employees", headers=h).json()[0]


def _check(client, h, eid, action, segment="casework", **extra):
    return client.post(f"/ai-employees/{eid}/authority/check",
                       json={"action_type": action, "segment": segment,
                             **extra}, headers=h).json()


class TestIdentityProfile:
    def test_1_2_profile_endpoint_and_default(self, client):
        h = _login(client)
        emps = client.get("/ai-employees", headers=h)
        assert emps.status_code == 200 and len(emps.json()) >= 1

    def test_3_4_5_identity_type_tenant_role(self, client):
        h = _login(client)
        e = _emp(client, h)
        assert e["identity_type"] == "AI_EMPLOYEE"
        assert e["tenant_id"] == "demo-hvac"
        assert e["role"] == "ai_worker"

    def test_6_7_8_9_10_capability_matrix_and_flags(self, client):
        h = _login(client)
        e = _emp(client, h)
        assert e["segment_capabilities"]
        assert e["forbidden_action_types"]
        assert e["approval_required_action_types"]
        assert e["production_autonomy_enabled"] is False
        assert e["honesty_labels"]
        # every dangerous capability is disabled
        for flag in ("can_verify_memory", "can_merge_customers",
                     "can_override_consent", "can_approve_quote",
                     "can_self_approve_quote", "can_execute_payment",
                     "can_change_case_outcome", "can_rewrite_evidence",
                     "can_delete_evidence", "can_call_external_provider"):
            assert e[flag] is False, flag

    def test_11_owner_reads_full_profile(self, client):
        h = _login(client)
        e = _emp(client, h)
        assert client.get(f"/ai-employees/{e['ai_employee_id']}",
                          headers=h).status_code == 200

    def test_12_viewer_reads_safe_profile(self, client):
        vh = _login(client, "viewer@demo.finalis")
        r = client.get("/ai-employees", headers=vh)
        assert r.status_code == 200
        # no secrets/tokens leak in the profile
        assert "password" not in r.text.lower() and "token" not in r.text.lower()

    def test_13_cross_tenant_read_denied(self, client):
        h = _login(client)
        eid = _emp(client, h)["ai_employee_id"]
        oh = _login(client, "owner@other.finalis")
        assert client.get(f"/ai-employees/{eid}",
                          headers=oh).status_code == 404

    def test_14_unauthorized_cannot_register_identity(self, client):
        # viewer/AI cannot create/modify identity (admin-only).
        vh = _login(client, "viewer@demo.finalis")
        assert client.post("/ai-employees/default",
                           headers=vh).status_code == 403

    def test_15_no_self_permission_mutation_endpoint(self, client):
        # There is deliberately NO endpoint to change an AI employee's
        # permissions — identity is immutable via the API surface.
        h = _login(client)
        eid = _emp(client, h)["ai_employee_id"]
        for verb in ("patch", "put", "delete"):
            r = getattr(client, verb)(f"/ai-employees/{eid}", headers=h)
            assert r.status_code in (404, 405)


class TestAuthorityCheck:
    def test_16_17_endpoint_and_deterministic(self, client):
        h = _login(client)
        eid = _emp(client, h)["ai_employee_id"]
        a = _check(client, h, eid, "read_case_summary")
        b = _check(client, h, eid, "read_case_summary")
        assert a["decision"] == b["decision"] == "READ_ONLY_ALLOWED"

    def test_18_forbidden_blocked_hard_fail(self, client):
        h = _login(client)
        eid = _emp(client, h)["ai_employee_id"]
        d = _check(client, h, eid, "rewrite_evidence")
        assert d["decision"] == "BLOCKED" and d["hard_fail"] is True

    def test_19_20_21_22_action_classes(self, client):
        h = _login(client)
        eid = _emp(client, h)["ai_employee_id"]
        assert _check(client, h, eid, "propose_merge")["decision"] \
            == "APPROVAL_REQUIRED"
        assert _check(client, h, eid, "draft_case_summary")["decision"] \
            == "ALLOWED_DRAFT_ONLY"
        assert _check(client, h, eid, "read_case_summary")["decision"] \
            == "READ_ONLY_ALLOWED"
        assert _check(client, h, eid, "totally_unknown")["decision"] \
            == "NOT_IMPLEMENTED"

    def test_23_cross_tenant_authority_check_blocked(self, client):
        h = _login(client)
        eid = _emp(client, h)["ai_employee_id"]
        d = _check(client, h, eid, "read_case_summary",
                   subject_tenant_id="other-tenant")
        assert d["decision"] == "BLOCKED" and d["hard_fail"] is True

    def test_23b_cross_tenant_employee_check_denied(self, client):
        h = _login(client)
        eid = _emp(client, h)["ai_employee_id"]
        oh = _login(client, "owner@other.finalis")
        assert client.post(f"/ai-employees/{eid}/authority/check",
                           json={"action_type": "read_case_summary"},
                           headers=oh).status_code == 404

    def test_24_response_reason_and_labels(self, client):
        h = _login(client)
        eid = _emp(client, h)["ai_employee_id"]
        d = _check(client, h, eid, "override_consent")
        assert d["reason"] and d["honesty_labels"]
        assert d["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_capability_snapshot_hash_present(self, client):
        h = _login(client)
        eid = _emp(client, h)["ai_employee_id"]
        snap = client.get(f"/ai-employees/{eid}/capability-snapshot",
                          headers=h).json()
        assert snap["capability_snapshot_hash"]
        assert snap["capability_snapshot"]["production_autonomy_enabled"] \
            is False


def test_25_no_external_provider_call_surface(client):
    # The identity/authority surface never reaches outward; assert the
    # honesty posture is explicit and no network egress is implied.
    h = _login(client)
    e = _emp(client, h)
    blob = " ".join(e["honesty_labels"])
    assert "cannot call external providers directly" in blob
    assert "Production autonomy is disabled." in blob
