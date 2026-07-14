# FINALIS 1000 — SP0005 Research Register (Source URLs)

Research corpus for the Safety Kernel, Assurance & Regulatory Truth Constitution,
corroborated on execution day (2026-07-11) by SWARM-F (regulatory temporal truth)
and SWARM-E (agentic threat taxonomies). **Honesty note:** `WebFetch` is blocked
by bot-protection (HTTP 403); URLs are recorded as provided and corroborated
against search snippets. Anything dated after 2026-07-11 is flagged future-dated
and NOT recorded as currently-in-force (INV-0005-18/19/20). No research paper is
treated as a binding standard (AC-0005-226); no ISO certification is claimed
(AC-0005-223).

## Verified 2026-07-11 regulatory status (SWARM-F)
- **EU AI Act (Reg. (EU) 2024/1689)** — `BINDING_LAW`; entry-into-force 2024-08-01;
  prohibited practices + AI literacy applicable 2025-02-02; GPAI 2025-08-02;
  general application + high-risk Annex III stand-alone 2026-08-02; embedded
  high-risk 2028-08-02.
- **Digital Omnibus (high-risk deferral)** — `ADOPTED_NOT_YET_APPLICABLE`
  (proposal 2025-11-19; political agreement 2026-05-06; Council adoption
  2026-06-29; **OJ publication pending**). **Political agreement ≠ enacted law**:
  the binding high-risk stand-alone date remains **2026-08-02** until publication.
- **High-risk classification guidelines** — `DRAFT_OFFICIAL_GUIDANCE`, consultation
  OPEN to 2026-07-23.
- **Prohibited-practices guidelines** — `FINAL_OFFICIAL_GUIDANCE` (2025-02-04);
  the Art. 5 prohibitions are `BINDING_LAW` since 2025-02-02.
- **AI system definition guidelines** — `FINAL_OFFICIAL_GUIDANCE` (2025-02-06).
- **GPAI Code of Practice** — `VOLUNTARY_OFFICIAL_CODE` (2025-07-10).
- **Serious-incident guidance (Art. 73)** — `DRAFT_OFFICIAL_GUIDANCE`; obligation
  applies 2026-08-02.
- NIST AI RMF / 600-1 / 800-4 / Agent Standards Initiative — `RESEARCH`; OWASP /
  MITRE ATLAS — `VENDOR_GUIDANCE`; ISO/IEC 42001/23894/42005/42006 —
  `INTERNATIONAL_STANDARD` (no certification claim).

## Verified 2026 threat taxonomies (SWARM-E)
- **OWASP Top 10 for Agentic Applications 2026** — ASI01 Goal Hijack, ASI02 Tool
  Misuse, ASI03 Identity/Privilege Abuse, ASI04 Supply-Chain, ASI05 Unexpected
  Code Exec, ASI06 Memory/Context Poisoning, ASI07 Insecure Inter-Agent Comms,
  ASI08 Cascading Failures, ASI09 Human-Agent Trust Exploitation, ASI10 Rogue
  Agents.
- **MITRE ATLAS** — reconnaissance … ML Model Access … execution … exfiltration …
  impact (AI-specific: ML Model Access, ML Attack Staging).
- **STPA** — 4 UCA categories confirmed: not-provided, provided-when-unsafe,
  wrong-timing/order, stopped-too-soon/applied-too-long.
- **NIST AI RMF** — GOVERN / MAP / MEASURE / MANAGE; 600-1 twelve GenAI risk
  categories; measurement probes emphasize observable boundary evidence over
  private chain-of-thought; AI 800-4 post-deployment monitoring.

## Source URLs (mandatory corpus)

### EU AI Act
- https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng
- https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai
- https://digital-strategy.ec.europa.eu/en/policies/guidelines-ai-high-risk-systems
- https://digital-strategy.ec.europa.eu/en/library/draft-commission-guidelines-classification-high-risk-ai-systems
- https://digital-strategy.ec.europa.eu/en/consultations/targeted-consultation-draft-guidelines-classification-high-risk-artificial-intelligence-systems
- https://digital-strategy.ec.europa.eu/en/library/commission-publishes-guidelines-prohibited-artificial-intelligence-ai-practices-defined-ai-act
- https://digital-strategy.ec.europa.eu/en/library/commission-publishes-guidelines-ai-system-definition-facilitate-first-ai-acts-rules-application
- https://digital-strategy.ec.europa.eu/en/faqs/ai-literacy-questions-answers

### NIST
- https://www.nist.gov/itl/ai-risk-management-framework
- https://airc.nist.gov/
- https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf
- https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative
- https://www.nist.gov/news-events/news/2026/02/announcing-ai-agent-standards-initiative-interoperable-and-secure
- https://www.nist.gov/programs-projects/building-evaluation-probes-agentic-ai
- https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.800-4.pdf
- https://www.nist.gov/blogs/caisi-research-blog/insights-ai-agent-security-large-scale-red-teaming-competition
- https://www.nist.gov/caisi

### OWASP / MITRE
- https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- https://genai.owasp.org/initiatives/agentic-security-initiative/
- https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/
- https://genai.owasp.org/resources/
- https://atlas.mitre.org/

### ISO
- https://www.iso.org/standard/42001
- https://www.iso.org/standard/77304.html
- https://www.iso.org/standard/42005
- https://www.iso.org/standard/42006

### STPA / STPA-Sec
- https://psas.scripts.mit.edu/home/publications/
- https://psas.scripts.mit.edu/home/wp-content/uploads/2016/01/Systems-Theoretic-Process-Analysis-STPA-John-Thomas.pdf
- https://psas.scripts.mit.edu/home/wp-content/uploads/2020/07/STPA-Sec-Tutorial.pdf

### Research (treated as research, not standards)
- https://arxiv.org/abs/2605.09045  (containment independent of alignment)
- https://arxiv.org/html/2605.09045v2
- https://arxiv.org/abs/2607.01793  (evidence-grounded safety testing)
- https://arxiv.org/html/2607.01793v1
- https://arxiv.org/abs/2602.22302  (agent behavioral contracts)
- https://arxiv.org/abs/2604.17562  · https://arxiv.org/abs/2605.04785  · https://arxiv.org/html/2508.00500v3  (runtime / trajectory-aware safety)
- https://arxiv.org/html/2510.14133v2  (formal agent-system safety properties)
- https://arxiv.org/html/2605.18672v1  (multi-layer assume–guarantee)
- https://arxiv.org/abs/2601.22773  · https://arxiv.org/html/2601.22773v3  · https://arxiv.org/abs/2602.03550  (safety cases)
- https://arxiv.org/abs/2606.13621  · https://arxiv.org/html/2606.13621v1  (shield / defensibility)

### Viktor (vendor product guidance)
- https://viktor.com/blog/how-to-control-what-your-ai-employee-can-access
- https://viktor.com/blog/how-to-keep-a-human-in-the-loop-with-your-ai-employee
- https://viktor.com/security
- https://viktor.com/blog/how-to-roll-out-an-ai-employee-to-your-whole-team
- https://viktor.com/

Viktor public patterns (read/write separation, read-only-first, narrow scope,
revocation, review checkpoints, blast-radius thinking) are treated as vendor
product guidance; Finalis extends them with proof-carrying authority, context-bound
admission leases, TOCTOU revalidation, evidence-grounded verification and
independent containment. No undocumented internal architecture is inferred.
