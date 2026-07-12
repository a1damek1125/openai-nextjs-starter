"""Evaluation baseline freeze (SP0011 §2.1, §4, AC-0011-011..020, D-0011-107).

Records the exact repository snapshot the evaluation operates over: branch/HEAD,
migration frontier, predecessor SP commits, the admitted SP0010 roots, and the
frozen evaluation baseline root. Any material change after freeze invalidates the
evaluation candidate (a divergent fresh freeze raises BASELINE_CHANGED). Git SHAs
are recorded facts of the ceremony; everything else is derived deterministically
from the tree.
"""
from __future__ import annotations

import ast
from pathlib import Path

from .canon import hash_obj
from .model import Finding, P0
from .admit import admit_program_seal

BRANCH = "claude/finalis-ai-casewoker-blueprint-f1huse"
FRONTIER_VERSION = 27
STARTING_HEAD = "3a5ee8b"

PREDECESSOR_COMMITS = {
    "SP0000": "e1b6b5c", "SP0001": "19413f2", "SP0002": "3eacdb0",
    "SP0003": "1ffb4e4", "SP0004": "e82ca87", "SP0005": "610e1e3",
    "SP0006": "d6ac046", "SP0007": "4eda536", "SP0008": "bb80912",
    "SP0009": "1e29581", "SP0010": "3a5ee8b",
}

# committed twin/genome roots that anchor the evaluated configuration identity
CONFIG_ROOT_SOURCES = {
    "contract_genome": ("docs/contracts_inventory/FINALIS_CONTRACT_GENOME.json",
                        "global_root"),
    "release_assurance": ("docs/release/FINALIS_RELEASE_TWIN.json",
                          "twin_digest"),
    "architecture_genome": ("docs/architecture_closure/"
                            "FINALIS_ARCHITECTURE_GENOME.json",
                            "global_architecture_root"),
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


def _config_roots(root: Path) -> dict:
    import json
    out = {}
    for name, (rel, key) in sorted(CONFIG_ROOT_SOURCES.items()):
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
    root = Path(root)
    adm = admit_program_seal(root)
    rec = {
        "branch": BRANCH,
        "starting_head": STARTING_HEAD,
        "predecessor_commits": PREDECESSOR_COMMITS,
        "migration_frontier": _migration_frontier(root),
        "config_roots": _config_roots(root),
        "sp0010_program_seal": adm["program_seal_hash"],
        "sp0010_architecture_genome_root": adm["architecture_genome_root"],
        "sp0010_tcb_root": adm["tcb_root"],
        "sp0010_admission_state": adm["admission_state"],
        "known_environment_instability": "browser E2E is environment-sensitive; "
        "excluded from the deterministic suite by convention",
        "sbom_state": "no lockfile/CI/build backend; recorded as visible gap",
    }
    rec["evaluation_baseline_root"] = hash_obj(rec)
    return rec


def check_frozen(recorded: dict, root: Path) -> list[Finding]:
    out: list[Finding] = []
    fresh = freeze(root)
    if fresh["evaluation_baseline_root"] != recorded.get(
            "evaluation_baseline_root"):
        out.append(Finding(
            "BASELINE_CHANGED", P0, "baseline",
            "evaluation baseline changed after freeze: candidate invalidated",
            {"recorded": recorded.get("evaluation_baseline_root"),
             "fresh": fresh["evaluation_baseline_root"]}))
    if fresh["migration_frontier"] != FRONTIER_VERSION:
        out.append(Finding(
            "BASELINE_CHANGED", P0, "migration_frontier",
            f"migration frontier is v{fresh['migration_frontier']}, expected "
            f"v{FRONTIER_VERSION}", {}))
    return out
