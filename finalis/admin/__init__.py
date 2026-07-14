"""Finalis Admin / Tenant / User / RBAC Engine — the control plane.

Native local-first identity + tenancy + RBAC with deny-by-default access
decisions, task-scoped AI-worker authorization, and full audit. External
IAM (Keycloak/ZITADEL/Ory/authentik) and policy engines (Cerbos/OpenFGA/
SpiceDB) plug in behind the adapter seams in `adapters.py` later —
local build never blocks on them.
"""
