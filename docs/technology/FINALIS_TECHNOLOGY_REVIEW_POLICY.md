# FINALIS Technology Review Policy (SP0004 D-0004-55/56)

Evidence freshness is technology-relative — there is **no universal review
interval** (D-0004-56). Each TDR declares a `volatility_class`; the review horizon
follows it:

| Volatility class | Review horizon | Example technologies |
|---|---|---|
| VERY_HIGH | 90 days | model providers, MCP |
| HIGH | 180 days | voice/telephony/email providers, A2A |
| MEDIUM | 365 days | FastAPI, SQLite, object storage, OpenTelemetry |
| LOW | 730 days | pytest |
| FOUNDATIONAL | 1095 days | Python (also pinned to EOL 2027-10-31) |

A decision is `REVIEW_DUE` when `review_by < today` or when critical evidence is
stale; an invalidating trigger fires `INVALIDATED` (§11.12). Review triggers are
explicit per TDR (e.g. "python EOL", "real model required", "new finalized MCP
spec"). The review clock is computed deterministically from local records; the
actual current status of external standards must be **refreshed through research**
(D-0004-48) — floating "latest" is never accepted for protected protocols
(D-0004-49).
