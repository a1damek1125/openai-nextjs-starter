# Finalis AI — WebScout Worker (Ethical Web Research)

> WebScout does *legal, source-recorded* public web research — checking manufacturer specs,
> public price ranges, catalogues, public registries, and public company data to support a
> case. It is explicitly **not** a "dark scraper": it never bypasses paywalls, CAPTCHAs,
> authentication, or terms, and it records a source + trust score for every fact.

## 1. Capabilities

- Search the public web; open and read public pages; extract text; download and read **public**
  PDFs.
- Compare market/price data; check manufacturer specs and warranty terms; check public
  registries and public company data; find alternatives.
- Produce **source-backed research notes** that feed the Offer Comparator and Decision Worker.

Every WebScout fact is stored (schema in `04`, `EvidenceReference` + a `Source` record) with:
**source URL · source type · date checked · trust score · extracted snippet · relevance ·
confidence.**

## 2. Hard restrictions (enforced, not advisory)

- **No bypassing** paywalls, CAPTCHAs, login/authentication, or access barriers.
- **Respect robots.txt and site terms** where applicable.
- **No unauthorized login**; no acting on a user's behalf on gated sites without explicit,
  scoped consent.
- **No hidden/mass scraping** of protected data; no impersonating a human to gain prohibited
  access.
- **Record every source.** No un-cited facts enter a case.

### Legal grounding (why "public only")
- **hiQ v. LinkedIn (9th Cir.)**: scraping **publicly available** data likely isn't access
  "without authorization" under the CFAA (applying the *Van Buren* "gates-up-or-down" test) —
  public pages have no gate to lift. https://en.wikipedia.org/wiki/HiQ_Labs_v._LinkedIn
- **But that's CFAA only.** The same cases make clear scraping can still breach **contract
  (ToS)**, copyright, trespass to chattels, or privacy law — hiQ ultimately settled and
  accepted an injunction for violating LinkedIn's user agreement. So: public-data reading is
  defensible; **bypassing a gate (auth/paywall/CAPTCHA) is on the wrong side of the line** and
  is prohibited by policy. *(This is legal-analysis synthesis, not per-jurisdiction advice;
  tenants operate under their own counsel. CAPTCHA-circumvention case law: UNVERIFIED — treat
  as prohibited regardless.)*

## 3. Tooling (structured browser control, sandboxed)

Prefer **structured, accessibility-tree** control over pixel/GUI autonomy (OSWorld shows GUI
autonomy is unreliable — see `02`).

| Tool | Role | License | Source |
|---|---|---|---|
| **Playwright MCP** (Microsoft) | Primary browser control via **accessibility tree, not screenshots**; deterministic, element-`ref` tool calls; "no vision models needed" | Apache-2.0 | https://github.com/microsoft/playwright-mcp |
| **Firecrawl** | Scrape/crawl/map/search/extract → **LLM-ready markdown/JSON**; **respects robots.txt by default** | AGPL-3.0 (SDKs MIT) | https://github.com/firecrawl/firecrawl |
| **browser-use** | Make sites accessible to agents; provider-agnostic | MIT | https://github.com/browser-use/browser-use |
| **Skyvern** | Heavier multi-step browser workflows (LLM + computer vision, built on Playwright) — used sparingly, only for public multi-step lookups | AGPL-3.0 | https://github.com/Skyvern-AI/skyvern |

**Default**: Firecrawl for read/extract at scale (robots-respecting, markdown output);
Playwright MCP for deterministic navigation of specific public pages. browser-use/Skyvern only
when a task genuinely needs multi-step interaction on public sites. **Note AGPL** licensing on
Firecrawl/Skyvern for the deployment model (self-host vs. hosted API) — resolve in `18`.

### Sandboxing & injection defense (required)
Agentic browsers introduce real security risks. WebScout runs in an **isolated, least-
privilege sandbox** with these controls:
- **Treat all web content as untrusted input.** Web pages can carry **indirect prompt
  injection** (OWASP LLM Top-10 **LLM01**), and over-permissioned agents enable **Excessive
  Agency** (**LLM06**). https://owasp.org/www-project-top-10-for-large-language-model-applications/
- Research basis: agentic browsers replace the human as "final arbiter of intent" with a
  manipulable model, changing the web threat model (BrowseSafe arXiv:2511.20597; ceLLMate
  sandboxing arXiv:2512.12594; WAAA! — *arXiv abstracts search-surfaced, verify before
  quoting*). Industry review documents zero-interaction exfiltration via hidden page
  instructions (Wiz 2025 year-end review — vendor commentary).
- **Controls**: no credentials in the browser sandbox; content is stripped/normalized before
  entering an LLM prompt; a **secondary "critic" pass** validates that extracted facts match
  the cited snippet (catches injected/hallucinated content); WebScout has **no write actions**
  (read-only) and cannot trigger case-state changes directly — it only returns proposed facts
  to the Orchestrator. Align with **OWASP Top-10 for Agentic Applications** (published Dec 9
  2025; ASI01–ASI10 covering goal hijacking, tool misuse, etc. — *ASI ordering SEMI-VERIFIED,
  confirm against final PDF*). https://genai.owasp.org/

## 4. Source trust scoring

`SourceTrust` (0–100), computed as in `05` §11:
`0.35·Authority + 0.25·Recency + 0.20·Corroboration + 0.15·Directness + 0.05·Transparency`.

Backed by established source-evaluation frameworks adapted to automation:
- **CRAAP** (Currency, Relevance, Authority, Accuracy, Purpose) — https://www.scribbr.com/working-with-sources/craap-test/
- **SIFT** (Stop, Investigate source, Find better coverage, **Trace claims to original**) — the
  "trace to original" step maps directly to preferring primary sources and verifying citations.
- Research motivation: search-augmented LLMs exhibit **structural citation failures**, so a
  research agent must *score and verify* sources, not trust retrieved citations ("Verified
  Misguidance" — *search-surfaced, verify*).

Trust bands: **Official/primary** (manufacturer, registry, gov) = high; **retailer/marketplace**
= medium; **forum/blog/unknown** = low. Low-trust facts require corroboration before they can
raise `Confidence` above `θ_conf`.

## 5. Output contract (research note)

```json
{
  "query": "market price range: 12kW air-source heat pump, PL, 2026",
  "facts": [
    {
      "claim": "Typical installed price €9,000–€13,000",
      "source_url": "https://manufacturer.example/pricing.pdf",
      "source_type": "manufacturer_pdf",
      "date_checked": "2026-07-07",
      "snippet": "MSRP for the 12kW unit ... installation not included ...",
      "trust_score": 84,
      "relevance": 0.9,
      "confidence": 0.8
    }
  ],
  "corroboration": "2 independent sources agree within 8%",
  "uncertainty_notes": "Retailer listings vary by region; excludes subsidies."
}
```

The Decision Worker and Offer Comparator consume these notes; the Command Center shows the
sources so the owner can click through. If WebScout cannot find a trustworthy source, it says
so — it never fabricates a range.

## 6. Example end-to-end

1. Task: "Is this heat-pump offer market-reasonable?"
2. WebScout finds manufacturer spec + public price ranges + warranty terms (records sources +
   trust).
3. Document Worker reads the client's offer (`07`).
4. Offer Comparator scores our offer vs. market (`10`).
5. Decision Worker: "Offer is ~9% above typical installed price but includes 5-yr warranty +
   service the market listings exclude; recommend emphasizing warranty. Sources: [3 links]."

Every step is evidence-linked and auditable.
