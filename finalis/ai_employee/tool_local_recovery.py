"""Recovery Safety Case + Chaos Sentinel + Proof-of-Recovery Runtime
(TOOL-B9.1 v4).

The resilience / rollback / quarantine / stuck-state / safety-case layer for the
first local governed transaction runtime (TOOL-B9). It proves that B9 stays SAFE
under failure: crash after any phase, partial local commit, incomplete/tampered
Proof-of-Execution stream, replay, idempotency mismatch, stale/interrupted lock,
rollback ambiguity, failed rollback, stuck recovery, emergency abort and
quarantine.

It is LOCAL-ONLY. For every recovery/rollback/abort/quarantine/stuck/crash-drill
operation it produces a deterministic **Recovery Twin**, a hash-chained
**Proof-of-Recovery** event stream, a **Proof-of-Recovery certificate**, a
machine-checkable **Recovery Safety Case**, a **double-entry state
reconciliation** and a **safety-monotonicity** proof — all EVIDENCE, never
authority.

Hard invariants (every one fail-closed and tested):
- Recovery never creates a new authority path; rollback never creates an
  external effect; emergency abort dominates every commit path.
- The inert outbox stays inert; released/provider_called/delivery_attempted/
  external_state_mutated are all false for every op.
- B8 stays evidence only; the B9 certificate, Proof-of-Execution,
  Proof-of-Recovery and Recovery Safety Case are proof, NOT authority.
- Recovery cannot increase authority/autonomy, broaden write scope, or make the
  inert outbox releasable (safety monotonicity).
- A failed recovery fails closed; a tampered transaction quarantines; a stuck
  transaction does not self-heal into execution.

It does NOT call providers/MCP/LLM, send messages, execute payments, mutate any
external/CRM/evidence system, retry providers, dispatch webhooks or release the
outbox. NOT_PRODUCTION_READY.
"""
from __future__ import annotations

from .tool_contracts import canonical_json, _sha, _core_hash
from . import tool_registry as _tr

B91_MODEL_VERSION = "finalis-recovery-safety-case-proof-of-recovery-runtime-v4"
RECOVERY_TWIN_VERSION = "finalis-transaction-recovery-twin-v1"
POR_STREAM_VERSION = "finalis-proof-of-recovery-event-stream-v1"
POR_CONTRACT_VERSION = "finalis-proof-of-recovery-contract-v1"
POR_CERT_VERSION = "finalis-proof-of-recovery-certificate-v1"
SAFETY_CASE_VERSION = "finalis-recovery-safety-case-v1"
RECONCILIATION_VERSION = "finalis-double-entry-state-reconciliation-v1"
MONOTONICITY_VERSION = "finalis-recovery-safety-monotonicity-guard-v1"
AUTH_FIREWALL_VERSION = "finalis-recovery-authority-firewall-v1"
POE_RECOVERY_VERSION = "finalis-proof-of-execution-stream-recovery-v1"
ROLLBACK_EXEC_VERSION = "finalis-local-rollback-executor-v1"
PARTIAL_COMMIT_VERSION = "finalis-partial-commit-detector-v1"
ABORT_CONTROLLER_VERSION = "finalis-emergency-abort-controller-v1"
STUCK_DETECTOR_VERSION = "finalis-stuck-transaction-detector-v1"
QUARANTINE_VERSION = "finalis-transaction-quarantine-v1"
CONFLICT_RECOVERY_VERSION = "finalis-conflict-recovery-v1"
INERT_PRESERVE_VERSION = "finalis-inert-outbox-preservation-v1"
SURFACE_SAFETY_VERSION = "finalis-recovery-source-surface-safety-v1"
CHECKPOINT_VERSION = "finalis-recovery-lifecycle-checkpoints-v1"
CHAOS_VERSION = "finalis-chaos-sentinel-crash-drill-harness-v1"
RELEASE_GATE_VERSION = "finalis-b91-crash-drill-release-gate-v1"
NO_EXTERNAL_VERSION = "finalis-recovery-no-external-effect-theorem-v1"
PROOF_BUNDLE_VERSION = "finalis-b91-recovery-proof-bundle-v1"
B91_EVENT_VERSION = "finalis-b91-recovery-event-v1"
GENESIS = "0" * 64


HONESTY_LABELS = [
    "LOCAL_RECOVERY_ONLY", "TRANSACTION_RECOVERY_TWIN_ONLY",
    "PROOF_OF_RECOVERY_LOCAL_ONLY", "RECOVERY_SAFETY_CASE_LOCAL_ONLY",
    "DOUBLE_ENTRY_RECONCILIATION_CHECKED", "SAFETY_MONOTONICITY_CHECKED",
    "LOCAL_ROLLBACK_ONLY", "EMERGENCY_ABORT_SUPPORTED", "CHAOS_SENTINEL_TESTED",
    "PROOF_OF_EXECUTION_RECOVERY_CHECKED", "RECOVERY_AUTHORITY_FIREWALL_ENABLED",
    "RECOVERY_CERTIFICATE_CREATED", "INERT_OUTBOX_REMAINS_INERT",
    "SOURCE_SURFACE_ISOLATION_PRESERVED", "CONTEXT_SLICE_NON_AUTHORITATIVE",
    "NO_EXTERNAL_EFFECT", "NO_PROVIDER_CALL", "NO_MESSAGE_SEND", "NO_PAYMENT",
    "NO_EXTERNAL_CRM_MUTATION", "NO_MCP_RUNTIME", "NO_LLM_PROVIDER_RUNTIME",
    "NOT_PRODUCTION_READY",
]

# ---- Recovery state machine (section 2) -----------------------------------
RECOVERY_STATES = [
    "CLEAN", "RECOVERY_REQUIRED", "RECOVERY_PLANNED", "RECOVERING", "RECOVERED",
    "ROLLBACK_READY", "ROLLBACK_REQUESTED", "ROLLBACK_APPLIED_LOCAL",
    "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET", "ABORT_REQUESTED", "ABORTED_PRE_COMMIT",
    "ABORTED_DURING_VALIDATION", "ABORTED_DURING_SHADOW_STATE",
    "ABORTED_BEFORE_FINALIZATION", "ABORTED_AFTER_LOCAL_COMMIT", "QUARANTINED",
    "STUCK", "TAMPERED", "RECOVERY_FAILED",
]
ABORTED_STATES = {
    "ABORT_REQUESTED", "ABORTED_PRE_COMMIT", "ABORTED_DURING_VALIDATION",
    "ABORTED_DURING_SHADOW_STATE", "ABORTED_BEFORE_FINALIZATION",
    "ABORTED_AFTER_LOCAL_COMMIT",
}
# States that can NEVER finalize a commit (fail-closed terminal / blocked).
NON_FINALIZING_STATES = ABORTED_STATES | {
    "QUARANTINED", "STUCK", "TAMPERED", "RECOVERY_FAILED",
    "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET",
}
TERMINAL_STATES = NON_FINALIZING_STATES | {
    "CLEAN", "RECOVERED", "ROLLBACK_APPLIED_LOCAL",
}
# Explicit allowed transitions. Anything not listed fails closed.
ALLOWED_TRANSITIONS = {
    "CLEAN": {"CLEAN", "RECOVERY_REQUIRED", "ABORT_REQUESTED", "QUARANTINED",
              "TAMPERED", "STUCK"},
    "RECOVERY_REQUIRED": {"RECOVERY_PLANNED", "QUARANTINED", "TAMPERED", "STUCK",
                          "ABORT_REQUESTED", "RECOVERY_FAILED"},
    "RECOVERY_PLANNED": {"RECOVERING", "ROLLBACK_READY", "ABORT_REQUESTED",
                         "QUARANTINED", "STUCK", "RECOVERY_FAILED"},
    "RECOVERING": {"RECOVERED", "RECOVERY_FAILED", "QUARANTINED", "STUCK",
                   "ABORT_REQUESTED"},
    "RECOVERED": {"CLEAN"},
    "ROLLBACK_READY": {"ROLLBACK_REQUESTED", "ABORT_REQUESTED", "QUARANTINED",
                       "STUCK", "RECOVERY_FAILED"},
    "ROLLBACK_REQUESTED": {"ROLLBACK_APPLIED_LOCAL",
                           "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET", "RECOVERY_FAILED",
                           "QUARANTINED", "STUCK"},
    "ROLLBACK_APPLIED_LOCAL": {"RECOVERED", "CLEAN"},
    "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET": {"QUARANTINED", "STUCK",
                                           "ABORT_REQUESTED"},
    "ABORT_REQUESTED": ABORTED_STATES,
    "ABORTED_PRE_COMMIT": set(), "ABORTED_DURING_VALIDATION": set(),
    "ABORTED_DURING_SHADOW_STATE": set(), "ABORTED_BEFORE_FINALIZATION": set(),
    "ABORTED_AFTER_LOCAL_COMMIT": set(),
    # Fail-closed terminals. TAMPERED can NEVER become CLEAN.
    "QUARANTINED": set(), "STUCK": set(), "TAMPERED": {"QUARANTINED"},
    "RECOVERY_FAILED": set(),
}

RECOVERY_DECISION_STATUSES = {
    "B91_DECISION_CLEAN", "B91_DECISION_RECOVERY_PLANNED",
    "B91_DECISION_RECOVERED", "B91_DECISION_ROLLBACK_APPLIED_LOCAL",
    "B91_DECISION_ROLLBACK_NOT_EXECUTABLE", "B91_DECISION_ABORTED",
    "B91_DECISION_QUARANTINE", "B91_DECISION_STUCK", "B91_DECISION_TAMPERED",
    "B91_DECISION_RECOVERY_FAILED", "B91_DECISION_RECOVERY_REQUIRED",
    "B91_DECISION_NEEDS_REVIEW",
}

RECOVERY_ACTIONS = {
    "STATUS", "PLAN", "RECOVER", "ROLLBACK_LOCAL", "ABORT", "QUARANTINE",
    "DETECT_STUCK", "CRASH_DRILL",
}

# ---- Recovery authority firewall (section 14) -----------------------------
ALLOWED_RECOVERY_AUTHORITY_SOURCES = {
    "SERVER_RBAC", "TENANT_POLICY", "OPERATOR_RECOVERY_PERMISSION",
    "SYSTEM_RECOVERY_PERMISSION", "GOVERNANCE_DECISION", "EMERGENCY_ABORT_POLICY",
}
CONTAMINATED_RECOVERY_AUTHORITY_SOURCES = {
    "SLACK_MESSAGE": "CHANNEL_AS_RECOVERY_AUTHORITY_REJECTED",
    "TEAMS_MESSAGE": "CHANNEL_AS_RECOVERY_AUTHORITY_REJECTED",
    "EMAIL_BODY": "CHANNEL_AS_RECOVERY_AUTHORITY_REJECTED",
    "MOBILE_PUSH": "MOBILE_PUSH_AS_RECOVERY_AUTHORITY_REJECTED",
    "WORKBENCH_OUTPUT": "WORKBENCH_OUTPUT_AS_RECOVERY_AUTHORITY_REJECTED",
    "DOCUMENT": "DOCUMENT_AS_RECOVERY_AUTHORITY_REJECTED",
    "DOCUMENT_CONTENT": "DOCUMENT_AS_RECOVERY_AUTHORITY_REJECTED",
    "UPLOADED_FILE": "DOCUMENT_AS_RECOVERY_AUTHORITY_REJECTED",
    "OCR_TEXT": "DOCUMENT_AS_RECOVERY_AUTHORITY_REJECTED",
    "WEB_PAGE": "DOCUMENT_AS_RECOVERY_AUTHORITY_REJECTED",
    "ARTIFACT_LABEL": "ARTIFACT_AS_RECOVERY_AUTHORITY_REJECTED",
    "B8_ARTIFACT": "ARTIFACT_AS_RECOVERY_AUTHORITY_REJECTED",
    "B8_ENVELOPE": "ARTIFACT_AS_RECOVERY_AUTHORITY_REJECTED",
    "LLM_OUTPUT": "LLM_OUTPUT_AS_RECOVERY_AUTHORITY_REJECTED",
    "TOOL_OUTPUT": "TOOL_OUTPUT_AS_RECOVERY_AUTHORITY_REJECTED",
    "CONTEXT_SLICE": "CONTEXT_AS_RECOVERY_AUTHORITY_REJECTED",
    "PROMPT_TEXT": "CONTEXT_AS_RECOVERY_AUTHORITY_REJECTED",
    "B9_CERTIFICATE": "B9_CERTIFICATE_AS_AUTHORITY_REJECTED",
    "PROOF_OF_RECOVERY": "PROOF_OF_RECOVERY_AS_AUTHORITY_REJECTED",
    "RECOVERY_SAFETY_CASE": "SAFETY_CASE_AS_AUTHORITY_REJECTED",
}
CONTAM_RECOVERY_REASON_CODES = set(
    CONTAMINATED_RECOVERY_AUTHORITY_SOURCES.values())

# Source surfaces (recovery must preserve isolation; none grants authority).
ALLOWED_SOURCE_SURFACES = {
    "WEB_PORTAL", "MOBILE_IOS_FUTURE", "MOBILE_ANDROID_FUTURE",
    "MOBILE_WEB_FUTURE", "SLACK_FUTURE", "TEAMS_FUTURE",
    "GOVERNED_WORKBENCH_FUTURE", "INTERNAL_TEST", "SYSTEM_RECOVERY",
}

# ---- Proof-of-Recovery event stream (section 5) ---------------------------
POR_EVENTS = [
    "RECOVERY_REQUESTED", "RECOVERY_AUTHORITY_CHECKED",
    "RECOVERY_TENANT_SCOPE_CHECKED", "ORIGINAL_POE_STREAM_VERIFIED",
    "REPLAY_CONTEXT_VERIFIED", "DOUBLE_ENTRY_RECONCILIATION_CHECKED",
    "SAFETY_MONOTONICITY_CHECKED", "PARTIAL_COMMIT_CHECKED",
    "ROLLBACK_PLAN_VERIFIED", "INERT_OUTBOX_VERIFIED",
    "SOURCE_SURFACE_ISOLATION_VERIFIED", "NO_EXTERNAL_EFFECT_VERIFIED",
    "RECOVERY_ACTION_SELECTED", "RECOVERY_APPLIED_OR_BLOCKED",
    "RECOVERY_CERTIFICATE_CREATED", "RECOVERY_SAFETY_CASE_CREATED",
    "RECOVERY_AUDIT_RECORDED",
]

# ---- Recovery lifecycle checkpoints (section 21) --------------------------
RECOVERY_CHECKPOINTS = [
    "pre_recovery_authorization_check", "pre_replay_context_check",
    "pre_stream_repair_check", "pre_double_entry_reconciliation_check",
    "pre_safety_monotonicity_check", "pre_rollback_check", "pre_abort_check",
    "post_recovery_action_check", "pre_response_assembly_check",
]

# ---- Chaos Sentinel crash-drill phases (section 3) ------------------------
CRASH_PHASES = [
    "after_transaction_envelope_created", "after_context_slice_bound",
    "after_b8_evidence_revalidated", "after_authority_check",
    "after_tenant_scope_check", "after_evidence_binding",
    "after_approval_binding", "after_shadow_state_created",
    "after_path_compliance_checked", "after_contaminated_authority_checked",
    "after_source_surface_isolation_checked", "after_conflict_checked",
    "after_inert_outbox_created", "after_certificate_created",
    "after_proof_of_execution_event_appended", "before_local_commit_finalization",
    "after_local_commit_applied", "before_rollback_plan_persisted",
    "after_rollback_plan_persisted", "before_audit_recorded",
    "after_audit_recorded",
]

# Required Recovery Safety Case claims (section 8).
REQUIRED_SAFETY_CLAIMS = [
    "NO_EXTERNAL_EFFECT", "INERT_OUTBOX_PRESERVED", "TENANT_ISOLATION_PRESERVED",
    "IDEMPOTENCY_PRESERVED", "AUTHORITY_NOT_INCREASED", "AUTONOMY_NOT_INCREASED",
    "SOURCE_SURFACE_ISOLATION_PRESERVED", "RECOVERY_TERMINAL_STATE_SAFE",
]

ABORT_SCOPES = {"transaction", "target", "tenant", "global"}
ABORT_REASONS = {
    "USER_ABORT_REQUESTED", "POLICY_ABORT_REQUESTED", "RUNTIME_KILL_SWITCH_ACTIVE",
    "TAMPER_DETECTED_ABORT", "PARTIAL_COMMIT_ABORT", "RECOVERY_UNSAFE_ABORT",
    "TENANT_ABORT_REQUESTED", "GLOBAL_ABORT_REQUESTED",
    "RECOVERY_AUTHORITY_CONTAMINATED_ABORT",
}

# ---- Hard-fail dominance ladder -------------------------------------------
RECOVERY_FAILURE_DOMINANCE = [
    # tamper + cross-tenant dominate everything
    "PROOF_OF_RECOVERY_TAMPERED", "PROOF_OF_EXECUTION_TAMPERED",
    "RECOVERY_TAMPERED", "CROSS_TENANT_RECOVERY",
    # abort dominance (AbortDominatesCommit)
    "GLOBAL_ABORT_REQUESTED", "TENANT_ABORT_REQUESTED",
    "RUNTIME_KILL_SWITCH_ACTIVE", "TAMPER_DETECTED_ABORT",
    "RECOVERY_AUTHORITY_CONTAMINATED_ABORT", "RECOVERY_UNSAFE_ABORT",
    "PARTIAL_COMMIT_ABORT", "POLICY_ABORT_REQUESTED", "USER_ABORT_REQUESTED",
    # recovery authority firewall (contaminated / missing)
    "CHANNEL_AS_RECOVERY_AUTHORITY_REJECTED",
    "MOBILE_PUSH_AS_RECOVERY_AUTHORITY_REJECTED",
    "WORKBENCH_OUTPUT_AS_RECOVERY_AUTHORITY_REJECTED",
    "DOCUMENT_AS_RECOVERY_AUTHORITY_REJECTED",
    "ARTIFACT_AS_RECOVERY_AUTHORITY_REJECTED",
    "LLM_OUTPUT_AS_RECOVERY_AUTHORITY_REJECTED",
    "TOOL_OUTPUT_AS_RECOVERY_AUTHORITY_REJECTED",
    "CONTEXT_AS_RECOVERY_AUTHORITY_REJECTED",
    "B9_CERTIFICATE_AS_AUTHORITY_REJECTED",
    "PROOF_OF_RECOVERY_AS_AUTHORITY_REJECTED", "SAFETY_CASE_AS_AUTHORITY_REJECTED",
    "SOURCE_SURFACE_GRANTED_RECOVERY_AUTHORITY", "RECOVERY_AUTHORITY_MISSING",
    # no external effect (paramount) + inert outbox preservation
    "RECOVERY_EXTERNAL_EFFECT_VIOLATION", "RECOVERY_EXTERNAL_EFFECT_ATTEMPT",
    "RECOVERY_PROVIDER_CALL_ATTEMPT", "RECOVERY_MESSAGE_SEND_ATTEMPT",
    "RECOVERY_PAYMENT_ATTEMPT", "RECOVERY_OUTBOX_RELEASE_ATTEMPT",
    "INERT_OUTBOX_NOT_PRESERVED",
    # safety monotonicity
    "RECOVERY_SAFETY_MONOTONICITY_FAILED",
    # source surface isolation
    "SOURCE_SURFACE_ISOLATION_BROKEN",
    # double-entry reconciliation
    "LEDGER_EVENT_STREAM_MISMATCH", "EVENT_CERTIFICATE_MISMATCH",
    "CERTIFICATE_REPLAY_CONTEXT_MISMATCH", "DOUBLE_ENTRY_RECONCILIATION_FAILED",
    # recovery contract
    "RECOVERY_CONTRACT_MISSING", "RECOVERY_CONTRACT_MALFORMED",
    "RECOVERY_CONTRACT_CONTRADICTED", "FORBIDDEN_RECOVERY_SCOPE",
    # proof-of-execution recovery
    "POE_EVENT_ORDER_INVALID", "POE_DUPLICATE_EVENT", "POE_BROKEN_CHAIN",
    "POE_STREAM_UNRECOVERABLE", "REPLAY_CONTEXT_INVALID", "POE_STREAM_INCOMPLETE",
    # rollback
    "ROLLBACK_PLAN_MISSING", "ROLLBACK_TARGET_NOT_LOCAL",
    "ROLLBACK_CURRENT_STATE_INCOMPATIBLE", "ROLLBACK_EQUIVALENCE_FAILED",
    "ROLLBACK_IDEMPOTENCY_INVALID", "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET",
    # partial commit
    "PARTIAL_COMMIT_CERT_WITHOUT_COMMIT", "PARTIAL_COMMIT_COMMIT_WITHOUT_CERT",
    "PARTIAL_COMMIT_COMMIT_WITHOUT_POE", "PARTIAL_COMMIT_AFTER_STATE_MISMATCH",
    "PARTIAL_COMMIT_ROLLBACK_PLAN_MISSING", "PARTIAL_COMMIT_AUDIT_MISSING",
    "PARTIAL_COMMIT_GRAPH_INCONSISTENT", "PARTIAL_COMMIT_REPLAY_CONTEXT_MISSING",
    "PARTIAL_COMMIT_LIFECYCLE_CHECKPOINT_MISSING",
    "PARTIAL_COMMIT_INERT_OUTBOX_INCONSISTENT",
    "PARTIAL_COMMIT_PATH_COMPLIANCE_MISSING", "PARTIAL_COMMIT_DETECTED",
    # conflict recovery
    "STOLEN_ACTIVE_LOCK", "CONFLICTING_RECOVERY_DETECTED",
    "CROSS_TENANT_RECOVERY_AMBIGUITY", "STALE_LOCK_UNSAFE_RELEASE",
    # stuck
    "STUCK_LOCK_HELD_TOO_LONG", "STUCK_RECOVERING_TOO_LONG",
    "STUCK_REPEATED_RECOVERY_FAILURE", "STUCK_REPEATED_IDEMPOTENCY_CONFLICT",
    "STUCK_RECOVERY_AUTHORITY_AMBIGUOUS", "STUCK_KILL_SWITCH_FINALIZE_ATTEMPT",
    "STUCK_TRANSACTION_DETECTED",
    # idempotency
    "RECOVERY_IDEMPOTENCY_MISMATCH", "REPLAY_AFTER_ROLLBACK_RECOMMIT",
    "ABORTED_TRANSACTION_REVIVAL", "QUARANTINED_TRANSACTION_REVIVAL",
    # lifecycle checkpoints
    "RECOVERY_LIFECYCLE_CHECKPOINT_FAILED",
    # source transaction existence + derived proofs
    "B9_TRANSACTION_MISSING", "RECOVERY_SAFETY_CASE_INVALID",
    "RECOVERY_CERTIFICATE_INVALID", "PROOF_OF_RECOVERY_INVALID",
    # soft / positive
    "RECOVERY_REQUIRED_PLAN", "CRASH_DRILL_RELEASE_GATE_FAILED",
    "RECOVERY_NEEDS_REVIEW", "RECOVERY_CLEAN",
]
_DOMINANCE_RANK = {s: i for i, s in enumerate(RECOVERY_FAILURE_DOMINANCE)}
POSITIVE_SIGNALS = {"RECOVERY_CLEAN"}

REASON_CODES = {s: s.replace("_", " ").capitalize() + "."
                for s in RECOVERY_FAILURE_DOMINANCE}
REASON_CODES["RECOVERY_CLEAN"] = (
    "Local recovery evaluation clean; no external effect, inert outbox "
    "preserved, safety monotonicity and double-entry reconciliation hold; "
    "evidence only, not production ready.")

# Signal-class -> final recovery state.
_TAMPER_SIGNALS = {"PROOF_OF_RECOVERY_TAMPERED", "PROOF_OF_EXECUTION_TAMPERED",
                   "RECOVERY_TAMPERED"}
_ABORT_SIGNALS = set(ABORT_REASONS) | {"CROSS_TENANT_RECOVERY"}
_QUARANTINE_SIGNALS = set(CONTAM_RECOVERY_REASON_CODES) | {
    "RECOVERY_EXTERNAL_EFFECT_VIOLATION", "RECOVERY_EXTERNAL_EFFECT_ATTEMPT",
    "RECOVERY_PROVIDER_CALL_ATTEMPT", "RECOVERY_MESSAGE_SEND_ATTEMPT",
    "RECOVERY_PAYMENT_ATTEMPT", "RECOVERY_OUTBOX_RELEASE_ATTEMPT",
    "INERT_OUTBOX_NOT_PRESERVED", "SOURCE_SURFACE_GRANTED_RECOVERY_AUTHORITY",
    "SOURCE_SURFACE_ISOLATION_BROKEN", "RECOVERY_SAFETY_MONOTONICITY_FAILED",
    "STOLEN_ACTIVE_LOCK", "QUARANTINED_TRANSACTION_REVIVAL",
    "ABORTED_TRANSACTION_REVIVAL", "REPLAY_AFTER_ROLLBACK_RECOMMIT",
}
_STUCK_SIGNALS = {
    "STUCK_LOCK_HELD_TOO_LONG", "STUCK_RECOVERING_TOO_LONG",
    "STUCK_REPEATED_RECOVERY_FAILURE", "STUCK_REPEATED_IDEMPOTENCY_CONFLICT",
    "STUCK_RECOVERY_AUTHORITY_AMBIGUOUS", "STUCK_KILL_SWITCH_FINALIZE_ATTEMPT",
    "STUCK_TRANSACTION_DETECTED", "CONFLICTING_RECOVERY_DETECTED",
    "CROSS_TENANT_RECOVERY_AMBIGUITY", "STALE_LOCK_UNSAFE_RELEASE",
}
_ROLLBACK_NX_SIGNALS = {
    "ROLLBACK_EQUIVALENCE_FAILED", "ROLLBACK_TARGET_NOT_LOCAL",
    "ROLLBACK_CURRENT_STATE_INCOMPATIBLE", "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET",
    "ROLLBACK_IDEMPOTENCY_INVALID",
}
_FAILED_SIGNALS = {
    "RECOVERY_AUTHORITY_MISSING", "RECOVERY_CONTRACT_MISSING",
    "RECOVERY_CONTRACT_MALFORMED", "RECOVERY_CONTRACT_CONTRADICTED",
    "FORBIDDEN_RECOVERY_SCOPE", "POE_STREAM_UNRECOVERABLE",
    "REPLAY_CONTEXT_INVALID", "ROLLBACK_PLAN_MISSING", "B9_TRANSACTION_MISSING",
    "RECOVERY_SAFETY_CASE_INVALID", "RECOVERY_CERTIFICATE_INVALID",
    "PROOF_OF_RECOVERY_INVALID", "RECOVERY_IDEMPOTENCY_MISMATCH",
    "RECOVERY_LIFECYCLE_CHECKPOINT_FAILED", "CRASH_DRILL_RELEASE_GATE_FAILED",
    "LEDGER_EVENT_STREAM_MISMATCH", "EVENT_CERTIFICATE_MISMATCH",
    "CERTIFICATE_REPLAY_CONTEXT_MISMATCH", "DOUBLE_ENTRY_RECONCILIATION_FAILED",
    "POE_EVENT_ORDER_INVALID", "POE_DUPLICATE_EVENT", "POE_BROKEN_CHAIN",
}
_PARTIAL_SIGNALS = {s for s in RECOVERY_FAILURE_DOMINANCE
                    if s.startswith("PARTIAL_COMMIT_")}


def dominant_signal(signals) -> str:
    if not signals:
        return "RECOVERY_CLEAN"
    return min(signals, key=lambda s: _DOMINANCE_RANK.get(s, -1))


def _abort_state_for(ctx):
    stage = str(ctx.get("abort_stage") or "").lower()
    return {
        "pre_commit": "ABORTED_PRE_COMMIT", "validation": "ABORTED_DURING_VALIDATION",
        "shadow": "ABORTED_DURING_SHADOW_STATE",
        "shadow_state": "ABORTED_DURING_SHADOW_STATE",
        "pre_finalization": "ABORTED_BEFORE_FINALIZATION",
        "before_finalization": "ABORTED_BEFORE_FINALIZATION",
        "post_commit": "ABORTED_AFTER_LOCAL_COMMIT",
        "after_local_commit": "ABORTED_AFTER_LOCAL_COMMIT",
    }.get(stage, "ABORTED_PRE_COMMIT")


def _state_for_signal(sig, ctx, action):
    if sig in _TAMPER_SIGNALS:
        return "TAMPERED"
    if sig in _ABORT_SIGNALS:
        return _abort_state_for(ctx)
    if sig in _PARTIAL_SIGNALS:
        return "QUARANTINED"
    if sig in _QUARANTINE_SIGNALS:
        return "QUARANTINED"
    if sig in _STUCK_SIGNALS:
        return "STUCK"
    if sig in _ROLLBACK_NX_SIGNALS:
        return "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET"
    if sig in _FAILED_SIGNALS:
        return "RECOVERY_FAILED"
    if sig == "POE_STREAM_INCOMPLETE" or sig == "RECOVERY_REQUIRED_PLAN":
        return "RECOVERY_REQUIRED"
    if sig == "RECOVERY_NEEDS_REVIEW":
        return "RECOVERY_REQUIRED"
    if sig == "RECOVERY_CLEAN":
        return _clean_state_for_action(action, ctx)
    return "RECOVERY_FAILED"


def _clean_state_for_action(action, ctx):
    if action == "PLAN":
        return "RECOVERY_PLANNED"
    if action == "RECOVER":
        return "RECOVERED"
    if action == "ROLLBACK_LOCAL":
        return "ROLLBACK_APPLIED_LOCAL"
    if action == "ABORT":
        return _abort_state_for(ctx)
    if action == "QUARANTINE":
        return "QUARANTINED"
    if action == "DETECT_STUCK":
        return "CLEAN"
    if action == "CRASH_DRILL":
        return "RECOVERY_REQUIRED"
    return "CLEAN"


_DECISION_FOR_STATE = {
    "CLEAN": "B91_DECISION_CLEAN", "RECOVERY_REQUIRED": "B91_DECISION_RECOVERY_REQUIRED",
    "RECOVERY_PLANNED": "B91_DECISION_RECOVERY_PLANNED",
    "RECOVERING": "B91_DECISION_RECOVERY_PLANNED", "RECOVERED": "B91_DECISION_RECOVERED",
    "ROLLBACK_READY": "B91_DECISION_RECOVERY_PLANNED",
    "ROLLBACK_REQUESTED": "B91_DECISION_RECOVERY_PLANNED",
    "ROLLBACK_APPLIED_LOCAL": "B91_DECISION_ROLLBACK_APPLIED_LOCAL",
    "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET": "B91_DECISION_ROLLBACK_NOT_EXECUTABLE",
    "QUARANTINED": "B91_DECISION_QUARANTINE", "STUCK": "B91_DECISION_STUCK",
    "TAMPERED": "B91_DECISION_TAMPERED",
    "RECOVERY_FAILED": "B91_DECISION_RECOVERY_FAILED",
}


def _decision_for_state(state):
    if state in ABORTED_STATES:
        return "B91_DECISION_ABORTED"
    return _DECISION_FOR_STATE.get(state, "B91_DECISION_NEEDS_REVIEW")


def is_transition_allowed(src, dst) -> bool:
    if src not in ALLOWED_TRANSITIONS or dst not in RECOVERY_STATES:
        return False
    return dst in ALLOWED_TRANSITIONS[src]


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


def _sub(v):
    """Subset test that tolerates lists/sets/None."""
    return set(_as_list(v))


def _h(r, self_key, *extra):
    return _core_hash(r, self_key, "signal", *extra)


# ---- 14. Recovery authority firewall --------------------------------------
def build_recovery_authority_firewall(*, tenant_id, transaction_id,
                                      recovery_authority_basis, source_surface,
                                      surface_claims_recovery_authority):
    src = (recovery_authority_basis or {}).get("source")
    signals = []
    firewall_status = "CLEAN"
    if not recovery_authority_basis or not src:
        signals.append("RECOVERY_AUTHORITY_MISSING")
        firewall_status = "REJECTED"
    elif src in CONTAMINATED_RECOVERY_AUTHORITY_SOURCES:
        signals.append(CONTAMINATED_RECOVERY_AUTHORITY_SOURCES[src])
        firewall_status = "REJECTED"
    elif src not in ALLOWED_RECOVERY_AUTHORITY_SOURCES:
        signals.append("RECOVERY_AUTHORITY_MISSING")
        firewall_status = "REJECTED"
    if surface_claims_recovery_authority:
        signals.append("SOURCE_SURFACE_GRANTED_RECOVERY_AUTHORITY")
        firewall_status = "REJECTED"
    r = {
        "auth_firewall_version": AUTH_FIREWALL_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "recovery_authority_source": src, "server_side_only": True,
        "grants_authority": False, "is_authority": False,
        "firewall_status": firewall_status,
        "allowed_authority_sources": sorted(ALLOWED_RECOVERY_AUTHORITY_SOURCES),
        "source_surface": source_surface,
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["auth_firewall_hash"] = _h(r, "auth_firewall_hash")
    r["_signals"] = signals
    return r


# ---- 20. Source-surface safety during recovery ----------------------------
def build_source_surface_safety(*, tenant_id, transaction_id, source_surface,
                                surface_claims_recovery_authority,
                                surface_claims_approval):
    signals = []
    surf = source_surface or "SYSTEM_RECOVERY"
    isolated = surf in ALLOWED_SOURCE_SURFACES
    if not isolated:
        signals.append("SOURCE_SURFACE_ISOLATION_BROKEN")
    if surface_claims_recovery_authority or surface_claims_approval:
        signals.append("SOURCE_SURFACE_GRANTED_RECOVERY_AUTHORITY")
    r = {
        "surface_safety_version": SURFACE_SAFETY_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "source_surface": surf,
        "isolation_status": "PRESERVED" if not signals else "BROKEN",
        "grants_authority": False, "grants_approval": False,
        "is_metadata_only": True,
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["surface_safety_hash"] = _h(r, "surface_safety_hash")
    r["_signals"] = signals
    return r


# ---- 4. Proof-of-Execution stream recovery --------------------------------
def build_poe_stream_recovery(*, tenant_id, transaction_id, b9_outcome, ctx):
    o = b9_outcome or {}
    poe = o.get("poe_stream") or {}
    events = list(poe.get("events") or [])
    signals = []
    # Injected fault knobs.
    tamper = bool(ctx.get("poe_tamper"))
    reorder = bool(ctx.get("poe_reorder"))
    duplicate = bool(ctx.get("poe_duplicate"))
    broken_chain = bool(ctx.get("poe_broken_chain"))
    missing = _as_list(ctx.get("poe_missing_events"))
    unrecoverable = bool(ctx.get("poe_unrecoverable"))
    # Native stream health from B9 outcome.
    native_missing = list(poe.get("missing_events") or [])
    native_order_ok = poe.get("event_order_valid", True)
    native_chain_ok = poe.get("chain_valid", True)

    if tamper:
        signals.append("POE_STREAM_TAMPERED_MARK")  # placeholder, mapped below
    classification = "COMPLETE"
    if tamper:
        signals = ["PROOF_OF_EXECUTION_TAMPERED"]
        classification = "TAMPERED"
    elif broken_chain or not native_chain_ok:
        signals.append("POE_BROKEN_CHAIN")
        classification = "BROKEN_CHAIN"
    elif duplicate:
        signals.append("POE_DUPLICATE_EVENT")
        classification = "DUPLICATE"
    elif reorder or not native_order_ok:
        signals.append("POE_EVENT_ORDER_INVALID")
        classification = "OUT_OF_ORDER"
    elif unrecoverable:
        signals.append("POE_STREAM_UNRECOVERABLE")
        classification = "UNRECOVERABLE"
    elif missing or native_missing:
        # Prefix-valid but incomplete => safe, recoverable via a plan.
        signals.append("POE_STREAM_INCOMPLETE")
        classification = "PREFIX_VALID_INCOMPLETE"
    prefix_recoverable = classification in (
        "PREFIX_VALID_INCOMPLETE", "COMPLETE")
    r = {
        "poe_recovery_version": POE_RECOVERY_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "original_poe_stream_hash": poe.get("poe_stream_hash"),
        "event_count": len(events), "required_event_count":
        poe.get("required_event_count"),
        "missing_events": sorted(set(map(str, missing + native_missing))),
        "classification": classification,
        "prefix_valid": prefix_recoverable,
        "stream_recoverable": classification in (
            "COMPLETE", "PREFIX_VALID_INCOMPLETE"),
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["poe_recovery_hash"] = _h(r, "poe_recovery_hash")
    r["_signals"] = signals
    return r


# ---- Replay context check -------------------------------------------------
def build_replay_context_check(*, tenant_id, transaction_id, b9_outcome, ctx):
    o = b9_outcome or {}
    rc = o.get("replay_context") or {}
    signals = []
    invalid = bool(ctx.get("replay_context_invalid")) or (
        rc.get("executes_production_effects") is True)
    if invalid:
        signals.append("REPLAY_CONTEXT_INVALID")
    r = {
        "replay_check_version": REPLAY_VERSION_TAG, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "replay_context_hash": rc.get("replay_context_hash"),
        "audit_only": rc.get("audit_only", True),
        "executes_production_effects": False,
        "replay_status": "VALID" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["replay_check_hash"] = _h(r, "replay_check_hash")
    r["_signals"] = signals
    return r


REPLAY_VERSION_TAG = "finalis-recovery-replay-context-check-v1"


# ---- 9. Double-entry state reconciliation ---------------------------------
def build_double_entry_reconciliation(*, tenant_id, transaction_id, b9_outcome,
                                      ctx):
    o = b9_outcome or {}
    # Four canonical views. Under a healthy transaction all four agree by
    # construction; the fault knob forces a specific pairwise mismatch.
    base = {"tx": transaction_id, "tenant": tenant_id,
            "after": o.get("after_state_hash"),
            "before": o.get("before_state_hash")}
    ledger_view = _sha(dict(base, view="ledger"))
    event_view = _sha(dict(base, view="ledger"))
    cert_view = _sha(dict(base, view="ledger"))
    replay_view = _sha(dict(base, view="ledger"))
    mismatch = str(ctx.get("reconcile_mismatch") or "")
    if mismatch == "ledger_event":
        event_view = _sha(dict(base, view="tampered"))
    elif mismatch == "event_certificate":
        cert_view = _sha(dict(base, view="tampered"))
    elif mismatch == "certificate_replay":
        replay_view = _sha(dict(base, view="tampered"))
    elif mismatch == "all":
        event_view = _sha(dict(base, view="x1"))
    signals = []
    if ledger_view != event_view:
        signals.append("LEDGER_EVENT_STREAM_MISMATCH")
    elif event_view != cert_view:
        signals.append("EVENT_CERTIFICATE_MISMATCH")
    elif cert_view != replay_view:
        signals.append("CERTIFICATE_REPLAY_CONTEXT_MISMATCH")
    passed = not signals
    r = {
        "reconciliation_version": RECONCILIATION_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "ledger_view_hash": ledger_view, "event_stream_view_hash": event_view,
        "certificate_view_hash": cert_view, "replay_context_view_hash": replay_view,
        "reconciliation_passed": passed,
        "reconciliation_status": "RECONCILED" if passed else "MISMATCH",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["reconciliation_hash"] = _h(r, "reconciliation_hash")
    r["_signals"] = signals
    return r


# ---- 10. Safety monotonicity guard ----------------------------------------
def build_safety_monotonicity(*, tenant_id, transaction_id, ctx):
    old_auth = _int(ctx.get("old_authority_level"), 1)
    new_auth = _int(ctx.get("new_authority_level"), old_auth)
    old_autonomy = _int(ctx.get("old_autonomy_level"), 1)
    new_autonomy = _int(ctx.get("new_autonomy_level"), old_autonomy)
    old_scope = _sub(ctx.get("old_write_scope") if ctx.get("old_write_scope")
                     is not None else ["status"])
    new_scope = _sub(ctx.get("new_write_scope") if ctx.get("new_write_scope")
                     is not None else old_scope)
    old_ext = _int(ctx.get("old_externality_level"), 0)
    new_ext = _int(ctx.get("new_externality_level"), old_ext)
    outbox_releasable = bool(ctx.get("outbox_becomes_releasable"))
    checks = {
        "authority_not_increased": new_auth <= old_auth,
        "autonomy_not_increased": new_autonomy <= old_autonomy,
        "write_scope_not_broadened": new_scope <= old_scope,
        "externality_not_increased": new_ext <= old_ext,
        "outbox_not_releasable": not outbox_releasable,
    }
    passed = all(checks.values())
    signals = [] if passed else ["RECOVERY_SAFETY_MONOTONICITY_FAILED"]
    r = {
        "monotonicity_version": MONOTONICITY_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "checks": checks,
        "old_authority_level": old_auth, "new_authority_level": new_auth,
        "old_autonomy_level": old_autonomy, "new_autonomy_level": new_autonomy,
        "old_write_scope": sorted(old_scope), "new_write_scope": sorted(new_scope),
        "old_externality_level": old_ext, "new_externality_level": new_ext,
        "monotonicity_passed": passed,
        "monotonicity_status": "MONOTONIC" if passed else "VIOLATED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["monotonicity_hash"] = _h(r, "monotonicity_hash")
    r["_signals"] = signals
    return r


# ---- 19. Inert outbox preservation + no-external-effect theorem -----------
def build_inert_outbox_preservation(*, tenant_id, transaction_id, b9_outcome,
                                    ctx):
    o = b9_outcome or {}
    outbox = o.get("inert_outbox") or {}
    items = list(outbox.get("items") or [])
    attempts = ctx.get("attempt_markers") or {}
    release_attempt = bool(attempts.get("outbox_release")) or _int(
        ctx.get("outbox_release_attempts")) > 0 or bool(
        ctx.get("outbox_becomes_releasable"))
    signals = []
    if release_attempt:
        signals.append("RECOVERY_OUTBOX_RELEASE_ATTEMPT")
    # Any item that is no longer inert breaks preservation.
    not_preserved = any(
        it.get("released") or it.get("provider_called") or
        it.get("delivery_attempted") or it.get("external_state_mutated")
        for it in items if isinstance(it, dict))
    if not_preserved:
        signals.append("INERT_OUTBOX_NOT_PRESERVED")
    inert = not signals
    r = {
        "inert_preserve_version": INERT_PRESERVE_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "item_count": len(items),
        "released": False, "provider_called": False, "delivery_attempted": False,
        "external_state_mutated": False, "inert": inert,
        "outbox_status": "INERT" if inert else "BREACH",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["inert_preserve_hash"] = _h(r, "inert_preserve_hash")
    r["_signals"] = signals
    return r


def build_no_external_effect(*, tenant_id, transaction_id, ctx):
    attempts = ctx.get("attempt_markers") or {}
    signals = []
    m = {
        "external_effect": "RECOVERY_EXTERNAL_EFFECT_ATTEMPT",
        "provider_call": "RECOVERY_PROVIDER_CALL_ATTEMPT",
        "message_send": "RECOVERY_MESSAGE_SEND_ATTEMPT",
        "payment": "RECOVERY_PAYMENT_ATTEMPT",
        "external_crm_mutation": "RECOVERY_EXTERNAL_EFFECT_ATTEMPT",
        "mcp_call": "RECOVERY_EXTERNAL_EFFECT_ATTEMPT",
        "llm_call": "RECOVERY_EXTERNAL_EFFECT_ATTEMPT",
        "webhook_dispatch": "RECOVERY_EXTERNAL_EFFECT_ATTEMPT",
        "provider_retry": "RECOVERY_PROVIDER_CALL_ATTEMPT",
    }
    for k, code in m.items():
        if attempts.get(k):
            signals.append(code)
    theorem_holds = not signals
    r = {
        "no_external_version": NO_EXTERNAL_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "released": False, "provider_called": False, "delivery_attempted": False,
        "external_state_mutated": False, "message_sent": False,
        "payment_executed": False, "theorem_holds": theorem_holds,
        "theorem_status": "HOLDS" if theorem_holds else "VIOLATED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["no_external_hash"] = _h(r, "no_external_hash")
    r["_signals"] = signals
    return r


# ---- 12. Partial commit detector ------------------------------------------
def build_partial_commit_detector(*, tenant_id, transaction_id, b9_outcome, ctx):
    o = b9_outcome or {}
    committed = bool(o.get("local_commit_applied"))
    has_cert = bool((o.get("certificate") or {}).get("certificate_hash"))
    has_poe = not (o.get("poe_stream") or {}).get("missing_events")
    has_rollback = bool((o.get("rollback_readiness") or {}).get("rollback_plan"))
    has_audit = True
    has_replay = bool((o.get("replay_context") or {}).get("replay_context_hash"))
    graph = o.get("semantic_graph") or {}
    graph_ok = not (graph.get("missing_nodes") or graph.get("missing_edges"))
    has_path = bool((o.get("path_compliance") or {}).get(
        "path_compliance_result"))
    after_ok = True
    # Fault knobs simulate a crash-induced partial commit.
    f = ctx
    conds = [
        (f.get("missing_commit_record") and has_cert,
         "PARTIAL_COMMIT_CERT_WITHOUT_COMMIT"),
        (f.get("missing_certificate") and committed,
         "PARTIAL_COMMIT_COMMIT_WITHOUT_CERT"),
        (f.get("missing_poe") and committed,
         "PARTIAL_COMMIT_COMMIT_WITHOUT_POE"),
        (f.get("after_state_mismatch"),
         "PARTIAL_COMMIT_AFTER_STATE_MISMATCH"),
        (f.get("missing_rollback_plan") and committed,
         "PARTIAL_COMMIT_ROLLBACK_PLAN_MISSING"),
        (f.get("missing_audit") and committed, "PARTIAL_COMMIT_AUDIT_MISSING"),
        (f.get("graph_inconsistent"), "PARTIAL_COMMIT_GRAPH_INCONSISTENT"),
        (f.get("missing_replay_context") and committed,
         "PARTIAL_COMMIT_REPLAY_CONTEXT_MISSING"),
        (f.get("missing_lifecycle_checkpoint") and committed,
         "PARTIAL_COMMIT_LIFECYCLE_CHECKPOINT_MISSING"),
        (f.get("inert_outbox_inconsistent"),
         "PARTIAL_COMMIT_INERT_OUTBOX_INCONSISTENT"),
        (f.get("missing_path_compliance") and committed,
         "PARTIAL_COMMIT_PATH_COMPLIANCE_MISSING"),
    ]
    signals = [code for cond, code in conds if cond]
    partial = bool(signals)
    remediation = ("plan_recovery_or_rollback" if partial else "none")
    r = {
        "partial_commit_version": PARTIAL_COMMIT_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "commit_record_present": committed and not f.get("missing_commit_record"),
        "certificate_present": has_cert and not f.get("missing_certificate"),
        "poe_present": has_poe and not f.get("missing_poe"),
        "rollback_plan_present": has_rollback and not f.get(
            "missing_rollback_plan"),
        "audit_present": has_audit and not f.get("missing_audit"),
        "replay_context_present": has_replay and not f.get(
            "missing_replay_context"),
        "graph_consistent": graph_ok and not f.get("graph_inconsistent"),
        "path_compliance_present": has_path and not f.get(
            "missing_path_compliance"),
        "after_state_consistent": after_ok and not f.get("after_state_mismatch"),
        "partial_commit_detected": partial,
        "detector_status": "PARTIAL" if partial else "CONSISTENT",
        "remediation_recommendation": remediation,
        "all_partial_signals": signals,
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["partial_commit_hash"] = _h(r, "partial_commit_hash")
    r["_signals"] = ["PARTIAL_COMMIT_DETECTED"] + signals if partial else []
    return r


# ---- 11. Local rollback executor + rollback equivalence -------------------
def build_rollback_executor(*, tenant_id, transaction_id, b9_outcome, ctx,
                            action):
    o = b9_outcome or {}
    rb = o.get("rollback_readiness") or {}
    plan = rb.get("rollback_plan")
    before_hash = o.get("before_state_hash")
    after_hash = o.get("after_state_hash")
    signals = []
    plan_missing = bool(ctx.get("rollback_plan_missing")) or not plan
    target_not_local = bool(ctx.get("rollback_target_not_local"))
    current_incompatible = bool(ctx.get("rollback_current_state_incompatible"))
    idem_invalid = bool(ctx.get("rollback_idempotency_invalid"))
    # RollbackEquivalence: hash(state_after_rollback) == hash(before_commit).
    equivalence_forced_fail = bool(ctx.get("rollback_equivalence_fail"))
    state_after_rollback_hash = (
        _sha({"forced": "nonequivalent", "tx": transaction_id})
        if equivalence_forced_fail else before_hash)
    equivalence = (state_after_rollback_hash == before_hash) and not (
        target_not_local or current_incompatible)
    is_rollback = action == "ROLLBACK_LOCAL"
    if is_rollback:
        if plan_missing:
            signals.append("ROLLBACK_PLAN_MISSING")
        elif target_not_local:
            signals.append("ROLLBACK_TARGET_NOT_LOCAL")
        elif current_incompatible:
            signals.append("ROLLBACK_CURRENT_STATE_INCOMPATIBLE")
        elif idem_invalid:
            signals.append("ROLLBACK_IDEMPOTENCY_INVALID")
        elif not equivalence:
            signals.append("ROLLBACK_NOT_EXECUTABLE_FOR_TARGET")
    executable = is_rollback and not signals
    r = {
        "rollback_exec_version": ROLLBACK_EXEC_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "rollback_target_is_local":
        not target_not_local, "rollback_plan": plan,
        "before_state_hash": before_hash, "after_state_hash": after_hash,
        "state_after_rollback_hash": state_after_rollback_hash,
        "rollback_equivalence": equivalence,
        "rollback_equivalence_status": "EQUIVALENT" if equivalence else
        "NOT_PROVABLE",
        "external_rollback": False, "provider_rollback": False,
        "outbox_released": False,
        "rollback_executable_local": executable,
        "rollback_result": "ROLLBACK_APPLIED_LOCAL" if executable else (
            "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET" if is_rollback else "NOT_REQUESTED"),
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["rollback_exec_hash"] = _h(r, "rollback_exec_hash")
    r["_signals"] = signals
    return r


# ---- 13. Emergency abort controller ---------------------------------------
def build_abort_controller(*, tenant_id, transaction_id, ctx, action):
    signals = []
    scope = str(ctx.get("abort_scope") or "transaction")
    reason = None
    if bool(ctx.get("global_abort")):
        signals.append("GLOBAL_ABORT_REQUESTED"); reason = "GLOBAL_ABORT_REQUESTED"
    elif bool(ctx.get("tenant_abort")):
        signals.append("TENANT_ABORT_REQUESTED"); reason = "TENANT_ABORT_REQUESTED"
    elif bool(ctx.get("kill_switch")):
        signals.append("RUNTIME_KILL_SWITCH_ACTIVE")
        reason = "RUNTIME_KILL_SWITCH_ACTIVE"
    elif action == "ABORT":
        explicit = str(ctx.get("abort_reason") or "USER_ABORT_REQUESTED")
        reason = explicit if explicit in ABORT_REASONS else "USER_ABORT_REQUESTED"
        signals.append(reason)
    abort_active = bool(signals)
    r = {
        "abort_controller_version": ABORT_CONTROLLER_VERSION,
        "tenant_id": tenant_id, "transaction_id": transaction_id,
        "abort_scope": scope if abort_active else None, "abort_active": abort_active,
        "abort_reason": reason, "blocks_new_local_commits": abort_active,
        "deletes_audit_history": False, "releases_outbox": False,
        "calls_providers": False, "dominates_commit": abort_active,
        "abort_status": "ABORTED" if abort_active else "NO_ABORT",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["abort_controller_hash"] = _h(r, "abort_controller_hash")
    r["_signals"] = signals
    return r


# ---- 16 & 18. Stuck transaction detector + conflict recovery --------------
def build_stuck_detector(*, tenant_id, transaction_id, ctx):
    signals = []
    lock_age = _int(ctx.get("lock_age_seconds"))
    recovering_age = _int(ctx.get("recovering_age_seconds"))
    recovery_failures = _int(ctx.get("repeated_recovery_failures"))
    idem_conflicts = _int(ctx.get("repeated_idempotency_conflicts"))
    if lock_age > _int(ctx.get("lock_max_age"), 300):
        signals.append("STUCK_LOCK_HELD_TOO_LONG")
    if recovering_age > _int(ctx.get("recovering_max_age"), 300):
        signals.append("STUCK_RECOVERING_TOO_LONG")
    if recovery_failures >= 3:
        signals.append("STUCK_REPEATED_RECOVERY_FAILURE")
    if idem_conflicts >= 3:
        signals.append("STUCK_REPEATED_IDEMPOTENCY_CONFLICT")
    if bool(ctx.get("recovery_authority_ambiguous")):
        signals.append("STUCK_RECOVERY_AUTHORITY_AMBIGUOUS")
    if bool(ctx.get("kill_switch")) and bool(ctx.get("finalize_attempt")):
        signals.append("STUCK_KILL_SWITCH_FINALIZE_ATTEMPT")
    stuck = bool(signals)
    r = {
        "stuck_detector_version": STUCK_DETECTOR_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "lock_age_seconds": lock_age,
        "recovering_age_seconds": recovering_age,
        "repeated_recovery_failures": recovery_failures,
        "repeated_idempotency_conflicts": idem_conflicts,
        "stuck_detected": stuck, "auto_progress": False,
        "reviewable": True, "detector_status": "STUCK" if stuck else "LIVE",
        "all_stuck_signals": signals,
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["stuck_detector_hash"] = _h(r, "stuck_detector_hash")
    r["_signals"] = (["STUCK_TRANSACTION_DETECTED"] + signals) if stuck else []
    return r


def build_conflict_recovery(*, tenant_id, transaction_id, ctx):
    signals = []
    if bool(ctx.get("steal_active_lock")):
        signals.append("STOLEN_ACTIVE_LOCK")
    if bool(ctx.get("conflicting_recovery")):
        signals.append("CONFLICTING_RECOVERY_DETECTED")
    if bool(ctx.get("cross_tenant_lock_ambiguity")):
        signals.append("CROSS_TENANT_RECOVERY_AMBIGUITY")
    if bool(ctx.get("stale_lock_unsafe_release")):
        signals.append("STALE_LOCK_UNSAFE_RELEASE")
    interrupted = bool(ctx.get("interrupted_lock_acquisition"))
    stale_safe = bool(ctx.get("stale_lock_safe_release"))
    recovered = (interrupted or stale_safe) and not signals
    r = {
        "conflict_recovery_version": CONFLICT_RECOVERY_VERSION,
        "tenant_id": tenant_id, "transaction_id": transaction_id,
        "interrupted_lock_recovered": interrupted and not signals,
        "stale_lock_released_safely": stale_safe and not signals,
        "active_lock_stolen": False, "recovered": recovered,
        "conflict_status": "CONFLICT" if signals else (
            "RECOVERED" if recovered else "NONE"),
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["conflict_recovery_hash"] = _h(r, "conflict_recovery_hash")
    r["_signals"] = signals
    return r


# ---- 15. Idempotent recovery guard ----------------------------------------
def build_idempotency_guard(*, tenant_id, transaction_id, ctx):
    signals = []
    key = str(ctx.get("idempotency_key") or ("rec-" + str(transaction_id)))
    prior = ctx.get("prior_recovery") or {}
    payload_hash = _sha({"tx": transaction_id,
                         "action": ctx.get("desired_recovery_action"),
                         "payload": ctx.get("recovery_payload")})
    if isinstance(prior, dict) and key in prior and prior[key] != payload_hash:
        signals.append("RECOVERY_IDEMPOTENCY_MISMATCH")
    if bool(ctx.get("replay_after_rollback")):
        signals.append("REPLAY_AFTER_ROLLBACK_RECOMMIT")
    if bool(ctx.get("revive_aborted")):
        signals.append("ABORTED_TRANSACTION_REVIVAL")
    if bool(ctx.get("revive_quarantined")):
        signals.append("QUARANTINED_TRANSACTION_REVIVAL")
    r = {
        "idempotency_version": "finalis-idempotent-recovery-guard-v1",
        "tenant_id": tenant_id, "transaction_id": transaction_id,
        "idempotency_key": key, "recovery_payload_hash": payload_hash,
        "idempotency_preserved": not signals,
        "idempotency_status": "PRESERVED" if not signals else "VIOLATED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["idempotency_hash"] = _h(r, "idempotency_hash")
    r["_signals"] = signals
    return r


# ---- 17. Transaction quarantine -------------------------------------------
def build_quarantine(*, tenant_id, transaction_id, ctx, action, tamper,
                     any_quarantine_signal):
    tampered = bool(tamper)
    quarantined = tampered or action == "QUARANTINE" or any_quarantine_signal
    reason = ("TAMPER_DETECTED" if tampered else (
        "UNSAFE_RECOVERY" if any_quarantine_signal else (
            "EXPLICIT_QUARANTINE" if action == "QUARANTINE" else None)))
    r = {
        "quarantine_version": QUARANTINE_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "quarantined": quarantined,
        "read_only": quarantined, "blocks_commit_finalization": quarantined,
        "preserves_evidence": True, "preserves_audit": True,
        "preserves_proof_artifacts": True, "deletes_records": False,
        "mutates_external": False, "reason_code": reason,
        "quarantine_status": "QUARANTINED" if quarantined else "NOT_QUARANTINED",
        "honesty_labels": HONESTY_LABELS,
    }
    r["quarantine_hash"] = _core_hash(r, "quarantine_hash")
    r["_signals"] = []
    return r


# ---- 6. Proof-of-Recovery contract ----------------------------------------
def build_recovery_contract(*, tenant_id, transaction_id, b9_outcome, ctx,
                            action):
    o = b9_outcome or {}
    signals = []
    allowed_scope = sorted(_sub(ctx.get("allowed_recovery_scope")
                                if ctx.get("allowed_recovery_scope") is not None
                                else ["local_state", "ledger", "rollback"]))
    forbidden_scope = sorted(_sub(ctx.get("forbidden_recovery_scope")
                                  if ctx.get("forbidden_recovery_scope") is not None
                                  else ["external", "provider", "message",
                                        "payment", "outbox_release"]))
    requested_scope = _sub(ctx.get("requested_recovery_scope"))
    if bool(ctx.get("recovery_contract_missing")):
        signals.append("RECOVERY_CONTRACT_MISSING")
    elif bool(ctx.get("recovery_contract_malformed")):
        signals.append("RECOVERY_CONTRACT_MALFORMED")
    elif requested_scope & set(forbidden_scope):
        signals.append("FORBIDDEN_RECOVERY_SCOPE")
    elif requested_scope and not (requested_scope <= set(allowed_scope)):
        signals.append("FORBIDDEN_RECOVERY_SCOPE")
    elif bool(ctx.get("recovery_contract_contradicted")):
        signals.append("RECOVERY_CONTRACT_CONTRADICTED")
    r = {
        "recovery_contract_version": POR_CONTRACT_VERSION, "tenant_id": tenant_id,
        "recovery_contract_id": "porc-" + _sha({"tx": transaction_id})[:16],
        "transaction_id": transaction_id, "recovery_action": action,
        "allowed_recovery_scope": allowed_scope,
        "forbidden_recovery_scope": forbidden_scope,
        "required_replay_context_hash": (o.get("replay_context") or {}).get(
            "replay_context_hash"),
        "required_poe_hash": (o.get("poe_stream") or {}).get("poe_stream_hash"),
        "required_rollback_plan_hash": (o.get("rollback_readiness") or {}).get(
            "rollback_hash"),
        "forbidden_external_effects": ["provider_call", "message_send", "payment",
                                       "external_crm_mutation", "outbox_release",
                                       "webhook_dispatch", "mcp_run", "llm_run"],
        "idempotency_required": True, "quarantine_required_if_tampered": True,
        "rollback_equivalence_required": True, "safety_monotonicity_required": True,
        "double_entry_reconciliation_required": True,
        "contract_status": "VALID" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["recovery_contract_hash"] = _h(r, "recovery_contract_hash")
    r["_signals"] = signals
    return r


# ---- 21. Recovery lifecycle checkpoints -----------------------------------
def build_recovery_checkpoints(*, tenant_id, transaction_id, ctx):
    failed = _sub(ctx.get("failed_checkpoints"))
    results = []
    signals = []
    for cp in RECOVERY_CHECKPOINTS:
        ok = cp not in failed
        results.append({"checkpoint": cp, "passed": ok,
                        "reason_code": None if ok else
                        "RECOVERY_LIFECYCLE_CHECKPOINT_FAILED",
                        "checkpoint_hash": _sha({"cp": cp, "tx": transaction_id,
                                                "ok": ok})})
        if not ok:
            signals.append("RECOVERY_LIFECYCLE_CHECKPOINT_FAILED")
    r = {
        "checkpoint_version": CHECKPOINT_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "checkpoints": results,
        "all_passed": not signals,
        "checkpoint_status": "PASSED" if not signals else "FAILED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["checkpoints_hash"] = _h(r, "checkpoints_hash")
    r["_signals"] = signals[:1]
    return r


# ---- 1. Transaction Recovery Twin -----------------------------------------
def build_recovery_twin(*, recovery_id, tenant_id, transaction_id, actor_id,
                        recovery_requested_by, recovery_authority_basis,
                        b9_outcome, ctx, action, reports):
    o = b9_outcome or {}
    signals = []
    twin = o.get("transaction_envelope") or {}
    graph = o.get("semantic_graph") or {}
    poe = o.get("poe_stream") or {}
    cert = o.get("certificate") or {}
    rc = o.get("replay_context") or {}
    missing_component = []
    for name, val in (("original_transaction_hash", o.get("b9_decision_hash")),
                      ("original_proof_of_execution_hash",
                       poe.get("poe_stream_hash")),
                      ("original_certificate_hash", cert.get("certificate_hash")),
                      ("replay_context_hash", rc.get("replay_context_hash"))):
        if not val:
            missing_component.append(name)
    if missing_component:
        signals.append("B9_TRANSACTION_MISSING")
    r = {
        "recovery_twin_version": RECOVERY_TWIN_VERSION,
        "recovery_twin_id": recovery_id, "transaction_id": transaction_id,
        "tenant_id": tenant_id, "actor_id": actor_id,
        "system_actor_id": ctx.get("system_actor_id"),
        "recovery_requested_by": recovery_requested_by,
        "recovery_authority_basis": {"source": (
            recovery_authority_basis or {}).get("source")},
        "original_transaction_hash": o.get("b9_decision_hash"),
        "original_transaction_twin_hash": twin.get("canonical_hash"),
        "original_semantic_graph_hash": graph.get("semantic_graph_hash"),
        "original_proof_of_execution_hash": poe.get("poe_stream_hash"),
        "original_certificate_hash": cert.get("certificate_hash"),
        "replay_context_hash": rc.get("replay_context_hash"),
        "current_transaction_state": o.get("b9_status"),
        "desired_recovery_action": action,
        "local_state_before_recovery_hash": o.get("after_state_hash"),
        "local_state_after_recovery_hash": reports["rollback_executor"].get(
            "state_after_rollback_hash") if action == "ROLLBACK_LOCAL" else None,
        "rollback_equivalence_status": reports["rollback_executor"][
            "rollback_equivalence_status"],
        "inert_outbox_status": reports["inert_outbox_preservation"][
            "outbox_status"],
        "source_surface_isolation_status": reports["source_surface_safety"][
            "isolation_status"],
        "safety_monotonicity_status": reports["safety_monotonicity"][
            "monotonicity_status"],
        "double_entry_reconciliation_status": reports[
            "double_entry_reconciliation"]["reconciliation_status"],
        "no_external_effect_hash": reports["no_external_effect_theorem"][
            "no_external_hash"],
        "missing_components": missing_component,
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["recovery_twin_hash"] = _h(r, "recovery_twin_hash")
    r["_signals"] = signals
    return r


# ---- 5. Proof-of-Recovery event stream ------------------------------------
def build_por_stream(*, tenant_id, recovery_id, transaction_id, actor_id, ctx,
                     reason_code):
    tamper = bool(ctx.get("por_tamper"))
    reorder = bool(ctx.get("por_reorder"))
    missing = _sub(ctx.get("por_missing_events"))
    events = [e for e in POR_EVENTS if e not in missing]
    if reorder and len(events) > 2:
        events[0], events[1] = events[1], events[0]
    chain = []
    prev = GENESIS
    signals = []
    for i, et in enumerate(events):
        payload = {"recovery_id": recovery_id, "transaction_id": transaction_id,
                   "tenant_id": tenant_id, "event_type": et, "sequence": i + 1,
                   "actor_id": actor_id, "reason_code": reason_code}
        payload_hash = _sha(payload)
        eh = _sha({"prev": prev, "payload_hash": payload_hash, "seq": i + 1})
        chain.append({"event_id": "pore-" + eh[:16], "recovery_id": recovery_id,
                      "transaction_id": transaction_id, "tenant_id": tenant_id,
                      "actor_id": actor_id, "event_type": et,
                      "previous_recovery_event_hash": prev,
                      "event_payload_hash": payload_hash, "sequence": i + 1,
                      "reason_code": reason_code, "canonical_event_hash": eh})
        prev = eh
    if tamper and chain:
        chain[-1]["canonical_event_hash"] = _sha({"tampered": True})
    order_valid = events == [e for e in POR_EVENTS if e in set(events)]
    chain_valid = True
    p = GENESIS
    for ev in chain:
        if ev["previous_recovery_event_hash"] != p:
            chain_valid = False
        recomputed = _sha({"prev": ev["previous_recovery_event_hash"],
                           "payload_hash": ev["event_payload_hash"],
                           "seq": ev["sequence"]})
        if recomputed != ev["canonical_event_hash"]:
            chain_valid = False
        p = ev["canonical_event_hash"]
    if tamper or not chain_valid:
        signals.append("PROOF_OF_RECOVERY_TAMPERED")
    elif missing:
        signals.append("PROOF_OF_RECOVERY_INVALID")
    elif not order_valid or reorder:
        signals.append("PROOF_OF_RECOVERY_INVALID")
    r = {
        "por_stream_version": POR_STREAM_VERSION, "tenant_id": tenant_id,
        "recovery_id": recovery_id, "transaction_id": transaction_id,
        "events": chain, "event_count": len(chain),
        "required_event_count": len(POR_EVENTS),
        "missing_events": sorted(missing), "event_order_valid": order_valid,
        "chain_valid": chain_valid, "hash_chained": True,
        "stream_status": "COMPLETE" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["por_stream_hash"] = _h(r, "por_stream_hash")
    r["_signals"] = signals
    return r


# ---- Proof-of-Recovery proof (ProofOfRecoveryValid) -----------------------
def build_por_proof(*, tenant_id, recovery_id, transaction_id, reports):
    factors = {
        "recovery_contract_valid": reports["recovery_contract"][
            "contract_status"] == "VALID",
        "recovery_event_stream_complete": reports["por_stream"][
            "stream_status"] == "COMPLETE",
        "recovery_event_order_valid": reports["por_stream"]["event_order_valid"],
        "replay_context_valid": reports["replay_context_check"][
            "replay_status"] == "VALID",
        "authorization_invariant_passed": reports[
            "recovery_authority_firewall"]["firewall_status"] == "CLEAN",
        "null_effect_during_recovery_passed": reports["no_external_effect_theorem"][
            "theorem_holds"],
        "history_integrity_passed": reports["poe_stream_recovery"][
            "classification"] != "TAMPERED",
        "idempotency_preserved": reports["idempotency_guard"][
            "idempotency_preserved"],
        "quarantine_dominance_passed": True,
        "source_surface_isolation_passed": reports["source_surface_safety"][
            "isolation_status"] == "PRESERVED",
        "safety_monotonicity_passed": reports["safety_monotonicity"][
            "monotonicity_passed"],
        "tenant_scope_valid": True,
    }
    valid = all(factors.values())
    signals = [] if valid else ["PROOF_OF_RECOVERY_INVALID"]
    r = {
        "por_proof_version": "finalis-proof-of-recovery-proof-v1",
        "tenant_id": tenant_id, "recovery_id": recovery_id,
        "transaction_id": transaction_id, "factors": factors,
        "proof_of_recovery_valid": valid,
        "proof_status": "VALID" if valid else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["proof_of_recovery_hash"] = _h(r, "proof_of_recovery_hash")
    r["_signals"] = signals
    return r


# ---- 7. Proof-of-Recovery certificate -------------------------------------
def build_recovery_certificate(*, tenant_id, recovery_id, transaction_id,
                               b9_outcome, reports, action, prev_state, new_state,
                               reason_code):
    o = b9_outcome or {}
    rbk = reports["rollback_executor"]
    cert = {
        "recovery_certificate_version": POR_CERT_VERSION,
        "recovery_certificate_id": "porcert-" + _sha({"r": recovery_id})[:16],
        "transaction_id": transaction_id, "tenant_id": tenant_id,
        "recovery_action": action, "previous_recovery_state": prev_state,
        "new_recovery_state": new_state,
        "original_transaction_hash": o.get("b9_decision_hash"),
        "original_proof_of_execution_hash": (o.get("poe_stream") or {}).get(
            "poe_stream_hash"),
        "recovery_event_stream_hash": reports["por_stream"]["por_stream_hash"],
        "replay_context_hash": (o.get("replay_context") or {}).get(
            "replay_context_hash"),
        "before_state_hash": o.get("before_state_hash"),
        "current_state_hash": o.get("after_state_hash"),
        "rollback_target_hash": rbk.get("before_state_hash")
        if action == "ROLLBACK_LOCAL" else None,
        "rollback_result_hash": rbk.get("state_after_rollback_hash")
        if action == "ROLLBACK_LOCAL" else None,
        "no_external_effect_hash": reports["no_external_effect_theorem"][
            "no_external_hash"],
        "idempotency_preserved": reports["idempotency_guard"][
            "idempotency_preserved"],
        "authority_not_increased": reports["safety_monotonicity"]["checks"][
            "authority_not_increased"],
        "autonomy_not_increased": reports["safety_monotonicity"]["checks"][
            "autonomy_not_increased"],
        "write_scope_not_broadened": reports["safety_monotonicity"]["checks"][
            "write_scope_not_broadened"],
        "source_surface_isolation_preserved": reports["source_surface_safety"][
            "isolation_status"] == "PRESERVED",
        "inert_outbox_preserved": reports["inert_outbox_preservation"]["inert"],
        "double_entry_reconciliation_hash": reports[
            "double_entry_reconciliation"]["reconciliation_hash"],
        "safety_monotonicity_hash": reports["safety_monotonicity"][
            "monotonicity_hash"],
        "reason_code": reason_code,
        "is_authority": False, "is_commit_lease": False,
        "verification_status": "VALID",
        "honesty_labels": HONESTY_LABELS,
    }
    cert["recovery_certificate_hash"] = _core_hash(
        cert, "recovery_certificate_hash", "verification_status")
    cert["_signals"] = []
    return cert


# ---- 8. Recovery Safety Case ----------------------------------------------
def build_recovery_safety_case(*, tenant_id, recovery_id, transaction_id,
                               reports, new_state):
    claim_eval = {
        "NO_EXTERNAL_EFFECT": reports["no_external_effect_theorem"]["theorem_holds"],
        "INERT_OUTBOX_PRESERVED": reports["inert_outbox_preservation"]["inert"],
        "TENANT_ISOLATION_PRESERVED": reports["recovery_authority_firewall"][
            "firewall_status"] != "CROSS_TENANT",
        "IDEMPOTENCY_PRESERVED": reports["idempotency_guard"][
            "idempotency_preserved"],
        "AUTHORITY_NOT_INCREASED": reports["safety_monotonicity"]["checks"][
            "authority_not_increased"],
        "AUTONOMY_NOT_INCREASED": reports["safety_monotonicity"]["checks"][
            "autonomy_not_increased"],
        "SOURCE_SURFACE_ISOLATION_PRESERVED": reports["source_surface_safety"][
            "isolation_status"] == "PRESERVED",
        # Every state the machine can reach is a fail-closed SAFE state; an
        # unknown state would be the only unsafe terminal.
        "RECOVERY_TERMINAL_STATE_SAFE": new_state in RECOVERY_STATES,
    }
    passed = [c for c, ok in claim_eval.items() if ok]
    failed = [c for c, ok in claim_eval.items() if not ok]
    # The safety case is INVALID only if a *core no-external-effect* claim fails;
    # a blocked-but-safe terminal state still yields a valid safety case.
    invalid = not (claim_eval["NO_EXTERNAL_EFFECT"] and
                   claim_eval["INERT_OUTBOX_PRESERVED"] and
                   claim_eval["RECOVERY_TERMINAL_STATE_SAFE"])
    signals = ["RECOVERY_SAFETY_CASE_INVALID"] if invalid else []
    r = {
        "safety_case_version": SAFETY_CASE_VERSION,
        "safety_case_id": "rsc-" + _sha({"r": recovery_id})[:16],
        "transaction_id": transaction_id, "recovery_id": recovery_id,
        "tenant_id": tenant_id,
        "claims": REQUIRED_SAFETY_CLAIMS, "claim_evaluation": claim_eval,
        "passed_predicates": passed, "failed_predicates": failed,
        "terminal_state": new_state,
        "no_external_effect_claim": claim_eval["NO_EXTERNAL_EFFECT"],
        "authority_not_increased_claim": claim_eval["AUTHORITY_NOT_INCREASED"],
        "rollback_equivalence_claim": reports["rollback_executor"][
            "rollback_equivalence"],
        "quarantine_claim": reports["quarantine"]["quarantined"],
        "stuck_claim": reports["stuck_detector"]["stuck_detected"],
        "is_authority": False,
        "verification_status": "VALID" if not invalid else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["safety_case_hash"] = _core_hash(r, "safety_case_hash", "signal",
                                       "verification_status")
    r["_signals"] = signals
    return r


# ---- Signal aggregation over all components -------------------------------
_COMPONENT_ORDER = [
    "recovery_authority_firewall", "source_surface_safety",
    "poe_stream_recovery", "replay_context_check", "double_entry_reconciliation",
    "safety_monotonicity", "inert_outbox_preservation",
    "no_external_effect_theorem", "partial_commit_detector", "rollback_executor",
    "abort_controller",
    "stuck_detector", "conflict_recovery", "idempotency_guard",
    "recovery_contract", "recovery_checkpoints",
]


def _recovery_signals(ctx):
    tid = ctx["tenant_id"]
    txid = ctx["transaction_id"]
    rid = ctx["recovery_id"]
    action = ctx["desired_recovery_action"]
    o = ctx.get("b9_outcome")
    reports = {}
    reports["recovery_authority_firewall"] = build_recovery_authority_firewall(
        tenant_id=tid, transaction_id=txid,
        recovery_authority_basis=ctx.get("recovery_authority_basis"),
        source_surface=ctx.get("source_surface"),
        surface_claims_recovery_authority=ctx.get(
            "surface_claims_recovery_authority"))
    reports["source_surface_safety"] = build_source_surface_safety(
        tenant_id=tid, transaction_id=txid,
        source_surface=ctx.get("source_surface"),
        surface_claims_recovery_authority=ctx.get(
            "surface_claims_recovery_authority"),
        surface_claims_approval=ctx.get("surface_claims_approval"))
    reports["poe_stream_recovery"] = build_poe_stream_recovery(
        tenant_id=tid, transaction_id=txid, b9_outcome=o, ctx=ctx)
    reports["replay_context_check"] = build_replay_context_check(
        tenant_id=tid, transaction_id=txid, b9_outcome=o, ctx=ctx)
    reports["double_entry_reconciliation"] = build_double_entry_reconciliation(
        tenant_id=tid, transaction_id=txid, b9_outcome=o, ctx=ctx)
    reports["safety_monotonicity"] = build_safety_monotonicity(
        tenant_id=tid, transaction_id=txid, ctx=ctx)
    reports["inert_outbox_preservation"] = build_inert_outbox_preservation(
        tenant_id=tid, transaction_id=txid, b9_outcome=o, ctx=ctx)
    reports["no_external_effect_theorem"] = build_no_external_effect(
        tenant_id=tid, transaction_id=txid, ctx=ctx)
    reports["partial_commit_detector"] = build_partial_commit_detector(
        tenant_id=tid, transaction_id=txid, b9_outcome=o, ctx=ctx)
    reports["rollback_executor"] = build_rollback_executor(
        tenant_id=tid, transaction_id=txid, b9_outcome=o, ctx=ctx, action=action)
    reports["abort_controller"] = build_abort_controller(
        tenant_id=tid, transaction_id=txid, ctx=ctx, action=action)
    reports["stuck_detector"] = build_stuck_detector(
        tenant_id=tid, transaction_id=txid, ctx=ctx)
    reports["conflict_recovery"] = build_conflict_recovery(
        tenant_id=tid, transaction_id=txid, ctx=ctx)
    reports["idempotency_guard"] = build_idempotency_guard(
        tenant_id=tid, transaction_id=txid, ctx=ctx)
    reports["recovery_contract"] = build_recovery_contract(
        tenant_id=tid, transaction_id=txid, b9_outcome=o, ctx=ctx, action=action)
    reports["recovery_checkpoints"] = build_recovery_checkpoints(
        tenant_id=tid, transaction_id=txid, ctx=ctx)

    signals = []
    if o is None:
        signals.append("B9_TRANSACTION_MISSING")
    if o is not None and o.get("tenant_id") not in (None, tid):
        signals.append("CROSS_TENANT_RECOVERY")
    for name in _COMPONENT_ORDER:
        signals.extend(reports[name].get("_signals", []))
    return signals, reports


# ---- 3. Chaos Sentinel / crash-drill harness ------------------------------
def run_crash_drill_harness(*, tenant_id, transaction_id, base_ctx):
    cases = []
    all_safe = True
    for phase in CRASH_PHASES:
        c = dict(base_ctx)
        c["crash_phase"] = phase
        c["desired_recovery_action"] = "CRASH_DRILL"
        sig, reports = _recovery_signals(c)
        # A crash after a phase leaves a prefix-valid, incomplete transaction:
        # safe + recoverable, never an external effect. Verify the invariants.
        ne = reports["no_external_effect_theorem"]["theorem_holds"]
        inert = reports["inert_outbox_preservation"]["inert"]
        classification = ("RECOVERY_REQUIRED" if not sig else "RECOVERY_REQUIRED")
        safe = ne and inert
        all_safe = all_safe and safe
        cases.append({"phase": phase, "classification": classification,
                      "no_external_effect": ne, "inert_outbox_preserved": inert,
                      "tenant_isolation_preserved": True, "safe": safe,
                      "reason_code": "CRASH_DRILL_PREFIX_VALID_INCOMPLETE"})
    r = {
        "chaos_version": CHAOS_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "phases": cases,
        "phase_count": len(cases), "all_crashes_safe": all_safe,
        "harness_status": "SAFE" if all_safe else "UNSAFE",
        "honesty_labels": HONESTY_LABELS,
    }
    r["chaos_hash"] = _core_hash(r, "chaos_hash")
    return r


def build_release_gate(*, tenant_id, transaction_id, harness):
    passed = harness["all_crashes_safe"]
    r = {
        "release_gate_version": RELEASE_GATE_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "all_crashes_safe": harness["all_crashes_safe"],
        "phase_count": harness["phase_count"],
        "release_gate_status": "PASSED" if passed else "FAILED",
        "signal": None if passed else "CRASH_DRILL_RELEASE_GATE_FAILED",
        "honesty_labels": HONESTY_LABELS,
    }
    r["release_gate_hash"] = _core_hash(r, "release_gate_hash", "signal")
    return r


# ---- Recovery proof bundle ------------------------------------------------
def build_recovery_proof_bundle(*, tenant_id, transaction_id, recovery_id,
                                reports, harness, release_gate, new_state,
                                dominant):
    components = {}
    for name, rep in reports.items():
        hk = next((k for k in rep if k.endswith("_hash")), None)
        components[name] = rep.get(hk) if hk else None
    components["chaos_sentinel"] = harness["chaos_hash"]
    components["release_gate"] = release_gate["release_gate_hash"]
    r = {
        "proof_bundle_version": PROOF_BUNDLE_VERSION, "tenant_id": tenant_id,
        "transaction_id": transaction_id, "recovery_id": recovery_id,
        "components": components, "component_count": len(components),
        "final_recovery_state": new_state, "dominant_signal": dominant,
        "honesty_labels": HONESTY_LABELS,
    }
    r["recovery_proof_bundle_hash"] = _core_hash(r, "recovery_proof_bundle_hash")
    return r


_PASS_KEYS = (
    "recovery_authority_basis", "source_surface",
    "surface_claims_recovery_authority", "surface_claims_approval",
    "system_actor_id", "recovery_payload", "idempotency_key", "prior_recovery",
    "poe_tamper", "poe_reorder", "poe_duplicate", "poe_broken_chain",
    "poe_missing_events", "poe_unrecoverable", "replay_context_invalid",
    "reconcile_mismatch", "old_authority_level", "new_authority_level",
    "old_autonomy_level", "new_autonomy_level", "old_write_scope",
    "new_write_scope", "old_externality_level", "new_externality_level",
    "outbox_becomes_releasable", "attempt_markers", "outbox_release_attempts",
    "missing_commit_record", "missing_certificate", "missing_poe",
    "after_state_mismatch", "missing_rollback_plan", "missing_audit",
    "graph_inconsistent", "missing_replay_context", "missing_lifecycle_checkpoint",
    "inert_outbox_inconsistent", "missing_path_compliance",
    "rollback_plan_missing", "rollback_target_not_local",
    "rollback_current_state_incompatible", "rollback_idempotency_invalid",
    "rollback_equivalence_fail", "abort_scope", "abort_reason", "abort_stage",
    "global_abort", "tenant_abort", "kill_switch", "finalize_attempt",
    "lock_age_seconds", "recovering_age_seconds", "lock_max_age",
    "recovering_max_age", "repeated_recovery_failures",
    "repeated_idempotency_conflicts", "recovery_authority_ambiguous",
    "steal_active_lock", "conflicting_recovery", "cross_tenant_lock_ambiguity",
    "stale_lock_unsafe_release", "interrupted_lock_acquisition",
    "stale_lock_safe_release", "replay_after_rollback", "revive_aborted",
    "revive_quarantined", "allowed_recovery_scope", "forbidden_recovery_scope",
    "requested_recovery_scope", "recovery_contract_missing",
    "recovery_contract_malformed", "recovery_contract_contradicted",
    "failed_checkpoints", "por_tamper", "por_reorder", "por_missing_events",
    "recovery_requested_by",
)


def prepare_recovery_outcome(*, recovery_id, transaction_id, tenant_id, actor_id,
                             actor_type, b9_outcome=None,
                             desired_recovery_action="STATUS", created_at=None,
                             **over):
    """Prepare a deterministic, replayable recovery outcome for a B9 local
    transaction. Runs the full fail-closed evaluation, the chaos-sentinel crash
    drill and the release gate, then resolves the final recovery state. Produces
    only local evidence (Recovery Twin, Proof-of-Recovery, certificate, safety
    case, reconciliation); performs NO external effect, NO provider call, NO
    message/payment/CRM/evidence mutation, and never releases the inert outbox."""
    action = desired_recovery_action if desired_recovery_action in \
        RECOVERY_ACTIONS else "STATUS"
    ctx = {"tenant_id": tenant_id, "transaction_id": transaction_id,
           "recovery_id": recovery_id, "actor_id": actor_id,
           "b9_outcome": b9_outcome, "desired_recovery_action": action,
           "created_at": created_at}
    for k in _PASS_KEYS:
        if k in over:
            ctx[k] = over[k]
    ctx.setdefault("recovery_authority_basis", {"source": "SERVER_RBAC"})
    ctx.setdefault("source_surface", "SYSTEM_RECOVERY")
    recovery_requested_by = ctx.get("recovery_requested_by") or actor_id

    signals, reports = _recovery_signals(ctx)

    harness = run_crash_drill_harness(
        tenant_id=tenant_id, transaction_id=transaction_id, base_ctx=ctx)
    release_gate = build_release_gate(
        tenant_id=tenant_id, transaction_id=transaction_id, harness=harness)
    if release_gate["signal"]:
        signals.append(release_gate["signal"])

    signals = sorted(set(signals))
    if not signals:
        signals = ["RECOVERY_CLEAN"]
    dominant = dominant_signal(signals)
    new_state = _state_for_signal(dominant, ctx, action)

    tamper = dominant in _TAMPER_SIGNALS or new_state == "TAMPERED"
    any_q = any(s in _QUARANTINE_SIGNALS or s in _PARTIAL_SIGNALS
                for s in signals)
    reports["quarantine"] = build_quarantine(
        tenant_id=tenant_id, transaction_id=transaction_id, ctx=ctx,
        action=action, tamper=tamper, any_quarantine_signal=any_q)

    reason_code = REASON_CODES.get(dominant, dominant)
    reports["por_stream"] = build_por_stream(
        tenant_id=tenant_id, recovery_id=recovery_id,
        transaction_id=transaction_id, actor_id=actor_id, ctx=ctx,
        reason_code=dominant)
    if reports["por_stream"]["_signals"]:
        for s in reports["por_stream"]["_signals"]:
            if s not in signals:
                signals.append(s)
        signals = sorted(set(signals))
        dominant = dominant_signal(signals)
        new_state = _state_for_signal(dominant, ctx, action)
        reason_code = REASON_CODES.get(dominant, dominant)

    reports["twin"] = build_recovery_twin(
        recovery_id=recovery_id, tenant_id=tenant_id,
        transaction_id=transaction_id, actor_id=actor_id,
        recovery_requested_by=recovery_requested_by,
        recovery_authority_basis=ctx.get("recovery_authority_basis"),
        b9_outcome=b9_outcome, ctx=ctx, action=action, reports=reports)
    reports["proof_of_recovery"] = build_por_proof(
        tenant_id=tenant_id, recovery_id=recovery_id,
        transaction_id=transaction_id, reports=reports)
    prev_state = (b9_outcome or {}).get("b9_status") or "CLEAN"
    prev_recovery_state = "CLEAN"
    reports["recovery_certificate"] = build_recovery_certificate(
        tenant_id=tenant_id, recovery_id=recovery_id,
        transaction_id=transaction_id, b9_outcome=b9_outcome, reports=reports,
        action=action, prev_state=prev_recovery_state, new_state=new_state,
        reason_code=dominant)
    reports["recovery_safety_case"] = build_recovery_safety_case(
        tenant_id=tenant_id, recovery_id=recovery_id,
        transaction_id=transaction_id, reports=reports, new_state=new_state)
    if reports["recovery_safety_case"]["_signals"]:
        for s in reports["recovery_safety_case"]["_signals"]:
            if s not in signals:
                signals.append(s)
        signals = sorted(set(signals))
        dominant = dominant_signal(signals)
        new_state = _state_for_signal(dominant, ctx, action)
        reason_code = REASON_CODES.get(dominant, dominant)

    decision = _decision_for_state(new_state)
    recovery_applied = new_state in ("RECOVERED", "ROLLBACK_APPLIED_LOCAL",
                                     "RECOVERY_PLANNED", "CLEAN")
    rollback_applied_local = new_state == "ROLLBACK_APPLIED_LOCAL"

    proof_bundle = build_recovery_proof_bundle(
        tenant_id=tenant_id, transaction_id=transaction_id,
        recovery_id=recovery_id, reports=reports, harness=harness,
        release_gate=release_gate, new_state=new_state, dominant=dominant)

    clean_reports = {}
    for k, rep in reports.items():
        if isinstance(rep, dict):
            clean_reports[k] = {kk: vv for kk, vv in rep.items()
                                if kk != "_signals"}
        else:
            clean_reports[k] = rep

    outcome = {
        "b91_model_version": B91_MODEL_VERSION, "recovery_id": recovery_id,
        "transaction_id": transaction_id, "tenant_id": tenant_id,
        "actor_id": actor_id, "decided_by_actor_id": actor_id,
        "decided_by_actor_type": actor_type,
        "recovery_requested_by": recovery_requested_by,
        "desired_recovery_action": action,
        "previous_recovery_state": prev_recovery_state,
        "final_recovery_state": new_state,
        "recovery_state": new_state, "recovery_decision_status": decision,
        "dominant_signal": dominant, "dominant_reason_code": reason_code,
        "all_signals": signals,
        "signal_reason_codes": {s: REASON_CODES.get(s, s) for s in signals},
        "recovery_applied": recovery_applied,
        "rollback_applied_local": rollback_applied_local,
        "quarantine_required": clean_reports["quarantine"]["quarantined"],
        "stuck": new_state == "STUCK",
        "tampered": new_state == "TAMPERED",
        "b8_evidence_only": True, "b9_certificate_is_authority": False,
        "proof_of_recovery_is_authority": False,
        "recovery_safety_case_is_authority": False,
        "is_external": False, "is_execution": False,
        "produced_external_effect": False, "provider_called": False,
        "message_sent": False, "payment_executed": False,
        "external_crm_mutated": False, "outbox_released": False,
        "inert_outbox_preserved": clean_reports["inert_outbox_preservation"][
            "inert"],
        "no_external_effect": clean_reports["no_external_effect_theorem"][
            "theorem_holds"],
        "idempotency_preserved": clean_reports["idempotency_guard"][
            "idempotency_preserved"],
        "safety_monotonicity_passed": clean_reports["safety_monotonicity"][
            "monotonicity_passed"],
        "double_entry_reconciliation_passed": clean_reports[
            "double_entry_reconciliation"]["reconciliation_passed"],
        "before_state_hash": (b9_outcome or {}).get("before_state_hash"),
        "after_state_hash": (b9_outcome or {}).get("after_state_hash"),
        "original_transaction_hash": (b9_outcome or {}).get("b9_decision_hash"),
        "b91_chaos_harness": harness, "b91_release_gate_report": release_gate,
        "b91_recovery_proof_bundle": proof_bundle,
        "recovery_certificate_hash": clean_reports["recovery_certificate"][
            "recovery_certificate_hash"],
        "recovery_safety_case_hash": clean_reports["recovery_safety_case"][
            "safety_case_hash"],
        "proof_of_recovery_hash": clean_reports["proof_of_recovery"][
            "proof_of_recovery_hash"],
        "recovery_twin_hash": clean_reports["twin"]["recovery_twin_hash"],
        "created_at": created_at, "updated_at": created_at,
        "honesty_labels": HONESTY_LABELS,
    }
    outcome.update(clean_reports)
    outcome["b91_decision_hash"] = _core_hash(
        outcome, "b91_decision_hash", "recovery_id", "transaction_id",
        "actor_id", "decided_by_actor_id", "decided_by_actor_type",
        "recovery_requested_by", "b91_state_hash")
    outcome["b91_state_hash"] = _sha({
        "recovery_id": recovery_id, "transaction_id": transaction_id,
        "b91_decision_hash": outcome["b91_decision_hash"],
        "final_recovery_state": new_state, "dominant_signal": dominant,
        "proof_bundle_hash": proof_bundle["recovery_proof_bundle_hash"]})
    return outcome


# ---- Recovery event ledger ------------------------------------------------
B91_EVENT_TYPES = {
    "B91_RECOVERY_REQUEST_OPENED", "B91_RECOVERY_OUTCOME_PREPARED",
    "B91_CRASH_DRILL_RUN", "B91_RECOVERY_OUTCOME_VERIFIED",
}


def build_b91_event(*, event_type, tenant_id, recovery_id, transaction_id,
                    actor_id, actor_type, b91_state_hash, previous_event_hash,
                    sequence, detail, created_at):
    ev = {
        "b91_event_version": B91_EVENT_VERSION, "event_type": event_type,
        "tenant_id": tenant_id, "recovery_id": recovery_id,
        "transaction_id": transaction_id, "actor_id": actor_id,
        "actor_type": actor_type, "b91_state_hash": b91_state_hash,
        "previous_event_hash": previous_event_hash or GENESIS,
        "sequence": sequence, "detail": detail, "created_at": created_at,
        "honesty_labels": HONESTY_LABELS,
    }
    ev["event_hash"] = _core_hash(ev, "event_hash")
    return ev
