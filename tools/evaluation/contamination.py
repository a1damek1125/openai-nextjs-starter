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

# Pinned expected SHA-256 of each immutable evaluator asset (red-team P1-2). The
# immutability gate compares LIVE bytes to these committed constants and FAILs on
# any mismatch — a rewritten scorer/kernel is detected, not merely a deleted file.
# Re-pin DELIBERATELY when an asset legitimately changes (like SP0010's frozen
# verifier constant). Empty => not yet pinned (matches_pinned defers to presence).
EXPECTED_ASSET_HASHES = {
    "tools/evaluation/kernel.py":
        "8d071761073c05afbaee0081c43db444c4a749ec11ff037f876d91eb6b6a9e9c",
    "tools/evaluation/credits.py":
        "c7278fb3092c87ecc8d603c3677cb55e3d7904148fb1efaf16169c2feaba5ae4",
    "tools/evaluation/hardgates.py":
        "84f184e84d85b459aff0d59681df126d9492e36f9490b06cd645ca1c3b60a6f2",
    "tools/evaluation/score.py":
        "71d4d081a0f64cf53f3d585c18c65e0ee57f3411f80cb1742e8adfc34f5f6996",
    "tools/evaluation/genome.py":
        "4984fa7048f75cd241aa789372f83826c29e6f17ec5fbb10ec36ce8bf6774bac",
    "tools/evaluation/canon.py":
        "9b3f64f2e7446b23713e110553dcf37f1cfd03248ba86be5e0bdf5422bcf50d6",
    "tools/evaluation/model.py":
        "55e70b7bf0d592bcaeb9e05fbd902b21b3e6bb5bf8bd1eb9b9a1c0983ed47181",
}


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
    # compare LIVE bytes to the pinned expected hashes (P1-2); a pinned asset that
    # does not match is TAMPERED. Assets without a pin are only presence-checked
    # (disclosed), so pinning strictly strengthens the gate.
    mismatched = sorted(rel for rel, want in EXPECTED_ASSET_HASHES.items()
                        if assets.get(rel) != want)
    return {"assets": assets, "manifest_root": hash_obj(assets),
            "all_present": all(v != "MISSING" for v in assets.values()),
            "pinned_count": len(EXPECTED_ASSET_HASHES),
            "mismatched_pins": mismatched,
            "matches_pinned": not mismatched}


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
    for rel in ledger["evaluator_immutability"].get("mismatched_pins", []):
        out.append(Finding("EVALUATOR_TAMPERING", P0, rel,
                           "immutable evaluator asset does not match its pinned "
                           "hash: rewritten scorer/kernel detected (P1-2)", {}))
    for rid in ledger["answer_exposures"]:
        out.append(Finding("HOLDOUT_ACCESS_VIOLATION", P0, rid,
                           "held-out answer exposure detected in a run", {}))
    # red-team P1-3: UNKNOWN contamination is fail-closed — it must NOT silently
    # pass. An unresolved contamination signal blocks like an exposure (the
    # "UNKNOWN never becomes CLEAN" guarantee applies at the finding/gate layer,
    # not only inside classify_contamination).
    for rid in ledger.get("unknown_classes", []):
        out.append(Finding("CONTAMINATION_UNKNOWN", P0, rid,
                           "unresolved (UNKNOWN) contamination on a run: cannot "
                           "be treated as CLEAN (fail-closed)", {}))
    return out
