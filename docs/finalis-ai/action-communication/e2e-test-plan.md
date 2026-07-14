# Action & Communication Engine — E2E Test Plan (as executed)

> Ground truth: `tests/test_action_communication.py` on branch
> `claude/finalis-action-communication-engine` — **25 tests, all passing**
> (`python3 -m pytest tests/test_action_communication.py` → `25 passed`; full repo suite
> `185 passed`). This is not a plan for future tests; sections 1–3 map the three mandated
> E2E scenarios to the test code that already runs them, step by step. Fixtures: simulated
> clock `T0 = 2026-07-07 11:00` (inside the 8–21 business window), tenant `hvac-1`,
> autonomy L3 default, all adapters deterministic mocks.

---

## 1. Scenario 1 — Missing photo follow-up → `test_17_e2e_missing_photo_followup`

The full loop: brain detects a missing item → safe ask with upload link → client
uploads → Case Graph resolves → everything audited on one verifiable chain.

| # | Step (spec) | Where it executes in the test / code |
|---|---|---|
| 1 | Case has open `MissingItem`s that block the quote | `case.missing_items = [installation_photo (blocks_quote), address (blocks_quote)]` |
| 2 | `ActionRequest(send_photo_request, purpose=installation_photo)` submitted | `eng.handle(case, req("send_photo_request", recipient=..., purpose=...), ...)` → audit `ACTION_REQUESTED` |
| 3 | ActionGate evaluates and allows (low-risk, L3) | `engine.handle` step 3 → `gate.evaluate` → `ALLOW` → audit `ACTION_CREATED` |
| 4 | Channel routed by priority + preference (whatsapp first) | `router.route("send_photo_request", prefs, [])` → whatsapp, fallback sms |
| 5 | Consent + business hours pass (`T0`=11:00, no opt-outs) | `consent.check` → `consent_ok` |
| 6 | Rate limit passes (first touch) | `rate.check` → `ok` |
| 7 | Expiring upload link minted; only token hash stored | `uploads.create(purpose="installation_photo")` → audit `UPLOAD_LINK_CREATED`; asserted `out.upload_url` contains `upload.finalis.example` |
| 8 | Polish draft composed with the link embedded | `composer.compose` → audit `MESSAGE_DRAFT_CREATED`; asserted `out.upload_url in out.draft.final_text` |
| 9 | Sent via provider adapter; execution recorded; cadence follow-up scheduled | `_send` → `novu.send` ok → audit `NOVU_NOTIFICATION_TRIGGERED`, `MESSAGE_SENT`, `TEMPORAL_WORKFLOW_STARTED`; asserted `out.status == "executed"` |
| 10 | Provider delivery webhook arrives | `eng.record_delivery(out.execution, status="delivered", provider_message_id="novu-1")` → audit `MESSAGE_DELIVERED` |
| 11 | Client opens the link (T0+3h, within 72h TTL) | `eng.uploads.open(token, T0+3h)` → status `OPENED` → audit `UPLOAD_LINK_OPENED` |
| 12 | Client uploads a valid file (image/jpeg, 3.2 MB ≤ 25 MB cap) | `eng.uploads.use(token, T0+4h, mime="image/jpeg", size_mb=3.2)` → status `USED` → audit `UPLOAD_LINK_USED` |
| 13 | Case Graph updated: missing item resolved, completion loop notified | `MissingInfoService.resolve(case, "installation_photo", audit=eng.audit, source="upload")` → audit `MISSING_INFO_RESOLVED` |
| 14 | Remaining gaps stay open (no over-resolution) | asserted: only `address` still unresolved |
| 15 | Audit completeness + integrity | asserted: all **8 event types** present — `ACTION_REQUESTED`, `UPLOAD_LINK_CREATED`, `MESSAGE_DRAFT_CREATED`, `MESSAGE_SENT`, `MESSAGE_DELIVERED`, `UPLOAD_LINK_OPENED`, `UPLOAD_LINK_USED`, `MISSING_INFO_RESOLVED` — and `eng.audit.verify_chain()` is true |

## 2. Scenario 2 — Offer follow-up after 72h silence → `test_18_e2e_offer_followup_after_72h`

| # | Step | Test/code |
|---|---|---|
| 1 | Offer sent, no client response for 72h | `t = T0 + 72h` (the completion loop's cadence trigger, simulated by clock) |
| 2 | `send_follow_up_after_offer` requested, client prefers email | `eng.handle(case, req("send_follow_up_after_offer", recipient=...), prefs=prefs(preferred_channel="email"), now=t)` |
| 3 | Gate allows (low risk); routing honors the client's preferred channel | asserted `out.execution.channel == "email"` |
| 4 | Polite Polish follow-up composed — no price, no pressure | asserted `"ofert" in out.draft.final_text` (and composer forbids prices by construction — see test_8) |
| 5 | Sent immediately (within window), **no human approval involved** | asserted `out.status == "executed"` and `not eng.approval_queue` |
| 6 | Chain verifies | asserted `eng.audit.verify_chain()` |

## 3. Scenario 3 — High-risk price negotiation needs approval → `test_19_e2e_high_risk_approval_flow`

| # | Step | Test/code |
|---|---|---|
| 1 | High-value case (25 000), autonomy L4 | `case = make_case(4); case.value_estimate = 25000` |
| 2 | `send_price_negotiation` requested with `risk="high"` | `eng.handle(...)` — gate maps it to `send_out_of_rule_price` → `REQUIRE_HUMAN_APPROVAL` |
| 3 | Draft is a human-edit skeleton (composer never writes a price); queued, not sent | asserted `out.status == "pending_approval"`; audit `HUMAN_APPROVAL_REQUESTED` |
| 4 | Human (`owner-1`) approves | `eng.decide_approval(out.approval_id, approver="owner-1", decision="approve", now=T0)` → audit `HUMAN_APPROVAL_GRANTED` with approver identity |
| 5 | Only then does the send happen | asserted `final.status == "executed"`; audit `MESSAGE_SENT` |
| 6 | Full audit trail asserted | `HUMAN_APPROVAL_REQUESTED`, `HUMAN_APPROVAL_GRANTED`, `MESSAGE_SENT` all present |

(The edit-before-approve variant — human rewrites the AI skeleton, `edited_text`
preserved next to the immutable AI `text` — is covered by `test_16`; rejection with a
recorded reason by `test_reject_records_reason`.)

---

## 4. The 20 mandated test cases

All in `tests/test_action_communication.py`; every row **PASSING**.

| # | Mandated case | Test | Status |
|---|---|---|---|
| 1 | ActionRequest created and audited | `test_1_action_request_created_and_audited` | PASSING |
| 2 | Gate allows low-risk action | `test_2_gate_allow_low_risk` | PASSING |
| 3 | Gate blocks on opted-out case | `test_3_gate_block_on_optout_case` | PASSING |
| 4 | Gate requires approval for high risk | `test_4_gate_requires_approval_for_high_risk` | PASSING |
| 5 | Router prefers client's channel | `test_5_prefers_client_channel` | PASSING |
| 6 | Router falls back when preferred unavailable | `test_6_falls_back_when_preferred_unavailable` | PASSING |
| 7 | Missing-photo message in Polish with upload link | `test_7_missing_photo_message_polish_with_link` | PASSING |
| 8 | Composer never invents a price (incl. hostile variables) | `test_8_composer_never_invents_price` | PASSING |
| 9 | Consent gate blocks opt-out | `test_9_consent_gate_blocks_optout` | PASSING |
| 10 | Rate limit prevents duplicate follow-up | `test_10_rate_limit_prevents_duplicate_followup` | PASSING |
| 11 | Upload link lifecycle (create/open/use/expire/bad-MIME) | `test_11_expiring_link_lifecycle` | PASSING |
| 12 | Temporal mock schedules and fires durable work | `test_12_temporal_mock_schedules_and_fires` | PASSING |
| 13 | Novu mock sends (owner notify → inbox) | `test_13_novu_mock_sends` | PASSING |
| 14 | Chatwoot mock creates handoff with AI summary | `test_14_chatwoot_mock_creates_handoff` | PASSING |
| 15 | Delivery event updates execution status | `test_15_delivery_event_updates_status` | PASSING |
| 16 | Approve with human edit, then send | `test_16_approve_edit_and_send` | PASSING |
| 17 | E2E scenario 1 (missing photo, full loop) | `test_17_e2e_missing_photo_followup` | PASSING |
| 18 | E2E scenario 2 (72h offer follow-up) | `test_18_e2e_offer_followup_after_72h` | PASSING |
| 19 | E2E scenario 3 (high-risk approval) | `test_19_e2e_high_risk_approval_flow` | PASSING |
| 20 | Audit written for all important steps + chain verify | `test_20_audit_written_for_all_important_steps` | PASSING |

## 5. Cross-cutting verifications (the 5 additional tests, 25 total)

| Verification | Test | What it proves |
|---|---|---|
| No duplicate follow-up | `test_10` (+ cooldown/`max_attempts`/daily-limit logic in `RateLimitSpamGuard`) | Second identical ask 1h later is blocked `rate_limited:*` and audited `FOLLOW_UP_RATE_LIMITED` |
| Opt-out blocks at routing layer | `test_optout_channel_excluded` | Opted-out channel never selected; router picks next permitted |
| Opt-out blocks everything (`any`) | `test_9` | Blanket opt-out → `no_permitted_channel`, hard block, audited |
| Business-hours deferral (not drop) | `test_business_hours_defer_via_temporal` | 23:00 send → `deferred`, durable `FollowUpWorkflow` scheduled, `ACTION_SCHEDULED` audited |
| Client reply pauses cadence | `test_client_reply_pauses_followups` | `record_delivery(status="replied")` → later follow-up blocked `paused_client_replied` |
| Provider failure → channel fallback | `test_provider_failure_uses_fallback_channel` | whatsapp down → sent via sms, `retry_count == 1`, still `executed` |
| Rejection is never silent | `test_reject_records_reason` | Reject → `REJECTED` status + `HUMAN_APPROVAL_REJECTED` with reason |
| No price promise | `test_8` + high-risk template design (`[SZKIC DO EDYCJI PRZEZ CZŁOWIEKA]`) | Composer raises `MessageComposeError` on smuggled prices; price-bearing drafts are human-edit skeletons |
| Audit completeness + tamper evidence | `test_17`, `test_18`, `test_20` (`verify_chain()`) | Every important step has an event; the shared hash chain verifies end-to-end |

## 6. Next stages (not yet executed)

1. **Real provider sandbox tests** — swap `NovuMock`/`ChatwootMock`/`TemporalMock` for
   sandbox-backed adapters (direct WhatsApp BSP / SMS / SMTP per the provider decision,
   Chatwoot dev instance, Temporal dev cluster) and re-run this exact suite; the
   adapters are behind `Protocol`s, so the tests should pass unchanged except timing.
2. **Webhook signature tests** — once `/webhooks/delivery-status` exists: valid
   signature accepted; missing/invalid/stale/replayed signature → 401 + security audit
   event; idempotent redelivery.
3. **Load / concurrency tests** — parallel `handle` calls on one case must not defeat
   the rate limiter (today's in-memory dict is not thread-safe — known gap); approval
   queue race (approve twice concurrently → exactly one send); per-tenant fairness
   under one noisy tenant.
4. **Idempotency tests** — same `Idempotency-Key` twice → one send, replayed response.
5. **Property/fuzz tests** — fuzzed cadence configs can never exceed `max_attempts`;
   fuzzed variables can never get a forbidden pattern past the composer.
