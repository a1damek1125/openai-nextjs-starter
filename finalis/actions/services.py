"""Channel router, message composer, consent gate, rate limiter, upload links."""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .models import (ChannelPreference, ConsentPreference, MessageDraft,
                     RateLimitRule, UploadLink)

# --- Channel Router -----------------------------------------------------------
CHANNEL_PRIORITY = {
    # message type -> ordered channel preference (spec §ChannelRouter)
    "send_photo_request": ["whatsapp", "sms", "email", "phone_callback"],
    "send_document_request": ["whatsapp", "email", "sms", "phone_callback"],
    "ask_for_missing_info": ["whatsapp", "sms", "email"],
    "send_address_request": ["whatsapp", "sms", "email"],
    "send_follow_up_after_offer": ["whatsapp", "email", "sms"],
    "send_upload_link": ["whatsapp", "sms", "email"],
    "confirm_document_received": ["whatsapp", "sms", "email"],
    "notify_owner": ["inbox", "email", "slack"],
    "handoff_to_human": ["chatwoot", "internal_task", "phone_callback"],
    "schedule_callback": ["internal_task"],
}


@dataclass
class RouteDecision:
    channel: Optional[str]
    fallback: Optional[str]
    reason: str
    provider: str = "mock"


class ChannelRouter:
    def route(self, action_type: str, prefs: ChannelPreference,
              consents: list[ConsentPreference]) -> RouteDecision:
        order = CHANNEL_PRIORITY.get(action_type,
                                     ["whatsapp", "sms", "email"])
        opted_out = {c.channel for c in consents if c.status == "opted_out"}
        # Client preference first if it's in the allowed order.
        if prefs.preferred_channel in order:
            order = [prefs.preferred_channel] + [
                c for c in order if c != prefs.preferred_channel]
        candidates = [c for c in order
                      if c in prefs.available_channels
                      or c in ("inbox", "chatwoot", "internal_task",
                               "phone_callback", "slack", "email")]
        candidates = [c for c in candidates
                      if c not in opted_out and "any" not in opted_out]
        if not candidates:
            return RouteDecision(None, None, "no_permitted_channel")
        fallback = candidates[1] if len(candidates) > 1 else None
        return RouteDecision(candidates[0], fallback,
                             f"priority_order_for_{action_type}")


# --- Message Composer ----------------------------------------------------------
TEMPLATES: dict[tuple[str, str], str] = {
    ("send_photo_request", "pl"): (
        "Dzień dobry, zgodnie z rozmową proszę o przesłanie zdjęcia obecnej "
        "instalacji oraz tabliczki znamionowej urządzenia. To pozwoli "
        "przygotować dokładniejszą wycenę.{upload_suffix}"),
    ("send_photo_request", "en"): (
        "Hello, as discussed, please send a photo of the current installation "
        "and the device nameplate so we can prepare an accurate quote."
        "{upload_suffix}"),
    ("send_address_request", "pl"): (
        "Dzień dobry, do przygotowania wyceny potrzebujemy jeszcze adresu "
        "inwestycji. Proszę o wiadomość zwrotną."),
    ("ask_for_missing_info", "pl"): (
        "Dzień dobry, do przygotowania wyceny brakuje nam jeszcze: {items}. "
        "Proszę o wiadomość zwrotną."),
    ("send_follow_up_after_offer", "pl"): (
        "Dzień dobry, chciałem zapytać, czy miał Pan chwilę spojrzeć na "
        "ofertę. Jeżeli są pytania albo chce Pan porównać zakres prac, "
        "chętnie pomożemy."),
    ("send_follow_up_after_offer", "en"): (
        "Hello, I wanted to check whether you had a moment to look at our "
        "offer. Happy to answer any questions or compare the scope of work."),
    ("confirm_document_received", "pl"): (
        "Dziękujemy, otrzymaliśmy przesłane materiały. Wracamy z wyceną "
        "najszybciej jak to możliwe."),
    ("handoff_to_human", "pl"): (
        "Dziękuję za zgłoszenie. Przekazuję sprawę koledze/koleżance z "
        "zespołu — skontaktujemy się najszybciej jak to możliwe."),
    ("mark_recovery_later", "pl"): (
        "Rozumiem, wrócimy do tematu w dogodniejszym terminie. Odezwiemy się "
        "zgodnie z ustaleniem."),
    # High-risk drafts are skeletons the HUMAN must edit before approval —
    # the composer never writes prices, discounts, or contract language.
    ("send_price_negotiation", "pl"): (
        "[SZKIC DO EDYCJI PRZEZ CZŁOWIEKA] Dzień dobry, wracam do tematu "
        "naszej oferty. {human_must_complete}"),
    ("send_contract_response", "pl"): (
        "[SZKIC DO EDYCJI PRZEZ CZŁOWIEKA] Dzień dobry, w sprawie umowy: "
        "{human_must_complete}"),
    ("send_quote_status_update", "pl"): (
        "Dzień dobry, pracujemy nad Pana wyceną i wrócimy z nią zgodnie z "
        "ustaleniem."),
}

FORBIDDEN_PATTERNS = ["zł", "PLN", "EUR", "€", "$",       # no invented prices
                      "guarantee you", "gwarantuję, że",   # no overpromising
                      "legal advice", "porada prawna"]


class MessageComposeError(Exception):
    pass


class MessageComposer:
    def compose(self, action_type: str, *, language: str, channel: str,
                tenant_id: str, case_id: str, action_request_id: str,
                variables: dict | None = None,
                risk_level: str = "low") -> MessageDraft:
        variables = variables or {}
        template = TEMPLATES.get((action_type, language)) \
            or TEMPLATES.get((action_type, "pl"))
        if template is None:
            raise MessageComposeError(f"no template for {action_type}")
        upload = variables.get("upload_link")
        text = template.format(
            upload_suffix=(f" Link do dodania zdjęć: {upload}" if upload
                           else ""),
            items=", ".join(variables.get("items", [])) or "informacji",
            upload_link=upload or "",
            human_must_complete=variables.get(
                "human_must_complete",
                "(treść do uzupełnienia przez człowieka przed wysyłką)"))
        # Safety: templates must never smuggle prices/advice; variables could.
        lowered = text.lower()
        for pat in FORBIDDEN_PATTERNS:
            if pat.lower() in lowered and pat.lower() not in (
                    template.lower()):
                raise MessageComposeError(f"forbidden content: {pat}")
        return MessageDraft(tenant_id=tenant_id, case_id=case_id,
                            action_request_id=action_request_id,
                            language=language, channel=channel, text=text,
                            variables=variables, risk_level=risk_level)


# --- Consent & Permission Gate --------------------------------------------------
@dataclass
class ConsentDecision:
    allowed: bool
    reason: str
    defer_until: Optional[datetime] = None


class ConsentPermissionService:
    def check(self, *, prefs: ChannelPreference,
              consents: list[ConsentPreference], channel: str,
              now: datetime, urgent: bool = False) -> ConsentDecision:
        if prefs.do_not_contact:
            return ConsentDecision(False, "do_not_contact")
        for c in consents:
            if c.status == "opted_out" and c.channel in (channel, "any"):
                return ConsentDecision(False, f"opted_out:{c.channel}")
        start, end = prefs.preferred_time_window
        in_window = start <= now.hour < end
        if not in_window and not urgent:
            defer = now.replace(hour=start, minute=0, second=0)
            if now.hour >= end:
                defer += timedelta(days=1)
            return ConsentDecision(False, "outside_business_hours",
                                   defer_until=defer)
        return ConsentDecision(True, "consent_ok")


# --- Rate Limit / Spam Guard -----------------------------------------------------
@dataclass
class RateDecision:
    allowed: bool
    reason: str


class RateLimitSpamGuard:
    def __init__(self, rule: RateLimitRule | None = None) -> None:
        self.rule = rule or RateLimitRule(tenant_id="default")
        self._history: dict[tuple, list[datetime]] = {}
        self._paused_cases: set[str] = set()

    def client_replied(self, case_id: str) -> None:
        """Client engagement pauses automated follow-up."""
        self._paused_cases.add(case_id)

    def resume(self, case_id: str) -> None:
        self._paused_cases.discard(case_id)

    def check(self, *, case_id: str, action_type: str,
              now: datetime) -> RateDecision:
        if case_id in self._paused_cases:
            return RateDecision(False, "paused_client_replied")
        key = (case_id, action_type)
        history = self._history.get(key, [])
        if len(history) >= self.rule.max_attempts:
            return RateDecision(False, "max_attempts")
        if history and (now - history[-1]) < timedelta(
                minutes=self.rule.cooldown_minutes):
            return RateDecision(False, "cooldown")
        day_count = sum(1 for hs in self._history.values() for t in hs
                        if t.date() == now.date()
                        and hs is not history or True
                        for _ in [0]) if False else sum(
            1 for (cid, _a), hs in self._history.items() if cid == case_id
            for t in hs if t.date() == now.date())
        if day_count >= self.rule.max_per_day:
            return RateDecision(False, "daily_limit")
        return RateDecision(True, "ok")

    def record(self, *, case_id: str, action_type: str,
               now: datetime) -> None:
        self._history.setdefault((case_id, action_type), []).append(now)


# --- Upload Link Generator --------------------------------------------------------
class UploadLinkGenerator:
    BASE_URL = "https://upload.finalis.example/u/"

    def __init__(self, audit) -> None:
        self.audit = audit
        self.links: dict[str, UploadLink] = {}     # token_hash -> link
        self._urls: dict[str, str] = {}            # link.id -> full url

    def create(self, *, tenant_id: str, case_id: str, purpose: str,
               now: datetime, ttl_hours: int = 72) -> tuple[UploadLink, str]:
        token = secrets.token_urlsafe(24)
        link = UploadLink(tenant_id=tenant_id, case_id=case_id,
                          purpose=purpose,
                          token_hash=UploadLink.hash_token(token),
                          expires_at=now + timedelta(hours=ttl_hours))
        self.links[link.token_hash] = link
        url = f"{self.BASE_URL}{token}"
        self._urls[link.id] = url
        self.audit.append(event_type="UPLOAD_LINK_CREATED", actor="system",
                          case_id=case_id,
                          payload={"link_id": link.id, "purpose": purpose,
                                   "expires_at": str(link.expires_at)})
        return link, url

    def open(self, token: str, now: datetime) -> Optional[UploadLink]:
        link = self.links.get(UploadLink.hash_token(token))
        if link is None:
            return None
        if now > link.expires_at or link.status in ("EXPIRED", "REVOKED"):
            link.status = "EXPIRED"
            return None
        if link.status in ("CREATED", "SENT"):
            link.status = "OPENED"
            self.audit.append(event_type="UPLOAD_LINK_OPENED", actor="client",
                              case_id=link.case_id,
                              payload={"link_id": link.id})
        return link

    def use(self, token: str, now: datetime, *, mime: str,
            size_mb: float) -> bool:
        link = self.open(token, now)
        if link is None:
            return False
        if mime not in link.allowed_types or size_mb > link.max_size_mb:
            return False
        link.status = "USED"
        link.used_at = now
        self.audit.append(event_type="UPLOAD_LINK_USED", actor="client",
                          case_id=link.case_id,
                          payload={"link_id": link.id, "mime": mime})
        return True

    def revoke(self, link_id: str) -> None:
        for link in self.links.values():
            if link.id == link_id:
                link.status = "REVOKED"
