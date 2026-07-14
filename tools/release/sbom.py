"""SBOM / AI-ML-BOM / VEX / vulnerability evidence (SP0009 §10, D-0009-35..40,
AC-0009-171..190).

SBOM EXISTS != SBOM COMPLETE: completeness is an explicit five-state claim,
never inferred. An SBOM binds to the exact artifact digest — a wrong-subject
SBOM fails. The AI/ML-BOM is a DISTINCT inventory (models, datasets, prompts,
policies, configurations), never folded into the software SBOM (D-0009-36).
VEX is an argument with evidence, scope, author, time and expiry — never an
automatic exemption (D-0009-37); vulnerability results bind the database
snapshot, scanner version and artifact and go stale (D-0009-38). Scanner
diversity is graded, common-mode dependence (shared parser/rules/input) stays
visible and is never silently majority-voted away (D-0009-39/40).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, P1, P2, SBOM_COMPLETENESS, SCANNER_DIVERSITY


def sbom(*, subject_digest: str, components: list, completeness: str,
         fmt: str = "CycloneDX-1.7") -> dict:
    if completeness not in SBOM_COMPLETENESS:
        raise ValueError(f"unknown completeness {completeness!r}")
    s = {"kind": "SBOM", "format": fmt, "subject_digest": subject_digest,
         "components": sorted(components, key=lambda c: str(c)),
         "completeness": completeness}
    s["ref"] = "SB-" + hash_obj(s)[:20]
    return s


def validate_sbom(s: dict, *, artifact_digest: str) -> list[Finding]:
    out: list[Finding] = []
    subject = str(s.get("ref") or "-")
    if s.get("subject_digest") != artifact_digest:
        out.append(Finding(
            "SBOM_SUBJECT_MISMATCH", P0, subject,
            "SBOM subject digest does not match the artifact: an SBOM for "
            "different bytes describes nothing about this artifact "
            "(AC-0009-175)", {"sbom_subject": s.get("subject_digest"),
                              "artifact": artifact_digest}))
    if s.get("completeness") not in SBOM_COMPLETENESS:
        out.append(Finding("SBOM_INCOMPLETE", P1, subject,
                           f"completeness {s.get('completeness')!r} is not an "
                           "explicit completeness state (D-0009-35)", {}))
    elif s.get("completeness") != "COMPLETE":
        out.append(Finding(
            "SBOM_INCOMPLETE", P2, subject,
            f"SBOM explicitly declares {s['completeness']}: recorded, not "
            "hidden — an incomplete SBOM never masquerades as complete", {}))
    return out


def spdx_projection(s: dict) -> dict:
    """SPDX 3.0-style projection of the same SBOM content."""
    return {"spdxVersion": "SPDX-3.0",
            "element_type": "software_Sbom",
            "subject": {"sha256": s["subject_digest"]},
            "elements": s["components"],
            "completeness": s["completeness"]}


def cyclonedx_projection(s: dict) -> dict:
    return {"bomFormat": "CycloneDX", "specVersion": "1.7",
            "metadata": {"subject": {"sha256": s["subject_digest"]}},
            "components": s["components"],
            "compositions": [{"aggregate":
                              "complete" if s["completeness"] == "COMPLETE"
                              else "incomplete"}]}


# --- AI/ML-BOM: distinct from the software SBOM (D-0009-36) --------------------------
def ai_ml_bom(*, subject_digest: str, models: list, datasets: list,
              prompts: list, policies: list, configurations: list) -> dict:
    b = {"kind": "AI_ML_BOM", "format": "CycloneDX-1.7-MLBOM",
         "subject_digest": subject_digest,
         "models": sorted(models, key=str),
         "datasets": sorted(datasets, key=str),
         "prompts": sorted(prompts, key=str),
         "policies": sorted(policies, key=str),
         "configurations": sorted(configurations, key=str)}
    b["ref"] = "AB-" + hash_obj(b)[:20]
    return b


def validate_ai_bom(b: dict, *, artifact_digest: str,
                    ai_bearing: bool) -> list[Finding]:
    out: list[Finding] = []
    subject = str(b.get("ref") or "-")
    if b.get("subject_digest") != artifact_digest:
        out.append(Finding("AI_BOM_INVALID", P0, subject,
                           "AI/ML-BOM subject digest mismatch", {}))
    if ai_bearing and not b.get("models"):
        out.append(Finding(
            "AI_ML_BOM_INCOMPLETE", P1, subject,
            "AI-bearing artifact with no model identity in its AI/ML-BOM",
            {}))
    return out


# --- vulnerability evidence: time-bound, artifact-bound (D-0009-38) -------------------
def vulnerability_evidence(*, subject_digest: str, scanner_id: str,
                           scanner_version: str, db_snapshot: str,
                           findings: list, observed_at: str,
                           expires_at: str) -> dict:
    v = {"kind": "VULN", "subject_digest": subject_digest,
         "scanner_id": scanner_id, "scanner_version": scanner_version,
         "db_snapshot": db_snapshot, "findings": findings,
         "observed_at": observed_at, "expires_at": expires_at}
    v["ref"] = "VU-" + hash_obj(v)[:20]
    return v


def validate_vuln_evidence(v: dict, *, artifact_digest: str,
                           now: str) -> list[Finding]:
    out: list[Finding] = []
    subject = str(v.get("ref") or "-")
    if v.get("subject_digest") != artifact_digest:
        out.append(Finding("VULNERABILITY_POLICY_FAILED", P0, subject,
                           "vulnerability evidence subject mismatch", {}))
    if not v.get("db_snapshot") or not v.get("scanner_version"):
        out.append(Finding("VULNERABILITY_POLICY_FAILED", P1, subject,
                           "vulnerability evidence must bind scanner version "
                           "and database snapshot (D-0009-38)", {}))
    exp = v.get("expires_at")
    if not exp or str(exp) <= str(now):
        out.append(Finding(
            "VULNERABILITY_EVIDENCE_STALE", P1, subject,
            "vulnerability evidence is stale/expired; scanner output is "
            "time-bound evidence (D-0009-38)", {"expires_at": exp}))
    return out


# --- VEX: evidence, not exemption (D-0009-37) ----------------------------------------
VEX_STATUSES = ("not_affected", "affected", "fixed", "under_investigation")


def vex_claim(*, subject_digest: str, vulnerability_id: str, status: str,
              justification: str, evidence_refs: list, author: str,
              observed_at: str, expires_at: str, version: int = 1) -> dict:
    c = {"kind": "VEX", "format": "OpenVEX-draft-adapter",
         "subject_digest": subject_digest,
         "vulnerability_id": vulnerability_id, "status": status,
         "justification": justification, "evidence_refs": list(evidence_refs),
         "author": author, "observed_at": observed_at,
         "expires_at": expires_at, "version": version,
         "adapter_note": "OpenVEX remains a draft; this is an experimental "
                         "projection adapter, not the sole canonical format "
                         "(AC-0009-185)"}
    c["ref"] = "VX-" + hash_obj(c)[:20]
    return c


def validate_vex(c: dict, *, artifact_digest: str, now: str) -> list[Finding]:
    out: list[Finding] = []
    subject = str(c.get("ref") or "-")
    if c.get("subject_digest") != artifact_digest:
        out.append(Finding("VEX_EVIDENCE_INSUFFICIENT", P0, subject,
                           "VEX subject digest mismatch", {}))
    if c.get("status") not in VEX_STATUSES:
        out.append(Finding("VEX_EVIDENCE_INSUFFICIENT", P1, subject,
                           f"unknown VEX status {c.get('status')!r}", {}))
    if c.get("status") == "not_affected":
        if not c.get("justification") or not c.get("evidence_refs"):
            out.append(Finding(
                "VEX_EVIDENCE_INSUFFICIENT", P0, subject,
                "a not_affected claim requires justification AND evidence "
                "(VEX is an argument, never an automatic exemption, "
                "D-0009-37)", {}))
    exp = c.get("expires_at")
    if not exp or str(exp) <= str(now):
        out.append(Finding("VEX_EVIDENCE_INSUFFICIENT", P1, subject,
                           "VEX claim expired or lacks expiry", {}))
    if not isinstance(c.get("version"), int):
        out.append(Finding("VEX_EVIDENCE_INSUFFICIENT", P1, subject,
                           "VEX claim must be versioned (AC-0009-182)", {}))
    return out


def vex_cannot_waive(policy_failed: bool, vex_claims: list) -> list[Finding]:
    """A VEX claim never auto-waives a vulnerability policy failure
    (AC-0009-184): policy failure survives regardless of VEX presence."""
    out: list[Finding] = []
    if policy_failed:
        out.append(Finding(
            "VULNERABILITY_POLICY_FAILED", P0, "vulnerability-policy",
            "vulnerability policy failed; VEX claims present do not "
            "auto-waive the failure — each claim must be individually "
            "validated and accepted by policy (AC-0009-184)",
            {"vex_claims": [c.get("ref") for c in vex_claims]}))
    return out


# --- scanner diversity / common-mode (§11.19, D-0009-39/40) ---------------------------
def scanner_diversity(scanners: list) -> dict:
    """Grade the diversity of a scanner fleet from declared dependencies.
    Scanners sharing a parser, rule source or input representation are
    common-mode; agreement between them is weaker evidence."""
    if not scanners:
        return {"classification": "UNKNOWN", "shared": {}}
    shared: dict = {}
    for key in ("parser", "rule_source", "input_representation"):
        vals: dict = {}
        for s in scanners:
            v = s.get(key)
            if v:
                vals.setdefault(v, []).append(s.get("scanner_id"))
        dupes = {v: ids for v, ids in vals.items() if len(ids) > 1}
        if dupes:
            shared[key] = dupes
    n = len({s.get("scanner_id") for s in scanners})
    if n < 2:
        cls = "UNKNOWN"
    elif not shared:
        cls = "INDEPENDENT_ENOUGH"
    elif all(len(ids) < n for d in shared.values() for ids in d.values()):
        cls = "PARTIALLY_DEPENDENT"
    else:
        cls = "COMMON_MODE_DOMINATED"
    assert cls in SCANNER_DIVERSITY
    return {"classification": cls, "shared": shared,
            "scanner_count": n}


def disagreement_findings(results: list) -> list[Finding]:
    """Scanner disagreement stays visible (D-0009-39): divergent verdicts on
    the same subject are reported, never majority-voted away."""
    out: list[Finding] = []
    by_subject: dict = {}
    for r in results:
        by_subject.setdefault(
            (r.get("subject_digest"), r.get("vulnerability_id")), []).append(r)
    for (subj, vuln), group in sorted(by_subject.items(),
                                      key=lambda kv: str(kv[0])):
        verdicts = {g.get("verdict") for g in group}
        if len(verdicts) > 1:
            out.append(Finding(
                "SCANNER_COMMON_MODE_RISK", P2, str(vuln),
                f"scanners disagree on {vuln}: {sorted(verdicts)} — "
                "disagreement preserved, not majority-voted (D-0009-39)",
                {"verdicts": {g.get('scanner_id'): g.get('verdict')
                              for g in group}}))
    return out
