"""Trust-root lifecycle, threshold diversity, attestation verification and
provenance projections (SP0009 FUNCTION H/I, §10.11, §11.14/11.15, §12.9,
D-0009-29/30/31/32, AC-0009-146..170).

SIGNED != TRUSTED: a cryptographically valid signature passes only when its
signer is authorized by a CURRENT, non-revoked trust root of sufficient
version, within validity, under the required predicate, over the exact subject
digest. TUF-style protections: root version monotonicity (rollback detection),
expiry (freeze detection), revocation, rotation with supersession. Threshold
quorum counts DISTINCT authorized signers in DISTINCT trust domains — multiple
signatures from one root/domain are one witness, never a quorum (D-0009-32).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, P1

KNOWN_PREDICATES = ("https://slsa.dev/provenance/v1",
                    "https://in-toto.io/attestation/v1",
                    "finalis/release-evidence/v1")


def trust_root(*, trust_root_id: str, version: int, trust_domain: str,
               threshold: int, authorized_signers: list, valid_from: str,
               expires_at: str, revoked_at=None, supersedes=None) -> dict:
    return {"trust_root_id": trust_root_id, "version": version,
            "trust_domain": trust_domain, "threshold": threshold,
            "authorized_signers": sorted(authorized_signers),
            "valid_from": valid_from, "expires_at": expires_at,
            "revoked_at": revoked_at, "supersedes": supersedes,
            "status": "ACTIVE"}


def validate_root(root: dict, *, now: str,
                  known_versions: dict | None = None) -> list[Finding]:
    """Root lifecycle validation (§11.14): expiry (freeze protection),
    revocation, version monotonicity (rollback protection)."""
    out: list[Finding] = []
    subject = str(root.get("trust_root_id") or "-")
    # lifecycle status is an allowlist: only an ACTIVE root authorizes anything.
    # SUPERSEDED / ROTATING / EXPIRED / REVOKED (status-only, even without a
    # revoked_at timestamp) never pass — missing-status is not permissive
    # (red-team #6).
    if root.get("status") != "ACTIVE":
        out.append(Finding(
            "TRUST_ROOT_INVALID", P0, subject,
            f"trust root status is {root.get('status')!r}, not ACTIVE: only an "
            "ACTIVE root may authorize signers (rotated/superseded/expired/"
            "revoked roots never pass)", {"status": root.get("status")}))
    if root.get("revoked_at") is not None:
        out.append(Finding("TRUST_ROOT_REVOKED", P0, subject,
                           "trust root is revoked", {}))
    exp = root.get("expires_at")
    if not exp:
        out.append(Finding("TRUST_ROOT_INVALID", P1, subject,
                           "trust root has no expiry (freeze protection "
                           "requires expiring metadata, D-0009-31)", {}))
    elif str(exp) <= str(now):
        out.append(Finding(
            "TRUST_ROOT_EXPIRED", P0, subject,
            "trust root metadata expired: expired metadata cannot authorize "
            "anything (freeze attack protection)", {"expires_at": exp}))
    ver = root.get("version")
    if not isinstance(ver, int) or ver < 1:
        out.append(Finding("TRUST_ROOT_INVALID", P1, subject,
                           f"root version must be a positive int, got {ver!r}",
                           {}))
    highest = (known_versions or {}).get(subject)
    if highest is not None and isinstance(ver, int) and ver < highest:
        out.append(Finding(
            "TRUST_ROOT_ROLLBACK_DETECTED", P0, subject,
            f"presented root version {ver} is OLDER than the highest "
            f"previously seen version {highest}: rollback attack — older "
            "trusted metadata can never replace newer (D-0009-31)",
            {"presented": ver, "highest_seen": highest}))
    if root.get("threshold", 0) < 1:
        out.append(Finding("TRUST_ROOT_INVALID", P1, subject,
                           "threshold must be >= 1", {}))
    return out


def threshold_quorum(signatures: list, roots: list, *, now: str,
                     min_trust_domains: int = 1,
                     known_versions: dict | None = None) -> dict:
    """§12.9: ValidThreshold = distinct authorized valid signers >= threshold,
    subject to trust-domain diversity. Duplicate signer identities collapse;
    signers not authorized by a CURRENT valid root do not count; domains
    collapse to distinct count."""
    valid_roots = []
    for r in roots:
        if not validate_root(r, now=now, known_versions=known_versions):
            valid_roots.append(r)
    counted: dict = {}          # signer -> trust_domain
    for sig in signatures:
        signer = sig.get("signer")
        if not signer or signer in counted:
            continue            # duplicates collapse (INV-0009-25)
        for r in valid_roots:
            if signer in r["authorized_signers"]:
                counted[signer] = r["trust_domain"]
                break
    required = max((r["threshold"] for r in valid_roots), default=1)
    domains = set(counted.values())
    ok = len(counted) >= required and len(domains) >= min_trust_domains
    return {"counted_signers": sorted(counted),
            "distinct_domains": sorted(domains),
            "required_threshold": required,
            "min_trust_domains": min_trust_domains,
            "quorum": ok}


def quorum_findings(q: dict, subject: str) -> list[Finding]:
    out: list[Finding] = []
    if not q["quorum"]:
        out.append(Finding(
            "TRUST_THRESHOLD_NOT_MET", P0, subject,
            f"signature quorum failed: {len(q['counted_signers'])} distinct "
            f"authorized signer(s) across {len(q['distinct_domains'])} trust "
            f"domain(s); required threshold {q['required_threshold']} with "
            f">= {q['min_trust_domains']} domain(s). Multiple signatures from "
            "one root are one witness (D-0009-32)", q))
    return out


# --- attestation verification (§11.15, D-0009-29) ------------------------------------
def attestation(*, subject_digest: str, predicate_type: str, predicate: dict,
                signer: str, signing_time: str, candidate_genome: str) -> dict:
    a = {"subject_digest": subject_digest, "predicate_type": predicate_type,
         "predicate": predicate, "signer": signer,
         "signing_time": signing_time, "candidate_genome": candidate_genome}
    a["attestation_id"] = "AT-" + hash_obj(a)[:20]
    return a


def verify_attestation(att: dict, *, artifact_digest: str,
                       candidate_genome: str, roots: list, now: str,
                       protected: bool = True,
                       known_versions: dict | None = None) -> list[Finding]:
    """The nine-step check (§11.15): subject, predicate, signer authorization
    via a current root, time validity, candidate binding. Signature alone can
    never pass (AC-0009-152)."""
    out: list[Finding] = []
    subject = str(att.get("attestation_id") or "-")
    if att.get("subject_digest") != artifact_digest:
        out.append(Finding(
            "PROVENANCE_SUBJECT_MISMATCH", P0, subject,
            "attestation subject digest does not match the artifact: this "
            "attestation is about different bytes",
            {"attested": att.get("subject_digest"),
             "artifact": artifact_digest}))
    pt = att.get("predicate_type")
    if pt not in KNOWN_PREDICATES:
        sev = P0 if protected else P1
        out.append(Finding(
            "UNKNOWN_PREDICATE_REJECTED", sev, subject,
            f"unknown predicate type {pt!r}: protected artifacts fail closed "
            "on unrecognized predicates (INV-0009-21)", {"predicate_type": pt}))
    if att.get("candidate_genome") != candidate_genome:
        out.append(Finding(
            "ATTESTATION_INVALID", P0, subject,
            "attestation bound to a different candidate genome", {}))
    # signer must be authorized by a current valid root
    signer = att.get("signer")
    authorized = False
    for r in roots:
        if validate_root(r, now=now, known_versions=known_versions):
            continue
        if signer in r.get("authorized_signers", []):
            authorized = True
            break
    if not authorized:
        out.append(Finding(
            "ATTESTATION_INVALID", P0, subject,
            f"signer {signer!r} is not authorized by any CURRENT valid trust "
            "root: a valid signature from an untrusted/expired root cannot "
            "pass (FUNCTION H)", {"signer": signer}))
    return out


# --- provenance projections (AC-0009-169/170) -----------------------------------------
def slsa_projection(build_manifest: dict, artifact: dict) -> dict:
    """SLSA v1-style provenance projection (predicate only; no level claim —
    D-0009-65)."""
    return {
        "predicate_type": "https://slsa.dev/provenance/v1",
        "subject": [{"digest": {"sha256": artifact["digest"]}}],
        "predicate": {
            "buildDefinition": {
                "externalParameters": {
                    "source_commit": build_manifest["source_commit"]},
                "resolvedDependencies": [
                    {"digest": {"sha256":
                                build_manifest["dependency_lock_hash"]}}],
            },
            "runDetails": {
                "builder": {"id": build_manifest["builder_identity"]},
            },
        },
        "note": "projection only; no SLSA level is claimed (D-0009-65)",
    }


def in_toto_projection(att: dict) -> dict:
    """in-toto Attestation Framework v1 statement projection."""
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"digest": {"sha256": att["subject_digest"]}}],
        "predicateType": att["predicate_type"],
        "predicate": att["predicate"],
    }
