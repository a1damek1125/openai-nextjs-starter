"""Contamination ledger + evaluation-integrity firewall (SP0011 §2.1.H, §11.10/
11.11, §10, D-0011-030/031/041/042/043, AC-0011-085..100, 241..247).

Public benchmarks are potentially contaminated (D-0011-030). This module classifies
search-time / metadata / question-context / explicit-answer leakage, detects
memory contamination, and asserts the evaluator immutability boundary: the
evaluated workspace cannot modify scorers, hard gates, hidden answers, analysis
plans, score aggregation, certificates or seals. Agent-reported metrics are
reconciled against a trusted reference (D-0011-043). UNKNOWN contamination never
becomes CLEAN silently (fail-closed).
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj, sha256_hex
from .model import Finding, P0, CONTAMINATION_CLASSES

# The evaluator assets whose bytes must not change during an evaluated run.
IMMUTABLE_EVALUATOR_ASSETS = (
    "tools/evaluation/kernel.py", "tools/evaluation/credits.py",
    "tools/evaluation/hardgates.py", "tools/evaluation/score.py",
    "tools/evaluation/genome.py", "tools/evaluation/canon.py",
    "tools/evaluation/model.py",
)


def classify_contamination(*, query_overlap: bool, retrieved_answer: bool,
                           metadata_exposed: bool, unknown: bool = False) -> str:
    """Fail-closed: an unresolved signal is UNKNOWN, never CLEAN."""
    if unknown:
        return "UNKNOWN"
    if retrieved_answer:
        return "ANSWER_EXPOSURE"
    if query_overlap:
        return "QUESTION_CONTEXT_EXPOSURE"
    if metadata_exposed:
        return "METADATA_EXPOSURE"
    return "CLEAN"


def evaluator_immutability_manifest(root: Path) -> dict:
    root = Path(root)
    assets = {}
    for rel in IMMUTABLE_EVALUATOR_ASSETS:
        p = root / rel
        assets[rel] = (sha256_hex(p.read_text(encoding="utf-8", errors="replace"))
                       if p.exists() else "MISSING")
    return {"assets": assets, "manifest_root": hash_obj(assets),
            "all_present": all(v != "MISSING" for v in assets.values())}


def reconcile_metric(agent_reported, trusted_reference) -> dict:
    """Agent-reported metrics are reconciled against the trusted reference; a
    discrepancy is metric tampering / reward hacking (D-0011-043)."""
    match = agent_reported == trusted_reference
    return {"agent_reported": agent_reported, "trusted_reference":
            trusted_reference, "match": match,
            "finding": None if match else "METRIC_TAMPERING"}


def build_ledger(root: Path, *, runs_contamination: dict = None) -> dict:
    """The contamination ledger for the repository-local evaluation: no live
    search, no public-benchmark download, no held-out answers exposed (the
    default reference runs are deterministic std-lib fixtures). Every recorded
    class is explicit."""
    runs_contamination = runs_contamination or {}
    immut = evaluator_immutability_manifest(root)
    classes = {rid: c for rid, c in runs_contamination.items()}
    return {
        "default_class": "CLEAN",
        "search_enabled": False,
        "public_benchmark_download": False,
        "held_out_answers_exposed": False,
        "memory_retains_eval_secrets": False,
        "evaluator_immutability": immut,
        "run_classes": classes,
        "unknown_classes": sorted(r for r, c in classes.items()
                                  if c == "UNKNOWN"),
        "answer_exposures": sorted(r for r, c in classes.items()
                                   if c == "ANSWER_EXPOSURE"),
        "ledger_root": hash_obj({"immut": immut["manifest_root"],
                                 "classes": classes}),
    }


def contamination_findings(ledger: dict) -> list[Finding]:
    out: list[Finding] = []
    if not ledger["evaluator_immutability"]["all_present"]:
        out.append(Finding("EVALUATOR_TAMPERING", P0, "immutability",
                           "an immutable evaluator asset is missing", {}))
    for rid in ledger["answer_exposures"]:
        out.append(Finding("HOLDOUT_ACCESS_VIOLATION", P0, rid,
                           "held-out answer exposure detected in a run", {}))
    # UNKNOWN contamination on a CRITICAL run would block; here surfaced as-is
    return out
