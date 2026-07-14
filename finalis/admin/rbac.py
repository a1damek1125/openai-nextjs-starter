"""Roles, permissions, memberships, and the deterministic AccessDecision
engine. Deny by default; RBAC now, ABAC/ReBAC context hooks in the decision
signature already (per the 2026 agent-authorization research: task-scoped
envelopes, no permission inheritance across tenants, audited denials)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional


def _uuid() -> str:
    return str(uuid.uuid4())


# --- Permission catalog ---------------------------------------------------------
PERMISSIONS: dict[str, str] = {  # key -> risk level
    "tenant.view": "low", "tenant.update_settings": "high",
    "tenant.manage_users": "high", "tenant.manage_integrations": "high",
    "tenant.manage_playbooks": "medium",
    "case.read": "low", "case.create": "low", "case.update": "low",
    "case.assign": "medium", "case.close": "medium",
    "case.reopen": "high", "case.delete_soft": "high",
    "document.view": "low", "document.upload": "low",
    "document.analyze": "low", "document.view_sensitive": "high",
    "document.delete": "high",
    "call.view": "low", "call.start_outbound": "medium",
    "call.transfer": "medium", "call.listen_recording": "high",
    "call.manage_recording_policy": "high",
    "action.request": "low", "action.execute_low_risk": "low",
    "action.approve": "medium", "action.reject": "medium",
    "action.approve_high_risk": "critical",
    "override.soft": "high", "override.hard": "critical",
    "override.compliance_review": "high",
    "offer.create": "medium", "offer.approve": "high",
    "invoice.create": "high", "invoice.view": "medium",
    "payment.view": "medium", "payment.mark_paid": "critical",
    "refund.request": "high",
    "audit.view": "medium", "audit.export": "high",
    "access_log.view": "medium",
    "ai.run_completion_loop": "low", "ai.run_conversation_analysis": "low",
    "ai.generate_message_draft": "low", "ai.use_tools": "low",
    # ai.approve_own_action intentionally NOT in the catalog: ungrantable.
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "owner": set(PERMISSIONS),          # everything grantable
    "manager": {"tenant.view", "case.read", "case.create", "case.update",
                "case.assign", "case.close", "document.view",
                "document.upload", "document.analyze", "call.view",
                "call.start_outbound", "call.transfer", "action.request",
                "action.execute_low_risk", "action.approve",
                "action.reject", "override.soft", "offer.create",
                "offer.approve", "invoice.view", "payment.view",
                "audit.view", "ai.run_completion_loop",
                "ai.run_conversation_analysis",
                "ai.generate_message_draft"},
    "operator": {"tenant.view", "case.read", "case.create", "case.update",
                 "document.view", "document.upload", "call.view",
                 "action.request", "action.execute_low_risk"},
    "technician": {"tenant.view", "case.read", "document.view",
                   "document.upload"},
    "accountant": {"tenant.view", "invoice.view", "invoice.create",
                   "payment.view", "payment.mark_paid", "audit.view"},
    "viewer": {"tenant.view", "case.read", "document.view", "call.view",
               "invoice.view"},
    "compliance_admin": {"tenant.view", "audit.view", "audit.export",
                         "access_log.view", "override.compliance_review",
                         "call.manage_recording_policy", "case.read"},
    "ai_worker": {"case.read", "case.update", "document.view",
                  "document.analyze", "action.request",
                  "action.execute_low_risk", "ai.run_completion_loop",
                  "ai.run_conversation_analysis",
                  "ai.generate_message_draft", "ai.use_tools"},
    "platform_admin": set(PERMISSIONS),  # internal; heavily audited
}

SENSITIVE_RESOURCES = {"call_recording": "call.listen_recording",
                       "sensitive_document": "document.view_sensitive",
                       "payment": "payment.view"}


@dataclass
class Tenant:
    name: str
    slug: str
    status: str = "active"
    industry: str = "hvac"
    id: str = field(default_factory=_uuid)


@dataclass
class User:
    email: str
    name: str
    status: str = "active"
    id: str = field(default_factory=_uuid)


@dataclass
class Membership:
    tenant_id: str
    user_id: str
    role: str
    status: str = "active"
    invited_by: Optional[str] = None
    id: str = field(default_factory=_uuid)


@dataclass
class Invitation:
    tenant_id: str
    email: str
    role: str
    token_hash: str
    invited_by: str
    status: str = "pending"
    expires_at: Optional[datetime] = None
    id: str = field(default_factory=_uuid)


@dataclass
class ServiceAccount:
    tenant_id: str
    name: str
    type: str = "ai_worker"
    scopes: set = field(default_factory=lambda: set(
        ROLE_PERMISSIONS["ai_worker"]))
    status: str = "active"
    id: str = field(default_factory=_uuid)


@dataclass
class ApiKey:
    tenant_id: str
    token_hash: str
    scopes: set
    owner_user_id: Optional[str] = None
    service_account_id: Optional[str] = None
    status: str = "active"
    expires_at: Optional[datetime] = None
    id: str = field(default_factory=_uuid)


@dataclass
class AccessDecision:
    decision: str                      # ALLOW | DENY | REQUIRE_APPROVAL
    reasons: list[str]
    required_permissions: list[str]
    risk_level: str
    audit_log_id: Optional[str] = None


class RbacEngine:
    """Deny-by-default access decisions + admin operations, all audited."""

    def __init__(self, audit) -> None:
        self.audit = audit
        self.tenants: dict[str, Tenant] = {}
        self.users: dict[str, User] = {}
        self.memberships: list[Membership] = []
        self.invitations: list[Invitation] = []
        self.service_accounts: dict[str, ServiceAccount] = {}
        self.api_keys: dict[str, ApiKey] = {}

    # -- admin ops (every mutation audited) -------------------------------------
    def create_tenant(self, name: str, slug: str) -> Tenant:
        t = Tenant(name=name, slug=slug)
        self.tenants[t.id] = t
        self.audit.append(event_type="ADMIN_TENANT_CREATED", actor="system",
                          payload={"tenant_id": t.id, "slug": slug})
        return t

    def create_user(self, email: str, name: str) -> User:
        u = User(email=email, name=name)
        self.users[u.id] = u
        return u

    def add_membership(self, *, tenant_id: str, user_id: str, role: str,
                       actor_user_id: str = "system") -> Membership:
        if role not in ROLE_PERMISSIONS:
            raise ValueError(f"unknown role {role}")
        m = Membership(tenant_id=tenant_id, user_id=user_id, role=role,
                       invited_by=actor_user_id)
        self.memberships.append(m)
        self.audit.append(event_type="ADMIN_MEMBERSHIP_ADDED",
                          actor=actor_user_id,
                          payload={"tenant_id": tenant_id,
                                   "user_id": user_id, "role": role})
        return m

    def membership_of(self, user_id: str,
                      tenant_id: str) -> Optional[Membership]:
        return next((m for m in self.memberships
                     if m.user_id == user_id and m.tenant_id == tenant_id
                     and m.status == "active"), None)

    def owners_of(self, tenant_id: str) -> list[Membership]:
        return [m for m in self.memberships
                if m.tenant_id == tenant_id and m.role == "owner"
                and m.status == "active"]

    def change_role(self, membership_id: str, new_role: str, *,
                    actor_user_id: str) -> Membership:
        m = next(x for x in self.memberships if x.id == membership_id)
        actor_m = self.membership_of(actor_user_id, m.tenant_id)
        # Escalation rule: cannot grant beyond your own permission set.
        if actor_m is None or not (
                ROLE_PERMISSIONS.get(new_role, set())
                <= ROLE_PERMISSIONS.get(actor_m.role, set())):
            self._log_denied(actor_user_id, m.tenant_id, "change_role",
                             "permission_escalation")
            raise PermissionError("cannot grant permissions you lack")
        # Last-owner rule.
        if m.role == "owner" and new_role != "owner" \
                and len(self.owners_of(m.tenant_id)) == 1:
            self._log_denied(actor_user_id, m.tenant_id, "change_role",
                             "last_owner")
            raise PermissionError("cannot demote the last owner")
        old = m.role
        m.role = new_role
        self.audit.append(event_type="ADMIN_ROLE_CHANGED",
                          actor=actor_user_id,
                          payload={"membership_id": m.id, "from": old,
                                   "to": new_role,
                                   "tenant_id": m.tenant_id})
        return m

    def remove_membership(self, membership_id: str, *,
                          actor_user_id: str) -> None:
        m = next(x for x in self.memberships if x.id == membership_id)
        if m.role == "owner" and len(self.owners_of(m.tenant_id)) == 1:
            raise PermissionError("cannot remove the last owner")
        m.status = "removed"
        self.audit.append(event_type="ADMIN_MEMBERSHIP_REMOVED",
                          actor=actor_user_id,
                          payload={"membership_id": m.id,
                                   "tenant_id": m.tenant_id})

    def invite(self, *, tenant_id: str, email: str, role: str,
               actor_user_id: str, now: datetime) -> Invitation:
        actor_m = self.membership_of(actor_user_id, tenant_id)
        if actor_m is None or "tenant.manage_users" not in \
                ROLE_PERMISSIONS[actor_m.role]:
            raise PermissionError("not permitted to invite users")
        import hashlib
        import secrets
        token = secrets.token_urlsafe(24)
        inv = Invitation(tenant_id=tenant_id, email=email, role=role,
                         token_hash=hashlib.sha256(token.encode())
                         .hexdigest(),
                         invited_by=actor_user_id,
                         expires_at=now + timedelta(days=7))
        self.invitations.append(inv)
        self.audit.append(event_type="ADMIN_USER_INVITED",
                          actor=actor_user_id,
                          payload={"tenant_id": tenant_id, "email": email,
                                   "role": role})
        return inv

    def create_api_key(self, *, tenant_id: str, scopes: set,
                       actor_user_id: str,
                       now: datetime) -> tuple[ApiKey, str]:
        import hashlib
        import secrets
        actor_m = self.membership_of(actor_user_id, tenant_id)
        if actor_m is None or not (
                scopes <= ROLE_PERMISSIONS[actor_m.role]):
            raise PermissionError("cannot mint key beyond own permissions")
        token = secrets.token_urlsafe(32)
        key = ApiKey(tenant_id=tenant_id,
                     token_hash=hashlib.sha256(token.encode()).hexdigest(),
                     scopes=scopes, owner_user_id=actor_user_id,
                     expires_at=now + timedelta(days=90))
        self.api_keys[key.id] = key
        self.audit.append(event_type="ADMIN_API_KEY_CREATED",
                          actor=actor_user_id,
                          payload={"tenant_id": tenant_id, "key_id": key.id,
                                   "scopes": sorted(scopes)})
        return key, token

    def check_api_key(self, token: str, *, required_scope: str,
                      tenant_id: str, now: datetime) -> bool:
        import hashlib
        h = hashlib.sha256(token.encode()).hexdigest()
        key = next((k for k in self.api_keys.values()
                    if k.token_hash == h), None)
        if key is None or key.status != "active":
            return False
        if key.tenant_id != tenant_id:
            return False
        if key.expires_at and now > key.expires_at:
            return False
        return required_scope in key.scopes

    def revoke_api_key(self, key_id: str, *, actor_user_id: str) -> None:
        self.api_keys[key_id].status = "revoked"
        self.audit.append(event_type="ADMIN_API_KEY_REVOKED",
                          actor=actor_user_id, payload={"key_id": key_id})

    # -- the AccessDecision engine ------------------------------------------------
    def access(self, *, actor_type: str, actor_id: str, tenant_id: str,
               action: str, resource_tenant_id: Optional[str] = None,
               resource_sensitivity: Optional[str] = None,
               own_action: bool = False,
               approval_granted: bool = False,
               context: Optional[dict[str, Any]] = None) -> AccessDecision:
        reasons: list[str] = []
        required = [action] if action in PERMISSIONS else []
        risk = PERMISSIONS.get(action, "critical")

        def deny(reason: str) -> AccessDecision:
            reasons.append(reason)
            d = AccessDecision("DENY", reasons, required, risk)
            d.audit_log_id = self._log_decision(actor_type, actor_id,
                                                tenant_id, action, d)
            return d

        # 1. Tenant isolation — always first, server-side, no exceptions.
        if resource_tenant_id is not None \
                and resource_tenant_id != tenant_id:
            return deny("tenant_mismatch")
        # 2. Unknown action → deny by default.
        if action not in PERMISSIONS:
            return deny("unknown_action_deny_by_default")
        # 3. Actor resolution.
        if actor_type == "user":
            user = self.users.get(actor_id)
            if user is None or user.status != "active":
                return deny("user_inactive")
            m = self.membership_of(actor_id, tenant_id)
            if m is None:
                return deny("no_active_membership")
            perms = ROLE_PERMISSIONS[m.role]
            if m.role == "platform_admin":
                self.audit.append(event_type="PLATFORM_ADMIN_ACCESS",
                                  actor=actor_id,
                                  payload={"tenant_id": tenant_id,
                                           "action": action})
        elif actor_type in ("ai_worker", "service_account"):
            sa = self.service_accounts.get(actor_id)
            if sa is None or sa.status != "active":
                return deny("service_account_inactive")
            if sa.tenant_id != tenant_id:
                return deny("tenant_mismatch")
            perms = sa.scopes
            # AI self-approval is structurally impossible:
            if own_action and action.startswith(("action.approve",
                                                 "override.")):
                return deny("ai_cannot_approve_own_action")
        else:
            return deny("unknown_actor_type")
        # 4. Permission check.
        if action not in perms:
            return deny("missing_permission")
        # 5. Sensitive resources need the elevated permission explicitly.
        if resource_sensitivity:
            needed = SENSITIVE_RESOURCES.get(resource_sensitivity)
            if needed and needed not in perms:
                return deny(f"sensitive_requires:{needed}")
        # 6. High-risk actions require approval unless granted.
        if risk == "critical" and not approval_granted \
                and actor_type != "user":
            d = AccessDecision("REQUIRE_APPROVAL",
                               ["critical_action_requires_approval"],
                               required, risk)
            d.audit_log_id = self._log_decision(actor_type, actor_id,
                                                tenant_id, action, d)
            return d
        d = AccessDecision("ALLOW", ["granted"], required, risk)
        d.audit_log_id = self._log_decision(actor_type, actor_id,
                                            tenant_id, action, d)
        return d

    def _log_decision(self, actor_type, actor_id, tenant_id, action,
                      decision: AccessDecision) -> str:
        ev = self.audit.append(
            event_type="ACCESS_DECISION", actor=f"{actor_type}:{actor_id}",
            payload={"tenant_id": tenant_id, "action": action,
                     "decision": decision.decision,
                     "reasons": decision.reasons,
                     "risk": decision.risk_level})
        return ev.id

    def _log_denied(self, actor, tenant_id, action, reason) -> None:
        self.audit.append(event_type="ACCESS_DENIED_ADMIN", actor=actor,
                          payload={"tenant_id": tenant_id,
                                   "action": action, "reason": reason})
