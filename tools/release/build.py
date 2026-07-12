"""Build manifests, hermeticity, reproducibility and diverse-builder quorum
(SP0009 §10.8, §11.12/11.13, §12.7, D-0009-24/25/26/27, AC-0009-121..134).

Build inputs are CLOSED: every material input (source, dependencies, toolchain,
environment variables, network endpoints, time sources) must be declared in the
manifest; any observed-but-undeclared input fails hermeticity (D-0009-24).
Reproducibility is byte-equality by default — a normalized equivalence relation
is admissible only when explicitly declared (D-0009-27). "Reproduced once" is
not "reproducibly built": the record keeps counts. Diverse-builder quorum
requires DISTINCT builder identities in DISTINCT trust domains producing
equivalent bytes — N builders in one trust domain (or one compromised
environment) are one witness, not N (D-0009-26).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, P1


def build_manifest(*, candidate_genome: str, source_commit: str,
                   builder_identity: str, builder_trust_domain: str,
                   builder_version: str, toolchain: list,
                   dependency_lock_hash: str, environment_inputs: dict,
                   declared_network_access: list, declared_time_inputs: list,
                   commands: list) -> dict:
    m = {
        "candidate_genome": candidate_genome,
        "source_commit": source_commit,
        "builder_identity": builder_identity,
        "builder_trust_domain": builder_trust_domain,
        "builder_version": builder_version,
        "toolchain": list(toolchain),
        "dependency_lock_hash": dependency_lock_hash,
        "environment_inputs": dict(environment_inputs),
        "declared_network_access": sorted(declared_network_access),
        "declared_time_inputs": sorted(declared_time_inputs),
        "commands": list(commands),
    }
    m["build_id"] = "BM-" + hash_obj(m)[:20]
    m["input_hash"] = hash_obj({k: m[k] for k in (
        "source_commit", "toolchain", "dependency_lock_hash",
        "environment_inputs", "commands")})
    return m


def hermeticity_findings(manifest: dict, observed: dict) -> list[Finding]:
    """Compare DECLARED inputs against OBSERVED build behavior. Any observed
    network endpoint, environment variable or time read that was not declared
    fails hermeticity (D-0009-24, AC-0009-127/128). Fail-closed: observation
    wins over declaration."""
    out: list[Finding] = []
    subject = str(manifest.get("build_id") or "-")
    declared_net = set(manifest.get("declared_network_access") or [])
    for ep in sorted(set(observed.get("network_access") or [])):
        if ep not in declared_net:
            out.append(Finding(
                "BUILD_INPUT_UNDECLARED", P0, subject,
                f"build accessed undeclared network endpoint {ep!r}: "
                "hermeticity failed (D-0009-24)", {"endpoint": ep}))
    declared_env = set((manifest.get("environment_inputs") or {}).keys())
    for var in sorted(set(observed.get("environment_reads") or [])):
        if var not in declared_env:
            out.append(Finding(
                "BUILD_INPUT_UNDECLARED", P1, subject,
                f"build read undeclared environment variable {var!r}",
                {"variable": var}))
    declared_time = set(manifest.get("declared_time_inputs") or [])
    for t in sorted(set(observed.get("time_reads") or [])):
        if t not in declared_time:
            out.append(Finding(
                "BUILD_INPUT_UNDECLARED", P1, subject,
                f"build read undeclared time source {t!r}", {"source": t}))
    return out


# --- reproducibility (§11.12, §12.7, D-0009-27) --------------------------------------
def reproducibility(build_a: dict, build_b: dict, *,
                    equivalence: dict | None = None) -> dict:
    """Compare two builds of the SAME inputs. Byte (digest) equality by
    default; a declared normalization relation must name exactly which
    differences it forgives — an undeclared difference always fails."""
    same_inputs = build_a.get("input_hash") == build_b.get("input_hash")
    da, db = build_a.get("artifact_digest"), build_b.get("artifact_digest")
    byte_equal = bool(da) and da == db
    normalized_equal = False
    relation = None
    if not byte_equal and equivalence is not None:
        relation = equivalence.get("relation_id")
        norm_a = equivalence.get("normalized_digest_a")
        norm_b = equivalence.get("normalized_digest_b")
        normalized_equal = bool(relation) and bool(norm_a) \
            and norm_a == norm_b
    return {
        "same_inputs": same_inputs,
        "byte_equal": byte_equal,
        "normalized_equal": normalized_equal,
        "equivalence_relation": relation,
        "reproducible": same_inputs and (byte_equal or normalized_equal),
        "note": "one successful reproduction is evidence, not a standing "
                "REPRODUCIBLE property (D-0009-65)",
    }


def reproducibility_findings(result: dict, subject: str) -> list[Finding]:
    out: list[Finding] = []
    if result["same_inputs"] and not result["reproducible"]:
        out.append(Finding(
            "BUILD_NOT_REPRODUCIBLE", P1, subject,
            "identical declared inputs produced non-equivalent artifacts "
            "(no declared normalization covers the difference)", {}))
    return out


# --- diverse-builder quorum (§11.13, D-0009-26) --------------------------------------
def builder_quorum(builds: list, *, min_builders: int = 2,
                   min_trust_domains: int = 2,
                   revoked_builders: set | None = None) -> dict:
    """Quorum over independent rebuilds. Counts only DISTINCT builder
    identities; trust-domain diversity counts DISTINCT domains; equivalence of
    artifact digests is required across every counted build. Builders sharing
    a trust domain collapse to that domain's count (fake diversity rejected,
    AC-0009-134)."""
    revoked = revoked_builders or set()
    valid = [b for b in builds
             if b.get("builder_identity")
             and b["builder_identity"] not in revoked]
    identities = {b["builder_identity"] for b in valid}
    domains = {b.get("builder_trust_domain") for b in valid
               if b.get("builder_trust_domain")}
    digests = {b.get("artifact_digest") for b in valid}
    equivalent = len(digests) == 1 and None not in digests and len(valid) > 0
    ok = (len(identities) >= min_builders
          and len(domains) >= min_trust_domains
          and equivalent)
    return {
        "builders": sorted(identities),
        "trust_domains": sorted(domains),
        "distinct_builders": len(identities),
        "distinct_trust_domains": len(domains),
        "artifact_equivalent": equivalent,
        "revoked_excluded": sorted(revoked & {b.get("builder_identity")
                                              for b in builds}),
        "quorum": ok,
    }


def quorum_findings(q: dict, subject: str) -> list[Finding]:
    out: list[Finding] = []
    if not q["quorum"]:
        reason = []
        if q["distinct_builders"] < 2:
            reason.append("insufficient distinct builders")
        if q["distinct_trust_domains"] < 2:
            reason.append("insufficient trust-domain diversity (builders in "
                          "one domain are one witness, D-0009-26)")
        if not q["artifact_equivalent"]:
            reason.append("artifacts not equivalent")
        out.append(Finding(
            "BUILDER_DIVERSITY_INSUFFICIENT", P1, subject,
            "diverse-builder quorum failed: " + "; ".join(reason), q))
    return out
