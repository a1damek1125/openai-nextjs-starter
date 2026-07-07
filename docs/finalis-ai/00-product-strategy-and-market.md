# Finalis AI — Product Strategy & Market

## 1. What it is (one sentence)

> **Finalis AI leads a client case from first contact to final decision, sale, signed offer,
> or completed service.**

It is **not** a chatbot, **not** an AI receptionist, and **not** an agent framework. It is an
**AI Case & Deal Worker** for service businesses: a digital employee that receives a client,
opens a living case file, asks follow-up questions, collects missing info, analyzes documents,
compares offers, researches the public web, prepares a decision brief, follows up until the
case progresses, and escalates to a human when needed.

**Category**: AI Case & Deal Worker for service businesses. *(Explicitly not cybersecurity /
SOC / SIEM / compliance automation — security exists internally as trust, permissions, audit,
and safe data handling, not as the product category.)*

## 2. The core insight

Most AI agents today work as: *user gives a command → agent does a task → done.* Finalis works
as: *client starts a case → AI opens a case file → AI drives the next steps → AI asks, analyzes,
follows up, escalates → AI closes the case.*

**We don't execute single tasks. We carry cases to completion.**

This matters because the evidence says general autonomy is still unreliable on long, realistic
business work:
- **TheAgentCompany (arXiv:2412.14161)**: best agent completed **~24%** of 175 realistic
  office tasks fully autonomously (~34% with partial credit); an updated leaderboard reports
  ~30%. *(Headline via search snippet of the paper.)*
- **OSWorld (arXiv:2404.07972)**: **humans ~72%** vs. **best model ~12%** at publication on
  real computer tasks.

So we deliberately build a **narrow, process-driven, human-supervised worker** — not "AI that
does everything." The moat is **operational case logic**, not the raw model.

## 3. Sales promise

- **Owner-facing**: *"Every case always has a next step, an owner, and a deadline — and anything
  the AI can't handle lands on your desk, never in a void."* (Marketing copy must stay within
  this defensible claim — see 16 §1.8 on over-promise risk.)
- **One-liner**: *"An AI receptionist answers the phone. Finalis AI closes the case."*
- **Value in the buyer's language**: more closed cases · fewer lost leads · fewer forgotten
  follow-ups · better document handling · faster client response · higher conversion · clearer
  decisions.

## 4. Core differentiators (the moat)

1. **Case Graph** — a living map of the case (client, docs, offers, promises, gaps, risks,
   next step), not a flat conversation log. (`04`, `02`)
2. **Completion Loop Engine** — the system never stops after one conversation; every case
   always has a next action, owner, due time, and closure path. (`09`, `03`)
3. **Promise Tracker** — tracks and enforces promises by every party (client, company,
   technician, notary, lawyer, supplier, insurer). (`09`)
4. **Missing-Information Hunter** — detects and chases the exact info blocking the case. (`09`)
5. **Document-to-Deal Engine** — links calls, documents, offers, and follow-up into one flow
   with evidence and confidence. (`07`, `10`)
6. **WebScout Worker** — ethical, source-recorded public web research. (`08`)
7. **Decision Brief** — a short "what to do now" for the owner, evidence-linked. (`09`, `11`)
8. **Revenue Recovery Dashboard** — quantifies recovered leads and pipeline in money terms.
   (`11`)

Competitors may have better voice, cheaper OCR, or more integrations. Finalis competes on
**understanding the case** — promises, gaps, documents, offers, risks, next step, moment of
closure — i.e. the **operational logic of the business**, which is far harder to copy.

## 5. First target market (MVP vertical)

**Home services / installation / renovation / HVAC / plumbing / electrical.**

Why first:
- High inbound call volume; clients call whoever answers first.
- WhatsApp photos, documents, offers, dimensions, deadlines, quotes.
- Clients compare competing offers and vanish after asking about price.
- High per-job value → simple, provable ROI.
- Lower regulatory risk than legal/medical.
- Every Finalis module is exercised: voice, intake, documents, missing-info, follow-up, offer
  comparison, decision briefs.

**First product**: *Finalis AI for Installers & Home Services.*

## 6. Later verticals (expansion)

| Order | Vertical | Product name | Notes |
|---|---|---|---|
| 1 | Auto repair workshops | Finalis Auto | make/model/VIN/symptoms/photos/status/pickup |
| 2 | Property management / rental / self-storage | Finalis Property | tickets, docs, viewings, protocols, tenants |
| 3 | Real estate agencies | Finalis Realty | leads, docs, viewings, offers |
| 4 | Insurance claims | Finalis Claims | claims, policies, photos, documents |
| 5 | B2B service sales | Finalis Sales | offers, follow-up, competitor comparison |
| 6 | Legal intake / notarial doc prep | Finalis Legal Intake | **intake + document prep only — never final legal advice** |

Expansion is via **`IndustryPlaybook`** config (intake schema, weights, timings, templates) —
not forked codebases. (`04`)

## 7. What we deliberately do NOT do at launch

Autonomous binding pricing without rules/approval · final legal or medical advice · autonomous
contract signing · taking payments · autonomous high-value negotiation · all verticals at once
· cybersecurity positioning. These are later, gated, or out of scope.

## 8. Pricing (direction — validate in beta)

Sell **outcomes/seats, not tokens** (buyers reject token pricing). Indicative tiers:

| Tier | € / month (indicative) | For | Headline features |
|---|---|---|---|
| Start | 99–149 | solo / very small | after-hours answering, notes, simple follow-up, WhatsApp/SMS, weekly report |
| Pro | 299–499 | daily leads | full answering, Case Graph, Follow-up Worker, Document Worker, Missing-Info Hunter, calendar, pipeline dashboard |
| Business | 799–1499 | larger firms | multi-number/user/language, WebScout, Offer Comparator, Quote Builder, advanced analytics, vertical integrations |
| Enterprise | 2500+ | chains, property mgmt, agencies | custom workflows, SLA, custom playbooks, case audit, roles, API |

*(Numbers are hypotheses to be tested against realized ROI — e.g. value of recovered leads —
in Phase 2 beta.)*

## 9. Success metrics (the product's own KPIs)

More closed cases · recovered leads (count + € pipeline) · follow-up success rate · faster
client response · document-handling accuracy · higher conversion · high escalation precision ·
low hallucination rate. These are formalized in the Evaluation Lab (`15`).

## 10. Reading order for this blueprint

`00` strategy → `01` features/modules → `02` architecture → `03` state machine → `04` data
model → `05` algorithms → `06` voice → `07` documents → `08` webscout → `09` completion loop →
`10` offer comparison/verification → `11` UX → `12` integrations → `13` autonomy & safety →
`14` MVP & roadmap → `15` evaluation → `16` risks → `17` engineering tasks → `18` tech stack →
`19` sources → `20` final build spec.
