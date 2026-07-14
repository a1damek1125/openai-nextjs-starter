# Admin / Tenant / User / RBAC Engine — Founder/CTO Report

**Branch**: `claude/finalis-admin-tenant-rbac-engine` · Tests: **367 passed**
(21 RBAC tests added; baseline 346 intact).

## Implemented and tested (native, local-first)
- **Tenants, users, memberships, invitations** (hashed tokens, expiry),
  **service accounts (AI worker identity)**, **API keys** (SHA-256 hashed,
  scope-capped by the minter's own permissions, tenant-bound, revocable,
  expiring).
- **9 roles** (owner/manager/operator/technician/accountant/viewer/
  compliance_admin/ai_worker/platform_admin) over a **~45-permission catalog**
  with risk levels; `ai.approve_own_action` is structurally ungrantable
  (tested: absent from catalog and every role).
- **AccessDecision engine — deny by default**: tenant mismatch always denies
  (tested across 8 resource actions); inactive user/membership denies;
  unknown action denies; sensitive resources (recordings, sensitive docs,
  payments) need the elevated permission explicitly; **critical actions by
  non-humans return REQUIRE_APPROVAL, never silent ALLOW**; AI worker cannot
  approve its own action or cross tenants; every decision writes an
  ACCESS_DECISION audit event on the hash chain.
- **Admin guardrails**: last-owner rule (demote + remove both refused);
  permission-escalation rule (cannot grant what you lack — role changes and
  API-key scopes both capped); platform_admin access is always audited;
  every admin mutation writes an audit event.

## Scaffolded (interfaces only, honestly)
`IdentityProviderAdapter` (Keycloak/ZITADEL/Ory/authentik) and
`PolicyEngineAdapter` (Cerbos/OpenFGA/SpiceDB) in `finalis/admin/adapters.py`.
Recommended per the 2026 agent-authz research (arXiv 2605.05287/05440/02682):
Phase 2 = ZITADEL or Keycloak for SSO/MFA; Phase 3 = Cerbos or OpenFGA for
policy/ReBAC. Not implemented; nothing blocks on them.

## Not yet wired
Portal endpoints for the admin UI (the portal keeps its simpler auth for
now; wiring RbacEngine behind /admin/* is the next sprint), teams,
MFA, admin UI pages.

## Blocks pilot: portal wiring + admin UI. Blocks production: external IAM
(SSO/MFA), DB persistence of RBAC entities, policy engine, RLS.

## Top next tasks
1. Wire RbacEngine into portal auth dependency (replace role-string checks).
2. /admin/* API endpoints + admin UI pages from the API.
3. Persist RBAC entities (migration v3).
4. Teams + per-operator assigned-case filtering.
5. ZITADEL adapter (Phase 2 IAM).
