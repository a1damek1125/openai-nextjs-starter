"""Finalis ViktorAI Transaction-Escrow Write-Intent Draft Runtime (TOOL-B7).

The FIRST write-INTENT layer — but strictly LOCAL, DETERMINISTIC and
DRAFT-ONLY. It models a *future* write: it creates local write-intent draft
records, local semantic transaction drafts, local transaction escrow capsules,
human-review packages, deterministic state deltas, shadow-state simulations,
blast-radius/rollback/compensation simulations, approval-requirement bindings,
meaningful-human-judgment checks, concurrent-draft conflict graphs,
state-witness quorum vectors, escrowed commit-readiness certificates, revalidation
debt ledgers and a *placeholder-only* future commit gate contract.

It NEVER commits, sends, pays, mutates CRM/evidence/customer state, exports,
calls a provider/MCP/LLM, issues/derives a token, reads a credential, releases
a staged effect or activates a commitment record. Every effect is a
placeholder; every certificate is local evidence; approval does not execute;
escrow does not execute; commit-readiness does not execute. The most permissive
outcome is ``TRANSACTION_ESCROW_DRAFT_CREATED`` — a local escrowed draft, never
an external effect.

It consumes a TOOL-B6 read-path runtime outcome (read-only, provenance-verified,
release-gate-passed) and proves, deterministically, that the *future* write it
models is draft-only, escrowed, non-executable, conflict-checked, rollback-attack
fenced and revalidation-debt explicit — and it fails closed under fault
injection. There is NO commit endpoint, NO execute endpoint, NO effect-release
endpoint and NO active-commitment endpoint anywhere in this module.
"""
from __future__ import annotations

from .tool_contracts import canonical_json, _sha, _core_hash, _flatten_text
from . import tool_registry as _tr

WRITE_INTENT_MODEL_VERSION = "finalis-transaction-escrow-write-intent-draft-runtime-v4"
REQUEST_VERSION = "finalis-write-intent-request-envelope-v1"
DRAFT_VERSION = "finalis-write-intent-draft-record-v1"
SEMANTIC_TX_VERSION = "finalis-semantic-transaction-draft-v1"
TX_BOUNDARY_VERSION = "finalis-semantic-transaction-boundary-v1"
SHADOW_STATE_VERSION = "finalis-shadow-state-delta-graph-v1"
STATE_DELTA_VERSION = "finalis-write-intent-state-delta-v1"
STAGED_OUTBOX_VERSION = "finalis-staged-effect-outbox-placeholder-v1"
ACTIVE_COMMITMENT_VERSION = "finalis-active-commitment-record-placeholder-v1"
REVIEW_PACKAGE_VERSION = "finalis-write-intent-human-review-package-v1"
APPROVAL_REQ_VERSION = "finalis-write-intent-approval-requirement-v1"
APPROVAL_BIND_VERSION = "finalis-write-intent-approval-binding-v1"
MEANINGFUL_JUDGMENT_VERSION = "finalis-meaningful-human-judgment-v1"
DUAL_CONTROL_VERSION = "finalis-write-intent-dual-control-v1"
ROLLBACK_SIM_VERSION = "finalis-write-intent-rollback-simulation-v1"
COMPENSATION_VERSION = "finalis-write-intent-compensation-plan-v1"
CONTESTABILITY_VERSION = "finalis-write-intent-contestability-window-v1"
OBLIGATION_VERSION = "finalis-write-intent-obligation-containment-v1"
EVIDENCE_PRESERVATION_VERSION = "finalis-write-intent-evidence-preservation-v1"
TX_INVARIANT_VERSION = "finalis-write-intent-transaction-invariants-v1"
TX_REPLAY_VERSION = "finalis-semantic-transaction-replay-v1"
COMMIT_NON_EXEC_VERSION = "finalis-write-intent-commit-non-execution-v1"
# v4 additions
TX_ESCROW_VERSION = "finalis-transaction-escrow-capsule-v1"
COMMIT_READINESS_VERSION = "finalis-escrowed-commit-readiness-certificate-v1"
COMMIT_GATE_CONTRACT_VERSION = "finalis-future-commit-gate-contract-placeholder-v1"
COMMIT_GATE_NONEXIST_VERSION = "finalis-commit-gate-non-existence-proof-v1"
REVAL_DEBT_VERSION = "finalis-revalidation-debt-ledger-v1"
ROLLBACK_FENCE_VERSION = "finalis-semantic-rollback-attack-fence-v1"
ACTION_REPLAY_VERSION = "finalis-action-replay-guard-v1"
AUTH_RESURRECTION_VERSION = "finalis-authority-resurrection-guard-v1"
ROLLBACK_EQUIV_VERSION = "finalis-rollback-replay-equivalence-proof-v1"
CONFLICT_GRAPH_VERSION = "finalis-concurrent-draft-conflict-graph-v1"
CONFLICT_ORACLE_VERSION = "finalis-transaction-conflict-oracle-v1"
WITNESS_QUORUM_VERSION = "finalis-state-witness-quorum-vector-v1"
OUTBOX_QUARANTINE_VERSION = "finalis-effect-outbox-quarantine-matrix-v1"
ESCROW_EXPIRY_VERSION = "finalis-escrow-expiry-and-renewal-policy-v1"
ESCROW_TAMPER_VERSION = "finalis-escrow-tamper-evidence-record-v1"
READINESS_NONEXEC_VERSION = "finalis-transaction-readiness-non-execution-certificate-v1"
TX_ESCROW_PROOF_EXT_VERSION = "finalis-transaction-escrow-proof-bundle-extension-v1"
FAULT_HARNESS_VERSION = "finalis-write-intent-fault-injection-harness-v1"
RELEASE_GATE_VERSION = "finalis-write-intent-release-gate-negative-test-report-v1"
CONFORMANCE_VERSION = "finalis-write-intent-conformance-vector-v1"
PROOF_BUNDLE_VERSION = "finalis-write-intent-proof-bundle-v1"
WRITE_INTENT_EVENT_VERSION = "finalis-write-intent-event-v1"
GENESIS = "0" * 64


HONESTY_LABELS = [
    "WRITE_INTENT_DRAFT_ONLY", "SEMANTIC_TRANSACTION_DRAFT_ONLY",
    "TRANSACTION_ESCROW_ONLY", "SHADOW_STATE_ONLY",
    "STAGED_EFFECT_OUTBOX_PLACEHOLDER_ONLY",
    "ACTIVE_COMMITMENT_RECORD_PLACEHOLDER_ONLY",
    "COMMIT_READINESS_ESCROW_ONLY", "FUTURE_COMMIT_GATE_PLACEHOLDER_ONLY",
    "SEMANTIC_ROLLBACK_ATTACK_FENCE_REQUIRED",
    "CONCURRENT_DRAFT_CONFLICT_CHECKED",
    "CONTESTABILITY_REQUIRED_BEFORE_FUTURE_COMMIT",
    "OBLIGATION_CONTAINMENT_REQUIRED", "NO_REAL_WRITE_EFFECT",
    "NO_EFFECT_RELEASE", "NO_COMMIT_ACTIVATION", "NO_EXTERNAL_PROVIDER",
    "NO_NETWORK", "NO_TOKEN", "NO_CREDENTIAL", "NO_PAYMENT",
    "NO_CUSTOMER_MESSAGE", "NO_CRM_MUTATION", "NO_EVIDENCE_MUTATION",
    "NO_DATA_EXPORT", "HUMAN_APPROVAL_REQUIRED_BEFORE_FUTURE_COMMIT",
    "MEANINGFUL_HUMAN_JUDGMENT_REQUIRED", "APPROVAL_DOES_NOT_EXECUTE",
    "ROLLBACK_SIMULATION_ONLY", "COMPENSATION_PLAN_ONLY",
    "FUTURE_COMMIT_PLACEHOLDER_ONLY", "NOT_PRODUCTION_AUTONOMOUS_EXECUTION",
]

# --- Upstream (B6) acceptance ----------------------------------------------
B6_ACCEPTABLE_STATUSES = {"RUNTIME_READ_ONLY_COMPLETED"}

# Data classes that may be *touched* by a shadow-state delta (draft-only). No
# customer/secret/credential/token class may be a raw output of the draft.
ALLOWED_TARGET_CLASSES = {"PUBLIC", "INTERNAL"}
FORBIDDEN_TARGET_CLASSES = {
    "SECRET_LIKE", "CREDENTIAL_LIKE", "TOKEN_LIKE", "EXECUTION_AUTHORITY",
    "CROSS_TENANT_SOURCE", "PROVIDER_RESULT", "MCP_RESULT", "LLM_RESULT",
}

# Any of these on the proposed draft indicate an attempt to escape draft-only
# semantics into a real effect. All are hard blockers.
EXECUTION_MARKER_FIELDS = {
    "commit_executable_now", "execute_now", "release_effects_now",
    "activate_commitment_now", "resolve_escrow_and_commit", "send_now",
    "mutate_now", "export_now", "call_provider", "call_mcp", "call_llm",
    "issue_token", "derive_token", "read_credential",
}
_INJECTION_NEEDLES = [
    "escrow means commit is allowed", "ready for future commit only means execute",
    "commit executable now", "commit gate endpoint", "resolve escrow and commit",
    "release staged effect", "reuse old approval", "replay prior",
    "restore consumed authority", "use old state witness",
    "both future ready", "unquarantined outbox item is okay",
    "blocking conflict is only warning", "escrow expired but still valid",
    "state witness quorum optional", "revalidation debt can be client resolved",
    "readiness certificate is bearer authority", "proof bundle overrides blocker",
    "execute now", "commit now", "send customer message", "mutate crm",
    "mutate evidence", "make payment", "export data", "call provider",
    "activate commitment", "release effects",
]

# Surfaces the commit-gate-non-existence proof must sweep. None may resolve to a
# real commit/effect endpoint.
COMMIT_SURFACES = [
    "WRITE_INTENT_COMMIT_ENDPOINT", "SEMANTIC_TRANSACTION_COMMIT_ENDPOINT",
    "EFFECT_RELEASE_ENDPOINT", "ACTIVE_COMMITMENT_ACTIVATE_ENDPOINT",
    "CRM_WRITE_ENDPOINT", "EVIDENCE_WRITE_ENDPOINT", "PAYMENT_ENDPOINT",
    "MESSAGE_SEND_ENDPOINT", "EXPORT_ENDPOINT", "PROVIDER_CALL_PATH",
    "MCP_CALL_PATH", "LLM_CALL_PATH",
]

DEBT_ITEM_TYPES = {
    "STATE_WITNESS_RECHECK", "POLICY_EPOCH_RECHECK", "APPROVAL_FRESHNESS_RECHECK",
    "CONSENT_RECHECK", "CONFLICT_RECHECK", "CONTESTABILITY_RECHECK",
    "OBLIGATION_RECHECK", "ROLLBACK_RECHECK", "COMPENSATION_RECHECK",
    "EVIDENCE_PRESERVATION_RECHECK", "IDEMPOTENCY_RECHECK", "AUTHORITY_RECHECK",
}
WITNESS_CLASSES = {
    "SOURCE_STATE_HASH", "POLICY_EPOCH", "CONSENT_STATE", "APPROVAL_STATE",
    "EVIDENCE_STATE", "CUSTOMER_PROMISE_STATE", "OBLIGATION_STATE",
    "CONFLICT_STATE", "CONTESTABILITY_STATE",
}
# Minimum witness classes required for a HIGH-risk future-commit readiness.
HIGH_RISK_WITNESS_CLASSES = {
    "SOURCE_STATE_HASH", "POLICY_EPOCH", "APPROVAL_STATE", "CONFLICT_STATE",
    "OBLIGATION_STATE",
}
CONFLICT_CLASSES = {
    "SAME_TARGET_WRITE", "OVERLAPPING_FIELD_DELTA", "EVIDENCE_MUTATION_CONFLICT",
    "CONSENT_SCOPE_CONFLICT", "CUSTOMER_PROMISE_CONFLICT", "OBLIGATION_CONFLICT",
    "IDEMPOTENCY_CONFLICT", "APPROVAL_SCOPE_CONFLICT", "STATE_WITNESS_CONFLICT",
    "SERIALIZATION_ORDER_CONFLICT",
}
CONFLICT_NODE_TYPES = {
    "WRITE_INTENT_DRAFT", "SEMANTIC_TRANSACTION_DRAFT", "TARGET_ENTITY",
    "SHADOW_DELTA_FIELD", "OBLIGATION", "EVIDENCE_REF", "CUSTOMER_PROMISE",
    "CONSENT_REF", "APPROVAL_REF", "STATE_WITNESS",
}
CONFLICT_EDGE_TYPES = {
    "READS", "PROPOSES_WRITE", "CONFLICTS_WITH", "OVERLAPS_WITH",
    "REQUIRES_ORDERING", "BLOCKS_FUTURE_READINESS", "REQUIRES_REVIEW",
}
ORACLE_DECISIONS = {"NO_CONFLICT", "NEEDS_REVIEW", "BLOCK_FUTURE_READINESS",
                    "QUARANTINE"}

DEFAULT_POLICY = {
    "max_shadow_delta_fields": 16, "max_blast_radius_entities": 8,
    "min_state_witness_quorum": 3, "escrow_ttl_epochs": 10,
    "max_unresolved_debt": 0, "max_compensation_gap": 0,
}


# --- Hard-fail dominance ladder --------------------------------------------
FAILURE_DOMINANCE = [
    "TAMPERED", "CROSS_TENANT", "REVOKED",
    "TOOL_B1_BLOCKED", "TOOL_B2_BLOCKED", "TOOL_B3_BLOCKED", "TOOL_B4_BLOCKED",
    "TOOL_B5_BLOCKED", "TOOL_B6_BLOCKED", "B6_PROOF_BUNDLE_MISSING",
    "B6_OUTPUT_PROVENANCE_FAILED", "B6_RELEASE_GATE_FAILED",
    "B6_EXTERNAL_EFFECT_DETECTED", "WRITE_INTENT_INVALID",
    "SEMANTIC_TRANSACTION_INVALID", "TRANSACTION_ESCROW_INVALID",
    "ESCROW_TAMPER_DETECTED", "ESCROW_EXPIRED",
    "COMMIT_READINESS_CERTIFICATE_MISMATCH", "COMMIT_GATE_CONTRACT_INVALID",
    "COMMIT_GATE_ENDPOINT_PRESENT", "REVALIDATION_DEBT_UNRESOLVED",
    "SEMANTIC_ROLLBACK_ATTACK_DETECTED", "ACTION_REPLAY_DETECTED",
    "AUTHORITY_RESURRECTION_DETECTED", "ROLLBACK_REPLAY_EQUIVALENCE_FAILED",
    "CONCURRENT_DRAFT_CONFLICT_BLOCKING", "TRANSACTION_CONFLICT_ORACLE_REJECTED",
    "STATE_WITNESS_QUORUM_MISSING", "EFFECT_OUTBOX_NOT_QUARANTINED",
    "EFFECT_RELEASE_ATTEMPT", "COMMITMENT_RECORD_ACTIVATED",
    "COMMIT_ATTEMPT_DETECTED", "PROVIDER_CALL_ATTEMPT", "MCP_CALL_ATTEMPT",
    "LLM_CALL_ATTEMPT", "TOKEN_ISSUANCE_ATTEMPT", "CREDENTIAL_READ_DETECTED",
    "CUSTOMER_MESSAGE_ATTEMPT", "PAYMENT_ATTEMPT", "CRM_MUTATION_ATTEMPT",
    "EVIDENCE_MUTATION_ATTEMPT", "DATA_EXPORT_ATTEMPT", "CONTESTATION_UNRESOLVED",
    "OBLIGATION_CONTAINMENT_FAILED", "EVIDENCE_PRESERVATION_FAILED",
    "EVIDENCE_DESTRUCTIVE_REPAIR_DETECTED", "REPAIR_FEASIBILITY_FAILED",
    "TRANSACTION_INVARIANT_FAILED", "TRANSACTION_CONSTRAINT_FAILED",
    "SEMANTIC_TRANSACTION_REPLAY_MISMATCH", "APPROVAL_MISSING",
    "APPROVAL_NOT_SERVER_VERIFIED", "SELF_APPROVAL_DETECTED",
    "DUAL_CONTROL_MISSING", "MEANINGFUL_JUDGMENT_FAILED",
    "ROLLBACK_SIMULATION_FAILED", "COMPENSATION_GAP_DETECTED",
    "IRREVERSIBILITY_BARRIER_DETECTED", "IDEMPOTENCY_CONFLICT", "REPLAY_CONFLICT",
    "TRANSACTION_READINESS_NON_EXECUTION_FAILED", "TRANSACTION_CONSTRAINT_FAILED",
    "TRANSACTION_CONFLICT_ORACLE_NEEDS_REVIEW",
    "CONCURRENT_DRAFT_CONFLICT_REVIEW", "ESCROW_RENEWAL_REQUIRED",
    "STATE_WITNESS_STALE", "FAULT_INJECTION_RELEASE_GATE_FAILED", "NEEDS_REVIEW",
    "TRANSACTION_ESCROW_DRAFT_CREATED",
]
_DOMINANCE_RANK = {s: i for i, s in enumerate(FAILURE_DOMINANCE)}
POSITIVE_SIGNALS = {"TRANSACTION_ESCROW_DRAFT_CREATED"}

WRITE_INTENT_STATUSES = {
    "WRITE_INTENT_REQUEST_PENDING", "WRITE_INTENT_DRAFT_CREATED",
    "TRANSACTION_ESCROW_DRAFT_CREATED", "TRANSACTION_ESCROW_NEEDS_RENEWAL",
    "TRANSACTION_ESCROW_NEEDS_CONFLICT_REVIEW",
    "TRANSACTION_ESCROW_NEEDS_REVALIDATION", "TRANSACTION_ESCROW_BLOCKED",
    "TRANSACTION_ESCROW_QUARANTINED", "TRANSACTION_ESCROW_REPLAY_CONFLICT",
    "TRANSACTION_ESCROW_NOT_IMPLEMENTED", "WRITE_INTENT_NEEDS_HUMAN_APPROVAL",
    "WRITE_INTENT_NEEDS_DUAL_CONTROL", "WRITE_INTENT_NEEDS_MEANINGFUL_REVIEW",
    "WRITE_INTENT_NEEDS_CONTESTABILITY_REVIEW",
    "WRITE_INTENT_NEEDS_OBLIGATION_REVIEW", "WRITE_INTENT_BLOCKED",
    "WRITE_INTENT_DENIED", "WRITE_INTENT_QUARANTINED", "WRITE_INTENT_STALE",
    "WRITE_INTENT_TAMPERED", "WRITE_INTENT_NEEDS_REVIEW",
    "WRITE_INTENT_NOT_IMPLEMENTED",
}
POSITIVE_STATUSES = {"TRANSACTION_ESCROW_DRAFT_CREATED",
                     "WRITE_INTENT_DRAFT_CREATED"}
DECISION_STATUSES = {
    "WRITE_INTENT_DECISION_ALLOW_DRAFT_ESCROW_ONLY",
    "WRITE_INTENT_DECISION_BLOCK", "WRITE_INTENT_DECISION_DENY",
    "WRITE_INTENT_DECISION_NEEDS_HUMAN_APPROVAL",
    "WRITE_INTENT_DECISION_NEEDS_DUAL_CONTROL",
    "WRITE_INTENT_DECISION_NEEDS_MEANINGFUL_REVIEW",
    "WRITE_INTENT_DECISION_NEEDS_CONTESTABILITY_REVIEW",
    "WRITE_INTENT_DECISION_NEEDS_OBLIGATION_REVIEW",
    "WRITE_INTENT_DECISION_NEEDS_CONFLICT_REVIEW",
    "WRITE_INTENT_DECISION_NEEDS_REVALIDATION",
    "WRITE_INTENT_DECISION_NEEDS_ESCROW_RENEWAL",
    "WRITE_INTENT_DECISION_NEEDS_REVIEW", "WRITE_INTENT_DECISION_STALE",
    "WRITE_INTENT_DECISION_QUARANTINE", "WRITE_INTENT_DECISION_REPLAY_CONFLICT",
    "WRITE_INTENT_DECISION_NOT_IMPLEMENTED",
}

_QUARANTINE_SIGNALS = {
    "COMMITMENT_RECORD_ACTIVATED", "COMMIT_ATTEMPT_DETECTED",
    "EFFECT_RELEASE_ATTEMPT", "PROVIDER_CALL_ATTEMPT", "MCP_CALL_ATTEMPT",
    "LLM_CALL_ATTEMPT", "TOKEN_ISSUANCE_ATTEMPT", "CREDENTIAL_READ_DETECTED",
    "CUSTOMER_MESSAGE_ATTEMPT", "PAYMENT_ATTEMPT", "CRM_MUTATION_ATTEMPT",
    "EVIDENCE_MUTATION_ATTEMPT", "DATA_EXPORT_ATTEMPT",
    "AUTHORITY_RESURRECTION_DETECTED", "SEMANTIC_ROLLBACK_ATTACK_DETECTED",
    "ACTION_REPLAY_DETECTED",
}
_STALE_SIGNALS = {"ESCROW_EXPIRED", "STATE_WITNESS_STALE"}
_RENEWAL_SIGNALS = {"ESCROW_RENEWAL_REQUIRED"}
_REVALIDATION_SIGNALS = {"REVALIDATION_DEBT_UNRESOLVED"}
_CONFLICT_REVIEW_SIGNALS = {"CONCURRENT_DRAFT_CONFLICT_REVIEW",
                            "TRANSACTION_CONFLICT_ORACLE_NEEDS_REVIEW"}
_APPROVAL_SIGNALS = {"APPROVAL_MISSING", "APPROVAL_NOT_SERVER_VERIFIED",
                     "SELF_APPROVAL_DETECTED"}
_MEANINGFUL_SIGNALS = {"MEANINGFUL_JUDGMENT_FAILED"}
_CONTESTABILITY_SIGNALS = {"CONTESTATION_UNRESOLVED"}
_OBLIGATION_SIGNALS = {"OBLIGATION_CONTAINMENT_FAILED"}
_REPLAY_CONFLICT_SIGNALS = {"REPLAY_CONFLICT", "IDEMPOTENCY_CONFLICT",
                            "SEMANTIC_TRANSACTION_REPLAY_MISMATCH"}


def _status_for_signal(sig):
    if sig == "TAMPERED":
        return "WRITE_INTENT_TAMPERED"
    if sig in POSITIVE_SIGNALS:
        return "TRANSACTION_ESCROW_DRAFT_CREATED"
    if sig in _QUARANTINE_SIGNALS:
        return "TRANSACTION_ESCROW_QUARANTINED"
    if sig in _REPLAY_CONFLICT_SIGNALS:
        return "TRANSACTION_ESCROW_REPLAY_CONFLICT"
    if sig in _RENEWAL_SIGNALS:
        return "TRANSACTION_ESCROW_NEEDS_RENEWAL"
    if sig in _REVALIDATION_SIGNALS:
        return "TRANSACTION_ESCROW_NEEDS_REVALIDATION"
    if sig in _CONFLICT_REVIEW_SIGNALS:
        return "TRANSACTION_ESCROW_NEEDS_CONFLICT_REVIEW"
    if sig in _STALE_SIGNALS:
        return "WRITE_INTENT_STALE"
    if sig in _APPROVAL_SIGNALS:
        return "WRITE_INTENT_NEEDS_HUMAN_APPROVAL"
    if sig == "DUAL_CONTROL_MISSING":
        return "WRITE_INTENT_NEEDS_DUAL_CONTROL"
    if sig in _MEANINGFUL_SIGNALS:
        return "WRITE_INTENT_NEEDS_MEANINGFUL_REVIEW"
    if sig in _CONTESTABILITY_SIGNALS:
        return "WRITE_INTENT_NEEDS_CONTESTABILITY_REVIEW"
    if sig in _OBLIGATION_SIGNALS:
        return "WRITE_INTENT_NEEDS_OBLIGATION_REVIEW"
    if sig == "NEEDS_REVIEW":
        return "WRITE_INTENT_NEEDS_REVIEW"
    return "TRANSACTION_ESCROW_BLOCKED"


def _decision_for_status(status):
    return {
        "TRANSACTION_ESCROW_DRAFT_CREATED":
            "WRITE_INTENT_DECISION_ALLOW_DRAFT_ESCROW_ONLY",
        "WRITE_INTENT_DRAFT_CREATED":
            "WRITE_INTENT_DECISION_ALLOW_DRAFT_ESCROW_ONLY",
        "WRITE_INTENT_TAMPERED": "WRITE_INTENT_DECISION_BLOCK",
        "TRANSACTION_ESCROW_QUARANTINED": "WRITE_INTENT_DECISION_QUARANTINE",
        "WRITE_INTENT_QUARANTINED": "WRITE_INTENT_DECISION_QUARANTINE",
        "WRITE_INTENT_STALE": "WRITE_INTENT_DECISION_STALE",
        "TRANSACTION_ESCROW_NEEDS_RENEWAL":
            "WRITE_INTENT_DECISION_NEEDS_ESCROW_RENEWAL",
        "TRANSACTION_ESCROW_NEEDS_REVALIDATION":
            "WRITE_INTENT_DECISION_NEEDS_REVALIDATION",
        "TRANSACTION_ESCROW_NEEDS_CONFLICT_REVIEW":
            "WRITE_INTENT_DECISION_NEEDS_CONFLICT_REVIEW",
        "TRANSACTION_ESCROW_REPLAY_CONFLICT":
            "WRITE_INTENT_DECISION_REPLAY_CONFLICT",
        "WRITE_INTENT_NEEDS_HUMAN_APPROVAL":
            "WRITE_INTENT_DECISION_NEEDS_HUMAN_APPROVAL",
        "WRITE_INTENT_NEEDS_DUAL_CONTROL":
            "WRITE_INTENT_DECISION_NEEDS_DUAL_CONTROL",
        "WRITE_INTENT_NEEDS_MEANINGFUL_REVIEW":
            "WRITE_INTENT_DECISION_NEEDS_MEANINGFUL_REVIEW",
        "WRITE_INTENT_NEEDS_CONTESTABILITY_REVIEW":
            "WRITE_INTENT_DECISION_NEEDS_CONTESTABILITY_REVIEW",
        "WRITE_INTENT_NEEDS_OBLIGATION_REVIEW":
            "WRITE_INTENT_DECISION_NEEDS_OBLIGATION_REVIEW",
        "WRITE_INTENT_NEEDS_REVIEW": "WRITE_INTENT_DECISION_NEEDS_REVIEW",
        "WRITE_INTENT_DENIED": "WRITE_INTENT_DECISION_DENY",
    }.get(status, "WRITE_INTENT_DECISION_BLOCK")


REASON_CODES = {s: s.replace("_", " ").capitalize() + "." for s in
                FAILURE_DOMINANCE}
REASON_CODES.update({
    "TRANSACTION_ESCROW_DRAFT_CREATED": "Local escrowed write-intent draft "
    "created for FUTURE human-approved commit; no real write, no commit, no "
    "effect release, no external effect.",
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
        return "TRANSACTION_ESCROW_DRAFT_CREATED"
    return min(signals, key=lambda s: _DOMINANCE_RANK.get(s, -1))


def status_for_signals(signals) -> str:
    return _status_for_signal(dominant_signal(signals))


def _has_injection(*texts) -> bool:
    blob = " ".join(_norm(t) for t in texts if t is not None)
    return any(n in blob for n in _INJECTION_NEEDLES)


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


# --- Upstream (B6) acceptance ----------------------------------------------
def _upstream_signals(*, tenant_id, b6_outcome, b6_request) -> list:
    sigs = []
    o = b6_outcome or {}
    if not o:
        return ["B6_PROOF_BUNDLE_MISSING"]
    if o.get("tenant_id") not in (None, tenant_id):
        sigs.append("CROSS_TENANT")
    if o.get("runtime_status") not in B6_ACCEPTABLE_STATUSES:
        sigs.append("TOOL_B6_BLOCKED")
    pb = o.get("runtime_proof_bundle") or {}
    if not pb or not pb.get("runtime_proof_bundle_hash"):
        sigs.append("B6_PROOF_BUNDLE_MISSING")
    cert = o.get("output_provenance_certificate") or {}
    if cert and cert.get("certificate_status") not in (
            None, "VALID", "PROVENANCE_CERTIFIED", "OUTPUT_PROVENANCE_CERTIFIED"):
        sigs.append("B6_OUTPUT_PROVENANCE_FAILED")
    rg = o.get("runtime_release_gate_report") or {}
    if rg and rg.get("release_gate_status") not in (
            None, "PASSED", "RELEASE_GATE_PASSED"):
        sigs.append("B6_RELEASE_GATE_FAILED")
    if o.get("produced_external_effect") is True or o.get("is_external") is True \
            or o.get("is_write") is True:
        sigs.append("B6_EXTERNAL_EFFECT_DETECTED")
    return sigs


# --- Write-intent draft record ---------------------------------------------
def build_write_intent_draft(*, tenant_id, write_intent_id, b6_outcome,
                             target_entity, proposed_deltas, intent,
                             obligations, evidence_refs, consent_scope,
                             customer_promises, execution_markers,
                             created_at=None) -> dict:
    te = target_entity or {}
    deltas = []
    for d in _as_list(proposed_deltas):
        d = d or {}
        deltas.append({
            "field_path": str(d.get("field_path", "")),
            "from_value_hash": _sha(d.get("from_value")),
            "to_value_hash": _sha(d.get("to_value")),
            "data_class": str(d.get("data_class", "INTERNAL")).upper(),
        })
    signals = []
    # Any raw execution marker on the draft is an attempt to escape draft-only.
    markers = {k: v for k, v in (execution_markers or {}).items()
               if k in EXECUTION_MARKER_FIELDS and v}
    forbidden = [d for d in deltas if d["data_class"] in FORBIDDEN_TARGET_CLASSES]
    injection = _has_injection(intent, canonical_json(execution_markers or {}),
                               canonical_json(te))
    valid = bool(te.get("entity_type")) and bool(deltas) and not forbidden \
        and not injection
    if not valid:
        signals.append("WRITE_INTENT_INVALID")
    draft = {
        "write_intent_draft_record_version": DRAFT_VERSION,
        "write_intent_id": write_intent_id, "tenant_id": tenant_id,
        "b6_runtime_request_id": (b6_outcome or {}).get("runtime_request_id"),
        "b6_runtime_decision_hash": (b6_outcome or {}).get(
            "runtime_decision_hash"),
        "target_entity_type": str(te.get("entity_type", "")),
        "target_entity_id": str(te.get("entity_id", "")),
        "intent": _norm(intent), "proposed_deltas": deltas,
        "obligation_ids": sorted(set(map(str, _as_list(obligations)))),
        "evidence_refs": sorted(set(map(str, _as_list(evidence_refs)))),
        "consent_scope": consent_scope or {},
        "customer_promise_ids": sorted(set(map(str,
                                               _as_list(customer_promises)))),
        "is_write": False, "is_commit": False, "is_execution": False,
        "draft_only": True, "will_execute": False,
        "detected_execution_markers": sorted(markers.keys()),
        "forbidden_delta_classes": sorted({d["data_class"] for d in forbidden}),
        "draft_valid": valid, "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    draft["write_intent_draft_hash"] = _core_hash(
        draft, "write_intent_draft_hash", "signal")
    draft["_signals"] = signals
    return draft


# --- Semantic transaction draft --------------------------------------------
def build_semantic_transaction(*, tenant_id, write_intent_id, draft,
                               task_scope, boundary_ops) -> dict:
    ops = [str(x) for x in _as_list(boundary_ops)] or ["STAGE_DELTA"]
    stid = "stx-" + _sha({"wi": write_intent_id,
                          "deltas": draft.get("proposed_deltas")})[:16]
    scoped = bool(task_scope)
    signals = [] if scoped else ["SEMANTIC_TRANSACTION_INVALID"]
    stx = {
        "semantic_transaction_draft_version": SEMANTIC_TX_VERSION,
        "semantic_transaction_id": stid, "tenant_id": tenant_id,
        "write_intent_id": write_intent_id, "task_scope": str(task_scope or ""),
        "boundary_operations": ops, "operation_count": len(ops),
        "atomic_all_or_nothing_draft": True, "is_execution": False,
        "draft_only": True, "semantic_transaction_valid": scoped,
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    stx["semantic_transaction_hash"] = _core_hash(
        stx, "semantic_transaction_hash", "signal")
    stx["_signals"] = signals
    return stx


def build_transaction_boundary(*, tenant_id, write_intent_id, stx,
                               draft) -> dict:
    b = {
        "semantic_transaction_boundary_version": TX_BOUNDARY_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "included_field_paths": sorted({d["field_path"] for d in
                                        draft.get("proposed_deltas", [])}),
        "included_obligation_ids": draft.get("obligation_ids", []),
        "included_evidence_refs": draft.get("evidence_refs", []),
        "deterministic_boundary": True, "boundary_leaks_out_of_scope": False,
        "honesty_labels": HONESTY_LABELS,
    }
    b["transaction_boundary_hash"] = _core_hash(b, "transaction_boundary_hash")
    b["_signals"] = []
    return b


# --- Shadow-state delta graph ----------------------------------------------
def build_shadow_state_delta_graph(*, tenant_id, write_intent_id, draft,
                                   policy) -> dict:
    deltas = draft.get("proposed_deltas", [])
    pol = policy or DEFAULT_POLICY
    nodes = [{"node_id": "shadow:" + d["field_path"],
              "field_path": d["field_path"], "data_class": d["data_class"],
              "shadow_only": True} for d in deltas]
    edges = [{"from": "draft", "to": n["node_id"], "edge_type":
              "SHADOW_DELTA"} for n in nodes]
    blast = sorted({draft.get("target_entity_id", "")} |
                   {n["field_path"].split(".")[0] for n in nodes})
    signals = []
    if len(deltas) > pol.get("max_shadow_delta_fields", 16):
        signals.append("TRANSACTION_CONSTRAINT_FAILED")
    if len(blast) > pol.get("max_blast_radius_entities", 8):
        signals.append("TRANSACTION_CONSTRAINT_FAILED")
    g = {
        "shadow_state_delta_graph_version": SHADOW_STATE_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "nodes": nodes, "edges": edges, "node_count": len(nodes),
        "blast_radius_entities": blast,
        "blast_radius_size": len(blast), "touches_production_state": False,
        "shadow_only": True, "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    g["shadow_state_delta_graph_hash"] = _core_hash(
        g, "shadow_state_delta_graph_hash", "signal")
    g["_signals"] = signals
    return g


def build_state_delta(*, tenant_id, write_intent_id, draft, shadow) -> dict:
    d = {
        "write_intent_state_delta_version": STATE_DELTA_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "delta_entries": draft.get("proposed_deltas", []),
        "delta_count": len(draft.get("proposed_deltas", [])),
        "shadow_state_delta_graph_hash": shadow[
            "shadow_state_delta_graph_hash"],
        "applied_to_production": False, "deterministic": True,
        "honesty_labels": HONESTY_LABELS,
    }
    d["state_delta_hash"] = _core_hash(d, "state_delta_hash")
    d["_signals"] = []
    return d


# --- Staged effect outbox placeholder + quarantine matrix ------------------
def build_staged_effect_outbox(*, tenant_id, write_intent_id, stx, draft,
                               release_attempts) -> dict:
    effects = []
    for i, d in enumerate(draft.get("proposed_deltas", [])):
        effects.append({
            "effect_id": f"eff-{i}-" + _sha(d)[:12],
            "effect_kind": "SHADOW_FIELD_WRITE_PLACEHOLDER",
            "target_field": d["field_path"], "released": False,
            "releasable": False, "quarantined": True,
        })
    ob = {
        "staged_effect_outbox_placeholder_version": STAGED_OUTBOX_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "effects": effects, "effect_count": len(effects),
        "any_released": False, "any_releasable": False,
        "release_attempts_detected": int(_int(release_attempts)),
        "placeholder_only": True, "honesty_labels": HONESTY_LABELS,
    }
    ob["staged_effect_outbox_hash"] = _core_hash(ob, "staged_effect_outbox_hash")
    ob["_signals"] = []
    return ob


def build_effect_outbox_quarantine(*, tenant_id, write_intent_id, stx,
                                   outbox) -> dict:
    effects = outbox.get("effects", [])
    statuses = ["QUARANTINED" for _ in effects]
    unquarantined = [e for e in effects if not e.get("quarantined")]
    release_attempts = outbox.get("release_attempts_detected", 0)
    signals = []
    if unquarantined:
        signals.append("EFFECT_OUTBOX_NOT_QUARANTINED")
    if release_attempts > 0 or outbox.get("any_released") or outbox.get(
            "any_releasable"):
        signals.append("EFFECT_RELEASE_ATTEMPT")
    m = {
        "effect_outbox_quarantine_version": OUTBOX_QUARANTINE_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "staged_effect_outbox_hash": outbox["staged_effect_outbox_hash"],
        "effect_ids": [e["effect_id"] for e in effects],
        "effect_kinds": sorted({e["effect_kind"] for e in effects}),
        "quarantine_statuses": statuses,
        "release_attempts_detected": release_attempts,
        "all_quarantined": not unquarantined,
        "quarantine_matrix_status": "QUARANTINED" if not signals else "BREACH",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    m["effect_outbox_quarantine_hash"] = _core_hash(
        m, "effect_outbox_quarantine_hash", "signal")
    m["_signals"] = signals
    return m


# --- Active commitment record placeholder ----------------------------------
def build_active_commitment_placeholder(*, tenant_id, write_intent_id, stx,
                                        activation_attempts) -> dict:
    attempts = _int(activation_attempts)
    signals = ["COMMITMENT_RECORD_ACTIVATED"] if attempts > 0 else []
    r = {
        "active_commitment_record_placeholder_version": ACTIVE_COMMITMENT_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "commitment_state": "PLACEHOLDER_INACTIVE", "activated": False,
        "can_activate": False, "activation_attempts_detected": attempts,
        "placeholder_only": True, "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["active_commitment_record_hash"] = _core_hash(
        r, "active_commitment_record_hash", "signal")
    r["_signals"] = signals
    return r


# --- Transaction escrow capsule (v4) ---------------------------------------
def build_transaction_escrow_capsule(*, tenant_id, write_intent_id, stx, draft,
                                     approval_binding, obligation,
                                     contestability, revalidation_debt,
                                     shadow, escrow_created_epoch,
                                     escrow_expires_epoch, escrow_mutable,
                                     created_at=None) -> dict:
    signals = []
    mutable = bool(escrow_mutable)
    if mutable:
        signals.append("TRANSACTION_ESCROW_INVALID")
    cap = {
        "transaction_escrow_capsule_version": TX_ESCROW_VERSION,
        "transaction_escrow_id": "esc-" + _sha({
            "wi": write_intent_id, "stx": stx["semantic_transaction_id"]})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "escrow_status": "ESCROWED" if not signals else "INVALID",
        "escrow_scope_hash": draft.get("write_intent_draft_hash"),
        "escrow_payload_hash": _sha(draft.get("proposed_deltas")),
        "escrow_state_delta_hash": shadow["shadow_state_delta_graph_hash"],
        "escrow_approval_hash": approval_binding.get(
            "approval_binding_hash"),
        "escrow_obligation_hash": obligation.get("obligation_containment_hash"),
        "escrow_contestability_hash": contestability.get(
            "contestability_window_hash"),
        "escrow_revalidation_debt_hash": revalidation_debt.get(
            "revalidation_debt_ledger_hash"),
        "escrow_created_epoch": _int(escrow_created_epoch, 0),
        "escrow_expires_epoch": _int(escrow_expires_epoch, 0),
        "escrow_mutable": mutable, "escrow_executes": False,
        "escrow_can_release_effects": False, "escrow_can_activate_commitment": False,
        "escrow_can_commit": False, "local_evidence_only": True,
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    cap["transaction_escrow_hash"] = _core_hash(
        cap, "transaction_escrow_hash", "signal")
    cap["_signals"] = signals
    return cap


def build_escrow_tamper_evidence(*, tenant_id, write_intent_id, stx, capsule,
                                observed_escrow_hash=None) -> dict:
    expected = capsule["transaction_escrow_hash"]
    observed = observed_escrow_hash if observed_escrow_hash is not None else \
        expected
    tamper = observed != expected
    signals = ["ESCROW_TAMPER_DETECTED"] if tamper else []
    fields = ["transaction_escrow_hash"] if tamper else []
    r = {
        "escrow_tamper_evidence_version": ESCROW_TAMPER_VERSION,
        "escrow_tamper_evidence_id": "tmp-" + _sha({
            "wi": write_intent_id, "exp": expected})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "expected_escrow_hash": expected, "observed_escrow_hash": observed,
        "tamper_detected": tamper, "tamper_fields": fields,
        "tamper_status": "TAMPERED" if tamper else "INTACT",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["escrow_tamper_evidence_hash"] = _core_hash(
        r, "escrow_tamper_evidence_hash", "signal")
    r["_signals"] = signals
    return r


def build_escrow_expiry_policy(*, tenant_id, write_intent_id, stx, capsule,
                              current_epoch, policy) -> dict:
    created = capsule["escrow_created_epoch"]
    expires = capsule["escrow_expires_epoch"]
    cur = _int(current_epoch, created)
    expired = cur >= expires if expires else False
    signals = []
    if expired:
        signals.append("ESCROW_EXPIRED")
    r = {
        "escrow_expiry_policy_version": ESCROW_EXPIRY_VERSION,
        "escrow_expiry_policy_id": "exp-" + _sha({
            "wi": write_intent_id, "c": created, "e": expires})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "escrow_created_epoch": created, "escrow_expires_epoch": expires,
        "current_epoch": cur, "renewal_required": expired,
        "renewal_allowed": expired, "renewal_executes": False,
        "renewal_requirements": ["FULL_REVALIDATION_BEFORE_RENEWAL"] if expired
        else [], "expiry_status": "EXPIRED" if expired else "VALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["escrow_expiry_policy_hash"] = _core_hash(
        r, "escrow_expiry_policy_hash", "signal")
    r["_signals"] = signals
    return r


# --- Revalidation debt ledger (v4) -----------------------------------------
def build_revalidation_debt_ledger(*, tenant_id, write_intent_id, stx,
                                  debt_items) -> dict:
    items = []
    for it in _as_list(debt_items):
        it = it or {}
        t = str(it.get("debt_type", "")).upper()
        if t not in DEBT_ITEM_TYPES:
            t = "AUTHORITY_RECHECK"
        items.append({
            "debt_type": t, "detail": _norm(it.get("detail", "")),
            "resolved": bool(it.get("resolved")),
            # Client cannot self-resolve: resolution requires a server witness.
            "server_verified_resolution": bool(
                it.get("server_verified_resolution")),
        })
    unresolved = [i for i in items if not (i["resolved"] and i[
        "server_verified_resolution"])]
    required = sorted({i["debt_type"] for i in items})
    signals = ["REVALIDATION_DEBT_UNRESOLVED"] if unresolved else []
    r = {
        "revalidation_debt_ledger_version": REVAL_DEBT_VERSION,
        "revalidation_debt_ledger_id": "dbt-" + _sha({
            "wi": write_intent_id, "n": len(items)})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "debt_items": items, "required_before_future_commit": required,
        "unresolved_debt_items": unresolved,
        "unresolved_count": len(unresolved),
        "debt_status": "CLEARED" if not unresolved else "OUTSTANDING",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["revalidation_debt_ledger_hash"] = _core_hash(
        r, "revalidation_debt_ledger_hash", "signal")
    r["_signals"] = signals
    return r


# --- Semantic rollback-attack fence + guards (v4) --------------------------
def build_action_replay_guard(*, tenant_id, write_intent_id, stx,
                            idempotency_key, prior_action_hashes,
                            proposed_action_hash) -> dict:
    priors = sorted(set(map(str, _as_list(prior_action_hashes))))
    proposed = str(proposed_action_hash or "")
    dup = proposed in priors and bool(proposed)
    signals = ["ACTION_REPLAY_DETECTED"] if dup else []
    r = {
        "action_replay_guard_version": ACTION_REPLAY_VERSION,
        "action_replay_guard_id": "arg-" + _sha({
            "wi": write_intent_id, "p": proposed})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "idempotency_key": str(idempotency_key or ""),
        "prior_action_hashes": priors, "proposed_action_hash": proposed,
        "semantic_duplicate_detected": dup,
        "replay_status": "REPLAY_DETECTED" if dup else "UNIQUE",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["action_replay_guard_hash"] = _core_hash(
        r, "action_replay_guard_hash", "signal")
    r["_signals"] = signals
    return r


def build_authority_resurrection_guard(*, tenant_id, write_intent_id, stx,
                                     consumed_authority_refs, approval_refs,
                                     token_like_refs, credential_like_refs,
                                     resurrected) -> dict:
    consumed = sorted(set(map(str, _as_list(consumed_authority_refs))))
    approvals = sorted(set(map(str, _as_list(approval_refs))))
    tokens = sorted(set(map(str, _as_list(token_like_refs))))
    creds = sorted(set(map(str, _as_list(credential_like_refs))))
    # Resurrection: any consumed authority re-presented as reusable, or any
    # token-like/credential-like bearer reuse.
    reused = [a for a in approvals if a in consumed]
    detected = bool(resurrected) or bool(reused) or bool(tokens) or bool(creds)
    signals = ["AUTHORITY_RESURRECTION_DETECTED"] if detected else []
    r = {
        "authority_resurrection_guard_version": AUTH_RESURRECTION_VERSION,
        "authority_resurrection_guard_id": "aug-" + _sha({
            "wi": write_intent_id, "c": consumed})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "consumed_authority_refs": consumed, "approval_refs": approvals,
        "token_like_refs": tokens, "credential_like_refs": creds,
        "reused_consumed_refs": sorted(reused),
        "resurrected_authority_detected": detected,
        "approval_is_reusable_bearer": False,
        "certificate_is_reusable_bearer": False,
        "placeholder_is_token": False,
        "guard_status": "RESURRECTION_DETECTED" if detected else "CLEAN",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["authority_resurrection_guard_hash"] = _core_hash(
        r, "authority_resurrection_guard_hash", "signal")
    r["_signals"] = signals
    return r


def build_rollback_simulation(*, tenant_id, write_intent_id, stx, draft,
                            rollback_feasible=True) -> dict:
    steps = [{"undo_field": d["field_path"], "reversible": True}
             for d in draft.get("proposed_deltas", [])]
    signals = [] if rollback_feasible else ["ROLLBACK_SIMULATION_FAILED"]
    r = {
        "rollback_simulation_version": ROLLBACK_SIM_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "undo_steps": steps, "all_reversible": rollback_feasible,
        "simulated_only": True, "executed": False,
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["rollback_simulation_hash"] = _core_hash(
        r, "rollback_simulation_hash", "signal")
    r["_signals"] = signals
    return r


def build_compensation_plan(*, tenant_id, write_intent_id, stx, draft,
                          compensation_gaps=0) -> dict:
    actions = [{"compensating_action": "REVERSE_" + d["field_path"],
                "planned_only": True}
               for d in draft.get("proposed_deltas", [])]
    gaps = _int(compensation_gaps)
    signals = ["COMPENSATION_GAP_DETECTED"] if gaps > 0 else []
    r = {
        "compensation_plan_version": COMPENSATION_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "compensating_actions": actions, "compensation_gap_count": gaps,
        "plan_only": True, "executed": False,
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["compensation_plan_hash"] = _core_hash(
        r, "compensation_plan_hash", "signal")
    r["_signals"] = signals
    return r


def build_semantic_rollback_fence(*, tenant_id, write_intent_id, stx,
                                checkpoint_refs, restore_refs, prior_effect_refs,
                                proposed_effect_refs, replay_guard,
                                resurrection_guard) -> dict:
    action_replay_risk = replay_guard.get("semantic_duplicate_detected", False)
    authority_resurrection_risk = resurrection_guard.get(
        "resurrected_authority_detected", False)
    signals = []
    if action_replay_risk:
        signals.append("SEMANTIC_ROLLBACK_ATTACK_DETECTED")
    if authority_resurrection_risk:
        signals.append("AUTHORITY_RESURRECTION_DETECTED")
    r = {
        "semantic_rollback_fence_version": ROLLBACK_FENCE_VERSION,
        "semantic_rollback_fence_id": "src-" + _sha({
            "wi": write_intent_id, "stx": stx["semantic_transaction_id"]})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "checkpoint_refs": sorted(set(map(str, _as_list(checkpoint_refs)))),
        "restore_refs": sorted(set(map(str, _as_list(restore_refs)))),
        "prior_effect_refs": sorted(set(map(str, _as_list(prior_effect_refs)))),
        "proposed_effect_refs": sorted(set(map(str,
                                              _as_list(proposed_effect_refs)))),
        "semantic_equivalence_hash": _sha({
            "prior": sorted(set(map(str, _as_list(prior_effect_refs)))),
            "proposed": sorted(set(map(str, _as_list(proposed_effect_refs))))}),
        "action_replay_risk": action_replay_risk,
        "authority_resurrection_risk": authority_resurrection_risk,
        "fence_executes_rollback": False, "fence_calls_external": False,
        "fence_status": "FENCED" if not signals else "ATTACK_RISK",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["semantic_rollback_fence_hash"] = _core_hash(
        r, "semantic_rollback_fence_hash", "signal")
    r["_signals"] = signals
    return r


def build_rollback_replay_equivalence(*, tenant_id, write_intent_id, stx,
                                    rollback_sim, tx_replay, replay_guard,
                                    force_mismatch=False) -> dict:
    rollback_hash = rollback_sim["rollback_simulation_hash"]
    replay_hash = tx_replay["semantic_transaction_replay_hash"]
    idem_hash = replay_guard["action_replay_guard_hash"]
    # Equivalence holds when replay is consistent AND no duplicate/authority
    # resurrection is introduced by the rollback.
    mismatch_reasons = []
    if force_mismatch:
        mismatch_reasons.append("FORCED_REPLAY_MISMATCH")
    if not tx_replay.get("replay_consistent", True):
        mismatch_reasons.append("SEMANTIC_TRANSACTION_REPLAY_MISMATCH")
    if replay_guard.get("semantic_duplicate_detected"):
        mismatch_reasons.append("ROLLBACK_DUPLICATES_EFFECT")
    matched = not mismatch_reasons
    signals = [] if matched else ["ROLLBACK_REPLAY_EQUIVALENCE_FAILED"]
    r = {
        "rollback_replay_equivalence_version": ROLLBACK_EQUIV_VERSION,
        "rollback_replay_equivalence_id": "rre-" + _sha({
            "wi": write_intent_id, "r": rollback_hash})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "rollback_simulation_hash": rollback_hash,
        "semantic_transaction_replay_hash": replay_hash,
        "idempotency_guard_hash": idem_hash,
        "equivalence_status": "EQUIVALENT" if matched else "MISMATCH",
        "mismatch_reasons": mismatch_reasons,
        "rollback_resurrects_authority": False,
        "rollback_duplicates_effect": replay_guard.get(
            "semantic_duplicate_detected", False),
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["rollback_replay_equivalence_hash"] = _core_hash(
        r, "rollback_replay_equivalence_hash", "signal")
    r["_signals"] = signals
    return r


# --- Concurrent draft conflict graph + oracle (v4) -------------------------
def build_concurrent_draft_conflict_graph(*, tenant_id, write_intent_id, draft,
                                        related_write_intents) -> dict:
    my_fields = {d["field_path"] for d in draft.get("proposed_deltas", [])}
    my_target = draft.get("target_entity_id", "")
    my_obl = set(draft.get("obligation_ids", []))
    my_ev = set(draft.get("evidence_refs", []))
    my_promises = set(draft.get("customer_promise_ids", []))
    nodes = [{"node_id": "wi:" + write_intent_id,
              "node_type": "WRITE_INTENT_DRAFT"},
             {"node_id": "target:" + my_target, "node_type": "TARGET_ENTITY"}]
    edges = [{"from": "wi:" + write_intent_id, "to": "target:" + my_target,
              "edge_type": "PROPOSES_WRITE"}]
    blocking, review = [], []
    for r in _as_list(related_write_intents):
        r = r or {}
        # Cross-tenant drafts are excluded entirely.
        if r.get("tenant_id") not in (None, tenant_id):
            continue
        other_id = str(r.get("write_intent_id", ""))
        if not other_id or other_id == write_intent_id:
            continue
        other_fields = set(map(str, _as_list(r.get("field_paths"))))
        other_target = str(r.get("target_entity_id", ""))
        other_obl = set(map(str, _as_list(r.get("obligation_ids"))))
        other_ev = set(map(str, _as_list(r.get("evidence_refs"))))
        other_promises = set(map(str, _as_list(r.get("customer_promise_ids"))))
        classes = []
        if other_target and other_target == my_target:
            classes.append("SAME_TARGET_WRITE")
        if my_fields & other_fields:
            classes.append("OVERLAPPING_FIELD_DELTA")
        if my_ev & other_ev:
            classes.append("EVIDENCE_MUTATION_CONFLICT")
        if my_obl & other_obl:
            classes.append("OBLIGATION_CONFLICT")
        if my_promises & other_promises:
            classes.append("CUSTOMER_PROMISE_CONFLICT")
        if not classes:
            continue
        nodes.append({"node_id": "wi:" + other_id,
                      "node_type": "WRITE_INTENT_DRAFT"})
        # Same-target OR overlapping-field OR evidence conflict is BLOCKING;
        # obligation/promise overlap alone requires review.
        hard = {"SAME_TARGET_WRITE", "OVERLAPPING_FIELD_DELTA",
                "EVIDENCE_MUTATION_CONFLICT"}
        edge_type = "BLOCKS_FUTURE_READINESS" if (set(classes) & hard) \
            else "REQUIRES_REVIEW"
        edges.append({"from": "wi:" + write_intent_id, "to": "wi:" + other_id,
                      "edge_type": edge_type, "conflict_classes": classes})
        entry = {"other_write_intent_id": other_id, "conflict_classes": classes}
        if edge_type == "BLOCKS_FUTURE_READINESS":
            blocking.append(entry)
        else:
            review.append(entry)
    signals = []
    if blocking:
        signals.append("CONCURRENT_DRAFT_CONFLICT_BLOCKING")
    elif review:
        signals.append("CONCURRENT_DRAFT_CONFLICT_REVIEW")
    g = {
        "concurrent_draft_conflict_graph_version": CONFLICT_GRAPH_VERSION,
        "concurrent_draft_conflict_graph_id": "cfg-" + _sha({
            "wi": write_intent_id})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "related_write_intent_ids": sorted({str((r or {}).get(
            "write_intent_id", "")) for r in _as_list(related_write_intents)
            if (r or {}).get("write_intent_id")}),
        "nodes": nodes, "edges": edges,
        "blocking_conflicts": blocking, "review_conflicts": review,
        "blocking_count": len(blocking), "review_count": len(review),
        "graph_status": "BLOCKING" if blocking else ("REVIEW" if review else
                                                     "CLEAR"),
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    g["concurrent_draft_conflict_graph_hash"] = _core_hash(
        g, "concurrent_draft_conflict_graph_hash", "signal")
    g["_signals"] = signals
    return g


def build_transaction_conflict_oracle(*, tenant_id, write_intent_id, stx,
                                    conflict_graph) -> dict:
    classes = sorted({c for e in conflict_graph.get("edges", [])
                      for c in e.get("conflict_classes", [])})
    # Any conflict class not in the known set is fail-closed to BLOCK.
    unknown = [c for c in classes if c not in CONFLICT_CLASSES]
    signals = []
    if conflict_graph.get("blocking_conflicts") or unknown:
        decision = "BLOCK_FUTURE_READINESS"
        signals.append("TRANSACTION_CONFLICT_ORACLE_REJECTED")
    elif conflict_graph.get("review_conflicts"):
        decision = "NEEDS_REVIEW"
        signals.append("TRANSACTION_CONFLICT_ORACLE_NEEDS_REVIEW")
    else:
        decision = "NO_CONFLICT"
    dominant = None
    if conflict_graph.get("blocking_conflicts"):
        dominant = conflict_graph["blocking_conflicts"][0]["conflict_classes"][0]
    elif unknown:
        dominant = unknown[0]
    o = {
        "transaction_conflict_oracle_version": CONFLICT_ORACLE_VERSION,
        "transaction_conflict_oracle_id": "tco-" + _sha({
            "wi": write_intent_id})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "conflict_graph_hash": conflict_graph[
            "concurrent_draft_conflict_graph_hash"],
        "conflict_classes": classes, "unknown_conflict_classes": unknown,
        "oracle_decision": decision, "dominant_conflict_reason": dominant,
        "oracle_status": decision,
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    o["transaction_conflict_oracle_hash"] = _core_hash(
        o, "transaction_conflict_oracle_hash", "signal")
    o["_signals"] = signals
    return o


# --- State-witness quorum vector (v4) --------------------------------------
def build_state_witness_quorum(*, tenant_id, write_intent_id, stx, risk_tier,
                             observed_witnesses, policy_epoch, policy) -> dict:
    pol = policy or DEFAULT_POLICY
    high_risk = str(risk_tier or "LOW").upper() == "HIGH"
    required_classes = sorted(HIGH_RISK_WITNESS_CLASSES) if high_risk else \
        sorted({"SOURCE_STATE_HASH"})
    required_count = pol.get("min_state_witness_quorum", 3) if high_risk else 1
    observed, observed_hashes, stale = [], [], []
    for w in _as_list(observed_witnesses):
        w = w or {}
        wc = str(w.get("witness_class", "")).upper()
        if wc not in WITNESS_CLASSES:
            continue
        wepoch = _int(w.get("epoch"), _int(policy_epoch))
        if policy_epoch is not None and wepoch < _int(policy_epoch):
            stale.append(wc)
            continue
        observed.append(wc)
        observed_hashes.append(str(w.get("witness_hash", "")))
    observed = sorted(set(observed))
    missing = sorted(set(required_classes) - set(observed))
    satisfied = (len(observed) >= required_count) and not missing
    signals = []
    if not satisfied:
        signals.append("STATE_WITNESS_QUORUM_MISSING")
    if stale:
        # Stale witness creates revalidation debt (does not silently pass).
        signals.append("STATE_WITNESS_STALE")
    q = {
        "state_witness_quorum_version": WITNESS_QUORUM_VERSION,
        "state_witness_quorum_id": "swq-" + _sha({
            "wi": write_intent_id, "rt": risk_tier})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "risk_tier": "HIGH" if high_risk else "LOW",
        "required_witness_count": required_count,
        "required_witness_classes": required_classes,
        "observed_witnesses": observed,
        "observed_witness_hashes": observed_hashes,
        "stale_witness_classes": sorted(set(stale)),
        "missing_witness_classes": missing, "quorum_satisfied": satisfied,
        "quorum_executes": False,
        "quorum_status": "SATISFIED" if satisfied else "MISSING",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    q["state_witness_quorum_hash"] = _core_hash(
        q, "state_witness_quorum_hash", "signal")
    q["_signals"] = signals
    return q


# --- Contestability / obligation / evidence (v3) ---------------------------
def build_contestability_window(*, tenant_id, write_intent_id, stx,
                              objections, window_open=True) -> dict:
    objs = [{"objection_id": str((o or {}).get("objection_id", i)),
             "resolved": bool((o or {}).get("resolved"))}
            for i, o in enumerate(_as_list(objections))]
    unresolved = [o for o in objs if not o["resolved"]]
    signals = ["CONTESTATION_UNRESOLVED"] if unresolved else []
    r = {
        "contestability_window_version": CONTESTABILITY_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "objections": objs, "unresolved_objections": unresolved,
        "window_open": bool(window_open),
        "contestability_required_before_future_commit": True,
        "contestability_status": "CLEAR" if not unresolved else "UNRESOLVED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["contestability_window_hash"] = _core_hash(
        r, "contestability_window_hash", "signal")
    r["_signals"] = signals
    return r


def build_obligation_containment(*, tenant_id, write_intent_id, stx, draft,
                               obligation_states) -> dict:
    states = {str((o or {}).get("obligation_id", "")):
              bool((o or {}).get("contained"))
              for o in _as_list(obligation_states)}
    uncontained = [oid for oid in draft.get("obligation_ids", [])
                   if not states.get(oid, False)]
    signals = ["OBLIGATION_CONTAINMENT_FAILED"] if uncontained else []
    r = {
        "obligation_containment_version": OBLIGATION_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "obligation_ids": draft.get("obligation_ids", []),
        "uncontained_obligation_ids": uncontained,
        "all_contained": not uncontained,
        "obligation_containment_required": True,
        "containment_status": "CONTAINED" if not uncontained else "UNCONTAINED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["obligation_containment_hash"] = _core_hash(
        r, "obligation_containment_hash", "signal")
    r["_signals"] = signals
    return r


def build_evidence_preservation(*, tenant_id, write_intent_id, stx, draft,
                              destructive_repair=False,
                              triggering_evidence_preserved=True) -> dict:
    signals = []
    if not triggering_evidence_preserved:
        signals.append("EVIDENCE_PRESERVATION_FAILED")
    if destructive_repair:
        signals.append("EVIDENCE_DESTRUCTIVE_REPAIR_DETECTED")
    r = {
        "evidence_preservation_version": EVIDENCE_PRESERVATION_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "evidence_refs": draft.get("evidence_refs", []),
        "triggering_evidence_preserved": bool(triggering_evidence_preserved),
        "destructive_repair_detected": bool(destructive_repair),
        "repair_is_evidence_preserving": not destructive_repair,
        "preservation_status": "PRESERVED" if not signals else "VIOLATED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["evidence_preservation_hash"] = _core_hash(
        r, "evidence_preservation_hash", "signal")
    r["_signals"] = signals
    return r


def build_transaction_invariants(*, tenant_id, write_intent_id, stx, draft,
                               boundary, invariant_violations=0) -> dict:
    v = _int(invariant_violations)
    signals = ["TRANSACTION_INVARIANT_FAILED"] if v > 0 else []
    r = {
        "transaction_invariants_version": TX_INVARIANT_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "invariant_checks": ["ATOMIC_BOUNDARY", "NO_PARTIAL_EFFECT",
                             "DETERMINISTIC_DELTA", "SCOPE_CONTAINED"],
        "invariant_violation_count": v, "all_invariants_hold": v == 0,
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["transaction_invariants_hash"] = _core_hash(
        r, "transaction_invariants_hash", "signal")
    r["_signals"] = signals
    return r


def build_semantic_transaction_replay(*, tenant_id, write_intent_id, stx,
                                    draft, replay_consistent=True) -> dict:
    replay_hash = _sha({"stx": stx["semantic_transaction_id"],
                        "deltas": draft.get("proposed_deltas"),
                        "ops": stx.get("boundary_operations")})
    signals = [] if replay_consistent else ["SEMANTIC_TRANSACTION_REPLAY_MISMATCH"]
    r = {
        "semantic_transaction_replay_version": TX_REPLAY_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "semantic_transaction_replay_hash": replay_hash,
        "replay_consistent": bool(replay_consistent),
        "replay_status": "CONSISTENT" if replay_consistent else "MISMATCH",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["_replay_wrapper_hash"] = _core_hash(r, "_replay_wrapper_hash", "signal")
    r["_signals"] = signals
    return r


# --- Approval binding / meaningful judgment / dual control (v2) -------------
def build_approval_requirement(*, tenant_id, write_intent_id, draft,
                             risk_tier) -> dict:
    high = str(risk_tier or "LOW").upper() == "HIGH"
    r = {
        "approval_requirement_version": APPROVAL_REQ_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "human_approval_required_before_future_commit": True,
        "meaningful_human_judgment_required": True,
        "dual_control_required": high,
        "required_acknowledgements": sorted({
            "ACK_DRAFT_ONLY_NO_EXECUTION", "ACK_FUTURE_COMMIT_SEPARATE",
            "ACK_ESCROW_NON_EXECUTING", "ACK_REVIEWED_SHADOW_DELTAS"}),
        "approval_does_not_execute": True,
        "honesty_labels": HONESTY_LABELS,
    }
    r["approval_requirement_hash"] = _core_hash(r, "approval_requirement_hash")
    r["_signals"] = []
    return r


def build_approval_binding(*, tenant_id, write_intent_id, draft, requirement,
                         approvals, requester_id, dual_control_required) -> dict:
    apprs = []
    for a in _as_list(approvals):
        a = a or {}
        apprs.append({
            "approver_id": str(a.get("approver_id", "")),
            "approver_role": str(a.get("approver_role", "")),
            "is_requester": bool(a.get("is_requester")) or (
                str(a.get("approver_id", "")) == str(requester_id or "")),
            "server_verified": bool(a.get("server_verified")),
            "challenge_passed": bool(a.get("challenge_passed")),
            "viewed_package_hash": a.get("viewed_package_hash"),
            "acknowledgements": {k: bool(v) for k, v in
                                 (a.get("acknowledgements") or {}).items()},
        })
    signals = []
    valid_apprs = [a for a in apprs if not a["is_requester"] and a[
        "server_verified"]]
    if not apprs:
        signals.append("APPROVAL_MISSING")
    elif any(a["is_requester"] for a in apprs) and not valid_apprs:
        signals.append("SELF_APPROVAL_DETECTED")
    elif not any(a["server_verified"] for a in apprs):
        signals.append("APPROVAL_NOT_SERVER_VERIFIED")
    if dual_control_required and len(valid_apprs) < 2:
        signals.append("DUAL_CONTROL_MISSING")
    r = {
        "approval_binding_version": APPROVAL_BIND_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "approval_requirement_hash": requirement["approval_requirement_hash"],
        "approvals": apprs, "valid_independent_approvals": len(valid_apprs),
        "requester_id": str(requester_id or ""),
        "dual_control_required": bool(dual_control_required),
        "approval_binds_future_commit_only": True,
        "approval_does_not_execute": True,
        "binding_status": "BOUND" if not signals else "INCOMPLETE",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["approval_binding_hash"] = _core_hash(r, "approval_binding_hash", "signal")
    r["_signals"] = signals
    return r


def build_meaningful_judgment(*, tenant_id, write_intent_id, binding, draft,
                            review_package) -> dict:
    apprs = binding.get("approvals", [])
    # Meaningful judgment: at least one independent approver challenged AND
    # viewed the exact review content AND acknowledged draft-only semantics.
    # Binds the content-addressed digest so a stale hash (viewed an OLD draft
    # before the payload changed) fails closed.
    pkg_hash = review_package["review_package_hash"]
    content_digest = review_package["review_content_digest"]
    meaningful = any(
        (not a["is_requester"]) and a["server_verified"] and
        a["challenge_passed"] and a.get("viewed_package_hash") in (
            content_digest, pkg_hash) and
        all(a["acknowledgements"].get(ack) for ack in
            ["ACK_DRAFT_ONLY_NO_EXECUTION", "ACK_FUTURE_COMMIT_SEPARATE"])
        for a in apprs)
    # Only evaluate meaningfulness once an approval is actually present + valid;
    # otherwise the approval signals dominate.
    has_candidate = any((not a["is_requester"]) and a["server_verified"]
                        for a in apprs)
    signals = ["MEANINGFUL_JUDGMENT_FAILED"] if (has_candidate and not
                                                 meaningful) else []
    r = {
        "meaningful_judgment_version": MEANINGFUL_JUDGMENT_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "review_package_hash": pkg_hash,
        "meaningful_judgment_present": meaningful,
        "rubber_stamp_detected": has_candidate and not meaningful,
        "judgment_status": "MEANINGFUL" if meaningful else "INSUFFICIENT",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["meaningful_judgment_hash"] = _core_hash(
        r, "meaningful_judgment_hash", "signal")
    r["_signals"] = signals
    return r


def build_review_package(*, tenant_id, write_intent_id, draft, stx, shadow,
                       rollback_sim, compensation) -> dict:
    r = {
        "review_package_version": REVIEW_PACKAGE_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "write_intent_draft_hash": draft["write_intent_draft_hash"],
        "semantic_transaction_hash": stx["semantic_transaction_hash"],
        "shadow_state_delta_graph_hash": shadow[
            "shadow_state_delta_graph_hash"],
        "rollback_simulation_hash": rollback_sim["rollback_simulation_hash"],
        "compensation_plan_hash": compensation["compensation_plan_hash"],
        "target_entity_type": draft["target_entity_type"],
        "delta_count": len(draft["proposed_deltas"]),
        "blast_radius_size": shadow["blast_radius_size"],
        "presents_draft_only": True, "presents_no_execution": True,
        # Content-addressed digest of exactly what a human reviews: independent
        # of the per-request write_intent_id, so an approval that viewed this
        # content stays valid across re-preparations of the same draft. This is
        # what meaningful-human-judgment binds to.
        "review_content_digest": _sha({
            "target_type": draft["target_entity_type"],
            "target_id": draft["target_entity_id"],
            "intent": draft["intent"], "deltas": draft["proposed_deltas"],
            "obligations": draft["obligation_ids"],
            "evidence": draft["evidence_refs"],
            "promises": draft["customer_promise_ids"],
            "blast_radius_size": shadow["blast_radius_size"]}),
        "honesty_labels": HONESTY_LABELS,
    }
    r["review_package_hash"] = _core_hash(r, "review_package_hash")
    r["_signals"] = []
    return r


# --- Future commit gate contract placeholder + non-existence proof (v4) ----
def build_future_commit_gate_contract(*, tenant_id, write_intent_id, stx,
                                    revalidation_debt, witness_quorum,
                                    conflict_oracle, contestability, obligation,
                                    commit_endpoint_present=False,
                                    commit_capability_present=False) -> dict:
    signals = []
    if commit_endpoint_present or commit_capability_present:
        signals.append("COMMIT_GATE_ENDPOINT_PRESENT")
    c = {
        "future_commit_gate_contract_version": COMMIT_GATE_CONTRACT_VERSION,
        "future_commit_gate_contract_id": "fcg-" + _sha({
            "wi": write_intent_id})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "placeholder_only": True,
        "required_revalidations": revalidation_debt.get(
            "required_before_future_commit", []),
        "required_approvals": ["INDEPENDENT_HUMAN_APPROVAL",
                              "MEANINGFUL_JUDGMENT"],
        "required_state_witness_quorum": witness_quorum[
            "required_witness_classes"],
        "required_conflict_check": conflict_oracle["oracle_decision"],
        "required_contestability_state": contestability["contestability_status"],
        "required_obligation_state": obligation["containment_status"],
        "commit_endpoint_present": bool(commit_endpoint_present),
        "commit_capability_present": bool(commit_capability_present),
        "contract_executes": False,
        "contract_status": "PLACEHOLDER" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    c["future_commit_gate_contract_hash"] = _core_hash(
        c, "future_commit_gate_contract_hash", "signal")
    c["_signals"] = signals
    return c


def build_commit_gate_non_existence_proof(*, tenant_id, write_intent_id,
                                        detected_endpoints=None,
                                        detected_capabilities=None,
                                        detected_activation_paths=None) -> dict:
    endpoints = sorted(set(map(str, _as_list(detected_endpoints))))
    caps = sorted(set(map(str, _as_list(detected_capabilities))))
    acts = sorted(set(map(str, _as_list(detected_activation_paths))))
    signals = []
    if endpoints or caps or acts:
        signals.append("COMMIT_GATE_ENDPOINT_PRESENT")
    p = {
        "commit_gate_non_existence_proof_version": COMMIT_GATE_NONEXIST_VERSION,
        "commit_gate_non_existence_proof_id": "cne-" + _sha({
            "wi": write_intent_id})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "surfaces_checked": list(COMMIT_SURFACES),
        "commit_endpoints_detected": endpoints,
        "commit_capabilities_detected": caps,
        "activation_paths_detected": acts,
        "no_commit_endpoint_exists": not endpoints,
        "no_commit_capability_exists": not caps,
        "no_activation_path_exists": not acts,
        "proof_status": "NON_EXISTENT" if not signals else "ENDPOINT_PRESENT",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    p["commit_gate_non_existence_hash"] = _core_hash(
        p, "commit_gate_non_existence_hash", "signal")
    p["_signals"] = signals
    return p


def build_commit_non_execution(*, tenant_id, write_intent_id, stx,
                             attempt_markers) -> dict:
    markers = {k: bool(v) for k, v in (attempt_markers or {}).items() if v}
    marker_to_signal = {
        "commit": "COMMIT_ATTEMPT_DETECTED",
        "provider_call": "PROVIDER_CALL_ATTEMPT",
        "mcp_call": "MCP_CALL_ATTEMPT", "llm_call": "LLM_CALL_ATTEMPT",
        "token_issue": "TOKEN_ISSUANCE_ATTEMPT",
        "credential_read": "CREDENTIAL_READ_DETECTED",
        "customer_message": "CUSTOMER_MESSAGE_ATTEMPT",
        "payment": "PAYMENT_ATTEMPT", "crm_mutation": "CRM_MUTATION_ATTEMPT",
        "evidence_mutation": "EVIDENCE_MUTATION_ATTEMPT",
        "data_export": "DATA_EXPORT_ATTEMPT",
    }
    signals = sorted({marker_to_signal[k] for k in markers
                      if k in marker_to_signal})
    r = {
        "commit_non_execution_version": COMMIT_NON_EXEC_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "detected_attempt_markers": sorted(markers.keys()),
        "commit_executed": False, "any_external_effect": False,
        "non_execution_status": "NON_EXECUTING" if not signals else
        "ATTEMPT_DETECTED", "signals_detected": signals,
        "honesty_labels": HONESTY_LABELS,
    }
    r["commit_non_execution_hash"] = _core_hash(
        r, "commit_non_execution_hash", "signals_detected")
    r["_signals"] = signals
    return r


# --- Escrowed commit-readiness certificate (v4) ----------------------------
def build_escrowed_commit_readiness(*, tenant_id, write_intent_id, stx, capsule,
                                  witness_quorum, revalidation_debt,
                                  conflict_oracle, approval_binding,
                                  meaningful_judgment, contestability,
                                  obligation, evidence_preservation,
                                  rollback_fence, expiry_policy, tamper,
                                  outbox_quarantine) -> dict:
    factors = {
        "escrow_valid": capsule["escrow_status"] == "ESCROWED",
        "escrow_not_tampered": not tamper["tamper_detected"],
        "escrow_not_expired": expiry_policy["expiry_status"] == "VALID",
        "revalidation_debt_cleared": revalidation_debt["debt_status"] ==
        "CLEARED",
        "state_witness_quorum_satisfied": witness_quorum["quorum_satisfied"],
        "no_blocking_conflict": conflict_oracle["oracle_decision"] ==
        "NO_CONFLICT",
        "approval_bound": approval_binding["binding_status"] == "BOUND",
        "meaningful_judgment": meaningful_judgment["meaningful_judgment_present"],
        "contestability_clear": contestability["contestability_status"] ==
        "CLEAR",
        "obligations_contained": obligation["containment_status"] ==
        "CONTAINED",
        "evidence_preserved": evidence_preservation["preservation_status"] ==
        "PRESERVED",
        "rollback_fence_clear": rollback_fence["fence_status"] == "FENCED",
        "effects_quarantined": outbox_quarantine[
            "quarantine_matrix_status"] == "QUARANTINED",
    }
    all_pass = all(factors.values())
    r = {
        "escrowed_commit_readiness_certificate_version": COMMIT_READINESS_VERSION,
        "escrowed_commit_readiness_certificate_id": "ecr-" + _sha({
            "wi": write_intent_id})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "transaction_escrow_hash": capsule["transaction_escrow_hash"],
        "commit_readiness_theorem_hash": _sha({"factors": factors}),
        "transaction_closure_readiness_hash": _sha({
            "reval": revalidation_debt["revalidation_debt_ledger_hash"],
            "conflict": conflict_oracle["transaction_conflict_oracle_hash"]}),
        "state_witness_quorum_hash": witness_quorum["state_witness_quorum_hash"],
        "revalidation_debt_hash": revalidation_debt[
            "revalidation_debt_ledger_hash"],
        "conflict_oracle_hash": conflict_oracle[
            "transaction_conflict_oracle_hash"],
        "readiness_factors": factors,
        "readiness_status": "READY_FOR_FUTURE_COMMIT_ONLY" if all_pass else
        "NOT_READY",
        # Can be true ONLY if all readiness factors pass; NEVER means "commit now".
        "ready_for_future_commit_only": all_pass,
        # MUST always be false in B7.
        "commit_executable_now": False,
        "is_production_signature": False, "certificate_executes": False,
        "certificate_is_bearer_authority": False,
        "certificate_status": "ESCROWED_EVIDENCE_ONLY",
        "honesty_labels": HONESTY_LABELS,
    }
    r["escrowed_commit_readiness_certificate_hash"] = _core_hash(
        r, "escrowed_commit_readiness_certificate_hash")
    r["_signals"] = []
    return r


# --- Transaction readiness non-execution certificate (v4) ------------------
def build_readiness_non_execution(*, tenant_id, write_intent_id, stx,
                                commit_readiness, commit_gate_contract,
                                commit_gate_nonexist, outbox_quarantine,
                                active_commitment, commit_non_execution,
                                escrow_capsule) -> dict:
    negative_claims = {
        "commit_readiness_did_not_execute": True,
        "escrow_did_not_execute": not escrow_capsule.get("escrow_executes",
                                                         False),
        "future_commit_gate_did_not_execute": not commit_gate_contract.get(
            "contract_executes", False),
        "staged_effect_outbox_did_not_release": outbox_quarantine[
            "quarantine_matrix_status"] == "QUARANTINED",
        "active_commitment_record_did_not_activate": not active_commitment[
            "activated"],
        "approval_did_not_execute": True,
        "no_crm_mutation": "CRM_MUTATION_ATTEMPT" not in commit_non_execution[
            "signals_detected"],
        "no_evidence_mutation": "EVIDENCE_MUTATION_ATTEMPT" not in
        commit_non_execution["signals_detected"],
        "no_payment": "PAYMENT_ATTEMPT" not in commit_non_execution[
            "signals_detected"],
        "no_customer_message": "CUSTOMER_MESSAGE_ATTEMPT" not in
        commit_non_execution["signals_detected"],
        "no_export": "DATA_EXPORT_ATTEMPT" not in commit_non_execution[
            "signals_detected"],
        "no_provider_mcp_llm_call": not (
            {"PROVIDER_CALL_ATTEMPT", "MCP_CALL_ATTEMPT", "LLM_CALL_ATTEMPT"} &
            set(commit_non_execution["signals_detected"])),
        "no_token_or_credential_use": not (
            {"TOKEN_ISSUANCE_ATTEMPT", "CREDENTIAL_READ_DETECTED"} &
            set(commit_non_execution["signals_detected"])),
        "commit_gate_does_not_exist": commit_gate_nonexist["proof_status"] ==
        "NON_EXISTENT",
        "commit_not_executable_now": not commit_readiness[
            "commit_executable_now"],
    }
    all_hold = all(negative_claims.values())
    signals = [] if all_hold else ["TRANSACTION_READINESS_NON_EXECUTION_FAILED"]
    r = {
        "transaction_readiness_non_execution_certificate_version":
        READINESS_NONEXEC_VERSION,
        "transaction_readiness_non_execution_certificate_id": "rne-" + _sha({
            "wi": write_intent_id})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "escrowed_commit_readiness_certificate_hash": commit_readiness[
            "escrowed_commit_readiness_certificate_hash"],
        "future_commit_gate_contract_hash": commit_gate_contract[
            "future_commit_gate_contract_hash"],
        "commit_gate_non_existence_hash": commit_gate_nonexist[
            "commit_gate_non_existence_hash"],
        "effect_outbox_quarantine_hash": outbox_quarantine[
            "effect_outbox_quarantine_hash"],
        "active_commitment_record_hash": active_commitment[
            "active_commitment_record_hash"],
        "negative_claims": negative_claims, "all_negative_claims_hold": all_hold,
        "certificate_status": "NON_EXECUTION_CERTIFIED" if all_hold else
        "FAILED", "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["transaction_readiness_non_execution_certificate_hash"] = _core_hash(
        r, "transaction_readiness_non_execution_certificate_hash", "signal")
    r["_signals"] = signals
    return r


# --- Transaction escrow proof bundle extension (v4) ------------------------
def build_transaction_escrow_proof_extension(*, tenant_id, write_intent_id, stx,
                                           reports) -> dict:
    ext = {
        "transaction_escrow_proof_extension_version": TX_ESCROW_PROOF_EXT_VERSION,
        "transaction_escrow_proof_extension_id": "tep-" + _sha({
            "wi": write_intent_id})[:16],
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "semantic_transaction_id": stx["semantic_transaction_id"],
        "transaction_escrow_hash": reports["transaction_escrow_capsule"][
            "transaction_escrow_hash"],
        "escrowed_commit_readiness_certificate_hash": reports[
            "escrowed_commit_readiness_certificate"][
            "escrowed_commit_readiness_certificate_hash"],
        "future_commit_gate_contract_hash": reports[
            "future_commit_gate_contract"]["future_commit_gate_contract_hash"],
        "commit_gate_non_existence_hash": reports[
            "commit_gate_non_existence_proof"]["commit_gate_non_existence_hash"],
        "revalidation_debt_ledger_hash": reports["revalidation_debt_ledger"][
            "revalidation_debt_ledger_hash"],
        "semantic_rollback_fence_hash": reports["semantic_rollback_fence"][
            "semantic_rollback_fence_hash"],
        "action_replay_guard_hash": reports["action_replay_guard"][
            "action_replay_guard_hash"],
        "authority_resurrection_guard_hash": reports[
            "authority_resurrection_guard"]["authority_resurrection_guard_hash"],
        "rollback_replay_equivalence_hash": reports[
            "rollback_replay_equivalence"]["rollback_replay_equivalence_hash"],
        "concurrent_draft_conflict_graph_hash": reports[
            "concurrent_draft_conflict_graph"][
            "concurrent_draft_conflict_graph_hash"],
        "transaction_conflict_oracle_hash": reports[
            "transaction_conflict_oracle"]["transaction_conflict_oracle_hash"],
        "state_witness_quorum_hash": reports["state_witness_quorum"][
            "state_witness_quorum_hash"],
        "effect_outbox_quarantine_hash": reports["effect_outbox_quarantine"][
            "effect_outbox_quarantine_hash"],
        "escrow_expiry_policy_hash": reports["escrow_expiry_policy"][
            "escrow_expiry_policy_hash"],
        "escrow_tamper_evidence_hash": reports["escrow_tamper_evidence"][
            "escrow_tamper_evidence_hash"],
        "transaction_readiness_non_execution_certificate_hash": reports[
            "transaction_readiness_non_execution_certificate"][
            "transaction_readiness_non_execution_certificate_hash"],
        "honesty_labels": HONESTY_LABELS,
    }
    ext["transaction_escrow_proof_extension_hash"] = _core_hash(
        ext, "transaction_escrow_proof_extension_hash")
    ext["_signals"] = []
    return ext


# --- Signal aggregation -----------------------------------------------------
def _wi_signals(ctx):
    """Build every report object and collect their fail-closed signals."""
    tid = ctx["tenant_id"]
    wid = ctx["write_intent_id"]
    b6 = ctx["b6_outcome"]
    reports = {}
    signals = list(_upstream_signals(tenant_id=tid, b6_outcome=b6,
                                     b6_request=ctx.get("b6_request")))

    draft = build_write_intent_draft(
        tenant_id=tid, write_intent_id=wid, b6_outcome=b6,
        target_entity=ctx.get("target_entity"),
        proposed_deltas=ctx.get("proposed_deltas"), intent=ctx.get("intent"),
        obligations=ctx.get("obligations"),
        evidence_refs=ctx.get("evidence_refs"),
        consent_scope=ctx.get("consent_scope"),
        customer_promises=ctx.get("customer_promises"),
        execution_markers=ctx.get("execution_markers"),
        created_at=ctx.get("created_at"))
    reports["write_intent_draft"] = draft

    stx = build_semantic_transaction(
        tenant_id=tid, write_intent_id=wid, draft=draft,
        task_scope=ctx.get("task_scope", "case"),
        boundary_ops=ctx.get("boundary_operations"))
    reports["semantic_transaction"] = stx
    reports["transaction_boundary"] = build_transaction_boundary(
        tenant_id=tid, write_intent_id=wid, stx=stx, draft=draft)

    shadow = build_shadow_state_delta_graph(
        tenant_id=tid, write_intent_id=wid, draft=draft, policy=ctx["policy"])
    reports["shadow_state_delta_graph"] = shadow
    reports["state_delta"] = build_state_delta(
        tenant_id=tid, write_intent_id=wid, draft=draft, shadow=shadow)

    outbox = build_staged_effect_outbox(
        tenant_id=tid, write_intent_id=wid, stx=stx, draft=draft,
        release_attempts=ctx.get("effect_release_attempts", 0))
    reports["staged_effect_outbox"] = outbox
    outbox_q = build_effect_outbox_quarantine(
        tenant_id=tid, write_intent_id=wid, stx=stx, outbox=outbox)
    reports["effect_outbox_quarantine"] = outbox_q

    active = build_active_commitment_placeholder(
        tenant_id=tid, write_intent_id=wid, stx=stx,
        activation_attempts=ctx.get("commitment_activation_attempts", 0))
    reports["active_commitment_record"] = active

    rollback_sim = build_rollback_simulation(
        tenant_id=tid, write_intent_id=wid, stx=stx, draft=draft,
        rollback_feasible=ctx.get("rollback_feasible", True))
    reports["rollback_simulation"] = rollback_sim
    compensation = build_compensation_plan(
        tenant_id=tid, write_intent_id=wid, stx=stx, draft=draft,
        compensation_gaps=ctx.get("compensation_gaps", 0))
    reports["compensation_plan"] = compensation

    review_pkg = build_review_package(
        tenant_id=tid, write_intent_id=wid, draft=draft, stx=stx, shadow=shadow,
        rollback_sim=rollback_sim, compensation=compensation)
    reports["review_package"] = review_pkg

    requirement = build_approval_requirement(
        tenant_id=tid, write_intent_id=wid, draft=draft,
        risk_tier=ctx.get("risk_tier"))
    reports["approval_requirement"] = requirement
    dual = requirement["dual_control_required"] or bool(
        ctx.get("dual_control_required"))
    binding = build_approval_binding(
        tenant_id=tid, write_intent_id=wid, draft=draft, requirement=requirement,
        approvals=ctx.get("approvals"), requester_id=ctx.get("requester_id"),
        dual_control_required=dual)
    reports["approval_binding"] = binding
    meaningful = build_meaningful_judgment(
        tenant_id=tid, write_intent_id=wid, binding=binding, draft=draft,
        review_package=review_pkg)
    reports["meaningful_judgment"] = meaningful

    contestability = build_contestability_window(
        tenant_id=tid, write_intent_id=wid, stx=stx,
        objections=ctx.get("objections"),
        window_open=ctx.get("contestability_window_open", True))
    reports["contestability_window"] = contestability
    obligation = build_obligation_containment(
        tenant_id=tid, write_intent_id=wid, stx=stx, draft=draft,
        obligation_states=ctx.get("obligation_states"))
    reports["obligation_containment"] = obligation
    evidence = build_evidence_preservation(
        tenant_id=tid, write_intent_id=wid, stx=stx, draft=draft,
        destructive_repair=ctx.get("destructive_repair", False),
        triggering_evidence_preserved=ctx.get("triggering_evidence_preserved",
                                              True))
    reports["evidence_preservation"] = evidence

    invariants = build_transaction_invariants(
        tenant_id=tid, write_intent_id=wid, stx=stx, draft=draft,
        boundary=reports["transaction_boundary"],
        invariant_violations=ctx.get("invariant_violations", 0))
    reports["transaction_invariants"] = invariants
    tx_replay = build_semantic_transaction_replay(
        tenant_id=tid, write_intent_id=wid, stx=stx, draft=draft,
        replay_consistent=ctx.get("replay_consistent", True))
    reports["semantic_transaction_replay"] = tx_replay

    # v4: escrow + guards + conflict + witness
    revalidation_debt = build_revalidation_debt_ledger(
        tenant_id=tid, write_intent_id=wid, stx=stx,
        debt_items=ctx.get("debt_items"))
    reports["revalidation_debt_ledger"] = revalidation_debt

    proposed_action_hash = ctx.get("proposed_action_hash") or _sha({
        "wi": wid, "deltas": draft.get("proposed_deltas")})
    replay_guard = build_action_replay_guard(
        tenant_id=tid, write_intent_id=wid, stx=stx,
        idempotency_key=ctx.get("idempotency_key", "idem-" + wid),
        prior_action_hashes=ctx.get("prior_action_hashes"),
        proposed_action_hash=proposed_action_hash)
    reports["action_replay_guard"] = replay_guard
    resurrection = build_authority_resurrection_guard(
        tenant_id=tid, write_intent_id=wid, stx=stx,
        consumed_authority_refs=ctx.get("consumed_authority_refs"),
        approval_refs=ctx.get("approval_refs"),
        token_like_refs=ctx.get("token_like_refs"),
        credential_like_refs=ctx.get("credential_like_refs"),
        resurrected=ctx.get("resurrected_authority", False))
    reports["authority_resurrection_guard"] = resurrection
    fence = build_semantic_rollback_fence(
        tenant_id=tid, write_intent_id=wid, stx=stx,
        checkpoint_refs=ctx.get("checkpoint_refs"),
        restore_refs=ctx.get("restore_refs"),
        prior_effect_refs=ctx.get("prior_effect_refs"),
        proposed_effect_refs=ctx.get("proposed_effect_refs"),
        replay_guard=replay_guard, resurrection_guard=resurrection)
    reports["semantic_rollback_fence"] = fence
    equivalence = build_rollback_replay_equivalence(
        tenant_id=tid, write_intent_id=wid, stx=stx, rollback_sim=rollback_sim,
        tx_replay=tx_replay, replay_guard=replay_guard,
        force_mismatch=ctx.get("rollback_replay_mismatch", False))
    reports["rollback_replay_equivalence"] = equivalence

    conflict_graph = build_concurrent_draft_conflict_graph(
        tenant_id=tid, write_intent_id=wid, draft=draft,
        related_write_intents=ctx.get("related_write_intents"))
    reports["concurrent_draft_conflict_graph"] = conflict_graph
    oracle = build_transaction_conflict_oracle(
        tenant_id=tid, write_intent_id=wid, stx=stx,
        conflict_graph=conflict_graph)
    reports["transaction_conflict_oracle"] = oracle

    witness_quorum = build_state_witness_quorum(
        tenant_id=tid, write_intent_id=wid, stx=stx,
        risk_tier=ctx.get("risk_tier"),
        observed_witnesses=ctx.get("state_witnesses"),
        policy_epoch=ctx.get("policy_epoch"), policy=ctx["policy"])
    reports["state_witness_quorum"] = witness_quorum

    capsule = build_transaction_escrow_capsule(
        tenant_id=tid, write_intent_id=wid, stx=stx, draft=draft,
        approval_binding=binding, obligation=obligation,
        contestability=contestability, revalidation_debt=revalidation_debt,
        shadow=shadow, escrow_created_epoch=ctx.get("escrow_created_epoch", 0),
        escrow_expires_epoch=ctx.get("escrow_expires_epoch",
                                    ctx["policy"].get("escrow_ttl_epochs", 10)),
        escrow_mutable=ctx.get("escrow_mutable", False),
        created_at=ctx.get("created_at"))
    reports["transaction_escrow_capsule"] = capsule
    tamper = build_escrow_tamper_evidence(
        tenant_id=tid, write_intent_id=wid, stx=stx, capsule=capsule,
        observed_escrow_hash=ctx.get("observed_escrow_hash"))
    reports["escrow_tamper_evidence"] = tamper
    expiry = build_escrow_expiry_policy(
        tenant_id=tid, write_intent_id=wid, stx=stx, capsule=capsule,
        current_epoch=ctx.get("current_epoch"), policy=ctx["policy"])
    reports["escrow_expiry_policy"] = expiry

    commit_gate_contract = build_future_commit_gate_contract(
        tenant_id=tid, write_intent_id=wid, stx=stx,
        revalidation_debt=revalidation_debt, witness_quorum=witness_quorum,
        conflict_oracle=oracle, contestability=contestability,
        obligation=obligation,
        commit_endpoint_present=ctx.get("commit_endpoint_present", False),
        commit_capability_present=ctx.get("commit_capability_present", False))
    reports["future_commit_gate_contract"] = commit_gate_contract
    commit_gate_nonexist = build_commit_gate_non_existence_proof(
        tenant_id=tid, write_intent_id=wid,
        detected_endpoints=ctx.get("detected_commit_endpoints"),
        detected_capabilities=ctx.get("detected_commit_capabilities"),
        detected_activation_paths=ctx.get("detected_activation_paths"))
    reports["commit_gate_non_existence_proof"] = commit_gate_nonexist

    commit_non_exec = build_commit_non_execution(
        tenant_id=tid, write_intent_id=wid, stx=stx,
        attempt_markers=ctx.get("attempt_markers"))
    reports["commit_non_execution"] = commit_non_exec

    commit_readiness = build_escrowed_commit_readiness(
        tenant_id=tid, write_intent_id=wid, stx=stx, capsule=capsule,
        witness_quorum=witness_quorum, revalidation_debt=revalidation_debt,
        conflict_oracle=oracle, approval_binding=binding,
        meaningful_judgment=meaningful, contestability=contestability,
        obligation=obligation, evidence_preservation=evidence,
        rollback_fence=fence, expiry_policy=expiry, tamper=tamper,
        outbox_quarantine=outbox_q)
    reports["escrowed_commit_readiness_certificate"] = commit_readiness

    readiness_non_exec = build_readiness_non_execution(
        tenant_id=tid, write_intent_id=wid, stx=stx,
        commit_readiness=commit_readiness,
        commit_gate_contract=commit_gate_contract,
        commit_gate_nonexist=commit_gate_nonexist, outbox_quarantine=outbox_q,
        active_commitment=active, commit_non_execution=commit_non_exec,
        escrow_capsule=capsule)
    reports["transaction_readiness_non_execution_certificate"] = \
        readiness_non_exec

    proof_ext = build_transaction_escrow_proof_extension(
        tenant_id=tid, write_intent_id=wid, stx=stx, reports=reports)
    reports["transaction_escrow_proof_extension"] = proof_ext

    # Collect signals from every report.
    for rep in reports.values():
        signals.extend(rep.get("_signals", []))
    # Renewal is a distinct, softer status than raw expiry when the escrow is
    # otherwise clean: surface it so operators know to renew+revalidate.
    if "ESCROW_EXPIRED" in signals and expiry["renewal_required"]:
        signals.append("ESCROW_RENEWAL_REQUIRED")
    return signals, reports


# --- Fault injection harness ------------------------------------------------
FAULT_CASES = [
    "escrow_means_commit_allowed", "ready_means_execute_now",
    "commit_executable_now_true", "hidden_commit_gate_endpoint",
    "resolve_escrow_and_commit", "release_staged_effect",
    "reuse_old_approval_after_payload_change", "replay_prior_payment_action",
    "restore_consumed_authority", "stale_state_witness",
    "two_conflicting_intents_future_ready", "unquarantined_outbox_item",
    "blocking_conflict_downgraded", "escrow_expired_still_valid",
    "state_witness_quorum_optional", "client_resolved_revalidation_debt",
    "readiness_certificate_as_bearer", "proof_bundle_overrides_blocker",
    "activate_commitment_record", "commit_attempt", "provider_call_injected",
]


def _apply_fault(fault, ctx):
    c = dict(ctx)
    if fault == "escrow_means_commit_allowed":
        c["execution_markers"] = {"resolve_escrow_and_commit": True}
    elif fault == "ready_means_execute_now":
        c["execution_markers"] = {"execute_now": True}
    elif fault == "commit_executable_now_true":
        c["execution_markers"] = {"commit_executable_now": True}
    elif fault == "hidden_commit_gate_endpoint":
        c["detected_commit_endpoints"] = ["WRITE_INTENT_COMMIT_ENDPOINT"]
    elif fault == "resolve_escrow_and_commit":
        c["attempt_markers"] = {"commit": True}
    elif fault == "release_staged_effect":
        c["effect_release_attempts"] = 1
    elif fault == "reuse_old_approval_after_payload_change":
        c["approvals"] = [{"approver_id": "old", "server_verified": True,
                          "viewed_package_hash": "STALE", "challenge_passed":
                          True}]
        c["proposed_deltas"] = list(_as_list(ctx.get("proposed_deltas"))) + [
            {"field_path": "changed.field", "to_value": "x",
             "data_class": "INTERNAL"}]
    elif fault == "replay_prior_payment_action":
        ph = _sha({"wi": ctx["write_intent_id"],
                  "deltas": ctx.get("proposed_deltas")})
        c["prior_action_hashes"] = [ph]
        c["proposed_action_hash"] = ph
    elif fault == "restore_consumed_authority":
        c["consumed_authority_refs"] = ["ap-1"]
        c["approval_refs"] = ["ap-1"]
    elif fault == "stale_state_witness":
        c["policy_epoch"] = 9
        c["state_witnesses"] = [{"witness_class": "SOURCE_STATE_HASH",
                                "witness_hash": "h", "epoch": 1}]
    elif fault == "two_conflicting_intents_future_ready":
        c["related_write_intents"] = [{
            "write_intent_id": "other", "tenant_id": ctx["tenant_id"],
            "target_entity_id": (ctx.get("target_entity") or {}).get(
                "entity_id", "E-1"),
            "field_paths": [d.get("field_path") for d in _as_list(
                ctx.get("proposed_deltas"))]}]
    elif fault == "unquarantined_outbox_item":
        c["effect_release_attempts"] = 2
    elif fault == "blocking_conflict_downgraded":
        c["related_write_intents"] = [{
            "write_intent_id": "other2", "tenant_id": ctx["tenant_id"],
            "target_entity_id": (ctx.get("target_entity") or {}).get(
                "entity_id", "E-1")}]
    elif fault == "escrow_expired_still_valid":
        c["current_epoch"] = 9999
        c["escrow_expires_epoch"] = 1
    elif fault == "state_witness_quorum_optional":
        c["risk_tier"] = "HIGH"
        c["state_witnesses"] = []
    elif fault == "client_resolved_revalidation_debt":
        c["debt_items"] = [{"debt_type": "CONSENT_RECHECK", "resolved": True,
                           "server_verified_resolution": False}]
    elif fault == "readiness_certificate_as_bearer":
        c["token_like_refs"] = ["ecr-bearer"]
    elif fault == "proof_bundle_overrides_blocker":
        c["execution_markers"] = {"commit_executable_now": True}
    elif fault == "activate_commitment_record":
        c["commitment_activation_attempts"] = 1
    elif fault == "commit_attempt":
        c["attempt_markers"] = {"commit": True}
    elif fault == "provider_call_injected":
        c["attempt_markers"] = {"provider_call": True}
    return c


def run_fault_injection_harness(*, tenant_id, write_intent_id, base_ctx) -> dict:
    cases = []
    all_blocked = True
    for fault in FAULT_CASES:
        c = _apply_fault(fault, base_ctx)
        sigs, _ = _wi_signals(c)
        sigs = sorted(set(sigs)) or ["TRANSACTION_ESCROW_DRAFT_CREATED"]
        dom = dominant_signal(sigs)
        status = _status_for_signal(dom)
        blocked = status not in POSITIVE_STATUSES
        if not blocked:
            all_blocked = False
        cases.append({"fault": fault, "dominant_signal": dom,
                      "resulting_status": status, "blocked": blocked})
    h = {
        "write_intent_fault_injection_harness_version": FAULT_HARNESS_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "fault_cases": cases, "fault_case_count": len(cases),
        "all_faults_blocked": all_blocked,
        "harness_status": "ALL_BLOCKED" if all_blocked else "LEAK_DETECTED",
        "honesty_labels": HONESTY_LABELS,
    }
    h["write_intent_fault_injection_harness_hash"] = _core_hash(
        h, "write_intent_fault_injection_harness_hash")
    return h


def build_release_gate(*, tenant_id, write_intent_id, harness) -> dict:
    passed = harness["all_faults_blocked"]
    g = {
        "write_intent_release_gate_version": RELEASE_GATE_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "negative_tests_total": harness["fault_case_count"],
        "negative_tests_blocked": sum(1 for c in harness["fault_cases"]
                                      if c["blocked"]),
        "release_gate_status": "PASSED" if passed else "FAILED",
        "signal": None if passed else "FAULT_INJECTION_RELEASE_GATE_FAILED",
        "honesty_labels": HONESTY_LABELS,
    }
    g["write_intent_release_gate_hash"] = _core_hash(
        g, "write_intent_release_gate_hash", "signal")
    return g


def build_conformance_vector(*, tenant_id, write_intent_id, reports, harness,
                           release_gate) -> dict:
    dims = {
        "write_intent_draft_only": reports["write_intent_draft"].get(
            "draft_only", False),
        "semantic_transaction_draft_only": reports["semantic_transaction"].get(
            "draft_only", False),
        "transaction_escrowed": reports["transaction_escrow_capsule"][
            "escrow_status"] == "ESCROWED",
        "escrow_immutable": reports["transaction_escrow_capsule"][
            "escrow_mutable"] is False,
        "commit_not_executable_now": reports[
            "escrowed_commit_readiness_certificate"][
            "commit_executable_now"] is False,
        "future_commit_gate_placeholder_only": reports[
            "future_commit_gate_contract"]["placeholder_only"] is True,
        "commit_gate_non_existent": reports["commit_gate_non_existence_proof"][
            "no_commit_endpoint_exists"] is True,
        "effects_quarantined": reports["effect_outbox_quarantine"][
            "all_quarantined"] is True,
        "commitment_not_activated": reports["active_commitment_record"][
            "activated"] is False,
        "readiness_non_execution_certified": reports[
            "transaction_readiness_non_execution_certificate"][
            "all_negative_claims_hold"] is True,
        "fault_injection_all_blocked": harness["all_faults_blocked"],
        "release_gate_passed": release_gate["release_gate_status"] == "PASSED",
    }
    conformant = all(dims.values())
    cv = {
        "write_intent_conformance_vector_version": CONFORMANCE_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "dimensions": dims, "conformant": conformant,
        "honesty_labels": HONESTY_LABELS,
    }
    cv["write_intent_conformance_vector_hash"] = _core_hash(
        cv, "write_intent_conformance_vector_hash")
    return cv


def build_proof_bundle(*, tenant_id, write_intent_id, reports, harness,
                     release_gate, status, dominant) -> dict:
    component_hashes = {}
    _HASH_KEYS = {
        "write_intent_draft": "write_intent_draft_hash",
        "semantic_transaction": "semantic_transaction_hash",
        "transaction_boundary": "transaction_boundary_hash",
        "shadow_state_delta_graph": "shadow_state_delta_graph_hash",
        "state_delta": "state_delta_hash",
        "staged_effect_outbox": "staged_effect_outbox_hash",
        "effect_outbox_quarantine": "effect_outbox_quarantine_hash",
        "active_commitment_record": "active_commitment_record_hash",
        "rollback_simulation": "rollback_simulation_hash",
        "compensation_plan": "compensation_plan_hash",
        "review_package": "review_package_hash",
        "approval_requirement": "approval_requirement_hash",
        "approval_binding": "approval_binding_hash",
        "meaningful_judgment": "meaningful_judgment_hash",
        "contestability_window": "contestability_window_hash",
        "obligation_containment": "obligation_containment_hash",
        "evidence_preservation": "evidence_preservation_hash",
        "transaction_invariants": "transaction_invariants_hash",
        "commit_non_execution": "commit_non_execution_hash",
        "revalidation_debt_ledger": "revalidation_debt_ledger_hash",
        "action_replay_guard": "action_replay_guard_hash",
        "authority_resurrection_guard": "authority_resurrection_guard_hash",
        "semantic_rollback_fence": "semantic_rollback_fence_hash",
        "rollback_replay_equivalence": "rollback_replay_equivalence_hash",
        "concurrent_draft_conflict_graph": "concurrent_draft_conflict_graph_hash",
        "transaction_conflict_oracle": "transaction_conflict_oracle_hash",
        "state_witness_quorum": "state_witness_quorum_hash",
        "transaction_escrow_capsule": "transaction_escrow_hash",
        "escrow_tamper_evidence": "escrow_tamper_evidence_hash",
        "escrow_expiry_policy": "escrow_expiry_policy_hash",
        "future_commit_gate_contract": "future_commit_gate_contract_hash",
        "commit_gate_non_existence_proof": "commit_gate_non_existence_hash",
        "escrowed_commit_readiness_certificate":
        "escrowed_commit_readiness_certificate_hash",
        "transaction_readiness_non_execution_certificate":
        "transaction_readiness_non_execution_certificate_hash",
        "transaction_escrow_proof_extension":
        "transaction_escrow_proof_extension_hash",
    }
    for rep_key, hash_key in _HASH_KEYS.items():
        rep = reports.get(rep_key)
        if rep and hash_key in rep:
            component_hashes[hash_key] = rep[hash_key]
    component_hashes["write_intent_fault_injection_harness_hash"] = harness[
        "write_intent_fault_injection_harness_hash"]
    component_hashes["write_intent_release_gate_hash"] = release_gate[
        "write_intent_release_gate_hash"]
    pb = {
        "write_intent_proof_bundle_version": PROOF_BUNDLE_VERSION,
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "component_hashes": component_hashes,
        "component_count": len(component_hashes),
        "resolved_status": status, "dominant_signal": dominant,
        # The proof bundle records the decision; it can NEVER override a blocker.
        "proof_bundle_overrides_blocker": False,
        "transaction_escrow_proof_extension_hash": reports[
            "transaction_escrow_proof_extension"][
            "transaction_escrow_proof_extension_hash"],
        "honesty_labels": HONESTY_LABELS,
    }
    pb["write_intent_proof_bundle_hash"] = _core_hash(
        pb, "write_intent_proof_bundle_hash")
    return pb


# --- Request envelope + orchestration --------------------------------------
def build_write_intent_request_envelope(*, write_intent_id, tenant_id, actor_id,
                                      actor_type, b6_outcome, target_entity,
                                      requested_deltas, intent, created_at) -> dict:
    o = b6_outcome or {}
    te = target_entity or {}
    env = {
        "write_intent_request_envelope_version": REQUEST_VERSION,
        "write_intent_id": write_intent_id, "tenant_id": tenant_id,
        "b6_runtime_request_id": o.get("runtime_request_id"),
        "b6_runtime_decision_hash": o.get("runtime_decision_hash"),
        "b6_proof_bundle_hash": (o.get("runtime_proof_bundle") or {}).get(
            "runtime_proof_bundle_hash"),
        "target_entity_type": str(te.get("entity_type", "")),
        "target_entity_id": str(te.get("entity_id", "")),
        "intent": _norm(intent),
        "requested_delta_paths": sorted({str((d or {}).get("field_path", ""))
                                        for d in _as_list(requested_deltas)}),
        "requested_by_actor_id": actor_id, "requested_by_actor_type": actor_type,
        "is_write": False, "is_commit": False, "is_execution": False,
        "draft_only": True, "created_at": created_at,
    }
    env["write_intent_request_hash"] = _core_hash(
        env, "write_intent_request_hash", "write_intent_id", "created_at",
        "requested_by_actor_id", "requested_by_actor_type")
    return env


def prepare_write_intent_outcome(*, write_intent_id, tenant_id, actor_id,
                               actor_type, envelope, b6_outcome, b6_request=None,
                               target_entity=None, proposed_deltas=None,
                               intent=None, obligations=None, evidence_refs=None,
                               consent_scope=None, customer_promises=None,
                               task_scope="case", boundary_operations=None,
                               risk_tier="LOW", approvals=None,
                               requester_id=None, dual_control_required=False,
                               objections=None, obligation_states=None,
                               contestability_window_open=True,
                               destructive_repair=False,
                               triggering_evidence_preserved=True,
                               invariant_violations=0, replay_consistent=True,
                               rollback_feasible=True, compensation_gaps=0,
                               debt_items=None, prior_action_hashes=None,
                               proposed_action_hash=None, idempotency_key=None,
                               consumed_authority_refs=None, approval_refs=None,
                               token_like_refs=None, credential_like_refs=None,
                               resurrected_authority=False, checkpoint_refs=None,
                               restore_refs=None, prior_effect_refs=None,
                               proposed_effect_refs=None,
                               rollback_replay_mismatch=False,
                               related_write_intents=None, state_witnesses=None,
                               policy_epoch=None, escrow_created_epoch=0,
                               escrow_expires_epoch=None, escrow_mutable=False,
                               observed_escrow_hash=None, current_epoch=None,
                               commit_endpoint_present=False,
                               commit_capability_present=False,
                               detected_commit_endpoints=None,
                               detected_commit_capabilities=None,
                               detected_activation_paths=None,
                               attempt_markers=None, execution_markers=None,
                               effect_release_attempts=0,
                               commitment_activation_attempts=0, policy=None,
                               created_at=None) -> dict:
    """Prepare a draft-only, escrowed write-intent outcome. Runs the full
    deterministic evaluation, the fault-injection harness and the release gate,
    then resolves the fail-closed status. Creates only local draft/escrow
    evidence; performs NO write, NO commit, NO effect release, NO commitment
    activation and NO external effect."""
    pol = dict(DEFAULT_POLICY)
    for k, v in (policy or {}).items():
        if k in DEFAULT_POLICY:
            pol[k] = v
    ctx = {
        "tenant_id": tenant_id, "write_intent_id": write_intent_id,
        "b6_outcome": b6_outcome, "b6_request": b6_request,
        "target_entity": target_entity or {"entity_type": "case",
                                           "entity_id": "E-1"},
        "proposed_deltas": proposed_deltas if proposed_deltas is not None else [
            {"field_path": "status", "from_value": "open", "to_value": "closed",
             "data_class": "INTERNAL"}],
        "intent": intent or "update case status", "obligations": obligations,
        "evidence_refs": evidence_refs, "consent_scope": consent_scope,
        "customer_promises": customer_promises, "task_scope": task_scope,
        "boundary_operations": boundary_operations, "risk_tier": risk_tier,
        "approvals": approvals, "requester_id": requester_id,
        "dual_control_required": dual_control_required, "objections": objections,
        "obligation_states": obligation_states,
        "contestability_window_open": contestability_window_open,
        "destructive_repair": destructive_repair,
        "triggering_evidence_preserved": triggering_evidence_preserved,
        "invariant_violations": invariant_violations,
        "replay_consistent": replay_consistent,
        "rollback_feasible": rollback_feasible,
        "compensation_gaps": compensation_gaps, "debt_items": debt_items,
        "prior_action_hashes": prior_action_hashes,
        "proposed_action_hash": proposed_action_hash,
        "idempotency_key": idempotency_key,
        "consumed_authority_refs": consumed_authority_refs,
        "approval_refs": approval_refs, "token_like_refs": token_like_refs,
        "credential_like_refs": credential_like_refs,
        "resurrected_authority": resurrected_authority,
        "checkpoint_refs": checkpoint_refs, "restore_refs": restore_refs,
        "prior_effect_refs": prior_effect_refs,
        "proposed_effect_refs": proposed_effect_refs,
        "rollback_replay_mismatch": rollback_replay_mismatch,
        "related_write_intents": related_write_intents,
        "state_witnesses": state_witnesses, "policy_epoch": policy_epoch,
        "escrow_created_epoch": escrow_created_epoch,
        "escrow_expires_epoch": escrow_expires_epoch,
        "escrow_mutable": escrow_mutable,
        "observed_escrow_hash": observed_escrow_hash,
        "current_epoch": current_epoch,
        "commit_endpoint_present": commit_endpoint_present,
        "commit_capability_present": commit_capability_present,
        "detected_commit_endpoints": detected_commit_endpoints,
        "detected_commit_capabilities": detected_commit_capabilities,
        "detected_activation_paths": detected_activation_paths,
        "attempt_markers": attempt_markers, "execution_markers":
        execution_markers, "effect_release_attempts": effect_release_attempts,
        "commitment_activation_attempts": commitment_activation_attempts,
        "policy": pol, "created_at": created_at,
    }
    signals, reports = _wi_signals(ctx)

    harness = run_fault_injection_harness(
        tenant_id=tenant_id, write_intent_id=write_intent_id, base_ctx=ctx)
    release_gate = build_release_gate(
        tenant_id=tenant_id, write_intent_id=write_intent_id, harness=harness)
    if release_gate["signal"]:
        signals.append(release_gate["signal"])

    signals = sorted(set(signals))
    if not signals:
        signals = ["TRANSACTION_ESCROW_DRAFT_CREATED"]
    dominant = dominant_signal(signals)
    status = _status_for_signal(dominant)
    decision = _decision_for_status(status)

    conformance = build_conformance_vector(
        tenant_id=tenant_id, write_intent_id=write_intent_id, reports=reports,
        harness=harness, release_gate=release_gate)
    proof_bundle = build_proof_bundle(
        tenant_id=tenant_id, write_intent_id=write_intent_id, reports=reports,
        harness=harness, release_gate=release_gate, status=status,
        dominant=dominant)

    outcome_kind = "TRANSACTION_ESCROW_ONLY" if status == \
        "TRANSACTION_ESCROW_DRAFT_CREATED" else status
    # Strip private signal-carrier keys before returning reports.
    clean_reports = {}
    for k, rep in reports.items():
        if isinstance(rep, dict):
            clean_reports[k] = {kk: vv for kk, vv in rep.items()
                                if kk != "_signals"}
        else:
            clean_reports[k] = rep
    outcome = {
        "write_intent_model_version": WRITE_INTENT_MODEL_VERSION,
        "write_intent_id": write_intent_id, "tenant_id": tenant_id,
        "b6_runtime_request_id": (b6_outcome or {}).get("runtime_request_id"),
        "write_intent_status": status, "write_intent_decision_status": decision,
        "write_intent_outcome_kind": outcome_kind,
        "dominant_signal": dominant,
        "dominant_reason_code": REASON_CODES.get(dominant, ""),
        "all_signals": signals,
        "signal_reason_codes": {s: REASON_CODES.get(s, "") for s in signals},
        "ready_for_future_commit_only": (
            clean_reports["escrowed_commit_readiness_certificate"][
                "ready_for_future_commit_only"] and status ==
            "TRANSACTION_ESCROW_DRAFT_CREATED"),
        "commit_executable_now": False, "is_write": False, "is_commit": False,
        "is_execution": False, "draft_only": True, "escrow_only": True,
        "produced_external_effect": False, "released_effect": False,
        "activated_commitment": False,
        "write_intent_request_hash": (envelope or {}).get(
            "write_intent_request_hash"),
        "decided_by_actor_id": actor_id, "decided_by_actor_type": actor_type,
        "created_at": created_at, "updated_at": created_at,
        "write_intent_fault_injection_harness": harness,
        "write_intent_release_gate_report": release_gate,
        "write_intent_conformance_vector": conformance,
        "write_intent_proof_bundle": proof_bundle,
        "honesty_labels": HONESTY_LABELS,
    }
    outcome.update(clean_reports)
    outcome["write_intent_decision_hash"] = _core_hash(
        outcome, "write_intent_decision_hash", "write_intent_id",
        "decided_by_actor_id", "decided_by_actor_type", "write_intent_state_hash")
    outcome["write_intent_state_hash"] = _sha({
        "write_intent_id": write_intent_id,
        "write_intent_decision_hash": outcome["write_intent_decision_hash"],
        "write_intent_status": status, "dominant_signal": dominant,
        "write_intent_request_hash": (envelope or {}).get(
            "write_intent_request_hash"),
        "proof_bundle_hash": proof_bundle["write_intent_proof_bundle_hash"]})
    return outcome


# --- Event ledger ----------------------------------------------------------
WRITE_INTENT_EVENT_TYPES = {
    "WRITE_INTENT_REQUEST_OPENED", "WRITE_INTENT_OUTCOME_PREPARED",
    "WRITE_INTENT_FAULT_INJECTED", "WRITE_INTENT_OUTCOME_VERIFIED",
}


def build_write_intent_event(*, event_type, tenant_id, write_intent_id, actor_id,
                           actor_type, write_intent_state_hash,
                           previous_event_hash, sequence, detail,
                           created_at) -> dict:
    ev = {
        "write_intent_event_version": WRITE_INTENT_EVENT_VERSION,
        "event_type": event_type, "tenant_id": tenant_id,
        "write_intent_id": write_intent_id, "actor_id": actor_id,
        "actor_type": actor_type,
        "write_intent_state_hash": write_intent_state_hash,
        "previous_event_hash": previous_event_hash or GENESIS,
        "sequence": sequence, "detail": detail or {}, "created_at": created_at,
    }
    ev["event_hash"] = _core_hash(ev, "event_hash")
    return ev
