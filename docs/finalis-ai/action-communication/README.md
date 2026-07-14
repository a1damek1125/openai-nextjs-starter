# Finalis Action & Communication Engine — Module Documentation

> **Mission**: this is the **execution layer** of Finalis. The Case Graph knows
> what happened, the Completion Loop knows what should happen next — **this
> engine executes safely**. It turns a Next-Best-Action proposal into a real
> message, callback, handoff, or internal task, and it does so through a fixed
> safety pipeline: gate → consent → rate limit → route → compose → (human
> approval) → durable schedule → send → delivery tracking → Case Graph update →
> audit. Nothing reaches a client without passing every stage.

## The core principle: infrastructure never decides

Temporal schedules, Chatwoot converses, provider adapters deliver — **none of
them decides**. Every decision (may this action run? on which channel? with
what text? does a human need to see it first?) is made in the Finalis brain:
`ActionGateService`, `ConsentPermissionService`, `RateLimitSpamGuard`,
`ChannelRouter`, `MessageComposer`, and the human-approval queue. The gate,
approval, and audit steps are **always in the path** — the adapters in
`finalis/actions/adapters.py` state this explicitly ("None of these adapters
makes decisions — the Finalis brain (gate/approval/audit) is always upstream")
and the engine enforces it: a blocked or rejected action is never silent; every
decision point appends to the tamper-evident, hash-chained `AuditLog`
(`finalis/audit.py`, `verify_chain()` asserted in the E2E tests).

## Status (honest)

| Layer | Status | Proof |
|---|---|---|
| Engine core (`finalis/actions/engine.py`: `ActionCommunicationEngine.handle` 10-step pipeline, `decide_approval`, `record_delivery`) | **Implemented and tested** | 25 tests in `tests/test_action_communication.py` (20 mandated cases + 3 E2E scenarios) |
| Services (`finalis/actions/services.py`: ChannelRouter, MessageComposer + forbidden-pattern guard, ConsentPermissionService, RateLimitSpamGuard, UploadLinkGenerator) | **Implemented and tested** | Router preference/opt-out/fallback tests; composer price-injection rejection; rate-limit and client-reply-pause tests; full upload-link lifecycle test |
| Data model (`finalis/actions/models.py`: ActionRequest, MessageDraft, ActionExecution, DeliveryEvent, UploadLink, ConsentPreference, ChannelPreference, RateLimitRule) | **Implemented and tested** | Exercised by every engine test; in-memory dataclasses today, persistence lands behind the same shapes |
| Durable workflows (Temporal) | **Mocked** — `TemporalMock` behind the `WorkflowAdapter` protocol: schedule + simulated-clock `advance_to`, state as plain data (the restart-survival property Temporal provides for real) | `test_12_temporal_mock_schedules_and_fires`, `test_business_hours_defer_via_temporal` |
| Multichannel delivery | **Mocked** — `NovuMock` behind the `NotificationAdapter` protocol. **Note**: after the technology decision (see `technology-decision-record.md`), Novu is replaced by a thin direct provider-adapter layer; `NovuMock` is therefore the mock of that *generic delivery-adapter seam*, not of Novu specifically. The protocol (`send(channel, recipient, text, tenant_id) -> {ok, provider_message_id}`) is what production adapters implement. | `test_13_novu_mock_sends`, `test_provider_failure_uses_fallback_channel` |
| Human handoff (Chatwoot) | **Mocked** — `ChatwootMock.create_handoff` creates a conversation with the AI summary as a private note + labels | `test_14_chatwoot_mock_creates_handoff` |
| Real providers (Meta WhatsApp Cloud API, Twilio SMS/WhatsApp, SES/SendGrid, Slack/Teams), real Temporal cluster, real Chatwoot instance | **Designed** — production swaps the transport behind the protocols, not the engine | `technology-decision-record.md`, `architecture.md` |

**Test command and result** (branch `claude/finalis-action-communication-engine`):

```
$ python3 -m pytest tests/ -q
185 passed in 0.27s

$ python3 -m pytest tests/test_action_communication.py -q
25 passed in 0.06s
```

## The 19-doc action-communication set

Five module docs (this directory) plus the fourteen canonical specs they refine:

| # | File | What it is |
|---|---|---|
| 1 | `action-communication/README.md` | This index: mission, honest status, core principle |
| 2 | `action-communication/technology-decision-record.md` | The ADR: options A–F scored, license matrix, the Novu challenge, final stack, revisit triggers |
| 3 | `action-communication/architecture.md` | Pipeline diagram mapped to `engine.handle` steps 1–10; the 15 core services mapped to code; 17-action-type status table |
| 4 | `action-communication/channel-router.md` | Routing inputs/outputs as coded; `CHANNEL_PRIORITY` verbatim; consent exclusion; fallback behaviour |
| 5 | `action-communication/message-composer.md` | Template catalog verbatim; forbidden-pattern guard; high-risk skeletons; production template/LLM plan |
| 6 | `../01-modules-and-features.md` | Canonical module catalog (Action & Communication Engine scope) |
| 7 | `../03-case-lifecycle-state-machine.md` | Per-state action catalog the engine executes against |
| 8 | `../04-data-model.md` | Canonical entities (ActionRequest, MessageDraft, AuditEvent, ...) |
| 9 | `../05-algorithms-and-scoring.md` | NBA utility scoring that produces the actions this engine executes |
| 10 | `../09-completion-loop-followup-promises.md` | The upstream loop that emits `ActionRequest`s |
| 11 | `../12-integrations.md` | Integration surface (channels, providers, webhooks) |
| 12 | `../13-autonomy-and-safety.md` | Autonomy levels L1–L5 and always-HITL actions the gate enforces |
| 13 | `../18-technology-stack.md` | Stack context the ADR extends |
| 14 | `../21-state-of-the-art-technology-review.md` | Prior technology survey the ADR supersedes for this module |
| 15 | `../22-api-and-event-model.md` | Event model the audit events align to |
| 16 | `../31-completion-loop-verification.md` | Loop verification (anti-spam invariants shared with this engine) |
| 17 | `../34-production-readiness-matrix.md` | Production-readiness criteria this module reports against |
| 18 | `../case-graph/action-gate.md` | The ActionGate this engine reuses (`finalis/case_services.py::ActionGateService`) |
| 19 | `../case-graph/audit-events.md` | Audit-event vocabulary this engine extends (MESSAGE_*, HUMAN_APPROVAL_*, UPLOAD_LINK_*, TEMPORAL_*, CHATWOOT_*) |

## How it connects

- **Upstream**: the Completion Loop (`finalis/completion_loop.py`) and NBA
  service propose actions; each proposal arrives here as an `ActionRequest`
  (`source="completion_loop"`, `proposed_by="ai"`).
- **Safety**: the engine reuses the Case Graph's `ActionGateService`
  (ALLOW / BLOCK / REQUIRE_HUMAN_APPROVAL / ABSTAIN_MISSING_DATA) — one gate,
  one autonomy model, one audit log across modules.
- **Downstream**: delivery events flow back through `record_delivery`, client
  uploads resolve `MissingItem`s via `MissingInfoService.resolve`, and every
  step lands in the shared hash-chained audit timeline the dashboard reads.
