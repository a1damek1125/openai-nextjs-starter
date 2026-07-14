# TOOL-B10 Acceptance Matrix

Acceptance-criteria **families** grouped by subsystem, mapped to the module and
public functions that satisfy them, with an honest coverage flag. Every row is backed
by code in `tools/context_governance/`. "Covered" means the behavior is implemented
and self-contained in the reference kernel (standard-library-only, deterministic, no
external effect). Where a capability is intentionally an optional external adapter,
it is noted rather than claimed as covered.

| Family | Subsystem | Module → public functions | Covered |
|--------|-----------|-----------------------------|---------|
| A | **Canon / hashing** | `canon` → `canonical_json`, `sha256_hex`, `hash_obj`, `strip_volatile`, `core_hash`, `merkle_root`, `class_root`, `global_root`, `content_address`, `commitment` | yes |
| B | **Model / four-valued lattice** | `model` → `claim_state`, `closes_critical`, `CLAIM_STATES4`, `SUPPORTED_ONLY`/`REFUTED_ONLY`/`BOTH`/`NEITHER`; `Finding`, `Report`, `report`, `REASON_CODES` | yes |
| C | **Entitlement before retrieval** | `entitlement` → `entitlement`, `check_entitlement` (tenant/principal/account/purpose/operation/expiry, all P0 on mismatch) | yes |
| D | **Snapshot / version vector** | `entitlement` → `version_vector`, `snapshot` (root excludes volatile `created_at`) | yes |
| E | **Lease / TOCTOU firewall** | `entitlement` → `issue_lease`, `revalidate` (delta certificate + verdict), `toctou_findings`; verdicts from `model.TOCTOU_VERDICTS` | yes |
| F | **Delta materiality classification** | `entitlement` → `_classify_delta` via `revalidate`; `CRITICAL_COMPONENTS`, `NONMATERIAL_CANDIDATES`; `model.DELTA_CLASSES` (unknown component ⇒ UNKNOWN ⇒ BLOCKED) | yes |
| G | **Cache coherency** | `entitlement` → `cache_key`, `cache_reusable` (exact scope+vector, ACTIVE, non-expired) | yes |
| H | **Evidence-before-belief store** | `evidence` → `evidence_record` (immutable, content-addressed, INFORMATION channel, tainted) | yes |
| I | **Paraconsistent claim ledger** | `evidence` → `claim`, `claim_findings` (critical not-`SUPPORTED_ONLY` ⇒ `CLAIM_BOTH`/`CLAIM_NEITHER`) | yes |
| J | **Provenance / influence graph** | `evidence` → `provenance_edge`, `provenance_root` | yes |
| K | **Common-mode / independence** | `evidence` → `common_mode_graph`, `independence_class`; `model.INDEPENDENCE` | yes |
| L | **Semantic taint** | `evidence` → `propagate_taint`, `taint_findings`; `model.taint_join`, `TAINT_LEVELS` (an unrecognized label is treated as most-severe, fail-closed) | yes |
| M | **Authority air-gap** | `evidence` → `authority_air_gap` (any authority-asserting record whose channel is not `AUTHORITY` is rejected; missing channel fails closed); `model.CHANNELS`; reinforced by `capsule.check_capsule` (`informs_only`) | yes |
| N | **Memory-writeback quarantine** | `evidence` → `memory_candidate` (starts QUARANTINED), `memory_findings`; `model.MEMORY_STATES` | yes |
| O | **Requirement hypergraph** | `requirements` → `requirement`, `evaluate_requirement`, `requirement_findings` | yes |
| P | **Minimal support / refutation / missing bases** | `requirements` → `_min_bases` via `evaluate_requirement` (`minimal_support_bases`, `minimal_refutation_bases`, `missing_evidence_bases`); `model.BASIS_TYPES` | yes |
| Q | **Independence floor** | `requirements` → `_independent_producers`, `min_independent`; finding `COMMON_MODE_SUPPORT_INSUFFICIENT` | yes |
| R | **Mandatory reservation** | `requirements` → `reserve_mandatory` (cheapest basis, `unreservable_requirements`) | yes |
| S | **Robust submodular selection** | `requirements` → `robust_select`, `_coverage_value`, `_robust_value`, `selection_findings` (budget + reserved subset checks) | yes |
| T | **Value-of-information retrieval** | `requirements` → `voi_retrieval`, `voi_findings` (never stops with mandatory atom unmet) | yes |
| U | **Anytime-valid monitoring** | `requirements` → `eprocess_wealth`, `anytime_decision` (optional-stopping-valid e-process) | yes |
| V | **Conformal + shift guard** | `requirements` → `conformal_interval`, `statistics_findings` (shift disables guarantee, fail-closed) | yes |
| W | **Claim-preserving compaction** | `compile` → `compaction`, `compaction_findings` (polarity/state/quantity/unit/scope/provenance/**taint** — a stripped taint set on a critical claim is `COMPRESSION_TAINT_STRIPPED`) | yes |
| X | **Conflict-preserving branch/merge** | `compile` → `branch`, `merge_branches`, `merge_findings` (critical conflicts preserved, no authority amplification) | yes |
| Y | **Least-privilege views** | `compile` → `compile_view`, `_VIEW_GRANTS`, `_FORBIDDEN_FIELDS`, `view_findings`; `model.VIEW_CLASSES`, `CONSUMER_CLASSES` | yes |
| Z | **Noninterference** | `compile` → `noninterference`, `view_findings` (`NONINTERFERENCE_FAILED`) | yes |
| AA | **Non-compensatory privacy budget** | `compile` → `privacy_budget`, `privacy_exposure`, `privacy_findings` (per-axis, no cross-axis offset; an exposure on an unknown axis fails closed) | yes |
| AB | **Proof of non-use** | `compile` → `proof_of_non_use`, `non_use_findings` (counterfactual byte-identity) | yes |
| AC | **Model-context ABI render** | `compile` → `render_abi`, `ABI_VERSION`, `SUPPORTED_ABI` (deterministic canonical bytes) | yes |
| AD | **Consumption receipt / truncation** | `compile` → `consumption_receipt`, `receipt_findings`; `model.TRUNCATION_STATES` (UNKNOWN fail-closed) | yes |
| AE | **Context BOM** | `capsule` → `bom_entry`, `context_bom` (ordered, `bom_root`) | yes |
| AF | **Risk envelope** | `capsule` → `risk_envelope` (residual risk carried with capsule) | yes |
| AG | **Capsule body + certificate** | `capsule` → `build_capsule`, `certify_capsule` (`informs_not_authorizes`; `global_root` incl. a `BODY` root over the entire canonical body, recorded as `body_hash`; secret-free assertion over keys **and** string values; closed shape via `ALLOWED_BODY_KEYS` — `well_formed`/`disallowed_keys`) | yes |
| AH | **Independent certificate checker** | `capsule` → `check_capsule`, `capsule_findings` (root_ok/class_ok/`body_hash_ok`/secret_free/`well_formed`+`disallowed_keys`/informs_only — rejects any body key hinting at authority/grant/approval — /independent) | yes |
| AI | **Replay twin** | `capsule` → `replay_twin`, `replay_findings` (determinism, `CAPSULE_REPLAY_DIVERGED`) | yes |
| AJ | **Context TCB manifest** | `capsule` → `tcb_manifest`, `TCB_COMPONENTS` (missing ⇒ incomplete, fail-closed) | yes |
| AK | **Transparency projection (SCITT-style)** | `capsule` → `transparency_receipt` (content commitment only, no signature material) | yes |
| AL | **Robustness frontier** | `capsule` → `robustness_frontier` (holds_under / breaks_under per scenario) | yes |
| AM | **Boundary / live-effect firewall** | `boundary` → `classify_effect` (a non-string operation ⇒ `UNKNOWN`, fail-closed), `boundary_findings`, `assert_pure`; `FORBIDDEN_EFFECTS`, `PERMITTED_EFFECTS` | yes |
| AN | **Invariant self-check** | `validate` → `self_check`, `validate`, `INVARIANTS` (17 self-checked invariants, incl. INV-22 unrecognized-taint fail-closed and INV-29 closed-shape body) | yes |
| AO | **End-to-end orchestration** | `governance` → `build_capsule` (fail-closed pipeline; capsule only when valid) | yes |
| AP | **Read-only CLI** | `cli`/`__main__` → `main` (`validate`, `invariants`, `info`; canonical JSON; pure) | yes |
| AQ | **Secret-free / no provider tokens** | `capsule` → `_scan_secret_free` (secret markers scanned in keys **and** string values via `_SECRET_VALUE_MARKERS`); `compile` → `_FORBIDDEN_FIELDS`; `boundary` `SECRET_EMIT`/`CREDENTIAL_READ` forbidden | yes |
| AR | **Deterministic identity & content addressing** | `canon` → `hash_obj`, `class_root`, `global_root`, `content_address`; volatile-stripped roots throughout | yes |
| AS | **Reason-code registry & findings discipline** | `model` → `REASON_CODES`, `_require`, `Finding.__post_init__`, `Report.valid` (valid iff zero P0/P1) | yes |

## Notes on honesty

- The rows above are **implemented in the reference kernel** and exercised by the
  kernel's own primitives; the self-check (`validate.self_check`) directly asserts
  the load-bearing invariants (four-valued lattice, taint join incl. unrecognized-
  label fail-closed, boundary classification, non-compensatory privacy, view
  leakage, generator non-self-certification, full-body root binding, closed-shape
  body).
- Capabilities the roadmap explicitly designates as **optional external adapters** —
  live MCP/A2A servers, external transparency-log services, external SMT solvers —
  are **not** part of the reference kernel and are **not** claimed here; the kernel
  produces the content commitments (`transparency_receipt`) and structural checks
  those adapters would consume, without opening any external effect.
- `governance.build_capsule` binds families C..AL into one result and withholds the
  capsule on any P0/P1 finding, so the acceptance families compose rather than being
  independently reachable only in isolation.
