"""WebScout worker (mock) — executable form of docs/finalis-ai/08 restrictions.

No real browsing here: the scaffold proves the POLICY layer — hard restriction
enforcement, mandatory source recording, and trust scoring — against fixture
pages. The real fetch layer (Firecrawl/Playwright MCP) plugs in behind
`FetcherProtocol` later.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from . import scoring
from .models import Source


class RestrictionViolation(Exception):
    pass


@dataclass
class FixturePage:
    url: str
    source_type: str
    content: str
    requires_login: bool = False
    paywalled: bool = False
    captcha: bool = False
    robots_disallowed: bool = False


class FetcherProtocol(Protocol):
    def fetch(self, url: str) -> FixturePage: ...


class WebScout:
    """Read-only, public-only, source-recorded research."""

    def __init__(self, fetcher: FetcherProtocol, audit) -> None:
        self.fetcher = fetcher
        self.audit = audit

    def research(self, url: str, *, date_checked: str,
                 trust_inputs: dict[str, float],
                 relevance: float) -> Source:
        page = self.fetcher.fetch(url)

        # Hard restrictions — never bypassed, always refused loudly (08 §2).
        for flag, label in ((page.requires_login, "auth_required"),
                            (page.paywalled, "paywall"),
                            (page.captcha, "captcha"),
                            (page.robots_disallowed, "robots_disallowed")):
            if flag:
                self.audit.append(event_type="webscout.blocked", actor="ai",
                                  payload={"url": url, "reason": label})
                raise RestrictionViolation(f"{label}: {url}")

        trust = scoring.source_trust(
            trust_inputs.get("authority", 0.0),
            trust_inputs.get("recency", 0.0),
            trust_inputs.get("corroboration", 0.0),
            trust_inputs.get("directness", 0.0),
            trust_inputs.get("transparency", 0.0),
        )
        source = Source(url=url, source_type=page.source_type,
                        date_checked=date_checked,
                        snippet=page.content[:280],
                        trust_score=trust, relevance=relevance,
                        confidence=min(1.0, trust / 100.0))
        # Mandatory source recording — a fact without a Source cannot exist.
        self.audit.append(event_type="webscout.research_completed", actor="ai",
                          payload={"url": url, "trust_score": trust,
                                   "source_id": source.id})
        return source
