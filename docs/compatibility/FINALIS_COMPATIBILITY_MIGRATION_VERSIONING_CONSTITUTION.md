# FINALIS Backward Compatibility, Migration, Versioning & Contract Evolution Constitution (SP0007)

**Position:** after SP0000–SP0006 (Architecture Lock → Immune System → Semantics
→ Program Dependency → Technology Sovereignty → Safety Kernel → Governed Work).
**Runtime feature:** none. **Live migration:** none (D-0007-70). **Product
behavior change:** none. **DB migration added:** none (frontier v27).

This is the permanent Compatibility and Evolution Control System: how Finalis
safely evolves APIs, events, stored data, database schemas, workflow histories,
semantic epochs, provider contracts, proof envelopes and CLIs — without silently
breaking consumers, tenants, active Owned Work, historical evidence, replay,
recovery, idempotency, audit, rollback, or future migrations.

## Constitutional distinctions

> NEWER ≠ COMPATIBLE · SAME SCHEMA ≠ SAME SEMANTICS · SCHEMA-VALID ≠
> BEHAVIORALLY COMPATIBLE · SEMVER LABEL ≠ COMPATIBILITY PROOF · SUCCESSFUL
> DEPLOYMENT ≠ SUCCESSFUL MIGRATION · UP MIGRATION ≠ ROLLBACK · PRODUCER ≠
> CONSUMER COMPATIBILITY · REPLAY PASSED ≠ ALL HISTORIES SAFE · DEPRECATED ≠
> REMOVED · VERSION ADAPTER ≠ SEMANTIC AUTHORITY

## Central principles

1. **Compatibility is directional** (D-0007-01). `Compat(P1,C0)` may differ from
   `Compat(P0,C1)`. Never store a bare `compatible = true` — every claim binds
   producer, consumer, versions, direction, contract surface, scenario scope,
   evidence, validator, and date.
2. **Compatibility is consumer-specific** (D-0007-05) and **multidimensional**
   (D-0007-02): syntactic, structural, semantic, behavioral, temporal, state,
   replay, proof/hash, security, operational. A hard-dimension failure can never
   be averaged away; **UNKNOWN is never COMPATIBLE** (INV-0007-07/08).
3. **A version number declares intent; evidence proves compatibility**
   (D-0007-04). Contract, implementation, deployment, provider, protocol,
   semantic-epoch and validator versions stay distinct (D-0007-03).
4. **Released contract versions are immutable** (D-0007-06): any material change
   is a NEW version, sealed by a content hash.
5. **Semantic evolution uses SP0002** (D-0007-09): EQUIVALENT / NARROWING /
   WIDENING / INCOMPATIBLE / REVIEW_REQUIRED — never inferred from JSON shape.
6. **Migration is a governed state transition** with preconditions,
   postconditions, a declared **loss vector** (field/semantic/precision/history/
   provenance/authority/evidence/ordering/referential), and an explicit
   **rollback boundary** (D-0007-35..41). Critical losses (authority, evidence,
   provenance) are non-compensatory; observed loss must be ⊆ declared loss;
   **an up migration never proves rollback**; rollback after the Last Safe
   Rollback Point is blocked and remediation follows the forward-fix plan.
7. **Expand–Migrate–Contract is the default** (D-0007-42/43): old consumers keep
   operating during EXPAND; the CONTRACT phase is gated on migrated consumers,
   absent unknown critical consumers, a passed support window, historical
   readers, and rollback/forward-fix readiness. Dual-read differences are
   measured and reconciled; dual-write requires deterministic reconciliation;
   shadow readers/writers never create authoritative state; backfills are
   checkpointed, resumable and idempotent under a migration lease + barrier.
8. **Historical state, events, workflows and proofs remain interpretable** for
   as long as Finalis owes duties based on them (D-0007-29/34): a protected
   contract carries a historical corpus (common/edge/adversarial/rare-critical/
   incident classes); workflow changes replay protected histories (replay is
   bounded evidence, D-0007-32); old proof bytes are never silently
   reinterpreted under new rules.
9. **Deprecation is not removal** (D-0007-58): notice → replacement → support
   window → consumer acknowledgment → evidence-based Sunset Readiness Gate.
   Unknown critical consumers block removal; waivers expire.
10. **No breaking change hides** inside a patch release, a default-value change,
    a feature flag, a provider adapter, a schema-compatible payload, or an
    automatically selected latest version. Protected contracts never float to
    `latest`; negotiation is deterministic and fail-closed; security downgrade
    is blocked; adapters are directional, declare losses, and cannot redefine
    core semantics (D-0007-24..28).
11. **Proof-carrying evolution** (§10.12/10.13): compatibility, migration,
    rollback and deprecation proof envelopes are deterministic and are
    **evidence, never authority** (INV-0007-46).

## Architecture

```
CURRENT CONTRACT SURFACES → CONTRACT DESCRIPTORS → PRODUCER–CONSUMER GRAPH
→ COMPATIBILITY TWIN → CONTRACT DIFFERENCE ENGINE → HISTORICAL CORPUS
→ SEMANTIC BRIDGE (SP0002) → DIRECTIONAL COMPATIBILITY CLAIMS
→ COMPATIBILITY CHANGE INTENT → MIGRATION GRAPH
→ EXPAND – MIGRATE – VERIFY – CONTRACT → ROLLBACK / FORWARD-FIX BOUNDARY
→ DEPRECATION AND SUNSET → PROOF-CARRYING EVOLUTION
```

The **Compatibility Twin** (contract identities, versions, producers, consumers,
directional claims, evidence, migration edges, deprecations, support windows,
fixtures, proofs) is distinct from the Architecture/Semantic/Program/Technology/
Safety/Governed-Work twins. The **Compatibility Firewall** keeps external
provider-version semantics out of the core (D-0007-27).

## Repository contract surfaces (grounded by SWARM-A archaeology)

The real surfaces this constitution protects: **405 HTTP routes** (FastAPI,
dict-shaped bodies — no pydantic; the least-governed surface, recorded as
compatibility debt), **3 hash-protected event families** (case audit chain,
run-ledger canonical envelope `finalis-run-event-v1`, EMP-A1 idempotent intake),
**27 forward-only DB migrations** (no down migrations exist — rollback claims
for schema are constitutionally UNKNOWN until inverses are built and verified),
**4 replay-protected state machines** (17-state Case FSM, 24-state lifecycle
kernel, 12-status run ledger, 23-state EMP-A1 inbox), **~371 version-pinned
proof-envelope identifiers** (`finalis-<surface>-v<N>`), 6 governance CLIs, and
11 provider Protocol seams. Two canonicalization dialects exist (strict
`separators=(",",":")` vs `finalis/audit.py`'s `default=str`) — recorded as
REVIEW_REQUIRED compatibility debt, not changed at runtime.

## Boundary

Governance tooling only (`tools/compatibility/` + `docs/compatibility/`):
performs no live migration, changes no product behavior, adds no DB migration,
is never imported by product code, and creates no parallel authority. See
`FINALIS_RESEARCH_REGISTER.md` for the standards register and
`SP0007_ROADMAP_IDENTITY_REPORT.md` for the preflight.
