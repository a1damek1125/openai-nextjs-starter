"""Understanding Extractor — rule-based MVP (production: local LLM behind the
same interface, e.g. Qwen via vLLM).

Design rules enforced here and tested:
- never invent a value: unknown stays {value: None, status: "unknown"};
- an ASR-uncertain term can NEVER become a certain fact (status: "uncertain");
- a later correction overwrites an earlier value (last confirmed wins);
- promises/objections/handoff triggers are detected with confidence scores.

Patterns cover English + Polish (MVP languages); the pattern tables are
playbook data, not code, in production.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .models import Utterance, VoiceExtraction

REQUIRED_FIELDS_HVAC = {
    "address": {"severity": "high", "blocks": "quote_preparation"},
    "installation_photo": {"severity": "high", "blocks": "quote_preparation"},
    "preferred_date": {"severity": "medium", "blocks": None},
    "device_brand": {"severity": "medium", "blocks": None},
}

INTENT_PATTERNS = {
    "request_quote": [
        r"\bquote\b", r"\bwycen", r"\boffer\b", r"\bofert",
        r"how much .*cost", r"\bile .*koszt",
    ],
    "reschedule": [r"\breschedul", r"przełoż", r"zmien.* termin"],
    "complaint": [r"\bcomplain", r"\breklamacj"],
    "status_inquiry": [r"\bstatus\b", r"what.*happening with", r"co z moj"],
}

SERVICE_PATTERNS = {
    "heat_pump_quote": [r"heat pump", r"pomp[aęy] ciepła"],
    "ac_install": [r"\bair.?condition", r"\bklimatyzacj", r"\bAC\b"],
    "boiler_service": [r"\bboiler", r"\bpiec\b", r"\bkocioł"],
}

PROMISE_PATTERNS = [
    # (who, regex, what)
    ("client", r"(i'?ll|i will|going to) send (you )?(the )?photos?", "send photos"),
    ("client", r"wyślę .*(zdjęci|foto)", "send photos"),
    ("client", r"(i'?ll|i will) (call|get) back", "call back"),
    ("client", r"odezwę się", "call back"),
    ("client", r"(i'?ll|i will) (check|confirm|ask)", "confirm details"),
]

DUE_PATTERNS = {
    "tomorrow": [r"\btomorrow\b", r"\bjutro\b"],
    "today": [r"\btoday\b", r"\bdzisiaj\b", r"\bdziś\b"],
    "this_week": [r"this week", r"w tym tygodniu"],
}

OBJECTION_PATTERNS = {
    "price_too_high": [r"too expensive", r"za drog"],
    "needs_time": [r"need (some )?time to think", r"muszę się zastanowić"],
    "has_competitor_offer": [r"(another|other|competitor) (quote|offer)",
                             r"inn[aą] ofert"],
}

HANDOFF_PATTERNS = {
    "human_requested": [r"(talk|speak) (to|with) (a )?(human|person|someone real)",
                        r"z człowiekiem", r"prawdziwym człowiekiem",
                        r"(a |the )?manager\b", r"kierownik"],
    "anger": [r"\bunacceptable\b", r"\boutrageous\b", r"\bfurious\b",
              r"skandal", r"oburzające", r"this is ridiculous",
              r"żenad", r"\bangry\b"],
    "legal_advice": [r"\b(sue|lawsuit|lawyer|legal advice)\b",
                     r"\bpozew\b", r"\bprawnik", r"porad[ay] prawn"],
    "medical_advice": [r"medical advice", r"porad[ay] medyczn"],
}

OUT_OF_SCOPE_PATTERNS = [
    r"\b(car|auto) (repair|engine)\b", r"napraw.* samoch",
    r"\broof(ing)?\b", r"\bdach\b", r"\bplumb", r"immigration",
]

# Two forms: "(at) ul./ulica/street NAME [NUMBER]" or "at NAME NUMBER".
# Street name needs >=3 chars so the "ul." token itself can never be captured.
ADDRESS_PATTERN = re.compile(
    r"\b(?:at\s+)?(?:ul\.|ulica|street|st\.)\s+"
    r"([A-ZŻŹĆĄŚĘŁÓŃ][\wĀ-ſ]{2,}(?:\s+\d+[a-z]?(?:/\d+)?)?)"
    r"|\bat\s+([A-ZŻŹĆĄŚĘŁÓŃ][\wĀ-ſ]{2,}\s+\d+[a-z]?(?:/\d+)?)",
    re.IGNORECASE | re.UNICODE)
REFUSE_ADDRESS = [r"(won'?t|not going to|don'?t want to) (give|share).*(address)",
                  r"nie podam .*adres", r"bez adresu"]
# Lead-in is case-insensitive via alternation, but the captured NAME stays
# case-sensitive (must start uppercase) so "I'm calling..." never yields a name.
NAME_PATTERN = re.compile(
    r"(?:[Mm]y name is|[Ii]'?m|[Nn]azywam się|[Zz] tej strony)\s+"
    r"([A-ZŻŹĆĄŚĘŁÓŃ][\wĀ-ſ]+(?:\s+[A-ZŻŹĆĄŚĘŁÓŃ][\wĀ-ſ]+)?)",
    re.UNICODE)
CORRECTION_PATTERNS = [r"\b(no,? (wait|sorry|actually))\b", r"\bi meant\b",
                       r"przepraszam,? (nie|pomyliłem)", r"znaczy się",
                       r"\bactually\b", r"\bcorrection\b"]
URGENCY_PATTERNS = {
    "emergency": [r"\bemergency\b", r"\bawaria\b", r"no heating", r"nie ma ogrzewania",
                  r"\bleak(ing)?\b", r"\bwyciek"],
    "urgent": [r"as soon as possible", r"\basap\b", r"jak najszybciej",
               r"this week", r"w tym tygodniu"],
}
PRICE_ASK = [r"how much (will|would|does|is)", r"what('?s| is) the price",
             r"ile (to )?(będzie )?koszt", r"jaka (jest )?cena"]


def _match_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


@dataclass
class FieldValue:
    value: Optional[Any] = None
    confidence: float = 0.0
    status: str = "unknown"       # unknown | uncertain | confirmed
    source_utterance_id: Optional[str] = None

    def as_dict(self) -> dict:
        return {"value": self.value, "confidence": round(self.confidence, 2),
                "status": self.status}


@dataclass
class Understanding:
    intent: Optional[str] = None
    intent_confidence: float = 0.0
    case_type: Optional[str] = None
    service_type: Optional[str] = None
    language: str = "en"
    languages_detected: set = field(default_factory=set)
    client_name: FieldValue = field(default_factory=FieldValue)
    address: FieldValue = field(default_factory=FieldValue)
    preferred_date: FieldValue = field(default_factory=FieldValue)
    device_brand: FieldValue = field(default_factory=FieldValue)
    urgency: str = "normal"
    address_refused: bool = False
    price_asked_without_data: bool = False
    corrections: int = 0
    promises: list[dict] = field(default_factory=list)
    objections: list[dict] = field(default_factory=list)
    handoff_triggers: list[str] = field(default_factory=list)
    out_of_scope: bool = False
    returning_client_reference: bool = False
    extractions: list[VoiceExtraction] = field(default_factory=list)


class UnderstandingExtractor:
    """Processes client utterances incrementally; never invents values."""

    UNCERTAIN_CONFIDENCE_CEILING = 0.5   # ASR-flagged terms cap out here

    def __init__(self, session_id: str,
                 case_id: Optional[str] = None) -> None:
        self.session_id = session_id
        self.case_id = case_id
        self.u = Understanding()

    # -- per-utterance processing ---------------------------------------------
    def process(self, utt: Utterance) -> None:
        if utt.speaker != "client":
            return
        text = utt.text
        self.u.languages_detected.add(utt.language)
        if len(self.u.languages_detected) == 1:
            self.u.language = utt.language

        self._detect_intent(text, utt)
        self._detect_service(text)
        self._detect_urgency(text)
        self._extract_name(text, utt)
        self._extract_address(text, utt)
        self._extract_date(text, utt)
        self._extract_brand(text, utt)
        self._detect_promises(text, utt)
        self._detect_objections(text, utt)
        self._detect_handoff(text, utt)
        self._detect_scope(text)
        if _match_any(text, [r"last (time|year|month)", r"previous (case|order|visit)",
                             r"poprzedni", r"ostatnim razem", r"again\b"]):
            self.u.returning_client_reference = True
        if _match_any(text, PRICE_ASK):
            self.u.price_asked_without_data = True

    # -- detectors -------------------------------------------------------------
    def _detect_intent(self, text: str, utt: Utterance) -> None:
        for intent, pats in INTENT_PATTERNS.items():
            if _match_any(text, pats):
                conf = min(0.95, 0.6 + 0.35 * utt.confidence)
                if conf > self.u.intent_confidence:
                    self.u.intent = intent
                    self.u.intent_confidence = conf
                    self._record("intent", {"intent": intent}, conf, utt)
                return

    def _detect_service(self, text: str) -> None:
        for service, pats in SERVICE_PATTERNS.items():
            if _match_any(text, pats):
                self.u.service_type = service
                self.u.case_type = {"heat_pump_quote": "hvac_installation",
                                    "ac_install": "hvac_installation",
                                    "boiler_service": "hvac_service"}[service]
                return

    def _detect_urgency(self, text: str) -> None:
        for level, pats in URGENCY_PATTERNS.items():
            if _match_any(text, pats):
                self.u.urgency = level
                return

    def _set_field(self, f: FieldValue, value: Any, utt: Utterance,
                   base_conf: float) -> None:
        is_correction = _match_any(utt.text, CORRECTION_PATTERNS)
        if is_correction:
            self.u.corrections += 1
        # Last confirmed value wins; corrections always overwrite.
        value_uncertain = any(term.lower() in str(value).lower()
                              for term in utt.uncertain_terms)
        conf = min(base_conf, utt.confidence)
        if value_uncertain:
            conf = min(conf, self.UNCERTAIN_CONFIDENCE_CEILING)
        if f.status != "confirmed" or is_correction or conf >= f.confidence:
            f.value = value
            f.confidence = conf
            f.status = "uncertain" if conf < 0.6 else "confirmed"
            f.source_utterance_id = utt.id

    def _extract_name(self, text: str, utt: Utterance) -> None:
        m = NAME_PATTERN.search(text)
        if m:
            self._set_field(self.u.client_name, m.group(1).strip(), utt, 0.9)

    def _extract_address(self, text: str, utt: Utterance) -> None:
        if _match_any(text, REFUSE_ADDRESS):
            self.u.address_refused = True
            return
        m = ADDRESS_PATTERN.search(text)
        if m:
            self._set_field(self.u.address, m.group(1).strip(), utt, 0.85)

    def _extract_date(self, text: str, utt: Utterance) -> None:
        for due, pats in DUE_PATTERNS.items():
            if _match_any(text, pats) and not self._looks_like_promise(text):
                self._set_field(self.u.preferred_date, due, utt, 0.7)
                return
        m = re.search(r"\b(on |w )?(monday|tuesday|wednesday|thursday|friday|"
                      r"poniedziałek|wtorek|środ[aę]|czwartek|piątek)\b",
                      text, re.IGNORECASE)
        if m:
            self._set_field(self.u.preferred_date, m.group(2).lower(), utt, 0.8)

    def _extract_brand(self, text: str, utt: Utterance) -> None:
        m = re.search(r"\b(it'?s a|mam|i have a|brand is|marki)\s+"
                      r"([A-Z][A-Za-z]{2,})", text)
        if m:
            self._set_field(self.u.device_brand, m.group(2), utt, 0.8)

    @staticmethod
    def _looks_like_promise(text: str) -> bool:
        return _match_any(text, [p for _, p, _ in PROMISE_PATTERNS])

    def _detect_promises(self, text: str, utt: Utterance) -> None:
        for who, pat, what in PROMISE_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                due = "unspecified"
                for d, pats in DUE_PATTERNS.items():
                    if _match_any(text, pats):
                        due = d
                        break
                conf = round(min(0.95, 0.55 + 0.35 * utt.confidence), 2)
                promise = {"who": who, "what": what, "due": due,
                           "confidence": conf}
                if promise not in self.u.promises:
                    self.u.promises.append(promise)
                    self._record("promise", promise, conf, utt)
                return

    def _detect_objections(self, text: str, utt: Utterance) -> None:
        for obj, pats in OBJECTION_PATTERNS.items():
            if _match_any(text, pats):
                entry = {"type": obj}
                if entry not in self.u.objections:
                    self.u.objections.append(entry)
                    self._record("objection", entry, 0.8, utt)

    def _detect_handoff(self, text: str, utt: Utterance) -> None:
        for trigger, pats in HANDOFF_PATTERNS.items():
            if _match_any(text, pats) and trigger not in self.u.handoff_triggers:
                self.u.handoff_triggers.append(trigger)
                self._record("handoff_trigger", {"trigger": trigger}, 0.9, utt)

    def _detect_scope(self, text: str) -> None:
        if _match_any(text, OUT_OF_SCOPE_PATTERNS):
            self.u.out_of_scope = True

    def _record(self, etype: str, payload: dict, conf: float,
                utt: Utterance) -> None:
        self.u.extractions.append(VoiceExtraction(
            voice_session_id=self.session_id, case_id=self.case_id,
            extraction_type=etype, payload=payload, confidence=conf,
            source_utterance_ids=[utt.id]))

    # -- missing-info derivation -----------------------------------------------
    def missing_items(self) -> list[dict]:
        out = []
        field_map = {"address": self.u.address,
                     "preferred_date": self.u.preferred_date,
                     "device_brand": self.u.device_brand}
        for key, spec in REQUIRED_FIELDS_HVAC.items():
            if key == "installation_photo":
                # Photos can't arrive during a call; a photo-send promise
                # covers the request path but the item stays missing.
                out.append({"type": key, **spec})
                continue
            fv = field_map.get(key)
            if fv is None or fv.status in ("unknown", "uncertain"):
                item = {"type": key, **spec}
                if fv is not None and fv.status == "uncertain":
                    item["note"] = "value_present_but_uncertain"
                out.append(item)
        return [{"type": i["type"], "severity": i["severity"],
                 "blocks": i["blocks"], **({"note": i["note"]} if "note" in i
                                           else {})} for i in out]
