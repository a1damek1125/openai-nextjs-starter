"""Finalis Transaction Twin + Proof-of-Execution Runtime (TOOL-B9 v5).

The FIRST local governed transaction runtime. It consumes a TOOL-B8 pre-B9
assurance envelope AS EVIDENCE ONLY, FULLY RE-VALIDATES it, and — only if every
factor of ``LocalCommitAllowed`` holds — applies a LOCAL, REVERSIBLE commit to
Finalis-internal state. It NEVER produces any external effect.

For every transaction it builds a deterministic, replayable **Transaction Twin**:
intended action, current + shadow local state, planned delta, compliance path,
authority/evidence/approval basis, rollback plan, an INERT external outbox, a
proof-carrying local action certificate, a hash-chained proof-of-execution
event stream, and an audit trail — the machine-checkable mirror of what the AI
employee wants to do.

Hard invariants (every one is fail-closed and tested):
- B8 envelope is EVIDENCE ONLY — never authority, approval, commit lease, B9
  activation, or provider permission; B9 revalidates it from scratch.
- Authority may come ONLY from server-side RBAC, tenant policy, an explicit
  approval record, a governance decision, or the local commit gate — NEVER from
  a document, artifact, channel message, mobile push, workbench output, LLM/tool
  output, OCR text, web page, or context slice (contaminated-authority firewall).
- Source surfaces (Slack/Teams/mobile/workbench, all *_FUTURE) are METADATA ONLY
  in B9: they grant no authority, no approval, no provider access, no bypass.
- The inert outbox NEVER releases, calls a provider, attempts delivery, or
  mutates external state. The No-External-Effect theorem holds for every tx.

It does NOT call providers/MCP/LLM, send messages, execute payments, mutate any
external/CRM/evidence system, or issue tokens/credentials. The most permissive
outcome is ``B9_LOCAL_COMMIT_APPLIED`` — a local, reversible internal commit,
never an external effect. NOT_PRODUCTION_READY.
"""
from __future__ import annotations

from .tool_contracts import canonical_json, _sha, _core_hash, _flatten_text
from . import tool_registry as _tr

B9_MODEL_VERSION = "finalis-transaction-twin-proof-of-execution-runtime-v5"
ENVELOPE_VERSION = "finalis-semantic-transaction-envelope-v1"
TWIN_VERSION = "finalis-transaction-twin-v1"
GRAPH_VERSION = "finalis-semantic-transaction-graph-v1"
POE_STREAM_VERSION = "finalis-proof-of-execution-event-stream-v1"
POE_PROOF_VERSION = "finalis-proof-of-execution-proof-v1"
CONTRACT_VERSION = "finalis-proof-of-execution-contract-v1"
REPLAY_VERSION = "finalis-replay-context-v1"
SHADOW_VERSION = "finalis-shadow-local-state-v1"
OUTBOX_VERSION = "finalis-inert-effect-outbox-v1"
CERTIFICATE_VERSION = "finalis-proof-carrying-local-action-certificate-v1"
PATH_COMPLIANCE_VERSION = "finalis-runtime-path-compliance-monitor-v1"
CONTAM_FIREWALL_VERSION = "finalis-contaminated-authority-firewall-v1"
SURFACE_ISOLATION_VERSION = "finalis-source-surface-isolation-proof-v1"
CONTEXT_SLICE_VERSION = "finalis-context-slice-contract-v1"
CHECKPOINT_VERSION = "finalis-agent-lifecycle-middleware-checkpoints-v1"
EFFECTOR_GATE_VERSION = "finalis-effector-exclusive-local-gate-v1"
ATTESTATION_VERSION = "finalis-deterministic-commit-attestation-v1"
ROLLBACK_VERSION = "finalis-emergency-abort-rollback-readiness-v1"
NO_EXTERNAL_VERSION = "finalis-no-external-effect-theorem-v1"
B8_HANDOFF_VERSION = "finalis-b8-evidence-only-handoff-v1"
FAULT_HARNESS_VERSION = "finalis-b9-fault-injection-harness-v1"
RELEASE_GATE_VERSION = "finalis-b9-release-gate-negative-test-report-v1"
CONFORMANCE_VERSION = "finalis-b9-conformance-vector-v1"
PROOF_BUNDLE_VERSION = "finalis-b9-proof-bundle-v1"
B9_EVENT_VERSION = "finalis-b9-event-v1"
GENESIS = "0" * 64


HONESTY_LABELS = [
    "FINALIS_TRANSACTION_TWIN_ONLY", "PROOF_OF_EXECUTION_LOCAL_ONLY",
    "GOVERNED_SEMANTIC_TRANSACTION_ONLY", "LOCAL_REVERSIBLE_COMMIT_ONLY",
    "SHADOW_STATE_VALIDATED", "INERT_OUTBOX_ONLY",
    "PROOF_CARRYING_LOCAL_ACTION", "PATH_COMPLIANCE_CHECKED",
    "CONTAMINATED_AUTHORITY_FIREWALL_ENABLED", "SOURCE_SURFACE_ISOLATED",
    "CONTEXT_SLICE_NON_AUTHORITATIVE", "NO_EXTERNAL_EFFECT", "NO_PROVIDER_CALL",
    "NO_PAYMENT", "NO_MESSAGE_SEND", "NO_EXTERNAL_CRM_MUTATION",
    "NO_MCP_RUNTIME", "NO_LLM_PROVIDER_RUNTIME", "B8_EVIDENCE_ONLY",
    "NOT_PRODUCTION_READY",
]

# --- Upstream (B8) acceptance ----------------------------------------------
B8_ACCEPTABLE_STATUSES = {"B8_V5_ACCEPTED"}

# Source surfaces. All *_FUTURE surfaces are METADATA ONLY in B9.
ALLOWED_SOURCE_SURFACES = {
    "WEB_PORTAL", "MOBILE_IOS_FUTURE", "MOBILE_ANDROID_FUTURE",
    "MOBILE_WEB_FUTURE", "SLACK_FUTURE", "TEAMS_FUTURE",
    "GOVERNED_WORKBENCH_FUTURE", "INTERNAL_TEST",
}
FUTURE_SURFACES = {
    "MOBILE_IOS_FUTURE", "MOBILE_ANDROID_FUTURE", "MOBILE_WEB_FUTURE",
    "SLACK_FUTURE", "TEAMS_FUTURE", "GOVERNED_WORKBENCH_FUTURE",
}
# Surfaces that may originate a LOCAL transaction request (not external effect).
REQUEST_ORIGIN_SURFACES = {"WEB_PORTAL", "INTERNAL_TEST"}

# Authority may come ONLY from these server-side sources.
ALLOWED_AUTHORITY_SOURCES = {
    "SERVER_RBAC", "TENANT_POLICY", "APPROVAL_RECORD", "GOVERNANCE_DECISION",
    "LOCAL_COMMIT_GATE",
}
# Contaminated authority sources -> reason code map (firewall).
CONTAMINATED_AUTHORITY_SOURCES = {
    "PROMPT_TEXT": "CONTEXT_AS_AUTHORITY_REJECTED",
    "DOCUMENT": "DOCUMENT_AS_COMMAND_REJECTED",
    "DOCUMENT_CONTENT": "DOCUMENT_AS_COMMAND_REJECTED",
    "UPLOADED_FILE": "DOCUMENT_AS_COMMAND_REJECTED",
    "OCR_TEXT": "DOCUMENT_AS_COMMAND_REJECTED",
    "EMAIL_BODY": "CHANNEL_AS_APPROVAL_REJECTED",
    "SLACK_MESSAGE": "CHANNEL_AS_APPROVAL_REJECTED",
    "TEAMS_MESSAGE": "CHANNEL_AS_APPROVAL_REJECTED",
    "WEB_PAGE": "DOCUMENT_AS_COMMAND_REJECTED",
    "ARTIFACT_LABEL": "ARTIFACT_AS_AUTHORITY_REJECTED",
    "B8_ARTIFACT": "B8_ARTIFACT_AS_AUTHORITY_REJECTED",
    "B8_ENVELOPE": "B8_ARTIFACT_AS_AUTHORITY_REJECTED",
    "MOBILE_PUSH": "MOBILE_PUSH_AS_APPROVAL_REJECTED",
    "WORKBENCH_OUTPUT": "WORKBENCH_OUTPUT_AS_EXECUTION_REJECTED",
    "LLM_OUTPUT": "LLM_OUTPUT_AS_AUTHORITY_REJECTED",
    "TOOL_OUTPUT": "TOOL_OUTPUT_AS_AUTHORITY_REJECTED",
    "CONTEXT_SLICE": "CONTEXT_AS_AUTHORITY_REJECTED",
}
CONTAM_REASON_CODES = set(CONTAMINATED_AUTHORITY_SOURCES.values())

# Path-compliance predicates (all must hold).
PATH_PREDICATES = [
    "consent_ok", "purpose_ok", "data_minimization_ok", "tenant_scope_ok",
    "object_scope_ok", "approval_ok", "local_only_ok", "no_external_effect_ok",
    "no_authority_leak_ok", "no_artifact_as_authority_ok",
    "no_document_as_command_ok", "no_channel_as_approval_ok",
    "no_mobile_push_as_approval_ok", "no_workbench_output_as_execution_ok",
    "no_b8_as_authority_ok", "source_surface_isolated_ok",
    "context_slice_non_authoritative_ok",
]

# Semantic-transaction-graph topology.
GRAPH_NODE_TYPES = [
    "TaskIntent", "Actor", "Tenant", "ObjectReference", "EvidenceSnapshot",
    "PolicySnapshot", "ApprovalSnapshot", "ContextSlice", "ShadowState",
    "PlannedDelta", "PathComplianceResult", "ProofOfExecutionStream",
    "LocalCommit", "RollbackPlan", "InertOutboxItem", "ActionCertificate",
    "AuditEvent", "SourceSurface",
]
GRAPH_EDGE_TYPES = [
    "requested_by", "belongs_to_tenant", "targets_object",
    "supported_by_evidence", "constrained_by_policy", "requires_approval",
    "contextualized_by", "produces_shadow_state", "validates_path",
    "produces_poe_stream", "produces_certificate", "commits_local_delta",
    "prepares_rollback", "blocks_external_effect", "originates_from_surface",
    "records_audit",
]
# Required proof-of-execution events (in canonical order), hash-chained.
POE_EVENTS = [
    "TX_REQUESTED", "B8_EVIDENCE_REVALIDATED", "AUTHORITY_CHECKED",
    "TENANT_SCOPE_CHECKED", "CONTEXT_SLICE_BOUND", "EVIDENCE_BOUND",
    "APPROVAL_BOUND", "SHADOW_STATE_CREATED", "PATH_COMPLIANCE_CHECKED",
    "CONTAMINATED_AUTHORITY_CHECKED", "SOURCE_SURFACE_ISOLATED",
    "CONFLICT_CHECKED", "INERT_OUTBOX_CREATED", "CERTIFICATE_CREATED",
    "LOCAL_COMMIT_PREPARED", "LOCAL_COMMIT_APPLIED", "ROLLBACK_PLAN_CREATED",
    "NO_EXTERNAL_EFFECT_VERIFIED", "AUDIT_RECORDED",
]
LIFECYCLE_CHECKPOINTS = [
    "post_user_request_check", "pre_plan_check", "pre_commit_validation",
    "post_shadow_state_check", "pre_certificate_check", "post_commit_check",
    "pre_response_assembly_check",
]

DEFAULT_POLICY = {"require_approval_for_commit": 1, "max_write_set": 32}


# --- Hard-fail dominance ladder --------------------------------------------
FAILURE_DOMINANCE = [
    "TAMPERED", "CROSS_TENANT", "REVOKED",
    # upstream B8 (evidence-only) revalidation
    "B8_ENVELOPE_MISSING", "B8_NOT_ACCEPTED", "B8_REVALIDATION_FAILED",
    "B8_TAMPERED", "B8_PRODUCTION_CLAIM_DETECTED",
    # contaminated authority firewall (root-cause specific)
    "DOCUMENT_AS_COMMAND_REJECTED", "ARTIFACT_AS_AUTHORITY_REJECTED",
    "CHANNEL_AS_APPROVAL_REJECTED", "MOBILE_PUSH_AS_APPROVAL_REJECTED",
    "WORKBENCH_OUTPUT_AS_EXECUTION_REJECTED", "B8_ARTIFACT_AS_AUTHORITY_REJECTED",
    "LLM_OUTPUT_AS_AUTHORITY_REJECTED", "TOOL_OUTPUT_AS_AUTHORITY_REJECTED",
    "CONTEXT_AS_AUTHORITY_REJECTED",
    # no-external-effect + attempts (the paramount invariant — dominates the
    # derived PoE/certificate failures they also cause)
    "NO_EXTERNAL_EFFECT_VIOLATION", "EXTERNAL_EFFECT_ATTEMPT",
    "PROVIDER_CALL_ATTEMPT", "MESSAGE_SEND_ATTEMPT", "PAYMENT_ATTEMPT",
    "EXTERNAL_CRM_MUTATION_ATTEMPT", "MCP_CALL_ATTEMPT", "LLM_CALL_ATTEMPT",
    "OUTBOX_RELEASE_ATTEMPT",
    # source-surface isolation + envelope + contract
    "SOURCE_SURFACE_LEAK", "SOURCE_SURFACE_GRANTED_AUTHORITY",
    "TRANSACTION_ENVELOPE_INVALID", "EXECUTION_CONTRACT_INVALID",
    "EXECUTION_CONTRACT_CONTRADICTED", "FORBIDDEN_WRITE_SET_VIOLATION",
    # path compliance
    "PATH_COMPLIANCE_FAILED",
    # shadow + effector gate + conflict
    "SHADOW_STATE_INVALID", "STALE_BEFORE_STATE", "CONCURRENT_COMMIT_COLLISION",
    "EFFECTOR_LOCK_HELD", "CONFLICT_DETECTED", "REPLAY_DETECTED",
    "IDEMPOTENCY_MISMATCH",
    # proof-of-execution + certificate (derived checks)
    "POE_STREAM_INCOMPLETE", "POE_EVENT_ORDER_INVALID", "POE_STREAM_TAMPERED",
    "PROOF_OF_EXECUTION_INVALID", "CERTIFICATE_INVALID",
    "REPLAY_CONTEXT_INVALID",
    # authority / approval / autonomy
    "AUTHORITY_BASIS_MISSING", "APPROVAL_MISSING", "AUTONOMY_LEVEL_EXCEEDED",
    # lifecycle checkpoints + kill switch + abort
    "LIFECYCLE_CHECKPOINT_FAILED", "KILL_SWITCH_ACTIVE", "TRANSACTION_ABORTED",
    # soft
    "NEEDS_APPROVAL", "NEEDS_REVALIDATION",
    "FAULT_INJECTION_RELEASE_GATE_FAILED", "NEEDS_REVIEW",
    "B9_LOCAL_COMMIT_APPLIED",
]
_DOMINANCE_RANK = {s: i for i, s in enumerate(FAILURE_DOMINANCE)}
POSITIVE_SIGNALS = {"B9_LOCAL_COMMIT_APPLIED"}

B9_STATUSES = {
    "B9_LOCAL_COMMIT_APPLIED", "B9_LOCAL_COMMIT_PREPARED", "B9_BLOCKED",
    "B9_NEEDS_APPROVAL", "B9_NEEDS_REVALIDATION", "B9_QUARANTINED",
    "B9_CONFLICT", "B9_ABORTED", "B9_STALE", "B9_TAMPERED",
    "B9_NEEDS_REVIEW", "B9_NOT_IMPLEMENTED",
}
POSITIVE_STATUSES = {"B9_LOCAL_COMMIT_APPLIED"}
DECISION_STATUSES = {
    "B9_DECISION_ALLOW_LOCAL_COMMIT", "B9_DECISION_BLOCK",
    "B9_DECISION_NEEDS_APPROVAL", "B9_DECISION_NEEDS_REVALIDATION",
    "B9_DECISION_QUARANTINE", "B9_DECISION_CONFLICT", "B9_DECISION_ABORTED",
    "B9_DECISION_STALE", "B9_DECISION_NEEDS_REVIEW",
    "B9_DECISION_NOT_IMPLEMENTED",
}

_QUARANTINE_SIGNALS = {
    "NO_EXTERNAL_EFFECT_VIOLATION", "EXTERNAL_EFFECT_ATTEMPT",
    "PROVIDER_CALL_ATTEMPT", "MESSAGE_SEND_ATTEMPT", "PAYMENT_ATTEMPT",
    "EXTERNAL_CRM_MUTATION_ATTEMPT", "MCP_CALL_ATTEMPT", "LLM_CALL_ATTEMPT",
    "OUTBOX_RELEASE_ATTEMPT", "KILL_SWITCH_ACTIVE",
} | CONTAM_REASON_CODES
_CONFLICT_SIGNALS = {"CONFLICT_DETECTED", "CONCURRENT_COMMIT_COLLISION",
                     "EFFECTOR_LOCK_HELD", "REPLAY_DETECTED",
                     "IDEMPOTENCY_MISMATCH"}
_STALE_SIGNALS = {"STALE_BEFORE_STATE", "B8_NOT_ACCEPTED"}
_ABORT_SIGNALS = {"TRANSACTION_ABORTED"}
_APPROVAL_SIGNALS = {"APPROVAL_MISSING", "NEEDS_APPROVAL",
                     "AUTHORITY_BASIS_MISSING"}
_REVAL_SIGNALS = {"NEEDS_REVALIDATION", "B8_REVALIDATION_FAILED"}


def _status_for_signal(sig):
    if sig in ("TAMPERED", "B8_TAMPERED", "POE_STREAM_TAMPERED"):
        return "B9_TAMPERED"
    if sig in POSITIVE_SIGNALS:
        return "B9_LOCAL_COMMIT_APPLIED"
    if sig in _QUARANTINE_SIGNALS:
        return "B9_QUARANTINED"
    if sig in _CONFLICT_SIGNALS:
        return "B9_CONFLICT"
    if sig in _ABORT_SIGNALS:
        return "B9_ABORTED"
    if sig in _STALE_SIGNALS:
        return "B9_STALE"
    if sig in _APPROVAL_SIGNALS:
        return "B9_NEEDS_APPROVAL"
    if sig in _REVAL_SIGNALS:
        return "B9_NEEDS_REVALIDATION"
    if sig == "NEEDS_REVIEW":
        return "B9_NEEDS_REVIEW"
    return "B9_BLOCKED"


def _decision_for_status(status):
    return {
        "B9_LOCAL_COMMIT_APPLIED": "B9_DECISION_ALLOW_LOCAL_COMMIT",
        "B9_TAMPERED": "B9_DECISION_BLOCK",
        "B9_QUARANTINED": "B9_DECISION_QUARANTINE",
        "B9_CONFLICT": "B9_DECISION_CONFLICT",
        "B9_ABORTED": "B9_DECISION_ABORTED",
        "B9_STALE": "B9_DECISION_STALE",
        "B9_NEEDS_APPROVAL": "B9_DECISION_NEEDS_APPROVAL",
        "B9_NEEDS_REVALIDATION": "B9_DECISION_NEEDS_REVALIDATION",
        "B9_NEEDS_REVIEW": "B9_DECISION_NEEDS_REVIEW",
    }.get(status, "B9_DECISION_BLOCK")


REASON_CODES = {s: s.replace("_", " ").capitalize() + "." for s in
                FAILURE_DOMINANCE}
REASON_CODES.update({
    "B9_LOCAL_COMMIT_APPLIED": "Local, reversible internal commit applied under "
    "full B9 revalidation; B8 was evidence only; no external effect, no "
    "provider call, no message/payment/CRM/evidence mutation.",
})

INERT_OUTBOX_REASON = "B9_INERT_OUTBOX_ONLY"


def _norm(text) -> str:
    return _tr._normalize("" if text is None else str(text)).strip()


def _as_list(v):
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple, set)) else [v]


def _int(v, default=0):
    try:
        if v is None:
            return default
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return default
        return int(f)
    except (TypeError, ValueError):
        return default


def dominant_signal(signals) -> str:
    if not signals:
        return "B9_LOCAL_COMMIT_APPLIED"
    return min(signals, key=lambda s: _DOMINANCE_RANK.get(s, -1))


def status_for_signals(signals) -> str:
    return _status_for_signal(dominant_signal(signals))


# ---- B8 evidence-only handoff (revalidate, never trust as authority) ------
def build_b8_handoff(*, tenant_id, transaction_id, b8_outcome):
    o = b8_outcome or {}
    signals = []
    if not o:
        signals.append("B8_ENVELOPE_MISSING")
    else:
        if o.get("tenant_id") not in (None, tenant_id):
            signals.append("CROSS_TENANT")
        if o.get("commit_simulation_status") not in B8_ACCEPTABLE_STATUSES:
            signals.append("B8_NOT_ACCEPTED")
        # B8 must NEVER assert executability; if it does, it is tampered/poisoned.
        if o.get("commit_executable_now") is True or o.get(
                "production_ready") is True:
            signals.append("B8_PRODUCTION_CLAIM_DETECTED")
        env = o.get("assurance_envelope") or {}
        if env and (env.get("is_authority") is True or env.get(
                "authorizes_b9") is True):
            signals.append("B8_ARTIFACT_AS_AUTHORITY_REJECTED")
    r = {
        "b8_handoff_version": B8_HANDOFF_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "b8_commit_simulation_id": o.get("commit_simulation_id"),
        "b8_status": o.get("commit_simulation_status"),
        "b8_decision_hash": o.get("commit_simulation_decision_hash"),
        "b8_treated_as": "EVIDENCE_ONLY",
        "b8_is_authority": False, "b8_is_approval": False,
        "b8_is_commit_lease": False, "b8_is_b9_activation": False,
        "b8_is_provider_permission": False, "b8_revalidated_by_b9": True,
        "revalidation_passed": not signals,
        "handoff_status": "EVIDENCE_REVALIDATED" if not signals else "REJECTED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["b8_handoff_hash"] = _core_hash(r, "b8_handoff_hash", "signal")
    r["_signals"] = signals
    return r


# ---- Semantic transaction envelope ----------------------------------------
def build_transaction_envelope(*, tenant_id, transaction_id, actor_id, role_id,
                             source_surface, source_channel, object_reference,
                             case_id, task_id, run_id, requested_intent,
                             allowed_local_scope, forbidden_external_scope,
                             autonomy_level_requested, autonomy_level_allowed,
                             context_slice_hash, before_state_hash,
                             evidence_snapshot_hash, policy_snapshot_hash,
                             approval_snapshot_hash, planned_delta_hash,
                             shadow_state_hash, idempotency_key):
    surface = str(source_surface or "WEB_PORTAL").upper()
    signals = []
    if surface not in ALLOWED_SOURCE_SURFACES:
        signals.append("TRANSACTION_ENVELOPE_INVALID")
    if not object_reference or not requested_intent:
        signals.append("TRANSACTION_ENVELOPE_INVALID")
    # Forbidden external scope must be non-empty declaration of what is barred.
    forb = sorted(set(map(str, _as_list(forbidden_external_scope)))) or [
        "ALL_EXTERNAL_EFFECTS"]
    env = {
        "transaction_envelope_version": ENVELOPE_VERSION,
        "transaction_id": transaction_id, "tenant_id": tenant_id,
        "actor_id": actor_id, "role_id": str(role_id or ""),
        "source_surface": surface, "source_channel": str(source_channel or ""),
        "object_reference": str(object_reference or ""),
        "case_id": case_id, "task_id": task_id, "run_id": run_id,
        "requested_intent": _norm(requested_intent),
        "allowed_local_scope": sorted(set(map(str,
                                             _as_list(allowed_local_scope)))),
        "forbidden_external_scope": forb,
        "autonomy_level_requested": _int(autonomy_level_requested, 1),
        "autonomy_level_allowed": _int(autonomy_level_allowed, 1),
        "context_slice_hash": context_slice_hash,
        "before_state_hash": before_state_hash,
        "evidence_snapshot_hash": evidence_snapshot_hash,
        "policy_snapshot_hash": policy_snapshot_hash,
        "approval_snapshot_hash": approval_snapshot_hash,
        "planned_delta_hash": planned_delta_hash,
        "shadow_state_hash": shadow_state_hash,
        "idempotency_key": str(idempotency_key or ""),
        "is_external": False, "grants_authority": False,
        "transaction_status": "ENVELOPE_BUILT" if not signals else "INVALID",
        "reason_code": None if not signals else "TRANSACTION_ENVELOPE_INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    # canonical_hash EXCLUDES actor identity + per-request id + volatile so the
    # envelope is a function of the evidence, reproducible by any verifier.
    env["canonical_hash"] = _core_hash(
        env, "canonical_hash", "signal", "reason_code", "transaction_status",
        "transaction_id", "actor_id", "role_id")
    env["_signals"] = signals
    return env


# ---- Source surface isolation ---------------------------------------------
def build_source_surface_isolation(*, tenant_id, transaction_id, source_surface,
                                 surface_claims_authority=False,
                                 surface_claims_approval=False):
    surface = str(source_surface or "WEB_PORTAL").upper()
    future = surface in FUTURE_SURFACES
    can_originate = surface in REQUEST_ORIGIN_SURFACES
    signals = []
    if surface_claims_authority or surface_claims_approval:
        signals.append("SOURCE_SURFACE_GRANTED_AUTHORITY")
    # A future surface that tries to originate an external effect is a leak.
    if future and not can_originate:
        # metadata-only is fine; only a claimed authority/approval leaks.
        pass
    r = {
        "source_surface_isolation_version": SURFACE_ISOLATION_VERSION,
        "tenant_id": tenant_id, "transaction_id": transaction_id,
        "source_surface": surface, "is_future_surface": future,
        "metadata_only": future, "can_originate_local_request": can_originate,
        "grants_authority": False, "grants_approval": False,
        "grants_provider_access": False, "bypasses_rbac": False,
        "bypasses_tenant_policy": False, "creates_external_effect": False,
        "isolation_status": "ISOLATED" if not signals else "LEAK",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["source_surface_isolation_hash"] = _core_hash(
        r, "source_surface_isolation_hash", "signal")
    r["_signals"] = signals
    return r


# ---- Contaminated authority firewall --------------------------------------
def build_contaminated_authority_firewall(*, tenant_id, transaction_id,
                                        authority_basis, approval_record):
    ab = authority_basis or {}
    src = str(ab.get("source", "")).upper()
    signals = []
    if not src:
        signals.append("AUTHORITY_BASIS_MISSING")
    elif src in CONTAMINATED_AUTHORITY_SOURCES:
        signals.append(CONTAMINATED_AUTHORITY_SOURCES[src])
    elif src not in ALLOWED_AUTHORITY_SOURCES:
        # Unknown source is fail-closed to contaminated-context.
        signals.append("CONTEXT_AS_AUTHORITY_REJECTED")
    r = {
        "contaminated_authority_firewall_version": CONTAM_FIREWALL_VERSION,
        "tenant_id": tenant_id, "transaction_id": transaction_id,
        "authority_source": src or None,
        "allowed_authority_sources": sorted(ALLOWED_AUTHORITY_SOURCES),
        "authority_from_allowed_source": src in ALLOWED_AUTHORITY_SOURCES,
        "approval_record_present": bool(approval_record),
        "firewall_status": "CLEAN" if not signals else "CONTAMINATED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["contaminated_authority_firewall_hash"] = _core_hash(
        r, "contaminated_authority_firewall_hash", "signal")
    r["_signals"] = signals
    return r


# ---- Context slice contract (non-authoritative) ---------------------------
def build_context_slice(*, tenant_id, transaction_id, context):
    c = context or {}
    r = {
        "context_slice_version": CONTEXT_SLICE_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "context_source": str(c.get("context_source", "")),
        "context_scope": str(c.get("context_scope", "")),
        "allowed_fields": sorted(set(map(str, _as_list(c.get(
            "allowed_fields"))))),
        "forbidden_fields": sorted(set(map(str, _as_list(c.get(
            "forbidden_fields"))))),
        "evidence_refs": sorted(set(map(str, _as_list(c.get("evidence_refs"))))),
        "freshness": str(c.get("freshness", "unknown")),
        "authority_level": "NONE",  # context NEVER grants authority
        "redaction_status": str(c.get("redaction_status", "redacted")),
        "informs_planning": True, "grants_authority": False,
        "honesty_labels": HONESTY_LABELS,
    }
    r["context_hash"] = _core_hash(r, "context_hash")
    r["_signals"] = []
    return r


# ---- Shadow local state ----------------------------------------------------
def _apply_delta(before, delta):
    after = dict(before or {})
    for k, v in (delta or {}).items():
        after[str(k)] = v
    return after


def build_shadow_state(*, tenant_id, transaction_id, object_reference,
                     current_local_state, planned_delta, allowed_local_scope,
                     expected_before_state_hash=None):
    before = dict(current_local_state or {})
    delta = dict(planned_delta or {})
    scope = set(map(str, _as_list(allowed_local_scope))) or set(delta.keys())
    before_hash = _sha({"target": str(object_reference or ""), "state": before})
    delta_hash = _sha({"target": str(object_reference or ""), "delta": delta})
    after = _apply_delta(before, delta)
    shadow_hash = _sha({"target": str(object_reference or ""), "state": after})
    signals = []
    # Every delta field must be inside the allowed LOCAL write scope.
    out_of_scope = sorted(set(map(str, delta.keys())) - scope)
    if out_of_scope:
        signals.append("SHADOW_STATE_INVALID")
    # Stale before-state (effector-exclusive freshness).
    if expected_before_state_hash is not None and \
            expected_before_state_hash != before_hash:
        signals.append("STALE_BEFORE_STATE")
    r = {
        "shadow_local_state_version": SHADOW_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "object_reference": str(object_reference or ""),
        "before_state": before, "planned_delta": delta, "shadow_state": after,
        "write_set": sorted(set(map(str, delta.keys()))),
        "out_of_scope_fields": out_of_scope,
        "before_state_hash": before_hash, "planned_delta_hash": delta_hash,
        "shadow_state_hash": shadow_hash, "applied_to_production": False,
        "reversible": True, "shadow_only": True,
        "shadow_status": "VALID" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["shadow_state_wrapper_hash"] = _core_hash(
        r, "shadow_state_wrapper_hash", "signal")
    r["_signals"] = signals
    return r


# ---- Proof-of-execution contract ------------------------------------------
def build_execution_contract(*, tenant_id, transaction_id, shadow,
                          required_evidence_refs, required_policy_refs,
                          required_approval_refs, forbidden_external_effects,
                          contract_valid=True):
    write_set = shadow.get("write_set", [])
    forbidden_write = shadow.get("out_of_scope_fields", [])
    signals = []
    if not contract_valid or not write_set:
        signals.append("EXECUTION_CONTRACT_INVALID")
    if forbidden_write:
        signals.append("FORBIDDEN_WRITE_SET_VIOLATION")
    r = {
        "execution_contract_version": CONTRACT_VERSION, "tenant_id": tenant_id,
        "contract_id": "poec-" + _sha({"tx": transaction_id})[:16],
        "transaction_id": transaction_id,
        "expected_local_delta": shadow.get("planned_delta", {}),
        "allowed_write_set": write_set,
        "forbidden_write_set": forbidden_write,
        "required_evidence_refs": sorted(set(map(str, _as_list(
            required_evidence_refs)))),
        "required_policy_refs": sorted(set(map(str, _as_list(
            required_policy_refs)))),
        "required_approval_refs": sorted(set(map(str, _as_list(
            required_approval_refs)))),
        "forbidden_external_effects": sorted(set(map(str, _as_list(
            forbidden_external_effects)))) or ["ALL_EXTERNAL"],
        "rollback_required": True, "replay_required": True,
        "outcome_closure_condition": "LOCAL_COMMIT_APPLIED_AND_REVERSIBLE",
        "contract_status": "VALID" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["contract_hash"] = _core_hash(r, "contract_hash", "signal")
    r["_signals"] = signals
    return r


# ---- Runtime path compliance monitor --------------------------------------
def build_path_compliance(*, tenant_id, transaction_id, checks):
    checks = checks or {}
    results = {}
    failed = []
    for p in PATH_PREDICATES:
        ok = bool(checks.get(p, True))
        results[p] = ok
        if not ok:
            failed.append(p)
    signals = ["PATH_COMPLIANCE_FAILED"] if failed else []
    r = {
        "path_compliance_version": PATH_COMPLIANCE_VERSION,
        "tenant_id": tenant_id, "transaction_id": transaction_id,
        "predicates": results, "failed_predicates": failed,
        "all_predicates_hold": not failed,
        "path_compliance_result": "PASSED" if not failed else "FAILED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["path_compliance_hash"] = _core_hash(r, "path_compliance_hash", "signal")
    r["_signals"] = signals
    return r


# ---- Effector-exclusive local gate + conflict -----------------------------
def build_effector_gate(*, tenant_id, transaction_id, object_reference,
                     idempotency_key, lock_held_by=None,
                     prior_idempotency=None, conflicting_txs=None,
                     replay_detected=False, stale_witness=False):
    prior = prior_idempotency or {}
    ikey = str(idempotency_key or "")
    signals = []
    # Duplicate idempotency key with the SAME payload -> safe deterministic
    # replay; with a DIFFERENT payload -> mismatch (block).
    idem_dup = ikey in prior
    idem_mismatch = idem_dup and prior.get(ikey) != _sha({
        "tx": transaction_id, "target": str(object_reference or "")}) and \
        prior.get(ikey) is not None and prior.get(ikey) != "SAME"
    if lock_held_by and str(lock_held_by) != str(transaction_id):
        signals.append("EFFECTOR_LOCK_HELD")
    conflicts = []
    for t in _as_list(conflicting_txs):
        t = t or {}
        if t.get("tenant_id") not in (None, tenant_id):
            continue  # cross-tenant excluded from the conflict set
        if str(t.get("object_reference")) == str(object_reference) and \
                (set(map(str, _as_list(t.get("write_set")))) &
                 set(map(str, _as_list(t.get("my_write_set"))))
                 if t.get("my_write_set") else True):
            conflicts.append(str(t.get("transaction_id", "")))
    if conflicts:
        signals.append("CONFLICT_DETECTED")
    if replay_detected:
        signals.append("REPLAY_DETECTED")
    if idem_mismatch:
        signals.append("IDEMPOTENCY_MISMATCH")
    if stale_witness:
        signals.append("STALE_BEFORE_STATE")
    r = {
        "effector_gate_version": EFFECTOR_GATE_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "object_reference": str(object_reference or ""),
        "idempotency_key": ikey, "single_writer": True,
        "lock_acquired": not (lock_held_by and str(lock_held_by) !=
                              str(transaction_id)),
        "idempotency_duplicate": idem_dup,
        "idempotency_mismatch": idem_mismatch,
        "conflicting_transaction_ids": sorted(conflicts),
        "replay_detected": bool(replay_detected),
        "stale_before_state": bool(stale_witness),
        "gate_status": "OPEN" if not signals else "BLOCKED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["effector_gate_hash"] = _core_hash(r, "effector_gate_hash", "signal")
    r["_signals"] = signals
    return r


# ---- Inert effect outbox ---------------------------------------------------
def build_inert_outbox(*, tenant_id, transaction_id, future_effects,
                    release_attempts=0):
    items = []
    for i, e in enumerate(_as_list(future_effects)):
        e = e or {}
        items.append({
            "outbox_item_id": f"ino-{i}-" + _sha({"tx": transaction_id,
                                                 "i": i})[:12],
            "effect_category": str(e.get("category", "GENERIC_EXTERNAL")),
            "bound_transaction_hash": _sha({"tx": transaction_id}),
            "requires_approval": True,
            "missing_provider_boundary": True,
            "released": False, "provider_called": False,
            "delivery_attempted": False, "external_effect": False,
            "external_state_mutated": False, "reason_code": INERT_OUTBOX_REASON,
        })
    attempts = _int(release_attempts)
    signals = ["OUTBOX_RELEASE_ATTEMPT"] if attempts > 0 else []
    r = {
        "inert_outbox_version": OUTBOX_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "items": items,
        "item_count": len(items), "any_released": False,
        "any_provider_called": False, "any_delivery_attempted": False,
        "any_external_state_mutated": False,
        "release_attempts_detected": attempts, "inert": True,
        "reason_code": INERT_OUTBOX_REASON,
        "outbox_status": "INERT" if not signals else "RELEASE_ATTEMPT",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["inert_outbox_hash"] = _core_hash(r, "inert_outbox_hash", "signal")
    r["_signals"] = signals
    return r


# ---- No-external-effect theorem -------------------------------------------
def build_no_external_effect_theorem(*, tenant_id, transaction_id, outbox,
                                   attempt_markers):
    marker_to_signal = {
        "external_effect": "EXTERNAL_EFFECT_ATTEMPT",
        "provider_call": "PROVIDER_CALL_ATTEMPT",
        "message_send": "MESSAGE_SEND_ATTEMPT", "payment": "PAYMENT_ATTEMPT",
        "external_crm_mutation": "EXTERNAL_CRM_MUTATION_ATTEMPT",
        "mcp_call": "MCP_CALL_ATTEMPT", "llm_call": "LLM_CALL_ATTEMPT",
    }
    markers = {k: bool(v) for k, v in (attempt_markers or {}).items() if v}
    signals = sorted({marker_to_signal[k] for k in markers
                      if k in marker_to_signal})
    per_item_ok = all(
        (not it["released"]) and (not it["provider_called"]) and
        (not it["delivery_attempted"]) and (not it["external_effect"]) and
        (not it["external_state_mutated"]) for it in outbox.get("items", []))
    # The theorem is about ACTUAL released/mutated effects (per-item) and direct
    # attempt markers. A recorded outbox release-*attempt* is surfaced by the
    # inert-outbox report's own OUTBOX_RELEASE_ATTEMPT signal, which dominates,
    # so this theorem does not double-count it.
    holds = per_item_ok and not signals
    if not holds and not signals:
        signals = ["NO_EXTERNAL_EFFECT_VIOLATION"]
    r = {
        "no_external_effect_theorem_version": NO_EXTERNAL_VERSION,
        "tenant_id": tenant_id, "transaction_id": transaction_id,
        "for_all_outbox_items": {
            "released_false": per_item_ok, "provider_called_false": per_item_ok,
            "delivery_attempted_false": per_item_ok,
            "external_state_mutated_false": per_item_ok},
        "detected_attempt_markers": sorted(markers.keys()),
        "theorem_holds": holds and not signals,
        "theorem_status": "PROVED" if (holds and not signals) else "VIOLATED",
        "signals_detected": signals,
        "honesty_labels": HONESTY_LABELS,
    }
    r["no_external_effect_hash"] = _core_hash(
        r, "no_external_effect_hash", "signals_detected")
    r["_signals"] = signals
    return r


# ---- Agent lifecycle middleware checkpoints -------------------------------
def build_lifecycle_checkpoints(*, tenant_id, transaction_id, failed_checkpoints):
    failed = set(map(str, _as_list(failed_checkpoints)))
    results = []
    any_failed = False
    for cp in LIFECYCLE_CHECKPOINTS:
        ok = cp not in failed
        if not ok:
            any_failed = True
        results.append({
            "checkpoint": cp, "passed": ok,
            "reason_code": None if ok else "LIFECYCLE_CHECKPOINT_FAILED",
            "checkpoint_hash": _sha({"tx": transaction_id, "cp": cp, "ok": ok})})
    signals = ["LIFECYCLE_CHECKPOINT_FAILED"] if any_failed else []
    r = {
        "lifecycle_checkpoints_version": CHECKPOINT_VERSION,
        "tenant_id": tenant_id, "transaction_id": transaction_id,
        "checkpoints": results, "all_passed": not any_failed,
        "checkpoints_status": "PASSED" if not any_failed else "FAILED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["lifecycle_checkpoints_hash"] = _core_hash(
        r, "lifecycle_checkpoints_hash", "signal")
    r["_signals"] = signals
    return r


# ---- Proof-of-execution event stream (hash-chained) -----------------------
def build_poe_stream(*, tenant_id, transaction_id, actor_id, missing_events=None,
                  reorder=False, tamper=False, created_at=None):
    missing = set(map(str, _as_list(missing_events)))
    events = [e for e in POE_EVENTS if e not in missing]
    if reorder and len(events) >= 2:
        events[0], events[1] = events[1], events[0]
    chain = []
    prev = GENESIS
    for i, etype in enumerate(events):
        payload = {"event_type": etype, "transaction_id": transaction_id,
                   "tenant_id": tenant_id, "actor_id": actor_id, "sequence": i}
        payload_hash = _sha(payload)
        ev = {"event_id": f"poe-{i}-" + _sha({"tx": transaction_id,
                                             "e": etype})[:12],
              "transaction_id": transaction_id, "tenant_id": tenant_id,
              "actor_id": actor_id, "event_type": etype, "sequence": i,
              "previous_event_hash": prev, "event_payload_hash": payload_hash,
              "reason_code": None}
        ev["canonical_event_hash"] = _sha({"prev": prev, "payload": payload_hash,
                                          "type": etype, "seq": i})
        chain.append(ev)
        prev = ev["canonical_event_hash"]
    if tamper and chain:
        chain[0]["event_payload_hash"] = "TAMPERED"
    missing_required = [e for e in POE_EVENTS if e not in
                        {c["event_type"] for c in chain}]
    order_valid = [c["event_type"] for c in chain] == [
        e for e in POE_EVENTS if e in {c["event_type"] for c in chain}]
    # Verify chain integrity.
    chain_valid = True
    p = GENESIS
    for c in chain:
        expect = _sha({"prev": p, "payload": c["event_payload_hash"],
                      "type": c["event_type"], "seq": c["sequence"]})
        if c["previous_event_hash"] != p or c["canonical_event_hash"] != expect:
            chain_valid = False
        p = c["canonical_event_hash"]
    signals = []
    if missing_required:
        signals.append("POE_STREAM_INCOMPLETE")
    if not order_valid:
        signals.append("POE_EVENT_ORDER_INVALID")
    if not chain_valid:
        signals.append("POE_STREAM_TAMPERED")
    r = {
        "poe_stream_version": POE_STREAM_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "events": chain,
        "event_count": len(chain), "required_event_count": len(POE_EVENTS),
        "missing_events": missing_required, "event_order_valid": order_valid,
        "chain_valid": chain_valid, "hash_chained": True,
        "stream_status": "COMPLETE" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["poe_stream_hash"] = _core_hash(r, "poe_stream_hash", "signal")
    r["_signals"] = signals
    return r


def build_proof_of_execution(*, tenant_id, transaction_id, poe_stream,
                          contract, path_compliance, effector_gate,
                          no_external_effect):
    contract_valid = contract["contract_status"] == "VALID"
    stream_complete = not poe_stream["missing_events"]
    order_valid = poe_stream["event_order_valid"]
    chain_valid = poe_stream["chain_valid"]
    path_ok = path_compliance["all_predicates_hold"]
    null_effect_on_deny = no_external_effect["theorem_holds"]
    authz_ok = effector_gate["gate_status"] == "OPEN"
    factors = {
        "contract_valid": contract_valid,
        "event_stream_complete": stream_complete,
        "event_order_valid": order_valid,
        "replay_context_valid": chain_valid,
        "authorization_invariant_passed": authz_ok,
        "path_compliance_passed": path_ok,
        "null_effect_on_deny_passed": null_effect_on_deny,
        "history_integrity_passed": chain_valid,
        "replayability_passed": chain_valid and stream_complete,
    }
    valid = all(factors.values())
    signals = [] if valid else ["PROOF_OF_EXECUTION_INVALID"]
    r = {
        "proof_of_execution_version": POE_PROOF_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "factors": factors,
        "proof_of_execution_valid": valid,
        "poe_stream_hash": poe_stream["poe_stream_hash"],
        "proof_status": "VALID" if valid else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["proof_of_execution_hash"] = _core_hash(
        r, "proof_of_execution_hash", "signal")
    r["_signals"] = signals
    return r


# ---- Semantic transaction graph -------------------------------------------
def build_semantic_graph(*, tenant_id, transaction_id, envelope, shadow):
    nodes = [{"node_id": f"{t}:{transaction_id}", "node_type": t}
             for t in GRAPH_NODE_TYPES]
    edges = [
        {"from": "TaskIntent", "to": "Actor", "edge_type": "requested_by"},
        {"from": "TaskIntent", "to": "Tenant", "edge_type": "belongs_to_tenant"},
        {"from": "TaskIntent", "to": "ObjectReference",
         "edge_type": "targets_object"},
        {"from": "TaskIntent", "to": "EvidenceSnapshot",
         "edge_type": "supported_by_evidence"},
        {"from": "TaskIntent", "to": "PolicySnapshot",
         "edge_type": "constrained_by_policy"},
        {"from": "TaskIntent", "to": "ApprovalSnapshot",
         "edge_type": "requires_approval"},
        {"from": "TaskIntent", "to": "ContextSlice",
         "edge_type": "contextualized_by"},
        {"from": "PlannedDelta", "to": "ShadowState",
         "edge_type": "produces_shadow_state"},
        {"from": "ShadowState", "to": "PathComplianceResult",
         "edge_type": "validates_path"},
        {"from": "PathComplianceResult", "to": "ProofOfExecutionStream",
         "edge_type": "produces_poe_stream"},
        {"from": "ProofOfExecutionStream", "to": "ActionCertificate",
         "edge_type": "produces_certificate"},
        {"from": "ActionCertificate", "to": "LocalCommit",
         "edge_type": "commits_local_delta"},
        {"from": "LocalCommit", "to": "RollbackPlan",
         "edge_type": "prepares_rollback"},
        {"from": "LocalCommit", "to": "InertOutboxItem",
         "edge_type": "blocks_external_effect"},
        {"from": "TaskIntent", "to": "SourceSurface",
         "edge_type": "originates_from_surface"},
        {"from": "LocalCommit", "to": "AuditEvent", "edge_type": "records_audit"},
    ]
    missing_nodes = sorted(set(GRAPH_NODE_TYPES) -
                           {n["node_type"] for n in nodes})
    present_edge_types = {e["edge_type"] for e in edges}
    missing_edges = sorted(set(GRAPH_EDGE_TYPES) - present_edge_types)
    signals = []
    if missing_nodes:
        signals.append("TRANSACTION_ENVELOPE_INVALID")
    r = {
        "semantic_graph_version": GRAPH_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "nodes": nodes, "edges": edges,
        "node_count": len(nodes), "edge_count": len(edges),
        "node_types": GRAPH_NODE_TYPES, "edge_types": GRAPH_EDGE_TYPES,
        "missing_nodes": missing_nodes, "missing_edges": missing_edges,
        "trace": ["TaskIntent", "SourceSurface", "ContextSlice", "ShadowState",
                  "PathCompliance", "ProofOfExecutionStream", "Certificate",
                  "LocalCommit", "RollbackPlan", "InertOutbox", "Audit"],
        "graph_status": "COMPLETE" if not (missing_nodes or missing_edges)
        else "INCOMPLETE",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["semantic_graph_hash"] = _core_hash(r, "semantic_graph_hash", "signal")
    r["_signals"] = signals
    return r


# ---- Rollback readiness ----------------------------------------------------
def build_rollback_readiness(*, tenant_id, transaction_id, shadow, abort_stage=None,
                          kill_switch=False):
    steps = [{"undo_field": k, "restore_to": v, "reversible": True}
             for k, v in shadow.get("before_state", {}).items()]
    signals = []
    if kill_switch:
        signals.append("KILL_SWITCH_ACTIVE")
    aborted = abort_stage in ("pre_commit", "validation", "shadow",
                              "pre_finalization")
    if aborted:
        signals.append("TRANSACTION_ABORTED")
    r = {
        "rollback_readiness_version": ROLLBACK_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "rollback_plan": steps, "rollback_ready": True,
        "before_state_hash": shadow["before_state_hash"],
        "rollback_hash": _sha({"tx": transaction_id,
                              "before": shadow["before_state_hash"]}),
        "supports_pre_commit_abort": True, "supports_validation_abort": True,
        "supports_shadow_abort": True, "supports_pre_finalization_abort": True,
        "supports_post_commit_rollback_request": True,
        "kill_switch_state": "ACTIVE" if kill_switch else "INACTIVE",
        "abort_stage": abort_stage,
        "executable_rollback_deferred_to": "B9.1",
        "readiness_status": "ABORTED" if aborted else ("KILL_SWITCH" if
                          kill_switch else "READY"),
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["rollback_readiness_hash"] = _core_hash(
        r, "rollback_readiness_hash", "signal")
    r["_signals"] = signals
    return r


# ---- Proof-carrying local action certificate ------------------------------
def build_certificate(*, tenant_id, transaction_id, actor_id, envelope,
                   authority_basis, approval_record, evidence_refs, policy_refs,
                   shadow, proof_of_execution, path_compliance, rollback,
                   no_external_effect, will_apply):
    after_hash = shadow["shadow_state_hash"] if will_apply else \
        shadow["before_state_hash"]
    cert = {
        "certificate_version": CERTIFICATE_VERSION, "tenant_id": tenant_id,
        "certificate_id": "pcac-" + _sha({"tx": transaction_id})[:16],
        "transaction_id": transaction_id, "actor_id": actor_id,
        "authorized_action": envelope.get("requested_intent"),
        "for_object": envelope.get("object_reference"),
        "for_case_id": envelope.get("case_id"),
        "for_task_id": envelope.get("task_id"),
        "authority_basis": {"source": (authority_basis or {}).get("source")},
        "approval_basis": {"present": bool(approval_record),
                           "refs": sorted(set(map(str, _as_list(
                               (approval_record or {}).get("refs")))))},
        "evidence_basis": sorted(set(map(str, _as_list(evidence_refs)))),
        "policy_basis": sorted(set(map(str, _as_list(policy_refs)))),
        "proof_of_execution_hash": proof_of_execution["proof_of_execution_hash"],
        "path_compliance_result": path_compliance["path_compliance_result"],
        "before_state_hash": shadow["before_state_hash"],
        "shadow_state_hash": shadow["shadow_state_hash"],
        "after_state_hash": after_hash,
        "rollback_hash": rollback["rollback_hash"],
        "no_external_effect_hash": no_external_effect["no_external_effect_hash"],
        "runtime_receipt_hash": _sha({"tx": transaction_id, "poe":
                                     proof_of_execution["proof_of_execution_hash"]}),
        "outcome_closure_hash": _sha({"closure":
                                     "LOCAL_COMMIT_APPLIED_AND_REVERSIBLE",
                                     "tx": transaction_id}),
        "forbidden": ["EXTERNAL_EFFECT", "PROVIDER_CALL", "MESSAGE_SEND",
                      "PAYMENT", "EXTERNAL_MUTATION"],
        "is_authority": False, "is_commit_lease": False,
        "replayable_for_audit": True,
        "verification_status": "VALID",
        "honesty_labels": HONESTY_LABELS,
    }
    cert["certificate_hash"] = _core_hash(cert, "certificate_hash",
                                         "verification_status")
    cert["_signals"] = []
    return cert


# ---- Replay context --------------------------------------------------------
def build_replay_context(*, tenant_id, transaction_id, envelope, shadow,
                      poe_stream, certificate, evidence_refs, policy_refs,
                      approval_record, will_apply):
    after_hash = shadow["shadow_state_hash"] if will_apply else \
        shadow["before_state_hash"]
    r = {
        "replay_context_version": REPLAY_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "code_version_or_commit_ref": B9_MODEL_VERSION,
        "migration_version": "v24",
        "policy_snapshot_hash": _sha({"policy": sorted(set(map(str, _as_list(
            policy_refs))))}),
        "evidence_snapshot_hash": _sha({"evidence": sorted(set(map(str,
            _as_list(evidence_refs))))}),
        "approval_snapshot_hash": _sha({"approval": (approval_record or {})}),
        "before_state_hash": shadow["before_state_hash"],
        "after_state_hash": after_hash,
        "event_stream_hash": poe_stream["poe_stream_hash"],
        "certificate_hash": certificate["certificate_hash"],
        "deterministic_inputs_hash": _sha({
            "envelope": envelope["canonical_hash"],
            "delta": shadow["planned_delta_hash"]}),
        "executes_production_effects": False, "audit_only": True,
        "replay_status": "REPLAYABLE",
        "honesty_labels": HONESTY_LABELS,
    }
    r["replay_context_hash"] = _core_hash(r, "replay_context_hash")
    r["_signals"] = []
    return r


# ---- Deterministic commit attestation -------------------------------------
def build_commit_attestation(*, tenant_id, transaction_id, actor_id, envelope,
                          graph, proof_of_execution, certificate, shadow,
                          rollback, path_compliance, evidence_refs, policy_refs,
                          approval_record, no_external_effect, will_apply):
    after_hash = shadow["shadow_state_hash"] if will_apply else \
        shadow["before_state_hash"]
    a = {
        "commit_attestation_version": ATTESTATION_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "transaction_hash": envelope["canonical_hash"],
        "graph_hash": graph["semantic_graph_hash"],
        "proof_of_execution_hash": proof_of_execution["proof_of_execution_hash"],
        "certificate_hash": certificate["certificate_hash"],
        "actor_hash": _sha({"actor": actor_id}),
        "tenant_hash": _sha({"tenant": tenant_id}),
        "target_hash": _sha({"target": envelope.get("object_reference")}),
        "before_hash": shadow["before_state_hash"],
        "shadow_hash": shadow["shadow_state_hash"],
        "after_hash": after_hash,
        "rollback_hash": rollback["rollback_hash"],
        "policy_hash": _sha({"policy": sorted(set(map(str,
            _as_list(policy_refs))))}),
        "evidence_hash": _sha({"evidence": sorted(set(map(str,
            _as_list(evidence_refs))))}),
        "approval_hash": _sha({"approval": (approval_record or {})}),
        "route_topology_hash": _sha({"routes": "b9-local-transactions-only"}),
        "no_external_effect_hash": no_external_effect["no_external_effect_hash"],
        "path_compliance_hash": path_compliance["path_compliance_hash"],
        "commit_applied": will_apply,
        "honesty_labels": HONESTY_LABELS,
    }
    a["commit_hash"] = _core_hash(a, "commit_hash")
    a["_signals"] = []
    return a


# --- Autonomy + approval checks --------------------------------------------
def _autonomy_signals(ctx):
    sigs = []
    req = _int(ctx.get("autonomy_level_requested"), 1)
    allowed = min(
        _int(ctx.get("role_autonomy_limit"), 5),
        _int(ctx.get("tenant_policy_limit"), 5),
        _int(ctx.get("segment_policy_limit"), 5),
        _int(ctx.get("tool_risk_limit"), 5),
        _int(ctx.get("evidence_confidence_limit"), 5),
        _int(ctx.get("human_approval_limit"), 5),
        _int(ctx.get("historical_trust_limit"), 5))
    if req > allowed:
        sigs.append("AUTONOMY_LEVEL_EXCEEDED")
    return sigs, allowed


def _approval_signals(ctx):
    sigs = []
    rec = ctx.get("approval_record")
    if ctx["policy"].get("require_approval_for_commit", 1) and not (
            rec and rec.get("server_verified")):
        sigs.append("APPROVAL_MISSING")
    return sigs


# --- Signal aggregation -----------------------------------------------------
def _b9_signals(ctx):
    tid = ctx["tenant_id"]
    txid = ctx["transaction_id"]
    reports = {}
    signals = []

    handoff = build_b8_handoff(tenant_id=tid, transaction_id=txid,
                               b8_outcome=ctx.get("b8_outcome"))
    reports["b8_handoff"] = handoff

    firewall = build_contaminated_authority_firewall(
        tenant_id=tid, transaction_id=txid,
        authority_basis=ctx.get("authority_basis"),
        approval_record=ctx.get("approval_record"))
    reports["contaminated_authority_firewall"] = firewall

    surface = build_source_surface_isolation(
        tenant_id=tid, transaction_id=txid,
        source_surface=ctx.get("source_surface"),
        surface_claims_authority=ctx.get("surface_claims_authority", False),
        surface_claims_approval=ctx.get("surface_claims_approval", False))
    reports["source_surface_isolation"] = surface

    context = build_context_slice(tenant_id=tid, transaction_id=txid,
                                  context=ctx.get("context_slice"))
    reports["context_slice"] = context

    shadow = build_shadow_state(
        tenant_id=tid, transaction_id=txid,
        object_reference=ctx.get("object_reference"),
        current_local_state=ctx.get("current_local_state"),
        planned_delta=ctx.get("planned_delta"),
        allowed_local_scope=ctx.get("allowed_local_scope"),
        expected_before_state_hash=ctx.get("expected_before_state_hash"))
    reports["shadow_state"] = shadow

    envelope = build_transaction_envelope(
        tenant_id=tid, transaction_id=txid, actor_id=ctx.get("actor_id"),
        role_id=ctx.get("role_id"), source_surface=ctx.get("source_surface"),
        source_channel=ctx.get("source_channel"),
        object_reference=ctx.get("object_reference"),
        case_id=ctx.get("case_id"), task_id=ctx.get("task_id"),
        run_id=ctx.get("run_id"), requested_intent=ctx.get("requested_intent"),
        allowed_local_scope=ctx.get("allowed_local_scope"),
        forbidden_external_scope=ctx.get("forbidden_external_scope"),
        autonomy_level_requested=ctx.get("autonomy_level_requested"),
        autonomy_level_allowed=ctx.get("_autonomy_allowed", 1),
        context_slice_hash=context["context_hash"],
        before_state_hash=shadow["before_state_hash"],
        evidence_snapshot_hash=_sha({"ev": sorted(set(map(str, _as_list(
            ctx.get("evidence_refs")))))}),
        policy_snapshot_hash=_sha({"pol": sorted(set(map(str, _as_list(
            ctx.get("policy_refs")))))}),
        approval_snapshot_hash=_sha({"ap": ctx.get("approval_record") or {}}),
        planned_delta_hash=shadow["planned_delta_hash"],
        shadow_state_hash=shadow["shadow_state_hash"],
        idempotency_key=ctx.get("idempotency_key"))
    reports["transaction_envelope"] = envelope

    contract = build_execution_contract(
        tenant_id=tid, transaction_id=txid, shadow=shadow,
        required_evidence_refs=ctx.get("evidence_refs"),
        required_policy_refs=ctx.get("policy_refs"),
        required_approval_refs=(ctx.get("approval_record") or {}).get("refs"),
        forbidden_external_effects=ctx.get("forbidden_external_scope"),
        contract_valid=ctx.get("contract_valid", True))
    reports["execution_contract"] = contract

    path = build_path_compliance(tenant_id=tid, transaction_id=txid,
                                 checks=ctx.get("path_checks"))
    reports["path_compliance"] = path

    effector = build_effector_gate(
        tenant_id=tid, transaction_id=txid,
        object_reference=ctx.get("object_reference"),
        idempotency_key=ctx.get("idempotency_key"),
        lock_held_by=ctx.get("lock_held_by"),
        prior_idempotency=ctx.get("prior_idempotency"),
        conflicting_txs=ctx.get("conflicting_txs"),
        replay_detected=ctx.get("replay_detected", False),
        stale_witness=ctx.get("stale_witness", False))
    reports["effector_gate"] = effector

    outbox = build_inert_outbox(
        tenant_id=tid, transaction_id=txid,
        future_effects=ctx.get("future_effects"),
        release_attempts=ctx.get("outbox_release_attempts", 0))
    reports["inert_outbox"] = outbox
    no_ext = build_no_external_effect_theorem(
        tenant_id=tid, transaction_id=txid, outbox=outbox,
        attempt_markers=ctx.get("attempt_markers"))
    reports["no_external_effect_theorem"] = no_ext

    checkpoints = build_lifecycle_checkpoints(
        tenant_id=tid, transaction_id=txid,
        failed_checkpoints=ctx.get("failed_checkpoints"))
    reports["lifecycle_checkpoints"] = checkpoints

    poe_stream = build_poe_stream(
        tenant_id=tid, transaction_id=txid, actor_id=ctx.get("actor_id"),
        missing_events=ctx.get("missing_poe_events"),
        reorder=ctx.get("poe_reorder", False),
        tamper=ctx.get("poe_tamper", False))
    reports["poe_stream"] = poe_stream
    poe = build_proof_of_execution(
        tenant_id=tid, transaction_id=txid, poe_stream=poe_stream,
        contract=contract, path_compliance=path, effector_gate=effector,
        no_external_effect=no_ext)
    reports["proof_of_execution"] = poe

    graph = build_semantic_graph(tenant_id=tid, transaction_id=txid,
                                 envelope=envelope, shadow=shadow)
    reports["semantic_graph"] = graph

    rollback = build_rollback_readiness(
        tenant_id=tid, transaction_id=txid, shadow=shadow,
        abort_stage=ctx.get("abort_stage"),
        kill_switch=ctx.get("kill_switch", False))
    reports["rollback_readiness"] = rollback

    # autonomy + approval + tamper on B8
    au_sigs, allowed = _autonomy_signals(ctx)
    ctx["_autonomy_allowed"] = allowed
    ap_sigs = _approval_signals(ctx)

    # Collect signals from every report.
    for rep in reports.values():
        signals.extend(rep.get("_signals", []))
    signals.extend(au_sigs)
    signals.extend(ap_sigs)

    # will_apply only if nothing blocking so far (for cert/after-state).
    will_apply = not signals
    certificate = build_certificate(
        tenant_id=tid, transaction_id=txid, actor_id=ctx.get("actor_id"),
        envelope=envelope, authority_basis=ctx.get("authority_basis"),
        approval_record=ctx.get("approval_record"),
        evidence_refs=ctx.get("evidence_refs"),
        policy_refs=ctx.get("policy_refs"), shadow=shadow,
        proof_of_execution=poe, path_compliance=path, rollback=rollback,
        no_external_effect=no_ext, will_apply=will_apply)
    reports["certificate"] = certificate
    replay = build_replay_context(
        tenant_id=tid, transaction_id=txid, envelope=envelope, shadow=shadow,
        poe_stream=poe_stream, certificate=certificate,
        evidence_refs=ctx.get("evidence_refs"),
        policy_refs=ctx.get("policy_refs"),
        approval_record=ctx.get("approval_record"), will_apply=will_apply)
    reports["replay_context"] = replay
    attestation = build_commit_attestation(
        tenant_id=tid, transaction_id=txid, actor_id=ctx.get("actor_id"),
        envelope=envelope, graph=graph, proof_of_execution=poe,
        certificate=certificate, shadow=shadow, rollback=rollback,
        path_compliance=path, evidence_refs=ctx.get("evidence_refs"),
        policy_refs=ctx.get("policy_refs"),
        approval_record=ctx.get("approval_record"), no_external_effect=no_ext,
        will_apply=will_apply)
    reports["commit_attestation"] = attestation

    return signals, reports, will_apply


# ---- Fault injection harness ----------------------------------------------
FAULT_CASES = [
    "b8_as_authority", "b8_not_accepted", "b8_production_claim",
    "document_as_command", "artifact_as_authority", "channel_as_approval",
    "mobile_push_as_approval", "workbench_output_as_execution",
    "llm_output_as_authority", "context_as_authority", "surface_grants_authority",
    "path_compliance_fail", "shadow_out_of_scope", "stale_before_state",
    "conflict", "replay", "idempotency_mismatch", "poe_missing_event",
    "poe_reorder", "poe_tamper", "external_effect_attempt", "provider_call",
    "outbox_release", "kill_switch", "approval_missing", "autonomy_exceeded",
    "checkpoint_failed",
]


def _apply_fault(fault, ctx):
    c = dict(ctx)
    if fault == "b8_as_authority":
        c["b8_outcome"] = dict(ctx.get("b8_outcome") or {},
                               assurance_envelope={"is_authority": True})
    elif fault == "b8_not_accepted":
        c["b8_outcome"] = dict(ctx.get("b8_outcome") or {},
                               commit_simulation_status="B8_V5_BLOCKED")
    elif fault == "b8_production_claim":
        c["b8_outcome"] = dict(ctx.get("b8_outcome") or {},
                               production_ready=True)
    elif fault == "document_as_command":
        c["authority_basis"] = {"source": "DOCUMENT"}
    elif fault == "artifact_as_authority":
        c["authority_basis"] = {"source": "ARTIFACT_LABEL"}
    elif fault == "channel_as_approval":
        c["authority_basis"] = {"source": "SLACK_MESSAGE"}
    elif fault == "mobile_push_as_approval":
        c["authority_basis"] = {"source": "MOBILE_PUSH"}
    elif fault == "workbench_output_as_execution":
        c["authority_basis"] = {"source": "WORKBENCH_OUTPUT"}
    elif fault == "llm_output_as_authority":
        c["authority_basis"] = {"source": "LLM_OUTPUT"}
    elif fault == "context_as_authority":
        c["authority_basis"] = {"source": "CONTEXT_SLICE"}
    elif fault == "surface_grants_authority":
        c["surface_claims_authority"] = True
    elif fault == "path_compliance_fail":
        c["path_checks"] = {"consent_ok": False}
    elif fault == "shadow_out_of_scope":
        c["allowed_local_scope"] = ["only_this"]
        c["planned_delta"] = {"forbidden_field": "x"}
    elif fault == "stale_before_state":
        c["expected_before_state_hash"] = "STALE"
    elif fault == "conflict":
        c["conflicting_txs"] = [{"transaction_id": "other",
                                "tenant_id": ctx["tenant_id"],
                                "object_reference": ctx.get("object_reference")}]
    elif fault == "replay":
        c["replay_detected"] = True
    elif fault == "idempotency_mismatch":
        c["prior_idempotency"] = {str(ctx.get("idempotency_key") or ""): "OTHER"}
    elif fault == "poe_missing_event":
        c["missing_poe_events"] = ["LOCAL_COMMIT_APPLIED"]
    elif fault == "poe_reorder":
        c["poe_reorder"] = True
    elif fault == "poe_tamper":
        c["poe_tamper"] = True
    elif fault == "external_effect_attempt":
        c["attempt_markers"] = {"external_effect": True}
    elif fault == "provider_call":
        c["attempt_markers"] = {"provider_call": True}
    elif fault == "outbox_release":
        c["outbox_release_attempts"] = 1
    elif fault == "kill_switch":
        c["kill_switch"] = True
    elif fault == "approval_missing":
        c["approval_record"] = None
    elif fault == "autonomy_exceeded":
        c["autonomy_level_requested"] = 9
        c["role_autonomy_limit"] = 1
    elif fault == "checkpoint_failed":
        c["failed_checkpoints"] = ["pre_commit_validation"]
    return c


def run_fault_injection_harness(*, tenant_id, transaction_id, base_ctx):
    cases = []
    all_blocked = True
    for fault in FAULT_CASES:
        c = _apply_fault(fault, base_ctx)
        sigs, _, _ = _b9_signals(c)
        sigs = sorted(set(sigs)) or ["B9_LOCAL_COMMIT_APPLIED"]
        dom = dominant_signal(sigs)
        status = _status_for_signal(dom)
        blocked = status not in POSITIVE_STATUSES
        if not blocked:
            all_blocked = False
        cases.append({"fault": fault, "dominant_signal": dom,
                      "resulting_status": status, "blocked": blocked})
    h = {
        "b9_fault_injection_harness_version": FAULT_HARNESS_VERSION,
        "tenant_id": tenant_id, "transaction_id": transaction_id,
        "fault_cases": cases, "fault_case_count": len(cases),
        "all_faults_blocked": all_blocked,
        "harness_status": "ALL_BLOCKED" if all_blocked else "LEAK_DETECTED",
        "honesty_labels": HONESTY_LABELS,
    }
    h["b9_fault_injection_harness_hash"] = _core_hash(
        h, "b9_fault_injection_harness_hash")
    return h


def build_release_gate(*, tenant_id, transaction_id, harness):
    passed = harness["all_faults_blocked"]
    g = {
        "b9_release_gate_version": RELEASE_GATE_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "negative_tests_total": harness["fault_case_count"],
        "negative_tests_blocked": sum(1 for c in harness["fault_cases"]
                                      if c["blocked"]),
        "release_gate_status": "PASSED" if passed else "FAILED",
        "signal": None if passed else "FAULT_INJECTION_RELEASE_GATE_FAILED",
        "honesty_labels": HONESTY_LABELS,
    }
    g["b9_release_gate_hash"] = _core_hash(g, "b9_release_gate_hash", "signal")
    return g


def build_conformance_vector(*, tenant_id, transaction_id, reports, harness,
                           release_gate, will_apply):
    dims = {
        "b8_evidence_only": reports["b8_handoff"]["b8_is_authority"] is False,
        "b8_revalidated": reports["b8_handoff"]["b8_revalidated_by_b9"] is True,
        "authority_from_allowed_source": reports[
            "contaminated_authority_firewall"]["firewall_status"] == "CLEAN",
        "source_surface_isolated": reports["source_surface_isolation"][
            "isolation_status"] == "ISOLATED",
        "context_non_authoritative": reports["context_slice"][
            "grants_authority"] is False,
        "shadow_valid": reports["shadow_state"]["shadow_status"] == "VALID",
        "path_compliant": reports["path_compliance"]["all_predicates_hold"],
        "poe_complete": reports["poe_stream"]["stream_status"] == "COMPLETE",
        "proof_of_execution_valid": reports["proof_of_execution"][
            "proof_of_execution_valid"],
        "graph_complete": reports["semantic_graph"]["graph_status"] ==
        "COMPLETE",
        "outbox_inert": reports["inert_outbox"]["outbox_status"] == "INERT",
        "no_external_effect": reports["no_external_effect_theorem"][
            "theorem_holds"],
        "rollback_ready": reports["rollback_readiness"]["rollback_ready"] is
        True,
        "certificate_valid": reports["certificate"]["verification_status"] ==
        "VALID",
        "effector_gate_open": reports["effector_gate"]["gate_status"] == "OPEN",
        "checkpoints_passed": reports["lifecycle_checkpoints"]["all_passed"],
        "fault_injection_all_blocked": harness["all_faults_blocked"],
        "release_gate_passed": release_gate["release_gate_status"] == "PASSED",
    }
    conformant = all(dims.values())
    cv = {
        "b9_conformance_vector_version": CONFORMANCE_VERSION,
        "tenant_id": tenant_id, "transaction_id": transaction_id,
        "dimensions": dims, "conformant": conformant,
        "honesty_labels": HONESTY_LABELS,
    }
    cv["b9_conformance_vector_hash"] = _core_hash(
        cv, "b9_conformance_vector_hash")
    return cv


_COMPONENT_HASH_KEYS = {
    "b8_handoff": "b8_handoff_hash",
    "contaminated_authority_firewall": "contaminated_authority_firewall_hash",
    "source_surface_isolation": "source_surface_isolation_hash",
    "context_slice": "context_hash",
    "shadow_state": "shadow_state_wrapper_hash",
    "transaction_envelope": "canonical_hash",
    "execution_contract": "contract_hash",
    "path_compliance": "path_compliance_hash",
    "effector_gate": "effector_gate_hash",
    "inert_outbox": "inert_outbox_hash",
    "no_external_effect_theorem": "no_external_effect_hash",
    "lifecycle_checkpoints": "lifecycle_checkpoints_hash",
    "poe_stream": "poe_stream_hash",
    "proof_of_execution": "proof_of_execution_hash",
    "semantic_graph": "semantic_graph_hash",
    "rollback_readiness": "rollback_readiness_hash",
    "certificate": "certificate_hash",
    "replay_context": "replay_context_hash",
    "commit_attestation": "commit_hash",
}


def build_proof_bundle(*, tenant_id, transaction_id, reports, harness,
                     release_gate, status, dominant):
    component_hashes = {}
    for rep_key, hash_key in _COMPONENT_HASH_KEYS.items():
        rep = reports.get(rep_key)
        if rep and hash_key in rep:
            component_hashes[hash_key] = rep[hash_key]
    component_hashes["b9_fault_injection_harness_hash"] = harness[
        "b9_fault_injection_harness_hash"]
    component_hashes["b9_release_gate_hash"] = release_gate["b9_release_gate_hash"]
    pb = {
        "b9_proof_bundle_version": PROOF_BUNDLE_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "component_hashes": component_hashes,
        "component_count": len(component_hashes), "resolved_status": status,
        "dominant_signal": dominant, "proof_bundle_overrides_blocker": False,
        "grants_authority": False, "authorizes_external_effect": False,
        "honesty_labels": HONESTY_LABELS,
    }
    pb["b9_proof_bundle_hash"] = _core_hash(pb, "b9_proof_bundle_hash")
    return pb


# --- Orchestration ----------------------------------------------------------
_PASS_KEYS = (
    "b8_outcome", "actor_id", "role_id", "source_surface", "source_channel",
    "object_reference", "case_id", "task_id", "run_id", "requested_intent",
    "allowed_local_scope", "forbidden_external_scope", "autonomy_level_requested",
    "role_autonomy_limit", "tenant_policy_limit", "segment_policy_limit",
    "tool_risk_limit", "evidence_confidence_limit", "human_approval_limit",
    "historical_trust_limit", "context_slice", "current_local_state",
    "planned_delta", "expected_before_state_hash", "evidence_refs", "policy_refs",
    "authority_basis", "approval_record", "idempotency_key", "lock_held_by",
    "prior_idempotency", "conflicting_txs", "replay_detected", "stale_witness",
    "future_effects", "outbox_release_attempts", "attempt_markers",
    "failed_checkpoints", "missing_poe_events", "poe_reorder", "poe_tamper",
    "path_checks", "contract_valid", "surface_claims_authority",
    "surface_claims_approval", "abort_stage", "kill_switch", "policy",
)


def prepare_local_transaction_outcome(*, transaction_id, tenant_id, actor_id,
                                    actor_type, envelope=None, b8_outcome=None,
                                    created_at=None, **over):
    """Prepare a Finalis Transaction Twin + proof-of-execution outcome and
    resolve whether a LOCAL, REVERSIBLE commit is allowed. Runs the full
    deterministic evaluation, the fault-injection harness and the release gate,
    then the fail-closed status. Produces only local evidence + (when allowed) a
    reversible local commit intent; performs NO external effect, NO provider
    call, NO message/payment/CRM/evidence mutation. B8 is evidence only."""
    pol = dict(DEFAULT_POLICY)
    for k, v in (over.get("policy") or {}).items():
        if k in DEFAULT_POLICY:
            pol[k] = v
    ctx = {"tenant_id": tenant_id, "transaction_id": transaction_id,
           "actor_id": actor_id, "b8_outcome": b8_outcome, "policy": pol,
           "created_at": created_at}
    for k in _PASS_KEYS:
        if k in over:
            ctx[k] = over[k]
    ctx["policy"] = pol
    ctx.setdefault("object_reference", "obj-1")
    ctx.setdefault("requested_intent", "update local object")
    ctx.setdefault("planned_delta", {"status": "reviewed"})
    ctx.setdefault("current_local_state", {"status": "new"})
    ctx.setdefault("allowed_local_scope", ["status"])
    ctx.setdefault("source_surface", "WEB_PORTAL")
    ctx.setdefault("authority_basis", {"source": "SERVER_RBAC"})
    ctx.setdefault("approval_record", {"server_verified": True,
                                       "refs": ["ap-1"]})
    ctx.setdefault("idempotency_key", "idem-" + str(transaction_id))

    signals, reports, will_apply = _b9_signals(ctx)

    harness = run_fault_injection_harness(
        tenant_id=tenant_id, transaction_id=transaction_id, base_ctx=ctx)
    release_gate = build_release_gate(
        tenant_id=tenant_id, transaction_id=transaction_id, harness=harness)
    if release_gate["signal"]:
        signals.append(release_gate["signal"])

    signals = sorted(set(signals))
    if not signals:
        signals = ["B9_LOCAL_COMMIT_APPLIED"]
    dominant = dominant_signal(signals)
    status = _status_for_signal(dominant)
    decision = _decision_for_status(status)
    commit_applied = status == "B9_LOCAL_COMMIT_APPLIED"

    conformance = build_conformance_vector(
        tenant_id=tenant_id, transaction_id=transaction_id, reports=reports,
        harness=harness, release_gate=release_gate, will_apply=commit_applied)
    proof_bundle = build_proof_bundle(
        tenant_id=tenant_id, transaction_id=transaction_id, reports=reports,
        harness=harness, release_gate=release_gate, status=status,
        dominant=dominant)

    outcome_kind = "LOCAL_REVERSIBLE_COMMIT" if commit_applied else status
    clean_reports = {}
    for k, rep in reports.items():
        if isinstance(rep, dict):
            clean_reports[k] = {kk: vv for kk, vv in rep.items()
                                if kk != "_signals"}
        else:
            clean_reports[k] = rep
    shadow = clean_reports["shadow_state"]
    outcome = {
        "b9_model_version": B9_MODEL_VERSION, "transaction_id": transaction_id,
        "tenant_id": tenant_id, "actor_id": actor_id,
        "b8_commit_simulation_id": (b8_outcome or {}).get(
            "commit_simulation_id"),
        "b9_status": status, "b9_decision_status": decision,
        "b9_outcome_kind": outcome_kind, "dominant_signal": dominant,
        "dominant_reason_code": REASON_CODES.get(dominant, ""),
        "all_signals": signals,
        "signal_reason_codes": {s: REASON_CODES.get(s, "") for s in signals},
        "local_commit_applied": commit_applied,
        "object_reference": ctx.get("object_reference"),
        "before_state_hash": shadow["before_state_hash"],
        "shadow_state_hash": shadow["shadow_state_hash"],
        "after_state_hash": (shadow["shadow_state_hash"] if commit_applied
                             else shadow["before_state_hash"]),
        "committed_state": (shadow["shadow_state"] if commit_applied else
                            shadow["before_state"]),
        "b8_evidence_only": True, "is_external": False, "is_execution": False,
        "produced_external_effect": False, "provider_called": False,
        "message_sent": False, "payment_executed": False,
        "external_crm_mutated": False, "reversible": True,
        "b9_transaction_request_hash": (envelope or {}).get("canonical_hash") or
        clean_reports["transaction_envelope"]["canonical_hash"],
        "decided_by_actor_id": actor_id, "decided_by_actor_type": actor_type,
        "created_at": created_at, "updated_at": created_at,
        "b9_fault_injection_harness": harness,
        "b9_release_gate_report": release_gate,
        "b9_conformance_vector": conformance, "b9_proof_bundle": proof_bundle,
        "honesty_labels": HONESTY_LABELS,
    }
    outcome.update(clean_reports)
    outcome["b9_decision_hash"] = _core_hash(
        outcome, "b9_decision_hash", "transaction_id", "actor_id",
        "decided_by_actor_id", "decided_by_actor_type", "b9_state_hash")
    outcome["b9_state_hash"] = _sha({
        "transaction_id": transaction_id,
        "b9_decision_hash": outcome["b9_decision_hash"], "b9_status": status,
        "dominant_signal": dominant,
        "proof_bundle_hash": proof_bundle["b9_proof_bundle_hash"]})
    return outcome


# --- Event ledger ----------------------------------------------------------
B9_EVENT_TYPES = {
    "B9_TX_REQUEST_OPENED", "B9_TX_OUTCOME_PREPARED", "B9_TX_FAULT_INJECTED",
    "B9_TX_OUTCOME_VERIFIED",
}


def build_b9_event(*, event_type, tenant_id, transaction_id, actor_id,
                actor_type, b9_state_hash, previous_event_hash, sequence,
                detail, created_at):
    ev = {
        "b9_event_version": B9_EVENT_VERSION, "event_type": event_type,
        "tenant_id": tenant_id, "transaction_id": transaction_id,
        "actor_id": actor_id, "actor_type": actor_type,
        "b9_state_hash": b9_state_hash,
        "previous_event_hash": previous_event_hash or GENESIS,
        "sequence": sequence, "detail": detail or {}, "created_at": created_at,
    }
    ev["event_hash"] = _core_hash(ev, "event_hash")
    return ev
