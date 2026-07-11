# AUDIT-TRACE-1 — Production Gaps

Recorded, not fixed (audit-only). Ordered by how far each gap sits from a
production deployment that actually acts on the outside world.

## TOP 10 GAPS

1. **No real external effect anywhere.** Non-test outbound network primitives =
   0 (`requests`/`httpx`/`smtplib`/`boto3`/`urllib`/`http.client`). Every
   provider is an in-process mock and the TOOL-B9+ outbox is deliberately inert.
   The system can simulate/draft/prove/recover/observe/admit — it cannot execute.
   This is the master gap; the rest are specializations of it.

2. **No adapter boundary (TOOL-B10) implemented.** The roadmap re-scopes TOOL-B10
   as the "External Adapter Boundary" — the first governed real effect — but no
   such module, route, migration, or test exists. Until it does, no proof ever
   crosses into reality.

3. **EMP-A1 handoff has no consumer (EMP-A2 NOT_FOUND).** EMP-A1 *prepares* one
   fenced single-use handoff but executes nothing; the consumer that would turn
   an admitted work item into bounded execution is named (`next_coding_sp =
   EMP-A2`) but unbuilt. Admitted work currently terminates at the fence.

4. **Delivery/notification is MOCK_ONLY.** `finalis/actions/adapters.py` uses
   `NovuMock` / `ChatwootMock`; no real email/SMS/chat provider. The whole
   Action & Communication pipeline is proven up to `send`, then hits a mock.

5. **Telephony dial is a mock provider.** `finalis/telephony/engine.py` `dial()`
   returns a simulated result; no PSTN/SIP/Twilio-class integration. All 11
   permission blockers and consent logic are real; the call itself is not.

6. **Scheduling calendar/video providers are mocks.** Confirmation tokens,
   double-booking property, and state machine are real; calendar and video links
   are mock — no Google/Microsoft/Zoom-class integration.

7. **CPQ payment / PDF / e-signature are mocks.** Decimal pricing, approval
   gating, and change orders are real and tested; payment capture, PDF rendering,
   and e-sign are mock providers.

8. **CRM external sync is a mock.** `crm_external_sync_events` /
   `crm_external_sync_cursors` and the sync APIs exist, but there is no real
   external CRM connector — sync is simulated.

9. **Persistence + concurrency are dev-grade.** SQLite with a documented
   single-writer-per-DB assumption (`db.py` audit-chain notes). No Postgres, no
   connection pooling, no multi-writer transaction story for production load;
   `create_app()` is an ~11.9k-line monolith whose shared closure scope has
   already caused cross-SP name-collision regressions.

10. **Voice ASR/TTS are router seams.** The Voice Engine routes to ASR/TTS
    providers behind mock seams; no real speech vendor is wired, so live
    transcription/synthesis does not happen.

## Cross-cutting notes
- **Not a correctness gap:** the mock boundary is intentional for the governance
  layers (their theorems are precisely *"produces no external effect"*). The gap
  is that *product* value requires those effects to eventually be real, governed
  by the same ladder.
- **Honesty labelling is present** (~217 references; provider honesty labels in
  UI since `7f3a1be`), so the system already **discloses** its mocks rather than
  pretending — a genuine strength to preserve when real adapters land.
- **Test coverage is broad but proves governance, not integration.** 5640
  collected tests exercise kernels, APIs, and simulated E2E flows; none exercise
  a real third-party call (there is none to exercise).

## What production-readiness would require (not a roadmap — a gap statement)
A governed external adapter (TOOL-B10) consuming EMP-A1/EMP-A2 handoffs; real
provider integrations behind that adapter with the existing consent/approval/
audit gates enforced live; a production datastore; and a decomposition of the
portal monolith. None of these exist today.
