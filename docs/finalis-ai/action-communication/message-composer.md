# MessageComposer — templates, safety guard, drafting rules

Code: `finalis/actions/services.py::MessageComposer` (+ `TEMPLATES`,
`FORBIDDEN_PATTERNS`, `MessageComposeError`).
Status: **Implemented and tested** (`TestMessageComposer`, plus draft-audit and
approval-flow assertions in the engine tests).

The composer's contract: deterministic templates in, a stored-and-audited
`MessageDraft` out — and it **never writes prices, discounts, guarantees, or
legal/contract language**, no matter what variables it is handed.

## Template catalog (verbatim from source)

Keys are `(action_type, language)`; today's catalog is Polish-first with two
English variants.

```python
TEMPLATES: dict[tuple[str, str], str] = {
    ("send_photo_request", "pl"): (
        "Dzień dobry, zgodnie z rozmową proszę o przesłanie zdjęcia obecnej "
        "instalacji oraz tabliczki znamionowej urządzenia. To pozwoli "
        "przygotować dokładniejszą wycenę.{upload_suffix}"),
    ("send_photo_request", "en"): (
        "Hello, as discussed, please send a photo of the current installation "
        "and the device nameplate so we can prepare an accurate quote."
        "{upload_suffix}"),
    ("send_address_request", "pl"): (
        "Dzień dobry, do przygotowania wyceny potrzebujemy jeszcze adresu "
        "inwestycji. Proszę o wiadomość zwrotną."),
    ("ask_for_missing_info", "pl"): (
        "Dzień dobry, do przygotowania wyceny brakuje nam jeszcze: {items}. "
        "Proszę o wiadomość zwrotną."),
    ("send_follow_up_after_offer", "pl"): (
        "Dzień dobry, chciałem zapytać, czy miał Pan chwilę spojrzeć na "
        "ofertę. Jeżeli są pytania albo chce Pan porównać zakres prac, "
        "chętnie pomożemy."),
    ("send_follow_up_after_offer", "en"): (
        "Hello, I wanted to check whether you had a moment to look at our "
        "offer. Happy to answer any questions or compare the scope of work."),
    ("confirm_document_received", "pl"): (
        "Dziękujemy, otrzymaliśmy przesłane materiały. Wracamy z wyceną "
        "najszybciej jak to możliwe."),
    ("handoff_to_human", "pl"): (
        "Dziękuję za zgłoszenie. Przekazuję sprawę koledze/koleżance z "
        "zespołu — skontaktujemy się najszybciej jak to możliwe."),
    ("mark_recovery_later", "pl"): (
        "Rozumiem, wrócimy do tematu w dogodniejszym terminie. Odezwiemy się "
        "zgodnie z ustaleniem."),
    # High-risk drafts are skeletons the HUMAN must edit before approval —
    # the composer never writes prices, discounts, or contract language.
    ("send_price_negotiation", "pl"): (
        "[SZKIC DO EDYCJI PRZEZ CZŁOWIEKA] Dzień dobry, wracam do tematu "
        "naszej oferty. {human_must_complete}"),
    ("send_contract_response", "pl"): (
        "[SZKIC DO EDYCJI PRZEZ CZŁOWIEKA] Dzień dobry, w sprawie umowy: "
        "{human_must_complete}"),
    ("send_quote_status_update", "pl"): (
        "Dzień dobry, pracujemy nad Pana wyceną i wrócimy z nią zgodnie z "
        "ustaleniem."),
}
```

Variable slots the composer fills: `{upload_suffix}` (rendered as
`" Link do dodania zdjęć: <url>"` when an upload link exists, empty
otherwise), `{items}` (comma-joined list, defaulting to `"informacji"` when
empty), and `{human_must_complete}` (defaulting to
`"(treść do uzupełnienia przez człowieka przed wysyłką)"`).

## The forbidden-pattern guard (price / advice safety)

```python
FORBIDDEN_PATTERNS = ["zł", "PLN", "EUR", "€", "$",       # no invented prices
                      "guarantee you", "gwarantuję, że",   # no overpromising
                      "legal advice", "porada prawna"]
```

After rendering, the composer lowercases the final text and raises
`MessageComposeError("forbidden content: <pattern>")` if any forbidden pattern
appears in the rendered text **without also appearing in the template
itself** — i.e. templates are trusted (they are code-reviewed and contain none
of these patterns today), but **variables are not**: anything injected at
runtime (an NBA payload, an upstream extraction, a future LLM suggestion) that
smuggles a price or advice phrase kills the compose outright rather than being
sent.

**Tested** (`test_8_composer_never_invents_price`):

- The rendered offer-follow-up contains no price-like string
  (`\d+\s*(zł|PLN|EUR|€)` asserted absent).
- Injecting `variables={"items": ["rabat 500 zł"]}` into
  `ask_for_missing_info` **raises `MessageComposeError`** — a discount amount
  cannot enter a client message through the variable side door.

## High-risk skeleton templates

`send_price_negotiation` and `send_contract_response` deliberately render as
**skeletons prefixed `[SZKIC DO EDYCJI PRZEZ CZŁOWIEKA]`** ("draft to be edited
by a human"). The composer contributes only a greeting and a placeholder — the
actual price/contract content **must be written by a human**. The engine
enforces the pairing: these action types are in `HIGH_RISK_ACTION_TYPES`, so
the draft always enters the `HumanApprovalQueue` (`approval_status="PENDING"`),
and the approver supplies `edited_text` before anything sends
(`MessageDraft.final_text` returns `edited_text or text`).
Tested: approve-with-edit sends the human's text
(`test_16_approve_edit_and_send`); reject records the reason and blocks
(`test_reject_records_reason`, "needs lawyer").

## Drafting rules

- **One ask at a time**: each `ActionRequest` yields exactly one draft with one
  ask; every template requests a single thing (a photo, an address, a look at
  the offer). `ask_for_missing_info` may enumerate several missing items but
  makes them **one** request with **one** reply expected. Stacking is
  prevented upstream by the `RateLimitSpamGuard` (3 attempts max, 20 h
  cooldown, 3/day per case, hard pause once the client replies — Implemented
  and tested).
- **Drafts are stored before sending — always**: the engine composes at step 8
  and appends `MESSAGE_DRAFT_CREATED` (with draft id, channel, risk level)
  *before* any approval or send decision at steps 9–10. Tested: test 20
  asserts `MESSAGE_DRAFT_CREATED` precedes `MESSAGE_SENT` in the audited step
  set, and the approval tests show pending drafts existing with no send.
- **Language fallback**: lookup is `(action_type, language)` first, then
  `(action_type, "pl")` — Polish is the default market language; a missing
  template for both raises `MessageComposeError` (no improvised text, ever).

## Production plan (Designed)

1. **Per-tenant template table**: the in-code `TEMPLATES` dict becomes a
   `CommunicationTemplate` entity (tenant_id, action_type, language, channel
   variant, body, version, approved_by, approved_at) so tenants customize tone
   and branding — with the additional constraint that WhatsApp
   business-initiated variants must match their Meta-approved template text
   (see the ADR's WhatsApp section).
2. **LLM-assisted drafting** for personalization and free-form replies —
   **always behind the same forbidden-pattern validator and the same approval
   gates**. The LLM proposes; the validator rejects price/guarantee/advice
   content exactly as it rejects poisoned variables today; risk classification
   and the ActionGate decide whether a human must approve. The invariant is
   the seam that already exists: *no text reaches `_send` except through
   `compose`-equivalent validation plus the gate/approval path.*
3. **Guard hardening**: extend `FORBIDDEN_PATTERNS` to a per-tenant policy
   list (regexes for numbers-near-currency, percentage discounts, delivery
   promises), and log every rejection as an audit event for prompt/variable
   forensics.
