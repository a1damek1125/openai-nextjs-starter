"""Constitutional baseline freeze (SP0010 FUNCTION A, §2.1, D-0010-27).

Records the exact repository snapshot being verified: branch/HEAD, predecessor
SP commits, migration frontier, predecessor twin/genome roots (read from the
committed artifacts), and the FROZEN SP0009 verifier identity (a content hash of
the exact verifier files, so a verifier modified inside this qualification step
cannot masquerade as the frozen one, D-0010-23/49). Any material change after
freeze invalidates the closure candidate (a fresh freeze that diverges from the
recorded one raises BASELINE_CHANGED_AFTER_FREEZE).

Git commit SHAs are recorded facts of the freeze ceremony (the tooling opens no
subprocess); everything else is derived deterministically from the tree.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from .canon import hash_obj, sha256_hex
from .model import Finding, P0

BRANCH = "claude/finalis-ai-casewoker-blueprint-f1huse"
FRONTIER_VERSION = 27

# predecessor SP commits recorded at the freeze ceremony (git log, HEAD=SP0009)
PREDECESSOR_COMMITS = {
    "SP0000": "e1b6b5c", "SP0001": "19413f2", "SP0002": "3eacdb0",
    "SP0003": "1ffb4e4", "SP0004": "e82ca87", "SP0005": "610e1e3",
    "SP0006": "d6ac046", "SP0007": "4eda536", "SP0008": "bb80912",
    "SP0009": "1e29581",
}

# The RECORDED frozen SP0009 verifier identity, captured at the freeze ceremony
# and hardcoded as a COMMITTED CONSTANT (like PREDECESSOR_COMMITS). The bootstrap
# ceremony compares the LIVE recompute against THIS constant — not against a
# freshly-recomputed value — so modifying tools/release/*.py inside this
# qualification step trips FROZEN_VERIFIER_MODIFIED (red-team P1-3, D-0010-23).
RECORDED_FROZEN_SP0009_VERIFIER_HASH = (
    "92d9590c09ec3f7d3b9eef21cfa87d9ac9be7aa6d6fc61e8a6f2520c93a1df0b")

# the exact files that constitute the frozen SP0009 verifier (D-0010-23)
FROZEN_SP0009_VERIFIER_FILES = (
    "tools/release/validate.py", "tools/release/modelcheck.py",
    "tools/release/boundary.py", "tools/release/envelope.py",
    "tools/release/qualify.py",
)

# committed twin/genome root artifacts: (path, top-level key)
TWIN_ROOT_SOURCES = {
    "contract_genome": ("docs/contracts_inventory/FINALIS_CONTRACT_GENOME.json",
                        "global_root"),
    "release_assurance": ("docs/release/FINALIS_RELEASE_TWIN.json",
                          "twin_digest"),
    "contract_inventory": ("docs/contracts_inventory/"
                           "FINALIS_CONTRACT_INVENTORY.json", "inventory_digest"),
}


def _migration_frontier(root: Path) -> int:
    db = root / "finalis" / "portal" / "db.py"
    if not db.exists():
        return 0
    try:
        tree = ast.parse(db.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return 0
    versions = []
    for node in ast.walk(tree):
        value = None
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "MIGRATIONS"
                for t in node.targets):
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(
                node.target, ast.Name) and node.target.id == "MIGRATIONS":
            value = node.value
        if isinstance(value, (ast.List, ast.Tuple)):
            for elt in value.elts:
                if isinstance(elt, ast.Tuple) and elt.elts and isinstance(
                        elt.elts[0], ast.Constant) and isinstance(
                        elt.elts[0].value, int):
                    versions.append(elt.elts[0].value)
    return max(versions) if versions else 0


def _file_hash(path: Path) -> str:
    return sha256_hex(path.read_text(encoding="utf-8", errors="replace"))


def frozen_verifier_hash(root: Path) -> str:
    """Content hash of the exact frozen SP0009 verifier files (D-0010-23)."""
    parts = []
    for rel in FROZEN_SP0009_VERIFIER_FILES:
        p = root / rel
        parts.append((rel, _file_hash(p) if p.exists() else "MISSING"))
    return hash_obj(parts)


def twin_roots(root: Path) -> dict:
    out = {}
    for name, (rel, key) in sorted(TWIN_ROOT_SOURCES.items()):
        p = root / rel
        if p.exists():
            try:
                out[name] = json.load(open(p, encoding="utf-8")).get(key,
                                                                     "ABSENT")
            except (ValueError, OSError):
                out[name] = "UNREADABLE"
        else:
            out[name] = "ABSENT"
    return out


def freeze(root: Path) -> dict:
    """Produce the deterministic baseline freeze record."""
    root = Path(root)
    rec = {
        "branch": BRANCH,
        "head": PREDECESSOR_COMMITS["SP0009"],
        "predecessor_commits": PREDECESSOR_COMMITS,
        "migration_frontier": _migration_frontier(root),
        "twin_roots": twin_roots(root),
        "frozen_sp0009_verifier_hash": frozen_verifier_hash(root),
        "recorded_frozen_sp0009_verifier_hash":
            RECORDED_FROZEN_SP0009_VERIFIER_HASH,
        "frozen_verifier_matches_recorded":
            frozen_verifier_hash(root) == RECORDED_FROZEN_SP0009_VERIFIER_HASH,
        "program_registry_present": (root / "docs" / "program" /
                                     "FINALIS_1000_PROGRAM_REGISTRY.json"
                                     ).exists(),
    }
    rec["freeze_hash"] = hash_obj(rec)
    return rec


def check_frozen(recorded: dict, root: Path) -> list[Finding]:
    """A fresh freeze that diverges from the recorded one means the baseline
    changed after freeze (D-0010-27)."""
    out: list[Finding] = []
    fresh = freeze(root)
    if fresh["freeze_hash"] != recorded.get("freeze_hash"):
        out.append(Finding(
            "BASELINE_CHANGED_AFTER_FREEZE", P0, "baseline",
            "repository baseline changed after freeze: the closure candidate "
            "is invalidated (D-0010-27)",
            {"recorded": recorded.get("freeze_hash"),
             "fresh": fresh["freeze_hash"]}))
    if fresh["migration_frontier"] != FRONTIER_VERSION:
        out.append(Finding(
            "BASELINE_CHANGED", P0, "migration_frontier",
            f"migration frontier is v{fresh['migration_frontier']}, expected "
            f"v{FRONTIER_VERSION}", {}))
    if not fresh["frozen_verifier_matches_recorded"]:
        out.append(Finding(
            "BASELINE_CHANGED_AFTER_FREEZE", P0, "frozen_verifier",
            "the live frozen SP0009 verifier hash does not match the recorded "
            "committed baseline: the verifier was modified after freeze "
            "(D-0010-23)",
            {"recorded": RECORDED_FROZEN_SP0009_VERIFIER_HASH,
             "live": fresh["frozen_sp0009_verifier_hash"]}))
    return out
