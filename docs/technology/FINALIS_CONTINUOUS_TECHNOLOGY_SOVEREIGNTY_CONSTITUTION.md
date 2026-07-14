# FINALIS Continuous Technology Sovereignty Constitution (SP0004)

**Position:** after SP0000 (Architecture Lock), SP0001 (Architecture Immune
System), SP0002 (Semantic Operating Constitution), SP0003 (Program Dependency &
Uncertainty Constitution). **Runtime feature:** none. **Product behavior change:**
none. **DB migration added:** none (frontier remains v27).

This constitution makes technology sovereignty a **continuously evaluated
architecture quality**, not a one-time decision. It governs how technology enters
Finalis, stays constrained, is continuously re-evaluated, and may leave — so that
a temporary 2026 implementation choice never becomes permanent Finalis business
architecture.

## Governing principles

1. **Finalis owns the semantics and the capability contract.** Providers implement
   mechanisms; they do not own employee identity, memory, case ownership, skills,
   authority, evidence, outcomes or learning (INV-0004-01/02).
2. **Replaceability must be tested, not asserted.** An interface existing does not
   prove substitutability (INV-0004-10); replaceability is measured by evidence
   proportional to criticality.
3. **A technology decision is a living engineering hypothesis**, re-validated by
   continuous fitness functions (D-0004-01).
4. **No averaged safety.** A hard-requirement failure or a sovereignty violation
   (P0/P1) can never be offset by a good advisory score (§12.6, INV-0004-07).

## The five-layer separation (D-0004-21)

```
FINALIS BUSINESS / EMPLOYEE LOGIC
  → FINALIS SEMANTIC CONTRACT
  → FINALIS CAPABILITY CONTRACT
  → GOVERNANCE / AUTHORITY
  → PROVIDER ADAPTER  → CREDENTIAL REFERENCE → PROVIDER IMPLEMENTATION → EXTERNAL API
```

Provider IDs, error codes, workflow state, prompt formats, credentials and
provider-specific extensions must never silently become canonical Finalis
semantics (INV-0004-03/04/05/06/14).

## Capability contracts: core + namespaced extensions (D-0004-22)

Contracts are capability-specific (`ModelProvider`, `TelephonyProvider`, …), never
a universal `Provider.execute(anything)`. Each exposes stable CORE capabilities
plus NAMESPACED optional extensions that cannot redefine core semantics — avoiding
both provider-specific business architecture AND lowest-common-denominator
abstraction. Provider-extension dependence is visible in the technology dependency
graph, exit analysis and impact cone (D-0004-67).

## Lock-in is multi-dimensional (D-0004-14)

Ten dimensions tracked separately: protocol, data, state, semantic, operational,
commercial, skills, governance, identity, observability. An interface alone does
not prove sovereignty; open source does not automatically remove lock-in
(INV-0004-23; arxiv 2409.01118).

## Common-mode: multi-provider ≠ resilience (D-0004-17/18, §12.4)

Two providers are not independent if they share a critical upstream (cloud,
region, identity, gateway, upstream model, control plane). Apparent diversity is
classified `DIVERSITY_REAL` / `DIVERSITY_PARTIAL` / `DIVERSITY_COSMETIC`.

## Decision method (D-0004-05..11)

Hard feasibility first (UNKNOWN ≠ PASS) → Pareto frontier (before weighted
scoring) → sensitivity (ROBUST / SENSITIVE / UNSTABLE) → scenario / robust
analysis → minimax regret only where calibrated (else
`REGRET_ANALYSIS_NOT_CALIBRATED`). No fabricated numerical precision.

## Continuous fitness & lifecycle

TDRs are append-only (`PROPOSED → … → ACCEPTED → ACTIVE → REVIEW_DUE →
SUPERSEDED → RETIRED`; a change creates a superseding record). Decision status and
fitness status are distinct (`ACTIVE_AND_FIT / REVIEW_DUE / ACTIVE_DEGRADED /
INVALIDATED`). Fitness functions detect, report and may block architecture change
— they never grant runtime authority (INV-0004-22). Constitutional P0 fitness
(no raw secret, provider-ID never identity, critical exit plan) can never be
waived (§17.6).

## Exit readiness & substitution

Exit readiness is measured across eight evidence dimensions, never a bare
`replaceable=true`; a critical missing data export is a hard blocker (D-0004-40).
Substitution evidence is version-bound (provider/contract/corpus version +
`tested_at`) and decays when a material input changes (INV-0004-20). The shadow
substitution lab replays canonical workloads and can never cause an unauthorized
external effect (INV-0004-21); effectful duplicate dual-run is prohibited.

## Standards posture

MCP (pinned 2025-11-25 finalized; the 2026-07-28 RC is not adopted) and A2A (1.0)
are interoperability boundaries, never authority (INV-0004-15/16). OpenTelemetry
is the preferred vendor-neutral telemetry direction with a replaceable backend
(INV-0004-17). Supply-chain strategy targets SLSA v1.2 + CycloneDX (AI/ML-BOM) and
evaluates SPDX — with no compliance claim without implementation evidence
(D-0004-77). Proof-carrying decision and substitution envelopes are evidence, not
authority (INV-0004-24/25).

## Non-goals

SP0004 opens no real providers, executes no external effects, replaces no current
technology, and adds no migration. It governs the technology around the existing
product. A valid decision may be KEEP / ADOPT / TRIAL / ASSESS / DEFER /
REPLACE_LATER — premature implementation is never forced (D-0004-04).
