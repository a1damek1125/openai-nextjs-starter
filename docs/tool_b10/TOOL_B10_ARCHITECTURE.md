# TOOL-B10 Architecture — FINALIS Sovereign Context Governance Vault

**Kernel ID:** `TOOL-B10`  **Version:** `3.0.0`  **Classification:** `FINALIS_SOVEREIGN_CONTEXT_GOVERNANCE_V3`
**Package:** `tools.context_governance`

The kernel is a deterministic, standard-library-only reference implementation that
transforms heterogeneous information into **point-in-time, least-privilege,
proof-carrying Context Capsules that INFORM but NEVER AUTHORIZE work**. It opens no
live external effect, executes no tool, mutates no product database, and emits no
secret material. The product runtime under `finalis/` never imports it
(`tools/context_governance/__init__.py`).

Every artifact — entitlement, version vector, snapshot, lease, evidence record,
claim, minimal basis, provenance edge, view, ABI rendering, consumption receipt,
Context BOM and the capsule itself — digests a **canonical serialization** (sorted
keys, compact separators, `allow_nan=False`) via `canon.canonical_json` /
`canon.hash_obj`, so roots are bit-reproducible and any material input change moves
the capsule root.

---

## 1. The pipeline

The end-to-end orchestrator is `governance.build_capsule(request, *, generator_id,
checker_id)`. It runs the stages below in order, is **fail-closed at every stage**,
and produces a capsule **only when the resulting `Report` is valid (zero P0 and zero
P1 findings)**. Any P0/P1 withholds the capsule and returns a non-`SEALED` state.

| # | Stage | Mechanism (module.function) | What it enforces |
|---|-------|------------------------------|------------------|
| 0 | **Boundary firewall** | `boundary.boundary_findings` over `requested_operations` (default `["PURE_COMPUTE"]`) | Only pure in-process computation is permitted; any forbidden or unrecognized operation is a P0 (fail-closed; `classify_effect` also returns `UNKNOWN` for a non-string operation). |
| 1 | **Entitlement before retrieval** | `entitlement.check_entitlement` | Tenant / principal / provider account / purpose / operation class must all match and the entitlement must be unexpired; any mismatch is a P0. |
| 2 | **Snapshot / version vector / lease / TOCTOU** | `entitlement.snapshot`, `.version_vector`, `.issue_lease`, `.revalidate`, `.toctou_findings` | Binds an exact version vector; at consumption re-derives the vector, classifies each delta, and blocks on an expired lease or an UNKNOWN critical delta. |
| 3 | **Evidence-before-belief + four-valued claims** | `evidence.evidence_record`, `.claim`, `.claim_findings` | Immutable content-addressed evidence is recorded before any derived claim; claims are four-valued; a critical claim not `SUPPORTED_ONLY` is surfaced (P1), never silently resolved. |
| 4 | **Taint + authority air-gap + memory quarantine** | `evidence.taint_findings`, `.authority_air_gap`, `.memory_findings` | Unremoved `SUSPECTED_INJECTION`/`QUARANTINED` taint is flagged; any record asserting authority whose channel is not `AUTHORITY` is rejected (a missing channel fails closed); auto-admitted memory writeback is forbidden. `model.taint_join` treats an unrecognized taint label as most-severe (fail-closed). |
| 5 | **Requirement hypergraph + minimal bases** | `requirements.evaluate_requirement`, `.requirement_findings` | Each requirement is a hyperedge over atoms; computes minimal support / refutation / missing-evidence bases and the satisfaction verdict with an independence floor. |
| 6 | **Mandatory reservation** | `requirements.reserve_mandatory` | Reserves each mandatory requirement's cheapest minimal support basis **before** any budgeted selection so a token budget can never evict safety-critical context. |
| 7 | **Robust submodular selection + VOI** | `requirements.robust_select`, `.selection_findings`, `.voi_retrieval`, `.voi_findings` | Greedy worst-case-over-scenarios coverage under a hard token budget; reserved claims are pre-committed and never dropped; VOI never stops while a mandatory atom is unmet. |
| 7b | **Anytime-valid / conformal statistics** | `requirements.statistics_findings` (over `conformal_interval`; also `eprocess_wealth`, `anytime_decision`) | Optional stopping is valid (e-process); a conformal guarantee broken by distribution shift is disabled and surfaced, never silently assumed. |
| 8 | **Claim-preserving compaction** | `compile.compaction`, `.compaction_findings` | A summary is admissible only if it preserves every critical claim's polarity, four-valued state, quantity/unit, scope, provenance **and taint** (stripping taint off a critical claim is `COMPRESSION_TAINT_STRIPPED`); a lost invariant is a P0. |
| 9 | **Conflict-preserving branch/merge** | `compile.branch`, `.merge_branches`, `.merge_findings` | Conflicting hypotheses stay separate; a critical atom supported on one branch and refuted on another is a preserved conflict (P0), never a false consensus. |
| 10 | **Least-privilege views + noninterference + privacy** | `compile.compile_view`, `.noninterference`, `.view_findings`, `.privacy_budget`, `.privacy_exposure`, `.privacy_findings` | Per-consumer projections dropping non-granted and forbidden fields; a high-sensitivity input may not change a low view's bytes; the privacy budget is a non-compensatory vector, and an exposure on an unknown axis has no budget and fails closed. |
| 11 | **ABI render + consumption receipt** | `compile.render_abi`, `.consumption_receipt`, `.receipt_findings` | Deterministic byte rendering; the receipt binds the exact bytes; a missing provider length is UNKNOWN (fail-closed), a mismatch is truncation DETECTED. |
| 12 | **Proof of non-use** | `compile.proof_of_non_use`, `.non_use_findings` | An excluded item is certified non-influential only if the counterfactual output (item withheld) is byte-identical to the delivered output. |
| 13 | **Capsule body + certificate (GENERATOR)** | `capsule.context_bom`, `.risk_envelope`, `.tcb_manifest`, `.build_capsule`, `.certify_capsule` | Assembles the informs-not-authorizes body plus BOM, risk envelope and TCB manifest; the generator produces the certificate global root (whose class roots include a `BODY` root over the **entire** canonical body), a secret-free assertion (secret markers are scanned in keys **and string values**), and a well-formedness assertion against the closed `ALLOWED_BODY_KEYS` allowlist. |
| 14 | **Independent checker + replay + TCB + transparency** | `capsule.check_capsule`, `.capsule_findings`, `.replay_twin`, `.replay_findings`, `.transparency_receipt`, `.robustness_frontier` | A byte-independent checker re-derives every root from the body alone, recomputes `body_hash` (`body_hash_ok`), enforces the closed body shape (`well_formed` / `disallowed_keys`), rejects any body key hinting at authority/grant/approval, and rejects self-certification; the replay twin must reproduce the identical root. |

The orchestrator returns `{"report", "valid", "state", "capsule", "check",
"reservation", "selection", "evaluations", "result_hash"}`. `capsule` is non-null
only when the report is valid and a snapshot + version vector were supplied; if the
independent check itself produces findings the capsule is dropped and the state
becomes `CERTIFICATE_INVALID`.

---

## 2. Module-by-module reference

| Module | Responsibility | Key public functions |
|--------|----------------|----------------------|
| `canon` | Deterministic canonical JSON, SHA-256, Context Merkle Forest; identity vs. volatile hashing; content addressing; commitments. | `canonical_json`, `sha256_hex`, `hash_obj`, `strip_volatile`, `core_hash`, `merkle_root`, `class_root`, `global_root`, `content_address`, `commitment` |
| `model` | Closed vocabulary: four-valued lattice, taint lattice, channels, view/consumer classes, all state machines, reason-code registry, Finding/Report. | `claim_state`, `closes_critical`, `taint_join`, `Finding`, `Report`, `report`; constants `CLAIM_STATES4`, `TAINT_LEVELS`, `CHANNELS`, `VIEW_CLASSES`, `REASON_CODES`, the `*_STATES` machines |
| `entitlement` | Entitlement graph, point-in-time snapshot, version vector, snapshot lease, TOCTOU revalidation + delta certificate, cache coherency. | `entitlement`, `check_entitlement`, `version_vector`, `snapshot`, `issue_lease`, `revalidate`, `cache_key`, `cache_reusable`, `toctou_findings` |
| `evidence` | Evidence-first store, paraconsistent four-valued claim ledger, provenance/influence/common-mode graphs, semantic taint, authority air-gap, memory-writeback quarantine. | `evidence_record`, `claim`, `claim_findings`, `provenance_edge`, `provenance_root`, `common_mode_graph`, `independence_class`, `propagate_taint`, `taint_findings`, `authority_air_gap`, `memory_candidate`, `memory_findings` |
| `requirements` | Requirement hypergraph, minimal support/refutation/missing bases, mandatory reservation, robust submodular selection, VOI retrieval, anytime-valid & conformal diagnostics. | `requirement`, `evaluate_requirement`, `requirement_findings`, `reserve_mandatory`, `robust_select`, `selection_findings`, `voi_retrieval`, `voi_findings`, `eprocess_wealth`, `anytime_decision`, `conformal_interval`, `statistics_findings` |
| `compile` | Claim-preserving compaction, conflict-preserving branch/merge, least-privilege views + noninterference, non-compensatory privacy budget, proof-of-non-use, model-context ABI + consumption receipt + truncation detection. | `compaction`, `compaction_findings`, `branch`, `merge_branches`, `merge_findings`, `compile_view`, `noninterference`, `view_findings`, `privacy_budget`, `privacy_exposure`, `privacy_findings`, `proof_of_non_use`, `non_use_findings`, `render_abi`, `consumption_receipt`, `receipt_findings` |
| `capsule` | Context BOM, risk envelope, TCB manifest, capsule body + certificate (generator), independent certificate checker (closed body shape, full-body root, secret value scan), SCITT transparency projection, robustness frontier, replay twin. | `bom_entry`, `context_bom`, `risk_envelope`, `tcb_manifest`, `build_capsule`, `certify_capsule`, `check_capsule`, `capsule_findings`, `transparency_receipt`, `robustness_frontier`, `replay_twin`, `replay_findings`; constant `ALLOWED_BODY_KEYS` |
| `governance` | End-to-end orchestrator binding every subsystem into one proof-carrying result; fail-closed at each stage; capsule emitted only when valid. | `build_capsule` |
| `boundary` | Live-effect firewall: classifies requested operations, permits only `PURE_COMPUTE`, refuses everything else (fail-closed on UNKNOWN). | `classify_effect`, `boundary_findings`, `assert_pure`; constants `FORBIDDEN_EFFECTS`, `PERMITTED_EFFECTS` |
| `validate` | Invariant self-check executed by construction against the kernel primitives; surfaces any regression as an INV-* finding. Enumerates 17 invariants, including INV-22 (unrecognized taint label treated as most-severe) and INV-29 (closed-shape capsule body). | `self_check`, `validate`; constant `INVARIANTS` |
| `cli` / `__main__` | Read-only CLI (`validate`, `invariants`, `info`) emitting canonical JSON to stdout; opens no external effect. | `main` |

---

## 3. Determinism & content addressing

- `canon.canonical_json` fixes serialization (`sort_keys=True`,
  `separators=(",",":")`, `allow_nan=False`); `hash_obj` is SHA-256 over it.
- `strip_volatile` removes presentation-only keys (`display_name`, `observed_at`,
  `created_at`, `issued_at`, `consumed_at`, ...) so `core_hash` captures identity
  independent of timestamps. Snapshot roots, lease hashes and claim hashes are
  computed over the object **excluding** their volatile timestamp field
  (`entitlement.snapshot` excludes `created_at`; `issue_lease` excludes
  `consumption_count`; `evidence.claim` excludes `observed_at`).
- The Merkle forest layers per-class roots: `class_root` sorts leaves for
  order-independence within a class; `global_root` binds the sorted class roots.
  `capsule._capsule_roots` derives `CLAIMS`, `SCOPE`, `BOM`, `RISK`, `TCB` **and a
  `BODY` root** from the body alone, and `certify_capsule` seals them with
  `global_root` and records `body_hash`. The `BODY` root is a hash over the
  **entire** canonical body, so every field — including `support_bases` and
  `compiler_version` — is bound; changing any body field moves the capsule root
  (red-team hardening: previously only a field subset was bound).
- `content_address` prefixes `cid-`; `commitment` is a hiding+binding hash that
  never publishes the secret.

Because the checker re-derives roots purely from the capsule body, and the replay
twin recomputes from the same snapshot, the guarantee is independently verifiable
and reproducible.
