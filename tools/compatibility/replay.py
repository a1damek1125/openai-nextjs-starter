"""Workflow Replay Harness, Proof Interpretability, and Differential /
Metamorphic verification (SP0007 §11.3/§11.4, D-0007-31/32/33/34/54/55/56,
AC-0007-101..110).

Recorded workflow histories are replayed deterministically against a candidate
transition table; any divergence yields a concrete counterexample (D-0007-31/
33). Passing recorded histories is BOUNDED evidence — it never proves all
possible histories, and results always say so (D-0007-32). Every historical
proof envelope version must stay readable, and a new validator can never
silently reinterpret an old proof (D-0007-34, INV-0007-26/27/28). Differential
execution compares two implementations over the corpus (D-0007-55); metamorphic
checks confirm that invariant-preserving mutations do not change evaluation
(D-0007-56).
"""
from __future__ import annotations

from .model import (Finding, P0, WORKFLOW_REPLAY_FAILED,
                    PROOF_VERSION_UNREADABLE)
from .canon import core_hash


def replay_history(history: list[dict], transition_table: dict, *,
                   initial: str) -> dict:
    """Deterministically replay one recorded history against a candidate
    transition table (D-0007-31). A missing transition or a different next
    state is a divergence with a counterexample; a full match is bounded
    evidence only (D-0007-32)."""
    state = initial
    for i, item in enumerate(history):
        event = item.get("event")
        expected = item.get("to_state")
        candidate = transition_table.get(state, {}).get(event)
        if candidate != expected:
            return {"replayed": i, "diverged": True, "divergence_index": i,
                    "counterexample": {"state": state, "event": event,
                                       "expected": expected,
                                       "candidate": candidate},
                    "verdict": "DIVERGED", "bounded_evidence": True}
        state = expected
    return {"replayed": len(history), "diverged": False,
            "verdict": "REPLAY_PASSED", "bounded_evidence": True,
            "note": "passing recorded histories does not prove all possible "
                    "histories (D-0007-32)"}


def replay_findings(histories: list[list[dict]], table, *,
                    initial) -> list[Finding]:
    """WORKFLOW_REPLAY_FAILED (P0) per diverged history, carrying the
    counterexample (D-0007-33, AC-0007-101..104)."""
    out: list[Finding] = []
    for idx, history in enumerate(histories):
        result = replay_history(history, table, initial=initial)
        if result["verdict"] == "DIVERGED":
            out.append(Finding(
                WORKFLOW_REPLAY_FAILED, P0, f"history[{idx}]",
                "candidate transition table diverges from recorded workflow "
                f"history at step {result['divergence_index']} (D-0007-31)",
                {"counterexample": result["counterexample"],
                 "divergence_index": result["divergence_index"]}))
    return out


def proof_interpretability_findings(old_proof: dict,
                                    readers: dict) -> list[Finding]:
    """Every historical proof envelope version stays readable (D-0007-34,
    INV-0007-26/27); a new validator can never silently reinterpret an old
    proof (AC-0007-108, INV-0007-28)."""
    out: list[Finding] = []
    version = old_proof.get("envelope_version")
    subject = str(version or old_proof.get("proof_id") or "-")
    if not version or version not in readers:
        out.append(Finding(
            PROOF_VERSION_UNREADABLE, P0, subject,
            f"no reader registered for historical proof envelope version "
            f"{version!r}; the proof is unverifiable (D-0007-34, "
            "INV-0007-26/27)", {"envelope_version": version,
                                "readers": sorted(map(str, readers))}))
    for ver, reader in readers.items():
        if isinstance(reader, dict) and reader.get("reinterprets"):
            out.append(Finding(
                PROOF_VERSION_UNREADABLE, P0, str(ver),
                "new validator cannot silently reinterpret old proof "
                "(AC-0007-108, INV-0007-28)",
                {"reader": ver, "reinterprets": reader.get("reinterprets")}))
    return out


def _run(impl, payload) -> str:
    try:
        return core_hash(impl(payload))
    except Exception as exc:  # an exception is itself a divergent behavior
        return core_hash({"error": str(exc)})


def differential(fixtures: list[dict], impl_a, impl_b) -> dict:
    """Differential execution over the corpus (D-0007-55, AC-0007-109/110):
    both implementations run every fixture payload; results are compared by
    canonical hash. An exception counts as divergent behavior."""
    divergences: list[dict] = []
    for fx in fixtures:
        payload = fx.get("payload")
        a_hash = _run(impl_a, payload)
        b_hash = _run(impl_b, payload)
        if a_hash != b_hash:
            divergences.append({"fixture_id": fx.get("fixture_id"),
                                "a_hash": a_hash, "b_hash": b_hash})
    return {"fixtures": len(fixtures), "divergences": divergences,
            "verdict": "CONSISTENT" if not divergences else "DIVERGENT"}


def metamorphic_checks(payload: dict, evaluate) -> dict:
    """Metamorphic verification (D-0007-56): invariant-preserving mutations
    (irrelevant extra field, key reorder, presentation-value rename) must not
    change the evaluation, compared by canonical hash."""
    baseline = _run(evaluate, payload)

    with_extra = dict(payload)
    with_extra["_mm_extra"] = "irrelevant-optional-field"

    reordered = dict(reversed(list(payload.items())))

    renamed = dict(payload)
    presentation_key = "display_name" if "display_name" in payload else "label"
    renamed[presentation_key] = "_mm_renamed_presentation_value"

    checks = []
    for mutation, mutated in (("add_irrelevant_field", with_extra),
                              ("reorder_keys", reordered),
                              ("rename_presentation_value", renamed)):
        held = _run(evaluate, mutated) == baseline
        checks.append({"mutation": mutation, "invariant_held": held})
    return {"checks": checks, "all_held": all(c["invariant_held"]
                                              for c in checks)}
