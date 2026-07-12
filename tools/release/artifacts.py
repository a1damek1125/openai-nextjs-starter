"""Artifact manifests, sealing, substitution detection and Artifact Closure
(SP0009 FUNCTION G, §10.9/10.10, §11.17, §12.8/12.10, D-0009-25/28).

Build once, verify the exact artifact, promote the same bytes: the digest that
was verified must equal the digest that would be promoted — any difference is
substitution (INV-0009-17). A sealed artifact is immutable: any post-seal
mutation is detected by its recorded seal hash. Artifact Closure is the closed
evidence graph around a protected artifact — SBOM, AI/ML-BOM (when AI-bearing),
VEX, vulnerability evidence, attestations, trust roots, transparency receipts,
verification summary — every claim bound to the artifact's subject digest.
An artifact with a signature but no closure is NOT complete (SIGNED != TRUSTED).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, P1


def artifact_manifest(*, candidate_genome: str, artifact_type: str,
                      digest: str, size_bytes: int, build_ref: str) -> dict:
    if not digest:
        raise ValueError("artifact digest is required (AC-0009-136)")
    m = {
        "candidate_genome": candidate_genome,
        "artifact_type": artifact_type,
        "digest_algorithm": "sha256",
        "digest": digest,
        "size_bytes": size_bytes,
        "build_ref": build_ref,
        "sealed": False,
    }
    m["artifact_id"] = "AR-" + hash_obj(m)[:20]
    return m


def seal(manifest: dict) -> dict:
    after = dict(manifest)
    after["sealed"] = True
    after["seal_hash"] = hash_obj(
        {k: after[k] for k in ("artifact_id", "candidate_genome", "digest",
                               "size_bytes", "build_ref")})
    return after


def verify_seal(manifest: dict) -> list[Finding]:
    """A sealed artifact whose material fields no longer match the seal hash
    was mutated after sealing (INV-0009-18)."""
    out: list[Finding] = []
    if manifest.get("sealed") is not True:
        return out
    fresh = hash_obj({k: manifest.get(k) for k in
                      ("artifact_id", "candidate_genome", "digest",
                       "size_bytes", "build_ref")})
    if fresh != manifest.get("seal_hash"):
        out.append(Finding(
            "ARTIFACT_SEALED_MUTATION", P0, str(manifest.get("artifact_id")),
            "sealed artifact fields no longer match the seal hash: sealed "
            "artifacts are immutable", {"recomputed": fresh,
                                        "recorded": manifest.get("seal_hash")}))
    return out


def promote_same_bytes(verified_digest: str, promotable_digest: str,
                       subject: str) -> list[Finding]:
    """§12.8: Digest(VerifiedArtifact) == Digest(PromotableArtifact). Strict
    string equality of non-empty digests — an empty/missing digest never
    matches anything (fail-closed)."""
    out: list[Finding] = []
    if not verified_digest or not promotable_digest \
            or verified_digest != promotable_digest:
        out.append(Finding(
            "ARTIFACT_DIGEST_MISMATCH", P0, subject,
            "verified artifact digest does not equal the promotable digest: "
            "different bytes would be promoted than were verified "
            "(build once / promote same bytes, D-0009-25)",
            {"verified": verified_digest, "promotable": promotable_digest}))
    return out


def substitution_findings(expected: dict, presented: dict) -> list[Finding]:
    """Artifact substitution: a presented artifact whose digest differs from
    the manifest's recorded digest (AC-0009-142)."""
    out: list[Finding] = []
    if expected.get("digest") != presented.get("digest") \
            or not presented.get("digest"):
        out.append(Finding(
            "ARTIFACT_SUBSTITUTION", P0, str(expected.get("artifact_id")),
            "presented artifact digest differs from the sealed manifest "
            "digest: substitution detected",
            {"expected": expected.get("digest"),
             "presented": presented.get("digest")}))
    return out


# --- Artifact Closure (§11.17, §12.10, D-0009-28) ------------------------------------
# relationships a PROTECTED artifact requires; AI-bearing artifacts also
# require ai_ml_bom_refs.
REQUIRED_CLOSURE = ("sbom_refs", "attestation_refs", "trust_root_refs",
                    "verification_summary_refs")


def closure(*, artifact: dict, sbom_refs=(), ai_ml_bom_refs=(), vex_refs=(),
            vulnerability_refs=(), attestation_refs=(), trust_root_refs=(),
            transparency_receipt_refs=(), verification_summary_refs=(),
            ai_bearing: bool = False) -> dict:
    c = {
        "artifact_id": artifact["artifact_id"],
        "subject_digest": artifact["digest"],
        "required_relationships": list(REQUIRED_CLOSURE) + (
            ["ai_ml_bom_refs"] if ai_bearing else []),
        "sbom_refs": list(sbom_refs),
        "ai_ml_bom_refs": list(ai_ml_bom_refs),
        "vex_refs": list(vex_refs),
        "vulnerability_refs": list(vulnerability_refs),
        "attestation_refs": list(attestation_refs),
        "trust_root_refs": list(trust_root_refs),
        "transparency_receipt_refs": list(transparency_receipt_refs),
        "verification_summary_refs": list(verification_summary_refs),
    }
    missing = [r for r in c["required_relationships"] if not c.get(r)]
    c["closure_status"] = "COMPLETE" if not missing else "INCOMPLETE"
    c["missing"] = missing
    return c


def closure_findings(c: dict, *, protected: bool = True) -> list[Finding]:
    out: list[Finding] = []
    if c.get("closure_status") != "COMPLETE" and protected:
        out.append(Finding(
            "ARTIFACT_CLOSURE_INCOMPLETE", P0, str(c.get("artifact_id")),
            f"protected artifact closure incomplete: missing "
            f"{c.get('missing')}; a protected artifact cannot qualify without "
            "its full evidence graph (D-0009-28)", {"missing": c.get("missing")}))
    return out


def subject_bound_findings(c: dict, claims: list) -> list[Finding]:
    """Every closure claim must name the artifact's subject digest — a claim
    about different bytes is not a claim about this artifact."""
    out: list[Finding] = []
    for claim in claims:
        if claim.get("subject_digest") != c.get("subject_digest"):
            out.append(Finding(
                "SBOM_SUBJECT_MISMATCH" if claim.get("kind") == "SBOM"
                else "PROVENANCE_SUBJECT_MISMATCH", P0,
                str(claim.get("ref") or "-"),
                "closure claim subject digest does not match the artifact "
                "(wrong-artifact evidence rejected)",
                {"claim_subject": claim.get("subject_digest"),
                 "artifact_subject": c.get("subject_digest")}))
    return out
