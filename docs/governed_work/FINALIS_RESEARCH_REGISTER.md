# FINALIS SP0006 — Research Register (Governed Work Constitution)

External sources provide research and interoperability input. They **never**
become Finalis internal authority (D-0006-63, INV-0006-45). All statuses are as
recorded at execution (2026-07-12) and must be re-checked on any future execution
day. Swarm roles: SWARM-J (security/agentic threats), SWARM-K (Viktor/competitor
reference), SWARM-L (authorization standards).

## 1. Viktor product reference (SWARM-K) — vendor claims, not internal architecture

Public patterns treated as product guidance only (do not infer undocumented
internals): plain-language delegation; Slack/Teams as work surfaces; cross-tool
execution; review-first sensitive actions; read/write separation; recurring
scheduled work; persistent memory + SOPs; credentials isolated from model
context; finished artifacts returned to the user.

- https://viktor.com/ · /product · /security
- https://viktor.com/blog/how-to-keep-a-human-in-the-loop-with-your-ai-employee
- https://viktor.com/blog/how-to-control-what-your-ai-employee-can-access
- https://viktor.com/blog/how-to-control-where-your-ai-employee-works
- https://viktor.com/blog/how-to-give-your-ai-employee-memory
- https://viktor.com/blog/how-to-roll-out-an-ai-employee-to-your-whole-team
- https://viktor.com/blog/how-to-add-an-ai-employee-to-microsoft-teams

**Finalis mapping:** "one message → completed work" (Viktor simplicity) sits on
top of Finalis governance (candidate intent → canonical work order → outcome
contract → bounded delegation → attenuated leases → contextual approvals →
verified outcome). Memory/context are NEVER a source of authority (INV-0006-05/06).

## 2. NIST AI agent identity & authorization (SWARM-J) — concept-stage

- https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative
- https://www.nist.gov/news-events/news/2026/02/announcing-ai-agent-standards-initiative-interoperable-and-secure
- https://www.nccoe.nist.gov/projects/software-and-ai-agent-identity-and-authorization
- https://www.nist.gov/identity-and-access-management

NCCoE material is **concept-stage guidance**, not a completed standard. Informs
execution-identity + delegation naming; does not define Finalis work semantics.

## 3. OWASP agentic security (SWARM-J) — threat mapping only

- https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- https://genai.owasp.org/initiatives/agentic-security-initiative/
- https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/
- https://genai.owasp.org/llm-top-10/

**Mapped to §17 threat model:** prompt/indirect-injection, scope smuggling, goal
hijacking, authority laundering, delegation-cycle, capability amplification, lease
/approval replay, target/parameter substitution, budget double-spend, reservation
/revocation race, memory/context permission injection, cross-tenant delegation,
credential leakage, hidden side task, recurrence persistence abuse, cancellation
bypass, unknown-outcome duplicate effect, outcome-proof forgery, verifier
collusion, accountability erasure, proof tampering.

## 4. GNAP + OAuth standards (SWARM-L) — external projections only (D-0006-63)

- GNAP: https://www.rfc-editor.org/rfc/rfc9635.html · https://datatracker.ietf.org/doc/rfc9635/
- OAuth RAR (Rich Authorization Requests): https://www.rfc-editor.org/rfc/rfc9396.html
- OAuth Token Exchange: https://www.rfc-editor.org/rfc/rfc8693.html
- OAuth Pushed Authorization Requests: https://www.rfc-editor.org/rfc/rfc9126.html

May inform external projections of a Finalis lease; do **not** define internal
work semantics. `projections.py` treats these as transport/evidence, never
authority.

## 5. Current IETF agent-authorization drafts (SWARM-L) — DRAFTS, not authority

Treated as drafts (no constitutional authority built on any of them):

- draft-niyikiza-oauth-attenuating-agent-tokens
- draft-mcguinness-oauth-mission · draft-mcguinness-oauth-actor-receipts
- draft-chen-oauth-agent-authz-use-cases
- draft-araut-oauth-transaction-tokens-for-agents
- draft-rosomakho-oauth-txn-challenge · draft-valverde-oauth-pact
- draft-liu-oauth-rego-policy

(all under https://datatracker.ietf.org/doc/<name>/)

## 6. Object capabilities: zcap, UCAN, Macaroons (SWARM-L)

- https://w3c-ccg.github.io/zcap-spec/ · https://www.w3.org/TR/did-core/ · https://www.w3.org/TR/vc-data-integrity/
- https://ucan.xyz/ · https://ucan.xyz/guides/getting-started/
- https://research.google/pubs/macaroons-cookies-with-contextual-caveats-for-decentralized-authorization-in-the-cloud/

**Principles adopted internally** (SP0006 owns the canonical lease; external
formats require projections): attenuation, contextual caveats, delegation chain,
non-forgeability, bounded invocation, revocation. These directly shaped the
capability-lease partial order (D-0006-16) and the `projections.py` caveat model.

## 7. Authorization policy engines (SWARM-L) — SP0004-gated, not adopted

- https://cedarpolicy.com/ · https://github.com/cedar-policy
- https://openpolicyagent.org/ · /docs · /docs/policy-language

Cedar/OPA/Rego are **not** introduced (D-0006-64). SP0006 reference tooling
remains standard-library-only and deterministic.

## 8. Formal verification (SWARM-I)

- https://lamport.azurewebsites.net/tla/tools.html · https://github.com/tlaplus/tlaplus

Bounded model checking for critical invariants only (state transitions, authority
monotonicity, lease attenuation, budget conservation, no-self-approval,
cancellation) via the standard-library `modelcheck.py`. TLA+ is **not** a
production dependency; optional TLA+ artifacts may cross-check if repo policy
permits.

## 9. OpenAI agent/subagent reference (SWARM-K) — provider documentation

- https://developers.openai.com/api/docs/guides/agents · /codex/subagents
- https://openai.com/index/unrolling-the-codex-agent-loop/
- https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/

Patterns (specialized subagents, tool-mediated execution, harness separated from
model, collected results, enterprise RBAC) inform delegation/execution-identity
structure; treated as provider docs.

## 10. Contracts & delegation research (arXiv) — research, not Finalis proof

Reported theorems/benchmarks are NOT treated as Finalis proof (research inputs
only): 2601.08815, 2602.22302, 2604.02767, 2606.30970, 2606.22916, 2605.20704,
2606.17099, 2603.02961, 2606.03518, 2603.20953, 2602.23193, 2604.23646, 2605.23989.

## Doctrine

Every external input above is classified as research / interoperability /
projection. None grants authority inside Finalis. The canonical work semantics,
capability leases, budgets, approvals, and outcome verification are defined solely
by this constitution and its deterministic repository-local tooling.
