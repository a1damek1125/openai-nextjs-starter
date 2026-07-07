# Finalis AI — E2E MVP Flow Verification (Executable Simulation)

> Companion to `26-math-and-algorithm-verification.md`, `27-state-machine-verification.md`,
> and `31-completion-loop-verification.md`. Verified on branch
> `claude/finalis-ai-enterprise-e2e-autofix`; full suite: **102 tests passing**
> (`python3 -m pytest tests/ -q`).

**Status: E2E FLOW IMPLEMENTED AS EXECUTABLE SIMULATION AND PASSING.**
The end-to-end MVP scenario lives in `tests/test_e2e_mvp_flow.py` and runs green against the
executable scaffold in `finalis/` (`state_machine.py`, `scoring.py`, `completion_loop.py`,
`autonomy.py`, `documents.py`, `certainty_core.py`, `audit.py`, `models.py`). This is **not a
production system** — it is a deterministic simulation over the scaffold, exactly as the
verification mandate required ("if no application code exists, create a minimal executable
simulation in tests that proves the logic"). Where docs 26/27 could only audit prose, this
document points at assertions that execute.

---

## 1. The 20 mandated steps → executable coverage

Primary test: `test_e2e_hvac_quote_flow` in `tests/test_e2e_mvp_flow.py`.
All line references are to that file.

| # | Mandated step | What the test does | Assertion that proves it |
|---|---|---|---|
| 1 | Contact arrives (call/web form) | Mock inbound phone transcript fixture `TRANSCRIPT` (Poznań AC-install request, 3 utterances); `contact.inbound_received` audit event appended | Step 20's event-type check requires `"contact.inbound_received" in types` |
| 2 | Intake extraction | `TRANSCRIPT["extracted"]` is the mocked Intake Worker output (name, phone, address, service_type, urgency, preferred date) | `assert intake["address"] and intake["service_type"]` |
| 3 | Case created | `Case(tenant_id="hvac-tenant-1", autonomy_level=3)` instantiated in `NEW_CONTACT` | Every subsequent `transition(...)` call succeeds from this object; final invariant check passes |
| 4 | Case graph stored | Client promise ("send room photos", due +8h) appended to `case.promises`; two `MissingItem`s (`room_photos` blocks_quote=True, `device_info`) appended to `case.missing_items` | Step 6 assertions read this graph back (`any(m.blocks_quote ...)`); Step 10 marks items `received` and promise `fulfilled` |
| 5 | State transitions begin | `transition()` drives NEW_CONTACT → INTAKE_IN_PROGRESS → WAITING_FOR_CLIENT_INFO; `lead_score` and `mis` computed and stored on the case | Transitions raise `IllegalTransition` if not in table (none raised); each writes a `case.state_changed` audit event counted in Step 19 |
| 6 | Missing-info detection | Missing Information Hunter result: photos block the quote; everything still missing | `assert any(m.blocks_quote for m in case.missing_items)`; `assert case.mis_score == 1.0` |
| 7 | Follow-up scheduled + sent (autonomy-gated) | `gate(case, "send_missing_info_request")` at autonomy L3, then `CompletionLoop.send_followup(..., channel="whatsapp")` | `assert g.allowed` (L3 permits missing-info request); `assert loop.send_followup(...)` returns True and emits `followup.sent` |
| 8 | Client sends document | `Document(doc_type="nameplate_photo", ocr_quality=0.85, fields=[...])` constructed; case moved to WAITING_FOR_DOCUMENTS | Transition legal per table; document carries two `ExtractedField`s |
| 9 | Mock OCR ingest | `ingest_document(case, doc, audit, critical_fields={"room_area_m2"})` runs field-level confidence gating (`evidence_confidence` per field) | `decisions` returned per field; `document.analysis_completed` required in Step 20's event-type check |
| 10 | EvidenceReference created | `EvidenceReference(source_type="document_region", source_id=doc.id, locator={"page": 1}, snippet="Midea X12", confidence=0.81)` appended; missing items marked received, promise fulfilled | Object appended to `case.evidence`; graph state consumed by later steps |
| 11 | Low-confidence critical field → human review, case proceeds | `room_area_m2` has confidence 0.7·0.6·1.0·0.9 = 0.378 < θ_conf 0.6 and is quote-critical; `device_model` passes | `assert outcomes["device_model"] == "accepted"`; `assert outcomes["room_area_m2"] == "human_review"`; then `assert not scoring.must_escalate(esc)` (1.12 < 1.5) — the *field* routes to a human while the *case* legally advances to DOCUMENT_ANALYSIS |
| 12 | Offer comparison | Two mock offers: ours €8 400 vs competitor €7 700; `normalize_prices` sets the price axis (cheapest → 1.0); `offer_score` on the 7 weighted axes | `assert s_ours > s_comp` — value (warranty/service/scope) beats the cheapest price, the exact behavior 10 §offer-comparison demands |
| 13 | Decision brief + LGGT-compatible certificate | `build_facts(doc.fields)` → `certainty.certify("decision_brief:"+case.id, facts, policy_version="hvac-playbook-v1")` via `NullAdapter`; brief dict embeds `certificate_id` | `assert cert.verdict == "heuristic" and cert.audit_id`; `certainty.stamped` required in Step 20's event-type check |
| 14 | Human approval required for quote | `gate(case, "send_rule_covered_quote")` — action class requires L4, case is L3 | `assert not g2.allowed and g2.approval is not None` (INV-3: blocked action converts to a queued `HumanApproval`); `approval.requested` in event-type check |
| 15 | Approved | `g2.approval.decision = "approved"`, `decided_by = "owner-1"`; `approval.decided` audit event written by actor `human` | `approval.decided` required in Step 20's event-type check |
| 16 | OFFER_SENT | `transition(case, CaseState.OFFER_SENT, actor="human", reason="approved", ...)`; next action + due time set | Legal per table QUOTE_PREPARATION → OFFER_SENT; counted in the 8 audited state changes |
| 17 | Completion-loop follow-up with anti-spam + stuck sweep | FOLLOW_UP_ACTIVE; send at T0+25h succeeds, second send 1h later blocked by `min_interval` (20h); nightly sweep run at day 6 and day 21 | `assert loop.send_followup(case, t, ...)`; `assert not loop.send_followup(case, t + timedelta(hours=1), ...)`; `assert loop.stuck_sweep([case], T0+6d) == []` (12.0 < θ_stuck 40); `assert queue and queue[0]["case_id"] == case.id` at day 21 (42.0 ≥ 40) |
| 18 | WON | Client accepts; `transition(..., CaseState.WON, actor="human", ...)` | `assert case.state is CaseState.WON`; terminal-adjacent cleanup drops `next_best_action` |
| 19 | Audit chain verified, every transition audited | Hash chain of the full run re-verified; state-change events counted | `assert audit.verify_chain()`; `assert len(state_changes) == 8` — exactly one `case.state_changed` per transition (INV-4) |
| 20 | All expected event types present + invariant clean | Set of event types checked against the mandated list; completion-loop invariant checker run on the closed case | `assert expected in types` for each of `contact.inbound_received`, `case.state_changed`, `followup.sent`, `document.analysis_completed`, `approval.requested`, `approval.decided`, `scores.recomputed`, `certainty.stamped`; `assert loop.check_invariants([case]) == []` |

### Second test: escalation and recovery variants

`test_e2e_escalation_and_recovery_paths` covers the two off-happy-path branches:

- **Escalation path:** angry client in NEGOTIATION at autonomy L4;
  `escalation_score(0.4, 0.6, 0.3, 0.9, 0.0, 0.2)` = **2.4 ≥ θ 1.5** →
  `assert scoring.must_escalate(esc)`; global interrupt edge fires
  (`escalation_interrupt=True`) → `HUMAN_REVIEW_REQUIRED`;
  `assert angry.effective_autonomy == 2` (invariant: autonomy frozen to L2) and
  `assert not gate(angry, "send_reminder").allowed` (outbound send blocked while frozen).
- **Recovery path:** silent client exhausts 3 follow-ups →
  `park_exhausted` → `assert silent.state is CaseState.RECOVERY_LATER` with a wake time;
  wake transitions legally back to FOLLOW_UP_ACTIVE; `assert audit.verify_chain()`.

---

## 2. What the simulation does NOT prove (honest list)

1. **No real STT/LLM extraction.** Step 1–2 use the `TRANSCRIPT` fixture with a pre-baked
   `extracted` dict. The determinism boundary flagged in doc 26 §1.3 (LLM-derived U/D inputs)
   is untested end-to-end — reproducibility is proven only from the persisted input vector onward.
2. **No real OCR.** `Document`/`ExtractedField` confidences are fixture values; the field-gating
   logic is real, the perception layer is not.
3. **No persistence or cross-process restart.** Only the scheduler-state rebuild is simulated
   (`tests/test_completion_loop.py::TestDurability` drops the loop object and rebuilds from case
   rows). No database, no transactional outbox, no crash-recovery of a half-committed transition
   (doc 27 issue E remains a design gap).
4. **No real channels.** WhatsApp/SMS/email sends are audit events, not deliveries; delivery
   failures, bounce handling, and channel fallback are unexercised.
5. **No wall-clock timing.** All time is a simulated `datetime` cursor; quiet-hours and cadence
   logic are tested logically, not against timezone/DST edge cases.

## 3. Verdict

**PASS at the simulation tier.** The 20-step MVP flow, the escalation interrupt, and the
recovery park/wake path all execute against the real transition table, real scoring functions,
real autonomy gates, and a real hash-chained audit log — with every mandated safety property
asserted (blocks_quote gating, confidence gating on critical fields, L3<L4 approval,
anti-spam min-interval, stuck-sweep thresholds, HRR autonomy freeze, chain integrity).

Next hardening steps, in order:

1. Replace fixtures with contract tests against a real STT/extraction service behind the same
   `extracted` schema (doc 28 plan) and a real OCR engine (docs 29/47).
2. Add persistence + transactional outbox and re-run this exact test through a
   kill-and-restart harness (resolves doc 27 issue E at the code level).
3. Wire real channel adapters with idempotency keys; assert `action_failed` events on injected
   delivery failures.
4. Promote the simulated clock to a controllable time provider and add timezone/DST cases for
   quiet hours.
5. Feed Evaluation Lab (doc 15) data back into the provisional thresholds (θ_stuck, θ_breach)
   before calling them calibrated.
