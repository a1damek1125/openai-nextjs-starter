"""Inventory proof envelopes (SP0008 §envelope, D-0008-42/44).

An envelope is a sealed, verifiable summary of an inventory run: the genome roots,
the surface/finding counts, and a content digest — enough for a downstream
verifier to pin this inventory and detect drift, with NOTHING that grants
authority. The validator uses a STRUCTURAL ALLOWLIST (the SP0007 E7 lesson): only
the known structural keys are permitted; any extra key — especially an
authority-flavoured synonym like "mandate"/"ratifies"/"empowers" — is rejected as
a mismatch. Allowlist + fail-closed, never a blacklist.
"""
from __future__ import annotations

from .canon import core_hash, canonical_json
from .model import Finding, P0, P1, PROOF_ENVELOPE_MISMATCH

# the ONLY keys an inventory proof envelope may carry (structural allowlist)
ENVELOPE_KEYS = frozenset({
    "envelope_kind", "inventory_version", "global_root", "class_roots",
    "surface_count", "finding_counts", "detector_names", "content_digest",
    "non_authoritative",
})

ENVELOPE_KIND = "finalis-contract-inventory-envelope-v1"


def inventory_envelope(*, inventory_version, genome, surface_count,
                       finding_counts, detector_names) -> dict:
    env = {
        "envelope_kind": ENVELOPE_KIND,
        "inventory_version": inventory_version,
        "global_root": genome["global_root"],
        "class_roots": genome["class_roots"],
        "surface_count": surface_count,
        "finding_counts": finding_counts,
        "detector_names": sorted(detector_names),
        "non_authoritative": True,
    }
    env["content_digest"] = core_hash(env)
    return env


def validate_envelope(env: dict) -> list[Finding]:
    """Structural allowlist validation, fail-closed (SP0007 E7)."""
    out: list[Finding] = []
    subject = str(env.get("envelope_kind") or "-")
    extra = set(env) - ENVELOPE_KEYS - {"content_digest"}
    if extra:
        out.append(Finding(
            PROOF_ENVELOPE_MISMATCH, P0, subject,
            f"envelope carries non-structural key(s) {sorted(extra)}; only the "
            "structural allowlist is permitted (no authority synonyms)",
            {"extra_keys": sorted(extra)}))
    if env.get("envelope_kind") != ENVELOPE_KIND:
        out.append(Finding(PROOF_ENVELOPE_MISMATCH, P1, subject,
                          f"unexpected envelope_kind {env.get('envelope_kind')!r}",
                          {}))
    if env.get("non_authoritative") is not True:
        out.append(Finding(
            PROOF_ENVELOPE_MISMATCH, P0, subject,
            "envelope must declare non_authoritative is True; an inventory "
            "envelope grants no authority", {}))
    # content digest must be PRESENT and verify — a missing/empty digest is an
    # unsealed envelope, not a pass (red-team P1: no fail-open on absence)
    recomputed = core_hash({k: env[k] for k in env if k != "content_digest"})
    if not env.get("content_digest"):
        out.append(Finding(
            PROOF_ENVELOPE_MISMATCH, P0, subject,
            "envelope has no content_digest: it is unsealed and cannot be "
            "accepted (fail-closed)", {"recomputed": recomputed}))
    elif env["content_digest"] != recomputed:
        out.append(Finding(
            PROOF_ENVELOPE_MISMATCH, P0, subject,
            "envelope content_digest does not match its content",
            {"recorded": env.get("content_digest"), "recomputed": recomputed}))
    return out


def envelope_bytes(env: dict) -> str:
    return canonical_json(env)
