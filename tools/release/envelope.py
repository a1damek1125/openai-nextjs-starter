"""Release Proof Envelope (SP0009 §10.17, AC-0009-235..237).

The sealed, deterministic digest of an entire release verification: candidate
genome, impact cone, gate registry + result ledger, DoD closure, test
selection + execution ledger (INCLUDING failures — a proof that omits the
failure ledger is tampering), flake clusters, mutation adequacy, build
manifests, artifact closure, provenance, trust roots, transparency receipts,
SBOM/AI-BOM/VEX, AI closure, waivers, rollback and defeaters. Structural
allowlist + mandatory non_authoritative marker + fail-closed content digest
(house style: SP0007 E7 / SP0008 hardening). The envelope creates NO deployment
authority (D-0009-64).
"""
from __future__ import annotations

from .canon import core_hash, canonical_json
from .model import Finding, P0, P1

ENVELOPE_KIND = "finalis-release-proof-envelope-v1"

HASH_FIELDS = (
    "candidate_genome", "impact_cone_hash", "gate_registry_hash",
    "gate_result_ledger_hash", "dod_closure_hash", "test_selection_hash",
    "test_execution_ledger_hash", "flake_cluster_hash",
    "mutation_adequacy_hash", "build_manifest_hash", "artifact_closure_hash",
    "provenance_hash", "trust_root_hash", "transparency_receipt_hash",
    "sbom_hash", "ai_ml_bom_hash", "vex_hash", "ai_release_closure_hash",
    "waiver_hash", "rollback_hash", "defeater_hash",
)

ENVELOPE_KEYS = frozenset(HASH_FIELDS) | frozenset({
    "envelope_kind", "envelope_version", "validator_version",
    "non_authoritative", "content_digest",
})

VALIDATOR_VERSION = "sp0009-release-validator-1"


def release_envelope(hashes: dict) -> dict:
    """Build the envelope. Every hash field is REQUIRED — absence is recorded
    as the explicit string "ABSENT" and therefore part of the digest (an
    omitted failure ledger changes the proof, AC-0009-237)."""
    env = {"envelope_kind": ENVELOPE_KIND, "envelope_version": "1.0.0",
           "validator_version": VALIDATOR_VERSION,
           "non_authoritative": True}
    for f in HASH_FIELDS:
        env[f] = hashes.get(f) or "ABSENT"
    env["content_digest"] = core_hash(
        {k: env[k] for k in env if k != "content_digest"})
    return env


def validate_envelope(env: dict) -> list[Finding]:
    out: list[Finding] = []
    subject = str(env.get("envelope_kind") or "-")
    extra = set(env) - ENVELOPE_KEYS
    if extra:
        out.append(Finding(
            "RELEASE_PROOF_MISMATCH", P0, subject,
            f"envelope carries non-structural key(s) {sorted(extra)}: only "
            "the structural allowlist is permitted (no authority synonyms)",
            {"extra": sorted(extra)}))
    if env.get("envelope_kind") != ENVELOPE_KIND:
        out.append(Finding("RELEASE_PROOF_MISMATCH", P1, subject,
                           f"unexpected envelope kind "
                           f"{env.get('envelope_kind')!r}", {}))
    if env.get("non_authoritative") is not True:
        out.append(Finding(
            "RELEASE_PROOF_MISMATCH", P0, subject,
            "envelope must declare non_authoritative True: a release proof "
            "creates no deployment authority (D-0009-64)", {}))
    for f in HASH_FIELDS:
        # "ABSENT" is the sentinel release_envelope substitutes for an OMITTED
        # hash — it is truthy, so a plain `not env.get(f)` test would let an
        # omitted ledger through (red-team #3). Reject both empty and ABSENT.
        if not env.get(f) or env.get(f) == "ABSENT":
            out.append(Finding(
                "RELEASE_PROOF_MISMATCH", P0, subject,
                f"envelope missing required hash field {f}: a proof that "
                "omits a ledger (e.g. failures) is tampering (AC-0009-237)",
                {"missing": f}))
    recomputed = core_hash({k: env[k] for k in env if k != "content_digest"})
    if not env.get("content_digest"):
        out.append(Finding(
            "RELEASE_PROOF_MISMATCH", P0, subject,
            "envelope has no content_digest: unsealed (fail-closed)", {}))
    elif env["content_digest"] != recomputed:
        out.append(Finding(
            "RELEASE_PROOF_MISMATCH", P0, subject,
            "envelope content digest does not match its content: tampering",
            {"recorded": env.get("content_digest"),
             "recomputed": recomputed}))
    return out


def envelope_bytes(env: dict) -> str:
    return canonical_json(env)
