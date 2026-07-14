"""Finalis ViktorAI Deterministic Lifecycle Kernel (CORE-A5).

A pure, deterministic Task State Machine: canonical states, a formal transition
graph, a graph verifier, an explainable guard vector, a side-effect firewall,
deterministic transition/task/completion hashing, and a ViktorAI-style
Completion Loop.

This kernel controls LIFECYCLE STATE ONLY. It executes nothing: no LLM, no Tool
Broker, no external provider, no payment, no customer message, no CRM write, no
evidence rewrite, no consent override. Server-side task state is authoritative;
a transition never performs the underlying action. Fail-closed: a transition is
allowed only when every factor of TransitionAllowed holds.
"""
from __future__ import annotations

import hashlib
import json

KERNEL_VERSION = "finalis-lifecycle-kernel-v1"
POLICY_CAPSULE_VERSION = "finalis-transition-policy-capsule-v1"
COMPLETION_CONTRACT_VERSION = "finalis-completion-contract-v1"
GENESIS = "0" * 64

# --- Canonical task states -------------------------------------------------
STATES = [
    "INTAKE_RECEIVED", "NORMALIZED", "CONTRACTED", "AUTHORITY_CHECKED",
    "ACCEPTED", "NEEDS_CLARIFICATION", "APPROVAL_REQUIRED", "APPROVAL_PENDING",
    "APPROVED_READY", "RUN_READY", "RUNNING_LEDGER_ONLY", "PAUSED", "BLOCKED",
    "DRAFT_READY", "REVIEW_READY", "COMPLETION_CHECK_REQUIRED",
    "COMPLETION_BLOCKED", "COMPLETED_NO_SIDE_EFFECTS", "CANCELLED", "FAILED",
    "EXPIRED", "SUPERSEDED", "RECONCILIATION_REQUIRED", "NOT_IMPLEMENTED",
]
STATE_SET = set(STATES)

TERMINAL_STATES = {"COMPLETED_NO_SIDE_EFFECTS", "CANCELLED", "FAILED",
                   "EXPIRED", "SUPERSEDED", "BLOCKED", "NOT_IMPLEMENTED"}

# Hard-fail dominance ordering (most dominant first).
DOMINANCE = ["BLOCKED", "EXPIRED", "CANCELLED", "FAILED", "NEEDS_CLARIFICATION",
             "APPROVAL_REQUIRED", "APPROVED_READY", "RUN_READY",
             "RUNNING_LEDGER_ONLY", "REVIEW_READY", "COMPLETED_NO_SIDE_EFFECTS"]

# --- Transition events -----------------------------------------------------
EVENTS = [
    "TASK_RECEIVED", "TASK_NORMALIZED", "TASK_CONTRACTED",
    "AUTHORITY_CHECK_COMPLETED", "TASK_ACCEPTED", "CLARIFICATION_REQUESTED",
    "CLARIFICATION_RECEIVED", "APPROVAL_REQUIRED_RECORDED",
    "APPROVAL_REQUEST_LINKED", "APPROVAL_GRANT_VALIDATED",
    "TASK_MARKED_APPROVED_READY", "RUN_LEDGER_CREATED", "TASK_MARKED_RUN_READY",
    "TASK_MARKED_RUNNING_LEDGER_ONLY", "TASK_PAUSED", "TASK_RESUMED",
    "TASK_BLOCKED", "DRAFT_CREATED", "TASK_MARKED_REVIEW_READY",
    "COMPLETION_CHECK_REQUESTED", "COMPLETION_CRITERIA_EVALUATED",
    "COMPLETION_BLOCKERS_RECORDED", "TASK_COMPLETED_NO_SIDE_EFFECTS",
    "TASK_CANCELLED", "TASK_FAILED", "TASK_EXPIRED", "TASK_SUPERSEDED",
    "TASK_RECONCILIATION_REQUIRED", "TASK_NOT_IMPLEMENTED_RECORDED",
    "TRANSITION_DENIED", "TRANSITION_VERIFIED", "TRANSITION_REPLAYED",
    "TRANSITION_RECONCILED", "TRANSITION_TAMPER_WARNING",
    "IDEMPOTENT_TRANSITION_REPLAYED", "STALE_TRANSITION_REJECTED",
    "SIDE_EFFECT_ATTEMPT_BLOCKED", "PATCH_STATUS_BYPASS_BLOCKED",
]
EVENT_SET = set(EVENTS)

# Events that imply real execution — never valid graph edges; the side-effect
# firewall blocks any request carrying one of these.
FORBIDDEN_SIDE_EFFECT_EVENTS = {
    "TOOL_EXECUTED", "LLM_CALLED", "PAYMENT_EXECUTED", "MESSAGE_SENT",
    "CRM_SYNCED", "EVIDENCE_REWRITTEN", "CONSENT_OVERRIDDEN",
}

# --- Transition graph (formal edges) ---------------------------------------
# Each edge: (from_state, event, to_state, requirements). Requirements flags:
#   grant   -> requires a valid approval grant (consume-check)
#   comp    -> requires CompletionReady = true
#   highrisk-> declares approval/guard requirements
def _e(frm, event, to, grant=False, comp=False, highrisk=False):
    return {"from": frm, "event": event, "to": to,
            "requires_approval_grant": grant, "requires_completion_ready": comp,
            "high_risk": highrisk}


_BASE_EDGES = [
    _e("INTAKE_RECEIVED", "TASK_NORMALIZED", "NORMALIZED"),
    _e("NORMALIZED", "TASK_CONTRACTED", "CONTRACTED"),
    _e("CONTRACTED", "AUTHORITY_CHECK_COMPLETED", "AUTHORITY_CHECKED"),
    _e("AUTHORITY_CHECKED", "TASK_ACCEPTED", "ACCEPTED"),
    _e("AUTHORITY_CHECKED", "TASK_BLOCKED", "BLOCKED"),
    _e("AUTHORITY_CHECKED", "CLARIFICATION_REQUESTED", "NEEDS_CLARIFICATION"),
    _e("AUTHORITY_CHECKED", "TASK_NOT_IMPLEMENTED_RECORDED", "NOT_IMPLEMENTED"),
    _e("ACCEPTED", "APPROVAL_REQUIRED_RECORDED", "APPROVAL_REQUIRED"),
    _e("ACCEPTED", "TASK_MARKED_RUN_READY", "RUN_READY"),
    _e("ACCEPTED", "DRAFT_CREATED", "DRAFT_READY"),
    _e("NEEDS_CLARIFICATION", "CLARIFICATION_RECEIVED", "ACCEPTED"),
    _e("APPROVAL_REQUIRED", "APPROVAL_REQUEST_LINKED", "APPROVAL_PENDING"),
    _e("APPROVAL_PENDING", "APPROVAL_GRANT_VALIDATED", "APPROVED_READY",
       grant=True, highrisk=True),
    _e("APPROVED_READY", "TASK_MARKED_RUN_READY", "RUN_READY", highrisk=True),
    _e("RUN_READY", "TASK_MARKED_RUNNING_LEDGER_ONLY", "RUNNING_LEDGER_ONLY"),
    _e("RUNNING_LEDGER_ONLY", "DRAFT_CREATED", "DRAFT_READY"),
    _e("RUNNING_LEDGER_ONLY", "TASK_MARKED_REVIEW_READY", "REVIEW_READY"),
    _e("RUNNING_LEDGER_ONLY", "TASK_PAUSED", "PAUSED"),
    _e("RUNNING_LEDGER_ONLY", "TASK_FAILED", "FAILED"),
    _e("PAUSED", "TASK_RESUMED", "RUN_READY"),
    _e("DRAFT_READY", "TASK_MARKED_REVIEW_READY", "REVIEW_READY"),
    _e("REVIEW_READY", "COMPLETION_CHECK_REQUESTED", "COMPLETION_CHECK_REQUIRED"),
    _e("REVIEW_READY", "CLARIFICATION_REQUESTED", "NEEDS_CLARIFICATION"),
    _e("COMPLETION_CHECK_REQUIRED", "TASK_COMPLETED_NO_SIDE_EFFECTS",
       "COMPLETED_NO_SIDE_EFFECTS", comp=True, highrisk=True),
    _e("COMPLETION_CHECK_REQUIRED", "COMPLETION_BLOCKERS_RECORDED",
       "COMPLETION_BLOCKED"),
    _e("COMPLETION_BLOCKED", "TASK_MARKED_REVIEW_READY", "REVIEW_READY"),
    _e("RECONCILIATION_REQUIRED", "TASK_MARKED_REVIEW_READY", "REVIEW_READY"),
]

# Universal safe-exit / blocker edges from EVERY non-terminal state.
_UNIVERSAL = [
    ("TASK_CANCELLED", "CANCELLED"),
    ("TASK_EXPIRED", "EXPIRED"),
    ("TASK_SUPERSEDED", "SUPERSEDED"),
    ("TASK_BLOCKED", "BLOCKED"),
    ("TASK_RECONCILIATION_REQUIRED", "RECONCILIATION_REQUIRED"),
]


def _build_edges():
    edges = list(_BASE_EDGES)
    seen = {(x["from"], x["event"]) for x in edges}
    for st in STATES:
        if st in TERMINAL_STATES:
            continue
        for event, to in _UNIVERSAL:
            if to == st:
                continue
            if (st, event) in seen:
                continue
            edges.append(_e(st, event, to))
            seen.add((st, event))
    return edges


EDGES = _build_edges()
_EDGE_INDEX = {(x["from"], x["event"]): x for x in EDGES}


def find_edge(from_state: str, event: str):
    return _EDGE_INDEX.get((from_state, event))


def allowed_events(from_state: str) -> list:
    return [{"event": x["event"], "to": x["to"],
             "requires_approval_grant": x["requires_approval_grant"],
             "requires_completion_ready": x["requires_completion_ready"]}
            for x in EDGES if x["from"] == from_state]


# --- Canonicalization / hashing --------------------------------------------
def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _sha(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


# --- Migration/coexistence: intake status -> canonical lifecycle state ------
_INTAKE_MAP = {
    "ACCEPTED": "ACCEPTED", "BLOCKED": "BLOCKED",
    "NEEDS_CLARIFICATION": "NEEDS_CLARIFICATION",
    "NOT_IMPLEMENTED": "NOT_IMPLEMENTED", "EXPIRED": "EXPIRED",
    "CANCELLED": "CANCELLED", "CREATED": "ACCEPTED",
}


def initial_state_from_status(task_status: str) -> str:
    return _INTAKE_MAP.get(task_status, "ACCEPTED")


# --- Graph verifier --------------------------------------------------------
def verify_graph(edges: list = None) -> dict:
    edges = EDGES if edges is None else edges
    invalid_edges, terminal_violations, forbidden = [], [], []
    for x in edges:
        if x["from"] not in STATE_SET:
            invalid_edges.append({"edge": x, "reason": "unknown from_state"})
        if x["to"] not in STATE_SET:
            invalid_edges.append({"edge": x, "reason": "unknown to_state"})
        if x["event"] not in EVENT_SET:
            invalid_edges.append({"edge": x, "reason": "unknown event"})
        if x["event"] in FORBIDDEN_SIDE_EFFECT_EVENTS:
            forbidden.append(x)
        if x["from"] in TERMINAL_STATES:
            terminal_violations.append(x)

    # Duplicate (from,event) edges must not disagree on target.
    dupe = {}
    for x in edges:
        key = (x["from"], x["event"])
        if key in dupe and dupe[key]["to"] != x["to"]:
            invalid_edges.append({"edge": x, "reason": "contradictory edge"})
        dupe[key] = x

    # Reachability from INTAKE_RECEIVED.
    reachable, frontier = {"INTAKE_RECEIVED"}, ["INTAKE_RECEIVED"]
    while frontier:
        cur = frontier.pop()
        for x in edges:
            if x["from"] == cur and x["to"] not in reachable:
                reachable.add(x["to"])
                frontier.append(x["to"])
    unreachable = sorted(STATE_SET - reachable)

    # Bypass invariants.
    bypass = []
    #  Completion cannot be reached except from COMPLETION_CHECK_REQUIRED.
    for x in edges:
        if x["to"] == "COMPLETED_NO_SIDE_EFFECTS" \
                and x["from"] != "COMPLETION_CHECK_REQUIRED":
            bypass.append({"edge": x,
                           "reason": "completion bypasses completion check"})
        if x["to"] == "COMPLETED_NO_SIDE_EFFECTS" \
                and not x["requires_completion_ready"]:
            bypass.append({"edge": x,
                           "reason": "completion edge omits readiness guard"})
        #  APPROVED_READY only via APPROVAL_PENDING with a grant guard.
        if x["to"] == "APPROVED_READY":
            if x["from"] != "APPROVAL_PENDING" or not x[
                    "requires_approval_grant"]:
                bypass.append({"edge": x,
                               "reason": "approved-ready bypasses approval "
                               "grant validation"})

    # Every non-terminal state must have at least one safe exit.
    for st in STATES:
        if st in TERMINAL_STATES:
            continue
        if not any(x["from"] == st for x in edges):
            terminal_violations.append({"state": st,
                                        "reason": "non-terminal has no exit"})

    ok = not (invalid_edges or terminal_violations or bypass or forbidden)
    return {
        "graph_verification_status": "MATCHED" if ok else "MISMATCHED",
        "kernel_version": KERNEL_VERSION,
        "states_checked": len(STATES), "edges_checked": len(edges),
        "invalid_edges": invalid_edges, "unreachable_states": unreachable,
        "terminal_state_violations": terminal_violations,
        "bypass_violations": bypass, "forbidden_event_violations": forbidden,
        "graph_hash": _sha({"states": STATES,
                            "edges": [(x["from"], x["event"], x["to"])
                                      for x in EDGES]}),
        "honesty_labels": HONESTY_LABELS,
    }


def state_matrix() -> dict:
    return {
        "kernel_version": KERNEL_VERSION, "states": STATES,
        "terminal_states": sorted(TERMINAL_STATES), "events": EVENTS,
        "edges": [{"from": x["from"], "event": x["event"], "to": x["to"],
                   "requires_approval_grant": x["requires_approval_grant"],
                   "requires_completion_ready": x["requires_completion_ready"],
                   "high_risk": x["high_risk"]} for x in EDGES],
        "guards": GUARD_DESCRIPTIONS, "honesty_labels": HONESTY_LABELS,
    }


# --- Guard vector ----------------------------------------------------------
GUARD_DESCRIPTIONS = {
    "TENANT_SCOPE": "transition target belongs to the actor's tenant",
    "ACTOR_AUTHORIZED": "actor is an authorized human/role for this transition",
    "STATE_EDGE_ALLOWED": "the (from_state, event) edge exists in the graph",
    "TASK_VERSION_MATCH": "expected_task_version matches current version",
    "TASK_CONTRACT_HASH_MATCH": "task contract hash is unchanged",
    "TASK_ENVELOPE_HASH_MATCH": "task envelope hash is unchanged",
    "NOT_TERMINAL": "current state is not terminal (or read-only op)",
    "NOT_EXPIRED": "task has not expired",
    "NOT_STALE": "task is not stale (advisory; refresh may be allowed)",
    "AUTHORITY_NOT_BLOCKED": "CORE-A1 authority is not BLOCKED/hard-fail",
    "SUBJECT_OWNERSHIP": "subject ownership verified or review required",
    "APPROVAL_GRANT_VALID_IF_REQUIRED": "valid approval grant when required",
    "CONSENT_VALID_IF_REQUIRED": "consent still valid when required",
    "EVIDENCE_VALID_IF_REQUIRED": "evidence/proof still valid when required",
    "RUN_STATE_COMPATIBLE": "run state hash compatible when run-bound",
    "COMPLETION_READY_IF_COMPLETING": "completion criteria satisfied if "
                                      "completing",
    "NO_FORBIDDEN_SIDE_EFFECT": "no forbidden side-effect event attempted",
    "PATCH_BYPASS_BLOCKED": "protected state change is not a raw PATCH bypass",
}

REMEDIATION = {
    "TENANT_SCOPE": "operate within your own tenant",
    "ACTOR_AUTHORIZED": "use an account with the required role",
    "STATE_EDGE_ALLOWED": "choose a transition allowed from the current state",
    "TASK_VERSION_MATCH": "reload the task and retry with current version",
    "TASK_CONTRACT_HASH_MATCH": "task contract changed; re-derive the contract",
    "TASK_ENVELOPE_HASH_MATCH": "task envelope changed; re-intake the task",
    "NOT_TERMINAL": "terminal tasks cannot transition; open a new task",
    "NOT_EXPIRED": "task expired; create a fresh task",
    "NOT_STALE": "refresh the task before continuing",
    "AUTHORITY_NOT_BLOCKED": "authority blocked this task; nothing to do",
    "SUBJECT_OWNERSHIP": "verify subject access or request server review",
    "APPROVAL_GRANT_VALID_IF_REQUIRED": "obtain a valid human approval grant",
    "CONSENT_VALID_IF_REQUIRED": "consent required or denied; resolve consent",
    "EVIDENCE_VALID_IF_REQUIRED": "provide required evidence / fix proof",
    "RUN_STATE_COMPATIBLE": "run advanced; reconcile the run link",
    "COMPLETION_READY_IF_COMPLETING": "resolve completion blockers first",
    "NO_FORBIDDEN_SIDE_EFFECT": "this action is blocked; the kernel executes "
                               "nothing",
    "PATCH_BYPASS_BLOCKED": "use the state-machine endpoints, not raw PATCH",
}


def _guard(name, ok, severity, reason, ctx_in, ctx_out, applicable=True,
           blocks=None):
    if not applicable:
        status = "NOT_APPLICABLE"
    elif ok is None:
        status = "SERVER_REVIEW_REQUIRED"
    else:
        status = "PASSED" if ok else "FAILED"
    if blocks is None:
        blocks = status in ("FAILED", "SERVER_REVIEW_REQUIRED") \
            and severity in ("BLOCKER", "HARD_FAIL")
    return {"guard_name": name, "guard_status": status,
            "guard_severity": severity, "guard_reason": reason,
            "guard_input_hash": _sha(ctx_in), "guard_output_hash": _sha(
                {"status": status, "reason": reason}),
            "remediation_hint": REMEDIATION.get(name, ""),
            "blocks_transition": bool(blocks)}


def evaluate_guards(ctx: dict) -> dict:
    """Deterministic, fail-closed guard vector for a requested transition."""
    g = []
    edge = find_edge(ctx["from_state"], ctx["event"])
    completing = bool(edge) and edge["to"] == "COMPLETED_NO_SIDE_EFFECTS"
    run_bound = bool(ctx.get("run_id"))

    g.append(_guard("TENANT_SCOPE", ctx.get("tenant_match", True), "HARD_FAIL",
                    "tenant scope", ctx.get("tenant_id"), None))
    g.append(_guard("ACTOR_AUTHORIZED", ctx.get("actor_authorized", False),
                    "HARD_FAIL", f"actor {ctx.get('actor_type')}/"
                    f"{ctx.get('actor_role')}",
                    {"t": ctx.get("actor_type"), "r": ctx.get("actor_role")},
                    None))
    g.append(_guard("NO_FORBIDDEN_SIDE_EFFECT",
                    not ctx.get("side_effect_attempted")
                    and ctx["event"] not in FORBIDDEN_SIDE_EFFECT_EVENTS,
                    "HARD_FAIL", "side-effect firewall", ctx["event"], None))
    g.append(_guard("PATCH_BYPASS_BLOCKED", not ctx.get("patch_bypass"),
                    "HARD_FAIL", "raw PATCH cannot set protected state",
                    ctx.get("via"), None))
    g.append(_guard("NOT_TERMINAL", ctx["from_state"] not in TERMINAL_STATES,
                    "HARD_FAIL", f"from_state {ctx['from_state']}",
                    ctx["from_state"], None))
    g.append(_guard("STATE_EDGE_ALLOWED", edge is not None, "HARD_FAIL",
                    f"{ctx['from_state']} --{ctx['event']}-->", {
                        "f": ctx["from_state"], "e": ctx["event"]}, None))
    g.append(_guard("NOT_EXPIRED", not ctx.get("expired"), "HARD_FAIL",
                    "expiry", ctx.get("expires_at"), None))
    g.append(_guard("AUTHORITY_NOT_BLOCKED",
                    not ctx.get("authority_blocked"), "HARD_FAIL",
                    f"authority {ctx.get('authority_decision')}",
                    ctx.get("authority_decision"), None))
    # version / hash-state integrity. Applicable blocking guards default to a
    # FAILING value when the caller omits the observed result — fail-closed, so
    # a missing input can never silently pass an applicable guard.
    g.append(_guard("TASK_VERSION_MATCH", ctx.get("version_match", False),
                    "BLOCKER", "optimistic version", {
                        "exp": ctx.get("expected_version"),
                        "cur": ctx.get("current_version")},
                    None, applicable=ctx.get("expected_version") is not None))
    g.append(_guard("TASK_CONTRACT_HASH_MATCH",
                    ctx.get("contract_hash_match", False), "BLOCKER",
                    "task contract hash", ctx.get("contract_hash"), None))
    g.append(_guard("TASK_ENVELOPE_HASH_MATCH",
                    ctx.get("envelope_hash_match", False), "BLOCKER",
                    "task envelope hash", ctx.get("envelope_hash"), None))
    g.append(_guard("RUN_STATE_COMPATIBLE", ctx.get("run_state_match", False),
                    "BLOCKER", "run state hash", ctx.get("run_state_hash"),
                    None, applicable=run_bound))
    g.append(_guard("NOT_STALE", not ctx.get("stale"), "WARNING", "staleness",
                    ctx.get("stale_after"), None, blocks=False))
    # subject ownership: only an explicit VERIFIED passes; missing/unexpected
    # values fail-closed (None -> SERVER_REVIEW_REQUIRED, which blocks).
    so = ctx.get("subject_access_status")
    so_ok = None if so in (None, "UNKNOWN") else (so == "VERIFIED")
    g.append(_guard("SUBJECT_OWNERSHIP", so_ok, "BLOCKER",
                    f"subject access {so}", so, None,
                    applicable=ctx.get("subject_required", False)))
    # approval grant (only enforced on grant-required edges)
    grant_required = bool(edge) and edge["requires_approval_grant"]
    grant_ok = ctx.get("approval_grant_validation_status") == "VALID"
    g.append(_guard("APPROVAL_GRANT_VALID_IF_REQUIRED", grant_ok, "HARD_FAIL",
                    f"grant {ctx.get('approval_grant_validation_status')}",
                    ctx.get("approval_grant_validation_status"), None,
                    applicable=grant_required))
    # consent / evidence — fail-closed when applicable and the observed result
    # is omitted.
    g.append(_guard("CONSENT_VALID_IF_REQUIRED", ctx.get("consent_ok", False),
                    "BLOCKER", "consent", ctx.get("consent_status"), None,
                    applicable=ctx.get("consent_required", False)))
    g.append(_guard("EVIDENCE_VALID_IF_REQUIRED", ctx.get("evidence_ok", False),
                    "BLOCKER", "evidence/proof", ctx.get("evidence_status"),
                    None, applicable=ctx.get("evidence_required", False)))
    # completion
    g.append(_guard("COMPLETION_READY_IF_COMPLETING",
                    ctx.get("completion_ready", False), "HARD_FAIL",
                    "completion readiness", ctx.get("completion_status"), None,
                    applicable=completing))

    failed = [x["guard_name"] for x in g if x["guard_status"] == "FAILED"]
    review = [x["guard_name"] for x in g
              if x["guard_status"] == "SERVER_REVIEW_REQUIRED"]
    blocks = [x["guard_name"] for x in g if x["blocks_transition"]]
    return {"guards": g, "failed_guards": failed, "review_guards": review,
            "blocking_guards": blocks,
            "guard_vector_hash": _sha([(x["guard_name"], x["guard_status"])
                                      for x in g])}


# Guard -> transition_status when that guard is the dominant blocker.
_GUARD_STATUS = {
    "TENANT_SCOPE": "DENIED", "ACTOR_AUTHORIZED": "DENIED",
    "NO_FORBIDDEN_SIDE_EFFECT": "BLOCKED", "PATCH_BYPASS_BLOCKED": "BLOCKED",
    "NOT_TERMINAL": "DENIED", "STATE_EDGE_ALLOWED": "DENIED",
    "NOT_EXPIRED": "EXPIRED", "AUTHORITY_NOT_BLOCKED": "BLOCKED",
    "TASK_VERSION_MATCH": "STALE_VERSION",
    "TASK_CONTRACT_HASH_MATCH": "STALE_HASH_STATE",
    "TASK_ENVELOPE_HASH_MATCH": "STALE_HASH_STATE",
    "RUN_STATE_COMPATIBLE": "STALE_HASH_STATE",
    "SUBJECT_OWNERSHIP": "SERVER_REVIEW_REQUIRED",
    "APPROVAL_GRANT_VALID_IF_REQUIRED": "REQUIRES_APPROVAL",
    "CONSENT_VALID_IF_REQUIRED": "BLOCKED",
    "EVIDENCE_VALID_IF_REQUIRED": "BLOCKED",
    "COMPLETION_READY_IF_COMPLETING": "COMPLETION_BLOCKED",
}
# Order in which a dominant blocker is chosen (fail-closed precedence). This
# mirrors the hard-fail DOMINANCE lattice: BLOCKED dominates EXPIRED, so the
# BLOCKED-producing guards (side-effect firewall, PATCH bypass, authority) are
# ranked above NOT_EXPIRED.
_STATUS_PRECEDENCE = [
    "TENANT_SCOPE", "NO_FORBIDDEN_SIDE_EFFECT", "PATCH_BYPASS_BLOCKED",
    "AUTHORITY_NOT_BLOCKED", "ACTOR_AUTHORIZED", "NOT_TERMINAL",
    "STATE_EDGE_ALLOWED", "NOT_EXPIRED", "TASK_VERSION_MATCH",
    "TASK_CONTRACT_HASH_MATCH", "TASK_ENVELOPE_HASH_MATCH",
    "RUN_STATE_COMPATIBLE", "SUBJECT_OWNERSHIP",
    "APPROVAL_GRANT_VALID_IF_REQUIRED", "CONSENT_VALID_IF_REQUIRED",
    "EVIDENCE_VALID_IF_REQUIRED", "COMPLETION_READY_IF_COMPLETING",
]


def decide_transition(ctx: dict) -> dict:
    """Pure transition decision. Returns status, target state, guard vector and
    reasons. Executes nothing and mutates nothing."""
    gv = evaluate_guards(ctx)
    edge = find_edge(ctx["from_state"], ctx["event"])
    blocking = {x["guard_name"] for x in gv["guards"]
                if x["blocks_transition"]}
    if not blocking:
        to_state = edge["to"]
        return {"transition_status": "ALLOWED", "to_state": to_state,
                "reason": f"{ctx['from_state']} --{ctx['event']}--> {to_state}",
                "blocked_reason": None, **gv}
    dominant = next((n for n in _STATUS_PRECEDENCE if n in blocking),
                    next(iter(blocking)))
    status = _GUARD_STATUS.get(dominant, "DENIED")
    reason = next((x["guard_reason"] for x in gv["guards"]
                   if x["guard_name"] == dominant), dominant)
    return {"transition_status": status,
            "to_state": ctx["from_state"],   # unchanged on denial
            "reason": f"guard {dominant} blocked transition",
            "blocked_reason": f"{dominant}: {reason}", **gv}


# --- Policy capsule / pre & post condition contracts -----------------------
def build_policy_capsule(ctx: dict, decision: dict) -> dict:
    edge = find_edge(ctx["from_state"], ctx["event"])
    policy_input = {
        "from_state": ctx["from_state"], "requested_event": ctx["event"],
        "actor_type": ctx.get("actor_type"), "actor_role": ctx.get("actor_role"),
        "task_type": ctx.get("task_type"), "segment": ctx.get("segment"),
        "risk_level": ctx.get("risk_level"),
        "authority_decision": ctx.get("authority_decision"),
        "approval_required": bool(edge and edge["requires_approval_grant"]),
        "completion_check_required": bool(edge and edge[
            "requires_completion_ready"]),
    }
    policy_output = {
        "requested_to_state": edge["to"] if edge else None,
        "valid_transition": edge is not None,
        "terminal_state": ctx["from_state"] in TERMINAL_STATES,
        "decision": decision["transition_status"],
        "guards_passed": [x["guard_name"] for x in decision["guards"]
                          if x["guard_status"] == "PASSED"],
        "guards_failed": decision["failed_guards"],
        "side_effect_attempted": bool(ctx.get("side_effect_attempted")),
    }
    capsule = {
        "transition_policy_version": POLICY_CAPSULE_VERSION,
        "tenant_id": ctx.get("tenant_id"), "task_id": ctx.get("task_id"),
        "run_id": ctx.get("run_id"), **policy_input, **policy_output,
        "policy_input_hash": _sha(policy_input),
        "policy_output_hash": _sha(policy_output),
    }
    return capsule


def build_preconditions(ctx: dict) -> dict:
    return {
        "same_tenant": ctx.get("tenant_match", True),
        "task_exists": True,
        "from_state": ctx["from_state"],
        "expected_task_version": ctx.get("expected_version"),
        "task_contract_hash": ctx.get("contract_hash"),
        "task_envelope_hash": ctx.get("envelope_hash"),
        "run_state_hash": ctx.get("run_state_hash"),
        "authority_decision": ctx.get("authority_decision"),
        "approval_grant_required": bool(
            (find_edge(ctx["from_state"], ctx["event"]) or {}).get(
                "requires_approval_grant")),
        "consent_required": ctx.get("consent_required", False),
        "evidence_required": ctx.get("evidence_required", False),
        "subject_required": ctx.get("subject_required", False),
    }


def build_postconditions(ctx: dict, decision: dict, *, applied: bool) -> dict:
    return {
        "resulting_state": decision["to_state"],
        "state_advanced": applied and decision[
            "transition_status"] == "ALLOWED",
        "version_incremented_by": 1 if (applied and decision[
            "transition_status"] == "ALLOWED") else 0,
        "state_mutated": applied and decision[
            "transition_status"] == "ALLOWED",
        "no_external_side_effect": True,
        "forbidden_fields_unchanged": True,
    }


def hash_pre(pre: dict) -> str:
    return _sha(pre)


def hash_post(post: dict) -> str:
    return _sha(post)


# --- Transition input/output/transition hashes -----------------------------
def transition_input_hash(ctx: dict) -> str:
    core = {
        "tenant_id": ctx.get("tenant_id"), "task_id": ctx.get("task_id"),
        "run_id": ctx.get("run_id"), "from_state": ctx["from_state"],
        "event": ctx["event"], "actor_id": ctx.get("actor_id"),
        "actor_type": ctx.get("actor_type"),
        "expected_version": ctx.get("expected_version"),
        "contract_hash": ctx.get("contract_hash"),
        "envelope_hash": ctx.get("envelope_hash"),
        "approval_grant_hash": ctx.get("approval_grant_hash"),
        "idempotency_key": ctx.get("idempotency_key"),
    }
    return _sha(core)


def transition_output_hash(decision: dict) -> str:
    return _sha({"transition_status": decision["transition_status"],
                 "to_state": decision["to_state"],
                 "guard_vector_hash": decision["guard_vector_hash"],
                 "failed_guards": sorted(decision["failed_guards"])})


def transition_hash(record: dict) -> str:
    # task_state_hash_after is stamped AFTER this hash is computed (it depends
    # on the post-apply snapshot), so it is excluded to keep the hash stable
    # and re-verifiable from the stored record.
    volatile = {"transition_hash", "previous_transition_hash",
                "transition_chain_hash", "created_at", "honesty_labels",
                "task_state_hash_after"}
    core = {k: v for k, v in record.items() if k not in volatile}
    return _sha(core)


def transition_chain_hash(previous_hash: str, this_hash: str) -> str:
    return _sha({"previous_transition_hash": previous_hash or GENESIS,
                 "transition_hash": this_hash})


# --- Task state hash / lifecycle snapshot ----------------------------------
def task_state_hash(snapshot: dict) -> str:
    core = {k: v for k, v in snapshot.items()
            if k not in ("task_state_hash", "task_lifecycle_snapshot_hash",
                         "updated_at", "honesty_labels")}
    return _sha(core)


def lifecycle_snapshot_hash(snapshot: dict) -> str:
    return _sha({k: v for k, v in snapshot.items()
                 if k not in ("task_lifecycle_snapshot_hash", "honesty_labels",
                              "updated_at")})


# --- Completion Loop -------------------------------------------------------
COMPLETION_STATUSES = {"NOT_CHECKED", "READY", "BLOCKED",
                       "RECONCILIATION_REQUIRED", "SERVER_REVIEW_REQUIRED",
                       "NOT_IMPLEMENTED"}

_BLOCKER_META = {
    "MISSING_REQUIRED_ARTIFACT": ("BLOCKER", "attach the required draft "
                                  "artifact"),
    "MISSING_APPROVAL_GRANT": ("HARD_FAIL", "obtain a valid human approval "
                               "grant"),
    "APPROVAL_GRANT_NOT_CONSUMABLE": ("BLOCKER", "grant not consumable; Tool "
                                      "Broker is not implemented"),
    "MISSING_EVIDENCE_REF": ("BLOCKER", "attach required evidence reference"),
    "EVIDENCE_PROOF_FAILED": ("HARD_FAIL", "fix the failing evidence proof"),
    "CONSENT_REQUIRED": ("BLOCKER", "consent is required for this task"),
    "CONSENT_DENIED": ("HARD_FAIL", "consent is denied; cannot complete"),
    "SUBJECT_ACCESS_NOT_VERIFIED": ("BLOCKER", "verify subject ownership"),
    "RUN_STATE_MISMATCH": ("BLOCKER", "reconcile the linked run state"),
    "TASK_CONTRACT_HASH_CHANGED": ("HARD_FAIL", "task contract changed"),
    "LIFECYCLE_REPLAY_MISMATCH": ("HARD_FAIL", "reconcile lifecycle replay"),
    "TRANSITION_CHAIN_MISMATCH": ("HARD_FAIL", "reconcile transition chain"),
    "OPEN_HIGH_RISK_BLOCKER": ("HARD_FAIL", "resolve the open high-risk "
                               "blocker"),
    "REVIEW_REQUIRED": ("BLOCKER", "human review required"),
    "TOOL_BROKER_NOT_IMPLEMENTED": ("INFO", "execution deferred to Tool Broker "
                                    "(not implemented)"),
    "LLM_RUNTIME_NOT_IMPLEMENTED": ("INFO", "LLM runtime is not implemented"),
}


def completion_criteria(task: dict) -> dict:
    return {
        "completion_contract_version": COMPLETION_CONTRACT_VERSION,
        "task_id": task.get("task_id"), "tenant_id": task.get("tenant_id"),
        "task_type": task.get("task_type"), "segment": task.get("segment"),
        "required_approval_grant": bool(task.get("requires_human_approval")),
        "required_evidence": bool(task.get("requires_evidence_check")),
        "required_consent": bool(task.get("requires_consent_check")),
        "required_subject_access": bool(task.get("subject_id")),
        "required_run_status": bool(task.get("requires_run_ledger")),
        "required_draft_status": True,
        "required_no_open_blockers": True,
        "required_no_lifecycle_mismatch": True,
    }


def evaluate_completion(task: dict, ctx: dict) -> dict:
    """Deterministic Completion Loop. `ctx` supplies observed states. No LLM,
    no free text can flip readiness; only satisfied criteria can."""
    criteria = completion_criteria(task)
    blockers = []

    def add(code):
        sev, hint = _BLOCKER_META[code]
        blockers.append({"blocker_code": code, "severity": sev,
                         "remediation_hint": hint})

    if criteria["required_approval_grant"]:
        gs = ctx.get("approval_grant_validation_status")
        if gs is None or gs == "NONE":
            add("MISSING_APPROVAL_GRANT")
        elif gs == "NOT_CONSUMABLE":
            add("APPROVAL_GRANT_NOT_CONSUMABLE")
        elif gs != "VALID":
            add("MISSING_APPROVAL_GRANT")
    if criteria["required_evidence"] and not ctx.get("evidence_ok"):
        add("EVIDENCE_PROOF_FAILED" if ctx.get("evidence_failed")
            else "MISSING_EVIDENCE_REF")
    if criteria["required_consent"]:
        cs = ctx.get("consent_status")
        if cs == "DENIED":
            add("CONSENT_DENIED")
        elif not ctx.get("consent_ok"):
            add("CONSENT_REQUIRED")
    if criteria["required_subject_access"]:
        sa = ctx.get("subject_access_status")
        if sa == "UNKNOWN":
            add("SUBJECT_ACCESS_NOT_VERIFIED")   # -> server review below
        elif sa == "NOT_VERIFIED":
            add("SUBJECT_ACCESS_NOT_VERIFIED")
    if criteria["required_draft_status"] and not ctx.get("draft_present", True):
        add("MISSING_REQUIRED_ARTIFACT")
    if criteria["required_run_status"] and not ctx.get("run_ok", True):
        add("RUN_STATE_MISMATCH")
    if ctx.get("contract_hash_changed"):
        add("TASK_CONTRACT_HASH_CHANGED")
    if ctx.get("replay_mismatch"):
        add("LIFECYCLE_REPLAY_MISMATCH")
    if ctx.get("chain_mismatch"):
        add("TRANSITION_CHAIN_MISMATCH")

    if ctx.get("replay_mismatch") or ctx.get("chain_mismatch"):
        status = "RECONCILIATION_REQUIRED"
    elif ctx.get("subject_access_status") == "UNKNOWN" \
            and criteria["required_subject_access"]:
        status = "SERVER_REVIEW_REQUIRED"
    elif blockers:
        status = "BLOCKED"
    else:
        status = "READY"

    result = {
        "completion_status": status,
        "completion_blockers": blockers,
        "criteria_satisfied": not blockers,
        "completion_blockers_hash": _sha(blockers),
    }
    criteria["completion_criteria_hash"] = _sha(criteria)
    result["completion_criteria_hash"] = criteria["completion_criteria_hash"]
    result["completion_result_hash"] = _sha({
        "status": status,
        "blockers": [b["blocker_code"] for b in blockers],
        "criteria_hash": criteria["completion_criteria_hash"]})
    result["completion_criteria"] = criteria
    result["honesty_labels"] = HONESTY_LABELS
    return result


def completion_ready(result: dict) -> bool:
    return result["completion_status"] == "READY"


# --- Replay ----------------------------------------------------------------
def replay(initial_state: str, transitions: list) -> dict:
    """Reconstruct lifecycle state from applied transitions. Executes nothing.
    Only ALLOWED transitions advance state; invalid ordering is reported."""
    state = initial_state
    errors = []
    applied = 0
    completion_status = "NOT_CHECKED"
    for i, t in enumerate(transitions):
        if t.get("transition_status") != "ALLOWED":
            continue
        edge = find_edge(t.get("from_state"), t.get("transition_event"))
        if t.get("from_state") != state:
            errors.append(f"transition {i}: from_state {t.get('from_state')} "
                          f"!= replay state {state}")
            continue
        if edge is None or edge["to"] != t.get("to_state"):
            errors.append(f"transition {i}: edge "
                          f"{t.get('from_state')}--{t.get('transition_event')}"
                          f"-->{t.get('to_state')} not in graph")
            continue
        state = t["to_state"]
        applied += 1
        if t.get("completion_status") in ("READY", "BLOCKED"):
            completion_status = t["completion_status"]
        if state == "COMPLETED_NO_SIDE_EFFECTS":
            completion_status = "READY"
    return {"replayed_state": state, "applied_count": applied,
            "replay_errors": errors, "replay_completion_status":
            completion_status}


HONESTY_LABELS = [
    "Server-side task state is authoritative.",
    "State transition does not execute the action.",
    "Transition dry-run does not mutate state.",
    "Transition replay reconstructs lifecycle state; it does not re-run the "
    "task.",
    "Transition reconciliation compares stored and replayed state; it does not "
    "auto-heal silently.",
    "Completion Loop checks readiness only; it does not execute the task.",
    "Completion is deterministic and cannot be set by free text.",
    "Approval grant validation does not call external providers.",
    "Approval grant does not override consent, evidence, RBAC or proof "
    "failures.",
    "Tool Broker is not implemented in this mission.",
    "LLM runtime is not implemented in this mission.",
    "External provider calls are not implemented in this mission.",
    "This is not production autonomous execution.",
]
