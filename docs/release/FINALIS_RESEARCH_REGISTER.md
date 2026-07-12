# FINALIS Release Assurance — Research Register

*How SP0009 relates to external standards and research, assessed at their actual
maturity on the execution date (2026-07-12). Every entry states what the item is, its
execution-day maturity, how SP0009 applies it (**projection**, **adapter**, or
**reference**), and an honesty caveat.*

**Global caveat:** SP0009 installs **no runtime** of any standard below. It emits
canonical JSON only. Where it "applies" a standard it does so as a data **projection**
(it shapes its own records to the standard's schema), a replaceable **adapter** (a thin
seam where a real tool could plug in), or a **reference** (a model it borrows from
without deploying). **No conformance level is claimed for any of them.**

---

## A. Supply-chain provenance, attestation, and trust

### SLSA 1.2
- **What:** Supply-chain Levels for Software Artifacts — provenance and
  verification-summary formats and level definitions.
- **Maturity:** established, versioned framework.
- **SP0009 use:** **projection.** Provenance and a verification summary (`VS-SP0009`)
  are shaped into SLSA-style records inside artifact closure.
- **Caveat:** **no SLSA level is claimed.** These are shape projections, not an assessed
  build level.

### in-toto Attestation Framework v1
- **What:** signed-statement framework (subject + predicate) with a standard envelope.
- **Maturity:** v1, established.
- **SP0009 use:** **projection.** Attestations use a subject digest and a typed
  predicate (`predicate_type: finalis/release-evidence/v1`).
- **Caveat:** unknown predicate types are rejected (`UNKNOWN_PREDICATE_REJECTED`);
  attested ≠ true.

### Sigstore bundle v0.3.2
- **What:** keyless-signing bundle format (certificate, signature, log entry).
- **Maturity:** a specific bundle schema version.
- **SP0009 use:** **adapter.** One replaceable verification seam; identity + policy are
  what matter, not the signature alone.
- **Caveat:** no Sigstore instance is contacted; signed ≠ trusted.

### TUF (The Update Framework)
- **What:** trusted-root model with threshold signing, rotation, expiry, rollback and
  freeze protection.
- **Maturity:** mature specification.
- **SP0009 use:** **reference/projection.** The trust-root lifecycle
  (`finalis-release-root-1`) implements version monotonicity, expiry, revocation, and
  rollback/freeze detection with a threshold quorum.
- **Caveat:** deployed threshold and domain diversity are **1** here; the record says so.

### GitHub artifact attestations
- **What:** GitHub's build provenance attestation product.
- **Maturity:** available GitHub feature.
- **SP0009 use:** **adapter** — one replaceable attestation source among many.
- **Caveat:** not invoked; this repo has no CI. A single adapter, not a dependency.

### OCI referrers
- **What:** digest-linked relationships between registry artifacts (referrers API).
- **Maturity:** part of the OCI distribution spec.
- **SP0009 use:** **reference.** The artifact-closure graph borrows the digest-linked
  relationship idea.
- **Caveat:** no registry, no images; releases here are source trees.

### GUAC
- **What:** graph model aggregating software-supply-chain metadata.
- **Maturity:** active project.
- **SP0009 use:** **reference** for the closure-graph model only.
- **Caveat:** **GUAC is not deployed.** No GUAC instance exists.

### SCITT
- **What:** Supply Chain Integrity, Transparency and Trust — standardized transparency
  services.
- **Maturity:** emerging / draft-stage standardization.
- **SP0009 use:** **future reference** for transparency receipts.
- **Caveat:** not implemented; receipts are recorded `UNVERIFIED` where inclusion is
  unchecked.

### Reproducible Builds
- **What:** the practice/definition of byte-identical rebuilds from the same inputs.
- **Maturity:** established practice.
- **SP0009 use:** **projection.** Reproducibility defaults to byte-equality.
- **Caveat:** one reproduction is **evidence, not a standing property** (`D-0009-65`).

---

## B. SBOM, ML-BOM, and vulnerability evidence

### SPDX 3.0
- **What:** software bill-of-materials standard.
- **Maturity:** 3.0 released.
- **SP0009 use:** **reference** for SBOM completeness semantics.
- **Caveat:** the materialized SBOM is emitted in CycloneDX form; SPDX is a reference
  point, not a produced document here.

### CycloneDX 1.7 (SBOM / ML-BOM / VEX)
- **What:** BOM standard covering software, ML, and VEX.
- **Maturity:** 1.7.
- **SP0009 use:** **projection.** The SBOM (`CycloneDX-1.7`) and the distinct AI/ML-BOM
  (`CycloneDX-1.7-MLBOM`) are shaped to it.
- **Caveat:** SBOM completeness is honestly `INCOMPLETE_THIRD_PARTY` (recorded as P2);
  ML-BOM lists `models: ["none"]`.

### OpenVEX (draft)
- **What:** vulnerability-exploitability-exchange statement format.
- **Maturity:** **draft.**
- **SP0009 use:** **adapter.** VEX is treated as evidence into a decision.
- **Caveat:** **OpenVEX is draft**; VEX is **evidence, not exemption**
  (`VEX_EVIDENCE_INSUFFICIENT`). No VEX statements are present in the reference twin.

### OSV
- **What:** open vulnerability database/schema.
- **Maturity:** established.
- **SP0009 use:** **adapter** — one replaceable vulnerability source.
- **Caveat:** not queried; vulnerability evidence is time-bound
  (`VULNERABILITY_EVIDENCE_STALE`).

### OpenSSF Scorecard
- **What:** repository security posture checks.
- **Maturity:** established.
- **SP0009 use:** **reference.** Its lesson — surface **findings, not one score** —
  matches the non-compensatory principle.
- **Caveat:** not run; no single score is produced or trusted.

---

## C. CI / workflow security

### GitHub Actions secure use
- **What:** hardening guidance — least-privilege tokens, full-SHA action pinning,
  untrusted `github` context, no privileged untrusted checkout.
- **Maturity:** established guidance.
- **SP0009 use:** **projection.** The CI-security gate encodes these as checks
  (`CI_TOKEN_OVERPRIVILEGED`, `DEPENDENCY_NOT_PINNED`, `DANGEROUS_CI_WORKFLOW`).
- **Caveat:** **no CI workflow files exist** in this repo; the gate operates on fixtures
  and future workflows (`workflows_present: false`).

### NIST SSDF & NIST AI RMF
- **What:** Secure Software Development Framework; AI Risk Management Framework.
- **Maturity:** published frameworks.
- **SP0009 use:** **reference.** Outcome mappings, not control-by-control certification.
- **Caveat:** SP0009 maps to outcomes; it makes **no compliance/certification claim**.

### OpenTelemetry
- **What:** observability/telemetry standard.
- **Maturity:** mature.
- **SP0009 use:** **future reference** for delivery observability.
- **Caveat:** no telemetry is emitted; progressive delivery is defined, not executed.

---

## D. 2026 research inputs

Each is applied as a **reference** shaping a kernel behavior; none is a deployed system.

| Item | What it studies | SP0009 application | Caveat |
|---|---|---|---|
| Agentic workflow injection (arXiv 2605.07135) | injection paths through agentic CI | taint analysis: untrusted content / model output never grants release authority | mechanism over fixtures; no live CI |
| Scanner disagreement (2601.14455) | scanners disagree | scanner-diversity + common-mode classes | diversity is `UNKNOWN` with no CI |
| LLM CI auditing disagreement (2605.02091) | LLM auditors disagree | model output cannot approve a release | advisory only; not authoritative |
| Workflow evolution (2602.14572) | CI workflows drift over time | genome binds `ci_workflow_hash`; drift changes identity | hash is `ABSENT` here |
| Cross-project flakiness (2602.09311) | flakiness across projects | flake registry / classification vocabulary | advisory; not a correctness claim |
| Environmental flakiness (2602.19098) | environment-caused flakes | environment-conditioned Beta posterior | the one P2 is `ENVIRONMENT_INSTABILITY` |
| Systemic flakiness (2504.16777) | co-failing test clusters | Jaccard co-failure clusters — **association, not causation** | no clusters in the reference twin |
| Identity-stable canary (2605.28097) | canary identity stability | anytime-valid e-process; identity-bound cohorts | delivery is DEFINED, not executed |

---

## E. Product-pattern reference — Viktor 2026

- **What:** Viktor 2026 product integration patterns — read-only integration,
  multi-account separation, pause/resume, visible status, config-preserving reconnect,
  approval before protected effects.
- **SP0009 use:** **reference.** Adopts the clarity/usability patterns (read-only,
  multi-account separation, pause/resume with revalidation, visible status,
  config-preserving reconnect) **and strengthens approval** beyond them: approvals are
  bound to candidate + effect + context, carry expiry and revocation, forbid
  self-approval, and respect authority ceilings.
- **Caveat:** the strengthening is a design stance; SP0009 executes no protected effect
  to approve — there is nothing to deploy.

---

## F. Honesty summary

- No runtime of any standard is installed; all outputs are canonical JSON.
- **No SLSA level claimed.** **OpenVEX is draft.** **GUAC is not deployed.** **SCITT /
  OpenTelemetry are future references.**
- Sigstore, OSV, GitHub attestations are **single replaceable adapters**, none invoked.
- NIST SSDF/AI RMF are **outcome mappings**, not certifications.
- The one flake is `ENVIRONMENT_INSTABILITY`, reproduced and classified, not caused by
  SP0009; flake statistics are advisory, never product-correctness claims.
- There is **no real AI provider** (all mocks) and **no SP0011 evidence**
  (`PENDING_SP0011`, never fabricated).
