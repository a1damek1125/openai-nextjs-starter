# FINALIS 1000 — DO-NOT-REBUILD Enforcement (SP0001)

SP0000's `FINALIS_1000_DO_NOT_REBUILD.md` states *what* must not be rebuilt.
SP0001 makes it **mechanically enforced** by the Architecture Immune System.
Every protected capability has `replacement_policy: DO_NOT_REBUILD` in the twin
and exactly one `canonical_owner` (INV-0001-01).

## How a silent rebuild is caught

A "silent rebuild" is a **second source of truth** for an existing capability —
`CRM2`, `customer_platform`, a second run ledger, an alternative approval kernel,
etc. Three mechanical signals catch it, none relying on the name:

1. **Ownership conflict (P0).** A new module/route/table namespace that overlaps
   a protected capability's declared ownership → `CAPABILITY_OWNERSHIP_CONFLICT`.
   A duplicate that claims `/crm`-like routes or `crm_`-like tables collides.
2. **Unowned node (P1).** A new module under `finalis/` that belongs to no
   declared capability → `UNOWNED_NODE`. A genuinely new capability must be
   declared (twin + Change Intent `NEW_CAPABILITY`); an undeclared one fails.
3. **Duplication candidate (P2, advisory).** The Semantic Duplication Candidate
   Detector scores structural overlap (routes ∪ tables ∪ permissions ∪
   dependency-neighborhood ∪ purpose lexicon, Jaccard, weights summing to 1). A
   high score is a **review candidate**, never proof (INV-0001-07); an LLM may
   review it but is never sole hard-gate evidence (D-0001-12).

## Protected capabilities (32)

All carry `DO_NOT_REBUILD`. Product engines: `crm`, `evidence`, `case_graph`,
`lifecycle_universal`, `cpq`, `scheduling`, `telephony`, `voice`,
`action_communication`, `command_center`, `agent_runtime_governance`,
`audit_chain`, `rbac_admin`, `portal_shell` (presentation, not authority).
Governance ladder: `core_a1_identity` … `core_a6_artifacts`, `tool_b1_registry`
… `tool_b92_observability`, `emp_a1_work_inbox`.

Forbidden edges make the **directionality** enforceable: every product engine
declares `forbidden_dependencies: ["finalis.ai_employee"]`, so a product engine
importing the governance kernel is a P0 — the governance ladder may be consumed
by the composition root, never by a product engine reaching sideways into it.

## What is allowed (not a rebuild)

- **Extension** of a capability through its `canonical_owner` (INV-0001-02:
  extension ≠ second source of truth).
- A **declared** new capability (twin entry + `NEW_CAPABILITY` intent).
- A **`DECLARED_REPLACEMENT`** with an explicit intent + strangler/parity plan
  (SP0000 D-0000-15 portal rule).
- Replacing a **mock provider** with a real, governed adapter at the SP0000
  Layer-8 effect boundary (that is new work, gated, not a rebuild).

## Mutation campaign (proves enforcement)

`tests/test_architecture_mutation.py` injects each forbidden pattern against a
synthetic repo/twin and asserts the exact finding fires: `CRM2` duplicate, a
`customer_platform` duplicating CRM, a second run ledger, route-ownership
conflict, table-ownership conflict, a historical migration edit, an outbound HTTP
primitive, a dynamic import in a protected layer, an expired waiver, an
undeclared package, and spec-code drift. All are recorded, none silently pass.
