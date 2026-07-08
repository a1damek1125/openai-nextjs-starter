# Finalis Working Portal — Founder / CTO Report

**Date**: 2026-07-07 · **Branch**: `claude/finalis-working-portal-mechanism`
**Baseline**: 212/212 (branch `claude/finalis-case-command-center`, head `76fefa3`)
**Now**: `python3 -m pytest tests/ -q` → **228 passed** (15 portal API tests + 1 full
browser E2E added; all 212 prior tests untouched and passing).

**Run locally**:
```bash
pip install fastapi uvicorn httpx playwright pytest
python3 -m finalis.portal.serve          # http://127.0.0.1:8000
# login: owner@demo.finalis / demo1234   (manager@/operator@/viewer@ too)
python3 -m pytest tests/ -q              # full suite incl. browser E2E
```

Wording: **Implemented and tested** = passing tests · **Mocked** = mock behind a real
interface · **Scaffolded** = interface exists, provider not real · **Requires credentials/
external provider** as marked.

---

## The 16 direct answers

**1. What is now a working portal?**
A user opens a browser, **logs in** (real PBKDF2 auth + HMAC session tokens), sees the
**Case Command Center rendered from real APIs over real persistence** (no hardcoded UI
data), opens a case, **runs the completion loop**, triggers a **photo request** (mock
WhatsApp send + real secure upload link), the **client opens the public upload page and
uploads**, the missing item **resolves**, the owner walks the case through **legal state
transitions** (the browser test proves an illegal jump is refused), closes it **WON**, and
the **audit chain shows VALID** — all verified end-to-end by a Playwright test in real
Chromium.

**2. What is connected to real persistence?** Everything the flow touches: tenants, users,
parties, cases (+missing items, promises as aggregate children), transcripts + analyses,
action requests, message drafts, executions, delivery events, upload links, documents,
offers, and the **append-only audit chain stored in SQL** (verify re-reads rows and
validates; restart-survival is tested — a second app instance over the same file sees the
data and an intact chain). Engine: **SQLite (Implemented and tested)** with versioned,
idempotent migrations; **PostgreSQL is the production path (Scaffolded)** — portable SQL,
swap documented, not yet exercised.

**3. Which APIs are implemented?** Auth (login/logout/me), all 10 dashboard sections,
cases (list/create/get/transition/timeline/audit-events), transcripts + analyze-
conversation, completion-loop (run, run-case), actions (request, approve, reject),
upload-links (create/open/upload — public token-auth), documents, offers (create/send/
simulate-client-response), audit verify. All tenant-scoped, auth-gated, RBAC-checked;
FastAPI auto-generates OpenAPI at `/docs`.

**4. Which UI pages are implemented?** Login; the portal (summary cards, action queue,
approval queue with approve/reject, case list, case detail with timeline/missing/promises/
documents/offers/audit-badge + loop/photo-request/transition/close controls, pipeline,
activity feed — all fetched from the APIs with loading/error/empty states); the
client-facing secure upload page. **Not built**: a full Next.js app (this shell consumes
the same endpoints a Next.js UI will), filters/search, offer-editor page, dedicated audit
browser.

**5./6. Providers real vs mocked?** **All external providers are Mocked behind real
interfaces**: WhatsApp/SMS/email delivery (`NotificationAdapter` — the direct-adapter seam
per the ADR), Chatwoot handoff, Temporal scheduling (simulated clock), ASR/TTS/OCR (from
the earlier modules). **Zero real provider calls exist.** Real integrations Require
credentials/external providers: Meta WhatsApp Cloud API (+ business verification — longest
lead item), Twilio, SMTP, self-hosted Chatwoot, Temporal cluster (compose file provided).

**7. Does login work?** **Yes — implemented and tested** (browser + API: good/bad
credentials, garbage tokens, unauthenticated requests all behave correctly).

**8. Does RBAC work?** **Yes at the implemented surface — tested**: viewer cannot create/
transition cases; operator cannot approve; owner/manager can. Not yet: per-operator
assigned-case filtering, approval-of-own-action prevention at API level.

**9. Does tenant isolation work?** **Yes — tested**: second seeded tenant sees zero demo
cases; cross-tenant case reads/transitions return 404; every query is tenant-filtered.
DB-level RLS: not implemented (application-level only).

**10. Does browser E2E pass?** **Yes** — real Chromium via Playwright, full journey,
including the negative test (illegal transition blocked in the UI).

**11. Does the full case flow work from UI?** **Yes** — the acceptance journey (login →
dashboard → case → loop → action → upload → resolve → transitions → WON → audit VALID)
is exactly what the browser test executes.

**12. Are all old tests still passing?** **Yes — 212/212 untouched, 228 total.**

**13. What is still not production-ready?** Real providers (everything outbound is mock);
Postgres + RLS; HTTPS/session hardening + rate limiting on auth; approval-expiry worker;
observability (structured logs/metrics/traces); backups/DR; the Next.js UI; SSO
(future-ready design only); per-tenant quotas/kill switch; CI pipeline.

**14. What requires external credentials?** WhatsApp Cloud API (Meta business
verification + message templates), Twilio, SMTP, Chatwoot instance, Temporal cluster,
S3/MinIO for real file storage (uploads currently store metadata + simulated content).

**15. Before first customer pilot**: wire ONE real channel (Twilio SMS is fastest;
WhatsApp verification started in parallel); Postgres + backups; real file storage for
uploads; HTTPS deployment behind a reverse proxy; approval-expiry + owner notification
emails; basic monitoring; a human-written onboarding checklist.

**16. Before public SaaS launch**: everything in 15 plus multi-tenant RLS, SSO, billing
(Stripe per doc 23), rate limiting + abuse protection, DR plan, pen test, DPA/GDPR
paperwork, the full Next.js UI, and the Evaluation Lab running against production traffic.

---

## Bugs found & fixed during this phase (all with regression coverage)
1. **Audit chain forked across writers** — `DbAuditLog` chained from its in-memory head;
   two instances over one DB (seeder + app) broke verification. Now chains from the DB's
   last row; restart-survival test proves it.
2. **Payload digest drift** — datetimes hashed differently at append vs. after SQL
   round-trip; payloads are now JSON-normalized before digesting.
3. **`save_case` clobbered `title`/`client_party_id`** on every aggregate save — found by
   the browser E2E (case row "disappeared" after upload). Presentation fields now update
   only when explicitly provided.
4. **Browser test flakiness root-caused** to zombie dev servers (port reuse) — fixture now
   fails loudly if the port is occupied and SIGKILLs on teardown.

## Verified / not verified
**Verified by tests**: everything in answers 1–12. **Not verified**: real provider
delivery, Postgres, concurrency/load, HTTPS deployment, long-session behavior, file
content storage (metadata-only uploads).

## Top 10 next tasks
1. Twilio SMS adapter behind `NotificationAdapter` + signed delivery webhooks (first real channel).
2. Start Meta WhatsApp Business verification + template approval (long lead time).
3. Postgres driver for `Database` + run the suite against compose Postgres.
4. Real file storage (MinIO/S3 presigned PUT) behind the upload service + AV scan hook.
5. Temporal worker running FollowUpWorkflow/HumanApprovalWorkflow against the compose cluster.
6. Next.js portal consuming the same APIs (contracts proven); Playwright suite reused.
7. Auth hardening: rate limiting, session revocation, password policy, audit on login.
8. Approval expiry worker + owner email digest (reusing the HTML renderer).
9. CI: GitHub Actions running the 228-test suite + browser E2E headless.
10. Observability: structured logs + the 8 designed metrics + health endpoint.
