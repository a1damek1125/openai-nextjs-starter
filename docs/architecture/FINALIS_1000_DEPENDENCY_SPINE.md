# FINALIS 1000 — DEPENDENCY SPINE

**SP0000 · docs-only.** Baseline: HEAD `5c30c60`, migration v27, runtime frontier EMP-A1.

This spine locks the **order** in which the Finalis 1000 layers may be built and the SP-block dependency graph. It is **acyclic at the block level**, references no undefined SP, and is consistent with the canonical SP0000+ program. SP0000 builds none of it.

## Hard sequencing rule

> Real external effects (Layer 8) may begin **only after** the Employee Operating Kernel, Knowledge/Memory, Certified/Adaptive/Outcome layers and Controlled Learning + Communication Cortex exist and pass their gates (D-0000-16, INV-0000-10). No shortcut opens a real provider "right after SP0000".

```
L0 EXISTING FOUNDATION (done)
        │
        ▼
L1 EMPLOYEE OPERATING KERNEL  ── owns Zero-Lost-Work, durable run state
        │
        ▼
L2 KNOWLEDGE & MEMORY  ── claims/facts/temporal validity/supersession
        │
        ▼
L3 CERTIFIED INTELLIGENCE (LGGT+)  ─┐
        │                            │  (L3 & L4 may proceed in parallel once L2 stable)
L4 ADAPTIVE COGNITION  ─────────────┘
        │
        ▼
L5 OUTCOME INTELLIGENCE  ── activity≠effect≠outcome≠completion
        │
        ▼
L6 CONTINUOUS EXPERIENCE INTELLIGENCE  ── gated learning
        │
        ▼
L7 COMMUNICATION CORTEX  ── channels as tools, one truth
        │
        ▼
L8 REAL-WORLD EFFECT BOUNDARY  ── FIRST real effect; passes governance   ⟵ GATE
        │
        ▼
L9 ROLE / VERTICAL COMPOSITION  ── packs, not core forks
        │
        ▼
L10 PRODUCTION PLATFORM  ── PostgreSQL/observability/scale (may harden in parallel from L1 as non-authoritative substrate)
```

## SP0000+ program blocks (architecture-program prerequisites)

SP0000 unlocks the **architecture-program** SP0001–SP0010 (rules-first), NOT implementation:

| SP | Name | Depends on | Unlocks |
|---|---|---|---|
| SP0000 | Master Architecture Lock (this) | AUDIT-TRACE-1 | SP0001–SP0010 |
| SP0001 | Baseline & Do-Not-Rebuild Enforcement | SP0000 | SP0002 |
| SP0002 | Canonical Terminology & Domain Contract | SP0001 | SP0003 |
| SP0003 | Dependency Graph & Critical Path Lock | SP0002 | SP0004 |
| SP0004 | Technology Decision Records (durable engine, DB, frontend…) | SP0003 | impl SPs |
| SP0005 | Threat/Safety/Regulatory & High-Risk Domain Taxonomy | SP0003 | L8 gate |
| SP0006 | Governed Work, Delegated Autonomy & Outcome Accountability Constitution | SP0003 | impl SPs |
| SP0007 | Compatibility, Migration & Versioning Policy | SP0003 | all impl |
| SP0008 | API / UI / Data Contract Inventory | SP0002 | L1, portal |
| SP0009 | Release Train & Definition of Done | SP0004,05,07,08,**11** | all impl |
| SP0010 | Global Brand Naming Sprint | SP0000 | product identity |
| SP0011 | Finalis 1000 Evaluation Charter (reassigned from SP0006) | SP0003 | L6 gate |

## Implementation-block references (named, not scheduled here)

These future implementation SPs are referenced by the invariants/state-machine/formal sections and must exist downstream (exact numbering fixed by SP0003):

- **SP0012** — Authoritative Employee State Machine (transition system).
- **SP0014** — Event Architecture (classes, idempotency, ordering, replay).
- **SP0015** — Zero-Lost-Work formalization + enforcement.
- **SP0021** — Direct audit of the current LGGT source before LGGT+ implementation.

## Layer → owning future-SP mapping (AC-22)

Each required layer maps to a future implementation-SP area. Exact SP *numbers* for the L1–L10 implementation blocks are locked by **SP0003** (Dependency Graph & Critical Path Lock); this table locks the *ownership* so no layer is orphaned.

| Layer | Owning future work | Governing invariant already locked |
|---|---|---|
| L0 Existing foundation | — (exists; DO-NOT-REBUILD) | INV-0000-01 |
| L1 Employee Operating Kernel | impl block after SP0004; Zero-Lost-Work = **SP0015**; state machine = **SP0012**; events = **SP0014** | INV-0000-06, D-0000-04 |
| L2 Knowledge & Memory | impl block; terminology = SP0002 | INV-0000-13 (tenant scope) |
| L3 Certified Intelligence (LGGT+) | LGGT source audit = **SP0021** → impl block | INV-0000-04, D-0000-10 |
| L4 Adaptive Cognition | impl block; model-router TDR = SP0004 | INV-0000-02, INV-0000-06 |
| L5 Outcome Intelligence | impl block | INV-0000-11 |
| L6 Continuous Experience Intelligence | eval charter = **SP0011** → impl block | INV-0000-08, INV-0000-13 |
| L7 Communication Cortex | impl block | INV-0000-07 |
| L8 Real-World Effect Boundary | threat/regulatory taxonomy = **SP0005**; adapter TDRs = SP0004 → impl block (roadmap TOOL-B10) | INV-0000-10, INV-0000-14 |
| L9 Role/Vertical Composition | impl block; contract inventory = SP0008 | D-0000-14 |
| L10 Production Platform | datastore/observability TDRs = **SP0004**; release train = SP0009 | INV-0000-09 |

No layer lacks an owner; no owner references an undefined SP; impl-SP numbering is the single deferred item, explicitly assigned to SP0003.

## Acyclicity note

Every edge points from a prerequisite to a dependent; there is no back edge. L10 (production platform) may *begin* hardening in parallel with L1 because it is a **non-authoritative substrate** — but it may not gate business authority, and authority/tenant isolation contracts it must honor come from L0. No block depends on an undefined SP; no block requires a later block.
