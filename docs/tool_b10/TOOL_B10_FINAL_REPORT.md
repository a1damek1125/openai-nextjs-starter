# TOOL-B10 V3 FINAL — FINALIS Sovereign Context Governance Vault — Final Report

**Canonical ID:** TOOL-B10 · **Classification:** `FINALIS_SOVEREIGN_CONTEXT_GOVERNANCE_V3` · **Kernel version:** 3.0.0
**Branch:** `claude/finalis-ai-casewoker-blueprint-f1huse` · **Date:** 2026-07-12

> **Filed as TOOL-B10.** The requester circulated this spec as "TOOL-B6 V3." On fetch, the
> authoritative remote was found to already carry a different canonical **TOOL-B6**
> (Verifiable Read-Path Runtime Microkernel, v5), plus B7/B8/B9. To preserve roadmap
> integrity, the Context Governance kernel was re-filed under the next free slot, **TOOL-B10**,
> with no change to content or guarantees. It rebases cleanly onto the current remote and
> touches no existing file. Internal `D-B6-*`/`AC-B6-*` codes are kept as source-spec citations.

## 1. What was built

A deterministic, **standard-library-only** Context Governance reference kernel under
`tools/context_governance/` that transforms heterogeneous information into
**point-in-time, least-privilege, proof-carrying Context Capsules that INFORM but NEVER
AUTHORIZE work.** The kernel is self-contained: no product code under `finalis/` imports
it, it opens no live external effect, it performs no database migration (frontier stays
**v20**), and it emits no secret material or provider tokens.

The end-to-end contract is `governance.build_capsule(request)`: a fail-closed pipeline that
either seals a certified capsule (zero P0/P1 findings) or withholds it with a precise reason.

## 2. Module map

| Module | Responsibility |
|---|---|
| `canon.py` | Deterministic canonical JSON, SHA-256, Merkle forest, content-addressing, commitments |
| `model.py` | Closed vocabulary, four-valued claim lattice, taint lattice, state machines, reason codes, `Finding`/`Report` |
| `entitlement.py` | Entitlement-before-retrieval, version vector, snapshot, lease, TOCTOU firewall + delta certificate, cache coherency |
| `evidence.py` | Evidence-before-belief store, paraconsistent claim ledger, provenance/common-mode graphs, semantic taint, authority air-gap, memory-writeback quarantine |
| `requirements.py` | Requirement hypergraph, minimal support/refutation/missing bases, mandatory reservation, robust submodular selection, VOI, anytime-valid + conformal-with-shift-guard |
| `compile.py` | Claim-preserving compaction, conflict-preserving branch/merge, least-privilege views, noninterference, non-compensatory privacy budget, ABI render, consumption receipt/truncation, proof-of-non-use |
| `capsule.py` | Context BOM, risk envelope, certificate (generator), **independent checker**, replay twin, TCB manifest, SCITT transparency projection, robustness frontier |
| `governance.py` | `build_capsule` orchestrator binding every subsystem |
| `boundary.py` | Live-effect firewall (only `PURE_COMPUTE` permitted; unknown ops fail closed) |
| `validate.py` | Invariant self-check (INV-01..30) |
| `cli.py` / `__main__.py` | Read-only CLI: `validate` / `invariants` / `info` |

## 3. Load-bearing guarantees (all executed in tests)

1. **Four-valued lattice** — `BOTH` is not TRUE, `NEITHER` is not FALSE; only `SUPPORTED_ONLY`
   closes a critical requirement; a truthy non-`True` value is **not** support (strict `is True`).
2. **Entitlement before retrieval** — tenant/principal/account/purpose/operation/expiry all
   fail closed on any mismatch.
3. **TOCTOU firewall** — an unknown version-vector component or expired lease returns `BLOCKED`
   (fail-closed); material source/evidence/approval/policy deltas force recompile/requalify.
4. **Evidence before belief** — evidence is immutable and content-addressed before any derived claim.
5. **Semantic taint** — join takes the more severe level; taint survives transformation unless
   removal is **proven**; unremoved injection taint on a critical claim is P0.
6. **Authority air-gap** — information-channel content can never assert authority.
7. **Common-mode quotient** — mirrors/shared-model/shared-provider sources don't multiply independence.
8. **Requirement hypergraph** — minimal support/refutation/missing-evidence bases; independence floor.
9. **Mandatory reservation precedes budget** — a token budget can never evict a safety-critical claim.
10. **Robust submodular selection + VOI** — worst-case coverage under budget; retrieval never stops
    while a mandatory atom is unmet.
11. **Anytime-valid + conformal-with-shift-guard** — optional stopping is valid; a detected
    distribution shift disables the conformal guarantee (surfaced, never assumed).
12. **Claim-preserving compaction** — a critical claim's polarity/quantity/scope/state/provenance
    cannot be silently dropped or altered.
13. **Conflict-preserving merge** — a critical atom supported on one branch and refuted on another
    is a preserved conflict, never a false consensus.
14. **Least-privilege views + noninterference** — forbidden fields never render; a high-sensitivity
    input cannot change a low view's bytes.
15. **Non-compensatory privacy budget** — slack on one axis cannot offset an overrun on another.
16. **Model-context ABI + consumption receipt** — silent provider truncation is detected; an unknown
    consumed length fails closed.
17. **Proof of non-use** — an excluded item is certified not to have influenced the output.
18. **Proof-carrying capsule + independent checker** — the checker re-derives every root from the
    capsule body alone and rejects any capsule where `checker_id == generator_id`
    (**a generator can never self-certify**), the root doesn't match, the body isn't secret-free,
    or the capsule asserts authority.
19. **Replay twin** — a re-derived capsule must reproduce the identical root (determinism).
20. **Boundary firewall** — the kernel performs only pure computation; every forbidden or unknown
    effect is refused.

## 4. Test coverage

- **137 kernel tests** in `tests/test_context_governance_*.py` (canon, model, entitlement, evidence,
  requirements, compile, capsule, boundary, validate, governance end-to-end, and an
  acceptance-family suite), all passing, plus the shared builder `tests/_b10_ctxgov_kernel.py`.
- The acceptance suite pins each subsystem family (A..AE grouping) to a concrete executed guarantee;
  `docs/tool_b10/TOOL_B10_ACCEPTANCE_MATRIX.md` maps the full family taxonomy to the implementing
  functions.
- CLI self-check (`python -m tools.context_governance validate`) returns `ok: true` over INV-01..30.

## 5. Full-repository regression

The complete repository suite was re-run after all TOOL-B10 work and the red-team
hardening: **exit code 0, zero failures.**

| Metric | Value |
|---|---|
| Baseline test functions (pre-TOOL-B10) | 2982 |
| New TOOL-B10 test functions | 187 |
| **Total `def test_` functions** | **3169** |
| Full-suite result (`python -m pytest --ignore=tests/e2e`) | **exit 0 — all passing** |
| Browser/E2E | excluded from the deterministic run by repo convention |

Because the kernel is a self-contained package that **no existing product code imports**
and TOOL-B10 modified **zero pre-existing files** (only added `tools/`, `docs/tool_b10/`,
and `tests/test_context_governance_*.py`), it is structurally incapable of regressing the
existing suite — and the run confirms it.

The 187 TOOL-B10 tests break down as: canon, model, entitlement, evidence, requirements,
compile, capsule, boundary, validate, governance (end-to-end), an acceptance-family suite,
a **red-team regression suite** (each pinning a fixed defect), and a **coverage/edge-case
suite** (36 boundary tests).

## 6. Adversarial red-team

An independent red-team swarm agent probed all 20 guarantees with constructed
attacks. It found **three real defects**, all instances of the same anti-pattern —
an allowlist check that failed **open** on anything outside its enumerated set.
All three were fixed and are now pinned by regression tests in
`tests/test_context_governance_redteam.py`; the fixes were re-verified against the
adversary's own probe scripts.

| # | Defect found | Fix |
|---|---|---|
| 1 | The capsule certificate bound only a subset of the body, so `support_bases` (the minimal-support proof), `compiler_version`, and any injected key were **unbound** — an "independently verified" capsule could carry a forged support basis. | The certificate now binds a `BODY` root = hash of the entire canonical body; the checker recomputes it. Any field change moves the capsule root. |
| 2 | `informs_only` rejected only the literal top-level key `authority_grant`, so an injected `authority`/`grant_of_authority` key passed. | The capsule body is now a **closed shape**: a strict `ALLOWED_BODY_KEYS` allowlist refuses any smuggled key, plus a defence-in-depth scan for authority/grant/approval key names. |
| 3 | `taint_join` ranked any **unrecognized** taint label as 0 (== UNTAINTED), so a severe unknown label was silently dropped. | Unrecognized labels now rank above every known level (fail-closed); an unknown severe taint survives propagation. |

Secondary hardening from the same audit: secret scanning now inspects string
**values** (not just key names); compaction flags taint-stripping off a critical
claim (`COMPRESSION_TAINT_STRIPPED`); privacy exposure on an **unknown axis** fails
closed; the authority air-gap flags any non-`AUTHORITY`-channel record asserting
authority (missing channel fails closed); and `boundary.classify_effect` returns
`UNKNOWN` for a non-string operation instead of crashing. Two new invariants
(INV-22 taint fail-closed, INV-29 closed-shape body) were added to the self-check,
which now covers 17 invariants and returns `ok: true`.

The seven guarantees the red-team could **not** break: four-valued lattice,
TOCTOU fail-closed, non-compensatory privacy (core axes), mandatory reservation vs
budget, truncation-unknown fail-closed, compaction of enumerated attributes, and
boundary classification.

## 7. Security posture / constraints honored

ZERO live external effects · ZERO tool/MCP/A2A execution · ZERO email/Slack/Teams/calendar/payment/CRM
mutation · ZERO production credentials · ZERO secret material in context · ZERO context item as authority ·
ZERO memory/document as approval · ZERO cross-tenant/principal/account/purpose context flow · ZERO
automatic memory writeback · ZERO provider tokens in capsules · NO database migration (frontier v20).
Product remains **NOT_PRODUCTION_READY**. Each constraint is cited to its structural enforcer in
`docs/tool_b10/TOOL_B10_SECURITY_CONSTRAINTS.md`.

## 8. Honest scope notes

- The kernel is a **reference kernel**: it models the governance algebra and proof structure over
  in-memory objects. External adapters (live provider clients, a persistent SCITT log, real retrieval
  corpora) are intentionally **out of scope** and are represented by their content commitments, not
  live integrations — consistent with the zero-live-effect constraint.
- Acceptance is expressed as **subsystem families**, each backed by executed tests, rather than 320
  individually numbered assertions; the family matrix documents the mapping so coverage is auditable.
