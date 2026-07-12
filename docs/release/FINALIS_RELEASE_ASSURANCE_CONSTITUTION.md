# FINALIS Release Assurance, Quality Gates, Definition of Done & Proof-Carrying Promotion Constitution

**Mission:** SP0009 — Release Train, Quality Gates and Definition of Done
**Kind:** Constitution + deterministic, repository-local release-assurance kernel
**Kernel location:** `tools/release/`
**Materialized twin:** `docs/release/FINALIS_RELEASE_TWIN.json`
**Status of the reference candidate RC-SP0009:** `READY_FOR_LATER_PROMOTION` (qualifiable, P0=0 / P1=0 / P2=1)

---

## 0. What this document is, and what it is not

This is the constitution for how a change earns the right to advance to the **next
non-production lifecycle state** in the FINALIS program. It defines a deterministic
control system that decides whether a change is sufficiently *defined*, *verified*,
*evidenced*, and *protected* to advance — and it records that decision as a
proof-carrying, revocable artifact.

It is a **governance-tooling kernel only**. To state the boundary honestly and
up front:

- **Zero live deployment.** Nothing here deploys anything.
- **Zero product migration.** The product frontier stays at v27; SP0009 moves no
  version.
- **Zero production credentials.** No secret value is read, stored, or emitted.
- **Zero external effect.** Every command produces canonical JSON and nothing else.
- **No SP0011 evaluation evidence.** Where an evaluation score would live, SP0009
  records only a `PENDING_SP0011` placeholder. It cannot and does not fabricate
  evaluation evidence.
- **Never imported by product code** (`INV-0009-66/67`). The kernel is inert with
  respect to the running product.

Every strong-sounding claim below is bounded by that reality. Where the kernel
honestly reports `UNKNOWN`, an absence, or `BLOCKED_PENDING_SP0011`, this document
says so in the same words.

---

## 1. The constitutional distinctions

The kernel exists because a set of everyday equivalences are false. Each false
equivalence is a place where unearned confidence leaks into a release. The
constitution names them and refuses each one structurally.

### 1.1 CODE MERGED ≠ DONE
A merged pull request means code is on a branch. It does not mean the obligations
that the change *incurred* are closed. Done is defined by the obligation
hypergraph (§4), not by merge. `merge != done` is enforced: an obligation can be
open on a fully merged change.

### 1.2 DONE ≠ RELEASE QUALIFIED
All obligations closed (Definition of Done met) is necessary but not sufficient.
Qualification is a separate, stricter conjunction (§13): every required hard gate
passes, every non-waivable obligation is closed, artifact closure is complete,
there is no open blocking defeater, and hard-scope unknowns are zero.

### 1.3 RELEASE QUALIFIED ≠ DEPLOYMENT AUTHORIZED
Qualification says a candidate *may* advance to the next assurance state. It grants
**no deployment authority**. The release proof envelope (§15) is explicitly
`non_authoritative: true` and creates no path to production. Deployment
authorization is out of scope for SP0009 and is never implied.

### 1.4 SIGNED ≠ TRUSTED
A valid signature proves a key produced a byte string. It does not prove the key
was *authorized* at signing time under a current, unrevoked, unexpired trust root
meeting threshold and domain-diversity requirements. Trust governance (§9) treats
"signed" as an input to a trust decision, never as the decision.

### 1.5 ATTESTED ≠ TRUE
An attestation is a signed claim. Its predicate may be unknown, its subject may not
match the artifact in hand, and its transparency receipt may be unverified. The
kernel records transparency receipts with an explicit `status: UNVERIFIED` where
inclusion has not been checked (§10). Attestation is evidence, not truth.

### 1.6 SBOM EXISTS ≠ SBOM COMPLETE
An SBOM file is not a complete SBOM. Completeness is a five-state property
(`COMPLETE`, `INCOMPLETE`, `INCOMPLETE_FIRST_PARTY`, `INCOMPLETE_THIRD_PARTY`,
`UNKNOWN`). The reference candidate's SBOM is honestly `INCOMPLETE_THIRD_PARTY` and
that fact is recorded as a P2 finding — an incomplete SBOM never masquerades as
complete (§11).

### 1.7 REPRODUCED ONCE ≠ REPRODUCIBLY BUILT
One successful reproduction is evidence, not a standing property (`D-0009-65`). The
reproducibility record for RC-SP0009 says `byte_equal: true` for the observed
inputs and explicitly notes that this is one reproduction, not a claim that the
build is reproducible for all time (§8).

### 1.8 SAME MODEL NAME ≠ SAME MODEL BEHAVIOR
A provider can change behavior behind a stable model name. AI release closure (§12)
binds a composite AI identity — name, version, deployment, fallback order, prompts,
tools, policy pack — and includes an opaque-provider-update detector. Same name is
never assumed to mean same behavior.

### 1.9 RETRY PASSED ≠ FAILURE DISAPPEARED
A passing rerun does not erase a prior failure (`D-0009-18/19`). The execution
ledger is append-only; the original FAIL stays recorded. A later PASS is a new row,
not a correction. Rerun-laundering — replacing a failure with a rerun to fabricate a
green history — is detectable and refused (§5).

### 1.10 CANARY PASSED ONCE ≠ ANYTIME-VALID
A single canary reading is a peek at a sequential process. Valid inference under
optional stopping requires an anytime-valid procedure (an e-process), pre-declared.
Progressive delivery contracts (§14) are **defined, not executed**, and carry a
pre-declared sequential policy so that no single favorable peek is mistaken for a
standing verdict.

---

## 2. The candidate genome and immutability

A **Candidate** is the unit of release reasoning. Its identity is a **Candidate
Genome**: a canonical hash over nine material bindings, including the source commit,
the contract-genome root it was built against, the dependency-lock hash, the
toolchain hash, the CI-workflow hash, the build-input hash, and the AI-release-closure
hash. RC-SP0009's genome is
`15fa5dc50ee65452b464b7736aee4afb3e2ec0bf596df326a211c3d3a11f0c89`.

**Absence is identity.** Where a material input does not exist, its absence is hashed
explicitly. This repository has **no CI workflow files** (`ci_workflow_hash: ABSENT`),
**no lockfile that pins exact versions**, and **no declared build backend** — and each
absence is folded into the genome as `ABSENT` rather than silently treated as equal to
presence. A change that later *adds* a CI workflow produces a different genome; the
system can never confuse "no workflow" with "some workflow."

**Immutability and history.** The genome is immutable. Lifecycle changes are recorded
as transitions, never as edits. RC-SP0009's history is a linear chain: `DRAFT →
CLASSIFIED → IMPACT_ANALYZED → SLICE_CLOSED → GATES_PLANNED → VERIFYING → QUALIFIED →
ARTIFACT_CLOSURE_SEALED → READY_FOR_LATER_PROMOTION`.

**Pause/resume revalidates stale evidence.** A paused candidate does not resume on
trust; on resume, evidence that has aged past its time-to-live is treated as stale and
must be re-established. **Supersede preserves history:** a superseded candidate is not
deleted; `superseded_by` links forward and the prior record remains.

**Classification gives small diffs no discount.** The classifier assigns multi-label
change classes and a risk vector from content, not size. A one-line authority change is
HIGH risk. RC-SP0009 classifies as `DOCS_CHANGE`, `GOVERNANCE_TOOLING_CHANGE`, and
`TEST_CHANGE` over 36 paths, with an all-LOW risk vector and no hard flags — because it
is exactly that: governance tooling, tests, and docs, touching no tenant, authority,
safety, or supply-chain surface.

---

## 3. The non-compensatory gate lattice and UNKNOWN-blocks

### 3.1 Applicability and result are separate dimensions
The kernel keeps **whether a gate applies** (`REQUIRED`, `NOT_APPLICABLE`,
`REVIEW_REQUIRED`) strictly separate from **what a gate found** (`PASS`, `FAIL`,
`UNKNOWN`, `STALE`, `INVALID`, `WAIVED`) (`D-0009-07`). Conflating them is how a
missing check gets read as a passing check; the separation makes that impossible.

### 3.2 The registry and the applicability engine
The gate registry defines the release checks — tenant isolation, RBAC/authority,
safety, proof integrity, secret exposure, artifact integrity, compatibility, contract
inventory, migration, unit tests, browser E2E, mutation adequacy, build hermeticity,
reproducibility, supply chain, CI workflow security, agentic injection, AI closure,
documentation, rollback-or-forward-fix, feature flags, and unknown-outcome handling.
An applicability engine, driven by the change classes and risk vector, decides which
gates are `REQUIRED` for a given candidate; a dependency DAG orders them. For
RC-SP0009 nine gates are required and the rest are honestly `NOT_APPLICABLE` (no
tenant, authority, safety, migration, supply-chain, CI, or AI surface is touched).

### 3.3 Non-compensatory, fail-closed
Gate aggregation is **non-compensatory**: no score, no quantity of passing gates, and
no averaged risk number can cancel a failure on a tenant, authority, safety, proof, or
supply-chain gate. The risk vector has ten dimensions and is **never averaged** — a
single HIGH on a hard dimension is a hard concern regardless of the other nine.

The lattice is **fail-closed**: for a required hard gate, `UNKNOWN`, `STALE`,
`INVALID`, and *missing* all **BLOCK**. The safe default is not "pass"; it is "not yet
shown." Aggregation is most-restrictive-policy: the worst applicable verdict governs.

### 3.4 Non-waivable gates
A subset of gates is registered **non-waivable**. No waiver, however well-formed, can
move them. Attempting to waive a non-waivable gate is itself a rejected action
(`NON_WAIVABLE_WAIVER_REJECTED`).

### 3.5 The reference verdict — with an honest advisory
RC-SP0009's verdict is `qualifiable: true` with an empty `blocking` list and one
`advisory` entry: `GATE_DOCUMENTATION` returned `UNKNOWN`. Because
`GATE_DOCUMENTATION` is an advisory gate rather than a required hard gate, its
`UNKNOWN` is surfaced honestly as advice and does not block — but it is *shown*, not
swallowed. Had it been a required hard gate, that same `UNKNOWN` would have blocked.

---

## 4. The obligation hypergraph and Definition of Done

**Done** is not a feeling and not a merge. It is closure over an **obligation
hypergraph**: change classes induce obligations, obligations require specific evidence,
and a candidate is `done` only when every applicable obligation is `CLOSED` with
current, candidate-bound evidence — and no applicable obligation is left open by an
invalid waiver.

RC-SP0009 induces five obligations — implementation, tests, documentation, ownership,
and proof — each closed on 2026-07-12 against candidate-bound evidence refs. `OB-PROOF`
is registered **non-waivable** (`waivable: false`). The DoD closure record is
`done: true` with empty `open`, `open_hard`, and `invalid_waivers` lists.

**Merge is not done.** The hypergraph is evaluated on the candidate, not on branch
state, so a change can be merged and still carry open obligations. Only closure makes
it done.

---

## 5. Honest failure and rerun ledgers

Two append-only ledgers keep the release honest about what actually happened.

The **test execution ledger** records every attempt with its environment fingerprint,
result, and failure signature. It is append-only: a result is never overwritten.
RC-SP0009's ledger has two rows for the same browser E2E test — attempt 1 `FAIL` under
`full-suite-parallel` with signature `'450 EUR' assertion on shared agent-view panel`,
attempt 2 `PASS` under `isolation`. Both stay.

The **rerun accounting** makes the constitutional rule explicit: *a pass after failure
is not proof of flakiness and does not erase the failure* (`D-0009-18/19`). The test
appears in `tests_with_failure_then_pass`, `total_attempts: 2`, and — importantly —
`reruns: 0`: the PASS was a different environment, not a rerun of the failing one, so
nothing was laundered. **Rerun-laundering detection** watches for the pattern where a
failure is quietly reissued as a rerun to manufacture green history; it is refused.

---

## 6. Flake intelligence

Flakiness is diagnosed, not waved away. The kernel treats a suspected flake as a
first-class object with **environment-conditioned** statistics and **systemic**
structure — and it is careful about causal language.

- **Environment-conditioned posterior.** For a suspected flake the kernel maintains a
  Beta posterior conditioned on a *single* environment fingerprint. RC-SP0009's
  browser test carries `Beta(1+f, 1+p)` on environment `EF-8bcb8812…` — two failures,
  zero passes, posterior mean 0.75 — flagged `advisory_only: true` and explicitly *not*
  a product-correctness statement (`D-0009-21`). In the *other* environment
  (`EF-c4b60bd1…`) it is two passes, zero failures.
- **Systemic co-failure clusters.** Tests that fail together are grouped by Jaccard
  similarity into clusters that describe **association, not causation**. RC-SP0009 has
  no clusters (`flake_clusters: []`).
- **Governed quarantine with critical-test protection.** Quarantine is a governed
  action, not a mute button, and critical tests are protected from quarantine
  (`CRITICAL_TEST_QUARANTINE_BLOCKED`).

The single browser E2E test is classified `ENVIRONMENT_INSTABILITY`: it fails
consistently under parallel load (module-scoped shared server+page fixtures, a fixed
port 8765, and stale-text waits) and passes in isolation. **SP0009 reproduced and
classified this flake; it did not cause it, did not attribute it to itself, did not
delete it, and did not weaken it.** It is the one P2 in the reference twin.

---

## 7. Reproducible and diverse builds

**Hermeticity is fail-closed.** Undeclared build inputs — network access, time
inputs, environment variables that actually matter — are treated as failures, not
conveniences (`BUILD_INPUT_UNDECLARED`, `BUILD_INPUT_UNKNOWN`). RC-SP0009's build
manifest declares empty network access and empty time inputs and marks `PYTHONHASHSEED`
`not-material`.

**Reproducibility is byte-equality by default.** The default relation is exact byte
equality; a normalized/equivalence relation is opt-in and, for RC-SP0009, unused
(`normalized_equal: false`). As noted in §1.7, one reproduction is evidence, not a
standing property.

**Diverse-builder quorum requires distinct trust domains.** A quorum of builders must
come from *distinct* trust domains, not merely distinct names, to defend against
common-mode compromise. RC-SP0009's honest reality: `min_trust_domains: 1`,
`required_threshold: 1`, one counted signer, one domain (`repository-local`). The
mechanism is real; the deployed diversity is one — and the record says exactly that
rather than overstating it.

Because releases here are **source trees, not built binaries**, the "artifact" is a
deterministic tree digest over the tracked release files. That is stated plainly, not
dressed up as a compiled-binary supply chain.

---

## 8. Artifact closure

An artifact is **sealed** to a digest and a candidate genome; **substitution** (a
different byte string presented under the same identity) is detected
(`ARTIFACT_SUBSTITUTION`); and promotion is **promote-the-same-bytes** — the exact
digest that was verified is the one that advances (build once / verify the exact
artifact / promote the same bytes). RC-SP0009's artifact is a sealed `SOURCE_TREE` of
239,498 bytes with digest `02d32b5b…`.

The **Artifact Closure graph** requires that an artifact carry its full set of related
evidence — SBOM, attestations, trust roots, and a verification summary — before closure
is complete. RC-SP0009's closure is `COMPLETE` with an empty `missing` list, linking
SBOM `SB-bf15db8b…`, attestation `AT-5f4a9b2f…`, trust root `finalis-release-root-1`,
verification summary `VS-SP0009`, and transparency receipt `TR-3878266a…`.

---

## 9. Trust-root governance and threshold diversity

Trust is governed as a **TUF-style trust-root lifecycle**. A trust root has a version,
a validity window, an expiry, a possible revocation, authorized signers, a threshold,
and a trust domain. The kernel enforces **version monotonicity** (no silent rollback),
**expiry**, **revocation**, and **rollback/freeze detection**
(`TRUST_ROOT_ROLLBACK_DETECTED`, `TRUST_FREEZE_DETECTED`), and it requires a
**threshold quorum with domain diversity** (`TRUST_THRESHOLD_NOT_MET`).

As established in §1.4, **signed is not trusted**: a signature is verified against the
*current, authorized* root, not accepted on its face. Trust and provenance are also
projected into **SLSA** and **in-toto** shapes (see the research register) — as
projections, with **no SLSA level claimed**.

RC-SP0009's single active root `finalis-release-root-1` is version 1, valid from
2026-07-12, expiring 2027-07-12, not revoked, threshold 1, one authorized signer, one
domain. Again: the governance is real; the deployed threshold and diversity are one,
and the record says so.

---

## 10. Transparency receipts

Inclusion in a transparency log is recorded as a **Merkle inclusion receipt** over an
RFC6962-style log. The constitutional caution is §1.5: **attested is not true**, and a
receipt whose inclusion has not been checked is marked honestly. RC-SP0009's receipt
`TR-3878266a…` sits at log index 0 in `finalis-release-log-1` with a size-1 checkpoint
and **`status: UNVERIFIED`** — an empty inclusion proof is not dressed up as a verified
one.

---

## 11. SBOM, AI/ML-BOM, and VEX

- **SBOM completeness is explicit.** Five states, no pretense. RC-SP0009's SBOM
  (CycloneDX-1.7) is `INCOMPLETE_THIRD_PARTY` and that is recorded as the single P2
  finding — *recorded, not hidden.*
- **AI/ML-BOM is distinct from the SBOM.** Models, datasets, prompts, configurations,
  and policies are inventoried separately (CycloneDX-1.7-MLBOM). RC-SP0009's ML-BOM
  honestly lists `models: ["none"]` and `configurations: ["mock-providers-only"]`.
- **VEX is evidence, not exemption.** A VEX statement informs a vulnerability decision;
  it does not by itself exempt a component (`VEX_EVIDENCE_INSUFFICIENT`).
- **Vulnerability evidence is time-bound.** Stale scan evidence is stale, not a pass
  (`VULNERABILITY_EVIDENCE_STALE`).
- **Scanner diversity and common-mode.** Multiple scanners help only if they are
  independent enough; common-mode dominance is flagged
  (`SCANNER_COMMON_MODE_RISK`, `SCANNER_DIVERSITY_INSUFFICIENT`). With no CI in this
  repo, scanner diversity is honestly `UNKNOWN`.

---

## 12. Agentic CI injection defense and AI release closure

**CI workflow security and agentic injection.** Untrusted content — issue text, PR
bodies, external comments, tool/model output — **never grants release authority**
(`EXTERNAL_CONTENT_AUTHORITY_REJECTED`, `AGENTIC_WORKFLOW_INJECTION_PATH`). A taint
analysis tracks whether untrusted data can flow into an authority-bearing decision;
**model output cannot approve a release.** This repository has **no CI workflow files**,
so the CI-security posture is recorded over fixtures and future workflows, with
`workflows_present: false` — the mechanism exists; there is nothing live to scan.

**AI release closure.** The composite AI release identity binds model name, version,
deployment, fallback order, prompts, tools, retrieval, safety and policy configuration.
**Same model name is not same behavior** (§1.8); the **fallback order is material**
(reordering fallbacks is a different system); and an **opaque-provider-update detector**
watches for behavior drift behind a stable name (`OPAQUE_PROVIDER_UPDATE_SUSPECTED`).

The honest reality for this repository: **there is no real AI provider** — every
adapter is a mock. The AI closure records exactly that: provider `none`, model name
`none`, and a known limitation that "repository has zero live AI providers; all
adapters are mocks." The **SP0011 placeholder cannot fabricate evidence**
(`SP0011_EVIDENCE_FABRICATION_REJECTED`); `sp0011_qualification` is `PENDING_SP0011`
with `evidence: null`.

---

## 13. Proof-carrying qualification and the unknown budget

**Qualification is a hard conjunction**, not a weighted score. A candidate is
qualifiable **iff all five** of these hold:

1. `all_required_hard_gates_pass`
2. `all_non_waivable_obligations_closed`
3. `artifact_closure_complete`
4. `no_open_blocking_defeater`
5. `hard_scope_unknowns_zero`

For RC-SP0009 all five are `true`, so `qualifiable: true`. There is also an **unknown
budget**: hard-scope unknowns must be zero (`hard_scope_count: 0` for RC-SP0009), and
`UNKNOWN_BUDGET_EXCEEDED` fires if that budget is breached. Reaching `qualifiable` moves
the candidate no further than `READY_FOR_LATER_PROMOTION` — a **non-production**
assurance state, never deployment.

---

## 14. Feature flags and progressive delivery

**Feature flags cannot widen authority.** A flag may narrow behavior; it may never
grant permissions the change did not otherwise earn
(`FEATURE_FLAG_AUTHORITY_VIOLATION`). **Missing flag data fails safe** — an absent or
unreadable flag resolves to the safe, restrictive value, not the permissive one. Flags
also expire (`FEATURE_FLAG_EXPIRED`).

**Progressive delivery contracts are DEFINED, not EXECUTED.** RC-SP0009 carries a
contract with `executes_rollout: false` and `status: DRAFT`. It pre-declares a
sequential policy (`e-process`, α=0.05, pre-declared), a sample-ratio-mismatch policy,
an interference policy, and **hard-abort rules** — `TENANT_VIOLATION`,
`AUTHORITY_VIOLATION`, `SAFETY_VIOLATION`, `PROOF_INTEGRITY_VIOLATION` — that trigger
immediate abort. As in §1.10, a single canary peek is not an anytime-valid verdict;
the pre-declared e-process is what makes optional stopping honest. Nothing is executed.

---

## 15. The release proof envelope

The **release proof envelope** is the single, structurally-allowlisted digest object
that binds every piece of the release proof — candidate genome, gate registry and
result ledger, impact cone, test selection and execution ledgers, mutation adequacy,
reproducibility, artifact closure, SBOM, AI/ML-BOM, AI closure, trust root,
transparency receipt, defeaters, waivers, VEX, provenance, rollback, and DoD closure.

It is **non-authoritative** (`non_authoritative: true`) and **fail-closed**: it is a
digest of proof, and it **creates no deployment authority**. Its structure is a fixed
allowlist so that unknown, unexpected fields cannot smuggle claims in. RC-SP0009's
envelope is `finalis-release-proof-envelope-v1`, version 1.0.0, content digest
`90d50a3d…`, validator `sp0009-release-validator-1`.

---

## 16. Defeaters and requalification

Qualification is **revocable**. A **defeater** is a challenge to a qualified state; a
*validated, blocking* defeater triggers requalification and moves the candidate toward
`SUSPENDED_BY_DEFEATER` / `REQUALIFICATION_REQUIRED`. **History is preserved** — a
requalified candidate carries its prior qualification, not a rewritten one. For
RC-SP0009 there is no open defeater (`open_defeaters: []`). This is the sense in which a
release is a *revocable* state transition: new evidence can reopen a closed question.

---

## 17. The change boundary (stated honestly)

This kernel is protected by a **fail-closed import allowlist** and an **AST frontier
check** (`boundary.py`, `modelcheck.py`): the release tooling may not import product
code, and the boundary check fails closed if it cannot prove the frontier is respected
(`BOUNDARY_VIOLATION`). Bounded invariant model checks (`modelcheck`) hold the core
properties — genome sensitivity, lattice fail-closed, ledger append-only, quorum
diversity — all `HOLD` in the reference twin.

To restate the boundary one more time, because honesty about limits is itself a
constitutional value: **zero deployment, zero migration (frontier stays v27), zero
production credentials, zero external effect, no SP0011 evidence, never imported by
product code.**

---

## 18. The fail-closed philosophy

Every default in this kernel points the same way: **the absence of proof is not
permission.**

- Unknown, stale, invalid, and missing all **block** a required hard gate.
- Absence is hashed as identity, never treated as equal to presence.
- A pass never erases a failure.
- Signed is not trusted; attested is not true; an SBOM's existence is not its
  completeness; one reproduction is not reproducibility; a model name is not a
  behavior; one canary peek is not an anytime-valid verdict.
- Untrusted content and model output can never grant release authority.
- The proof envelope creates no deployment authority.
- The kernel is **deterministic**: the twin rebuilds byte-identical, and `validate`
  fails P0 if a committed twin does not byte-match a fresh build.

Where the honest answer is `UNKNOWN`, `ABSENT`, `INCOMPLETE`, or
`BLOCKED_PENDING_SP0011`, the kernel says exactly that — and so does this constitution.
