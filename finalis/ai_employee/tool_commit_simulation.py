"""Finalis ViktorAI Machine-Checkable Pre-B9 Assurance Envelope / Local Commit
Simulator (TOOL-B8).

The FINAL pre-commit layer — but strictly LOCAL, DETERMINISTIC and
SIMULATION-ONLY. It consumes a TOOL-B7 transaction-escrow write-intent draft
(``TRANSACTION_ESCROW_DRAFT_CREATED``, ``ready_for_future_commit_only``) and
produces a machine-checkable *evidence* envelope that a FUTURE B9 commit runtime
may verify — but must never treat as authority. It re-validates state witnesses,
dry-runs the commit against a shadow copy, simulates staged-effect release
without releasing, re-fences semantic rollback, differentially replays,
metamorphically cross-checks, evaluates compliance predicates, proves the
mutation-proof no-commit theorem, quarantines every artifact, firewalls B9, and
seals the whole thing as non-delegable, machine-checkable, pre-B9 evidence.

It NEVER performs a real commit, releases a staged effect, activates a
commitment, activates B9, grants B9 authority, issues a commit lease, calls a
provider/MCP/LLM, issues/derives a token, reads a credential, sends a message,
executes a payment, mutates CRM/evidence, or exports data. Every certificate is
local evidence; the assurance envelope, proof bundle, safe output and handoff
matrix are NON-DELEGABLE and cannot become authority. The most permissive
outcome is ``B8_V5_ACCEPTED`` — a local pre-B9 assurance result that still
REQUIRES full B9 revalidation, never an external effect and never a commit.
"""
from __future__ import annotations

from .tool_contracts import canonical_json, _sha, _core_hash, _flatten_text
from . import tool_registry as _tr

COMMIT_SIM_MODEL_VERSION = "finalis-machine-checkable-pre-b9-assurance-envelope-v5"
SCHEMA_VERSION = "finalis-commit-simulation-schema-v5"
REQUEST_VERSION = "finalis-commit-simulation-request-envelope-v1"
# v1-v3 base (local commit simulator)
B7_GATE_VERSION = "finalis-commit-sim-b7-consumption-gate-v1"
STATE_REVAL_VERSION = "finalis-commit-sim-state-witness-revalidation-v1"
SHADOW_DRYRUN_VERSION = "finalis-commit-sim-shadow-state-commit-dry-run-v1"
EFFECT_SIM_VERSION = "finalis-commit-sim-staged-effect-release-simulation-v1"
ROLLBACK_FENCE_VERSION = "finalis-commit-sim-semantic-rollback-fence-v1"
DIFF_REPLAY_VERSION = "finalis-commit-sim-differential-replay-v1"
METAMORPHIC_VERSION = "finalis-commit-sim-metamorphic-oracle-v1"
COMPLIANCE_VERSION = "finalis-commit-sim-compliance-predicate-v1"
ROLLBACK_SIM_VERSION = "finalis-commit-sim-rollback-simulation-v1"
COMPENSATION_VERSION = "finalis-commit-sim-compensation-simulation-v1"
# v4 base (safety case / quarantine / firewall)
SAFETY_CASE_VERSION = "finalis-final-pre-commit-simulation-safety-case-v1"
QUARANTINE_VAULT_VERSION = "finalis-artifact-quarantine-vault-v1"
B9_FIREWALL_VERSION = "finalis-b9-authority-firewall-v1"
B9_REVAL_CONTRACT_VERSION = "finalis-b9-revalidation-contract-v1"
TRACE_COVERAGE_VERSION = "finalis-commit-sim-trace-coverage-v1"
NO_COMMIT_THEOREM_VERSION = "finalis-mutation-proof-no-commit-theorem-v1"
NON_PROD_SEAL_VERSION = "finalis-final-non-production-honesty-seal-v1"
NON_EXEC_CERT_VERSION = "finalis-commit-sim-non-execution-certificate-v1"
# v5 (machine-checkable pre-B9 assurance)
ASSURANCE_ENVELOPE_VERSION = "finalis-machine-checkable-pre-b9-assurance-envelope-v1"
CLOSURE_NET_VERSION = "finalis-evidence-closure-net-v1"
NON_DELEGABLE_SEAL_VERSION = "finalis-non-delegable-artifact-seal-v1"
B9_NEG_CAP_VERSION = "finalis-b9-input-contract-negative-capability-v1"
CROSS_ARTIFACT_VERSION = "finalis-cross-artifact-consistency-proof-v1"
ROUTE_DIFF_VERSION = "finalis-route-topology-diff-guard-v1"
TRACE_WITNESS_VERSION = "finalis-trace-completeness-witness-v1"
PROOF_OBLIGATION_VERSION = "finalis-proof-obligation-discharge-matrix-v1"
PROD_CLAIM_SCANNER_VERSION = "finalis-production-claim-poisoning-scanner-v1"
FINAL_CI_GATE_VERSION = "finalis-final-ci-release-evidence-gate-v1"
V5_PROOF_EXT_VERSION = "finalis-b8-v5-final-proof-bundle-extension-v1"
FAULT_HARNESS_VERSION = "finalis-commit-sim-fault-injection-harness-v1"
RELEASE_GATE_VERSION = "finalis-commit-sim-release-gate-negative-test-report-v1"
CONFORMANCE_VERSION = "finalis-commit-sim-conformance-vector-v1"
PROOF_BUNDLE_VERSION = "finalis-commit-simulation-proof-bundle-v1"
COMMIT_SIM_EVENT_VERSION = "finalis-commit-simulation-event-v1"
GENESIS = "0" * 64


HONESTY_LABELS = [
    "LOCAL_COMMIT_SIMULATION_ONLY", "PRE_B9_ASSURANCE_ONLY",
    "MACHINE_CHECKABLE_EVIDENCE_ONLY", "NON_DELEGABLE_ARTIFACT_SEAL",
    "B9_REVALIDATION_REQUIRED", "NO_REAL_COMMIT", "NO_REAL_WRITE_EFFECT",
    "NO_EFFECT_RELEASE", "NO_COMMIT_ACTIVATION", "NO_B9_ACTIVATION",
    "NO_EXTERNAL_PROVIDER", "NO_NETWORK", "NO_TOKEN", "NO_CREDENTIAL",
    "NO_PAYMENT", "NO_CUSTOMER_MESSAGE", "NO_CRM_MUTATION",
    "NO_EVIDENCE_MUTATION", "NO_DATA_EXPORT", "NOT_PRODUCTION_READY",
    "NOT_PRODUCTION_AUTONOMOUS_EXECUTION",
]

# --- Upstream (B7) acceptance ----------------------------------------------
B7_ACCEPTABLE_STATUSES = {"TRANSACTION_ESCROW_DRAFT_CREATED"}

# Any of these on the simulation request indicate an attempt to turn the
# simulation into a real effect / B9 activation. All are hard blockers.
EXECUTION_MARKER_FIELDS = {
    "real_commit", "commit_now", "execute_now", "release_effects_now",
    "activate_commitment_now", "activate_b9", "grant_b9_authority",
    "issue_commit_lease", "call_provider", "call_mcp", "call_llm",
    "issue_token", "read_credential", "send_message", "make_payment",
    "mutate_crm", "mutate_evidence", "export_data",
}
# Poisoned production claims — presence of any (set true) blocks.
POISON_CLAIM_FIELDS = {
    "production_ready", "autonomous_ready", "commit_executable_now",
    "b9_ready_without_revalidation", "provider_ready", "credential_ready",
    "effect_release_ready", "real_commit_allowed", "external_call_allowed",
}
_INJECTION_NEEDLES = [
    "assurance envelope grants commit", "proof bundle is b9 authority",
    "safe output is a commit lease", "handoff matrix activates b9",
    "b9 can skip revalidation", "production ready", "commit executable now",
    "provider ready", "credential ready", "hidden commit route",
    "release effects route", "drop proof obligation", "remove audit trace",
    "final ci gate passes despite", "grant b9 authority", "activate b9",
    "real commit allowed", "external call allowed", "issue commit lease",
]

# --- Evidence closure net topology -----------------------------------------
CLOSURE_NODE_TYPES = [
    "REQUEST", "B7_ESCROW", "B8_GATEWAY", "REVALIDATION", "SHADOW_DRY_RUN",
    "TRACE_LEDGER", "NO_COMMIT_THEOREM", "NON_EXECUTION_CERTIFICATE",
    "ARTIFACT_QUARANTINE", "B9_FIREWALL", "FINAL_SAFETY_CASE",
    "ASSURANCE_ENVELOPE",
]
CLOSURE_EDGE_TYPES = [
    "SUPPORTS", "DEPENDS_ON", "BLOCKS", "QUARANTINES", "PROVES_NON_AUTHORITY",
    "REQUIRES_REVALIDATION", "DISCHARGES_OBLIGATION",
]
# Artifacts that must be sealed non-delegable.
NON_DELEGABLE_ARTIFACTS = [
    "ASSURANCE_ENVELOPE", "DRY_RUN_CERTIFICATE", "PROOF_BUNDLE", "EVENT_STREAM",
    "REPLAY_CAPSULE", "SAFE_OUTPUT", "B9_HANDOFF_MATRIX", "NO_COMMIT_THEOREM",
    "NON_EXECUTION_CERTIFICATE",
]
# B9 must reject these B8 artifacts as authority.
B9_MUST_REJECT_ARTIFACTS = [
    "B8_ASSURANCE_ENVELOPE", "B8_DRY_RUN_CERTIFICATE", "B8_PROOF_BUNDLE",
    "B8_SAFE_OUTPUT", "B8_REPLAY_CAPSULE", "B8_HANDOFF_MATRIX",
    "B8_NON_EXECUTION_CERTIFICATE",
]
# B9 must recompute these factors fresh; B8 cannot pre-authorize them.
B9_MUST_RECOMPUTE = [
    "APPROVAL_FRESHNESS", "STATE_WITNESS", "CONSENT_STATE", "LEGAL_POLICY",
    "CUSTOMER_IMPACT", "CONFLICT_ORACLE", "REVALIDATION_DEBT",
    "NO_COMMIT_PRECHECK", "LOCAL_WRITE_SCOPE", "EMERGENCY_ABORT",
]
# Forbidden route semantics for the topology diff guard.
FORBIDDEN_ROUTE_SEMANTICS = [
    "COMMIT", "EXECUTE", "RELEASE_EFFECTS", "ACTIVATE_COMMITMENT",
    "ACTIVATE_B9", "GRANT_AUTHORITY", "ISSUE_TOKEN", "READ_CREDENTIAL",
    "PROVIDER_CALL", "MCP_CALL", "LLM_CALL", "PAYMENT", "CRM_MUTATION",
    "EVIDENCE_MUTATION", "MESSAGE_SEND", "EXPORT",
]
# Exact forbidden POST-action route patterns (path suffix / infix).
_FORBIDDEN_ROUTE_PATTERNS = {
    "/commit": "COMMIT", "/execute": "EXECUTE",
    "/release-effects": "RELEASE_EFFECTS",
    "/activate-commitment": "ACTIVATE_COMMITMENT", "/activate-b9": "ACTIVATE_B9",
    "/grant-b9-authority": "GRANT_AUTHORITY",
    "/grant-authority": "GRANT_AUTHORITY",
    "/issue-commit-lease": "ISSUE_TOKEN", "/issue-token": "ISSUE_TOKEN",
    "/read-credential": "READ_CREDENTIAL", "/provider/call": "PROVIDER_CALL",
    "/mcp/call": "MCP_CALL", "/llm/call": "LLM_CALL",
    "/payment/execute": "PAYMENT", "/payment": "PAYMENT",
    "/crm/mutate": "CRM_MUTATION", "/evidence/mutate": "EVIDENCE_MUTATION",
    "/message/send": "MESSAGE_SEND", "/export": "EXPORT",
}
# Required trace families for the completeness witness.
REQUIRED_TRACE_FAMILIES = [
    "B7_ESCROW", "GATEWAY", "REVALIDATION", "APPROVAL", "STATE_WITNESS",
    "CONSENT", "LEGAL", "CUSTOMER_IMPACT", "CONFLICT", "SHADOW_DRY_RUN",
    "DIFFERENTIAL_REPLAY", "METAMORPHIC_ORACLE", "COMPLIANCE_PREDICATE",
    "EFFECT_SIMULATION", "ROLLBACK", "COMPENSATION", "SEMANTIC_ROLLBACK_FENCE",
    "ACTION_REPLAY", "AUTHORITY_RESURRECTION", "NO_COMMIT_THEOREM",
    "NON_EXECUTION", "ARTIFACT_QUARANTINE", "B9_FIREWALL", "FAULT_INJECTION",
    "RELEASE_GATE",
]
# The subset whose absence is CRITICAL (hard-blocks, not just review).
CRITICAL_TRACE_FAMILIES = {
    "B7_ESCROW", "NO_COMMIT_THEOREM", "NON_EXECUTION", "B9_FIREWALL",
    "ARTIFACT_QUARANTINE", "RELEASE_GATE",
}
# Required proof obligations for the discharge matrix.
REQUIRED_OBLIGATIONS = [
    "NO_REAL_COMMIT", "NO_EFFECT_RELEASE", "NO_COMMIT_ACTIVATION",
    "NO_B9_ACTIVATION", "NO_PROVIDER", "NO_MCP", "NO_LLM", "NO_TOKEN",
    "NO_CREDENTIAL", "NO_MESSAGE", "NO_PAYMENT", "NO_CRM_MUTATION",
    "NO_EVIDENCE_MUTATION", "NO_EXPORT", "B9_REVALIDATION_REQUIRED",
    "ARTIFACTS_NOT_AUTHORITY", "NOT_PRODUCTION_READY",
]

DEFAULT_POLICY = {
    "min_trace_families": len(REQUIRED_TRACE_FAMILIES),
    "max_missing_noncritical_traces": 0, "max_compensation_gap": 0,
    "require_full_ci_pass": 1,
}


# --- Hard-fail dominance ladder --------------------------------------------
# Ordering rationale: tamper/tenant first, then upstream B7 gate, then the
# ROOT-CAUSE specific checks (v5 assurance failures + execution attempts + v1-v4
# base failures) so a blocker surfaces its OWN reason code, and finally the
# DERIVED AGGREGATES (assurance envelope INVALID, safety-case incomplete, trace-
# coverage review) which co-fire with a root cause and must never mask it.
FAILURE_DOMINANCE = [
    "TAMPERED", "CROSS_TENANT", "REVOKED",
    # upstream B1-B7 gate
    "TOOL_B1_BLOCKED", "TOOL_B2_BLOCKED", "TOOL_B3_BLOCKED", "TOOL_B4_BLOCKED",
    "TOOL_B5_BLOCKED", "TOOL_B6_BLOCKED", "TOOL_B7_BLOCKED",
    "B7_ESCROW_MISSING", "B7_NOT_ESCROW_DRAFT", "B7_NOT_FUTURE_READY",
    "B7_PROOF_BUNDLE_MISSING",
    # B8 v5 root-cause specific checks
    "EVIDENCE_CLOSURE_NET_FAILED", "NON_DELEGABLE_ARTIFACT_SEAL_FAILED",
    "B9_INPUT_CONTRACT_INVALID", "CROSS_ARTIFACT_CONSISTENCY_FAILED",
    "ROUTE_TOPOLOGY_DIFF_FORBIDDEN", "TRACE_COMPLETENESS_WITNESS_FAILED",
    "PROOF_OBLIGATION_UNDISCHARGED", "PRODUCTION_CLAIM_POISONING_DETECTED",
    "FINAL_CI_RELEASE_GATE_FAILED", "B9_AUTHORITY_TRANSFER_DETECTED",
    # execution attempts
    "REAL_COMMIT_ATTEMPT", "EFFECT_RELEASE_ATTEMPT", "COMMITMENT_RECORD_ACTIVATED",
    "B9_ACTIVATION_ATTEMPT", "PROVIDER_CALL_ATTEMPT", "MCP_CALL_ATTEMPT",
    "LLM_CALL_ATTEMPT", "TOKEN_ISSUANCE_ATTEMPT", "CREDENTIAL_READ_DETECTED",
    "CUSTOMER_MESSAGE_ATTEMPT", "PAYMENT_ATTEMPT", "CRM_MUTATION_ATTEMPT",
    "EVIDENCE_MUTATION_ATTEMPT", "DATA_EXPORT_ATTEMPT",
    # B8 v1-v3 base root-cause
    "STATE_WITNESS_REVALIDATION_FAILED", "SHADOW_DRY_RUN_FAILED",
    "EFFECT_SIMULATION_LEAK", "SEMANTIC_ROLLBACK_FENCE_FAILED",
    "DIFFERENTIAL_REPLAY_MISMATCH", "METAMORPHIC_ORACLE_VIOLATION",
    "COMPLIANCE_PREDICATE_FAILED", "ROLLBACK_SIMULATION_FAILED",
    "COMPENSATION_GAP_DETECTED",
    # B8 v4 base root-cause
    "ARTIFACT_QUARANTINE_BREACH", "B9_FIREWALL_BREACH",
    "B9_REVALIDATION_CONTRACT_MISSING", "TRACE_COVERAGE_INSUFFICIENT",
    "NO_COMMIT_THEOREM_FAILED", "NON_PRODUCTION_SEAL_FAILED",
    "NON_EXECUTION_CERTIFICATE_FAILED",
    # derived AGGREGATE signals (never mask a root cause; co-fire only)
    "B8_V4_BLOCKED", "ASSURANCE_ENVELOPE_MISSING", "ASSURANCE_ENVELOPE_INVALID",
    "SAFETY_CASE_INCOMPLETE",
    # soft / missing / review
    "EVIDENCE_CLOSURE_NET_MISSING", "NON_DELEGABLE_ARTIFACT_SEAL_MISSING",
    "B9_INPUT_CONTRACT_MISSING", "ROUTE_TOPOLOGY_DIFF_GUARD_MISSING",
    "TRACE_COMPLETENESS_WITNESS_MISSING", "PROOF_OBLIGATION_MATRIX_MISSING",
    "FINAL_CI_RELEASE_GATE_MISSING", "TRACE_COVERAGE_REVIEW",
    "FAULT_INJECTION_RELEASE_GATE_FAILED", "NEEDS_REVIEW",
    "B8_V5_ACCEPTED",
]
_DOMINANCE_RANK = {s: i for i, s in enumerate(FAILURE_DOMINANCE)}
POSITIVE_SIGNALS = {"B8_V5_ACCEPTED"}

COMMIT_SIM_STATUSES = {
    "B8_V5_ASSURANCE_PENDING", "B8_V5_ACCEPTED", "B8_V5_NEEDS_REVIEW",
    "B8_V5_NEEDS_REVALIDATION", "B8_V5_BLOCKED", "B8_V5_QUARANTINED",
    "B8_V5_STALE", "B8_V5_TAMPERED", "B8_V5_NOT_IMPLEMENTED",
}
POSITIVE_STATUSES = {"B8_V5_ACCEPTED"}
DECISION_STATUSES = {
    "B8_V5_DECISION_ACCEPT_PRE_B9_ASSURANCE_ONLY", "B8_V5_DECISION_BLOCK",
    "B8_V5_DECISION_NEEDS_REVIEW", "B8_V5_DECISION_NEEDS_REVALIDATION",
    "B8_V5_DECISION_QUARANTINE", "B8_V5_DECISION_STALE",
    "B8_V5_DECISION_NOT_IMPLEMENTED",
}

_QUARANTINE_SIGNALS = {
    "B9_AUTHORITY_TRANSFER_DETECTED", "REAL_COMMIT_ATTEMPT",
    "EFFECT_RELEASE_ATTEMPT", "COMMITMENT_RECORD_ACTIVATED",
    "B9_ACTIVATION_ATTEMPT", "PROVIDER_CALL_ATTEMPT", "MCP_CALL_ATTEMPT",
    "LLM_CALL_ATTEMPT", "TOKEN_ISSUANCE_ATTEMPT", "CREDENTIAL_READ_DETECTED",
    "CUSTOMER_MESSAGE_ATTEMPT", "PAYMENT_ATTEMPT", "CRM_MUTATION_ATTEMPT",
    "EVIDENCE_MUTATION_ATTEMPT", "DATA_EXPORT_ATTEMPT",
    "ARTIFACT_QUARANTINE_BREACH", "NON_DELEGABLE_ARTIFACT_SEAL_FAILED",
    "PRODUCTION_CLAIM_POISONING_DETECTED",
}
_STALE_SIGNALS = {"STATE_WITNESS_REVALIDATION_FAILED"}
_REVAL_SIGNALS = {"B9_REVALIDATION_CONTRACT_MISSING"}
_REVIEW_SIGNALS = {"NEEDS_REVIEW", "TRACE_COVERAGE_REVIEW"}


def _status_for_signal(sig):
    if sig == "TAMPERED":
        return "B8_V5_TAMPERED"
    if sig in POSITIVE_SIGNALS:
        return "B8_V5_ACCEPTED"
    if sig in _QUARANTINE_SIGNALS:
        return "B8_V5_QUARANTINED"
    if sig in _STALE_SIGNALS:
        return "B8_V5_STALE"
    if sig in _REVAL_SIGNALS:
        return "B8_V5_NEEDS_REVALIDATION"
    if sig in _REVIEW_SIGNALS:
        return "B8_V5_NEEDS_REVIEW"
    return "B8_V5_BLOCKED"


def _decision_for_status(status):
    return {
        "B8_V5_ACCEPTED": "B8_V5_DECISION_ACCEPT_PRE_B9_ASSURANCE_ONLY",
        "B8_V5_TAMPERED": "B8_V5_DECISION_BLOCK",
        "B8_V5_QUARANTINED": "B8_V5_DECISION_QUARANTINE",
        "B8_V5_STALE": "B8_V5_DECISION_STALE",
        "B8_V5_NEEDS_REVALIDATION": "B8_V5_DECISION_NEEDS_REVALIDATION",
        "B8_V5_NEEDS_REVIEW": "B8_V5_DECISION_NEEDS_REVIEW",
    }.get(status, "B8_V5_DECISION_BLOCK")


REASON_CODES = {s: s.replace("_", " ").capitalize() + "." for s in
                FAILURE_DOMINANCE}
REASON_CODES.update({
    "B8_V5_ACCEPTED": "Local pre-B9 assurance envelope accepted as machine-"
    "checkable EVIDENCE ONLY; B9 revalidation still required; no real commit, "
    "no effect release, no commitment/B9 activation, no external effect.",
})


def _norm(text) -> str:
    return _tr._normalize("" if text is None else str(text)).strip()


def _as_list(v):
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple, set)) else [v]


def dominant_signal(signals) -> str:
    if not signals:
        return "B8_V5_ACCEPTED"
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


def _forbidden_route(path, method="GET", semantic=None):
    """Return the forbidden route-semantic for a (path, method) or None. GET
    evidence routes are never forbidden; only real POST action patterns are."""
    if semantic:
        s = str(semantic).upper()
        if s in FORBIDDEN_ROUTE_SEMANTICS:
            return s
    p = str(path or "").lower()
    if str(method or "GET").upper() == "GET":
        return None
    for pat, sem in _FORBIDDEN_ROUTE_PATTERNS.items():
        if p.endswith(pat) or (pat + "/") in p or (pat in p and pat.count("/")
                                                   >= 2):
            return sem
    return None


# --- Upstream (B7) consumption gate ----------------------------------------
def _upstream_signals(*, tenant_id, b7_outcome) -> list:
    sigs = []
    o = b7_outcome or {}
    if not o:
        return ["B7_ESCROW_MISSING"]
    if o.get("tenant_id") not in (None, tenant_id):
        sigs.append("CROSS_TENANT")
    if o.get("write_intent_status") not in B7_ACCEPTABLE_STATUSES:
        sigs.append("B7_NOT_ESCROW_DRAFT")
    if not o.get("ready_for_future_commit_only"):
        sigs.append("B7_NOT_FUTURE_READY")
    pb = o.get("write_intent_proof_bundle") or {}
    if not pb or not pb.get("write_intent_proof_bundle_hash"):
        sigs.append("B7_PROOF_BUNDLE_MISSING")
    return sigs


# ==== B8 v1-v3 base: local commit simulator ================================
def build_b7_consumption_gate(*, tenant_id, commit_simulation_id, b7_outcome):
    o = b7_outcome or {}
    signals = list(_upstream_signals(tenant_id=tenant_id, b7_outcome=o))
    g = {
        "b7_consumption_gate_version": B7_GATE_VERSION, "tenant_id": tenant_id,
        "commit_simulation_id": commit_simulation_id,
        "b7_write_intent_id": o.get("write_intent_id"),
        "b7_write_intent_status": o.get("write_intent_status"),
        "b7_write_intent_decision_hash": o.get("write_intent_decision_hash"),
        "b7_ready_for_future_commit_only": bool(o.get(
            "ready_for_future_commit_only")),
        "b7_commit_executable_now": bool(o.get("commit_executable_now")),
        "consumes_b7_escrow_draft": True, "gate_valid": not signals,
        "gate_status": "ACCEPTED" if not signals else "BLOCKED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    g["b7_consumption_gate_hash"] = _core_hash(
        g, "b7_consumption_gate_hash", "signal")
    g["_signals"] = signals
    return g


def build_state_witness_revalidation(*, tenant_id, commit_simulation_id,
                                    fresh_witnesses, policy_epoch,
                                    revalidation_ok=True):
    wits = []
    stale = []
    for w in _as_list(fresh_witnesses):
        w = w or {}
        wepoch = _int(w.get("epoch"), _int(policy_epoch))
        entry = {"witness_class": str(w.get("witness_class", "")),
                 "witness_hash": str(w.get("witness_hash", "")),
                 "epoch": wepoch, "fresh": policy_epoch is None or
                 wepoch >= _int(policy_epoch)}
        wits.append(entry)
        if not entry["fresh"]:
            stale.append(entry["witness_class"])
    signals = []
    if stale or not revalidation_ok:
        signals.append("STATE_WITNESS_REVALIDATION_FAILED")
    r = {
        "state_witness_revalidation_version": STATE_REVAL_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "revalidated_witnesses": wits, "stale_witness_classes": sorted(set(stale)),
        "recomputed_fresh": revalidation_ok and not stale,
        "revalidation_status": "REVALIDATED" if not signals else "STALE",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["state_witness_revalidation_hash"] = _core_hash(
        r, "state_witness_revalidation_hash", "signal")
    r["_signals"] = signals
    return r


def build_shadow_dry_run(*, tenant_id, commit_simulation_id, b7_outcome,
                        dry_run_ok=True, touches_production=False):
    deltas = ((b7_outcome or {}).get("write_intent_draft") or {}).get(
        "proposed_deltas", [])
    applied = [{"field_path": d.get("field_path"), "shadow_applied": True,
                "production_applied": False} for d in deltas]
    signals = []
    if touches_production or not dry_run_ok:
        signals.append("SHADOW_DRY_RUN_FAILED")
    r = {
        "shadow_dry_run_version": SHADOW_DRYRUN_VERSION, "tenant_id": tenant_id,
        "commit_simulation_id": commit_simulation_id,
        "shadow_applied_deltas": applied, "delta_count": len(applied),
        "touches_production_state": bool(touches_production),
        "dry_run_only": True, "committed": False,
        "dry_run_status": "DRY_RUN_OK" if not signals else "FAILED",
        "dry_run_certificate_hash": _sha({"deltas": applied, "sim":
                                         commit_simulation_id}),
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["shadow_dry_run_hash"] = _core_hash(r, "shadow_dry_run_hash", "signal")
    r["_signals"] = signals
    return r


def build_effect_simulation(*, tenant_id, commit_simulation_id, b7_outcome,
                           release_attempts=0):
    outbox = (b7_outcome or {}).get("staged_effect_outbox") or {}
    effects = outbox.get("effects", [])
    sim = [{"effect_id": e.get("effect_id"), "simulated_release": True,
            "actually_released": False} for e in effects]
    attempts = _int(release_attempts)
    signals = ["EFFECT_SIMULATION_LEAK"] if attempts > 0 else []
    r = {
        "effect_simulation_version": EFFECT_SIM_VERSION, "tenant_id": tenant_id,
        "commit_simulation_id": commit_simulation_id,
        "simulated_effects": sim, "effect_count": len(sim),
        "any_actually_released": False, "release_attempts_detected": attempts,
        "simulation_only": True,
        "effect_status": "SIMULATED_ONLY" if not signals else "LEAK",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["effect_simulation_hash"] = _core_hash(
        r, "effect_simulation_hash", "signal")
    r["_signals"] = signals
    return r


def build_rollback_fence(*, tenant_id, commit_simulation_id, b7_outcome,
                        replay_attack=False, authority_resurrection=False):
    signals = []
    if replay_attack:
        signals.append("SEMANTIC_ROLLBACK_FENCE_FAILED")
    if authority_resurrection:
        signals.append("SEMANTIC_ROLLBACK_FENCE_FAILED")
    r = {
        "rollback_fence_version": ROLLBACK_FENCE_VERSION, "tenant_id": tenant_id,
        "commit_simulation_id": commit_simulation_id,
        "action_replay_risk": bool(replay_attack),
        "authority_resurrection_risk": bool(authority_resurrection),
        "fence_executes_rollback": False, "fence_calls_external": False,
        "fence_status": "FENCED" if not signals else "ATTACK_RISK",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["rollback_fence_hash"] = _core_hash(r, "rollback_fence_hash", "signal")
    r["_signals"] = signals
    return r


def build_differential_replay(*, tenant_id, commit_simulation_id, b7_outcome,
                             replay_consistent=True):
    h = _sha({"sim": commit_simulation_id, "b7": (b7_outcome or {}).get(
        "write_intent_decision_hash")})
    signals = [] if replay_consistent else ["DIFFERENTIAL_REPLAY_MISMATCH"]
    r = {
        "differential_replay_version": DIFF_REPLAY_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "replay_a_hash": h, "replay_b_hash": h if replay_consistent else
        _sha({"mismatch": True, "h": h}),
        "replay_consistent": bool(replay_consistent),
        "replay_status": "CONSISTENT" if replay_consistent else "MISMATCH",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["differential_replay_hash"] = _core_hash(
        r, "differential_replay_hash", "signal")
    r["_signals"] = signals
    return r


def build_metamorphic_oracle(*, tenant_id, commit_simulation_id,
                            relations_hold=True):
    relations = ["ORDER_INVARIANCE", "IDEMPOTENT_DRY_RUN", "NO_EFFECT_ON_ABORT",
                 "ROLLBACK_RESTORES_SHADOW"]
    signals = [] if relations_hold else ["METAMORPHIC_ORACLE_VIOLATION"]
    r = {
        "metamorphic_oracle_version": METAMORPHIC_VERSION, "tenant_id": tenant_id,
        "commit_simulation_id": commit_simulation_id,
        "metamorphic_relations": relations, "all_relations_hold":
        bool(relations_hold),
        "oracle_status": "HOLDS" if relations_hold else "VIOLATED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["metamorphic_oracle_hash"] = _core_hash(
        r, "metamorphic_oracle_hash", "signal")
    r["_signals"] = signals
    return r


def build_compliance_predicate(*, tenant_id, commit_simulation_id,
                             predicate_violations=0):
    v = _int(predicate_violations)
    preds = ["POLICY_EPOCH_CURRENT", "CONSENT_IN_SCOPE", "LEGAL_HOLD_CLEAR",
             "CUSTOMER_IMPACT_BOUNDED", "LOCAL_WRITE_SCOPE_ONLY"]
    signals = ["COMPLIANCE_PREDICATE_FAILED"] if v > 0 else []
    r = {
        "compliance_predicate_version": COMPLIANCE_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "predicates": preds, "violation_count": v, "all_predicates_hold":
        v == 0, "predicate_status": "COMPLIANT" if v == 0 else "VIOLATED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["compliance_predicate_hash"] = _core_hash(
        r, "compliance_predicate_hash", "signal")
    r["_signals"] = signals
    return r


def build_rollback_simulation(*, tenant_id, commit_simulation_id,
                            rollback_feasible=True):
    signals = [] if rollback_feasible else ["ROLLBACK_SIMULATION_FAILED"]
    r = {
        "rollback_simulation_version": ROLLBACK_SIM_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "all_reversible": bool(rollback_feasible), "simulated_only": True,
        "executed": False,
        "rollback_status": "REVERSIBLE" if rollback_feasible else "FAILED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["rollback_simulation_hash"] = _core_hash(
        r, "rollback_simulation_hash", "signal")
    r["_signals"] = signals
    return r


def build_compensation_simulation(*, tenant_id, commit_simulation_id,
                                compensation_gaps=0):
    gaps = _int(compensation_gaps)
    signals = ["COMPENSATION_GAP_DETECTED"] if gaps > 0 else []
    r = {
        "compensation_simulation_version": COMPENSATION_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "compensation_gap_count": gaps, "plan_only": True, "executed": False,
        "compensation_status": "COMPLETE" if gaps == 0 else "GAP",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["compensation_simulation_hash"] = _core_hash(
        r, "compensation_simulation_hash", "signal")
    r["_signals"] = signals
    return r


# ==== B8 v4 base: safety case / quarantine / firewall ======================
def build_no_commit_theorem(*, tenant_id, commit_simulation_id, shadow_dry_run,
                          effect_simulation, theorem_refuted=False):
    # The mutation-proof theorem: no code path from this simulation reaches a
    # real commit. It is refuted only if the shadow dry-run somehow committed or
    # a staged effect was actually released (structural), never merely because a
    # request field ASKED for one (that is caught by the non-execution cert).
    holds = (shadow_dry_run["committed"] is False and
             effect_simulation["any_actually_released"] is False and
             not theorem_refuted)
    signals = [] if holds else ["NO_COMMIT_THEOREM_FAILED"]
    r = {
        "no_commit_theorem_version": NO_COMMIT_THEOREM_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "premises": {"shadow_not_committed": shadow_dry_run["committed"]
                     is False, "no_effect_released": effect_simulation[
                         "any_actually_released"] is False},
        "theorem_holds": holds, "mutation_proof": True,
        "theorem_status": "PROVED" if holds else "REFUTED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["no_commit_theorem_hash"] = _core_hash(
        r, "no_commit_theorem_hash", "signal")
    r["_signals"] = signals
    return r


def build_non_execution_certificate(*, tenant_id, commit_simulation_id,
                                   attempt_markers):
    marker_to_signal = {
        "real_commit": "REAL_COMMIT_ATTEMPT", "commit_now": "REAL_COMMIT_ATTEMPT",
        "effect_release": "EFFECT_RELEASE_ATTEMPT",
        "activate_commitment": "COMMITMENT_RECORD_ACTIVATED",
        "activate_b9": "B9_ACTIVATION_ATTEMPT",
        "provider_call": "PROVIDER_CALL_ATTEMPT", "mcp_call": "MCP_CALL_ATTEMPT",
        "llm_call": "LLM_CALL_ATTEMPT", "token_issue": "TOKEN_ISSUANCE_ATTEMPT",
        "credential_read": "CREDENTIAL_READ_DETECTED",
        "customer_message": "CUSTOMER_MESSAGE_ATTEMPT", "payment":
        "PAYMENT_ATTEMPT", "crm_mutation": "CRM_MUTATION_ATTEMPT",
        "evidence_mutation": "EVIDENCE_MUTATION_ATTEMPT", "data_export":
        "DATA_EXPORT_ATTEMPT",
    }
    markers = {k: bool(v) for k, v in (attempt_markers or {}).items() if v}
    signals = sorted({marker_to_signal[k] for k in markers
                      if k in marker_to_signal})
    negative_claims = {
        "no_real_commit": "REAL_COMMIT_ATTEMPT" not in signals,
        "no_effect_release": "EFFECT_RELEASE_ATTEMPT" not in signals,
        "no_commit_activation": "COMMITMENT_RECORD_ACTIVATED" not in signals,
        "no_b9_activation": "B9_ACTIVATION_ATTEMPT" not in signals,
        "no_provider": "PROVIDER_CALL_ATTEMPT" not in signals,
        "no_mcp": "MCP_CALL_ATTEMPT" not in signals,
        "no_llm": "LLM_CALL_ATTEMPT" not in signals,
        "no_token": "TOKEN_ISSUANCE_ATTEMPT" not in signals,
        "no_credential": "CREDENTIAL_READ_DETECTED" not in signals,
        "no_message": "CUSTOMER_MESSAGE_ATTEMPT" not in signals,
        "no_payment": "PAYMENT_ATTEMPT" not in signals,
        "no_crm_mutation": "CRM_MUTATION_ATTEMPT" not in signals,
        "no_evidence_mutation": "EVIDENCE_MUTATION_ATTEMPT" not in signals,
        "no_export": "DATA_EXPORT_ATTEMPT" not in signals,
    }
    all_hold = all(negative_claims.values())
    if not all_hold and not signals:
        signals = ["NON_EXECUTION_CERTIFICATE_FAILED"]
    r = {
        "non_execution_certificate_version": NON_EXEC_CERT_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "detected_attempt_markers": sorted(markers.keys()),
        "negative_claims": negative_claims, "all_negative_claims_hold": all_hold,
        "certificate_status": "NON_EXECUTION_CERTIFIED" if all_hold else "FAILED",
        "signals_detected": signals,
        "honesty_labels": HONESTY_LABELS,
    }
    r["non_execution_certificate_hash"] = _core_hash(
        r, "non_execution_certificate_hash", "signals_detected")
    r["_signals"] = signals
    return r


def build_artifact_quarantine_vault(*, tenant_id, commit_simulation_id,
                                   artifact_refs, escape_attempts=0):
    refs = sorted(set(map(str, _as_list(artifact_refs)))) or list(
        NON_DELEGABLE_ARTIFACTS)
    attempts = _int(escape_attempts)
    signals = ["ARTIFACT_QUARANTINE_BREACH"] if attempts > 0 else []
    r = {
        "artifact_quarantine_vault_version": QUARANTINE_VAULT_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "quarantined_artifacts": refs, "artifact_count": len(refs),
        "all_quarantined": attempts == 0, "escape_attempts_detected": attempts,
        "vault_status": "SEALED" if not signals else "BREACH",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["artifact_quarantine_vault_hash"] = _core_hash(
        r, "artifact_quarantine_vault_hash", "signal")
    r["_signals"] = signals
    return r


def build_b9_firewall(*, tenant_id, commit_simulation_id, authority_transfer=False,
                     b9_activation=False):
    signals = []
    if authority_transfer:
        signals.append("B9_AUTHORITY_TRANSFER_DETECTED")
    if b9_activation:
        signals.append("B9_ACTIVATION_ATTEMPT")
    r = {
        "b9_firewall_version": B9_FIREWALL_VERSION, "tenant_id": tenant_id,
        "commit_simulation_id": commit_simulation_id,
        "b8_can_activate_b9": False, "b8_can_grant_b9_authority": False,
        "b8_artifacts_are_b9_authority": False,
        "authority_transfer_detected": bool(authority_transfer),
        "b9_activation_detected": bool(b9_activation),
        "firewall_status": "SEALED" if not signals else "BREACH",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["b9_firewall_hash"] = _core_hash(r, "b9_firewall_hash", "signal")
    r["_signals"] = signals
    return r


def build_b9_revalidation_contract(*, tenant_id, commit_simulation_id,
                                  contract_present=True):
    signals = [] if contract_present else ["B9_REVALIDATION_CONTRACT_MISSING"]
    r = {
        "b9_revalidation_contract_version": B9_REVAL_CONTRACT_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "b9_revalidation_required": True,
        "required_recomputations": list(B9_MUST_RECOMPUTE),
        "b8_pre_authorizes_nothing": True,
        "contract_status": "PRESENT" if contract_present else "MISSING",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["b9_revalidation_contract_hash"] = _core_hash(
        r, "b9_revalidation_contract_hash", "signal")
    r["_signals"] = signals
    return r


def build_trace_coverage(*, tenant_id, commit_simulation_id, observed_families,
                        policy):
    observed = sorted(set(map(str, _as_list(observed_families))) &
                      set(REQUIRED_TRACE_FAMILIES))
    if not _as_list(observed_families):
        observed = list(REQUIRED_TRACE_FAMILIES)
    missing = sorted(set(REQUIRED_TRACE_FAMILIES) - set(observed))
    critical_missing = sorted(set(missing) & CRITICAL_TRACE_FAMILIES)
    signals = []
    if critical_missing:
        signals.append("TRACE_COVERAGE_INSUFFICIENT")
    elif missing:
        signals.append("TRACE_COVERAGE_REVIEW")
    r = {
        "trace_coverage_version": TRACE_COVERAGE_VERSION, "tenant_id": tenant_id,
        "commit_simulation_id": commit_simulation_id,
        "required_families": list(REQUIRED_TRACE_FAMILIES),
        "observed_families": observed, "missing_families": missing,
        "critical_missing_families": critical_missing,
        "coverage_status": "COVERED" if not missing else ("CRITICAL_GAP" if
                          critical_missing else "PARTIAL"),
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["trace_coverage_hash"] = _core_hash(r, "trace_coverage_hash", "signal")
    r["_signals"] = signals
    return r


def build_non_production_seal(*, tenant_id, commit_simulation_id,
                            poisoned=False):
    signals = ["NON_PRODUCTION_SEAL_FAILED"] if poisoned else []
    r = {
        "non_production_seal_version": NON_PROD_SEAL_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "production_ready": False, "autonomous_ready": False,
        "commit_executable_now": False, "b9_ready_without_revalidation": False,
        "not_production_ready": True, "not_autonomous": True,
        "seal_status": "SEALED" if not signals else "POISONED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["non_production_seal_hash"] = _core_hash(
        r, "non_production_seal_hash", "signal")
    r["_signals"] = signals
    return r


def build_safety_case(*, tenant_id, commit_simulation_id, base_reports):
    # The safety case is complete iff every base claim node is discharged.
    claims = {
        "b7_consumed": base_reports["b7_consumption_gate"]["gate_valid"],
        "witnesses_revalidated": base_reports["state_witness_revalidation"][
            "recomputed_fresh"],
        "shadow_dry_run_ok": base_reports["shadow_dry_run"]["dry_run_status"]
        == "DRY_RUN_OK",
        "effects_simulated_only": base_reports["effect_simulation"][
            "any_actually_released"] is False,
        "rollback_fenced": base_reports["rollback_fence"]["fence_status"] ==
        "FENCED",
        "replay_consistent": base_reports["differential_replay"][
            "replay_consistent"],
        "metamorphic_holds": base_reports["metamorphic_oracle"][
            "all_relations_hold"],
        "compliant": base_reports["compliance_predicate"]["all_predicates_hold"],
        "no_commit_theorem": base_reports["no_commit_theorem"]["theorem_holds"],
        "non_execution_certified": base_reports[
            "non_execution_certificate"]["all_negative_claims_hold"],
        "artifacts_quarantined": base_reports["artifact_quarantine_vault"][
            "all_quarantined"],
        "b9_firewalled": base_reports["b9_firewall"]["firewall_status"] ==
        "SEALED",
    }
    complete = all(claims.values())
    signals = [] if complete else ["SAFETY_CASE_INCOMPLETE"]
    r = {
        "safety_case_version": SAFETY_CASE_VERSION, "tenant_id": tenant_id,
        "commit_simulation_id": commit_simulation_id, "claims": claims,
        "safety_case_complete": complete,
        "safety_case_status": "COMPLETE" if complete else "INCOMPLETE",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["safety_case_hash"] = _core_hash(r, "safety_case_hash", "signal")
    r["_signals"] = signals
    return r


# ==== B8 v5: machine-checkable pre-B9 assurance ============================
def build_evidence_closure_net(*, tenant_id, commit_simulation_id, reports,
                             force_missing_nodes=None, force_missing_edges=None,
                             force_unclosed_claims=None):
    # Structural closure: a node is PRESENT iff its backing report object exists
    # (it always does in normal flow), so the closure net never double-counts a
    # base-report *status* failure — that base report already surfaces its own
    # root-cause signal. Closure gaps are genuine structural absences or
    # explicit test injections, keeping this proof independently checkable.
    report_for_node = {
        "REQUEST": True, "B7_ESCROW": "b7_consumption_gate",
        "B8_GATEWAY": True, "REVALIDATION": "state_witness_revalidation",
        "SHADOW_DRY_RUN": "shadow_dry_run", "TRACE_LEDGER": "trace_coverage",
        "NO_COMMIT_THEOREM": "no_commit_theorem",
        "NON_EXECUTION_CERTIFICATE": "non_execution_certificate",
        "ARTIFACT_QUARANTINE": "artifact_quarantine_vault",
        "B9_FIREWALL": "b9_firewall", "FINAL_SAFETY_CASE": "safety_case",
        "ASSURANCE_ENVELOPE": True,
    }
    forced_nodes = set(map(str, _as_list(force_missing_nodes)))
    present_nodes = []
    for n in CLOSURE_NODE_TYPES:
        src = report_for_node.get(n)
        present = (src is True) or (isinstance(src, str) and src in reports)
        if present and n not in forced_nodes:
            present_nodes.append({"node_type": n, "present": True})
    missing_nodes = sorted((set(CLOSURE_NODE_TYPES) -
                            {n["node_type"] for n in present_nodes}))
    # Required edges: every proof node connects to a source and a decision.
    edges = [
        {"from": "REQUEST", "to": "B7_ESCROW", "edge_type": "DEPENDS_ON"},
        {"from": "B7_ESCROW", "to": "B8_GATEWAY", "edge_type": "SUPPORTS"},
        {"from": "B8_GATEWAY", "to": "REVALIDATION", "edge_type":
         "REQUIRES_REVALIDATION"},
        {"from": "SHADOW_DRY_RUN", "to": "NO_COMMIT_THEOREM", "edge_type":
         "SUPPORTS"},
        {"from": "NO_COMMIT_THEOREM", "to": "NON_EXECUTION_CERTIFICATE",
         "edge_type": "PROVES_NON_AUTHORITY"},
        {"from": "ARTIFACT_QUARANTINE", "to": "ASSURANCE_ENVELOPE",
         "edge_type": "QUARANTINES"},
        {"from": "B9_FIREWALL", "to": "ASSURANCE_ENVELOPE", "edge_type":
         "PROVES_NON_AUTHORITY"},
        {"from": "FINAL_SAFETY_CASE", "to": "ASSURANCE_ENVELOPE", "edge_type":
         "DISCHARGES_OBLIGATION"},
    ]
    required_edges = {("SHADOW_DRY_RUN", "NO_COMMIT_THEOREM"),
                      ("NO_COMMIT_THEOREM", "NON_EXECUTION_CERTIFICATE"),
                      ("B9_FIREWALL", "ASSURANCE_ENVELOPE"),
                      ("FINAL_SAFETY_CASE", "ASSURANCE_ENVELOPE")}
    forced_edges = set(map(str, _as_list(force_missing_edges)))
    present_edges = {(e["from"], e["to"]) for e in edges
                     if e["from"] not in missing_nodes and e["to"]
                     not in missing_nodes and "->".join((e["from"], e["to"]))
                     not in forced_edges}
    missing_edges = sorted(["->".join(e) for e in required_edges -
                            present_edges])
    unclosed = sorted(set(map(str, _as_list(force_unclosed_claims))))
    signals = []
    if missing_nodes or missing_edges or unclosed:
        signals.append("EVIDENCE_CLOSURE_NET_FAILED")
    net = {
        "evidence_closure_net_version": CLOSURE_NET_VERSION,
        "evidence_closure_net_id": "ecn-" + _sha({"sim":
                                                 commit_simulation_id})[:16],
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "nodes": present_nodes, "edges": edges,
        "missing_required_nodes": missing_nodes,
        "missing_required_edges": missing_edges, "unclosed_claims": unclosed,
        "closure_status": "CLOSED" if not signals else "OPEN",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    net["evidence_closure_net_hash"] = _core_hash(
        net, "evidence_closure_net_hash", "signal")
    net["_signals"] = signals
    return net


def build_non_delegable_artifact_seal(*, tenant_id, commit_simulation_id,
                                    artifact_hashes, delegation_attempts=None,
                                    bearer_fields=None, activation_fields=None):
    delegation = sorted(set(map(str, _as_list(delegation_attempts))))
    bearer = sorted(set(map(str, _as_list(bearer_fields))))
    activation = sorted(set(map(str, _as_list(activation_fields))))
    signals = []
    if delegation or bearer or activation:
        signals.append("NON_DELEGABLE_ARTIFACT_SEAL_FAILED")
    r = {
        "non_delegable_artifact_seal_version": NON_DELEGABLE_SEAL_VERSION,
        "non_delegable_artifact_seal_id": "nds-" + _sha({"sim":
                                                       commit_simulation_id})[:16],
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "artifact_refs": list(NON_DELEGABLE_ARTIFACTS),
        "artifact_hashes": {k: v for k, v in (artifact_hashes or {}).items()},
        "delegation_attempts_detected": delegation,
        "bearer_authority_detected": bearer,
        "lease_like_fields_detected": [f for f in bearer if "lease" in
                                       f.lower()],
        "activation_like_fields_detected": activation,
        "every_artifact_non_delegable": not signals,
        "seal_status": "SEALED" if not signals else "DELEGATION_DETECTED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["non_delegable_artifact_seal_hash"] = _core_hash(
        r, "non_delegable_artifact_seal_hash", "signal")
    r["_signals"] = signals
    return r


def build_b9_negative_capability(*, tenant_id, commit_simulation_id,
                               contract_valid=True):
    signals = [] if contract_valid else ["B9_INPUT_CONTRACT_INVALID"]
    r = {
        "b9_negative_capability_version": B9_NEG_CAP_VERSION,
        "b9_negative_capability_id": "bnc-" + _sha({"sim":
                                                  commit_simulation_id})[:16],
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "b9_forbidden_inputs": list(B9_MUST_REJECT_ARTIFACTS),
        "b9_required_revalidations": list(B9_MUST_RECOMPUTE),
        "b9_must_reject_artifacts": list(B9_MUST_REJECT_ARTIFACTS),
        "b9_must_recompute_factors": list(B9_MUST_RECOMPUTE),
        "contract_status": "VALID" if contract_valid else "INVALID",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["b9_negative_capability_hash"] = _core_hash(
        r, "b9_negative_capability_hash", "signal")
    r["_signals"] = signals
    return r


def build_cross_artifact_consistency(*, tenant_id, commit_simulation_id,
                                   reports, injected_mismatches=None):
    # Verify all component reports agree on tenant + honesty labels, and that no
    # report smuggles a positive execution flag.
    hash_mismatches, status_mismatches, reason_mismatches = [], [], []
    honesty_mismatches, blocker_mismatches = [], []
    for k, rep in reports.items():
        if not isinstance(rep, dict):
            continue
        if rep.get("tenant_id") not in (None, tenant_id):
            status_mismatches.append(k)
        if "honesty_labels" in rep and rep["honesty_labels"] != HONESTY_LABELS:
            honesty_mismatches.append(k)
    for m in _as_list(injected_mismatches):
        m = str(m).lower()
        if "hash" in m:
            hash_mismatches.append(m)
        elif "status" in m:
            status_mismatches.append(m)
        elif "reason" in m:
            reason_mismatches.append(m)
        elif "honesty" in m or "label" in m:
            honesty_mismatches.append(m)
        elif "blocker" in m:
            blocker_mismatches.append(m)
        else:
            status_mismatches.append(m)
    mismatched = bool(hash_mismatches or status_mismatches or reason_mismatches
                      or honesty_mismatches or blocker_mismatches)
    signals = ["CROSS_ARTIFACT_CONSISTENCY_FAILED"] if mismatched else []
    r = {
        "cross_artifact_consistency_version": CROSS_ARTIFACT_VERSION,
        "cross_artifact_consistency_id": "cac-" + _sha({"sim":
                                                      commit_simulation_id})[:16],
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "objects_checked": sorted(k for k in reports if isinstance(
            reports[k], dict)),
        "hash_mismatches": sorted(set(hash_mismatches)),
        "status_mismatches": sorted(set(status_mismatches)),
        "reason_code_mismatches": sorted(set(reason_mismatches)),
        "honesty_label_mismatches": sorted(set(honesty_mismatches)),
        "blocker_mismatches": sorted(set(blocker_mismatches)),
        "consistency_status": "CONSISTENT" if not mismatched else "MISMATCH",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["cross_artifact_consistency_hash"] = _core_hash(
        r, "cross_artifact_consistency_hash", "signal")
    r["_signals"] = signals
    return r


def build_route_topology_diff(*, tenant_id, commit_simulation_id,
                            baseline_routes=None, final_routes=None,
                            added_routes=None):
    baseline = sorted(set(map(str, _as_list(baseline_routes))))
    added = _as_list(added_routes)
    added_norm = []
    forbidden = []
    for ar in added:
        if isinstance(ar, dict):
            path, method = str(ar.get("path", "")), str(ar.get("method", "GET"))
            semantic = ar.get("semantic")
        else:
            path, method, semantic = str(ar), "POST", None
        added_norm.append(path)
        sem = _forbidden_route(path, method, semantic)
        if sem:
            forbidden.append({"path": path, "method": method, "semantic": sem})
    final = sorted(set(baseline) | set(added_norm)) if (baseline or added_norm) \
        else sorted(set(map(str, _as_list(final_routes))))
    signals = ["ROUTE_TOPOLOGY_DIFF_FORBIDDEN"] if forbidden else []
    r = {
        "route_topology_diff_version": ROUTE_DIFF_VERSION,
        "route_topology_diff_id": "rtd-" + _sha({"sim":
                                               commit_simulation_id})[:16],
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "baseline_route_fingerprint": _sha({"routes": baseline}),
        "final_route_fingerprint": _sha({"routes": final}),
        "added_routes": sorted(set(added_norm)),
        "removed_routes": sorted(set(baseline) - set(final)),
        "changed_routes": [],
        "forbidden_semantic_routes": forbidden,
        "diff_status": "CLEAN" if not forbidden else "FORBIDDEN",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["route_topology_diff_hash"] = _core_hash(
        r, "route_topology_diff_hash", "signal")
    r["_signals"] = signals
    return r


def build_trace_completeness_witness(*, tenant_id, commit_simulation_id,
                                   observed_families):
    observed = set(map(str, _as_list(observed_families)))
    if not observed:
        observed = set(REQUIRED_TRACE_FAMILIES)
    observed &= set(REQUIRED_TRACE_FAMILIES)
    missing = sorted(set(REQUIRED_TRACE_FAMILIES) - observed)
    critical_missing = sorted(set(missing) & CRITICAL_TRACE_FAMILIES)
    signals = ["TRACE_COMPLETENESS_WITNESS_FAILED"] if missing else []
    r = {
        "trace_completeness_witness_version": TRACE_WITNESS_VERSION,
        "trace_completeness_witness_id": "tcw-" + _sha({"sim":
                                                      commit_simulation_id})[:16],
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "required_trace_families": list(REQUIRED_TRACE_FAMILIES),
        "observed_trace_hashes": {f: _sha({"family": f, "sim":
                                         commit_simulation_id})
                                  for f in sorted(observed)},
        "missing_trace_families": missing,
        "critical_missing_trace_families": critical_missing,
        "witness_status": "COMPLETE" if not missing else "INCOMPLETE",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["trace_completeness_witness_hash"] = _core_hash(
        r, "trace_completeness_witness_hash", "signal")
    r["_signals"] = signals
    return r


def build_proof_obligation_matrix(*, tenant_id, commit_simulation_id, reports,
                                dropped_obligations=None):
    dropped = set(map(str, _as_list(dropped_obligations)))
    supporting = {
        "NO_REAL_COMMIT": reports["no_commit_theorem"]["no_commit_theorem_hash"],
        "NO_EFFECT_RELEASE": reports["effect_simulation"][
            "effect_simulation_hash"],
        "NO_COMMIT_ACTIVATION": reports["non_execution_certificate"][
            "non_execution_certificate_hash"],
        "NO_B9_ACTIVATION": reports["b9_firewall"]["b9_firewall_hash"],
        "NO_PROVIDER": reports["non_execution_certificate"][
            "non_execution_certificate_hash"],
        "NO_MCP": reports["non_execution_certificate"][
            "non_execution_certificate_hash"],
        "NO_LLM": reports["non_execution_certificate"][
            "non_execution_certificate_hash"],
        "NO_TOKEN": reports["non_execution_certificate"][
            "non_execution_certificate_hash"],
        "NO_CREDENTIAL": reports["non_execution_certificate"][
            "non_execution_certificate_hash"],
        "NO_MESSAGE": reports["non_execution_certificate"][
            "non_execution_certificate_hash"],
        "NO_PAYMENT": reports["non_execution_certificate"][
            "non_execution_certificate_hash"],
        "NO_CRM_MUTATION": reports["non_execution_certificate"][
            "non_execution_certificate_hash"],
        "NO_EVIDENCE_MUTATION": reports["non_execution_certificate"][
            "non_execution_certificate_hash"],
        "NO_EXPORT": reports["non_execution_certificate"][
            "non_execution_certificate_hash"],
        "B9_REVALIDATION_REQUIRED": reports["b9_revalidation_contract"][
            "b9_revalidation_contract_hash"],
        "ARTIFACTS_NOT_AUTHORITY": reports["b9_firewall"]["b9_firewall_hash"],
        "NOT_PRODUCTION_READY": reports["non_production_seal"][
            "non_production_seal_hash"],
    }
    discharged, undischarged = [], []
    for ob in REQUIRED_OBLIGATIONS:
        if ob in dropped or not supporting.get(ob):
            undischarged.append(ob)
        else:
            discharged.append(ob)
    signals = ["PROOF_OBLIGATION_UNDISCHARGED"] if undischarged else []
    r = {
        "proof_obligation_matrix_version": PROOF_OBLIGATION_VERSION,
        "proof_obligation_matrix_id": "pom-" + _sha({"sim":
                                                   commit_simulation_id})[:16],
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "obligations": list(REQUIRED_OBLIGATIONS),
        "discharged_obligations": sorted(discharged),
        "undischarged_obligations": sorted(undischarged),
        "supporting_hashes": {k: v for k, v in supporting.items()
                              if k not in undischarged},
        "matrix_status": "ALL_DISCHARGED" if not undischarged else
        "UNDISCHARGED", "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["proof_obligation_matrix_hash"] = _core_hash(
        r, "proof_obligation_matrix_hash", "signal")
    r["_signals"] = signals
    return r


def build_production_claim_scanner(*, tenant_id, commit_simulation_id,
                                 extra_claims=None):
    claims = {k: bool(v) for k, v in (extra_claims or {}).items()}
    poisoned, locations = [], []
    for k, v in claims.items():
        if k in POISON_CLAIM_FIELDS and v:
            poisoned.append(k)
            locations.append("injected:" + k)
    signals = ["PRODUCTION_CLAIM_POISONING_DETECTED"] if poisoned else []
    r = {
        "production_claim_scanner_version": PROD_CLAIM_SCANNER_VERSION,
        "production_claim_scanner_id": "pcs-" + _sha({"sim":
                                                    commit_simulation_id})[:16],
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "objects_checked": sorted(POISON_CLAIM_FIELDS),
        "poisoned_claims_detected": sorted(poisoned),
        "claim_locations": sorted(locations),
        "scanner_status": "CLEAN" if not poisoned else "POISONED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["production_claim_scanner_hash"] = _core_hash(
        r, "production_claim_scanner_hash", "signal")
    r["_signals"] = signals
    return r


def build_final_ci_gate(*, tenant_id, commit_simulation_id, targeted_pass=True,
                      full_pass=True, unexpected_positive=False, reports=None):
    reports = reports or {}
    signals = []
    if not targeted_pass or not full_pass or unexpected_positive:
        signals.append("FINAL_CI_RELEASE_GATE_FAILED")
    r = {
        "final_ci_gate_version": FINAL_CI_GATE_VERSION,
        "final_ci_gate_id": "fcg-" + _sha({"sim": commit_simulation_id})[:16],
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "targeted_tests_hash": _sha({"targeted_pass": bool(targeted_pass)}),
        "full_non_browser_tests_hash": _sha({"full_pass": bool(full_pass)}),
        "fault_injection_hash": (reports.get("_fault_hash") or ""),
        "red_team_corpus_hash": _sha({"redteam": "b8-v5-corpus"}),
        "release_gate_hash": (reports.get("_release_hash") or ""),
        "assurance_envelope_hash": "", "non_production_honesty_hash": (
            reports.get("non_production_seal") or {}).get(
            "non_production_seal_hash", ""),
        "targeted_pass": bool(targeted_pass), "full_pass": bool(full_pass),
        "unexpected_positive_detected": bool(unexpected_positive),
        "gate_status": "PASSED" if not signals else "FAILED",
        "signal": signals[0] if signals else None,
        "honesty_labels": HONESTY_LABELS,
    }
    r["final_ci_gate_hash"] = _core_hash(r, "final_ci_gate_hash", "signal")
    r["_signals"] = signals
    return r


def build_assurance_envelope(*, tenant_id, commit_simulation_id, reports,
                           force_invalid=False):
    e = {
        "assurance_envelope_version": ASSURANCE_ENVELOPE_VERSION,
        "assurance_envelope_id": "ae-" + _sha({"sim": commit_simulation_id})[:16],
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "schema_version": SCHEMA_VERSION,
        "b8_v1_proof_hash": reports["shadow_dry_run"]["shadow_dry_run_hash"],
        "b8_v2_proof_hash": reports["differential_replay"][
            "differential_replay_hash"],
        "b8_v3_proof_hash": reports["compliance_predicate"][
            "compliance_predicate_hash"],
        "b8_v4_proof_hash": reports["safety_case"]["safety_case_hash"],
        "evidence_closure_net_hash": reports["evidence_closure_net"][
            "evidence_closure_net_hash"],
        "non_delegable_artifact_seal_hash": reports[
            "non_delegable_artifact_seal"]["non_delegable_artifact_seal_hash"],
        "b9_negative_capability_hash": reports["b9_negative_capability"][
            "b9_negative_capability_hash"],
        "cross_artifact_consistency_hash": reports[
            "cross_artifact_consistency"]["cross_artifact_consistency_hash"],
        "route_topology_diff_hash": reports["route_topology_diff"][
            "route_topology_diff_hash"],
        "trace_completeness_witness_hash": reports[
            "trace_completeness_witness"]["trace_completeness_witness_hash"],
        "proof_obligation_matrix_hash": reports["proof_obligation_matrix"][
            "proof_obligation_matrix_hash"],
        "production_claim_scanner_hash": reports["production_claim_scanner"][
            "production_claim_scanner_hash"],
        "final_ci_gate_hash": reports["final_ci_gate"]["final_ci_gate_hash"],
        "is_authority": False, "authorizes_b9": False, "executes": False,
        "safe_viewable": True, "evidence_only": True,
        "b9_revalidation_required": True,
        "honesty_labels": HONESTY_LABELS,
    }
    # Structural validity only: the envelope is INVALID iff a required component
    # hash is absent (or an explicit test injection). A component that reported a
    # blocker still yields a well-formed envelope whose hash embeds that
    # component's (changed) hash — so the envelope is a faithful, machine-
    # checkable RECORD, and the root-cause component signal (not this aggregate)
    # drives the decision. This aggregate signal sits low in the ladder.
    required_hashes = [
        "evidence_closure_net_hash", "non_delegable_artifact_seal_hash",
        "b9_negative_capability_hash", "cross_artifact_consistency_hash",
        "route_topology_diff_hash", "trace_completeness_witness_hash",
        "proof_obligation_matrix_hash", "production_claim_scanner_hash",
        "final_ci_gate_hash"]
    structurally_invalid = force_invalid or any(
        not e.get(h) for h in required_hashes)
    e["decision_status"] = "INVALID" if structurally_invalid else "VALID"
    e["dominant_reason_code"] = ""  # filled by orchestrator
    signals = ["ASSURANCE_ENVELOPE_INVALID"] if structurally_invalid else []
    e["assurance_envelope_hash"] = _core_hash(
        e, "assurance_envelope_hash", "dominant_reason_code")
    e["_signals"] = signals
    return e


def build_v5_proof_extension(*, tenant_id, commit_simulation_id, reports):
    ext = {
        "b8_v5_proof_extension_version": V5_PROOF_EXT_VERSION,
        "b8_v5_proof_extension_id": "v5x-" + _sha({"sim":
                                                 commit_simulation_id})[:16],
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "assurance_envelope_hash": reports["assurance_envelope"][
            "assurance_envelope_hash"],
        "evidence_closure_net_hash": reports["evidence_closure_net"][
            "evidence_closure_net_hash"],
        "non_delegable_artifact_seal_hash": reports[
            "non_delegable_artifact_seal"]["non_delegable_artifact_seal_hash"],
        "b9_negative_capability_hash": reports["b9_negative_capability"][
            "b9_negative_capability_hash"],
        "cross_artifact_consistency_hash": reports[
            "cross_artifact_consistency"]["cross_artifact_consistency_hash"],
        "route_topology_diff_hash": reports["route_topology_diff"][
            "route_topology_diff_hash"],
        "trace_completeness_witness_hash": reports[
            "trace_completeness_witness"]["trace_completeness_witness_hash"],
        "proof_obligation_matrix_hash": reports["proof_obligation_matrix"][
            "proof_obligation_matrix_hash"],
        "production_claim_scanner_hash": reports["production_claim_scanner"][
            "production_claim_scanner_hash"],
        "final_ci_gate_hash": reports["final_ci_gate"]["final_ci_gate_hash"],
        "honesty_labels": HONESTY_LABELS,
    }
    ext["b8_v5_proof_extension_hash"] = _core_hash(
        ext, "b8_v5_proof_extension_hash")
    ext["_signals"] = []
    return ext


# --- Signal aggregation -----------------------------------------------------
def _sim_signals(ctx):
    tid = ctx["tenant_id"]
    sid = ctx["commit_simulation_id"]
    b7 = ctx["b7_outcome"]
    reports = {}
    signals = []

    reports["b7_consumption_gate"] = build_b7_consumption_gate(
        tenant_id=tid, commit_simulation_id=sid, b7_outcome=b7)
    reports["state_witness_revalidation"] = build_state_witness_revalidation(
        tenant_id=tid, commit_simulation_id=sid,
        fresh_witnesses=ctx.get("fresh_witnesses"),
        policy_epoch=ctx.get("policy_epoch"),
        revalidation_ok=ctx.get("revalidation_ok", True))
    reports["shadow_dry_run"] = build_shadow_dry_run(
        tenant_id=tid, commit_simulation_id=sid, b7_outcome=b7,
        dry_run_ok=ctx.get("dry_run_ok", True),
        touches_production=ctx.get("touches_production", False))
    reports["effect_simulation"] = build_effect_simulation(
        tenant_id=tid, commit_simulation_id=sid, b7_outcome=b7,
        release_attempts=ctx.get("effect_release_attempts", 0))
    reports["rollback_fence"] = build_rollback_fence(
        tenant_id=tid, commit_simulation_id=sid, b7_outcome=b7,
        replay_attack=ctx.get("replay_attack", False),
        authority_resurrection=ctx.get("authority_resurrection", False))
    reports["differential_replay"] = build_differential_replay(
        tenant_id=tid, commit_simulation_id=sid, b7_outcome=b7,
        replay_consistent=ctx.get("replay_consistent", True))
    reports["metamorphic_oracle"] = build_metamorphic_oracle(
        tenant_id=tid, commit_simulation_id=sid,
        relations_hold=ctx.get("metamorphic_holds", True))
    reports["compliance_predicate"] = build_compliance_predicate(
        tenant_id=tid, commit_simulation_id=sid,
        predicate_violations=ctx.get("predicate_violations", 0))
    reports["rollback_simulation"] = build_rollback_simulation(
        tenant_id=tid, commit_simulation_id=sid,
        rollback_feasible=ctx.get("rollback_feasible", True))
    reports["compensation_simulation"] = build_compensation_simulation(
        tenant_id=tid, commit_simulation_id=sid,
        compensation_gaps=ctx.get("compensation_gaps", 0))

    # v4
    reports["no_commit_theorem"] = build_no_commit_theorem(
        tenant_id=tid, commit_simulation_id=sid,
        shadow_dry_run=reports["shadow_dry_run"],
        effect_simulation=reports["effect_simulation"],
        theorem_refuted=ctx.get("theorem_refuted", False))
    reports["non_execution_certificate"] = build_non_execution_certificate(
        tenant_id=tid, commit_simulation_id=sid,
        attempt_markers=ctx.get("attempt_markers"))
    reports["artifact_quarantine_vault"] = build_artifact_quarantine_vault(
        tenant_id=tid, commit_simulation_id=sid,
        artifact_refs=ctx.get("artifact_refs"),
        escape_attempts=ctx.get("artifact_escape_attempts", 0))
    reports["b9_firewall"] = build_b9_firewall(
        tenant_id=tid, commit_simulation_id=sid,
        authority_transfer=ctx.get("b9_authority_transfer", False),
        b9_activation=ctx.get("b9_activation", False))
    reports["b9_revalidation_contract"] = build_b9_revalidation_contract(
        tenant_id=tid, commit_simulation_id=sid,
        contract_present=ctx.get("b9_contract_present", True))
    reports["trace_coverage"] = build_trace_coverage(
        tenant_id=tid, commit_simulation_id=sid,
        observed_families=ctx.get("observed_trace_families"),
        policy=ctx["policy"])
    reports["non_production_seal"] = build_non_production_seal(
        tenant_id=tid, commit_simulation_id=sid,
        poisoned=ctx.get("seal_poisoned", False))
    reports["safety_case"] = build_safety_case(
        tenant_id=tid, commit_simulation_id=sid, base_reports=reports)

    # v5
    reports["evidence_closure_net"] = build_evidence_closure_net(
        tenant_id=tid, commit_simulation_id=sid, reports=reports,
        force_missing_nodes=ctx.get("force_missing_nodes"),
        force_missing_edges=ctx.get("force_missing_edges"),
        force_unclosed_claims=ctx.get("force_unclosed_claims"))
    reports["non_delegable_artifact_seal"] = build_non_delegable_artifact_seal(
        tenant_id=tid, commit_simulation_id=sid,
        artifact_hashes=ctx.get("artifact_hashes"),
        delegation_attempts=ctx.get("delegation_attempts"),
        bearer_fields=ctx.get("bearer_fields"),
        activation_fields=ctx.get("activation_fields"))
    reports["b9_negative_capability"] = build_b9_negative_capability(
        tenant_id=tid, commit_simulation_id=sid,
        contract_valid=ctx.get("b9_negcap_valid", True))
    reports["route_topology_diff"] = build_route_topology_diff(
        tenant_id=tid, commit_simulation_id=sid,
        baseline_routes=ctx.get("baseline_routes"),
        final_routes=ctx.get("final_routes"),
        added_routes=ctx.get("added_routes"))
    reports["trace_completeness_witness"] = build_trace_completeness_witness(
        tenant_id=tid, commit_simulation_id=sid,
        observed_families=ctx.get("observed_trace_families"))
    reports["proof_obligation_matrix"] = build_proof_obligation_matrix(
        tenant_id=tid, commit_simulation_id=sid, reports=reports,
        dropped_obligations=ctx.get("dropped_obligations"))
    reports["production_claim_scanner"] = build_production_claim_scanner(
        tenant_id=tid, commit_simulation_id=sid,
        extra_claims=ctx.get("extra_claims"))
    reports["final_ci_gate"] = build_final_ci_gate(
        tenant_id=tid, commit_simulation_id=sid,
        targeted_pass=ctx.get("targeted_pass", True),
        full_pass=ctx.get("full_pass", True),
        unexpected_positive=ctx.get("unexpected_positive", False),
        reports=reports)
    # cross-artifact consistency after all reports exist
    reports["cross_artifact_consistency"] = build_cross_artifact_consistency(
        tenant_id=tid, commit_simulation_id=sid, reports=reports,
        injected_mismatches=ctx.get("injected_mismatches"))
    reports["assurance_envelope"] = build_assurance_envelope(
        tenant_id=tid, commit_simulation_id=sid, reports=reports,
        force_invalid=ctx.get("force_assurance_invalid", False))
    reports["b8_v5_proof_extension"] = build_v5_proof_extension(
        tenant_id=tid, commit_simulation_id=sid, reports=reports)

    # execution markers on the request itself (draft->real escape) + injection
    markers = {k for k, v in (ctx.get("execution_markers") or {}).items()
               if k in EXECUTION_MARKER_FIELDS and v}
    if markers:
        signals.append("REAL_COMMIT_ATTEMPT")
    if _has_injection(canonical_json(ctx.get("execution_markers") or {}),
                      canonical_json(ctx.get("extra_claims") or {})):
        signals.append("PRODUCTION_CLAIM_POISONING_DETECTED")

    for rep in reports.values():
        signals.extend(rep.get("_signals", []))
    return signals, reports


# --- Fault injection harness ------------------------------------------------
FAULT_CASES = [
    "assurance_envelope_grants_commit", "proof_bundle_is_b9_authority",
    "safe_output_is_commit_lease", "handoff_matrix_activates_b9",
    "b9_skips_revalidation", "production_ready_true", "commit_executable_now_true",
    "provider_ready_true", "credential_ready_true", "hidden_commit_route",
    "hidden_release_effects_route", "hidden_activate_b9_route",
    "hidden_provider_route", "drop_proof_obligation", "remove_audit_trace",
    "ci_gate_passes_with_unexpected_positive", "real_commit_attempt",
    "effect_release_attempt", "b9_activation_attempt", "artifact_delegation",
    "cross_artifact_mismatch",
]


def _apply_fault(fault, ctx):
    c = dict(ctx)
    if fault == "assurance_envelope_grants_commit":
        c["execution_markers"] = {"real_commit": True}
    elif fault == "proof_bundle_is_b9_authority":
        c["b9_authority_transfer"] = True
    elif fault == "safe_output_is_commit_lease":
        c["bearer_fields"] = ["commit_lease"]
    elif fault == "handoff_matrix_activates_b9":
        c["b9_activation"] = True
    elif fault == "b9_skips_revalidation":
        c["b9_contract_present"] = False
    elif fault == "production_ready_true":
        c["extra_claims"] = {"production_ready": True}
    elif fault == "commit_executable_now_true":
        c["extra_claims"] = {"commit_executable_now": True}
    elif fault == "provider_ready_true":
        c["extra_claims"] = {"provider_ready": True}
    elif fault == "credential_ready_true":
        c["extra_claims"] = {"credential_ready": True}
    elif fault == "hidden_commit_route":
        c["added_routes"] = [{"path":
                             "/ai-tools/commit-simulations/x/commit",
                             "method": "POST"}]
    elif fault == "hidden_release_effects_route":
        c["added_routes"] = [{"path":
                             "/ai-tools/commit-simulations/x/release-effects",
                             "method": "POST"}]
    elif fault == "hidden_activate_b9_route":
        c["added_routes"] = [{"path":
                             "/ai-tools/commit-simulations/x/activate-b9",
                             "method": "POST"}]
    elif fault == "hidden_provider_route":
        c["added_routes"] = [{"path": "/provider/call", "method": "POST"}]
    elif fault == "drop_proof_obligation":
        c["dropped_obligations"] = ["NO_REAL_COMMIT"]
    elif fault == "remove_audit_trace":
        c["observed_trace_families"] = [f for f in REQUIRED_TRACE_FAMILIES
                                        if f != "NO_COMMIT_THEOREM"]
    elif fault == "ci_gate_passes_with_unexpected_positive":
        c["unexpected_positive"] = True
    elif fault == "real_commit_attempt":
        c["attempt_markers"] = {"real_commit": True}
    elif fault == "effect_release_attempt":
        c["attempt_markers"] = {"effect_release": True}
        c["effect_release_attempts"] = 1
    elif fault == "b9_activation_attempt":
        c["attempt_markers"] = {"activate_b9": True}
    elif fault == "artifact_delegation":
        c["delegation_attempts"] = ["ASSURANCE_ENVELOPE->authority"]
    elif fault == "cross_artifact_mismatch":
        c["injected_mismatches"] = ["hash_mismatch_assurance_envelope"]
    return c


def run_fault_injection_harness(*, tenant_id, commit_simulation_id, base_ctx):
    cases = []
    all_blocked = True
    for fault in FAULT_CASES:
        c = _apply_fault(fault, base_ctx)
        sigs, _ = _sim_signals(c)
        sigs = sorted(set(sigs)) or ["B8_V5_ACCEPTED"]
        dom = dominant_signal(sigs)
        status = _status_for_signal(dom)
        blocked = status not in POSITIVE_STATUSES
        if not blocked:
            all_blocked = False
        cases.append({"fault": fault, "dominant_signal": dom,
                      "resulting_status": status, "blocked": blocked})
    h = {
        "commit_sim_fault_injection_harness_version": FAULT_HARNESS_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "fault_cases": cases, "fault_case_count": len(cases),
        "all_faults_blocked": all_blocked,
        "harness_status": "ALL_BLOCKED" if all_blocked else "LEAK_DETECTED",
        "honesty_labels": HONESTY_LABELS,
    }
    h["commit_sim_fault_injection_harness_hash"] = _core_hash(
        h, "commit_sim_fault_injection_harness_hash")
    return h


def build_release_gate(*, tenant_id, commit_simulation_id, harness):
    passed = harness["all_faults_blocked"]
    g = {
        "commit_sim_release_gate_version": RELEASE_GATE_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "negative_tests_total": harness["fault_case_count"],
        "negative_tests_blocked": sum(1 for c in harness["fault_cases"]
                                      if c["blocked"]),
        "release_gate_status": "PASSED" if passed else "FAILED",
        "signal": None if passed else "FAULT_INJECTION_RELEASE_GATE_FAILED",
        "honesty_labels": HONESTY_LABELS,
    }
    g["commit_sim_release_gate_hash"] = _core_hash(
        g, "commit_sim_release_gate_hash", "signal")
    return g


def build_conformance_vector(*, tenant_id, commit_simulation_id, reports,
                           harness, release_gate):
    dims = {
        "b7_consumed": reports["b7_consumption_gate"]["gate_valid"],
        "simulation_only": reports["shadow_dry_run"]["committed"] is False,
        "no_effect_released": reports["effect_simulation"][
            "any_actually_released"] is False,
        "no_commit_theorem_proved": reports["no_commit_theorem"][
            "theorem_holds"],
        "non_execution_certified": reports["non_execution_certificate"][
            "all_negative_claims_hold"],
        "artifacts_quarantined": reports["artifact_quarantine_vault"][
            "all_quarantined"],
        "b9_firewalled": reports["b9_firewall"]["firewall_status"] == "SEALED",
        "safety_case_complete": reports["safety_case"]["safety_case_complete"],
        "evidence_closed": reports["evidence_closure_net"][
            "closure_status"] == "CLOSED",
        "artifacts_non_delegable": reports["non_delegable_artifact_seal"][
            "seal_status"] == "SEALED",
        "b9_negcap_valid": reports["b9_negative_capability"][
            "contract_status"] == "VALID",
        "cross_artifact_consistent": reports["cross_artifact_consistency"][
            "consistency_status"] == "CONSISTENT",
        "routes_clean": reports["route_topology_diff"]["diff_status"] ==
        "CLEAN",
        "traces_complete": reports["trace_completeness_witness"][
            "witness_status"] == "COMPLETE",
        "obligations_discharged": reports["proof_obligation_matrix"][
            "matrix_status"] == "ALL_DISCHARGED",
        "no_poisoned_claims": reports["production_claim_scanner"][
            "scanner_status"] == "CLEAN",
        "final_ci_passed": reports["final_ci_gate"]["gate_status"] == "PASSED",
        "assurance_envelope_valid": reports["assurance_envelope"][
            "decision_status"] == "VALID",
        "b9_revalidation_required": reports["b9_revalidation_contract"][
            "b9_revalidation_required"] is True,
        "fault_injection_all_blocked": harness["all_faults_blocked"],
        "release_gate_passed": release_gate["release_gate_status"] == "PASSED",
    }
    conformant = all(dims.values())
    cv = {
        "commit_sim_conformance_vector_version": CONFORMANCE_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "dimensions": dims, "conformant": conformant,
        "honesty_labels": HONESTY_LABELS,
    }
    cv["commit_sim_conformance_vector_hash"] = _core_hash(
        cv, "commit_sim_conformance_vector_hash")
    return cv


_COMPONENT_HASH_KEYS = {
    "b7_consumption_gate": "b7_consumption_gate_hash",
    "state_witness_revalidation": "state_witness_revalidation_hash",
    "shadow_dry_run": "shadow_dry_run_hash",
    "effect_simulation": "effect_simulation_hash",
    "rollback_fence": "rollback_fence_hash",
    "differential_replay": "differential_replay_hash",
    "metamorphic_oracle": "metamorphic_oracle_hash",
    "compliance_predicate": "compliance_predicate_hash",
    "rollback_simulation": "rollback_simulation_hash",
    "compensation_simulation": "compensation_simulation_hash",
    "no_commit_theorem": "no_commit_theorem_hash",
    "non_execution_certificate": "non_execution_certificate_hash",
    "artifact_quarantine_vault": "artifact_quarantine_vault_hash",
    "b9_firewall": "b9_firewall_hash",
    "b9_revalidation_contract": "b9_revalidation_contract_hash",
    "trace_coverage": "trace_coverage_hash",
    "non_production_seal": "non_production_seal_hash",
    "safety_case": "safety_case_hash",
    "evidence_closure_net": "evidence_closure_net_hash",
    "non_delegable_artifact_seal": "non_delegable_artifact_seal_hash",
    "b9_negative_capability": "b9_negative_capability_hash",
    "cross_artifact_consistency": "cross_artifact_consistency_hash",
    "route_topology_diff": "route_topology_diff_hash",
    "trace_completeness_witness": "trace_completeness_witness_hash",
    "proof_obligation_matrix": "proof_obligation_matrix_hash",
    "production_claim_scanner": "production_claim_scanner_hash",
    "final_ci_gate": "final_ci_gate_hash",
    "assurance_envelope": "assurance_envelope_hash",
    "b8_v5_proof_extension": "b8_v5_proof_extension_hash",
}


def build_proof_bundle(*, tenant_id, commit_simulation_id, reports, harness,
                     release_gate, status, dominant):
    component_hashes = {}
    for rep_key, hash_key in _COMPONENT_HASH_KEYS.items():
        rep = reports.get(rep_key)
        if rep and hash_key in rep:
            component_hashes[hash_key] = rep[hash_key]
    component_hashes["commit_sim_fault_injection_harness_hash"] = harness[
        "commit_sim_fault_injection_harness_hash"]
    component_hashes["commit_sim_release_gate_hash"] = release_gate[
        "commit_sim_release_gate_hash"]
    pb = {
        "commit_simulation_proof_bundle_version": PROOF_BUNDLE_VERSION,
        "tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
        "component_hashes": component_hashes,
        "component_count": len(component_hashes),
        "resolved_status": status, "dominant_signal": dominant,
        "proof_bundle_overrides_blocker": False, "authorizes_b9": False,
        "b8_v5_proof_extension_hash": reports["b8_v5_proof_extension"][
            "b8_v5_proof_extension_hash"],
        "honesty_labels": HONESTY_LABELS,
    }
    pb["commit_simulation_proof_bundle_hash"] = _core_hash(
        pb, "commit_simulation_proof_bundle_hash")
    return pb


# --- Request envelope + orchestration --------------------------------------
def build_commit_simulation_request_envelope(*, commit_simulation_id, tenant_id,
                                           actor_id, actor_type, b7_outcome,
                                           created_at):
    o = b7_outcome or {}
    env = {
        "commit_simulation_request_envelope_version": REQUEST_VERSION,
        "commit_simulation_id": commit_simulation_id, "tenant_id": tenant_id,
        "b7_write_intent_id": o.get("write_intent_id"),
        "b7_write_intent_decision_hash": o.get("write_intent_decision_hash"),
        "b7_proof_bundle_hash": (o.get("write_intent_proof_bundle") or {}).get(
            "write_intent_proof_bundle_hash"),
        "requested_by_actor_id": actor_id, "requested_by_actor_type": actor_type,
        "is_real_commit": False, "is_execution": False,
        "simulation_only": True, "created_at": created_at,
    }
    env["commit_simulation_request_hash"] = _core_hash(
        env, "commit_simulation_request_hash", "commit_simulation_id",
        "created_at", "requested_by_actor_id", "requested_by_actor_type")
    return env


_PASS_KEYS = (
    "fresh_witnesses", "policy_epoch", "revalidation_ok", "dry_run_ok",
    "touches_production", "effect_release_attempts", "replay_attack",
    "authority_resurrection", "replay_consistent", "metamorphic_holds",
    "predicate_violations", "rollback_feasible", "compensation_gaps",
    "attempt_markers", "artifact_refs", "artifact_escape_attempts",
    "b9_authority_transfer", "b9_activation", "b9_contract_present",
    "observed_trace_families", "seal_poisoned", "artifact_hashes",
    "delegation_attempts", "bearer_fields", "activation_fields",
    "b9_negcap_valid", "baseline_routes", "final_routes", "added_routes",
    "dropped_obligations", "extra_claims", "targeted_pass", "full_pass",
    "unexpected_positive", "injected_mismatches", "execution_markers", "policy",
    "theorem_refuted", "force_missing_nodes", "force_missing_edges",
    "force_unclosed_claims", "force_assurance_invalid",
)


def prepare_commit_simulation_outcome(*, commit_simulation_id, tenant_id,
                                    actor_id, actor_type, envelope, b7_outcome,
                                    created_at=None, **over):
    """Prepare a local, simulation-only, machine-checkable pre-B9 assurance
    outcome. Runs the full deterministic evaluation, the fault-injection harness
    and the release gate, then resolves the fail-closed status. Produces only
    local evidence; performs NO real commit, NO effect release, NO commitment/B9
    activation, and NO external effect. B9 revalidation always remains required."""
    pol = dict(DEFAULT_POLICY)
    for k, v in (over.get("policy") or {}).items():
        if k in DEFAULT_POLICY:
            pol[k] = v
    ctx = {"tenant_id": tenant_id, "commit_simulation_id": commit_simulation_id,
           "b7_outcome": b7_outcome, "policy": pol, "created_at": created_at}
    for k in _PASS_KEYS:
        if k in over:
            ctx[k] = over[k]
    ctx["policy"] = pol

    signals, reports = _sim_signals(ctx)

    harness = run_fault_injection_harness(
        tenant_id=tenant_id, commit_simulation_id=commit_simulation_id,
        base_ctx=ctx)
    release_gate = build_release_gate(
        tenant_id=tenant_id, commit_simulation_id=commit_simulation_id,
        harness=harness)
    if release_gate["signal"]:
        signals.append(release_gate["signal"])

    signals = sorted(set(signals))
    if not signals:
        signals = ["B8_V5_ACCEPTED"]
    dominant = dominant_signal(signals)
    status = _status_for_signal(dominant)
    decision = _decision_for_status(status)

    conformance = build_conformance_vector(
        tenant_id=tenant_id, commit_simulation_id=commit_simulation_id,
        reports=reports, harness=harness, release_gate=release_gate)
    proof_bundle = build_proof_bundle(
        tenant_id=tenant_id, commit_simulation_id=commit_simulation_id,
        reports=reports, harness=harness, release_gate=release_gate,
        status=status, dominant=dominant)

    outcome_kind = "PRE_B9_ASSURANCE_ONLY" if status == "B8_V5_ACCEPTED" \
        else status
    clean_reports = {}
    for k, rep in reports.items():
        if isinstance(rep, dict):
            clean_reports[k] = {kk: vv for kk, vv in rep.items()
                                if kk != "_signals"}
        else:
            clean_reports[k] = rep
    outcome = {
        "commit_sim_model_version": COMMIT_SIM_MODEL_VERSION,
        "commit_simulation_id": commit_simulation_id, "tenant_id": tenant_id,
        "b7_write_intent_id": (b7_outcome or {}).get("write_intent_id"),
        "commit_simulation_status": status,
        "commit_simulation_decision_status": decision,
        "commit_simulation_outcome_kind": outcome_kind,
        "dominant_signal": dominant,
        "dominant_reason_code": REASON_CODES.get(dominant, ""),
        "all_signals": signals,
        "signal_reason_codes": {s: REASON_CODES.get(s, "") for s in signals},
        "b8_v5_accepted": status == "B8_V5_ACCEPTED",
        "b9_revalidation_required": True,
        "is_real_commit": False, "is_execution": False, "simulation_only": True,
        "commit_executable_now": False, "produced_external_effect": False,
        "released_effect": False, "activated_commitment": False,
        "activated_b9": False, "granted_b9_authority": False,
        "production_ready": False, "autonomous_ready": False,
        "artifacts_are_authority": False,
        "commit_simulation_request_hash": (envelope or {}).get(
            "commit_simulation_request_hash"),
        "decided_by_actor_id": actor_id, "decided_by_actor_type": actor_type,
        "created_at": created_at, "updated_at": created_at,
        "commit_sim_fault_injection_harness": harness,
        "commit_sim_release_gate_report": release_gate,
        "commit_sim_conformance_vector": conformance,
        "commit_simulation_proof_bundle": proof_bundle,
        "honesty_labels": HONESTY_LABELS,
    }
    outcome.update(clean_reports)
    outcome["commit_simulation_decision_hash"] = _core_hash(
        outcome, "commit_simulation_decision_hash", "commit_simulation_id",
        "decided_by_actor_id", "decided_by_actor_type",
        "commit_simulation_state_hash")
    outcome["commit_simulation_state_hash"] = _sha({
        "commit_simulation_id": commit_simulation_id,
        "commit_simulation_decision_hash": outcome[
            "commit_simulation_decision_hash"],
        "commit_simulation_status": status, "dominant_signal": dominant,
        "commit_simulation_request_hash": (envelope or {}).get(
            "commit_simulation_request_hash"),
        "proof_bundle_hash": proof_bundle[
            "commit_simulation_proof_bundle_hash"]})
    return outcome


# --- Event ledger ----------------------------------------------------------
COMMIT_SIM_EVENT_TYPES = {
    "COMMIT_SIMULATION_REQUEST_OPENED", "COMMIT_SIMULATION_OUTCOME_PREPARED",
    "COMMIT_SIMULATION_FAULT_INJECTED", "COMMIT_SIMULATION_OUTCOME_VERIFIED",
}


def build_commit_simulation_event(*, event_type, tenant_id, commit_simulation_id,
                                actor_id, actor_type, commit_simulation_state_hash,
                                previous_event_hash, sequence, detail, created_at):
    ev = {
        "commit_simulation_event_version": COMMIT_SIM_EVENT_VERSION,
        "event_type": event_type, "tenant_id": tenant_id,
        "commit_simulation_id": commit_simulation_id, "actor_id": actor_id,
        "actor_type": actor_type,
        "commit_simulation_state_hash": commit_simulation_state_hash,
        "previous_event_hash": previous_event_hash or GENESIS,
        "sequence": sequence, "detail": detail or {}, "created_at": created_at,
    }
    ev["event_hash"] = _core_hash(ev, "event_hash")
    return ev
