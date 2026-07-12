"""Immutable release candidates and the Candidate Genome (SP0009 §10.1,
§11.11, D-0009-02/03).

A candidate is a proof-carrying identity for one exact proposed release: it
binds source commit, dependency-closed release slice, SP0008 Contract Genome
root, dependency locks, CI workflow state, toolchain, gate policy epoch, build
inputs and (where applicable) the AI Release Closure. The genome is the SHA-256
of the canonical serialization of those bindings — ANY material change yields a
different genome and therefore a NEW candidate. Evidence and approvals are
genome-bound and can never silently follow a changed candidate (INV-0009-1..4).
Supersession, cancellation and pause/resume preserve history; nothing is erased.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import (Finding, P0, P1, CANDIDATE_STATES, report)

GENOME_FIELDS = ("source_commit", "release_slice_ref", "contract_genome_root",
                 "dependency_lock_hash", "ci_workflow_hash", "toolchain_hash",
                 "release_policy_epoch", "build_input_hash",
                 "ai_release_closure_hash")


def candidate_genome(bindings: dict) -> str:
    """CandidateGenome = SHA256(CanonicalJSON(material bindings)) (§11.11).
    Missing material bindings are hashed as explicit nulls — absence is part of
    the identity, never silently equal to presence."""
    material = {k: bindings.get(k) for k in GENOME_FIELDS}
    return hash_obj(material)


def new_candidate(candidate_id: str, bindings: dict) -> dict:
    genome = candidate_genome(bindings)
    return {
        "candidate_id": candidate_id,
        "candidate_genome": genome,
        **{k: bindings.get(k) for k in GENOME_FIELDS},
        "change_intent_refs": list(bindings.get("change_intent_refs") or []),
        "artifact_refs": [],
        "status": "DRAFT",
        "superseded_by": None,
        "history": [],
    }


def verify_genome(candidate: dict) -> list[Finding]:
    """Recompute the genome from the candidate's own bindings; divergence means
    the candidate was mutated after creation (CANDIDATE_GENOME_MISMATCH, P0)."""
    fresh = candidate_genome(candidate)
    out: list[Finding] = []
    if fresh != candidate.get("candidate_genome"):
        out.append(Finding(
            "CANDIDATE_GENOME_MISMATCH", P0, str(candidate.get("candidate_id")),
            "candidate bindings do not match the recorded genome: the "
            "candidate was materially changed after creation — a material "
            "change must create a NEW candidate (D-0009-02)",
            {"recorded": candidate.get("candidate_genome"),
             "recomputed": fresh}))
    return out


def material_change(candidate: dict, new_bindings: dict) -> bool:
    """True if new bindings would change the genome (=> new candidate)."""
    merged = {**{k: candidate.get(k) for k in GENOME_FIELDS}, **new_bindings}
    return candidate_genome(merged) != candidate.get("candidate_genome")


def supersede(old: dict, new_id: str, new_bindings: dict) -> tuple:
    """Create a successor candidate; the old one becomes SUPERSEDED but remains
    fully historical (AC-0009-042). Evidence does NOT move (D-0009-02)."""
    merged = {**{k: old.get(k) for k in GENOME_FIELDS}, **new_bindings}
    successor = new_candidate(new_id, merged)
    old_after = dict(old)
    old_after["status"] = "SUPERSEDED"
    old_after["superseded_by"] = new_id
    old_after["history"] = list(old.get("history") or []) + [
        {"event": "CANDIDATE_SUPERSEDED", "successor": new_id}]
    return old_after, successor


# --- lifecycle -----------------------------------------------------------------
_TRANSITIONS = {
    "DRAFT": {"CLASSIFIED", "CANCELLED"},
    "CLASSIFIED": {"IMPACT_ANALYZED", "BLOCKED", "PAUSED", "CANCELLED"},
    "IMPACT_ANALYZED": {"SLICE_CLOSED", "BLOCKED", "PAUSED", "CANCELLED"},
    "SLICE_CLOSED": {"GATES_PLANNED", "BLOCKED", "PAUSED", "CANCELLED"},
    "GATES_PLANNED": {"VERIFYING", "BLOCKED", "PAUSED", "CANCELLED"},
    "VERIFYING": {"QUALIFIED", "BLOCKED", "PAUSED", "CANCELLED",
                  "INVALIDATED"},
    "QUALIFIED": {"ARTIFACT_CLOSURE_SEALED", "SUSPENDED_BY_DEFEATER",
                  "INVALIDATED", "SUPERSEDED"},
    "ARTIFACT_CLOSURE_SEALED": {"READY_FOR_LATER_PROMOTION",
                                "SUSPENDED_BY_DEFEATER", "INVALIDATED"},
    "READY_FOR_LATER_PROMOTION": {"SUSPENDED_BY_DEFEATER", "SUPERSEDED",
                                  "INVALIDATED"},
    "BLOCKED": {"VERIFYING", "CLASSIFIED", "CANCELLED", "SUPERSEDED"},
    "PAUSED": {},          # resume() is the only exit — it revalidates
    "SUSPENDED_BY_DEFEATER": {"REQUALIFICATION_REQUIRED", "INVALIDATED"},
    "REQUALIFICATION_REQUIRED": {"VERIFYING", "CANCELLED", "SUPERSEDED"},
    "CANCELLED": set(), "SUPERSEDED": set(), "INVALIDATED": set(),
}


def transition(candidate: dict, to_state: str) -> dict:
    if to_state not in CANDIDATE_STATES:
        raise ValueError(f"unknown state {to_state!r}")
    frm = candidate.get("status")
    if to_state not in _TRANSITIONS.get(frm, set()):
        raise ValueError(f"illegal candidate transition {frm} -> {to_state}")
    after = dict(candidate)
    after["status"] = to_state
    after["history"] = list(candidate.get("history") or []) + [
        {"event": "TRANSITION", "from": frm, "to": to_state}]
    return after


# --- pause / resume (FUNCTION P, D-0009-51) --------------------------------------
def pause(candidate: dict, *, next_action: str, open_obligations: list) -> dict:
    """Pause preserves candidate identity, gate ledger, failures, approvals,
    blockers, next action, pending obligations."""
    frm = candidate.get("status")
    after = dict(candidate)
    after["status"] = "PAUSED"
    after["pause_context"] = {
        "paused_from": frm,
        "next_action": next_action,
        "open_obligations": list(open_obligations),
    }
    after["history"] = list(candidate.get("history") or []) + [
        {"event": "CANDIDATE_PAUSED", "from": frm}]
    return after


def resume(candidate: dict, *, evidence_records: list,
           now: str) -> tuple:
    """Resume returns to the paused-from state AND flags every evidence record
    that went stale while paused — stale evidence must be revalidated, never
    silently reused (INV-0009-58).

    Only a PAUSED candidate may resume — resume can never force a non-paused
    candidate into VERIFYING (red-team #8)."""
    if candidate.get("status") != "PAUSED" or not candidate.get(
            "pause_context"):
        raise ValueError("resume requires a PAUSED candidate with a "
                         "pause_context")
    ctx = candidate.get("pause_context") or {}
    frm = ctx.get("paused_from") or "VERIFYING"
    after = dict(candidate)
    after["status"] = frm
    after["history"] = list(candidate.get("history") or []) + [
        {"event": "CANDIDATE_RESUMED", "to": frm}]
    stale: list[Finding] = []
    for ev in evidence_records:
        vt = ev.get("valid_to")
        if vt is not None and str(vt) <= str(now):
            stale.append(Finding(
                "GATE_STALE", P1, str(ev.get("evidence_id") or "-"),
                "evidence expired while the candidate was paused; it must be "
                "revalidated before reuse (resume revalidates, INV-0009-58)",
                {"valid_to": vt, "now": now}))
    return after, stale


def cancel(candidate: dict, *, reason: str) -> dict:
    after = dict(candidate)
    after["status"] = "CANCELLED"
    after["history"] = list(candidate.get("history") or []) + [
        {"event": "CANCELLED", "reason": reason}]
    return after
