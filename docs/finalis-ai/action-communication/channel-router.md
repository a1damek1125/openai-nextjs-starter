# ChannelRouter — routing rules as coded

Code: `finalis/actions/services.py::ChannelRouter` (+ `CHANNEL_PRIORITY`).
Status: **Implemented and tested** (`TestChannelRouter`, plus the engine-level
provider-failure fallback test). The router picks *where* a message goes; it
never decides *whether* it goes — the gate, consent check, and rate limiter do
that (see `architecture.md`, steps 3–6).

## Inputs and outputs

```python
ChannelRouter().route(action_type: str,
                      prefs: ChannelPreference,
                      consents: list[ConsentPreference]) -> RouteDecision
```

- **`action_type`** — selects the priority order from `CHANNEL_PRIORITY`.
- **`prefs: ChannelPreference`** — `preferred_channel` (default `"whatsapp"`),
  `available_channels` (default `("whatsapp", "sms", "email")`),
  `preferred_time_window`, `do_not_contact` (the last two are enforced by
  `ConsentPermissionService`, not the router).
- **`consents: list[ConsentPreference]`** — per-channel `opted_in` /
  `opted_out` records; channel may be a concrete channel or `"any"`.
- **Returns `RouteDecision`**: `channel` (primary, or `None`), `fallback`
  (next candidate, or `None`), `reason`
  (`"priority_order_for_<action_type>"` or `"no_permitted_channel"`), and
  `provider` (`"mock"` today; the production adapter name after the swap).

## The `CHANNEL_PRIORITY` table (verbatim from source)

```python
CHANNEL_PRIORITY = {
    # message type -> ordered channel preference (spec §ChannelRouter)
    "send_photo_request": ["whatsapp", "sms", "email", "phone_callback"],
    "send_document_request": ["whatsapp", "email", "sms", "phone_callback"],
    "ask_for_missing_info": ["whatsapp", "sms", "email"],
    "send_address_request": ["whatsapp", "sms", "email"],
    "send_follow_up_after_offer": ["whatsapp", "email", "sms"],
    "send_upload_link": ["whatsapp", "sms", "email"],
    "confirm_document_received": ["whatsapp", "sms", "email"],
    "notify_owner": ["inbox", "email", "slack"],
    "handoff_to_human": ["chatwoot", "internal_task", "phone_callback"],
    "schedule_callback": ["internal_task"],
}
```

Unknown action types fall back to the default order
`["whatsapp", "sms", "email"]`.

## The algorithm, in order

1. **Start from the action type's priority order** (or the default).
2. **Client-preference override**: if `prefs.preferred_channel` appears in the
   order, it is moved to the front — the rest of the order is preserved behind
   it. A preference for a channel *not* in the order does **not** inject it
   (the action-type policy stays authoritative).
   Tested: `send_photo_request` with `preferred_channel="sms"` routes
   `channel="sms"`, `fallback="whatsapp"` (test 5).
3. **Availability filter**: a candidate survives if it is in
   `prefs.available_channels` **or** is one of the always-eligible
   internal/system channels: `inbox`, `chatwoot`, `internal_task`,
   `phone_callback`, `slack`, `email` (these don't require the client to have
   registered them as reachable channels).
   Tested: preferred `whatsapp` but `available_channels=("sms","email")` →
   routes `sms` (test 6).
4. **Consent-aware exclusion**: every channel with an `opted_out` consent is
   removed, and an opt-out on **`"any"` kills all candidates** — the router
   returns `RouteDecision(None, None, "no_permitted_channel")` and the engine
   blocks with an `ACTION_GATE_BLOCK` audit event.
   Tested: whatsapp opt-out → routes `sms` (`test_optout_channel_excluded`);
   `any` opt-out → engine outcome `blocked`, reason `no_permitted_channel`
   (test 9).
5. **Fallback selection**: `fallback` is simply the **second surviving
   candidate** (`candidates[1]`), or `None` if only one channel survives.

## Provider-failure fallback (engine-level)

Routing produces the plan; `engine._send` executes it. If the primary
channel's provider send fails (`{"ok": False, ...}`) **and** a fallback exists,
the engine increments `execution.retry_count`, switches
`execution.channel` to the fallback, and sends again. If that also fails, the
execution is marked `failed`, a `MESSAGE_FAILED` audit event is written, and
the outcome is `blocked` with reason `delivery_failed` — never a silent drop.

Tested (`test_provider_failure_uses_fallback_channel`): with the whatsapp
provider down (`fail_channels={"whatsapp"}`), a `send_photo_request` still
executes — `execution.channel == "sms"`, `execution.retry_count == 1`.

In production this single in-process retry is the *channel*-level fallback;
*attempt*-level retries and timeouts per provider call are supplied by Temporal
activity retry policies (Designed — see the ADR), so the router and adapters
stay free of retry logic.

## Spec channel-priority examples — confirmed in code

| Spec example | `CHANNEL_PRIORITY` entry | Confirmed |
|---|---|---|
| Missing photo: WhatsApp → SMS → Email → phone callback | `send_photo_request: ["whatsapp", "sms", "email", "phone_callback"]` | Yes — verbatim |
| Owner alert: inbox → email → Slack | `notify_owner: ["inbox", "email", "slack"]` | Yes — verbatim |
| Human handoff: Chatwoot → internal task → phone callback | `handoff_to_human: ["chatwoot", "internal_task", "phone_callback"]` | Yes — verbatim (note: the engine short-circuits `handoff_to_human` straight to the Chatwoot adapter at step 1; the internal-task and callback fallbacks apply when Chatwoot is unavailable — that fallback wiring is Designed) |

## Production notes (Designed)

- `RouteDecision.provider` becomes the concrete adapter name (Meta Cloud API,
  Twilio, SES/SendGrid, Slack) selected per tenant.
- Per-tenant channel enablement (e.g. a tenant without a WhatsApp number)
  folds into `available_channels` at load time — no router change needed.
- WhatsApp-first defaults assume an approved Meta template exists for the
  message type (see the ADR's WhatsApp provisioning section); if no approved
  template covers a business-initiated send outside the 24 h window, the
  router's WhatsApp candidate must be skipped at adapter level and the
  fallback used.
