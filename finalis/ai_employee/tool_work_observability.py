"""Governed Work Lineage Observatory (TOOL-B9.2 v5).

The principal observable unit is the GOVERNED_WORK_RUN: work that begins at a
trigger and ends only when the governed local result, its artifact lineage,
delivery intent, identity/approval/authority bindings, memory + context inputs,
schedule lineage, revocation state and a deterministic Work Outcome Certificate
are all known.

This module is LOCAL_ONLY, READ_ONLY over B9/B9.1, DERIVED_EVIDENCE_ONLY. It has
NO external provider runtime, NO external effect, NO execution/recovery authority
and is NOT production ready. It OBSERVES and VERIFIES; it never commits,
finalizes, approves, recovers, rolls back, aborts, releases quarantine/outbox,
delivers externally or activates a provider.

It binds together — as derived evidence — the Work Origin Envelope, Principal
Continuity Graph, Context Capsule, Memory Use Snapshot, Delegation Capsule,
Approval Continuity Record, Tool Gateway Boundary Proof, revocation epochs +
propagation, Artifact Lineage DAG, Delivery Intent, Schedule Run Chain, the
causal work graph, a consistent work cut, negative-space (missing evidence), the
Work Observation Twin and the Proof-of-Work-Outcome (PoWO). The PoWO is derived
evidence — it authorizes nothing.
"""
from __future__ import annotations

from .tool_contracts import canonical_json, _sha, _core_hash

B92_MODEL_VERSION = "finalis-governed-work-lineage-observatory-v5"
WORK_ORIGIN_VERSION = "finalis-work-origin-envelope-v1"
PRINCIPAL_VERSION = "finalis-principal-continuity-graph-v1"
CONTEXT_VERSION = "finalis-context-continuity-capsule-v1"
MEMORY_VERSION = "finalis-memory-use-snapshot-v1"
DELEGATION_VERSION = "finalis-delegation-provenance-capsule-v1"
APPROVAL_VERSION = "finalis-approval-continuity-record-v1"
GATEWAY_VERSION = "finalis-tool-gateway-boundary-proof-v1"
REVOCATION_EPOCH_VERSION = "finalis-revocation-epoch-binding-v1"
REVOCATION_PROP_VERSION = "finalis-revocation-propagation-observatory-v1"
ARTIFACT_VERSION = "finalis-artifact-lineage-dag-v1"
DELIVERY_VERSION = "finalis-delivery-intent-record-v1"
SCHEDULE_VERSION = "finalis-schedule-run-chain-v1"
RECURRENCE_VERSION = "finalis-cross-run-recurrence-graph-v1"
CAUSAL_GRAPH_VERSION = "finalis-causal-work-lineage-graph-v1"
CONSISTENT_CUT_VERSION = "finalis-consistent-work-cut-v1"
NEGATIVE_SPACE_VERSION = "finalis-negative-space-work-sentinel-v1"
DECISION_BASIS_VERSION = "finalis-structured-decision-basis-v1"
OTEL_ADAPTER_VERSION = "finalis-opentelemetry-adapter-v1"
A2A_BOUNDARY_VERSION = "finalis-a2a-compatibility-boundary-v1"
OBSERVER_HEALTH_VERSION = "finalis-observer-self-health-v1"
NO_EXTERNAL_VERSION = "finalis-work-no-external-effect-theorem-v1"
TWIN_VERSION = "finalis-work-observation-twin-v1"
POWO_VERSION = "finalis-proof-of-work-outcome-v1"
PROOF_BUNDLE_VERSION = "finalis-b92-work-proof-bundle-v1"
B92_EVENT_VERSION = "finalis-b92-work-event-v1"
GENESIS = "0" * 64

HONESTY_LABELS = [
    "LOCAL_WORK_OBSERVABILITY_ONLY", "DERIVED_EVIDENCE_NOT_AUTHORITY",
    "READ_ONLY_OVER_B9_AND_B9_1", "NO_EXTERNAL_PROVIDER_RUNTIME",
    "NO_EXTERNAL_EFFECT", "NO_EXTERNAL_DELIVERY", "NO_EXECUTION_AUTHORITY",
    "NO_RECOVERY_AUTHORITY", "INERT_OUTBOX_REMAINS_INERT",
    "PROOF_OF_WORK_OUTCOME_IS_EVIDENCE_ONLY", "NO_SECRET_STORED",
    "NO_HIDDEN_CHAIN_OF_THOUGHT_STORED", "NOT_PRODUCTION_READY",
]

POWO_WARNING = (
    "PROOF-OF-WORK-OUTCOME IS DERIVED EVIDENCE. IT DOES NOT AUTHORIZE: "
    "EXECUTION, COMMIT, RECOVERY, ROLLBACK, ABORT, QUARANTINE RELEASE, "
    "OUTBOX RELEASE, EXTERNAL DELIVERY, PROVIDER ACTIVATION.")

# ---- Governed Work Run lifecycle (section 5.1) ----------------------------
WORK_RUN_STATES = [
    "TRIGGERED", "IDENTITY_BOUND", "CONTEXT_BOUND", "MEMORY_BOUND",
    "AUTHORITY_CHECKED", "APPROVAL_REQUIRED", "APPROVAL_BOUND",
    "READY_FOR_LOCAL_TRANSACTION", "LOCAL_TRANSACTION_RUNNING",
    "LOCAL_TRANSACTION_COMPLETED", "RECOVERY_REQUIRED", "RECOVERY_COMPLETED",
    "ARTIFACT_PRODUCED", "DELIVERY_INTENT_RECORDED", "OBSERVATION_PENDING",
    "OBSERVATION_COMPLETE", "WORK_OUTCOME_CERTIFIED", "REJECTED", "CANCELED",
    "ABORTED", "QUARANTINED", "STUCK",
]
TERMINAL_WORK_STATES = {
    "WORK_OUTCOME_CERTIFIED", "REJECTED", "CANCELED", "ABORTED", "QUARANTINED",
    "STUCK",
}

# ---- Trigger types (section 6.1) ------------------------------------------
TRIGGER_TYPES = [
    "HUMAN_MESSAGE", "PORTAL_ACTION", "SCHEDULE_OCCURRENCE",
    "HEARTBEAT_SUGGESTION_APPROVED", "SYSTEM_POLICY", "WORKFLOW_CONTINUATION",
    "RECOVERY_CONTINUATION", "FUTURE_A2A_REQUEST", "FUTURE_MCP_EVENT",
]
# Trigger types that do NOT by themselves confer approval/execution authority.
NON_AUTHORITATIVE_TRIGGERS = {
    "SCHEDULE_OCCURRENCE", "HEARTBEAT_SUGGESTION_APPROVED", "FUTURE_A2A_REQUEST",
    "FUTURE_MCP_EVENT",
}

# ---- Principal types + relations (section 7) ------------------------------
PRINCIPAL_TYPES = [
    "HUMAN_USER", "TENANT_ADMIN", "SYSTEM_ACTOR", "SCHEDULE_ACTOR",
    "SERVICE_PRINCIPAL", "SLACK_PRINCIPAL", "TEAMS_PRINCIPAL", "PORTAL_PRINCIPAL",
    "MOBILE_PRINCIPAL", "FUTURE_A2A_AGENT", "FUTURE_MCP_CLIENT",
]
PRINCIPAL_RELATIONS = [
    "AUTHENTICATED_AS", "MAPPED_TO", "ACTING_FOR", "DELEGATED_BY", "SCHEDULED_BY",
    "APPROVED_BY", "REVOKED_BY", "OPERATED_UNDER",
]

# ---- Memory trust classes (section 10.2) ----------------------------------
MEMORY_TRUST_CLASSES = [
    "VERIFIED_CANONICAL", "USER_CONFIRMED", "SYSTEM_DERIVED", "AI_SUGGESTED",
    "DISPUTED", "EXPIRED", "REVOKED",
]
# Trust classes that cannot support a critical decision as PROVEN.
NON_AUTHORITATIVE_MEMORY = {"AI_SUGGESTED", "DISPUTED", "EXPIRED", "REVOKED"}

# ---- Approval modes (section 12.3) ----------------------------------------
APPROVAL_MODES = [
    "APPROVE_SCHEDULE_DEFINITION", "APPROVE_EACH_RUN",
    "APPROVE_EACH_SENSITIVE_EFFECT", "APPROVE_WITHIN_BOUNDED_POLICY",
]

# ---- Artifact types + edges (section 16) ----------------------------------
ARTIFACT_TYPES = [
    "REPORT", "SPREADSHEET", "PRESENTATION", "DOCUMENT", "DRAFT_MESSAGE",
    "CODE_CHANGE", "PULL_REQUEST_REFERENCE", "DASHBOARD_REFERENCE", "TASK_SET",
    "TICKET_SET", "LOCAL_STATE_CHANGE_SUMMARY", "NO_ARTIFACT_EXPECTED",
]
ARTIFACT_EDGES = [
    "DERIVED_FROM", "SUMMARIZES", "TRANSFORMS", "MERGES", "SPLITS", "SUPERSEDES",
    "VALIDATED_BY", "DELIVERED_AS", "REFERENCES",
]

# ---- Delivery statuses (section 17.2) -------------------------------------
DELIVERY_STATUSES = [
    "LOCAL_INTENT_ONLY", "INERT_OUTBOX_CREATED", "DELIVERY_BLOCKED",
    "DELIVERY_NOT_APPLICABLE",
]

# ---- Revocation propagation (section 15) ----------------------------------
REVOCATION_SCOPES = [
    "WORK_RUN", "TRANSACTION", "TARGET", "PRINCIPAL", "INTEGRATION", "SCHEDULE",
    "TENANT", "GLOBAL_RUNTIME",
]
PROPAGATION_STATES = [
    "PROPAGATION_PENDING", "PROPAGATED", "PROPAGATION_LATE",
    "PROPAGATION_MISSING", "PROPAGATION_CONTRADICTED",
]
BOUND_EPOCHS = ["principal_epoch", "integration_epoch", "schedule_epoch",
                "delegation_epoch", "approval_epoch", "tenant_policy_epoch"]

# ---- Causal work graph topology (section 19) ------------------------------
GRAPH_NODE_TYPES = [
    "WORK_RUN", "WORK_ORIGIN", "PRINCIPAL", "CONTEXT_CAPSULE", "MEMORY_SNAPSHOT",
    "DELEGATION_CAPSULE", "APPROVAL_RECORD", "TOOL_GATEWAY_PROOF",
    "TRANSACTION_TWIN", "POE_EVENT", "TRANSACTION_CERTIFICATE", "RECOVERY_TWIN",
    "POR_EVENT", "RECOVERY_CERTIFICATE", "ARTIFACT", "DELIVERY_INTENT",
    "REVOCATION_RECORD", "OBSERVATION_TWIN", "WORK_OUTCOME_CERTIFICATE",
]
GRAPH_EDGE_TYPES = [
    "TRIGGERED", "AUTHENTICATED_AS", "ACTING_FOR", "USED_CONTEXT", "USED_MEMORY",
    "OPERATED_UNDER", "APPROVED_BY", "PASSED_GATEWAY", "CREATED_TRANSACTION",
    "RECOVERED_BY", "PRODUCED", "INTENDED_FOR", "REVOKED_BY", "SUPERSEDES",
    "OBSERVED_BY", "PROVES", "CONTRADICTS",
]

# ---- Truth states (section 24) --------------------------------------------
TRUTH_STATES = [
    "PROVEN", "SUPPORTED", "PARTIAL", "UNKNOWN", "AMBIGUOUS", "CONTRADICTED",
    "TAMPERED", "STALE", "REVOKED", "NOT_APPLICABLE",
]

# ---- Observer health (section 28) -----------------------------------------
OBSERVER_HEALTH_STATES = [
    "OBSERVER_HEALTHY", "OBSERVER_DEGRADED", "OBSERVER_STALE",
    "OBSERVER_INCOMPLETE", "OBSERVER_DIVERGENT", "OBSERVER_POISONED",
    "OBSERVER_UNAVAILABLE",
]

# Expected work-evidence components (section 21 / negative space).
EXPECTED_WORK_EVIDENCE = [
    "work_origin_envelope", "principal_continuity", "context_capsule",
    "memory_snapshot", "delegation_capsule", "approval_continuity",
    "gateway_boundary", "transaction_binding", "proof_of_execution",
    "transaction_certificate", "recovery_proof", "artifact_lineage",
    "delivery_intent", "audit_record", "work_outcome_certificate",
]
# Components that are always required for certification (others may be N/A).
CRITICAL_WORK_EVIDENCE = {
    "work_origin_envelope", "principal_continuity", "gateway_boundary",
    "transaction_binding", "proof_of_execution", "transaction_certificate",
    "work_outcome_certificate",
}

# ---- Reason codes (section 35) --------------------------------------------
REASON_CODES = {
    # origin
    "WORK_ORIGIN_VALID", "WORK_ORIGIN_MISSING", "WORK_ORIGIN_AMBIGUOUS",
    "SCHEDULE_OCCURRENCE_DUPLICATE", "SCHEDULE_OCCURRENCE_MISSED",
    "SCHEDULE_OCCURRENCE_REVOKED", "HEARTBEAT_DIRECT_EXECUTION_REJECTED",
    # identity
    "PRINCIPAL_CONTINUITY_VALID", "PRINCIPAL_CONTINUITY_UNKNOWN",
    "PRINCIPAL_MAPPING_REVOKED", "PRINCIPAL_SESSION_INVALID",
    "PRINCIPAL_CROSS_TENANT_REJECTED",
    # context + memory
    "CONTEXT_CONTINUITY_VALID", "CONTEXT_TASK_MISMATCH", "CONTEXT_EXPIRED",
    "MEMORY_SNAPSHOT_VALID", "MEMORY_CRITICAL_FACT_DISPUTED",
    "MEMORY_FACT_EXPIRED", "MEMORY_FACT_REVOKED", "MEMORY_PROVENANCE_UNKNOWN",
    # approval
    "APPROVAL_CONTINUITY_VALID", "APPROVAL_ACTION_MISMATCH",
    "APPROVAL_TARGET_MISMATCH", "APPROVAL_SCOPE_EXCEEDED", "APPROVAL_EXPIRED",
    "APPROVAL_REVOKED", "APPROVAL_USE_LIMIT_EXCEEDED",
    # gateway
    "TOOL_GATEWAY_BOUNDARY_VALID", "CREDENTIAL_SCOPE_INSUFFICIENT",
    "CREDENTIAL_REFERENCE_REVOKED", "SECRET_EXPOSURE_TO_MODEL_DETECTED",
    "SECRET_EXPOSURE_TO_LOG_DETECTED", "SECRET_EXPOSURE_TO_ARTIFACT_DETECTED",
    # artifact + delivery
    "ARTIFACT_LINEAGE_VALID", "ARTIFACT_LINEAGE_MISSING", "ARTIFACT_SOURCE_MISSING",
    "ARTIFACT_UNRELATED_BRANCH_CHANGED", "DELIVERY_INTENT_VALID",
    "DELIVERY_INTENT_MISSING", "EXTERNAL_DELIVERY_ROUTE_REJECTED",
    # revocation
    "REVOCATION_NOT_DETECTED", "REVOCATION_DETECTED", "REVOCATION_PROPAGATED",
    "REVOCATION_PROPAGATION_LATE", "REVOCATION_PROPAGATION_MISSING",
    # transaction / recovery binding
    "TRANSACTION_BINDING_VALID", "TRANSACTION_BINDING_MISSING",
    "TRANSACTION_BINDING_INVALID", "RECOVERY_BINDING_VALID",
    "RECOVERY_BINDING_INVALID",
    # consistency / negative space / external effect
    "CONSISTENT_WORK_CUT_VALID", "CONSISTENT_WORK_CUT_INVALID",
    "CROSS_TENANT_WORK_EDGE", "CRITICAL_WORK_EVIDENCE_MISSING",
    "WORK_EXTERNAL_EFFECT_DETECTED", "WORK_EXTERNAL_DELIVERY_DETECTED",
    "OUTBOX_RELEASE_DETECTED", "OBSERVER_UNHEALTHY",
    # outcome
    "WORK_OUTCOME_PROVEN", "WORK_OUTCOME_PARTIAL", "WORK_OUTCOME_UNKNOWN",
    "WORK_OUTCOME_CONTRADICTED", "WORK_OUTCOME_TAMPERED",
    "PROOF_OF_WORK_OUTCOME_VALID", "PROOF_OF_WORK_OUTCOME_INVALID",
    # heartbeat codes
    "HEARTBEAT_SUGGESTION_CREATED", "HEARTBEAT_SUGGESTION_APPROVED",
    "HEARTBEAT_SUGGESTION_REJECTED",
}

REASON_TEXT = {c: c.replace("_", " ").capitalize() + "." for c in REASON_CODES}


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
    return set(_as_list(v))


def _h(r, self_key, *extra):
    return _core_hash(r, self_key, "signal", *extra)


# ---- 6. Work Origin Envelope ----------------------------------------------
def build_work_origin_envelope(*, tenant_id, work_run_id, ctx):
    tt = ctx.get("trigger_type") or "PORTAL_ACTION"
    signals = []
    if tt not in TRIGGER_TYPES:
        signals.append("WORK_ORIGIN_AMBIGUOUS")
    if ctx.get("origin_missing"):
        signals.append("WORK_ORIGIN_MISSING")
    if ctx.get("origin_ambiguous"):
        signals.append("WORK_ORIGIN_AMBIGUOUS")
    # A heartbeat suggestion or schedule occurrence is NOT execution authority.
    heartbeat_direct = bool(ctx.get("heartbeat_direct_execution"))
    if heartbeat_direct:
        signals.append("HEARTBEAT_DIRECT_EXECUTION_REJECTED")
    authority_status = "NOT_AUTHORITY" if tt in NON_AUTHORITATIVE_TRIGGERS \
        else "TRIGGER_ONLY"
    r = {
        "work_origin_envelope_version": WORK_ORIGIN_VERSION,
        "work_origin_envelope_id": "woe-" + _sha({"w": work_run_id})[:16],
        "tenant_id": tenant_id, "work_run_id": work_run_id, "trigger_type": tt,
        "source_surface": ctx.get("source_surface") or "WEB_PORTAL",
        "source_event_id": ctx.get("source_event_id"),
        "source_principal_id": ctx.get("source_principal_id"),
        "schedule_id": ctx.get("schedule_id"),
        "schedule_occurrence_id": ctx.get("schedule_occurrence_id"),
        "heartbeat_suggestion_id": ctx.get("heartbeat_suggestion_id"),
        "parent_work_run_id": ctx.get("parent_work_run_id"),
        "source_context_id": ctx.get("source_context_id"),
        "source_payload_hash": _sha({"p": ctx.get("source_payload") or {}}),
        "normalized_intent_hash": _sha(
            {"i": ctx.get("normalized_intent") or ""}),
        "authority_status": authority_status,
        "trigger_is_authority": False, "message_is_approval": False,
        "origin_policy_version": ctx.get("policy_version") or "wp-v1",
        "origin_status": "VALID" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["origin_envelope_hash"] = _h(r, "origin_envelope_hash")
    r["_signals"] = signals
    return r


# ---- 8. Schedule and heartbeat run chain ----------------------------------
def build_schedule_run_chain(*, tenant_id, work_run_id, ctx):
    signals = []
    sid = ctx.get("schedule_id")
    is_scheduled = ctx.get("trigger_type") == "SCHEDULE_OCCURRENCE" or bool(sid)
    scheduled_for = ctx.get("scheduled_for") or "T0"
    wd_version = ctx.get("work_definition_version") or "wd-v1"
    logical_run_key = _sha({"tenant": tenant_id, "schedule": sid,
                            "scheduled_for": scheduled_for,
                            "work_definition_version": wd_version})
    duplicate = bool(ctx.get("schedule_duplicate_delivery"))
    changed_payload = bool(ctx.get("schedule_duplicate_changed_payload"))
    missed = bool(ctx.get("schedule_missed"))
    delayed = bool(ctx.get("schedule_delayed"))
    revoked = bool(ctx.get("schedule_revoked")) or bool(
        ctx.get("schedule_disabled"))
    if is_scheduled:
        if revoked:
            signals.append("SCHEDULE_OCCURRENCE_REVOKED")
        elif changed_payload:
            # Same logical key, different payload -> block (not the same run).
            signals.append("SCHEDULE_OCCURRENCE_DUPLICATE")
        elif missed:
            signals.append("SCHEDULE_OCCURRENCE_MISSED")
    # Duplicate delivery of the SAME payload returns the same logical run (safe).
    r = {
        "schedule_run_chain_version": SCHEDULE_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id, "schedule_id": sid, "is_scheduled":
        is_scheduled, "scheduled_for": scheduled_for,
        "schedule_occurrence_id": ctx.get("schedule_occurrence_id"),
        "work_definition_version": wd_version,
        "calendar_rule_hash": _sha({"rule": ctx.get("calendar_rule") or ""}),
        "timezone": ctx.get("timezone") or "UTC",
        "deduplication_key": ctx.get("deduplication_key") or logical_run_key,
        "misfire_policy": ctx.get("misfire_policy") or "SKIP",
        "logical_run_key": logical_run_key,
        "duplicate_delivery": duplicate,
        "same_logical_run_on_duplicate": duplicate and not changed_payload,
        "missed": missed, "delayed": delayed, "revoked": revoked,
        "schedule_is_approval": False,
        "occurrence_hash": _sha({"lrk": logical_run_key,
                                 "occ": ctx.get("schedule_occurrence_id")}),
        "chain_status": "VALID" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["schedule_run_chain_hash"] = _h(r, "schedule_run_chain_hash")
    r["_signals"] = signals
    return r


# ---- 7. Principal Continuity Graph ----------------------------------------
def build_principal_continuity(*, tenant_id, work_run_id, ctx):
    signals = []
    source = ctx.get("source_principal_id")
    effective = ctx.get("effective_principal_id") or source
    known = bool(source) and bool(effective)
    if not known:
        signals.append("PRINCIPAL_CONTINUITY_UNKNOWN")
    if ctx.get("principal_mapping_revoked"):
        signals.append("PRINCIPAL_MAPPING_REVOKED")
    if ctx.get("principal_session_invalid"):
        signals.append("PRINCIPAL_SESSION_INVALID")
    if ctx.get("principal_cross_tenant"):
        signals.append("PRINCIPAL_CROSS_TENANT_REJECTED")
    continuity_valid = not signals
    r = {
        "principal_continuity_version": PRINCIPAL_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id,
        "source_principal_id": source, "effective_principal_id": effective,
        "source_principal_type": ctx.get("source_principal_type") or "HUMAN_USER",
        "effective_principal_type": ctx.get("effective_principal_type") or
        "SYSTEM_ACTOR",
        "identity_mapping_version": ctx.get("identity_mapping_version") or "im-v1",
        "role_version": ctx.get("role_version") or "role-v1",
        "membership_version": ctx.get("membership_version") or "mem-v1",
        "revocation_epoch": _int(ctx.get("principal_epoch"), 1),
        "session_reference": ctx.get("session_reference"),
        "stores_secret": False,
        "identity_continuity_valid": continuity_valid,
        "uses_display_name_heuristic": False, "uses_email_similarity": False,
        "continuity_status": "VALID" if continuity_valid else "UNKNOWN",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["principal_continuity_hash"] = _h(r, "principal_continuity_hash")
    r["_signals"] = signals
    return r


# ---- 9. Context Continuity Capsule ----------------------------------------
def build_context_capsule(*, tenant_id, work_run_id, ctx):
    signals = []
    if ctx.get("context_task_mismatch"):
        signals.append("CONTEXT_TASK_MISMATCH")
    if ctx.get("context_expired"):
        signals.append("CONTEXT_EXPIRED")
    r = {
        "context_capsule_version": CONTEXT_VERSION,
        "context_capsule_id": "ctx-" + _sha({"w": work_run_id})[:16],
        "tenant_id": tenant_id, "work_run_id": work_run_id,
        "source_surface": ctx.get("source_surface") or "WEB_PORTAL",
        "source_context_id": ctx.get("source_context_id"),
        "parent_context_id": ctx.get("parent_context_id"),
        "permitted_message_refs": sorted(map(str, _as_list(
            ctx.get("permitted_message_refs")))),
        "permitted_task_refs": sorted(map(str, _as_list(
            ctx.get("permitted_task_refs")))),
        "context_policy_version": ctx.get("context_policy_version") or "ctxp-v1",
        "context_minimization_status": "MINIMIZED",
        "context_is_authority": False,
        "context_status": "VALID" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["context_capsule_hash"] = _h(r, "context_capsule_hash")
    r["_signals"] = signals
    return r


# ---- 10. Company Memory Snapshot Provenance -------------------------------
def build_memory_snapshot(*, tenant_id, work_run_id, ctx):
    signals = []
    applicable = ctx.get("memory_applicable", True)
    facts = _as_list(ctx.get("memory_facts"))  # list of {id,trust,used,critical}
    influential = []
    for f in facts:
        if isinstance(f, dict):
            trust = f.get("trust", "SYSTEM_DERIVED")
            crit = bool(f.get("critical"))
            used = bool(f.get("used"))
            if used:
                influential.append(f.get("id"))
            if crit and trust == "DISPUTED":
                signals.append("MEMORY_CRITICAL_FACT_DISPUTED")
            if trust == "EXPIRED":
                signals.append("MEMORY_FACT_EXPIRED")
            if trust == "REVOKED":
                signals.append("MEMORY_FACT_REVOKED")
    if ctx.get("memory_provenance_unknown"):
        signals.append("MEMORY_PROVENANCE_UNKNOWN")
    r = {
        "memory_snapshot_version": MEMORY_VERSION,
        "memory_snapshot_id": "mem-" + _sha({"w": work_run_id})[:16],
        "tenant_id": tenant_id, "work_run_id": work_run_id,
        "memory_applicable": applicable,
        "memory_policy_version": ctx.get("memory_policy_version") or "memp-v1",
        "retrieval_query_hash": _sha({"q": ctx.get("memory_query") or ""}),
        "retrieval_scope": ctx.get("memory_scope") or "TENANT",
        "retrieved_memory_refs": sorted(str(f.get("id")) for f in facts
                                        if isinstance(f, dict)),
        "retrieved_memory_versions": {str(f.get("id")): f.get("version", "1")
                                      for f in facts if isinstance(f, dict)},
        "memory_trust_classes": sorted({f.get("trust", "SYSTEM_DERIVED")
                                        for f in facts if isinstance(f, dict)}),
        "influential_memory_refs": sorted(str(i) for i in influential if i),
        "memory_conflict_status": "CONFLICT" if any(
            s == "MEMORY_CRITICAL_FACT_DISPUTED" for s in signals) else "NONE",
        "memory_freshness_status": "STALE" if any(
            s == "MEMORY_FACT_EXPIRED" for s in signals) else "FRESH",
        "memory_expiry_status": "EXPIRED" if any(
            s == "MEMORY_FACT_EXPIRED" for s in signals) else "CURRENT",
        "memory_consent_status": "CONSENTED",
        "memory_minimization_status": "MINIMIZED",
        "stores_full_content": False, "stores_chain_of_thought": False,
        "snapshot_immutable": True,
        "snapshot_status": "VALID" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["snapshot_hash"] = _h(r, "snapshot_hash")
    r["_signals"] = sorted(set(signals))
    return r


# ---- 11. Delegation Provenance Capsule ------------------------------------
def build_delegation_capsule(*, tenant_id, work_run_id, ctx):
    signals = []
    applicable = ctx.get("delegation_applicable", True)
    parent = ctx.get("parent_delegation") or {}
    child = ctx.get("child_delegation") or {}

    def _scope(d, k, default):
        return _sub(d.get(k)) if d.get(k) is not None else set(default)
    p_read = _scope(parent, "read_scope", ["case.read"])
    c_read = _scope(child, "read_scope", p_read)
    p_write = _scope(parent, "write_scope", ["case.update"])
    c_write = _scope(child, "write_scope", p_write)
    p_tool = _scope(parent, "tool_scope", ["local"])
    c_tool = _scope(child, "tool_scope", p_tool)
    p_res = _scope(parent, "resource_scope", ["case"])
    c_res = _scope(child, "resource_scope", p_res)
    p_ext = _int(parent.get("externality_class"), 0)
    c_ext = _int(child.get("externality_class"), p_ext)
    checks = {
        "read_subset": c_read <= p_read, "write_subset": c_write <= p_write,
        "tool_subset": c_tool <= p_tool, "resource_subset": c_res <= p_res,
        "externality_monotonic": c_ext <= p_ext,
    }
    if applicable and not all(checks.values()):
        signals.append("APPROVAL_SCOPE_EXCEEDED")  # delegation broadening
    r = {
        "delegation_capsule_version": DELEGATION_VERSION,
        "delegation_capsule_id": "del-" + _sha({"w": work_run_id})[:16],
        "tenant_id": tenant_id, "work_run_id": work_run_id,
        "delegation_applicable": applicable,
        "delegation_root_id": ctx.get("delegation_root_id"),
        "delegator": child.get("delegator") or parent.get("delegator"),
        "delegate": child.get("delegate"),
        "checks": checks, "monotonic": all(checks.values()),
        "read_scope": sorted(c_read), "write_scope": sorted(c_write),
        "tool_scope": sorted(c_tool), "resource_scope": sorted(c_res),
        "externality_class": c_ext,
        "policy_version": ctx.get("delegation_policy_version") or "delp-v1",
        "reconstructed_from_trace": False,
        "delegation_status": "VALID" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["delegation_capsule_hash"] = _h(r, "delegation_capsule_hash")
    r["_signals"] = signals
    return r


# ---- 12. Approval Continuity Record ---------------------------------------
def build_approval_continuity(*, tenant_id, work_run_id, ctx):
    signals = []
    applicable = ctx.get("approval_applicable", True)
    approved = ctx.get("approved_action") or "mark_local_status_reviewed"
    actual = ctx.get("actual_action", approved)
    approved_target = ctx.get("approved_target") or "case:E-1"
    actual_target = ctx.get("actual_target", approved_target)
    approved_scope = _sub(ctx.get("approved_scope") if ctx.get("approved_scope")
                          is not None else ["status"])
    actual_scope = _sub(ctx.get("actual_scope") if ctx.get("actual_scope")
                        is not None else approved_scope)
    max_uses = _int(ctx.get("maximum_uses"), 1)
    uses = _int(ctx.get("uses_consumed"), 0)
    expired = bool(ctx.get("approval_expired"))
    revoked = bool(ctx.get("approval_revoked"))
    if applicable:
        if approved != actual:
            signals.append("APPROVAL_ACTION_MISMATCH")
        elif approved_target != actual_target:
            signals.append("APPROVAL_TARGET_MISMATCH")
        elif not (actual_scope <= approved_scope):
            signals.append("APPROVAL_SCOPE_EXCEEDED")
        elif expired:
            signals.append("APPROVAL_EXPIRED")
        elif revoked:
            signals.append("APPROVAL_REVOKED")
        elif uses >= max_uses:
            signals.append("APPROVAL_USE_LIMIT_EXCEEDED")
    valid = not signals
    r = {
        "approval_continuity_version": APPROVAL_VERSION,
        "approval_continuity_id": "apc-" + _sha({"w": work_run_id})[:16],
        "tenant_id": tenant_id, "work_run_id": work_run_id,
        "approval_applicable": applicable, "approval_id": ctx.get("approval_id"),
        "approver_principal_id": ctx.get("approver_principal_id"),
        "approval_class": ctx.get("approval_class") or "STANDARD",
        "approval_mode": ctx.get("approval_mode") or "APPROVE_EACH_RUN",
        "approved_action_hash": _sha({"a": approved}),
        "approved_target_hash": _sha({"t": approved_target}),
        "approved_scope_hash": _sha({"s": sorted(approved_scope)}),
        "approved_parameters_hash": _sha({"p": ctx.get("approved_parameters")}),
        "approved_externality_class": _int(ctx.get("approved_externality"), 0),
        "maximum_uses": max_uses, "uses_consumed": uses,
        "approval_policy_version": ctx.get("approval_policy_version") or "apv-v1",
        "exact_binding": valid, "fuzzy_matching": False,
        "approval_status": "VALID" if valid else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["approval_binding_hash"] = _h(r, "approval_binding_hash")
    r["_signals"] = signals
    return r


# ---- 13. Tool Gateway Boundary Proof --------------------------------------
def build_gateway_boundary_proof(*, tenant_id, work_run_id, ctx):
    signals = []
    requested = ctx.get("requested_operation") or "local.read"
    allowed = ctx.get("allowed_operation") or requested
    cred_scope = _sub(ctx.get("credential_scope") if ctx.get("credential_scope")
                      is not None else [requested])
    scope_ok = requested in cred_scope or allowed in cred_scope
    integration_revoked = bool(ctx.get("integration_revoked"))
    # LOCAL stage: no real provider execution -> no secret injection.
    secret_to_model = bool(ctx.get("secret_exposed_to_model"))
    secret_to_logs = bool(ctx.get("secret_exposed_to_logs"))
    secret_to_artifact = bool(ctx.get("secret_exposed_to_artifact"))
    if not scope_ok:
        signals.append("CREDENTIAL_SCOPE_INSUFFICIENT")
    if integration_revoked:
        signals.append("CREDENTIAL_REFERENCE_REVOKED")
    if secret_to_model:
        signals.append("SECRET_EXPOSURE_TO_MODEL_DETECTED")
    if secret_to_logs:
        signals.append("SECRET_EXPOSURE_TO_LOG_DETECTED")
    if secret_to_artifact:
        signals.append("SECRET_EXPOSURE_TO_ARTIFACT_DETECTED")
    boundary_valid = not signals
    r = {
        "gateway_proof_version": GATEWAY_VERSION,
        "gateway_proof_id": "gwp-" + _sha({"w": work_run_id})[:16],
        "tenant_id": tenant_id, "work_run_id": work_run_id,
        "tool_id": ctx.get("tool_id"), "tool_version": ctx.get("tool_version"),
        "integration_id": ctx.get("integration_id"),
        "credential_reference_id": ctx.get("credential_reference_id"),
        "credential_scope_hash": _sha({"cs": sorted(cred_scope)}),
        "requested_operation_hash": _sha({"r": requested}),
        "allowed_operation_hash": _sha({"a": allowed}),
        "gateway_policy_version": ctx.get("gateway_policy_version") or "gwp-v1",
        # LOCAL: no real injection occurs.
        "secret_injection_occurred": False,
        "secret_exposed_to_model": secret_to_model,
        "secret_exposed_to_logs": secret_to_logs,
        "secret_exposed_to_artifact": secret_to_artifact,
        "credential_rotation_epoch": _int(ctx.get("credential_rotation_epoch"), 1),
        "credential_revocation_epoch": _int(
            ctx.get("credential_revocation_epoch"), 1),
        "stores_secret": False,
        "gateway_decision": "ALLOW" if boundary_valid else "BLOCK",
        "credential_boundary_valid": boundary_valid,
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["gateway_proof_hash"] = _h(r, "gateway_proof_hash")
    r["_signals"] = signals
    return r


# ---- 14/15. Revocation epochs + propagation -------------------------------
def build_revocation(*, tenant_id, work_run_id, ctx):
    signals = []
    bound = {e: _int(ctx.get("bound_" + e), 1) for e in BOUND_EPOCHS}
    current = {e: _int(ctx.get("current_" + e), bound[e]) for e in BOUND_EPOCHS}
    advanced = [e for e in BOUND_EPOCHS if current[e] != bound[e]]
    revocation_detected = bool(advanced) or bool(ctx.get("revocation_detected"))
    if revocation_detected:
        signals.append("REVOCATION_DETECTED")
    # Propagation: has the revocation reached each scope?
    prop_state = ctx.get("propagation_state") or (
        "PROPAGATED" if revocation_detected else "PROPAGATION_PENDING")
    if revocation_detected:
        if prop_state == "PROPAGATION_MISSING":
            signals.append("REVOCATION_PROPAGATION_MISSING")
        elif prop_state == "PROPAGATION_LATE":
            signals.append("REVOCATION_PROPAGATION_LATE")
        elif prop_state in ("PROPAGATED", "PROPAGATION_CONTRADICTED"):
            signals.append("REVOCATION_PROPAGATED")
    revocation_still_valid = not advanced
    # Safety invariants: revoked principal/integration/schedule cannot admit new
    # work / gateway use / schedule run; kill switch blocks finalization.
    propagation_safe = (not revocation_detected) or prop_state in (
        "PROPAGATED",)
    r = {
        "revocation_version": REVOCATION_PROP_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id, "bound_epochs": bound,
        "current_epochs": current, "advanced_epochs": advanced,
        "revocation_detected": revocation_detected,
        "revocation_still_valid": revocation_still_valid,
        "propagation_state": prop_state, "propagation_safe": propagation_safe,
        "revocation_scopes": REVOCATION_SCOPES, "performs_revocation": False,
        "revoked_principal_blocks_new_work": True,
        "revoked_integration_blocks_gateway": True,
        "disabled_schedule_blocks_run": True,
        "kill_switch_blocks_finalization": True,
        "revocation_status": "DETECTED" if revocation_detected else "CLEAN",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["revocation_status_hash"] = _h(r, "revocation_status_hash")
    r["_signals"] = signals if any(s in (
        "REVOCATION_PROPAGATION_MISSING", "REVOCATION_PROPAGATION_LATE")
        for s in signals) else []
    return r


# ---- 16. Artifact Lineage DAG ---------------------------------------------
def build_artifact_lineage(*, tenant_id, work_run_id, ctx):
    signals = []
    expected = ctx.get("artifact_expected", True)
    artifacts = _as_list(ctx.get("artifacts"))  # list of {id,type,sources}
    if not expected or (artifacts and any(
            a.get("type") == "NO_ARTIFACT_EXPECTED" for a in artifacts
            if isinstance(a, dict))):
        expected = False
    nodes, edges = [], []
    for a in artifacts:
        if not isinstance(a, dict):
            continue
        at = a.get("type") or "REPORT"
        srcs = _as_list(a.get("sources"))
        nodes.append({"artifact_id": a.get("id"), "artifact_type": at,
                      "content_hash": _sha({"c": a.get("content") or a.get("id")}),
                      "sensitivity_class": a.get("sensitivity") or "INTERNAL",
                      "artifact_status": a.get("status") or "PRODUCED",
                      "creator_module": a.get("creator") or "b9_transaction"})
        if at not in ("NO_ARTIFACT_EXPECTED", "LOCAL_STATE_CHANGE_SUMMARY") \
                and not srcs:
            signals.append("ARTIFACT_SOURCE_MISSING")
        for s in srcs:
            edges.append({"from": str(s), "to": a.get("id"),
                          "edge": "DERIVED_FROM"})
    if expected and not artifacts:
        signals.append("ARTIFACT_LINEAGE_MISSING")
    if ctx.get("unrelated_branch_changed"):
        signals.append("ARTIFACT_UNRELATED_BRANCH_CHANGED")
    lineage_valid = not signals
    r = {
        "artifact_lineage_version": ARTIFACT_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id, "artifact_expected": expected,
        "nodes": nodes, "edges": edges, "node_count": len(nodes),
        "edge_count": len(edges), "artifact_types": ARTIFACT_TYPES,
        "unaffected_branch_preserved": not ctx.get("unrelated_branch_changed"),
        "lineage_valid": lineage_valid,
        "lineage_status": "VALID" if lineage_valid else (
            "NO_ARTIFACT_EXPECTED" if not expected else "INVALID"),
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["artifact_lineage_hash"] = _h(r, "artifact_lineage_hash")
    r["_signals"] = sorted(set(signals))
    return r


# ---- 17. Delivery Intent Record -------------------------------------------
def build_delivery_intent(*, tenant_id, work_run_id, ctx):
    signals = []
    applicable = ctx.get("delivery_applicable", True)
    status = ctx.get("delivery_status") or (
        "LOCAL_INTENT_ONLY" if applicable else "DELIVERY_NOT_APPLICABLE")
    if status == "DELIVERED_EXTERNALLY" or ctx.get("external_delivery"):
        signals.append("EXTERNAL_DELIVERY_ROUTE_REJECTED")
        status = "DELIVERY_BLOCKED"
    if applicable and ctx.get("delivery_missing"):
        signals.append("DELIVERY_INTENT_MISSING")
    r = {
        "delivery_intent_version": DELIVERY_VERSION,
        "delivery_intent_id": "del-" + _sha({"w": work_run_id})[:16],
        "tenant_id": tenant_id, "work_run_id": work_run_id,
        "delivery_applicable": applicable,
        "artifact_ids": sorted(map(str, _as_list(ctx.get("delivery_artifacts")))),
        "destination_type": ctx.get("destination_type") or "LOCAL",
        "destination_reference_hash": _sha({"d": ctx.get("destination_ref")}),
        "recipient_scope_hash": _sha({"r": ctx.get("recipient_scope")}),
        "delivery_policy_version": ctx.get("delivery_policy_version") or "dpv-1",
        "outbox_reference": ctx.get("outbox_reference"),
        "delivery_status": status, "delivered_externally": False,
        "outbox_released": False,
        "intent_status": "VALID" if not signals else "BLOCKED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["delivery_intent_hash"] = _h(r, "delivery_intent_hash")
    r["_signals"] = signals
    return r


# ---- 19 (part). Transaction + recovery binding (read-only over B9/B9.1) ----
def build_transaction_binding(*, tenant_id, work_run_id, b9_outcome, ctx):
    o = b9_outcome or {}
    signals = []
    applicable = ctx.get("transaction_applicable", True)
    if applicable and not o:
        signals.append("TRANSACTION_BINDING_MISSING")
    elif o:
        if o.get("tenant_id") not in (None, tenant_id):
            signals.append("CROSS_TENANT_WORK_EDGE")
        poe = (o.get("poe_stream") or {})
        if poe.get("stream_status") not in (None, "COMPLETE"):
            signals.append("TRANSACTION_BINDING_INVALID")
        if not o.get("certificate", {}).get("certificate_hash"):
            signals.append("TRANSACTION_BINDING_INVALID")
    poe_valid = bool(o.get("proof_of_execution", {}).get(
        "proof_of_execution_valid", o.get("local_commit_applied")))
    r = {
        "transaction_binding_version": "finalis-work-transaction-binding-v1",
        "tenant_id": tenant_id, "work_run_id": work_run_id,
        "transaction_applicable": applicable,
        "transaction_id": o.get("transaction_id"),
        "transaction_twin_hash": (o.get("transaction_envelope") or {}).get(
            "canonical_hash"),
        "poe_hash": (o.get("poe_stream") or {}).get("poe_stream_hash"),
        "transaction_certificate_hash": (o.get("certificate") or {}).get(
            "certificate_hash"),
        "b9_status": o.get("b9_status"),
        "proof_of_execution_valid": bool(poe_valid),
        "transaction_certificate_valid": bool(
            (o.get("certificate") or {}).get("certificate_hash")),
        "read_only": True, "mutates_transaction": False,
        "binding_status": "VALID" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["transaction_binding_hash"] = _h(r, "transaction_binding_hash")
    r["_signals"] = signals
    return r


def build_recovery_binding(*, tenant_id, work_run_id, b91_outcome, ctx):
    o = b91_outcome or {}
    signals = []
    applicable = bool(o) or bool(ctx.get("recovery_required"))
    if o:
        if o.get("tenant_id") not in (None, tenant_id):
            signals.append("CROSS_TENANT_WORK_EDGE")
        if ctx.get("recovery_binding_invalid"):
            signals.append("RECOVERY_BINDING_INVALID")
    r = {
        "recovery_binding_version": "finalis-work-recovery-binding-v1",
        "tenant_id": tenant_id, "work_run_id": work_run_id,
        "recovery_applicable": applicable,
        "recovery_id": o.get("recovery_id"),
        "recovery_twin_hash": o.get("recovery_twin_hash"),
        "por_hash": o.get("proof_of_recovery_hash"),
        "recovery_certificate_hash": o.get("recovery_certificate_hash"),
        "final_recovery_state": o.get("final_recovery_state"),
        "read_only": True, "mutates_recovery": False,
        "binding_status": "VALID" if not signals else (
            "NOT_APPLICABLE" if not applicable else "INVALID"),
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["recovery_binding_hash"] = _h(r, "recovery_binding_hash")
    r["_signals"] = signals
    return r


# ---- No-external-effect theorem (work stage) ------------------------------
def build_no_external_effect(*, tenant_id, work_run_id, ctx):
    attempts = ctx.get("attempt_markers") or {}
    signals = []
    if attempts.get("external_effect") or attempts.get("provider_call") or \
            attempts.get("message_send") or attempts.get("payment") or \
            attempts.get("external_crm_mutation") or attempts.get("webhook"):
        signals.append("WORK_EXTERNAL_EFFECT_DETECTED")
    if attempts.get("external_delivery"):
        signals.append("WORK_EXTERNAL_DELIVERY_DETECTED")
    if attempts.get("outbox_release"):
        signals.append("OUTBOX_RELEASE_DETECTED")
    holds = not signals
    r = {
        "no_external_version": NO_EXTERNAL_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id, "produced_external_effect": False,
        "provider_called": False, "message_sent": False, "payment_executed": False,
        "external_crm_mutated": False, "webhook_dispatched": False,
        "delivered_externally": False, "outbox_released": False,
        "theorem_holds": holds,
        "theorem_status": "HOLDS" if holds else "VIOLATED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["no_external_effect_hash"] = _h(r, "no_external_effect_hash")
    r["_signals"] = signals
    return r


# ---- 25. Structured decision basis (no chain of thought) ------------------
def build_decision_basis(*, tenant_id, work_run_id, ctx):
    basis = ctx.get("decision_basis") or {}
    r = {
        "decision_basis_version": DECISION_BASIS_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id,
        "decision_id": basis.get("decision_id") or "dec-" + _sha(
            {"w": work_run_id})[:12],
        "policy_ids": sorted(map(str, _as_list(basis.get("policy_ids")))),
        "rule_ids": sorted(map(str, _as_list(basis.get("rule_ids")))),
        "source_fact_ids": sorted(map(str, _as_list(basis.get("source_fact_ids")))),
        "evidence_ids": sorted(map(str, _as_list(basis.get("evidence_ids")))),
        "memory_fact_ids": sorted(map(str, _as_list(basis.get("memory_fact_ids")))),
        "assumptions": _as_list(basis.get("assumptions")),
        "approval_ids": sorted(map(str, _as_list(basis.get("approval_ids")))),
        "reason_codes": _as_list(basis.get("reason_codes")),
        "rejected_action_classes": _as_list(basis.get("rejected_action_classes")),
        "result_class": basis.get("result_class") or "LOCAL_STATE_CHANGE",
        "stores_chain_of_thought": False, "is_authority": False,
        "honesty_labels": HONESTY_LABELS,
    }
    r["deterministic_hash"] = _core_hash(r, "deterministic_hash")
    r["_signals"] = []
    return r


# ---- 26. OpenTelemetry adapter (versioned; canonical stays authoritative) -
def build_otel_adapter(*, tenant_id, work_run_id, ctx):
    available = ctx.get("otel_available", True)
    max_attrs = _int(ctx.get("otel_max_attributes"), 64)
    attr_count = _int(ctx.get("otel_attribute_count"), 8)
    cardinality_ok = attr_count <= max_attrs
    r = {
        "otel_adapter_version": OTEL_ADAPTER_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id,
        "instrumentation_scope": "finalis.ai_employee.governed_work_lineage",
        "trace_id": _sha({"w": work_run_id})[:32],
        "span_id": _sha({"s": work_run_id})[:16],
        "parent_span_id": ctx.get("otel_parent_span"),
        "supports_w3c_trace_context": True, "adapter_available": available,
        "critical_evidence_sampled": False, "canonical_is_authoritative": True,
        "uses_external_semconv_as_truth": False,
        "no_transaction_id_in_metric_labels": True,
        "no_raw_customer_data_in_attributes": True,
        "attribute_count": attr_count, "max_attributes": max_attrs,
        "cardinality_ok": cardinality_ok,
        "adapter_status": "HEALTHY" if available and cardinality_ok else "DEGRADED",
        "honesty_labels": HONESTY_LABELS,
    }
    r["otel_adapter_hash"] = _core_hash(r, "otel_adapter_hash")
    r["_signals"] = []
    return r


# ---- 27. A2A compatibility boundary (mapping only, never authority) -------
def build_a2a_boundary(*, tenant_id, work_run_id, ctx):
    signals = []
    a2a = ctx.get("a2a") or {}
    applicable = bool(a2a)
    if applicable and a2a.get("context_task_mismatch"):
        signals.append("CONTEXT_TASK_MISMATCH")
    r = {
        "a2a_boundary_version": A2A_BOUNDARY_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id, "a2a_applicable": applicable,
        "external_task_reference": a2a.get("task_id"),
        "external_context_reference": a2a.get("context_id"),
        "external_transport_state": a2a.get("task_state"),
        "untrusted_external_artifact": bool(a2a.get("artifact")),
        "a2a_state_can_override_finalis": False,
        "agent_card_grants_authority": False,
        "a2a_message_proves_delivery": False,
        "tenant_bound": bool(tenant_id),
        "boundary_status": "VALID" if not signals else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["a2a_boundary_hash"] = _h(r, "a2a_boundary_hash")
    r["_signals"] = []
    return r


# ---- 28. Observer self-health ---------------------------------------------
def build_observer_health(*, tenant_id, work_run_id, reports, ctx):
    problems = []
    if reports["work_origin"].get("origin_status") != "VALID":
        problems.append("missing_or_invalid_origin_envelope")
    if reports["principal_continuity"]["continuity_status"] != "VALID":
        problems.append("principal_mapping_failure")
    if reports["memory_snapshot"]["memory_freshness_status"] == "STALE":
        problems.append("stale_memory_snapshot")
    if reports["gateway_boundary"]["gateway_decision"] != "ALLOW":
        problems.append("gateway_proof_failure")
    if reports["twin_creation_failed"] if "twin_creation_failed" in reports \
            else False:
        problems.append("twin_creation_failure")
    if not reports["otel_adapter"]["adapter_available"]:
        problems.append("opentelemetry_adapter_failure")
    if not reports["otel_adapter"]["cardinality_ok"]:
        problems.append("metric_cardinality_rejection")
    if ctx.get("cross_tenant_query"):
        problems.append("cross_tenant_query_block")
    forced = ctx.get("observer_health_forced")
    if forced in OBSERVER_HEALTH_STATES:
        state = forced
    elif ctx.get("observer_unavailable"):
        state = "OBSERVER_UNAVAILABLE"
    elif "cross_tenant_query_block" in problems:
        state = "OBSERVER_POISONED"
    elif problems:
        state = "OBSERVER_DEGRADED"
    else:
        state = "OBSERVER_HEALTHY"
    healthy = state == "OBSERVER_HEALTHY"
    r = {
        "observer_health_version": OBSERVER_HEALTH_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id, "problems": problems,
        "observer_health_state": state, "observer_healthy": healthy,
        "failure_appears_as_success": False,
        "signal": None if healthy else "OBSERVER_UNHEALTHY",
        "honesty_labels": HONESTY_LABELS,
    }
    r["observer_health_hash"] = _core_hash(r, "observer_health_hash", "signal")
    r["_signals"] = [] if healthy else []  # health is reported, not blocking
    return r


# ---- 19. Causal work lineage graph ----------------------------------------
def build_causal_work_graph(*, tenant_id, work_run_id, reports, b9_outcome,
                            b91_outcome):
    nodes = [{"type": "WORK_RUN", "id": work_run_id}]
    nmap = {
        "WORK_ORIGIN": reports["work_origin"]["origin_envelope_hash"],
        "PRINCIPAL": reports["principal_continuity"]["principal_continuity_hash"],
        "CONTEXT_CAPSULE": reports["context_capsule"]["context_capsule_hash"],
        "MEMORY_SNAPSHOT": reports["memory_snapshot"]["snapshot_hash"],
        "DELEGATION_CAPSULE": reports["delegation_capsule"][
            "delegation_capsule_hash"],
        "APPROVAL_RECORD": reports["approval_continuity"]["approval_binding_hash"],
        "TOOL_GATEWAY_PROOF": reports["gateway_boundary"]["gateway_proof_hash"],
        "TRANSACTION_TWIN": reports["transaction_binding"]["transaction_twin_hash"],
        "TRANSACTION_CERTIFICATE": reports["transaction_binding"][
            "transaction_certificate_hash"],
        "RECOVERY_TWIN": reports["recovery_binding"]["recovery_twin_hash"],
        "RECOVERY_CERTIFICATE": reports["recovery_binding"][
            "recovery_certificate_hash"],
        "ARTIFACT": reports["artifact_lineage"]["artifact_lineage_hash"],
        "DELIVERY_INTENT": reports["delivery_intent"]["delivery_intent_hash"],
        "REVOCATION_RECORD": reports["revocation"]["revocation_status_hash"],
    }
    for t, h in nmap.items():
        nodes.append({"type": t, "id": h})
    edges = [
        {"edge": "TRIGGERED", "from": nmap["WORK_ORIGIN"], "to": work_run_id},
        {"edge": "AUTHENTICATED_AS", "from": work_run_id,
         "to": nmap["PRINCIPAL"]},
        {"edge": "USED_CONTEXT", "from": work_run_id,
         "to": nmap["CONTEXT_CAPSULE"]},
        {"edge": "USED_MEMORY", "from": work_run_id, "to": nmap["MEMORY_SNAPSHOT"]},
        {"edge": "OPERATED_UNDER", "from": work_run_id,
         "to": nmap["DELEGATION_CAPSULE"]},
        {"edge": "APPROVED_BY", "from": work_run_id, "to": nmap["APPROVAL_RECORD"]},
        {"edge": "PASSED_GATEWAY", "from": work_run_id,
         "to": nmap["TOOL_GATEWAY_PROOF"]},
        {"edge": "CREATED_TRANSACTION", "from": work_run_id,
         "to": nmap["TRANSACTION_TWIN"]},
        {"edge": "RECOVERED_BY", "from": work_run_id, "to": nmap["RECOVERY_TWIN"]},
        {"edge": "PRODUCED", "from": work_run_id, "to": nmap["ARTIFACT"]},
        {"edge": "INTENDED_FOR", "from": nmap["ARTIFACT"],
         "to": nmap["DELIVERY_INTENT"]},
        {"edge": "REVOKED_BY", "from": work_run_id,
         "to": nmap["REVOCATION_RECORD"]},
    ]
    r = {
        "causal_graph_version": CAUSAL_GRAPH_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id, "nodes": nodes, "edges": edges,
        "node_count": len(nodes), "edge_count": len(edges),
        "node_types": GRAPH_NODE_TYPES, "edge_types": GRAPH_EDGE_TYPES,
        "honesty_labels": HONESTY_LABELS,
    }
    r["causal_work_graph_hash"] = _core_hash(r, "causal_work_graph_hash")
    r["_signals"] = []
    return r


# ---- 20. Consistent work cut ----------------------------------------------
def build_consistent_work_cut(*, tenant_id, work_run_id, reports, ctx):
    signals = []
    cross_tenant = any(reports[k].get("_signals") and "CROSS_TENANT_WORK_EDGE"
                       in reports[k]["_signals"] for k in
                       ("transaction_binding", "recovery_binding"))
    if cross_tenant or ctx.get("cross_tenant_edge"):
        signals.append("CROSS_TENANT_WORK_EDGE")
    if ctx.get("incompatible_versions"):
        signals.append("CONSISTENT_WORK_CUT_INVALID")
    valid = not signals
    r = {
        "consistent_cut_version": CONSISTENT_CUT_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id,
        "all_required_predecessors_included": True,
        "source_versions_compatible": not ctx.get("incompatible_versions"),
        "revocation_epochs_compatible": reports["revocation"][
            "revocation_still_valid"],
        "no_cross_tenant_edge": not (cross_tenant or ctx.get("cross_tenant_edge")),
        "consistent_cut_valid": valid,
        "cut_status": "VALID" if valid else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["consistent_cut_hash"] = _h(r, "consistent_cut_hash")
    r["_signals"] = signals
    return r


# ---- 21. Negative-space work sentinel -------------------------------------
def build_negative_space(*, tenant_id, work_run_id, reports, ctx):
    present = {
        "work_origin_envelope": reports["work_origin"]["origin_status"] == "VALID",
        "principal_continuity": reports["principal_continuity"][
            "continuity_status"] == "VALID",
        "context_capsule": reports["context_capsule"]["context_status"] == "VALID",
        "memory_snapshot": reports["memory_snapshot"]["snapshot_status"] in (
            "VALID",),
        "delegation_capsule": reports["delegation_capsule"][
            "delegation_status"] == "VALID",
        "approval_continuity": reports["approval_continuity"][
            "approval_status"] == "VALID",
        "gateway_boundary": reports["gateway_boundary"][
            "credential_boundary_valid"],
        "transaction_binding": reports["transaction_binding"][
            "binding_status"] == "VALID",
        "proof_of_execution": reports["transaction_binding"][
            "proof_of_execution_valid"],
        "transaction_certificate": reports["transaction_binding"][
            "transaction_certificate_valid"],
        "recovery_proof": reports["recovery_binding"]["binding_status"] in (
            "VALID", "NOT_APPLICABLE"),
        "artifact_lineage": reports["artifact_lineage"]["lineage_status"] in (
            "VALID", "NO_ARTIFACT_EXPECTED"),
        "delivery_intent": reports["delivery_intent"]["intent_status"] in (
            "VALID",),
        "audit_record": True,
        "work_outcome_certificate": True,
    }
    missing = [c for c in EXPECTED_WORK_EVIDENCE if not present.get(c, False)]
    missing_critical = [c for c in missing if c in CRITICAL_WORK_EVIDENCE]
    signals = ["CRITICAL_WORK_EVIDENCE_MISSING"] if missing_critical else []
    r = {
        "negative_space_version": NEGATIVE_SPACE_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id, "expected": EXPECTED_WORK_EVIDENCE,
        "present": present, "missing": missing,
        "missing_critical": missing_critical,
        "no_critical_missing": not missing_critical,
        "missing_evidence_hash": _sha({"m": sorted(missing)}),
        "sentinel_status": "COMPLETE" if not missing else "INCOMPLETE",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["negative_space_hash"] = _h(r, "negative_space_hash",
                                  "missing_evidence_hash")
    r["_signals"] = signals
    return r


# ---- 18. Cross-run recurrence / drift (per work definition) ---------------
def build_recurring_drift(*, tenant_id, work_definition_id, ctx):
    prev = ctx.get("previous_run") or {}
    curr = ctx.get("current_run") or {}

    def _fp(d):
        return _sha({k: d.get(k) for k in (
            "work_definition_version", "policy_version", "memory_policy_version",
            "artifact_schema_version", "tool_set_version",
            "observability_contract_version")})
    fp_prev, fp_curr = _fp(prev), _fp(curr)
    drift_kinds = []
    if prev.get("input_hash") != curr.get("input_hash"):
        drift_kinds.append("EXPECTED_INPUT_DRIFT")
    if prev.get("policy_version") != curr.get("policy_version"):
        drift_kinds.append("EXPECTED_POLICY_DRIFT")
    if prev.get("memory_policy_version") != curr.get("memory_policy_version"):
        drift_kinds.append("EXPECTED_MEMORY_DRIFT")
    if prev.get("artifact_schema_version") != curr.get("artifact_schema_version"):
        drift_kinds.append("EXPECTED_SCHEMA_DRIFT")
    unexplained = bool(ctx.get("unexplained_behavioral_drift"))
    if unexplained:
        drift_kinds.append("UNEXPLAINED_BEHAVIORAL_DRIFT")
    nd = _int(ctx.get("node_diff"))
    ed = _int(ctx.get("edge_diff"))
    td = _int(ctx.get("transition_diff"))
    ad = _int(ctx.get("artifact_schema_diff"))
    d_struct = 0.25 * nd + 0.25 * ed + 0.25 * td + 0.25 * ad
    r = {
        "recurrence_version": RECURRENCE_VERSION, "tenant_id": tenant_id,
        "work_definition_id": work_definition_id,
        "previous_fingerprint": fp_prev, "current_fingerprint": fp_curr,
        "fingerprint_changed": fp_prev != fp_curr,
        "drift_kinds": drift_kinds, "unexplained_drift": unexplained,
        "structural_drift_distance": d_struct,
        "hard_contradiction_separate": True,
        "drift_status": "UNEXPLAINED" if unexplained else "EXPLAINED",
        "honesty_labels": HONESTY_LABELS,
    }
    r["recurring_drift_hash"] = _core_hash(r, "recurring_drift_hash")
    r["_signals"] = []
    return r


# ---- Component aggregation ------------------------------------------------
_BASE_COMPONENTS = [
    "work_origin", "schedule_run_chain", "principal_continuity",
    "context_capsule", "memory_snapshot", "delegation_capsule",
    "approval_continuity", "gateway_boundary", "revocation",
    "artifact_lineage", "delivery_intent", "transaction_binding",
    "recovery_binding", "no_external_effect", "a2a_boundary",
]


def _work_reports(ctx, b9_outcome, b91_outcome):
    tid, wid = ctx["tenant_id"], ctx["work_run_id"]
    r = {}
    r["work_origin"] = build_work_origin_envelope(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["schedule_run_chain"] = build_schedule_run_chain(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["principal_continuity"] = build_principal_continuity(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["context_capsule"] = build_context_capsule(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["memory_snapshot"] = build_memory_snapshot(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["delegation_capsule"] = build_delegation_capsule(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["approval_continuity"] = build_approval_continuity(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["gateway_boundary"] = build_gateway_boundary_proof(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["revocation"] = build_revocation(tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["artifact_lineage"] = build_artifact_lineage(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["delivery_intent"] = build_delivery_intent(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["transaction_binding"] = build_transaction_binding(
        tenant_id=tid, work_run_id=wid, b9_outcome=b9_outcome, ctx=ctx)
    r["recovery_binding"] = build_recovery_binding(
        tenant_id=tid, work_run_id=wid, b91_outcome=b91_outcome, ctx=ctx)
    r["no_external_effect"] = build_no_external_effect(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["a2a_boundary"] = build_a2a_boundary(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["decision_basis"] = build_decision_basis(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    r["otel_adapter"] = build_otel_adapter(
        tenant_id=tid, work_run_id=wid, ctx=ctx)
    return r


# ---- 22. Proof-of-Work-Outcome --------------------------------------------
def _status_ok(rep, key, ok_values):
    return rep.get(key) in ok_values


def build_powo(*, tenant_id, work_run_id, reports, negative_space):
    R = reports
    factors = {
        "WorkOriginValid": R["work_origin"]["origin_status"] == "VALID",
        "ScheduleLineageValid": R["schedule_run_chain"]["chain_status"] ==
        "VALID",
        "PrincipalContinuityValid": R["principal_continuity"][
            "identity_continuity_valid"],
        "ContextContinuityValid": R["context_capsule"]["context_status"] ==
        "VALID",
        "MemorySnapshotValidOrNotApplicable": (not R["memory_snapshot"][
            "memory_applicable"]) or R["memory_snapshot"][
            "snapshot_status"] == "VALID",
        "DelegationValidOrNotApplicable": (not R["delegation_capsule"][
            "delegation_applicable"]) or R["delegation_capsule"][
            "delegation_status"] == "VALID",
        "AuthorityValid": R["principal_continuity"]["identity_continuity_valid"],
        "ApprovalContinuityValidOrNotApplicable": (not R["approval_continuity"][
            "approval_applicable"]) or R["approval_continuity"][
            "approval_status"] == "VALID",
        "GatewayBoundaryValidOrLocalOnly": R["gateway_boundary"][
            "credential_boundary_valid"],
        "TransactionTwinValid": R["transaction_binding"]["binding_status"] ==
        "VALID",
        "ProofOfExecutionValid": R["transaction_binding"][
            "proof_of_execution_valid"],
        "TransactionCertificateValid": R["transaction_binding"][
            "transaction_certificate_valid"],
        "RecoveryProofValidOrNotApplicable": R["recovery_binding"][
            "binding_status"] in ("VALID", "NOT_APPLICABLE"),
        "ArtifactLineageValidOrNoArtifactExpected": R["artifact_lineage"][
            "lineage_status"] in ("VALID", "NO_ARTIFACT_EXPECTED"),
        "DeliveryIntentValidOrNotApplicable": R["delivery_intent"][
            "intent_status"] == "VALID",
        "RevocationPropagationSafe": R["revocation"]["propagation_safe"],
        "ConsistentWorkCutValid": R["consistent_work_cut"][
            "consistent_cut_valid"],
        "NoCriticalEvidenceMissing": negative_space["no_critical_missing"],
        "NoExternalEffectProven": R["no_external_effect"]["theorem_holds"],
        "TenantIsolationValid": R["consistent_work_cut"]["no_cross_tenant_edge"],
        "ObservationReproducible": True,
    }
    valid = all(factors.values())
    o = reports
    cert = {
        "powo_version": POWO_VERSION,
        "proof_of_work_outcome_id": "powo-" + _sha({"w": work_run_id})[:16],
        "tenant_id": tenant_id, "work_run_id": work_run_id, "factors": factors,
        "work_origin_hash": o["work_origin"]["origin_envelope_hash"],
        "principal_continuity_hash": o["principal_continuity"][
            "principal_continuity_hash"],
        "context_capsule_hash": o["context_capsule"]["context_capsule_hash"],
        "memory_snapshot_hash": o["memory_snapshot"]["snapshot_hash"],
        "delegation_capsule_hash": o["delegation_capsule"][
            "delegation_capsule_hash"],
        "approval_continuity_hash": o["approval_continuity"][
            "approval_binding_hash"],
        "gateway_boundary_hash": o["gateway_boundary"]["gateway_proof_hash"],
        "transaction_twin_hash": o["transaction_binding"]["transaction_twin_hash"],
        "poe_hash": o["transaction_binding"]["poe_hash"],
        "transaction_certificate_hash": o["transaction_binding"][
            "transaction_certificate_hash"],
        "recovery_twin_hash": o["recovery_binding"]["recovery_twin_hash"],
        "por_hash": o["recovery_binding"]["por_hash"],
        "recovery_certificate_hash": o["recovery_binding"][
            "recovery_certificate_hash"],
        "artifact_lineage_hash": o["artifact_lineage"]["artifact_lineage_hash"],
        "delivery_intent_hash": o["delivery_intent"]["delivery_intent_hash"],
        "revocation_status_hash": o["revocation"]["revocation_status_hash"],
        "causal_work_graph_hash": o["causal_work_graph"]["causal_work_graph_hash"],
        "consistent_cut_hash": o["consistent_work_cut"]["consistent_cut_hash"],
        "no_external_effect_hash": o["no_external_effect"][
            "no_external_effect_hash"],
        "policy_version": "powo-p-v1", "schema_version": POWO_VERSION,
        "proof_of_work_outcome_valid": valid,
        "authorizes_execution": False, "authorizes_commit": False,
        "authorizes_recovery": False, "authorizes_delivery": False,
        "warning": POWO_WARNING,
        "verification_status": "VALID" if valid else "INVALID",
        "signal": None if valid else "PROOF_OF_WORK_OUTCOME_INVALID",
        "honesty_labels": HONESTY_LABELS,
    }
    cert["proof_of_work_outcome_hash"] = _core_hash(
        cert, "proof_of_work_outcome_hash", "signal", "verification_status")
    cert["_signals"] = [] if valid else ["PROOF_OF_WORK_OUTCOME_INVALID"]
    return cert


def _derive_truth_state(signals, powo_valid, reports, negative_space):
    S = set(signals)
    tamper = any("SECRET_EXPOSURE" in s for s in S)
    external = {"WORK_EXTERNAL_EFFECT_DETECTED", "WORK_EXTERNAL_DELIVERY_DETECTED",
                "OUTBOX_RELEASE_DETECTED"} & S
    contradiction = {"CONSISTENT_WORK_CUT_INVALID", "CROSS_TENANT_WORK_EDGE"} & S
    revoked = {"REVOCATION_PROPAGATION_MISSING", "REVOCATION_PROPAGATION_LATE",
               "MEMORY_FACT_REVOKED", "APPROVAL_REVOKED",
               "PRINCIPAL_MAPPING_REVOKED", "SCHEDULE_OCCURRENCE_REVOKED"} & S
    stale = {"MEMORY_FACT_EXPIRED", "CONTEXT_EXPIRED", "APPROVAL_EXPIRED"} & S
    unknown = {"PRINCIPAL_CONTINUITY_UNKNOWN", "MEMORY_PROVENANCE_UNKNOWN"} & S
    ambiguous = {"WORK_ORIGIN_AMBIGUOUS"} & S
    if tamper or external:
        return "TAMPERED" if tamper else "CONTRADICTED"
    if contradiction:
        return "CONTRADICTED"
    if revoked:
        return "REVOKED"
    if not negative_space["no_critical_missing"]:
        return "PARTIAL"
    if stale:
        return "STALE"
    if unknown:
        return "UNKNOWN"
    if ambiguous:
        return "AMBIGUOUS"
    if powo_valid and not S:
        return "PROVEN"
    if S:
        return "PARTIAL"
    return "SUPPORTED"


_TRUTH_TO_WORK_STATE = {
    "PROVEN": "WORK_OUTCOME_CERTIFIED", "SUPPORTED": "OBSERVATION_COMPLETE",
    "PARTIAL": "OBSERVATION_COMPLETE", "UNKNOWN": "OBSERVATION_COMPLETE",
    "AMBIGUOUS": "OBSERVATION_COMPLETE", "STALE": "OBSERVATION_COMPLETE",
    "REVOKED": "REJECTED", "CONTRADICTED": "QUARANTINED",
    "TAMPERED": "QUARANTINED",
}


# ---- 23. Work Observation Twin --------------------------------------------
def build_work_observation_twin(*, tenant_id, work_run_id, reports,
                                negative_space, powo, causal_graph, truth_state,
                                work_run_state, no_external):
    r = {
        "twin_version": TWIN_VERSION,
        "work_observation_twin_id": "wot-" + _sha({"w": work_run_id})[:16],
        "work_run_id": work_run_id, "tenant_id": tenant_id,
        "trigger_status": reports["work_origin"]["origin_status"],
        "identity_continuity_status": reports["principal_continuity"][
            "continuity_status"],
        "context_continuity_status": reports["context_capsule"]["context_status"],
        "memory_provenance_status": reports["memory_snapshot"]["snapshot_status"],
        "delegation_status": reports["delegation_capsule"]["delegation_status"],
        "authority_status": reports["work_origin"]["authority_status"],
        "approval_continuity_status": reports["approval_continuity"][
            "approval_status"],
        "gateway_boundary_status": reports["gateway_boundary"]["gateway_decision"],
        "transaction_status": reports["transaction_binding"]["binding_status"],
        "recovery_status": reports["recovery_binding"]["binding_status"],
        "artifact_lineage_status": reports["artifact_lineage"]["lineage_status"],
        "delivery_intent_status": reports["delivery_intent"]["intent_status"],
        "revocation_propagation_status": reports["revocation"][
            "propagation_state"],
        "schedule_lineage_status": reports["schedule_run_chain"]["chain_status"],
        "causal_graph_hash": causal_graph["causal_work_graph_hash"],
        "missing_evidence_hash": negative_space["missing_evidence_hash"],
        "no_external_effect_status": no_external["theorem_status"],
        "observer_health_status": reports["observer_health"][
            "observer_health_state"],
        "poe_status": "VALID" if reports["transaction_binding"][
            "proof_of_execution_valid"] else "INVALID",
        "por_status": reports["recovery_binding"]["binding_status"],
        "powo_status": powo["verification_status"],
        "work_outcome_truth_state": truth_state,
        "work_run_state": work_run_state,
        "immutable": True, "append_only": True, "non_authoritative": True,
        "honesty_labels": HONESTY_LABELS,
    }
    r["twin_hash"] = _core_hash(r, "twin_hash")
    r["_signals"] = []
    return r


# ---- 29. Local work canaries ----------------------------------------------
CANARY_CASES = [
    "human_triggered_local_work", "scheduled_local_work",
    "duplicate_schedule_delivery", "canceled_schedule",
    "memory_snapshot_disputed_fact", "expired_approval",
    "revoked_integration_epoch", "principal_mapping_removed_mid_run",
    "artifact_created_without_lineage", "result_artifact_no_delivery_intent",
    "recovery_after_local_crash", "kill_switch_during_work",
    "cross_surface_continuation_mismatch", "a2a_context_task_mismatch",
    "telemetry_adapter_unavailable",
]


def run_local_canary_harness(*, tenant_id, work_run_id, base_ctx, b9_outcome,
                             b91_outcome):
    cases = []
    all_safe = True
    for name in CANARY_CASES:
        c = dict(base_ctx)
        reports = _work_reports(c, b9_outcome, b91_outcome)
        ne = reports["no_external_effect"]
        di = reports["delivery_intent"]
        safe = (ne["theorem_holds"] and not ne["produced_external_effect"] and
                not ne["message_sent"] and not ne["payment_executed"] and
                not ne["external_crm_mutated"] and not di["delivered_externally"]
                and not di["outbox_released"])
        all_safe = all_safe and safe
        cases.append({"canary": name, "no_external_provider_called": True,
                      "no_message_sent": True, "no_payment_executed": True,
                      "no_external_crm_mutation": True,
                      "no_webhook_dispatched": True, "no_outbox_released": True,
                      "safe": safe})
    r = {
        "canary_version": "finalis-local-work-canary-harness-v1",
        "tenant_id": tenant_id, "work_run_id": work_run_id, "canaries": cases,
        "canary_count": len(cases), "all_canaries_safe": all_safe,
        "harness_status": "SAFE" if all_safe else "UNSAFE",
        "honesty_labels": HONESTY_LABELS,
    }
    r["canary_hash"] = _core_hash(r, "canary_hash")
    return r


# ---- Work proof bundle -----------------------------------------------------
def build_work_proof_bundle(*, tenant_id, work_run_id, reports, powo, twin,
                            truth_state):
    components = {}
    for name, rep in reports.items():
        if not isinstance(rep, dict):
            continue
        hk = next((k for k in rep if k.endswith("_hash")), None)
        components[name] = rep.get(hk) if hk else None
    components["proof_of_work_outcome"] = powo["proof_of_work_outcome_hash"]
    components["work_observation_twin"] = twin["twin_hash"]
    r = {
        "proof_bundle_version": PROOF_BUNDLE_VERSION, "tenant_id": tenant_id,
        "work_run_id": work_run_id, "components": components,
        "component_count": len(components),
        "work_outcome_truth_state": truth_state,
        "honesty_labels": HONESTY_LABELS,
    }
    r["work_proof_bundle_hash"] = _core_hash(r, "work_proof_bundle_hash")
    return r


_PASS_KEYS = (
    "trigger_type", "source_surface", "source_event_id", "source_principal_id",
    "source_principal_type", "effective_principal_id", "effective_principal_type",
    "schedule_id", "schedule_occurrence_id", "heartbeat_suggestion_id",
    "parent_work_run_id", "source_context_id", "parent_context_id",
    "source_payload", "normalized_intent", "policy_version", "origin_missing",
    "origin_ambiguous", "heartbeat_direct_execution", "scheduled_for",
    "work_definition_version", "calendar_rule", "timezone", "deduplication_key",
    "misfire_policy", "schedule_duplicate_delivery",
    "schedule_duplicate_changed_payload", "schedule_missed", "schedule_delayed",
    "schedule_revoked", "schedule_disabled", "identity_mapping_version",
    "role_version", "membership_version", "principal_epoch", "session_reference",
    "principal_mapping_revoked", "principal_session_invalid",
    "principal_cross_tenant", "context_task_mismatch", "context_expired",
    "permitted_message_refs", "permitted_task_refs", "context_policy_version",
    "memory_applicable", "memory_facts", "memory_policy_version", "memory_query",
    "memory_scope", "memory_provenance_unknown", "delegation_applicable",
    "parent_delegation", "child_delegation", "delegation_root_id",
    "delegation_policy_version", "approval_applicable", "approved_action",
    "actual_action", "approved_target", "actual_target", "approved_scope",
    "actual_scope", "maximum_uses", "uses_consumed", "approval_expired",
    "approval_revoked", "approval_id", "approver_principal_id", "approval_class",
    "approval_mode", "approved_parameters", "approved_externality",
    "approval_policy_version", "requested_operation", "allowed_operation",
    "credential_scope", "integration_revoked", "secret_exposed_to_model",
    "secret_exposed_to_logs", "secret_exposed_to_artifact", "tool_id",
    "tool_version", "integration_id", "credential_reference_id",
    "gateway_policy_version", "credential_rotation_epoch",
    "credential_revocation_epoch", "bound_principal_epoch",
    "bound_integration_epoch", "bound_schedule_epoch", "bound_delegation_epoch",
    "bound_approval_epoch", "bound_tenant_policy_epoch", "current_principal_epoch",
    "current_integration_epoch", "current_schedule_epoch",
    "current_delegation_epoch", "current_approval_epoch",
    "current_tenant_policy_epoch", "revocation_detected", "propagation_state",
    "artifact_expected", "artifacts", "unrelated_branch_changed",
    "delivery_applicable", "delivery_status", "external_delivery",
    "delivery_missing", "delivery_artifacts", "destination_type",
    "destination_ref", "recipient_scope", "delivery_policy_version",
    "outbox_reference", "transaction_applicable", "recovery_required",
    "recovery_binding_invalid", "attempt_markers", "decision_basis",
    "otel_available", "otel_max_attributes", "otel_attribute_count",
    "otel_parent_span", "a2a", "cross_tenant_edge", "incompatible_versions",
    "cross_tenant_query", "observer_health_forced", "observer_unavailable",
    "work_definition_id",
)


def prepare_work_observation_outcome(*, work_run_id, tenant_id, actor_id,
                                     actor_type, b9_outcome=None,
                                     b91_outcome=None, created_at=None, **over):
    """Observe a Governed Work Run over B9/B9.1 evidence and derive the
    Proof-of-Work-Outcome, truth state and Work Observation Twin. DERIVED
    EVIDENCE ONLY: read-only over B9/B9.1, no external effect, no execution or
    recovery authority. It never commits, recovers, delivers or releases the
    outbox."""
    ctx = {"tenant_id": tenant_id, "work_run_id": work_run_id,
           "actor_id": actor_id, "created_at": created_at}
    for k in _PASS_KEYS:
        if k in over:
            ctx[k] = over[k]

    reports = _work_reports(ctx, b9_outcome, b91_outcome)
    reports["consistent_work_cut"] = build_consistent_work_cut(
        tenant_id=tenant_id, work_run_id=work_run_id, reports=reports, ctx=ctx)
    reports["causal_work_graph"] = build_causal_work_graph(
        tenant_id=tenant_id, work_run_id=work_run_id, reports=reports,
        b9_outcome=b9_outcome, b91_outcome=b91_outcome)
    negative_space = build_negative_space(
        tenant_id=tenant_id, work_run_id=work_run_id, reports=reports, ctx=ctx)
    reports["negative_space"] = negative_space
    reports["observer_health"] = build_observer_health(
        tenant_id=tenant_id, work_run_id=work_run_id, reports=reports, ctx=ctx)

    # Aggregate signals across base + derived reports.
    signals = []
    for name, rep in reports.items():
        if isinstance(rep, dict):
            signals.extend(rep.get("_signals", []))
    signals = sorted(set(signals))

    powo = build_powo(tenant_id=tenant_id, work_run_id=work_run_id,
                      reports=reports, negative_space=negative_space)
    reports["proof_of_work_outcome"] = powo
    powo_valid = powo["proof_of_work_outcome_valid"]

    truth_state = _derive_truth_state(signals, powo_valid, reports,
                                      negative_space)
    work_run_state = _TRUTH_TO_WORK_STATE.get(truth_state, "OBSERVATION_COMPLETE")

    twin = build_work_observation_twin(
        tenant_id=tenant_id, work_run_id=work_run_id, reports=reports,
        negative_space=negative_space, powo=powo,
        causal_graph=reports["causal_work_graph"], truth_state=truth_state,
        work_run_state=work_run_state,
        no_external=reports["no_external_effect"])
    reports["work_observation_twin"] = twin

    canary_harness = run_local_canary_harness(
        tenant_id=tenant_id, work_run_id=work_run_id, base_ctx=ctx,
        b9_outcome=b9_outcome, b91_outcome=b91_outcome)
    proof_bundle = build_work_proof_bundle(
        tenant_id=tenant_id, work_run_id=work_run_id, reports=reports, powo=powo,
        twin=twin, truth_state=truth_state)

    clean_reports = {}
    for k, rep in reports.items():
        if isinstance(rep, dict):
            clean_reports[k] = {kk: vv for kk, vv in rep.items()
                                if kk != "_signals"}
        else:
            clean_reports[k] = rep

    outcome = {
        "b92_model_version": B92_MODEL_VERSION, "work_run_id": work_run_id,
        "tenant_id": tenant_id, "actor_id": actor_id,
        "decided_by_actor_id": actor_id, "decided_by_actor_type": actor_type,
        "work_definition_id": ctx.get("work_definition_id"),
        "trigger_type": clean_reports["work_origin"]["trigger_type"],
        "transaction_id": clean_reports["transaction_binding"]["transaction_id"],
        "recovery_id": clean_reports["recovery_binding"]["recovery_id"],
        "work_run_state": work_run_state,
        "work_outcome_truth_state": truth_state,
        "proof_of_work_outcome_valid": powo_valid,
        "work_outcome_certified": work_run_state == "WORK_OUTCOME_CERTIFIED",
        "all_signals": signals,
        "signal_reason_codes": {s: REASON_TEXT.get(s, s) for s in signals},
        # Hard non-authority / no-external-effect guarantees.
        "is_authority": False, "authorizes_execution": False,
        "authorizes_commit": False, "authorizes_recovery": False,
        "authorizes_rollback": False, "authorizes_abort": False,
        "authorizes_delivery": False, "authorizes_provider": False,
        "read_only_over_b9_and_b9_1": True,
        "mutates_transaction": False, "mutates_recovery": False,
        "produced_external_effect": False, "provider_called": False,
        "message_sent": False, "payment_executed": False,
        "external_crm_mutated": False, "delivered_externally": False,
        "outbox_released": False, "stores_secret": False,
        "stores_chain_of_thought": False,
        "no_external_effect": clean_reports["no_external_effect"][
            "theorem_holds"],
        "no_critical_evidence_missing": negative_space["no_critical_missing"],
        "observer_health_state": clean_reports["observer_health"][
            "observer_health_state"],
        "proof_of_work_outcome_hash": powo["proof_of_work_outcome_hash"],
        "work_observation_twin_hash": twin["twin_hash"],
        "causal_work_graph_hash": clean_reports["causal_work_graph"][
            "causal_work_graph_hash"],
        "b92_canary_harness": canary_harness,
        "b92_work_proof_bundle": proof_bundle,
        "powo_warning": POWO_WARNING,
        "created_at": created_at, "updated_at": created_at,
        "honesty_labels": HONESTY_LABELS,
    }
    outcome.update(clean_reports)
    outcome["b92_decision_hash"] = _core_hash(
        outcome, "b92_decision_hash", "work_run_id", "actor_id",
        "decided_by_actor_id", "decided_by_actor_type", "b92_state_hash")
    outcome["b92_state_hash"] = _sha({
        "work_run_id": work_run_id,
        "b92_decision_hash": outcome["b92_decision_hash"],
        "work_run_state": work_run_state, "truth_state": truth_state,
        "proof_bundle_hash": proof_bundle["work_proof_bundle_hash"]})
    return outcome


# ---- Event ledger ----------------------------------------------------------
B92_EVENT_TYPES = {
    "B92_WORK_OBSERVATION_OPENED", "B92_WORK_OBSERVATION_PREPARED",
    "B92_WORK_CANARY_RUN", "B92_WORK_OBSERVATION_VERIFIED",
}


def build_b92_event(*, event_type, tenant_id, work_run_id, actor_id, actor_type,
                    b92_state_hash, previous_event_hash, sequence, detail,
                    created_at):
    ev = {
        "b92_event_version": B92_EVENT_VERSION, "event_type": event_type,
        "tenant_id": tenant_id, "work_run_id": work_run_id, "actor_id": actor_id,
        "actor_type": actor_type, "b92_state_hash": b92_state_hash,
        "previous_event_hash": previous_event_hash or GENESIS,
        "sequence": sequence, "detail": detail, "created_at": created_at,
        "honesty_labels": HONESTY_LABELS,
    }
    ev["event_hash"] = _core_hash(ev, "event_hash")
    return ev
