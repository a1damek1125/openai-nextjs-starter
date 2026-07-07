# Finalis AI — MVP Scope & Roadmap

> Ship a **narrow, deep, provable** MVP for one vertical, then expand via playbooks. Scope
> discipline is a feature: the autonomy evidence (`02`) says breadth kills reliability.

## 1. MVP definition

**Finalis AI for Installers & Home Services** (HVAC / plumbing / electrical / renovation).

### In scope (MVP)
1. AI answers the phone (voice worker, cascaded pipeline) + after-hours (requires the
   inbound-answer action type at autonomy L3 — the recommended day-one default for inbound;
   outbound action types may start L1–L2, see 13 §1).
2. Intake: collects client + case data (address, problem, urgency, scope, timing, budget band,
   "do you have another quote?").
3. Requests photos/documents via **WhatsApp** (+ SMS/email).
4. Creates the **Case Graph** and Case file.
5. **Missing-Information Hunter** detects and chases gaps.
6. **Follow-up** at `+24h/+48h/+72h` cadence (anti-spam, quiet hours, opt-out).
7. **Document/offer analysis** (upload/WhatsApp PDF → OCR → fields + confidence + summary).
8. **Consistency check** of an offer/document vs. prior agreements.
9. **Decision Brief** for the owner.
10. **Command Center**: pipeline, hot leads, stuck cases, promises due, offers with no
    response, calls to make, recovered/closed, **and AI actions requiring approval**.
11. **Promise Tracker** (calls + messages).
12. Calendar booking (Google/Outlook).
13. Autonomy Levels 1–4 configurable; escalation to human; full audit.

### Out of scope (MVP — deferred)
Full autonomous binding pricing · full legal advice · autonomous contract signing · payments ·
autonomous high-value negotiation · all verticals · WebScout v1 (comes Phase 3) · own voice
model. (WebScout and Quote Builder ship as v1 in Phase 3.)

### MVP success criteria (measured, `15`)
- Voice: P50 TTFA ≤ 800 ms, P95 ≤ 1500 ms on simple turns.
- Missing-info recall ≥ 0.9 on the golden set.
- OCR field F1 ≥ target per field type on the tenant's doc mix.
- Follow-up produces measurable reply lift vs. baseline (no-AI) leads.
- Hallucination rate (unsupported-claim rate) near-zero on evidence-required outputs.
- Demonstrable **recovered leads / pipeline €** across pilot tenants.

## 2. Roadmap (phased)

### Phase 0 — Technical design (≈2 weeks)
Decisions: MVP vertical playbook, data model, conversation scripts, case states, integrations,
voice stack, OCR stack, initial scoring weights (Phase-0 open decisions in `18` §9).
**Deliverables**: this spec set, conversation-flow prototype, dashboard mockups, intake data
list, ADRs for the open decisions.

### Phase 1 — Prototype (≈4–6 weeks)
Build: AI phone + WhatsApp/SMS follow-up, Case Graph, basic Command Center, document upload +
OCR/summary, Missing-Info Hunter, simple Next-Best-Action. **Goal**: real demo on 5–10 cases.

### Phase 2 — Beta (≈8–12 weeks)
10–20 pilot firms. Measure (`15`): calls answered, leads qualified, follow-ups done, cases
closed, AI errors, escalations, documents read correctly, € pipeline. Harden autonomy,
guardrails, audit. **Goal**: proven ROI + reliability envelope.

### Phase 3 — Paid MVP (≈3–6 months)
Payments/billing (Stripe — already in the starter), self-serve onboarding, call limits, full
reports, better offer comparison, **WebScout v1**, **Quote Builder v1**, Revenue Recovery
dashboard. **Goal**: repeatable paid customers in vertical #1.

### Phase 4 — Vertical platform (≈6–12 months)
New playbooks: auto workshops, property management, legal intake (intake + docs only),
insurance claims, B2B sales. Vertical integrations. **Goal**: multi-vertical via config, not
forks.

## 3. Phase → capability matrix

| Capability | P0 | P1 | P2 | P3 | P4 |
|---|:--:|:--:|:--:|:--:|:--:|
| Data model + state machine + orchestrator | ◑ | ● | ● | ● | ● |
| Voice (cascaded) | | ● | ● | ● | ● |
| WhatsApp/SMS/email + follow-up loop | | ● | ● | ● | ● |
| Case Graph + Deal Memory | ◑ | ● | ● | ● | ● |
| Missing-Info Hunter + Promise Tracker | | ● | ● | ● | ● |
| Document intelligence | | ◑ | ● | ● | ● |
| Offer comparison / contract check | | | ◑ | ● | ● |
| Decision briefs | | ◑ | ● | ● | ● |
| Command Center | | ◑ | ● | ● | ● |
| Autonomy L1–4 + audit + guardrails | | ◑ | ● | ● | ● |
| WebScout | | | | ● | ● |
| Quote Builder | | | ◑ | ● | ● |
| Billing / self-serve | | | | ● | ● |
| Multi-vertical playbooks | | | | | ● |

● full · ◑ partial. See `17` for task-level sequencing.

## 4. Guiding constraints throughout

Evidence over claims (never assert below `θ_conf`) · human-in-the-loop at the right moments ·
never final legal advice · anti-spam follow-up · full audit trail · privacy by default. These
are non-negotiable across all phases.
