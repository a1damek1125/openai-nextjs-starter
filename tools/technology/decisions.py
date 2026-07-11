"""Technology Decision Registry — append-only TDRs (SP0004 D-0004-03/04/55/75,
§10.2/§11.12, INV-0004-08/09).

An accepted decision's record is append-only: a changed decision creates a
SUPERSEDING record and the old one remains historically interpretable
(AC-0004-018/019). Decision status (lifecycle) and fitness status are distinct
(D-0004-75). A DEFER requires an explicit trigger (D-0004-04). Freshness is
technology-relative (volatility class); an invalidating trigger → INVALIDATED, an
overdue review or stale critical evidence → REVIEW_DUE (§11.12).
"""
from __future__ import annotations

from .canon import core_hash
from .model import (Finding, P0, P1, TDR_STATES, FROZEN_TDR_STATES,
                    FITNESS_STATES, REVERSIBILITY, CRITICALITY,
                    INVALID_TDR, INSUFFICIENT_EVIDENCE, APPEND_ONLY_VIOLATION,
                    TECHNOLOGY_DECISION_STALE, TECHNOLOGY_DECISION_INVALIDATED)


def tdr_index(reg: dict) -> dict[str, dict]:
    return {d["decision_id"]: d for d in reg.get("decisions", [])}


def validate_tdr(d: dict) -> list[Finding]:
    out: list[Finding] = []
    did = d.get("decision_id", "-")
    if not d.get("decision_id"):
        out.append(Finding(INVALID_TDR, P0, "-", "TDR missing decision_id", {}))
    if d.get("status") not in TDR_STATES:
        out.append(Finding(INVALID_TDR, P1, did,
                           f"invalid TDR status {d.get('status')!r}", {}))
    if d.get("fitness_status") not in FITNESS_STATES:
        out.append(Finding(INVALID_TDR, P1, did,
                           f"invalid fitness_status {d.get('fitness_status')!r}",
                           {}))
    if d.get("criticality") not in CRITICALITY:
        out.append(Finding(INVALID_TDR, P1, did,
                           f"invalid criticality {d.get('criticality')!r}", {}))
    rc = d.get("reversibility_class")
    if rc is not None and rc not in REVERSIBILITY:
        out.append(Finding(INVALID_TDR, P1, did,
                           f"invalid reversibility_class {rc!r}", {}))
    # an ACCEPTED/ACTIVE decision must cite evidence and a review policy
    if d.get("status") in ("ACCEPTED", "ACTIVE"):
        if not d.get("evidence_refs"):
            out.append(Finding(INSUFFICIENT_EVIDENCE, P0, did,
                               "accepted/active TDR without evidence_refs "
                               "(AC-0004-002)", {}))
        if d.get("criticality") in ("T3", "T4") and not d.get("review_by") \
                and not d.get("review_triggers"):
            out.append(Finding(INVALID_TDR, P1, did,
                               "critical active TDR without a review policy "
                               "(AC-0004-002)", {}))
    # a DEFERRED decision needs an explicit decision trigger (D-0004-04)
    if d.get("status") == "DEFERRED" and not (d.get("review_triggers")
                                              or d.get("decision_trigger")):
        out.append(Finding(INVALID_TDR, P1, did,
                           "DEFERRED decision without a decision trigger "
                           "(AC-0004-020)", {}))
    return out


def validate_registry(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    idx = tdr_index(reg)
    for d in reg.get("decisions", []):
        did = d.get("decision_id")
        if did in seen:
            out.append(Finding(INVALID_TDR, P0, did, "duplicate decision_id", {}))
        seen.add(did)
        out.extend(validate_tdr(d))
        # supersedes must reference existing decisions
        for s in d.get("supersedes", []):
            if s not in idx:
                out.append(Finding(INVALID_TDR, P1, did,
                                   f"supersedes unknown decision {s!r}", {}))
    return out


def check_append_only(old_reg: dict, new_reg: dict) -> list[Finding]:
    """A frozen (accepted+) decision's canonical core must never change; a change
    must appear as a NEW superseding record (INV-0004-08/09, AC-0004-018)."""
    out: list[Finding] = []
    old = tdr_index(old_reg)
    new = tdr_index(new_reg)
    for did, od in old.items():
        if od.get("status") not in FROZEN_TDR_STATES:
            continue
        nd = new.get(did)
        if nd is None:
            out.append(Finding(APPEND_ONLY_VIOLATION, P0, did,
                               "frozen decision was deleted", {}))
            continue
        # allow only status transitions to SUPERSEDED/RETIRED/INVALIDATED and
        # fitness updates; the substantive decision core is immutable.
        if _decision_core(od) != _decision_core(nd):
            out.append(Finding(APPEND_ONLY_VIOLATION, P0, did,
                               "frozen decision core was mutated in place; a "
                               "change must create a superseding record", {}))
    return out


# Only these keys may change on a frozen decision (lifecycle progression +
# editorial). EVERYTHING else is the immutable decision core — a substantive
# change (criticality, evidence_refs, exit_plan_ref, switching_cost, …) must
# create a superseding record, not mutate in place (red-team hardening: an
# allowlist of "core fields" silently permitted mutation of unlisted substantive
# fields, so the core is now defined by EXCLUSION).
MUTABLE_FIELDS = frozenset({"status", "fitness_status", "title", "context",
                            "notes", "display_name", "_comment"})


def _decision_core(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in MUTABLE_FIELDS}


def decision_core_hash(d: dict) -> str:
    return core_hash(_decision_core(d))


def freshness(d: dict, *, today: str, invalidating_triggers_fired: bool = False,
              critical_evidence_stale: bool = False) -> str:
    """Decision freshness (§11.12). `today` and staleness are passed in (no
    wall-clock in the tooling, for determinism)."""
    if invalidating_triggers_fired:
        return "INVALIDATED"
    rb = d.get("review_by")
    if rb is not None and str(rb) < str(today):
        return "REVIEW_DUE"
    if critical_evidence_stale:
        return "REVIEW_DUE"
    return "CURRENT"


def freshness_findings(reg: dict, *, today: str,
                       invalidated_ids: set[str] | None = None,
                       stale_evidence_ids: set[str] | None = None
                       ) -> list[Finding]:
    invalidated_ids = invalidated_ids or set()
    stale_evidence_ids = stale_evidence_ids or set()
    out: list[Finding] = []
    for d in reg.get("decisions", []):
        if d.get("status") not in ("ACTIVE", "ACCEPTED", "REVIEW_DUE"):
            continue
        did = d.get("decision_id", "-")
        f = freshness(d, today=today,
                      invalidating_triggers_fired=did in invalidated_ids,
                      critical_evidence_stale=did in stale_evidence_ids)
        if f == "INVALIDATED":
            out.append(Finding(TECHNOLOGY_DECISION_INVALIDATED, P1, did,
                               "decision invalidated by a fired trigger", {}))
        elif f == "REVIEW_DUE":
            out.append(Finding(TECHNOLOGY_DECISION_STALE, P2, did,
                               "decision review overdue / evidence stale "
                               "(advisory)", {}))
    return out
