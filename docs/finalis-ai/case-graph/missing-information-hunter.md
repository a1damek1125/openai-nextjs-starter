# Case Graph — Missing Information Hunter

> **Ground truth**: `finalis/case_services.py` (`MissingInfoService`,
> `HVAC_REQUIRED_INFO`, `SEVERITY_WEIGHT`), branch
> `claude/finalis-case-graph-completion-loop`, 160 tests passing.
> Spec: `docs/finalis-ai/05-algorithms-and-scoring.md` §2 (MIS),
> `docs/finalis-ai/09-completion-loop-followup-promises.md`.

## 1. The HVAC required-info profile AS CODED

`HVAC_REQUIRED_INFO` is a plain list of dicts — the first industry profile,
registered as `MissingInfoService.PROFILES = {"hvac": HVAC_REQUIRED_INFO}`:

| `type` | `severity` | `blocks_state` | `recommended_question` (Polish, client-facing) | `recommended_channel` | `auto_allowed` |
|---|---|---|---|---|---|
| `client_contact` | high | — | "Jak możemy się z Panem/Panią skontaktować?" | `phone` | true |
| `address` | high | `QUOTE_PREPARATION` | "Proszę o adres inwestycji do wyceny." | `sms_or_whatsapp` | true |
| `service_type` | high | `QUOTE_PREPARATION` | "Jakiej usługi dotyczy zapytanie?" | `phone` | true |
| `installation_photo` | high | `QUOTE_PREPARATION` | "Proszę wysłać zdjęcie obecnej instalacji i tabliczki znamionowej urządzenia." | `sms_or_whatsapp` | true |
| `urgency` | medium | — | "Jak pilna jest sprawa?" | `phone` | true |
| `preferred_date` | medium | — | "Jaki termin by Panu/Pani odpowiadał?" | `sms_or_whatsapp` | true |

Severity maps to the MIS business weight `w_i` (doc 05 §2) via
`SEVERITY_WEIGHT = {"high": 0.9, "medium": 0.5, "low": 0.2}`.

## 2. Detection logic

`detect(case, known_facts, *, industry="hvac", audit)`:

1. Look up the industry profile (`KeyError` for an unregistered industry —
   there is no silent fallback).
2. A fact is **present** iff `known_facts[type] not in (None, "", [], {})` —
   empty strings/lists/dicts do not count as answers.
3. For every profile entry that is absent **and not already tracked**
   (dedup on `field_key` against `case.missing_items`), create a
   `MissingItem(field_key, label=recommended_question, weight=SEVERITY_WEIGHT[severity],
   blocks_quote=(blocks_state == "QUOTE_PREPARATION"))`.
4. If anything was created, emit **one** consolidated `MISSING_INFO_DETECTED`
   audit event (`actor="ai"`, payload lists all created keys) — matching
   doc 05 §2's "one consolidated request per contact, never field-by-field spam".

No-duplicate behavior is pinned by
`tests/test_case_graph_services.py::TestMissingInfoService::test_no_duplicate_detection`
(second `detect` on the same case returns `[]`). Profile detection is pinned by
`test_detect_from_hvac_profile` (contact + service_type known → exactly
`{address, installation_photo, urgency, preferred_date}` created).

## 3. Resolution flow

`resolve(case, field_key, *, audit, source="client")`:

- Finds the first matching item with `status != "received"`, sets
  `status = "received"`, emits `MISSING_INFO_RESOLVED` with **`actor=source`**
  (so the timeline shows *who* supplied the fact), and bumps
  `case.last_progress_at = utcnow()` — which directly lowers the next
  StuckScore sweep (doc 05 §9).
- Returns `True` on success, `False` if nothing matched or the item was already
  received — idempotent, safe to call from duplicate webhook deliveries.

## 4. Blockers: `blocks_quote` gates `QUOTE_PREPARATION`

`open_blockers(case)` returns items with `status != "received"` and
`blocks_quote=True`. For HVAC that is `address`, `service_type`, and
`installation_photo` while unresolved.

**Honest scope note**: the state machine itself does not read
`missing_items`; the gate is enforced by the caller checking
`open_blockers(case) == []` before transitioning to `QUOTE_PREPARATION` — this
is exactly how the 23-step E2E does it (steps 13–15: photo resolved but address
open → case stays `WAITING_FOR_CLIENT_INFO`; address resolved →
`open_blockers == []` → `QUALIFIED` → `QUOTE_PREPARATION`). Pinned by
`test_blockers_block_and_resolution_unblocks` and
`TestE2EHvacLifecycle::test_full_lifecycle`.

## 5. Upstream feeds

**Voice** (`finalis/voice/extractor.py`, `engine.py`,
`conversation_intelligence.py`): the live extractor's `missing_items()` compares
extracted utterance fields against `REQUIRED_FIELDS_HVAC`; `installation_photo`
is *always* reported missing during a call ("photos can't arrive during a call —
a photo-send promise covers the request path but the item stays missing"). At
session end the engine appends the corresponding `MissingItem`s to
`case.missing_items` (weight 0.9 high / 0.5 otherwise, `blocks_quote` from the
voice spec's `blocks == "quote_preparation"`) and emits `MISSING_INFO_DETECTED`;
Conversation Intelligence recommends `send_missing_info_request` as the next
action when items remain.

**OCR / documents** (`finalis/documents.py::ingest_document`): the document
confidence gate feeds the hunter in two ways — (a) a scan below `QUALITY_GATE`
marks the whole document `needs_rescan` and emits `document.needs_rescan`,
i.e. the needed fact is still missing and a clearer copy must be requested;
(b) an **accepted** field (confidence ≥ θ_conf) is the evidence with which a
caller resolves the matching item via `MissingInfoService.resolve(case, key,
source=...)`. There is no automatic key-matching wire from `ingest_document`
to `resolve()` yet — resolution is caller-driven in the scaffold (as in the
E2E, where the arriving photo is resolved explicitly). This matches doc 22's
design where the Missing-Info Hunter consumes `document.received` /
`document.analysis_completed` as a candidate-match consumer.

**NBA consumption**: open `installation_photo` / `address` items are precisely
what enumerates `send_photo_request` / `ask_for_missing_info` candidates in
`NextBestActionService` (see `next-best-action.md`).

## 6. Extending to new industries — profiles are data

A new vertical needs **zero engine code**: author a list of spec dicts with the
same six keys (`type`, `severity`, `blocks_state`, `recommended_question`,
`recommended_channel`, `auto_allowed`) and register it:

```python
MissingInfoService.PROFILES["real_estate"] = REAL_ESTATE_REQUIRED_INFO
```

Detection, dedup, weighting, blocker gating, resolution, and audit all come for
free because they only read the profile shape. This is the executable form of
doc 05's "weights live in `IndustryPlaybook` (JSON) so verticals differ without
code changes"; in production the profile rows load from the playbook store
instead of a module constant, behind the same `detect/resolve/open_blockers`
signatures.

## 7. Test coverage

| Behavior | Test (`tests/test_case_graph_services.py` unless noted) |
|---|---|
| Profile detection with known facts | `TestMissingInfoService::test_detect_from_hvac_profile` |
| Blockers gate + resolution unblocks + `MISSING_INFO_RESOLVED` count | `TestMissingInfoService::test_blockers_block_and_resolution_unblocks` |
| No duplicate items on re-detect | `TestMissingInfoService::test_no_duplicate_detection` |
| Full lifecycle: detect → request → resolve → unblock | `TestE2EHvacLifecycle::test_full_lifecycle` (steps 3, 11–15) |
| MIS math (Σw=0 guard, HVAC vector 1.3/3.4) | `tests/test_scoring.py::TestMIS` |
| Voice-side derivation | `tests/test_voice_engine.py`, `tests/test_conversation_intelligence.py` |
