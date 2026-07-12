# TOOL-B10 Invariants

The kernel enforces its guarantees **by construction**: each invariant is realized
by a specific primitive, and the self-check in `validate.py` exercises the load-
bearing ones so a regression surfaces as an `INV-*` finding rather than a silently
weakened guarantee. `validate.INVARIANTS` enumerates the self-checked set; this
document mirrors that set and expands it with the full mechanism.

The `validate.INVARIANTS` tuple (17 invariants, self-checked in
`validate.self_check`):

```
INV-01 capsule informs, never authorizes
INV-02 no live external effect
INV-03 unknown operation fails closed
INV-04 capsule body is secret-free
INV-10 four-valued: BOTH is not TRUE
INV-11 four-valued: NEITHER is not FALSE
INV-12 only SUPPORTED_ONLY closes a critical requirement
INV-13 truthy-string is not support
INV-20 taint join takes the more severe level
INV-21 taint survives transformation unless removal proven
INV-22 unrecognized taint label is treated as most-severe (fail-closed)
INV-25 generator cannot self-certify
INV-26 recomputed capsule root binds the ENTIRE body
INV-27 privacy budget is non-compensatory
INV-28 mandatory reservation precedes budgeted selection
INV-29 capsule body is a closed shape (no smuggled keys)
INV-30 view leakage of a forbidden field is rejected
```

> **Note (red-team hardening).** INV-22 and INV-29 were added after a red-team
> pass, and INV-26 was strengthened from binding a field subset to binding the
> **entire** canonical body via a dedicated `BODY` root.

---

## Four-valued claim lattice

**Statement.** Claims track support and refutation independently over four values —
`SUPPORTED_ONLY` (1,0), `REFUTED_ONLY` (0,1), `BOTH` (1,1), `NEITHER` (0,0). `BOTH`
is not TRUE and `NEITHER` is not FALSE; a **critical** requirement is satisfied only
by `SUPPORTED_ONLY`.

**Where enforced.** `model.claim_state` (strict `is True` on both booleans — a
truthy string is not support, INV-13); `model.closes_critical` returns true only for
`SUPPORTED_ONLY` (INV-10/11/12). Consumed by `evidence.claim` /
`evidence.claim_findings`, and by `requirements._atom_support` (only
`SUPPORTED_ONLY` claims discharge an atom for critical satisfaction).

**How it fails closed.** A critical claim in `BOTH` or `NEITHER` cannot discharge its
atom, leaving the atom unmet; `evidence.claim_findings` emits `CLAIM_BOTH` /
`CLAIM_NEITHER` (P1) and the contradiction stays visible — contradictions are never
silently resolved.

## Authority air-gap

**Statement.** External / INFORMATION-channel content can never create authority.
Documents, tool outputs and memory INFORM; they never AUTHORIZE.

**Where enforced.** `evidence.evidence_record` stamps every external record with
`channel="INFORMATION"`; `evidence.authority_air_gap` rejects **any** record that
carries `asserts_authority` while its channel is not `"AUTHORITY"` — a missing or
unknown channel fails closed. The capsule reinforces this: the body sets
`informs_not_authorizes=True` and `capsule.check_capsule` requires it to be true and
rejects any body key hinting at authority (`authority`, `grant`, `approval`,
`permission`, `entitle_action`); the closed `ALLOWED_BODY_KEYS` allowlist already
blocks such keys, so this check is defence in depth (INV-01).

> **Note (red-team hardening).** The air-gap previously keyed on the INFORMATION
> channel only; it now flags any authority-asserting record whose channel is not
> `"AUTHORITY"`, so a record with a missing channel cannot slip through.

**How it fails closed.** A record asserting authority yields
`AUTHORITY_INFERENCE_REJECTED` (P0); a capsule that asserts authority fails the
independent check and is withheld.

## TOCTOU fail-closed

**Statement.** A snapshot binds an exact version vector; at consumption the current
vector is recomputed and each delta classified. An expired lease, a material delta,
or an **UNKNOWN** critical delta blocks.

**Where enforced.** `entitlement.revalidate` compares snapshot vs. current vector,
classifies each changed component with `_classify_delta` (critical components →
`MATERIAL_RECOMPILE`; nonmaterial candidates → allowed or `MATERIAL_REQUALIFY`; any
**unrecognized** component → `UNKNOWN`), and returns `BLOCKED` on expiry or on any
`UNKNOWN` delta. `entitlement.toctou_findings` turns `BLOCKED` into
`TOCTOU_REVALIDATION_FAILED` (P0). Cache reuse via `entitlement.cache_reusable`
requires an exact scope+vector key, `ACTIVE` state, and non-expiry.

**How it fails closed.** Unknown component ⇒ `UNKNOWN` ⇒ `BLOCKED`; the default for
an unrecognized delta is to block, not to allow.

## Taint survival

**Statement.** Semantic taint joins to the more severe level and survives
paraphrase / summary / translation until removal is **proven**.

**Where enforced.** `model.taint_join` returns the higher-ranked level over the
lattice `UNTAINTED < EXTERNAL < TOOL_OUTPUT < UNTRUSTED_DERIVED <
SUSPECTED_INJECTION < QUARANTINED` (INV-20), and ranks an **unrecognized** taint
label above every known level, so it is treated as most-severe and can never be
silently dropped to `UNTAINTED` (INV-22, fail-closed; red-team hardening).
`evidence.propagate_taint` joins all input taints and only clears when
`removal_proven=True` (INV-21). `evidence.taint_findings` flags claims carrying
`SUSPECTED_INJECTION` / `QUARANTINED`.

**How it fails closed.** A transformation does not clear taint by default; an
unremoved critical-claim taint is P0 (P1 for non-critical), so tainted content cannot
quietly launder into a clean claim. Compaction cannot launder taint either:
`compile.compaction` flags a changed `taint_refs` set on a critical claim as
`COMPRESSION_TAINT_STRIPPED` (P0 via `compile.compaction_findings`).

## Non-compensatory privacy exposure

**Statement.** The privacy exposure budget is a vector over independent axes (`pii`,
`financial`, `health`, `biometric`, `location`, `cross_tenant`); slack on one axis
can never offset an overrun on another.

**Where enforced.** `compile.privacy_exposure` compares each axis independently
against `compile.privacy_budget`; any single axis over limit produces an overrun
(INV-27). `compile.privacy_findings` emits `PRIVACY_EXPOSURE_EXCEEDED` (P0) per
overrun.

**How it fails closed.** `within_budget` is `not over` — a single overrun fails the
whole check regardless of headroom elsewhere. An exposure on an axis **outside** the
known vector has no budget and is treated as an overrun with limit 0 rather than
being silently ignored (red-team hardening).

## Mandatory reservation precedes selection

**Statement.** Every mandatory requirement's minimal support basis is reserved
**before** any budget-driven selection; a token budget can never evict a
safety-critical claim.

**Where enforced.** `requirements.reserve_mandatory` picks the cheapest minimal
support basis per mandatory requirement (INV-28); `requirements.robust_select`
pre-commits the reserved set and never drops it; `requirements.selection_findings`
verifies the reserved set is a subset of the selected set.

**How it fails closed.** If a mandatory requirement has no reservable basis →
`MANDATORY_REQUIREMENT_MISSING` (P0); if reservation exceeds the budget →
`CONTEXT_BUDGET_INSUFFICIENT` (P0, `budget_ok=False`); if a reserved claim is missing
from the selection → `MANDATORY_RETRIEVAL_STOPPED` (P0). VOI retrieval
(`requirements.voi_retrieval`) likewise refuses to stop while a mandatory atom is
unmet, and `voi_findings` flags a stop with unmet mandatory atoms (P0).

## Generator cannot self-certify

**Statement.** The party that builds the certificate cannot also accept it; a
byte-independent checker must re-derive every root from the capsule body alone.

**Where enforced.** `capsule.certify_capsule` records `generator_id`;
`capsule.check_capsule` recomputes `_capsule_roots` and the `global_root` from the
body, and accepts only if the root matches, class roots match, the recomputed `BODY`
hash matches the certificate's `body_hash` (`body_hash_ok`), the body is
secret-free **and** well-formed (closed shape, `disallowed_keys` empty),
informs-not-authorizes holds, **and** `checker_id != generator_id` (INV-25/26/29).
`capsule.capsule_findings` emits `GENERATOR_SELF_CERTIFICATION` (P0) when the ids
collide.

**How it fails closed.** In the self-check, a capsule checked by its own generator is
rejected; only a distinct checker accepts a valid capsule. In `governance.build_capsule`
any capsule finding drops the capsule and sets state `CERTIFICATE_INVALID`.

## Recomputed capsule root binds the ENTIRE body

**Statement.** The capsule root is a deterministic function of the body; **every**
body field is bound (not just a subset), any material change moves the root, and the
replay twin must reproduce it.

**Where enforced.** `capsule._capsule_roots` + `certify_capsule` (`global_root` over
`CLAIMS`/`SCOPE`/`BOM`/`RISK`/`TCB`/`BODY`, where `BODY` is a hash over the entire
canonical body, so every field — including `support_bases` and `compiler_version` —
is bound; the certificate also records it as `body_hash`); `check_capsule`
re-derives and compares, returning `body_hash_ok` alongside `root_ok`/`class_ok`
(INV-26); `capsule.replay_twin` recomputes from the same body and flags divergence.

**How it fails closed.** A root or body-hash mismatch →
`CAPSULE_CERTIFICATE_INVALID` (P0); a divergent replay → `CAPSULE_REPLAY_DIVERGED`
(P0).

> **Note (red-team hardening).** The certificate previously bound only a field
> subset via the structural class roots; the `BODY` root now covers the entire
> canonical body, and the independent checker returns the extra fields
> `body_hash_ok`, `well_formed` and `disallowed_keys`.

## Capsule body is a closed shape (no smuggled keys)

**Statement.** The capsule body admits **only** the keys in
`capsule.ALLOWED_BODY_KEYS`; nothing (an authority grant, an extra proof field) can
be smuggled into the body after certification.

**Where enforced.** `capsule._disallowed_body_keys` lists keys outside the
allowlist; `certify_capsule` records `well_formed` / `disallowed_keys`;
`check_capsule` recomputes them independently and refuses acceptance when any
disallowed key is present (INV-29).

**How it fails closed.** A body key outside the allowlist →
`CAPSULE_CERTIFICATE_INVALID` (P0) via `capsule.capsule_findings`, and the capsule
is withheld. Added after the red-team pass (the allowlist fails CLOSED).

## Capsule body is secret-free / no provider tokens

**Statement.** The capsule body carries no provider token, secret, api key,
credential, authority grant, answer key, password or private key.

**Where enforced.** `capsule._scan_secret_free` walks the body and flags any secret
marker appearing as a **key** or in a **string value** (`_SECRET_VALUE_MARKERS`,
e.g. `sk-`, `bearer `, `-----begin`, `access_token`); `certify_capsule` records
`secret_free`; `check_capsule` re-scans independently (INV-04). Views apply the same
discipline: `compile.compile_view` drops `_FORBIDDEN_FIELDS` and reports
`leaked_forbidden`.

> **Note (red-team hardening).** Value scanning was added to close the gap where a
> secret hid under an innocuous key name.

**How it fails closed.** A secret marker in the body → `PROVIDER_TOKEN_IN_CAPSULE`
(P0); a forbidden field in a view → `VIEW_LEAKAGE` (P0, INV-30).

## Capsule informs, never authorizes

**Statement.** A Context Capsule contains no authority grant; it is evidence-carrying
context that informs downstream work but confers no permission.

**Where enforced.** `capsule.build_capsule` sets `informs_not_authorizes=True`;
`capsule.check_capsule` requires it true and rejects any body key hinting at
authority (`authority`, `grant`, `approval`, `permission`, `entitle_action`) —
defence in depth on top of the closed `ALLOWED_BODY_KEYS` allowlist (INV-01);
`capsule.capsule_findings` emits `AUTHORITY_INFERENCE_REJECTED` (P0) otherwise. This
is the structural complement of the authority air-gap at the evidence layer.

**How it fails closed.** A capsule asserting authority fails the independent check and
is never sealed.

## No live external effect

**Statement.** The kernel performs only pure, in-process, deterministic computation;
network, messaging, payment, CRM mutation, tool/MCP/A2A execution, subprocess,
filesystem write, DB migration, credential read, memory writeback and secret emit are
all structurally forbidden.

**Where enforced.** `boundary.FORBIDDEN_EFFECTS` / `PERMITTED_EFFECTS` +
`boundary.classify_effect`; `boundary.boundary_findings` emits
`LIVE_EFFECT_ATTEMPTED` (P0) for a forbidden op and `BOUNDARY_VIOLATION` (P0) for an
UNKNOWN op (INV-02/03). `boundary.assert_pure` is true only if every op is
`PURE_COMPUTE`; the CLI asserts purity before running.

**How it fails closed.** `classify_effect` returns `UNKNOWN` for anything not
explicitly permitted — including a **non-string** operation (red-team hardening) —
and UNKNOWN is a P0: the default is refusal, not execution.
The module imports no network, filesystem-mutating, subprocess or provider client,
and the package is never imported by product runtime.

## Memory quarantine cannot self-release

**Statement.** A memory-writeback candidate starts `QUARANTINED`; successful work
does not auto-admit it.

**Where enforced.** `evidence.memory_candidate` sets `state="QUARANTINED"` and
`auto_admitted=False` regardless of `work_succeeded`; `evidence.memory_findings`
emits `MEMORY_WRITEBACK_QUARANTINED` (P0) if any candidate is `auto_admitted`.

**How it fails closed.** There is no code path that promotes a candidate on success;
auto-admission is only ever a violation, never an outcome.
