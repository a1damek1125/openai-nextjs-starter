"""External IAM / policy adapter seams — SCAFFOLDED ONLY (not implemented).

Local-first rule: the native RbacEngine serves dev + first pilot. These
protocols define where Keycloak/ZITADEL/Ory/authentik (identity) and
Cerbos/OpenFGA/SpiceDB (policy) plug in without touching call sites.
"""
from __future__ import annotations

from typing import Optional, Protocol


class IdentityProviderAdapter(Protocol):
    """Keycloak / ZITADEL / Ory / authentik implement this (SCAFFOLDED).

    Keycloak: OIDC/OAuth2/SAML + LDAP/AD + fine-grained authz services.
    ZITADEL: B2B multi-tenant first-class, MFA/passkeys, audit trail.
    Ory: API-first auth components. authentik: self-host SSO/proxy.
    """
    name: str
    def authenticate(self, token: str) -> Optional[dict]: ...
    def get_user(self, external_id: str) -> Optional[dict]: ...


class PolicyEngineAdapter(Protocol):
    """Cerbos (RBAC/ABAC/PBAC policies) / OpenFGA / SpiceDB (Zanzibar-style
    ReBAC) implement this (SCAFFOLDED). The native AccessDecision engine
    keeps identical semantics so a swap is behavior-preserving."""
    name: str
    def check(self, *, actor: dict, action: str, resource: dict,
              context: dict) -> str: ...   # ALLOW | DENY | REQUIRE_APPROVAL
