# FINALIS Governed Work, Delegated Autonomy & Outcome Accountability Constitution (SP0006)

**Position:** after SP0000 (Architecture Lock), SP0001 (Architecture Immune
System), SP0002 (Semantic Operating Constitution), SP0003 (Program Dependency &
Uncertainty Constitution), SP0004 (Technology Sovereignty Constitution), SP0005
(Safety Kernel, Assurance & Regulatory Truth Constitution).
**Runtime feature:** none. **External effects opened:** none (INV-0006-47).
**Product behavior change:** none. **DB migration added:** none (frontier v27).

This constitution defines the missing boundary between a **human request** and
**governed, delegated, budgeted, approved, verified work** — so that one message
can start useful work without any message, memory, provider, or agent becoming an
independent source of authority.

> REQUEST ≠ WORK ORDER ≠ PLAN ≠ AUTHORITY ≠ EXECUTION ≠ OUTCOME ≠ VERIFIED COMPLETION

## Central principles

1. **Intent is an untrusted proposal** (D-0006-01). A message, document, model
   interpretation, memory, or external event may create CANDIDATE_INTENT — never
   authority, approval, legal basis, consent, or a capability lease.
2. **Goal validity does not authorize action** (D-0006-05). `GoalValid(W)` ⇏
   `ActionAuthorized(a)`.
3. **Plan is not authority** (D-0006-06). A valid SP0003 plan grants no capability
   or approval.
4. **Context is not consent; memory cannot create authority** (INV-0006-04/05/06).
5. **Delegation distributes work, not authority or accountability.** Child
   authority ⊆ parent authority (D-0006-15); the accountable owner is conserved
   (D-0006-21).
6. **Capability rights are contextual, expiring, revocable leases** (D-0006-18) —
   no ambient permanent agent capability exists.
7. **Approval binds the exact material action and context** (D-0006-32); a
   material change invalidates it (D-0006-33); no self-approval (D-0006-36).
8. **Artifact ≠ outcome; claimed ≠ verified; partial ≠ complete** (D-0006-11,
   INV-0006-37/38/39). Evidence from the world outranks agent self-report.
9. **A safety score never overrides a hard invariant; UNKNOWN is not low**
   (INV-0006-20/21/22).
10. **Proof is evidence, not authority** (D-0006-62). Envelopes cannot grant
    future capability.
11. **External authorization standards are projections, not internal semantics**
    (D-0006-63, INV-0006-45).

## Two identities (D-0006-02)

A `semantic_work_hash` covers the canonical MEANING of the work (epoch, goal,
scope, constraints, outcome contract, purpose, capability ceiling, risk
requirements — excluding execution identity and timestamps). A separate
`work_instance_hash` covers the execution instance (work_order_id, tenant,
requester, owner, source, recurrence instance, issue/expiry + the semantic hash).
Two semantically equivalent jobs share the semantic identity yet remain distinct
execution instances.

## Constitutional flow (§9.1)

```
SOURCE MESSAGE/EVENT → CANDIDATE INTENT (untrusted) → WORK ORDER COMPILER
→ AMBIGUITY/CONFLICT ANALYSIS → WORK ADMISSION GATE → CANONICAL GOVERNED WORK ORDER
→ SP0003 CANDIDATE PLAN → PATH/BUDGET/SAFETY VALIDATION → DELEGATION GRAPH
→ ATTENUATED CAPABILITY LEASES → APPROVAL TOPOLOGY → CONTROLLED EXECUTION
→ ARTIFACT/EFFECT → OUTCOME EVIDENCE → INDEPENDENT VERIFICATION
→ VERIFIED COMPLETION → PROOF + ACCOUNTABILITY
```

## Admission (§11.1, D-0006-04)

`Admitted(W)` is the **conjunction** of identity, tenant, canonical goal, scope,
constraint-consistency, outcome-contract, capability-ceiling, budget, purpose,
approval-topology, dependency, technology, safety, and no-authority-from-context
predicates. Admission is **fail-closed**: a critical UNKNOWN can never become
PASS. Outputs: `ADMITTED` / `AMBIGUOUS` / `CONFLICTED` / `REJECTED` /
`REQUIRES_CLARIFICATION`.

## Delegation & capability leases (§9.5/9.6, D-0006-13..20)

The authority-bearing delegation graph is a **DAG**; depth and fan-out are
bounded. For every child: `A_child ⊆ A_parent ∩ A_W ∩ A_policy ∩ A_tenant`. A
child lease is a **structural attenuation** of its parent — operations/targets/
data/effects are subsets, risk/cost ceilings ≤, expiry ≤, use-count ≤ — with a
stored attenuation proof. Leases are context-bound and revocable; revoking a
parent invalidates all descendants unless an independent root exists; revocation
staleness is bounded and modeled (not a production distributed system).

## Budgets & risk (§9.7, D-0006-23..31)

Budget is multidimensional (financial, model/token, tool-call, external-effect,
data-access, risk, deadline, resource capacity). Reservations precede
consumption; `Consumed_b + Reserved_b ≤ Total_b`; `Σ Allocation_b(child_i) ≤
Available_b(parent)`. Time is not naively additive across parallel work. Risk is
a **vector** with a **non-compensatory control floor** `⊔_i g_i(r_i)`; hard
prohibitions dominate. Expected loss / CVaR are used only when calibrated, else
`QUANTITATIVE_RISK_NOT_CALIBRATED`. Correlation is never assumed independent.

## Approval topology (§9.8, D-0006-32..38)

Approval is a context-bound token binding work-instance hash, action/target
fingerprint, material parameters, effect class, risk snapshot, approver, class,
times, and uses. A conservative approval **floor** `⊔(Effect, Risk,
Irreversibility, Data, Authority, Regulatory, Tenant)` selects a class from the
lattice A0<A1<A2<A3<A4<A5; a lower class cannot satisfy a higher floor. Material
change → revalidation. No single execution identity may be sole proposer +
executor + approver + verifier where independence is required. SP0006 approval
tokens and leases **interoperate with**, and never replace, SP0005 safety
admission (D-0006-39).

## Path & goal integrity (§9.9, D-0006-42..48)

Hard goal-drift predicates (tenant/purpose/target/forbidden-scope/capability-
ceiling/outcome-redefinition/hard-constraint-removal/approval-context) block
immediately regardless of any soft score; a soft weighted drift metric is
advisory and versioned. Every access and action must be **purpose-bound**; hidden
work (a side task not in the admitted plan/approved replan) is forbidden. Prefer
the least-authority path and offer least-irreversible safe alternatives.

## Recurrence, cancellation, outcome (§9.10..9.12, D-0006-50..61)

A recurring **contract** is distinct from each recurring **instance**; there is
no permanent recurring authorization — every run reauthorizes. **Cancellation is
a barrier protocol** (block new actions → identify in-flight → revoke leases →
invalidate approvals → reconcile UNKNOWN outcomes → record irreversible effects →
CANCELLED); it cannot erase completed effects. **Quarantine cannot self-release.**
`UNKNOWN_OUTCOME` is first-class and never treated as failure; blind retry of a
non-idempotent effect is prohibited. Outcomes have a lifecycle (CLAIMED →
EVIDENCED → VERIFYING → VERIFIED / PARTIALLY_VERIFIED / DISPUTED / INVALIDATED);
critical outcomes require a deterministic or independent qualified verifier;
defeaters can reopen a completed work order via a linked successor while the
original completion record stays immutable.

## Formal verification (§9.14, D-0006-65)

A standard-library bounded state-space explorer checks state-machine safety,
authority monotonicity, lease attenuation, budget conservation, no-self-approval,
and cancellation on small finite models — enumerating reachable states, returning
counterexample paths, and reporting truncation honestly (never claiming a
truncated search as proof).

See `FINALIS_FORMAL_INVARIANTS.md` for the 48 invariants and the model-checked
properties, and `SP0006_ROADMAP_IDENTITY_REPORT.md` for the authorized SP0006
reassignment (Evaluation charter → SP0011).

## Boundary

Governance tooling only, under `tools/governed_work/` + `docs/governed_work/`.
It changes no product runtime behavior, opens no external effects, adds no
product database migration (frontier stays v27), and is never imported by product
code (`finalis/`). It **references** — and never rebuilds — Owned Work / EMP-A1
R-FSAFEQ admission, the TOOL-B9.2 Governed Work Lineage Observatory, the authority
/approval/RBAC/tenant fabric, the TOOL-B9 write-path family, the run ledger,
evidence chain-of-custody, and CRM consent.
