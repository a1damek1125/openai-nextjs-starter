"""Admin/Tenant/User/RBAC engine tests — the 25 mandated scenarios (grouped)."""
from datetime import datetime

import pytest

from finalis.audit import AuditLog
from finalis.admin.rbac import (PERMISSIONS, ROLE_PERMISSIONS, RbacEngine,
                                ServiceAccount)

NOW = datetime(2026, 7, 8, 12, 0)


@pytest.fixture()
def rig():
    audit = AuditLog()
    eng = RbacEngine(audit)
    t1 = eng.create_tenant("Demo HVAC", "demo-hvac")
    t2 = eng.create_tenant("Other Co", "other")
    owner = eng.create_user("owner@demo", "Owner")
    manager = eng.create_user("manager@demo", "Manager")
    operator = eng.create_user("operator@demo", "Operator")
    viewer = eng.create_user("viewer@demo", "Viewer")
    tech = eng.create_user("tech@demo", "Tech")
    acct = eng.create_user("acct@demo", "Acct")
    eng.add_membership(tenant_id=t1.id, user_id=owner.id, role="owner")
    eng.add_membership(tenant_id=t1.id, user_id=manager.id, role="manager")
    eng.add_membership(tenant_id=t1.id, user_id=operator.id,
                       role="operator")
    eng.add_membership(tenant_id=t1.id, user_id=viewer.id, role="viewer")
    eng.add_membership(tenant_id=t1.id, user_id=tech.id, role="technician")
    eng.add_membership(tenant_id=t1.id, user_id=acct.id, role="accountant")
    ai = ServiceAccount(tenant_id=t1.id, name="finalis-ai")
    eng.service_accounts[ai.id] = ai
    return eng, t1, t2, owner, manager, operator, viewer, tech, acct, ai


class TestRolesAndPermissions:
    def test_catalog_never_contains_ai_self_approval(self):
        assert "ai.approve_own_action" not in PERMISSIONS
        for role, perms in ROLE_PERMISSIONS.items():
            assert "ai.approve_own_action" not in perms

    def test_5_operator_cannot_approve_high_risk(self, rig):
        eng, t1, *_ , operator, viewer, tech, acct, ai = rig[0], rig[1], \
            rig[2], rig[3], rig[4], rig[5], rig[6], rig[7], rig[8], rig[9]
        d = eng.access(actor_type="user", actor_id=operator.id,
                       tenant_id=t1.id, action="action.approve_high_risk")
        assert d.decision == "DENY"
        assert "missing_permission" in d.reasons

    def test_7_viewer_cannot_mutate_case(self, rig):
        eng, t1 = rig[0], rig[1]
        viewer = rig[6]
        assert eng.access(actor_type="user", actor_id=viewer.id,
                          tenant_id=t1.id,
                          action="case.update").decision == "DENY"
        assert eng.access(actor_type="user", actor_id=viewer.id,
                          tenant_id=t1.id,
                          action="case.read").decision == "ALLOW"

    def test_8_technician_scope(self, rig):
        eng, t1 = rig[0], rig[1]
        tech = rig[7]
        assert eng.access(actor_type="user", actor_id=tech.id,
                          tenant_id=t1.id,
                          action="document.upload").decision == "ALLOW"
        assert eng.access(actor_type="user", actor_id=tech.id,
                          tenant_id=t1.id,
                          action="invoice.view").decision == "DENY"

    def test_9_accountant_payments_not_recordings(self, rig):
        eng, t1 = rig[0], rig[1]
        acct, operator = rig[8], rig[5]
        assert eng.access(actor_type="user", actor_id=acct.id,
                          tenant_id=t1.id,
                          action="payment.view").decision == "ALLOW"
        # Accountant has no call access at all.
        assert eng.access(actor_type="user", actor_id=acct.id,
                          tenant_id=t1.id,
                          action="call.view").decision == "DENY"
        # Operator HAS call.view but recordings need the elevated permission.
        d = eng.access(actor_type="user", actor_id=operator.id,
                       tenant_id=t1.id, action="call.view",
                       resource_sensitivity="call_recording")
        assert d.decision == "DENY"
        assert any("call.listen_recording" in r for r in d.reasons)

    def test_4_manager_cannot_manage_owner_settings(self, rig):
        eng, t1 = rig[0], rig[1]
        manager = rig[4]
        assert eng.access(actor_type="user", actor_id=manager.id,
                          tenant_id=t1.id,
                          action="tenant.update_settings"
                          ).decision == "DENY"

    def test_23_sensitive_document_needs_permission(self, rig):
        eng, t1 = rig[0], rig[1]
        operator = rig[5]
        d = eng.access(actor_type="user", actor_id=operator.id,
                       tenant_id=t1.id, action="document.view",
                       resource_sensitivity="sensitive_document")
        assert d.decision == "DENY"
        owner = rig[3]
        d2 = eng.access(actor_type="user", actor_id=owner.id,
                        tenant_id=t1.id, action="document.view",
                        resource_sensitivity="sensitive_document")
        assert d2.decision == "ALLOW"


class TestTenantIsolation:
    def test_12_cross_tenant_denied_for_every_resource_action(self, rig):
        eng, t1, t2 = rig[0], rig[1], rig[2]
        owner = rig[3]
        for action in ["case.read", "document.view", "call.view",
                       "invoice.view", "payment.view", "action.approve",
                       "audit.view", "tenant.manage_users"]:
            d = eng.access(actor_type="user", actor_id=owner.id,
                           tenant_id=t1.id, action=action,
                           resource_tenant_id=t2.id)
            assert d.decision == "DENY", action
            assert "tenant_mismatch" in d.reasons

    def test_owner_of_one_tenant_is_nobody_in_another(self, rig):
        eng, t1, t2 = rig[0], rig[1], rig[2]
        owner = rig[3]           # owner of t1 only
        d = eng.access(actor_type="user", actor_id=owner.id,
                       tenant_id=t2.id, action="case.read")
        assert d.decision == "DENY"
        assert "no_active_membership" in d.reasons


class TestAiWorker:
    def test_6_ai_cannot_approve_own_action(self, rig):
        eng, t1 = rig[0], rig[1]
        ai = rig[9]
        d = eng.access(actor_type="ai_worker", actor_id=ai.id,
                       tenant_id=t1.id, action="action.approve",
                       own_action=True)
        assert d.decision == "DENY"
        assert "ai_cannot_approve_own_action" in d.reasons

    def test_20_service_account_scopes_enforced(self, rig):
        eng, t1 = rig[0], rig[1]
        ai = rig[9]
        assert eng.access(actor_type="ai_worker", actor_id=ai.id,
                          tenant_id=t1.id,
                          action="ai.run_completion_loop"
                          ).decision == "ALLOW"
        assert eng.access(actor_type="ai_worker", actor_id=ai.id,
                          tenant_id=t1.id,
                          action="tenant.update_settings"
                          ).decision == "DENY"
        # Critical action (even in scope) → approval, never silent ALLOW.
        ai.scopes.add("payment.mark_paid")
        d = eng.access(actor_type="ai_worker", actor_id=ai.id,
                       tenant_id=t1.id, action="payment.mark_paid")
        assert d.decision == "REQUIRE_APPROVAL"

    def test_ai_cannot_cross_tenant(self, rig):
        eng, t1, t2 = rig[0], rig[1], rig[2]
        ai = rig[9]
        d = eng.access(actor_type="ai_worker", actor_id=ai.id,
                       tenant_id=t2.id, action="case.read")
        assert d.decision == "DENY"


class TestAdminGuardrails:
    def test_10_last_owner_cannot_be_removed_or_demoted(self, rig):
        eng, t1 = rig[0], rig[1]
        owner = rig[3]
        m = eng.membership_of(owner.id, t1.id)
        with pytest.raises(PermissionError):
            eng.change_role(m.id, "manager", actor_user_id=owner.id)
        with pytest.raises(PermissionError):
            eng.remove_membership(m.id, actor_user_id=owner.id)

    def test_11_cannot_grant_permissions_you_lack(self, rig):
        eng, t1 = rig[0], rig[1]
        manager, operator = rig[4], rig[5]
        m = eng.membership_of(operator.id, t1.id)
        with pytest.raises(PermissionError):
            eng.change_role(m.id, "owner", actor_user_id=manager.id)

    def test_3_owner_invites_and_17_audit_events(self, rig):
        eng, t1 = rig[0], rig[1]
        owner, operator = rig[3], rig[5]
        inv = eng.invite(tenant_id=t1.id, email="new@demo", role="operator",
                         actor_user_id=owner.id, now=NOW)
        assert inv.status == "pending" and inv.token_hash
        with pytest.raises(PermissionError):   # operator cannot invite
            eng.invite(tenant_id=t1.id, email="x@demo", role="viewer",
                       actor_user_id=operator.id, now=NOW)
        # Role change writes audit.
        m = eng.membership_of(operator.id, t1.id)
        eng.change_role(m.id, "viewer", actor_user_id=owner.id)
        types = {e.event_type for e in eng.audit.events()}
        assert {"ADMIN_USER_INVITED", "ADMIN_ROLE_CHANGED",
                "ADMIN_MEMBERSHIP_ADDED"} <= types
        assert eng.audit.verify_chain()


class TestApiKeys:
    def test_18_19_key_hashed_and_revocable(self, rig):
        eng, t1 = rig[0], rig[1]
        owner = rig[3]
        key, token = eng.create_api_key(tenant_id=t1.id,
                                        scopes={"case.read"},
                                        actor_user_id=owner.id, now=NOW)
        assert token not in key.token_hash          # hashed, not raw
        assert eng.check_api_key(token, required_scope="case.read",
                                 tenant_id=t1.id, now=NOW)
        assert not eng.check_api_key(token, required_scope="case.update",
                                     tenant_id=t1.id, now=NOW)
        assert not eng.check_api_key(token, required_scope="case.read",
                                     tenant_id="other", now=NOW)
        eng.revoke_api_key(key.id, actor_user_id=owner.id)
        assert not eng.check_api_key(token, required_scope="case.read",
                                     tenant_id=t1.id, now=NOW)

    def test_key_scopes_capped_by_minter(self, rig):
        eng, t1 = rig[0], rig[1]
        operator = rig[5]
        with pytest.raises(PermissionError):
            eng.create_api_key(tenant_id=t1.id,
                               scopes={"payment.mark_paid"},
                               actor_user_id=operator.id, now=NOW)


class TestDefaults:
    def test_22_deny_by_default(self, rig):
        eng, t1 = rig[0], rig[1]
        owner = rig[3]
        d = eng.access(actor_type="user", actor_id=owner.id,
                       tenant_id=t1.id, action="nonexistent.action")
        assert d.decision == "DENY"
        assert "unknown_action_deny_by_default" in d.reasons

    def test_21_platform_admin_access_audited(self, rig):
        eng, t1 = rig[0], rig[1]
        pa = eng.create_user("root@finalis", "Platform Admin")
        eng.add_membership(tenant_id=t1.id, user_id=pa.id,
                           role="platform_admin")
        eng.access(actor_type="user", actor_id=pa.id, tenant_id=t1.id,
                   action="audit.export")
        assert eng.audit.events(event_type="PLATFORM_ADMIN_ACCESS")

    def test_every_decision_is_logged(self, rig):
        eng, t1 = rig[0], rig[1]
        owner = rig[3]
        before = len(eng.audit.events(event_type="ACCESS_DECISION"))
        d = eng.access(actor_type="user", actor_id=owner.id,
                       tenant_id=t1.id, action="case.read")
        assert d.audit_log_id
        assert len(eng.audit.events(
            event_type="ACCESS_DECISION")) == before + 1
        assert eng.audit.verify_chain()

    def test_inactive_user_and_membership_denied(self, rig):
        eng, t1 = rig[0], rig[1]
        operator = rig[5]
        eng.users[operator.id].status = "disabled"
        assert eng.access(actor_type="user", actor_id=operator.id,
                          tenant_id=t1.id,
                          action="case.read").decision == "DENY"
