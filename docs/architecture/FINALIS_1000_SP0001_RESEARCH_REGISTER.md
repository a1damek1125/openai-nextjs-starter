# FINALIS 1000 — SP0001 Research Register

**Executed 2026-07-11 (SWARM-D).** RETRIEVAL LIMITATION: direct `WebFetch`
returned HTTP 403 on every host (origin bot-protection; egress proxy healthy) —
all content corroborated via WebSearch snippets from the same primary domains.
All four 2026-dated arXiv IDs resolved with substantive abstracts (none
fabricated). Items that could not be corroborated are flagged and excluded from
evidentiary use.

| # | Source | URL | Status | Architectural implication |
|---|---|---|---|---|
| 1 | OpenAI — Harness Engineering | https://openai.com/index/harness-engineering/ | CURRENT (via index) | Agent-first repos need mechanical layer/edge boundaries + custom linters + structural tests in CI; docs are a table-of-contents. **Founding thesis: prompts do not enforce; the conformance gate does.** |
| 2 | OpenAI — Symphony | https://openai.com/index/open-source-codex-orchestration-symphony/ | CURRENT (via index); demo spec | Parallel autonomous agents, ~5× more landed PRs, less human review. **Per-PR deterministic gates + proof envelope are mandatory — human review can't scale to that rate.** |
| 3 | Architecture Without Architects | https://arxiv.org/abs/2604.04990 · /html/2604.04990v1 | CURRENT (2026-04) | "Vibe architecting": prompt wording alone yields structurally different systems (141→827 LOC). **Justifies declared-graph-vs-observed-graph conformance + decision records (proof envelope).** |
| 4 | SlopCodeBench | https://arxiv.org/abs/2603.24755 · /html/2603.24755v1 | CURRENT (2026-03-25) | Erosion rises in 80% of trajectories, verbosity 89.8%; invisible at any single green checkpoint; agent code 2.2× more verbose than OSS. **Green tests necessary-not-sufficient; drift must be longitudinal (Drift Observatory).** |
| 5 | AI-Generated Smells | https://arxiv.org/abs/2605.02741 | CURRENT (2026-05-04) | TLoC is a near-perfect decay predictor; correctness decoupled from quality; LLMs prefer high-coupling ("Unstable Dependency"). **Forbidden-edge/layering gate targets the dominant failure mode; TLoC/complexity are cheap drift proxies.** |
| 6 | The Spec Growth Engine | https://arxiv.org/abs/2606.27045 · /html/2606.27045v1 | CURRENT (2026-06-25) | Spec-anchored + code-coupled + drift-enforced (divergence = blocking merge); machine-readable spec graph; "Spine" context assembler scoped to ownership path. **Near-blueprint: spec graph→twin, Spine→context spine, drift gate→conformance gate. Vocabulary adopted.** |
| 7 | ContextCov (executable constraints) | https://arxiv.org/abs/2603.00822 · /html/2603.00822v1 | CURRENT v1 (2026-02-28); v2 UNVERIFIED | NL agent instructions are passively violated ("context drift"); transform into executable guardrails via static AST + architectural validators. **Bridge from CLAUDE.md prose to the deterministic gate.** |
| 8 | ArchAgent (architecture recovery) | https://arxiv.org/abs/2601.13007 | CURRENT (2026-01-19) | Static analysis + segmentation + LLM synthesis recovers architecture from legacy repos. **Pattern for offline twin seeding (bootstrap.py) — LLM recovery stays offline, never in the gate path (deterministic).** |
| 9 | Python `ast` | https://docs.python.org/3/library/ast.html | CURRENT (stable) | Offline, execution-free extraction of imports/defs/calls. **The v0 deterministic scanner engine (observe.py).** |
| 10 | Import Linter | https://import-linter.readthedocs.io/en/stable/ · github.com/seddonym/import-linter | CURRENT (via index) | Layers / Forbidden / Independence contracts with transitive edge checking. **Reference semantics reimplemented on the AST graph (adapter boundary, not a dependency).** |
| 11 | CodeQL | https://codeql.github.com/docs/codeql-overview/about-codeql/ | CURRENT (via index) | "Code as queryable data"; variant analysis for clone/duplication. **FUTURE ScannerAdapter boundary — not a mandatory dep now (D-0001-16).** |
| 12 | JSON Schema 2020-12 | https://json-schema.org/draft/2020-12 · /json-schema-core.html · /json-schema-validation.html | CURRENT (via index) | Deterministic, tool-agnostic validation. **Schema language for the twin + change intent; artifacts self-validate.** |
| 13 | Open Policy Agent / Rego | https://openpolicyagent.org/ · /docs/policy-language | CURRENT (via index) | Decouples policy decision from enforcement (facts→policy→decision over JSON). **FUTURE adapter boundary — v0 encodes rules deterministically in-process (D-0001-16); fact→policy→decision shape preserved.** |
| 14 | SLSA v1.2 attestations/provenance | https://slsa.dev/spec/v1.2/ · /attestation-model · /provenance | CURRENT (v1.2 Nov 2025, via index) | Every artifact carries verifiable provenance (in-toto predicate: subject + checks/results, DSSE-signed). **Motivates the Proof-Carrying Change Envelope — UNSIGNED/deterministic for now; DSSE/KMS signing deferred (D-0001-14).** |
| 15 | GitHub CODEOWNERS + Rulesets | https://docs.github.com/.../about-code-owners · .../managing-rulesets/about-rulesets · .../available-rules-for-rulesets | CURRENT (via index; required-reviewer rule GA 2026-02-17) | CODEOWNERS = one-owner analogy; gate = a required status check via a ruleset; envelope = the PR evidence. **How the repo-local system attaches to platform merge control.** |

## Decisions grounded in the research

- **Deterministic Python-AST scanner v0** (S9), reimplementing **Import Linter** layer/forbidden/independence semantics (S10) on the observed graph — no external dependency; OPA/Rego (S13) and CodeQL (S11) kept as future `ScannerAdapter` boundaries (D-0001-15/16).
- **Declared twin vs observed twin conformance** as the core (S1, S3, S6), with **longitudinal Drift Observatory** because green tests are necessary-not-sufficient (S4, S5).
- **Change Intent + drift gate** (S6, S7): architecture-significant divergence must be declared; undeclared delta is drift.
- **Proof-Carrying Change Envelope** modeled on SLSA in-toto predicate shape but **unsigned/deterministic** now (S14, D-0001-14).
- **Context Spine** scoped to ownership path (S6) to fight context explosion.
- **Offline twin seeding** (S8) — LLM/recovery never in the deterministic gate path.

## Source-handling honesty
Vendor posts (OpenAI) labeled PRIMARY-as-vendor. Roadmaps/RCs not treated as shipped. ContextCov v2 unverified (v1 used). All content is snippet-corroborated, not full-text — treat as directional, re-verify before any hard external commitment.
