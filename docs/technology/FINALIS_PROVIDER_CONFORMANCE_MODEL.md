# FINALIS Provider Conformance Model (SP0004 D-0004-24..37)

## Golden Canonical Workload Corpus
Provider-neutral workloads describing Finalis **intent** (canonical input +
required contract properties), never provider-native requests (D-0004-33).
Effectful workloads default to `NO_EXTERNAL_EFFECT` (AC-0004-065). The corpus
belongs to Finalis and is versioned (`corpus_version`).

## Deterministic Reference Provider
Each critical contract has a stdlib-only `DeterministicReferenceProvider`
(`tools/technology/conformance.py`) producing identical output for identical
canonical input, with named fault injection (`UNKNOWN_OUTCOME`, `TIMEOUT`, …). It
enables offline conformance, replay and failure testing (D-0004-31).

## Conformance harness (§11.8)
`run_conformance(provider, corpus)` validates schemas, runs the corpus, checks
required properties and error translation, and returns `PASS` / `FAIL` /
`UNSUPPORTED_CAPABILITY`.

## Differential & substitutability (§11.9/§11.10)
`differential(A, B, corpus)` compares two providers on outcome class and contract
compliance (never byte-identical nondeterministic output). Substitutability is
NOT Boolean: `CONTRACT_EQUIVALENT` / `FUNCTIONALLY_ACCEPTABLE` /
`PARTIALLY_SUBSTITUTABLE` / `NON_EQUIVALENT` / `UNKNOWN`, per capability.

## Shadow substitution (D-0004-36/37)
The lab replays canonical requests against a candidate or fake and **refuses any
effectful workload not in `NO_EXTERNAL_EFFECT` mode** (INV-0004-21). Effectful
duplicate dual-run (real email/call/payment) is prohibited — simulation / shadow /
record-replay only.

## Substitution drills (D-0004-41)
Drill levels D0 (docs) → D5 (controlled migration rehearsal); the minimum required
level scales with criticality (T3 → D3, T4 → D4). Substitution evidence is
version-bound and decays (INV-0004-20).
