# TOOL-B10 Security Constraints

The FINALIS Context Governance kernel operates under a set of **hard constraints**.
Each is enforced structurally — by construction in the code, not by convention — so a
violation surfaces as a P0 finding or is impossible to express. This document restates
each constraint and cites the module/function that enforces it.

The kernel is a deterministic, standard-library-only reference package
(`tools.context_governance`). It is **never imported by product runtime** under
`finalis/` (`tools/context_governance/__init__.py`), so it cannot alter production
behavior.

| # | Hard constraint | Structural enforcement (module.function) |
|---|-----------------|-------------------------------------------|
| 1 | **ZERO live external effects.** Only pure, in-process, deterministic computation is permitted. | `boundary.PERMITTED_EFFECTS = {"PURE_COMPUTE"}`; `boundary.classify_effect` returns `UNKNOWN` (fail-closed) for anything else; `boundary.boundary_findings` emits `LIVE_EFFECT_ATTEMPTED`/`BOUNDARY_VIOLATION` (P0); `boundary.assert_pure`. The module imports no network/filesystem-mutating/subprocess/provider client. |
| 2 | **ZERO tool / MCP / A2A execution.** | `boundary.FORBIDDEN_EFFECTS` includes `TOOL_EXECUTION`, `MCP_CALL`, `A2A_CALL`, `SUBPROCESS`; classified `FORBIDDEN` ⇒ P0 via `boundary.boundary_findings`. |
| 3 | **ZERO email / Slack / calendar / payment / CRM mutation.** | `boundary.FORBIDDEN_EFFECTS` includes `EMAIL_SEND`, `SLACK_POST`, `TEAMS_POST`, `CALENDAR_WRITE`, `PAYMENT`, `CRM_MUTATION`; any occurrence ⇒ `LIVE_EFFECT_ATTEMPTED` (P0). |
| 4 | **ZERO production credentials.** No credential read; no filesystem write. | `boundary.FORBIDDEN_EFFECTS` includes `CREDENTIAL_READ`, `FILESYSTEM_WRITE`; classified `FORBIDDEN` ⇒ P0. |
| 5 | **ZERO secret material in context.** The capsule body and every view are structurally secret-free. | `capsule._scan_secret_free` + `capsule.check_capsule` (`secret_free`) ⇒ `PROVIDER_TOKEN_IN_CAPSULE` (P0); `compile._FORBIDDEN_FIELDS` + `compile.compile_view` / `view_findings` ⇒ `VIEW_LEAKAGE` (P0); `boundary.FORBIDDEN_EFFECTS` includes `SECRET_EMIT`. Key markers scanned: `provider_token`, `secret`, `api_key`, `credential`, `authority_grant`, `answer_key`, `raw_secret`, `password`, `private_key`. String **values** are also scanned against `capsule._SECRET_VALUE_MARKERS` (e.g. `sk-`, `bearer `, `-----begin`, `access_token`), closing the red-team gap where a secret hid under an innocuous key. The body is additionally a **closed shape**: any key outside `capsule.ALLOWED_BODY_KEYS` fails `well_formed` ⇒ `CAPSULE_CERTIFICATE_INVALID` (P0). |
| 6 | **ZERO context item treated as authority.** External/INFORMATION content never confers permission. | `evidence.evidence_record` stamps `channel="INFORMATION"`; `evidence.authority_air_gap` flags **any** record asserting authority whose channel is not `AUTHORITY` — a missing channel fails closed ⇒ `AUTHORITY_INFERENCE_REJECTED` (P0); `capsule.check_capsule` requires `informs_not_authorizes` true and rejects any body key hinting at authority/grant/approval/permission/entitle_action (`informs_only`); the closed `ALLOWED_BODY_KEYS` allowlist blocks such keys structurally. |
| 7 | **ZERO memory / document treated as approval.** | `evidence.authority_air_gap` (air-gap on information channel); `capsule.build_capsule` sets `informs_not_authorizes=True` and carries no approval grant; `capsule.capsule_findings` rejects an authority-asserting capsule (P0). |
| 8 | **ZERO cross-tenant / principal / account / purpose flow.** | `entitlement.check_entitlement` (tenant, principal, provider account, purpose, operation class — each mismatch is P0: `SOURCE_TENANT_MISMATCH`, `SOURCE_ACCOUNT_MISMATCH`, `SOURCE_PURPOSE_MISMATCH`, `ENTITLEMENT_MISSING`); `entitlement.cache_key` + `cache_reusable` require an exact scope+vector match, making cross-scope reuse structurally impossible. |
| 9 | **ZERO automatic memory writeback / lesson promotion.** | `evidence.memory_candidate` starts `state="QUARANTINED"`, `auto_admitted=False`, ignoring `work_succeeded`; `evidence.memory_findings` ⇒ `MEMORY_WRITEBACK_QUARANTINED` (P0) if auto-admitted; `boundary.FORBIDDEN_EFFECTS` includes `MEMORY_WRITEBACK`. |
| 10 | **ZERO provider tokens in capsules.** | `capsule._scan_secret_free` (marker `provider_token`); `capsule.check_capsule` (`secret_free`) ⇒ `PROVIDER_TOKEN_IN_CAPSULE` (P0); `compile.render_abi`/`consumption_receipt` render only view fields and byte hashes, never tokens. |
| 11 | **No DB migration — frontier stays v20.** | `boundary.FORBIDDEN_EFFECTS` includes `DB_MIGRATION`; the kernel adds no migration and product runtime under `finalis/` never imports it (`__init__.py`). Recorded in `TOOL_B10_VERIFIED_BASELINE.md` (MIGRATION_FRONTIER v20). |
| 12 | **Product remains NOT_PRODUCTION_READY.** The kernel is a self-contained reference/proof artifact, not a wired-in runtime component. | Package docstring in `__init__.py` ("never imported by product runtime"); every module reiterates "reference kernel only … opens no external effect"; nothing in `finalis/` imports `tools.context_governance`. |

## Enforcement posture

- **Fail-closed by default.** Anything unrecognized is refused, not allowed:
  `boundary.classify_effect` returns `UNKNOWN` (P0) for unknown operations — and for
  a **non-string** operation; `entitlement._classify_delta` returns `UNKNOWN` (⇒
  `BLOCKED`) for unknown vector components; `compile.consumption_receipt` returns
  `UNKNOWN` truncation (P1) when the provider length is missing;
  `capsule.tcb_manifest` marks the TCB incomplete when a component is absent;
  `model.taint_join` treats an unrecognized taint label as most-severe;
  `compile.privacy_exposure` treats an exposure on an unknown axis as an overrun
  with limit 0; `evidence.authority_air_gap` rejects an authority-asserting record
  with a missing channel.
- **Validity gate.** `model.Report.valid` is true only with **zero P0 and zero P1**
  findings; `governance.build_capsule` emits a capsule only when the report is valid,
  and drops it (state `CERTIFICATE_INVALID`) if the independent check finds anything.
- **Self-verifying.** `validate.self_check` asserts the load-bearing constraints by
  construction (boundary classification, secret-free/independent capsule
  certification, full-body root binding, closed-shape body, non-compensatory
  privacy, view leakage, four-valued lattice, taint join incl. unrecognized-label
  fail-closed) — 17 invariants enumerated in `validate.INVARIANTS`, including
  INV-22 (taint fail-closed) and INV-29 (closed-shape body) — so a regression in
  any of these surfaces as an `INV-*` finding via
  `python -m tools.context_governance validate`.
- **No emitted secrets or signatures.** `capsule.transparency_receipt` emits only a
  content commitment (no signature material); `canon.commitment` binds a secret
  without publishing it; the CLI (`cli.main`) emits canonical JSON of identity /
  invariants / self-check results and asserts purity before running.
