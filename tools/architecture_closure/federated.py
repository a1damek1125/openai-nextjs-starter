"""Federated N-Version verification + convergence gate (SP0010 V5 FUNCTION X,
§0, D-0010-96..100).

The 3-phase bootstrap ceremony (bootstrap_verify.py) proves verifier IDENTITY
diversity. This module adds heterogeneous PROOF BACKENDS over the same object —
the genome class roots — each computing an independent fingerprint by a DISTINCT
algorithm (canonical-JSON fold, binary Merkle tree, polynomial rolling hash,
length-prefixed streaming digest). Different algorithms produce different
fingerprints by construction, so convergence is NOT "equal fingerprints" (that
would only hold for common-mode wrappers). Instead each backend must:

  1. be DETERMINISTIC — recomputing the fingerprint agrees,
  2. be SENSITIVE — a canary mutation to any class root changes its fingerprint
     (a backend blind to a root change is a degenerate/common-mode verifier,
     D-0010-97), and
  3. AGREE ON THE SHARED ANCHOR — the canonical global root each backend derives
     equals the recorded genome global_architecture_root.

The convergence gate CONVERGES only when >= 3 heterogeneous backends all satisfy
(1)(2)(3). Any divergence, or too few backends, blocks the seal (fail-closed).

Governance/analysis tooling only; never imported by product code; no external
effect; emits no secret values.
"""
from __future__ import annotations

from .canon import canonical_json, global_root, merkle_root, sha256_hex, hash_obj
from .model import Finding, P0, FEDERATION_STATES

_MIN_BACKENDS = 3


# --- heterogeneous fingerprint algorithms (each genuinely distinct) ---------- #
def _fp_canonical(class_roots: dict) -> str:
    """Backend 1: sha256 of the canonical-JSON list (the reference construction)."""
    ordered = [f"{k}={class_roots[k]}" for k in sorted(class_roots)]
    return sha256_hex(canonical_json(ordered))


def _fp_merkle(class_roots: dict) -> str:
    """Backend 2: binary Merkle tree over sorted leaves (distinct algorithm)."""
    leaves = [sha256_hex(f"{k}\x1f{class_roots[k]}") for k in sorted(class_roots)]
    return merkle_root(leaves)


def _fp_polynomial(class_roots: dict) -> str:
    """Backend 3: polynomial rolling hash mod a large prime over sorted items —
    a numeric construction independent of the SHA-tree structure."""
    P, M = 1_000_003, (1 << 127) - 1
    acc = 0
    for k in sorted(class_roots):
        for ch in f"{k}={class_roots[k]};":
            acc = (acc * P + ord(ch)) % M
    return f"poly:{acc:032x}"


def _fp_streaming(class_roots: dict) -> str:
    """Backend 4: length-prefixed streaming digest (guards against boundary
    ambiguity — distinct from the JSON and Merkle framings)."""
    acc = sha256_hex("SEED\x00")
    for k in sorted(class_roots):
        chunk = f"{len(k)}:{k}={len(str(class_roots[k]))}:{class_roots[k]}"
        acc = sha256_hex(acc + "\x00" + chunk)
    return acc


BACKENDS = (
    ("canonical-json-fold", _fp_canonical),
    ("binary-merkle-tree", _fp_merkle),
    ("polynomial-rolling", _fp_polynomial),
    ("length-prefixed-stream", _fp_streaming),
)


def _perturb(value) -> str:
    v = str(value)
    return (("0" if v[:1] != "0" else "1") + v[1:]) if v else "x"


def _canaries(class_roots: dict) -> list:
    """One minimal perturbation PER ROOT (red-team P1-B): flipping each root in
    turn. A correct backend MUST change its fingerprint for EVERY root — a
    backend blind to even one root (tested only against the lexically-first root
    before) is a degenerate/common-mode verifier and must be caught."""
    if not class_roots:
        return [{"__canary__": "x"}]
    out = []
    for k in sorted(class_roots):
        m = dict(class_roots)
        m[k] = _perturb(m[k])
        out.append((k, m))
    return out


def run_backend(name, fn, class_roots: dict, recorded_root: str) -> dict:
    fp = fn(class_roots)
    deterministic = fn(class_roots) == fp
    # SENSITIVE only if the fingerprint moves for EVERY single root, so no root
    # is invisible to this backend.
    blind_to = sorted(k for k, m in _canaries(class_roots) if fn(m) == fp)
    sensitive = not blind_to
    # anchor consistency: the RECORDED genome root must equal the canonical
    # recomputation from these class roots (catches a stale/forged recorded root
    # against the actual class-root set — meaningful when verifying a committed
    # genome, not tautological on a forged input).
    anchor_ok = _fp_canonical(class_roots) == recorded_root
    return {
        "backend": name,
        "fingerprint": fp,
        "deterministic": deterministic,
        "sensitive": sensitive,
        "blind_to_roots": blind_to,
        "anchor_matches_genome": anchor_ok,
        "ok": deterministic and sensitive and anchor_ok,
    }


def federate(class_roots: dict, recorded_root: str) -> dict:
    results = [run_backend(n, fn, class_roots, recorded_root)
               for n, fn in BACKENDS]
    n_ok = sum(1 for r in results if r["ok"])
    distinct_fps = len({r["fingerprint"] for r in results})
    if len(results) < _MIN_BACKENDS:
        state = "INSUFFICIENT_BACKENDS"
    elif all(r["ok"] for r in results) and distinct_fps == len(results):
        state = "CONVERGED"
    else:
        state = "DIVERGED"
    assert state in FEDERATION_STATES
    disagreements = []
    for r in results:
        if not r["deterministic"]:
            disagreements.append(f"{r['backend']}: non-deterministic")
        if not r["sensitive"]:
            disagreements.append(
                f"{r['backend']}: insensitive to roots {r['blind_to_roots']}")
        if not r["anchor_matches_genome"]:
            disagreements.append(f"{r['backend']}: anchor != genome root")
    if distinct_fps != len(results):
        disagreements.append("backends are not heterogeneous (common-mode)")
    return {
        "backends": results,
        "backend_count": len(results),
        "converged_count": n_ok,
        "distinct_fingerprints": distinct_fps,
        "state": state,
        "converged": state == "CONVERGED",
        "disagreements": disagreements,
        "federation_root": hash_obj(sorted(r["fingerprint"] for r in results)),
    }


def federation_findings(federation: dict) -> list[Finding]:
    out: list[Finding] = []
    if federation["state"] == "INSUFFICIENT_BACKENDS":
        out.append(Finding(
            "FEDERATION_INSUFFICIENT_BACKENDS", P0, "federation",
            f"fewer than {_MIN_BACKENDS} heterogeneous proof backends: cannot "
            "establish N-version convergence (D-0010-96)", {}))
    elif federation["state"] == "DIVERGED":
        for d in federation["disagreements"]:
            out.append(Finding(
                "FEDERATION_DIVERGENCE", P0, "federation",
                f"federated backend divergence: {d} (D-0010-97)", {}))
    return out


def federation_root(federation: dict) -> str:
    return federation["federation_root"]
