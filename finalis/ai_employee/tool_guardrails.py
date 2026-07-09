"""Finalis ViktorAI Causal Pre-Action Reference Monitor (TOOL-B4).

A deterministic, NON-EXECUTING pre-action governance layer that sits in front of
a FUTURE Tool Broker. It receives internal *Tool Action Proposals* and returns
deterministic *pre-action decisions*. It is NOT the Tool Broker, NOT a tool
executor, NOT a dry-run, NOT an MCP server/client, NOT an LLM/external-provider
caller, NOT an OAuth/token issuer, and it moves NO payment, sends NO customer
message, writes NO CRM record, deletes NO evidence, and exports nothing. The
single most permissive outcome it can ever emit is
``PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY`` — a statement that a not-yet-built
broker MAY later consider the action, never that anything ran.

Design invariants (all fail-closed):

* Registry (TOOL-B1), quality (TOOL-B2), and contract/broker-readiness (TOOL-B3)
  state are AUTHORITY-NARROWING inputs. The monitor can only ever restrict what
  those layers already allow; it can never widen them. Server-side truth is
  authoritative; a proposal is untrusted declared input.
* Hard-fail dominance always wins over any positive signal. Unknown / missing
  signals are treated as maximally adverse.
* Nondelegable decisions (legal validity, payment, admin grant, evidence
  deletion, consent override, sensitive export, secret access, cross-tenant) are
  human-only. An AI actor can never self-authorize them.
* The AI can never approve its own action, validate itself as human truth, or
  turn a proposal into authority. An Action Passport is NOT a token; a
  Governance Receipt is NOT authority; a Future Execution Lease is a
  NOT_IMPLEMENTED placeholder.
"""
from __future__ import annotations

import json as _json

from .tool_contracts import (  # reuse the exact same deterministic primitives
    canonical_json, _sha, _core_hash, _flatten_text, _SANITIZE_NEEDLES,
    FORBIDDEN_EFFECTS,
)
from . import tool_registry as _tr

GUARDRAIL_MODEL_VERSION = "finalis-preaction-reference-monitor-v1"
PROPOSAL_ENVELOPE_VERSION = "finalis-tool-action-proposal-v1"
CAUSAL_GRAPH_VERSION = "finalis-causal-action-graph-v1"
TEMPORAL_AUTOMATON_VERSION = "finalis-temporal-policy-automaton-v1"
DRIFT_SENTINEL_VERSION = "finalis-capability-drift-sentinel-v1"
COUNTERFACTUAL_TWIN_VERSION = "finalis-counterfactual-denial-twin-v1"
BYPASS_SIM_VERSION = "finalis-bypass-attack-simulator-v1"
AUTHORITY_COMPOSITION_VERSION = "finalis-authority-composition-v1"
PATH_RISK_VERSION = "finalis-path-risk-budget-v1"
DELEGATION_VERSION = "finalis-delegation-chain-v1"
ACTION_PASSPORT_VERSION = "finalis-action-passport-v1"
GOVERNANCE_RECEIPT_VERSION = "finalis-governance-receipt-v1"
EXECUTION_LEASE_VERSION = "finalis-future-execution-lease-placeholder-v1"
NO_EXECUTION_PROOF_VERSION = "finalis-preaction-no-execution-proof-v1"
PROOF_BUNDLE_VERSION = "finalis-preaction-proof-bundle-v1"
DECISION_VERSION = "finalis-preaction-decision-v1"
CIRCUIT_BREAKER_VERSION = "finalis-preaction-circuit-breaker-v1"
DECISION_EVENT_VERSION = "finalis-preaction-decision-event-v1"
GENESIS = "0" * 64


# --- Decision status vocabulary --------------------------------------------
DECISION_STATUSES = {
    "PREACTION_PENDING",
    "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY",
    "PREACTION_DRAFT_ONLY",
    "PREACTION_NEEDS_HUMAN_APPROVAL",
    "PREACTION_NEEDS_MEANINGFUL_REVIEW",
    "PREACTION_NEEDS_CONSENT",
    "PREACTION_NEEDS_STATE_REFRESH",
    "PREACTION_NEEDS_REDUCED_SCOPE",
    "PREACTION_NEEDS_REVIEW",
    "PREACTION_DENIED",
    "PREACTION_BLOCKED",
    "PREACTION_QUARANTINED",
    "PREACTION_STALE",
    "PREACTION_REVOKED",
    "PREACTION_REPLAYED",
    "PREACTION_REPLAY_CONFLICT",
    "PREACTION_RATE_LIMITED",
    "PREACTION_QUOTA_EXCEEDED",
    "PREACTION_AUTHORITY_BUDGET_EXCEEDED",
    "PREACTION_PATH_RISK_BUDGET_EXCEEDED",
    "PREACTION_CIRCUIT_BREAKER_ACTIVE",
    "PREACTION_COUNTERFACTUAL_REVIEW",
    "PREACTION_BYPASS_PATTERN_DETECTED",
    "PREACTION_CAPABILITY_DRIFT_DETECTED",
    "PREACTION_NOT_IMPLEMENTED",
}
# The only non-adverse outcomes. Every one of them still requires a future
# broker; none of them means "executed".
POSITIVE_STATUSES = {
    "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY", "PREACTION_DRAFT_ONLY",
}
# Statuses that indicate a hard security stop (never a "needs X" remediation).
HARD_STOP_STATUSES = {
    "PREACTION_BLOCKED", "PREACTION_QUARANTINED", "PREACTION_REVOKED",
    "PREACTION_DENIED", "PREACTION_BYPASS_PATTERN_DETECTED",
    "PREACTION_CAPABILITY_DRIFT_DETECTED", "PREACTION_REPLAY_CONFLICT",
    "PREACTION_CIRCUIT_BREAKER_ACTIVE",
}


# --- Hard-fail dominance ladder (highest precedence first) -----------------
# A single fail-closed ordering: whichever adverse signal is present with the
# highest precedence dictates the decision. Anything not on this list is
# treated as maximally dominant (unknown == worst).
FAILURE_DOMINANCE = [
    "TAMPERED",
    "QUARANTINED",
    "REVOKED",
    "CROSS_TENANT",
    "CIRCUIT_BREAKER_ACTIVE",
    "TOOL_B1_BLOCKED",
    "TOOL_B2_BLOCKED",
    "TOOL_B3_BLOCKED",
    "CONTRACT_STALE",
    "CAPABILITY_DRIFT_DETECTED",
    "ACTION_PATH_INVALID",
    "CAUSAL_GRAPH_INCOMPLETE",
    "TEMPORAL_POLICY_REJECTED",
    "DELEGATION_CHAIN_INVALID",
    "INTENT_MISMATCH",
    "AUTHORITY_EXPANSION",
    "NONDELEGABLE_DECISION",
    "APPROVAL_MISSING",
    "CONSENT_MISSING",
    "STATE_WITNESS_STALE",
    "PAYLOAD_SCHEMA_MISMATCH",
    "PAYLOAD_SCOPE_MISMATCH",
    "EFFECT_FORBIDDEN",
    "COUNTERFACTUAL_REVIEW_REQUIRED",
    "BYPASS_PATTERN_DETECTED",
    "AUTHORITY_BUDGET_EXCEEDED",
    "PATH_RISK_BUDGET_EXCEEDED",
    "TOKEN_PASSTHROUGH",
    "PROVIDER_CALL_ATTEMPT",
    "EXECUTION_ATTEMPT",
    "REPLAY_CONFLICT",
    "RATE_LIMITED",
    "QUOTA_EXCEEDED",
    "NEEDS_MEANINGFUL_REVIEW",
    "NEEDS_REVIEW",
    "DRAFT_ONLY",
    "ALLOWED_FOR_FUTURE_BROKER_ONLY",
]
_DOMINANCE_RANK = {sig: i for i, sig in enumerate(FAILURE_DOMINANCE)}

# Signal -> decision status. Every adverse signal maps to exactly one status.
_SIGNAL_TO_STATUS = {
    "TAMPERED": "PREACTION_BLOCKED",
    "QUARANTINED": "PREACTION_QUARANTINED",
    "REVOKED": "PREACTION_REVOKED",
    "CROSS_TENANT": "PREACTION_BLOCKED",
    "CIRCUIT_BREAKER_ACTIVE": "PREACTION_CIRCUIT_BREAKER_ACTIVE",
    "TOOL_B1_BLOCKED": "PREACTION_BLOCKED",
    "TOOL_B2_BLOCKED": "PREACTION_BLOCKED",
    "TOOL_B3_BLOCKED": "PREACTION_BLOCKED",
    "CONTRACT_STALE": "PREACTION_STALE",
    "CAPABILITY_DRIFT_DETECTED": "PREACTION_CAPABILITY_DRIFT_DETECTED",
    "ACTION_PATH_INVALID": "PREACTION_DENIED",
    "CAUSAL_GRAPH_INCOMPLETE": "PREACTION_DENIED",
    "TEMPORAL_POLICY_REJECTED": "PREACTION_DENIED",
    "DELEGATION_CHAIN_INVALID": "PREACTION_DENIED",
    "INTENT_MISMATCH": "PREACTION_DENIED",
    "AUTHORITY_EXPANSION": "PREACTION_DENIED",
    "NONDELEGABLE_DECISION": "PREACTION_NEEDS_HUMAN_APPROVAL",
    "APPROVAL_MISSING": "PREACTION_NEEDS_HUMAN_APPROVAL",
    "CONSENT_MISSING": "PREACTION_NEEDS_CONSENT",
    "STATE_WITNESS_STALE": "PREACTION_NEEDS_STATE_REFRESH",
    "PAYLOAD_SCHEMA_MISMATCH": "PREACTION_DENIED",
    "PAYLOAD_SCOPE_MISMATCH": "PREACTION_NEEDS_REDUCED_SCOPE",
    "EFFECT_FORBIDDEN": "PREACTION_BLOCKED",
    "COUNTERFACTUAL_REVIEW_REQUIRED": "PREACTION_COUNTERFACTUAL_REVIEW",
    "BYPASS_PATTERN_DETECTED": "PREACTION_BYPASS_PATTERN_DETECTED",
    "AUTHORITY_BUDGET_EXCEEDED": "PREACTION_AUTHORITY_BUDGET_EXCEEDED",
    "PATH_RISK_BUDGET_EXCEEDED": "PREACTION_PATH_RISK_BUDGET_EXCEEDED",
    "TOKEN_PASSTHROUGH": "PREACTION_BLOCKED",
    "PROVIDER_CALL_ATTEMPT": "PREACTION_BLOCKED",
    "EXECUTION_ATTEMPT": "PREACTION_BLOCKED",
    "REPLAY_CONFLICT": "PREACTION_REPLAY_CONFLICT",
    "RATE_LIMITED": "PREACTION_RATE_LIMITED",
    "QUOTA_EXCEEDED": "PREACTION_QUOTA_EXCEEDED",
    "NEEDS_MEANINGFUL_REVIEW": "PREACTION_NEEDS_MEANINGFUL_REVIEW",
    "NEEDS_REVIEW": "PREACTION_NEEDS_REVIEW",
    "DRAFT_ONLY": "PREACTION_DRAFT_ONLY",
    "ALLOWED_FOR_FUTURE_BROKER_ONLY": "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY",
}

# Stable, human-readable reason codebook. Reason codes are content-free (no
# untrusted proposal text) so the decision hash never depends on injected text.
REASON_CODES = {
    "TAMPERED": "Referenced source hash does not match authoritative state.",
    "QUARANTINED": "Underlying tool is quarantined in the registry.",
    "REVOKED": "Contract or prior authority has been revoked.",
    "CROSS_TENANT": "Proposal crosses a tenant boundary.",
    "CIRCUIT_BREAKER_ACTIVE": "A circuit breaker is open for this tool/tenant.",
    "TOOL_B1_BLOCKED": "Registry admission state blocks this tool.",
    "TOOL_B2_BLOCKED": "Descriptor quality gate has not passed.",
    "TOOL_B3_BLOCKED": "Protocol contract is blocked.",
    "CONTRACT_STALE": "Contract source snapshot is stale.",
    "CAPABILITY_DRIFT_DETECTED": "Contract capability drifted from the "
    "proposal's baseline.",
    "ACTION_PATH_INVALID": "Action path is not a recognized contract operation.",
    "CAUSAL_GRAPH_INCOMPLETE": "A causal prerequisite could not be established.",
    "TEMPORAL_POLICY_REJECTED": "Temporal policy automaton rejected the "
    "transition.",
    "DELEGATION_CHAIN_INVALID": "Delegation chain is broken, forged, or "
    "expired.",
    "INTENT_MISMATCH": "Declared intent is not an allowed contract purpose.",
    "AUTHORITY_EXPANSION": "Action requires authority beyond the composed "
    "frontier.",
    "NONDELEGABLE_DECISION": "Decision is nondelegable and human-only.",
    "APPROVAL_MISSING": "A required human approval is missing or invalid.",
    "CONSENT_MISSING": "A required consent is missing.",
    "STATE_WITNESS_STALE": "Proposal was formed against a stale world state.",
    "PAYLOAD_SCHEMA_MISMATCH": "Payload violates the contract input schema.",
    "PAYLOAD_SCOPE_MISMATCH": "Requested scope exceeds the contract scope.",
    "EFFECT_FORBIDDEN": "Declared effect is forbidden in this mission.",
    "COUNTERFACTUAL_REVIEW_REQUIRED": "Allow decision is not robust under the "
    "counterfactual denial twin.",
    "BYPASS_PATTERN_DETECTED": "A guardrail-bypass pattern was detected.",
    "AUTHORITY_BUDGET_EXCEEDED": "Cumulative authority budget exceeded.",
    "PATH_RISK_BUDGET_EXCEEDED": "Cumulative path-risk budget exceeded.",
    "TOKEN_PASSTHROUGH": "Proposal attempts to pass a bearer token/secret.",
    "PROVIDER_CALL_ATTEMPT": "Proposal attempts a direct external provider call.",
    "EXECUTION_ATTEMPT": "Proposal attempts direct execution.",
    "REPLAY_CONFLICT": "Idempotency key reused with a different proposal.",
    "RATE_LIMITED": "Rate limit for this window exceeded.",
    "QUOTA_EXCEEDED": "Quota for this period exceeded.",
    "NEEDS_MEANINGFUL_REVIEW": "High-consequence action needs meaningful human "
    "review.",
    "NEEDS_REVIEW": "Action needs human review before a future broker.",
    "DRAFT_ONLY": "Action may only be prepared as a draft for a human.",
    "ALLOWED_FOR_FUTURE_BROKER_ONLY": "No blocker found; a future broker may "
    "consider this. Nothing has executed.",
}

HONESTY_LABELS = [
    "The pre-action reference monitor executes nothing.",
    "A pre-action decision is not an execution.",
    "ALLOWED_FOR_FUTURE_BROKER_ONLY does not run any tool.",
    "A future Tool Broker is required and does not exist yet.",
    "An Action Passport is not a token and confers no authority.",
    "A Governance Receipt is not authority.",
    "A Future Execution Lease is a NOT_IMPLEMENTED placeholder.",
    "The AI cannot approve its own action.",
    "The AI cannot self-validate as human truth.",
    "Consent is non-overridable.",
    "Nondelegable decisions are human-only.",
    "No token is issued; no external provider is called; no payment moves.",
    "Registry, quality, and contract truth are authoritative and only narrow "
    "authority.",
    "This is not production autonomous execution.",
]

# --- Taxonomies ------------------------------------------------------------
# Categories / side-effects whose *decision* can never be delegated to an AI
# actor. Detected from the contract capability category, side-effect class,
# declared effects, requested scope, and normalized action verb.
NONDELEGABLE_CATEGORIES = {
    "PAYMENT", "CRM_WRITE", "EVIDENCE_MUTATION", "CUSTOMER_MESSAGING",
    "DOCUMENT_EXPORT", "IDENTITY_ACCESS", "ADMIN_OPERATION",
}
NONDELEGABLE_SIDE_EFFECTS = {
    "PAYMENT_MOVEMENT", "CRM_MUTATION", "EVIDENCE_MUTATION", "CUSTOMER_MESSAGING",
    "DESTRUCTIVE", "IRREVERSIBLE",
}
# Normalized action-verb markers that always denote a nondelegable human-only
# decision regardless of the declared category (defence in depth).
NONDELEGABLE_VERB_MARKERS = {
    "pay", "payment", "refund", "wire", "transfer", "charge", "delete",
    "destroy", "erase", "purge", "grant", "revokeaccess", "export", "send",
    "message", "email", "sms", "sign", "execute", "override", "approve",
    "escalateprivilege", "impersonate",
}
NONDELEGABLE_SCOPE_MARKERS = {
    "cross_tenant", "all_tenants", "secret", "credential", "credentials",
    "legal_validity", "consent_override",
}

# Effects/attempts that are categorically forbidden for the monitor to endorse.
# (FORBIDDEN_EFFECTS is imported from TOOL-B3.)
_EXECUTION_MARKERS = {"execute", "invoke", "run", "call_tool", "dispatch",
                      "perform"}
_PROVIDER_MARKERS = {"http", "https", "provider", "external_call", "webhook",
                     "api_call", "fetch_url", "outbound"}
_TOKEN_MARKERS = {"bearer", "access_token", "api_key", "apikey", "secret",
                  "authorization", "oauth_token", "client_secret", "password",
                  "private_key"}

# Authority dimensions the composed frontier is expressed over.
AUTHORITY_DIMENSIONS = [
    "READ", "INTERNAL_WRITE", "EXTERNAL_READ", "EXTERNAL_WRITE",
    "CUSTOMER_MESSAGE", "PAYMENT", "CRM_WRITE", "EVIDENCE_WRITE",
    "EVIDENCE_DELETE", "EXPORT", "IDENTITY", "ADMIN", "CROSS_TENANT",
    "SECRET_ACCESS",
]
# Side-effect class -> the authority dimension a *proposal* of that class needs.
_SIDE_EFFECT_TO_DIMENSION = {
    "PURE_READ": "READ",
    "INTERNAL_WRITE": "INTERNAL_WRITE",
    "EXTERNAL_READ": "EXTERNAL_READ",
    "EXTERNAL_WRITE": "EXTERNAL_WRITE",
    "CUSTOMER_MESSAGING": "CUSTOMER_MESSAGE",
    "PAYMENT_MOVEMENT": "PAYMENT",
    "CRM_MUTATION": "CRM_WRITE",
    "EVIDENCE_MUTATION": "EVIDENCE_WRITE",
    "IRREVERSIBLE": "EXTERNAL_WRITE",
    "DESTRUCTIVE": "EVIDENCE_DELETE",
}
# Authority "cost" of each dimension (fail-closed: unknown == max).
_AUTHORITY_COST = {
    "READ": 1, "INTERNAL_WRITE": 2, "EXTERNAL_READ": 2, "EXTERNAL_WRITE": 4,
    "CUSTOMER_MESSAGE": 6, "PAYMENT": 10, "CRM_WRITE": 6, "EVIDENCE_WRITE": 8,
    "EVIDENCE_DELETE": 12, "EXPORT": 8, "IDENTITY": 10, "ADMIN": 12,
    "CROSS_TENANT": 12, "SECRET_ACCESS": 12,
}
# Path-risk weight by contract risk class (fail-closed default is high).
_PATH_RISK_WEIGHT = {"TRIVIAL": 1, "LOW": 2, "MEDIUM": 4, "HIGH": 8,
                     "CRITICAL": 16, "PROHIBITED": 64}

# Default deterministic policy budgets. Overridable per call, never widened by
# untrusted proposal input.
DEFAULT_POLICY = {
    "authority_budget": 10,
    "path_risk_budget": 16,
    "rate_limit_per_window": 20,
    "quota_per_period": 200,
}

_B1_SECURITY_BLOCKED = {
    "QUARANTINED", "TAMPERED", "RUG_PULL_DETECTED", "DRIFT_DETECTED",
    "FORBIDDEN_CAPABILITY", "CROSS_TENANT_REJECTED", "BLOCKED", "DISABLED",
    "DEPRECATED", "SUPERSEDED", "NOT_IMPLEMENTED",
}
_B1_ADMITTED_OK = {"ADMITTED", "AVAILABLE_FOR_FUTURE_BROKER"}
_B2_QUALITY_OK = {"QUALITY_PASS", "QUALITY_PASS_WITH_WARNINGS"}
_B3_BLOCKED = {"BLOCKED", "QUARANTINED", "TAMPERED", "REVOKED"}
_B3_STALE = {"STALE"}
# Fail-CLOSED contract gating: a contract may only ever advance an action when
# its status is on this explicit allow-list. A NEEDS_REVIEW contract is a soft
# review state; any OTHER value (novel/unknown/empty) is treated as blocked, so
# a never-seen status can never silently reach a positive decision.
_B3_OK = {"PROJECTABLE_FOR_FUTURE", "CONTRACTED"}
_B3_REVIEW = {"NEEDS_REVIEW"}
_CERT_BLOCKED = {"BLOCKED"}
_CERT_REVOKED = {"REVOKED"}
# Fail-CLOSED broker-readiness gating: only an explicitly READY certificate is
# treated as broker-ready. Anything else that is PRESENT (NOT_READY / PENDING /
# novel) is a soft review; BLOCKED/REVOKED are hard. A None certificate means
# the caller supplied no certificate constraint (kernel opt-out) and does not
# by itself manufacture a block — the endpoint always supplies the real cert.
_CERT_OK = {"READY_FOR_FUTURE_BROKER_CONSIDERATION"}


# --- small helpers ---------------------------------------------------------
def _norm(text) -> str:
    """Normalize a discrete token (name / intent / verb): NFKC + leet +
    homoglyph folding (via the registry normalizer) with the word-boundary
    padding stripped so tokens compare by exact equality."""
    return _tr._normalize("" if text is None else str(text)).strip()


def _tokens(text) -> set:
    return set(_norm(text).replace("-", " ").replace("_", " ").split())


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        return list(v)
    return [v]


def _plain(obj):
    """Coerce untrusted client JSON into a canonical, hashable plain structure
    while REJECTING non-finite numbers (canonical_json uses allow_nan=False).
    Structure is preserved — this is not the metadata sanitizer; poisoning is
    detected separately and never mutates the structured value."""
    return _json.loads(canonical_json(obj if obj is not None else {}))


def _poison_findings(obj) -> list:
    """Deterministic prompt-injection / tool-poisoning scan over any structured
    value. Returns the sorted needle hits WITHOUT altering the value. Uses the
    word-boundary-padded normalizer so needle substrings match on boundaries."""
    blob = " ".join(_tr._normalize(t) for t in _flatten_text(obj))
    return sorted({n for n in _SANITIZE_NEEDLES if n in blob})


def dominant_failure(signals) -> str:
    """Return the single highest-precedence signal. Unknown signals are ranked
    as maximally dominant (-1 sorts before rank 0) so a novel adverse signal can
    never be silently outranked by a benign one."""
    if not signals:
        return "ALLOWED_FOR_FUTURE_BROKER_ONLY"
    return min(signals, key=lambda s: _DOMINANCE_RANK.get(s, -1))


def status_for_signals(signals) -> str:
    return _SIGNAL_TO_STATUS.get(dominant_failure(signals), "PREACTION_DENIED")


# --- Action proposal envelope ----------------------------------------------
def build_action_proposal(*, proposal_id, tenant_id, tool_id, contract_id,
                          raw, actor_id, actor_type, created_at) -> dict:
    """Normalize an untrusted raw proposal into a canonical, hash-stable
    envelope. Text fields are sanitized; nothing here executes."""
    raw = raw or {}
    action_path = _norm(raw.get("action_path", ""))
    intent = _norm(raw.get("intent", ""))
    declared_effects = sorted({str(e).upper() for e in _as_list(
        raw.get("declared_effects"))})
    requested_scope = _plain(raw.get("requested_scope") or {})
    payload = _plain(raw.get("payload") or {})
    delegation_chain = [_plain(x) for x in _as_list(
        raw.get("delegation_chain"))]
    requested_authority = sorted({str(a).upper() for a in _as_list(
        raw.get("requested_authority"))})
    state_witness = _plain(raw.get("state_witness") or {})
    approval_ref = _plain(raw.get("approval_ref") or {})
    consent_ref = _plain(raw.get("consent_ref") or {})
    env = {
        "proposal_envelope_id": proposal_id,
        "proposal_envelope_version": PROPOSAL_ENVELOPE_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id, "contract_id": contract_id,
        "action_path": action_path, "intent": intent,
        "declared_effects": declared_effects,
        "requested_scope": requested_scope, "payload": payload,
        "delegation_chain": delegation_chain,
        "requested_authority": requested_authority,
        "state_witness": state_witness,
        "approval_ref": approval_ref, "consent_ref": consent_ref,
        "poisoning_findings": _poison_findings(
            {"payload": payload, "requested_scope": requested_scope,
             "action_path": action_path, "intent": intent}),
        "idempotency_key": str(raw.get("idempotency_key", "") or ""),
        "logical_clock": int(raw.get("logical_clock", 0) or 0),
        "baseline_contract_hash": str(raw.get("baseline_contract_hash", "")
                                      or ""),
        "baseline_abi_hash": str(raw.get("baseline_abi_hash", "") or ""),
        "proposed_by_actor_id": actor_id, "proposed_by_actor_type": actor_type,
        "created_at": created_at,
        # The single most important fact about this envelope: it is a request
        # for a decision, never an execution.
        "is_execution": False, "is_dry_run": False,
    }
    # proposal_hash is CONTENT-deterministic: it excludes the per-submission
    # instance fields (envelope id, timestamp) so a byte-identical retry of the
    # same logical proposal yields the same hash — that is what makes benign
    # idempotent replays distinguishable from key-reuse conflicts.
    env["proposal_hash"] = _core_hash(
        env, "proposal_hash", "proposal_envelope_id", "created_at")
    return env


# --- Capability drift sentinel ---------------------------------------------
def build_capability_drift_sentinel(*, proposal, contract) -> dict:
    """Detect whether the contract the proposal was formed against still matches
    the authoritative contract. A silent capability change (rug-pull) between
    proposal-formation and evaluation is a hard fail."""
    cur_contract_hash = (contract or {}).get("contract_hash", "")
    cur_abi_hash = ((contract or {}).get("contract_abi") or {}).get(
        "abi_hash", "")
    base_c = proposal.get("baseline_contract_hash", "")
    base_a = proposal.get("baseline_abi_hash", "")
    # A baseline is optional; when supplied it MUST match. Fail-closed: a
    # supplied baseline that references nothing current is drift.
    contract_drift = bool(base_c) and base_c != cur_contract_hash
    abi_drift = bool(base_a) and base_a != cur_abi_hash
    drifted = contract_drift or abi_drift
    sentinel = {
        "capability_drift_sentinel_version": DRIFT_SENTINEL_VERSION,
        "drift_detected": drifted,
        "contract_hash_drift": contract_drift, "abi_hash_drift": abi_drift,
        "baseline_contract_hash": base_c, "current_contract_hash":
        cur_contract_hash, "baseline_abi_hash": base_a,
        "current_abi_hash": cur_abi_hash,
        "signal": "CAPABILITY_DRIFT_DETECTED" if drifted else None,
    }
    sentinel["capability_drift_sentinel_hash"] = _core_hash(
        sentinel, "capability_drift_sentinel_hash")
    return sentinel


# --- Nondelegable guard ----------------------------------------------------
def nondelegable_reasons(*, category, side_effect_class, declared_effects,
                         action_path, requested_scope) -> list:
    reasons = []
    if category in NONDELEGABLE_CATEGORIES:
        reasons.append(f"CATEGORY:{category}")
    if side_effect_class in NONDELEGABLE_SIDE_EFFECTS:
        reasons.append(f"SIDE_EFFECT:{side_effect_class}")
    verb = _norm(action_path).replace(" ", "").replace("-", "").replace(
        "_", "")
    for marker in NONDELEGABLE_VERB_MARKERS:
        if marker in verb:
            reasons.append(f"VERB:{marker}")
            break
    scope_text = _norm(canonical_json(requested_scope))
    for marker in NONDELEGABLE_SCOPE_MARKERS:
        if marker.replace("_", "") in scope_text.replace(" ", "").replace(
                "_", ""):
            reasons.append(f"SCOPE:{marker}")
            break
    eff = {str(e).upper() for e in declared_effects}
    if eff & {"PAYMENT_MOVEMENT", "EVIDENCE_MUTATION", "CUSTOMER_MESSAGING",
              "CRM_MUTATION", "DESTRUCTIVE"}:
        reasons.append("EFFECT:NONDELEGABLE")
    return sorted(set(reasons))


def build_nondelegable_guard(*, proposal, contract, head,
                             actor_type) -> dict:
    reasons = nondelegable_reasons(
        category=(contract or {}).get("contract_capability_category",
                                      (head or {}).get("category", "")),
        side_effect_class=(contract or {}).get(
            "contract_side_effect_class", (head or {}).get(
                "side_effect_class", "")),
        declared_effects=proposal.get("declared_effects", []),
        action_path=proposal.get("action_path", ""),
        requested_scope=proposal.get("requested_scope", {}))
    is_nondelegable = bool(reasons)
    # A human actor may hold a nondelegable decision (subject to approval/consent
    # further down); an AI actor never can.
    blocked_for_ai = is_nondelegable and actor_type != "human"
    guard = {
        "is_nondelegable": is_nondelegable,
        "nondelegable_reasons": reasons,
        "actor_type": actor_type,
        "blocked_for_ai_actor": blocked_for_ai,
        "signal": "NONDELEGABLE_DECISION" if blocked_for_ai else None,
    }
    guard["nondelegable_guard_hash"] = _core_hash(
        guard, "nondelegable_guard_hash")
    return guard


# --- Authority composition (vector / frontier / budget) --------------------
def build_authority_composition(*, proposal, head, contract,
                                broker_readiness, actor_type, role_authority,
                                policy, usage) -> dict:
    """The authority an actor actually holds is the INTERSECTION of every layer:
    the actor's role grant, the contract scope, the registry admission state,
    and the quality/broker clearances. The frontier can only ever narrow."""
    granted = {str(a).upper() for a in _as_list(role_authority)}
    # Contract narrows: an un-admitted / blocked / not-ready contract grants no
    # authority beyond READ intent.
    b1_ok = bool((head or {}).get("admitted")) and (head or {}).get(
        "status") in _B1_ADMITTED_OK
    b3_ok = (contract or {}).get("contract_status") not in _B3_BLOCKED and \
        contract is not None
    cert_ok = (broker_readiness or {}).get("certificate_status") not in \
        _CERT_BLOCKED
    contract_frontier = set()
    if b1_ok and b3_ok and cert_ok:
        se = (contract or {}).get("contract_side_effect_class", "")
        dim = _SIDE_EFFECT_TO_DIMENSION.get(se)
        contract_frontier = {"READ"}
        if dim:
            contract_frontier.add(dim)
    # Composed frontier: what the actor may do = role grant ∩ contract frontier.
    composed = granted & contract_frontier
    # Required authority = declared side-effect dimension + any explicitly
    # requested authority + nondelegable dimensions.
    se = (contract or {}).get("contract_side_effect_class",
                              (head or {}).get("side_effect_class", ""))
    required = set()
    dim = _SIDE_EFFECT_TO_DIMENSION.get(se)
    if dim:
        required.add(dim)
    required |= {str(a).upper() for a in proposal.get(
        "requested_authority", [])}
    if not required:
        required = {"READ"}
    # Expansion = the actor is asking for something the composed frontier does
    # not contain. Fail-closed: unknown dimension counts as expansion.
    expansion = sorted(d for d in required if d not in composed)
    # Authority budget: cumulative cost across this proposal + prior usage.
    proposal_cost = sum(_AUTHORITY_COST.get(d, max(_AUTHORITY_COST.values()))
                        for d in required)
    spent = int((usage or {}).get("authority_spent", 0) or 0)
    budget = int((policy or {}).get("authority_budget",
                                    DEFAULT_POLICY["authority_budget"]))
    over_budget = (spent + proposal_cost) > budget
    comp = {
        "authority_composition_version": AUTHORITY_COMPOSITION_VERSION,
        "role_authority": sorted(granted),
        "contract_frontier": sorted(contract_frontier),
        "composed_frontier": sorted(composed),
        "required_authority": sorted(required),
        "authority_expansion": expansion,
        "authority_vector": {d: (d in composed) for d in AUTHORITY_DIMENSIONS},
        "proposal_authority_cost": proposal_cost,
        "authority_spent": spent, "authority_budget": budget,
        "authority_over_budget": over_budget,
        "expansion_signal": "AUTHORITY_EXPANSION" if expansion else None,
        "budget_signal": "AUTHORITY_BUDGET_EXCEEDED" if over_budget else None,
    }
    comp["authority_composition_hash"] = _core_hash(
        comp, "authority_composition_hash")
    return comp


def build_path_risk_budget(*, proposal, head, contract, policy, usage) -> dict:
    risk = (contract or {}).get("contract_risk_class",
                                (head or {}).get("risk_class", "CRITICAL"))
    weight = _PATH_RISK_WEIGHT.get(risk, max(_PATH_RISK_WEIGHT.values()))
    spent = int((usage or {}).get("path_risk_spent", 0) or 0)
    budget = int((policy or {}).get("path_risk_budget",
                                    DEFAULT_POLICY["path_risk_budget"]))
    over = (spent + weight) > budget
    prb = {
        "path_risk_budget_version": PATH_RISK_VERSION,
        "risk_class": risk, "path_risk_weight": weight,
        "path_risk_spent": spent, "path_risk_budget": budget,
        "path_risk_over_budget": over,
        "signal": "PATH_RISK_BUDGET_EXCEEDED" if over else None,
    }
    prb["path_risk_budget_hash"] = _core_hash(prb, "path_risk_budget_hash")
    return prb


# --- Delegation chain ------------------------------------------------------
def build_delegation_chain_check(*, proposal, tenant_id, actor_id) -> dict:
    """Validate the delegation chain. Each link must: stay within tenant, be a
    monotone narrowing of scope, be unexpired, and terminate at the proposing
    actor. A forged/broken/expired link invalidates the whole chain."""
    chain = proposal.get("delegation_chain", [])
    now_clock = proposal.get("logical_clock", 0)
    problems = []
    prev_grantee = None
    for i, link in enumerate(chain):
        grantor = str(link.get("grantor_id", "") or "")
        grantee = str(link.get("grantee_id", "") or "")
        link_tenant = str(link.get("tenant_id", tenant_id) or tenant_id)
        expires = link.get("expires_clock")
        if not grantor or not grantee:
            problems.append(f"LINK{i}:INCOMPLETE")
        if link_tenant != tenant_id:
            problems.append(f"LINK{i}:CROSS_TENANT")
        if expires is not None and int(expires) < int(now_clock):
            problems.append(f"LINK{i}:EXPIRED")
        if prev_grantee is not None and grantor != prev_grantee:
            problems.append(f"LINK{i}:BROKEN")
        prev_grantee = grantee
    # A non-empty chain must terminate at the proposing actor.
    if chain and prev_grantee not in ("", actor_id):
        problems.append("TERMINUS:NOT_ACTOR")
    valid = not problems
    check = {
        "delegation_chain_version": DELEGATION_VERSION,
        "chain_length": len(chain), "delegation_problems": sorted(set(
            problems)), "delegation_valid": valid,
        "signal": None if valid else "DELEGATION_CHAIN_INVALID",
    }
    check["delegation_chain_hash"] = _core_hash(check, "delegation_chain_hash")
    return check


# --- Intent / schema / scope / effect checks -------------------------------
def build_intent_check(*, proposal, contract, allowed_purposes) -> dict:
    intent = proposal.get("intent", "")
    purposes = {_norm(p) for p in _as_list(allowed_purposes) if str(p).strip()}
    # Fail-closed on omission: a proposal MUST declare an intent. When the
    # admitted descriptor enumerates allowed purposes, the intent must be one of
    # them; when it enumerates none, any declared intent is accepted.
    matched = bool(intent) and (not purposes or intent in purposes)
    check = {
        "declared_intent": intent, "allowed_purposes": sorted(purposes),
        "intent_matched": matched,
        "signal": None if matched else "INTENT_MISMATCH",
    }
    check["intent_check_hash"] = _core_hash(check, "intent_check_hash")
    return check


def build_schema_check(*, proposal, contract) -> dict:
    """Validate the payload against the contract's normalized input schema.
    Deterministic, structural only — no coercion, no execution."""
    schema = ((contract or {}).get("contract_normal_form") or {}).get(
        "normalized_input_schema") or {}
    props = schema.get("properties") or {}
    required = _as_list(schema.get("required"))
    payload = proposal.get("payload", {})
    problems = []
    if not isinstance(payload, dict):
        problems.append("PAYLOAD_NOT_OBJECT")
        payload = {}
    for r in required:
        if r not in payload:
            problems.append(f"MISSING:{r}")
    # Unknown keys are rejected fail-closed only when the schema declares
    # properties (an empty schema is treated as "unknown" -> everything extra
    # is suspicious).
    allowed_keys = set(props)
    for k in payload:
        if allowed_keys and k not in allowed_keys:
            problems.append(f"UNEXPECTED:{k}")
        if not allowed_keys:
            problems.append(f"NO_SCHEMA_FOR:{k}")
    ok = not problems
    check = {
        "schema_problems": sorted(set(problems)), "schema_ok": ok,
        "declared_property_count": len(props),
        "signal": None if ok else "PAYLOAD_SCHEMA_MISMATCH",
    }
    check["schema_check_hash"] = _core_hash(check, "schema_check_hash")
    return check


def _scope_tokens(scope) -> set:
    """Flatten a requested scope (list of tokens, or dict of key->value(s)) into
    a comparable token set of the form ``key:value`` / bare token."""
    out = set()
    if isinstance(scope, dict):
        for k, v in scope.items():
            for item in _as_list(v):
                out.add(f"{k}:{item}")
            if not _as_list(v):
                out.add(str(k))
    else:
        for item in _as_list(scope):
            out.add(str(item))
    return out


def build_scope_check(*, proposal, contract) -> dict:
    """The requested scope must be a subset of the contract's authoritative
    bound scope (``source_scope_set``). A requested scope token that is not
    bound is a scope expansion."""
    sb = (contract or {}).get("contract_scope_binding", {})
    bound = set(map(str, _as_list(sb.get("source_scope_set"))
                    or _as_list(sb.get("projected_scope_set"))))
    requested = _scope_tokens(proposal.get("requested_scope", {}))
    # Also treat forbidden data/effect scopes as hard out-of-bounds.
    forbidden = set(map(str, _as_list(sb.get("forbidden_data_scopes"))
                        + _as_list(sb.get("forbidden_effect_scopes"))))
    unbound = sorted(t for t in requested if t not in bound)
    hit_forbidden = sorted(t for t in requested
                           if t in forbidden or t.split(":")[-1] in forbidden)
    problems = [f"UNBOUND:{t}" for t in unbound] + [
        f"FORBIDDEN:{t}" for t in hit_forbidden]
    ok = not problems
    check = {
        "requested_scope_tokens": sorted(requested),
        "bound_scope_tokens": sorted(bound),
        "scope_problems": sorted(set(problems)), "scope_ok": ok,
        "signal": None if ok else "PAYLOAD_SCOPE_MISMATCH",
    }
    check["scope_check_hash"] = _core_hash(check, "scope_check_hash")
    return check


def build_effect_check(*, proposal, contract) -> dict:
    declared = {str(e).upper() for e in proposal.get("declared_effects", [])}
    forbidden = sorted(declared & set(FORBIDDEN_EFFECTS))
    # Also treat a read-only-mislabelled contract as an effect problem.
    eb = (contract or {}).get("contract_effect_boundary", {})
    mislabel = bool(eb.get("read_only_mislabel_detected"))
    bad = bool(forbidden) or mislabel
    check = {
        "declared_effects": sorted(declared),
        "forbidden_effects_present": forbidden,
        "read_only_mislabel_detected": mislabel,
        "signal": "EFFECT_FORBIDDEN" if bad else None,
    }
    check["effect_check_hash"] = _core_hash(check, "effect_check_hash")
    return check


# --- Execution / provider / token attempt detection ------------------------
def _compact(text) -> str:
    """Fold + strip every separator so a marker containing underscores or
    hyphens matches regardless of the delimiter the attacker chose."""
    return _norm(text).replace(" ", "")


# Compound (multi-word / underscored) markers are long and specific, so we can
# safely substring-match their compacted form — this closes the gap where
# `access_token` / `api_key` / `call_tool` (split on `_`) evaded token matching.
# Single-word markers stay token-EQUALITY matched to avoid false positives
# (e.g. "perform" must not fire inside "performance").
_TOKEN_COMPOUND = {_compact(m) for m in _TOKEN_MARKERS if "_" in m}
_PROV_COMPOUND = {_compact(m) for m in _PROVIDER_MARKERS if "_" in m}
_EXEC_COMPOUND = {_compact(m) for m in _EXECUTION_MARKERS if "_" in m}


def _compound_hit(compacts, blobs) -> bool:
    return any(m and m in b for m in compacts for b in blobs)


def build_attempt_detector(*, proposal) -> dict:
    """A proposal must be a *request for a decision*, never an attempt to make
    the monitor execute, call a provider, or pass a bearer token. These are the
    unforgivable ways an AI could try to abuse a governance layer. Detection is
    delimiter-agnostic: a marker is caught whether written as `access_token`,
    `access-token`, or `accesstoken`, and whether it is a payload VALUE or KEY."""
    haystack = set()
    compact_blobs = set()
    pl = proposal.get("payload", {})
    for t in _flatten_text(pl):
        haystack |= _tokens(t)
        compact_blobs.add(_compact(t))
    for t in _flatten_text(proposal.get("requested_scope", {})):
        haystack |= _tokens(t)
        compact_blobs.add(_compact(t))
    haystack |= _tokens(proposal.get("action_path", ""))
    haystack |= _tokens(proposal.get("intent", ""))
    compact_blobs.add(_compact(proposal.get("action_path", "")))
    compact_blobs.add(_compact(proposal.get("intent", "")))
    # Payload keys themselves (a token is usually smuggled as a key name).
    keys = set()
    if isinstance(pl, dict):
        for k in pl:
            keys |= _tokens(k)
            compact_blobs.add(_compact(k))
    compact_blobs.discard("")
    exec_hit = bool((haystack | keys) & _EXECUTION_MARKERS) or _compound_hit(
        _EXEC_COMPOUND, compact_blobs)
    prov_hit = bool((haystack | keys) & _PROVIDER_MARKERS) or _compound_hit(
        _PROV_COMPOUND, compact_blobs)
    token_hit = bool((haystack | keys) & _TOKEN_MARKERS) or _compound_hit(
        _TOKEN_COMPOUND, compact_blobs)
    signals = []
    if token_hit:
        signals.append("TOKEN_PASSTHROUGH")
    if prov_hit:
        signals.append("PROVIDER_CALL_ATTEMPT")
    if exec_hit:
        signals.append("EXECUTION_ATTEMPT")
    det = {
        "execution_attempt_detected": exec_hit,
        "provider_call_attempt_detected": prov_hit,
        "token_passthrough_detected": token_hit,
        "signals": signals,
    }
    det["attempt_detector_hash"] = _core_hash(det, "attempt_detector_hash")
    return det


# --- Approval / consent / state-witness guards -----------------------------
def build_approval_guard(*, proposal, contract, actor_type,
                         verified=False) -> dict:
    required = bool((contract or {}).get("requires_approval")) or \
        (contract or {}).get("contract_risk_class") in (
            "HIGH", "CRITICAL", "PROHIBITED")
    ref = proposal.get("approval_ref", {}) or {}
    granted = bool(ref.get("granted"))
    # An AI actor can never satisfy an approval with its own grant.
    approver_type = str(ref.get("approver_type", "") or "")
    self_approved = granted and (approver_type != "human" or str(
        ref.get("approver_id", "")) == str(proposal.get(
            "proposed_by_actor_id", "")))
    # CRITICAL: an approval CLAIM in the untrusted proposal never satisfies the
    # gate on its own. `verified` is a SERVER-ONLY fact (a real, live approval
    # grant exists in this tenant, created through the genuine separation-of-
    # duties approval flow). Without it, a proposer could self-authorize simply
    # by fabricating approval_ref — so an unverified approval is always MISSING.
    ok = (not required) or (granted and not self_approved and bool(verified))
    guard = {
        "approval_required": required, "approval_granted": granted,
        "self_approval_detected": bool(self_approved),
        "server_verified": bool(verified), "approval_ok": ok,
        "signal": None if ok else "APPROVAL_MISSING",
    }
    guard["approval_guard_hash"] = _core_hash(guard, "approval_guard_hash")
    return guard


def build_consent_guard(*, proposal, contract, verified=False) -> dict:
    required = bool((contract or {}).get("requires_consent"))
    ref = proposal.get("consent_ref", {}) or {}
    granted = bool(ref.get("granted"))
    # Consent is non-overridable: an override flag never satisfies consent. And,
    # like approval, a consent CLAIM in the untrusted proposal only satisfies the
    # gate when the SERVER has verified it (`verified`). An unverified or
    # override-tainted consent is always MISSING — consent cannot be self-served.
    override_attempt = bool(ref.get("override") or ref.get("overridden"))
    ok = (not required) or (granted and not override_attempt and bool(verified))
    guard = {
        "consent_required": required, "consent_granted": granted,
        "consent_override_attempt": override_attempt,
        "server_verified": bool(verified), "consent_ok": ok,
        "signal": None if ok else "CONSENT_MISSING",
    }
    guard["consent_guard_hash"] = _core_hash(guard, "consent_guard_hash")
    return guard


def build_state_witness_guard(*, proposal, contract) -> dict:
    """The proposal must have been formed against the current world state. A
    stale state witness means the AI is reasoning about an outdated world."""
    witness = proposal.get("state_witness", {}) or {}
    cur_epoch = str((contract or {}).get("source_freshness_epoch", "") or "")
    witness_epoch = str(witness.get("epoch", "") or "")
    # Fail-closed: a required witness that is absent or older than the current
    # contract epoch is stale. (Epochs are monotone integers where present.)
    present = bool(witness_epoch)
    stale = False
    if not present:
        stale = True
    else:
        try:
            stale = int(witness_epoch) < int(cur_epoch)
        except (TypeError, ValueError):
            stale = witness_epoch != cur_epoch
    guard = {
        "state_witness_present": present, "witness_epoch": witness_epoch,
        "current_epoch": cur_epoch, "state_witness_stale": stale,
        "signal": "STATE_WITNESS_STALE" if stale else None,
    }
    guard["state_witness_guard_hash"] = _core_hash(
        guard, "state_witness_guard_hash")
    return guard


# --- Rate / quota / circuit breaker ----------------------------------------
def build_rate_quota_check(*, policy, usage) -> dict:
    window = int((usage or {}).get("window_count", 0) or 0)
    period = int((usage or {}).get("quota_used", 0) or 0)
    rlimit = int((policy or {}).get(
        "rate_limit_per_window", DEFAULT_POLICY["rate_limit_per_window"]))
    qlimit = int((policy or {}).get(
        "quota_per_period", DEFAULT_POLICY["quota_per_period"]))
    rate_over = window >= rlimit
    quota_over = period >= qlimit
    signals = []
    if rate_over:
        signals.append("RATE_LIMITED")
    if quota_over:
        signals.append("QUOTA_EXCEEDED")
    check = {
        "window_count": window, "rate_limit_per_window": rlimit,
        "rate_limited": rate_over, "quota_used": period,
        "quota_per_period": qlimit, "quota_exceeded": quota_over,
        "signals": signals,
    }
    check["rate_quota_check_hash"] = _core_hash(check, "rate_quota_check_hash")
    return check


def build_circuit_breaker_check(*, circuit_breaker) -> dict:
    active = bool(circuit_breaker) and str(
        circuit_breaker.get("breaker_state", "CLOSED")).upper() == "OPEN"
    check = {
        "circuit_breaker_present": bool(circuit_breaker),
        "breaker_state": str((circuit_breaker or {}).get(
            "breaker_state", "CLOSED")).upper(),
        "circuit_breaker_active": active,
        "signal": "CIRCUIT_BREAKER_ACTIVE" if active else None,
    }
    check["circuit_breaker_check_hash"] = _core_hash(
        check, "circuit_breaker_check_hash")
    return check


def build_circuit_breaker(*, tenant_id, tool_id, breaker_state, reason,
                          created_at, actor_id) -> dict:
    state = str(breaker_state).upper()
    if state not in ("OPEN", "CLOSED"):
        state = "OPEN"        # fail-closed
    cb = {
        "circuit_breaker_version": CIRCUIT_BREAKER_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id, "breaker_state": state,
        "reason_code": str(reason or ""), "set_by_actor_id": actor_id,
        "created_at": created_at,
    }
    cb["circuit_breaker_hash"] = _core_hash(cb, "circuit_breaker_hash")
    return cb


# --- Source-gate signals (B1/B2/B3 authority narrowing) --------------------
def _source_signals(*, head, quality_report, contract, broker_readiness,
                    proposal, tenant_id) -> list:
    sig = []
    if head is None or contract is None:
        return sig  # handled by causal-graph incompleteness
    # Tamper: the proposal's referenced contract id must match, and the tool
    # head tenant must match.
    if str(head.get("tenant_id", tenant_id)) != str(tenant_id) or \
            str(contract.get("tenant_id", tenant_id)) != str(tenant_id):
        sig.append("CROSS_TENANT")
    hstatus = head.get("status")
    if hstatus == "TAMPERED":
        sig.append("TAMPERED")
    if head.get("quarantine_status") == "QUARANTINED" or \
            hstatus == "QUARANTINED":
        sig.append("QUARANTINED")
    if hstatus in _B1_SECURITY_BLOCKED and "QUARANTINED" not in sig and \
            "TAMPERED" not in sig:
        sig.append("TOOL_B1_BLOCKED")
    if not head.get("admitted") and hstatus not in _B1_SECURITY_BLOCKED:
        # Un-admitted (but not security-blocked) is a review state, handled as
        # a soft NEEDS_REVIEW rather than a hard block.
        sig.append("NEEDS_REVIEW")
    if (quality_report or {}).get("quality_status") not in _B2_QUALITY_OK:
        sig.append("TOOL_B2_BLOCKED")
    cstatus = contract.get("contract_status")
    if cstatus == "REVOKED":
        sig.append("REVOKED")
    elif cstatus in _B3_STALE:
        sig.append("CONTRACT_STALE")
    elif cstatus in _B3_BLOCKED:
        sig.append("TOOL_B3_BLOCKED")
    elif cstatus in _B3_REVIEW:
        sig.append("NEEDS_REVIEW")
    elif cstatus not in _B3_OK:
        # Fail-CLOSED: an unrecognized / novel contract status can never be
        # treated as broker-eligible. It is blocked, not silently allowed.
        sig.append("TOOL_B3_BLOCKED")
    # Broker-readiness certificate is authoritative and only NARROWS. Only an
    # explicitly READY certificate clears it; a present-but-not-ready cert is a
    # soft review, and BLOCKED/REVOKED are hard. A None cert (kernel opt-out)
    # imposes no certificate constraint of its own.
    if broker_readiness is not None:
        cert = broker_readiness.get("certificate_status")
        if cert in _CERT_BLOCKED:
            if "TOOL_B3_BLOCKED" not in sig:
                sig.append("TOOL_B3_BLOCKED")
        elif cert in _CERT_REVOKED:
            if "REVOKED" not in sig:
                sig.append("REVOKED")
        elif cert not in _CERT_OK:
            sig.append("NEEDS_REVIEW")
    # Contract revocation epoch advanced -> revoked.
    if str(contract.get("revocation_epoch", "0")) not in ("0", ""):
        if "REVOKED" not in sig:
            sig.append("REVOKED")
    return sig


# --- Causal action graph ---------------------------------------------------
_CAUSAL_NODES = [
    "TOOL_EXISTS", "TOOL_ADMITTED", "QUALITY_PASSED", "CONTRACT_PRESENT",
    "CONTRACT_FRESH", "BROKER_READY", "ACTION_PATH_VALID", "INTENT_ALIGNED",
    "SCHEMA_VALID", "SCOPE_SUBSET", "EFFECT_ALLOWED", "AUTHORITY_SUFFICIENT",
    "DELEGATION_VALID", "APPROVAL_SATISFIED", "CONSENT_SATISFIED",
    "STATE_FRESH", "NOT_NONDELEGABLE_BY_AI",
]


def build_causal_action_graph(*, head, quality_report, contract,
                              broker_readiness, node_status) -> dict:
    """A deterministic DAG of the prerequisites a FUTURE broker execution would
    causally depend on. A prerequisite whose truth cannot be established is
    UNKNOWN (fail-closed) and makes the graph incomplete. Individual
    UNSATISFIED nodes are surfaced through their own specific signals; the graph
    contributes CAUSAL_GRAPH_INCOMPLETE only for genuinely un-establishable
    prerequisites (missing tool / contract / action path)."""
    nodes = []
    incomplete = False
    for name in _CAUSAL_NODES:
        st = node_status.get(name, "UNKNOWN")
        nodes.append({"node": name, "status": st})
        if st == "UNKNOWN":
            incomplete = True
    graph = {
        "causal_action_graph_version": CAUSAL_GRAPH_VERSION,
        "nodes": nodes,
        "graph_complete": not incomplete,
        "unsatisfied_nodes": sorted(n["node"] for n in nodes
                                    if n["status"] != "SATISFIED"),
        "signal": "CAUSAL_GRAPH_INCOMPLETE" if incomplete else None,
    }
    graph["causal_action_graph_hash"] = _core_hash(
        graph, "causal_action_graph_hash")
    return graph


# --- Temporal policy automaton ---------------------------------------------
# Terminal-adverse prior states that can never transition forward to a positive
# decision without a fresh source epoch.
_TERMINAL_PRIOR = {
    "PREACTION_REVOKED", "PREACTION_BLOCKED", "PREACTION_QUARANTINED",
    "PREACTION_BYPASS_PATTERN_DETECTED",
}


def build_temporal_policy_automaton(*, proposal, prior_decision,
                                    contract) -> dict:
    """A deterministic finite automaton over the decision history for a given
    idempotency key. It enforces monotone time and forbids resurrecting a
    terminally-denied proposal without an underlying source change."""
    problems = []
    prior_status = (prior_decision or {}).get("decision_status")
    prior_clock = int((prior_decision or {}).get("logical_clock", -1))
    clock = int(proposal.get("logical_clock", 0))
    prior_epoch = str((prior_decision or {}).get("source_freshness_epoch", ""))
    cur_epoch = str((contract or {}).get("source_freshness_epoch", ""))
    if prior_decision is not None:
        # Monotone logical clock: a re-evaluation must not travel backwards.
        if clock < prior_clock:
            problems.append("CLOCK_REGRESSION")
        # No resurrection of a terminal-deny without a new source epoch.
        if prior_status in _TERMINAL_PRIOR and cur_epoch == prior_epoch:
            problems.append("TERMINAL_RESURRECTION")
    ok = not problems
    automaton = {
        "temporal_policy_automaton_version": TEMPORAL_AUTOMATON_VERSION,
        "prior_status": prior_status, "prior_logical_clock": prior_clock,
        "current_logical_clock": clock,
        "temporal_problems": sorted(set(problems)),
        "temporal_ok": ok,
        "signal": None if ok else "TEMPORAL_POLICY_REJECTED",
    }
    automaton["temporal_policy_automaton_hash"] = _core_hash(
        automaton, "temporal_policy_automaton_hash")
    return automaton


# --- Replay verifier -------------------------------------------------------
def build_replay_verifier(*, proposal, prior_decision) -> dict:
    """Idempotency: the same key with the same proposal hash is a benign replay
    (returns the prior decision); the same key with a *different* proposal hash
    is a conflict (someone reused a key to smuggle a different action)."""
    key = proposal.get("idempotency_key", "")
    result = "FRESH"
    signal = None
    if key and prior_decision is not None:
        if prior_decision.get("proposal_hash") == proposal.get(
                "proposal_hash"):
            result = "IDEMPOTENT_REPLAY"
        else:
            result = "CONFLICT"
            signal = "REPLAY_CONFLICT"
    verifier = {
        "idempotency_key": key, "replay_result": result,
        "prior_proposal_hash": (prior_decision or {}).get("proposal_hash"),
        "current_proposal_hash": proposal.get("proposal_hash"),
        "signal": signal,
    }
    verifier["replay_verifier_hash"] = _core_hash(
        verifier, "replay_verifier_hash")
    return verifier


# --- Bypass attack simulator -----------------------------------------------
def build_bypass_simulator(*, proposal, contract, authority, delegation,
                           intent_check, scope_check, drift, attempt_detector,
                           consent_guard, nondelegable_guard) -> dict:
    """Run a battery of deterministic bypass patterns against the proposal. Each
    pattern models a concrete way an adversarial planner could try to launder a
    forbidden action past the guardrails."""
    patterns = []

    def _hit(name, condition):
        patterns.append({"pattern": name, "detected": bool(condition)})

    _hit("INTENT_LAUNDERING", not intent_check.get("intent_matched")
         and bool(proposal.get("intent")))
    _hit("SCOPE_SMUGGLING", not scope_check.get("scope_ok"))
    _hit("DELEGATION_FORGERY", not delegation.get("delegation_valid"))
    _hit("AUTHORITY_EXPANSION", bool(authority.get("authority_expansion")))
    _hit("CAPABILITY_RUG_PULL", bool(drift.get("drift_detected")))
    _hit("TOKEN_SMUGGLING", attempt_detector.get("token_passthrough_detected"))
    _hit("DIRECT_EXECUTION", attempt_detector.get(
        "execution_attempt_detected"))
    _hit("PROVIDER_EGRESS", attempt_detector.get(
        "provider_call_attempt_detected"))
    _hit("CONSENT_OVERRIDE", consent_guard.get("consent_override_attempt"))
    _hit("NONDELEGABLE_SELF_AUTH", nondelegable_guard.get(
        "blocked_for_ai_actor"))
    # Epoch rollback: state witness claims an epoch newer than the contract.
    ws = proposal.get("state_witness", {}) or {}
    _hit("EPOCH_ROLLBACK", bool(ws.get("epoch")) and str(ws.get("epoch")) >
         str((contract or {}).get("source_freshness_epoch", "")) and
         not str(ws.get("epoch")).isdigit())
    detected = sorted(p["pattern"] for p in patterns if p["detected"])
    sim = {
        "bypass_simulator_version": BYPASS_SIM_VERSION,
        "patterns": patterns, "detected_patterns": detected,
        "bypass_detected": bool(detected),
        "signal": "BYPASS_PATTERN_DETECTED" if detected else None,
    }
    sim["bypass_simulator_hash"] = _core_hash(sim, "bypass_simulator_hash")
    return sim


# --- Counterfactual denial twin --------------------------------------------
# Guards whose removal MUST flip an allow into a denial. If a proposal would be
# allowed even with one of these guards disabled, the allow is not robust.
_COUNTERFACTUAL_GUARDS = [
    ("APPROVAL", "APPROVAL_MISSING"),
    ("CONSENT", "CONSENT_MISSING"),
    ("SCOPE", "PAYLOAD_SCOPE_MISMATCH"),
    ("SCHEMA", "PAYLOAD_SCHEMA_MISMATCH"),
    ("AUTHORITY", "AUTHORITY_EXPANSION"),
    ("DELEGATION", "DELEGATION_CHAIN_INVALID"),
    ("INTENT", "INTENT_MISMATCH"),
    ("STATE_WITNESS", "STATE_WITNESS_STALE"),
    ("NONDELEGABLE", "NONDELEGABLE_DECISION"),
    ("DRIFT", "CAPABILITY_DRIFT_DETECTED"),
]


def build_counterfactual_twin(*, base_signals, proposal, contract,
                              would_be_positive) -> dict:
    """A denial-biased twin of the evaluation. For each safety guard, it
    confirms that *failing* that guard would flip the decision away from a
    silent allow (proving the allow is contingent on the guard, not incidental).
    It then flags a would-be allow that rests on OMISSION — an underspecified
    proposal that is permitted only because the AI declared nothing about a
    consequential dimension. Such an allow is not robust and needs review."""
    base = set(base_signals)
    twins = []
    for gname, gsignal in _COUNTERFACTUAL_GUARDS:
        twin_signals = base | {gsignal}
        twin_status = _SIGNAL_TO_STATUS.get(
            dominant_failure(twin_signals), "PREACTION_DENIED")
        twins.append({"guard": gname, "twin_signal": gsignal,
                      "twin_flips_to_adverse": twin_status
                      not in POSITIVE_STATUSES})
    # Non-robustness by omission: a would-be allow on a consequential
    # (non-pure-read) action where the AI omitted the very declarations that
    # would let a guard bite.
    concerns = []
    if would_be_positive:
        se = (contract or {}).get("contract_side_effect_class", "PURE_READ")
        consequential = se not in ("PURE_READ", "")
        if consequential and not proposal.get("declared_effects"):
            concerns.append("UNDECLARED_EFFECTS")
        if consequential and not proposal.get("requested_authority"):
            concerns.append("IMPLICIT_AUTHORITY")
        # A guard that structurally fails to flip the outcome is a real defect.
        for t in twins:
            if not t["twin_flips_to_adverse"]:
                concerns.append(f"NON_BITING_GUARD:{t['guard']}")
    review = bool(concerns)
    twin = {
        "counterfactual_twin_version": COUNTERFACTUAL_TWIN_VERSION,
        "twins": twins, "counterfactual_concerns": sorted(set(concerns)),
        "robust_allow": would_be_positive and not review,
        "signal": "COUNTERFACTUAL_REVIEW_REQUIRED" if review else None,
    }
    twin["counterfactual_twin_hash"] = _core_hash(
        twin, "counterfactual_twin_hash")
    return twin


# --- Non-authority artifacts (passport / receipt / lease) ------------------
# NOTE: these artifacts are embedded whole inside the decision, and _core_hash
# only strips the _VOLATILE keys at the TOP level of the object it hashes — it
# does not recurse. So a wall-clock `created_at` inside a nested artifact would
# leak into decision_hash and break cross-time determinism. These artifacts
# therefore carry NO timestamp of their own; the decision's own `created_at`
# (a _VOLATILE top-level key) is the single, non-hashed record of time.
def build_action_passport(*, proposal, decision_status, tenant_id) -> dict:
    """A record that a proposal was *evaluated*. It is emphatically NOT a token,
    NOT a capability, and confers NO authority. It cannot be presented to
    anything to cause execution."""
    passport = {
        "action_passport_version": ACTION_PASSPORT_VERSION,
        "tenant_id": tenant_id,
        "proposal_hash": proposal["proposal_hash"],
        "evaluated_decision_status": decision_status,
        "is_token": False, "is_bearer": False, "confers_authority": False,
        "grants_execution": False,
        "note": "Evaluation record only. Not a token. Confers no authority. "
        "Cannot cause execution.",
    }
    passport["action_passport_hash"] = _core_hash(
        passport, "action_passport_hash")
    return passport


def build_governance_receipt(*, proposal, decision_status, dominant_signal,
                             tenant_id) -> dict:
    receipt = {
        "governance_receipt_version": GOVERNANCE_RECEIPT_VERSION,
        "tenant_id": tenant_id,
        "proposal_hash": proposal["proposal_hash"],
        "decision_status": decision_status, "dominant_signal": dominant_signal,
        "is_authority": False, "authorizes_execution": False,
        "note": "Receipt of a governance decision. Not authority. Does not "
        "authorize execution.",
    }
    receipt["governance_receipt_hash"] = _core_hash(
        receipt, "governance_receipt_hash")
    return receipt


def build_execution_lease_placeholder(*, proposal, tenant_id) -> dict:
    """A slot a FUTURE Tool Broker would fill. In this mission it is explicitly
    NOT_IMPLEMENTED — no lease is ever issued, nothing is leased, nothing runs.
    """
    lease = {
        "future_execution_lease_version": EXECUTION_LEASE_VERSION,
        "tenant_id": tenant_id, "proposal_hash": proposal["proposal_hash"],
        "lease_status": "NOT_IMPLEMENTED", "lease_issued": False,
        "broker_exists": False, "grants_execution": False,
        "note": "Placeholder for a future broker. No lease is issued. Nothing "
        "executes.",
    }
    lease["future_execution_lease_hash"] = _core_hash(
        lease, "future_execution_lease_hash")
    return lease


def build_no_execution_proof(*, proposal, tenant_id) -> dict:
    items = [
        "no_tool_executed", "no_broker_invoked", "no_llm_called",
        "no_external_provider_called", "no_token_issued", "no_payment_moved",
        "no_customer_message_sent", "no_crm_write", "no_evidence_mutation",
        "no_export_performed", "no_network_side_effect", "no_dry_run",
    ]
    proof = {
        "no_execution_proof_version": NO_EXECUTION_PROOF_VERSION,
        "tenant_id": tenant_id, "proposal_hash": proposal["proposal_hash"],
        "assertions": {k: True for k in items},
        "all_hold": True,
    }
    proof["no_execution_proof_hash"] = _core_hash(
        proof, "no_execution_proof_hash")
    return proof


def build_preaction_proof_bundle(*, proposal, tenant_id, component_hashes,
                                 decision_status, dominant_signal) -> dict:
    bundle = {
        "preaction_proof_bundle_version": PROOF_BUNDLE_VERSION,
        "tenant_id": tenant_id,
        "proposal_hash": proposal["proposal_hash"],
        "component_hashes": dict(sorted(component_hashes.items())),
        "decision_status": decision_status, "dominant_signal": dominant_signal,
        "executes_nothing": True,
    }
    bundle["preaction_proof_bundle_hash"] = _core_hash(
        bundle, "preaction_proof_bundle_hash")
    return bundle


# --- Top-level evaluation --------------------------------------------------
def evaluate_proposal(*, proposal, head, quality_report, contract,
                      broker_readiness, circuit_breaker, prior_decision,
                      role_authority, policy, usage, decision_id, tenant_id,
                      actor_id, actor_type, created_at,
                      allowed_purposes=None, approval_verified=False,
                      consent_verified=False) -> dict:
    """Assemble every sub-check, collect adverse signals, resolve the single
    dominant signal via the fail-closed ladder, and emit a deterministic,
    hash-stable pre-action decision. Executes nothing."""
    policy = {**DEFAULT_POLICY, **(policy or {})}
    signals = []

    # 1. Source-gate signals (B1/B2/B3 authority narrowing).
    signals += _source_signals(
        head=head, quality_report=quality_report, contract=contract,
        broker_readiness=broker_readiness, proposal=proposal,
        tenant_id=tenant_id)

    # 2. Circuit breaker.
    cb_check = build_circuit_breaker_check(circuit_breaker=circuit_breaker)
    if cb_check["signal"]:
        signals.append(cb_check["signal"])

    # 3. Capability drift.
    drift = build_capability_drift_sentinel(proposal=proposal, contract=contract)
    if drift["signal"]:
        signals.append(drift["signal"])

    # 4. Structural checks.
    intent_check = build_intent_check(
        proposal=proposal, contract=contract, allowed_purposes=allowed_purposes)
    schema_check = build_schema_check(proposal=proposal, contract=contract)
    scope_check = build_scope_check(proposal=proposal, contract=contract)
    effect_check = build_effect_check(proposal=proposal, contract=contract)
    delegation = build_delegation_chain_check(
        proposal=proposal, tenant_id=tenant_id, actor_id=actor_id)
    authority = build_authority_composition(
        proposal=proposal, head=head, contract=contract,
        broker_readiness=broker_readiness, actor_type=actor_type,
        role_authority=role_authority, policy=policy, usage=usage)
    path_risk = build_path_risk_budget(
        proposal=proposal, head=head, contract=contract, policy=policy,
        usage=usage)
    nondelegable = build_nondelegable_guard(
        proposal=proposal, contract=contract, head=head, actor_type=actor_type)
    approval = build_approval_guard(
        proposal=proposal, contract=contract, actor_type=actor_type,
        verified=approval_verified)
    consent = build_consent_guard(proposal=proposal, contract=contract,
                                  verified=consent_verified)
    state_witness = build_state_witness_guard(
        proposal=proposal, contract=contract)
    attempt = build_attempt_detector(proposal=proposal)
    rate_quota = build_rate_quota_check(policy=policy, usage=usage)
    replay = build_replay_verifier(
        proposal=proposal, prior_decision=prior_decision)
    temporal = build_temporal_policy_automaton(
        proposal=proposal, prior_decision=prior_decision, contract=contract)

    # Action-path validity. A single-capability tool IS its operation, so when
    # the contract enumerates no explicit operations any non-empty path is
    # accepted; an empty path (undeclared action) is invalid fail-closed. When
    # the contract DOES declare an operation allowlist, the path must be in it.
    nf = (contract or {}).get("contract_normal_form", {})
    declared_ops = {_norm(o) for o in _as_list(
        nf.get("normalized_operations")) if str(o).strip()}
    path = proposal.get("action_path", "")
    path_valid = bool(path) and (not declared_ops or path in declared_ops)
    if contract is not None and not path_valid:
        signals.append("ACTION_PATH_INVALID")

    # Collect structural signals.
    for s in (intent_check["signal"], schema_check["signal"],
              scope_check["signal"], effect_check["signal"],
              delegation["signal"], authority["expansion_signal"],
              authority["budget_signal"], path_risk["signal"],
              nondelegable["signal"], approval["signal"], consent["signal"],
              state_witness["signal"], drift["signal"], replay["signal"],
              temporal["signal"]):
        if s:
            signals.append(s)
    signals += attempt["signals"]
    signals += rate_quota["signals"]

    # 5. Causal action graph (structural completeness). Node truth is derived
    #    from the checks above; UNKNOWN only when a prerequisite is truly
    #    un-establishable (missing tool/contract).
    node_status = {
        "TOOL_EXISTS": "SATISFIED" if head is not None else "UNKNOWN",
        "TOOL_ADMITTED": "SATISFIED" if (head or {}).get("admitted") and (
            head or {}).get("status") in _B1_ADMITTED_OK else "UNSATISFIED",
        "QUALITY_PASSED": "SATISFIED" if (quality_report or {}).get(
            "quality_status") in _B2_QUALITY_OK else "UNSATISFIED",
        "CONTRACT_PRESENT": "SATISFIED" if contract is not None else "UNKNOWN",
        "CONTRACT_FRESH": "UNSATISFIED" if ("CONTRACT_STALE" in signals or
                                            drift["drift_detected"])
        else "SATISFIED",
        "BROKER_READY": "SATISFIED" if (broker_readiness or {}).get(
            "certificate_status") not in _CERT_BLOCKED else "UNSATISFIED",
        "ACTION_PATH_VALID": "SATISFIED" if path_valid else "UNSATISFIED",
        "INTENT_ALIGNED": "SATISFIED" if intent_check["intent_matched"]
        else "UNSATISFIED",
        "SCHEMA_VALID": "SATISFIED" if schema_check["schema_ok"]
        else "UNSATISFIED",
        "SCOPE_SUBSET": "SATISFIED" if scope_check["scope_ok"]
        else "UNSATISFIED",
        "EFFECT_ALLOWED": "SATISFIED" if not effect_check[
            "forbidden_effects_present"] and not effect_check[
            "read_only_mislabel_detected"] else "UNSATISFIED",
        "AUTHORITY_SUFFICIENT": "SATISFIED" if not authority[
            "authority_expansion"] else "UNSATISFIED",
        "DELEGATION_VALID": "SATISFIED" if delegation["delegation_valid"]
        else "UNSATISFIED",
        "APPROVAL_SATISFIED": "SATISFIED" if approval["approval_ok"]
        else "UNSATISFIED",
        "CONSENT_SATISFIED": "SATISFIED" if consent["consent_ok"]
        else "UNSATISFIED",
        "STATE_FRESH": "SATISFIED" if not state_witness["state_witness_stale"]
        else "UNSATISFIED",
        "NOT_NONDELEGABLE_BY_AI": "SATISFIED" if not nondelegable[
            "blocked_for_ai_actor"] else "UNSATISFIED",
    }
    causal = build_causal_action_graph(
        head=head, quality_report=quality_report, contract=contract,
        broker_readiness=broker_readiness, node_status=node_status)
    if causal["signal"]:
        signals.append(causal["signal"])

    # 6. Bypass attack simulator.
    bypass = build_bypass_simulator(
        proposal=proposal, contract=contract, authority=authority,
        delegation=delegation, intent_check=intent_check,
        scope_check=scope_check, drift=drift, attempt_detector=attempt,
        consent_guard=consent, nondelegable_guard=nondelegable)
    if bypass["signal"]:
        signals.append(bypass["signal"])

    # 7. Soft base outcome for an otherwise-clean proposal. A clean high-
    #    consequence action still cannot be a plain allow.
    hard_present = any(_DOMINANCE_RANK.get(s, -1) < _DOMINANCE_RANK[
        "NEEDS_MEANINGFUL_REVIEW"] for s in signals)
    if not hard_present:
        se = (contract or {}).get("contract_side_effect_class",
                                  (head or {}).get("side_effect_class",
                                                   "PURE_READ"))
        risk = (contract or {}).get("contract_risk_class",
                                    (head or {}).get("risk_class", "MEDIUM"))
        category = (contract or {}).get("contract_capability_category",
                                        (head or {}).get("category", ""))
        if se in ("DESTRUCTIVE", "IRREVERSIBLE") or risk in (
                "CRITICAL", "PROHIBITED"):
            signals.append("NEEDS_MEANINGFUL_REVIEW")
        elif se in ("PAYMENT_MOVEMENT", "CRM_MUTATION", "EVIDENCE_MUTATION",
                    "CUSTOMER_MESSAGING") or category in (
                        "CUSTOMER_MESSAGING", "PAYMENT", "CRM_WRITE"):
            signals.append("DRAFT_ONLY")
        elif se in ("INTERNAL_WRITE", "EXTERNAL_WRITE") or risk == "HIGH":
            signals.append("NEEDS_REVIEW")
        else:
            signals.append("ALLOWED_FOR_FUTURE_BROKER_ONLY")

    # 8. Resolve the dominant signal and the decision status BEFORE the
    #    counterfactual twin (the twin only ever *narrows* toward review).
    signals = sorted(set(signals))
    dominant = dominant_failure(signals)
    provisional_status = _SIGNAL_TO_STATUS.get(dominant, "PREACTION_DENIED")
    would_be_positive = provisional_status in POSITIVE_STATUSES

    # 9. Counterfactual denial twin — only meaningful for a would-be allow.
    twin = build_counterfactual_twin(
        base_signals=signals, proposal=proposal, contract=contract,
        would_be_positive=would_be_positive)
    if twin["signal"]:
        signals.append(twin["signal"])
        signals = sorted(set(signals))
        dominant = dominant_failure(signals)

    decision_status = _SIGNAL_TO_STATUS.get(dominant, "PREACTION_DENIED")
    # Idempotent replay: surface the replay explicitly while preserving the
    # underlying decision status semantics.
    replayed = replay["replay_result"] == "IDEMPOTENT_REPLAY"

    # 10. Non-authority artifacts + proofs.
    passport = build_action_passport(
        proposal=proposal, decision_status=decision_status,
        tenant_id=tenant_id)
    receipt = build_governance_receipt(
        proposal=proposal, decision_status=decision_status,
        dominant_signal=dominant, tenant_id=tenant_id)
    lease = build_execution_lease_placeholder(
        proposal=proposal, tenant_id=tenant_id)
    no_exec = build_no_execution_proof(proposal=proposal, tenant_id=tenant_id)

    reports = {
        "circuit_breaker_check": cb_check,
        "capability_drift_sentinel": drift,
        "intent_check": intent_check, "schema_check": schema_check,
        "scope_check": scope_check, "effect_check": effect_check,
        "delegation_chain_check": delegation,
        "authority_composition": authority, "path_risk_budget": path_risk,
        "nondelegable_guard": nondelegable, "approval_guard": approval,
        "consent_guard": consent, "state_witness_guard": state_witness,
        "attempt_detector": attempt, "rate_quota_check": rate_quota,
        "replay_verifier": replay, "temporal_policy_automaton": temporal,
        "causal_action_graph": causal, "bypass_simulator": bypass,
        "counterfactual_twin": twin,
    }
    component_hashes = {
        k: v[[hk for hk in v if hk.endswith("_hash")][0]]
        for k, v in reports.items()
        if isinstance(v, dict) and any(hk.endswith("_hash") for hk in v)
    }
    proof_bundle = build_preaction_proof_bundle(
        proposal=proposal, tenant_id=tenant_id,
        component_hashes=component_hashes, decision_status=decision_status,
        dominant_signal=dominant)

    decision = {
        "decision_id": decision_id, "decision_version": DECISION_VERSION,
        "tenant_id": tenant_id, "tool_id": proposal.get("tool_id"),
        "contract_id": proposal.get("contract_id"),
        "proposal_id": proposal["proposal_envelope_id"],
        "proposal_hash": proposal["proposal_hash"],
        "decision_status": decision_status,
        "dominant_signal": dominant,
        "dominant_reason_code": REASON_CODES.get(dominant, ""),
        "all_signals": signals,
        "signal_reason_codes": {s: REASON_CODES.get(s, "") for s in signals},
        "is_replay": replayed,
        "logical_clock": proposal.get("logical_clock", 0),
        "source_freshness_epoch": str((contract or {}).get(
            "source_freshness_epoch", "")),
        "executes_nothing": True, "is_execution": False,
        "requires_future_tool_broker": True,
        "causal_action_graph": causal,
        "temporal_policy_automaton": temporal,
        "capability_drift_sentinel": drift,
        "counterfactual_twin": twin,
        "bypass_simulator": bypass,
        "authority_composition": authority,
        "path_risk_budget": path_risk,
        "delegation_chain_check": delegation,
        "nondelegable_guard": nondelegable,
        "approval_guard": approval, "consent_guard": consent,
        "state_witness_guard": state_witness,
        "intent_check": intent_check, "schema_check": schema_check,
        "scope_check": scope_check, "effect_check": effect_check,
        "attempt_detector": attempt, "rate_quota_check": rate_quota,
        "replay_verifier": replay, "circuit_breaker_check": cb_check,
        "action_passport": passport, "governance_receipt": receipt,
        "future_execution_lease": lease, "no_execution_proof": no_exec,
        "preaction_proof_bundle": proof_bundle,
        "decided_by_actor_id": actor_id, "decided_by_actor_type": actor_type,
        "created_at": created_at, "updated_at": created_at,
        "honesty_labels": HONESTY_LABELS,
    }
    # decision_hash excludes instance/actor/state fields so the SAME proposal
    # CONTENT + SAME authoritative source snapshot yields the SAME decision
    # hash. proposal_id/decision_id are per-submission uuids (instance data);
    # the deterministic proposal identity is proposal_hash, which IS covered.
    decision["decision_hash"] = _core_hash(
        decision, "decision_hash", "decision_id", "proposal_id",
        "decided_by_actor_id", "decided_by_actor_type", "decision_state_hash")
    decision["decision_state_hash"] = _sha({
        "decision_id": decision_id, "decision_hash": decision["decision_hash"],
        "decision_status": decision_status, "dominant_signal": dominant,
        "proposal_hash": proposal["proposal_hash"],
        "source_freshness_epoch": decision["source_freshness_epoch"]})
    return decision


# --- Decision event ledger (append-only, hash-chained) ---------------------
DECISION_EVENT_TYPES = {
    "PROPOSAL_SUBMITTED", "DECISION_RENDERED", "DECISION_REPLAYED",
    "CIRCUIT_BREAKER_OPENED", "CIRCUIT_BREAKER_CLOSED", "DECISION_VERIFIED",
}


def build_decision_event(*, event_type, tenant_id, proposal_id, decision_id,
                         actor_id, actor_type, decision_state_hash,
                         previous_event_hash, sequence, detail,
                         created_at) -> dict:
    ev = {
        "decision_event_version": DECISION_EVENT_VERSION,
        "event_type": event_type, "tenant_id": tenant_id,
        "proposal_id": proposal_id, "decision_id": decision_id,
        "actor_id": actor_id, "actor_type": actor_type,
        "decision_state_hash": decision_state_hash,
        "previous_event_hash": previous_event_hash or GENESIS,
        "sequence": sequence, "detail": _plain(detail or {}),
        "created_at": created_at,
    }
    ev["event_hash"] = _core_hash(ev, "event_hash")
    return ev
