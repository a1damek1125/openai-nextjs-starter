"""Extraction Uncertainty Firewall (SP0010 V5 FUNCTION T, §0, D-0010-70..74).

Every node that enters the Architecture Description Graph is either a HARD FACT
(it carries a verifiable on-disk source span) or an EXTRACTED CLAIM (an agent or
document asserted it). This firewall guarantees the second kind can never be
promoted to hard truth without grounding: each declared node must resolve at
least one **source span** — a `path` that exists and, if a `symbol` is given,
that symbol must literally occur in the file (the same grounding discipline the
invariant/counterfactual controls already use). A node whose spans do NOT
resolve is quarantined `UNGROUNDED`; it is admitted to the graph only as an
UNGROUNDED node, is excluded from every hard-truth root, and — if it is a
critical node — blocks closure (fail-closed). Partial grounding is disclosed,
never rounded up to GROUNDED.

Governance/analysis tooling only; never imported by product code; no external
effect; emits no secret values.
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj
from .model import (Finding, P0, P1, P2, EXTRACTION_GROUNDING)


def source_span(*, path: str, symbol: str | None = None,
                kind: str = "file") -> dict:
    """A claimed on-disk location backing a declared node. `kind` is advisory
    (file / symbol / directory); grounding is decided by resolution, not label."""
    span = {"path": path, "symbol": symbol, "kind": kind}
    span["span_id"] = "SPAN-" + hash_obj(span)[:12]
    return span


def resolve_span(root: Path, span: dict) -> dict:
    """Resolve a span against the real tree. A span RESOLVES iff its file exists
    AND (when a symbol is named) the symbol literally occurs in the file. A bare
    directory/file span resolves on existence. Reading failures resolve to
    False, never to a silent pass (fail-closed)."""
    p = root / span["path"]
    if not p.exists():
        return {**span, "resolved": False, "reason": "PATH_ABSENT"}
    sym = span.get("symbol")
    if not sym:
        return {**span, "resolved": True, "reason": "EXISTS"}
    if p.is_dir():
        # a directory with a named symbol: existence only (cannot grep a tree
        # deterministically without ordering assumptions); disclosed as such.
        return {**span, "resolved": True, "reason": "DIR_EXISTS_SYMBOL_UNCHECKED"}
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {**span, "resolved": False, "reason": "UNREADABLE"}
    if sym in text:
        return {**span, "resolved": True, "reason": "SYMBOL_PRESENT"}
    return {**span, "resolved": False, "reason": "SYMBOL_ABSENT"}


def ground_node(root: Path, *, node_id: str, critical: bool,
                spans: list, extracted: bool = False) -> dict:
    """Classify a declared node's grounding. `extracted=True` marks a node that
    an agent/document asserted (not a hard fact); such a node MUST resolve a span
    to be trusted — the firewall's whole purpose (D-0010-70)."""
    resolved = [resolve_span(root, s) for s in spans]
    n_ok = sum(1 for r in resolved if r["resolved"])
    if not spans:
        grounding = "UNGROUNDED"
    elif n_ok == len(resolved):
        grounding = "GROUNDED"
    elif n_ok == 0:
        grounding = "UNGROUNDED"
    else:
        grounding = "PARTIALLY_GROUNDED"
    assert grounding in EXTRACTION_GROUNDING
    return {
        "node_id": node_id,
        "critical": critical is True,
        "extracted": extracted is True,
        "spans": resolved,
        "resolved_count": n_ok,
        "span_count": len(resolved),
        "grounding": grounding,
        # a node is admitted as HARD TRUTH only when fully grounded; an
        # extracted node that is not GROUNDED is quarantined.
        "hard_truth": grounding == "GROUNDED",
    }


def firewall(root: Path, declared_nodes: list) -> dict:
    """Run the firewall over a list of declared nodes. Returns the per-node
    grounding plus the quarantine set (nodes that may NOT enter hard-truth
    roots)."""
    graded = [ground_node(root, **n) for n in declared_nodes]
    quarantined = [g["node_id"] for g in graded if not g["hard_truth"]]
    hard = [g["node_id"] for g in graded if g["hard_truth"]]
    return {
        "nodes": graded,
        "hard_truth_nodes": sorted(hard),
        "quarantined_nodes": sorted(quarantined),
        "firewall_root": hash_obj(sorted(
            (g["node_id"], g["grounding"]) for g in graded)),
    }


def extraction_findings(fw: dict) -> list[Finding]:
    out: list[Finding] = []
    for g in fw["nodes"]:
        if g["grounding"] == "UNGROUNDED":
            sev = P0 if g["critical"] else P1
            out.append(Finding(
                "EXTRACTION_NODE_UNGROUNDED", sev, g["node_id"],
                "declared node has no resolvable on-disk source span: it is "
                "quarantined and cannot become hard truth (D-0010-70)"
                + (" — critical node blocks closure" if g["critical"] else ""),
                {"grounding": g["grounding"], "extracted": g["extracted"]}))
        elif g["grounding"] == "PARTIALLY_GROUNDED":
            out.append(Finding(
                "EXTRACTION_PARTIALLY_GROUNDED",
                P1 if g["critical"] else P2, g["node_id"],
                f"declared node is only partially grounded "
                f"({g['resolved_count']}/{g['span_count']} spans resolve); the "
                "unresolved spans are disclosed, not rounded up (D-0010-72)",
                {"unresolved": [s for s in g["spans"] if not s["resolved"]]}))
    return out
