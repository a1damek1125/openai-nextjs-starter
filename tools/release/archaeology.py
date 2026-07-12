"""Repository release archaeology (SP0009 §2.1 item 2): the ACTUAL release-
relevant state of this repository, read deterministically from the tree.

Findings of absence are findings: this repo has NO CI workflow files, NO
lockfile beyond pyproject.toml, NO build backend and NO published artifact —
each absence is hashed explicitly into the candidate genome (absence is
identity, never silently equal to presence).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .canon import hash_obj, sha256_hex

ABSENT = "ABSENT"


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def ci_workflow_hash(root: Path) -> str:
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.exists():
        return ABSENT
    parts = []
    for p in sorted(wf_dir.rglob("*")):
        if p.is_file():
            parts.append((str(p.relative_to(root)), _file_hash(p)))
    return hash_obj(parts) if parts else ABSENT


def dependency_lock_hash(root: Path) -> str:
    candidates = ["pyproject.toml", "requirements.txt", "uv.lock",
                  "poetry.lock", "package-lock.json"]
    parts = []
    for name in candidates:
        p = root / name
        if p.exists():
            parts.append((name, _file_hash(p)))
    return hash_obj(parts) if parts else ABSENT


def toolchain_hash(root: Path) -> str:
    import sys
    return hash_obj({"python": sys.version.split()[0],
                     "implementation": sys.implementation.name})


def tree_digest(root: Path, rel_paths: list) -> str:
    """Deterministic digest over a set of tracked files: sorted
    (path, content-hash) pairs. This is the repository's honest 'artifact'
    digest — releases here are source trees, not built binaries."""
    parts = []
    for rel in sorted(set(rel_paths)):
        p = root / rel
        if p.is_file():
            parts.append((rel, _file_hash(p)))
    return sha256_hex(hash_obj(parts))


def release_archaeology(root: Path) -> dict:
    """The full archaeology record."""
    contract_genome = ABSENT
    gpath = root / "docs" / "contracts_inventory" / \
        "FINALIS_CONTRACT_GENOME.json"
    if gpath.exists():
        contract_genome = json.load(open(gpath, encoding="utf-8")).get(
            "global_root", ABSENT)
    compat_claims = ABSENT
    cpath = root / "docs" / "compatibility" / \
        "FINALIS_COMPATIBILITY_CLAIMS.json"
    if cpath.exists():
        compat_claims = hash_obj(json.load(open(cpath, encoding="utf-8")))
    test_files = sorted(p.name for p in (root / "tests").glob("test_*.py"))
    rec = {
        "ci_workflow_hash": ci_workflow_hash(root),
        "ci_workflows_present": (root / ".github" / "workflows").exists(),
        "dependency_lock_hash": dependency_lock_hash(root),
        "lockfile_pins_exact_versions": False,   # pyproject declares no pins
        "build_backend_declared": False,          # no [build-system] table
        "toolchain_hash": toolchain_hash(root),
        "contract_genome_root": contract_genome,
        "compatibility_claims_hash": compat_claims,
        "test_file_count": len(test_files),
        "browser_e2e_present": "test_browser_e2e.py" in test_files,
        "known_flakes": [
            {"test_id": "test_browser_e2e.py::"
                        "test_evidence_prompt_injection_flow_in_browser",
             "documented_in": [
                 "docs/compatibility/FINALIS_SWARM_REVIEW.md",
                 "docs/contracts_inventory/FINALIS_SWARM_REVIEW.md"],
             "mechanism": "module-scoped shared server+page fixtures, fixed "
                          "port 8765, stale-text waits under parallel load",
             "passes_in_isolation": True}],
        "published_artifacts": [],                # none exist
        "release_mechanism_today": "full pytest suite in 4 file shards with "
                                   "tests/test_browser_e2e.py excluded, plus "
                                   "per-mission P0=0/P1=0 validators",
    }
    rec["archaeology_hash"] = hash_obj(rec)
    return rec
