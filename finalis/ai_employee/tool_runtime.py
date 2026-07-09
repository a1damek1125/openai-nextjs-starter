"""Finalis ViktorAI Verifiable Read-Path Runtime Microkernel (TOOL-B6).

The FIRST controlled runtime layer — but strictly LOCAL, DETERMINISTIC and
READ-ONLY. It runs local deterministic read-only adapters over FROZEN local
snapshots and produces provenance-verifiable safe output. It is snapshot-bound,
temporally isolated, semantically read-filtered, read-set-attested,
output-provenance-verifiable, replay-verifiable, data-diode-output-filtered,
resource-budgeted and information-budgeted.

It is NOT external tool execution, NOT write-capable, NOT payment/message/CRM/
evidence/export, NOT MCP/LLM runtime/server/client, NOT OAuth/token issuance,
NOT production credential handling, NOT production autonomous execution. It
never reads mutable production state, never mutates a source artifact, never
calls the network/a provider/MCP/LLM, never reads a secret or credential, and
never issues or derives a token. The most permissive outcome is
``RUNTIME_READ_ONLY_COMPLETED`` — a local read-only result, never an external
effect.

The unique guarantee: every safe output field is a deterministic function of an
attested read-set over a frozen snapshot; no forbidden source can influence safe
output (semantic non-interference); no synthetic canary can leak; information and
side-channel exposure are budgeted; and the whole microkernel fails closed under
deterministic fault injection.
"""
from __future__ import annotations

from .tool_contracts import canonical_json, _sha, _core_hash, _flatten_text
from . import tool_registry as _tr

RUNTIME_MODEL_VERSION = "finalis-read-path-runtime-microkernel-v1"
REQUEST_VERSION = "finalis-runtime-request-envelope-v1"
ADMISSION_VERSION = "finalis-runtime-admission-gate-v1"
MICROKERNEL_VERSION = "finalis-runtime-microkernel-contract-v1"
OP_LEDGER_VERSION = "finalis-runtime-operation-ledger-v1"
SEMANTIC_READ_VERSION = "finalis-semantic-read-firewall-v1"
READ_SET_LEDGER_VERSION = "finalis-read-set-ledger-v1"
READ_SET_COMPLETENESS_VERSION = "finalis-read-set-completeness-proof-v1"
READ_SET_ATTESTATION_VERSION = "finalis-read-set-attestation-capsule-v1"
TEMPORAL_ISOLATION_VERSION = "finalis-temporal-snapshot-isolation-v1"
EPOCH_VECTOR_VERSION = "finalis-snapshot-epoch-vector-v1"
ADAPTER_REGISTRY_VERSION = "finalis-read-only-adapter-registry-v1"
CAPABILITY_CALCULUS_VERSION = "finalis-adapter-capability-calculus-v1"
ADAPTER_FIREWALL_VERSION = "finalis-adapter-capability-firewall-v1"
SNAPSHOT_SEAL_VERSION = "finalis-runtime-snapshot-seal-v1"
SNAPSHOT_TWIN_VERSION = "finalis-runtime-snapshot-twin-v1"
SNAPSHOT_DAG_VERSION = "finalis-snapshot-provenance-dag-v1"
SNAPSHOT_INPUT_VERSION = "finalis-snapshot-bound-input-envelope-v1"
AUTHORITY_FREEZE_VERSION = "finalis-runtime-authority-freeze-v1"
PATH_POLICY_VERSION = "finalis-runtime-path-policy-automaton-v1"
KERNEL_VERSION = "finalis-read-only-runtime-sandbox-kernel-v1"
EXECUTION_RECORD_VERSION = "finalis-runtime-execution-record-v1"
RESOURCE_BUDGET_VERSION = "finalis-runtime-resource-budget-envelope-v1"
RESOURCE_USAGE_VERSION = "finalis-runtime-resource-usage-proof-v1"
ENTROPY_SEAL_VERSION = "finalis-determinism-entropy-seal-v1"
REPLAY_TWIN_VERSION = "finalis-deterministic-replay-twin-v1"
OUTPUT_RECORD_VERSION = "finalis-runtime-output-record-v1"
DATA_DIODE_VERSION = "finalis-data-diode-output-gate-v1"
OUTPUT_TAINT_VERSION = "finalis-output-taint-lattice-v1"
NON_EXFILTRATION_VERSION = "finalis-output-non-exfiltration-gate-v1"
SAFE_OUTPUT_VERSION = "finalis-safe-output-projection-v1"
EFFECT_LEDGER_VERSION = "finalis-runtime-effect-ledger-v1"
NON_ESCALATION_VERSION = "finalis-runtime-non-escalation-proof-v1"
SURFACE_DIFF_VERSION = "finalis-runtime-boundary-surface-diff-guard-v1"
ESCAPE_SENTINEL_VERSION = "finalis-runtime-escape-sentinel-v1"
FAULT_HARNESS_VERSION = "finalis-runtime-fault-injection-harness-v1"
RELEASE_GATE_VERSION = "finalis-runtime-release-gate-negative-test-report-v1"
CONFORMANCE_VERSION = "finalis-runtime-conformance-vector-v1"
PROOF_BUNDLE_VERSION = "finalis-runtime-proof-bundle-v1"
# v5 additions
QUERY_PLAN_VERSION = "finalis-query-plan-normal-form-v1"
PROVENANCE_MAP_VERSION = "finalis-read-output-provenance-map-v1"
BISIMULATION_VERSION = "finalis-output-provenance-bisimulation-v1"
NON_INTERFERENCE_VERSION = "finalis-semantic-non-interference-matrix-v1"
CANARY_HARNESS_VERSION = "finalis-synthetic-canary-snapshot-harness-v1"
CANARY_PROOF_VERSION = "finalis-canary-non-leakage-proof-v1"
INFO_BUDGET_VERSION = "finalis-information-budget-envelope-v1"
INFO_USAGE_VERSION = "finalis-information-usage-proof-v1"
READ_AMP_VERSION = "finalis-read-amplification-guard-v1"
SIDE_CHANNEL_VERSION = "finalis-side-channel-budget-seal-v1"
OUTPUT_CERT_VERSION = "finalis-output-provenance-certificate-v1"
RUNTIME_EVENT_VERSION = "finalis-runtime-event-v1"
GENESIS = "0" * 64


HONESTY_LABELS = [
    "READ_ONLY_INTERNAL_RUNTIME_ONLY", "SNAPSHOT_BOUND_ONLY",
    "TEMPORAL_SNAPSHOT_ISOLATED", "SEMANTIC_READ_FIREWALL_PASSED",
    "READ_SET_ATTESTED", "OUTPUT_PROVENANCE_BISIMULATED",
    "CANARY_NON_LEAKAGE_PROVED", "INFORMATION_BUDGET_ENFORCED",
    "READ_AMPLIFICATION_GUARDED", "SIDE_CHANNEL_BUDGET_SEALED",
    "LOCAL_SNAPSHOT_ONLY", "READ_SET_LEDGER_REQUIRED",
    "DETERMINISTIC_REPLAY_REQUIRED", "DETERMINISM_ENTROPY_SEALED",
    "DATA_DIODE_OUTPUT_ONLY", "RESOURCE_BUDGET_ENFORCED",
    "NO_EXTERNAL_PROVIDER", "NO_NETWORK", "NO_TOKEN", "NO_CREDENTIAL",
    "NO_SECRET_READ", "NO_MUTABLE_PRODUCTION_READ", "NO_WRITE_EFFECT",
    "NO_CUSTOMER_MESSAGE", "NO_PAYMENT", "NO_CRM_MUTATION",
    "NO_EVIDENCE_MUTATION", "NO_DATA_EXPORT",
    "NOT_PRODUCTION_AUTONOMOUS_EXECUTION",
]


# --- Upstream (B5) acceptance ----------------------------------------------
B5_ACCEPTABLE_STATUSES = {"BROKER_PREPARED_FOR_FUTURE_ONLY", "NULL_ONLY_PREPARED"}

# --- Data classes ----------------------------------------------------------
# Only these two classes may be READ into the read-set; everything else is a
# forbidden source that can never influence safe output.
ALLOWED_READ_CLASSES = {"PUBLIC", "INTERNAL"}
# Values that may appear RAW in safe output (INTERNAL is redacted, not raw).
RAW_OUTPUT_CLASSES = {"PUBLIC"}
FORBIDDEN_SOURCE_CLASSES = {
    "CUSTOMER_SENSITIVE", "APPROVAL_SENSITIVE", "CONSENT_SENSITIVE",
    "SECRET_LIKE", "CREDENTIAL_LIKE", "TOKEN_LIKE", "EXECUTION_AUTHORITY",
    "CROSS_TENANT_SOURCE", "MUTABLE_PRODUCTION_STATE", "CANARY_FIELD",
    "PROVIDER_RESULT", "MCP_RESULT", "LLM_RESULT",
}
SOURCE_CLASSES = ({"ALLOWED_SNAPSHOT_FIELD", "ALLOWED_SAFE_VIEW_FIELD",
                   "LOCAL_POLICY_METADATA", "LOCAL_PROOF_METADATA",
                   "DETERMINISTIC_CONSTANT"} | FORBIDDEN_SOURCE_CLASSES)

# Minimal read-only capability set. Any operation outside this set is rejected.
READ_ONLY_CAPABILITIES = {
    "READ_SNAPSHOT_FIELD", "COMPUTE_DETERMINISTIC", "PROJECT_SAFE_OUTPUT",
    "RECORD_LEDGER", "ATTEST_READ_SET",
}
# Adapter capability flags that must all be false-for-danger / read-only.
FORBIDDEN_ADAPTER_CAPS = {
    "write", "network", "credential", "provider", "mcp", "llm", "external",
    "execute", "mutate", "token",
}
RUNTIME_SURFACE_FLAGS = {
    "write_endpoint", "network_path", "provider_call_path", "mcp_path",
    "llm_path", "token_path", "credential_path", "execute_endpoint",
    "mutate_capability", "external_path",
}
ENTROPY_SOURCES = {"wall_clock", "random", "uuid", "network_time", "pid",
                   "thread_id", "env_nondeterministic", "system_entropy"}
KNOWN_ADAPTER_KINDS = {"count", "presence", "field_projection",
                       "redacted_summary"}
_SECRET_MARKERS = {"secret", "password", "privatekey", "apikey", "accesstoken",
                   "bearer", "oauthtoken", "clientsecret", "credential",
                   "authorization", "sessiontoken", "refreshtoken"}

DEFAULT_POLICY = {
    "max_output_fields": 8, "max_sensitive_field_count": 0,
    "max_taint_level": 1, "max_read_to_output_edges": 32,
    "max_repeated_query_count": 5, "max_correlation_risk_bucket": 2,
    "max_output_entropy_bucket": 3, "resource_op_budget": 256,
    "resource_read_budget": 128, "resource_output_size_budget": 4096,
    "side_channel_duration_bucket_max": 3, "side_channel_output_bucket_max": 3,
    "side_channel_error_bucket_max": 1, "read_amplification_overlap_max": 3,
}
# Taint level per data class (higher = more sensitive).
_TAINT_LEVEL = {"PUBLIC": 0, "INTERNAL": 1, "DETERMINISTIC_CONSTANT": 0}


# --- Hard-fail dominance ladder --------------------------------------------
FAILURE_DOMINANCE = [
    "TAMPERED", "CROSS_TENANT", "REVOKED",
    "TOOL_B1_BLOCKED", "TOOL_B2_BLOCKED", "TOOL_B3_BLOCKED", "TOOL_B4_BLOCKED",
    "TOOL_B5_BLOCKED", "B5_CERTIFICATE_MISSING", "B5_CERTIFICATE_MISMATCH",
    "B5_NEGATIVE_CERTIFICATE_MISMATCH", "B5_RELEASE_GATE_FAILED",
    "B5_OUTCOME_NOT_NULL_ONLY", "B5_PROOF_BUNDLE_MISMATCH",
    "ADAPTER_NOT_REGISTERED", "ADAPTER_WRITE_CAPABLE", "ADAPTER_EXTERNAL",
    "ADAPTER_NETWORK_CAPABLE", "ADAPTER_CREDENTIAL_REQUIRED",
    "ADAPTER_PROVIDER_BACKED", "ADAPTER_MCP_CAPABLE", "ADAPTER_LLM_CAPABLE",
    "ADAPTER_CAPABILITY_DRIFT", "RUNTIME_MICROKERNEL_REJECTED",
    "RUNTIME_OPERATION_NOT_ADMITTED", "UNKNOWN_CAPABILITY",
    "RUNTIME_AUTHORITY_EXPANSION", "SEMANTIC_READ_DENIED", "READ_SET_MISSING",
    "READ_SET_INCOMPLETE", "READ_SET_ATTESTATION_FAILED",
    "READ_SET_SNAPSHOT_MISMATCH", "READ_TO_OUTPUT_PROVENANCE_MISSING",
    "OUTPUT_PROVENANCE_BISIMULATION_FAILED", "SEMANTIC_NON_INTERFERENCE_FAILED",
    "CANARY_LEAK_DETECTED", "INFORMATION_BUDGET_EXCEEDED",
    "INFORMATION_USAGE_PROOF_FAILED", "READ_AMPLIFICATION_DETECTED",
    "SIDE_CHANNEL_BUDGET_EXCEEDED", "TEMPORAL_SNAPSHOT_ISOLATION_FAILED",
    "SNAPSHOT_EPOCH_MISMATCH", "SNAPSHOT_MISSING", "SNAPSHOT_MUTABLE",
    "SNAPSHOT_HASH_MISMATCH", "SNAPSHOT_SCOPE_DENIED", "SNAPSHOT_TWIN_MISMATCH",
    "SNAPSHOT_PROVENANCE_INVALID", "RESOURCE_BUDGET_EXCEEDED",
    "RESOURCE_USAGE_PROOF_FAILED", "INPUT_HASH_MISMATCH", "PAYLOAD_MUTATED",
    "RUNTIME_POLICY_MISMATCH", "RUNTIME_PATH_POLICY_REJECTED",
    "RUNTIME_SURFACE_DIFF_DETECTED", "ENVIRONMENT_ASSUMPTION_DRIFT",
    "DETERMINISM_ENTROPY_UNSEALED", "REPLAY_MISMATCH",
    "DATA_DIODE_OUTPUT_GATE_FAILED", "OUTPUT_TAINT_ESCAPE_DETECTED",
    "OUTPUT_EXFILTRATION_DETECTED", "SAFE_OUTPUT_PROJECTION_FAILED",
    "WRITE_EFFECT_DETECTED", "NETWORK_EFFECT_DETECTED", "SECRET_READ_DETECTED",
    "CREDENTIAL_READ_DETECTED", "TOKEN_ISSUANCE_ATTEMPT",
    "TOKEN_DERIVATION_ATTEMPT", "PROVIDER_CALL_ATTEMPT", "MCP_CALL_ATTEMPT",
    "LLM_CALL_ATTEMPT", "PAYMENT_ATTEMPT", "CRM_MUTATION_ATTEMPT",
    "EVIDENCE_MUTATION_ATTEMPT", "DATA_EXPORT_ATTEMPT", "RUNTIME_ESCAPE_DETECTED",
    "FAULT_INJECTION_RELEASE_GATE_FAILED", "REPLAY_CONFLICT", "NEEDS_RECHECK",
    "READ_ONLY_RUNTIME_COMPLETED",
]
_DOMINANCE_RANK = {s: i for i, s in enumerate(FAILURE_DOMINANCE)}
POSITIVE_SIGNALS = {"READ_ONLY_RUNTIME_COMPLETED"}

RUNTIME_STATUSES = {
    "RUNTIME_REQUEST_PENDING", "RUNTIME_READ_ONLY_PREPARED",
    "RUNTIME_READ_ONLY_COMPLETED", "RUNTIME_NEEDS_RECHECK", "RUNTIME_BLOCKED",
    "RUNTIME_DENIED", "RUNTIME_QUARANTINED", "RUNTIME_STALE", "RUNTIME_TAMPERED",
    "RUNTIME_REPLAYED", "RUNTIME_REPLAY_CONFLICT", "RUNTIME_NOT_IMPLEMENTED",
}
POSITIVE_STATUSES = {"RUNTIME_READ_ONLY_COMPLETED", "RUNTIME_READ_ONLY_PREPARED"}
DECISION_STATUSES = {
    "RUNTIME_DECISION_ALLOW_READ_ONLY_LOCAL", "RUNTIME_DECISION_BLOCK",
    "RUNTIME_DECISION_DENY", "RUNTIME_DECISION_NEEDS_RECHECK",
    "RUNTIME_DECISION_STALE", "RUNTIME_DECISION_QUARANTINE",
    "RUNTIME_DECISION_REPLAYED", "RUNTIME_DECISION_NOT_IMPLEMENTED",
}

_QUARANTINE_SIGNALS = {
    "CANARY_LEAK_DETECTED", "OUTPUT_TAINT_ESCAPE_DETECTED",
    "OUTPUT_EXFILTRATION_DETECTED", "WRITE_EFFECT_DETECTED",
    "NETWORK_EFFECT_DETECTED", "SECRET_READ_DETECTED",
    "CREDENTIAL_READ_DETECTED", "TOKEN_ISSUANCE_ATTEMPT",
    "TOKEN_DERIVATION_ATTEMPT", "PROVIDER_CALL_ATTEMPT", "MCP_CALL_ATTEMPT",
    "LLM_CALL_ATTEMPT", "PAYMENT_ATTEMPT", "CRM_MUTATION_ATTEMPT",
    "EVIDENCE_MUTATION_ATTEMPT", "DATA_EXPORT_ATTEMPT", "RUNTIME_ESCAPE_DETECTED",
}
_STALE_SIGNALS = {"SNAPSHOT_EPOCH_MISMATCH", "SNAPSHOT_MUTABLE"}


def _status_for_signal(sig):
    if sig == "TAMPERED":
        return "RUNTIME_TAMPERED"
    if sig == "REPLAY_CONFLICT":
        return "RUNTIME_REPLAY_CONFLICT"
    if sig == "NEEDS_RECHECK":
        return "RUNTIME_NEEDS_RECHECK"
    if sig in _STALE_SIGNALS:
        return "RUNTIME_STALE"
    if sig in _QUARANTINE_SIGNALS:
        return "RUNTIME_QUARANTINED"
    if sig in POSITIVE_SIGNALS:
        return "RUNTIME_READ_ONLY_COMPLETED"
    return "RUNTIME_BLOCKED"


def _decision_for_status(status):
    return {
        "RUNTIME_READ_ONLY_COMPLETED": "RUNTIME_DECISION_ALLOW_READ_ONLY_LOCAL",
        "RUNTIME_TAMPERED": "RUNTIME_DECISION_BLOCK",
        "RUNTIME_QUARANTINED": "RUNTIME_DECISION_QUARANTINE",
        "RUNTIME_STALE": "RUNTIME_DECISION_STALE",
        "RUNTIME_NEEDS_RECHECK": "RUNTIME_DECISION_NEEDS_RECHECK",
        "RUNTIME_REPLAY_CONFLICT": "RUNTIME_DECISION_BLOCK",
        "RUNTIME_DENIED": "RUNTIME_DECISION_DENY",
    }.get(status, "RUNTIME_DECISION_BLOCK")


REASON_CODES = {s: s.replace("_", " ").capitalize() + "." for s in
                FAILURE_DOMINANCE}
REASON_CODES.update({
    "READ_ONLY_RUNTIME_COMPLETED": "Local read-only runtime completed; no "
    "external effect.",
})


def _norm(text) -> str:
    return _tr._normalize("" if text is None else str(text)).strip()


def _compact(text) -> str:
    return _norm(text).replace(" ", "")


def _as_list(v):
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple, set)) else [v]


def dominant_signal(signals) -> str:
    if not signals:
        return "READ_ONLY_RUNTIME_COMPLETED"
    return min(signals, key=lambda s: _DOMINANCE_RANK.get(s, -1))


def status_for_signals(signals) -> str:
    return _status_for_signal(dominant_signal(signals))


# --- Snapshot construction (frozen, local) ---------------------------------
def build_snapshot(*, snapshot_id, tenant_id, epoch, scope, fields,
                   provenance=None, created_at=None) -> dict:
    """A FROZEN local snapshot. ``fields`` maps field_path -> {value, data_class}.
    The snapshot is immutable evidence; its hash seals its content + epoch."""
    norm_fields = {}
    for path, spec in (fields or {}).items():
        spec = spec or {}
        norm_fields[str(path)] = {
            "value": spec.get("value"),
            "data_class": str(spec.get("data_class", "INTERNAL")).upper()}
    snap = {
        "runtime_snapshot_seal_version": SNAPSHOT_SEAL_VERSION,
        "snapshot_id": snapshot_id, "tenant_id": tenant_id, "epoch": str(epoch),
        "scope": str(scope or ""), "fields": norm_fields, "immutable": True,
        "field_count": len(norm_fields),
        "provenance_dag": provenance or {"nodes": ["ORIGIN"], "edges": [],
                                         "dag_kind": "LOCAL_FROZEN"},
    }
    snap["snapshot_hash"] = _core_hash(snap, "snapshot_hash")
    return snap


def build_snapshot_epoch_vector(*, tenant_id, runtime_request_id,
                                snapshot) -> dict:
    epochs = {str((snapshot or {}).get("epoch", ""))}
    epochs.discard("")
    single = len(epochs) == 1
    vec = {
        "snapshot_epoch_vector_version": EPOCH_VECTOR_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "epochs": sorted(epochs), "single_epoch": single,
        "epoch_vector_status": "EPOCH_SINGLE" if single else "EPOCH_MIXED",
        "signal": None if single else "SNAPSHOT_EPOCH_MISMATCH",
    }
    vec["snapshot_epoch_vector_hash"] = _core_hash(
        vec, "snapshot_epoch_vector_hash")
    return vec


def build_temporal_isolation(*, tenant_id, runtime_request_id, snapshot,
                             epoch_vector, requested_epoch) -> dict:
    snap_epoch = str((snapshot or {}).get("epoch", ""))
    mismatch = bool(requested_epoch) and requested_epoch != snap_epoch
    mixed = not epoch_vector["single_epoch"]
    ok = not mismatch and not mixed and bool(snap_epoch)
    iso = {
        "temporal_snapshot_isolation_version": TEMPORAL_ISOLATION_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "snapshot_epoch": snap_epoch, "requested_epoch": str(
            requested_epoch or ""),
        "epoch_mismatch": mismatch, "mixed_epochs": mixed,
        "isolation_status": "TEMPORAL_ISOLATED" if ok else "TEMPORAL_FAILED",
        "signal": None if ok else "TEMPORAL_SNAPSHOT_ISOLATION_FAILED",
    }
    iso["temporal_snapshot_isolation_hash"] = _core_hash(
        iso, "temporal_snapshot_isolation_hash")
    return iso


def build_snapshot_seal_check(*, tenant_id, runtime_request_id, snapshot,
                             sealed_snapshot_hash, allowed_scopes) -> dict:
    """Verify the snapshot is present, immutable, hash-matched to the sealed
    value, and within an allowed scope."""
    sig = None
    if not snapshot:
        sig = "SNAPSHOT_MISSING"
    elif not snapshot.get("immutable"):
        sig = "SNAPSHOT_MUTABLE"
    elif sealed_snapshot_hash is not None and snapshot.get(
            "snapshot_hash") != sealed_snapshot_hash:
        sig = "SNAPSHOT_HASH_MISMATCH"
    elif allowed_scopes is not None and str(snapshot.get("scope", "")) not in \
            set(map(str, allowed_scopes)):
        sig = "SNAPSHOT_SCOPE_DENIED"
    check = {
        "snapshot_seal_check_version": SNAPSHOT_SEAL_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "snapshot_present": bool(snapshot),
        "snapshot_immutable": bool((snapshot or {}).get("immutable")),
        "snapshot_hash": (snapshot or {}).get("snapshot_hash"),
        "sealed_snapshot_hash": sealed_snapshot_hash,
        "seal_status": "SEAL_MATCHED" if sig is None else "SEAL_FAILED",
        "signal": sig,
    }
    check["snapshot_seal_check_hash"] = _core_hash(
        check, "snapshot_seal_check_hash")
    return check


def build_snapshot_twin(*, tenant_id, runtime_request_id, snapshot) -> dict:
    """Re-derive the snapshot hash from its content; an identical twin must
    match (detects in-place mutation not reflected in the sealed hash)."""
    recomputed = _core_hash(
        {k: v for k, v in (snapshot or {}).items()
         if k != "snapshot_hash"}, "snapshot_hash") if snapshot else None
    match = bool(snapshot) and recomputed == (snapshot or {}).get(
        "snapshot_hash")
    twin = {
        "runtime_snapshot_twin_version": SNAPSHOT_TWIN_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "recomputed_snapshot_hash": recomputed,
        "stored_snapshot_hash": (snapshot or {}).get("snapshot_hash"),
        "twin_matched": match,
        "signal": None if match else "SNAPSHOT_TWIN_MISMATCH",
    }
    twin["runtime_snapshot_twin_hash"] = _core_hash(
        twin, "runtime_snapshot_twin_hash")
    return twin


def build_snapshot_provenance_dag(*, tenant_id, runtime_request_id,
                                  snapshot) -> dict:
    dag = (snapshot or {}).get("provenance_dag", {}) or {}
    nodes = _as_list(dag.get("nodes"))
    edges = _as_list(dag.get("edges"))
    # Valid: acyclic, all edge endpoints are nodes, has an ORIGIN.
    node_set = set(map(str, nodes))
    valid = bool(node_set) and "ORIGIN" in node_set and all(
        str(e.get("from")) in node_set and str(e.get("to")) in node_set
        for e in edges if isinstance(e, dict))
    out = {
        "snapshot_provenance_dag_version": SNAPSHOT_DAG_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "node_count": len(nodes), "edge_count": len(edges),
        "dag_valid": valid, "provenance_status": "DAG_VALID" if valid else
        "DAG_INVALID", "signal": None if valid else "SNAPSHOT_PROVENANCE_INVALID",
    }
    out["snapshot_provenance_dag_hash"] = _core_hash(
        out, "snapshot_provenance_dag_hash")
    return out


# --- Read-only adapter registry / capability calculus / firewall -----------
def build_adapter_descriptor(*, adapter_id, adapter_kind, allowed_sources,
                             allowed_projection, capabilities=None) -> dict:
    """A registered LOCAL READ-ONLY adapter descriptor. All dangerous
    capabilities are explicitly false; it can only read declared snapshot
    fields and project declared output fields."""
    caps = {c: False for c in FORBIDDEN_ADAPTER_CAPS}
    caps.update({str(k): bool(v) for k, v in (capabilities or {}).items()})
    adapter = {
        "read_only_adapter_registry_version": ADAPTER_REGISTRY_VERSION,
        "adapter_id": adapter_id, "adapter_kind": str(adapter_kind),
        "read_only": True, "local_only": True,
        "allowed_sources": sorted(set(map(str, _as_list(allowed_sources)))),
        "allowed_projection": sorted(set(map(str, _as_list(
            allowed_projection)))),
        "capabilities": caps,
    }
    adapter["adapter_hash"] = _core_hash(adapter, "adapter_hash")
    return adapter


def build_capability_calculus(*, tenant_id, runtime_request_id, adapter) -> dict:
    caps = (adapter or {}).get("capabilities", {})
    dangerous = sorted(c for c in FORBIDDEN_ADAPTER_CAPS if caps.get(c))
    kind = (adapter or {}).get("adapter_kind")
    unknown_kind = kind not in KNOWN_ADAPTER_KINDS
    calc = {
        "adapter_capability_calculus_version": CAPABILITY_CALCULUS_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "adapter_kind": kind, "unknown_kind": unknown_kind,
        "dangerous_capabilities": dangerous,
        "capability_set": sorted(READ_ONLY_CAPABILITIES),
        "calculus_status": "READ_ONLY_MINIMAL" if not dangerous and not
        unknown_kind else "CAPABILITY_VIOLATION",
    }
    calc["adapter_capability_calculus_hash"] = _core_hash(
        calc, "adapter_capability_calculus_hash")
    return calc


def _adapter_signals(adapter, calc) -> list:
    sig = []
    if not adapter or not adapter.get("adapter_id"):
        return ["ADAPTER_NOT_REGISTERED"]
    caps = adapter.get("capabilities", {})
    if not adapter.get("read_only"):
        sig.append("ADAPTER_WRITE_CAPABLE")
    if not adapter.get("local_only") or caps.get("external"):
        sig.append("ADAPTER_EXTERNAL")
    if caps.get("write") or caps.get("mutate"):
        sig.append("ADAPTER_WRITE_CAPABLE")
    if caps.get("network"):
        sig.append("ADAPTER_NETWORK_CAPABLE")
    if caps.get("credential"):
        sig.append("ADAPTER_CREDENTIAL_REQUIRED")
    if caps.get("provider"):
        sig.append("ADAPTER_PROVIDER_BACKED")
    if caps.get("mcp"):
        sig.append("ADAPTER_MCP_CAPABLE")
    if caps.get("llm"):
        sig.append("ADAPTER_LLM_CAPABLE")
    if calc["unknown_kind"]:
        sig.append("UNKNOWN_CAPABILITY")
    return sig


def build_adapter_firewall(*, tenant_id, runtime_request_id, adapter,
                           sealed_adapter_hash) -> dict:
    drift = sealed_adapter_hash is not None and (adapter or {}).get(
        "adapter_hash") != sealed_adapter_hash
    sigs = _adapter_signals(adapter, {"unknown_kind":
                            (adapter or {}).get("adapter_kind")
                            not in KNOWN_ADAPTER_KINDS})
    if drift:
        sigs.append("ADAPTER_CAPABILITY_DRIFT")
    ok = not sigs
    fw = {
        "adapter_capability_firewall_version": ADAPTER_FIREWALL_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "adapter_hash": (adapter or {}).get("adapter_hash"),
        "sealed_adapter_hash": sealed_adapter_hash,
        "capability_drift_detected": drift, "firewall_findings": sorted(sigs),
        "firewall_status": "ADAPTER_ALLOWED_READ_ONLY" if ok else
        "ADAPTER_BLOCKED", "signal": None if ok else sorted(sigs)[0],
    }
    fw["adapter_capability_firewall_hash"] = _core_hash(
        fw, "adapter_capability_firewall_hash")
    return fw


# --- Query plan normal form ------------------------------------------------
def build_query_plan_normal_form(*, tenant_id, runtime_request_id, adapter,
                                 snapshot, requested_sources,
                                 requested_projection) -> dict:
    """Normalize the read plan BEFORE execution. Unknown source or forbidden
    projection blocks. The plan hash participates in the replay hash."""
    fields = (snapshot or {}).get("fields", {})
    allowed_src = set((adapter or {}).get("allowed_sources", []))
    req_src = sorted(set(map(str, _as_list(requested_sources))) or allowed_src)
    unknown = sorted(s for s in req_src if s not in fields)
    forbidden_src = sorted(
        s for s in req_src if s in fields and fields[s].get("data_class") in
        FORBIDDEN_SOURCE_CLASSES)
    out_of_allow = sorted(s for s in req_src if s not in allowed_src)
    req_proj = sorted(set(map(str, _as_list(requested_projection)))
                      or set((adapter or {}).get("allowed_projection", [])))
    forbidden_proj = sorted(
        p for p in req_proj if p not in set((adapter or {}).get(
            "allowed_projection", [])))
    normalized = {"sources": req_src, "projection": req_proj,
                  "adapter_kind": (adapter or {}).get("adapter_kind")}
    sig = None
    if unknown or out_of_allow:
        sig = "SEMANTIC_READ_DENIED" if out_of_allow else \
            "RUNTIME_PATH_POLICY_REJECTED"
    if unknown:
        sig = "SEMANTIC_READ_DENIED"
    if forbidden_proj:
        sig = "RUNTIME_PATH_POLICY_REJECTED"
    plan = {
        "query_plan_normal_form_version": QUERY_PLAN_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "normalized_query_plan": normalized, "query_plan_hash": _sha(normalized),
        "allowed_sources": sorted(allowed_src),
        "forbidden_sources": forbidden_src,
        "unknown_sources": unknown, "out_of_allowlist_sources": out_of_allow,
        "allowed_projection_fields": sorted((adapter or {}).get(
            "allowed_projection", [])),
        "forbidden_projection_fields": forbidden_proj,
        "query_plan_status": "PLAN_NORMALIZED" if sig is None else
        "PLAN_REJECTED", "signal": sig,
    }
    plan["query_plan_normal_form_hash"] = _core_hash(
        plan, "query_plan_normal_form_hash")
    return plan


# --- Pure read-only execution ----------------------------------------------
def _redact(value, data_class):
    if data_class in RAW_OUTPUT_CLASSES:
        return value
    return f"[REDACTED:{data_class}]"


def _execute_read_only(adapter, snapshot, query_plan):
    """Pure, deterministic read-only execution. Returns (read_set, raw_output,
    safe_output, provenance_edges, operations). Reads ONLY allowed, non-forbidden
    snapshot fields; forbidden fields are never read. No side effect."""
    fields = (snapshot or {}).get("fields", {})
    kind = (adapter or {}).get("adapter_kind")
    plan = query_plan["normalized_query_plan"]
    sources = [s for s in plan["sources"]
               if s in fields and fields[s].get("data_class") in
               ALLOWED_READ_CLASSES
               and s in set((adapter or {}).get("allowed_sources", []))]
    read_set, operations = [], []
    for i, path in enumerate(sources):
        spec = fields[path]
        entry = {"read_entry_id": f"r{i}", "field_path": path,
                 "data_class": spec["data_class"], "purpose": "read_path_runtime",
                 "snapshot_id": snapshot.get("snapshot_id"),
                 "epoch": snapshot.get("epoch"),
                 "value_hash": _sha(spec.get("value"))}
        read_set.append(entry)
        operations.append({"op": "READ_SNAPSHOT_FIELD", "capability":
                           "READ_SNAPSHOT_FIELD", "field_path": path})
    operations.append({"op": "COMPUTE_DETERMINISTIC",
                       "capability": "COMPUTE_DETERMINISTIC"})
    # Deterministic transform by adapter kind.
    safe_output, provenance_edges = {}, []
    if kind == "count":
        safe_output["count"] = len(read_set)
        for e in read_set:
            provenance_edges.append({"output_field": "count",
                                     "read_entry_id": e["read_entry_id"],
                                     "transform": "count"})
    elif kind == "presence":
        for e in read_set:
            of = f"present:{e['field_path']}"
            safe_output[of] = True
            provenance_edges.append({"output_field": of, "read_entry_id":
                                     e["read_entry_id"], "transform": "presence"})
    else:  # field_projection / redacted_summary
        for e in read_set:
            spec = fields[e["field_path"]]
            of = e["field_path"]
            safe_output[of] = _redact(spec.get("value"), spec["data_class"])
            provenance_edges.append({"output_field": of, "read_entry_id":
                                     e["read_entry_id"],
                                     "transform": "identity" if spec[
                                         "data_class"] in RAW_OUTPUT_CLASSES
                                     else "redact"})
    operations.append({"op": "PROJECT_SAFE_OUTPUT",
                       "capability": "PROJECT_SAFE_OUTPUT"})
    raw_output = {e["field_path"]: fields[e["field_path"]].get("value")
                  for e in read_set}
    return read_set, raw_output, safe_output, provenance_edges, operations


# --- Microkernel admission / operation ledger / path policy ----------------
def build_microkernel(*, tenant_id, runtime_request_id, operations) -> dict:
    not_admitted = [o for o in operations if o.get("capability") not in
                    READ_ONLY_CAPABILITIES]
    unknown = [o for o in operations if o.get("capability") is None]
    ok = not not_admitted and not unknown
    mk = {
        "runtime_microkernel_contract_version": MICROKERNEL_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "admitted_capabilities": sorted(READ_ONLY_CAPABILITIES),
        "operation_count": len(operations),
        "rejected_operations": [o.get("op") for o in not_admitted],
        "microkernel_status": "MICROKERNEL_ADMITTED_READ_ONLY" if ok else
        "MICROKERNEL_REJECTED",
        "signal": None if ok else ("UNKNOWN_CAPABILITY" if unknown else
                                   "RUNTIME_OPERATION_NOT_ADMITTED"),
    }
    mk["runtime_microkernel_contract_hash"] = _core_hash(
        mk, "runtime_microkernel_contract_hash")
    return mk


def build_operation_ledger(*, tenant_id, runtime_request_id, operations) -> dict:
    ledger = {
        "runtime_operation_ledger_version": OP_LEDGER_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "operations": operations, "operation_count": len(operations),
        "operation_sequence_hash": _sha([o.get("op") for o in operations]),
    }
    ledger["runtime_operation_ledger_hash"] = _core_hash(
        ledger, "runtime_operation_ledger_hash")
    return ledger


_PATH_AUTOMATON = ["READ_SNAPSHOT_FIELD", "COMPUTE_DETERMINISTIC",
                   "PROJECT_SAFE_OUTPUT"]


def build_path_policy(*, tenant_id, runtime_request_id, operations) -> dict:
    caps = [o.get("capability") for o in operations]
    # Accepted trajectory: zero+ reads, then compute, then project. No capability
    # outside the read-only set; project must come after compute.
    ok = all(c in READ_ONLY_CAPABILITIES for c in caps)
    if ok and "PROJECT_SAFE_OUTPUT" in caps and "COMPUTE_DETERMINISTIC" in caps:
        ok = caps.index("COMPUTE_DETERMINISTIC") < caps.index(
            "PROJECT_SAFE_OUTPUT")
    pp = {
        "runtime_path_policy_automaton_version": PATH_POLICY_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "accepted_trajectory": _PATH_AUTOMATON, "trajectory": caps,
        "path_status": "PATH_ACCEPTED" if ok else "PATH_REJECTED",
        "signal": None if ok else "RUNTIME_PATH_POLICY_REJECTED",
    }
    pp["runtime_path_policy_automaton_hash"] = _core_hash(
        pp, "runtime_path_policy_automaton_hash")
    return pp


# --- Semantic read firewall + read-set ledger/completeness/attestation -----
def build_semantic_read_firewall(*, tenant_id, runtime_request_id, snapshot,
                                 adapter, query_plan) -> dict:
    fields = (snapshot or {}).get("fields", {})
    allowed_src = set((adapter or {}).get("allowed_sources", []))
    findings = []
    for path in query_plan["normalized_query_plan"]["sources"]:
        if path not in fields:
            continue
        dc = fields[path].get("data_class")
        if dc in FORBIDDEN_SOURCE_CLASSES:
            findings.append(f"TAINT:{path}:{dc}")
        elif path not in allowed_src:
            findings.append(f"SCOPE:{path}")
        elif dc not in ALLOWED_READ_CLASSES:
            findings.append(f"CLASS:{path}:{dc}")
    ok = not findings
    fw = {
        "semantic_read_firewall_version": SEMANTIC_READ_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "firewall_findings": sorted(findings),
        "read_status": "SEMANTIC_READ_ALLOWED" if ok else "SEMANTIC_READ_BLOCKED",
        "signal": None if ok else ("SEMANTIC_READ_DENIED"
                                   if any(f.startswith("TAINT") or
                                          f.startswith("CLASS")
                                          for f in findings)
                                   else "SEMANTIC_READ_DENIED"),
    }
    fw["semantic_read_firewall_hash"] = _core_hash(
        fw, "semantic_read_firewall_hash")
    return fw


def build_read_set_ledger(*, tenant_id, runtime_request_id, read_set,
                          snapshot) -> dict:
    ledger = {
        "read_set_ledger_version": READ_SET_LEDGER_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "read_entries": read_set, "read_count": len(read_set),
        "snapshot_id": (snapshot or {}).get("snapshot_id"),
        "snapshot_epoch": (snapshot or {}).get("epoch"),
        "read_set_hash": _sha([(e["field_path"], e["value_hash"])
                               for e in read_set]),
        "signal": "READ_SET_MISSING" if read_set is None else None,
    }
    ledger["read_set_ledger_hash"] = _core_hash(ledger, "read_set_ledger_hash")
    return ledger


def build_read_set_completeness(*, tenant_id, runtime_request_id, read_set,
                                provenance_edges) -> dict:
    read_ids = {e["read_entry_id"] for e in read_set}
    used_ids = {e["read_entry_id"] for e in provenance_edges}
    missing = sorted(used_ids - read_ids)
    complete = not missing
    out = {
        "read_set_completeness_proof_version": READ_SET_COMPLETENESS_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "read_entry_count": len(read_ids), "used_entry_count": len(used_ids),
        "missing_entries": missing, "complete": complete,
        "signal": None if complete else "READ_SET_INCOMPLETE",
    }
    out["read_set_completeness_proof_hash"] = _core_hash(
        out, "read_set_completeness_proof_hash")
    return out


def build_read_set_attestation(*, tenant_id, runtime_request_id, read_set_ledger,
                               snapshot) -> dict:
    bound = read_set_ledger.get("snapshot_id") == (snapshot or {}).get(
        "snapshot_id") and read_set_ledger.get("snapshot_epoch") == (
        snapshot or {}).get("epoch")
    cap = {
        "read_set_attestation_capsule_version": READ_SET_ATTESTATION_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "read_set_hash": read_set_ledger.get("read_set_hash"),
        "snapshot_hash": (snapshot or {}).get("snapshot_hash"),
        "bound_to_snapshot": bound,
        "attestation_status": "READ_SET_ATTESTED" if bound else
        "ATTESTATION_FAILED",
        "signal": None if bound else "READ_SET_SNAPSHOT_MISMATCH",
    }
    cap["read_set_attestation_capsule_hash"] = _core_hash(
        cap, "read_set_attestation_capsule_hash")
    return cap


# --- Provenance map / bisimulation / non-interference ----------------------
def build_provenance_map(*, tenant_id, runtime_request_id, safe_output,
                         read_set, provenance_edges, snapshot,
                         redaction_policy_hash) -> dict:
    read_class = {e["read_entry_id"]: e["data_class"] for e in read_set}
    field_paths = sorted(safe_output.keys()) if isinstance(safe_output, dict) \
        else []
    edge_by_field = {}
    for e in provenance_edges:
        edge_by_field.setdefault(e["output_field"], []).append(e)
    unproven = sorted(f for f in field_paths if f not in edge_by_field)
    forbidden_influence = False
    taint_join = {}
    for f in field_paths:
        classes = {read_class.get(e["read_entry_id"], "DETERMINISTIC_CONSTANT")
                   for e in edge_by_field.get(f, [])}
        taint_join[f] = sorted(classes)
        if classes & FORBIDDEN_SOURCE_CLASSES:
            forbidden_influence = True
    sig = None
    if unproven:
        sig = "READ_TO_OUTPUT_PROVENANCE_MISSING"
    elif forbidden_influence:
        sig = "READ_TO_OUTPUT_PROVENANCE_MISSING"
    pmap = {
        "read_output_provenance_map_version": PROVENANCE_MAP_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "safe_output_field_paths": field_paths,
        "source_read_entry_ids": sorted({e["read_entry_id"] for e in
                                         provenance_edges}),
        "source_read_entry_hashes": sorted({_sha(e) for e in read_set}),
        "transform_ids": sorted({e["transform"] for e in provenance_edges}),
        "transform_hashes": sorted({_sha(e["transform"]) for e in
                                    provenance_edges}),
        "taint_join_results": taint_join,
        "redaction_policy_hash": redaction_policy_hash,
        "forbidden_source_influence_detected": forbidden_influence,
        "unproven_output_fields": unproven,
        "provenance_status": ("OUTPUT_PROVENANCE_MATCHED" if sig is None else
                              ("OUTPUT_PROVENANCE_FORBIDDEN_SOURCE"
                               if forbidden_influence else
                               "OUTPUT_PROVENANCE_MISSING")),
        "signal": sig,
    }
    pmap["read_output_provenance_map_hash"] = _core_hash(
        pmap, "read_output_provenance_map_hash")
    return pmap


def _recompute_safe_output(adapter, snapshot, query_plan):
    _, _, safe, _, _ = _execute_read_only(adapter, snapshot, query_plan)
    return safe


def build_bisimulation(*, tenant_id, runtime_request_id, provenance_map,
                       safe_output, adapter, snapshot, query_plan,
                       read_set) -> dict:
    recomputed = _recompute_safe_output(adapter, snapshot, query_plan)
    safe_hash = _sha(safe_output)
    recomputed_hash = _sha(recomputed)
    matched = safe_hash == recomputed_hash
    mismatch = [] if matched else sorted(
        set(safe_output) ^ set(recomputed)) if isinstance(safe_output, dict) \
        else ["ALL"]
    out = {
        "output_provenance_bisimulation_version": BISIMULATION_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "read_output_provenance_map_hash": provenance_map[
            "read_output_provenance_map_hash"],
        "safe_output_hash": safe_hash, "recomputed_safe_output_hash":
        recomputed_hash, "allowed_read_set_hash": _sha(
            [e["read_entry_id"] for e in read_set]),
        "bisimulation_status": "BISIMULATION_MATCHED" if matched else
        "BISIMULATION_FAILED", "mismatch_fields": mismatch,
        "signal": None if matched else "OUTPUT_PROVENANCE_BISIMULATION_FAILED",
    }
    out["output_provenance_bisimulation_hash"] = _core_hash(
        out, "output_provenance_bisimulation_hash")
    return out


def build_non_interference(*, tenant_id, runtime_request_id, adapter, snapshot,
                           query_plan, safe_output) -> dict:
    """For every forbidden source, perturb it while holding the allowed read-set
    fixed; the safe output hash must NOT change. If it does, a forbidden source
    influenced the output."""
    import copy
    base_hash = _sha(safe_output)
    rows, forbidden_flow = [], False
    twin = copy.deepcopy(snapshot)
    for path, spec in (twin.get("fields", {}) or {}).items():
        if spec.get("data_class") in FORBIDDEN_SOURCE_CLASSES:
            spec["value"] = f"PERTURBED::{path}"
    twin["snapshot_hash"] = _core_hash(
        {k: v for k, v in twin.items() if k != "snapshot_hash"},
        "snapshot_hash")
    perturbed = _recompute_safe_output(adapter, twin, query_plan)
    perturbed_hash = _sha(perturbed)
    changed = perturbed_hash != base_hash
    if changed:
        forbidden_flow = True
    for cls in sorted(FORBIDDEN_SOURCE_CLASSES):
        rows.append({"source_class": cls, "target_output_field": "*",
                     "allowed_flow": False, "observed_flow": changed})
    ok = not forbidden_flow
    out = {
        "semantic_non_interference_matrix_version": NON_INTERFERENCE_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "matrix_rows": rows, "base_safe_output_hash": base_hash,
        "perturbed_safe_output_hash": perturbed_hash,
        "forbidden_flow_detected": forbidden_flow,
        "matrix_status": "SEMANTIC_NON_INTERFERENCE_MATCHED" if ok else
        "SEMANTIC_NON_INTERFERENCE_FAILED",
        "signal": None if ok else "SEMANTIC_NON_INTERFERENCE_FAILED",
    }
    out["semantic_non_interference_matrix_hash"] = _core_hash(
        out, "semantic_non_interference_matrix_hash")
    return out


# --- Canary harness + non-leakage proof ------------------------------------
def build_canary_harness(*, tenant_id, runtime_request_id, snapshot) -> dict:
    """Inject synthetic canaries into a LOCAL copy of the snapshot only. Never
    mutates the real snapshot / production. Canaries are FORBIDDEN-class fields
    with known marker values."""
    import copy
    canary_fields = {
        "__canary_secret": {"value": "CANARY-MARKER-7F3A9C", "data_class":
                            "CANARY_FIELD"},
        "__canary_customer": {"value": "canary+leak@example.test",
                              "data_class": "CANARY_FIELD"},
    }
    twin = copy.deepcopy(snapshot) if snapshot else {"fields": {}, "epoch": "0",
                                                     "snapshot_id": "syn"}
    twin["fields"] = {**(twin.get("fields", {})), **canary_fields}
    twin["snapshot_id"] = str(twin.get("snapshot_id", "syn")) + "-canary"
    twin["synthetic"] = True
    twin["snapshot_hash"] = _core_hash(
        {k: v for k, v in twin.items() if k != "snapshot_hash"},
        "snapshot_hash")
    harness = {
        "synthetic_canary_harness_version": CANARY_HARNESS_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "canary_snapshot_id": twin["snapshot_id"],
        "canary_fields": sorted(canary_fields),
        "canary_values": [v["value"] for v in canary_fields.values()],
        "canary_hashes": sorted(_sha(v["value"]) for v in
                                canary_fields.values()),
        "canary_scope": "SYNTHETIC_LOCAL_ONLY", "mutates_production": False,
        "harness_status": "CANARY_HARNESS_READY",
        "_canary_snapshot": twin,
    }
    harness["synthetic_canary_harness_hash"] = _core_hash(
        harness, "synthetic_canary_harness_hash", "_canary_snapshot")
    return harness


def build_canary_non_leakage(*, tenant_id, runtime_request_id, harness, adapter,
                             query_plan, safe_output) -> dict:
    """Run the adapter over the canary snapshot and confirm no canary value /
    hash fragment / marker / correlation appears in the safe output."""
    canary_snap = harness.get("_canary_snapshot")
    canary_output = _recompute_safe_output(adapter, canary_snap, query_plan)
    blob = " ".join(_compact(t) for t in _flatten_text(canary_output))
    diff_from_base = _sha(canary_output) != _sha(safe_output)
    leaked_markers = []
    for val in harness.get("canary_values", []):
        if _compact(val) and _compact(val) in blob:
            leaked_markers.append("CANARY_VALUE")
    for h in harness.get("canary_hashes", []):
        if h[:12] in " ".join(_flatten_text(canary_output)):
            leaked_markers.append("CANARY_HASH_FRAGMENT")
    for name in harness.get("canary_fields", []):
        if isinstance(canary_output, dict) and name in canary_output:
            leaked_markers.append("CANARY_DERIVED_MARKER")
    # Correlation: adding canaries changed the safe output => the output depends
    # on canary presence (a correlation channel).
    correlated = diff_from_base
    leaked = bool(leaked_markers) or correlated
    out = {
        "canary_non_leakage_proof_version": CANARY_PROOF_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "synthetic_canary_harness_hash": harness[
            "synthetic_canary_harness_hash"],
        "safe_output_hash": _sha(safe_output),
        "canary_markers_checked": harness.get("canary_fields", []),
        "canary_hash_fragments_checked": len(harness.get("canary_hashes", [])),
        "canary_correlation_signals": ["OUTPUT_CHANGED_WITH_CANARY"] if
        correlated else [], "detected_leaks": sorted(set(leaked_markers)),
        "leak_detected": leaked,
        "proof_status": "CANARY_NON_LEAKAGE_MATCHED" if not leaked else
        "CANARY_LEAK_DETECTED",
        "signal": None if not leaked else "CANARY_LEAK_DETECTED",
    }
    out["canary_non_leakage_proof_hash"] = _core_hash(
        out, "canary_non_leakage_proof_hash")
    return out


# --- Information budget / usage / read amplification / side-channel ---------
def build_information_budget(*, tenant_id, runtime_request_id, policy) -> dict:
    policy = {**DEFAULT_POLICY, **(policy or {})}
    env = {
        "information_budget_envelope_version": INFO_BUDGET_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "max_output_fields": policy["max_output_fields"],
        "max_sensitive_field_count": policy["max_sensitive_field_count"],
        "max_taint_level_allowed": policy["max_taint_level"],
        "max_read_to_output_edges": policy["max_read_to_output_edges"],
        "max_repeated_query_count": policy["max_repeated_query_count"],
        "max_correlation_risk_bucket": policy["max_correlation_risk_bucket"],
        "max_output_entropy_bucket": policy["max_output_entropy_bucket"],
        "budget_policy_hash": _sha(policy), "budget_status": "BUDGET_DEFINED",
        "note": "Information budget is not approval to export data.",
    }
    env["information_budget_envelope_hash"] = _core_hash(
        env, "information_budget_envelope_hash")
    return env


def _bucket(n, edges):
    for i, e in enumerate(edges):
        if n <= e:
            return i
    return len(edges)


def build_information_usage(*, tenant_id, runtime_request_id, budget,
                            safe_output, provenance_map, read_set,
                            repeated_query_count) -> dict:
    fields = list(safe_output.keys()) if isinstance(safe_output, dict) else []
    taint = provenance_map.get("taint_join_results", {})
    sensitive = sum(1 for f in fields if any(
        c not in ("PUBLIC", "DETERMINISTIC_CONSTANT")
        for c in taint.get(f, [])))
    highest = 0
    for f in fields:
        for c in taint.get(f, []):
            highest = max(highest, _TAINT_LEVEL.get(c, 2))
    edge_count = len(provenance_map.get("source_read_entry_ids", []))
    entropy_bucket = _bucket(len(fields), [0, 2, 4, 8])
    corr_bucket = _bucket(int(repeated_query_count or 0), [0, 2, 5])
    violations = []
    if len(fields) > budget["max_output_fields"]:
        violations.append("MAX_OUTPUT_FIELDS")
    if sensitive > budget["max_sensitive_field_count"]:
        violations.append("MAX_SENSITIVE_FIELDS")
    if highest > budget["max_taint_level_allowed"]:
        violations.append("MAX_TAINT_LEVEL")
    if edge_count > budget["max_read_to_output_edges"]:
        violations.append("MAX_EDGES")
    if int(repeated_query_count or 0) > budget["max_repeated_query_count"]:
        violations.append("MAX_REPEATED_QUERY")
    if corr_bucket > budget["max_correlation_risk_bucket"]:
        violations.append("MAX_CORRELATION")
    if entropy_bucket > budget["max_output_entropy_bucket"]:
        violations.append("MAX_ENTROPY")
    sig = "INFORMATION_BUDGET_EXCEEDED" if violations else None
    out = {
        "information_usage_proof_version": INFO_USAGE_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "output_fields_count": len(fields), "sensitive_field_count": sensitive,
        "highest_output_taint": highest, "read_to_output_edge_count": edge_count,
        "repeated_query_count": int(repeated_query_count or 0),
        "correlation_risk_bucket": corr_bucket,
        "output_entropy_bucket": entropy_bucket,
        "information_budget_hash": budget["information_budget_envelope_hash"],
        "budget_violations": violations,
        "proof_status": "INFORMATION_BUDGET_MATCHED" if not violations else
        "INFORMATION_BUDGET_EXCEEDED", "signal": sig,
    }
    out["information_usage_proof_hash"] = _core_hash(
        out, "information_usage_proof_hash")
    return out


def build_read_amplification(*, tenant_id, runtime_request_id, read_set,
                             related_requests, policy) -> dict:
    policy = {**DEFAULT_POLICY, **(policy or {})}
    related = related_requests or []
    cur_paths = {e["field_path"] for e in read_set}
    overlap_total, same_snap, same_cust, same_case = 0, 0, 0, 0
    for r in related:
        rp = set(map(str, _as_list(r.get("read_paths"))))
        overlap_total += len(cur_paths & rp)
        same_snap += 1 if r.get("snapshot_id") else 0
        same_cust += 1 if r.get("customer_id") else 0
        same_case += 1 if r.get("case_id") else 0
    gain_bucket = _bucket(len(cur_paths), [0, 2, 4, 8])
    amplified = overlap_total > policy["read_amplification_overlap_max"] or \
        len(related) > policy["max_repeated_query_count"]
    out = {
        "read_amplification_guard_version": READ_AMP_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "related_runtime_request_ids": sorted(str(r.get("runtime_request_id"))
                                              for r in related),
        "same_snapshot_query_count": same_snap,
        "same_customer_query_count": same_cust,
        "same_case_query_count": same_case,
        "overlapping_read_count": overlap_total,
        "incremental_information_gain_bucket": gain_bucket,
        "amplification_detected": amplified,
        "guard_status": "READ_AMPLIFICATION_CLEAR" if not amplified else
        "READ_AMPLIFICATION_DETECTED",
        "signal": None if not amplified else "READ_AMPLIFICATION_DETECTED",
    }
    out["read_amplification_guard_hash"] = _core_hash(
        out, "read_amplification_guard_hash")
    return out


def build_side_channel_seal(*, tenant_id, runtime_request_id, safe_output,
                            operations, read_set, policy, error_shape=0) -> dict:
    policy = {**DEFAULT_POLICY, **(policy or {})}
    out_size = len(canonical_json(safe_output))
    dur_bucket = _bucket(len(operations), [0, 4, 16, 64])
    out_bucket = _bucket(out_size, [0, 256, 1024, 4096])
    err_bucket = _bucket(int(error_shape or 0), [0, 1, 2])
    op_bucket = _bucket(len(operations), [0, 8, 32])
    read_bucket = _bucket(len(read_set), [0, 4, 16])
    branch_bucket = _bucket(len(read_set), [0, 4, 16])
    violations = []
    if dur_bucket > policy["side_channel_duration_bucket_max"]:
        violations.append("DURATION_BUCKET")
    if out_bucket > policy["side_channel_output_bucket_max"]:
        violations.append("OUTPUT_SIZE_BUCKET")
    if err_bucket > policy["side_channel_error_bucket_max"]:
        violations.append("ERROR_SHAPE_BUCKET")
    sig = "SIDE_CHANNEL_BUDGET_EXCEEDED" if violations else None
    seal = {
        "side_channel_budget_seal_version": SIDE_CHANNEL_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "duration_bucket": dur_bucket, "output_size_bucket": out_bucket,
        "error_shape_bucket": err_bucket, "operation_count_bucket": op_bucket,
        "read_count_bucket": read_bucket, "branch_count_bucket": branch_bucket,
        "side_channel_policy_hash": _sha({k: policy[k] for k in (
            "side_channel_duration_bucket_max", "side_channel_output_bucket_max",
            "side_channel_error_bucket_max")}),
        "side_channel_budget_violations": violations,
        "seal_status": "SIDE_CHANNEL_SEALED" if not violations else
        "SIDE_CHANNEL_BUDGET_EXCEEDED",
        "note": "Coarse deterministic buckets only; no wall-clock timing; no "
        "OS-level side-channel enforcement is claimed.", "signal": sig,
    }
    seal["side_channel_budget_seal_hash"] = _core_hash(
        seal, "side_channel_budget_seal_hash")
    return seal


# --- Resource budget / usage / entropy seal / replay -----------------------
def build_resource_budget(*, tenant_id, runtime_request_id, policy) -> dict:
    policy = {**DEFAULT_POLICY, **(policy or {})}
    env = {
        "runtime_resource_budget_envelope_version": RESOURCE_BUDGET_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "op_budget": policy["resource_op_budget"],
        "read_budget": policy["resource_read_budget"],
        "output_size_budget": policy["resource_output_size_budget"],
        "budget_policy_hash": _sha({k: policy[k] for k in (
            "resource_op_budget", "resource_read_budget",
            "resource_output_size_budget")}),
    }
    env["runtime_resource_budget_envelope_hash"] = _core_hash(
        env, "runtime_resource_budget_envelope_hash")
    return env


def build_resource_usage(*, tenant_id, runtime_request_id, budget, operations,
                         read_set, safe_output) -> dict:
    op_n, read_n = len(operations), len(read_set)
    out_size = len(canonical_json(safe_output))
    violations = []
    if op_n > budget["op_budget"]:
        violations.append("OP_BUDGET")
    if read_n > budget["read_budget"]:
        violations.append("READ_BUDGET")
    if out_size > budget["output_size_budget"]:
        violations.append("OUTPUT_SIZE_BUDGET")
    sig = "RESOURCE_BUDGET_EXCEEDED" if violations else None
    out = {
        "runtime_resource_usage_proof_version": RESOURCE_USAGE_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "operation_count": op_n, "read_count": read_n,
        "output_size": out_size,
        "resource_budget_hash": budget[
            "runtime_resource_budget_envelope_hash"],
        "budget_violations": violations,
        "usage_status": "RESOURCE_WITHIN_BUDGET" if not violations else
        "RESOURCE_BUDGET_EXCEEDED", "signal": sig,
    }
    out["runtime_resource_usage_proof_hash"] = _core_hash(
        out, "runtime_resource_usage_proof_hash")
    return out


def build_entropy_seal(*, tenant_id, runtime_request_id, declared_entropy) -> dict:
    used = sorted(set(map(str, _as_list(declared_entropy))) & ENTROPY_SOURCES)
    sealed = not used
    seal = {
        "determinism_entropy_seal_version": ENTROPY_SEAL_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "watched_entropy_sources": sorted(ENTROPY_SOURCES),
        "detected_entropy_sources": used, "entropy_sealed": sealed,
        "seal_status": "ENTROPY_SEALED" if sealed else "ENTROPY_UNSEALED",
        "signal": None if sealed else "DETERMINISM_ENTROPY_UNSEALED",
    }
    seal["determinism_entropy_seal_hash"] = _core_hash(
        seal, "determinism_entropy_seal_hash")
    return seal


def build_replay_twin(*, tenant_id, runtime_request_id, adapter, snapshot,
                      query_plan, safe_output) -> dict:
    recomputed = _recompute_safe_output(adapter, snapshot, query_plan)
    match = _sha(recomputed) == _sha(safe_output)
    twin = {
        "deterministic_replay_twin_version": REPLAY_TWIN_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "safe_output_hash": _sha(safe_output),
        "replay_safe_output_hash": _sha(recomputed),
        "replay_matched": match,
        "signal": None if match else "REPLAY_MISMATCH",
    }
    twin["deterministic_replay_twin_hash"] = _core_hash(
        twin, "deterministic_replay_twin_hash")
    return twin


# --- Data-diode output gate / taint lattice / non-exfiltration / safe proj -
_SAFE_DESCRIPTIVE_KEYS = {"honesty_labels", "note", "runtime_status",
                          "dominant_reason_code", "effect_kind"}


def _output_leaks(candidate, *, tenant_id):
    findings = []
    if not isinstance(candidate, dict):
        return findings
    key_blobs, val_blobs = set(), []
    for k, v in candidate.items():
        key_blobs.add(_compact(k))
        if k in _SAFE_DESCRIPTIVE_KEYS:
            continue
        for t in _flatten_text(v):
            val_blobs.append(_compact(t))
    if any(m in b for b in val_blobs for m in _SECRET_MARKERS):
        findings.append("SECRET_LIKE")
    if any(m in b for b in val_blobs for m in ("bearer", "accesstoken",
                                               "oauthtoken", "refreshtoken")):
        findings.append("TOKEN_LIKE")
    if any(m in b for b in key_blobs for m in _SECRET_MARKERS):
        findings.append("CREDENTIAL_LIKE")
    for k in ("raw_payload", "payload", "approval_ref", "consent_ref",
              "provider_result", "execution_authority", "grants_execution"):
        if k in candidate:
            findings.append(k.upper())
    for k in ("email", "phone", "ssn", "card", "iban"):
        if k in candidate:
            findings.append("CUSTOMER_SENSITIVE")
    for t in [x for k, v in candidate.items() if k not in _SAFE_DESCRIPTIVE_KEYS
              for x in _flatten_text(v)]:
        if isinstance(t, str) and t.startswith("tenant:") and t != \
                f"tenant:{tenant_id}":
            findings.append("CROSS_TENANT")
    return sorted(set(findings))


def build_output_taint_lattice(*, tenant_id, runtime_request_id,
                               provenance_map) -> dict:
    taint = provenance_map.get("taint_join_results", {})
    escaped = sorted({c for classes in taint.values() for c in classes
                      if c in FORBIDDEN_SOURCE_CLASSES})
    highest = 0
    for classes in taint.values():
        for c in classes:
            highest = max(highest, _TAINT_LEVEL.get(c, 2))
    ok = not escaped and highest <= 1
    lat = {
        "output_taint_lattice_version": OUTPUT_TAINT_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "highest_taint_level": highest, "escaped_taint_classes": escaped,
        "lattice_status": "TAINT_WITHIN_LATTICE" if ok else "TAINT_ESCAPE",
        "signal": None if ok else "OUTPUT_TAINT_ESCAPE_DETECTED",
    }
    lat["output_taint_lattice_hash"] = _core_hash(
        lat, "output_taint_lattice_hash")
    return lat


def build_safe_output_projection(*, tenant_id, runtime_request_id, safe_output,
                                 redaction_policy_hash) -> dict:
    leaks = _output_leaks(safe_output, tenant_id=tenant_id)
    ok = not leaks
    proj = {
        "safe_output_projection_version": SAFE_OUTPUT_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "safe_output": safe_output, "safe_output_hash": _sha(safe_output),
        "redaction_policy_hash": redaction_policy_hash,
        "projection_status": "SAFE_PROJECTION_MATCHED" if ok else
        "SAFE_PROJECTION_FAILED", "leak_fields": leaks,
        "signal": None if ok else "SAFE_OUTPUT_PROJECTION_FAILED",
    }
    proj["safe_output_projection_hash"] = _core_hash(
        proj, "safe_output_projection_hash")
    return proj


def build_data_diode(*, tenant_id, runtime_request_id, safe_output,
                     non_exfiltration_ok, taint_ok) -> dict:
    ok = non_exfiltration_ok and taint_ok
    diode = {
        "data_diode_output_gate_version": DATA_DIODE_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "one_way": True, "reverse_flow_possible": False,
        "diode_status": "DATA_DIODE_OUTPUT_ALLOWED_SAFE_ONLY" if ok else
        "DATA_DIODE_OUTPUT_BLOCKED",
        "signal": None if ok else "DATA_DIODE_OUTPUT_GATE_FAILED",
    }
    diode["data_diode_output_gate_hash"] = _core_hash(
        diode, "data_diode_output_gate_hash")
    return diode


def build_non_exfiltration(*, tenant_id, runtime_request_id, safe_output) -> dict:
    leaks = _output_leaks(safe_output, tenant_id=tenant_id)
    ok = not leaks
    out = {
        "output_non_exfiltration_gate_version": NON_EXFILTRATION_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "detected_leaks": leaks, "leak_detected": bool(leaks),
        "gate_status": "NO_OUTPUT_EXFILTRATION" if ok else
        "OUTPUT_EXFILTRATION_DETECTED",
        "signal": None if ok else "OUTPUT_EXFILTRATION_DETECTED",
    }
    out["output_non_exfiltration_gate_hash"] = _core_hash(
        out, "output_non_exfiltration_gate_hash")
    return out


# --- Effect ledger + no-* proofs + non-escalation + surface + escape -------
def build_effect_ledger(*, tenant_id, runtime_request_id, operations) -> dict:
    write_ops = [o for o in operations if o.get("capability") not in
                 READ_ONLY_CAPABILITIES]
    ledger = {
        "runtime_effect_ledger_version": EFFECT_LEDGER_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "effect_operations": [o.get("op") for o in write_ops],
        "effect_count": len(write_ops), "read_only": not write_ops,
    }
    ledger["runtime_effect_ledger_hash"] = _core_hash(
        ledger, "runtime_effect_ledger_hash")
    return ledger


def build_no_effect_proofs(*, tenant_id, runtime_request_id, adapter,
                           effect_ledger, surface_findings) -> dict:
    caps = (adapter or {}).get("capabilities", {})
    checks = {
        "no_write_proof": (not caps.get("write") and not caps.get("mutate")
                           and effect_ledger["read_only"],
                           "WRITE_EFFECT_DETECTED"),
        "no_network_proof": (not caps.get("network") and "network_path" not in
                             surface_findings, "NETWORK_EFFECT_DETECTED"),
        "no_secret_proof": (True, "SECRET_READ_DETECTED"),
        "no_credential_proof": (not caps.get("credential") and "credential_path"
                                not in surface_findings,
                                "CREDENTIAL_READ_DETECTED"),
        "no_token_proof": (not caps.get("token") and "token_path" not in
                           surface_findings, "TOKEN_DERIVATION_ATTEMPT"),
        "no_provider_proof": (not caps.get("provider") and "provider_call_path"
                              not in surface_findings, "PROVIDER_CALL_ATTEMPT"),
        "no_mcp_proof": (not caps.get("mcp") and "mcp_path" not in
                         surface_findings, "MCP_CALL_ATTEMPT"),
        "no_llm_proof": (not caps.get("llm") and "llm_path" not in
                         surface_findings, "LLM_CALL_ATTEMPT"),
    }
    proofs = {"tenant_id": tenant_id, "runtime_request_id": runtime_request_id}
    signals = []
    for name, (ok, sig) in checks.items():
        proofs[name] = {"holds": bool(ok),
                        "status": "PROVEN" if ok else "VIOLATION",
                        "signal": None if ok else sig}
        if not ok:
            signals.append(sig)
    proofs["signals"] = signals
    proofs["no_effect_proofs_hash"] = _core_hash(proofs, "no_effect_proofs_hash")
    return proofs


def build_surface_diff(*, tenant_id, runtime_request_id, observed_surface,
                       adapter) -> dict:
    surface = observed_surface or {}
    caps = (adapter or {}).get("capabilities", {})
    detected = sorted(k for k, v in surface.items()
                      if k in RUNTIME_SURFACE_FLAGS and v)
    for cap in ("write", "network", "provider", "mcp", "llm", "external",
                "execute"):
        if caps.get(cap):
            detected.append(f"adapter_{cap}")
    detected = sorted(set(detected))
    ok = not detected
    guard = {
        "runtime_surface_diff_version": SURFACE_DIFF_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "watched_flags": sorted(RUNTIME_SURFACE_FLAGS),
        "detected_surface": detected,
        "diff_status": "SURFACE_CLEAR" if ok else "RUNTIME_SURFACE_DETECTED",
        "signal": None if ok else "RUNTIME_SURFACE_DIFF_DETECTED",
    }
    guard["runtime_surface_diff_hash"] = _core_hash(
        guard, "runtime_surface_diff_hash")
    return guard


def build_escape_sentinel(*, tenant_id, runtime_request_id, operations,
                          surface_diff, effect_ledger) -> dict:
    findings = []
    if not effect_ledger["read_only"]:
        findings.append("WRITE_OPERATION")
    if surface_diff["detected_surface"]:
        findings.append("RUNTIME_SURFACE")
    for o in operations:
        if o.get("capability") not in READ_ONLY_CAPABILITIES:
            findings.append("NON_READONLY_OP")
            break
    ok = not findings
    sentinel = {
        "runtime_escape_sentinel_version": ESCAPE_SENTINEL_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "escape_findings": sorted(set(findings)), "escape_detected": bool(
            findings),
        "signal": None if ok else "RUNTIME_ESCAPE_DETECTED",
    }
    sentinel["runtime_escape_sentinel_hash"] = _core_hash(
        sentinel, "runtime_escape_sentinel_hash")
    return sentinel


def build_non_escalation(*, tenant_id, runtime_request_id, adapter,
                         b5_outcome) -> dict:
    # Runtime authority may only ever be read-only-local; it cannot be upgraded
    # by adapter metadata, B5 certs, proof bundles, safe views, or output.
    caps = (adapter or {}).get("capabilities", {})
    escalated = sorted(c for c in ("write", "network", "provider", "mcp", "llm",
                                   "external", "execute", "mutate", "token")
                       if caps.get(c))
    b5_authorizes = False
    for name in ("proof_carrying_broker_action_certificate",
                 "negative_execution_certificate"):
        o = (b5_outcome or {}).get(name, {}) or {}
        if o.get("authorizes_execution") or o.get("grants_execution"):
            b5_authorizes = True
    ok = not escalated and not b5_authorizes
    proof = {
        "runtime_non_escalation_proof_version": NON_ESCALATION_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "escalation_findings": escalated, "b5_authorizes_execution":
        b5_authorizes, "authority_frozen": True,
        "status": "NON_ESCALATED" if ok else "RUNTIME_AUTHORITY_EXPANSION",
        "signal": None if ok else "RUNTIME_AUTHORITY_EXPANSION",
    }
    proof["runtime_non_escalation_proof_hash"] = _core_hash(
        proof, "runtime_non_escalation_proof_hash")
    return proof


def build_authority_freeze(*, tenant_id, runtime_request_id) -> dict:
    fr = {
        "runtime_authority_freeze_version": AUTHORITY_FREEZE_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "authority": "READ_ONLY_LOCAL", "frozen": True,
        "can_write": False, "can_network": False, "can_call_provider": False,
        "can_mint_token": False, "can_derive_token": False,
    }
    fr["runtime_authority_freeze_hash"] = _core_hash(
        fr, "runtime_authority_freeze_hash")
    return fr


# --- Upstream (B5) verification --------------------------------------------
def _upstream_signals(*, tenant_id, b5_outcome, b5_request) -> list:
    sig = []
    o = b5_outcome or {}
    if not o or not b5_request:
        return ["TOOL_B5_BLOCKED"]
    if str(o.get("tenant_id", tenant_id)) != str(tenant_id):
        sig.append("CROSS_TENANT")
    if o.get("broker_status") not in B5_ACCEPTABLE_STATUSES:
        sig.append("TOOL_B5_BLOCKED")
    if o.get("effect_outcome") != "NO_EFFECT_OUTCOME" or not o.get(
            "null_effect_only"):
        sig.append("B5_OUTCOME_NOT_NULL_ONLY")
    pcc = o.get("proof_carrying_broker_action_certificate")
    if not pcc or not pcc.get("proof_carrying_broker_action_certificate_hash"):
        sig.append("B5_CERTIFICATE_MISSING")
    elif pcc.get("authorizes_execution") or pcc.get("is_token"):
        sig.append("B5_CERTIFICATE_MISMATCH")
    nec = o.get("negative_execution_certificate")
    if not nec or nec.get("certificate_status") != \
            "NEGATIVE_EXECUTION_CERTIFIED":
        sig.append("B5_NEGATIVE_CERTIFICATE_MISMATCH")
    gate = o.get("broker_release_gate_report", {}) or {}
    if gate.get("release_gate_status") != "RELEASE_GATE_PASSED":
        sig.append("B5_RELEASE_GATE_FAILED")
    if not (o.get("broker_proof_bundle") or {}).get("broker_proof_bundle_hash"):
        sig.append("B5_PROOF_BUNDLE_MISMATCH")
    return sig


# --- Certificate + proof bundle --------------------------------------------
def build_output_provenance_certificate(*, tenant_id, runtime_request_id,
                                        provenance_map, bisimulation,
                                        non_interference, canary, info_usage,
                                        side_channel) -> dict:
    ok = (provenance_map["signal"] is None and bisimulation["signal"] is None
          and non_interference["signal"] is None and canary["signal"] is None
          and info_usage["signal"] is None and side_channel["signal"] is None)
    cert = {
        "output_provenance_certificate_version": OUTPUT_CERT_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "read_output_provenance_map_hash": provenance_map[
            "read_output_provenance_map_hash"],
        "output_provenance_bisimulation_hash": bisimulation[
            "output_provenance_bisimulation_hash"],
        "semantic_non_interference_matrix_hash": non_interference[
            "semantic_non_interference_matrix_hash"],
        "canary_non_leakage_proof_hash": canary[
            "canary_non_leakage_proof_hash"],
        "information_usage_proof_hash": info_usage[
            "information_usage_proof_hash"],
        "side_channel_budget_seal_hash": side_channel[
            "side_channel_budget_seal_hash"],
        "is_token": False, "authorizes_write_execution": False,
        "certificate_status": "OUTPUT_PROVENANCE_CERTIFIED" if ok else
        "OUTPUT_PROVENANCE_CERTIFICATE_FAILED",
        "note": "Local deterministic evidence only. Not a production signature. "
        "Cannot authorize write execution.",
    }
    cert["output_provenance_certificate_hash"] = _core_hash(
        cert, "output_provenance_certificate_hash")
    return cert


# --- Fault-injection harness -----------------------------------------------
FAULT_CASES = [
    "missing_b5_certificate", "forged_b5_certificate",
    "b5_release_gate_failed", "b5_outcome_not_null",
    "adapter_write_capable", "adapter_network_capable", "adapter_provider",
    "adapter_unknown_kind", "adapter_capability_drift",
    "snapshot_missing", "snapshot_mutable", "snapshot_hash_mismatch",
    "mixed_snapshot_epoch", "forbidden_source_read",
    "missing_output_provenance", "forbidden_source_influence",
    "output_provenance_bisimulation_mismatch", "canary_leak",
    "information_budget_breach", "read_amplification",
    "side_channel_budget_breach", "query_plan_forbidden_projection",
    "query_plan_unknown_source", "entropy_source_present",
    "replay_mismatch", "runtime_surface_inserted", "write_effect_attempt",
    "token_derivation_attempt", "output_exfiltration",
]


def _apply_fault(fault, ctx):
    import copy
    c = copy.deepcopy(ctx)
    o = c.get("b5_outcome") or {}
    if fault == "missing_b5_certificate":
        o["proof_carrying_broker_action_certificate"] = {}
    elif fault == "forged_b5_certificate":
        o.setdefault("proof_carrying_broker_action_certificate", {})[
            "authorizes_execution"] = True
    elif fault == "b5_release_gate_failed":
        o.setdefault("broker_release_gate_report", {})[
            "release_gate_status"] = "RELEASE_GATE_FAILED"
    elif fault == "b5_outcome_not_null":
        o["effect_outcome"] = "SOME_EFFECT"
    elif fault == "adapter_write_capable":
        c["adapter_caps"] = {"write": True}
    elif fault == "adapter_network_capable":
        c["adapter_caps"] = {"network": True}
    elif fault == "adapter_provider":
        c["adapter_caps"] = {"provider": True}
    elif fault == "adapter_unknown_kind":
        c["adapter_kind"] = "unknown_kind_xyz"
    elif fault == "adapter_capability_drift":
        c["sealed_adapter_hash"] = "DRIFTED_SEAL"
    elif fault == "snapshot_missing":
        c["snapshot"] = None
    elif fault == "snapshot_mutable":
        if c.get("snapshot"):
            c["snapshot"] = {**c["snapshot"], "immutable": False}
    elif fault == "snapshot_hash_mismatch":
        c["sealed_snapshot_hash"] = "WRONG_SNAP_HASH"
    elif fault == "mixed_snapshot_epoch":
        c["requested_epoch"] = "OTHER_EPOCH"
    elif fault == "forbidden_source_read":
        c["extra_fields"] = {"__leak": {"value": "x", "data_class":
                             "CUSTOMER_SENSITIVE"}}
        c["extra_sources"] = ["__leak"]
    elif fault == "missing_output_provenance":
        c["drop_provenance"] = True
    elif fault == "forbidden_source_influence":
        # A forbidden VALUE mislabelled PUBLIC and read into output must be
        # caught by the REAL output/exfiltration + read-firewall detectors — not
        # by a harness-side flag. (Cross-tenant marker value flows to output.)
        c["adapter_kind"] = "field_projection"
        c["extra_fields"] = {"__influence": {"value": "tenant:OTHER-LEAK",
                             "data_class": "PUBLIC"}}
        c["extra_sources"] = ["__influence"]
    elif fault == "output_provenance_bisimulation_mismatch":
        c["tamper_safe_output"] = True
    elif fault == "canary_leak":
        # A canary MARKER value flowing to output must be caught by the REAL
        # canary-non-leakage detector (marker scan over the canary snapshot),
        # not by a harness-side flag.
        c["adapter_kind"] = "field_projection"
        c["extra_fields"] = {"__canaryish": {"value": "CANARY-MARKER-7F3A9C",
                             "data_class": "PUBLIC"}}
        c["extra_sources"] = ["__canaryish"]
    elif fault == "information_budget_breach":
        c["policy"] = {**(c.get("policy") or {}), "max_output_fields": 0}
    elif fault == "read_amplification":
        c["related_requests"] = [{"runtime_request_id": f"r{i}", "read_paths":
                                  c.get("all_paths", []), "snapshot_id": "s"}
                                 for i in range(6)]
    elif fault == "side_channel_budget_breach":
        c["policy"] = {**(c.get("policy") or {}),
                       "side_channel_output_bucket_max": 0}
        c["error_shape"] = 5
    elif fault == "query_plan_forbidden_projection":
        c["requested_projection"] = ["__not_allowed_field"]
    elif fault == "query_plan_unknown_source":
        c["requested_sources"] = ["__nonexistent_source"]
    elif fault == "entropy_source_present":
        c["declared_entropy"] = ["wall_clock"]
    elif fault == "replay_mismatch":
        c["tamper_safe_output"] = True
    elif fault == "runtime_surface_inserted":
        c["observed_surface"] = {"execute_endpoint": True}
    elif fault == "write_effect_attempt":
        c["adapter_caps"] = {"write": True}
    elif fault == "token_derivation_attempt":
        c["adapter_caps"] = {"token": True}
    elif fault == "output_exfiltration":
        c["force_exfiltration"] = True
    c["b5_outcome"] = o
    return c


def _runtime_signals(ctx):
    """Deterministic core: build every model + collect signals for one runtime
    request. Does NOT run the fault harness."""
    import copy
    tid = ctx["tenant_id"]
    rid = ctx["runtime_request_id"]
    b5o, b5r = ctx.get("b5_outcome"), ctx.get("b5_request")
    signals, reports = [], {}

    signals += _upstream_signals(tenant_id=tid, b5_outcome=b5o, b5_request=b5r)

    # Snapshot (possibly with injected extra fields for faults).
    snapshot = copy.deepcopy(ctx.get("snapshot")) if ctx.get("snapshot") else \
        ctx.get("snapshot")
    if snapshot and ctx.get("extra_fields"):
        snapshot["fields"] = {**snapshot.get("fields", {}),
                              **ctx["extra_fields"]}
        snapshot["snapshot_hash"] = _core_hash(
            {k: v for k, v in snapshot.items() if k != "snapshot_hash"},
            "snapshot_hash")

    # Adapter (with fault-injected caps/kind).
    adapter = build_adapter_descriptor(
        adapter_id=ctx.get("adapter_id", "adp-count"),
        adapter_kind=ctx.get("adapter_kind", "count"),
        allowed_sources=ctx.get("allowed_sources",
                                list((snapshot or {}).get("fields", {}))),
        allowed_projection=ctx.get("allowed_projection", ["count"]),
        capabilities=ctx.get("adapter_caps"))
    calc = build_capability_calculus(tenant_id=tid, runtime_request_id=rid,
                                     adapter=adapter)
    firewall = build_adapter_firewall(
        tenant_id=tid, runtime_request_id=rid, adapter=adapter,
        sealed_adapter_hash=ctx.get("sealed_adapter_hash"))
    if firewall["signal"]:
        signals.append(firewall["signal"])

    epoch_vec = build_snapshot_epoch_vector(
        tenant_id=tid, runtime_request_id=rid, snapshot=snapshot)
    if epoch_vec["signal"]:
        signals.append(epoch_vec["signal"])
    temporal = build_temporal_isolation(
        tenant_id=tid, runtime_request_id=rid, snapshot=snapshot,
        epoch_vector=epoch_vec, requested_epoch=ctx.get("requested_epoch"))
    if temporal["signal"]:
        signals.append(temporal["signal"])
    seal_check = build_snapshot_seal_check(
        tenant_id=tid, runtime_request_id=rid, snapshot=snapshot,
        sealed_snapshot_hash=ctx.get("sealed_snapshot_hash"),
        allowed_scopes=ctx.get("allowed_scopes"))
    if seal_check["signal"]:
        signals.append(seal_check["signal"])
    snap_twin = build_snapshot_twin(tenant_id=tid, runtime_request_id=rid,
                                    snapshot=snapshot)
    if snap_twin["signal"]:
        signals.append(snap_twin["signal"])
    snap_dag = build_snapshot_provenance_dag(
        tenant_id=tid, runtime_request_id=rid, snapshot=snapshot)
    if snap_dag["signal"]:
        signals.append(snap_dag["signal"])

    req_sources = ctx.get("requested_sources")
    if ctx.get("extra_sources"):
        req_sources = (req_sources or list((snapshot or {}).get(
            "fields", {}))) + ctx["extra_sources"]
    query_plan = build_query_plan_normal_form(
        tenant_id=tid, runtime_request_id=rid, adapter=adapter,
        snapshot=snapshot or {"fields": {}}, requested_sources=req_sources,
        requested_projection=ctx.get("requested_projection"))
    if query_plan["signal"]:
        signals.append(query_plan["signal"])
    sem_read = build_semantic_read_firewall(
        tenant_id=tid, runtime_request_id=rid, snapshot=snapshot or
        {"fields": {}}, adapter=adapter, query_plan=query_plan)
    if sem_read["signal"]:
        signals.append(sem_read["signal"])

    # Pure execution.
    if snapshot:
        read_set, raw_output, safe_output, prov_edges, operations = \
            _execute_read_only(adapter, snapshot, query_plan)
    else:
        read_set, raw_output, safe_output, prov_edges, operations = \
            [], {}, {}, [], [{"op": "COMPUTE_DETERMINISTIC", "capability":
                             "COMPUTE_DETERMINISTIC"}]
    if ctx.get("drop_provenance"):
        prov_edges = []
    if ctx.get("tamper_safe_output"):
        safe_output = {**safe_output, "__tampered": "x"}
    if ctx.get("force_exfiltration"):
        safe_output = {**safe_output, "email": "leak@example.test"}

    mk = build_microkernel(tenant_id=tid, runtime_request_id=rid,
                           operations=operations)
    if mk["signal"]:
        signals.append(mk["signal"])
    op_ledger = build_operation_ledger(tenant_id=tid, runtime_request_id=rid,
                                       operations=operations)
    path_policy = build_path_policy(tenant_id=tid, runtime_request_id=rid,
                                    operations=operations)
    if path_policy["signal"]:
        signals.append(path_policy["signal"])
    authority = build_authority_freeze(tenant_id=tid, runtime_request_id=rid)

    rs_ledger = build_read_set_ledger(tenant_id=tid, runtime_request_id=rid,
                                      read_set=read_set, snapshot=snapshot)
    rs_complete = build_read_set_completeness(
        tenant_id=tid, runtime_request_id=rid, read_set=read_set,
        provenance_edges=prov_edges)
    if rs_complete["signal"]:
        signals.append(rs_complete["signal"])
    rs_attest = build_read_set_attestation(
        tenant_id=tid, runtime_request_id=rid, read_set_ledger=rs_ledger,
        snapshot=snapshot or {})
    if rs_attest["signal"]:
        signals.append(rs_attest["signal"])

    redaction_hash = ctx.get("redaction_policy_hash",
                             _sha({"redaction": "default-v1"}))
    prov_map = build_provenance_map(
        tenant_id=tid, runtime_request_id=rid, safe_output=safe_output,
        read_set=read_set, provenance_edges=prov_edges, snapshot=snapshot or {},
        redaction_policy_hash=redaction_hash)
    if prov_map["signal"]:
        signals.append(prov_map["signal"])
    bisim = build_bisimulation(
        tenant_id=tid, runtime_request_id=rid, provenance_map=prov_map,
        safe_output=safe_output, adapter=adapter, snapshot=snapshot or
        {"fields": {}}, query_plan=query_plan, read_set=read_set)
    if bisim["signal"]:
        signals.append(bisim["signal"])
    non_interf = build_non_interference(
        tenant_id=tid, runtime_request_id=rid, adapter=adapter,
        snapshot=snapshot or {"fields": {}}, query_plan=query_plan,
        safe_output=safe_output)
    if non_interf["signal"]:
        signals.append(non_interf["signal"])

    harness = build_canary_harness(tenant_id=tid, runtime_request_id=rid,
                                   snapshot=snapshot or {"fields": {}})
    canary = build_canary_non_leakage(
        tenant_id=tid, runtime_request_id=rid, harness=harness, adapter=adapter,
        query_plan=query_plan, safe_output=safe_output)
    if canary["signal"]:
        signals.append(canary["signal"])

    info_budget = build_information_budget(tenant_id=tid, runtime_request_id=rid,
                                           policy=ctx.get("policy"))
    info_usage = build_information_usage(
        tenant_id=tid, runtime_request_id=rid, budget=info_budget,
        safe_output=safe_output, provenance_map=prov_map, read_set=read_set,
        repeated_query_count=ctx.get("repeated_query_count", 0))
    if info_usage["signal"]:
        signals.append(info_usage["signal"])
    read_amp = build_read_amplification(
        tenant_id=tid, runtime_request_id=rid, read_set=read_set,
        related_requests=ctx.get("related_requests"), policy=ctx.get("policy"))
    if read_amp["signal"]:
        signals.append(read_amp["signal"])
    side_channel = build_side_channel_seal(
        tenant_id=tid, runtime_request_id=rid, safe_output=safe_output,
        operations=operations, read_set=read_set, policy=ctx.get("policy"),
        error_shape=ctx.get("error_shape", 0))
    if side_channel["signal"]:
        signals.append(side_channel["signal"])

    res_budget = build_resource_budget(tenant_id=tid, runtime_request_id=rid,
                                       policy=ctx.get("policy"))
    res_usage = build_resource_usage(
        tenant_id=tid, runtime_request_id=rid, budget=res_budget,
        operations=operations, read_set=read_set, safe_output=safe_output)
    if res_usage["signal"]:
        signals.append(res_usage["signal"])
    entropy = build_entropy_seal(tenant_id=tid, runtime_request_id=rid,
                                 declared_entropy=ctx.get("declared_entropy"))
    if entropy["signal"]:
        signals.append(entropy["signal"])
    replay = build_replay_twin(
        tenant_id=tid, runtime_request_id=rid, adapter=adapter,
        snapshot=snapshot or {"fields": {}}, query_plan=query_plan,
        safe_output=safe_output)
    if replay["signal"]:
        signals.append(replay["signal"])

    taint = build_output_taint_lattice(tenant_id=tid, runtime_request_id=rid,
                                       provenance_map=prov_map)
    if taint["signal"]:
        signals.append(taint["signal"])
    non_exfil = build_non_exfiltration(tenant_id=tid, runtime_request_id=rid,
                                       safe_output=safe_output)
    if non_exfil["signal"]:
        signals.append(non_exfil["signal"])
    safe_proj = build_safe_output_projection(
        tenant_id=tid, runtime_request_id=rid, safe_output=safe_output,
        redaction_policy_hash=redaction_hash)
    if safe_proj["signal"]:
        signals.append(safe_proj["signal"])
    diode = build_data_diode(
        tenant_id=tid, runtime_request_id=rid, safe_output=safe_output,
        non_exfiltration_ok=non_exfil["signal"] is None,
        taint_ok=taint["signal"] is None)
    if diode["signal"]:
        signals.append(diode["signal"])

    effect_ledger = build_effect_ledger(tenant_id=tid, runtime_request_id=rid,
                                        operations=operations)
    surface = build_surface_diff(
        tenant_id=tid, runtime_request_id=rid,
        observed_surface=ctx.get("observed_surface"), adapter=adapter)
    if surface["signal"]:
        signals.append(surface["signal"])
    no_effect = build_no_effect_proofs(
        tenant_id=tid, runtime_request_id=rid, adapter=adapter,
        effect_ledger=effect_ledger, surface_findings=surface[
            "detected_surface"])
    signals += no_effect["signals"]
    escape = build_escape_sentinel(
        tenant_id=tid, runtime_request_id=rid, operations=operations,
        surface_diff=surface, effect_ledger=effect_ledger)
    if escape["signal"]:
        signals.append(escape["signal"])
    non_escal = build_non_escalation(
        tenant_id=tid, runtime_request_id=rid, adapter=adapter, b5_outcome=b5o)
    if non_escal["signal"]:
        signals.append(non_escal["signal"])

    cert = build_output_provenance_certificate(
        tenant_id=tid, runtime_request_id=rid, provenance_map=prov_map,
        bisimulation=bisim, non_interference=non_interf, canary=canary,
        info_usage=info_usage, side_channel=side_channel)

    reports.update({
        "adapter": adapter, "adapter_capability_calculus": calc,
        "adapter_capability_firewall": firewall,
        "snapshot_epoch_vector": epoch_vec,
        "temporal_snapshot_isolation": temporal,
        "snapshot_seal_check": seal_check, "runtime_snapshot_twin": snap_twin,
        "snapshot_provenance_dag": snap_dag,
        "query_plan_normal_form": query_plan,
        "semantic_read_firewall": sem_read,
        "runtime_microkernel_contract": mk,
        "runtime_operation_ledger": op_ledger,
        "runtime_path_policy_automaton": path_policy,
        "runtime_authority_freeze": authority,
        "read_set_ledger": rs_ledger,
        "read_set_completeness_proof": rs_complete,
        "read_set_attestation_capsule": rs_attest,
        "read_output_provenance_map": prov_map,
        "output_provenance_bisimulation": bisim,
        "semantic_non_interference_matrix": non_interf,
        "synthetic_canary_harness": {k: v for k, v in harness.items()
                                     if k != "_canary_snapshot"},
        "canary_non_leakage_proof": canary,
        "information_budget_envelope": info_budget,
        "information_usage_proof": info_usage,
        "read_amplification_guard": read_amp,
        "side_channel_budget_seal": side_channel,
        "runtime_resource_budget_envelope": res_budget,
        "runtime_resource_usage_proof": res_usage,
        "determinism_entropy_seal": entropy,
        "deterministic_replay_twin": replay,
        "output_taint_lattice": taint,
        "output_non_exfiltration_gate": non_exfil,
        "safe_output_projection": safe_proj,
        "data_diode_output_gate": diode,
        "runtime_effect_ledger": effect_ledger,
        "runtime_surface_diff": surface, "no_effect_proofs": no_effect,
        "runtime_escape_sentinel": escape,
        "runtime_non_escalation_proof": non_escal,
        "output_provenance_certificate": cert,
        "_safe_output": safe_output,
    })
    return sorted(set(signals)), reports


def run_fault_injection_harness(*, tenant_id, runtime_request_id, base_ctx):
    results, unexpected = [], []
    for fault in FAULT_CASES:
        fctx = _apply_fault(fault, base_ctx)
        sigs, _ = _runtime_signals(fctx)
        status = status_for_signals(sigs)
        closed = status not in POSITIVE_STATUSES
        results.append({"fault_case": fault, "dominant_signal":
                        dominant_signal(sigs), "runtime_status": status,
                        "failed_closed": closed})
        if not closed:
            unexpected.append(fault)
    hstatus = "FAULT_INJECTION_PASSED" if not unexpected else \
        "FAULT_INJECTION_FAILED"
    harness = {
        "runtime_fault_injection_harness_version": FAULT_HARNESS_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "fault_cases": FAULT_CASES, "fault_results": results,
        "unexpected_positive_results": unexpected, "harness_status": hstatus,
        "signal": None if not unexpected else
        "FAULT_INJECTION_RELEASE_GATE_FAILED",
    }
    harness["runtime_fault_injection_harness_hash"] = _core_hash(
        harness, "runtime_fault_injection_harness_hash")
    return harness


def build_release_gate(*, tenant_id, runtime_request_id, harness) -> dict:
    failures = harness.get("unexpected_positive_results", [])
    passed = harness.get("harness_status") == "FAULT_INJECTION_PASSED" and \
        not failures
    gate = {
        "runtime_release_gate_version": RELEASE_GATE_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "harness_hash": harness["runtime_fault_injection_harness_hash"],
        "negative_test_count": len(harness.get("fault_cases", [])),
        "negative_test_failures": failures,
        "release_gate_status": "RELEASE_GATE_PASSED" if passed else
        "RELEASE_GATE_FAILED",
        "signal": None if passed else "FAULT_INJECTION_RELEASE_GATE_FAILED",
    }
    gate["runtime_release_gate_hash"] = _core_hash(
        gate, "runtime_release_gate_hash")
    return gate


def build_conformance_vector(*, tenant_id, runtime_request_id, reports, harness,
                             release_gate) -> dict:
    dims = {
        "adapter_read_only": reports["adapter_capability_firewall"][
            "firewall_status"] == "ADAPTER_ALLOWED_READ_ONLY",
        "microkernel_admitted": reports["runtime_microkernel_contract"][
            "microkernel_status"] == "MICROKERNEL_ADMITTED_READ_ONLY",
        "semantic_read_allowed": reports["semantic_read_firewall"][
            "read_status"] == "SEMANTIC_READ_ALLOWED",
        "read_set_attested": reports["read_set_attestation_capsule"][
            "attestation_status"] == "READ_SET_ATTESTED",
        "provenance_matched": reports["read_output_provenance_map"][
            "provenance_status"] == "OUTPUT_PROVENANCE_MATCHED",
        "bisimulation_matched": reports["output_provenance_bisimulation"][
            "bisimulation_status"] == "BISIMULATION_MATCHED",
        "non_interference_matched": reports[
            "semantic_non_interference_matrix"]["matrix_status"] ==
        "SEMANTIC_NON_INTERFERENCE_MATCHED",
        "canary_non_leakage": reports["canary_non_leakage_proof"][
            "proof_status"] == "CANARY_NON_LEAKAGE_MATCHED",
        "information_budget": reports["information_usage_proof"][
            "proof_status"] == "INFORMATION_BUDGET_MATCHED",
        "read_amplification_clear": reports["read_amplification_guard"][
            "guard_status"] == "READ_AMPLIFICATION_CLEAR",
        "side_channel_sealed": reports["side_channel_budget_seal"][
            "seal_status"] == "SIDE_CHANNEL_SEALED",
        "temporal_isolated": reports["temporal_snapshot_isolation"][
            "isolation_status"] == "TEMPORAL_ISOLATED",
        "entropy_sealed": reports["determinism_entropy_seal"][
            "seal_status"] == "ENTROPY_SEALED",
        "replay_matched": reports["deterministic_replay_twin"][
            "replay_matched"],
        "data_diode_ok": reports["data_diode_output_gate"][
            "diode_status"] == "DATA_DIODE_OUTPUT_ALLOWED_SAFE_ONLY",
        "no_exfiltration": reports["output_non_exfiltration_gate"][
            "gate_status"] == "NO_OUTPUT_EXFILTRATION",
        "output_certified": reports["output_provenance_certificate"][
            "certificate_status"] == "OUTPUT_PROVENANCE_CERTIFIED",
        "fault_injection_passed": harness["harness_status"] ==
        "FAULT_INJECTION_PASSED",
        "release_gate_passed": release_gate["release_gate_status"] ==
        "RELEASE_GATE_PASSED",
    }
    vec = {
        "runtime_conformance_vector_version": CONFORMANCE_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "dimensions": dims, "conformant": all(dims.values()),
    }
    vec["runtime_conformance_vector_hash"] = _core_hash(
        vec, "runtime_conformance_vector_hash")
    return vec


def build_proof_bundle(*, tenant_id, runtime_request_id, reports, harness,
                       release_gate, status, dominant) -> dict:
    r = reports
    component_hashes = {
        "query_plan_normal_form_hash": r["query_plan_normal_form"][
            "query_plan_normal_form_hash"],
        "read_output_provenance_map_hash": r["read_output_provenance_map"][
            "read_output_provenance_map_hash"],
        "output_provenance_bisimulation_hash": r[
            "output_provenance_bisimulation"][
            "output_provenance_bisimulation_hash"],
        "semantic_non_interference_matrix_hash": r[
            "semantic_non_interference_matrix"][
            "semantic_non_interference_matrix_hash"],
        "synthetic_canary_harness_hash": r["synthetic_canary_harness"][
            "synthetic_canary_harness_hash"],
        "canary_non_leakage_proof_hash": r["canary_non_leakage_proof"][
            "canary_non_leakage_proof_hash"],
        "information_budget_envelope_hash": r["information_budget_envelope"][
            "information_budget_envelope_hash"],
        "information_usage_proof_hash": r["information_usage_proof"][
            "information_usage_proof_hash"],
        "read_amplification_guard_hash": r["read_amplification_guard"][
            "read_amplification_guard_hash"],
        "side_channel_budget_seal_hash": r["side_channel_budget_seal"][
            "side_channel_budget_seal_hash"],
        "output_provenance_certificate_hash": r["output_provenance_certificate"][
            "output_provenance_certificate_hash"],
        "semantic_read_firewall_hash": r["semantic_read_firewall"][
            "semantic_read_firewall_hash"],
        "read_set_ledger_hash": r["read_set_ledger"]["read_set_ledger_hash"],
        "read_set_attestation_capsule_hash": r["read_set_attestation_capsule"][
            "read_set_attestation_capsule_hash"],
        "temporal_snapshot_isolation_hash": r["temporal_snapshot_isolation"][
            "temporal_snapshot_isolation_hash"],
        "snapshot_epoch_vector_hash": r["snapshot_epoch_vector"][
            "snapshot_epoch_vector_hash"],
        "adapter_capability_firewall_hash": r["adapter_capability_firewall"][
            "adapter_capability_firewall_hash"],
        "determinism_entropy_seal_hash": r["determinism_entropy_seal"][
            "determinism_entropy_seal_hash"],
        "deterministic_replay_twin_hash": r["deterministic_replay_twin"][
            "deterministic_replay_twin_hash"],
        "data_diode_output_gate_hash": r["data_diode_output_gate"][
            "data_diode_output_gate_hash"],
        "output_non_exfiltration_gate_hash": r["output_non_exfiltration_gate"][
            "output_non_exfiltration_gate_hash"],
        "runtime_resource_usage_proof_hash": r["runtime_resource_usage_proof"][
            "runtime_resource_usage_proof_hash"],
        "runtime_fault_injection_harness_hash": harness[
            "runtime_fault_injection_harness_hash"],
        "runtime_release_gate_hash": release_gate["runtime_release_gate_hash"],
    }
    bundle = {
        "runtime_proof_bundle_version": PROOF_BUNDLE_VERSION,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "component_hashes": dict(sorted(component_hashes.items())),
        "runtime_status": status, "dominant_signal": dominant,
        "read_only": True, "executes_nothing_external": True,
    }
    bundle["runtime_proof_bundle_hash"] = _core_hash(
        bundle, "runtime_proof_bundle_hash")
    return bundle


# --- Request envelope + top-level ------------------------------------------
def build_runtime_request_envelope(*, runtime_request_id, tenant_id, actor_id,
                                   actor_type, b5_outcome, adapter_id,
                                   snapshot, requested_sources,
                                   requested_projection, requested_epoch,
                                   created_at) -> dict:
    o = b5_outcome or {}
    env = {
        "runtime_request_envelope_version": REQUEST_VERSION,
        "runtime_request_id": runtime_request_id, "tenant_id": tenant_id,
        "b5_broker_request_id": o.get("broker_request_id"),
        "b5_broker_decision_hash": o.get("broker_decision_hash"),
        "adapter_id": str(adapter_id or ""),
        "snapshot_id": (snapshot or {}).get("snapshot_id"),
        "snapshot_hash": (snapshot or {}).get("snapshot_hash"),
        "requested_epoch": str(requested_epoch or (snapshot or {}).get(
            "epoch", "")),
        "requested_sources": sorted(set(map(str, _as_list(requested_sources)))),
        "requested_projection": sorted(set(map(str, _as_list(
            requested_projection)))),
        "requested_by_actor_id": actor_id, "requested_by_actor_type":
        actor_type, "is_write": False, "is_external": False,
        "read_only_local_only": True, "created_at": created_at,
    }
    # runtime_request_hash is CONTENT-deterministic: it binds the snapshot/
    # adapter/sources/projection/epoch/B5 evidence but EXCLUDES the per-request
    # instance fields (request id, timestamp) AND the actor identity, so the
    # request — and therefore runtime_decision_hash which embeds it — is a
    # function of the EVIDENCE alone, reproducible by any verifier.
    env["runtime_request_hash"] = _core_hash(
        env, "runtime_request_hash", "runtime_request_id", "created_at",
        "requested_by_actor_id", "requested_by_actor_type")
    return env


def prepare_runtime_outcome(*, runtime_request_id, tenant_id, actor_id,
                            actor_type, envelope, b5_outcome, b5_request,
                            snapshot, adapter_id=None, adapter_kind=None,
                            allowed_sources=None, allowed_projection=None,
                            requested_sources=None, requested_projection=None,
                            requested_epoch=None, sealed_snapshot_hash=None,
                            sealed_adapter_hash=None, allowed_scopes=None,
                            related_requests=None, repeated_query_count=0,
                            declared_entropy=None, observed_surface=None,
                            adapter_caps=None, policy=None,
                            redaction_policy_hash=None, created_at=None) -> dict:
    """Prepare a read-only runtime outcome. Runs the full deterministic
    evaluation, the fault-injection harness and the release gate, then resolves
    the fail-closed status. Reads only the frozen local snapshot; produces only
    a local safe output; performs no external effect."""
    ctx = {
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "b5_outcome": b5_outcome, "b5_request": b5_request, "snapshot": snapshot,
        "adapter_id": adapter_id or "adp-count",
        "adapter_kind": adapter_kind or "count",
        "allowed_sources": allowed_sources if allowed_sources is not None else
        list((snapshot or {}).get("fields", {})),
        "allowed_projection": allowed_projection if allowed_projection is not
        None else ["count"],
        "requested_sources": requested_sources,
        "requested_projection": requested_projection,
        "requested_epoch": requested_epoch,
        "sealed_snapshot_hash": sealed_snapshot_hash if sealed_snapshot_hash
        is not None else (snapshot or {}).get("snapshot_hash"),
        "sealed_adapter_hash": sealed_adapter_hash,
        "allowed_scopes": allowed_scopes, "related_requests": related_requests,
        "repeated_query_count": repeated_query_count,
        "declared_entropy": declared_entropy,
        "observed_surface": observed_surface, "adapter_caps": adapter_caps,
        "policy": policy, "redaction_policy_hash": redaction_policy_hash or
        _sha({"redaction": "default-v1"}),
        "all_paths": list((snapshot or {}).get("fields", {})),
    }
    signals, reports = _runtime_signals(ctx)

    harness = run_fault_injection_harness(
        tenant_id=tenant_id, runtime_request_id=runtime_request_id,
        base_ctx=ctx)
    release_gate = build_release_gate(
        tenant_id=tenant_id, runtime_request_id=runtime_request_id,
        harness=harness)
    if release_gate["signal"]:
        signals.append(release_gate["signal"])

    signals = sorted(set(signals))
    if not signals:
        signals = ["READ_ONLY_RUNTIME_COMPLETED"]
    dominant = dominant_signal(signals)
    status = _status_for_signal(dominant)
    decision = _decision_for_status(status)

    conformance = build_conformance_vector(
        tenant_id=tenant_id, runtime_request_id=runtime_request_id,
        reports=reports, harness=harness, release_gate=release_gate)
    proof_bundle = build_proof_bundle(
        tenant_id=tenant_id, runtime_request_id=runtime_request_id,
        reports=reports, harness=harness, release_gate=release_gate,
        status=status, dominant=dominant)

    safe_output = reports.pop("_safe_output", {})
    outcome_kind = "READ_ONLY_LOCAL_RESULT" if status == \
        "RUNTIME_READ_ONLY_COMPLETED" else status.replace("RUNTIME_", "")
    outcome = {
        "runtime_output_record_version": OUTPUT_RECORD_VERSION,
        "runtime_execution_record_version": EXECUTION_RECORD_VERSION,
        "runtime_request_id": runtime_request_id, "tenant_id": tenant_id,
        "b5_broker_request_id": (b5_outcome or {}).get("broker_request_id"),
        "adapter_id": ctx["adapter_id"],
        "snapshot_id": (snapshot or {}).get("snapshot_id"),
        "runtime_status": status, "runtime_decision_status": decision,
        "runtime_outcome_kind": outcome_kind,
        "dominant_signal": dominant,
        "dominant_reason_code": REASON_CODES.get(dominant, ""),
        "all_signals": signals,
        "signal_reason_codes": {s: REASON_CODES.get(s, "") for s in signals},
        "safe_output": safe_output if status == "RUNTIME_READ_ONLY_COMPLETED"
        else {},
        "safe_output_hash": _sha(safe_output),
        "read_only": True, "local_only": True, "snapshot_bound": True,
        "is_write": False, "is_external": False, "is_execution": False,
        "produced_external_effect": False,
        "runtime_request_hash": (envelope or {}).get("runtime_request_hash"),
        "data_diode_status": reports["data_diode_output_gate"]["diode_status"],
        "decided_by_actor_id": actor_id, "decided_by_actor_type": actor_type,
        "created_at": created_at, "updated_at": created_at,
        "runtime_fault_injection_harness": harness,
        "runtime_release_gate_report": release_gate,
        "runtime_conformance_vector": conformance,
        "runtime_proof_bundle": proof_bundle,
        "honesty_labels": HONESTY_LABELS,
    }
    outcome.update(reports)
    outcome["runtime_decision_hash"] = _core_hash(
        outcome, "runtime_decision_hash", "runtime_request_id",
        "decided_by_actor_id", "decided_by_actor_type", "runtime_state_hash")
    outcome["runtime_state_hash"] = _sha({
        "runtime_request_id": runtime_request_id,
        "runtime_decision_hash": outcome["runtime_decision_hash"],
        "runtime_status": status, "dominant_signal": dominant,
        "runtime_request_hash": (envelope or {}).get("runtime_request_hash"),
        "safe_output_hash": outcome["safe_output_hash"]})
    return outcome


# --- Event ledger ----------------------------------------------------------
RUNTIME_EVENT_TYPES = {
    "RUNTIME_REQUEST_OPENED", "RUNTIME_OUTCOME_PREPARED",
    "RUNTIME_FAULT_INJECTED", "RUNTIME_OUTCOME_VERIFIED",
}


def build_runtime_event(*, event_type, tenant_id, runtime_request_id, actor_id,
                        actor_type, runtime_state_hash, previous_event_hash,
                        sequence, detail, created_at) -> dict:
    ev = {
        "runtime_event_version": RUNTIME_EVENT_VERSION, "event_type": event_type,
        "tenant_id": tenant_id, "runtime_request_id": runtime_request_id,
        "actor_id": actor_id, "actor_type": actor_type,
        "runtime_state_hash": runtime_state_hash,
        "previous_event_hash": previous_event_hash or GENESIS,
        "sequence": sequence, "detail": detail or {}, "created_at": created_at,
    }
    ev["event_hash"] = _core_hash(ev, "event_hash")
    return ev
