# FINALIS Safety Kernel, Assurance & Regulatory Truth Constitution (SP0005)

**Position:** after SP0000 (Architecture Lock), SP0001 (Architecture Immune
System), SP0002 (Semantic Operating Constitution), SP0003 (Program Dependency &
Uncertainty Constitution), SP0004 (Continuous Technology Sovereignty Constitution).
**Runtime feature:** none. **External effects opened:** none (INV-0005-27).
**Product behavior change:** none. **DB migration added:** none (frontier v27).

This is the permanent safety constitution — established **before** real effect
authority exists, so safety is not retrofitted at the most dangerous boundary.

## Central principles

1. **The model is not the hard safety boundary** (INV-0005-01). For hard-boundary
   analysis the reasoning model is an UNTRUSTED PROPOSER that may propose any
   syntactically valid action; the effect-mediating layer must still reject
   actions outside the permitted boundary.
2. **Safety admission is context-bound and time-bound** (D-0005-13). A prior
   approval cannot authorize a materially changed context — the Time-of-Check /
   Time-of-Use gap is closed by immediate pre-effect revalidation.
3. **A safe action can participate in an unsafe trajectory** (INV-0005-03). Local
   action safety ≠ global trajectory safety.
4. **Evidence from the world outranks agent self-report** (INV-0005-11).
5. **A safety score can never override a hard safety invariant** (INV-0005-10);
   UNKNOWN is never LOW (INV-0005-09); a prohibited action is never allowed by
   optimization.
6. **Compliance is not safety**, and a draft/political announcement is not binding
   law (INV-0005-18/19/20).

## Threat ≠ Hazard ≠ Loss ≠ Risk (INV-0005-02)

A LOSS is the harm prevented; a HAZARD is a system state that can lead to it; a
THREAT is an adversarial/failure source; RISK combines likelihood and severity.
External taxonomies (OWASP ASI, MITRE ATLAS, NIST) are mapped as threat INPUTS,
never adopted as the Finalis hazard model.

## Design-time hazard engineering (STPA)

Losses → hazards → control structure → **unsafe control actions** (four STPA
categories: not-provided-when-required, provided-when-unsafe, wrong-timing/order,
stopped-too-soon/applied-too-long) → causal scenarios → safety constraints. Every
critical hazard must close: loss + constraint + (control OR explicit hard block) +
test/evidence/claim linkage, else `UNCONTROLLED_CRITICAL_HAZARD` (INV-0005-14).

## Context-bound admission & TOCTOU

A **Safety Admission Lease** binds an action fingerprint, tenant, actor, target,
authority snapshot, safety context and trajectory state, with an expiry.
Immediately before any future effect the material context is recomputed and
compared to the lease; a changed target/recipient/amount/authority/tenant/consent/
policy/epoch, or expiry, means the lease cannot authorize the effect
(`SAFETY_TOCTOU_MISMATCH`). A lease is non-transferable across action/target/tenant
(INV-0005-04..08) and is **evidence, not authority by itself** (D-0005-84).

## Non-compensatory control lattice

The safety state is a ten-dimension vector (never prematurely scalarized). Each
dimension maps to a minimum control class; the overall class is the JOIN (max) — a
severe dimension cannot be averaged away (D-0005-19). Risk monotonicity holds; a
hard prohibition dominates all optimization; expected loss and tail risk are
advisory and computed only where calibrated.

## Independent containment

For boundary-enforceable hard properties, the effect-mediating layer enforces the
property **independently of model cooperation** (INV-0005-01); a containment proof
applies only to its modeled scope (never universal AI safety, D-0005-32); emergency
containment must be enforceable outside the acting model (D-0005-33).

## Control independence & assurance

Two controls sharing a failure domain (model / provider / prompt / policy engine /
data / human / code path) are not automatically independent (INV-0005-12); no naive
probability multiplication. Assurance claims require claim + argument + evidence +
context + assumption + defeater + residual uncertainty; a claim cannot be
`SUPPORTED_CURRENT` while a blocking critical defeater is open (INV-0005-15) or its
critical evidence is stale (INV-0005-16).

## Regulatory temporal truth

A regulatory matter has MANY dates and a legal state SEPARATE from its timeline
state. As verified 2026-07-11: the EU AI Act is `BINDING_LAW` (high-risk
stand-alone applies 2026-08-02); the **Digital Omnibus** deferral is
`ADOPTED_NOT_YET_APPLICABLE` (political agreement ≠ enacted law — until OJ
publication the binding high-risk date remains 2026-08-02); the high-risk
classification guidelines are `DRAFT_OFFICIAL_GUIDANCE` with consultation open to
2026-07-23; prohibited-practice and AI-system-definition guidelines are
`FINAL_OFFICIAL_GUIDANCE`; NIST frameworks are `RESEARCH`; OWASP/ATLAS are
`VENDOR_GUIDANCE`; ISO standards are `INTERNATIONAL_STANDARD` (no certification
claim). Internal `FINALIS_IMPACT_0..5` classes never auto-map to legal high-risk
(INV-0005-17); ambiguity returns `UNCERTAIN_REQUIRES_QUALIFIED_REVIEW`.

## Executable safety & oracle hierarchy

Critical requirements become deterministic validators / property tests / automata
where mechanically expressible. Every executable safety scenario carries a
verification predicate grounded in observable evidence; agent self-report is never
the sole oracle for a hard property. Safety traceability relies on observable
decisions, not private chain-of-thought.

## Non-goals

SP0005 opens no external effects, implements no runtime Safety Kernel, no real
emergency kill switch, no production regulatory monitor, no legal advice; it makes
no compliance or ISO-certification claim and no universal formal-safety claim. It
adds hazard semantics, trajectory safety, admission contracts, assurance and
regulatory temporal truth AROUND the existing controls (CORE-A/TOOL-B/EMP-A, RBAC,
tenant isolation, approvals, Evidence Trust Fabric, recovery), which it maps —
never rebuilds.
