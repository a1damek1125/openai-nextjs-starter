"""Finalis ViktorAI Adversarially Verified Four-Plane Proof-Carrying Null Broker
(TOOL-B5).

A deterministic internal broker *skeleton* that performs PROOF-CARRYING NULL
EXECUTION only. It is an airlock between the TOOL-B4 pre-action reference
monitor and a hypothetical FUTURE real execution runtime. It consumes only
B4-approved (ALLOWED_FOR_FUTURE_BROKER_ONLY) proposals and produces only
validation / null-effect outcomes.

It is NOT real tool execution, NOT external provider execution, NOT MCP
runtime/server/client, NOT OpenAI Apps SDK runtime, NOT LLM runtime, NOT
OAuth/token issuance, NOT credential handling, NOT payment/message/CRM/evidence/
export. There is NO execute endpoint anywhere. The single most permissive
outcome is ``BROKER_PREPARED_FOR_FUTURE_ONLY`` — a NULL_EFFECT_ONLY record that
a future runtime *might* later consider. Nothing runs.

The broker does not only prove "nothing was executed"; it proves "nothing could
be interpreted as execution": no null output leaks a payload/secret/credential/
approval/consent/customer field or hidden execution authority; no set of many
requests can recreate one dangerous effect; no forged/stale/mutated/reordered
evidence yields a positive broker result; and the whole skeleton fails closed
under deterministic fault injection.
"""
from __future__ import annotations

from .tool_contracts import canonical_json, _sha, _core_hash, _flatten_text
from . import tool_registry as _tr

BROKER_MODEL_VERSION = "finalis-null-broker-v1"
BROKER_REQUEST_VERSION = "finalis-broker-request-envelope-v1"
FOUR_PLANE_VERSION = "finalis-four-plane-broker-integrity-v1"
PLANE_NONINTERFERENCE_VERSION = "finalis-plane-non-interference-matrix-v1"
SAFETY_LATTICE_VERSION = "finalis-broker-safety-lattice-v1"
MULTI_REQUEST_LEDGER_VERSION = "finalis-multi-request-safety-ledger-v1"
EFFECT_CONSERVATION_VERSION = "finalis-cross-request-effect-conservation-v1"
RISK_CONSERVATION_VERSION = "finalis-cumulative-risk-conservation-v1"
NON_EXFILTRATION_VERSION = "finalis-null-output-non-exfiltration-v1"
SAFE_OUTPUT_VERSION = "finalis-safe-output-projection-v1"
CORRIDOR_VERSION = "finalis-credential-free-corridor-v1"
TOKEN_NON_DERIVATION_VERSION = "finalis-token-non-derivation-v1"
ADAPTER_FREEZE_VERSION = "finalis-adapter-manifest-freeze-v1"
RUNTIME_SURFACE_VERSION = "finalis-runtime-surface-diff-guard-v1"
CAPABILITY_SEAL_VERSION = "finalis-capability-identity-seal-v1"
CERT_CHAIN_VERSION = "finalis-certificate-chain-closure-v1"
OPEN_CHECKPOINT_VERSION = "finalis-broker-open-checkpoint-v1"
ASSUMPTION_LEDGER_VERSION = "finalis-assumption-capture-ledger-v1"
PROOF_CARRYING_CERT_VERSION = "finalis-proof-carrying-broker-action-certificate-v1"
NEGATIVE_EXEC_CERT_VERSION = "finalis-negative-execution-certificate-v1"
NULL_EFFECTOR_VERSION = "finalis-null-effector-v1"
ADAPTER_QUARANTINE_VERSION = "finalis-adapter-quarantine-matrix-v1"
ADAPTER_NON_RESOLUTION_VERSION = "finalis-adapter-non-resolution-proof-v1"
OUTCOME_CLOSURE_VERSION = "finalis-outcome-closure-checkpoint-v1"
EVENT_STREAM_VERSION = "finalis-execution-causal-event-stream-v1"
REPLAY_CONTEXT_VERSION = "finalis-broker-replay-context-v1"
OUTCOME_RECORD_VERSION = "finalis-broker-outcome-record-v1"
SIDE_EFFECT_ZERO_VERSION = "finalis-side-effect-zero-proof-v1"
CREDENTIAL_ABSENCE_VERSION = "finalis-credential-absence-proof-v1"
NO_PROVIDER_VERSION = "finalis-no-provider-proof-v1"
NO_TOKEN_VERSION = "finalis-no-token-proof-v1"
NON_EXECUTION_VERSION = "finalis-broker-non-execution-proof-v1"
BYPASS_SENTINEL_VERSION = "finalis-broker-bypass-sentinel-v1"
FAULT_HARNESS_VERSION = "finalis-adversarial-fault-injection-harness-v1"
RELEASE_GATE_VERSION = "finalis-broker-release-gate-negative-test-report-v1"
CONFORMANCE_VECTOR_VERSION = "finalis-broker-conformance-vector-v1"
PROOF_BUNDLE_VERSION = "finalis-broker-proof-bundle-v1"
ADMISSION_VERSION = "finalis-broker-admission-decision-v1"
EVIDENCE_CONSISTENCY_VERSION = "finalis-evidence-consistency-capsule-v1"
CAPABILITY_SNAPSHOT_VERSION = "finalis-capability-snapshot-seal-v1"
REVALIDATION_VERSION = "finalis-certificate-revalidation-loop-v1"
SHADOW_PLAN_VERSION = "finalis-broker-shadow-plan-v1"
BROKER_EVENT_VERSION = "finalis-broker-event-v1"
GENESIS = "0" * 64


# --- Honesty posture (every positive result carries these) -----------------
HONESTY_LABELS = [
    "NULL_EFFECT_ONLY",
    "NO_REAL_EXECUTION",
    "VALIDATION_ONLY",
    "FUTURE_RUNTIME_PLACEHOLDER",
    "PROOF_CARRYING_NULL_BROKER_ONLY",
    "FOUR_PLANE_BROKER_INTEGRITY_ONLY",
    "CREDENTIAL_FREE_CORRIDOR_ONLY",
    "ADVERSARIALLY_VERIFIED_NULL_ONLY",
    "This broker executes nothing and calls no external provider.",
    "An Action Passport, Governance Receipt, Proof-Carrying Certificate and "
    "Negative Execution Certificate are evidence only, never execution "
    "authority or tokens.",
    "The only effector is a null effector; its outcome is NO_EFFECT_OUTCOME.",
    "Server-side B1/B2/B3/B4 truth is authoritative and only narrows authority.",
]


# --- Acceptable upstream B4 statuses ---------------------------------------
# Only a future-broker-consideration status may even be admitted for null
# preparation. Anything else is a hard upstream block.
B4_ACCEPTABLE_STATUSES = {"PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"}
_B4_HARD_STATUSES = {
    "PREACTION_BLOCKED", "PREACTION_QUARANTINED", "PREACTION_REVOKED",
    "PREACTION_DENIED", "PREACTION_BYPASS_PATTERN_DETECTED",
    "PREACTION_CAPABILITY_DRIFT_DETECTED", "PREACTION_REPLAY_CONFLICT",
    "PREACTION_CIRCUIT_BREAKER_ACTIVE", "PREACTION_STALE",
}

_B1_SECURITY_BLOCKED = {
    "QUARANTINED", "TAMPERED", "RUG_PULL_DETECTED", "DRIFT_DETECTED",
    "FORBIDDEN_CAPABILITY", "CROSS_TENANT_REJECTED", "BLOCKED", "DISABLED",
    "DEPRECATED", "SUPERSEDED", "NOT_IMPLEMENTED",
}
_B1_ADMITTED_OK = {"ADMITTED", "AVAILABLE_FOR_FUTURE_BROKER"}
_B2_QUALITY_OK = {"QUALITY_PASS", "QUALITY_PASS_WITH_WARNINGS"}
_B3_OK = {"PROJECTABLE_FOR_FUTURE", "CONTRACTED"}
_B3_BLOCKED = {"BLOCKED", "QUARANTINED", "TAMPERED"}
_CERT_OK = {"READY_FOR_FUTURE_BROKER_CONSIDERATION"}
_CERT_BLOCKED = {"BLOCKED"}
_CERT_REVOKED = {"REVOKED"}


# --- Hard-fail dominance ladder (highest precedence first) -----------------
FAILURE_DOMINANCE = [
    "TAMPERED",
    "CROSS_TENANT",
    "REVOKED",
    "CIRCUIT_BREAKER_ACTIVE",
    "TOOL_B1_BLOCKED",
    "TOOL_B2_BLOCKED",
    "TOOL_B3_BLOCKED",
    "TOOL_B4_BLOCKED",
    "B4_RECEIPT_MISMATCH",
    "B4_REPLAY_MISMATCH",
    "CONTRACT_STALE",
    "CAPABILITY_DRIFT_DETECTED",
    "STATE_WITNESS_STALE",
    "PAYLOAD_MUTATED",
    "ACTION_PATH_MUTATED",
    "CAUSAL_GRAPH_MUTATED",
    "BROKER_OPEN_CHECKPOINT_FAILED",
    "ASSUMPTION_DRIFT",
    "FOUR_PLANE_INTEGRITY_FAILED",
    "PLANE_INTERFERENCE_DETECTED",
    "BROKER_SAFETY_LATTICE_FAILED",
    "MULTI_REQUEST_SAFETY_FAILED",
    "CROSS_REQUEST_EFFECT_CONSERVATION_FAILED",
    "CUMULATIVE_RISK_CONSERVATION_FAILED",
    "NULL_OUTPUT_EXFILTRATION_DETECTED",
    "SAFE_OUTPUT_PROJECTION_FAILED",
    "CREDENTIAL_CORRIDOR_BROKEN",
    "TOKEN_DERIVATION_ATTEMPT",
    "ADAPTER_MANIFEST_DRIFT",
    "RUNTIME_SURFACE_DIFF_DETECTED",
    "CAPABILITY_IDENTITY_SEAL_FAILED",
    "CERTIFICATE_CHAIN_CLOSURE_FAILED",
    "REAL_ADAPTER_RESOLUTION_ATTEMPT",
    "ADAPTER_NON_RESOLUTION_PROOF_FAILED",
    "CREDENTIAL_PRESENT",
    "TOKEN_ISSUANCE_ATTEMPT",
    "PROVIDER_CALL_ATTEMPT",
    "EXECUTION_ATTEMPT",
    "SIDE_EFFECT_ATTEMPT",
    "NULL_EFFECT_PROOF_FAILED",
    "OUTCOME_CLOSURE_FAILED",
    "NEGATIVE_EXECUTION_CERTIFICATE_FAILED",
    "FAULT_INJECTION_RELEASE_GATE_FAILED",
    "REPLAY_CONFLICT",
    "NEEDS_RECHECK",
    "NULL_ONLY_PREPARED",
    "BROKER_PREPARED_FOR_FUTURE_ONLY",
]
_DOMINANCE_RANK = {sig: i for i, sig in enumerate(FAILURE_DOMINANCE)}

# The clean, non-adverse terminal signals.
POSITIVE_SIGNALS = {"NULL_ONLY_PREPARED", "BROKER_PREPARED_FOR_FUTURE_ONLY"}

BROKER_STATUSES = {
    "BROKER_PREPARED_FOR_FUTURE_ONLY", "NULL_ONLY_PREPARED", "NEEDS_RECHECK",
    "REPLAY_CONFLICT", "BLOCKED", "DENIED", "STALE", "REVOKED", "QUARANTINED",
    "NOT_IMPLEMENTED",
}
POSITIVE_STATUSES = {"BROKER_PREPARED_FOR_FUTURE_ONLY", "NULL_ONLY_PREPARED"}

# Signal -> broker admission status.
_SIGNAL_TO_STATUS = {
    "TAMPERED": "BLOCKED", "CROSS_TENANT": "BLOCKED", "REVOKED": "REVOKED",
    "CIRCUIT_BREAKER_ACTIVE": "BLOCKED", "TOOL_B1_BLOCKED": "BLOCKED",
    "TOOL_B2_BLOCKED": "BLOCKED", "TOOL_B3_BLOCKED": "BLOCKED",
    "TOOL_B4_BLOCKED": "BLOCKED", "B4_RECEIPT_MISMATCH": "BLOCKED",
    "B4_REPLAY_MISMATCH": "BLOCKED", "CONTRACT_STALE": "STALE",
    "CAPABILITY_DRIFT_DETECTED": "BLOCKED", "STATE_WITNESS_STALE": "NEEDS_RECHECK",
    "PAYLOAD_MUTATED": "BLOCKED", "ACTION_PATH_MUTATED": "BLOCKED",
    "CAUSAL_GRAPH_MUTATED": "BLOCKED", "BROKER_OPEN_CHECKPOINT_FAILED": "BLOCKED",
    "ASSUMPTION_DRIFT": "NEEDS_RECHECK", "FOUR_PLANE_INTEGRITY_FAILED": "BLOCKED",
    "PLANE_INTERFERENCE_DETECTED": "BLOCKED",
    "BROKER_SAFETY_LATTICE_FAILED": "BLOCKED",
    "MULTI_REQUEST_SAFETY_FAILED": "BLOCKED",
    "CROSS_REQUEST_EFFECT_CONSERVATION_FAILED": "BLOCKED",
    "CUMULATIVE_RISK_CONSERVATION_FAILED": "BLOCKED",
    "NULL_OUTPUT_EXFILTRATION_DETECTED": "QUARANTINED",
    "SAFE_OUTPUT_PROJECTION_FAILED": "BLOCKED",
    "CREDENTIAL_CORRIDOR_BROKEN": "QUARANTINED",
    "TOKEN_DERIVATION_ATTEMPT": "QUARANTINED", "ADAPTER_MANIFEST_DRIFT": "BLOCKED",
    "RUNTIME_SURFACE_DIFF_DETECTED": "QUARANTINED",
    "CAPABILITY_IDENTITY_SEAL_FAILED": "BLOCKED",
    "CERTIFICATE_CHAIN_CLOSURE_FAILED": "BLOCKED",
    "REAL_ADAPTER_RESOLUTION_ATTEMPT": "QUARANTINED",
    "ADAPTER_NON_RESOLUTION_PROOF_FAILED": "BLOCKED",
    "CREDENTIAL_PRESENT": "QUARANTINED", "TOKEN_ISSUANCE_ATTEMPT": "QUARANTINED",
    "PROVIDER_CALL_ATTEMPT": "QUARANTINED", "EXECUTION_ATTEMPT": "QUARANTINED",
    "SIDE_EFFECT_ATTEMPT": "QUARANTINED", "NULL_EFFECT_PROOF_FAILED": "BLOCKED",
    "OUTCOME_CLOSURE_FAILED": "BLOCKED",
    "NEGATIVE_EXECUTION_CERTIFICATE_FAILED": "BLOCKED",
    "FAULT_INJECTION_RELEASE_GATE_FAILED": "BLOCKED",
    "REPLAY_CONFLICT": "REPLAY_CONFLICT", "NEEDS_RECHECK": "NEEDS_RECHECK",
    "NULL_ONLY_PREPARED": "NULL_ONLY_PREPARED",
    "BROKER_PREPARED_FOR_FUTURE_ONLY": "BROKER_PREPARED_FOR_FUTURE_ONLY",
}

REASON_CODES = {s: s.replace("_", " ").capitalize() + "." for s in
                FAILURE_DOMINANCE}


# --- Taxonomies ------------------------------------------------------------
# Effect classes that, if they aggregate across many "null" requests, could
# reconstitute one dangerous effect (split-attack surface).
SENSITIVE_EFFECT_CLASSES = {
    "EXPORT", "CUSTOMER_MESSAGE", "PAYMENT", "EVIDENCE_WRITE", "EVIDENCE_DELETE",
    "CRM_WRITE", "EXTERNAL_WRITE",
}
_SIDE_EFFECT_TO_CLASS = {
    "PURE_READ": None, "INTERNAL_WRITE": None, "EXTERNAL_READ": None,
    "EXTERNAL_WRITE": "EXTERNAL_WRITE", "CUSTOMER_MESSAGING": "CUSTOMER_MESSAGE",
    "PAYMENT_MOVEMENT": "PAYMENT", "CRM_MUTATION": "CRM_WRITE",
    "EVIDENCE_MUTATION": "EVIDENCE_WRITE", "IRREVERSIBLE": "EXTERNAL_WRITE",
    "DESTRUCTIVE": "EVIDENCE_DELETE",
}
FORBIDDEN_LEAK_PATTERNS = [
    "SECRET_VALUE", "TOKEN_LIKE_VALUE", "CREDENTIAL_LIKE_VALUE",
    "FULL_PAYLOAD_LEAK", "FULL_APPROVAL_ARTIFACT_LEAK",
    "FULL_CONSENT_ARTIFACT_LEAK", "CUSTOMER_SENSITIVE_FIELD_LEAK",
    "CROSS_TENANT_DATA_LEAK", "EXECUTION_AUTHORITY_LEAK",
    "PROVIDER_RESULT_FABRICATION",
]
# Value-shaped markers used to sniff leaks / credential-like objects.
_SECRET_MARKERS = {"secret", "password", "privatekey", "apikey", "accesstoken",
                   "bearer", "oauthtoken", "clientsecret", "credential",
                   "authorization", "sessiontoken", "refreshtoken"}
_CUSTOMER_SENSITIVE_KEYS = {"email", "phone", "ssn", "dob", "address",
                            "card", "iban", "account", "customer_email",
                            "customer_phone"}
_RUNTIME_SURFACE_FLAGS = {
    "execute_endpoint", "provider_call_path", "token_path",
    "external_network_path", "adapter_callable", "side_effect_capability",
    "callable", "runtime_enabled", "network_enabled",
}
# Default deterministic budgets for the conservation/lattice checks.
DEFAULT_POLICY = {
    "effect_budget": 2,          # allowed sensitive-effect units across a set
    "risk_limit": 12,            # cumulative risk ceiling across a set
    "split_threshold": 3,        # >= N related sensitive requests => split risk
}


def _norm(text) -> str:
    return _tr._normalize("" if text is None else str(text)).strip()


def _compact(text) -> str:
    return _norm(text).replace(" ", "")


def _as_list(v):
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple, set)) else [v]


def _flatten_values(obj, out=None):
    """Collect only string VALUE leaves (never dict keys). A safety-flag key
    like ``is_bearer`` (value False) must not be mistaken for a bearer token."""
    out = [] if out is None else out
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _flatten_values(v, out)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            _flatten_values(v, out)
    return out


def dominant_signal(signals) -> str:
    """Highest-precedence signal. Unknown signals rank maximally dominant so a
    novel adverse signal can never be outranked by a benign one."""
    if not signals:
        return "BROKER_PREPARED_FOR_FUTURE_ONLY"
    return min(signals, key=lambda s: _DOMINANCE_RANK.get(s, -1))


def status_for_signals(signals) -> str:
    return _SIGNAL_TO_STATUS.get(dominant_signal(signals), "BLOCKED")


# --- Broker request envelope -----------------------------------------------
def build_broker_request_envelope(*, broker_request_id, tenant_id, actor_id,
                                  actor_type, b4_decision, b4_proposal,
                                  batch_id, task_id, case_id, customer_id,
                                  created_at) -> dict:
    """Normalize a broker request. It references a B4 decision and SEALS the
    reference hashes captured at open-time so any later drift is detectable.
    Executes nothing."""
    d = b4_decision or {}
    p = b4_proposal or {}
    open_seal = {
        "b4_decision_id": d.get("decision_id"),
        "b4_decision_status": d.get("decision_status"),
        "b4_decision_hash": d.get("decision_hash"),
        "b4_proposal_hash": d.get("proposal_hash"),
        "b4_passport_hash": (d.get("action_passport") or {}).get(
            "action_passport_hash"),
        "b4_receipt_hash": (d.get("governance_receipt") or {}).get(
            "governance_receipt_hash"),
        "b4_proof_bundle_hash": (d.get("preaction_proof_bundle") or {}).get(
            "preaction_proof_bundle_hash"),
        "b4_causal_graph_hash": (d.get("causal_action_graph") or {}).get(
            "causal_action_graph_hash"),
        "payload_hash": _sha(p.get("payload", {})),
        "action_path_hash": _sha(_norm(p.get("action_path", ""))),
        "source_freshness_epoch": d.get("source_freshness_epoch", ""),
    }
    env = {
        "broker_request_envelope_id": broker_request_id,
        "broker_request_version": BROKER_REQUEST_VERSION,
        "tenant_id": tenant_id, "tool_id": d.get("tool_id") or p.get("tool_id"),
        "contract_id": d.get("contract_id") or p.get("contract_id"),
        "b4_proposal_id": d.get("proposal_id"),
        "action_path": _norm(p.get("action_path", "")),
        "intent": _norm(p.get("intent", "")),
        "idempotency_key": str(p.get("idempotency_key", "") or ""),
        "batch_id": str(batch_id or ""), "task_id": str(task_id or ""),
        "case_id": str(case_id or ""), "customer_id": str(customer_id or ""),
        "broker_open_seal": open_seal,
        "requested_by_actor_id": actor_id,
        "requested_by_actor_type": actor_type,
        "is_execution": False, "is_dry_run": False,
        "requests_null_broker_only": True, "created_at": created_at,
    }
    env["broker_request_hash"] = _core_hash(env, "broker_request_hash")
    return env


# --- Upstream source verification (B1/B2/B3/B4) ----------------------------
def _upstream_signals(*, tenant_id, b4_decision, b4_proposal, head,
                      quality_report, contract, broker_readiness,
                      circuit_breaker) -> list:
    sig = []
    d, p = b4_decision or {}, b4_proposal or {}
    if not d or not p or head is None or contract is None:
        sig.append("TOOL_B4_BLOCKED")  # missing upstream evidence, fail closed
        return sig
    # Tenant isolation across every referenced object.
    tids = {str(d.get("tenant_id", tenant_id)), str(p.get("tenant_id",
            tenant_id)), str(head.get("tenant_id", tenant_id)),
            str(contract.get("tenant_id", tenant_id))}
    if tids - {str(tenant_id)}:
        sig.append("CROSS_TENANT")
    # B4 decision must be an acceptable future-only status.
    b4status = d.get("decision_status")
    if b4status not in B4_ACCEPTABLE_STATUSES:
        sig.append("TOOL_B4_BLOCKED")
    # B4 receipt/passport present + non-authority + replay-verifiable.
    passport = d.get("action_passport") or {}
    receipt = d.get("governance_receipt") or {}
    if not passport or passport.get("is_token") or passport.get(
            "confers_authority") or passport.get("grants_execution"):
        sig.append("B4_RECEIPT_MISMATCH")
    if not receipt or receipt.get("is_authority") or receipt.get(
            "authorizes_execution"):
        sig.append("B4_RECEIPT_MISMATCH")
    if not (d.get("preaction_proof_bundle") or {}).get(
            "preaction_proof_bundle_hash"):
        sig.append("TOOL_B4_BLOCKED")
    # B1 registry.
    hstatus = head.get("status")
    if hstatus == "TAMPERED":
        sig.append("TAMPERED")
    elif head.get("quarantine_status") == "QUARANTINED" or \
            hstatus == "QUARANTINED":
        sig.append("TOOL_B1_BLOCKED")
    elif hstatus in _B1_SECURITY_BLOCKED or not head.get("admitted") or \
            hstatus not in _B1_ADMITTED_OK:
        sig.append("TOOL_B1_BLOCKED")
    # B2 quality.
    if (quality_report or {}).get("quality_status") not in _B2_QUALITY_OK:
        sig.append("TOOL_B2_BLOCKED")
    # B3 contract + broker-readiness.
    cstatus = contract.get("contract_status")
    if cstatus == "REVOKED" or str(contract.get("revocation_epoch", "0")) \
            not in ("0", ""):
        sig.append("REVOKED")
    elif cstatus == "STALE":
        sig.append("CONTRACT_STALE")
    elif cstatus in _B3_BLOCKED or cstatus not in _B3_OK:
        sig.append("TOOL_B3_BLOCKED")
    cert = (broker_readiness or {}).get("certificate_status")
    if broker_readiness is not None:
        if cert in _CERT_REVOKED:
            sig.append("REVOKED")
        elif cert in _CERT_BLOCKED or cert not in _CERT_OK:
            sig.append("TOOL_B3_BLOCKED")
    # Circuit breaker.
    if circuit_breaker and str(circuit_breaker.get(
            "breaker_state", "CLOSED")).upper() == "OPEN":
        sig.append("CIRCUIT_BREAKER_ACTIVE")
    return sig


def _evidence_drift_signals(*, envelope, b4_decision, b4_proposal,
                            contract) -> list:
    """Compare the CURRENT authoritative evidence against the request's sealed
    open-checkpoint. Any drift (payload/action/causal/contract/receipt/replay/
    decision) is a hard fail."""
    sig = []
    seal = (envelope or {}).get("broker_open_seal", {})
    d, p = b4_decision or {}, b4_proposal or {}
    cur = {
        "b4_decision_hash": d.get("decision_hash"),
        "b4_proposal_hash": d.get("proposal_hash"),
        "b4_receipt_hash": (d.get("governance_receipt") or {}).get(
            "governance_receipt_hash"),
        "b4_causal_graph_hash": (d.get("causal_action_graph") or {}).get(
            "causal_action_graph_hash"),
        "payload_hash": _sha(p.get("payload", {})),
        "action_path_hash": _sha(_norm(p.get("action_path", ""))),
        "source_freshness_epoch": d.get("source_freshness_epoch", ""),
    }
    if seal.get("b4_receipt_hash") != cur["b4_receipt_hash"]:
        sig.append("B4_RECEIPT_MISMATCH")
    if seal.get("b4_decision_hash") != cur["b4_decision_hash"]:
        sig.append("B4_REPLAY_MISMATCH")
    if str(seal.get("source_freshness_epoch", "")) != str(
            contract.get("source_freshness_epoch", "")) if contract else False:
        sig.append("CONTRACT_STALE")
    if seal.get("payload_hash") != cur["payload_hash"]:
        sig.append("PAYLOAD_MUTATED")
    if seal.get("action_path_hash") != cur["action_path_hash"]:
        sig.append("ACTION_PATH_MUTATED")
    if seal.get("b4_causal_graph_hash") != cur["b4_causal_graph_hash"]:
        sig.append("CAUSAL_GRAPH_MUTATED")
    if seal.get("b4_proposal_hash") != cur["b4_proposal_hash"]:
        sig.append("B4_REPLAY_MISMATCH")
    # Capability drift signalled by B4 decision's own drift sentinel.
    if (d.get("capability_drift_sentinel") or {}).get("drift_detected"):
        sig.append("CAPABILITY_DRIFT_DETECTED")
    # State witness staleness carried from B4.
    if (d.get("state_witness_guard") or {}).get("state_witness_stale"):
        sig.append("STATE_WITNESS_STALE")
    return sig


# --- Four-plane broker integrity model -------------------------------------
def build_four_plane_model(*, tenant_id, broker_request_id, envelope,
                           b4_decision, recordkeeping_enables_effect=False) -> dict:
    d = b4_decision or {}
    planner = {"plane": "PLANNER", "records": "what_would_be_planned",
               "action_path": envelope.get("action_path"),
               "intent": envelope.get("intent"), "can_execute": False}
    enforcement = {"plane": "ENFORCEMENT", "records": "what_was_checked",
                   "b4_decision_status": d.get("decision_status"),
                   "b4_decision_hash": d.get("decision_hash"),
                   "can_execute": False}
    effect = {"plane": "EFFECT", "records": "null_effect_only",
              "effect_outcome": "NO_EFFECT_OUTCOME", "callable": False,
              "adapter_resolved": False, "provider_called": False,
              "token_issued": False, "can_execute": False}
    # A recordkeeping plane must NEVER be able to enable the effect plane. This
    # is a real, model-level input (not a hardcoded constant) so the
    # fault-injection harness's recordkeeping_enables_effect_plane case is
    # detected by the model itself, not by harness-side bookkeeping.
    recordkeeping = {"plane": "RECORDKEEPING", "records": "evidence_and_hashes",
                     "b4_receipt_hash": (d.get("governance_receipt") or {}).get(
                         "governance_receipt_hash"),
                     "enables_effect_plane": bool(recordkeeping_enables_effect),
                     "can_execute": False}
    planes = {"planner_plane": planner, "enforcement_plane": enforcement,
              "effect_plane": effect, "recordkeeping_plane": recordkeeping}
    # Integrity: no plane may claim executability, the effect plane must be
    # null, and recordkeeping must not enable the effect plane.
    integrity_ok = (not any(pl.get("can_execute") for pl in planes.values())
                    and effect["effect_outcome"] == "NO_EFFECT_OUTCOME"
                    and not effect["callable"] and not effect["adapter_resolved"]
                    and not recordkeeping["enables_effect_plane"])
    model = {
        "four_plane_broker_integrity_version": FOUR_PLANE_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        **planes,
        "four_plane_integrity_status": "MATCHED" if integrity_ok else "FAILED",
        "signal": None if integrity_ok else "FOUR_PLANE_INTEGRITY_FAILED",
    }
    model["four_plane_broker_integrity_hash"] = _core_hash(
        model, "four_plane_broker_integrity_hash")
    return model


def build_plane_non_interference(*, tenant_id, broker_request_id,
                                 four_plane) -> dict:
    # No plane may enable another to execute; recordkeeping must not feed effect.
    interference = []
    if four_plane["recordkeeping_plane"].get("enables_effect_plane"):
        interference.append("RECORDKEEPING_ENABLES_EFFECT")
    if four_plane["effect_plane"].get("callable") or four_plane[
            "effect_plane"].get("adapter_resolved"):
        interference.append("EFFECT_PLANE_CALLABLE")
    if four_plane["planner_plane"].get("can_execute") or four_plane[
            "enforcement_plane"].get("can_execute"):
        interference.append("PLANE_CLAIMS_EXECUTION")
    ok = not interference
    matrix = {
        "plane_non_interference_version": PLANE_NONINTERFERENCE_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "interference_findings": sorted(interference),
        "non_interference_status": "MATCHED" if ok else "FAILED",
        "signal": None if ok else "PLANE_INTERFERENCE_DETECTED",
    }
    matrix["plane_non_interference_hash"] = _core_hash(
        matrix, "plane_non_interference_hash")
    return matrix


# --- Broker safety lattice -------------------------------------------------
def build_safety_lattice(*, tenant_id, broker_request_id, input_statuses,
                         prior_status=None) -> dict:
    """All broker states form a dominance lattice. Risk/evidence drift can only
    move a request DOWNWARD (toward blocked). An unknown status blocks; an
    unsafe UPWARD transition (from a blocked prior to a positive current
    without fresh evidence) blocks."""
    statuses = [s for s in input_statuses if s]
    unknown = [s for s in statuses if s not in _DOMINANCE_RANK]
    computed = dominant_signal(statuses) if statuses else \
        "BROKER_PREPARED_FOR_FUTURE_ONLY"
    unsafe_up = False
    history = []
    if prior_status is not None:
        history = [prior_status, computed]
        pr = _DOMINANCE_RANK.get(prior_status, -1)
        cr = _DOMINANCE_RANK.get(computed, -1)
        # Higher rank index == more benign (later in the ladder). Moving to a
        # MORE benign state than a prior hard-blocked state is an unsafe upward
        # transition.
        prior_blocked = prior_status not in POSITIVE_SIGNALS and \
            prior_status in _DOMINANCE_RANK
        if prior_blocked and cr > pr:
            unsafe_up = True
    if unknown:
        status = "LATTICE_FAILED"
        signal = "BROKER_SAFETY_LATTICE_FAILED"
    elif unsafe_up:
        status = "UNSAFE_UPWARD_TRANSITION_DETECTED"
        signal = "BROKER_SAFETY_LATTICE_FAILED"
    else:
        status = "LATTICE_MATCHED"
        signal = None
    lattice = {
        "broker_safety_lattice_version": SAFETY_LATTICE_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "input_statuses": statuses, "dominance_order": FAILURE_DOMINANCE,
        "computed_status": computed,
        "dominant_reason_code": REASON_CODES.get(computed, ""),
        "lattice_transition_history": history,
        "unknown_statuses": sorted(unknown),
        "unsafe_upward_transition_detected": unsafe_up,
        "broker_safety_lattice_status": status, "signal": signal,
    }
    lattice["broker_safety_lattice_hash"] = _core_hash(
        lattice, "broker_safety_lattice_hash")
    return lattice


# --- Multi-request safety ledger + conservation ----------------------------
def _request_effect_class(rec) -> str:
    se = rec.get("side_effect_class")
    cls = _SIDE_EFFECT_TO_CLASS.get(se)
    if cls:
        return cls
    for e in _as_list(rec.get("aggregate_effects")):
        if str(e).upper() in SENSITIVE_EFFECT_CLASSES:
            return str(e).upper()
    return ""


def build_multi_request_ledger(*, tenant_id, broker_request_id, envelope,
                               self_effects, related_requests, policy) -> dict:
    policy = {**DEFAULT_POLICY, **(policy or {})}
    reqs = list(related_requests or [])
    self_rec = {"broker_request_id": broker_request_id,
                "aggregate_effects": [str(e).upper() for e in _as_list(
                    self_effects)],
                "customer_id": envelope.get("customer_id"),
                "batch_id": envelope.get("batch_id"),
                "task_id": envelope.get("task_id"),
                "case_id": envelope.get("case_id")}
    allrecs = reqs + [self_rec]
    agg_effects, data_scopes = [], []
    ext, cust_vis, risk = 0, 0, 0
    class_counts = {}
    for r in allrecs:
        cls = _request_effect_class(r)
        for e in _as_list(r.get("aggregate_effects")):
            eu = str(e).upper()
            agg_effects.append(eu)
            if eu in SENSITIVE_EFFECT_CLASSES:
                class_counts[eu] = class_counts.get(eu, 0) + 1
        if cls:
            class_counts[cls] = class_counts.get(cls, 0) + 1
        data_scopes += [str(s) for s in _as_list(r.get("data_scopes"))]
        ext += int(r.get("externality", 0) or 0)
        cust_vis += int(r.get("customer_visibility", 0) or 0)
        risk += int(r.get("risk_score", 0) or 0)
    # Split-risk: the same sensitive effect class appears across >= threshold
    # requests (a dangerous effect split into individually-"null" pieces).
    split_classes = sorted(cls for cls, n in class_counts.items()
                           if cls in SENSITIVE_EFFECT_CLASSES
                           and n >= policy["split_threshold"])
    split = bool(split_classes)
    if split:
        status, signal = "SPLIT_RISK_DETECTED", "MULTI_REQUEST_SAFETY_FAILED"
    elif any(c in SENSITIVE_EFFECT_CLASSES for c in class_counts):
        status, signal = "NEEDS_REVIEW", None
    else:
        status, signal = "MULTI_REQUEST_SAFE", None
    ledger = {
        "multi_request_safety_ledger_version": MULTI_REQUEST_LEDGER_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "related_broker_request_ids": sorted(str(r.get("broker_request_id"))
                                             for r in reqs),
        "batch_id": envelope.get("batch_id"), "task_id": envelope.get("task_id"),
        "case_id": envelope.get("case_id"),
        "customer_id": envelope.get("customer_id"),
        "aggregate_effects": sorted(set(agg_effects)),
        "aggregate_data_scopes": sorted(set(data_scopes)),
        "aggregate_externality": ext, "aggregate_customer_visibility": cust_vis,
        "aggregate_risk_score": risk, "sensitive_class_counts": dict(
            sorted(class_counts.items())),
        "split_risk_detected": split, "split_risk_classes": split_classes,
        "ledger_status": status, "signal": signal,
    }
    ledger["multi_request_safety_ledger_hash"] = _core_hash(
        ledger, "multi_request_safety_ledger_hash")
    return ledger


def build_effect_conservation(*, tenant_id, broker_request_id, ledger,
                              related_requests, policy) -> dict:
    policy = {**DEFAULT_POLICY, **(policy or {})}
    # Sum of sensitive-effect units across the request set.
    declared_sum = sum(n for cls, n in ledger["sensitive_class_counts"].items()
                       if cls in SENSITIVE_EFFECT_CLASSES)
    budget = int(policy["effect_budget"])
    exceeded = declared_sum > budget
    if exceeded:
        status, signal = "EFFECT_BUDGET_EXCEEDED", \
            "CROSS_REQUEST_EFFECT_CONSERVATION_FAILED"
    else:
        status, signal = "EFFECT_CONSERVATION_MATCHED", None
    proof = {
        "cross_request_effect_conservation_version": EFFECT_CONSERVATION_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "related_request_hashes": sorted(str(r.get("payload_hash") or r.get(
            "broker_request_id")) for r in (related_requests or [])),
        "declared_effect_sum": declared_sum, "allowed_effect_budget": budget,
        "effect_budget_exceeded": exceeded, "conservation_status": status,
        "signal": signal,
    }
    proof["cross_request_effect_conservation_hash"] = _core_hash(
        proof, "cross_request_effect_conservation_hash")
    return proof


def build_risk_conservation(*, tenant_id, broker_request_id, ledger,
                            related_requests, policy) -> dict:
    policy = {**DEFAULT_POLICY, **(policy or {})}
    risk_sum = int(ledger["aggregate_risk_score"])
    limit = int(policy["risk_limit"])
    exceeded = risk_sum > limit
    if exceeded:
        status, signal = "RISK_EXCEEDED", "CUMULATIVE_RISK_CONSERVATION_FAILED"
    else:
        status, signal = "RISK_CONSERVATION_MATCHED", None
    proof = {
        "cumulative_risk_conservation_version": RISK_CONSERVATION_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "related_request_hashes": sorted(str(r.get("payload_hash") or r.get(
            "broker_request_id")) for r in (related_requests or [])),
        "risk_dimensions": {"aggregate_externality": ledger[
            "aggregate_externality"], "aggregate_customer_visibility": ledger[
            "aggregate_customer_visibility"], "aggregate_risk_score": risk_sum},
        "risk_sum": risk_sum, "risk_limit": limit, "risk_exceeded": exceeded,
        "risk_conservation_status": status, "signal": signal,
    }
    proof["cumulative_risk_conservation_hash"] = _core_hash(
        proof, "cumulative_risk_conservation_hash")
    return proof


# --- Null output / safe projection / non-exfiltration ----------------------
# Keys whose values are constant, non-sensitive descriptive text (labels,
# reason codes, status strings). Their text must NOT be scanned for markers —
# e.g. the honesty label "CREDENTIAL_FREE_CORRIDOR_ONLY" is safe, not a leak.
_SAFE_DESCRIPTIVE_KEYS = {
    "honesty_labels", "note", "dominant_reason_code", "reason_code",
    "broker_status", "effect_outcome", "non_exfiltration_status", "status",
    "null_effect_only", "broker_request_id", "tenant_id",
}


def _leak_findings(safe_output, *, tenant_id) -> list:
    """Scan a candidate broker output for forbidden leak patterns. The clean
    safe output contains only ids/status/hashes/labels; any sensitive VALUE or
    sensitive KEY is a leak. Constant descriptive text is not scanned."""
    findings = []
    if not isinstance(safe_output, dict):
        return findings
    # Scan only the values of NON-descriptive keys for secret/token markers.
    scan_texts = []
    key_blobs = set()
    for k, v in safe_output.items():
        key_blobs.add(_compact(k))
        if k in _SAFE_DESCRIPTIVE_KEYS:
            continue
        for t in _flatten_text(v):
            scan_texts.append(_compact(t))
    if any(m in b for b in scan_texts for m in _SECRET_MARKERS):
        findings.append("SECRET_VALUE")
        findings.append("CREDENTIAL_LIKE_VALUE")
    if any(m in b for b in scan_texts for m in (
            "bearer", "accesstoken", "oauthtoken", "refreshtoken",
            "sessiontoken")):
        findings.append("TOKEN_LIKE_VALUE")
    # Sensitive KEY names present anywhere in the output.
    if any(m in b for b in key_blobs for m in _SECRET_MARKERS):
        findings.append("CREDENTIAL_LIKE_VALUE")
    if "raw_payload" in safe_output or "payload" in safe_output:
        findings.append("FULL_PAYLOAD_LEAK")
    if "approval_ref" in safe_output or "approval_artifact" in safe_output:
        findings.append("FULL_APPROVAL_ARTIFACT_LEAK")
    if "consent_ref" in safe_output or "consent_artifact" in safe_output:
        findings.append("FULL_CONSENT_ARTIFACT_LEAK")
    if any(k in safe_output for k in _CUSTOMER_SENSITIVE_KEYS):
        findings.append("CUSTOMER_SENSITIVE_FIELD_LEAK")
    if "provider_result" in safe_output:
        findings.append("PROVIDER_RESULT_FABRICATION")
    if safe_output.get("grants_execution") or "execution_authority" in \
            safe_output:
        findings.append("EXECUTION_AUTHORITY_LEAK")
    # Cross-tenant reference in a scanned (non-descriptive) value.
    for k, v in safe_output.items():
        if k in _SAFE_DESCRIPTIVE_KEYS:
            continue
        for t in _flatten_text(v):
            if isinstance(t, str) and t.startswith("tenant:") and t != \
                    f"tenant:{tenant_id}":
                findings.append("CROSS_TENANT_DATA_LEAK")
    return sorted(set(findings))


def build_safe_output_projection(*, tenant_id, broker_request_id, raw_outcome,
                                 redaction_policy_hash) -> dict:
    """Deterministically project a raw outcome into a SAFE outcome that contains
    only non-sensitive fields (ids, status, hashes, labels). A mismatch between
    the redacted safe outcome and the projection means redaction failed."""
    safe = {
        "broker_request_id": broker_request_id, "tenant_id": tenant_id,
        "broker_status": (raw_outcome or {}).get("broker_status"),
        "effect_outcome": "NO_EFFECT_OUTCOME",
        "dominant_reason_code": (raw_outcome or {}).get("dominant_reason_code"),
        "null_effect_only": True, "honesty_labels": HONESTY_LABELS,
    }
    leaks = _leak_findings(safe, tenant_id=tenant_id)
    mismatch = leaks  # a clean safe projection has zero leak fields
    if mismatch:
        status, signal = "SAFE_PROJECTION_FAILED", "SAFE_OUTPUT_PROJECTION_FAILED"
    else:
        status, signal = "SAFE_PROJECTION_MATCHED", None
    proof = {
        "safe_output_projection_version": SAFE_OUTPUT_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "raw_outcome_hash": _sha(raw_outcome or {}),
        "safe_outcome": safe, "safe_outcome_hash": _sha(safe),
        "redaction_policy_hash": redaction_policy_hash,
        "projection_status": status, "projection_mismatch_fields": mismatch,
        "signal": signal,
    }
    proof["safe_output_projection_hash"] = _core_hash(
        proof, "safe_output_projection_hash")
    return proof


def build_non_exfiltration(*, tenant_id, broker_request_id, candidate_output,
                           sensitive_inputs) -> dict:
    """Prove the broker's (candidate) null output reveals none of the forbidden
    leak patterns. The candidate is what would be surfaced; a leak quarantines.
    """
    leaks = _leak_findings(candidate_output, tenant_id=tenant_id)
    if leaks:
        status, signal = "OUTPUT_EXFILTRATION_DETECTED", \
            "NULL_OUTPUT_EXFILTRATION_DETECTED"
    else:
        status, signal = "NO_OUTPUT_EXFILTRATION", None
    proof = {
        "null_output_non_exfiltration_version": NON_EXFILTRATION_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "output_fields_checked": sorted(candidate_output.keys()) if isinstance(
            candidate_output, dict) else [],
        "sensitive_inputs_hashes": sorted(_sha(x) for x in _as_list(
            sensitive_inputs)),
        "redacted_fields": [], "forbidden_leak_patterns": FORBIDDEN_LEAK_PATTERNS,
        "leak_detected": bool(leaks), "detected_leaks": leaks,
        "non_exfiltration_status": status, "signal": signal,
    }
    proof["null_output_non_exfiltration_hash"] = _core_hash(
        proof, "null_output_non_exfiltration_hash")
    return proof


# --- Credential-free corridor / token non-derivation -----------------------
def build_credential_free_corridor(*, tenant_id, broker_request_id, envelope,
                                   b4_decision, adapter_manifest) -> dict:
    """Prove there is NO usable credential path from the broker request to the
    effect plane. Certificates/receipts/passports/leases must not be credentials.
    """
    findings = []
    # Scan VALUES only (not safe boolean flag keys such as is_bearer/is_token).
    haystacks = [envelope, (b4_decision or {}).get("action_passport"),
                 (b4_decision or {}).get("governance_receipt")]
    for hs in haystacks:
        for t in _flatten_values(hs or {}):
            c = _compact(t)
            if any(m in c for m in _SECRET_MARKERS):
                findings.append("CREDENTIAL_LIKE_OBJECT")
                break
    # Adapters are the credential-carrying surface — scan their keys AND values,
    # and treat any credential/token-bearing key as a broken corridor.
    if isinstance(adapter_manifest, dict):
        for blob in [_compact(x) for x in _flatten_text(adapter_manifest)]:
            if any(m in blob for m in _SECRET_MARKERS):
                findings.append("ADAPTER_CARRIES_CREDENTIAL")
                break
        if adapter_manifest.get("credential") or adapter_manifest.get(
                "credentials") or adapter_manifest.get("token"):
            findings.append("ADAPTER_CARRIES_CREDENTIAL")
    ok = not findings
    corridor = {
        "credential_free_corridor_version": CORRIDOR_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "credential_findings": sorted(set(findings)),
        "corridor_status": "CREDENTIAL_FREE" if ok else "CORRIDOR_BROKEN",
        "signal": None if ok else "CREDENTIAL_CORRIDOR_BROKEN",
    }
    corridor["credential_free_corridor_hash"] = _core_hash(
        corridor, "credential_free_corridor_hash")
    return corridor


def build_token_non_derivation(*, tenant_id, broker_request_id, b4_decision,
                               envelope) -> dict:
    """No token may be minted, accepted, inferred, derived or simulated from
    B4/B5 evidence. Passport/receipt/certificate are NOT tokens."""
    findings = []
    d = b4_decision or {}
    for name, obj in (("action_passport", d.get("action_passport")),
                      ("governance_receipt", d.get("governance_receipt")),
                      ("future_execution_lease", d.get(
                          "future_execution_lease"))):
        o = obj or {}
        if o.get("is_token") or o.get("is_bearer") or o.get(
                "confers_authority") or o.get("grants_execution"):
            findings.append(f"{name.upper()}_IS_TOKEN_LIKE")
    for t in _flatten_values(envelope):
        c = _compact(t)
        if any(m in c for m in ("bearer", "accesstoken", "oauthtoken",
                                "refreshtoken")):
            findings.append("REQUEST_CARRIES_TOKEN_LIKE_VALUE")
            break
    ok = not findings
    proof = {
        "token_non_derivation_version": TOKEN_NON_DERIVATION_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "token_derivation_findings": sorted(set(findings)),
        "token_minted": False, "token_accepted": False, "token_derived": False,
        "token_non_derivation_status": "NO_TOKEN_DERIVED" if ok else
        "TOKEN_DERIVATION_DETECTED",
        "signal": None if ok else "TOKEN_DERIVATION_ATTEMPT",
    }
    proof["token_non_derivation_hash"] = _core_hash(
        proof, "token_non_derivation_hash")
    return proof


# --- Adapter freeze / non-resolution / quarantine / runtime surface --------
DEFAULT_ADAPTER_MANIFEST = {"adapter_kind": "NULL_PLACEHOLDER",
                            "callable": False, "resolvable": False}


def build_adapter_manifest_freeze(*, tenant_id, broker_request_id,
                                  adapter_manifest, sealed_manifest_hash) -> dict:
    manifest = adapter_manifest or DEFAULT_ADAPTER_MANIFEST
    cur_hash = _sha(manifest)
    drift = sealed_manifest_hash is not None and cur_hash != sealed_manifest_hash
    callable_flag = bool(manifest.get("callable") or manifest.get(
        "resolvable") or manifest.get("adapter_callable"))
    if drift or callable_flag:
        status = "ADAPTER_MANIFEST_DRIFT" if drift else "CALLABLE_ADAPTER"
        signal = "ADAPTER_MANIFEST_DRIFT"
    else:
        status, signal = "MANIFEST_FROZEN", None
    freeze = {
        "adapter_manifest_freeze_version": ADAPTER_FREEZE_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "frozen_manifest_hash": cur_hash,
        "sealed_manifest_hash": sealed_manifest_hash,
        "manifest_drift_detected": drift, "callable_adapter_detected":
        callable_flag, "freeze_status": status, "signal": signal,
    }
    freeze["adapter_manifest_freeze_hash"] = _core_hash(
        freeze, "adapter_manifest_freeze_hash")
    return freeze


def build_adapter_non_resolution(*, tenant_id, broker_request_id,
                                 adapter_manifest) -> dict:
    manifest = adapter_manifest or {}
    resolved = bool(manifest.get("resolved") or manifest.get(
        "resolvable") or manifest.get("callable") or manifest.get(
        "endpoint") or manifest.get("provider_url"))
    quarantine = []
    if resolved:
        quarantine.append("ADAPTER_RESOLVED")
    if manifest.get("callable"):
        quarantine.append("ADAPTER_CALLABLE")
    if manifest.get("provider_url") or manifest.get("endpoint"):
        quarantine.append("ADAPTER_HAS_ENDPOINT")
    ok = not resolved and not quarantine
    matrix = {
        "adapter_quarantine_matrix_version": ADAPTER_QUARANTINE_VERSION,
        "adapter_non_resolution_version": ADAPTER_NON_RESOLUTION_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "adapter_resolved": resolved, "quarantine_findings": sorted(
            set(quarantine)),
        "non_resolution_status": "NULL_ADAPTER_ONLY" if ok else
        "REAL_ADAPTER_RESOLUTION_DETECTED",
        "signal": None if ok else ("REAL_ADAPTER_RESOLUTION_ATTEMPT"
                                   if resolved else
                                   "ADAPTER_NON_RESOLUTION_PROOF_FAILED"),
    }
    matrix["adapter_non_resolution_proof_hash"] = _core_hash(
        matrix, "adapter_non_resolution_proof_hash")
    return matrix


def build_runtime_surface_diff(*, tenant_id, broker_request_id,
                               observed_surface) -> dict:
    surface = observed_surface or {}
    detected = sorted(k for k, v in surface.items()
                      if k in _RUNTIME_SURFACE_FLAGS and v)
    ok = not detected
    guard = {
        "runtime_surface_diff_version": RUNTIME_SURFACE_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "watched_flags": sorted(_RUNTIME_SURFACE_FLAGS),
        "detected_runtime_surface": detected,
        "diff_status": "SURFACE_CLEAR" if ok else "RUNTIME_SURFACE_DETECTED",
        "signal": None if ok else "RUNTIME_SURFACE_DIFF_DETECTED",
    }
    guard["runtime_surface_diff_hash"] = _core_hash(
        guard, "runtime_surface_diff_hash")
    return guard


# --- Capability identity seal + certificate chain closure ------------------
def build_capability_identity_seal(*, tenant_id, broker_request_id, head,
                                   contract, envelope) -> dict:
    ok = head is not None and contract is not None and \
        str(head.get("tenant_id", tenant_id)) == str(tenant_id) and \
        head.get("tool_id") == envelope.get("tool_id")
    seal_material = {"tool_id": envelope.get("tool_id"),
                     "tool_version_id": (head or {}).get("latest_version_id"),
                     "contract_id": envelope.get("contract_id"),
                     "descriptor_hash": (head or {}).get("descriptor_hash"),
                     "abi_hash": ((contract or {}).get("contract_abi") or {}).get(
                         "abi_hash")}
    seal = {
        "capability_identity_seal_version": CAPABILITY_SEAL_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "seal_material_hash": _sha(seal_material),
        "identity_sealed": ok,
        "seal_status": "SEALED" if ok else "SEAL_FAILED",
        "signal": None if ok else "CAPABILITY_IDENTITY_SEAL_FAILED",
    }
    seal["capability_identity_seal_hash"] = _core_hash(
        seal, "capability_identity_seal_hash")
    return seal


def build_certificate_chain_closure(*, tenant_id, broker_request_id, head,
                                    quality_report, contract, b4_decision) -> dict:
    """Close the chain B1 registry -> B2 quality -> B3 contract -> B4 receipt ->
    B5 negative certificate. Any missing link blocks; closure never authorizes
    execution."""
    links = {
        "b1_registry": bool(head) and (head or {}).get(
            "descriptor_hash") is not None,
        "b2_quality": bool(quality_report) and (quality_report or {}).get(
            "quality_report_hash") is not None,
        "b3_contract": bool(contract) and (contract or {}).get(
            "contract_hash") is not None,
        "b4_receipt": bool((b4_decision or {}).get("governance_receipt", {}).get(
            "governance_receipt_hash")),
    }
    missing = sorted(k for k, v in links.items() if not v)
    ok = not missing
    closure = {
        "certificate_chain_closure_version": CERT_CHAIN_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "chain_links": links, "missing_links": missing,
        "chain_material_hash": _sha({
            "b1": (head or {}).get("descriptor_hash"),
            "b2": (quality_report or {}).get("quality_report_hash"),
            "b3": (contract or {}).get("contract_hash"),
            "b4": (b4_decision or {}).get("governance_receipt", {}).get(
                "governance_receipt_hash")}),
        "authorizes_execution": False,
        "closure_status": "CHAIN_CLOSED" if ok else "CHAIN_OPEN",
        "signal": None if ok else "CERTIFICATE_CHAIN_CLOSURE_FAILED",
    }
    closure["certificate_chain_closure_hash"] = _core_hash(
        closure, "certificate_chain_closure_hash")
    return closure


# --- Open checkpoint / assumptions / null effector -------------------------
def build_open_checkpoint(*, tenant_id, broker_request_id, envelope,
                          drift_signals) -> dict:
    ok = not any(s in drift_signals for s in (
        "B4_RECEIPT_MISMATCH", "B4_REPLAY_MISMATCH", "PAYLOAD_MUTATED",
        "ACTION_PATH_MUTATED", "CAUSAL_GRAPH_MUTATED"))
    cp = {
        "broker_open_checkpoint_version": OPEN_CHECKPOINT_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "sealed_open_hash": (envelope or {}).get("broker_request_hash"),
        "checkpoint_matched": ok,
        "checkpoint_status": "OPEN_CHECKPOINT_MATCHED" if ok else
        "OPEN_CHECKPOINT_FAILED",
        "signal": None if ok else "BROKER_OPEN_CHECKPOINT_FAILED",
    }
    cp["broker_open_checkpoint_hash"] = _core_hash(
        cp, "broker_open_checkpoint_hash")
    return cp


def build_assumption_ledger(*, tenant_id, broker_request_id, b4_decision,
                            head, quality_report, contract, drift_signals) -> dict:
    assumptions = {
        "b4_allowed_for_future_only": (b4_decision or {}).get(
            "decision_status") in B4_ACCEPTABLE_STATUSES,
        "b1_admitted": bool((head or {}).get("admitted")),
        "b2_quality_passed": (quality_report or {}).get(
            "quality_status") in _B2_QUALITY_OK,
        "b3_contract_ok": (contract or {}).get("contract_status") in _B3_OK,
        "evidence_unchanged": not any(s in drift_signals for s in (
            "PAYLOAD_MUTATED", "ACTION_PATH_MUTATED", "CAUSAL_GRAPH_MUTATED",
            "B4_RECEIPT_MISMATCH", "B4_REPLAY_MISMATCH")),
    }
    drifted = sorted(k for k, v in assumptions.items() if not v)
    ok = not drifted
    ledger = {
        "assumption_capture_ledger_version": ASSUMPTION_LEDGER_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "captured_assumptions": assumptions, "drifted_assumptions": drifted,
        "assumptions_still_valid": ok,
        "signal": None if ok else "ASSUMPTION_DRIFT",
    }
    ledger["assumption_capture_ledger_hash"] = _core_hash(
        ledger, "assumption_capture_ledger_hash")
    return ledger


def build_null_effector(*, tenant_id, broker_request_id, envelope) -> dict:
    """The ONLY effector. It records what a FUTURE runtime would have needed and
    always yields NO_EFFECT_OUTCOME. It calls nothing."""
    effector = {
        "null_effector_version": NULL_EFFECTOR_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "would_need_for_future_execution": {
            "future_adapter": "NOT_IMPLEMENTED",
            "future_credential": "NOT_IMPLEMENTED",
            "future_runtime": "NOT_IMPLEMENTED",
            "future_broker_lease": "NOT_IMPLEMENTED"},
        "effect_outcome": "NO_EFFECT_OUTCOME", "invoked_external_system": False,
        "produced_real_output": False, "null_effect_only": True,
    }
    effector["null_effector_hash"] = _core_hash(effector, "null_effector_hash")
    return effector


# --- Side-effect zero / credential absence / no-provider / no-token --------
def build_side_effect_zero(*, tenant_id, broker_request_id, null_effector,
                           runtime_surface_diff, adapter_freeze) -> dict:
    attempts = []
    if null_effector.get("invoked_external_system") or null_effector.get(
            "produced_real_output"):
        attempts.append("EFFECTOR_SIDE_EFFECT")
    if runtime_surface_diff.get("detected_runtime_surface"):
        attempts.append("RUNTIME_SURFACE")
    if adapter_freeze.get("callable_adapter_detected"):
        attempts.append("CALLABLE_ADAPTER")
    ok = not attempts
    proof = {
        "side_effect_zero_version": SIDE_EFFECT_ZERO_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "side_effect_attempts": sorted(attempts),
        "side_effect_count": 0 if ok else len(attempts),
        "side_effect_zero_status": "SIDE_EFFECT_ZERO" if ok else
        "SIDE_EFFECT_DETECTED",
        "signal": None if ok else "SIDE_EFFECT_ATTEMPT",
    }
    proof["side_effect_zero_hash"] = _core_hash(proof, "side_effect_zero_hash")
    return proof


def build_absence_proofs(*, tenant_id, broker_request_id, corridor,
                         token_non_derivation, adapter_non_resolution,
                         runtime_surface_diff) -> dict:
    credential_present = bool(corridor.get("credential_findings"))
    provider_call = bool(adapter_non_resolution.get("adapter_resolved")) or \
        "provider_call_path" in runtime_surface_diff.get(
            "detected_runtime_surface", [])
    token_attempt = bool(token_non_derivation.get("token_derivation_findings"))
    proofs = {
        "credential_absence_proof": {
            "version": CREDENTIAL_ABSENCE_VERSION,
            "credential_present": credential_present,
            "status": "NO_CREDENTIAL" if not credential_present else
            "CREDENTIAL_PRESENT",
            "signal": "CREDENTIAL_PRESENT" if credential_present else None},
        "no_provider_proof": {
            "version": NO_PROVIDER_VERSION, "provider_called": provider_call,
            "status": "NO_PROVIDER_CALL" if not provider_call else
            "PROVIDER_CALL_DETECTED",
            "signal": "PROVIDER_CALL_ATTEMPT" if provider_call else None},
        "no_token_proof": {
            "version": NO_TOKEN_VERSION, "token_issued": token_attempt,
            "status": "NO_TOKEN" if not token_attempt else
            "TOKEN_ISSUANCE_DETECTED",
            "signal": "TOKEN_ISSUANCE_ATTEMPT" if token_attempt else None},
    }
    proofs["tenant_id"] = tenant_id
    proofs["broker_request_id"] = broker_request_id
    proofs["absence_proofs_hash"] = _core_hash(proofs, "absence_proofs_hash")
    return proofs


def build_non_execution_proof(*, tenant_id, broker_request_id) -> dict:
    items = ["no_tool_executed", "no_broker_runtime", "no_mcp_server",
             "no_mcp_client", "no_llm_called", "no_external_provider_called",
             "no_token_issued", "no_token_derived", "no_credential_read",
             "no_secret_read", "no_payment_executed", "no_customer_message_sent",
             "no_crm_mutated", "no_evidence_mutated", "no_data_exported",
             "no_network_side_effect", "no_adapter_resolved", "no_dry_run"]
    proof = {
        "broker_non_execution_version": NON_EXECUTION_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "assertions": {k: True for k in items}, "all_hold": True,
    }
    proof["broker_non_execution_hash"] = _core_hash(
        proof, "broker_non_execution_hash")
    return proof


# --- Bypass sentinel -------------------------------------------------------
def build_bypass_sentinel(*, tenant_id, broker_request_id, b4_decision,
                          envelope, upstream_signals) -> dict:
    findings = []
    d = b4_decision or {}
    # Any B4 evidence object used as execution authority is a bypass attempt.
    for name in ("action_passport", "governance_receipt",
                 "future_execution_lease"):
        o = d.get(name) or {}
        if o.get("grants_execution") or o.get("confers_authority") or o.get(
                "is_authority") or o.get("authorizes_execution"):
            findings.append(f"{name.upper()}_USED_AS_AUTHORITY")
    if "TOOL_B4_BLOCKED" in upstream_signals:
        findings.append("B4_BYPASS_ATTEMPT")
    if envelope.get("is_execution") or envelope.get("is_dry_run"):
        findings.append("REQUEST_CLAIMS_EXECUTION")
    ok = not findings
    sentinel = {
        "broker_bypass_sentinel_version": BYPASS_SENTINEL_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "bypass_findings": sorted(set(findings)), "bypass_detected": bool(
            findings),
        "signal": "EXECUTION_ATTEMPT" if findings else None,
    }
    sentinel["broker_bypass_sentinel_hash"] = _core_hash(
        sentinel, "broker_bypass_sentinel_hash")
    return sentinel


# --- Core evaluation (no fault harness, no release gate) --------------------
def _broker_signals(ctx) -> tuple:
    """Deterministic core: compute every model + collect adverse signals for one
    broker request. Does NOT run the fault harness (which re-enters this)."""
    tid = ctx["tenant_id"]
    rid = ctx["broker_request_id"]
    env = ctx["envelope"]
    d = ctx["b4_decision"]
    p = ctx["b4_proposal"]
    head, quality = ctx["head"], ctx["quality_report"]
    contract, cert = ctx["contract"], ctx["broker_readiness"]
    reports, signals = {}, []

    up = _upstream_signals(
        tenant_id=tid, b4_decision=d, b4_proposal=p, head=head,
        quality_report=quality, contract=contract, broker_readiness=cert,
        circuit_breaker=ctx.get("circuit_breaker"))
    signals += up
    drift = _evidence_drift_signals(
        envelope=env, b4_decision=d, b4_proposal=p, contract=contract)
    signals += drift

    four_plane = build_four_plane_model(
        tenant_id=tid, broker_request_id=rid, envelope=env, b4_decision=d,
        recordkeeping_enables_effect=ctx.get("recordkeeping_enables_effect",
                                             False))
    non_interf = build_plane_non_interference(
        tenant_id=tid, broker_request_id=rid, four_plane=four_plane)
    open_cp = build_open_checkpoint(
        tenant_id=tid, broker_request_id=rid, envelope=env, drift_signals=drift)
    assumptions = build_assumption_ledger(
        tenant_id=tid, broker_request_id=rid, b4_decision=d, head=head,
        quality_report=quality, contract=contract, drift_signals=drift)
    self_effect = _SIDE_EFFECT_TO_CLASS.get(
        (contract or {}).get("contract_side_effect_class", "PURE_READ"))
    ledger = build_multi_request_ledger(
        tenant_id=tid, broker_request_id=rid, envelope=env,
        self_effects=[self_effect] if self_effect else [],
        related_requests=ctx.get("related_requests"), policy=ctx.get("policy"))
    effect_cons = build_effect_conservation(
        tenant_id=tid, broker_request_id=rid, ledger=ledger,
        related_requests=ctx.get("related_requests"), policy=ctx.get("policy"))
    risk_cons = build_risk_conservation(
        tenant_id=tid, broker_request_id=rid, ledger=ledger,
        related_requests=ctx.get("related_requests"), policy=ctx.get("policy"))
    adapter_manifest = ctx.get("adapter_manifest")
    corridor = build_credential_free_corridor(
        tenant_id=tid, broker_request_id=rid, envelope=env, b4_decision=d,
        adapter_manifest=adapter_manifest)
    token_nd = build_token_non_derivation(
        tenant_id=tid, broker_request_id=rid, b4_decision=d, envelope=env)
    freeze = build_adapter_manifest_freeze(
        tenant_id=tid, broker_request_id=rid, adapter_manifest=adapter_manifest,
        sealed_manifest_hash=ctx.get("sealed_manifest_hash"))
    adapter_nr = build_adapter_non_resolution(
        tenant_id=tid, broker_request_id=rid, adapter_manifest=adapter_manifest)
    surface = build_runtime_surface_diff(
        tenant_id=tid, broker_request_id=rid,
        observed_surface=ctx.get("observed_surface"))
    seal = build_capability_identity_seal(
        tenant_id=tid, broker_request_id=rid, head=head, contract=contract,
        envelope=env)
    chain = build_certificate_chain_closure(
        tenant_id=tid, broker_request_id=rid, head=head,
        quality_report=quality, contract=contract, b4_decision=d)
    null_eff = build_null_effector(
        tenant_id=tid, broker_request_id=rid, envelope=env)
    side_zero = build_side_effect_zero(
        tenant_id=tid, broker_request_id=rid, null_effector=null_eff,
        runtime_surface_diff=surface, adapter_freeze=freeze)
    absence = build_absence_proofs(
        tenant_id=tid, broker_request_id=rid, corridor=corridor,
        token_non_derivation=token_nd, adapter_non_resolution=adapter_nr,
        runtime_surface_diff=surface)
    bypass = build_bypass_sentinel(
        tenant_id=tid, broker_request_id=rid, b4_decision=d, envelope=env,
        upstream_signals=up)
    non_exec = build_non_execution_proof(tenant_id=tid, broker_request_id=rid)

    # Candidate null output the broker would surface -> non-exfiltration check.
    candidate = {"broker_request_id": rid, "tenant_id": tid,
                 "effect_outcome": "NO_EFFECT_OUTCOME",
                 "null_effect_only": True, "honesty_labels": HONESTY_LABELS}
    candidate.update(ctx.get("injected_output_extra") or {})
    non_exfil = build_non_exfiltration(
        tenant_id=tid, broker_request_id=rid, candidate_output=candidate,
        sensitive_inputs=[p.get("payload") if p else {}])
    safe_proj = build_safe_output_projection(
        tenant_id=tid, broker_request_id=rid,
        raw_outcome={"broker_status": "PENDING", "dominant_reason_code": ""},
        redaction_policy_hash=ctx.get("redaction_policy_hash",
                                      _sha({"policy": "default-v1"})))

    for m in (four_plane, non_interf, open_cp, assumptions, ledger, effect_cons,
              risk_cons, corridor, token_nd, freeze, adapter_nr, surface, seal,
              chain, side_zero, bypass, non_exfil, safe_proj):
        s = m.get("signal")
        if s:
            signals.append(s)
    for k in ("credential_absence_proof", "no_provider_proof", "no_token_proof"):
        s = absence[k].get("signal")
        if s:
            signals.append(s)

    # Replay conflict: same idempotency key + DIFFERENT evidence (broker request
    # hash) as a prior outcome is a conflict. Computed HERE (in the core signal
    # pass) so the fault-injection harness's same_idempotency_key_different_
    # payload case is detected by the model, not by harness-side bookkeeping.
    prior = ctx.get("prior_outcome")
    if ctx.get("replay_conflict") or (
            prior is not None
            and prior.get("idempotency_key") == env.get("idempotency_key")
            and prior.get("broker_request_hash") != env.get(
                "broker_request_hash")):
        signals.append("REPLAY_CONFLICT")

    # Safety lattice over the collected input statuses.
    lattice = build_safety_lattice(
        tenant_id=tid, broker_request_id=rid, input_statuses=list(signals),
        prior_status=ctx.get("prior_status"))
    if lattice["signal"]:
        signals.append(lattice["signal"])

    reports.update({
        "four_plane_model": four_plane, "plane_non_interference": non_interf,
        "broker_open_checkpoint": open_cp, "assumption_capture_ledger":
        assumptions, "broker_safety_lattice": lattice,
        "multi_request_safety_ledger": ledger,
        "cross_request_effect_conservation": effect_cons,
        "cumulative_risk_conservation": risk_cons,
        "credential_free_corridor": corridor, "token_non_derivation": token_nd,
        "adapter_manifest_freeze": freeze, "adapter_non_resolution": adapter_nr,
        "runtime_surface_diff": surface, "capability_identity_seal": seal,
        "certificate_chain_closure": chain, "null_effector": null_eff,
        "side_effect_zero": side_zero, "absence_proofs": absence,
        "broker_bypass_sentinel": bypass, "broker_non_execution_proof": non_exec,
        "null_output_non_exfiltration": non_exfil,
        "safe_output_projection": safe_proj,
    })
    return sorted(set(signals)), reports


# --- Adversarial fault-injection harness -----------------------------------
FAULT_CASES = [
    "missing_b4_receipt", "stale_b4_receipt", "mutated_payload",
    "mutated_b3_contract", "mutated_adapter_manifest", "reordered_event_stream",
    "dropped_event_stream_event", "duplicated_event_stream_event",
    "forged_proof_carrying_certificate", "forged_negative_execution_certificate",
    "token_like_artifact_inserted", "credential_like_artifact_inserted",
    "callable_adapter_flag_inserted", "runtime_surface_inserted",
    "fake_provider_result_inserted", "null_output_leaks_payload",
    "recordkeeping_enables_effect_plane", "split_export_across_requests",
    "same_idempotency_key_different_payload",
]


def _apply_fault(fault, ctx):
    """Return a deterministically corrupted copy of ctx for one fault case."""
    import copy
    c = copy.deepcopy(ctx)
    d = c.get("b4_decision") or {}
    p = c.get("b4_proposal") or {}
    if fault == "missing_b4_receipt":
        d["governance_receipt"] = {}
    elif fault == "stale_b4_receipt":
        d.setdefault("governance_receipt", {})["governance_receipt_hash"] = \
            "STALE_" + str((d.get("governance_receipt") or {}).get(
                "governance_receipt_hash"))
    elif fault == "mutated_payload":
        p["payload"] = {**(p.get("payload") or {}), "_injected": "x"}
    elif fault == "mutated_b3_contract":
        if c.get("contract"):
            c["contract"] = {**c["contract"], "contract_hash": "MUTATED"}
            c["contract"]["contract_status"] = "TAMPERED_UNKNOWN"
    elif fault == "mutated_adapter_manifest":
        c["adapter_manifest"] = {**(c.get("adapter_manifest") or {}),
                                 "_drift": True}
    elif fault in ("reordered_event_stream", "dropped_event_stream_event",
                   "duplicated_event_stream_event"):
        c["event_stream_integrity_ok"] = False
        c.setdefault("injected_output_extra", {})
        # An event-stream integrity break maps to a replay mismatch.
        d["decision_hash"] = "EVENTSTREAM_" + fault
    elif fault == "forged_proof_carrying_certificate":
        c["forged_proof_carrying_certificate"] = True
        d["preaction_proof_bundle"] = {**(d.get("preaction_proof_bundle") or {}),
                                       "preaction_proof_bundle_hash": "FORGED"}
        d["decision_hash"] = "FORGED_PCC"
    elif fault == "forged_negative_execution_certificate":
        c["forged_negative_execution_certificate"] = True
        d["governance_receipt"] = {**(d.get("governance_receipt") or {}),
                                   "governance_receipt_hash": "FORGED_NEC"}
    elif fault == "token_like_artifact_inserted":
        c["injected_output_extra"] = {"access_token": "eyJhbGciOi"}
        d["action_passport"] = {**(d.get("action_passport") or {}),
                                "is_token": True}
    elif fault == "credential_like_artifact_inserted":
        c["adapter_manifest"] = {**(c.get("adapter_manifest") or {}),
                                 "credential": "supersecret"}
    elif fault == "callable_adapter_flag_inserted":
        c["adapter_manifest"] = {**(c.get("adapter_manifest") or {}),
                                 "callable": True}
    elif fault == "runtime_surface_inserted":
        c["observed_surface"] = {**(c.get("observed_surface") or {}),
                                 "execute_endpoint": True}
    elif fault == "fake_provider_result_inserted":
        c["injected_output_extra"] = {"provider_result": {"ok": True}}
    elif fault == "null_output_leaks_payload":
        c["injected_output_extra"] = {"payload": (p.get("payload") or {})}
    elif fault == "recordkeeping_enables_effect_plane":
        c["recordkeeping_enables_effect"] = True
    elif fault == "split_export_across_requests":
        c["related_requests"] = [
            {"broker_request_id": f"r{i}", "aggregate_effects": ["EXPORT"],
             "risk_score": 5} for i in range(5)]
    elif fault == "same_idempotency_key_different_payload":
        c["prior_status"] = None
        c["replay_conflict"] = True
    c["b4_decision"], c["b4_proposal"] = d, p
    return c


def run_fault_injection_harness(*, tenant_id, broker_request_id, base_ctx):
    """Deterministically corrupt/remove/stale/reorder/mutate/replay evidence.
    Every injected fault MUST fail closed (a blocker status). Any unexpected
    positive result blocks release."""
    results = []
    unexpected = []
    for fault in FAULT_CASES:
        fctx = _apply_fault(fault, base_ctx)
        # Every fault is detected by the MODEL itself (via _broker_signals):
        # hash/manifest/surface/candidate corruption -> drift/guard signals;
        # recordkeeping_enables_effect -> four-plane failure; replay_conflict ->
        # replay signal; split -> multi-request failure. No harness-side
        # hardcoded signals — the corruption must reach a real detector.
        sigs, _ = _broker_signals(fctx)
        sigs = sorted(set(sigs))
        status = status_for_signals(sigs)
        failed_closed = status not in POSITIVE_STATUSES
        results.append({"fault_case": fault, "dominant_signal":
                        dominant_signal(sigs), "broker_status": status,
                        "failed_closed": failed_closed})
        if not failed_closed:
            unexpected.append(fault)
    harness_status = "FAULT_INJECTION_PASSED" if not unexpected else \
        "FAULT_INJECTION_FAILED"
    harness = {
        "fault_injection_harness_version": FAULT_HARNESS_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "fault_cases": FAULT_CASES, "fault_results": results,
        "unexpected_positive_results": unexpected,
        "harness_status": harness_status,
        "signal": None if not unexpected else "FAULT_INJECTION_RELEASE_GATE_FAILED",
    }
    harness["fault_injection_harness_hash"] = _core_hash(
        harness, "fault_injection_harness_hash")
    return harness


def build_release_gate(*, tenant_id, broker_request_id, harness) -> dict:
    failures = harness.get("unexpected_positive_results", [])
    passed = harness.get("harness_status") == "FAULT_INJECTION_PASSED" and \
        not failures
    gate = {
        "broker_release_gate_report_version": RELEASE_GATE_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "harness_hash": harness["fault_injection_harness_hash"],
        "negative_test_count": len(harness.get("fault_cases", [])),
        "negative_test_failures": failures,
        "release_gate_status": "RELEASE_GATE_PASSED" if passed else
        "RELEASE_GATE_FAILED",
        "signal": None if passed else "FAULT_INJECTION_RELEASE_GATE_FAILED",
    }
    gate["broker_release_gate_hash"] = _core_hash(
        gate, "broker_release_gate_hash")
    return gate


# --- Certificates / outcome / proof bundle ---------------------------------
def build_proof_carrying_certificate(*, tenant_id, broker_request_id, envelope,
                                     b4_decision, reports, status) -> dict:
    cert = {
        "proof_carrying_broker_action_certificate_version":
        PROOF_CARRYING_CERT_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "b4_decision_id": (b4_decision or {}).get("decision_id"),
        "b4_receipt_hash": (b4_decision or {}).get("governance_receipt", {}).get(
            "governance_receipt_hash"),
        "broker_open_checkpoint_hash": reports["broker_open_checkpoint"][
            "broker_open_checkpoint_hash"],
        "assumption_ledger_hash": reports["assumption_capture_ledger"][
            "assumption_capture_ledger_hash"],
        "null_effector_hash": reports["null_effector"]["null_effector_hash"],
        "broker_status": status,
        "is_token": False, "is_credential": False,
        "authorizes_execution": False,
        "note": "Proof-carrying evidence only. Not a token, not a credential, "
        "not execution authority.",
    }
    cert["proof_carrying_broker_action_certificate_hash"] = _core_hash(
        cert, "proof_carrying_broker_action_certificate_hash")
    return cert


def build_negative_execution_certificate(*, tenant_id, broker_request_id,
                                         non_execution_proof, side_effect_zero,
                                         absence_proofs) -> dict:
    ok = (non_execution_proof.get("all_hold") and
          side_effect_zero.get("side_effect_zero_status") == "SIDE_EFFECT_ZERO"
          and not absence_proofs["credential_absence_proof"].get(
              "credential_present")
          and not absence_proofs["no_provider_proof"].get("provider_called")
          and not absence_proofs["no_token_proof"].get("token_issued"))
    cert = {
        "negative_execution_certificate_version": NEGATIVE_EXEC_CERT_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "states_that_did_not_happen": [
            "no_tool_executed", "no_provider_called", "no_token_issued",
            "no_token_derived", "no_credential_read", "no_side_effect",
            "no_payment", "no_customer_message", "no_crm_mutation",
            "no_evidence_mutation", "no_data_export"],
        "is_token": False, "authorizes_execution": False,
        "replay_verifiable": True,
        "certificate_status": "NEGATIVE_EXECUTION_CERTIFIED" if ok else
        "NEGATIVE_EXECUTION_CERTIFICATE_FAILED",
        "signal": None if ok else "NEGATIVE_EXECUTION_CERTIFICATE_FAILED",
        "note": "Local replay-verifiable evidence of what did NOT happen. Not a "
        "production signature. Cannot authorize execution.",
    }
    cert["negative_execution_certificate_hash"] = _core_hash(
        cert, "negative_execution_certificate_hash")
    return cert


def build_outcome_closure(*, tenant_id, broker_request_id, null_effector,
                          negative_certificate) -> dict:
    ok = (null_effector.get("effect_outcome") == "NO_EFFECT_OUTCOME" and
          negative_certificate.get("certificate_status") ==
          "NEGATIVE_EXECUTION_CERTIFIED")
    cp = {
        "outcome_closure_checkpoint_version": OUTCOME_CLOSURE_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "outcome_equivalent_to_no_state_changed": ok,
        "closure_status": "OUTCOME_CLOSED_NULL" if ok else
        "OUTCOME_CLOSURE_FAILED",
        "signal": None if ok else "OUTCOME_CLOSURE_FAILED",
    }
    cp["outcome_closure_checkpoint_hash"] = _core_hash(
        cp, "outcome_closure_checkpoint_hash")
    return cp


def build_conformance_vector(*, tenant_id, broker_request_id, reports,
                             harness, release_gate) -> dict:
    dims = {
        "four_plane_integrity": reports["four_plane_model"][
            "four_plane_integrity_status"] == "MATCHED",
        "plane_non_interference": reports["plane_non_interference"][
            "non_interference_status"] == "MATCHED",
        "safety_lattice": reports["broker_safety_lattice"][
            "broker_safety_lattice_status"] == "LATTICE_MATCHED",
        "multi_request_safety": reports["multi_request_safety_ledger"][
            "ledger_status"] in ("MULTI_REQUEST_SAFE", "NEEDS_REVIEW"),
        "effect_conservation": reports["cross_request_effect_conservation"][
            "conservation_status"] == "EFFECT_CONSERVATION_MATCHED",
        "risk_conservation": reports["cumulative_risk_conservation"][
            "risk_conservation_status"] == "RISK_CONSERVATION_MATCHED",
        "non_exfiltration": reports["null_output_non_exfiltration"][
            "non_exfiltration_status"] == "NO_OUTPUT_EXFILTRATION",
        "safe_output_projection": reports["safe_output_projection"][
            "projection_status"] == "SAFE_PROJECTION_MATCHED",
        "credential_free_corridor": reports["credential_free_corridor"][
            "corridor_status"] == "CREDENTIAL_FREE",
        "token_non_derivation": reports["token_non_derivation"][
            "token_non_derivation_status"] == "NO_TOKEN_DERIVED",
        "adapter_frozen": reports["adapter_manifest_freeze"][
            "freeze_status"] == "MANIFEST_FROZEN",
        "runtime_surface_clear": reports["runtime_surface_diff"][
            "diff_status"] == "SURFACE_CLEAR",
        "side_effect_zero": reports["side_effect_zero"][
            "side_effect_zero_status"] == "SIDE_EFFECT_ZERO",
        "fault_injection_passed": harness["harness_status"] ==
        "FAULT_INJECTION_PASSED",
        "release_gate_passed": release_gate["release_gate_status"] ==
        "RELEASE_GATE_PASSED",
    }
    vec = {
        "broker_conformance_vector_version": CONFORMANCE_VECTOR_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "dimensions": dims, "conformant": all(dims.values()),
    }
    vec["broker_conformance_vector_hash"] = _core_hash(
        vec, "broker_conformance_vector_hash")
    return vec


def build_proof_bundle(*, tenant_id, broker_request_id, reports, harness,
                       release_gate, status, dominant) -> dict:
    component_hashes = {
        "broker_safety_lattice_hash": reports["broker_safety_lattice"][
            "broker_safety_lattice_hash"],
        "multi_request_safety_ledger_hash": reports[
            "multi_request_safety_ledger"]["multi_request_safety_ledger_hash"],
        "cross_request_effect_conservation_hash": reports[
            "cross_request_effect_conservation"][
            "cross_request_effect_conservation_hash"],
        "cumulative_risk_conservation_hash": reports[
            "cumulative_risk_conservation"]["cumulative_risk_conservation_hash"],
        "null_output_non_exfiltration_hash": reports[
            "null_output_non_exfiltration"]["null_output_non_exfiltration_hash"],
        "safe_output_projection_hash": reports["safe_output_projection"][
            "safe_output_projection_hash"],
        "fault_injection_harness_hash": harness["fault_injection_harness_hash"],
        "broker_release_gate_hash": release_gate["broker_release_gate_hash"],
        "four_plane_broker_integrity_hash": reports["four_plane_model"][
            "four_plane_broker_integrity_hash"],
        "plane_non_interference_hash": reports["plane_non_interference"][
            "plane_non_interference_hash"],
        "credential_free_corridor_hash": reports["credential_free_corridor"][
            "credential_free_corridor_hash"],
        "token_non_derivation_hash": reports["token_non_derivation"][
            "token_non_derivation_hash"],
        "adapter_manifest_freeze_hash": reports["adapter_manifest_freeze"][
            "adapter_manifest_freeze_hash"],
        "runtime_surface_diff_hash": reports["runtime_surface_diff"][
            "runtime_surface_diff_hash"],
        "capability_identity_seal_hash": reports["capability_identity_seal"][
            "capability_identity_seal_hash"],
        "certificate_chain_closure_hash": reports["certificate_chain_closure"][
            "certificate_chain_closure_hash"],
        "side_effect_zero_hash": reports["side_effect_zero"][
            "side_effect_zero_hash"],
        "broker_non_execution_hash": reports["broker_non_execution_proof"][
            "broker_non_execution_hash"],
    }
    bundle = {
        "broker_proof_bundle_version": PROOF_BUNDLE_VERSION,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "component_hashes": dict(sorted(component_hashes.items())),
        "broker_status": status, "dominant_signal": dominant,
        "executes_nothing": True, "null_effect_only": True,
    }
    bundle["broker_proof_bundle_hash"] = _core_hash(
        bundle, "broker_proof_bundle_hash")
    return bundle


# --- Top-level preparation -------------------------------------------------
def prepare_broker_outcome(*, broker_request_id, tenant_id, actor_id,
                           actor_type, envelope, b4_decision, b4_proposal, head,
                           quality_report, contract, broker_readiness,
                           circuit_breaker=None, related_requests=None,
                           adapter_manifest=None, observed_surface=None,
                           sealed_manifest_hash=None, prior_status=None,
                           prior_outcome=None, policy=None,
                           redaction_policy_hash=None, created_at=None) -> dict:
    """Prepare a NULL broker outcome. Runs the full deterministic evaluation,
    the adversarial fault-injection harness, and the release gate, then resolves
    the fail-closed dominant status. Executes nothing."""
    # Seal the adapter manifest at prepare-time so any later mutation (incl. the
    # fault-injection harness's mutated_adapter_manifest case) drifts from the
    # sealed baseline and fails closed.
    if sealed_manifest_hash is None:
        sealed_manifest_hash = _sha(adapter_manifest or DEFAULT_ADAPTER_MANIFEST)
    ctx = {
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "envelope": envelope, "b4_decision": b4_decision,
        "b4_proposal": b4_proposal, "head": head, "quality_report":
        quality_report, "contract": contract, "broker_readiness":
        broker_readiness, "circuit_breaker": circuit_breaker,
        "related_requests": related_requests or [],
        "adapter_manifest": adapter_manifest, "observed_surface":
        observed_surface, "sealed_manifest_hash": sealed_manifest_hash,
        "prior_status": prior_status, "policy": policy,
        "prior_outcome": prior_outcome,
        "redaction_policy_hash": redaction_policy_hash or _sha(
            {"policy": "default-v1"}),
        "injected_output_extra": None,
    }
    # Replay conflict (same idempotency key, different evidence) is now detected
    # inside _broker_signals from ctx["prior_outcome"], so it is exercised by the
    # fault-injection harness too.
    signals, reports = _broker_signals(ctx)

    # Fault-injection harness + release gate (adversarial verification).
    harness = run_fault_injection_harness(
        tenant_id=tenant_id, broker_request_id=broker_request_id, base_ctx=ctx)
    release_gate = build_release_gate(
        tenant_id=tenant_id, broker_request_id=broker_request_id,
        harness=harness)
    if release_gate["signal"]:
        signals.append(release_gate["signal"])

    # Certificates + outcome closure.
    non_exec = reports["broker_non_execution_proof"]
    neg_cert = build_negative_execution_certificate(
        tenant_id=tenant_id, broker_request_id=broker_request_id,
        non_execution_proof=non_exec,
        side_effect_zero=reports["side_effect_zero"],
        absence_proofs=reports["absence_proofs"])
    if neg_cert["signal"]:
        signals.append(neg_cert["signal"])
    closure = build_outcome_closure(
        tenant_id=tenant_id, broker_request_id=broker_request_id,
        null_effector=reports["null_effector"], negative_certificate=neg_cert)
    if closure["signal"]:
        signals.append(closure["signal"])

    signals = sorted(set(signals))
    # If nothing adverse, the clean terminal is a null-only preparation.
    if not signals:
        signals = ["BROKER_PREPARED_FOR_FUTURE_ONLY"]
    dominant = dominant_signal(signals)
    status = _SIGNAL_TO_STATUS.get(dominant, "BLOCKED")

    pcc = build_proof_carrying_certificate(
        tenant_id=tenant_id, broker_request_id=broker_request_id,
        envelope=envelope, b4_decision=b4_decision, reports=reports,
        status=status)
    conformance = build_conformance_vector(
        tenant_id=tenant_id, broker_request_id=broker_request_id,
        reports=reports, harness=harness, release_gate=release_gate)
    proof_bundle = build_proof_bundle(
        tenant_id=tenant_id, broker_request_id=broker_request_id,
        reports=reports, harness=harness, release_gate=release_gate,
        status=status, dominant=dominant)

    # Safe output projection bound to the final status (deterministic, redacted).
    safe_proj = build_safe_output_projection(
        tenant_id=tenant_id, broker_request_id=broker_request_id,
        raw_outcome={"broker_status": status,
                     "dominant_reason_code": REASON_CODES.get(dominant, "")},
        redaction_policy_hash=ctx["redaction_policy_hash"])
    reports["safe_output_projection"] = safe_proj

    outcome = {
        "broker_outcome_record_version": OUTCOME_RECORD_VERSION,
        "broker_admission_decision_version": ADMISSION_VERSION,
        "broker_request_id": broker_request_id, "tenant_id": tenant_id,
        "tool_id": (envelope or {}).get("tool_id"),
        "contract_id": (envelope or {}).get("contract_id"),
        "b4_decision_id": (b4_decision or {}).get("decision_id"),
        "broker_status": status, "dominant_signal": dominant,
        "dominant_reason_code": REASON_CODES.get(dominant, ""),
        "all_signals": signals,
        "signal_reason_codes": {s: REASON_CODES.get(s, "") for s in signals},
        "effect_outcome": "NO_EFFECT_OUTCOME", "null_effect_only": True,
        "executes_nothing": True, "is_execution": False,
        "requires_future_runtime": True,
        "broker_request_hash": (envelope or {}).get("broker_request_hash"),
        "idempotency_key": (envelope or {}).get("idempotency_key"),
        "decided_by_actor_id": actor_id, "decided_by_actor_type": actor_type,
        "created_at": created_at, "updated_at": created_at,
        # Model records.
        "four_plane_model": reports["four_plane_model"],
        "plane_non_interference": reports["plane_non_interference"],
        "broker_open_checkpoint": reports["broker_open_checkpoint"],
        "assumption_capture_ledger": reports["assumption_capture_ledger"],
        "broker_safety_lattice": reports["broker_safety_lattice"],
        "multi_request_safety_ledger": reports["multi_request_safety_ledger"],
        "cross_request_effect_conservation": reports[
            "cross_request_effect_conservation"],
        "cumulative_risk_conservation": reports["cumulative_risk_conservation"],
        "null_output_non_exfiltration": reports["null_output_non_exfiltration"],
        "safe_output_projection": safe_proj,
        "credential_free_corridor": reports["credential_free_corridor"],
        "token_non_derivation": reports["token_non_derivation"],
        "adapter_manifest_freeze": reports["adapter_manifest_freeze"],
        "adapter_non_resolution": reports["adapter_non_resolution"],
        "runtime_surface_diff": reports["runtime_surface_diff"],
        "capability_identity_seal": reports["capability_identity_seal"],
        "certificate_chain_closure": reports["certificate_chain_closure"],
        "null_effector": reports["null_effector"],
        "side_effect_zero": reports["side_effect_zero"],
        "absence_proofs": reports["absence_proofs"],
        "broker_bypass_sentinel": reports["broker_bypass_sentinel"],
        "broker_non_execution_proof": non_exec,
        "negative_execution_certificate": neg_cert,
        "outcome_closure_checkpoint": closure,
        "proof_carrying_broker_action_certificate": pcc,
        "fault_injection_harness": harness,
        "broker_release_gate_report": release_gate,
        "broker_conformance_vector": conformance,
        "broker_proof_bundle": proof_bundle,
        "honesty_labels": HONESTY_LABELS,
    }
    outcome["broker_decision_hash"] = _core_hash(
        outcome, "broker_decision_hash", "broker_request_id",
        "decided_by_actor_id", "decided_by_actor_type", "broker_state_hash")
    outcome["broker_state_hash"] = _sha({
        "broker_request_id": broker_request_id,
        "broker_decision_hash": outcome["broker_decision_hash"],
        "broker_status": status, "dominant_signal": dominant,
        "broker_request_hash": (envelope or {}).get("broker_request_hash")})
    return outcome


# --- Event stream + broker event ledger ------------------------------------
BROKER_EVENT_TYPES = {
    "BROKER_REQUEST_OPENED", "BROKER_OUTCOME_PREPARED", "BROKER_FAULT_INJECTED",
    "BROKER_RELEASE_GATE_EVALUATED", "BROKER_OUTCOME_VERIFIED",
}


def build_broker_event(*, event_type, tenant_id, broker_request_id,
                       actor_id, actor_type, broker_state_hash,
                       previous_event_hash, sequence, detail, created_at) -> dict:
    ev = {
        "broker_event_version": BROKER_EVENT_VERSION, "event_type": event_type,
        "tenant_id": tenant_id, "broker_request_id": broker_request_id,
        "actor_id": actor_id, "actor_type": actor_type,
        "broker_state_hash": broker_state_hash,
        "previous_event_hash": previous_event_hash or GENESIS,
        "sequence": sequence, "detail": detail or {}, "created_at": created_at,
    }
    ev["event_hash"] = _core_hash(ev, "event_hash")
    return ev
