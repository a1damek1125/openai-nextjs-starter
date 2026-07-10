# AUDIT-REPORT-1 — Route / API Audit

Branch `claude/finalis-ai-casewoker-blueprint-f1huse` · HEAD `d95be03` · evidence: `grep` on `finalis/portal/app.py`.

## Totals
- **340** `@app.{get,post,put,delete,patch}` routes + **23** dynamically-mounted sub-field GET routes (`add_api_route`, used by runtime/write-intent/commit-sim evidence sub-fields).

## Route groups (by 2nd path segment)

| Group | Count | Classification |
|---|---|---|
| `/ai-tools` | 120 | governance: read-only evidence, draft-only, safe verify/policy/registry routes |
| `/evidence` | 40 | domain read + tenant-scoped local writes (upload/review/legal-hold) + proof/merkle read |
| `/crm` | 25 | domain read + tenant-scoped local writes (parties/consent/memory) + opt-in dry-run sync |
| `/ai-tasks` | 22 | governance draft/lifecycle (task intake, transitions) |
| `/ai-artifacts` | 22 | governance versioned artifacts (local, materialization-firewalled) |
| `/quotes` | 20 | domain CPQ writes (local) + mock PDF/handoff |
| `/cases` | 17 | domain case read/write (local) + transcript/analyze |
| `/ai-approvals` | 14 | human approval decisions/grants (no execution) |
| `/ai-runs` | 11 | run ledger (append-only, replay) |
| `/ai-employees` | 6 | identity read |
| `/scheduling` | 5 | domain scheduling writes (local) + mock calendar/video |
| `/admin` | 5 | RBAC-gated admin ops (users/roles/access-logs) |
| `/price-books`,`/pricing-rules`,`/pricing` | 8 | CPQ pricing config (local) |
| `/telephony` | 3 | call-control simulation (mock provider, `provider_is_mock:true`) |
| `/actions` | 3 | communication pipeline (mock Novu/Chatwoot) |
| `/upload-links` | 3 | evidence upload links (`.example` host) |
| `/auth` | 3 | login/me/logout (dev-grade HMAC token) |
| `/governance` | 2 | read-only observability (traces/blocked, redacted) |
| `/dashboard` | 2 | read-only dashboard sections |
| `/completion-loop` | 2 | local case-tick (no external effect) |
| `/confirm`,`/audit` | 2 | confirm page + audit-chain verify |

## Forbidden execution route scan — RESULT: CLEAN

Scanned POST/PUT/DELETE/PATCH paths ending in dangerous verbs. **None present:**

`/commit` · `/execute` · `/release-effects` · `/activate-commitment` · `/activate-b9` · `/grant-authority` · `/grant-b9-authority` · `/issue-token` · `/issue-commit-lease` · `/read-credential` · `/provider/call` · `/mcp/call` · `/llm/call` · `/payment/execute` · `/crm/mutate` · `/evidence/mutate` · `/message/send` · `/export`

The only POST containing the substring "commit" is **`POST /ai-tools/commit-simulations`** — the TOOL-B8 *simulation creator* (safe; verified that `.../{id}/commit`, `/execute`, `/release-effects`, `/activate-commitment`, `/activate-b9`, `/grant-b9-authority`, `/issue-commit-lease` all return **404/405**).

## Domain write routes (present, but SAFE)
Routes like `POST /crm/parties`, `POST /quotes`, `POST /scheduling/appointments`, `POST /evidence/upload`, `POST /cases` **do write** — but only to **local SQLite / local filesystem**, tenant-scoped and RBAC-gated. These are legitimate domain persistence, **not external effects**. Every route whose semantics would be an external send/call/pay terminates in a **mock provider** (`is_mock=True`, `provider_is_mock` in response).

## Route-shadowing control
`app.py` explicitly **hoists** literal `/ai-tools/actions/*`, `/ai-tools/broker/*`, `/ai-tools/runtime/*`, `/ai-tools/write-intents/*`, `/ai-tools/commit-simulations/*` routes ahead of the parameterized `/ai-tools/{tool_id}/*` routes so first-match routing does not shadow them. Covered by the fact that all governance sub-field endpoints resolve 200 in tests.

## Classification summary
- **Read-only evidence / safe verification / policy / registry:** the entire `/ai-tools/{broker,runtime,write-intents,commit-simulations}/*` evidence surface + `/governance/*` + `/dashboard/*` + `/audit/*`.
- **Draft-only:** `/ai-tools/write-intents` (escrow drafts), `/ai-tasks` (intake/lifecycle).
- **Simulation-only:** `/ai-tools/commit-simulations` (B8).
- **Local domain writes (safe):** `/crm`, `/quotes`, `/scheduling`, `/evidence`, `/cases`, `/price-books`, `/pricing-rules`.
- **Mock-provider edges (safe):** `/telephony`, `/actions`, `/upload-links`, quote PDF/handoff, scheduling calendar/video.
- **Dangerous routes:** **NONE.**
- **Ambiguous / needs review:** **NONE** — every write/send path is either local domain persistence or a self-labelled mock.
