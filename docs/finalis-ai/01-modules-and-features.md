# Finalis AI — Modules & Complete Feature List

This is the canonical feature catalogue. Each module lists its job, key features, inputs/
outputs, and the doc with full detail. Modules map to workers (`02`) and to case states (`03`).

## Module map

| # | Module | Type | Detail |
|---|---|---|---|
| 1 | Contact Worker | channel front-door | `06`, `12` |
| 2 | Intake Worker | qualification | `03`, `05` |
| 3 | Case Graph | memory/logic core | `04`, `02` |
| 4 | Completion Loop Engine | process driver | `09`, `03` |
| 5 | Follow-up Worker | outbound cadence | `09` |
| 6 | Promise Tracker | commitment tracking | `09` |
| 7 | Missing-Information Hunter | gap detection | `09`, `05` |
| 8 | Document Intelligence Worker | OCR + analysis | `07` |
| 9 | Offer Comparator | offer scoring | `10`, `05` |
| 10 | Contract Reality Check | business doc review | `10` |
| 11 | WebScout Worker | web research | `08` |
| 12 | Decision Worker | owner briefs | `09`, `11` |
| 13 | Objection Handler | sales objections | `09` |
| 14 | Quote Builder | draft quotes | `09` |
| 15 | Timeline Worker | case history view | `11` |
| 16 | Case Command Center | owner dashboard | `11` |
| 17 | Evaluation Lab | continuous QA | `15` |

---

## 1. Contact Worker
**Job**: first contact across **phone, WhatsApp, SMS, email, web form, web chat** (later
Messenger / Google Business Profile). Answers as naturally as a trained assistant.
**Features**: ultra-low-latency voice (`06`), barge-in/interruptions/pauses/corrections,
multi-language, human handoff, returning-client recognition (Deal Memory), unified thread into
one `Conversation`/`Case`.
**In**: inbound event/media. **Out**: created/updated `Case`, `Conversation`, `Message`/`Call`.

## 2. Intake Worker
**Job**: qualify the client + case; collect industry-structured info.
**Features**: playbook-driven questions (address, urgency, scope, budget, photos, documents,
preferred time, existing offers, deadlines), initial `LeadScore` + `MIS`, no-over-asking.
**In**: conversation, `IndustryPlaybook`. **Out**: filled fields, `MissingItem`s, scores.

## 3. Case Graph
**Job**: the "brain of the case" — a graph, not a note.
**Features**: nodes (client, business, case, messages, calls, documents, photos, offers,
promises, missing info, deadlines, risks, tasks, decisions) + typed edges ("client sent
document", "offer contradicts previous agreement", "missing photo blocks quote", "promise due
tomorrow", "case requires human approval"). Semantic retrieval via embeddings. Full spec `04`.

## 4. Completion Loop Engine
**Job**: never stop after one conversation.
**Features**: every case has status, next action, due time, owner, `risk_score`, `lead_score`,
`mis_score`, closure path; nightly stuck sweep + event-driven recompute; closure only via
won / lost / completed / abandoned / recovery-later (human-review escalation is a pause, not a
closure). Full spec `09`, `03`.

## 5. Follow-up Worker
**Job**: contact the client until the case progresses — without spamming.
**Features**: next-best channel + timing via `FollowUpPriority`; quiet hours, opt-outs,
max-attempts; remembers client preferences; recovers silent leads. Full spec `09`.

## 6. Promise Tracker
**Job**: track promises by client, company, technician, salesperson, notary, lawyer, supplier,
insurer.
**Features**: promise extraction from calls/messages; `PromiseBreachScore`; reminders
(client) / escalation (company); dependency awareness. Full spec `09`.

## 7. Missing-Information Hunter
**Job**: detect and chase info blocking the case.
**Features**: `MIS`-driven detection; asks for photos, VIN, address, dimensions, invoices,
contracts, previous offers, ID, signatures, attachments, decisions; one consolidated,
example-bearing request. Full spec `09`.

## 8. Document Intelligence Worker
**Job**: read/analyze PDFs, scans, images, handwriting, offers, invoices, contracts, notarial/
property/insurance/reports/protocols/commercial offers.
**Features**: layout-aware OCR (Docling/olmOCR/PaddleOCR-VL/Qwen-VL/Surya), structured field
extraction with **confidence**, evidence refs (page/bbox/snippet), never-pretend-certainty
abstention, `DocRisk`. Full spec `07`.

## 9. Offer Comparator
**Job**: compare multiple offers.
**Features**: price, scope, deadlines, warranty, payment terms, exclusions, hidden costs,
service, risk, consistency with earlier agreements; `OfferScore` with per-vertical weights;
plain-language recommendation + hidden-risk flags. Full spec `10`.

## 10. Contract Reality Check
**Job**: does this document make business sense? (Not legal advice.)
**Features**: flags missing elements, asymmetry, unclear deadlines, risky payment terms,
contradictions, missing warranties/attachments, inconsistencies vs. prior emails/calls;
labels legal content for human review. Full spec `10`.

## 11. WebScout Worker
**Job**: ethical, source-recorded public web research.
**Features**: read public pages/PDFs, manufacturer specs, catalogues, public registries, price
ranges; every fact carries URL, source type, date checked, trust level, snippet; hard limits
(no paywall/CAPTCHA/auth/robots bypass); sandboxed + injection-defended. Full spec `08`.

## 12. Decision Worker
**Job**: produce short, actionable decision briefs for the owner.
**Features**: value range, situation, competitor delta, our advantage, recommended next step,
risk, confidence, evidence links. Full spec `09`, `11`.

## 13. Objection Handler
**Job**: detect + respond to objections (price too high, needs time, has competitor offer,
wants discount, deadline too long, doesn't trust, needs partner approval, missing docs).
**Features**: recommended response within authorized bounds, or escalate. Full spec `09`.

## 14. Quote Builder
**Job**: draft quotes from intake, photos, documents, price rules, past cases.
**Features**: scope, base + premium variants, assumptions, remaining blockers, risks, sales
arguments; never finalizes a binding price without rules/approval when uncertainty is high.
Full spec `09`.

## 15. Timeline Worker
**Job**: full case history — first contact, calls, documents, photos, offers, missing data,
follow-ups, decisions, risks, next step — understandable in ~20 seconds. Full spec `11`.

## 16. Case Command Center
**Job**: the owner's dashboard/command center.
**Features**: hot leads, stuck cases, missing documents, promises due, offers with no response,
calls to make, estimated pipeline, recovered leads, closed cases, and AI actions requiring
approval. Full spec `11`.

## 17. Evaluation Lab
**Job**: continuous testing — voice quality, intent recognition, data extraction, OCR
accuracy, missing-info detection, offer comparison, follow-up appropriateness, escalation
precision, hallucination rate, latency. Full spec `15`.

---

## Feature completeness checklist (traceability to the brief)

- [x] Multi-channel contact (phone/WhatsApp/SMS/email/form/chat) — `06`,`12`
- [x] Natural, low-latency, interruptible, multilingual voice + handoff — `06`
- [x] Industry-structured intake + qualification — `01`,`03`
- [x] Case Graph (nodes + typed edges) — `04`
- [x] Completion Loop (status/next-action/owner/scores/closure) — `09`,`03`
- [x] Follow-up (anti-spam, best channel/timing, preferences) — `09`
- [x] Promise Tracker (all parties, breach detection) — `09`
- [x] Missing-Info Hunter — `09`
- [x] Document intelligence with confidence + evidence — `07`
- [x] Offer comparison — `10`
- [x] Contract reality check (not legal advice) — `10`
- [x] WebScout (ethical, sourced) — `08`
- [x] Decision briefs — `09`,`11`
- [x] Objection handler — `09`
- [x] Quote builder — `09`
- [x] Timeline — `11`
- [x] Command center — `11`
- [x] Evaluation lab — `15`
- [x] 10 scoring models — `05`
- [x] Formal state machine (17 states) — `03`
- [x] Full data model (25+ entities) — `04`
- [x] Autonomy levels 1–5 — `13`
- [x] Integrations — `12`
- [x] MVP scope + roadmap — `14`
- [x] Risks & mitigations — `16`
- [x] Engineering task breakdown — `17`
- [x] Tech stack — `18`
- [x] Sources — `19`
- [x] Final build spec — `20`
