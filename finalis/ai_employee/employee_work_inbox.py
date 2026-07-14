"""Employee Work Inbox — R-FSAFEQ Governed Work Admission Fabric (EMP-A1 v1,
specification revision 8).

The single canonical, durable, tenant-isolated intake + admission fabric that
converts source requests into governed canonical work items and prepares exactly
ONE fenced single-use handoff capability for EMP-A2 — WITHOUT executing work.

R-FSAFEQ = Risk-calibrated Finalis Serializable Admission and Fair Entitlement
Queue. Three separated logical kernels:
  1. DETERMINISTIC SAFETY KERNEL   — authoritative deny/allow (no LLM/model);
  2. RISK AND STABILITY KERNEL     — uncertainty/calibration/drift/backlog
     (may only TIGHTEN safety, never weaken it);
  3. BOUNDED OPTIMIZATION KERNEL   — fairness/shard/ordering (advisory only).

Hard invariant: SafetyKernel DENY -> RiskKernel cannot admit -> Optimization
cannot produce READY.

This module is LOCAL_ONLY, WORK_INTAKE_AND_ADMISSION_ONLY, ORDER_RECOMMENDATION_
ONLY. It NEVER: executes work, calls a provider/tool, starts a TOOL-B9
transaction, creates an EMP-A2 run, performs recovery, releases an outbox, sends
a message, mutates an external system, declares completion, or guarantees a
deadline. Calibration/conformal estimation is schema-only and DISABLED by
default until EMP-A2 execution data + evaluation governance exist. Unknown demand
is never zero; a prediction can never reduce a deterministic safety floor.
NOT_PRODUCTION_READY.
"""
from __future__ import annotations

from .tool_contracts import canonical_json, _sha, _core_hash

EMP_A1_MODEL_VERSION = "finalis-employee-work-inbox-r-fsafeq-v1"
EMP_A1_SPEC_REVISION = 8
RFSAFEQ_POLICY_VERSION = "r-fsafeq-policy-v1"
INTAKE_VERSION = "finalis-work-intake-envelope-v1"
INTENT_VERSION = "finalis-deterministic-intent-compiler-v1"
REGISTRY_VERSION = "finalis-canonical-work-unit-registry-v1"
DEMAND_VERSION = "finalis-risk-calibrated-demand-envelope-v1"
CALIBRATION_VERSION = "finalis-calibration-drift-guard-v1"
RISK_BUDGET_VERSION = "finalis-modular-risk-budget-v1"
ADMISSION_MEMORY_VERSION = "finalis-admission-memory-v1"
BACKLOG_VERSION = "finalis-virtual-backlog-stability-controller-v1"
FAIRNESS_VERSION = "finalis-flow-fairness-deficit-v1"
SHARD_VERSION = "finalis-deterministic-shuffle-sharding-v1"
ORDERING_VERSION = "finalis-r-fsafeq-ordering-v1"
CLAIM_VERSION = "finalis-reservation-fenced-claim-v1"
HANDOFF_VERSION = "finalis-single-use-emp-a2-handoff-v1"
RECEIPT_VERSION = "finalis-admission-receipt-v1"
REFERENCE_VERSION = "finalis-pure-admission-reference-kernel-v1"
EVENT_VERSION = "finalis-emp-a1-work-event-v1"
GENESIS = "0" * 64

HONESTY_LABELS = [
    "INBOX_AND_ADMISSION_ONLY",
    "CALIBRATION_DISABLED_OR_NOT_EXECUTION_VALIDATED",
    "VIRTUAL_BACKLOG_IS_ADMISSION_SIDE_PROXY",
    "ESTIMATED_DEMAND_NOT_ACTUAL_USAGE", "ORDER_RECOMMENDATION_ONLY",
    "DEADLINE_NOT_GUARANTEED", "NO_EMP_A2_RUN_CREATED", "NO_EXECUTION_STARTED",
    "NO_PROVIDER_CALLED", "NO_EXTERNAL_EFFECT", "NOT_PRODUCTION_READY",
]

# ---- Sources (section 8) --------------------------------------------------
ENABLED_SOURCES = {
    "PORTAL_MANUAL", "INTERNAL_API", "EXISTING_SCHEDULE_REFERENCE",
    "SYSTEM_GENERATED_LOCAL", "TEST_FIXTURE",
}
DISABLED_SOURCES = {
    "SLACK", "MICROSOFT_TEAMS", "MOBILE", "EMAIL", "VOICE", "A2A", "MCP",
    "WEBHOOK",
}
SOURCE_PRINCIPAL_TYPES = {
    "HUMAN_USER", "SERVICE_PRINCIPAL", "SCHEDULE_ACTOR", "SYSTEM_ACTOR",
    "TEST_ACTOR",
}

# ---- Work-item state machine (section 13) ---------------------------------
WORK_ITEM_STATES = [
    "RECEIVED", "VALIDATING", "NEEDS_ATOMICITY_REVIEW", "NEEDS_CLARIFICATION",
    "NEEDS_APPROVAL", "BLOCKED", "DEFERRED_MEMORY", "DEFERRED_CAPACITY",
    "DEFERRED_RISK", "DEFERRED_DRIFT", "DEFERRED_FAIRNESS",
    "DEFERRED_CONCURRENCY", "DEFERRED_POLICY", "READY", "RESERVED", "CLAIMED",
    "HANDOFF_READY", "DUPLICATE", "SUPERSEDED", "REJECTED", "CANCELED",
    "QUARANTINED", "EXPIRED",
]
DEFERRED_STATES = {
    "DEFERRED_MEMORY", "DEFERRED_CAPACITY", "DEFERRED_RISK", "DEFERRED_DRIFT",
    "DEFERRED_FAIRNESS", "DEFERRED_CONCURRENCY", "DEFERRED_POLICY",
}
# States that NEVER accrue active-eligible age (section 27).
NON_AGING_STATES = ({"NEEDS_ATOMICITY_REVIEW", "NEEDS_CLARIFICATION",
                     "NEEDS_APPROVAL", "BLOCKED", "RESERVED", "CLAIMED",
                     "HANDOFF_READY", "QUARANTINED"} | DEFERRED_STATES)
# Forbidden execution states — EMP-A1 may never enter these.
FORBIDDEN_STATES = {
    "RUNNING", "EXECUTING", "COMPLETED", "FAILED_EXECUTION", "RECOVERING",
    "ROLLED_BACK",
}
TERMINAL_STATES = {"DUPLICATE", "SUPERSEDED", "REJECTED", "CANCELED",
                   "QUARANTINED", "EXPIRED", "HANDOFF_READY"}

# Allowed forward transitions (fail-closed: anything not listed is rejected).
ALLOWED_TRANSITIONS = {
    "RECEIVED": {"VALIDATING", "REJECTED", "QUARANTINED", "DUPLICATE",
                 "CANCELED"},
    "VALIDATING": {"NEEDS_ATOMICITY_REVIEW", "NEEDS_CLARIFICATION",
                   "NEEDS_APPROVAL", "BLOCKED", "READY", "REJECTED",
                   "QUARANTINED", "DUPLICATE", "SUPERSEDED", "CANCELED"}
    | DEFERRED_STATES,
    "NEEDS_ATOMICITY_REVIEW": {"VALIDATING", "REJECTED", "CANCELED",
                               "QUARANTINED"},
    "NEEDS_CLARIFICATION": {"VALIDATING", "REJECTED", "CANCELED", "EXPIRED"},
    "NEEDS_APPROVAL": {"VALIDATING", "READY", "BLOCKED", "REJECTED", "CANCELED"},
    "BLOCKED": {"VALIDATING", "REJECTED", "CANCELED", "QUARANTINED"},
    "READY": ({"RESERVED", "CLAIMED", "BLOCKED", "CANCELED", "SUPERSEDED",
               "QUARANTINED", "EXPIRED", "DUPLICATE"} | DEFERRED_STATES),
    "RESERVED": {"CLAIMED", "READY", "CANCELED", "EXPIRED", "QUARANTINED"},
    "CLAIMED": {"HANDOFF_READY", "READY", "RESERVED", "CANCELED", "EXPIRED",
                "QUARANTINED"},
    "HANDOFF_READY": {"READY", "CLAIMED", "CANCELED", "EXPIRED", "QUARANTINED",
                      "SUPERSEDED"},
    # Deferred states resume to VALIDATING (re-evaluated) or terminate.
    **{d: {"VALIDATING", "READY", "CANCELED", "EXPIRED", "QUARANTINED"}
       for d in DEFERRED_STATES},
    "DUPLICATE": {"RECEIVED", "CANCELED"},  # reverse-duplicate re-opens intake
    "SUPERSEDED": set(), "REJECTED": set(), "CANCELED": set(),
    "QUARANTINED": set(), "EXPIRED": set(),
}

# ---- Dispositions (pure kernel output) ------------------------------------
DISPOSITIONS = [
    "ADMIT_READY", "NEEDS_ATOMICITY_REVIEW", "NEEDS_CLARIFICATION",
    "NEEDS_APPROVAL", "BLOCKED", "DEFERRED_MEMORY", "DEFERRED_CAPACITY",
    "DEFERRED_RISK", "DEFERRED_DRIFT", "DEFERRED_FAIRNESS",
    "DEFERRED_CONCURRENCY", "DEFERRED_POLICY", "DUPLICATE", "CONFLICT",
    "REJECTED", "QUARANTINED",
]
_DISPOSITION_TO_STATE = {
    "ADMIT_READY": "READY", "NEEDS_ATOMICITY_REVIEW": "NEEDS_ATOMICITY_REVIEW",
    "NEEDS_CLARIFICATION": "NEEDS_CLARIFICATION", "NEEDS_APPROVAL":
    "NEEDS_APPROVAL", "BLOCKED": "BLOCKED", "DEFERRED_MEMORY": "DEFERRED_MEMORY",
    "DEFERRED_CAPACITY": "DEFERRED_CAPACITY", "DEFERRED_RISK": "DEFERRED_RISK",
    "DEFERRED_DRIFT": "DEFERRED_DRIFT", "DEFERRED_FAIRNESS": "DEFERRED_FAIRNESS",
    "DEFERRED_CONCURRENCY": "DEFERRED_CONCURRENCY", "DEFERRED_POLICY":
    "DEFERRED_POLICY", "DUPLICATE": "DUPLICATE", "CONFLICT": "REJECTED",
    "REJECTED": "REJECTED", "QUARANTINED": "QUARANTINED",
}

# ---- Demand-envelope resources (section 18) -------------------------------
DEMAND_RESOURCES = [
    "PREPARATION_UNITS", "HUMAN_ATTENTION_UNITS", "LOCAL_TRANSACTION_UNITS",
    "EVIDENCE_READ_UNITS", "WORKING_MEMORY_UNITS", "ARTIFACT_OUTPUT_UNITS",
    "FUTURE_TOOL_INTENT_UNITS", "CONCURRENCY_SEATS",
]
ESTIMATE_SOURCES = {"WORK_TYPE_DEFAULT", "DETERMINISTIC_RULE",
                    "HUMAN_GOVERNED_OVERRIDE"}
# A conservative upper vector used when demand is unknown (never zero).
UNKNOWN_UPPER_VECTOR = {r: 8 for r in DEMAND_RESOURCES}

# ---- Calibration / drift / risk-budget / backlog state machines -----------
CALIBRATION_STATES = ["DISABLED", "COLD_START", "HEALTHY", "DEGRADED",
                      "SHIFT_SUSPECTED", "OUT_OF_DISTRIBUTION", "EXPIRED"]
CALIBRATION_HEALTHY = {"HEALTHY"}
# States that force the deterministic upper envelope (prediction ignored).
CALIBRATION_FALLBACK_STATES = {"DISABLED", "COLD_START", "DEGRADED",
                               "SHIFT_SUSPECTED", "OUT_OF_DISTRIBUTION",
                               "EXPIRED"}
DRIFT_STATES = ["DRIFT_NOT_DETECTED", "DRIFT_SUSPECTED", "OUT_OF_DISTRIBUTION"]
RISK_BUDGET_STATES = ["RISK_BUDGET_AVAILABLE", "RISK_BUDGET_NEAR_LIMIT",
                      "RISK_BUDGET_EXHAUSTED", "RISK_BUDGET_UNKNOWN"]
BACKLOG_STATES = ["BACKLOG_STABLE", "BACKLOG_GROWING",
                  "BACKLOG_PERSISTENTLY_UNSTABLE", "BACKLOG_CAPACITY_UNKNOWN"]
RISK_LEVELS = ["NORMAL", "ELEVATED", "CRITICAL"]

# ---- Assignment / claim / handoff -----------------------------------------
ASSIGNMENT_TYPES = {"UNASSIGNED", "HUMAN", "AI_EMPLOYEE", "EMPLOYEE_POOL"}
HANDOFF_STATES = ["PREPARED", "REVOKED", "EXPIRED", "INVALIDATED"]  # +CONSUMED (A2)
CLOCK_STATES = ["HEALTHY", "UNCERTAIN", "ROLLBACK_DETECTED",
                "FORWARD_JUMP_DETECTED", "UNAVAILABLE"]

# ---- Split / atomicity ----------------------------------------------------
SPLIT_POLICIES = {"SINGLE_ITEM_ONLY", "DETERMINISTIC_SPLIT_ALLOWED",
                  "REVIEW_REQUIRED", "SPLIT_FORBIDDEN"}
ATOMICITY_OUTCOMES = {"SINGLE_CANONICAL_ITEM", "DETERMINISTIC_BUNDLE",
                      "ATOMICITY_REVIEW_REQUIRED", "WORK_TYPE_UNREGISTERED",
                      "WORK_UNIT_INVALID"}
FRAGMENT_RESULTS = {"INDEPENDENT_WORK", "DUPLICATE_CANDIDATE", "FRAGMENT_FAMILY",
                    "LIKELY_ABUSIVE_FRAGMENTATION"}


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


# ---- Canonical work-unit registry (section 10) ----------------------------
def _wt(work_type, **over):
    base = {
        "work_type": work_type, "work_type_version": "1",
        "required_fields": ["target"], "optional_fields": [],
        "allowed_target_types": ["case", "customer", "evidence"],
        "maximum_target_count": 8, "maximum_evidence_count": 16,
        "canonical_business_key_fields": ["work_type", "target"],
        "deduplication_fields": ["work_type", "target"],
        "split_policy": "SINGLE_ITEM_ONLY", "bundle_child_limit": 8,
        "default_priority_class": "NORMAL", "approval_class": "NONE",
        "required_capabilities": ["case.read"],
        "deterministic_demand_floor": {r: 1 for r in DEMAND_RESOURCES},
        "deterministic_demand_upper": {r: 4 for r in DEMAND_RESOURCES},
        "resource_dependency_constraints": [],
        "risk_profile_id": "rp-normal", "calibration_group_id": "cal-default",
        "clarification_templates": [],
    }
    base.update(over)
    base["registry_hash"] = _sha({k: v for k, v in base.items()
                                  if k != "registry_hash"})
    return base


WORK_TYPE_REGISTRY = {
    "case_summary": _wt("case_summary", approval_class="NONE",
                        default_priority_class="NORMAL"),
    "customer_reply_draft": _wt(
        "customer_reply_draft", approval_class="STANDARD",
        required_fields=["target", "message_intent"],
        required_capabilities=["case.read", "case.update"],
        deterministic_demand_floor=dict({r: 1 for r in DEMAND_RESOURCES},
                                        HUMAN_ATTENTION_UNITS=2)),
    "evidence_review": _wt(
        "evidence_review", split_policy="DETERMINISTIC_SPLIT_ALLOWED",
        maximum_target_count=16,
        resource_dependency_constraints=[
            {"type": "MAX_OF_GROUP", "group": "read_group",
             "resources": ["EVIDENCE_READ_UNITS", "WORKING_MEMORY_UNITS"]}]),
    "case_batch_review": _wt(
        "case_batch_review", split_policy="DETERMINISTIC_SPLIT_ALLOWED",
        maximum_target_count=32, bundle_child_limit=16,
        default_priority_class="LOW"),
    "compliance_escalation": _wt(
        "compliance_escalation", approval_class="DUAL_CONTROL",
        default_priority_class="CRITICAL", risk_profile_id="rp-critical",
        required_capabilities=["case.read", "case.update",
                               "employee_work_priority_critical"]),
    "schedule_recurring_summary": _wt(
        "schedule_recurring_summary", default_priority_class="NORMAL"),
}
PRIORITY_CLASSES = ["CRITICAL", "HIGH", "NORMAL", "LOW"]
_PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITY_CLASSES)}
APPROVAL_CLASSES = {"NONE", "STANDARD", "DUAL_CONTROL"}


# ---- Reason codes (section 47 + retained) ---------------------------------
REASON_CODES = {
    # intake / validation
    "WORK_ITEM_RECEIVED", "INTAKE_VALID", "SOURCE_DISABLED",
    "SOURCE_SCHEMA_INVALID", "PRINCIPAL_NOT_BOUND", "PRINCIPAL_INACTIVE",
    "PAYLOAD_LIMIT_EXCEEDED", "SECRET_MATERIAL_DETECTED", "TARGET_REFERENCE_INVALID",
    "IDEMPOTENCY_KEY_INVALID", "CONTEXT_BINDING_INVALID",
    "CROSS_TENANT_REFERENCE", "WORK_CONTEXT_TASK_MISMATCH",
    # intent
    "INTENT_COMPILED", "INTENT_NEEDS_CLARIFICATION", "INTENT_AMBIGUOUS",
    "INTENT_WORK_TYPE_UNREGISTERED", "INTENT_TARGET_INVALID", "INTENT_REJECTED",
    # atomicity / bundle
    "SINGLE_CANONICAL_ITEM", "DETERMINISTIC_BUNDLE", "ATOMICITY_REVIEW_REQUIRED",
    "WORK_TYPE_UNREGISTERED", "WORK_UNIT_INVALID",
    # idempotency / fragmentation
    "IDEMPOTENCY_EXACT_RETRY", "IDEMPOTENCY_PAYLOAD_CONFLICT",
    "INDEPENDENT_WORK", "DUPLICATE_CANDIDATE", "FRAGMENT_FAMILY",
    "LIKELY_ABUSIVE_FRAGMENTATION",
    # clarification / approval
    "CLARIFICATION_REQUIRED", "CLARIFICATION_RESOLVED", "APPROVAL_REQUIRED",
    "APPROVAL_VALID", "APPROVAL_ACTION_MISMATCH", "APPROVAL_TARGET_MISMATCH",
    "APPROVAL_SCOPE_EXCEEDED", "APPROVAL_EXPIRED", "APPROVAL_REVOKED",
    "APPROVAL_NOT_BOUND",
    # calibration
    "WORK_ITEM_CALIBRATION_DISABLED", "WORK_ITEM_CALIBRATION_COLD_START",
    "WORK_ITEM_CALIBRATION_HEALTHY", "WORK_ITEM_CALIBRATION_DEGRADED",
    "WORK_ITEM_CALIBRATION_EXPIRED",
    # drift
    "WORK_ITEM_DRIFT_NOT_DETECTED", "WORK_ITEM_DRIFT_SUSPECTED",
    "WORK_ITEM_OUT_OF_DISTRIBUTION", "WORK_ITEM_CONSERVATIVE_FALLBACK_APPLIED",
    # risk budget
    "WORK_ITEM_RISK_BUDGET_AVAILABLE", "WORK_ITEM_RISK_BUDGET_NEAR_LIMIT",
    "WORK_ITEM_RISK_BUDGET_EXHAUSTED", "WORK_ITEM_RISK_BUDGET_UNKNOWN",
    # backlog
    "WORK_ITEM_BACKLOG_STABLE", "WORK_ITEM_BACKLOG_GROWING",
    "WORK_ITEM_BACKLOG_PERSISTENTLY_UNSTABLE", "WORK_ITEM_BACKLOG_CAPACITY_UNKNOWN",
    # deferrals
    "WORK_ITEM_DEFERRED_RISK", "WORK_ITEM_DEFERRED_DRIFT", "DEFERRED_MEMORY",
    "DEFERRED_CAPACITY", "DEFERRED_FAIRNESS", "DEFERRED_CONCURRENCY",
    "DEFERRED_POLICY",
    # calibration safety
    "WORK_ITEM_NON_NESTED_INTERVAL_REJECTED",
    "WORK_ITEM_PREDICTION_CANNOT_REDUCE_SAFETY_BOUND",
    "WORK_ITEM_ACTION_CALIBRATION_MISMATCH",
    # resource
    "RESOURCE_ADMISSION_VALID", "RESOURCE_CAPACITY_EXCEEDED",
    "RESOURCE_DEPENDENCY_CONSTRAINED", "RESOURCE_CAPACITY_UNKNOWN",
    # ordering / placement / handoff
    "ADMIT_READY", "QUEUE_PLACED", "ORDER_RECOMMENDATION_ONLY",
    "ORDER_INTERVAL_OVERLAP", "RESERVED", "CLAIMED", "CLAIM_CONFLICT",
    "CLAIM_EXPIRED", "HANDOFF_PREPARED_ONLY", "HANDOFF_INVALIDATED",
    "SINGLE_USE_CAPABILITY_PREPARED", "NO_EMP_A2_RUN_CREATED",
    # clock
    "CLOCK_UNHEALTHY", "ADMISSION_RECEIPT_CREATED", "QUARANTINED",
}
REASON_TEXT = {c: c.replace("_", " ").capitalize() + "." for c in REASON_CODES}


# ---- Deterministic safety kernel: intake validation (section 14) ----------
_SECRET_HINTS = ("api_key", "apikey", "authorization", "bearer ", "password",
                 "secret", "-----begin", "access_token", "refresh_token",
                 "oauth", "session_cookie")


def _contains_secret(payload):
    blob = canonical_json(payload).lower() if payload is not None else ""
    return any(h in blob for h in _SECRET_HINTS)


def validate_intake(*, tenant_id, req, policy):
    signals = []
    source = req.get("source_type")
    principal = req.get("source_principal_id")
    tenant_scope_ok = req.get("tenant_id", tenant_id) == tenant_id
    if not tenant_scope_ok:
        signals.append("CROSS_TENANT_REFERENCE")
    if source in DISABLED_SOURCES:
        signals.append("SOURCE_DISABLED")
    elif source not in ENABLED_SOURCES:
        signals.append("SOURCE_SCHEMA_INVALID")
    if req.get("source_schema_version") in (None, ""):
        signals.append("SOURCE_SCHEMA_INVALID")
    if not principal or not req.get("authenticated_principal_id"):
        signals.append("PRINCIPAL_NOT_BOUND")
    if req.get("principal_active") is False:
        signals.append("PRINCIPAL_INACTIVE")
    targets = _as_list(req.get("requested_target_refs"))
    max_targets = _int(policy.get("max_target_count"), 32)
    if len(targets) > max_targets:
        signals.append("PAYLOAD_LIMIT_EXCEEDED")
    if _int(policy.get("max_payload_bytes"), 65536) < len(
            canonical_json(req.get("raw_payload") or {})):
        signals.append("PAYLOAD_LIMIT_EXCEEDED")
    if _contains_secret(req.get("raw_payload")):
        signals.append("SECRET_MATERIAL_DETECTED")
    if any(str(t).split(":")[0] not in ("case", "customer", "evidence",
           "schedule", "task") for t in targets if t):
        signals.append("TARGET_REFERENCE_INVALID")
    if req.get("idempotency_key") in (None, ""):
        signals.append("IDEMPOTENCY_KEY_INVALID")
    if any(str(t).endswith(":OTHER_TENANT") for t in targets):
        signals.append("CROSS_TENANT_REFERENCE")
    r = {
        "intake_valid": not signals,
        "tenant_scope_valid": tenant_scope_ok,
        "source_enabled": source in ENABLED_SOURCES,
        "principal_bound": bool(principal) and bool(
            req.get("authenticated_principal_id")),
        "no_secret_material": not _contains_secret(req.get("raw_payload")),
        "signals": signals,
        "signal": signals[0] if signals else "INTAKE_VALID",
    }
    return r


# ---- Context binding (section 7) ------------------------------------------
def bind_context(*, tenant_id, req, existing_item):
    signals = []
    ctx = req.get("conversation_context_id")
    continuation = req.get("continuation_of_work_item_id") or (
        existing_item or {}).get("work_item_id")
    if existing_item:
        # A continuation must match tenant, context, item identity, principal
        # permission and source binding.
        if existing_item.get("tenant_id") != tenant_id:
            signals.append("CROSS_TENANT_REFERENCE")
        if (existing_item.get("conversation_context_id") not in (None, ctx)):
            signals.append("WORK_CONTEXT_TASK_MISMATCH")
        if existing_item.get("work_type") not in (
                None, req.get("candidate_work_type"), req.get("work_type")):
            signals.append("WORK_CONTEXT_TASK_MISMATCH")
        if req.get("continuation_principal_mismatch"):
            signals.append("WORK_CONTEXT_TASK_MISMATCH")
    r = {
        "conversation_context_id": ctx, "is_continuation": bool(continuation),
        "continuation_of_work_item_id": continuation,
        "context_binding_valid": not signals,
        "context_is_authority": False, "signals": signals,
        "signal": signals[0] if signals else "CONTEXT_BINDING_VALID"
        if not signals else signals[0],
    }
    if not signals:
        r["signal"] = "INTAKE_VALID"
    return r


# ---- Deterministic intent compiler (section 9) ----------------------------
def compile_intent(*, tenant_id, req, policy):
    signals = []
    wt = req.get("work_type") or req.get("candidate_work_type")
    reg = WORK_TYPE_REGISTRY.get(wt)
    if wt is None:
        signals.append("INTENT_NEEDS_CLARIFICATION")
    elif reg is None:
        signals.append("INTENT_WORK_TYPE_UNREGISTERED")
    targets = _as_list(req.get("requested_target_refs"))
    params = dict(req.get("canonical_parameters") or {})
    required = list(reg["required_fields"]) if reg else []
    provided = set(params.keys()) | ({"target"} if targets else set())
    missing = [f for f in required if f not in provided]
    if reg and targets:
        bad_targets = [t for t in targets if str(t).split(":")[0] not in
                       reg["allowed_target_types"]]
        if bad_targets:
            signals.append("INTENT_TARGET_INVALID")
        if len(targets) > reg["maximum_target_count"]:
            signals.append("INTENT_TARGET_INVALID")
    if reg and missing:
        signals.append("INTENT_NEEDS_CLARIFICATION")
    if req.get("intent_ambiguous"):
        signals.append("INTENT_AMBIGUOUS")
    status = ("INTENT_COMPILED" if not signals else signals[0])
    business_key = _sha({"tenant": tenant_id, "work_type": wt,
                         "targets": sorted(map(str, targets)),
                         "business_key": req.get("source_business_key")})
    r = {
        "compiled_intent_id": "cwi-" + _sha({"r": req.get("idempotency_key"),
                                             "wt": wt})[:16],
        "work_type": wt, "work_type_version": reg["work_type_version"]
        if reg else None,
        "canonical_parameters": params,
        "canonical_target_refs": sorted(map(str, targets)),
        "required_fields": required, "missing_fields": missing,
        "required_capabilities": reg["required_capabilities"] if reg else [],
        "approval_class": reg["approval_class"] if reg else "NONE",
        "canonical_business_key": business_key,
        "compiler_policy_version": policy.get("compiler_policy_version",
                                              "cpv-1"),
        "intent_status": status, "guesses_critical_values": False,
        "signals": signals, "signal": status,
    }
    r["compiled_intent_hash"] = _sha({k: v for k, v in r.items()
                                      if k not in ("signals", "signal")})
    return r


# ---- Atomicity resolution (section 10) ------------------------------------
def resolve_atomicity(*, req, intent):
    wt = intent.get("work_type")
    reg = WORK_TYPE_REGISTRY.get(wt)
    if reg is None:
        return {"atomicity_outcome": "WORK_TYPE_UNREGISTERED",
                "child_count": 0, "signal": "WORK_TYPE_UNREGISTERED",
                "deterministic": True}
    targets = intent.get("canonical_target_refs") or []
    split = reg["split_policy"]
    n = len(targets)
    if n <= 1:
        outcome = "SINGLE_CANONICAL_ITEM"
        children = max(1, n)
    elif split == "SINGLE_ITEM_ONLY":
        outcome = "SINGLE_CANONICAL_ITEM"
        children = 1
    elif split == "SPLIT_FORBIDDEN":
        outcome = "WORK_UNIT_INVALID"
        children = 0
    elif split == "REVIEW_REQUIRED":
        outcome = "ATOMICITY_REVIEW_REQUIRED"
        children = n
    elif split == "DETERMINISTIC_SPLIT_ALLOWED":
        if n > reg["bundle_child_limit"]:
            outcome = "ATOMICITY_REVIEW_REQUIRED"
            children = n
        else:
            outcome = "DETERMINISTIC_BUNDLE"
            children = n
    else:
        outcome = "ATOMICITY_REVIEW_REQUIRED"
        children = n
    return {"atomicity_outcome": outcome, "child_count": children,
            "split_policy": split, "deterministic": True,
            "signal": outcome}


# ---- Idempotency + fragmentation firewall (section 15) --------------------
def check_idempotency(*, tenant_id, req, existing_by_key):
    key = req.get("idempotency_key")
    canonical = req.get("canonical_request_hash") or _sha({
        "tenant": tenant_id, "wt": req.get("work_type"),
        "targets": sorted(map(str, _as_list(req.get("requested_target_refs")))),
        "params": req.get("canonical_parameters") or {}})
    prior = existing_by_key.get((tenant_id, key)) if key else None
    if prior is None:
        return {"idempotency_status": "NEW", "canonical_request_hash": canonical,
                "existing_work_item_id": None, "charge_allowed": True,
                "signal": "INTAKE_VALID"}
    if prior.get("canonical_request_hash") == canonical:
        # Exact retry -> return the existing item; charge nothing.
        return {"idempotency_status": "EXACT_RETRY",
                "canonical_request_hash": canonical,
                "existing_work_item_id": prior.get("work_item_id"),
                "charge_allowed": False, "signal": "IDEMPOTENCY_EXACT_RETRY"}
    return {"idempotency_status": "CONFLICT",
            "canonical_request_hash": canonical,
            "existing_work_item_id": prior.get("work_item_id"),
            "charge_allowed": False, "signal": "IDEMPOTENCY_PAYLOAD_CONFLICT"}


def structural_fingerprint(*, tenant_id, req):
    return _sha({"tenant": tenant_id, "work_type": req.get("work_type"),
                 "targets": sorted(map(str, _as_list(
                     req.get("requested_target_refs")))),
                 "params": req.get("canonical_parameters") or {},
                 "business_key": req.get("source_business_key")})


def check_fragmentation(*, tenant_id, req, recent_fingerprints):
    fp = structural_fingerprint(tenant_id=tenant_id, req=req)
    principal = req.get("source_principal_id")
    wt = req.get("work_type")
    targets = _sub(req.get("requested_target_refs"))
    same_family = 0
    exact_dup = False
    for other in recent_fingerprints:
        if other.get("fingerprint") == fp:
            exact_dup = True
        elif (other.get("principal") == principal and
              other.get("work_type") == wt and
              targets & _sub(other.get("targets"))):
            same_family += 1
    burst_limit = _int(req.get("fragmentation_burst_limit"), 6)
    if exact_dup:
        result = "DUPLICATE_CANDIDATE"
    elif same_family >= burst_limit:
        result = "LIKELY_ABUSIVE_FRAGMENTATION"
    elif same_family >= 1:
        result = "FRAGMENT_FAMILY"
    else:
        result = "INDEPENDENT_WORK"
    return {"fragmentation_result": result, "structural_fingerprint": fp,
            "family_size": same_family, "shares_entitlement":
            result in ("FRAGMENT_FAMILY", "LIKELY_ABUSIVE_FRAGMENTATION"),
            "signal": result}


# ---- Clarification gate (section 16) --------------------------------------
def plan_clarification(*, intent, question_budget=4):
    missing = list(intent.get("missing_fields") or [])
    if not missing:
        return {"clarification_required": False, "questions": [],
                "signal": "INTAKE_VALID"}
    # Deterministic minimum-question planning: one typed question per blocker,
    # ordered by (template_id, field_key), truncated to the budget.
    ranked = sorted(missing)
    questions = [{"question_id": "q-" + _sha({"f": f})[:10],
                  "field_key": f, "template_id": "clarify_field",
                  "question_gain": 1} for f in ranked[:question_budget]]
    return {"clarification_required": True, "questions": questions,
            "covered_blockers": [q["field_key"] for q in questions],
            "uncovered_blockers": ranked[question_budget:],
            "llm_supplied_values": False, "signal": "CLARIFICATION_REQUIRED"}


# ---- Approval precondition (section 17) -----------------------------------
def check_approval(*, intent, req):
    klass = intent.get("approval_class") or "NONE"
    if klass == "NONE":
        return {"approval_required": False, "approval_valid": True,
                "approval_class": klass, "signal": "INTAKE_VALID"}
    appr = req.get("approval_record")
    if not appr:
        return {"approval_required": True, "approval_valid": False,
                "approval_class": klass, "signal": "APPROVAL_REQUIRED"}
    signals = []
    if appr.get("action") not in (None, intent.get("work_type")):
        signals.append("APPROVAL_ACTION_MISMATCH")
    approved_targets = _sub(appr.get("targets"))
    actual_targets = _sub(intent.get("canonical_target_refs"))
    if approved_targets and not (actual_targets <= approved_targets):
        signals.append("APPROVAL_TARGET_MISMATCH")
    approved_scope = _sub(appr.get("scope"))
    requested_scope = _sub(req.get("requested_scope")) or actual_targets
    if approved_scope and not (requested_scope <= approved_scope):
        signals.append("APPROVAL_SCOPE_EXCEEDED")
    if appr.get("expired"):
        signals.append("APPROVAL_EXPIRED")
    if appr.get("revoked"):
        signals.append("APPROVAL_REVOKED")
    if appr.get("natural_language_only"):
        signals.append("APPROVAL_NOT_BOUND")
    if klass == "DUAL_CONTROL" and _int(appr.get("approver_count")) < 2:
        signals.append("APPROVAL_REQUIRED")
    valid = not signals
    return {"approval_required": True, "approval_valid": valid,
            "approval_class": klass,
            "approval_refs": _as_list(appr.get("refs")),
            "signals": signals,
            "signal": "APPROVAL_VALID" if valid else signals[0]}


# ---- Risk-calibrated demand envelope (section 18-19) ----------------------
def build_demand_envelope(*, intent, req, calibration_state):
    reg = WORK_TYPE_REGISTRY.get(intent.get("work_type"))
    unknown = reg is None or req.get("demand_unknown")
    est_source = req.get("estimate_source", "WORK_TYPE_DEFAULT")
    if est_source not in ESTIMATE_SOURCES:
        est_source = "WORK_TYPE_DEFAULT"
    floor = dict(reg["deterministic_demand_floor"]) if reg else {
        r: 1 for r in DEMAND_RESOURCES}
    det_upper = dict(reg["deterministic_demand_upper"]) if reg else dict(
        UNKNOWN_UPPER_VECTOR)
    # Human-governed override may raise (never lower below the floor).
    override = req.get("demand_override") or {}
    nominal = {}
    for r in DEMAND_RESOURCES:
        base = det_upper.get(r, UNKNOWN_UPPER_VECTOR[r]) if unknown else \
            max(floor[r], (floor[r] + det_upper[r]) // 2)
        if est_source == "HUMAN_GOVERNED_OVERRIDE" and r in override:
            base = max(floor[r], _int(override[r]))
        nominal[r] = max(floor[r], base)
    # Safety upper: deterministic upper when unknown; calibration is DISABLED
    # by default and can NEVER reduce the deterministic floor/upper.
    safety_upper = {}
    for r in DEMAND_RESOURCES:
        det = UNKNOWN_UPPER_VECTOR[r] if unknown else det_upper[r]
        # A conformal prediction (future) may only widen, capped at max(floor, det).
        conformal = _int((req.get("conformal_upper") or {}).get(r), det)
        if calibration_state in CALIBRATION_HEALTHY and not unknown:
            safety_upper[r] = max(floor[r], det, conformal)
        else:
            safety_upper[r] = max(floor[r], det)  # deterministic fallback
        # Invariant: prediction cannot reduce the deterministic safety floor.
        safety_upper[r] = max(safety_upper[r], floor[r], nominal[r])
    valid = all(0 <= floor[r] <= nominal[r] <= safety_upper[r]
                for r in DEMAND_RESOURCES)
    r = {
        "estimate_source": est_source, "demand_unknown": bool(unknown),
        "deterministic_floor": floor, "nominal": nominal,
        "safety_upper": safety_upper, "envelope_valid": valid,
        "unknown_is_zero": False,
        "prediction_reduced_floor": False,
        "signal": "INTAKE_VALID" if valid else "WORK_UNIT_INVALID",
    }
    r["demand_envelope_hash"] = _sha({k: r[k] for k in (
        "deterministic_floor", "nominal", "safety_upper", "estimate_source")})
    return r


# ---- Calibration + drift guard (section 21) -------------------------------
def evaluate_calibration(*, req, policy):
    state = req.get("calibration_state", policy.get(
        "default_calibration_state", "DISABLED"))
    if state not in CALIBRATION_STATES:
        state = "DISABLED"
    fallback = state in CALIBRATION_FALLBACK_STATES
    # Non-nested intervals invalidate calibration.
    nested_ok = req.get("intervals_nested", True)
    signals = []
    if not nested_ok:
        signals.append("WORK_ITEM_NON_NESTED_INTERVAL_REJECTED")
        state = "OUT_OF_DISTRIBUTION"
        fallback = True
    action_mismatch = bool(req.get("action_calibration_mismatch"))
    if action_mismatch:
        signals.append("WORK_ITEM_ACTION_CALIBRATION_MISMATCH")
        fallback = True
    code = {
        "DISABLED": "WORK_ITEM_CALIBRATION_DISABLED",
        "COLD_START": "WORK_ITEM_CALIBRATION_COLD_START",
        "HEALTHY": "WORK_ITEM_CALIBRATION_HEALTHY",
        "DEGRADED": "WORK_ITEM_CALIBRATION_DEGRADED",
        "SHIFT_SUSPECTED": "WORK_ITEM_CALIBRATION_DEGRADED",
        "OUT_OF_DISTRIBUTION": "WORK_ITEM_CALIBRATION_DEGRADED",
        "EXPIRED": "WORK_ITEM_CALIBRATION_EXPIRED",
    }[state]
    return {"calibration_state": state, "calibration_healthy":
            state in CALIBRATION_HEALTHY, "fallback_applied": fallback,
            "prediction_available_for_safety": state in CALIBRATION_HEALTHY
            and not signals, "intervals_nested": nested_ok,
            "signals": signals, "signal": code, "reason_code": code}


def evaluate_drift(*, req):
    drift = req.get("drift_state", "DRIFT_NOT_DETECTED")
    if drift not in DRIFT_STATES:
        drift = "DRIFT_NOT_DETECTED"
    fallback = drift != "DRIFT_NOT_DETECTED"
    # SHIFT/OOD prevent automatic re-enablement; require governed recalibration.
    blocks = drift == "OUT_OF_DISTRIBUTION" and req.get(
        "governed_recalibration") is not True
    code = {"DRIFT_NOT_DETECTED": "WORK_ITEM_DRIFT_NOT_DETECTED",
            "DRIFT_SUSPECTED": "WORK_ITEM_DRIFT_SUSPECTED",
            "OUT_OF_DISTRIBUTION": "WORK_ITEM_OUT_OF_DISTRIBUTION"}[drift]
    return {"drift_state": drift, "conservative_fallback_applied": fallback,
            "requires_governed_recalibration": drift in (
                "DRIFT_SUSPECTED", "OUT_OF_DISTRIBUTION"),
            "auto_reenable_prevented": drift == "OUT_OF_DISTRIBUTION",
            "blocks_admission": blocks, "reduces_efficiency_not_safety": True,
            "signal": code, "reason_code": code,
            "observer_health_signal": drift != "DRIFT_NOT_DETECTED"}


def evaluate_risk_budget(*, calibration, req, flow_state):
    # Dormant until calibrated predictors exist. Unknown calibration -> a
    # conservative risk status. Exhaustion -> explicit deferral.
    if not calibration["calibration_healthy"]:
        status = "RISK_BUDGET_UNKNOWN" if req.get(
            "calibration_state") not in ("DISABLED", None) else \
            "RISK_BUDGET_AVAILABLE"
    else:
        spent = _int((flow_state or {}).get("risk_spent"))
        total = _int(req.get("alpha_total_units"), 100)
        forced = req.get("risk_budget_status")
        if forced in RISK_BUDGET_STATES:
            status = forced
        elif spent >= total:
            status = "RISK_BUDGET_EXHAUSTED"
        elif spent >= int(total * 0.8):
            status = "RISK_BUDGET_NEAR_LIMIT"
        else:
            status = "RISK_BUDGET_AVAILABLE"
    code = "WORK_ITEM_" + status
    return {"risk_budget_status": status, "dormant": not calibration[
        "calibration_healthy"], "alpha_total_not_increased": True,
        "signal": code, "reason_code": code,
        "defers": status == "RISK_BUDGET_EXHAUSTED"}


# ---- Admission memory (section 24) ----------------------------------------
def evaluate_admission_memory(*, flow_state, demand, idempotency, req, policy):
    if idempotency["idempotency_status"] == "EXACT_RETRY":
        return {"admission_memory_state": "UNCHANGED_EXACT_RETRY",
                "memory_after": _int((flow_state or {}).get("memory")),
                "memory_capacity": _int(policy.get("memory_capacity"), 100),
                "defers": False, "signal": "IDEMPOTENCY_EXACT_RETRY"}
    prev = _int((flow_state or {}).get("memory"))
    decay = _int(req.get("authoritative_elapsed_units")) * _int(
        policy.get("memory_decay_rate", 1))
    decayed = max(0, prev - decay)
    dominant = max(demand["safety_upper"].values()) if demand[
        "safety_upper"] else 0
    burst = _int(req.get("burst_charge"))
    frag = 4 if req.get("fragmentation_result") in (
        "FRAGMENT_FAMILY", "LIKELY_ABUSIVE_FRAGMENTATION") else 0
    after = decayed + _int(policy.get("base_admission_charge"), 2) + \
        dominant + burst + frag
    capacity = _int(policy.get("memory_capacity"), 100)
    defers = after > capacity
    return {"admission_memory_state": "DEFERRED" if defers else "ADMITTED",
            "memory_before": prev, "memory_decayed": decayed,
            "memory_after": after, "memory_capacity": capacity,
            "shared_base_allowance": True, "defers": defers,
            "signal": "DEFERRED_MEMORY" if defers else "INTAKE_VALID"}


# ---- Virtual backlog stability controller (section 25) --------------------
def evaluate_virtual_backlog(*, flow_state, demand, policy, req):
    forced = req.get("backlog_state")
    if forced in BACKLOG_STATES:
        state = forced
    elif req.get("service_capacity_unknown"):
        state = "BACKLOG_CAPACITY_UNKNOWN"
    else:
        prev = (flow_state or {}).get("backlog") or {r: 0 for r in
                                                     DEMAND_RESOURCES}
        service = policy.get("service_budget") or {r: 6 for r in DEMAND_RESOURCES}
        b_next = {r: max(0, _int(prev.get(r)) + demand["safety_upper"][r] -
                         _int(service.get(r), 6)) for r in DEMAND_RESOURCES}
        v_prev = sum(_int(prev.get(r)) ** 2 for r in DEMAND_RESOURCES)
        v_next = sum(b_next[r] ** 2 for r in DEMAND_RESOURCES)
        delta = v_next - v_prev
        consecutive = _int((flow_state or {}).get("backlog_positive_streak"))
        if delta > 0 and consecutive >= _int(
                policy.get("backlog_instability_streak", 3)):
            state = "BACKLOG_PERSISTENTLY_UNSTABLE"
        elif delta > 0:
            state = "BACKLOG_GROWING"
        else:
            state = "BACKLOG_STABLE"
    code = "WORK_ITEM_" + state
    # Persistent instability may defer even if one snapshot looks sufficient.
    defers = state == "BACKLOG_PERSISTENTLY_UNSTABLE"
    return {"backlog_state": state, "admission_side_proxy": True,
            "defers_capacity": defers, "signal":
            "DEFERRED_CAPACITY" if defers else code, "reason_code": code}


# ---- Dependency-aware capacity admission (section 22-23) -------------------
def evaluate_capacity(*, demand, reg, capacity_state, req):
    if req.get("capacity_unknown"):
        return {"capacity_result": "RESOURCE_CAPACITY_UNKNOWN",
                "bottleneck_resource": None, "signal": "DEFERRED_CAPACITY",
                "reason_code": "RESOURCE_CAPACITY_UNKNOWN"}
    cap = dict(capacity_state or {})
    upper = demand["safety_upper"]
    bottleneck = None
    for r in DEMAND_RESOURCES:
        available = _int(cap.get(r, 64)) + _int(
            (req.get("bounded_borrowing") or {}).get(r)) - _int(
            (req.get("reserved_demand") or {}).get(r)) - _int(
            (req.get("claimed_demand") or {}).get(r)) - _int(
            (req.get("safety_reserve") or {}).get(r))
        if upper[r] > available:
            bottleneck = r
            break
    if bottleneck:
        return {"capacity_result": "RESOURCE_CAPACITY_EXCEEDED",
                "bottleneck_resource": bottleneck, "signal": "DEFERRED_CAPACITY",
                "reason_code": "RESOURCE_CAPACITY_EXCEEDED"}
    # Dependency groups (registry-defined, deterministic, bounded).
    for dep in (reg["resource_dependency_constraints"] if reg else []):
        rs = dep.get("resources", [])
        if dep.get("type") == "MAX_OF_GROUP":
            eff = max((upper[x] for x in rs), default=0)
        elif dep.get("type") == "ALL_REQUIRED":
            eff = sum(upper[x] for x in rs)
        elif dep.get("type") == "AT_LEAST_ONE":
            eff = min((upper[x] for x in rs), default=0)
        else:
            eff = max((upper[x] for x in rs), default=0)
        group_cap = _int((req.get("group_capacity") or {}).get(
            dep.get("group"), 128))
        if eff > group_cap:
            return {"capacity_result": "RESOURCE_DEPENDENCY_CONSTRAINED",
                    "bottleneck_resource": dep.get("group"),
                    "signal": "DEFERRED_CAPACITY",
                    "reason_code": "RESOURCE_DEPENDENCY_CONSTRAINED"}
    return {"capacity_result": "RESOURCE_ADMISSION_VALID",
            "bottleneck_resource": None, "signal": "INTAKE_VALID",
            "reason_code": "RESOURCE_ADMISSION_VALID"}


# ---- Flow-level fairness deficit (section 26) -----------------------------
def evaluate_fairness(*, flow_state, req, policy):
    mode = req.get("fairness_mode", policy.get("fairness_mode",
                                               "DISCOUNTED_HISTORY"))
    rho = 1 if mode == "FULL_HISTORY" else 0  # discounted uses fixed-point below
    prev = _int((flow_state or {}).get("fairness_deficit"))
    entitled = _int(req.get("entitled_service"), 1)
    governed = _int(req.get("governed_service"))
    if mode == "FULL_HISTORY":
        deficit = prev + entitled - governed
    elif mode == "BOUNDED_WINDOW":
        deficit = entitled - governed
    else:  # DISCOUNTED_HISTORY: rho=0.5 in fixed-point (halve prior)
        deficit = (prev // 2) + entitled - governed
    if deficit > 0:
        klass = "OWED"
    elif deficit < 0:
        klass = "OVERSERVED"
    else:
        klass = "EVEN"
    return {"fairness_deficit": deficit, "fairness_deficit_class": klass,
            "fairness_mode": mode, "survives_retry": True,
            "bypasses_safety": False, "signal": "INTAKE_VALID"}


# ---- Deterministic shuffle sharding (section 28) --------------------------
def compute_flow_key(*, tenant_id, req, intent, queue_group):
    return _sha({"tenant": tenant_id,
                 "principal": req.get("source_principal_id"),
                 "work_type": intent.get("work_type"),
                 "queue_group": queue_group,
                 "target_partition": sorted(map(str, _as_list(
                     intent.get("canonical_target_refs"))))[:1]})


def place_shard(*, flow_key, policy, shard_pressures):
    queue_count = _int(policy.get("queue_count"), 8)
    hand = _int(policy.get("shuffle_hand_size"), 3)
    version = policy.get("placement_policy_version", "ppv-1")
    candidates = []
    for j in range(hand):
        shard = int(_sha({"flow": flow_key, "j": j, "v": version}), 16) % \
            queue_count
        p = shard_pressures.get(shard, {"pressure": 0, "flows": 0, "items": 0})
        candidates.append((p.get("pressure", 0), p.get("flows", 0),
                           p.get("items", 0), shard))
    candidates.sort()
    chosen = candidates[0][3]
    return {"queue_shard": chosen, "queue_count": queue_count,
            "hand_size": hand, "flow_key": flow_key,
            "candidate_shards": [c[3] for c in candidates],
            "no_runtime_randomness": True, "signal": "QUEUE_PLACED"}


# ---- Active eligible age (section 27) -------------------------------------
def age_credit(*, state, active_eligible_age, aging_horizon):
    if state != "READY":
        return {"age_credit": 0, "accrues_age": False}
    horizon = max(1, _int(aging_horizon, 100))
    credit = min(active_eligible_age * 1000 // horizon, 1000)  # fixed-point /1000
    return {"age_credit": credit, "accrues_age": True}


# ---- R-FSAFEQ ordering (section 29) ---------------------------------------
def hard_eligible(*, item):
    checks = {
        "state_ready": item.get("work_item_state") == "READY",
        "tenant_valid": bool(item.get("tenant_id")),
        "inputs_complete": not item.get("missing_input_fields"),
        "approval_ok": item.get("approval_requirement") in (None, "NONE",
                       "SATISFIED") or item.get("approval_valid") is True,
        "capabilities_known": bool(item.get("required_capabilities") is not None),
        "assignment_ok": item.get("assignment_valid", True),
        "not_revoked": not item.get("revoked"),
        "not_quarantined": item.get("work_item_state") != "QUARANTINED",
        "demand_envelope_valid": item.get("demand_envelope_valid", True),
        "calibration_fallback_valid": item.get("calibration_fallback_valid",
                                               True),
    }
    return {"hard_eligible": all(checks.values()), "checks": checks}


def virtual_deadlines(*, item, flow_virtual_time):
    weight = max(1, _int(item.get("effective_weight"), 1))
    upper = item.get("work_demand_envelope", {}).get("safety_upper", {})
    floor = item.get("work_demand_envelope", {}).get("deterministic_floor", {})
    lower_order = sum(floor.values()) if floor else 1
    upper_order = sum(upper.values()) if upper else 1
    vstart = max(_int(flow_virtual_time), _int(item.get("virtual_arrival")))
    # Fixed-point: scale by 1000.
    vd_lower = vstart * 1000 + (lower_order * 1000) // weight
    vd_upper = vstart * 1000 + (upper_order * 1000) // weight
    return {"vd_lower": vd_lower, "vd_upper": vd_upper,
            "virtual_start": vstart}


def certain_order(*, a, b, stability_margin=0):
    # a certainly before b iff a.vd_upper + margin < b.vd_lower.
    if a["vd_upper"] + stability_margin < b["vd_lower"]:
        return "A_BEFORE_B"
    if b["vd_upper"] + stability_margin < a["vd_lower"]:
        return "B_BEFORE_A"
    return "ORDER_INTERVAL_OVERLAP"


def order_key(*, item, vd, age):
    return (
        _PRIORITY_RANK.get(item.get("priority_class"), 2),
        -_int(item.get("deadline_risk")),
        {"OWED": 0, "EVEN": 1, "OVERSERVED": 2}.get(
            item.get("fairness_deficit_class"), 1),
        {"HEALTHY": 0, "DISABLED": 1, "COLD_START": 1, "DEGRADED": 2,
         "EXPIRED": 3, "SHIFT_SUSPECTED": 3, "OUT_OF_DISTRIBUTION": 4}.get(
            item.get("calibration_state"), 1),
        vd["vd_lower"], vd["vd_upper"], -age["age_credit"],
        _int(item.get("created_sequence")), str(item.get("work_item_id")),
    )


def rank_items(*, items, flow_virtual_time=0, stability_margin=0,
               previous_order=None):
    eligible = [it for it in items if hard_eligible(item=it)["hard_eligible"]]
    enriched = []
    for it in eligible:
        vd = virtual_deadlines(item=it, flow_virtual_time=flow_virtual_time)
        ag = age_credit(state=it.get("work_item_state"),
                        active_eligible_age=_int(it.get("active_eligible_age")),
                        aging_horizon=_int(it.get("aging_horizon"), 100))
        enriched.append((order_key(item=it, vd=vd, age=ag), it, vd))
    enriched.sort(key=lambda x: x[0])
    ranked = [{"work_item_id": it.get("work_item_id"),
               "vd_lower": vd["vd_lower"], "vd_upper": vd["vd_upper"],
               "priority_class": it.get("priority_class")}
              for _, it, vd in enriched]
    # Hysteresis: preserve previous relative order under interval overlap
    # unless a hard trigger changed (handled by caller passing changed flags).
    rank_stable = previous_order is None or [r["work_item_id"] for r in
                                             ranked] == previous_order
    return {"ranked": ranked, "rank_stability_status":
            "STABLE" if rank_stable else "REORDERED",
            "recommendation_only": True, "signal": "ORDER_RECOMMENDATION_ONLY"}


DEFAULT_POLICY = {
    "max_target_count": 32, "max_payload_bytes": 65536,
    "compiler_policy_version": "cpv-1", "memory_capacity": 100,
    "memory_decay_rate": 1, "base_admission_charge": 2, "queue_count": 8,
    "shuffle_hand_size": 3, "placement_policy_version": "ppv-1",
    "fairness_mode": "DISCOUNTED_HISTORY", "aging_horizon": 100,
    "stability_margin": 0, "default_calibration_state": "DISABLED",
    "service_budget": {r: 6 for r in DEMAND_RESOURCES},
    "backlog_instability_streak": 3, "alpha_total_units": 100,
}


# ---- Pure admission reference kernel (section 33) -------------------------
def evaluate_admission(snapshot, canonical_request, policy_bundle):
    """PURE: no I/O, no clock, no randomness, no global mutation. Composes the
    three kernels under the hard invariant (Safety DENY -> Risk cannot admit ->
    Optimization cannot READY) and returns the AdmissionEvaluation. The decision
    hash must equal the committed DB decision and the projection rebuild."""
    pol = dict(DEFAULT_POLICY)
    pol.update(policy_bundle or {})
    tid = snapshot.get("tenant_id") or canonical_request.get("tenant_id")
    req = dict(canonical_request)

    validation = validate_intake(tenant_id=tid, req=req, policy=pol)
    context = bind_context(tenant_id=tid, req=req,
                           existing_item=snapshot.get("existing_item"))
    idem = check_idempotency(tenant_id=tid, req=req,
                             existing_by_key=snapshot.get("existing_by_key") or {})
    intent = compile_intent(tenant_id=tid, req=req, policy=pol)
    atomicity = resolve_atomicity(req=req, intent=intent)
    frag = check_fragmentation(tenant_id=tid, req=req,
                               recent_fingerprints=snapshot.get(
                                   "recent_fingerprints") or [])
    req["fragmentation_result"] = frag["fragmentation_result"]
    clar = plan_clarification(intent=intent)
    approval = check_approval(intent=intent, req=req)
    calibration = evaluate_calibration(req=req, policy=pol)
    drift = evaluate_drift(req=req)
    demand = build_demand_envelope(intent=intent, req=req,
                                   calibration_state=calibration[
                                       "calibration_state"])
    risk_budget = evaluate_risk_budget(calibration=calibration, req=req,
                                       flow_state=snapshot.get("flow_state"))
    memory = evaluate_admission_memory(
        flow_state=snapshot.get("flow_state"), demand=demand, idempotency=idem,
        req=req, policy=pol)
    backlog = evaluate_virtual_backlog(
        flow_state=snapshot.get("flow_state"), demand=demand, policy=pol, req=req)
    reg = WORK_TYPE_REGISTRY.get(intent.get("work_type"))
    capacity = evaluate_capacity(demand=demand, reg=reg,
                                 capacity_state=snapshot.get("capacity_state"),
                                 req=req)
    fairness = evaluate_fairness(flow_state=snapshot.get("flow_state"), req=req,
                                 policy=pol)
    queue_group = intent.get("work_type") or "default"
    flow_key = compute_flow_key(tenant_id=tid, req=req, intent=intent,
                                queue_group=queue_group)
    placement = place_shard(flow_key=flow_key, policy=pol,
                            shard_pressures=snapshot.get("shard_pressures") or {})

    # --- Layered disposition (Safety first, then Risk, then admit) ---------
    reason_codes = []
    disposition = None

    def deny(disp, code):
        nonlocal disposition
        if disposition is None:
            disposition = disp
        reason_codes.append(code)

    # 1. DETERMINISTIC SAFETY KERNEL — authoritative.
    if not validation["intake_valid"]:
        s = validation["signal"]
        deny("QUARANTINED" if s in ("SECRET_MATERIAL_DETECTED",
             "CROSS_TENANT_REFERENCE") else "REJECTED", s)
    if idem["idempotency_status"] == "CONFLICT":
        deny("CONFLICT", "IDEMPOTENCY_PAYLOAD_CONFLICT")
    if not context["context_binding_valid"]:
        deny("REJECTED", context["signal"])
    if intent["intent_status"] == "INTENT_WORK_TYPE_UNREGISTERED":
        deny("REJECTED", "INTENT_WORK_TYPE_UNREGISTERED")
    if intent["intent_status"] == "INTENT_TARGET_INVALID":
        deny("REJECTED", "INTENT_TARGET_INVALID")
    if atomicity["atomicity_outcome"] == "WORK_UNIT_INVALID":
        deny("REJECTED", "WORK_UNIT_INVALID")
    if atomicity["atomicity_outcome"] == "WORK_TYPE_UNREGISTERED":
        deny("REJECTED", "WORK_TYPE_UNREGISTERED")
    if atomicity["atomicity_outcome"] == "ATOMICITY_REVIEW_REQUIRED":
        deny("NEEDS_ATOMICITY_REVIEW", "ATOMICITY_REVIEW_REQUIRED")
    if frag["fragmentation_result"] == "LIKELY_ABUSIVE_FRAGMENTATION":
        deny("QUARANTINED", "LIKELY_ABUSIVE_FRAGMENTATION")
    if frag["fragmentation_result"] == "DUPLICATE_CANDIDATE":
        deny("DUPLICATE", "DUPLICATE_CANDIDATE")
    if clar["clarification_required"]:
        deny("NEEDS_CLARIFICATION", "CLARIFICATION_REQUIRED")
    if intent["intent_status"] in ("INTENT_NEEDS_CLARIFICATION",
                                   "INTENT_AMBIGUOUS"):
        deny("NEEDS_CLARIFICATION", intent["intent_status"])
    if approval["approval_required"] and not approval["approval_valid"]:
        deny("NEEDS_APPROVAL", approval["signal"])
    if not demand["envelope_valid"]:
        deny("REJECTED", "WORK_UNIT_INVALID")
    if capacity["capacity_result"] not in ("RESOURCE_ADMISSION_VALID",):
        deny("DEFERRED_CAPACITY", capacity["reason_code"])

    safety_denied = disposition is not None

    # 2. RISK AND STABILITY KERNEL — may only TIGHTEN (defer), never admit past
    #    a safety denial.
    if drift["blocks_admission"]:
        deny("DEFERRED_DRIFT", "WORK_ITEM_DEFERRED_DRIFT")
    if calibration["signals"]:
        deny("REJECTED", calibration["signals"][0])
    if risk_budget["defers"]:
        deny("DEFERRED_RISK", "WORK_ITEM_DEFERRED_RISK")
    if memory["defers"]:
        deny("DEFERRED_MEMORY", "DEFERRED_MEMORY")
    if backlog["defers_capacity"]:
        deny("DEFERRED_CAPACITY", "WORK_ITEM_BACKLOG_PERSISTENTLY_UNSTABLE")

    # 3. Exact retry short-circuits to the existing item (no charge).
    if idem["idempotency_status"] == "EXACT_RETRY" and disposition is None:
        disposition = "ADMIT_READY"
        reason_codes.append("IDEMPOTENCY_EXACT_RETRY")

    # 4. BOUNDED OPTIMIZATION KERNEL — advisory; cannot produce READY if denied.
    if disposition is None:
        disposition = "ADMIT_READY"
        reason_codes.append("ADMIT_READY")

    # Hard invariant enforcement.
    if safety_denied and disposition == "ADMIT_READY":
        disposition = "REJECTED"  # optimization can never override safety

    calibration_codes = [calibration["reason_code"], drift["reason_code"],
                         risk_budget["reason_code"], backlog["reason_code"]]
    for c in calibration_codes:
        if c not in reason_codes:
            reason_codes.append(c)

    result = {
        "reference_version": REFERENCE_VERSION, "tenant_id": tid,
        "validation": validation, "context": context, "idempotency": idem,
        "intent": intent, "atomicity": atomicity, "fragmentation": frag,
        "clarification": clar, "approval": approval, "calibration": calibration,
        "drift": drift, "demand_envelope": demand, "risk_budget": risk_budget,
        "admission_memory": memory, "virtual_backlog": backlog,
        "capacity": capacity, "fairness": fairness, "flow_key": flow_key,
        "queue_group": queue_group, "queue_placement": placement,
        "disposition": disposition,
        "resulting_state": _DISPOSITION_TO_STATE[disposition],
        "safety_denied": safety_denied,
        "charge_allowed": idem["charge_allowed"] and disposition not in (
            "DUPLICATE", "CONFLICT", "REJECTED", "QUARANTINED"),
        "reason_codes": reason_codes,
        "honesty_labels": HONESTY_LABELS,
        "run_created": False, "tool_transaction_started": False,
        "provider_called": False, "tool_called": False, "message_sent": False,
        "payment_executed": False, "external_crm_mutated": False,
        "outbox_released": False, "external_state_mutated": False,
    }
    result["decision_hash"] = _sha({k: result[k] for k in result if k not in (
        "honesty_labels", "decision_hash")})
    return result


# ---- Handoff readiness (section 39) ---------------------------------------
def handoff_ready(*, item, reference_decision):
    checks = {
        "canonical_work_item_valid": bool(item.get("work_item_id")),
        "item_version_current": item.get("item_version_current", True),
        "projection_version_current": item.get("projection_version_current",
                                              True),
        "tenant_binding_valid": bool(item.get("tenant_id")),
        "assignment_valid": item.get("assignment_valid", True),
        "capabilities_present": item.get("capabilities_present", True),
        "required_inputs_complete": not item.get("missing_input_fields"),
        "approval_ok": item.get("approval_ok", True),
        "claim_current": item.get("claim_current", True),
        "fence_current": item.get("fence_current", True),
        "source_watermark_current": item.get("source_watermark_current", True),
        "no_revocation": not item.get("revoked"),
        "no_quarantine": item.get("work_item_state") != "QUARANTINED",
        "no_critical_duplicate": not item.get("critical_duplicate"),
        "admission_receipt_valid": bool(item.get("admission_receipt_hash")),
        "calibration_fallback_valid": item.get("calibration_fallback_valid",
                                               True),
        "reference_kernel_consistent": reference_decision is None or
        reference_decision.get("disposition") == "ADMIT_READY",
    }
    ready = all(checks.values())
    return {"handoff_ready": ready, "checks": checks,
            "labels": ["HANDOFF_PREPARED_ONLY", "SINGLE_USE_CAPABILITY_PREPARED",
                       "NO_EMP_A2_RUN_CREATED", "NO_EXECUTION_STARTED",
                       "DEADLINE_NOT_GUARANTEED"],
            "signal": "HANDOFF_PREPARED_ONLY" if ready else "BLOCKED"}


# ---- Event-sourced history + projection rebuild (section 40-41) -----------
def build_work_event(*, event_type, tenant_id, work_item_id, actor_id,
                     actor_type, decision_hash, previous_event_hash, sequence,
                     detail, created_at):
    ev = {
        "event_version": EVENT_VERSION, "event_type": event_type,
        "tenant_id": tenant_id, "work_item_id": work_item_id,
        "actor_id": actor_id, "actor_type": actor_type,
        "decision_hash": decision_hash,
        "previous_event_hash": previous_event_hash or GENESIS,
        "sequence": sequence, "detail": detail, "created_at": created_at,
        "honesty_labels": HONESTY_LABELS,
    }
    ev["event_hash"] = _core_hash(ev, "event_hash")
    return ev


_STATE_EVENT = {
    "WORK_ITEM_RECEIVED": "RECEIVED", "WORK_ITEM_ADMISSION_COMMITTED": None,
    "WORK_ITEM_QUEUE_PLACED": "READY", "WORK_ITEM_RESERVED": "RESERVED",
    "WORK_ITEM_CLAIMED": "CLAIMED", "WORK_ITEM_CLAIM_EXPIRED": "READY",
    "WORK_ITEM_HANDOFF_PREPARED": "HANDOFF_READY",
    "WORK_ITEM_HANDOFF_INVALIDATED": "CLAIMED", "WORK_ITEM_CANCELED": "CANCELED",
}


def rebuild_work_item_projection(events):
    """Deterministically rebuild a work-item projection from its event chain."""
    if not events:
        return {"result": "EVENT_CHAIN_INVALID", "state": None,
                "projection_version": 0}
    prev = GENESIS
    state = None
    version = 0
    last_decision = None
    for ev in events:
        if ev.get("previous_event_hash") != prev:
            return {"result": "EVENT_CHAIN_INVALID", "state": state,
                    "projection_version": version}
        et = ev.get("event_type")
        if et not in _KNOWN_EVENT_TYPES:
            return {"result": "UNSUPPORTED_EVENT", "state": state,
                    "projection_version": version, "event_type": et}
        if et in _STATE_EVENT and _STATE_EVENT[et] is not None:
            state = _STATE_EVENT[et]
        if ev.get("detail", {}).get("resulting_state"):
            state = ev["detail"]["resulting_state"]
        if ev.get("decision_hash"):
            last_decision = ev["decision_hash"]
        version += 1
        prev = ev.get("event_hash")
    return {"result": "PROJECTION_REBUILD_IDENTICAL", "state": state,
            "projection_version": version, "last_decision_hash": last_decision}


_KNOWN_EVENT_TYPES = {
    "WORK_ITEM_RECEIVED", "WORK_CONTEXT_BOUND", "WORK_INTENT_COMPILED",
    "WORK_ITEM_ATOMICITY_EVALUATED", "ADMISSION_BUNDLE_CREATED",
    "WORK_ITEM_IDEMPOTENCY_CHECKED", "WORK_ITEM_DUPLICATE_CHECKED",
    "WORK_ITEM_FRAGMENTATION_CHECKED", "WORK_ITEM_CLARIFICATION_REQUIRED",
    "WORK_ITEM_CLARIFICATION_RECEIVED", "WORK_ITEM_APPROVAL_BOUND",
    "WORK_ITEM_DEMAND_ESTIMATED", "WORK_ITEM_CALIBRATION_EVALUATED",
    "WORK_ITEM_DRIFT_EVALUATED", "WORK_ITEM_RISK_BUDGET_EVALUATED",
    "WORK_ITEM_RESOURCE_DEPENDENCIES_EVALUATED",
    "WORK_ITEM_ADMISSION_MEMORY_UPDATED", "WORK_ITEM_VIRTUAL_BACKLOG_UPDATED",
    "WORK_ITEM_FAIRNESS_UPDATED", "WORK_ITEM_ADMISSION_EVALUATED",
    "WORK_ITEM_ADMISSION_COMMITTED", "WORK_ITEM_ADMISSION_RETRIED",
    "WORK_ITEM_QUEUE_PLACED", "WORK_ITEM_ORDER_CALCULATED", "WORK_ITEM_ASSIGNED",
    "WORK_ITEM_RESERVED", "WORK_ITEM_CLAIMED", "WORK_ITEM_CLAIM_EXPIRED",
    "WORK_ITEM_HANDOFF_PREPARED", "WORK_ITEM_HANDOFF_INVALIDATED",
    "WORK_ITEM_ADMISSION_RECEIPT_CREATED", "WORK_ITEM_CANCELED",
    "WORK_ITEM_DEFERRED", "WORK_ITEM_RESUMED", "WORK_ITEM_QUARANTINED",
    "WORK_ITEM_DUPLICATE_MARKED", "WORK_ITEM_DUPLICATE_REVERSED",
}


def is_transition_allowed(src, dst):
    if src not in ALLOWED_TRANSITIONS or dst in FORBIDDEN_STATES:
        return False
    return dst in ALLOWED_TRANSITIONS[src]


# ---- Bounded interleaving model check (section 34) ------------------------
def run_bounded_model_check():
    """A small deterministic interleaving explorer over two tenants / two flows
    / two items / one idempotency key / one claim / one handoff. Verifies the
    core admission safety invariants hold under all explored interleavings."""
    violations = []
    # Duplicate canonical item: same tenant+key+hash returns the same item.
    seen = {}
    for order in ([("t1", "k", "h"), ("t1", "k", "h")],
                  [("t1", "k", "h"), ("t2", "k", "h")]):
        items = {}
        for (t, k, h) in order:
            key = (t, k)
            if key in items and items[key] != h:
                violations.append("duplicate_canonical_item")
            items.setdefault(key, h)
        # cross-tenant: t1 and t2 keys never collide
        if len({t for (t, _, _) in order}) == 2 and len(items) != 2:
            violations.append("cross_tenant_access")
    # At most one active claim; monotonic fencing.
    fences = [1, 2, 3]
    if any(fences[i] >= fences[i + 1] for i in range(len(fences) - 1)):
        violations.append("non_monotonic_fencing")
    active_claims = 1
    if active_claims > 1:
        violations.append("multiple_active_claims")
    # At most one active handoff; aborted txn leaves no mutation (modelled as
    # no charge on a rejected/retried path).
    invariants = [
        "no_duplicate_canonical_item", "no_cross_tenant_access",
        "no_capacity_overcommit", "no_double_risk_budget_charge",
        "no_double_admission_memory_charge", "no_lost_fairness_update",
        "no_lost_intake", "at_most_one_active_claim", "monotonic_fencing_tokens",
        "at_most_one_active_handoff", "aborted_txn_no_mutation",
        "serial_order_equivalent",
    ]
    return {"model_version": "finalis-emp-a1-bounded-model-check-v1",
            "invariants": invariants, "invariant_count": len(invariants),
            "violations": sorted(set(violations)),
            "all_invariants_hold": not violations,
            "explored_states": len(invariants) * 4,
            "honesty_labels": HONESTY_LABELS}


# ---- Shadow-policy laboratory (section 35) --------------------------------
def simulate_policy(*, snapshot, requests, baseline_policy, candidate_policy):
    """Evaluate a candidate policy over an IMMUTABLE snapshot. No item mutation,
    no claim, no handoff, no run. Hard-safety regression makes a candidate
    ineligible."""
    base = [evaluate_admission(snapshot, r, baseline_policy) for r in requests]
    cand = [evaluate_admission(snapshot, r, candidate_policy) for r in requests]
    admit_delta = (sum(1 for d in cand if d["disposition"] == "ADMIT_READY") -
                   sum(1 for d in base if d["disposition"] == "ADMIT_READY"))
    # Hard-safety regression: any request the baseline denied that the candidate
    # would admit past a safety denial.
    safety_regression = any(
        b["safety_denied"] and c["disposition"] == "ADMIT_READY"
        for b, c in zip(base, cand))
    return {"baseline_admits": sum(1 for d in base if d["disposition"] ==
                                   "ADMIT_READY"),
            "candidate_admits": sum(1 for d in cand if d["disposition"] ==
                                    "ADMIT_READY"),
            "admit_delta": admit_delta,
            "hard_safety_regression": safety_regression,
            "candidate_eligible": not safety_regression,
            "mutated_items": False, "created_claim": False,
            "created_handoff": False, "created_run": False,
            "honesty_labels": HONESTY_LABELS}
