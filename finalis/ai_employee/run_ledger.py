"""Finalis Causally Verifiable Run Ledger + Event-Sourced Replay (CORE-A3).

Pure, deterministic logic: canonical run-event envelope + event hashing, a
hash-linked append-only event chain, an internal Merkle checkpoint over event
hashes, the event schema registry, the lifecycle transition validator, and the
event-sourced replay reducer that recomputes run state from the event stream.

The Run Ledger RECORDS, REPLAYS and VERIFIES what happened; it never grants
permission to act. Nothing here executes anything, calls an LLM, calls a tool,
or reaches an external provider. Event payloads may carry untrusted text but
can never rewrite prior events, change the authority snapshot, or move the
replayed state outside the reducer's deterministic rules. Server-side policy
remains authoritative.
"""
from __future__ import annotations

import hashlib
import json

from ..evidence import transparency as _mrk

CANONICAL_EVENT_VERSION = "finalis-run-event-v1"
EVENT_SCHEMA_VERSION = "run-event-v1"
EVENT_HASH_ALGORITHM = "sha256"
GENESIS = "GENESIS"

RUN_STATUSES = [
    "CREATED", "STARTED", "PLANNING", "WAITING_FOR_CONTEXT",
    "APPROVAL_REQUIRED", "PAUSED", "BLOCKED", "DRAFT_READY", "FAILED",
    "CANCELLED", "COMPLETED_NO_SIDE_EFFECTS", "NOT_IMPLEMENTED",
]

TERMINAL_STATUSES = {"BLOCKED", "FAILED", "CANCELLED",
                     "COMPLETED_NO_SIDE_EFFECTS", "NOT_IMPLEMENTED"}

ACTOR_TYPES = {
    "HUMAN_USER", "AI_EMPLOYEE", "SYSTEM",
    "POLICY_ENGINE_NOT_IMPLEMENTED", "TOOL_BROKER_NOT_IMPLEMENTED",
    "APPROVAL_GATE_NOT_IMPLEMENTED",
}

EVENT_STATUSES = {"RECORDED", "BLOCKED", "FAILED", "REDACTED", "VERIFIED",
                  "MISMATCHED", "NOT_IMPLEMENTED"}

# Deterministic lifecycle transitions (from -> allowed to).
TRANSITIONS = {
    "CREATED": {"STARTED", "CANCELLED"},
    "STARTED": {"PLANNING", "BLOCKED"},
    "PLANNING": {"WAITING_FOR_CONTEXT", "APPROVAL_REQUIRED", "DRAFT_READY",
                 "BLOCKED", "FAILED"},
    "WAITING_FOR_CONTEXT": {"PLANNING", "CANCELLED"},
    "APPROVAL_REQUIRED": {"PAUSED", "CANCELLED"},
    "PAUSED": {"CANCELLED", "BLOCKED"},
    "DRAFT_READY": {"COMPLETED_NO_SIDE_EFFECTS", "CANCELLED"},
    "BLOCKED": set(), "FAILED": set(), "CANCELLED": set(),
    "COMPLETED_NO_SIDE_EFFECTS": set(), "NOT_IMPLEMENTED": set(),
}


def valid_transition(src: str, dst: str) -> bool:
    return dst in TRANSITIONS.get(src, set())


# --- Event schema registry -------------------------------------------------
# effect = run status this event drives the run into (None = no status change).
# future_placeholder = represents future capability, never an executed action.
def _e(effect=None, *, terminal=False, future=False, untrusted=False,
       redact=False, actors=("SYSTEM",)):
    return {"schema_version": EVENT_SCHEMA_VERSION, "effect": effect,
            "terminal": terminal, "future_placeholder": future,
            "untrusted_ok": untrusted, "requires_redaction": redact,
            "allowed_actors": set(actors)}


EVENT_SCHEMA = {
    "RUN_CREATED": _e("CREATED"),
    "RUN_STARTED": _e("STARTED"),
    "TASK_CONTRACT_SNAPSHOT_RECORDED": _e(),
    "TASK_ENVELOPE_SNAPSHOT_RECORDED": _e(untrusted=True, redact=True),
    "AUTHORITY_SNAPSHOT_RECORDED": _e(),
    "CAPABILITY_SNAPSHOT_RECORDED": _e(),
    "DATA_SCOPE_SNAPSHOT_RECORDED": _e(),
    "POLICY_PRECHECK_RECORDED": _e(),
    "CONTEXT_REQUESTED": _e("WAITING_FOR_CONTEXT"),
    "CONTEXT_ATTACHED": _e(untrusted=True, redact=True),
    "UNTRUSTED_INPUT_FLAG_RECORDED": _e(untrusted=True),
    "PLAN_DRAFTED": _e("PLANNING"),
    "DRAFT_OUTPUT_PLACEHOLDER_CREATED": _e("DRAFT_READY"),
    "ARTIFACT_REFERENCE_ATTACHED": _e(),
    "EVIDENCE_REFERENCE_ATTACHED": _e(),
    "EVIDENCE_REPORT_REFERENCE_ATTACHED": _e(),
    "APPROVAL_REQUIRED_RECORDED": _e("APPROVAL_REQUIRED"),
    "APPROVAL_GATE_NOT_IMPLEMENTED_RECORDED": _e("PAUSED", future=True,
                                                 actors=("APPROVAL_GATE_NOT_IMPLEMENTED", "SYSTEM")),
    "TOOL_CALL_PROPOSED": _e(future=True, actors=("AI_EMPLOYEE", "SYSTEM")),
    "TOOL_BROKER_NOT_IMPLEMENTED_RECORDED": _e(future=True,
                                               actors=("TOOL_BROKER_NOT_IMPLEMENTED", "SYSTEM")),
    "TOOL_CALL_BLOCKED": _e(),
    "EXTERNAL_PROVIDER_CALL_BLOCKED": _e(),
    "LLM_CALL_BLOCKED": _e(),
    "PROMPT_INJECTION_ATTEMPT_RECORDED": _e(untrusted=True),
    "DATA_SCOPE_EXPANSION_ATTEMPT_RECORDED": _e(untrusted=True),
    "RUN_BLOCKED": _e("BLOCKED", terminal=True),
    "RUN_FAILED": _e("FAILED", terminal=True),
    "RUN_CANCELLED": _e("CANCELLED", terminal=True,
                        actors=("HUMAN_USER", "SYSTEM")),
    "RUN_COMPLETED_NO_SIDE_EFFECTS": _e("COMPLETED_NO_SIDE_EFFECTS",
                                        terminal=True),
    "RUN_SAFE_VIEW_GENERATED": _e(),
    "RUN_VERIFIED": _e(),
    "RUN_VERIFICATION_FAILED": _e(),
    "RUN_TAMPER_WARNING": _e(),
    "RUN_REPLAYED": _e(),
    "RUN_REPLAY_MISMATCH": _e(),
}

HONESTY_LABELS = [
    "Run Ledger records what happened; it does not grant permission to act.",
    "Replay verifies ledger consistency; it does not re-run the task.",
    "Task creation and run creation do not execute external side effects.",
    "No LLM execution is implemented in this mission.",
    "No Tool Broker execution is implemented in this mission.",
    "Human Approval Gate is not implemented in this mission.",
    "Slack and Microsoft Teams execution are not implemented in this "
    "mission.",
    "Trace-ready fields are internal; external telemetry export is not "
    "implemented.",
    "OpenTelemetry provider integration is not implemented.",
    "W3C traceparent propagation is not implemented unless explicitly "
    "exposed.",
    "CloudEvents compliance is not claimed unless explicitly implemented and "
    "tested.",
    "Run event Merkle root is an internal checkpoint; it is not external "
    "notarization.",
    "Safe run view may omit sensitive fields; omitted fields do not change "
    "server-side run truth.",
    "Safe run view is not a separate ledger.",
    "Retention fields are advisory in this build; production retention "
    "enforcement is not implemented.",
    "Server-side policy remains authoritative.",
    "This is not production autonomous execution.",
]

# Fields excluded from the event hash: the hash itself, wall-clock time, and
# server insert time. Everything else (identity, index, chain link, causal
# links, payload) is bound into the hash.
_EVENT_HASH_EXCLUDED = {"event_hash", "event_time", "created_at"}

# Payload fields a SAFE run view redacts.
SAFE_VIEW_OMITTED = ["event_payload", "task_description"]


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _sha(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def payload_hash(payload) -> str:
    return _sha(payload)


def build_event_envelope(*, event_id, run_id, tenant_id, task_id, event_index,
                         event_type, event_status, actor_id, actor_type,
                         trace_id, span_id, parent_span_id, event_source,
                         event_subject, previous_event_hash,
                         causal_parent_event_ids, event_payload,
                         authority_decision=None, policy_decision=None,
                         risk_level=None, artifact_refs=None,
                         evidence_refs=None, report_refs=None, error_code=None,
                         reason="", event_payload_trust="SERVER_GENERATED"
                         ) -> dict:
    """Canonical run-event envelope (CloudEvents-style fields; compliance NOT
    claimed). Deterministic; the event hash is computed over this minus the
    excluded volatile fields."""
    return {
        "canonical_event_version": CANONICAL_EVENT_VERSION,
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "event_id": event_id, "run_id": run_id, "tenant_id": tenant_id,
        "task_id": task_id, "event_index": event_index,
        "causal_parent_event_ids": list(causal_parent_event_ids or []),
        "event_type": event_type, "event_status": event_status,
        "actor_id": actor_id, "actor_type": actor_type, "trace_id": trace_id,
        "span_id": span_id, "parent_span_id": parent_span_id,
        "event_source": event_source, "event_subject": event_subject,
        "previous_event_hash": previous_event_hash,
        "event_payload": event_payload,
        "event_payload_hash": payload_hash(event_payload),
        "event_payload_trust": event_payload_trust,
        "authority_decision": authority_decision,
        "policy_decision": policy_decision, "risk_level": risk_level,
        "artifact_refs": list(artifact_refs or []),
        "evidence_refs": list(evidence_refs or []),
        "report_refs": list(report_refs or []), "error_code": error_code,
        "reason": reason,
    }


def event_hash(envelope: dict) -> str:
    """Deterministic event hash over the envelope minus volatile fields.
    Excludes itself; binds index, run, tenant, task, type, payload, chain
    link and causal parents."""
    core = {k: v for k, v in envelope.items() if k not in _EVENT_HASH_EXCLUDED}
    return _sha(core)


def run_chain_hash(event_hashes: list) -> str:
    """Deterministic derived chain hash over the ordered event hashes —
    changes on any event-hash change or reorder."""
    return _sha(list(event_hashes))


def run_event_merkle_root(event_hashes: list) -> str:
    """Internal Merkle checkpoint over event hashes (reuses the Evidence
    transparency helper). NOT external notarization."""
    return _mrk.merkle_root(list(event_hashes)) if event_hashes \
        else _mrk.merkle_root([])


# --- Event-sourced replay reducer ------------------------------------------
def reduce_run(events: list) -> dict:
    """Deterministically recompute run state from the ordered event stream.
    No external/LLM/tool calls. Detects unknown types, non-contiguous
    indexes, broken hash links, invalid transitions and bad causal parents."""
    status = None
    replay_errors: list = []
    warnings: list = []
    approval_required = False
    tool_broker_required = False
    blocked_reason = None
    failure_reason = None
    terminal = False
    artifact_refs: list = []
    report_refs: list = []
    evidence_refs: list = []
    seen_ids: set = set()
    prev_hash = GENESIS
    expected_index = 1

    for ev in events:
        etype = ev.get("event_type")
        schema = EVENT_SCHEMA.get(etype)
        if schema is None:
            replay_errors.append(f"unknown event_type '{etype}' at index "
                                 f"{ev.get('event_index')}")
            continue
        # index contiguity
        if ev.get("event_index") != expected_index:
            replay_errors.append(
                f"non-contiguous event_index: expected {expected_index}, got "
                f"{ev.get('event_index')}")
        expected_index = ev.get("event_index", expected_index) + 1
        # chain linkage
        if ev.get("previous_event_hash") != prev_hash:
            replay_errors.append(
                f"broken chain at index {ev.get('event_index')}: "
                "previous_event_hash mismatch")
        prev_hash = ev.get("event_hash")
        # causal parents must be earlier, same run, existing
        for pid in ev.get("causal_parent_event_ids", []):
            if pid not in seen_ids:
                replay_errors.append(
                    f"causal parent {pid} missing/not-earlier at index "
                    f"{ev.get('event_index')}")
        seen_ids.add(ev.get("event_id"))
        # status effect + transition validation
        effect = schema["effect"]
        if effect is not None:
            if status is None:
                status = effect               # RUN_CREATED seeds CREATED
            elif valid_transition(status, effect):
                status = effect
            elif status == effect:
                pass
            else:
                replay_errors.append(
                    f"invalid transition {status} -> {effect} via {etype}")
        if etype == "APPROVAL_REQUIRED_RECORDED":
            approval_required = True
        if etype in ("TOOL_CALL_PROPOSED",
                     "TOOL_BROKER_NOT_IMPLEMENTED_RECORDED"):
            tool_broker_required = True
        if etype == "RUN_BLOCKED":
            blocked_reason = ev.get("reason")
        if etype == "RUN_FAILED":
            failure_reason = ev.get("reason")
        if schema["terminal"]:
            terminal = True
        artifact_refs += ev.get("artifact_refs", []) or []
        report_refs += ev.get("report_refs", []) or []
        evidence_refs += ev.get("evidence_refs", []) or []

    ehashes = [ev.get("event_hash") for ev in events]
    state = {
        "replayed_run_status": status or "CREATED",
        "event_count": len(events),
        "latest_event_hash": ehashes[-1] if ehashes else None,
        "run_chain_hash": run_chain_hash(ehashes),
        "terminal": terminal, "approval_required": approval_required,
        "tool_broker_required": tool_broker_required,
        "blocked_reason": blocked_reason, "failure_reason": failure_reason,
        "artifact_refs": sorted(set(artifact_refs)),
        "report_refs": sorted(set(report_refs)),
        "evidence_refs": sorted(set(evidence_refs)),
        "replay_errors": replay_errors, "warnings": warnings,
    }
    state["run_state_hash"] = run_state_hash(state)
    return state


def run_state_hash(state: dict) -> str:
    """Hash of the canonical replayed state, excluding the hash itself and
    volatile diagnostic lists (errors/warnings do not define the state)."""
    core = {k: v for k, v in state.items()
            if k not in ("run_state_hash", "replay_errors", "warnings",
                         "latest_event_hash", "run_chain_hash")}
    return _sha(core)


def assemble_events(*, run_id, tenant_id, task_id, trace_id, actor_id,
                    specs, id_factory) -> list:
    """Build the hash-linked, causally-linked event chain from an ordered list
    of specs. Each spec: dict(event_type, [event_status], [payload],
    [actor_type], [trust], [artifact_refs/evidence_refs/report_refs],
    [authority_decision], [risk_level], [reason]). Deterministic given the
    ids produced by id_factory."""
    events: list = []
    prev = GENESIS
    for i, spec in enumerate(specs, start=1):
        eid = id_factory(i)
        env = build_event_envelope(
            event_id=eid, run_id=run_id, tenant_id=tenant_id, task_id=task_id,
            event_index=i, event_type=spec["event_type"],
            event_status=spec.get("event_status", "RECORDED"),
            actor_id=actor_id, actor_type=spec.get("actor_type", "SYSTEM"),
            trace_id=trace_id, span_id=f"{trace_id}-{i:02d}",
            parent_span_id=(f"{trace_id}-{i - 1:02d}" if i > 1 else None),
            event_source="finalis/ai-employee/run", event_subject=run_id,
            previous_event_hash=prev,
            causal_parent_event_ids=([events[-1]["event_id"]] if events
                                     else []),
            event_payload=spec.get("payload", {}),
            authority_decision=spec.get("authority_decision"),
            policy_decision=spec.get("policy_decision"),
            risk_level=spec.get("risk_level"),
            artifact_refs=spec.get("artifact_refs"),
            evidence_refs=spec.get("evidence_refs"),
            report_refs=spec.get("report_refs"),
            reason=spec.get("reason", ""),
            event_payload_trust=spec.get("trust", "SERVER_GENERATED"))
        env["event_hash"] = event_hash(env)
        prev = env["event_hash"]
        events.append(env)
    return events


def verify_events(events: list) -> dict:
    """Ledger-integrity verification over an ordered event list: recompute
    each event hash, check contiguity + chain linkage + causal parents. Pure;
    returns a structured verdict (no I/O)."""
    tamper_reasons: list = []
    index_status = "CONTIGUOUS"
    causal_status = "VALID"
    prev = GENESIS
    seen: set = set()
    for i, ev in enumerate(events, start=1):
        recomputed = event_hash({k: v for k, v in ev.items()
                                 if k != "event_hash"})
        if recomputed != ev.get("event_hash"):
            tamper_reasons.append(
                f"event {ev.get('event_index')} hash mismatch (payload/type "
                "tampered)")
        if ev.get("event_index") != i:
            index_status = ("DUPLICATE_DETECTED"
                            if ev.get("event_index") in seen
                            else "GAP_DETECTED")
            tamper_reasons.append(
                f"event_index gap/duplicate at position {i}")
        seen.add(ev.get("event_index"))
        if ev.get("previous_event_hash") != prev:
            tamper_reasons.append(
                f"chain break at event {ev.get('event_index')}")
        prev = ev.get("event_hash")
        for pid in ev.get("causal_parent_event_ids", []):
            if pid not in {e.get("event_id") for e in events[:i - 1]}:
                causal_status = "INVALID"
                tamper_reasons.append(
                    f"causal parent {pid} invalid at event "
                    f"{ev.get('event_index')}")
    return {"tamper_reasons": tamper_reasons,
            "event_index_status": index_status,
            "causal_link_status": causal_status,
            "recomputed_latest_event_hash": (events[-1]["event_hash"]
                                             if events else None),
            "recomputed_run_chain_hash": run_chain_hash(
                [e.get("event_hash") for e in events]),
            "recomputed_merkle_root": run_event_merkle_root(
                [e.get("event_hash") for e in events])}


def safe_view_run(run_json: dict, events: list) -> dict:
    """A redacted run view: omit sensitive/untrusted payload; never changes
    stored truth; not a separate ledger."""
    def redact_event(ev):
        return {k: ("<omitted in safe view>" if k in SAFE_VIEW_OMITTED else v)
                for k, v in ev.items()}
    view = dict(run_json)
    view["redaction_profile"] = "SAFE_RUN_VIEW"
    view["events"] = [redact_event(e) for e in events]
    view["redaction_manifest"] = {
        "omitted_fields": sorted(SAFE_VIEW_OMITTED),
        "note": "Safe run view may omit sensitive fields; omitted fields do "
                "not change server-side run truth. Safe run view is not a "
                "separate ledger."}
    view["redaction_manifest_hash"] = _sha(view["redaction_manifest"])
    return view
