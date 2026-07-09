"""Finalis ViktorAI Evidence-Grade Artifact System (CORE-A6).

Pure, deterministic logic for formal, versioned, hash-verifiable, provenance-
linked, claim-linked, safe-viewable, quarantine-aware and materialization-gated
work products.

The Artifact System RECORDS and VERSIONS work products. It executes nothing: no
LLM, no Tool Broker, no external provider, no customer message, no payment, no
CRM write, no evidence rewrite, no document export, no production signing. There
is no C2PA / Sigstore / DSSE / SLSA / in-toto here. Server-side artifact truth
is authoritative; artifact content (which may carry prompt injection) can never
change server policy. Fail-closed: an artifact is valid only when every factor
of ArtifactValid holds.
"""
from __future__ import annotations

import hashlib
import json
import re

ARTIFACT_MODEL_VERSION = "finalis-artifact-v1"
MANIFEST_VERSION = "finalis-artifact-manifest-v1"
ENVELOPE_VERSION = "finalis-artifact-content-envelope-v1"
CLAIM_GRAPH_VERSION = "finalis-artifact-claim-graph-v1"
ABOM_VERSION = "finalis-artifact-abom-v1"
PROVENANCE_VERSION = "finalis-artifact-provenance-v1"
POLICY_CAPSULE_VERSION = "finalis-artifact-policy-capsule-v1"
GENESIS = "0" * 64
GENERATION_METHODS = {"LOCAL_DETERMINISTIC", "MANUAL_TEST_FIXTURE"}

# --- Artifact type taxonomy ------------------------------------------------
ARTIFACT_TYPES = {
    "CASE_SUMMARY_DRAFT", "CUSTOMER_REPLY_DRAFT", "INTERNAL_NOTE_DRAFT",
    "ACTION_PLAN_DRAFT", "CHECKLIST", "REVIEW_CHECKLIST",
    "APPROVAL_CONTEXT_PACKAGE", "EVIDENCE_REPORT_REFERENCE", "PROOF_SUMMARY",
    "QUOTE_DRAFT", "CONTRACT_DRAFT_REFERENCE", "TASK_COMPLETION_SUMMARY",
    "BLOCKER_SUMMARY", "RESEARCH_NOTE", "RISK_ASSESSMENT",
    "POLICY_DECISION_SUMMARY", "RUN_TRACE_SUMMARY", "SAFE_VIEW_SNAPSHOT",
    "TOOL_INPUT_PROPOSAL", "MATERIALIZATION_PLAN", "CLAIM_GRAPH_SUMMARY",
    "ARTIFACT_BOM", "DECONTAMINATED_DERIVATIVE", "NOT_IMPLEMENTED_PLACEHOLDER",
}
# Future-only / forbidden types — never faked; rejected as NOT_IMPLEMENTED.
FORBIDDEN_TYPES = {
    "CUSTOMER_MESSAGE_SENT", "PAYMENT_EXECUTED", "CRM_WRITE_COMPLETED",
    "EVIDENCE_REWRITE", "CONSENT_OVERRIDE", "SIGNED_LEGAL_DOCUMENT",
    "PRODUCTION_SIGNATURE", "EXTERNAL_PROVIDER_RESULT",
    "PRODUCTION_C2PA_CREDENTIAL", "PRODUCTION_SIGSTORE_ATTESTATION",
    "PRODUCTION_DSSE_ENVELOPE", "PRODUCTION_SLSA_ATTESTATION",
    "PRODUCTION_IN_TOTO_ATTESTATION",
}
# Types that require a valid human approval grant before they can be VALIDATED.
APPROVAL_REQUIRED_TYPES = {"CUSTOMER_REPLY_DRAFT", "QUOTE_DRAFT",
                           "CONTRACT_DRAFT_REFERENCE"}
# Types that are proposals for FUTURE tool input (never executable here).
TOOL_INPUT_TYPES = {"TOOL_INPUT_PROPOSAL", "MATERIALIZATION_PLAN"}

ARTIFACT_STATUSES = {
    "DRAFT", "NEEDS_REVIEW", "REVIEW_READY", "VALIDATED", "BLOCKED",
    "QUARANTINED", "DECONTAMINATED_DERIVATIVE_READY",
    "REDACTED_SAFE_VIEW_AVAILABLE", "SUPERSEDED", "ARCHIVED", "TAMPERED",
    "DELETED_LOGICAL", "NOT_IMPLEMENTED",
}
TERMINAL_STATUSES = {"SUPERSEDED", "ARCHIVED", "DELETED_LOGICAL", "TAMPERED",
                     "NOT_IMPLEMENTED"}

TRUST_TIERS = {
    "UNTRUSTED_CAPTURE", "AI_DRAFT_UNVERIFIED",
    "SYSTEM_GENERATED_DETERMINISTIC", "HUMAN_REVIEW_REQUIRED", "HUMAN_REVIEWED",
    "INTERNAL_VALIDATED", "REFERENCE_ONLY", "SAFE_REDACTED", "QUARANTINED",
    "DECONTAMINATED_DERIVATIVE",
}
CONTENT_FORMATS = {"TEXT", "MARKDOWN", "JSON", "STRUCTURED_SUMMARY",
                   "REFERENCE_ONLY", "SAFE_VIEW_ONLY"}
CONTENT_TRUST_LEVELS = {
    "USER_PROVIDED", "AI_DRAFT", "SYSTEM_GENERATED", "REFERENCE_ONLY",
    "SAFE_REDACTED", "UNTRUSTED_INPUT_CAPTURED", "QUARANTINED_CONTENT",
    "DECONTAMINATED_DERIVATIVE",
}
CLAIM_SUPPORT_STATUSES = {"SUPPORTED_BY_REFERENCE", "UNSUPPORTED",
                          "NEEDS_REVIEW", "CONTRADICTED", "NOT_APPLICABLE",
                          "NOT_IMPLEMENTED"}
MATERIALIZATION_STATUSES = {
    "MATERIALIZATION_ALLOWED_FOR_INTERNAL_REVIEW", "MATERIALIZATION_BLOCKED",
    "MATERIALIZATION_REQUIRES_TOOL_BROKER", "MATERIALIZATION_REQUIRES_APPROVAL",
    "MATERIALIZATION_REQUIRES_SAFE_VIEW",
    "MATERIALIZATION_REQUIRES_DECONTAMINATION", "MATERIALIZATION_NOT_IMPLEMENTED",
}

HONESTY_LABELS = [
    "Artifact creation does not execute the action.",
    "Artifact creation does not send customer messages.",
    "Artifact creation does not execute payments.",
    "Artifact creation does not call external providers.",
    "Artifact creation does not call LLM providers.",
    "Artifact creation does not rewrite evidence.",
    "Artifact validation is internal integrity validation, not legal validity.",
    "AI draft content is not human-verified truth.",
    "Claim graph records local support status; it does not create legal truth.",
    "Artifact quarantine preserves the artifact but blocks readiness and "
    "future use.",
    "Materialization-check validates future readiness only; it does not "
    "execute anything.",
    "Safe artifact view may omit sensitive fields; omitted fields do not "
    "change server-side artifact truth.",
    "Safe artifact view is not a separate artifact.",
    "Document export is not implemented in this mission.",
    "Production signing is not implemented in this mission.",
    "C2PA/Sigstore/DSSE/SLSA/in-toto are not implemented in this mission.",
    "Server-side artifact truth is authoritative.",
    "This is not production autonomous execution.",
]


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _sha(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def _text_sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# --- Deterministic content scanner (prompt-injection / tool-poisoning) ------
# (needle, category). Categories: prompt_injection, tool_poisoning,
# data_exfiltration, unsafe_content. Content that trips a category is advisory
# and NEVER affects server policy; it only flags/quarantines the artifact.
_SCANNER_PATTERNS = [
    ("ignore previous instructions", "prompt_injection"),
    ("ignore all previous", "prompt_injection"),
    ("override policy", "prompt_injection"),
    ("disregard the rules", "prompt_injection"),
    ("use this as a system prompt", "prompt_injection"),
    ("you are now", "prompt_injection"),
    ("call external provider", "tool_poisoning"),
    ("execute payment", "unsafe_content"),
    ("call stripe", "unsafe_content"),
    ("send customer message", "unsafe_content"),
    ("send this to the customer", "unsafe_content"),
    ("rewrite evidence", "unsafe_content"),
    ("delete evidence", "unsafe_content"),
    ("override consent", "unsafe_content"),
    ("hide proof failure", "unsafe_content"),
    ("change tenant id", "unsafe_content"),
    ("change task contract", "unsafe_content"),
    ("validate as human truth", "unsafe_content"),
    ("remote instructions", "tool_poisoning"),
    ("grant admin", "unsafe_content"),
    ("mark legal validity", "unsafe_content"),
    ("mark this legally valid", "unsafe_content"),
    ("claim verified by law", "unsafe_content"),
    ("mark production ready", "unsafe_content"),
    ("mark production signed", "unsafe_content"),
    ("remove quarantine", "unsafe_content"),
    ("sync crm", "unsafe_content"),
    ("export pdf", "unsafe_content"),
    ("exfiltrate", "data_exfiltration"),
    ("curl http", "data_exfiltration"),
    ("download and execute", "data_exfiltration"),
    ("download and run", "data_exfiltration"),
    ("tool call", "tool_poisoning"),
    ("use this as tool call", "tool_poisoning"),
    ("mcp server", "tool_poisoning"),
    ("register tool", "tool_poisoning"),
    ("register mcp", "tool_poisoning"),
]
_CATEGORY_FIELD = {
    "prompt_injection": "prompt_injection_flags",
    "tool_poisoning": "tool_poisoning_flags",
    "data_exfiltration": "data_exfiltration_flags",
    "unsafe_content": "unsafe_content_flags",
}


def scan_content(content_body: str) -> dict:
    """Deterministic, pattern-based safety scan. No LLM. Returns advisory flags
    and a quarantine verdict; the artifact is preserved regardless.

    The content is normalized (lowercased, punctuation and whitespace runs
    collapsed to single spaces) before matching, so trivial spacing/punctuation
    tricks — "ignore   previous instructions", "ignore, previous instructions",
    "ignore previous\\ninstructions" — do not evade the scanner."""
    blob = " " + re.sub(r"[^a-z0-9]+", " ", (content_body or "").lower()) + " "
    found = {"prompt_injection_flags": [], "tool_poisoning_flags": [],
             "data_exfiltration_flags": [], "unsafe_content_flags": []}
    for needle, category in _SCANNER_PATTERNS:
        if needle in blob:
            field = _CATEGORY_FIELD[category]
            if needle not in found[field]:
                found[field].append(needle)
    any_flag = any(found[k] for k in found)
    result = {
        **found,
        "quarantine_status": "QUARANTINED" if any_flag else "CLEAN",
        "quarantine_reason": ("unsafe content patterns detected: "
                              + ", ".join(sorted(
                                  n for v in found.values() for n in v))
                              if any_flag else None),
        "scanner_version": "finalis-artifact-scanner-v1",
    }
    result["scanner_hash"] = _sha({k: sorted(v) if isinstance(v, list) else v
                                   for k, v in result.items()
                                   if k != "scanner_hash"})
    return result


# --- Content envelope ------------------------------------------------------
def build_content_envelope(*, content_format, content_role, content_trust_level,
                           content_body, input_sources=None,
                           untrusted_input_refs=None, generated_by="SYSTEM",
                           generation_method="LOCAL_DETERMINISTIC",
                           review_required=True, limitations=None,
                           warnings=None, scanner=None) -> dict:
    if content_format not in CONTENT_FORMATS:
        raise ValueError(f"unknown content_format {content_format}")
    if content_trust_level not in CONTENT_TRUST_LEVELS:
        raise ValueError(f"unknown content_trust_level {content_trust_level}")
    if generation_method not in GENERATION_METHODS:
        raise ValueError(f"unknown generation_method {generation_method}")
    scanner = scanner or scan_content(content_body)
    env = {
        "content_envelope_version": ENVELOPE_VERSION,
        "content_format": content_format, "content_role": content_role,
        "content_trust_level": content_trust_level,
        "content_body": content_body, "content_body_hash": _text_sha(
            content_body),
        "input_sources": list(input_sources or []),
        "untrusted_input_refs": list(untrusted_input_refs or []),
        "generated_by": generated_by, "generation_method": generation_method,
        "review_required": bool(review_required),
        "external_provider_used": False, "llm_provider_used": False,
        "tool_broker_used": False,
        "limitations": list(limitations or []),
        "warnings": list(warnings or []),
        "unsafe_content_flags": scanner["unsafe_content_flags"],
        "prompt_injection_flags": scanner["prompt_injection_flags"],
        "tool_poisoning_flags": scanner["tool_poisoning_flags"],
        "data_exfiltration_flags": scanner["data_exfiltration_flags"],
        "honesty_labels": HONESTY_LABELS,
    }
    return env


def content_hash(envelope: dict) -> str:
    core = {k: v for k, v in envelope.items()
            if k not in ("content_body_hash", "honesty_labels")}
    return _sha(core)


# --- Claim graph -----------------------------------------------------------
_ALLOWED_PREDICATES = {
    "summarizes", "recommends", "references", "asserts", "requests_action",
    "reports_status", "cites_evidence", "identifies_blocker",
    "proposes_tool_input", "describes_risk",
}


def _claim_support(claim: dict) -> str:
    """Deterministic support status. A claim is supported only if it carries at
    least one supporting reference; otherwise it is UNSUPPORTED / NEEDS_REVIEW.
    This is LOCAL structural support only — it never asserts legal truth."""
    if claim.get("claim_predicate") not in _ALLOWED_PREDICATES:
        return "NEEDS_REVIEW"
    if not claim.get("claim_subject_id"):
        return "NEEDS_REVIEW"
    has_ref = bool(claim.get("supporting_evidence_refs")
                   or claim.get("supporting_report_refs")
                   or claim.get("supporting_artifact_refs"))
    return "SUPPORTED_BY_REFERENCE" if has_ref else "UNSUPPORTED"


def build_claim_graph(*, artifact_id, artifact_version_id, tenant_id,
                      claims_input, source_text) -> dict:
    """Build the local claim graph. `claims_input` is a list of structured
    claim dicts (deterministic); free-text extraction is out of scope and
    marked NOT_IMPLEMENTED when no structured claims are provided."""
    nodes = []
    src_hash = _text_sha(source_text)
    if not claims_input:
        nodes.append({
            "claim_id": f"{artifact_version_id}-claim-0",
            "artifact_id": artifact_id,
            "artifact_version_id": artifact_version_id, "tenant_id": tenant_id,
            "claim_type": "CLAIM_EXTRACTION_NOT_IMPLEMENTED",
            "claim_subject_type": None, "claim_subject_id": None,
            "claim_predicate": None, "claim_value": None,
            "claim_value_hash": _text_sha(""),
            "claim_confidence": "LOCAL_STRUCTURAL_ONLY",
            "claim_support_status": "NOT_IMPLEMENTED",
            "supporting_evidence_refs": [], "supporting_report_refs": [],
            "supporting_artifact_refs": [], "source_text_hash": src_hash,
        })
    for i, c in enumerate(claims_input or []):
        value = c.get("claim_value")
        node = {
            "claim_id": f"{artifact_version_id}-claim-{i}",
            "artifact_id": artifact_id,
            "artifact_version_id": artifact_version_id, "tenant_id": tenant_id,
            "claim_type": c.get("claim_type", "STRUCTURED"),
            "claim_subject_type": c.get("claim_subject_type"),
            "claim_subject_id": c.get("claim_subject_id"),
            "claim_predicate": c.get("claim_predicate"),
            "claim_value": value, "claim_value_hash": _sha(value),
            "claim_confidence": "LOCAL_STRUCTURAL_ONLY",
            "supporting_evidence_refs": list(c.get("supporting_evidence_refs",
                                                   []) or []),
            "supporting_report_refs": list(c.get("supporting_report_refs", [])
                                           or []),
            "supporting_artifact_refs": list(c.get("supporting_artifact_refs",
                                                   []) or []),
            "source_text_hash": src_hash,
        }
        node["claim_support_status"] = _claim_support(node)
        nodes.append(node)
    graph = {"claim_graph_version": CLAIM_GRAPH_VERSION,
             "artifact_id": artifact_id, "tenant_id": tenant_id,
             "claims": nodes,
             "unsupported_count": sum(1 for n in nodes if n[
                 "claim_support_status"] in ("UNSUPPORTED", "CONTRADICTED")),
             "needs_review_count": sum(1 for n in nodes if n[
                 "claim_support_status"] == "NEEDS_REVIEW")}
    graph["claim_graph_hash"] = claim_graph_hash(graph)
    return graph


def claim_graph_hash(graph: dict) -> str:
    core = {k: v for k, v in graph.items() if k != "claim_graph_hash"}
    return _sha(core)


def claims_all_supported(graph: dict) -> bool:
    return bool(graph["claims"]) and graph["claims"][0][
        "claim_support_status"] != "NOT_IMPLEMENTED" and all(
        n["claim_support_status"] in ("SUPPORTED_BY_REFERENCE",
                                      "NOT_APPLICABLE")
        for n in graph["claims"])


# --- ABOM (Artifact Bill of Materials) — NOT an SBOM -----------------------
def build_abom(*, artifact_id, artifact_version_id, tenant_id, artifact_type,
               content_format, input_sources, source_channels,
               dependency_artifact_versions, evidence_refs, report_refs,
               task_refs, run_refs, approval_refs, policy_capsule_hash,
               scanner_hash, trust_tier) -> dict:
    abom = {
        "abom_version": ABOM_VERSION, "artifact_id": artifact_id,
        "artifact_version_id": artifact_version_id, "tenant_id": tenant_id,
        "artifact_type": artifact_type, "content_format": content_format,
        "input_sources": list(input_sources or []),
        "source_channels": list(source_channels or []),
        "dependency_artifact_versions": list(dependency_artifact_versions or []),
        "evidence_refs": list(evidence_refs or []),
        "report_refs": list(report_refs or []),
        "task_refs": list(task_refs or []), "run_refs": list(run_refs or []),
        "approval_refs": list(approval_refs or []),
        "policy_capsule_hash": policy_capsule_hash, "scanner_hash": scanner_hash,
        "trust_tier": trust_tier, "generation_method": "LOCAL_DETERMINISTIC",
        "external_provider_used": False, "llm_provider_used": False,
        "tool_broker_used": False,
        "not_an_sbom": "ABOM is local Finalis composition metadata; it is not "
        "an SBOM and claims no SPDX/CycloneDX/SLSA compliance.",
        "honesty_labels": HONESTY_LABELS,
    }
    abom["abom_hash"] = abom_hash(abom)
    return abom


def abom_hash(abom: dict) -> str:
    core = {k: v for k, v in abom.items()
            if k not in ("abom_hash", "honesty_labels")}
    return _sha(core)


# --- Provenance graph (local; NOT C2PA/SLSA/in-toto) -----------------------
def build_provenance(*, artifact_id, artifact_version_id, tenant_id, task_id,
                     run_id, approval_request_id, created_by_actor_id,
                     created_by_actor_type, assigned_ai_employee_id,
                     dependency_artifact_ids, evidence_refs, report_refs,
                     supersedes_artifact_id, has_claim, has_abom) -> dict:
    agent_type = {"human": "PROV_AGENT_HUMAN_USER",
                  "ai_employee": "PROV_AGENT_AI_EMPLOYEE"}.get(
        created_by_actor_type, "PROV_AGENT_SYSTEM")
    nodes = [
        {"node": "PROV_ENTITY_ARTIFACT", "id": artifact_id},
        {"node": "PROV_ENTITY_ARTIFACT_VERSION", "id": artifact_version_id},
        {"node": "PROV_ACTIVITY_ARTIFACT_CREATE", "id": artifact_version_id
         + "-create"},
        {"node": agent_type, "id": created_by_actor_id},
    ]
    edges = [
        {"edge": "WAS_GENERATED_BY", "from": artifact_version_id,
         "to": artifact_version_id + "-create"},
        {"edge": "WAS_ATTRIBUTED_TO", "from": artifact_id,
         "to": created_by_actor_id},
    ]
    if task_id:
        nodes.append({"node": "PROV_ENTITY_TASK", "id": task_id})
        edges.append({"edge": "USED", "from": artifact_version_id
                      + "-create", "to": task_id})
    if run_id:
        nodes.append({"node": "PROV_ENTITY_RUN", "id": run_id})
        edges.append({"edge": "WAS_INFORMED_BY", "from": artifact_version_id
                      + "-create", "to": run_id})
    if approval_request_id:
        nodes.append({"node": "PROV_ENTITY_APPROVAL", "id":
                      approval_request_id})
        edges.append({"edge": "USED", "from": artifact_version_id + "-create",
                      "to": approval_request_id})
    for dep in dependency_artifact_ids or []:
        nodes.append({"node": "PROV_ENTITY_DEPENDENCY_ARTIFACT", "id": dep})
        edges.append({"edge": "WAS_DERIVED_FROM", "from": artifact_id,
                      "to": dep})
    for ev in evidence_refs or []:
        edges.append({"edge": "REFERENCES", "from": artifact_id, "to": ev})
    for rep in report_refs or []:
        edges.append({"edge": "REFERENCES", "from": artifact_id, "to": rep})
    if supersedes_artifact_id:
        edges.append({"edge": "WAS_REVISION_OF", "from": artifact_id,
                      "to": supersedes_artifact_id})
    if has_claim:
        edges.append({"edge": "HAS_CLAIM", "from": artifact_version_id,
                      "to": artifact_version_id + "-claims"})
    if has_abom:
        edges.append({"edge": "HAS_ABOM", "from": artifact_version_id,
                      "to": artifact_version_id + "-abom"})
    graph = {"provenance_version": PROVENANCE_VERSION,
             "artifact_id": artifact_id, "tenant_id": tenant_id,
             "nodes": nodes, "edges": edges,
             "note": "Local Finalis provenance graph; not C2PA/SLSA/in-toto "
             "production attestation."}
    graph["provenance_hash"] = provenance_hash(graph)
    return graph


def provenance_hash(graph: dict) -> str:
    core = {k: v for k, v in graph.items() if k != "provenance_hash"}
    return _sha(core)


# --- Dependency / lineage graph --------------------------------------------
def build_dependency_graph(*, artifact_id, tenant_id, dependencies) -> dict:
    """`dependencies` is a list of {artifact_id, version_number, version_hash}."""
    graph = {"artifact_id": artifact_id, "tenant_id": tenant_id,
             "dependencies": [
                 {"artifact_id": d["artifact_id"],
                  "version_number": d.get("version_number"),
                  "version_hash": d.get("version_hash")}
                 for d in (dependencies or [])]}
    graph["dependency_graph_hash"] = dependency_graph_hash(graph)
    return graph


def dependency_graph_hash(graph: dict) -> str:
    core = {k: v for k, v in graph.items() if k != "dependency_graph_hash"}
    return _sha(core)


def build_lineage(*, artifact_id, tenant_id, task_id, run_id,
                  approval_request_id, evidence_refs, report_refs,
                  dependency_artifact_ids, supersedes_artifact_id,
                  is_tool_input, is_safe_view_of, quarantined_from,
                  decontaminated_from) -> dict:
    edges = []

    def add(kind, ref):
        if ref:
            edges.append({"lineage_type": kind, "ref": ref})
    add("CREATED_FROM_TASK", task_id)
    add("CREATED_FROM_RUN", run_id)
    add("CREATED_FROM_APPROVAL", approval_request_id)
    for ev in evidence_refs or []:
        add("REFERENCES_EVIDENCE", ev)
    for rep in report_refs or []:
        add("REFERENCES_REPORT", rep)
    for dep in dependency_artifact_ids or []:
        add("DERIVED_FROM_ARTIFACT", dep)
    add("SUPERSEDES_ARTIFACT", supersedes_artifact_id)
    if is_tool_input:
        add("PROPOSED_TOOL_INPUT", artifact_id)
    add("SAFE_VIEW_OF", is_safe_view_of)
    add("QUARANTINED_FROM", quarantined_from)
    add("DECONTAMINATED_FROM", decontaminated_from)
    graph = {"artifact_id": artifact_id, "tenant_id": tenant_id,
             "lineage_edges": edges}
    graph["artifact_lineage_hash"] = lineage_hash(graph)
    return graph


def lineage_hash(graph: dict) -> str:
    core = {k: v for k, v in graph.items() if k != "artifact_lineage_hash"}
    return _sha(core)


def detect_cycle(artifact_id: str, dependency_ids: list) -> bool:
    """A self-dependency is an obvious cycle. Deeper cycle detection over the
    stored graph happens at the endpoint layer where the full graph is known."""
    return artifact_id in (dependency_ids or [])


# --- Manifest --------------------------------------------------------------
def build_manifest(*, artifact_id, tenant_id, artifact_type, artifact_status,
                   artifact_trust_tier, task_id, run_id, approval_request_id,
                   approval_grant_id, created_by_actor_id, created_by_actor_type,
                   task_contract_hash, task_envelope_hash, task_state_hash,
                   run_state_hash, run_chain_hash, approval_grant_hash,
                   content_hash, version_hash, claim_graph_hash,
                   dependency_hashes, provenance_hash, abom_hash, evidence_refs,
                   report_refs, subject_refs, redaction_profile,
                   safe_view_available, quarantine_status,
                   materialization_status, retention_hint, legal_hold_hint):
    manifest = {
        "manifest_version": MANIFEST_VERSION, "artifact_id": artifact_id,
        "tenant_id": tenant_id, "artifact_type": artifact_type,
        "artifact_status": artifact_status,
        "artifact_trust_tier": artifact_trust_tier, "task_id": task_id,
        "run_id": run_id, "approval_request_id": approval_request_id,
        "approval_grant_id": approval_grant_id,
        "created_by_actor_id": created_by_actor_id,
        "created_by_actor_type": created_by_actor_type,
        "task_contract_hash": task_contract_hash,
        "task_envelope_hash": task_envelope_hash,
        "task_state_hash": task_state_hash, "run_state_hash": run_state_hash,
        "run_chain_hash": run_chain_hash, "approval_grant_hash":
        approval_grant_hash, "content_hash": content_hash,
        "version_hash": version_hash, "claim_graph_hash": claim_graph_hash,
        "dependency_hashes": list(dependency_hashes or []),
        "provenance_hash": provenance_hash, "abom_hash": abom_hash,
        "evidence_refs": list(evidence_refs or []),
        "report_refs": list(report_refs or []),
        "subject_refs": list(subject_refs or []),
        "redaction_profile": redaction_profile,
        "safe_view_available": bool(safe_view_available),
        "quarantine_status": quarantine_status,
        "materialization_status": materialization_status,
        "retention_hint": retention_hint, "legal_hold_hint": legal_hold_hint,
        "honesty_labels": HONESTY_LABELS,
    }
    manifest["manifest_hash"] = manifest_hash(manifest)
    return manifest


def manifest_hash(manifest: dict) -> str:
    # version_hash is excluded to break the manifest<->version hash cycle:
    # version_hash covers manifest_hash, so manifest_hash cannot cover
    # version_hash. Content/claim/provenance/dependency hashes ARE covered, so
    # any content or linkage change still changes the manifest hash.
    core = {k: v for k, v in manifest.items()
            if k not in ("manifest_hash", "honesty_labels", "version_hash")}
    return _sha(core)


# --- Version hashing -------------------------------------------------------
def version_hash(*, artifact_id, version_number, content_hash, manifest_hash,
                 claim_graph_hash, provenance_hash, abom_hash,
                 previous_version_hash, created_by_actor_id) -> str:
    return _sha({"artifact_id": artifact_id, "version_number": version_number,
                 "content_hash": content_hash, "manifest_hash": manifest_hash,
                 "claim_graph_hash": claim_graph_hash,
                 "provenance_hash": provenance_hash, "abom_hash": abom_hash,
                 "previous_version_hash": previous_version_hash or GENESIS,
                 "created_by_actor_id": created_by_actor_id})


def version_chain_hash(previous_chain: str, this_version_hash: str) -> str:
    return _sha({"previous_version_chain_hash": previous_chain or GENESIS,
                 "version_hash": this_version_hash})


# --- Policy capsule --------------------------------------------------------
def build_policy_capsule(*, artifact_id, tenant_id, task_id, run_id,
                         approval_request_id, approval_grant_id, artifact_type,
                         artifact_status, artifact_trust_tier, creator_actor_type,
                         creator_role, task_state, task_contract_hash,
                         task_envelope_hash, run_state_hash, approval_grant_hash,
                         requires_approval, requires_human_review,
                         requires_safe_view, allowed_for_completion,
                         allowed_for_tool_input, claims_required, blocked_reasons,
                         quarantine_reasons, required_reviews,
                         required_redactions, created_at) -> dict:
    policy_input = {
        "artifact_type": artifact_type, "artifact_trust_tier":
        artifact_trust_tier, "creator_actor_type": creator_actor_type,
        "creator_role": creator_role, "task_state": task_state,
        "requires_approval": bool(requires_approval),
        "requires_human_review": bool(requires_human_review),
        "claims_required": bool(claims_required),
    }
    policy_output = {
        "artifact_status": artifact_status,
        "artifact_requires_approval": bool(requires_approval),
        "artifact_requires_human_review": bool(requires_human_review),
        "artifact_requires_safe_view": bool(requires_safe_view),
        "artifact_allowed_for_completion": bool(allowed_for_completion),
        "artifact_allowed_for_tool_input": bool(allowed_for_tool_input),
        "artifact_allowed_for_external_export": False,
        "materialization_requires_tool_broker": artifact_type in
        TOOL_INPUT_TYPES,
        "blocked_reasons": list(blocked_reasons or []),
        "quarantine_reasons": list(quarantine_reasons or []),
        "required_reviews": list(required_reviews or []),
        "required_redactions": list(required_redactions or []),
    }
    capsule = {
        "artifact_policy_id": artifact_id + "-policy",
        "artifact_policy_version": POLICY_CAPSULE_VERSION, "tenant_id":
        tenant_id, "artifact_id": artifact_id, "task_id": task_id,
        "run_id": run_id, "approval_request_id": approval_request_id,
        "approval_grant_id": approval_grant_id, "task_contract_hash":
        task_contract_hash, "task_envelope_hash": task_envelope_hash,
        "run_state_hash": run_state_hash, "approval_grant_hash":
        approval_grant_hash, "artifact_claims_required": bool(claims_required),
        **policy_input, **policy_output,
        "policy_input_hash": _sha(policy_input),
        "policy_output_hash": _sha(policy_output), "created_at": created_at,
    }
    return capsule


def policy_capsule_hash(capsule: dict) -> str:
    core = {k: v for k, v in capsule.items()
            if k not in ("artifact_policy_capsule_hash", "created_at")}
    return _sha(core)


# --- Artifact state hash ---------------------------------------------------
def artifact_state_hash(*, artifact_id, tenant_id, artifact_type,
                        artifact_status, artifact_trust_tier, latest_version_id,
                        version_number, task_id, run_id, approval_request_id,
                        approval_grant_hash, task_contract_hash, content_hash,
                        manifest_hash, claim_graph_hash, provenance_hash,
                        abom_hash, dependency_graph_hash, lineage_hash,
                        quarantine_status, materialization_status,
                        version_chain_hash) -> str:
    return _sha({
        "artifact_id": artifact_id, "tenant_id": tenant_id,
        "artifact_type": artifact_type, "artifact_status": artifact_status,
        "artifact_trust_tier": artifact_trust_tier,
        "latest_version_id": latest_version_id, "version_number": version_number,
        "task_id": task_id, "run_id": run_id, "approval_request_id":
        approval_request_id, "approval_grant_hash": approval_grant_hash,
        "task_contract_hash": task_contract_hash, "content_hash": content_hash,
        "manifest_hash": manifest_hash, "claim_graph_hash": claim_graph_hash,
        "provenance_hash": provenance_hash, "abom_hash": abom_hash,
        "dependency_graph_hash": dependency_graph_hash, "lineage_hash":
        lineage_hash, "quarantine_status": quarantine_status,
        "materialization_status": materialization_status,
        "version_chain_hash": version_chain_hash})


# --- Safe view / redaction -------------------------------------------------
_SECRET_PATTERNS = [
    ("sk-", "api_key"), ("bearer ", "bearer_token"),
    ("-----begin", "private_key"), ("password=", "password"),
    ("api_key=", "api_key"), ("token=", "token"), ("secret=", "secret"),
    ("aws_secret", "aws_secret"), ("ssh-rsa", "ssh_key"),
]
SAFE_VIEW_OMITTED = ["content_body", "raw_untrusted_input", "policy_input"]


def redact_content(content_body: str, *, restricted: bool) -> tuple:
    """Return (safe_text, redaction_notes). Redacts secrets/tokens/keys; for
    restricted roles also masks tool-like instructions. Never mutates the
    original content."""
    text = content_body or ""
    notes = []
    lower = text.lower()
    for needle, kind in _SECRET_PATTERNS:
        if needle in lower:
            notes.append(f"redacted:{kind}")
    redacted = "[REDACTED — sensitive content omitted from safe view]" \
        if notes else text
    if restricted:
        scan = scan_content(text)
        if any(scan[k] for k in ("prompt_injection_flags",
                                 "tool_poisoning_flags",
                                 "data_exfiltration_flags",
                                 "unsafe_content_flags")):
            redacted = "[REDACTED — tool-like / unsafe instructions hidden " \
                "from restricted role]"
            notes.append("redacted:tool_like_instructions")
    return redacted, sorted(set(notes))


def build_safe_view(artifact: dict, version: dict, *, restricted: bool) -> dict:
    env = version.get("content_envelope", {})
    # A quarantined artifact's raw content is treated as unsafe for EVERY
    # viewer: force the restricted-role redaction so a known-poisoned payload
    # is never surfaced verbatim in the safe view.
    force = restricted or artifact.get("quarantine_status") == "QUARANTINED" \
        or artifact.get("artifact_status") == "QUARANTINED"
    safe_text, notes = redact_content(env.get("content_body", ""),
                                      restricted=force)
    manifest = {"omitted_fields": sorted(SAFE_VIEW_OMITTED),
                "redaction_notes": notes, "restricted_role": restricted,
                "note": "Safe artifact view may omit sensitive fields; omitted "
                "fields do not change server-side artifact truth. Safe artifact "
                "view is not a separate artifact."}
    view = {
        "artifact_id": artifact["artifact_id"],
        "artifact_type": artifact["artifact_type"],
        "artifact_status": artifact["artifact_status"],
        "artifact_trust_tier": artifact["artifact_trust_tier"],
        "artifact_title": artifact.get("artifact_title"),
        "safe_content": safe_text, "content_format": env.get("content_format"),
        "redaction_manifest": manifest,
        "redaction_manifest_hash": _sha(manifest),
        "quarantine_status": artifact.get("quarantine_status"),
        "unsupported_claim_count": artifact.get("unsupported_claim_count", 0),
        "ai_draft": artifact["artifact_trust_tier"] in (
            "AI_DRAFT_UNVERIFIED",),
        "honesty_labels": HONESTY_LABELS,
    }
    view["artifact_safe_view_hash"] = _sha({k: v for k, v in view.items()
                                            if k != "artifact_safe_view_hash"
                                            and k != "honesty_labels"})
    return view


# --- Materialization policy (validation-only) ------------------------------
def materialization_check(artifact: dict, *, claims_supported: bool,
                          approval_valid: bool) -> dict:
    """Validation-only readiness for FUTURE use. Executes nothing, sends
    nothing, calls no Tool Broker / LLM / external provider."""
    atype = artifact["artifact_type"]
    status = artifact["artifact_status"]
    reasons = []
    if atype in FORBIDDEN_TYPES or atype == "NOT_IMPLEMENTED_PLACEHOLDER":
        mat = "MATERIALIZATION_NOT_IMPLEMENTED"
        reasons.append(f"artifact type {atype} is not implemented")
    elif artifact.get("quarantine_status") == "QUARANTINED" \
            or status == "QUARANTINED":
        mat = "MATERIALIZATION_BLOCKED"
        reasons.append("quarantined artifact cannot be materialized")
    elif status in ("BLOCKED", "TAMPERED"):
        mat = "MATERIALIZATION_BLOCKED"
        reasons.append(f"artifact status {status} blocks materialization")
    elif atype in TOOL_INPUT_TYPES:
        mat = "MATERIALIZATION_REQUIRES_TOOL_BROKER"
        reasons.append("execution requires a future Tool Broker (not "
                       "implemented)")
    elif atype in APPROVAL_REQUIRED_TYPES and not approval_valid:
        mat = "MATERIALIZATION_REQUIRES_APPROVAL"
        reasons.append("a valid human approval grant is required")
    elif artifact.get("claims_required") and not claims_supported:
        mat = "MATERIALIZATION_BLOCKED"
        reasons.append("required claims are unsupported")
    else:
        mat = "MATERIALIZATION_ALLOWED_FOR_INTERNAL_REVIEW"
    return {"materialization_status": mat, "can_execute_now": False,
            "tool_broker_required": atype in TOOL_INPUT_TYPES,
            "reasons": reasons,
            "materialization_policy_hash": _sha({"type": atype,
                                                 "status": status, "mat": mat}),
            "honesty_labels": HONESTY_LABELS}


# --- Trust tier derivation -------------------------------------------------
def default_trust_tier(artifact_type: str, actor_type: str) -> str:
    # Fail-closed: only an explicit human creator may receive a non-AI-draft
    # tier. Any non-human / unknown actor_type is AI_DRAFT_UNVERIFIED and can
    # never be treated as human-verified truth.
    if actor_type != "human":
        return "AI_DRAFT_UNVERIFIED"
    if artifact_type in ("SAFE_VIEW_SNAPSHOT",):
        return "SAFE_REDACTED"
    if artifact_type in ("RUN_TRACE_SUMMARY", "CLAIM_GRAPH_SUMMARY",
                         "ARTIFACT_BOM", "POLICY_DECISION_SUMMARY"):
        return "SYSTEM_GENERATED_DETERMINISTIC"
    if artifact_type in ("EVIDENCE_REPORT_REFERENCE",
                         "CONTRACT_DRAFT_REFERENCE"):
        return "REFERENCE_ONLY"
    return "HUMAN_REVIEW_REQUIRED"
