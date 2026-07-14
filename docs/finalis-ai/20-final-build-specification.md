# Finalis AI — Final Build Specification (Developer Handoff)

> This is the consolidated, developer-facing spec: what to build, in what order, with what
> contracts. It references the detailed docs (`00`–`19`) rather than repeating them. If you
> read only one file before starting, read this — then `03`, `04`, `05`, `02`.

## 1. System summary

Finalis AI is an **AI Case & Deal Worker**: a supervised team of narrow workers driving a
durable case process from first contact to closure. Not a chatbot, not one big autonomous
agent. The moat is **operational case logic** (Case Graph + Completion Loop + scoring +
playbooks), which is model- and vendor-agnostic behind interfaces.

MVP vertical: **HVAC / plumbing / electrical / renovation home services**.

## 2. Architecture contract (build these seams first)

```
Channels → Orchestrator(state machine + completion loop) → Workers → State/Memory → Human surface
                                     │
                             MCP tool servers (integrations)
```

- **Orchestrator** owns the `Case` state machine (`03`), runs the Completion Loop (`09`),
  enforces autonomy (`13`), recomputes scores (`05`), writes `AuditEvent`s, and raises
  `HumanApproval`. Recommended substrate: **LangGraph** (durable/HITL) + **Temporal** (or
  Postgres queue) for time-based durability (`18`).
- **Workers** are narrow agents with a strict I/O contract (below). They **propose**; the
  Orchestrator **applies** transitions under autonomy rules. Workers never mutate case state
  directly.
- **Integrations** are **MCP servers** (`12`), credentials by reference only (`04`
  `IntegrationAccount`).
- **State/Memory**: Postgres (system of record + `graph_edges` Case Graph) + pgvector +
  S3 (`04`, `18`).

### Worker I/O contract (all workers)
```
input:  { case_id, tenant_id, trigger_event, case_graph_snapshot, playbook }
output: {
  proposals: [ { type, payload, autonomy_required, ... } ],
  extracted: [ ExtractedField | Promise | MissingItem | RiskFlag | ... ],
  evidence:  [ EvidenceReference ],   // every claim linked
  confidence: 0..1,                    // honest; below θ_conf ⇒ abstain
  escalate:  bool + reason
}
```
The Orchestrator validates proposals through **guardrails** (PII/scope/price-rule/injection),
applies allowed ones, audits everything, and gates the rest to `HumanApproval`.

## 3. Data model (build `04` first)

Postgres schema per `04`: `Case, Party, Conversation, Message, Call, Document, ExtractedField,
EvidenceReference, Photo, Offer, Comparison, Promise, MissingItem, Action, Task,
FollowUpSequence, DecisionBrief, RiskFlag, HumanApproval, AuditEvent, IntegrationAccount,
BusinessProfile, IndustryPlaybook, VoiceProfile, UserRole` + `graph_edges` + `CasePartyRole`.

Non-negotiables: multi-tenant **row-level security**; **append-only `AuditEvent`** (hash-
chained); PII columns tagged/encrypted with retention policies; secrets in a manager, not the
DB.

## 4. State machine (build `03` as an explicit FSM)

17 states, global invariants (active case always has `next_best_action` + `due_at`), the global
interrupt edge to `HUMAN_REVIEW_REQUIRED` on `EscalationScore ≥ θ_escalate`, and the transition
table are in `03`. Every transition writes an `AuditEvent`.

## 5. Scoring (build `05` as pure, tested functions)

Ten+ deterministic functions with tenant-tunable weights from `IndustryPlaybook`: `LeadScore,
MIS, NBA Utility, FollowUpPriority, DocRisk, Evidence Confidence, OfferScore, EscalationScore,
StuckScore, PromiseBreachScore`, plus `SourceTrust`. Each persists its input vector + weight
version to `AuditEvent` for reproducibility. **These are unit-testable in isolation — do them
early with golden cases.**

## 6. The Completion Loop (the heartbeat)

Event-driven recompute + **nightly stuck sweep** over all active cases (`09`): recompute scores,
enforce the "has-a-future-action" invariant, choose NBA (`05` §3), execute-if-allowed-else-
approve, park/wake `RECOVERY_LATER`. Must run on a durable substrate so scheduled follow-ups
survive restarts.

## 7. Channel & worker specs

- **Voice** (`06`): cascaded STT→LLM→TTS on LiveKit/Pipecat; TTFA P50 ≤800 ms / P95 ≤1500 ms;
  barge-in, repair, language switch, handoff; post-call → summary + promises + missing items +
  next actions.
- **Intake** (`03`,`05`): playbook-driven; produces fields, `MissingItem`s, LeadScore inputs.
- **Documents** (`07`): routed OCR (Docling/olmOCR/PaddleOCR-VL/Qwen-VL/Surya) → fields +
  confidence + evidence; abstain below `θ_conf`; `DocRisk`.
- **WebScout** (`08`): read-only, sandboxed, public-only, source-recorded; Playwright MCP +
  Firecrawl; injection-defended; trust-scored.
- **Offer Comparator / Contract Check** (`10`): `OfferScore`/`DocRisk`, evidence-linked,
  never legal advice.
- **Follow-up / Promise / Missing-Info / Objection / Quote** (`09`): the completion-loop skills.
- **Decision Worker** (`09`,`11`): short evidence-linked owner briefs.
- **Quality/Eval Worker** (`02`,`15`): verifies evidence-linking + honesty (secondary critic).

## 8. Autonomy, guardrails, audit (`13`)

Autonomy Levels 1–5 (L5 disabled until post-MVP — 14 §1), `effective_level = min(tenant default per action-type, case setting)`;
`HUMAN_REVIEW_REQUIRED` caps at Level 2. Parallel guardrails (OWASP LLM01/LLM06, Agentic
ASI-series). Anti-hallucination: `θ_conf` abstention + mandatory evidence links + Quality
critic. Immutable hash-chained audit; PII access logged.

## 9. UI (`11`) — reuse this repo

Build the Command Center on the existing Next.js/React/TS starter (auth, Postgres, Stripe
already present). Five screens: Command Center, Case Detail (+Timeline), Document Analysis,
Offer Comparison, AI Control Center. Every AI claim shows evidence + confidence; Approve/Call/
Send-follow-up actions on cases; mobile-first; real-time updates.

## 10. Integrations (`12`)

MVP as MCP servers: Google/Outlook Calendar, Gmail/Outlook, WhatsApp Business (template/opt-in
rules), SMS (A2P/STOP), telephony/SIP, web form + chat, Drive/OneDrive, PDF upload. Each mapped
to an autonomy level + approval requirement.

## 11. Evaluation (`15`) — wire from day one

Golden datasets per vertical; regression gates in CI; metrics: voice latency P50/P95, call
completion, intent/slot accuracy, lead-qual precision/recall, OCR field F1 + calibration
(ECE/Brier), missing-info recall, follow-up success, offer-comparison accuracy, **hallucination
(unsupported-claim) rate**, escalation precision/recall, human-approval + reversal rate,
close-assist rate. Shadow/canary + weight back-testing before rollout; red-team injection.

## 12. Build order (dependency-correct)

1. **Foundations**: repo/CI, multi-tenancy + RLS, secrets, observability.
2. **Data model + `graph_edges`** (`04`).
3. **State machine skeleton + Orchestrator + AuditEvent** (`03`,`02`).
4. **Scoring functions + tests** (`05`).
5. **Intake + Case Graph** on **one channel (WhatsApp)** end-to-end.
6. **Completion Loop + Follow-up + Missing-Info + Promise Tracker** (`09`) on durable substrate.
7. **Document intelligence** (`07`) → Offer Comparator/Contract Check (`10`).
8. **Voice Worker** (`06`).
9. **Decision Worker + Command Center** (`09`,`11`).
10. **WebScout** (`08`), **Quote Builder** (`09`).
11. **Autonomy/guardrails hardening + Evaluation Lab** throughout (`13`,`15`).

Full task-level backlog with sizes, milestones (Phase 0–4), and parallelization: `17`.

## 13. Definition of Done (MVP)

- One vertical playbook fully drives intake→follow-up→documents→decision brief→close.
- All 17 states reachable and audited; every active case always has a next action.
- Voice hits latency targets; documents produce evidenced fields with honest confidence.
- Follow-up demonstrably recovers leads without violating anti-spam guarantees.
- Autonomy levels + human approval + audit trail work end-to-end.
- Evaluation Lab reports the metric suite per tenant; hallucination rate on evidence-required
  outputs is near-zero.
- Privacy: encryption, retention, erasure/export, consent handling in place (`16`).

## 14. Open decisions to resolve in Phase 0 (ADRs)

Telephony provider · OCR self-host vs. managed · Postgres-graph vs. Neo4j · Temporal vs.
Celery/Redis · LangGraph-only vs. hybrid · AGPL posture for Firecrawl/Skyvern (`18` §9).

## 15. Guiding rules (apply everywhere)

Evidence over claims · abstain below `θ_conf` · human-in-the-loop at the right moments · never
final legal/medical advice · anti-spam follow-up · full immutable audit · privacy by default ·
narrow scope beats broad autonomy (`02` evidence).
