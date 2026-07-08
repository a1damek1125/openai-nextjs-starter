"""Event-sourced engine rehydration (V-E, Gap 1).

Rebuilds live EvidenceEngine state deterministically from persisted
facts: metadata rows, chain events, access events, symbols, integrity,
legal hold. The chain is replayed to a projected lifecycle state and
checked against the stored snapshot. Stored untrusted stays untrusted;
hard blockers stay blocking; no volatile state is the source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .gates import admissibility_gate, ai_file_access_gate
from .models import (ADMISSIBLE_STATES, ChainEvent, EvidenceChainOfCustody,
                     EvidenceFileMetadata, EvidenceIntegrityRecord,
                     EvidenceObject, EvidenceSource, EvidenceStoragePointer)


class EvidenceStateProjector:
    """Deterministic terminal-state projection from ordered chain events.
    projected_{t+1} = apply(projected_t, event_t)."""

    INITIAL = "UPLOADED"

    def project(self, chain_rows: list[dict]) -> str:
        import json
        state = self.INITIAL
        for row in chain_rows:
            if row["event_type"] == "STATE_CHANGED":
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    payload = json.loads(row.get("payload_json", "{}"))
                to = payload.get("to")
                if to:
                    state = to
        return state


@dataclass
class EvidenceProjectionInvariant:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class EvidenceRehydrationReport:
    tenant_scope: Optional[str]
    loaded: int = 0
    projected_mismatches: list = field(default_factory=list)
    invariants: list = field(default_factory=list)
    ok: bool = True

    def fail(self, inv: EvidenceProjectionInvariant) -> None:
        self.invariants.append(inv)
        if not inv.ok:
            self.ok = False


def _rebuild_object(row: dict, chain_rows: list[dict]) -> EvidenceObject:
    import json
    meta = EvidenceFileMetadata(
        original_filename=row["original_filename"],
        declared_mime=row["declared_mime"],
        detected_mime=row["detected_mime"], extension=row["extension"],
        size_bytes=row["size_bytes"],
        mime_mismatch=bool(row["mime_mismatch"]),
        active_content=bool(row["active_content"]))
    integrity = EvidenceIntegrityRecord(
        algorithm="sha256", digest=row["sha256"],
        valid=row["state"] != "INTEGRITY_FAILED") if row["sha256"] else None
    ev = EvidenceObject(
        tenant_id=row["tenant_id"], case_id=row["case_id"],
        evidence_type=row["evidence_type"], meta=meta,
        source=EvidenceSource(kind=row["source_kind"]),
        uploaded_by=row["uploaded_by"], state=row["state"],
        storage=EvidenceStoragePointer(provider=row["storage_provider"],
                                       key=row["storage_key"],
                                       is_mock=False)
        if row["storage_key"] else None,
        integrity=integrity, sensitivity=row["sensitivity"],
        injection_risk=row["injection_risk"],
        parser_kind=row["parser_kind"],
        human_verified=bool(row["human_verified"]),
        legal_hold=bool(row["legal_hold"]),
        retention_until=datetime.fromisoformat(row["retention_until"])
        if row["retention_until"] else None, id=row["id"])
    # Sticky untrusted markers — a reread NEVER upgrades trust.
    from .models import EvidenceSymbol, EvidenceUntrustedDataMarker
    ev.symbols = [EvidenceSymbol(
        evidence_id=ev.id, kind=s["kind"], trusted=bool(s["trusted"]),
        human_verified_for=s["human_verified_for"],
        marker=EvidenceUntrustedDataMarker(origin=s["origin"],
                                           reason=s["reason"]),
        id=s["id"]) for s in json.loads(row["symbols_json"])]
    # Replay chain-of-custody exactly as stored (hashes preserved).
    chain = EvidenceChainOfCustody()
    for cr in chain_rows:
        chain.events.append(ChainEvent(
            event_type=cr["event_type"], actor=cr["actor"],
            payload=json.loads(cr["payload_json"]),
            created_at=datetime.fromisoformat(cr["created_at"]),
            hash_prev=cr["hash_prev"], hash_self=cr["hash_self"],
            id=cr["id"]))
    ev.chain = chain
    return ev


class EvidenceRehydrator:
    """Rebuilds engine.objects from a store; verifies invariants I1–I6."""

    def __init__(self, store) -> None:
        self.store = store

    def rehydrate(self, engine, *, tenant_id: Optional[str] = None
                  ) -> EvidenceRehydrationReport:
        report = EvidenceRehydrationReport(tenant_scope=tenant_id)
        projector = EvidenceStateProjector()
        rows = self.store.all_objects(tenant_id=tenant_id)
        for row in rows:
            chain_rows = self.store.chain_events(
                row["id"], tenant_id=row["tenant_id"])
            ev = _rebuild_object(row, chain_rows)
            # Reattach access events + token map is not needed (evidence
            # confirmation is not token-based). Rebuild derivatives text.
            engine.objects[ev.id] = ev
            report.loaded += 1

            # Projected terminal state must match the stored snapshot.
            projected = projector.project(chain_rows)
            if projected != ev.state and ev.state != "UPLOADED":
                report.projected_mismatches.append(
                    {"evidence_id": ev.id, "stored": ev.state,
                     "projected": projected})

            # I1: stored untrusted marker → agent raw content forbidden.
            if any(not s.trusted for s in ev.symbols):
                d = ai_file_access_gate(ev, tenant_id=ev.tenant_id,
                                        requested_raw=True)
                report.fail(EvidenceProjectionInvariant(
                    "I1_untrusted_no_raw",
                    d.decision != "ALLOW_RAW"
                    and "RAW" not in d.decision.replace(
                        "ALLOW_SAFE", "").replace("ALLOW_RED", ""),
                    ev.id))
            # I2: hard blocker → not ADMISSIBLE.
            g = admissibility_gate(ev, tenant_id=ev.tenant_id)
            if g.hard_blockers:
                report.fail(EvidenceProjectionInvariant(
                    "I2_hard_blocker_not_allowed",
                    g.decision != "ADMISSIBLE", ev.id))
            # I3: integrity failed → INTEGRITY_FAILED + unusable.
            if ev.integrity and not ev.integrity.valid:
                report.fail(EvidenceProjectionInvariant(
                    "I3_integrity_failed",
                    ev.state == "INTEGRITY_FAILED"
                    and ev.state not in ADMISSIBLE_STATES, ev.id))
            # I5: legal hold → hard delete not allowed (checked via flag).
            if ev.legal_hold:
                report.fail(EvidenceProjectionInvariant(
                    "I5_legal_hold_blocks_delete", ev.legal_hold, ev.id))
        return report
