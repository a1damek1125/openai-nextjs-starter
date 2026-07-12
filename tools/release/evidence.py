"""Candidate-bound, bitemporal gate evidence and the append-only gate result
ledger (SP0009 §10.4, D-0009-12/13/18, AC-0009-065..068).

Evidence binds the candidate genome, the gate configuration fingerprint, the
environment and tool version, and carries the full bitemporal record
(valid_from/valid_to = when the fact held; observed_at/superseded_at = when we
recorded/retracted it). Evidence produced for one candidate can NEVER satisfy a
gate for another candidate (cross-candidate reuse rejected), stale evidence can
never pass, and ledger appends never overwrite: a rerun of a gate appends a new
result linked to the old one — it does not erase it.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, P1

OPEN = None


def evidence_record(*, candidate_genome: str, gate_id: str,
                    configuration_fingerprint: str, environment: dict,
                    tool_version: str, result: str, valid_from: str,
                    valid_to=OPEN, observed_at: str = "RUN") -> dict:
    rec = {
        "candidate_genome": candidate_genome,
        "gate_id": gate_id,
        "configuration_fingerprint": configuration_fingerprint,
        "environment": environment,
        "tool_version": tool_version,
        "result": result,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "observed_at": observed_at,
        "superseded_at": None,
    }
    rec["evidence_id"] = "GE-" + hash_obj(rec)[:20]
    return rec


def validate_for_candidate(ev: dict, *, candidate_genome: str,
                           gate_id: str, now: str) -> list[Finding]:
    """The full evidence admission check: candidate binding, gate binding,
    configuration binding, staleness (D-0009-12/13, AC-0009-067/068)."""
    out: list[Finding] = []
    subject = str(ev.get("evidence_id") or "-")
    if ev.get("candidate_genome") != candidate_genome:
        out.append(Finding(
            "GATE_INVALID", P0, subject,
            "evidence is bound to a DIFFERENT candidate genome; cross-"
            "candidate evidence reuse is rejected (D-0009-12, AC-0009-068)",
            {"evidence_genome": ev.get("candidate_genome"),
             "candidate_genome": candidate_genome}))
    if ev.get("gate_id") != gate_id:
        out.append(Finding(
            "GATE_INVALID", P1, subject,
            f"evidence was produced for gate {ev.get('gate_id')!r}, not "
            f"{gate_id!r}", {}))
    from .gates import gate_configuration_fingerprint, GATE_REGISTRY
    if gate_id in GATE_REGISTRY and ev.get("configuration_fingerprint") != \
            gate_configuration_fingerprint(gate_id):
        out.append(Finding(
            "GATE_STALE", P1, subject,
            "evidence was produced under a different gate configuration; the "
            "gate definition changed since (configuration-fingerprint bound)",
            {}))
    vt = ev.get("valid_to")
    if vt is not None and str(vt) <= str(now):
        out.append(Finding(
            "GATE_STALE", P1, subject,
            "evidence validity expired; stale evidence cannot pass "
            "(AC-0009-067)", {"valid_to": vt, "now": now}))
    if ev.get("superseded_at") is not None:
        out.append(Finding(
            "GATE_STALE", P1, subject,
            "evidence was superseded; superseded evidence cannot pass", {}))
    vf = ev.get("valid_from")
    if vt is not None and vf is not None and str(vt) < str(vf):
        out.append(Finding(
            "GATE_INVALID", P1, subject,
            f"bitemporal interval invalid: valid_to {vt!r} < valid_from "
            f"{vf!r}", {}))
    return out


# --- append-only gate result ledger (AC-0009-065, INV-0009-9/10) -----------------
class GateResultLedger:
    """Append-only: entries are never replaced or removed. A new result for the
    same gate LINKS to the prior one (rerun_of); the prior stays visible."""

    def __init__(self) -> None:
        self._entries: list[dict] = []

    def append(self, entry: dict) -> dict:
        prior = [e for e in self._entries
                 if e.get("gate_id") == entry.get("gate_id")
                 and e.get("candidate_genome") == entry.get("candidate_genome")]
        rec = dict(entry)
        rec["attempt_number"] = len(prior) + 1
        rec["rerun_of"] = prior[-1]["entry_id"] if prior else None
        rec["entry_id"] = "GL-" + hash_obj(
            {k: rec.get(k) for k in ("gate_id", "candidate_genome",
                                     "attempt_number", "result")})[:20]
        self._entries.append(rec)
        return rec

    def entries(self) -> list:
        return list(self._entries)

    def latest(self, gate_id: str, candidate_genome: str):
        matches = [e for e in self._entries if e.get("gate_id") == gate_id
                   and e.get("candidate_genome") == candidate_genome]
        return matches[-1] if matches else None

    def failures_ever(self, gate_id: str, candidate_genome: str) -> list:
        """Every recorded failure, regardless of later passes: a passing rerun
        never erases the original failure (D-0009-18)."""
        return [e for e in self._entries if e.get("gate_id") == gate_id
                and e.get("candidate_genome") == candidate_genome
                and e.get("result") == "FAIL"]

    def ledger_hash(self) -> str:
        return hash_obj(self._entries)
