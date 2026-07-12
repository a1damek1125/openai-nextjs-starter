# TOOL-B10 Roadmap Identity Report

> **RE-FILING CORRECTION (authoritative).** This kernel was authored against a spec the
> requester circulated as *"TOOL-B6 V3 FINAL — FINALIS Sovereign Context Governance Vault."*
> The identity analysis below was performed against a **stale local checkout** (HEAD
> `7d2c44a`, TOOL-B5) that did not contain the authoritative remote history. On fetch at
> push time, the remote branch was found to already carry a **different canonical TOOL-B6**
> — *"TOOL-B6 v5: Verifiable Read-Path Runtime Microkernel"* (`finalis/ai_employee/tool_runtime.py`)
> — as well as TOOL-B7, TOOL-B8, and TOOL-B9. The Context Governance subject is genuinely
> new (no `tools/context_governance` package exists on the remote), but the **`TOOL-B6` ID
> was already taken by an unrelated subject**. To honour roadmap integrity ("do not modify
> the roadmap to fit the spec") this deliverable was re-filed under the **next free slot,
> `TOOL-B10`**, with no change to its content, tests, or guarantees. Every "TOOL-B10" below
> reflects that corrected filing; the original spec's internal `D-B6-*`/`AC-B6-*` decision
> codes are retained verbatim as source-spec citations. The "no canonical definition exists"
> conclusion in §1 was true of the stale local checkout only and does **not** hold against
> the authoritative remote — hence the re-file rather than a claim of a free B6 slot.

---


**Canonical mission ID:** TOOL-B10
**Canonical mission title:** FINALIS Sovereign Context Governance Vault — Point-in-Time
Context Snapshots, TOCTOU-Safe Context Leases, Evidence-Before-Belief Memory Bridge,
Semantic Information-Flow Control, Anytime-Valid Retrieval, Robust Minimal-Evidence
Compilation & Proof-Carrying Context Capsule
**Spec revision:** TOOL-B10 **V3 FINAL** (supersedes V1, V2, and every earlier draft)
**Classification target:** `FINALIS_SOVEREIGN_CONTEXT_GOVERNANCE_V3`
**Mission class:** product extension + deterministic reference kernel + tests + formal
models + documentation + proof artifacts
**Canonical predecessor:** TOOL-B5 (Null Broker) — **VERIFIED PRESENT** at HEAD `7d2c44a`
**Canonical successor:** TOOL-B7 (to be read from the locked roadmap after TOOL-B10; not
invented here)
**Execution date:** 2026-07-12

This report records what TOOL-B10 *is*, the repository-truth binding decision, the
change/migration boundary, existing implementation overlap, and the semantic comparison
with the V3 spec — **before any other tracked file is modified**.

---

## 1. Binding decision — PROCEED

The spec directs reading the canonical mission title from `docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json`,
`ROADMAP_LOCK_1_NEXT_20_SP.md`, `docs/audit/AUDIT_TRACE_1_MASTER.md`, `docs/program/`.
**None of those files exist in this repository** (the only roadmap doc is
`docs/finalis-ai/14-mvp-and-roadmap.md`, a phased MVP roadmap that does not enumerate the
CORE-A / TOOL-B mission IDs). A repository-wide search finds **no canonical TOOL-B10
definition and no TOOL-B7 reference** anywhere in `docs/` or `finalis/`.

Applying the spec's binding rules against repository truth:

- There is **no materially-different canonical TOOL-B10 subject** to conflict with (rule C
  does not apply — nothing is assigned to another subject).
- The repository's actual trajectory is **CORE-A1..A6** (foundation, lifecycle, run
  ledger, approval gate, artifact system) → **TOOL-B1..B5** (tool capability governance:
  zero-trust registry → descriptor assurance graph → protocol contract proof → causal
  reference monitor → proof-carrying null broker). **Context governance** — governing the
  *evidence and context* that tools and planners consume — is a **coherent, adjacent next
  step** in this tool/context-governance arc.
- The V3 subject (context preparation, evidence context, tool context, provenance,
  retrieval, memory-to-work context, context governance, context compilation) matches
  **binding rule A / B**.

**Decision: PROCEED** — use this canonical title, retain all compatible V3 requirements,
and implement as a deterministic reference kernel that **extends, never rebuilds**,
TOOL-B1..B5 and the existing evidence/memory/tenant substrate. The roadmap is **not**
edited to fit this document.

## 2. Change & migration boundary (repository truth authoritative)

- **Effect boundary:** zero live external effects / tool execution / MCP / A2A / message
  sends / payments / CRM mutation; zero secrets or provider tokens in context; zero
  context item treated as authority/approval/permission; zero silent truncation,
  contradiction resolution, taint removal, or cross-tenant/principal/account/purpose flow;
  zero automatic memory writeback or lesson promotion.
- **Migration boundary:** **frontier stays v20** — no product DB migration. A migration is
  permitted only after a `TOOL_B10_MIGRATION_NECESSITY_REPORT` proves necessity, no
  equivalent persistence, additive-only, isolation, rollback, mixed-version safety, and a
  repository-derived number. The deterministic reference kernel uses repository-local
  content-addressed artifacts + fixtures, so **no migration is expected**.
- **Location:** all TOOL-B10 work lives under `tools/context_governance/`,
  `docs/tool_b10/`, `tests/test_context_governance_*.py`. Existing product runtime under
  `finalis/` is not modified by default.

## 3. Existing implementation overlap (extend, do not duplicate)

| Canonical subsystem (must reuse) | Repository location |
|---|---|
| Tool capability governance (TOOL-B1..B5) | `finalis/ai_employee/tool_{registry,contracts,guardrails,quality,broker}.py` (+ `_store.py`) |
| Immutable / content-addressed evidence | `finalis/evidence/immutability.py`, `evidence_store.py`, `finalis/portal/evidence_store.py` |
| Transparency receipts | `finalis/evidence/transparency.py` |
| Evidence requirements / views / gates / policy / derivatives | `finalis/evidence/{requirements,views,gates,policy,derivatives,models,storage}.py` |
| Memory | `finalis/crm/memory.py` |
| Tenant / principal / RBAC / approval / authority | `finalis/portal/{app,db}.py`, `finalis/ai_employee/{authority,approvals,approval_decisions}.py` |

The TOOL-B10 kernel **references** these as the canonical authorities and defines only the
*context-governance* layer above them (entitlement, snapshot/lease/TOCTOU, four-valued
claim ledger over evidence, provenance/influence/common-mode, taint, requirement
hypergraph + minimal bases, robust selection, claim-preserving compaction, branch/merge,
least-privilege views, model-context ABI, consumption receipts, proof-carrying capsule +
independent checker). It creates **no** parallel evidence authority, memory truth, tenant
model, provider identity, policy/approval engine, or context store.

## 4. Semantic comparison with V3 & retained hardening

The V3 spec's 71 subsystem families (§2) and 320 acceptance criteria (§24) are retained in
full where compatible with repository truth. The 16 unique innovations (point-in-time
snapshot lease, TOCTOU firewall, Context BOM, SCITT-compatible transparency, minimal
evidence basis, anytime-valid retrieval, conformal-with-shift-guard, robust submodular
selection, branch/merge, model-context ABI, consumption receipt, proof of non-use, privacy
exposure budget, cache coherency, robustness frontier, proof-carrying capsule) are all
in-scope for the deterministic std-lib reference kernel. Excluded/deferred elements are
recorded in the acceptance matrix with owner + next action (e.g. live MCP/A2A servers,
external transparency services, external SMT solvers — all optional adapters, never
required by the reference kernel).

## 5. PROCEED

Scope resolved (no conflict → PROCEED); predecessor TOOL-B5 verified present; baseline
clean and frozen (`TOOL_B10_VERIFIED_BASELINE.md`); change/migration boundary asserted.
TOOL-B10 V3 proceeds under a repository-local, deterministic, standard-library-only Context
Governance kernel producing point-in-time, least-privilege, proof-carrying Context
Capsules that **inform but never authorize** work.
