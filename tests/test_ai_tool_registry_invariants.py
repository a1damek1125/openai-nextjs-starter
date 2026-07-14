"""TOOL-B1 cross-cutting negative-space invariants.

These assert the properties the whole registry must uphold no matter what a
descriptor declares: there is NO execute path, forbidden capabilities are never
admitted, `may_execute_now` is False everywhere, AI workers cannot self-admit,
and the static registry routes are not shadowed by the /{tool_id} param route.
"""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.auth import AuthService
from finalis.portal.seed import seed
from tests.conftest import Gate, OWNER, MANAGER


@pytest.fixture()
def gate():
    return Gate()


class TestNoExecutionSurface:
    def test_no_execute_route_registered(self, gate):
        paths = {getattr(r, "path", "") for r in gate.app.routes}
        for forbidden in ("/ai-tools/{tool_id}/execute",
                          "/ai-tools/{tool_id}/run",
                          "/ai-tools/{tool_id}/invoke",
                          "/ai-tools/{tool_id}/call",
                          "/ai-tools/execute"):
            assert forbidden not in paths, forbidden

    def test_registry_policy_declares_no_broker(self, gate):
        p = gate.c.get("/ai-tools/registry/policy",
                       headers=gate.h(OWNER)).json()
        assert p["is_tool_broker"] is False
        assert p["has_execute_endpoint"] is False
        assert p["has_dry_run_execution"] is False
        assert p["calls_external_providers"] is False
        assert p["calls_llm"] is False
        assert p["is_mcp_server"] is False
        assert p["admission_is_fail_closed"] is True

    def test_admit_response_never_permits_execution(self, gate):
        tid = gate.register_tool(requester=OWNER).json()["tool_id"]
        r = gate.admit_tool(tid, actor=OWNER).json()
        assert r["may_execute_now"] is False
        assert r["admitted"] is True                # clean tool admits
        assert r["admission_status"] == "AVAILABLE_FOR_FUTURE_BROKER"

    def test_safe_view_never_permits_execution(self, gate):
        tid = gate.register_tool(requester=OWNER).json()["tool_id"]
        v = gate.c.get(f"/ai-tools/{tid}/safe", headers=gate.h(OWNER)).json()
        assert v["may_execute_now"] is False


class TestForbiddenNeverAdmitted:
    @pytest.mark.parametrize("category,side_effect", [
        ("PAYMENT", "PAYMENT_MOVEMENT"),
        ("CRM_WRITE", "CRM_MUTATION"),
        ("EVIDENCE_MUTATION", "EVIDENCE_MUTATION"),
        ("CUSTOMER_MESSAGING", "CUSTOMER_MESSAGING"),
        ("DOCUMENT_EXPORT", "EXTERNAL_WRITE"),
        ("IDENTITY_ACCESS", "INTERNAL_WRITE"),
        ("ADMIN_OPERATION", "INTERNAL_WRITE"),
    ])
    def test_forbidden_category_cannot_be_admitted(self, gate, category,
                                                   side_effect):
        body = gate.clean_tool_body(tool_name=f"X {category}",
                                    category=category,
                                    side_effect_class=side_effect,
                                    declared_side_effects=[side_effect])
        tid = gate.register_tool(body=body, requester=OWNER).json()["tool_id"]
        r = gate.admit_tool(tid, actor=OWNER).json()
        assert r["admitted"] is False
        assert r["admission_status"] != "AVAILABLE_FOR_FUTURE_BROKER"

    def test_forbidden_side_effect_forces_forbidden_status(self, gate):
        body = gate.clean_tool_body(tool_name="Destroyer",
                                    category="INTERNAL_WRITE",
                                    side_effect_class="DESTRUCTIVE",
                                    declared_side_effects=["DESTRUCTIVE"])
        head = gate.register_tool(body=body, requester=OWNER).json()
        assert head["status"] == "FORBIDDEN_CAPABILITY"
        assert head["admitted"] is False


class TestSelfAdmissionForbidden:
    def test_ai_worker_cannot_register_and_admit(self, gate):
        gate.add_user("ai@demo.finalis", "ai_worker")
        # ai_worker has case.update, so it may register a DRAFT descriptor…
        r = gate.register_tool(requester="ai@demo.finalis")
        assert r.status_code == 200
        tid = r.json()["tool_id"]
        # …but may never admit it (no tenant.manage_integrations).
        assert gate.c.post(f"/ai-tools/{tid}/admit",
                           headers=gate.h("ai@demo.finalis")).status_code == 403

    def test_manager_cannot_admit(self, gate):
        tid = gate.register_tool(requester=MANAGER).json()["tool_id"]
        assert gate.c.post(f"/ai-tools/{tid}/admit",
                           headers=gate.h(MANAGER)).status_code == 403


class TestRouteOrdering:
    def test_static_registry_routes_not_shadowed(self, gate):
        h = gate.h(OWNER)
        # These must resolve to their dedicated handlers, never be swallowed by
        # /ai-tools/{tool_id} (which would 404 "tool not found").
        for path in ("/ai-tools/types", "/ai-tools/registry/policy",
                     "/ai-tools/registry/snapshot", "/ai-tools/registry/events"):
            r = gate.c.get(path, headers=h)
            assert r.status_code == 200, path
            assert "not found" not in r.text.lower(), path

    def test_types_payload_is_taxonomy_not_a_tool(self, gate):
        j = gate.c.get("/ai-tools/types", headers=gate.h(OWNER)).json()
        assert "categories" in j and "status_dominance" in j
        assert "tool_id" not in j
