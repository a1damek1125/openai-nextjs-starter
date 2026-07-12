"""FINALIS SP0007 — Backward Compatibility, Migration, Versioning & Contract
Evolution Constitution.

Deterministic, standard-library-only, repository-local GOVERNANCE tooling. It
defines how Finalis contract surfaces (APIs, events, stored data, database
schemas, workflow histories, semantic epochs, provider contracts, proof
envelopes, CLIs) may safely evolve — without silently breaking consumers,
tenants, active work, historical evidence, replay, recovery, or rollback.

Constraints (INV-0007-46..49): performs NO live migration, changes NO product
runtime behavior, adds NO product database migration (frontier stays v27), and
is NEVER imported by product code (`finalis/`). Reference implementation only.

Core principles: compatibility is directional, consumer-specific and
multidimensional · a version number declares intent, evidence proves
compatibility · newer ≠ compatible · same schema ≠ same semantics · up
migration ≠ rollback · deprecated ≠ removed · replay passed ≠ all histories
safe · proof is evidence, not authority.
"""
