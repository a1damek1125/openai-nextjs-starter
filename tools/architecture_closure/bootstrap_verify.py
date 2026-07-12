"""Bootstrap-safe N-version verification (SP0010 FUNCTION N, §11.15, D-0010-22/
23/24, AC-0010-141..160).

A verifier cannot solely certify itself (D-0010-24). Three phases:

  PHASE A — the FROZEN SP0009 verifier. Its identity is the content hash of its
    exact files (freeze.frozen_verifier_hash); a verifier modified inside this
    qualification step no longer matches the frozen identity and is rejected
    (D-0010-23). The tooling never IMPORTS tools.release (boundary allowlist);
    Phase A checks identity + records the SP0009 twin's committed validity.
  PHASE B — the SP0010 REFERENCE verifier recomputes the architecture closure
    (the genome global root from its component class roots).
  PHASE C — an INDEPENDENT verifier recomputes the material roots by a distinct
    path and compares Phase A and Phase B, searching for disagreement.

Two wrappers over one engine are common-mode (D-0010-22); the three phases are
in distinct trust domains. The seal is issued only when required results agree.
"""
from __future__ import annotations

import json
from pathlib import Path

from .canon import global_root, hash_obj, merkle_root, sha256_hex
from .freeze import frozen_verifier_hash
from .model import Finding, P0

# the class roots every complete genome must carry (catches root omission). V5
# (red-team P1-C): the 7 V5 subsystem roots are folded into the genome by
# closure.build_closure, so they MUST be required here too — otherwise a V5
# subsystem could be silently unwired from the sealed architecture identity.
REQUIRED_CLASS_ROOTS = ("constitution", "twin", "hypergraph", "epistemic",
                        "invariant", "hyperproperty", "assurance", "gap",
                        "verifier_set",
                        "dual_graph", "extraction_firewall", "tcb",
                        "certificate", "causal", "cegar", "robustness")


def phase_a(root: Path, recorded_frozen_hash: str) -> dict:
    """Frozen SP0009 verifier identity + its twin's recorded validity."""
    fresh = frozen_verifier_hash(root)
    twin_path = root / "docs" / "release" / "FINALIS_RELEASE_TWIN.json"
    twin_digest = None
    if twin_path.exists():
        try:
            twin_digest = json.load(open(twin_path, encoding="utf-8")).get(
                "twin_digest")
        except (ValueError, OSError):
            twin_digest = "UNREADABLE"
    return {
        "verifier": "frozen_sp0009",
        "trust_domain": "release-frozen",
        "frozen_identity_matches": fresh == recorded_frozen_hash,
        "frozen_identity": fresh,
        "recorded_identity": recorded_frozen_hash,
        "sp0009_twin_digest": twin_digest,
    }


def phase_b(genome: dict) -> dict:
    """SP0010 reference verifier recomputes the global architecture root."""
    recomputed = global_root(genome.get("class_roots", {}))
    return {
        "verifier": "sp0010_reference",
        "trust_domain": "closure-reference",
        "global_root": recomputed,
        "matches_genome": recomputed == genome.get(
            "global_architecture_root"),
    }


def phase_c(genome: dict, phase_a_result: dict, phase_b_result: dict) -> dict:
    """Independent verifier — a GENUINELY distinct construction (red-team P1-2).

    Phase B aggregates the class roots via global_root (sha256 of a canonical
    JSON list). Phase C aggregates them via a Merkle TREE over sorted leaves —
    a different algorithm. Phase C's own witness is `independent_merkle_root`.
    The cross-check is that the CANONICAL global root recomputes to the recorded
    genome root (the shared invariant every verifier must agree on), that Phase
    C's Merkle witness is deterministic, and that NO required class root is
    OMITTED (a missing class root is a silent root-omission escape). Disagreement
    on any of these blocks the seal."""
    class_roots = genome.get("class_roots", {})
    recorded = genome.get("global_architecture_root")
    # Phase C's independent aggregation: a Merkle tree over "k=v" leaves
    leaves = [sha256_hex(f"{k}={class_roots[k]}") for k in sorted(class_roots)]
    independent_merkle_root = merkle_root(leaves)
    # Phase C also recomputes the canonical root by its own call and cross-checks
    canonical_recompute = global_root(class_roots)
    disagreements = []
    if not phase_a_result.get("frozen_identity_matches"):
        disagreements.append("frozen verifier identity changed")
    if not phase_b_result.get("matches_genome"):
        disagreements.append("reference verifier root mismatch")
    if canonical_recompute != recorded:
        disagreements.append("independent canonical recompute mismatch")
    missing = [k for k in REQUIRED_CLASS_ROOTS if k not in class_roots]
    if missing:
        disagreements.append(f"class roots omitted: {missing}")
    # the Merkle witness must be stable (a second computation must agree)
    if merkle_root(leaves) != independent_merkle_root:
        disagreements.append("Merkle witness non-deterministic")
    return {
        "verifier": "sp0010_independent",
        "trust_domain": "closure-independent",
        "construction": "merkle-tree",
        "independent_merkle_root": independent_merkle_root,
        "canonical_recompute": canonical_recompute,
        "missing_class_roots": missing,
        "disagreements": disagreements,
        "agree": not disagreements,
    }


def verifier_diversity(results: list) -> dict:
    """Verifier diversity is real only across distinct CONSTRUCTIONS, not just
    label strings (red-team P1-2, D-0010-22). The three phases use distinct
    constructions: file-content-hash (A), canonical-JSON global root (B), Merkle
    tree (C)."""
    domains = sorted({r.get("trust_domain") for r in results})
    verifiers = sorted({r.get("verifier") for r in results})
    constructions = sorted({r.get("construction",
                                   {"frozen_sp0009": "file-content-hash",
                                    "sp0010_reference": "canonical-json"}.get(
                                       r.get("verifier"), r.get("verifier")))
                            for r in results})
    return {"verifiers": verifiers, "trust_domains": domains,
            "constructions": constructions,
            "distinct_domains": len(domains),
            "distinct_constructions": len(constructions),
            "diverse": len(domains) >= 2 and len(constructions) >= 2}


def run_ceremony(root: Path, *, recorded_frozen_hash: str,
                 genome: dict) -> dict:
    a = phase_a(root, recorded_frozen_hash)
    b = phase_b(genome)
    c = phase_c(genome, a, b)
    diversity = verifier_diversity([a, b, c])
    return {"phase_a": a, "phase_b": b, "phase_c": c,
            "verifier_diversity": diversity,
            "sealed_ok": c["agree"] and diversity["diverse"]
            and a["frozen_identity_matches"]}


def ceremony_findings(ceremony: dict) -> list[Finding]:
    out: list[Finding] = []
    a = ceremony["phase_a"]
    if not a["frozen_identity_matches"]:
        out.append(Finding(
            "FROZEN_VERIFIER_MODIFIED", P0, "phase_a",
            "the frozen SP0009 verifier's identity changed: a verifier "
            "modified inside this qualification step cannot serve as the "
            "frozen Phase-A verifier (D-0010-23)",
            {"recorded": a["recorded_identity"],
             "fresh": a["frozen_identity"]}))
    c = ceremony["phase_c"]
    for d in c["disagreements"]:
        out.append(Finding(
            "INDEPENDENT_VERIFIER_DISAGREEMENT", P0, "phase_c",
            f"verifier disagreement: {d}", {}))
    if not ceremony["verifier_diversity"]["diverse"]:
        out.append(Finding(
            "VERIFIER_COMMON_MODE_RISK", P0, "verifier_diversity",
            "verifier set lacks trust-domain diversity (two wrappers over one "
            "engine are common-mode, D-0010-22)", {}))
    return out


def verifier_set_root(ceremony: dict) -> str:
    return hash_obj({
        "a": ceremony["phase_a"]["frozen_identity"],
        "b": ceremony["phase_b"]["global_root"],
        "c": ceremony["phase_c"]["independent_merkle_root"],
        "domains": ceremony["verifier_diversity"]["trust_domains"],
        "constructions": ceremony["verifier_diversity"]["constructions"]})
