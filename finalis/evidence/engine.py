"""EvidenceEngine — ingest, validation, quarantine, mock scan, review,
retention/legal hold, fact extraction (never commands), decision
contracts, and access logging. Deterministic and auditable throughout.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .gates import admissibility_gate, ai_file_access_gate
from .models import (ACTIVE_CONTENT_EXTENSIONS, ALLOWED_EXTENSIONS,
                     DANGEROUS_EXTENSIONS, MAX_SIZE_MB, EvidenceAccessEvent,
                     EvidenceDecisionContract, EvidenceDerivative,
                     EvidenceFileMetadata, EvidenceIntegrityRecord,
                     EvidenceObject, EvidenceSource, ExtractedFacts,
                     LegalHoldRecord, RetentionDecision, detect_mime,
                     evidence_transition)
from .requirements import check_requirements
from .scores import EvidenceThresholds, scan_for_injection
from .storage import EvidenceStorageProvider


class EvidenceValidationError(Exception):
    pass


# A deterministic malware marker for the MOCK scanner (EICAR-style):
# real ClamAV/CDR replaces this verdict behind the same provider shape.
MOCK_MALWARE_MARKER = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$"


@dataclass
class RetentionContext:
    legal_hold: bool = False
    retention_until: Optional[datetime] = None
    used_by_active_decision: bool = False
    actor_role: str = "operator"


class RetentionDecisionEngine:
    def decide(self, ev: EvidenceObject, *, hard_delete: bool,
               ctx: RetentionContext,
               now: Optional[datetime] = None) -> RetentionDecision:
        now = now or datetime.utcnow()
        if hard_delete:
            if ev.legal_hold or ctx.legal_hold:
                return RetentionDecision(
                    "DENY_LEGAL_HOLD",
                    ["evidence is under legal hold — hard delete blocked"])
            until = ev.retention_until or ctx.retention_until
            if until and now < until:
                return RetentionDecision(
                    "DENY_RETENTION_PERIOD",
                    [f"retention lock until {until:%Y-%m-%d} blocks "
                     "hard delete"])
            if ctx.used_by_active_decision:
                return RetentionDecision(
                    "REQUIRE_COMPLIANCE_REVIEW",
                    ["evidence supports an active decision — compliance "
                     "review before hard delete"])
            if ctx.actor_role != "owner":
                return RetentionDecision(
                    "REQUIRE_OWNER_APPROVAL",
                    ["hard delete requires the owner"])
            return RetentionDecision("ALLOW_HARD_DELETE",
                                     ["no hold, no retention, owner"])
        if ctx.used_by_active_decision:
            return RetentionDecision(
                "REQUIRE_COMPLIANCE_REVIEW",
                ["evidence supports an active decision — review before "
                 "soft delete"])
        return RetentionDecision("ALLOW_SOFT_DELETE",
                                 ["soft delete keeps bytes + audit"])


_AMOUNT = re.compile(r"\b\d[\d ,.]*\d\s?(?:zł|PLN|EUR|€|\$|USD)\b",
                     re.IGNORECASE)
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[./]\d{1,2}[./]\d{4}\b")
_NAME = re.compile(r"\b[A-ZŁŚŻŹĆ][a-ząęółśżźćń]+ [A-ZŁŚŻŹĆ]"
                   r"[a-ząęółśżźćń]+\b")


def extract_facts(text: str) -> ExtractedFacts:
    """Documents provide facts, never commands: instruction-like spans
    are suppressed and counted; the returned structure has no field that
    could carry an action."""
    risk, hits = scan_for_injection(text)
    cleaned = text or ""
    for h in hits:
        cleaned = cleaned.replace(h, " ")
    return ExtractedFacts(
        amounts=_AMOUNT.findall(cleaned),
        dates=_DATE.findall(cleaned),
        names=_NAME.findall(cleaned)[:10],
        mentions=[w for w in ("invoice", "payment", "installation",
                              "protocol", "warranty")
                  if w in cleaned.lower()],
        injection_risk=risk,
        suppressed_instruction_count=len(hits))


class EvidenceEngine:
    def __init__(self, storage: EvidenceStorageProvider, audit=None,
                 thresholds: Optional[EvidenceThresholds] = None) -> None:
        self.storage = storage
        self.audit = audit
        self.thresholds = thresholds or EvidenceThresholds()
        self.objects: dict[str, EvidenceObject] = {}
        self.access_events: list[EvidenceAccessEvent] = []
        self.legal_holds: list[LegalHoldRecord] = []
        self.contracts: list[EvidenceDecisionContract] = []
        self.retention = RetentionDecisionEngine()

    def _audit(self, event_type: str, ev: EvidenceObject,
               **payload) -> None:
        if self.audit is not None:
            self.audit.append(event_type=event_type, actor="evidence",
                              case_id=ev.case_id,
                              payload={"evidence_id": ev.id, **payload})

    # -- ingest -----------------------------------------------------------------
    def ingest(self, *, tenant_id: str, case_id: str, uploaded_by: str,
               filename: str, declared_mime: str, data: bytes,
               evidence_type: str = "document",
               source: Optional[EvidenceSource] = None,
               sensitivity: str = "normal",
               text_preview: str = "") -> EvidenceObject:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if not data:
            raise EvidenceValidationError("zero-byte file rejected")
        if len(data) > MAX_SIZE_MB * 1024 * 1024:
            raise EvidenceValidationError(
                f"file exceeds the {MAX_SIZE_MB} MB limit")
        if ext in DANGEROUS_EXTENSIONS:
            raise EvidenceValidationError(
                f"file type .{ext} is not allowed (dangerous)")
        if ext not in ALLOWED_EXTENSIONS:
            raise EvidenceValidationError(
                f"file type .{ext or '?'} is not on the allowlist")
        detected = detect_mime(data)
        meta = EvidenceFileMetadata(
            original_filename=filename,        # metadata only, never a path
            declared_mime=declared_mime, detected_mime=detected,
            extension=ext, size_bytes=len(data),
            mime_mismatch=bool(detected and declared_mime
                               and detected != declared_mime
                               and not (detected == "application/zip"
                                        and ext in ("docx", "xlsx"))),
            active_content=ext in ACTIVE_CONTENT_EXTENSIONS)
        pointer, sha256 = self.storage.put_bytes(tenant_id=tenant_id,
                                                 data=data)
        injection_risk, _ = scan_for_injection(text_preview)
        ev = EvidenceObject(
            tenant_id=tenant_id, case_id=case_id,
            evidence_type=evidence_type, meta=meta,
            source=source or EvidenceSource(), uploaded_by=uploaded_by,
            storage=pointer,
            integrity=EvidenceIntegrityRecord(
                algorithm="sha256", digest=sha256,
                verified_at=datetime.utcnow()),
            sensitivity=sensitivity, injection_risk=injection_risk)
        ev.chain.append_event(event_type="UPLOADED", actor=uploaded_by,
                              payload={"filename": filename,
                                       "sha256": sha256,
                                       "size": len(data)})
        evidence_transition(ev, "QUARANTINED", actor="system",
                            reason="all new evidence starts quarantined")
        self.objects[ev.id] = ev
        self._audit("EVIDENCE_INGESTED", ev, sha256=sha256,
                    evidence_type=evidence_type, quarantined=True)
        if text_preview:
            # Dual-view: the content gets an opaque UNTRUSTED symbol —
            # storage inside Finalis never launders external content.
            from .models import EvidenceSymbol, EvidenceUntrustedDataMarker
            ev.symbols.append(EvidenceSymbol(
                evidence_id=ev.id, kind="document_text", trusted=False,
                marker=EvidenceUntrustedDataMarker(
                    origin=ev.source.kind)))
            # A safe derivative carries FACTS extracted from content —
            # instruction-like spans are suppressed before storage.
            facts = extract_facts(text_preview)
            ev.derivatives.append(EvidenceDerivative(
                kind="safe_text",
                text=(f"amounts={facts.amounts} dates={facts.dates} "
                      f"names={facts.names} mentions={facts.mentions}")))
            ev.injection_risk = max(ev.injection_risk,
                                    facts.injection_risk)
        return ev

    # -- mock scan (SCAFFOLDED verdict behind the real provider shape) -----
    def run_scan(self, ev: EvidenceObject, data: bytes) -> None:
        evidence_transition(ev, "SCAN_PENDING", actor="scanner-mock")
        if MOCK_MALWARE_MARKER in data:
            ev.scan.status, ev.scan.detail = "SUSPICIOUS", "mock marker"
            evidence_transition(ev, "MALWARE_SUSPECTED",
                                actor="scanner-mock")
            self._audit("EVIDENCE_MALWARE_SUSPECTED", ev, is_mock=True)
            return
        ev.scan.status = "CLEAN"
        evidence_transition(ev, "SCANNED_CLEAN", actor="scanner-mock")
        self._audit("EVIDENCE_SCANNED", ev, verdict="CLEAN", is_mock=True)

    # -- integrity ---------------------------------------------------------------
    def verify_integrity(self, ev: EvidenceObject) -> bool:
        ok = ev.storage is not None and ev.integrity is not None and \
            self.storage.verify_integrity(ev.storage, ev.integrity.digest)
        if ev.integrity:
            ev.integrity.verified_at = datetime.utcnow()
            ev.integrity.valid = ok
        if not ok and ev.state != "INTEGRITY_FAILED":
            evidence_transition(ev, "INTEGRITY_FAILED", actor="system",
                                reason="checksum mismatch")
            self._audit("EVIDENCE_INTEGRITY_FAILED", ev)
        return ok

    # -- review ------------------------------------------------------------------
    def human_review(self, ev: EvidenceObject, *, reviewer: str,
                     verdict: str, note: str = "") -> None:
        if ev.state == "REJECTED":
            # Explicit re-review event is the only path out of REJECTED.
            evidence_transition(ev, "NEEDS_HUMAN_REVIEW", actor=reviewer,
                                reason="explicit re-review")
        if ev.state == "SCANNED_CLEAN":
            evidence_transition(ev, "NEEDS_HUMAN_REVIEW", actor=reviewer)
        evidence_transition(ev, verdict, actor=reviewer, reason=note)
        if verdict in ("ADMISSIBLE", "ADMISSIBLE_WITH_LIMITS"):
            ev.human_verified = True
        self._audit("EVIDENCE_REVIEWED", ev, verdict=verdict,
                    reviewer=reviewer)

    def auto_admit_clean(self, ev: EvidenceObject) -> None:
        """Low-risk clean evidence may be admitted automatically."""
        evidence_transition(ev, "ADMISSIBLE_WITH_LIMITS", actor="system",
                            reason="auto-admitted clean, limited")

    # -- AI access ---------------------------------------------------------------
    def ai_access(self, ev: EvidenceObject, *, tenant_id: str,
                  actor_id: str, purpose: str = "fact_extraction",
                  task_scoped_authorization: bool = False,
                  requested_raw: bool = False):
        decision = ai_file_access_gate(
            ev, tenant_id=tenant_id, purpose=purpose,
            task_scoped_authorization=task_scoped_authorization,
            requested_raw=requested_raw, thresholds=self.thresholds)
        event = EvidenceAccessEvent(
            tenant_id=tenant_id, evidence_id=ev.id, actor_kind="ai_worker",
            actor_id=actor_id, purpose=purpose, decision=decision.decision)
        self.access_events.append(event)
        ev.chain.append_event(event_type="AI_ACCESS_DECIDED",
                              actor=actor_id,
                              payload={"decision": decision.decision,
                                       "purpose": purpose})
        self._audit("EVIDENCE_AI_ACCESS", ev, decision=decision.decision,
                    actor_id=actor_id)
        return decision

    # -- legal hold / retention -------------------------------------------------
    def place_legal_hold(self, ev: EvidenceObject, *, reason: str,
                         placed_by: str) -> LegalHoldRecord:
        hold = LegalHoldRecord(tenant_id=ev.tenant_id, evidence_id=ev.id,
                               reason=reason, placed_by=placed_by)
        self.legal_holds.append(hold)
        ev.legal_hold = True
        if ev.state in ("ADMISSIBLE", "ADMISSIBLE_WITH_LIMITS"):
            evidence_transition(ev, "LEGAL_HOLD", actor=placed_by,
                                reason=reason)
        self._audit("EVIDENCE_LEGAL_HOLD_PLACED", ev, reason=reason)
        return hold

    def delete(self, ev: EvidenceObject, *, hard: bool,
               ctx: RetentionContext) -> RetentionDecision:
        decision = self.retention.decide(ev, hard_delete=hard, ctx=ctx)
        if decision.decision == "ALLOW_HARD_DELETE":
            self.storage.delete_hard_if_allowed(ev.storage, allowed=True)
            ev.chain.append_event(event_type="HARD_DELETED",
                                  actor=ctx.actor_role,
                                  payload={"reasons": decision.reasons})
        elif decision.decision == "ALLOW_SOFT_DELETE":
            self.storage.delete_soft(ev.storage)
            evidence_transition(ev, "DELETED_SOFT", actor=ctx.actor_role)
        self._audit("EVIDENCE_DELETE_DECISION", ev,
                    decision=decision.decision, hard=hard)
        return decision

    # -- decision contracts -------------------------------------------------------
    def build_contract(self, *, decision_type: str, tenant_id: str,
                       case_id: str, actor: str,
                       evidence: list[EvidenceObject],
                       trust_by_id: Optional[dict[str, float]] = None,
                       facts: Optional[dict] = None,
                       ai_access_level: str = "none",
                       human_verified: bool = False
                       ) -> EvidenceDecisionContract:
        contract = EvidenceDecisionContract(
            decision_type=decision_type, tenant_id=tenant_id,
            case_id=case_id, actor=actor,
            evidence_ids=[e.id for e in evidence], facts=facts or {},
            ai_access_level=ai_access_level,
            human_verified=human_verified)
        hard: list[str] = []
        trusts = []
        for ev in evidence:
            gate = admissibility_gate(ev, tenant_id=tenant_id,
                                      case_id=case_id,
                                      thresholds=self.thresholds)
            if gate.decision in ("ADMISSIBLE", "ADMISSIBLE_WITH_LIMITS"):
                contract.admissible_ids.append(ev.id)
                trusts.append((trust_by_id or {}).get(ev.id, 0.6))
            else:
                # A bad attachment is recorded and excluded — it does not
                # veto a decision that has sufficient admissible evidence.
                # Cross-boundary violations DO block the whole decision.
                contract.rejected_ids.append(ev.id)
                hard.extend(b for b in gate.hard_blockers
                            if "mismatch" in b)
        check = check_requirements(
            decision_type,
            [e for e in evidence if e.id in contract.admissible_ids],
            trust_by_id=trust_by_id, human_verified=human_verified)
        contract.hard_blockers = hard + check.missing
        contract.trust_summary = min(trusts) if trusts else 0.0
        if check.ok and not hard:
            contract.final_decision = "ALLOWED"
        elif check.missing or hard:
            contract.final_decision = "BLOCKED"
        else:
            contract.final_decision = "REVIEW"
        self.contracts.append(contract)
        if self.audit is not None:
            ev_audit = self.audit.append(
                event_type="EVIDENCE_DECISION_CONTRACT", actor=actor,
                case_id=case_id,
                payload={"decision_type": decision_type,
                         "final": contract.final_decision,
                         "admissible": len(contract.admissible_ids),
                         "rejected": len(contract.rejected_ids),
                         "hard_blockers": contract.hard_blockers})
            contract.audit_event_id = ev_audit.id
        return contract
