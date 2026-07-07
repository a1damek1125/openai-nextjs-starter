# Finalis AI — Product & Technical Blueprint

**Finalis AI is an AI Case & Deal Worker for service businesses.** It receives a client
contact, opens a living case file, asks follow-up questions, collects missing information,
analyzes documents, compares offers, researches the public web, prepares a decision brief,
follows up until the case progresses, and escalates to a human when needed.

> **Core promise:** *"Finalis AI leads a client case from first contact to final decision,
> sale, signed offer, or completed service."*
>
> Not a chatbot. Not an AI receptionist. Not an agent framework. An **operational AI worker
> that closes cases** — voice-first, document-aware, web-aware, stateful, follow-up-driven,
> evidence-based.

First vertical (MVP): **HVAC / plumbing / electrical / renovation home services.**

---

## How this blueprint is organized

| # | Document | What's inside |
|---|---|---|
| [00](00-product-strategy-and-market.md) | Product Strategy & Market | vision, differentiators, target markets, pricing |
| [01](01-modules-and-features.md) | Modules & Complete Feature List | all 17 modules + traceability checklist |
| [02](02-multi-agent-architecture.md) | Multi-Agent Architecture | orchestrator + workers; why narrow+supervised (with benchmark evidence) |
| [03](03-case-lifecycle-state-machine.md) | Case Lifecycle State Machine | 17 states, transitions, invariants, escalation edges |
| [04](04-data-model.md) | Data Model | 25+ entities, Case Graph edges, retention/privacy |
| [05](05-algorithms-and-scoring.md) | Algorithms & Scoring | LeadScore, MIS, NBA, FollowUp, DocRisk, Confidence, OfferScore, Escalation, Stuck, Breach, Trust |
| [06](06-voice-architecture.md) | Voice Architecture | cascaded STT→LLM→TTS, latency targets, barge-in, handoff |
| [07](07-document-intelligence.md) | Document Intelligence | routed OCR stack, confidence, evidence-based analysis |
| [08](08-webscout-web-research.md) | WebScout Web Research | ethical/legal limits, sandbox, source trust scoring |
| [09](09-completion-loop-followup-promises.md) | Completion Loop, Follow-up, Promises, Missing-Info | the "never stops" engine |
| [10](10-offer-comparison-and-verification.md) | Offer Comparison & Document Verification | OfferScore, contract reality check (not legal advice) |
| [11](11-ux-dashboards.md) | UX / Dashboards | Command Center + 4 more screens |
| [12](12-integrations.md) | Integrations | MCP-first; calendar/email/WhatsApp/SMS/telephony/drive |
| [13](13-autonomy-and-safety.md) | Autonomy & Safety | Levels 1–5, escalation, guardrails, anti-hallucination, audit |
| [14](14-mvp-and-roadmap.md) | MVP & Roadmap | scope + Phase 0–4 |
| [15](15-evaluation-lab.md) | Evaluation Lab | continuous metrics, calibration, red-teaming |
| [16](16-risks-and-mitigations.md) | Risks & Mitigations | AI/business/legal/security/operational register |
| [17](17-engineering-task-breakdown.md) | Engineering Task Breakdown | epics, tasks, build sequence, milestones |
| [18](18-technology-stack.md) | Technology Stack | recommended stack + rationale + open decisions |
| [19](19-sources-and-references.md) | Sources & References | every citation + verification status |
| [20](20-final-build-specification.md) | Final Build Specification | consolidated developer handoff |
| [21](21-state-of-the-art-technology-review.md) | State-of-the-Art Technology Review | per-component "best now vs. best future" comparison + SOTA mandate |

**Suggested reading order for developers:** `20` (build spec) → `02` → `03` → `04` → `05`,
then the module docs as needed. **For founders/PMs:** `00` → `01` → `14` → `16`.

---

## The 17 modules at a glance

Contact Worker · Intake Worker · Case Graph · Completion Loop Engine · Follow-up Worker ·
Promise Tracker · Missing-Information Hunter · Document Intelligence Worker · Offer Comparator ·
Contract Reality Check · WebScout Worker · Decision Worker · Objection Handler · Quote Builder ·
Timeline Worker · Case Command Center · Evaluation Lab.

## The 10+ scoring models

LeadScore · Missing-Information Score · Next-Best-Action Utility · Follow-up Priority ·
Document Risk Score · Evidence Confidence · Offer Score · Escalation Score · Case Stuck Score ·
Promise Breach Score · Source Trust Score. (Full math in [05](05-algorithms-and-scoring.md).)

---

## Evidence & honesty policy

Every technical claim in this blueprint carries a source and a verification status
(`[VERIFIED]` / `[snippet]` / `[UNVERIFIED]`) — see [19](19-sources-and-references.md). Where a
figure could only be confirmed via a search snippet (a proxy blocked some direct fetches during
research), it is flagged so it can be re-read before being quoted verbatim. Legal statements are
synthesis, **not legal advice** — confirm with counsel per jurisdiction. The product itself is
built on the same principle: **never assert below the confidence threshold; always link
evidence; escalate to humans at the right moments.**

## Positioning guardrail

Finalis AI is **not** a cybersecurity / SOC / SIEM / compliance product. Security, privacy,
permissions, audit, and safe data handling exist as **internal trust layers**, not as the
product category. The category is **AI Case & Deal Worker for service businesses**, and the
value is: more closed cases, fewer lost leads, fewer forgotten follow-ups, better document
handling, faster response, higher conversion, clearer decisions.
