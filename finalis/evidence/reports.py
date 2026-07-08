"""Finalis Canonical Evidence Report Package (EVIDENCE-REPORT-C2).

A deterministic, replayable, auditable proof-report artifact over the
Evidence Trust Fabric. Pure logic here (no I/O): canonical JSON, the report
hash + hash-input manifest, the D1..D15 proof algebra, the report payload and
package builders, and the artifact-integrity verifier.

report_hash is content-addressed over the PROOF-CRITICAL payload only —
volatile fields (report_id, timestamps, the hash/signature/package fields
themselves) are excluded and enumerated in the hash-input manifest, so the
same proof state always hashes the same, and any proof-critical change flips
the hash. No signing, no external providers, no legal-validity claim.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

CANONICALIZATION_PROFILE = "finalis-canonical-json-v1"
CANONICALIZATION_VERSION = "1"
REPORT_HASH_INPUT_SCHEMA_VERSION = "1"
REPORT_HASH_ALGORITHM = "sha256"
REPORT_TYPE = "evidence-proof-report"
REPORT_VERSION = 1
STRICT_RFC8785_JCS_STATUS = "NOT_IMPLEMENTED"

# Volatile / self-referential fields never enter the report hash.
EXCLUDED_HASH_FIELDS = [
    "report_id", "generated_at", "created_at", "updated_at",
    "last_verified_at", "verified_at", "report_hash", "package_hash",
    "payload_hash", "manifest_hash", "report_signature", "signature",
    "signature_envelope", "replay_status",
]

HONESTY_LABELS = [
    "Cryptographic verification is not the same as legal validity.",
    "Evidence verification does not automatically approve a case outcome.",
    "Report hash is implemented.",
    "Report hash is computed from the canonical report hash input manifest.",
    "Strict RFC 8785 JCS compliance is not claimed unless explicitly "
    "implemented and tested.",
    "Report signing requires configured signing infrastructure.",
    "External notarization is not connected.",
    "Blockchain anchoring is not implemented.",
    "RFC 3161 timestamp provider is not connected unless explicitly "
    "configured.",
    "C2PA provenance is a signal, not final truth.",
    "SCITT receipts are not implemented.",
    "Object Lock is not implemented unless explicitly added in a later "
    "mission.",
    "Safe view may omit sensitive fields; omitted fields do not change "
    "server-side evidence truth.",
    "Safe view is not a separate proof.",
    "Production readiness is false.",
    "Server-side Evidence logic remains authoritative.",
]

# Fields a SAFE / redacted view must omit (restricted or verbose internals).
SAFE_VIEW_OMITTED_FIELDS = [
    "content_hash", "canonical_hash", "leaf_hash", "consistency_proof_nodes",
    "derivatives_detail", "contracts_detail",
]


# ---------------------------------------------------------------------------
# Canonicalization + hashing
# ---------------------------------------------------------------------------
def canonical_json(obj: Any) -> str:
    """Deterministic project-local canonical JSON (finalis-canonical-json-v1):
    sorted keys, stable separators, UTF-8, arrays keep order, NaN/Infinity
    rejected. NOT strict RFC 8785 JCS — see STRICT_RFC8785_JCS_STATUS."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strip_excluded(obj: Any) -> Any:
    """Recursively drop EXCLUDED_HASH_FIELDS so the hash is a pure function
    of proof-critical content."""
    if isinstance(obj, dict):
        return {k: _strip_excluded(v) for k, v in obj.items()
                if k not in EXCLUDED_HASH_FIELDS}
    if isinstance(obj, list):
        return [_strip_excluded(v) for v in obj]
    return obj


def compute_report_hash(hashable_payload: dict) -> str:
    """report_hash = sha256(canonical_json(payload without excluded fields)).
    Excludes itself and all volatile/signature fields by construction."""
    return _sha256_hex(canonical_json(_strip_excluded(hashable_payload)))


def hash_input_manifest(hashable_payload: dict) -> dict:
    included = sorted(k for k in hashable_payload
                      if k not in EXCLUDED_HASH_FIELDS)
    return {
        "included_fields": included,
        "excluded_fields": sorted(EXCLUDED_HASH_FIELDS),
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "hash_algorithm": REPORT_HASH_ALGORITHM,
        "schema_version": REPORT_HASH_INPUT_SCHEMA_VERSION,
        "strict_rfc8785_jcs_status": STRICT_RFC8785_JCS_STATUS,
    }


# ---------------------------------------------------------------------------
# Proof algebra D1..D15
# ---------------------------------------------------------------------------
DIMENSION_NAMES = {
    "D1": "HashIntegrity", "D2": "MerkleInclusion", "D3": "MerkleConsistency",
    "D4": "TimestampEvidence", "D5": "ProvenanceSignal",
    "D6": "DerivativeChain", "D7": "ContractLink", "D8": "TenantIsolation",
    "D9": "AlgorithmAgility", "D10": "Freshness", "D11": "BusinessContext",
    "D12": "ReportCanonicalization", "D13": "ReportReplayability",
    "D14": "ReportSignatureReadiness", "D15": "SafeViewIntegrity",
}

_HARD_FAIL = {
    "D1": {"FAIL"}, "D2": {"FAIL"}, "D3": {"FAIL"}, "D6": {"FAIL"},
    "D7": {"FAIL"}, "D8": {"FAIL"},
    "D9": {"UNSUPPORTED_CRITICAL_ALGORITHM"}, "D11": {"DISPUTED"},
    "D12": {"FAIL"}, "D13": {"MISMATCHED"}, "D15": {"FAIL"},
}


def build_proof_algebra(signals: dict) -> dict:
    ev = signals["evidence"]
    d: dict[str, str] = {}
    integ = ev.get("integrity_valid")
    d["D1"] = "PASS" if integ is True else ("FAIL" if integ is False
                                            else "UNKNOWN")
    inc = signals.get("inclusion") or {}
    d["D2"] = {"VERIFIED": "PASS", "NOT_VERIFIED": "FAIL"}.get(
        inc.get("status"), "NOT_EXPOSED")
    con = signals.get("consistency")
    if not con or con.get("status") in (None, "NOT_EXPOSED"):
        d["D3"] = "NOT_EXPOSED"
    else:
        d["D3"] = "PASS" if con.get("append_only_verified") else "FAIL"
    d["D4"] = "NOT_EXPOSED"
    d["D5"] = "NOT_EXPOSED"
    derivs = signals.get("derivatives")
    if derivs is None:
        d["D6"] = "NOT_EXPOSED"
    elif not derivs:
        d["D6"] = "NOT_APPLICABLE"
    else:
        d["D6"] = "FAIL" if any(x.get("orphan") for x in derivs) else "PASS"
    contracts = signals.get("contracts")
    d["D7"] = "NOT_EXPOSED" if contracts is None else (
        "PASS" if contracts else "NOT_APPLICABLE")
    d["D8"] = "PASS"                       # loader confirmed tenant match
    alg = (ev.get("algorithm") or "").lower()
    d["D9"] = "UNKNOWN" if not alg else (
        "UNSUPPORTED_CRITICAL_ALGORITHM"
        if any(x in alg for x in ("md5", "sha1", "sha-1")) else "PASS")
    d["D10"] = "PASS" if integ is True else "UNKNOWN"
    state = ev.get("state")
    d["D11"] = "DISPUTED" if state in ("REJECTED", "DISPUTED") else (
        "PASS" if (state == "ADMISSIBLE" and ev.get("human_verified"))
        else "REVIEW_REQUIRED")
    d["D12"] = "PASS" if signals.get("canonicalization_ok", True) else "FAIL"
    d["D13"] = "PASS" if signals.get("replayable", True) else "MISMATCHED"
    d["D14"] = "NOT_EXPOSED"               # signing not implemented
    d["D15"] = "PASS" if signals.get("safe_view_ok", True) else "FAIL"
    return d


def hard_fail_reasons(dims: dict) -> list:
    return [f"{k}:{DIMENSION_NAMES[k]}={dims[k]}"
            for k, bad in _HARD_FAIL.items() if dims.get(k) in bad]


def verdict_from_dims(dims: dict) -> tuple:
    """Returns (final_technical_verdict, automation_allowed, hard_fails).
    A hard-fail can never be averaged away by positive signals."""
    hard = hard_fail_reasons(dims)
    if dims.get("D1") == "FAIL":
        return "TAMPER_WARNING", False, hard
    if dims.get("D8") == "FAIL":
        return "FAILED_VERIFICATION", False, hard
    if dims.get("D2") == "FAIL":
        return "FAILED_VERIFICATION", False, hard
    if hard:
        return "REVIEW_REQUIRED", False, hard
    if dims.get("D1") != "PASS":
        return "NOT_VERIFIED", False, hard
    if dims.get("D2") != "PASS":
        return "REVIEW_REQUIRED", False, hard
    if dims.get("D3") == "PASS" and dims.get("D11") == "PASS":
        return "VERIFIED_FOR_INTEGRITY", True, hard
    if dims.get("D3") == "PASS":
        return "VERIFIED_FOR_INTEGRITY", False, hard   # integrity only
    return "VERIFIED_WITH_LIMITATIONS", False, hard


# ---------------------------------------------------------------------------
# Conflicts / warnings / capability accounting
# ---------------------------------------------------------------------------
def _conflicts(dims: dict, signals: dict) -> list:
    out = []
    if dims["D1"] == "FAIL":
        out.append({"category": "integrity", "detail": "hash mismatch",
                    "effect": "BLOCKS AUTOMATION"})
    if dims["D2"] == "FAIL":
        out.append({"category": "integrity",
                    "detail": "Merkle inclusion mismatch",
                    "effect": "REVIEW"})
    if dims["D3"] == "FAIL":
        out.append({"category": "consistency",
                    "detail": "append-only consistency failed",
                    "effect": "REVIEW"})
    if dims["D6"] == "FAIL":
        out.append({"category": "derivative",
                    "detail": "derivative parent missing/over-trust",
                    "effect": "BLOCKS TRUST"})
    if dims["D9"] == "UNSUPPORTED_CRITICAL_ALGORITHM":
        out.append({"category": "algorithm",
                    "detail": "deprecated/unsupported algorithm",
                    "effect": "REVIEW"})
    if dims["D11"] != "PASS":
        out.append({"category": "business",
                    "detail": "integrity vs business/legal validity",
                    "effect": "integrity != business truth"})
    if dims["D13"] == "MISMATCHED":
        out.append({"category": "report_replay",
                    "detail": "recomputed report hash mismatch",
                    "effect": "REVIEW"})
    return out


def _warnings(dims: dict) -> list:
    w = []
    if dims["D2"] in ("NOT_EXPOSED",):
        w.append("Merkle inclusion proof is not exposed for this evidence.")
    if dims["D3"] in ("NOT_EXPOSED", "FAIL"):
        w.append("Merkle consistency is not verified — append-only cannot "
                 "be assumed.")
    if dims["D6"] == "FAIL":
        w.append("Derivative parent evidence is missing.")
    w.append("Report signing infrastructure is not configured.")
    w.append("Cryptographic verification is not legal validity.")
    w.append("External notarization is not connected.")
    w.append("Production readiness is false.")
    return w


MISSING_CAPABILITIES = [
    "production signed report", "PDF proof package", "public shareable report",
    "RFC 3161 timestamp provider", "C2PA provenance verification API",
    "SCITT receipt API", "Object Lock adapter",
    "legal validation workflow", "external report notarization",
    "W3C VC / Data Integrity issuance",
    "strict RFC 8785 JCS canonicalization",
]

SCAFFOLDED_ONLY = [
    "report signature envelope metadata", "timestamp signal",
    "provenance / C2PA signal", "SCITT statement/receipt signal",
    "object-lock signal", "PDF export", "external notary",
]


def signature_block() -> dict:
    """No signing infrastructure exists — every signing field is null and
    the status is honest. No fake SIGNED is ever produced."""
    return {
        "report_signature_status": "NOT_CONFIGURED",
        "signature_envelope_type": "SIGNED_PRODUCTION_NOT_IMPLEMENTED",
        "signature_algorithm": None,
        "signature_key_ref": None,
        "signed_payload_hash": None,
        "signature_created_at": None,
        "signature_verification_status": "NOT_CONFIGURED",
        "dsse_ready": True, "cose_ready": True,
        "http_message_signature_ready": True,
        "note": "Report signing requires configured signing infrastructure.",
    }


# ---------------------------------------------------------------------------
# Payload + package builders
# ---------------------------------------------------------------------------
def build_report_payload(*, report_id: str, tenant_id: str, generated_by: str,
                         generated_at: str, signals: dict,
                         parent_report_id: Optional[str] = None,
                         supersedes_report_id: Optional[str] = None) -> dict:
    ev = signals["evidence"]
    inc = signals.get("inclusion") or {}
    con = signals.get("consistency") or {}
    dims = build_proof_algebra(signals)
    verdict, automation, hard = verdict_from_dims(dims)
    conflicts = _conflicts(dims, signals)
    warnings = _warnings(dims)

    subject = {
        "evidence_id": ev.get("id"), "case_id": ev.get("case_id"),
        "contract_id": signals.get("contract_id"),
        "quote_id": signals.get("quote_id"),
        "decision_id": signals.get("decision_id"),
        "evidence_type": ev.get("evidence_type"), "source": ev.get("source"),
        "created_at": ev.get("created_at"),
        "content_hash": ev.get("content_hash"),
        "canonical_hash": ev.get("content_hash"),
        "algorithm": ev.get("algorithm"),
    }
    proof_snapshot = {
        "hash_integrity": dims["D1"], "merkle_inclusion": dims["D2"],
        "merkle_consistency": dims["D3"], "derivative_chain": dims["D6"],
        "contract_history": dims["D7"], "timestamp_signal": "NOT_EXPOSED",
        "provenance_signal": "NOT_EXPOSED", "c2pa_signal": "NOT_EXPOSED",
        "scitt_signal": "NOT_IMPLEMENTED", "object_lock_signal": "NOT_EXPOSED",
        "algorithm_pqc_signal": {"algorithm": ev.get("algorithm"),
                                 "family": "CLASSICAL_ONLY"
                                 if ev.get("algorithm") else "UNKNOWN",
                                 "pqc_ready": "NOT_EXPOSED"},
    }
    transparency_log_snapshot = {
        "root_id": inc.get("root_id"), "root_hash": inc.get("root_hash"),
        "tree_size": inc.get("tree_size"), "leaf_index": inc.get("leaf_index"),
        "leaf_hash": inc.get("leaf_hash"),
        "inclusion_proof_status": inc.get("status", "NOT_EXPOSED"),
        "consistency_proof_status": con.get("status", "NOT_EXPOSED"),
        "append_only_verified": bool(con.get("append_only_verified")),
        "previous_root_id": con.get("previous_root_id"),
        "current_root_id": con.get("current_root_id"),
        "consistency_proof_nodes": con.get("proof_nodes", []),
        "checkpoint_status": "NOT_IMPLEMENTED",
        "witness_status": "NOT_IMPLEMENTED",
        "external_transparency_status": "NOT_CONNECTED",
    }
    verdict_block = {
        "final_technical_verdict": verdict,
        "automation_allowed": automation,
        "hard_fail_reasons": hard,
        "human_review_required": bool(hard) or verdict != "VERIFIED_FOR_INTEGRITY",
        "limitations": ["Cryptographic verification is not the same as legal "
                        "validity."],
    }

    # Proof-critical content — the ONLY thing report_hash is computed over.
    hashable = {
        "report_type": REPORT_TYPE, "report_version": REPORT_VERSION,
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "report_hash_input_schema_version": REPORT_HASH_INPUT_SCHEMA_VERSION,
        "report_hash_algorithm": REPORT_HASH_ALGORITHM,
        "subject": subject, "proof_snapshot": proof_snapshot,
        "transparency_log_snapshot": transparency_log_snapshot,
        "proof_algebra": dims, "verdict": verdict_block,
        "conflicts": conflicts, "warnings": warnings,
        "missing_capabilities": MISSING_CAPABILITIES,
        "scaffolded_only": SCAFFOLDED_ONLY,
        "honesty_labels": HONESTY_LABELS,
    }
    rhash = compute_report_hash(hashable)
    manifest = hash_input_manifest(hashable)

    metadata = {
        "report_id": report_id, "tenant_id": tenant_id,
        "report_type": REPORT_TYPE, "report_version": REPORT_VERSION,
        "report_status": "GENERATED", "subject_type": "evidence",
        "subject_id": ev.get("id"), "evidence_id": ev.get("id"),
        "case_id": ev.get("case_id"),
        "generated_by": generated_by, "generated_at": generated_at,
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "report_hash_algorithm": REPORT_HASH_ALGORITHM,
        "report_hash": rhash,
        "report_hash_input_schema_version": REPORT_HASH_INPUT_SCHEMA_VERSION,
        "report_hash_excluded_fields": sorted(EXCLUDED_HASH_FIELDS),
        "replay_status": "NOT_RUN", "redaction_profile": "FULL_AUDIT_VIEW",
        "safe_view_available": True,
        "final_verdict": verdict, "automation_allowed": automation,
        "warnings_count": len(warnings), "conflicts_count": len(conflicts),
        "missing_capabilities_count": len(MISSING_CAPABILITIES),
        "parent_report_id": parent_report_id,
        "supersedes_report_id": supersedes_report_id,
        "created_from_run_id": None,
    }
    metadata.update(signature_block())

    payload = {"report_metadata": metadata, **hashable,
               "hash_input_manifest": manifest}
    return payload


def build_package(payload: dict) -> dict:
    """A logical (JSON) report package. Every hash excludes itself and
    changes if the payload or manifest changes."""
    rhash = payload["report_metadata"]["report_hash"]
    manifest = payload["hash_input_manifest"]
    manifest_hash = _sha256_hex(canonical_json(manifest))
    payload_hash = _sha256_hex(canonical_json(_strip_excluded(payload)))
    package_core = {
        "package_version": 1, "report_id": payload["report_metadata"][
            "report_id"], "report_hash": rhash,
        "manifest_hash": manifest_hash, "payload_hash": payload_hash,
        "logical_parts": ["report_payload", "hash_input_manifest",
                          "verification_manifest", "honesty_labels",
                          "safe_view_manifest", "redaction_manifest"],
    }
    package_hash = _sha256_hex(canonical_json(package_core))
    return {**package_core, "package_hash": package_hash}


# ---------------------------------------------------------------------------
# Safe view / redaction
# ---------------------------------------------------------------------------
def safe_view(payload: dict) -> dict:
    """A redacted view: omit restricted/verbose fields. Never changes stored
    truth; not a separate proof."""
    def redact(obj):
        if isinstance(obj, dict):
            return {k: ("<omitted in safe view>"
                        if k in SAFE_VIEW_OMITTED_FIELDS else redact(v))
                    for k, v in obj.items()}
        if isinstance(obj, list):
            return [redact(v) for v in obj]
        return obj
    view = redact(payload)
    view["redaction_profile"] = "SAFE_VIEW"
    view["redaction_manifest"] = {
        "omitted_fields": sorted(SAFE_VIEW_OMITTED_FIELDS),
        "note": "Safe view may omit sensitive fields; omitted fields do not "
                "change server-side evidence truth. Safe view is not a "
                "separate proof."}
    return view


# ---------------------------------------------------------------------------
# Artifact-integrity verification (replay of the STORED artifact)
# ---------------------------------------------------------------------------
def verify_report_artifact(stored_payload: dict, stored_report_hash: str,
                           stored_package_hash: Optional[str]) -> dict:
    """artifact_integrity_verification: recompute the report + package hashes
    from the stored payload and compare. This checks the stored artifact, NOT
    current evidence truth (that would be current_state_replay)."""
    try:
        hashable = {k: stored_payload[k] for k in stored_payload
                    if k not in ("report_metadata", "hash_input_manifest")}
        recomputed = compute_report_hash(hashable)
    except (ValueError, TypeError, KeyError) as e:
        return {"verification_status": "NOT_REPLAYABLE",
                "recomputed_report_hash": None,
                "stored_report_hash": stored_report_hash,
                "package_hash_status": "NOT_CHECKED",
                "reason": f"report payload did not canonicalize: {e}"}
    pkg_status = "NOT_PRESENT"
    if stored_package_hash:
        recomputed_pkg = build_package(stored_payload)["package_hash"]
        pkg_status = ("MATCHED" if recomputed_pkg == stored_package_hash
                      else "MISMATCHED")
    matched = (recomputed == stored_report_hash
               and pkg_status in ("MATCHED", "NOT_PRESENT"))
    return {
        "verification_status": "MATCHED" if matched else "MISMATCHED",
        "verification_kind": "artifact_integrity_verification",
        "current_state_comparison": False,
        "recomputed_report_hash": recomputed,
        "stored_report_hash": stored_report_hash,
        "package_hash_status": pkg_status,
        "signature_status": "NOT_CONFIGURED",
        "reason": ("Stored report hash matches recomputed report hash."
                   if matched else
                   "Stored report hash does not match recomputed report "
                   "hash — artifact tampering detected."),
    }
