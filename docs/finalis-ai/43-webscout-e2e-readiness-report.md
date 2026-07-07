# Finalis AI — WebScout E2E Readiness Report

> Reviewer report on branch `claude/finalis-ai-enterprise-e2e-autofix` (scaffold: 102 passing
> tests). Companion to `08-webscout-web-research.md` (design + restrictions),
> `30-webscout-verification-plan.md` (verification plan), `14-mvp-and-roadmap.md` (phasing).

## Verdict

**Policy/safety layer = Implemented and tested. Fetching = Designed (WebScout v1 ships in
Phase 3 per `14`).**

`finalis/webscout.py` is the executable form of the `08` restriction policy: hard
restriction enforcement, mandatory source recording, and trust scoring — proven against
fixture pages. There is no real browsing: no Firecrawl, no Playwright, no network I/O. The
real fetch layer plugs in behind `FetcherProtocol` later.

## What IS tested (`tests/test_documents_webscout_ocr.py::TestWebScoutPolicy`)

- `test_public_page_researched_with_source_record` — researching a public manufacturer PDF
  produces a `Source` record with `url`, `date_checked`, `snippet` (280-char cap from page
  content), and a computed `trust_score`: the fixture trust vector
  (authority .9, recency .8, corroboration .5, directness 1.0, transparency 1.0) yields
  exactly **81.5** through `scoring.source_trust`, and confidence is derived from it.
  Mandatory source recording is enforced in code — a fact without a `Source` cannot exist;
  every research emits a `webscout.research_completed` audit event carrying the source id.
- `test_hard_restrictions_refuse_loudly` (parametrized ×4) — **all four hard restrictions**
  from `08` §2 — `requires_login`, `paywalled`, `captcha`, `robots_disallowed` — raise
  `RestrictionViolation` AND emit a `webscout.blocked` audit event with the reason. The
  restrictions are never bypassed and never fail silently; the loop in
  `finalis/webscout.py::WebScout.research` checks them before any content is used.

## Designed but NOT coded (per `08`, verification plan in `30`)

- **Sandboxing** — least-privilege browser sandbox with HTTP-layer policy interposition
  (ceLLMate-style), no credentials in the sandbox (`08` §3, `30` §5 item 3).
- **Injection defense** — the R1–R6 red-team suite (`30` §4): indirect prompt injection,
  exfiltration attempts, trust-inflation injection, continuous fuzzing in CI. No fixture
  site, no injection corpus exists yet.
- **Contradiction detection / corroboration across sources** — designed in `08`, not coded.

## Design guarantee honored by the scaffold

`08` guarantees that **WebScout has no write actions and cannot mutate case state** — it is
read-only and returns proposed facts only. The scaffold honors this structurally:
`WebScout.research()` takes no `Case`, touches no case entity, and returns a `Source`
object; the ONLY writes it performs are append-only audit events (`webscout.blocked`,
`webscout.research_completed`). Any state change driven by web research must go through the
normal evidence → confidence → autonomy-gate path, same as every other fact source.

## Backlog to real WebScout (Phase 3)

1. **Firecrawl adapter behind `FetcherProtocol`** — robots-respecting fetch/extract to
   LLM-ready markdown (`08` §"Default"); the fixture fetcher and the real adapter must pass
   the identical policy test suite (the four restriction tests run unchanged against real
   interstitial fixtures).
2. **Sandboxing** — ceLLMate-style HTTP-layer policy interposition: allowlist-scoped
   requests, zero credentials in the environment, out-of-scope/side-effecting requests
   blocked at the HTTP layer, asserted by server logs.
3. **Injection red-team suite** — build the fixture site + injection corpus of `30` §3–4
   (planted paywall/CAPTCHA/login interstitials, R1–R6 injection pages), run it in CI; any
   successful attack is a P1 and becomes a permanent regression test.
4. **Trust calibration** — validate `source_trust` weights against human judgments on real
   sources; injected self-descriptions must not inflate Authority (trust computed from our
   own assessment, never from page claims — `30` R4).

Until item 1 lands, all WebScout capability claims must be phrased as policy guarantees
(tested) plus planned fetching (designed) — never as live web research.
