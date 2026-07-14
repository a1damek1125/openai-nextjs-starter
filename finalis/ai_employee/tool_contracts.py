"""Finalis ViktorAI Formal Protocol Contract Proof Kernel (TOOL-B3).

A security-first internal protocol contract module over the TOOL-B1 registry and
TOOL-B2 quality gate. It normalizes an admitted, quality-passed tool descriptor
into an internal CONTRACT and produces validation-only PROJECTIONS
(MCP-like / Apps-SDK-like / OpenAPI-like / safe planner / human-review /
trace-only) as safe, non-executable, hash-verifiable, scope-bound artifacts that
prepare a FUTURE Tool Broker.

It executes NOTHING and implements NO protocol runtime: no MCP server/client, no
tool execution, no Tool Broker call, no LLM/external provider, no OAuth/token
issuance, no sampling, no elicitation, no resource/prompt serving, no network
side effect. All runtime capabilities are DENIED. Internal Finalis truth is
authoritative; a protocol projection is a derived view and can never lower risk,
hide a side effect, remove approval/consent, mislabel a write tool read-only,
expand scope, pass a token, or override any TOOL-B1/TOOL-B2 security state.
"""
from __future__ import annotations

import hashlib
import json

from . import tool_registry as _tr

CONTRACT_MODEL_VERSION = "finalis-tool-contract-v1"
NORMAL_FORM_VERSION = "finalis-contract-normal-form-v1"
ABI_VERSION = "finalis-contract-abi-v1"
EFFECT_TRACE_VERSION = "finalis-effect-trace-semantics-v1"
DEONTIC_LEDGER_VERSION = "finalis-deontic-obligation-ledger-v1"
PROOF_BUNDLE_VERSION = "finalis-contract-proof-bundle-v1"
BROKER_CERT_VERSION = "finalis-broker-readiness-certificate-v1"
METHOD_FIREWALL_VERSION = "finalis-protocol-method-firewall-v1"
DIALECT_MATRIX_VERSION = "finalis-protocol-dialect-matrix-v1"
CAP_NEG_VERSION = "finalis-capability-negotiation-boundary-v1"
SEPARATION_VERSION = "finalis-separation-guard-v1"
DENY_GRAPH_VERSION = "finalis-runtime-capability-deny-graph-v1"
SCOPE_BINDING_VERSION = "finalis-scope-binding-v1"
AUTH_ENVELOPE_VERSION = "finalis-auth-context-envelope-v1"
DATA_BOUNDARY_VERSION = "finalis-data-boundary-v1"
EFFECT_BOUNDARY_VERSION = "finalis-effect-boundary-v1"
PROMPT_BOUNDARY_VERSION = "finalis-prompt-context-boundary-v1"
TRACEABILITY_VERSION = "finalis-traceability-envelope-v1"
PROJECTION_ENVELOPE_VERSION = "finalis-projection-envelope-v1"
NON_INTERFERENCE_VERSION = "finalis-non-interference-matrix-v1"
COMPAT_REPORT_VERSION = "finalis-compatibility-report-v1"
CONTRACT_EVENT_VERSION = "finalis-contract-event-v1"
GENESIS = "0" * 64

# --- Effect-trace vocabulary -----------------------------------------------
EFFECT_CLASSES = {
    "NO_EFFECT", "READ_LOCAL_STATE", "READ_CUSTOMER_DATA", "READ_EVIDENCE_DATA",
    "READ_ARTIFACT_DATA", "WRITE_LOCAL_STATE", "CUSTOMER_VISIBLE_WRITE",
    "PAYMENT_RELATED_EFFECT", "EVIDENCE_MUTATION", "CONSENT_MUTATION",
    "ADMIN_PERMISSION_EFFECT", "SECRET_ACCESS", "EXTERNAL_NETWORK_EFFECT",
    "EXTERNAL_PROVIDER_EFFECT", "DATA_EXPORT_EFFECT", "TOOL_BROKER_CALL_EFFECT",
    "LLM_CALL_EFFECT", "MCP_RUNTIME_EFFECT", "NOT_IMPLEMENTED_EFFECT",
}
# Effects that are always FORBIDDEN in B3 (runtime / dangerous).
FORBIDDEN_EFFECTS = {
    "PAYMENT_RELATED_EFFECT", "EVIDENCE_MUTATION", "CONSENT_MUTATION",
    "ADMIN_PERMISSION_EFFECT", "SECRET_ACCESS", "EXTERNAL_PROVIDER_EFFECT",
    "DATA_EXPORT_EFFECT", "TOOL_BROKER_CALL_EFFECT", "LLM_CALL_EFFECT",
    "MCP_RUNTIME_EFFECT",
}

# --- Runtime capabilities to deny ------------------------------------------
RUNTIME_CAPABILITIES = [
    "MCP_SERVER_RUNTIME", "MCP_CLIENT_RUNTIME", "MCP_TOOL_EXECUTION",
    "MCP_RESOURCE_SERVING", "MCP_PROMPT_SERVING", "MCP_SAMPLING",
    "MCP_ELICITATION", "OAUTH_TOKEN_ISSUANCE", "PROVIDER_CALL", "LLM_CALL",
    "TOOL_BROKER_CALL", "CUSTOMER_MESSAGE_SEND", "PAYMENT_EXECUTION",
    "EVIDENCE_MUTATION", "CRM_MUTATION", "DATA_EXPORT", "SECRET_ACCESS",
    "NETWORK_SIDE_EFFECT",
]

# --- Protocol method classes -----------------------------------------------
METHOD_CLASSES = {
    "TOOL_DESCRIPTOR", "RESOURCE_DESCRIPTOR", "PROMPT_DESCRIPTOR",
    "SAMPLING_REQUEST", "ELICITATION_REQUEST", "ROOTS_DECLARATION",
    "AUTHORIZATION_FLOW", "PROGRESS_NOTIFICATION", "LOGGING_NOTIFICATION",
    "CANCELLATION_SIGNAL", "ERROR_SIGNAL", "NOT_IMPLEMENTED_METHOD",
}
ALLOWED_METHOD_CLASSES = {"TOOL_DESCRIPTOR"}
# Method classes that name a runtime feature B3 must never enable.
RUNTIME_METHOD_CLASSES = {"SAMPLING_REQUEST", "ELICITATION_REQUEST",
                          "RESOURCE_DESCRIPTOR", "PROMPT_DESCRIPTOR",
                          "ROOTS_DECLARATION"}

# --- Protocol dialects -----------------------------------------------------
DIALECTS = {
    "INTERNAL_BROKER_DRAFT", "MCP_2025_06_18_LIKE", "MCP_2025_11_25_LIKE",
    "MCP_DRAFT_LIKE_READ_ONLY", "OPENAI_APPS_SDK_LIKE", "OPENAPI_3_1_LIKE",
    "OPENAPI_3_2_LIKE", "TRACE_ONLY", "SAFE_PLANNER_SUMMARY",
    "NOT_IMPLEMENTED_DIALECT",
}

# --- Projection targets ----------------------------------------------------
PROJECTION_TARGETS = {
    "INTERNAL_TOOL_BROKER_CONTRACT", "MCP_LIKE_TOOL_DESCRIPTOR",
    "OPENAI_APPS_SDK_LIKE_DESCRIPTOR", "OPENAPI_LIKE_SCHEMA_CONTRACT",
    "SAFE_PLANNER_SUMMARY", "SAFE_HUMAN_REVIEW_VIEW", "TRACE_ONLY_CONTRACT",
}
# Targets that will feed a future MODEL context (planner-facing).
MODEL_FACING_TARGETS = {"MCP_LIKE_TOOL_DESCRIPTOR",
                        "OPENAI_APPS_SDK_LIKE_DESCRIPTOR",
                        "SAFE_PLANNER_SUMMARY"}

# --- Taint labels ----------------------------------------------------------
TAINT_LABELS = {
    "SAFE_INTERNAL", "SAFE_FOR_HUMAN_REVIEW", "SAFE_FOR_FUTURE_PLANNER_SUMMARY",
    "UNTRUSTED_DESCRIPTOR_TEXT", "REDACTED", "NEVER_EXPOSE_TO_MODEL",
    "SECURITY_SENSITIVE", "SCOPE_SENSITIVE", "AUTH_SENSITIVE", "SECRET_LIKE",
    "POISONING_SUSPECTED", "PROTOCOL_SENSITIVE", "RUNTIME_FORBIDDEN",
    "AMBIENT_AUTHORITY_RISK", "CROSS_PROJECTION_RISK", "EFFECT_TRACE_SENSITIVE",
    "OBLIGATION_SENSITIVE",
}
MODEL_UNSAFE_TAINTS = {"NEVER_EXPOSE_TO_MODEL", "SECRET_LIKE",
                       "POISONING_SUSPECTED", "RUNTIME_FORBIDDEN",
                       "AMBIENT_AUTHORITY_RISK"}

DEONTIC_CLASSES = {"PERMITTED", "FORBIDDEN", "REQUIRED", "DISPENSATION_SLOT",
                   "NOT_IMPLEMENTED"}

# --- Contract / projection statuses ----------------------------------------
CONTRACT_STATUSES = {
    "CONTRACTED", "PROJECTABLE_FOR_FUTURE", "NEEDS_REVIEW", "BLOCKED",
    "QUARANTINED", "STALE", "REVOKED", "TAMPERED", "NOT_IMPLEMENTED",
}
PROJECTION_STATUSES = {
    "PROJECTABLE_FOR_FUTURE", "PROJECTED_SAFE_SUMMARY_ONLY", "NEEDS_REVIEW",
    "BLOCKED", "QUARANTINED", "STALE", "REVOKED", "TAMPERED", "NOT_IMPLEMENTED",
}

# Hard-fail dominance, most dominant first.
FAILURE_DOMINANCE = [
    "TAMPERED", "REVOKED", "CROSS_TENANT", "STALE_SOURCE", "TOOL_B1_BLOCKED",
    "TOOL_B2_BLOCKED", "QUALITY_FAIL", "PROMPT_CONTEXT_BLOCKED",
    "PROTOCOL_METHOD_VIOLATION", "PROTOCOL_BOUNDARY_VIOLATION",
    "SAMPLING_ELICITATION_VIOLATION", "RUNTIME_CAPABILITY_DENIED",
    "EFFECT_TRACE_MISSING", "PROOF_OBLIGATION_FAILED", "RISK_DOWNGRADE",
    "SIDE_EFFECT_DOWNGRADE", "READONLY_MISLABEL", "METADATA_POISONING",
    "CROSS_PROJECTION_INTERFERENCE", "SCOPE_EXPANSION", "TOKEN_PASSTHROUGH",
    "IMPLICIT_NETWORK", "NEEDS_REVIEW",
]
_FAILURE_TO_STATUS = {
    "TAMPERED": "TAMPERED", "REVOKED": "REVOKED", "CROSS_TENANT": "BLOCKED",
    "STALE_SOURCE": "STALE", "TOOL_B1_BLOCKED": "BLOCKED",
    "TOOL_B2_BLOCKED": "BLOCKED", "QUALITY_FAIL": "BLOCKED",
    "PROMPT_CONTEXT_BLOCKED": "BLOCKED",
    "PROTOCOL_METHOD_VIOLATION": "BLOCKED",
    "PROTOCOL_BOUNDARY_VIOLATION": "BLOCKED",
    "SAMPLING_ELICITATION_VIOLATION": "BLOCKED",
    "RUNTIME_CAPABILITY_DENIED": "BLOCKED", "EFFECT_TRACE_MISSING": "BLOCKED",
    "PROOF_OBLIGATION_FAILED": "BLOCKED", "RISK_DOWNGRADE": "BLOCKED",
    "SIDE_EFFECT_DOWNGRADE": "BLOCKED", "READONLY_MISLABEL": "BLOCKED",
    "METADATA_POISONING": "QUARANTINED",
    "CROSS_PROJECTION_INTERFERENCE": "BLOCKED", "SCOPE_EXPANSION": "BLOCKED",
    "TOKEN_PASSTHROUGH": "BLOCKED", "IMPLICIT_NETWORK": "BLOCKED",
    "NEEDS_REVIEW": "NEEDS_REVIEW",
}
# TOOL-B1 statuses that forbid any projection.
_B1_SECURITY_BLOCKED = {
    "QUARANTINED", "TAMPERED", "RUG_PULL_DETECTED", "DRIFT_DETECTED",
    "FORBIDDEN_CAPABILITY", "CROSS_TENANT_REJECTED", "BLOCKED", "DISABLED",
    "DEPRECATED", "SUPERSEDED", "NOT_IMPLEMENTED",
}
_B2_QUALITY_OK = {"QUALITY_PASS", "QUALITY_PASS_WITH_WARNINGS"}

HONESTY_LABELS = [
    "Internal contract does not execute tools.",
    "Projection does not mean executable.",
    "Broker-readiness certificate does not execute tools.",
    "Future Tool Broker is required before any tool call.",
    "MCP-like projection is internal future-readiness metadata only.",
    "Apps-SDK-like projection is internal future-readiness metadata only.",
    "OpenAPI-like projection is internal future-readiness metadata only.",
    "This is not an MCP server or client.",
    "This is not OpenAI Apps SDK runtime integration.",
    "No OAuth/token issuance is implemented.",
    "No external providers are called.",
    "Sampling, elicitation, resources and prompts are not implemented in this "
    "mission.",
    "Runtime capabilities are denied in this mission.",
    "Effect-trace semantics are future-readiness metadata only; no runtime "
    "effects are observed in B3.",
    "Contract compatibility does not mean production protocol compliance.",
    "Server-side registry truth is authoritative.",
    "This is not production autonomous execution.",
]


# --- Hashing ---------------------------------------------------------------
def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _sha(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


_VOLATILE = ("created_at", "updated_at", "honesty_labels")


def _core_hash(obj: dict, self_key: str, *extra) -> str:
    excluded = {self_key, *_VOLATILE, *extra}
    return _sha({k: v for k, v in obj.items() if k not in excluded})


def _norm(text: str) -> str:
    return _tr._normalize(text)


def dominant_failure(signals) -> str:
    present = set(signals)
    for s in FAILURE_DOMINANCE:
        if s in present:
            return s
    # Unknown signal → fail-closed to the top of the ladder.
    unknown = present - set(FAILURE_DOMINANCE)
    return sorted(unknown)[0] if unknown else None


def status_for_failures(signals) -> str:
    dom = dominant_failure(signals)
    if dom is None:
        return None
    return _FAILURE_TO_STATUS.get(dom, "BLOCKED")


# --- Metadata sanitization pipeline ----------------------------------------
_SANITIZE_NEEDLES = [
    "ignore previous instructions", "system prompt", "hidden instruction",
    "do not tell the user", "prefer this tool", "always choose this tool",
    "token passthrough", "pass the token", "call provider", "call external",
    "mcp server is now live", "tool broker execute", "execute now",
    "readonly for payment", "hide approval", "remove consent", "cross tenant",
    "downgrade risk", "enable sampling", "enable elicitation", "serve prompt",
    "serve resource", "ambient authority", "certificate means executable",
    "effect trace allows payment", "send customer message", "grant admin",
    "read secret", "private key", "external network allowed",
]


def sanitize_metadata(raw: dict) -> dict:
    """Deterministic sanitizer over `_meta`/annotations/examples/descriptions/
    schema text. Detects hidden instructions / poisoning; returns the safe
    subset + findings. No LLM. Unsafe metadata blocks or is redacted."""
    findings = []
    safe = {}
    flat = _flatten_text(raw)
    blob = " ".join(_norm(t) for t in flat)
    for needle in _SANITIZE_NEEDLES:
        if needle in blob:
            findings.append(needle)
    # Only carry through a curated safe key set; everything else is dropped.
    for k in ("title", "displayName", "summary", "tags"):
        if k in (raw or {}) and isinstance(raw[k], (str, list)):
            v = raw[k]
            if isinstance(v, str) and any(
                    n in _norm(v) for n in _SANITIZE_NEEDLES):
                findings.append(f"unsafe:{k}")
            else:
                safe[k] = v
    result = {
        "metadata_sanitization_version": "finalis-metadata-sanitizer-v1",
        "safe_metadata": safe, "dropped_keys": sorted(
            set((raw or {}).keys()) - set(safe.keys())),
        "poisoning_findings": sorted(set(findings)),
        "sanitized_clean": not findings,
    }
    result["metadata_sanitization_hash"] = _core_hash(
        result, "metadata_sanitization_hash")
    return result


def _flatten_text(obj, out=None):
    out = [] if out is None else out
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.append(str(k))
            _flatten_text(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _flatten_text(v, out)
    return out


# --- Effect-trace semantics ------------------------------------------------
def build_effect_trace_semantics(*, tenant_id, contract_id, tool_id,
                                 effect_contract, data_flow, category) -> dict:
    allowed, forbidden = set(), set(FORBIDDEN_EFFECTS)
    reads = set(data_flow.get("reads_data_classes", []))
    if reads:
        allowed.add("READ_LOCAL_STATE")
    if reads & {"PII", "SENSITIVE_PII"}:
        allowed.add("READ_CUSTOMER_DATA")
    if reads & {"EVIDENCE"}:
        allowed.add("READ_EVIDENCE_DATA")
    se = effect_contract.get("side_effect_class")
    rank = effect_contract.get("side_effect_rank", 0)
    if se == "PURE_READ":
        if not allowed:
            allowed.add("NO_EFFECT")
    elif rank >= _tr.SIDE_EFFECT_RANK["INTERNAL_WRITE"]:
        allowed.add("WRITE_LOCAL_STATE")
    # Any dangerous declared effect is recorded as forbidden-for-B3 (future
    # broker territory), never allowed here.
    sem = {
        "effect_trace_semantics_version": EFFECT_TRACE_VERSION,
        "tenant_id": tenant_id, "contract_id": contract_id, "tool_id": tool_id,
        "allowed_effects": sorted(allowed),
        "forbidden_effects": sorted(forbidden),
        "required_effect_boundaries": ["future broker must observe declared "
                                       "effects before execution"],
        "observable_effect_assumption": "B3 observes NO runtime effects; these "
        "are declared future boundaries only",
        "mediated_effect_boundary": "all effects mediated by a future Tool "
        "Broker; none mediated here",
        "effect_trace_status": "MATCHED" if allowed else "NOT_IMPLEMENTED",
    }
    sem["effect_trace_semantics_hash"] = _core_hash(
        sem, "effect_trace_semantics_hash")
    return sem


# --- Runtime capability deny graph -----------------------------------------
def build_deny_graph(*, tenant_id, contract_id, tool_id) -> dict:
    nodes = [{"node": "CONTRACT", "id": contract_id}]
    edges = []
    for cap in RUNTIME_CAPABILITIES:
        nodes.append({"node": "RUNTIME_CAPABILITY", "id": cap})
        edges.append({"from": contract_id, "to": cap, "type": "DENIES"})
    graph = {
        "runtime_capability_deny_graph_id": contract_id + "-deny",
        "runtime_capability_deny_graph_version": DENY_GRAPH_VERSION,
        "tenant_id": tenant_id, "contract_id": contract_id, "tool_id": tool_id,
        "nodes": nodes, "edges": edges,
        "denied_capabilities": list(RUNTIME_CAPABILITIES),
        "deny_graph_status": "MATCHED",
    }
    graph["deny_graph_hash"] = _core_hash(graph, "deny_graph_hash")
    return graph


# --- Protocol method firewall ----------------------------------------------
_METHOD_TERMS = {
    "RESOURCE_DESCRIPTOR": ["resource", "resources"],
    "PROMPT_DESCRIPTOR": ["prompt template", "serve prompt", "prompt server"],
    "SAMPLING_REQUEST": ["sampling", "sample completion", "createmessage"],
    "ELICITATION_REQUEST": ["elicit", "elicitation"],
    "ROOTS_DECLARATION": ["roots", "filesystem root"],
}


def build_method_firewall(*, tenant_id, contract_id, tool_id, descriptor,
                          runtime_requested) -> dict:
    blob = _norm(descriptor.get("tool_description", "") + " "
                 + descriptor.get("tool_summary", ""))
    confusion = []
    for cls, terms in sorted(_METHOD_TERMS.items()):
        if any(t in blob for t in terms):
            confusion.append(cls)
    status = "MATCHED"
    if runtime_requested:
        status = "BLOCKED"
    elif confusion:
        status = "NEEDS_REVIEW"
    fw = {
        "protocol_method_firewall_version": METHOD_FIREWALL_VERSION,
        "tenant_id": tenant_id, "contract_id": contract_id, "tool_id": tool_id,
        "declared_method_class": "TOOL_DESCRIPTOR",
        "allowed_method_classes": sorted(ALLOWED_METHOD_CLASSES),
        "blocked_method_classes": sorted(METHOD_CLASSES - ALLOWED_METHOD_CLASSES),
        "detected_method_confusion": sorted(confusion),
        "runtime_method_requested": bool(runtime_requested),
        "method_firewall_status": status,
    }
    fw["method_firewall_hash"] = _core_hash(fw, "method_firewall_hash")
    return fw


# --- Resource/prompt/tool separation guard ---------------------------------
def build_separation_guard(*, tenant_id, contract_id, tool_id, descriptor,
                           declared_kind) -> dict:
    blob = _norm(descriptor.get("tool_description", "") + " "
                 + descriptor.get("tool_summary", ""))

    def terms(words):
        return sorted(w for w in words if w in blob)
    res = terms(["resource", "resources"])
    prm = terms(["prompt", "prompts"])
    tool = terms(["tool", "function", "action"])
    samp = terms(["sampling", "sample"])
    elic = terms(["elicit", "elicitation"])
    roots = terms(["roots", "root directory"])
    confusion = declared_kind != "TOOL_CONTRACT" or bool(samp or elic or roots)
    status = ("BLOCKED" if (samp or elic or roots)
              else ("NEEDS_REVIEW" if confusion else "MATCHED"))
    guard = {
        "separation_guard_version": SEPARATION_VERSION, "tenant_id": tenant_id,
        "contract_id": contract_id, "tool_id": tool_id,
        "declared_kind": declared_kind, "detected_resource_terms": res,
        "detected_prompt_terms": prm, "detected_tool_terms": tool,
        "detected_sampling_terms": samp, "detected_elicitation_terms": elic,
        "detected_roots_terms": roots, "kind_confusion_detected": confusion,
        "separation_guard_status": status,
    }
    guard["separation_guard_hash"] = _core_hash(guard, "separation_guard_hash")
    return guard


# --- Capability negotiation boundary ---------------------------------------
def build_capability_negotiation(*, tenant_id, contract_id, tool_id,
                                 runtime_requested) -> dict:
    cap = {
        "capability_negotiation_boundary_version": CAP_NEG_VERSION,
        "tenant_id": tenant_id, "contract_id": contract_id, "tool_id": tool_id,
        "declared_future_server_features": ["tools"],
        "declared_future_client_features": [],
        "tools_feature_allowed_for_future": True,
        "resources_feature_allowed_for_future": False,
        "prompts_feature_allowed_for_future": False,
        "sampling_feature_allowed_for_future": False,
        "elicitation_feature_allowed_for_future": False,
        "roots_feature_allowed_for_future": False,
        "runtime_negotiation_performed": False,
        "capability_boundary_status": "BLOCKED" if runtime_requested
        else "MATCHED",
    }
    cap["capability_negotiation_boundary_hash"] = _core_hash(
        cap, "capability_negotiation_boundary_hash")
    return cap


# --- Protocol dialect matrix -----------------------------------------------
def build_dialect_matrix(*, tenant_id, contract_id, tool_id) -> dict:
    supported = ["INTERNAL_BROKER_DRAFT", "MCP_2025_06_18_LIKE",
                 "MCP_2025_11_25_LIKE", "MCP_DRAFT_LIKE_READ_ONLY",
                 "OPENAI_APPS_SDK_LIKE", "OPENAPI_3_1_LIKE", "OPENAPI_3_2_LIKE",
                 "TRACE_ONLY", "SAFE_PLANNER_SUMMARY"]
    m = {
        "protocol_dialect_matrix_version": DIALECT_MATRIX_VERSION,
        "tenant_id": tenant_id, "contract_id": contract_id, "tool_id": tool_id,
        "supported_dialects": supported,
        "blocked_dialects": ["NOT_IMPLEMENTED_DIALECT"],
        "dialect_feature_flags": {"runtime": False, "tools_only": True},
        "dialect_boundary_rules": ["dialect labels are internal future-ready "
                                   "only; no compliance claimed",
                                   "no dialect enables runtime features"],
        "protocol_version_notes": "MCP 2025-06-18 / 2025-11-25 shapes referenced "
        "as internal-like only; not compliance-tested",
    }
    m["protocol_dialect_matrix_hash"] = _core_hash(
        m, "protocol_dialect_matrix_hash")
    return m


# --- Scope binding + calculus ----------------------------------------------
def build_scope_binding(*, tenant_id, tool_id, tool_version_id, contract_id,
                        head, data_flow, requires_approval,
                        requires_consent) -> dict:
    source_scope = sorted(set(data_flow.get("reads_data_classes", []))
                          | set(data_flow.get("writes_data_classes", []))
                          | {f"tenant:{tenant_id}", f"category:{head['category']}"})
    binding = {
        "scope_binding_version": SCOPE_BINDING_VERSION, "tenant_id": tenant_id,
        "tool_id": tool_id, "tool_version_id": tool_version_id,
        "contract_id": contract_id, "source_scope_set": source_scope,
        "projected_scope_set": source_scope,          # projection == source
        "allowed_actor_types": ["human", "ai_employee"],
        "allowed_roles": ["owner", "manager", "operator"],
        "required_permissions": ["case.read"],
        "required_tenant_scope": tenant_id, "required_subject_scope": "case",
        "required_task_scope": "future-broker-task",
        "required_artifact_scope": [],
        "required_data_scopes": sorted(data_flow.get("reads_data_classes", [])),
        "forbidden_data_scopes": sorted(_tr.EGRESS_FORBIDDEN_DATA),
        "required_effect_scopes": [head["side_effect_class"]],
        "forbidden_effect_scopes": sorted(_tr.FORBIDDEN_SIDE_EFFECTS),
        "required_approval_scope": bool(requires_approval),
        "required_consent_scope": bool(requires_consent),
        "requires_human_review": head["risk_class"] in ("HIGH", "CRITICAL",
                                                         "PROHIBITED"),
        "requires_future_tool_broker": True, "cross_tenant_allowed": False,
        "scope_expansion_detected": False, "scope_binding_status": "MATCHED",
    }
    binding["scope_binding_hash"] = _core_hash(binding, "scope_binding_hash")
    return binding


def scope_is_subset(projected, source) -> bool:
    return set(projected).issubset(set(source))


# --- Auth context envelope -------------------------------------------------
def build_auth_envelope(*, tenant_id, tool_id, contract_id, head,
                        requires_approval, requires_consent) -> dict:
    env = {
        "auth_context_envelope_version": AUTH_ENVELOPE_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id, "contract_id": contract_id,
        "required_actor_type": "human", "required_roles": ["owner", "manager"],
        "required_permissions": ["case.read"],
        "required_approval_grant": bool(requires_approval),
        "required_consent_check": bool(requires_consent),
        "required_subject_binding": True, "required_audience_binding": True,
        "required_resource_binding": True,
        "caller_binding_future_slot": "REQUIRED_BEFORE_FUTURE_EXECUTION",
        "principal_binding_future_slot": "REQUIRED_BEFORE_FUTURE_EXECUTION",
        "token_passthrough_allowed": False,
        "oauth_required_future_slot": "NOT_IMPLEMENTED",
        "mcp_authorization_future_slot": "NOT_IMPLEMENTED",
        "apps_sdk_auth_future_slot": "NOT_IMPLEMENTED",
        "confused_deputy_prechecks": ["bind caller", "bind subject",
                                      "bind audience", "bind resource",
                                      "bind tenant", "bind scope",
                                      "require approval"],
        "ambient_authority_allowed": False,
    }
    env["auth_context_envelope_hash"] = _core_hash(
        env, "auth_context_envelope_hash")
    return env


# --- Data / effect / prompt-context boundaries -----------------------------
def build_data_boundary(*, tenant_id, tool_id, contract_id, data_flow) -> dict:
    reads = sorted(data_flow.get("reads_data_classes", []))
    writes = sorted(data_flow.get("writes_data_classes", []))
    b = {
        "data_boundary_version": DATA_BOUNDARY_VERSION, "tenant_id": tenant_id,
        "tool_id": tool_id, "contract_id": contract_id,
        "input_data_classes": reads, "output_data_classes": writes,
        "allowed_data_scopes": reads,
        "forbidden_data_scopes": sorted(_tr.EGRESS_FORBIDDEN_DATA),
        "customer_data_allowed": bool(set(reads) & {"PII", "SENSITIVE_PII"}),
        "evidence_data_allowed": "EVIDENCE" in reads,
        "payment_data_allowed": "PAYMENT_DATA" in reads,
        "secret_data_allowed": False, "cross_tenant_data_allowed": False,
        "data_export_allowed": False,
        "artifact_input_allowed": True, "artifact_output_declared": bool(writes),
        "unsafe_output_to_input_path_detected": bool(
            data_flow.get("exfiltration_hazard")),
    }
    b["data_boundary_hash"] = _core_hash(b, "data_boundary_hash")
    return b


def build_effect_boundary(*, tenant_id, tool_id, contract_id, effect_contract,
                          descriptor) -> dict:
    se = effect_contract.get("side_effect_class")
    blob = _norm(descriptor.get("tool_description", ""))
    read_only_claimed = ("read only" in blob or "readonly" in blob
                         or "read-only" in blob)
    writes = se != "PURE_READ"
    mislabel = read_only_claimed and (
        writes or effect_contract.get("touches_external")
        or effect_contract.get("touches_payment")
        or effect_contract.get("touches_customer"))
    b = {
        "effect_boundary_version": EFFECT_BOUNDARY_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id, "contract_id": contract_id,
        "side_effect_class": se, "read_only_claimed": read_only_claimed,
        "writes_local_state": writes,
        "writes_external_state": bool(effect_contract.get("touches_external")),
        "customer_visible": bool(effect_contract.get("touches_customer")),
        "payment_related": bool(effect_contract.get("touches_payment")),
        "evidence_mutating": bool(effect_contract.get("touches_evidence")),
        "consent_mutating": False,
        "admin_mutating": False, "security_sensitive": se
        in _tr.FORBIDDEN_SIDE_EFFECTS,
        "network_required": bool(effect_contract.get("touches_external")),
        "external_provider_required": False,
        "future_tool_broker_required": True,
        "read_only_mislabel_detected": mislabel,
    }
    b["effect_boundary_hash"] = _core_hash(b, "effect_boundary_hash")
    return b


def build_prompt_context_boundary(*, tenant_id, tool_id, contract_id,
                                  selection_boundary) -> dict:
    minimal = selection_boundary.get("minimal_context_status", "NEVER_EXPOSE")
    b = {
        "prompt_context_boundary_version": PROMPT_BOUNDARY_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id, "contract_id": contract_id,
        "allowed_fields_for_future_model": selection_boundary.get(
            "allowed_descriptor_fields_for_planner", []),
        "summary_only_fields": selection_boundary.get("summary_only_fields", []),
        "redacted_fields": selection_boundary.get("redacted_fields", []),
        "never_expose_fields": selection_boundary.get("never_expose_fields", []),
        "safe_planner_summary": minimal != "NEVER_EXPOSE",
        "prompt_context_exposure_status": minimal,
    }
    b["prompt_context_boundary_hash"] = _core_hash(
        b, "prompt_context_boundary_hash")
    return b


# --- Deontic obligation ledger ---------------------------------------------
_REQUIRED_OBLIGATIONS = [
    "preserve_tenant_scope", "preserve_approval_requirement",
    "preserve_consent_requirement", "preserve_risk_class",
    "preserve_side_effect_class", "preserve_prompt_context_boundary",
    "preserve_traceability", "deny_runtime_capability", "deny_token_passthrough",
    "deny_external_provider_calls", "deny_tool_broker_calls", "deny_llm_calls",
    "deny_execution",
]


def build_deontic_ledger(*, tenant_id, contract_id, projection_id,
                         obligation_results) -> dict:
    obligations = []
    for name in _REQUIRED_OBLIGATIONS:
        ok = obligation_results.get(name, True)
        obligations.append({
            "obligation_id": f"{contract_id}:{name}",
            "obligation_type": name,
            "deontic_class": "REQUIRED",
            "obligation_status": "MATCHED" if ok else "FAILED",
            "evidence_hashes": [], "dispensation_reason": None,
        })
    failed = [o["obligation_type"] for o in obligations
              if o["obligation_status"] == "FAILED"]
    ledger = {
        "deontic_obligation_ledger_version": DEONTIC_LEDGER_VERSION,
        "tenant_id": tenant_id, "contract_id": contract_id,
        "projection_id": projection_id, "obligations": obligations,
        "failed_obligations": failed,
        "ledger_status": "MATCHED" if not failed else "FAILED",
    }
    ledger["deontic_obligation_ledger_hash"] = _core_hash(
        ledger, "deontic_obligation_ledger_hash")
    return ledger


# --- Finite violation witness ----------------------------------------------
def build_violation_witness(*, tenant_id, contract_id, projection_id,
                            violated_invariant, field_path, source_model,
                            source_hash, expected, actual, dominant_status,
                            explanation) -> dict:
    w = {
        "violation_witness_id": f"{projection_id}:{violated_invariant}",
        "tenant_id": tenant_id, "contract_id": contract_id,
        "projection_id": projection_id, "violated_invariant": violated_invariant,
        "violating_field_path": field_path, "source_model": source_model,
        "source_hash": source_hash, "expected_value": expected,
        "actual_value": _redact_witness_value(actual),
        "dominant_failure_status": dominant_status,
        "witness_explanation": explanation,
    }
    w["violation_witness_hash"] = _core_hash(w, "violation_witness_hash")
    return w


def _redact_witness_value(v):
    if isinstance(v, str) and any(s in _norm(v) for s in (
            "token", "secret", "password", "private key", "api key")):
        return "[REDACTED — secret-like value]"
    if isinstance(v, str) and len(v) > 120:
        return v[:120] + "…"
    return v


# --- Contract normal form --------------------------------------------------
def build_normal_form(*, tenant_id, tool_id, tool_version_id, contract_id, head,
                      descriptor, effect_contract, data_flow, quality_report,
                      effect_trace, deny_graph, scope_binding) -> dict:
    safe_desc = descriptor.get("tool_description", "")
    if quality_report and quality_report.get("planner_selection_boundary", {}
                                              ).get("minimal_context_status") \
            == "NEVER_EXPOSE":
        safe_desc = "[REDACTED — descriptor not exposable]"
    nf = {
        "contract_normal_form_version": NORMAL_FORM_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id,
        "tool_version_id": tool_version_id, "contract_id": contract_id,
        "normalized_name": head["tool_name"],
        "normalized_description_safe": safe_desc,
        "normalized_declared_kind": "TOOL_CONTRACT",
        "normalized_capability_category": head["category"],
        "normalized_side_effect_class": head["side_effect_class"],
        "normalized_risk_class": head["risk_class"],
        "normalized_input_schema": descriptor.get("schema_envelope", {}).get(
            "input_schema", {}),
        "normalized_output_schema": descriptor.get("schema_envelope", {}).get(
            "output_schema", {}),
        "normalized_scope_set": scope_binding["source_scope_set"],
        "normalized_data_boundary": sorted(
            data_flow.get("reads_data_classes", [])),
        "normalized_effect_boundary": head["side_effect_class"],
        "normalized_auth_requirements": ["case.read"],
        "normalized_approval_requirements": head["risk_class"] in (
            "HIGH", "CRITICAL", "PROHIBITED"),
        "normalized_consent_requirements": descriptor.get(
            "consent_contract", {}).get("consent_requirement", "NONE"),
        "normalized_prompt_context_boundary": (quality_report or {}).get(
            "planner_selection_boundary", {}).get("minimal_context_status"),
        "normalized_protocol_boundary": "TOOL_DESCRIPTOR",
        "normalized_runtime_capability_denials": list(RUNTIME_CAPABILITIES),
        "normalized_effect_trace_semantics": effect_trace["allowed_effects"],
        "normalized_deontic_obligations": list(_REQUIRED_OBLIGATIONS),
        "normalized_traceability_refs": [head["descriptor_hash"]],
        "normal_form_status": "MATCHED",
    }
    nf["contract_normal_form_hash"] = _core_hash(nf, "contract_normal_form_hash")
    return nf


# --- Contract ABI ----------------------------------------------------------
def build_abi(*, tenant_id, tool_id, tool_version_id, contract_id, normal_form,
              effect_trace, previous_abi_hash=None) -> dict:
    abi = {
        "contract_abi_version": ABI_VERSION, "tenant_id": tenant_id,
        "tool_id": tool_id, "tool_version_id": tool_version_id,
        "contract_id": contract_id,
        "input_abi": _sha(normal_form["normalized_input_schema"]),
        "output_abi": _sha(normal_form["normalized_output_schema"]),
        "effect_abi": normal_form["normalized_effect_boundary"],
        "effect_trace_abi": effect_trace["effect_trace_semantics_hash"],
        "data_scope_abi": _sha(normal_form["normalized_data_boundary"]),
        "auth_abi": _sha(normal_form["normalized_auth_requirements"]),
        "approval_abi": normal_form["normalized_approval_requirements"],
        "consent_abi": normal_form["normalized_consent_requirements"],
        "artifact_abi": "future-broker-only",
        "prompt_context_abi": normal_form["normalized_prompt_context_boundary"],
        "protocol_boundary_abi": normal_form["normalized_protocol_boundary"],
        "runtime_capability_abi": _sha(
            normal_form["normalized_runtime_capability_denials"]),
        "broker_readiness_abi": "future-broker-only",
    }
    new_hash = _core_hash(abi, "abi_hash", "abi_breaking_change_flags")
    breaking = []
    if previous_abi_hash and previous_abi_hash != new_hash:
        breaking.append("ABI_HASH_CHANGED")
    abi["abi_breaking_change_flags"] = breaking
    abi["abi_hash"] = new_hash
    return abi


# --- Non-execution proof ---------------------------------------------------
_NON_EXEC_ITEMS = [
    "no_execute_endpoint", "no_tool_broker_call", "no_llm_call",
    "no_mcp_server_client_call", "no_mcp_sampling", "no_mcp_elicitation",
    "no_mcp_resource_serving", "no_mcp_prompt_serving", "no_external_provider",
    "no_customer_message", "no_payment_execution", "no_crm_write",
    "no_evidence_mutation", "no_data_export", "no_token_issuance",
    "no_secret_access", "no_network_side_effect",
]


def build_non_execution_proof(*, tenant_id, tool_id, contract_id) -> dict:
    # Structural: B3 has no execution path, so every item holds by construction.
    proof = {
        "contract_non_execution_proof_id": contract_id + "-nonexec",
        "tenant_id": tenant_id, "tool_id": tool_id, "contract_id": contract_id,
        "proof_items": {i: True for i in _NON_EXEC_ITEMS},
        "failed_items": [], "proof_status": "MATCHED",
    }
    proof["contract_non_execution_proof_hash"] = _core_hash(
        proof, "contract_non_execution_proof_hash")
    return proof


# --- Traceability envelope -------------------------------------------------
def build_traceability_envelope(*, tenant_id, tool_id, tool_version_id,
                                contract_id, head, version, quality_report,
                                source_freshness_epoch, revocation_epoch,
                                contract_hash, normal_form_hash, abi_hash,
                                effect_trace_hash, proof_bundle_hash,
                                dialect_hash, deny_graph_hash, actor_id,
                                actor_type, created_at) -> dict:
    env = {
        "traceability_envelope_version": TRACEABILITY_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id,
        "tool_version_id": tool_version_id, "contract_id": contract_id,
        "source_descriptor_hash": head["descriptor_hash"],
        "source_admission_hash": head["admission_package_hash"],
        "source_quality_report_hash": (quality_report or {}).get(
            "quality_report_hash"),
        "source_quality_assurance_case_hash": (quality_report or {}).get(
            "quality_assurance_case_hash"),
        "source_security_case_hash": version["security_case"][
            "security_case_hash"],
        "source_negative_capability_hash": version["negative_capabilities"][
            "negative_capability_hash"],
        "source_policy_hash": head["policy_capsule_hash"],
        "source_risk_hash": head["risk_capsule_hash"],
        "source_tbom_hash": head["tbom_hash"],
        "source_registry_event_chain_hash": head["tool_state_hash"],
        "source_freshness_epoch": source_freshness_epoch,
        "revocation_epoch": revocation_epoch, "contract_hash": contract_hash,
        "contract_normal_form_hash": normal_form_hash, "contract_abi_hash":
        abi_hash, "effect_trace_semantics_hash": effect_trace_hash,
        "contract_proof_bundle_hash": proof_bundle_hash,
        "protocol_dialect_matrix_hash": dialect_hash,
        "runtime_capability_deny_graph_hash": deny_graph_hash,
        "projection_manifest_hash": None,
        "created_by_actor_id": actor_id, "created_by_actor_type": actor_type,
        "created_at": created_at,
    }
    env["traceability_envelope_hash"] = _core_hash(
        env, "traceability_envelope_hash")
    return env


# --- Source freshness epoch ------------------------------------------------
def source_freshness_epoch(head, quality_report) -> str:
    """Deterministic epoch fingerprint over the source hashes that, if changed,
    make a prior contract STALE."""
    return _sha({
        "descriptor_hash": head["descriptor_hash"],
        "version_hash": head["version_hash"],
        "policy_capsule_hash": head["policy_capsule_hash"],
        "risk_capsule_hash": head["risk_capsule_hash"],
        "admission_package_hash": head["admission_package_hash"],
        "tool_state_hash": head["tool_state_hash"], "status": head["status"],
        "quality_report_hash": (quality_report or {}).get("quality_report_hash"),
        "quality_status": (quality_report or {}).get("quality_status"),
    })


# --- Schema closure gate ---------------------------------------------------
def build_schema_closure(*, tenant_id, contract_id, tool_id, schema_envelope,
                         risk_class) -> dict:
    inp = schema_envelope.get("input_schema") or {}
    out = schema_envelope.get("output_schema") or {}

    def closed(schema):
        if not isinstance(schema, dict) or not schema:
            return False, ["schema empty/undeclared"]
        issues = []
        if schema.get("type") == "object" and "properties" not in schema:
            issues.append("object schema declares no properties")
        if schema.get("additionalProperties") is True and _tr.RISK_RANK.get(
                risk_class, 0) >= _tr.RISK_RANK["MEDIUM"]:
            issues.append("unrestricted additionalProperties on a "
                          f"{risk_class}-risk schema")
        return not issues, issues
    in_closed, in_issues = closed(inp)
    out_closed, out_issues = closed(out)
    open_world = in_issues + out_issues
    status = ("NEEDS_REVIEW" if open_world else "MATCHED")
    g = {
        "schema_closure_gate_version": "finalis-schema-closure-gate-v1",
        "tenant_id": tenant_id, "contract_id": contract_id, "tool_id": tool_id,
        "input_schema_closed": in_closed, "output_schema_closed": out_closed,
        "open_world_fields": open_world, "schema_closure_status": status,
    }
    g["schema_closure_hash"] = _core_hash(g, "schema_closure_hash")
    return g


# --- Field provenance + taint ----------------------------------------------
def build_field_provenance(*, tenant_id, contract_id, projection_id, fields,
                           quarantined) -> dict:
    """fields: list of (field_path, source_model, source_field_path,
    source_hash, transformation, taint)."""
    provs = []
    for fp, sm, sfp, sh, transform, taint in fields:
        provs.append({
            "field_path": fp, "source_model": sm, "source_field_path": sfp,
            "source_hash": sh, "transformation": transform,
            "taint": taint,
            "redaction_applied": taint in ("REDACTED", "NEVER_EXPOSE_TO_MODEL"),
            "sanitization_applied": transform == "sanitized",
        })
    fp_obj = {
        "field_provenance_version": "finalis-field-provenance-v1",
        "tenant_id": tenant_id, "contract_id": contract_id,
        "projection_id": projection_id, "fields": provs,
        "all_fields_have_provenance": all(f["source_hash"] for f in provs),
        "taint_labels": sorted({f["taint"] for f in provs}),
    }
    fp_obj["field_provenance_hash"] = _core_hash(fp_obj, "field_provenance_hash")
    return fp_obj


# --- Non-interference matrix -----------------------------------------------
def build_non_interference(*, tenant_id, contract_id, target,
                           field_provenance) -> dict:
    model_facing = target in MODEL_FACING_TARGETS
    leakage = []
    for f in field_provenance["fields"]:
        if model_facing and f["taint"] in MODEL_UNSAFE_TAINTS \
                and not f["redaction_applied"]:
            leakage.append(f["field_path"])
    status = "MATCHED" if not leakage else "FAILED"
    m = {
        "non_interference_matrix_version": NON_INTERFERENCE_VERSION,
        "tenant_id": tenant_id, "contract_id": contract_id,
        "source_projection_target": target,
        "target_projection_target": target,
        "shared_fields": [f["field_path"] for f in field_provenance["fields"]],
        "field_policy": {"model_facing": model_facing,
                         "unsafe_taints_denied": sorted(MODEL_UNSAFE_TAINTS)},
        "leakage_detected": bool(leakage),
        "downgrade_detected": False, "redaction_conflict_detected": False,
        "leaked_fields": leakage, "non_interference_status": status,
    }
    m["non_interference_matrix_hash"] = _core_hash(
        m, "non_interference_matrix_hash")
    return m


# --- Proof obligations -----------------------------------------------------
PROOF_OBLIGATION_NAMES = [
    "source_hash_matched", "source_freshness_epoch_matched",
    "revocation_epoch_matched", "tool_b1_admission_matched",
    "tool_b2_quality_matched", "contract_normal_form_matched",
    "contract_abi_matched", "protocol_method_firewall_matched",
    "runtime_capability_deny_graph_matched", "effect_trace_semantics_declared",
    "deontic_obligations_matched", "scope_subset_proof_matched",
    "risk_non_downgrade_matched", "side_effect_non_downgrade_matched",
    "read_only_correctness_matched", "metadata_sanitized",
    "field_provenance_complete", "taint_policy_satisfied",
    "cross_projection_non_interference_matched", "no_ambient_authority_matched",
    "no_token_passthrough_matched", "non_execution_proof_matched",
]


def build_proof_obligations(*, tenant_id, contract_id, projection_id,
                            results) -> list:
    obligations = []
    for name in PROOF_OBLIGATION_NAMES:
        r = results.get(name, {"status": "MATCHED", "reason": None,
                               "witness": None})
        ob = {
            "proof_obligation_id": f"{projection_id}:{name}",
            "tenant_id": tenant_id, "contract_id": contract_id,
            "projection_id": projection_id, "obligation_name": name,
            "obligation_status": r["status"], "evidence_hashes": r.get(
                "evidence", []), "failure_reason": r.get("reason"),
            "violation_witness_ref": r.get("witness"),
        }
        ob["proof_obligation_hash"] = _core_hash(ob, "proof_obligation_hash")
        obligations.append(ob)
    return obligations


# --- Contract proof bundle -------------------------------------------------
def build_proof_bundle(*, tenant_id, contract_id, projection_id, proof_obligations,
                       deontic_ledger, effect_trace, deny_graph,
                       non_interference, scope_binding, effect_boundary,
                       schema_closure, traceability_hash, witnesses) -> dict:
    failed = [o["obligation_name"] for o in proof_obligations
              if o["obligation_status"] == "FAILED"]
    review = [o["obligation_name"] for o in proof_obligations
              if o["obligation_status"] == "NEEDS_REVIEW"]
    status = ("FAILED" if failed or deontic_ledger["ledger_status"] == "FAILED"
              or non_interference["non_interference_status"] == "FAILED"
              else ("NEEDS_REVIEW" if review else "MATCHED"))
    bundle = {
        "contract_proof_bundle_id": projection_id + "-bundle",
        "contract_proof_bundle_version": PROOF_BUNDLE_VERSION,
        "tenant_id": tenant_id, "contract_id": contract_id,
        "projection_id": projection_id,
        "proof_obligations": [o["proof_obligation_hash"]
                              for o in proof_obligations],
        "obligation_ledger_refs": [deontic_ledger[
            "deontic_obligation_ledger_hash"]],
        "effect_trace_ref": effect_trace["effect_trace_semantics_hash"],
        "runtime_deny_graph_ref": deny_graph["deny_graph_hash"],
        "non_interference_ref": non_interference[
            "non_interference_matrix_hash"],
        "scope_proof_ref": scope_binding["scope_binding_hash"],
        "risk_delta_ref": None, "side_effect_delta_ref": None,
        "read_only_correctness_ref": effect_boundary["effect_boundary_hash"],
        "schema_closure_ref": schema_closure["schema_closure_hash"],
        "traceability_ref": traceability_hash,
        "violation_witnesses": [w["violation_witness_hash"] for w in witnesses],
        "failed_obligations": failed, "review_obligations": review,
        "proof_bundle_status": status,
    }
    bundle["contract_proof_bundle_hash"] = _core_hash(
        bundle, "contract_proof_bundle_hash")
    return bundle


# --- Broker-readiness certificate ------------------------------------------
def build_broker_readiness(*, tenant_id, contract_id, tool_id, tool_version_id,
                           projection_id, blockers, source_descriptor_hash,
                           source_admission_hash, source_quality_report_hash,
                           contract_hash, projection_hash, proof_bundle,
                           effect_trace, scope_binding, traceability_hash,
                           b1_admitted, b2_ok) -> dict:
    cert_blockers = list(blockers)
    if not b1_admitted:
        cert_blockers.append("TOOL_B1_NOT_ADMITTED")
    if not b2_ok:
        cert_blockers.append("TOOL_B2_QUALITY_NOT_PASSED")
    if effect_trace["effect_trace_status"] == "NOT_IMPLEMENTED":
        cert_blockers.append("EFFECT_TRACE_MISSING")
    if proof_bundle["proof_bundle_status"] == "FAILED":
        cert_blockers.append("PROOF_BUNDLE_FAILED")
    if cert_blockers:
        # A pending-admission tool (TOOL_B1_NOT_ADMITTED / NEEDS_REVIEW) is
        # NOT_READY, not BLOCKED — it is awaiting admission/review, not a
        # security violation. Any hard blocker → BLOCKED.
        _soft = {"TOOL_B1_NOT_ADMITTED", "NEEDS_REVIEW"}
        status = ("BLOCKED" if any(b not in _soft for b in cert_blockers)
                  else "NOT_READY")
        if proof_bundle["proof_bundle_status"] == "NEEDS_REVIEW":
            status = "NEEDS_REVIEW"
    elif proof_bundle["proof_bundle_status"] == "NEEDS_REVIEW":
        status = "NEEDS_REVIEW"
    else:
        status = "READY_FOR_FUTURE_BROKER_CONSIDERATION"
    cert = {
        "broker_readiness_certificate_id": projection_id + "-cert",
        "broker_readiness_certificate_version": BROKER_CERT_VERSION,
        "tenant_id": tenant_id, "contract_id": contract_id, "tool_id": tool_id,
        "tool_version_id": tool_version_id, "projection_id": projection_id,
        "certificate_status": status, "certificate_blockers": sorted(
            set(cert_blockers)),
        "source_descriptor_hash": source_descriptor_hash,
        "source_admission_hash": source_admission_hash,
        "source_quality_report_hash": source_quality_report_hash,
        "contract_hash": contract_hash, "projection_hash": projection_hash,
        "proof_bundle_hash": proof_bundle["contract_proof_bundle_hash"],
        "effect_trace_semantics_hash": effect_trace[
            "effect_trace_semantics_hash"],
        "scope_binding_hash": scope_binding["scope_binding_hash"],
        "traceability_envelope_hash": traceability_hash,
    }
    cert["certificate_hash"] = _core_hash(cert, "certificate_hash")
    return cert


# --- Protocol-like internal shapes -----------------------------------------
def build_mcp_like_shape(normal_form, *, read_only) -> dict:
    return {"name": normal_form["normalized_name"],
            "title": normal_form["normalized_name"],
            "description": normal_form["normalized_description_safe"],
            "inputSchema": normal_form["normalized_input_schema"],
            "outputSchema": normal_form["normalized_output_schema"],
            "annotations": {"readOnlyHint": bool(read_only),
                            "destructiveHint": normal_form[
                                "normalized_side_effect_class"]
                            in ("DESTRUCTIVE", "IRREVERSIBLE"),
                            "openWorldHint": False},
            "_protocol_note": "internal MCP-like shape only; not an MCP server "
            "response; no runtime features"}


def build_apps_sdk_like_shape(normal_form, *, read_only) -> dict:
    return {"title": normal_form["normalized_name"],
            "description": normal_form["normalized_description_safe"],
            "inputSchema": normal_form["normalized_input_schema"],
            "outputSchema": normal_form["normalized_output_schema"],
            "securitySchemes": {"future_slot": "NOT_IMPLEMENTED"},
            "_meta": {"finalis_internal": True, "read_only": bool(read_only)},
            "_protocol_note": "internal Apps-SDK-like shape only; no runtime"}


def build_openapi_like_shape(normal_form, *, read_only) -> dict:
    return {"operationId": _tr.normalize_tool_key(
        normal_form["normalized_name"]).replace("-", "_"),
        "summary": normal_form["normalized_name"],
        "description": normal_form["normalized_description_safe"],
        "requestBody": {"content": {"application/json": {
            "schema": normal_form["normalized_input_schema"]}}},
        "responses": {"200": {"content": {"application/json": {
            "schema": normal_form["normalized_output_schema"]}}}},
        "security": [{"future_slot": []}],
        "tags": [normal_form["normalized_capability_category"]],
        "x-finalis-note": "internal OpenAPI-like shape only; no server/client "
        "generated; no compliance claimed"}


def deterministic_contract_id(*, tenant_id, tool_id, tool_version_id,
                              source_freshness_epoch) -> str:
    """A contract is uniquely identified by its SOURCE snapshot, so the same
    (tenant, tool, version, freshness epoch) always yields the same contract id.
    This makes contract_hash source-deterministic and makes contract creation
    idempotent — re-creating over an unchanged source returns the same contract,
    and a source drift (new epoch) yields a new contract id."""
    return "ctr-" + _sha({"tenant_id": tenant_id, "tool_id": tool_id,
                          "tool_version_id": tool_version_id,
                          "source_freshness_epoch": source_freshness_epoch})[:40]


# --- Top-level contract assembly -------------------------------------------
def build_contract(*, head, version, quality_report, contract_id,
                   actor_id, actor_type, tenant_id, created_at,
                   runtime_requested=False, previous_abi_hash=None):
    """Normalize an admitted, quality-passed tool into an internal contract.
    Executes nothing. Returns the contract dict. All runtime capabilities are
    denied; source truth is preserved (no risk/effect downgrade)."""
    tool_id = head["tool_id"]
    tool_version_id = head["latest_version_id"]
    descriptor = version["descriptor"]
    effect_contract = version["effect_contract"]
    data_flow = version["data_flow_contract"]
    selection_boundary = (quality_report or {}).get(
        "planner_selection_boundary", {"minimal_context_status": "NEVER_EXPOSE"})
    requires_approval = head["risk_class"] in ("HIGH", "CRITICAL", "PROHIBITED")
    requires_consent = descriptor.get("consent_contract", {}).get(
        "consent_requirement", "NONE") not in ("NONE",)

    epoch = source_freshness_epoch(head, quality_report)
    revocation_epoch = "0"

    effect_trace = build_effect_trace_semantics(
        tenant_id=tenant_id, contract_id=contract_id, tool_id=tool_id,
        effect_contract=effect_contract, data_flow=data_flow,
        category=head["category"])
    deny_graph = build_deny_graph(tenant_id=tenant_id, contract_id=contract_id,
                                  tool_id=tool_id)
    method_firewall = build_method_firewall(
        tenant_id=tenant_id, contract_id=contract_id, tool_id=tool_id,
        descriptor=descriptor, runtime_requested=runtime_requested)
    separation = build_separation_guard(
        tenant_id=tenant_id, contract_id=contract_id, tool_id=tool_id,
        descriptor=descriptor, declared_kind="TOOL_CONTRACT")
    cap_neg = build_capability_negotiation(
        tenant_id=tenant_id, contract_id=contract_id, tool_id=tool_id,
        runtime_requested=runtime_requested)
    dialect = build_dialect_matrix(tenant_id=tenant_id, contract_id=contract_id,
                                   tool_id=tool_id)
    scope_binding = build_scope_binding(
        tenant_id=tenant_id, tool_id=tool_id, tool_version_id=tool_version_id,
        contract_id=contract_id, head=head, data_flow=data_flow,
        requires_approval=requires_approval, requires_consent=requires_consent)
    auth_envelope = build_auth_envelope(
        tenant_id=tenant_id, tool_id=tool_id, contract_id=contract_id,
        head=head, requires_approval=requires_approval,
        requires_consent=requires_consent)
    data_boundary = build_data_boundary(
        tenant_id=tenant_id, tool_id=tool_id, contract_id=contract_id,
        data_flow=data_flow)
    effect_boundary = build_effect_boundary(
        tenant_id=tenant_id, tool_id=tool_id, contract_id=contract_id,
        effect_contract=effect_contract, descriptor=descriptor)
    prompt_boundary = build_prompt_context_boundary(
        tenant_id=tenant_id, tool_id=tool_id, contract_id=contract_id,
        selection_boundary=selection_boundary)
    normal_form = build_normal_form(
        tenant_id=tenant_id, tool_id=tool_id, tool_version_id=tool_version_id,
        contract_id=contract_id, head=head, descriptor=descriptor,
        effect_contract=effect_contract, data_flow=data_flow,
        quality_report=quality_report, effect_trace=effect_trace,
        deny_graph=deny_graph, scope_binding=scope_binding)
    abi = build_abi(
        tenant_id=tenant_id, tool_id=tool_id, tool_version_id=tool_version_id,
        contract_id=contract_id, normal_form=normal_form,
        effect_trace=effect_trace, previous_abi_hash=previous_abi_hash)
    non_exec = build_non_execution_proof(
        tenant_id=tenant_id, tool_id=tool_id, contract_id=contract_id)
    schema_closure = build_schema_closure(
        tenant_id=tenant_id, contract_id=contract_id, tool_id=tool_id,
        schema_envelope=descriptor.get("schema_envelope", {}),
        risk_class=head["risk_class"])

    # Contract-level status: source-gate first, then structural guards.
    signals = []
    if head["status"] in _B1_SECURITY_BLOCKED:
        signals.append("TOOL_B1_BLOCKED")
    if (quality_report or {}).get("quality_status") not in _B2_QUALITY_OK:
        signals.append("TOOL_B2_BLOCKED")
    if method_firewall["method_firewall_status"] == "BLOCKED":
        signals.append("PROTOCOL_METHOD_VIOLATION")
    if separation["separation_guard_status"] == "BLOCKED":
        signals.append("SAMPLING_ELICITATION_VIOLATION")
    if cap_neg["capability_boundary_status"] == "BLOCKED":
        signals.append("RUNTIME_CAPABILITY_DENIED")
    if effect_boundary["read_only_mislabel_detected"]:
        signals.append("READONLY_MISLABEL")
    if signals:
        contract_status = status_for_failures(signals)
        if contract_status in ("BLOCKED", "QUARANTINED", "TAMPERED", "REVOKED"):
            contract_status = "BLOCKED"
    elif method_firewall["method_firewall_status"] == "NEEDS_REVIEW" or \
            separation["separation_guard_status"] == "NEEDS_REVIEW":
        contract_status = "NEEDS_REVIEW"
    else:
        contract_status = ("PROJECTABLE_FOR_FUTURE"
                           if head["admitted"] else "CONTRACTED")

    contract = {
        "contract_id": contract_id, "tenant_id": tenant_id, "tool_id": tool_id,
        "tool_version_id": tool_version_id,
        "contract_version": 1, "contract_status": contract_status,
        "contract_target": "INTERNAL_TOOL_BROKER_CONTRACT",
        "source_descriptor_hash": head["descriptor_hash"],
        "source_tool_version_hash": head["version_hash"],
        "source_admission_package_hash": head["admission_package_hash"],
        "source_policy_capsule_hash": head["policy_capsule_hash"],
        "source_risk_capsule_hash": head["risk_capsule_hash"],
        "source_security_case_hash": version["security_case"][
            "security_case_hash"],
        "source_negative_capability_proof_hash": version[
            "negative_capabilities"]["negative_capability_hash"],
        "source_quality_report_hash": (quality_report or {}).get(
            "quality_report_hash"),
        "source_quality_assurance_case_hash": (quality_report or {}).get(
            "quality_assurance_case_hash"),
        "source_prompt_context_policy_hash": version["prompt_context_policy"][
            "prompt_context_policy_hash"],
        "source_freshness_epoch": epoch, "revocation_epoch": revocation_epoch,
        "contract_normal_form": normal_form, "contract_abi": abi,
        "effect_trace_semantics": effect_trace, "protocol_method_firewall":
        method_firewall, "protocol_dialect_matrix": dialect,
        "capability_negotiation_boundary": cap_neg,
        "separation_guard": separation,
        "runtime_capability_deny_graph": deny_graph,
        "contract_scope_binding": scope_binding,
        "auth_context_envelope": auth_envelope,
        "contract_data_boundary": data_boundary,
        "contract_effect_boundary": effect_boundary,
        "contract_prompt_context_boundary": prompt_boundary,
        "schema_closure": schema_closure,
        "contract_non_execution_proof": non_exec,
        "contract_name": head["tool_name"],
        "contract_description_safe": normal_form[
            "normalized_description_safe"],
        "contract_declared_kind": "TOOL_CONTRACT",
        "contract_capability_category": head["category"],
        "contract_side_effect_class": head["side_effect_class"],
        "contract_risk_class": head["risk_class"],
        "requires_future_tool_broker": True,
        "requires_approval": requires_approval,
        "requires_consent": requires_consent,
        "contract_blockers": signals,
        "created_by_actor_id": actor_id, "created_by_actor_type": actor_type,
        "created_at": created_at, "updated_at": created_at,
        "honesty_labels": HONESTY_LABELS,
    }
    # contract_hash is SOURCE-deterministic: it excludes the derived
    # state/traceability (computed after) and the instance actor fields, so the
    # same source snapshot yields the same contract_hash. (contract_id is itself
    # source-derived via deterministic_contract_id, so it may remain covered.)
    contract_hash = _core_hash(
        contract, "contract_hash", "contract_state_hash",
        "contract_traceability_envelope", "created_by_actor_id",
        "created_by_actor_type", "contract_status", "contract_blockers")
    contract["contract_hash"] = contract_hash

    proof_bundle_placeholder = None
    traceability = build_traceability_envelope(
        tenant_id=tenant_id, tool_id=tool_id, tool_version_id=tool_version_id,
        contract_id=contract_id, head=head, version=version,
        quality_report=quality_report, source_freshness_epoch=epoch,
        revocation_epoch=revocation_epoch, contract_hash=contract_hash,
        normal_form_hash=normal_form["contract_normal_form_hash"],
        abi_hash=abi["abi_hash"],
        effect_trace_hash=effect_trace["effect_trace_semantics_hash"],
        proof_bundle_hash=proof_bundle_placeholder,
        dialect_hash=dialect["protocol_dialect_matrix_hash"],
        deny_graph_hash=deny_graph["deny_graph_hash"], actor_id=actor_id,
        actor_type=actor_type, created_at=created_at)
    contract["contract_traceability_envelope"] = traceability
    contract["contract_state_hash"] = _sha({
        "contract_id": contract_id, "contract_hash": contract_hash,
        "contract_status": contract_status,
        "source_freshness_epoch": epoch, "revocation_epoch": revocation_epoch,
        "abi_hash": abi["abi_hash"]})
    return contract


# --- Projection assembly + firewall ----------------------------------------
def build_projection(*, contract, head, quality_report, target, projection_id,
                     tenant_id, created_at, runtime_requested=False):
    """Validation-only projection of a contract into a target shape. Runs the
    projection firewall; a failure produces finite violation witnesses and a
    BLOCKED/NEEDS_REVIEW/STALE status. Executes nothing."""
    if target not in PROJECTION_TARGETS:
        raise ValueError(f"unknown projection target {target}")
    tool_id = contract["tool_id"]
    tool_version_id = contract["tool_version_id"]
    contract_id = contract["contract_id"]
    normal_form = contract["contract_normal_form"]
    effect_trace = contract["effect_trace_semantics"]
    deny_graph = contract["runtime_capability_deny_graph"]
    scope_binding = contract["contract_scope_binding"]
    effect_boundary = contract["contract_effect_boundary"]
    schema_closure = contract["schema_closure"]
    prompt_boundary = contract["contract_prompt_context_boundary"]
    b1_admitted = head["admitted"]
    b2_ok = (quality_report or {}).get("quality_status") in _B2_QUALITY_OK
    model_facing = target in MODEL_FACING_TARGETS
    minimal = prompt_boundary["prompt_context_exposure_status"]

    signals = []
    witnesses = []

    def witness(inv, field, source_model, source_hash, expected, actual,
                explanation):
        w = build_violation_witness(
            tenant_id=tenant_id, contract_id=contract_id,
            projection_id=projection_id, violated_invariant=inv,
            field_path=field, source_model=source_model, source_hash=source_hash,
            expected=expected, actual=actual, dominant_status="BLOCKED",
            explanation=explanation)
        witnesses.append(w)
        return w["violation_witness_hash"]

    # Source-state gates.
    if head["tenant_id"] != tenant_id:
        signals.append("CROSS_TENANT")
    # Staleness: a projection is validation-only against the CURRENT source, so
    # a drifted source (or an already-STALE/REVOKED contract) can never be
    # projected positive. Fail-closed at the kernel so every caller
    # (project, /mcp-like, /compatibility, default) respects it.
    current_epoch = source_freshness_epoch(head, quality_report)
    if current_epoch != contract.get("source_freshness_epoch") or \
            contract.get("contract_status") == "STALE":
        signals.append("STALE_SOURCE")
        witness("source_freshness_epoch_matched", "source_freshness_epoch",
                "tool_registry", head["tool_state_hash"],
                contract.get("source_freshness_epoch"), current_epoch,
                "source drifted since contract creation; projection is stale")
    if contract.get("contract_status") == "REVOKED" or \
            contract.get("revocation_epoch") not in ("0", None):
        signals.append("REVOKED")
    # B1 gate. A security-blocked source is a hard TOOL_B1_BLOCKED. A merely
    # not-yet-admitted (DRAFT/NEEDS_REVIEW) but clean source is NOT a security
    # violation — it is pending admission, so it can never reach a POSITIVE
    # projectable status (it becomes NEEDS_REVIEW) but its proof bundle need not
    # fail. Either way the projection is never PROJECTABLE_FOR_FUTURE while
    # unadmitted.
    if head["status"] in _B1_SECURITY_BLOCKED:
        signals.append("TOOL_B1_BLOCKED")
        witness("tool_b1_admission_matched", "head.status", "tool_registry",
                head["tool_state_hash"], "not security-blocked", head["status"],
                "TOOL-B1 security state forbids projection")
    elif not head.get("admitted"):
        signals.append("NEEDS_REVIEW")
    if not b2_ok:
        signals.append("TOOL_B2_BLOCKED")
        witness("tool_b2_quality_matched", "quality.quality_status",
                "tool_quality", (quality_report or {}).get(
                    "quality_report_hash"), "QUALITY_PASS",
                (quality_report or {}).get("quality_status"),
                "TOOL-B2 quality state forbids projection")
    # Prompt-context: model-facing target over a NEVER_EXPOSE descriptor.
    if model_facing and minimal == "NEVER_EXPOSE":
        signals.append("PROMPT_CONTEXT_BLOCKED")
        witness("prompt_context_boundary", "prompt_context_boundary",
                "tool_quality", (quality_report or {}).get(
                    "quality_report_hash"), "exposable", minimal,
                "descriptor is NEVER_EXPOSE; cannot be model-facing projected")
    # Protocol / runtime guards.
    if contract["protocol_method_firewall"]["method_firewall_status"] \
            == "BLOCKED" or runtime_requested:
        signals.append("PROTOCOL_METHOD_VIOLATION")
    if contract["separation_guard"]["separation_guard_status"] == "BLOCKED":
        signals.append("SAMPLING_ELICITATION_VIOLATION")
    if contract["capability_negotiation_boundary"][
            "capability_boundary_status"] == "BLOCKED" or runtime_requested:
        signals.append("RUNTIME_CAPABILITY_DENIED")
        witness("runtime_capability_deny_graph_matched", "runtime",
                "tool_contracts", deny_graph["deny_graph_hash"], "all denied",
                "runtime requested",
                "runtime capabilities are denied in B3")
    if effect_trace["effect_trace_status"] == "NOT_IMPLEMENTED":
        signals.append("EFFECT_TRACE_MISSING")
    if effect_boundary["read_only_mislabel_detected"]:
        signals.append("READONLY_MISLABEL")
        witness("read_only_correctness_matched", "effect_boundary",
                "tool_contracts", effect_boundary["effect_boundary_hash"],
                "not read-only", "read-only claimed",
                "write/dangerous tool mislabeled read-only")
    if not scope_is_subset(scope_binding["projected_scope_set"],
                           scope_binding["source_scope_set"]):
        signals.append("SCOPE_EXPANSION")

    # Build the projected shape only from the normal form (never raw source).
    read_only = normal_form["normalized_side_effect_class"] == "PURE_READ"
    if target == "MCP_LIKE_TOOL_DESCRIPTOR":
        shape = build_mcp_like_shape(normal_form, read_only=read_only)
    elif target == "OPENAI_APPS_SDK_LIKE_DESCRIPTOR":
        shape = build_apps_sdk_like_shape(normal_form, read_only=read_only)
    elif target == "OPENAPI_LIKE_SCHEMA_CONTRACT":
        shape = build_openapi_like_shape(normal_form, read_only=read_only)
    elif target == "SAFE_PLANNER_SUMMARY":
        shape = {"name": normal_form["normalized_name"],
                 "category": normal_form["normalized_capability_category"],
                 "risk_class": normal_form["normalized_risk_class"],
                 "requires_future_tool_broker": True}
    elif target == "SAFE_HUMAN_REVIEW_VIEW":
        shape = {"name": normal_form["normalized_name"],
                 "description": normal_form["normalized_description_safe"],
                 "risk_class": normal_form["normalized_risk_class"],
                 "side_effect_class": normal_form[
                     "normalized_side_effect_class"],
                 "runtime_features_enabled": False}
    else:                                               # TRACE_ONLY / broker
        shape = {"contract_hash": contract["contract_hash"],
                 "abi_hash": contract["contract_abi"]["abi_hash"]}

    # Metadata sanitization over the ENTIRE projected shape — including the
    # input/output schema text (property descriptions/examples/enums), which is
    # exactly where a poisoned descriptor hides instructions that would reach a
    # model-facing shape. Any poisoning blocks + quarantines the projection.
    sanitization = sanitize_metadata({
        "title": normal_form["normalized_name"],
        "shape_text": _flatten_text(shape),
        "input_schema": normal_form["normalized_input_schema"],
        "output_schema": normal_form["normalized_output_schema"]})
    if not sanitization["sanitized_clean"]:
        signals.append("METADATA_POISONING")
        witness("metadata_sanitized", "projected_shape", "tool_registry",
                head["descriptor_hash"], "clean",
                sanitization["poisoning_findings"],
                "projected shape / schema text carries poisoning patterns")

    # Field provenance + taint for each projected field. Taints are derived
    # from the field's ACTUAL content so the non-interference matrix has real
    # signal: a field whose text trips the poisoning/secret detectors is tagged
    # POISONING_SUSPECTED / SECRET_LIKE (an unsafe taint the matrix denies on a
    # model-facing target), and constrained descriptions are REDACTED.
    def _field_taint(fp, value):
        blob = " ".join(_norm(t) for t in _flatten_text(value))
        if any(n in blob for n in _SANITIZE_NEEDLES):
            return "POISONING_SUSPECTED"
        if any(s in blob for s in ("token", "secret", "password",
                                   "private key", "api key")):
            return "SECRET_LIKE"
        if fp in ("description",) and minimal in ("SUMMARY_ONLY",
                                                  "REQUIRES_REDACTION"):
            return "REDACTED" if model_facing else "SAFE_FOR_HUMAN_REVIEW"
        return "SAFE_INTERNAL"
    fields = []
    for fp in sorted(shape.keys()):
        taint = _field_taint(fp, shape[fp])
        fields.append((fp, "contract_normal_form", f"normalized_{fp}",
                       normal_form["contract_normal_form_hash"],
                       "projected", taint))
    field_provenance = build_field_provenance(
        tenant_id=tenant_id, contract_id=contract_id,
        projection_id=projection_id, fields=fields,
        quarantined=minimal == "NEVER_EXPOSE")
    if not field_provenance["all_fields_have_provenance"]:
        signals.append("PROOF_OBLIGATION_FAILED")

    non_interference = build_non_interference(
        tenant_id=tenant_id, contract_id=contract_id, target=target,
        field_provenance=field_provenance)
    if non_interference["non_interference_status"] == "FAILED":
        signals.append("CROSS_PROJECTION_INTERFERENCE")

    # Redact model-facing description when exposure is constrained.
    if model_facing and minimal in ("SUMMARY_ONLY", "REQUIRES_REDACTION") \
            and "description" in shape:
        shape["description"] = "[SUMMARY WITHHELD — exposure constrained]"

    # Deontic obligations.
    ob_results = {
        "preserve_risk_class": "RISK_DOWNGRADE" not in signals,
        "preserve_side_effect_class": "SIDE_EFFECT_DOWNGRADE" not in signals,
        "deny_runtime_capability": "RUNTIME_CAPABILITY_DENIED" not in signals,
        "deny_token_passthrough": not contract["auth_context_envelope"][
            "token_passthrough_allowed"],
        "preserve_tenant_scope": "CROSS_TENANT" not in signals,
    }
    deontic = build_deontic_ledger(
        tenant_id=tenant_id, contract_id=contract_id,
        projection_id=projection_id, obligation_results=ob_results)
    if deontic["ledger_status"] == "FAILED":
        signals.append("PROOF_OBLIGATION_FAILED")

    # Proof obligations.
    def ob(ok, witness_ref=None, reason=None):
        return {"status": "MATCHED" if ok else "FAILED", "reason": reason,
                "witness": witness_ref}
    ob_map = {
        "tool_b1_admission_matched": ob("TOOL_B1_BLOCKED" not in signals),
        "tool_b2_quality_matched": ob("TOOL_B2_BLOCKED" not in signals),
        "protocol_method_firewall_matched": ob(
            "PROTOCOL_METHOD_VIOLATION" not in signals),
        "runtime_capability_deny_graph_matched": ob(
            "RUNTIME_CAPABILITY_DENIED" not in signals),
        "effect_trace_semantics_declared": ob(
            "EFFECT_TRACE_MISSING" not in signals),
        "risk_non_downgrade_matched": ob("RISK_DOWNGRADE" not in signals),
        "side_effect_non_downgrade_matched": ob(
            "SIDE_EFFECT_DOWNGRADE" not in signals),
        "read_only_correctness_matched": ob("READONLY_MISLABEL" not in signals),
        "metadata_sanitized": ob("METADATA_POISONING" not in signals),
        "field_provenance_complete": ob(field_provenance[
            "all_fields_have_provenance"]),
        "cross_projection_non_interference_matched": ob(
            "CROSS_PROJECTION_INTERFERENCE" not in signals),
        "no_token_passthrough_matched": ob(True),
        "no_ambient_authority_matched": ob(True),
        "non_execution_proof_matched": ob(True),
        "scope_subset_proof_matched": ob("SCOPE_EXPANSION" not in signals),
    }
    proof_obligations = build_proof_obligations(
        tenant_id=tenant_id, contract_id=contract_id,
        projection_id=projection_id, results=ob_map)

    proof_bundle = build_proof_bundle(
        tenant_id=tenant_id, contract_id=contract_id,
        projection_id=projection_id, proof_obligations=proof_obligations,
        deontic_ledger=deontic, effect_trace=effect_trace, deny_graph=deny_graph,
        non_interference=non_interference, scope_binding=scope_binding,
        effect_boundary=effect_boundary, schema_closure=schema_closure,
        traceability_hash=contract["contract_traceability_envelope"][
            "traceability_envelope_hash"], witnesses=witnesses)

    # Projection status.
    if signals:
        status = status_for_failures(signals)
        if status not in PROJECTION_STATUSES:
            status = "BLOCKED"
    elif proof_bundle["proof_bundle_status"] == "NEEDS_REVIEW" or \
            schema_closure["schema_closure_status"] == "NEEDS_REVIEW":
        status = "NEEDS_REVIEW"
    elif model_facing and minimal in ("SUMMARY_ONLY", "REQUIRES_REDACTION"):
        status = "PROJECTED_SAFE_SUMMARY_ONLY"
    else:
        status = "PROJECTABLE_FOR_FUTURE"

    projection_hash_core = {
        "target": target, "shape": shape,
        "field_provenance_hash": field_provenance["field_provenance_hash"],
        "proof_bundle_hash": proof_bundle["contract_proof_bundle_hash"],
        "status": status}
    projection_hash = _sha(projection_hash_core)

    broker_cert = build_broker_readiness(
        tenant_id=tenant_id, contract_id=contract_id, tool_id=tool_id,
        tool_version_id=tool_version_id, projection_id=projection_id,
        blockers=[s for s in signals], source_descriptor_hash=head[
            "descriptor_hash"], source_admission_hash=head[
            "admission_package_hash"], source_quality_report_hash=(
            quality_report or {}).get("quality_report_hash"),
        contract_hash=contract["contract_hash"], projection_hash=projection_hash,
        proof_bundle=proof_bundle, effect_trace=effect_trace,
        scope_binding=scope_binding, traceability_hash=contract[
            "contract_traceability_envelope"]["traceability_envelope_hash"],
        b1_admitted=b1_admitted, b2_ok=b2_ok)

    envelope = {
        "projection_envelope_id": projection_id,
        "projection_envelope_version": PROJECTION_ENVELOPE_VERSION,
        "tenant_id": tenant_id, "contract_id": contract_id, "tool_id": tool_id,
        "tool_version_id": tool_version_id, "projection_target": target,
        "projection_status": status,
        "protocol_dialect": _target_dialect(target),
        "projected_name": shape.get("name") or shape.get("title")
        or normal_form["normalized_name"],
        "projected_description": shape.get("description"),
        "projected_input_schema": normal_form["normalized_input_schema"],
        "projected_output_schema": normal_form["normalized_output_schema"],
        "projected_annotations": shape.get("annotations", {}),
        "projected_metadata": sanitization["safe_metadata"],
        "projected_shape": shape,
        "field_provenance": field_provenance,
        "projection_taint_labels": field_provenance["taint_labels"],
        "redaction_manifest": {"redacted_model_facing": model_facing and minimal
                               in ("SUMMARY_ONLY", "REQUIRES_REDACTION",
                                   "NEVER_EXPOSE")},
        "proof_obligations": proof_obligations,
        "deontic_obligation_ledger": deontic,
        "non_interference_matrix": non_interference,
        "contract_proof_bundle": proof_bundle,
        "broker_readiness_certificate": broker_cert,
        "violation_witnesses": witnesses,
        "broker_readiness_certificate_ref": broker_cert["certificate_hash"],
        "projection_blockers": sorted(set(signals)),
        "projection_warnings": [],
        "source_hashes": {"descriptor_hash": head["descriptor_hash"],
                          "version_hash": head["version_hash"],
                          "quality_report_hash": (quality_report or {}).get(
                              "quality_report_hash")},
        "source_freshness_epoch": contract["source_freshness_epoch"],
        "revocation_epoch": contract["revocation_epoch"],
        "metadata_sanitization": sanitization,
        "metadata_sanitization_hash": sanitization[
            "metadata_sanitization_hash"],
        "schema_closure": schema_closure,
        "projection_hash": projection_hash,
        "created_at": created_at, "honesty_labels": HONESTY_LABELS,
    }
    envelope["projection_envelope_hash"] = _core_hash(
        envelope, "projection_envelope_hash")
    return envelope


def _target_dialect(target):
    return {"MCP_LIKE_TOOL_DESCRIPTOR": "MCP_2025_11_25_LIKE",
            "OPENAI_APPS_SDK_LIKE_DESCRIPTOR": "OPENAI_APPS_SDK_LIKE",
            "OPENAPI_LIKE_SCHEMA_CONTRACT": "OPENAPI_3_1_LIKE",
            "SAFE_PLANNER_SUMMARY": "SAFE_PLANNER_SUMMARY",
            "TRACE_ONLY_CONTRACT": "TRACE_ONLY",
            "INTERNAL_TOOL_BROKER_CONTRACT": "INTERNAL_BROKER_DRAFT",
            "SAFE_HUMAN_REVIEW_VIEW": "TRACE_ONLY"}.get(target, "TRACE_ONLY")


# --- Compatibility report --------------------------------------------------
def build_compatibility_report(*, tenant_id, contract_id, tool_id,
                               tool_version_id, projections) -> dict:
    """projections: list of (target, projection_envelope)."""
    scores, blockers = {}, []
    per_target = {}
    for target, env in projections:
        st = env["projection_status"]
        ok = st in ("PROJECTABLE_FOR_FUTURE", "PROJECTED_SAFE_SUMMARY_ONLY")
        scores[target] = 5 if ok else (2 if st == "NEEDS_REVIEW" else 0)
        per_target[target] = st
        if not ok and st not in ("NEEDS_REVIEW",):
            blockers.extend(env["projection_blockers"])
    any_ok = any(v >= 5 for v in scores.values())
    status = ("COMPATIBLE_INTERNAL_ONLY" if any_ok
              else ("NEEDS_REVIEW" if any(v == 2 for v in scores.values())
                    else "BLOCKED"))
    report = {
        "compatibility_report_id": contract_id + "-compat",
        "compatibility_report_version": COMPAT_REPORT_VERSION,
        "tenant_id": tenant_id, "contract_id": contract_id, "tool_id": tool_id,
        "tool_version_id": tool_version_id,
        "compatibility_status": status, "compatibility_score_vector": scores,
        "compatibility_blockers": sorted(set(blockers)),
        "compatibility_warnings": [],
        "mcp_like_compatibility": per_target.get("MCP_LIKE_TOOL_DESCRIPTOR"),
        "apps_sdk_like_compatibility": per_target.get(
            "OPENAI_APPS_SDK_LIKE_DESCRIPTOR"),
        "openapi_like_compatibility": per_target.get(
            "OPENAPI_LIKE_SCHEMA_CONTRACT"),
        "internal_broker_compatibility": per_target.get(
            "INTERNAL_TOOL_BROKER_CONTRACT"),
        "protocol_version_notes": "internal-like shapes only; no compliance",
    }
    report["compatibility_report_hash"] = _core_hash(
        report, "compatibility_report_hash")
    return report


# --- Invalidation / staleness ----------------------------------------------
INVALIDATION_REASONS = {
    "SOURCE_DESCRIPTOR_CHANGED", "SOURCE_TOOL_VERSION_CHANGED",
    "SOURCE_ADMISSION_CHANGED", "SOURCE_QUALITY_CHANGED",
    "SOURCE_POLICY_CHANGED", "SOURCE_RISK_CHANGED",
    "SOURCE_SECURITY_CASE_CHANGED", "SOURCE_PROMPT_CONTEXT_CHANGED",
    "SOURCE_PROTOCOL_BOUNDARY_CHANGED", "SOURCE_EFFECT_TRACE_CHANGED",
    "SOURCE_FRESHNESS_EPOCH_CHANGED", "CONTRACT_TAMPERED", "CONTRACT_REVOKED",
    "TENANT_SCOPE_CHANGED",
}


def invalidation_check(*, contract, head, quality_report) -> dict:
    current_epoch = source_freshness_epoch(head, quality_report)
    reasons = []
    if current_epoch != contract["source_freshness_epoch"]:
        reasons.append("SOURCE_FRESHNESS_EPOCH_CHANGED")
    if head["descriptor_hash"] != contract["source_descriptor_hash"]:
        reasons.append("SOURCE_DESCRIPTOR_CHANGED")
    if (quality_report or {}).get("quality_report_hash") != contract[
            "source_quality_report_hash"]:
        reasons.append("SOURCE_QUALITY_CHANGED")
    if head["admission_package_hash"] != contract[
            "source_admission_package_hash"]:
        reasons.append("SOURCE_ADMISSION_CHANGED")
    # A status CHANGE is captured by the freshness epoch (which covers status);
    # a stably-blocked status present since creation is not staleness — that is
    # a BLOCKED projection, decided by the firewall, not a stale one.
    stale = bool(reasons)
    result = {"contract_id": contract["contract_id"],
              "stale": stale, "invalidation_reasons": sorted(set(reasons)),
              "current_source_freshness_epoch": current_epoch,
              "contract_source_freshness_epoch": contract[
                  "source_freshness_epoch"],
              "new_status": "STALE" if stale else contract["contract_status"],
              "honesty_labels": HONESTY_LABELS}
    result["invalidation_hash"] = _sha({k: v for k, v in result.items()
                                        if k not in ("invalidation_hash",
                                                     "honesty_labels")})
    return result


# --- Contract event ledger -------------------------------------------------
CONTRACT_EVENT_TYPES = {
    "CONTRACT_CREATED", "CONTRACT_PROJECTED", "CONTRACT_VERIFIED",
    "CONTRACT_INVALIDATED", "CONTRACT_REVOKED", "PROJECTION_BLOCKED",
    "PROJECTION_STALE", "PROJECTION_REVOKED", "PROTOCOL_METHOD_BLOCKED",
    "RUNTIME_CAPABILITY_BLOCKED", "PROOF_OBLIGATION_FAILED",
    "FINITE_VIOLATION_WITNESS_RECORDED", "BROKER_READINESS_CERTIFICATE_RECORDED",
}


def build_contract_event(*, event_type, tool_id, contract_id, tenant_id,
                         actor_id, actor_type, contract_state_hash,
                         previous_event_hash, sequence, detail,
                         created_at) -> dict:
    if event_type not in CONTRACT_EVENT_TYPES:
        raise ValueError(f"unknown contract event_type {event_type}")
    ev = {
        "contract_event_version": CONTRACT_EVENT_VERSION,
        "event_type": event_type, "tool_id": tool_id, "contract_id": contract_id,
        "tenant_id": tenant_id, "actor_id": actor_id, "actor_type": actor_type,
        "contract_state_hash": contract_state_hash,
        "previous_event_hash": previous_event_hash or GENESIS,
        "sequence": sequence, "detail": detail, "created_at": created_at,
    }
    ev["event_hash"] = _sha({k: v for k, v in ev.items() if k != "event_hash"})
    return ev


def contract_version_hash(*, contract_id, version_number, contract_hash,
                          abi_hash, previous_contract_version_hash) -> str:
    return _sha({"contract_id": contract_id, "version_number": version_number,
                 "contract_hash": contract_hash, "abi_hash": abi_hash,
                 "previous_contract_version_hash":
                 previous_contract_version_hash or GENESIS})


def contract_chain_hash(previous_chain, this_version_hash) -> str:
    return _sha({"previous_contract_chain_hash": previous_chain or GENESIS,
                 "contract_version_hash": this_version_hash})


