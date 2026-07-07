# Finalis Action & Communication Engine
### Module Description — Strategic & Product Overview

*Finalis AI — created by Adam Laabs*

---

## 1. What the module is

The Finalis Action & Communication Engine is the **controlled execution layer** of Finalis
AI. It is responsible for client communication, follow-ups, reminders, human approvals,
secure upload links, internal notifications, delivery tracking, and the safe execution of
every outbound action the system takes.

Finalis AI is an AI Case & Deal Worker. Its purpose is not to chat — it is to move every
client case from first contact to a final outcome: won, lost, completed, escalated, or
recovered later. Within that architecture, the division of responsibility is precise:

> **Case Graph knows what happened.
> Completion Loop knows what should happen next.
> Action & Communication Engine safely executes the next step.**

The engine receives recommended actions from the Completion Loop and transforms them into
real, auditable, policy-controlled communication. It is not a generic notification module.
Every message it sends exists because a case needs it, passes through safety gates before
it leaves, and is recorded after it lands.

## 2. Why the module is necessary

Without this module, Finalis would be an excellent analyst and a useless employee. It would
understand every case, detect every missing document, recognize every promise — and then do
nothing about any of it.

With the Action & Communication Engine, Finalis can:

- ask the client for missing photos,
- request missing documents,
- remind the client after an offer,
- notify the owner about urgent cases,
- create internal tasks,
- hand off to a human at the right moment,
- schedule follow-ups days ahead,
- send secure upload links,
- and prevent cases from being quietly forgotten.

This module is what makes Finalis **operational** — the difference between insight and
outcome.

## 3. What problem it solves

Small and medium service companies lose real money in the gaps between conversations. Not
because they lack skill, but because operational memory fails: follow-ups are forgotten,
client replies are missed, missing information is never requested, quotes are delayed,
offers are never chased, and promises evaporate.

Clients say these things every day:

> "I will send photos tomorrow."
> "I will check the offer later."
> "Call me next week."
> "I need to compare another offer."
> "I forgot to send the document."

In a normal company, these sentences disappear — into email threads, WhatsApp scroll,
notebooks, and memory. Each disappearance is a stalled case, and a stalled case is revenue
that quietly walks to a competitor who simply called back.

**The Finalis Action & Communication Engine makes sure that nothing disappears.** Every
promise becomes a deadline, every missing item becomes a polite request, every silent offer
becomes a scheduled follow-up, and every risky situation becomes a human decision — on
time, every time.

## 4. How it works conceptually

The execution path is a fixed sequence of checks and steps. No stage can be skipped, and no
message reaches a client without passing every gate:

1. **Completion Loop** detects that a case needs action.
2. **Next Best Action Engine** proposes what should happen.
3. **Action Gate** checks whether the AI is allowed to act.
4. If the action is **low-risk**, the engine executes it autonomously.
5. If the action is **risky**, it goes to **Human Approval** — always.
6. **Channel Router** selects the best channel for this client and message.
7. **Message Composer** prepares a short, safe, context-aware message.
8. **Consent Gate** checks whether communication is permitted at all.
9. **Rate Limit Guard** prevents spam and duplicate contact.
10. **Delivery Tracker** follows the message: sent, delivered, read, clicked, replied.
11. **Case Graph** is updated with the result.
12. **Audit Events** are written for every decision along the way — including refusals.

A blocked action is never silent: the engine records *why* it did not act, with the same
rigor as when it does.

## 5. Main submodules

**Action Request Handler** — receives proposed actions from the Completion Loop, Voice
Engine, Document Intelligence, WebScout, or human users, and normalizes them into a single
auditable request format.

**Action Gate** — the safety brain. For every request it returns one of four outcomes:
*allowed*, *blocked*, *requires human approval*, or *abstain — data is missing*. High-risk
action classes can never bypass it, regardless of autonomy settings.

**Channel Router** — selects the best channel: WhatsApp, SMS, email, Chatwoot inbox,
internal notification, phone callback task, or an upload-link message. It honors the
client's preferred channel, excludes anything opted out, and always holds a fallback.

**Message Composer** — creates short, safe, context-aware messages from the case state and
missing information. One ask at a time, in the client's language, with every draft stored
before sending.

**Consent & Permission Gate** — checks opt-in, opt-out, per-channel permission, business
hours, no-contact requests, GDPR constraints, and client time preferences. Outside business
hours, messages are deferred — not dropped.

**Rate Limit & Anti-Spam Guard** — prevents too many messages, duplicate follow-ups,
repeated reminders, and aggressive cadence. If the client replies, automated follow-up
pauses immediately.

**Human Approval Queue** — holds risky actions for review. A human can approve, edit, or
reject; the original and edited message are both preserved, and the decision is audited.

**Upload Link Generator** — creates secure, expiring, case-scoped links for photos,
documents, offers, contracts, invoices, or technical evidence. Only a hash of the token is
ever stored; file types and sizes are restricted; every open and upload is an event.

**Delivery Tracker** — tracks each message through its life: created, scheduled, sent,
delivered, failed, read, replied, clicked, uploaded. A failure triggers the fallback
channel; a reply feeds straight back into the case.

**Case Graph Updater** — writes the result of every action back to the case: a resolved
missing item, a fulfilled promise, a scheduled next step. Execution and memory never drift
apart.

**Audit Logger** — records every decision, message, approval, rejection, blocked action,
delivery status, and case update on an append-only, tamper-evident log. There are no hidden
AI actions.

## 6. Example scenario

A client asks for a heat pump quote.

The Voice Engine captures the conversation. Conversation Intelligence detects that the
client promised to send installation photos *tomorrow*. Case Graph stores the promise with
its deadline.

Twenty-four hours later, the Completion Loop checks the case. The photos are still missing.
The Next Best Action is clear: **send a photo request**. The Action Gate allows it — it is
a low-risk, information-gathering message. The Channel Router selects WhatsApp, with SMS as
fallback. The Upload Link Generator creates a secure, expiring link. The Message Composer
writes a short, polite Polish message. The Consent Gate confirms the channel is permitted
and the time is within business hours.

The message is sent. The Delivery Tracker records that it was delivered, then opened. The
client uploads two photos through the link. The Case Graph marks the missing item resolved
and the promise fulfilled; the case moves toward quote preparation. Every step — from the
detected promise to the resolved item — exists as an audit event.

No one in the company had to remember anything.

## 7. Example message

> *"Dzień dobry, zgodnie z rozmową proszę o przesłanie zdjęcia obecnej instalacji oraz
> tabliczki znamionowej urządzenia. To pozwoli przygotować dokładniejszą wycenę. Link do
> dodania zdjęć: {{upload_link}}"*

Short, contextual, one request, no pressure. And bounded by hard rules: Finalis **must not
invent facts, promise prices, pressure the client, or send risky content without human
approval**. The composer enforces this mechanically — a message containing an unapproved
price simply cannot be generated, and high-risk drafts are produced only as skeletons a
human must complete.

## 8. Safety rules

The AI may automatically execute **low-risk actions**:

- asking for missing photos,
- asking for an address,
- confirming document receipt,
- sending a polite reminder,
- creating an internal task.

The AI **must obtain human approval** for:

- pricing commitments,
- discounts,
- legal or contract language,
- angry clients,
- low-confidence OCR or transcription,
- conflicting facts,
- high-value cases,
- payment-related messages,
- unusual promises,
- final decisions.

These boundaries are enforced by the Action Gate and the approval queue — not by prompt
instructions. An AI worker cannot approve its own high-risk action.

## 9. Recommended infrastructure

The module should not be built entirely from scratch where strong self-hosted, open-source
infrastructure exists. The recommended architecture:

**Temporal** — for durable workflows: delayed follow-ups, retries, promise reminders,
human-approval timeouts, and long-running case processes that must survive restarts and
still fire days later.

**Novu** — as the notification and communication delivery abstraction across email, SMS,
chat, in-app inbox, Slack, Teams, Telegram, WhatsApp, and other channels. *(Note: the
project's technology decision record found that Novu's community self-hosted tier currently
gates multi-tenancy and delivery webhooks to its cloud edition; where full self-hosting is
required, the same delivery-abstraction role is filled by a thin layer of direct provider
adapters — Meta WhatsApp Cloud API, Twilio, SES — behind the identical interface. The
architecture does not change; only the adapter behind it does.)*

**Chatwoot** — for the omnichannel inbox, human handoff, agent/operator panel, conversation
history, and manual takeover. When Finalis hands a case to a person, it arrives as a
Chatwoot conversation with the AI's summary attached as a private note.

**Activepieces** — only as an optional integration layer for customer-specific automations
(CRM sync, exports, custom webhooks). Never for core logic.

**Important:** Chatwoot, Novu, Temporal, and Activepieces are infrastructure. **They are
not the Finalis brain.** The brain remains: Case Graph, Completion Loop, Action Gate, Human
Approval, Audit Trail, and — in future — the LGGT ProofGate. Infrastructure delivers
messages; Finalis decides why, when, whether, and to whom.

## 10. Enterprise requirements

The module is enterprise-ready by design: tenant isolation on every entity; RBAC so only
authorized people approve risky actions; an append-only audit log; consent management with
per-channel opt-out and do-not-contact handling; PII protection in message storage and
logs; secure hashed upload tokens; idempotent, retry-safe execution; signed webhooks;
end-to-end delivery tracking; a full approval history including edits; per-tenant cost
controls and daily send limits; anti-spam rules that cannot be overridden by any score; and
the absolute rule that **there are no hidden AI actions** — everything is on the record.

## 11. Strategic value

Most AI assistants can answer, summarize, or generate messages. That capability is now a
commodity.

The Finalis Action & Communication Engine does something categorically different: it
**moves business cases forward, safely**. It ensures that:

- no lead is forgotten,
- no promise disappears,
- no missing document blocks a case silently,
- no offer waits forever,
- no risky action is sent without approval,
- and every action is auditable.

Competitors can copy a voice. They can license an OCR model. What is hard to copy is a
controlled execution loop that a business owner can trust with their client relationships —
because it is provably polite, provably compliant, and provably on time. That trust is the
moat.

## 12. Positioning statement

> **The Finalis Action & Communication Engine is the operational execution layer that
> transforms AI recommendations into safe, auditable business actions. It is the difference
> between an AI that only talks and an AI that actually helps close cases.**
