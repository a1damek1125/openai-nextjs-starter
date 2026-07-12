# FINALIS SP0007 — Research Register (Compatibility Constitution)

External specifications describe bounded contract surfaces; they **never**
become Finalis semantic authority (D-0007-68). All statuses recorded at
execution (2026-07-12) and must be re-verified on any future execution day.
Swarm roles: SWARM-K (standards), SWARM-L (Viktor/competitor reference).

## 1. Semantic Versioning — declaration, not proof (D-0007-04)
- https://semver.org/ · https://github.com/semver/semver
- SemVer communicates INTENDED compatibility of a declared public API. It does
  not mechanically prove behavioral, semantic, state, replay, security, or
  migration-reversibility compatibility. SP0007 checks the declaration against
  classified evidence (`SEMVER_MISMATCH` when a breaking change hides in a
  non-major release).

## 2. OpenAPI — external contract format
- https://spec.openapis.org/oas/latest.html · https://spec.openapis.org/oas/v3.2.0.html
- https://github.com/OAI/OpenAPI-Specification · https://learn.openapis.org/
- Latest published at authoring: 3.2.0 (re-verify on execution day). Candidate
  representation only; Finalis HTTP contracts today are dict-shaped (no OpenAPI
  export exists) — recorded as compatibility debt.

## 3. AsyncAPI — event-contract representation candidate
- https://www.asyncapi.com/docs/reference/specification/latest ·
  https://www.asyncapi.com/docs/reference/specification/v3.1.0 ·
  https://github.com/asyncapi/spec — not Finalis event semantics.

## 4. CloudEvents — interoperable envelopes only
- https://cloudevents.io/ · https://github.com/cloudevents/spec ·
  https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md
- Defines no business meaning, ordering, idempotency, authority, or outcome
  semantics.

## 5. JSON Schema — structural validity ≠ compatibility (D-0007-12)
- https://json-schema.org/specification · https://json-schema.org/draft/2020-12 ·
  https://github.com/json-schema-org/json-schema-spec

## 6. Protocol Buffers — adopted principles (D-0007-16/17)
- https://protobuf.dev/programming-guides/proto3/ · #updating · #unknowns ·
  https://protobuf.dev/editions/overview/ ·
  https://protobuf.dev/support/cross-version-runtime-guarantee/
- **Adopted:** never reuse field numbers; reserve removed identifiers; preserve
  unknown fields when round-trip preservation is required; wire-safe ≠
  behaviorally safe. These shaped the Reserved-Identifier Registry and
  Unknown-Field Policy.

## 7. Apache Avro — schema-resolution reference (SP0004-gated dependency)
- https://avro.apache.org/docs/current/specification/ · #schema-resolution ·
  https://github.com/apache/avro

## 8. Temporal — workflow-versioning principles (technology stays SP0004-gated)
- https://docs.temporal.io/develop/python/workflows/versioning ·
  https://docs.temporal.io/workflows · https://docs.temporal.io/encyclopedia/event-history ·
  https://docs.temporal.io/develop/python/testing-suite#replay
- **Adopted:** workflow code changes may break historical replay; protected
  histories require replay testing; deployment success ≠ history compatibility.
  These shaped the Workflow Replay Harness (D-0007-31/32).

## 9. Kubernetes API deprecation policy
- https://kubernetes.io/docs/reference/using-api/deprecation-policy/ ·
  https://kubernetes.io/docs/reference/using-api/
- **Adopted patterns:** versioned groups, no silent removal within a version,
  stability-specific support rules, round-trip expectations, explicit
  deprecation periods → Deprecation Registry + Support Windows.

## 10. GitHub REST API versioning
- https://docs.github.com/en/rest/about-the-rest-api/api-versions ·
  https://docs.github.com/en/rest/meta/meta
- **Adopted:** explicit version header, supported-version registry, scheduled
  support termination, explicit unsupported-version behavior (fail-closed
  negotiation).

## 11. Stripe API versioning
- https://docs.stripe.com/api/versioning · /upgrades · /changelog ·
  /webhooks/versioning
- **Adopted:** per-request/per-endpoint version pinning, backward-compatible
  regular releases, explicitly tested major upgrades → Version Pinning Contract
  (protected contracts never float to latest, D-0007-24).

## 12. Consumer-driven contracts (Pact — principles only, no dependency)
- https://docs.pact.io/ · https://docs.pact.io/getting_started/how_pact_works ·
  https://github.com/pact-foundation · https://github.com/pact-foundation/pact-specification
- **Adopted:** consumer expectations as first-class evidence (D-0007-53). Pact
  itself is NOT introduced (SP0004 gate).

## 13. Expand–Migrate–Contract / Parallel Change
- https://martinfowler.com/bliki/ParallelChange.html
- Base pattern adopted and EXTENDED with migration leases, checkpointing, replay
  testing, outcome safety, proof preservation, rollback boundaries, long-running
  work compatibility, and authority/tenant invariants (D-0007-42..52).

## 14. PostgreSQL migration behavior (future INFRA-1 reference)
- https://www.postgresql.org/docs/current/sql-altertable.html · /ddl-alter.html ·
  /explicit-locking.html
- Migration plans must model real lock/scan/rewrite behavior; not every ALTER is
  online-safe. Recorded in Migration Edge `lock_profile`/`downtime_class`.

## 15. OpenTelemetry schema evolution
- https://opentelemetry.io/docs/specs/semconv/ · /semconv/general/schema/ ·
  /otel/schemas/ — telemetry schemas evolve with versions; telemetry remains
  evidence, not business authority.

## 16. 2026 research (research, not standards)
- https://arxiv.org/abs/2603.06029 · https://arxiv.org/abs/2605.14312 ·
  https://arxiv.org/abs/2601.12735
- Conclusions used: specifications and implementations diverge; differential
  testing reveals behavioral inconsistency; syntactically valid API descriptions
  may be semantically incomplete; LLM-generated contracts require deterministic
  verification → Differential Implementation Testing (D-0007-55).

## 17. Viktor product reference (vendor guidance; SWARM-L)
- https://viktor.com/ · /product · /integrations · /security · /changelog ·
  https://viktor.com/blog/how-to-roll-out-an-ai-employee-to-your-whole-team
- Product-continuity lessons only: integrations stay stable for ordinary users;
  provider changes must not force work redesign; gradual rollout; clear
  communication of externally visible change. No undocumented internals inferred.

## Classification discipline

Every source above is tagged OFFICIAL STANDARD / OFFICIAL DOCUMENTATION /
RESEARCH / VENDOR CLAIM as appropriate. None grants internal authority; the
canonical compatibility semantics are defined solely by this constitution and
its deterministic repository-local tooling.
