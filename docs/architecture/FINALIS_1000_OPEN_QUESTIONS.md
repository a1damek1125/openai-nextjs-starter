# FINALIS 1000 — OPEN QUESTIONS

**SP0000 · docs-only.** Unresolved questions deferred to named downstream SPs. None of these is a P0/P1 *contradiction* in the locked architecture — each is a decision the architecture is explicitly designed to defer without a future dead end. Severity: **P2** = design decision; **P3** = research/monitoring item.

| ID | Question | Severity | Owner SP | Why deferrable now |
|---|---|---|---|---|
| OQ-01 | Which durable-execution engine (Temporal vs alternative vs in-house)? | P2 | SP0004 (TDR) | Architecture locks only *durable capability required + engine replaceable* (D-0000-16). Business state stays authoritative in Finalis regardless of engine. |
| OQ-02 | Production datastore choice + migration path from SQLite (PostgreSQL assumed). | P2 | SP0004 / Layer 10 | Layer 10 is a non-authoritative substrate behind stable contracts; swap does not touch authority. |
| OQ-03 | Final frontend framework + version for the new Employee OS portal. | P2 | SP0004 / SP0008 | Portal is presentation, never authority (INV-0000-05); D-0000-15 strangler migration. |
| OQ-04 | Exact employee state-machine transition table. | P2 | SP0012 | SP0000 locks the required state set + "no UI/provider/model may define business state". |
| OQ-05 | Event architecture details (ordering guarantees per class, idempotency keys, replay windows). | P2 | SP0014 | SP0000 locks event classes + principles (tenant-bound, versioned, idempotent, replay-safe). |
| OQ-06 | Zero-Lost-Work formal predicate + enforcement mechanism. | P2 | SP0015 | SP0000 locks the invariant as mandatory; formula stated, not implemented. |
| OQ-07 | Current LGGT source truth — has it advanced beyond older docs? | P3 | SP0021 | LGGT+ role is locked (Certified Intelligence Plane, not brain/oracle/executor); direct source audit precedes implementation. |
| OQ-08 | MCP authorization/transport specifics at the Layer 8 gateway. | P3 | SP0005 / Layer 8 | Locked: MCP output is data, servers are external trust domains, not authority. |
| OQ-09 | A2A interoperability surface — which agents, which trust model. | P3 | SP0005 / Layer 8 | Locked: A2A is an interoperability boundary, never internal authority. |
| OQ-10 | Observability vendor + content-capture policy (privacy/redaction). | P2 | SP0005 / Layer 10 | Locked: OpenTelemetry-compatible, correlation IDs enumerated, no default content capture. |
| OQ-11 | Regulatory risk-classification taxonomy for HR/legal/finance domains (EU AI Act high-risk mapping). | P2 | SP0005 | SP0000 is not legal advice; it locks that risk classification lives in the architecture with human authority not bolted on. |
| OQ-12 | Learning promotion criteria + eval thresholds (regression gates). | P2 | SP0006 | Locked: no direct production self-modification; candidate→eval→promotion pipeline mandatory. |
| OQ-13 | Global brand naming (public product identity may change; "Finalis"/"ViktorAI" internal codenames). | P3 | SP0010 | Naming is independent of architecture; INV-0000 unaffected. |
| OQ-14 | Model-router policy (which model for which task/risk/cost/latency band). | P2 | Layer 4 impl | Locked: models replaceable (D-0000-06); router is advisory, never authority. |
| OQ-15 | Skill Genome representation + versioning + rollback semantics. | P2 | Layer 4/6 impl | Locked: skills are strategic Finalis IP; versioned; upgrades must be survivable (§FAILURE). |

## Recorded non-questions (already locked, listed to prevent re-litigation)

- Finalis identity = Outcome-Driven, Self-Improving, Multilingual, Omnichannel **AI Employee Operating System** (D-0000-01). Not open.
- Authority lives only in the governance chain. Not open.
- One user-facing employee, many internal specialists. Not open.
- Real effects are gated behind Layer 8. Not open.
- Do-not-rebuild list. Not open.

## Escalation policy

If any downstream SP discovers that an open question, once answered, would **force a core rewrite** (violating INV-0000-09 or the acyclic spine), that is a P0 escalation back to an architecture-lock revision — not a silent workaround.
