"""Finalis ViktorAI Formal Tool Descriptor Assurance Graph (TOOL-B2).

A security-first, formal-quality, planner-safety and descriptor-assurance
module over the TOOL-B1 registry. It proves — locally and deterministically —
that a registered tool descriptor is clear, bounded, non-deceptive and formally
consistent enough for FUTURE planner reasoning.

This module executes NOTHING. It is not a Tool Broker, not tool execution, not
an MCP server/client, not an external-provider or LLM integration, and it never
rewrites descriptors. All scoring, linting, mutation and metamorphic testing is
deterministic keyword/structure logic — no model is called. "Quality" here is a
security property, not a production-safety certification.

Authoritative rules (fail-closed, no-Goodhart):
- Descriptor TEXT can never lower TOOL-B1 risk, hide a side effect, hide data
  flow, override policy, remove an approval/consent requirement, make unsafe
  prompt-context exposure safe, or make a future Tool Broker unnecessary.
- A high numeric score can never override a single critical blocker.
- Quality PASS means only "descriptor quality gate passed"; it does not mean
  executable and cannot override any TOOL-B1 security/admission state.
"""
from __future__ import annotations

import hashlib
import json

from . import tool_registry as _tr

QUALITY_GATE_VERSION = "finalis-tool-quality-gate-v1"
IR_VERSION = "finalis-tool-descriptor-ir-v1"
SEMANTIC_RECORD_VERSION = "finalis-tool-canonical-semantic-record-v1"
ASSURANCE_GRAPH_VERSION = "finalis-tool-assurance-graph-v1"
SCORE_VECTOR_VERSION = "finalis-tool-quality-score-vector-v1"
INTENT_FINGERPRINT_VERSION = "finalis-tool-semantic-intent-fingerprint-v1"
EVIDENCE_PACKAGE_VERSION = "finalis-tool-quality-evidence-package-v1"
ASSURANCE_CASE_VERSION = "finalis-tool-quality-assurance-case-v1"
CONFUSION_VERSION = "finalis-tool-planner-confusion-matrix-v1"
SELECTION_BOUNDARY_VERSION = "finalis-tool-planner-selection-boundary-v1"
COUNTERFACTUAL_VERSION = "finalis-tool-counterfactual-planner-v1"
MUTATION_VERSION = "finalis-tool-mutation-harness-v1"
METAMORPHIC_VERSION = "finalis-tool-metamorphic-v1"
MONOTONIC_VERSION = "finalis-tool-monotonic-risk-proof-v1"
NON_REGRESSION_VERSION = "finalis-tool-non-regression-proof-v1"
QUALITY_EVENT_VERSION = "finalis-tool-quality-event-v1"
GENESIS = "0" * 64

# --- Quality statuses ------------------------------------------------------
QUALITY_STATUSES = {
    "QUALITY_PENDING", "QUALITY_PASS", "QUALITY_PASS_WITH_WARNINGS",
    "QUALITY_NEEDS_REVIEW", "QUALITY_FAIL", "QUALITY_BLOCKED",
    "QUALITY_QUARANTINED", "QUALITY_MUTATION_FAILED",
    "QUALITY_METAMORPHIC_FAILED", "QUALITY_IR_MISMATCH",
    "QUALITY_ASSURANCE_GRAPH_FAILED", "QUALITY_CONTEXT_EXPOSURE_BLOCKED",
    "QUALITY_NOT_IMPLEMENTED",
}

# TOOL-B1 statuses that are a security hard-fail: such a tool can never yield a
# quality PASS and its descriptor is NEVER_EXPOSE to a future planner. Kept in
# one place so the selection boundary and the no-Goodhart override agree.
_SECURITY_BLOCKED_STATUSES = {
    "QUARANTINED", "TAMPERED", "RUG_PULL_DETECTED", "DRIFT_DETECTED",
    "FORBIDDEN_CAPABILITY", "CROSS_TENANT_REJECTED", "BLOCKED",
}

# Hard-fail dominance categories, most dominant first. A single higher category
# always wins over every category after it and over any positive score.
BLOCKER_DOMINANCE = [
    "POISONED", "HIDDEN_INSTRUCTION", "FORMAL_IR_MISMATCH",
    "ASSURANCE_GRAPH_FAILED", "CONTRADICTION", "SIDE_EFFECT_MISMATCH",
    "SCHEMA_MISMATCH", "POLICY_MISMATCH", "CAPABILITY_DOWNGRADE", "OVERCLAIM",
    "OVERBROAD", "PLANNER_MISUSE", "METAMORPHIC_FAILED",
    "ADVERSARIAL_MUTATION_FAIL", "CONTEXT_EXPOSURE_UNSAFE", "AMBIGUOUS",
    "NEEDS_REVIEW",
]
_CATEGORY_TO_STATUS = {
    "POISONED": "QUALITY_QUARANTINED",
    "HIDDEN_INSTRUCTION": "QUALITY_BLOCKED",
    "FORMAL_IR_MISMATCH": "QUALITY_IR_MISMATCH",
    "ASSURANCE_GRAPH_FAILED": "QUALITY_ASSURANCE_GRAPH_FAILED",
    "CONTRADICTION": "QUALITY_FAIL",
    "SIDE_EFFECT_MISMATCH": "QUALITY_FAIL",
    "SCHEMA_MISMATCH": "QUALITY_FAIL",
    "POLICY_MISMATCH": "QUALITY_FAIL",
    "CAPABILITY_DOWNGRADE": "QUALITY_FAIL",
    "OVERCLAIM": "QUALITY_FAIL",
    "OVERBROAD": "QUALITY_FAIL",
    "PLANNER_MISUSE": "QUALITY_FAIL",
    "METAMORPHIC_FAILED": "QUALITY_METAMORPHIC_FAILED",
    "ADVERSARIAL_MUTATION_FAIL": "QUALITY_MUTATION_FAILED",
    "CONTEXT_EXPOSURE_UNSAFE": "QUALITY_CONTEXT_EXPOSURE_BLOCKED",
    "AMBIGUOUS": "QUALITY_NEEDS_REVIEW",
    "NEEDS_REVIEW": "QUALITY_NEEDS_REVIEW",
}

# --- Score dimensions ------------------------------------------------------
SCORE_DIMENSIONS = [
    "NAME_CLARITY", "DESCRIPTION_SPECIFICITY", "FORMAL_IR_ALIGNMENT",
    "ASSURANCE_GRAPH_COMPLETENESS", "EVIDENCE_BOUND_CLAIMS",
    "PURPOSE_ALIGNMENT", "INPUT_SCHEMA_COMPLETENESS",
    "OUTPUT_SCHEMA_COMPLETENESS", "SIDE_EFFECT_DISCLOSURE",
    "DATA_FLOW_DISCLOSURE", "RISK_DISCLOSURE", "APPROVAL_DISCLOSURE",
    "CONSENT_DISCLOSURE", "PROMPT_CONTEXT_SAFETY", "TOOL_CONTEXT_MINIMALITY",
    "EXAMPLE_SAFETY", "DEFAULT_VALUE_SAFETY", "ALIAS_SAFETY",
    "HUMAN_REVIEW_READABILITY", "PLANNER_MISUSE_RISK",
    "TOOL_SELECTION_MISROUTING_RISK", "CONTRADICTION_FREE", "POLICY_ALIGNMENT",
    "SECURITY_CASE_ALIGNMENT", "NEGATIVE_CAPABILITY_ALIGNMENT",
    "OVERCLAIM_RESISTANCE", "CAPABILITY_DOWNGRADE_RESISTANCE",
    "ADVERSARIAL_MUTATION_ROBUSTNESS", "METAMORPHIC_SAFETY", "MONOTONIC_RISK",
    "NON_REGRESSION",
]

HONESTY_LABELS = [
    "Tool Description Quality Gate does not execute tools.",
    "Quality pass does not mean executable.",
    "Future Tool Broker is required before any tool call.",
    "Quality scoring is deterministic and local; it does not use LLM.",
    "Descriptor quality is security-relevant but not a production safety "
    "certification.",
    "Formal descriptor IR is deterministic and limited; it is not full "
    "semantic understanding.",
    "Assurance graph is local evidence, not production certification.",
    "Mutation harness is deterministic and limited; it does not prove full "
    "paraphrase robustness.",
    "Metamorphic tests are deterministic and limited; they do not prove "
    "complete semantic safety.",
    "Counterfactual planner simulation is deterministic and approximate; it "
    "does not model a real LLM planner.",
    "Planner selection boundary is future-readiness metadata only; no model is "
    "called.",
    "Prompt-context recommendation is future-readiness metadata only; no model "
    "is called.",
    "Quality pass cannot override TOOL-B1 security blockers.",
    "External providers are not called in this mission.",
    "MCP server/client is not implemented in this mission.",
    "Server-side registry truth is authoritative.",
    "This is not production autonomous execution.",
]


# --- Hashing ---------------------------------------------------------------
def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _sha(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def _text_sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


_VOLATILE = ("created_at", "updated_at", "honesty_labels")


def _core_hash(obj: dict, self_key: str, *extra) -> str:
    excluded = {self_key, *_VOLATILE, *extra}
    return _sha({k: v for k, v in obj.items() if k not in excluded})


def _norm(text: str) -> str:
    # Reuse the registry's NFKC + leet + homoglyph + punctuation-collapsing
    # normalizer so quality checks resist the same evasions as the scanner.
    return _tr._normalize(text)


def _tokens(text: str) -> list:
    return [t for t in _norm(text).split() if t]


_NEGATORS = {"no", "not", "without", "never", "zero", "non", "cannot", "cant",
             "dont", "doesnt", "wont", "nor", "neither", "excludes",
             "excluding"}


def _positive_token_set(blob: str) -> set:
    """Token set with directly-negated occurrences removed, so 'no external
    calls', 'no side effects' and 'without writes' do not register externality/
    side-effect/write terms. Only the IMMEDIATELY-following token is treated as
    negated (window of 1): this is fail-closed against double-negation evasion
    ('never fails to delete evidence' keeps 'delete'/'evidence' visible so the
    danger still escalates) while still clearing simple 'no X' disclaimers.
    Deterministic, limited negation handling — not full semantic understanding."""
    seq = blob.split()
    negated = set()
    for i, t in enumerate(seq):
        if t in _NEGATORS and i + 1 < len(seq):
            negated.add(i + 1)
    return {t for i, t in enumerate(seq) if i not in negated}


# --- Keyword tables (deterministic IR + linters) ---------------------------
_ACTION_VERBS = {
    "read", "list", "search", "get", "fetch", "summarize", "analyze",
    "compute", "send", "email", "message", "notify", "pay", "charge", "refund",
    "transfer", "write", "update", "create", "delete", "remove", "export",
    "download", "upload", "sync", "grant", "revoke", "sign", "approve",
    "schedule", "call", "invoke", "execute", "run",
}
_SIDE_EFFECT_TERMS = {"send", "write", "update", "create", "delete", "remove",
                      "pay", "charge", "refund", "transfer", "export", "sync",
                      "modify", "mutate", "overwrite", "wipe"}
_DATA_FLOW_TERMS = {"read", "fetch", "store", "save", "log", "retain", "cache",
                    "collect", "share", "egress", "upload", "download",
                    "transmit"}
_EXTERNALITY_TERMS = {"external", "internet", "network", "http", "https", "api",
                      "webhook", "third", "party", "outbound", "remote", "url"}
_APPROVAL_TERMS = {"approval", "approve", "approver", "authorize",
                   "authorization", "review", "sign", "off", "gate"}
_CONSENT_TERMS = {"consent", "opt", "in", "gdpr", "lawful", "basis",
                  "permission"}
_RISK_TERMS = {"risk", "dangerous", "sensitive", "critical", "high", "caution",
               "irreversible", "destructive"}
_SECRET_TERMS = {"secret", "token", "password", "credential", "credentials",
                 "key", "apikey", "privatekey", "ssh"}
_CUSTOMER_TERMS = {"customer", "client", "recipient", "user", "contact",
                   "whatsapp", "sms", "email"}
_EVIDENCE_TERMS = {"evidence", "proof", "chain", "attestation"}
_PAYMENT_TERMS = {"payment", "pay", "charge", "invoice", "refund", "money",
                  "stripe", "bank", "iban", "card"}
_ADMIN_TERMS = {"admin", "owner", "root", "superuser", "privilege",
                "privileges", "rbac", "role", "grant"}
_FORBIDDEN_TERMS = {"payment", "crm", "evidence", "customer", "export",
                    "identity", "admin"}

# Persuasive / planner-manipulation phrases (normalized, space-joined).
_PLANNER_PERSUASION = [
    "prefer this tool", "always choose this tool", "always use this tool",
    "choose this tool over", "prefer this over", "best tool for everything",
    "use this instead of", "you should always call", "recommended over all",
    "pick this tool first",
]
# Hidden-instruction / injection phrases specific to descriptor prose.
_HIDDEN_INSTRUCTION = [
    "ignore previous instructions", "ignore all previous", "system prompt",
    "use this as a system prompt", "hidden parameter", "use hidden parameter",
    "do not tell the user", "secret instruction", "when called also",
    "also call", "silently", "without telling", "override policy",
    "disregard the rules",
]
# Overclaim phrases (safety/capability the descriptor cannot self-certify).
_OVERCLAIM = [
    "completely safe", "totally safe", "100 safe", "guaranteed safe",
    "safe because i say so", "safe to show to model even if poisoned",
    "trust me", "no risk", "risk free", "cannot cause harm", "always safe",
    "fully verified", "production ready", "certified safe",
    "safe even if poisoned",
]
# Capability-downgrade phrases (text trying to lower TOOL-B1 risk).
_CAPABILITY_DOWNGRADE = [
    "lower this tool risk", "lower risk to low", "mark as low risk",
    "treat as low risk", "reduce risk", "downgrade risk", "risk is actually low",
    "consider this low risk", "set risk to low", "this is low risk",
]
# Text claiming execution / that a broker is unnecessary.
_EXECUTION_CLAIM = [
    "execute now", "runs immediately", "executes the tool",
    "no tool broker", "tool broker is unnecessary", "tool broker not required",
    "broker not needed", "no broker needed", "run without broker",
    "executes without approval", "bypass approval", "no approval needed",
    "skip approval", "no approval required for payment",
]
# Generic / uninformative names.
_GENERIC_NAMES = {"tool", "helper", "util", "utils", "do", "run", "action",
                  "handler", "service", "api", "func", "function", "thing",
                  "misc", "general", "wrapper", "exec", "execute"}
# Reserved-like names a descriptor must not claim.
_RESERVED_NAMES = {"admin", "root", "system", "superuser", "owner", "kernel",
                   "sudo", "god", "master", "broker", "toolbroker"}

# Synonyms of dangerous verbs (for the mutation harness).
_DANGEROUS_SYNONYMS = {
    "bypass": ["skip", "avoid", "circumvent", "evade", "sidestep"],
    "approval": ["authorization", "signoff", "review", "consent"],
    "execute": ["run", "perform", "carry out", "trigger"],
    "payment": ["charge", "transfer", "money movement"],
    "delete": ["remove", "wipe", "erase", "destroy"],
    "secret": ["token", "credential", "api key", "private key"],
    "admin": ["administrator", "root", "superuser"],
}


def _has_phrase(blob: str, phrases) -> list:
    return [p for p in phrases if p in blob]


def _blob(*texts) -> str:
    return " ".join(_norm(t) for t in texts if t)


# --- Finding model ---------------------------------------------------------
def _finding(code, severity, category, dimension, detail):
    return {"code": code, "severity": severity, "category": category,
            "dimension": dimension, "detail": detail}


# --- Formal descriptor intermediate representation -------------------------
def build_formal_ir(*, descriptor, tenant_id, tool_id, tool_version_id,
                    source_descriptor_hash, b1_category, b1_side_effect,
                    b1_risk, b1_prompt_exposure) -> dict:
    """Deterministic descriptor interpretation, compared against TOOL-B1 truth.
    No LLM; no claim of full semantic understanding."""
    name = descriptor.get("tool_name", "")
    desc = descriptor.get("tool_description", "")
    summary = descriptor.get("tool_summary", "")
    blob = _blob(name, summary, desc)
    toks = _positive_token_set(blob)

    def hits(table):
        return sorted(toks & table)
    verbs = hits(_ACTION_VERBS)
    se_terms = hits(_SIDE_EFFECT_TERMS)
    df_terms = hits(_DATA_FLOW_TERMS)
    ext_terms = hits(_EXTERNALITY_TERMS)
    approval_terms = hits(_APPROVAL_TERMS)
    consent_terms = hits(_CONSENT_TERMS)
    risk_terms = hits(_RISK_TERMS)
    secret_terms = hits(_SECRET_TERMS)
    customer_terms = hits(_CUSTOMER_TERMS)
    evidence_terms = hits(_EVIDENCE_TERMS)
    payment_terms = hits(_PAYMENT_TERMS)
    admin_terms = hits(_ADMIN_TERMS)
    forbidden_terms = hits(_FORBIDDEN_TERMS)
    objects = sorted(t for t in toks if len(t) > 3 and t not in _ACTION_VERBS)[
        :24]

    # Deterministic guesses from the prose alone.
    if payment_terms:
        cat_guess = "PAYMENT"
    elif customer_terms and se_terms:
        cat_guess = "CUSTOMER_MESSAGING"
    elif evidence_terms and se_terms:
        cat_guess = "EVIDENCE_MUTATION"
    elif se_terms and ext_terms:
        cat_guess = "EXTERNAL_API_WRITE"
    elif se_terms:
        cat_guess = "INTERNAL_WRITE"
    elif ext_terms:
        cat_guess = "EXTERNAL_API_READ"
    else:
        cat_guess = "DATA_READ"
    if payment_terms:
        se_guess = "PAYMENT_MOVEMENT"
    elif customer_terms and se_terms:
        se_guess = "CUSTOMER_MESSAGING"
    elif evidence_terms and se_terms:
        se_guess = "EVIDENCE_MUTATION"
    elif se_terms and ext_terms:
        se_guess = "EXTERNAL_WRITE"
    elif se_terms:
        se_guess = "INTERNAL_WRITE"
    else:
        se_guess = "PURE_READ"
    if payment_terms or (evidence_terms and se_terms) or secret_terms:
        risk_guess = "HIGH"
    elif se_terms or ext_terms:
        risk_guess = "MEDIUM"
    else:
        risk_guess = "TRIVIAL"
    prompt_risk = ("HIGH" if (secret_terms or payment_terms or forbidden_terms)
                   else ("MEDIUM" if ext_terms else "LOW"))

    # Compare with TOOL-B1 truth. The IR can only ESCALATE — it flags a mismatch
    # when the prose implies MORE danger than B1 declares (a hidden effect) or
    # names a forbidden capability B1 did not classify as forbidden.
    reasons = []
    b1_se_rank = _tr.SIDE_EFFECT_RANK.get(b1_side_effect, 0)
    ir_se_rank = _tr.SIDE_EFFECT_RANK.get(se_guess, 0)
    if ir_se_rank > b1_se_rank:
        reasons.append(f"prose implies side effect {se_guess} above declared "
                       f"{b1_side_effect}")
    b1_risk_rank = _tr.RISK_RANK.get(b1_risk, 0)
    ir_risk_rank = _tr.RISK_RANK.get(risk_guess, 0)
    if ir_risk_rank > b1_risk_rank:
        reasons.append(f"prose implies risk {risk_guess} above declared "
                       f"{b1_risk}")
    if payment_terms and b1_category != "PAYMENT" and not b1_side_effect == \
            "PAYMENT_MOVEMENT":
        reasons.append("prose references payment but category/effect is not "
                       "payment")
    if customer_terms and se_terms and not (
            b1_side_effect == "CUSTOMER_MESSAGING"
            or b1_category == "CUSTOMER_MESSAGING"):
        reasons.append("prose implies customer messaging not declared")
    if evidence_terms and se_terms and b1_side_effect != "EVIDENCE_MUTATION" \
            and b1_category != "EVIDENCE_MUTATION":
        reasons.append("prose implies evidence mutation not declared")

    ir = {
        "descriptor_ir_version": IR_VERSION, "tenant_id": tenant_id,
        "tool_id": tool_id, "tool_version_id": tool_version_id,
        "source_descriptor_hash": source_descriptor_hash,
        "detected_action_verbs": verbs, "detected_objects": objects,
        "detected_side_effect_terms": se_terms,
        "detected_data_flow_terms": df_terms,
        "detected_externality_terms": ext_terms,
        "detected_approval_terms": approval_terms,
        "detected_consent_terms": consent_terms,
        "detected_risk_terms": risk_terms,
        "detected_secret_terms": secret_terms,
        "detected_customer_visible_terms": customer_terms,
        "detected_evidence_terms": evidence_terms,
        "detected_payment_terms": payment_terms,
        "detected_admin_terms": admin_terms,
        "detected_forbidden_terms": forbidden_terms,
        "ir_category_guess": cat_guess, "ir_side_effect_guess": se_guess,
        "ir_risk_guess": risk_guess, "ir_prompt_context_risk_guess": prompt_risk,
        "ir_matches_tool_b1_truth": not reasons,
        "ir_mismatch_reasons": reasons,
    }
    ir["formal_descriptor_ir_hash"] = _core_hash(ir, "formal_descriptor_ir_hash")
    return ir


# --- Semantic intent fingerprint -------------------------------------------
def build_semantic_intent_fingerprint(*, descriptor, tenant_id, tool_id,
                                      ir) -> dict:
    blob = _blob(descriptor.get("tool_name", ""),
                 descriptor.get("tool_summary", ""),
                 descriptor.get("tool_description", ""))
    toks = _positive_token_set(blob)
    verbs = ir["detected_action_verbs"]
    if ir["detected_payment_terms"]:
        intent = "MOVE_MONEY"
    elif ir["detected_customer_visible_terms"] and ir[
            "detected_side_effect_terms"]:
        intent = "CONTACT_CUSTOMER"
    elif ir["detected_evidence_terms"] and ir["detected_side_effect_terms"]:
        intent = "MUTATE_EVIDENCE"
    elif ir["detected_side_effect_terms"]:
        intent = "WRITE_DATA"
    elif ir["detected_externality_terms"]:
        intent = "EXTERNAL_READ"
    else:
        intent = "READ_DATA"
    fp = {
        "semantic_intent_version": INTENT_FINGERPRINT_VERSION,
        "tool_id": tool_id, "tenant_id": tenant_id,
        "declared_action_verbs": verbs,
        "declared_objects": ir["detected_objects"],
        "declared_side_effect_terms": ir["detected_side_effect_terms"],
        "declared_externality_terms": ir["detected_externality_terms"],
        "declared_approval_terms": ir["detected_approval_terms"],
        "declared_consent_terms": ir["detected_consent_terms"],
        "declared_risk_terms": ir["detected_risk_terms"],
        "declared_prohibited_terms": sorted(toks & _FORBIDDEN_TERMS),
        "derived_intent_class": intent,
        "intent_confidence": "LOCAL_DETERMINISTIC_ONLY",
    }
    fp["semantic_intent_fingerprint_hash"] = _core_hash(
        fp, "semantic_intent_fingerprint_hash")
    return fp


# --- Deterministic linters -------------------------------------------------
def lint_descriptor(descriptor) -> list:
    """Name/description/planner-prose linter."""
    findings = []
    name = descriptor.get("tool_name", "")
    desc = descriptor.get("tool_description", "")
    key = _tr.normalize_tool_key(name)
    name_toks = set(_tokens(name))
    if not name.strip():
        findings.append(_finding("name_missing", "BLOCKER", "AMBIGUOUS",
                                 "NAME_CLARITY", "tool has no name"))
    elif name_toks & _RESERVED_NAMES:
        findings.append(_finding("name_reserved", "BLOCKER", "OVERBROAD",
                                 "NAME_CLARITY",
                                 f"name uses reserved term {sorted(name_toks & _RESERVED_NAMES)}"))
    elif key in _GENERIC_NAMES or (name_toks and name_toks <= _GENERIC_NAMES):
        findings.append(_finding("name_generic", "WARNING", "AMBIGUOUS",
                                 "NAME_CLARITY", "name is generic/uninformative"))
    d = desc.strip()
    if not d:
        findings.append(_finding("description_missing", "BLOCKER", "AMBIGUOUS",
                                 "DESCRIPTION_SPECIFICITY",
                                 "tool has no description"))
    elif len(d) < 20 or len(_tokens(d)) < 4:
        findings.append(_finding("description_vague", "WARNING", "AMBIGUOUS",
                                 "DESCRIPTION_SPECIFICITY",
                                 "description is too short/vague"))
    blob = _blob(name, descriptor.get("tool_summary", ""), desc)
    for p in _has_phrase(blob, _PLANNER_PERSUASION):
        findings.append(_finding("planner_persuasion", "BLOCKER",
                                 "PLANNER_MISUSE", "PLANNER_MISUSE_RISK",
                                 f"persuasive planner-manipulation prose: '{p}'"))
    for p in _has_phrase(blob, _HIDDEN_INSTRUCTION):
        findings.append(_finding("hidden_instruction", "BLOCKER",
                                 "HIDDEN_INSTRUCTION", "PLANNER_MISUSE_RISK",
                                 f"hidden/injection instruction: '{p}'"))
    for p in _has_phrase(blob, _EXECUTION_CLAIM):
        findings.append(_finding("execution_or_broker_claim", "BLOCKER",
                                 "POLICY_MISMATCH", "POLICY_ALIGNMENT",
                                 f"descriptor claims execution / broker not "
                                 f"required: '{p}'"))
    for p in _has_phrase(blob, _OVERCLAIM):
        findings.append(_finding("overclaim", "BLOCKER", "OVERCLAIM",
                                 "OVERCLAIM_RESISTANCE",
                                 f"overclaim of safety/capability: '{p}'"))
    return findings


def lint_schema(schema_envelope, *, b1_risk) -> list:
    findings = []
    params = schema_envelope.get("parameters", [])
    inp = schema_envelope.get("input_schema") or {}
    out = schema_envelope.get("output_schema") or {}
    if not inp and not params:
        findings.append(_finding("input_schema_missing", "BLOCKER",
                                 "SCHEMA_MISMATCH", "INPUT_SCHEMA_COMPLETENESS",
                                 "no input schema / parameters declared"))
    if not out:
        findings.append(_finding("output_schema_missing", "WARNING",
                                 "SCHEMA_MISMATCH", "OUTPUT_SCHEMA_COMPLETENESS",
                                 "no output schema declared"))
    for p in params:
        pname = p.get("name", "")
        pdesc = _norm(p.get("description", ""))
        default = p.get("default")
        example = p.get("example")
        dc = p.get("data_class", "INTERNAL")
        # dangerous defaults / examples.
        for label, val in (("default", default), ("example", example)):
            if isinstance(val, str) and val:
                b = _norm(val)
                if _has_phrase(b, _HIDDEN_INSTRUCTION) or _has_phrase(
                        b, _EXECUTION_CLAIM):
                    findings.append(_finding(
                        f"schema_dangerous_{label}", "BLOCKER", "SCHEMA_MISMATCH",
                        "EXAMPLE_SAFETY" if label == "example"
                        else "DEFAULT_VALUE_SAFETY",
                        f"parameter {pname} {label} carries dangerous text"))
        # secret/token fields without secret data-class.
        if any(s in _norm(pname) for s in ("token", "secret", "password",
                                           "apikey", "privatekey")) \
                and dc not in ("CREDENTIALS", "SECRET"):
            findings.append(_finding("schema_secret_field_misclassed", "BLOCKER",
                                     "SCHEMA_MISMATCH", "INPUT_SCHEMA_COMPLETENESS",
                                     f"parameter {pname} references a secret but "
                                     f"is classed {dc}"))
        # free-form high-risk input.
        if p.get("type") == "string" and not p.get("description") \
                and _tr.RISK_RANK.get(b1_risk, 0) >= _tr.RISK_RANK["MEDIUM"]:
            findings.append(_finding("schema_freeform_highrisk", "WARNING",
                                     "SCHEMA_MISMATCH", "INPUT_SCHEMA_COMPLETENESS",
                                     f"undocumented free-form field {pname} on a "
                                     f"{b1_risk}-risk tool"))
    return findings


def lint_prompt_context(descriptor, prompt_context_policy, *, scanner) -> list:
    findings = []
    poisoned = scanner.get("quarantine_status") == "QUARANTINED"
    if poisoned:
        findings.append(_finding("prompt_context_poisoned", "BLOCKER",
                                 "POISONED", "PROMPT_CONTEXT_SAFETY",
                                 "descriptor tripped the poisoning scanner; "
                                 "unsafe for any model context"))
    exposure = prompt_context_policy.get("effective_exposure")
    if prompt_context_policy.get("expose_full_descriptor_to_model") and (
            _has_phrase(_blob(descriptor.get("tool_description", "")),
                        _HIDDEN_INSTRUCTION)):
        findings.append(_finding("prompt_context_unsafe_full", "BLOCKER",
                                 "CONTEXT_EXPOSURE_UNSAFE", "PROMPT_CONTEXT_SAFETY",
                                 "full-descriptor exposure with injection prose"))
    return findings


def detect_contradictions(descriptor, ir, *, b1_side_effect, b1_category,
                          b1_risk, effect_contract, data_flow, consent) -> list:
    """Description vs contracts / risk / approval / data-flow."""
    findings = []
    blob = _blob(descriptor.get("tool_name", ""),
                 descriptor.get("tool_summary", ""),
                 descriptor.get("tool_description", ""))
    reads_only_claim = ("read only" in blob or "readonly" in blob
                        or "read-only" in blob)
    writes = (b1_side_effect not in ("PURE_READ",)) or effect_contract.get(
        "touches_external") or data_flow.get("writes_data_classes")
    if reads_only_claim and writes:
        findings.append(_finding("readonly_but_writes", "BLOCKER",
                                 "CONTRADICTION", "CONTRADICTION_FREE",
                                 "claims read-only but effect/data-flow writes"))
    # low risk claim with dangerous effect.
    if _tr.RISK_RANK.get(b1_risk, 0) <= _tr.RISK_RANK["LOW"] and (
            effect_contract.get("touches_payment")
            or effect_contract.get("touches_customer")
            or effect_contract.get("touches_evidence")
            or b1_side_effect in _tr.FORBIDDEN_SIDE_EFFECTS
            or ir["detected_secret_terms"]):
        findings.append(_finding("low_risk_dangerous_effect", "BLOCKER",
                                 "CONTRADICTION", "RISK_DISCLOSURE",
                                 "low risk declared with a dangerous effect"))
    # description says external API but effect declares no network.
    if ir["detected_externality_terms"] and not effect_contract.get(
            "touches_external"):
        findings.append(_finding("external_prose_no_network", "BLOCKER",
                                 "CONTRADICTION", "DATA_FLOW_DISCLOSURE",
                                 "prose implies external/network but effect "
                                 "declares none"))
    # high side-effect with no approval visible.
    high = effect_contract.get("side_effect_rank", 0) >= _tr.SIDE_EFFECT_RANK[
        "EXTERNAL_WRITE"]
    if high and not ir["detected_approval_terms"]:
        findings.append(_finding("no_approval_high_effect", "BLOCKER",
                                 "SIDE_EFFECT_MISMATCH", "APPROVAL_DISCLOSURE",
                                 "high side-effect but approval not disclosed in "
                                 "the descriptor"))
    # secret schema field but B1 says no secret data.
    reads = set(data_flow.get("reads_data_classes", []))
    if ir["detected_secret_terms"] and not (reads & {"CREDENTIALS", "SECRET"}):
        findings.append(_finding("secret_prose_no_secret_dataclass", "BLOCKER",
                                 "SIDE_EFFECT_MISMATCH", "DATA_FLOW_DISCLOSURE",
                                 "prose references secrets but data-flow declares "
                                 "no secret class"))
    return findings


def detect_capability_downgrade(descriptor, *, b1_risk) -> list:
    blob = _blob(descriptor.get("tool_name", ""),
                 descriptor.get("tool_summary", ""),
                 descriptor.get("tool_description", ""))
    findings = []
    for p in _has_phrase(blob, _CAPABILITY_DOWNGRADE):
        findings.append(_finding("capability_downgrade", "BLOCKER",
                                 "CAPABILITY_DOWNGRADE",
                                 "CAPABILITY_DOWNGRADE_RESISTANCE",
                                 f"text attempts to downgrade risk: '{p}'"))
    return findings


def detect_overbroad(ir, *, b1_category) -> list:
    findings = []
    verbs = set(ir["detected_action_verbs"])
    # A benign-category descriptor whose prose spans many dangerous verbs.
    dangerous = verbs & {"pay", "charge", "delete", "grant", "transfer", "sign",
                         "export"}
    if b1_category in ("DATA_READ", "DATA_SEARCH", "INTERNAL_COMPUTE",
                       "ANALYTICS") and len(dangerous) >= 2:
        findings.append(_finding("overbroad_capability", "BLOCKER", "OVERBROAD",
                                 "TOOL_SELECTION_MISROUTING_RISK",
                                 f"benign category but prose spans dangerous "
                                 f"verbs {sorted(dangerous)}"))
    return findings


# --- Planner confusion matrix ----------------------------------------------
def _jaccard(a, b):
    a, b = set(a), set(b)
    if not a and not b:
        return 0.0
    return round(len(a & b) / len(a | b), 4)


def build_planner_confusion_matrix(*, tool_id, tenant_id, candidate,
                                   existing) -> dict:
    """candidate/existing entries: {tool_id, tool_key, tool_name, aliases,
    purpose, risk_rank, side_effect_rank}. Deterministic token-overlap only."""
    cand_name = set(_tokens(candidate.get("tool_name", "")))
    cand_alias = set()
    for a in candidate.get("aliases", []):
        cand_alias |= set(_tokens(a))
    cand_purpose = set(candidate.get("purpose", []))
    confusable_ids, confusable_cats = [], []
    worst_name = worst_alias = worst_purpose = 0.0
    misroute = 0.0
    reasons = []
    for e in existing:
        if e.get("tool_id") == tool_id:
            continue
        e_name = set(_tokens(e.get("tool_name", "")))
        e_alias = set()
        for a in e.get("aliases", []):
            e_alias |= set(_tokens(a))
        no = _jaccard(cand_name, e_name)
        ao = _jaccard(cand_alias | cand_name, e_alias | e_name)
        po = _jaccard(cand_purpose, set(e.get("purpose", [])))
        worst_name = max(worst_name, no)
        worst_alias = max(worst_alias, ao)
        worst_purpose = max(worst_purpose, po)
        if no >= 0.5 or ao >= 0.5 or po >= 0.6:
            confusable_ids.append(e.get("tool_id"))
            confusable_cats.append(e.get("category"))
            # Confusion with a MORE privileged tool is a misrouting hazard.
            gap = e.get("risk_rank", 0) - candidate.get("risk_rank", 0)
            se_gap = e.get("side_effect_rank", 0) - candidate.get(
                "side_effect_rank", 0)
            if gap > 0 or se_gap > 0:
                misroute = max(misroute, round((no + ao + po) / 3, 4))
                reasons.append(f"confusable with more-privileged tool "
                               f"{e.get('tool_id')}")
    matrix = {
        "planner_confusion_matrix_version": CONFUSION_VERSION,
        "tool_id": tool_id, "tenant_id": tenant_id,
        "confusable_tool_ids": sorted(set(x for x in confusable_ids if x)),
        "confusable_categories": sorted(set(c for c in confusable_cats if c)),
        "name_overlap_score": worst_name, "alias_overlap_score": worst_alias,
        "purpose_overlap_score": worst_purpose,
        "risk_gap_score": round(misroute, 4),
        "side_effect_gap_score": round(misroute, 4),
        "misrouting_risk": misroute, "misrouting_reasons": sorted(set(reasons)),
    }
    matrix["planner_confusion_hash"] = _core_hash(matrix,
                                                  "planner_confusion_hash")
    return matrix


def detect_tool_selection_misrouting(confusion, counterfactual) -> list:
    findings = []
    if confusion["misrouting_risk"] >= 0.5:
        findings.append(_finding("planner_misrouting", "BLOCKER",
                                 "PLANNER_MISUSE", "TOOL_SELECTION_MISROUTING_RISK",
                                 "high confusion with a more-privileged tool"))
    elif confusion["misrouting_risk"] > 0:
        findings.append(_finding("planner_misrouting_warn", "WARNING",
                                 "PLANNER_MISUSE", "TOOL_SELECTION_MISROUTING_RISK",
                                 "some confusion with a more-privileged tool"))
    if counterfactual and counterfactual.get("misrouting_detected"):
        findings.append(_finding("counterfactual_misrouting", "BLOCKER",
                                 "PLANNER_MISUSE", "PLANNER_MISUSE_RISK",
                                 "counterfactual planner selects this tool for an "
                                 "unsafe task"))
    return findings


# --- Planner selection boundary --------------------------------------------
_PLANNER_SAFE_FIELDS = ["tool_id", "tool_name", "tool_summary", "category",
                        "risk_class"]
_SUMMARY_ONLY_FIELDS = ["tool_description", "parameters"]
_NEVER_EXPOSE_FIELDS = ["input_schema", "output_schema", "declared_provider",
                        "aliases"]


def build_selection_boundary(*, tool_id, tenant_id, b1_status, b1_risk,
                             quarantined, prompt_exposure, ir_mismatch) -> dict:
    reasons = []
    if quarantined or b1_status in _SECURITY_BLOCKED_STATUSES:
        minimal = "NEVER_EXPOSE"
        reasons.append("poisoned / security-blocked descriptor")
    elif ir_mismatch:
        minimal = "REQUIRES_REDACTION"
        reasons.append("formal IR disagrees with registry truth")
    elif _tr.RISK_RANK.get(b1_risk, 0) >= _tr.RISK_RANK["HIGH"]:
        minimal = "SUMMARY_ONLY"
        reasons.append("high-risk tool")
    elif prompt_exposure in ("NEVER_EXPOSE", "NAME_ONLY"):
        minimal = "SUMMARY_ONLY"
        reasons.append("prompt-context policy restricts exposure")
    else:
        minimal = "MINIMAL"
    budget = {"MINIMAL": 5, "SUMMARY_ONLY": 3, "REQUIRES_REDACTION": 2,
              "NEVER_EXPOSE": 0, "TOO_BROAD": 1}.get(minimal, 0)
    if minimal == "NEVER_EXPOSE":
        allowed = ["tool_id"]
    elif minimal in ("SUMMARY_ONLY", "REQUIRES_REDACTION"):
        allowed = ["tool_id", "tool_name", "category", "risk_class"]
    else:
        allowed = list(_PLANNER_SAFE_FIELDS)
    boundary = {
        "planner_selection_boundary_version": SELECTION_BOUNDARY_VERSION,
        "tool_id": tool_id, "tenant_id": tenant_id,
        "allowed_descriptor_fields_for_planner": allowed,
        "summary_only_fields": list(_SUMMARY_ONLY_FIELDS),
        "redacted_fields": ([] if minimal == "MINIMAL"
                            else list(_SUMMARY_ONLY_FIELDS)),
        "never_expose_fields": list(_NEVER_EXPOSE_FIELDS),
        "context_exposure_budget": budget, "minimal_context_status": minimal,
        "selection_boundary_status": ("NEVER_EXPOSE" if minimal
                                      == "NEVER_EXPOSE" else "PRESENT"),
        "reasons": reasons,
    }
    boundary["selection_boundary_hash"] = _core_hash(
        boundary, "selection_boundary_hash")
    return boundary


# --- Counterfactual planner simulation -------------------------------------
_COUNTERFACTUAL_TASKS = [
    ("read_only_information_request", {"DATA_READ", "DATA_SEARCH",
                                       "INTERNAL_COMPUTE", "ANALYTICS"}),
    ("customer_message_request", {"CUSTOMER_MESSAGING"}),
    ("payment_request", {"PAYMENT"}),
    ("evidence_rewrite_request", {"EVIDENCE_MUTATION"}),
    ("admin_permission_request", {"ADMIN_OPERATION", "IDENTITY_ACCESS"}),
    ("external_api_request", {"EXTERNAL_API_READ", "EXTERNAL_API_WRITE"}),
    ("secret_read_request", {"IDENTITY_ACCESS"}),
    ("data_export_request", {"DOCUMENT_EXPORT"}),
]


def counterfactual_planner_simulation(*, tool_id, tenant_id, category, ir,
                                      b1_side_effect) -> dict:
    """Deterministic heuristic: would a naive keyword planner pick THIS tool for
    each canonical task, and is that a safe match? Detects a benign-looking
    descriptor that a planner could route a dangerous task to."""
    results = []
    misrouting = False
    reasons = []
    intent = {
        "customer_message_request": ir["detected_customer_visible_terms"] and
        ir["detected_side_effect_terms"],
        "payment_request": bool(ir["detected_payment_terms"]),
        "evidence_rewrite_request": ir["detected_evidence_terms"] and ir[
            "detected_side_effect_terms"],
        "admin_permission_request": bool(ir["detected_admin_terms"]),
        "secret_read_request": bool(ir["detected_secret_terms"]),
        "data_export_request": "export" in ir["detected_action_verbs"],
        "external_api_request": bool(ir["detected_externality_terms"]),
        "read_only_information_request": True,
    }
    for task, safe_cats in _COUNTERFACTUAL_TASKS:
        selected = bool(intent.get(task, False))
        safe = category in safe_cats
        # Misrouting: the descriptor's prose invites selection for a dangerous
        # task its declared category is NOT the safe home for.
        if selected and not safe and task != "read_only_information_request":
            misrouting = True
            reasons.append(f"prose invites selection for {task} but category "
                           f"{category} is not its safe home")
        results.append({"task": task, "selected_by_heuristic": selected,
                        "expected_safe_category": sorted(safe_cats),
                        "safe_match": safe})
    proof = {
        "counterfactual_planner_version": COUNTERFACTUAL_VERSION,
        "tool_id": tool_id, "tenant_id": tenant_id,
        "counterfactual_tasks": results,
        "misrouting_detected": misrouting,
        "misrouting_reasons": sorted(set(reasons)),
    }
    proof["counterfactual_planner_proof_hash"] = _core_hash(
        proof, "counterfactual_planner_proof_hash")
    return proof


# --- Adversarial mutation harness ------------------------------------------
_DANGEROUS_FAMILIES = {
    "bypass_approval": ["bypass approval", "skip approval", "no approval needed"],
    "execute_payment": ["execute payment", "move money", "charge the card"],
    "send_customer_message": ["send customer message", "message the customer"],
    "rewrite_evidence": ["rewrite evidence", "delete evidence"],
    "call_external": ["call external provider", "call external api silently"],
    "system_prompt": ["use this as a system prompt", "ignore previous "
                      "instructions"],
    "prefer_tool": ["prefer this tool", "always choose this tool"],
    "broker_unnecessary": ["tool broker is unnecessary", "no tool broker"],
    "grant_admin": ["grant admin", "become owner"],
    "read_secret": ["read secret", "read the credentials"],
    "cross_tenant": ["cross tenant access", "change tenant"],
    "mark_production": ["mark production ready"],
    "lower_risk": ["lower risk to low", "mark as low risk"],
}


def _mutate_normalization(phrase: str) -> list:
    """Deterministic mutations the NORMALIZER is expected to defeat: case,
    whitespace, punctuation, separators, leet, homoglyph and benign wrappers.
    A covered phrase must remain detected under ALL of these."""
    return [
        phrase.upper(),
        phrase.title(),
        phrase.replace(" ", "  "),
        phrase.replace(" ", " . "),
        phrase.replace(" ", "-"),
        phrase.replace(" ", "_"),
        "please kindly " + phrase + " thanks",
        phrase.replace("o", "0").replace("i", "1").replace("e", "3"),
        phrase.replace("a", "@"),
        "note: " + phrase,
        # Proper homoglyph substitution: latin a/o/e → Cyrillic look-alikes,
        # which the normalizer must fold back to latin.
        phrase.replace("a", "а").replace("o", "о").replace(
            "e", "е"),
    ]


def _mutate_synonym(phrase: str) -> list:
    """Limited synonym expansion — a PARAPHRASE probe. Escapes here are a known
    limitation (deterministic keyword matching cannot cover all synonyms); the
    mission explicitly forbids claiming complete paraphrase robustness, so these
    are recorded as paraphrase gaps, not robustness weaknesses."""
    out = []
    for base, syns in _DANGEROUS_SYNONYMS.items():
        if base in phrase:
            for s in syns:
                out.append(phrase.replace(base, s))
    return out


def mutation_harness(*, tool_id, tenant_id) -> dict:
    """Confirm the descriptor scanner + hidden-instruction detector still flag
    each dangerous family under deterministic textual mutation. A miss is a
    WEAKNESS_FOUND (the detector, not a specific descriptor, is being probed)."""
    def _caught(text):
        blob = _blob(text)
        scanner = _tr.scan_descriptor(tool_description=text)
        return (scanner["quarantine_status"] == "QUARANTINED"
                or _has_phrase(blob, _HIDDEN_INSTRUCTION)
                or _has_phrase(blob, _EXECUTION_CLAIM)
                or _has_phrase(blob, _PLANNER_PERSUASION)
                or _has_phrase(blob, _CAPABILITY_DOWNGRADE)
                or _has_phrase(blob, _OVERCLAIM))
    cases = 0
    findings = []
    uncovered = []
    paraphrase_gaps = []
    for family, phrases in sorted(_DANGEROUS_FAMILIES.items()):
        for phrase in phrases:
            if not _caught(phrase):
                # Base phrase outside detector coverage — a coverage matter, not
                # a robustness one. Recorded honestly.
                uncovered.append({"family": family, "phrase": phrase})
                continue
            for variant in _mutate_normalization(phrase):
                cases += 1
                if not _caught(variant):
                    # A covered phrase became invisible under a NORMALIZATION
                    # mutation: a real robustness weakness in the normalizer.
                    findings.append({"family": family, "variant": variant,
                                     "base": phrase})
            for variant in _mutate_synonym(phrase):
                cases += 1
                if not _caught(variant):
                    paraphrase_gaps.append({"family": family, "variant": variant,
                                            "base": phrase})
    status = "CLEAR" if not findings else "WEAKNESS_FOUND"
    result = {
        "mutation_harness_version": MUTATION_VERSION, "tool_id": tool_id,
        "tenant_id": tenant_id, "mutation_harness_status": status,
        "mutation_cases_run": cases, "mutation_findings": findings,
        "uncovered_bases": uncovered, "paraphrase_gaps": paraphrase_gaps,
        "families_covered": sorted(_DANGEROUS_FAMILIES.keys()),
        "paraphrase_robustness_claimed": False,
    }
    result["mutation_harness_hash"] = _core_hash(result, "mutation_harness_hash")
    return result


# --- Metamorphic testing ---------------------------------------------------
def metamorphic_testing(*, tool_id, tenant_id) -> dict:
    """Deterministic metamorphic relations: an equivalent dangerous intent must
    remain detected under transformation. Each relation is checked over a probe
    phrase; a failure means a transformation made a dangerous phrase 'safe'."""
    cases = []
    failures = []

    def detects(text):
        blob = _blob(text)
        sc = _tr.scan_descriptor(tool_description=text)
        return (sc["quarantine_status"] == "QUARANTINED"
                or _has_phrase(blob, _HIDDEN_INSTRUCTION)
                or _has_phrase(blob, _EXECUTION_CLAIM)
                or _has_phrase(blob, _PLANNER_PERSUASION)
                or _has_phrase(blob, _CAPABILITY_DOWNGRADE))
    relations = [
        ("case_invariance", "Bypass Approval", "bypass approval"),
        ("whitespace_invariance", "bypass   approval", "bypass approval"),
        ("politeness_invariance", "please bypass approval thank you",
         "bypass approval"),
        ("leet_invariance", "byp4ss appr0val", "bypass approval"),
        ("synonym_invariance", "skip approval", "bypass approval"),
        ("broker_invariance", "tool broker is unnecessary",
         "tool broker is unnecessary"),
        ("secret_invariance", "read the credentials", "read secret"),
        ("downgrade_invariance", "mark as low risk", "lower risk to low"),
        ("injection_invariance", "ignore previous instructions",
         "ignore previous instructions"),
        ("prefer_invariance", "always choose this tool", "prefer this tool"),
    ]
    for name, transformed, base in relations:
        base_detected = detects(base)
        trans_detected = detects(transformed)
        ok = trans_detected if base_detected else True
        cases.append({"relation": name, "base_detected": base_detected,
                      "transformed_detected": trans_detected, "held": ok})
        if not ok:
            failures.append(name)
    status = "PASSED" if not failures else "FAILED"
    result = {
        "metamorphic_version": METAMORPHIC_VERSION, "tool_id": tool_id,
        "tenant_id": tenant_id, "metamorphic_status": status,
        "metamorphic_cases": cases, "metamorphic_failures": failures,
    }
    result["metamorphic_test_hash"] = _core_hash(result, "metamorphic_test_hash")
    return result


# --- Monotonic risk proof --------------------------------------------------
def monotonic_risk_proof(*, tenant_id, tool_id, tool_version_id, b1_risk,
                         b1_side_effect, ir) -> dict:
    detected_risk = ir["ir_risk_guess"]
    detected_se = ir["ir_side_effect_guess"]
    failed = []
    # The quality-detected risk/effect must be >= B1 truth (text may only
    # escalate). We take the MAX so the recorded quality risk never drops below
    # B1, and flag if the detector itself somehow produced a lower value that a
    # caller might misread as a downgrade.
    final_risk = max(b1_risk, detected_risk, key=lambda r: _tr.RISK_RANK.get(
        r, 0))
    final_se = max(b1_side_effect, detected_se,
                   key=lambda s: _tr.SIDE_EFFECT_RANK.get(s, 0))
    if _tr.RISK_RANK.get(final_risk, 0) < _tr.RISK_RANK.get(b1_risk, 0):
        failed.append("risk below TOOL-B1 truth")
    if _tr.SIDE_EFFECT_RANK.get(final_se, 0) < _tr.SIDE_EFFECT_RANK.get(
            b1_side_effect, 0):
        failed.append("side effect below TOOL-B1 truth")
    status = "MATCHED" if not failed else "FAILED"
    proof = {
        "monotonic_risk_proof_id": tool_version_id + "-monorisk",
        "monotonic_risk_proof_version": MONOTONIC_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id,
        "tool_version_id": tool_version_id, "tool_b1_risk_class": b1_risk,
        "tool_b1_side_effect_class": b1_side_effect,
        "quality_detected_risk_class": final_risk,
        "quality_detected_side_effect_class": final_se,
        "monotonicity_status": status,
        "non_downgrade_status": status, "failed_items": failed,
    }
    proof["monotonic_risk_proof_hash"] = _core_hash(
        proof, "monotonic_risk_proof_hash")
    return proof


# --- Non-regression proof --------------------------------------------------
def non_regression_proof(*, tenant_id, tool_id, tool_version_id, previous,
                         current_blockers, current_report_hash,
                         current_score_total, current_risk,
                         current_descriptor_hash) -> dict:
    prev_blockers = (previous or {}).get("quality_blockers", [])
    prev_codes = {b["code"] for b in prev_blockers}
    cur_codes = {b["code"] for b in current_blockers}
    new_blockers = sorted(cur_codes - prev_codes)
    removed = sorted(prev_codes - cur_codes)
    prev_score = (previous or {}).get("quality_score_total")
    prev_risk = (previous or {}).get("monotonic_detected_risk", current_risk)
    # A removed blocker must be justified: a removal is only "evidenced" when the
    # descriptor actually changed (a genuine edit). If a blocker vanished while
    # the descriptor hash is unchanged, that is an unexplained regression and
    # needs review.
    prev_desc_hash = (previous or {}).get("tool_descriptor_hash")
    removed_have_evidence = (not removed) or (
        prev_desc_hash is not None
        and prev_desc_hash != current_descriptor_hash)
    status = "MATCHED"
    if removed and not removed_have_evidence:
        status = "NEEDS_REVIEW"
    proof = {
        "non_regression_proof_id": tool_version_id + "-nonreg",
        "non_regression_proof_version": NON_REGRESSION_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id,
        "tool_version_id": tool_version_id,
        "previous_quality_report_hash": (previous or {}).get(
            "quality_report_hash"),
        "current_quality_report_hash": current_report_hash,
        "previous_blockers": sorted(prev_codes),
        "current_blockers": sorted(cur_codes), "new_blockers": new_blockers,
        "removed_blockers": removed,
        "removed_blockers_have_evidence": bool(removed_have_evidence),
        "score_delta": (None if prev_score is None
                        else current_score_total - prev_score),
        "risk_delta": _tr.RISK_RANK.get(current_risk, 0) - _tr.RISK_RANK.get(
            prev_risk, 0),
        "prompt_context_delta": None, "non_regression_status": status,
    }
    proof["non_regression_proof_hash"] = _core_hash(
        proof, "non_regression_proof_hash")
    return proof


# --- Assurance graph (DAG) -------------------------------------------------
def build_assurance_graph(*, tool_id, tenant_id, tool_version_id,
                          source_hashes, checks, blockers, warnings,
                          positive_claims) -> dict:
    """Build a DAG of claims/evidence/checks/blockers. Every positive claim must
    have >=1 SUPPORTS edge from a non-prose evidence node; every blocker maps to
    a violated invariant; cycles are forbidden."""
    nodes, edges = [], []

    def add_node(nid, ntype, label=None):
        nodes.append({"id": nid, "type": ntype, "label": label})
    for h_name, h_val in sorted(source_hashes.items()):
        add_node(f"src:{h_name}", "SOURCE_HASH", h_val)
    for c in checks:
        add_node(f"check:{c['id']}", c.get("type", "LINTER_RESULT"),
                 c.get("result"))
        edges.append({"from": f"check:{c['id']}", "to": f"src:{c['source']}",
                      "type": "DERIVED_FROM"})
    unsupported, violated = [], []
    for i, claim in enumerate(positive_claims):
        cid = f"claim:{i}"
        add_node(cid, "QUALITY_CLAIM", claim["text"])
        support = [c for c in checks if c["id"] in claim.get("supported_by", [])]
        if not support:
            unsupported.append(claim["text"])
        for c in support:
            edges.append({"from": f"check:{c['id']}", "to": cid,
                          "type": "SUPPORTS"})
    for i, b in enumerate(blockers):
        bid = f"blocker:{i}"
        add_node(bid, "BLOCKER", b["code"])
        inv = b.get("category", "UNSPECIFIED")
        violated.append(inv)
        edges.append({"from": bid, "to": f"inv:{inv}", "type": "BLOCKS"})
        add_node(f"inv:{inv}", "EVIDENCE_REF", inv)
    for i, w in enumerate(warnings):
        wid = f"warning:{i}"
        add_node(wid, "WARNING", w["code"])
    add_node("honesty", "HONESTY_LABEL", "no-execution")
    acyclic = _is_acyclic(nodes, edges)
    if not acyclic:
        status = "FAILED"
    elif unsupported or violated:
        status = "MISMATCHED"
    else:
        status = "MATCHED"
    graph = {
        "assurance_graph_id": tool_version_id + "-assurance",
        "assurance_graph_version": ASSURANCE_GRAPH_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id,
        "tool_version_id": tool_version_id, "nodes": nodes, "edges": edges,
        "acyclic": acyclic, "unsupported_claims": unsupported,
        "violated_invariants": sorted(set(violated)),
        "assurance_graph_status": status,
    }
    graph["assurance_graph_hash"] = _core_hash(graph, "assurance_graph_hash")
    return graph


def _is_acyclic(nodes, edges) -> bool:
    adj = {n["id"]: [] for n in nodes}
    for e in edges:
        if e["from"] in adj and e["to"] in adj:
            adj[e["from"]].append(e["to"])
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n["id"]: WHITE for n in nodes}

    def dfs(u):
        color[u] = GRAY
        for v in adj[u]:
            if color[v] == GRAY:
                return False
            if color[v] == WHITE and not dfs(v):
                return False
        color[u] = BLACK
        return True
    return all(dfs(n["id"]) for n in nodes if color[n["id"]] == WHITE)


# --- Score vector (deterministic, diagnostic only) -------------------------
def compute_score_vector(*, findings, ir, assurance_graph, mutation, metamorphic,
                         monotonic, non_regression, boundary, confusion) -> dict:
    scores = {d: 5 for d in SCORE_DIMENSIONS}
    for f in findings:
        dim = f["dimension"]
        if dim in scores:
            scores[dim] = 0 if f["severity"] == "BLOCKER" else min(
                scores[dim], 3)
    if not ir["ir_matches_tool_b1_truth"]:
        scores["FORMAL_IR_ALIGNMENT"] = 0
    if assurance_graph["assurance_graph_status"] != "MATCHED":
        scores["ASSURANCE_GRAPH_COMPLETENESS"] = 0
    if assurance_graph["unsupported_claims"]:
        scores["EVIDENCE_BOUND_CLAIMS"] = 0
    if mutation["mutation_harness_status"] != "CLEAR":
        scores["ADVERSARIAL_MUTATION_ROBUSTNESS"] = 0
    if metamorphic["metamorphic_status"] != "PASSED":
        scores["METAMORPHIC_SAFETY"] = 0
    if monotonic["monotonicity_status"] != "MATCHED":
        scores["MONOTONIC_RISK"] = 0
    if non_regression and non_regression["non_regression_status"] != "MATCHED":
        scores["NON_REGRESSION"] = min(scores["NON_REGRESSION"], 2)
    if boundary["minimal_context_status"] == "NEVER_EXPOSE":
        scores["TOOL_CONTEXT_MINIMALITY"] = 0
    if confusion["misrouting_risk"] >= 0.5:
        scores["TOOL_SELECTION_MISROUTING_RISK"] = 0
    vector = {"score_vector_version": SCORE_VECTOR_VERSION, "scores": scores,
              "total": sum(scores.values()),
              "max_total": 5 * len(SCORE_DIMENSIONS)}
    vector["score_vector_hash"] = _core_hash(vector, "score_vector_hash")
    return vector


# --- Dominant status + no-goodhart -----------------------------------------
def quality_dominant_status(findings) -> tuple:
    """Return (status, dominant_category). No-Goodhart: any BLOCKER forces a
    non-pass status regardless of score; WARNING-only → PASS_WITH_WARNINGS."""
    blocker_cats = [f["category"] for f in findings if f["severity"] == "BLOCKER"]
    review_cats = [f["category"] for f in findings
                   if f["severity"] == "REVIEW"]
    warnings = [f for f in findings if f["severity"] == "WARNING"]
    if blocker_cats:
        for cat in BLOCKER_DOMINANCE:
            if cat in blocker_cats:
                return _CATEGORY_TO_STATUS[cat], cat
    if review_cats:
        return "QUALITY_NEEDS_REVIEW", "NEEDS_REVIEW"
    if warnings:
        return "QUALITY_PASS_WITH_WARNINGS", None
    return "QUALITY_PASS", None


# --- Canonical semantic record ---------------------------------------------
def build_canonical_semantic_record(*, descriptor, ir, fingerprint, tenant_id,
                                    tool_id, tool_version_id) -> dict:
    rec = {
        "canonical_semantic_record_version": SEMANTIC_RECORD_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id,
        "tool_version_id": tool_version_id,
        "tool_key": descriptor.get("tool_key"),
        "category": descriptor.get("category"),
        "ir_category_guess": ir["ir_category_guess"],
        "ir_side_effect_guess": ir["ir_side_effect_guess"],
        "ir_risk_guess": ir["ir_risk_guess"],
        "derived_intent_class": fingerprint["derived_intent_class"],
        "action_verbs": ir["detected_action_verbs"],
        "objects": ir["detected_objects"],
    }
    rec["canonical_semantic_record_hash"] = _core_hash(
        rec, "canonical_semantic_record_hash")
    return rec


# --- Evidence package ------------------------------------------------------
def build_evidence_package(*, tenant_id, tool_id, tool_version_id, source_hashes,
                           ir_hash, assurance_graph_hash, score_vector_hash,
                           fingerprint_hash, mutation_hash, metamorphic_hash,
                           monotonic_hash, non_regression_hash, linter_hash,
                           blockers, warnings) -> dict:
    pkg = {
        "quality_evidence_package_id": tool_version_id + "-evidence",
        "quality_evidence_package_version": EVIDENCE_PACKAGE_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id,
        "tool_version_id": tool_version_id,
        **{k: v for k, v in source_hashes.items()},
        "formal_descriptor_ir_hash": ir_hash,
        "assurance_graph_hash": assurance_graph_hash,
        "linter_result_hash": linter_hash, "score_vector_hash": score_vector_hash,
        "semantic_intent_fingerprint_hash": fingerprint_hash,
        "mutation_harness_hash": mutation_hash,
        "metamorphic_test_hash": metamorphic_hash,
        "monotonic_risk_proof_hash": monotonic_hash,
        "non_regression_proof_hash": non_regression_hash,
        "blocker_summary": sorted(b["code"] for b in blockers),
        "warning_summary": sorted(w["code"] for w in warnings),
    }
    pkg["quality_evidence_package_hash"] = _core_hash(
        pkg, "quality_evidence_package_hash")
    return pkg


# --- Assurance case --------------------------------------------------------
def build_assurance_case(*, tenant_id, tool_id, tool_version_id, status,
                         blockers, warnings, assurance_graph_hash, mutation,
                         metamorphic, monotonic, non_regression) -> dict:
    claims = [{"claim": "descriptor quality gate evaluated deterministically",
               "supported": True},
              {"claim": "no tool executed", "supported": True},
              {"claim": "text did not downgrade TOOL-B1 risk",
               "supported": monotonic["monotonicity_status"] == "MATCHED"},
              {"claim": "no critical blocker",
               "supported": not blockers}]
    gaps = [b["code"] for b in blockers]
    status_case = ("PRESENT" if status in ("QUALITY_PASS",
                                           "QUALITY_PASS_WITH_WARNINGS")
                   else ("NEEDS_REVIEW" if status == "QUALITY_NEEDS_REVIEW"
                         else "FAILED"))
    case = {
        "quality_assurance_case_id": tool_version_id + "-assurance-case",
        "quality_assurance_case_version": ASSURANCE_CASE_VERSION,
        "tenant_id": tenant_id, "tool_id": tool_id,
        "tool_version_id": tool_version_id, "claims": claims,
        "assumptions": ["TOOL-B1 registry truth is authoritative",
                        "no model is called", "deterministic checks only"],
        "evidence_refs": [assurance_graph_hash],
        "quality_gaps": gaps,
        "residual_risks": ["deterministic checks do not prove full semantic "
                           "safety or complete paraphrase robustness"],
        "critical_blockers": sorted(b["code"] for b in blockers),
        "assurance_graph_ref": assurance_graph_hash,
        "metamorphic_results": metamorphic["metamorphic_status"],
        "mutation_results": mutation["mutation_harness_status"],
        "monotonic_risk_results": monotonic["monotonicity_status"],
        "non_regression_results": (non_regression or {}).get(
            "non_regression_status", "NOT_IMPLEMENTED"),
        "quality_assurance_status": status_case,
    }
    case["quality_assurance_case_hash"] = _core_hash(
        case, "quality_assurance_case_hash")
    return case


# Fields excluded from the descriptor-deterministic quality_report_hash: the
# derived hashes computed after it, every HISTORY-dependent field (non-
# regression + advisory + evidence package + assurance case, which embed the
# non-regression hash) and every PEER-dependent field (planner confusion matrix
# + confusion set). Each excluded object carries its own integrity hash that
# verify checks independently.
_REPORT_HASH_EXCLUDED = (
    "quality_report_hash", "quality_gate_state_hash", "quality_decision_hash",
    "non_regression_summary", "non_regression_proof_hash",
    "non_regression_review_required", "quality_evidence_package",
    "quality_evidence_package_hash", "quality_assurance_case",
    "quality_assurance_case_hash", "planner_confusion_matrix",
    "planner_confusion_hash", "descriptor_confusion_set")


# --- Top-level quality report ----------------------------------------------
def build_quality_report(*, head, version, existing_summaries, previous_report,
                         created_at):
    """Orchestrate the full deterministic quality gate over one TOOL-B1 tool
    version. Returns the quality report dict. Executes nothing."""
    tid = version["tenant_id"]
    tool_id = version["tool_id"]
    tool_version_id = version["tool_version_id"]
    descriptor = version["descriptor"]
    schema_env = version["schema_envelope"]
    effect = version["effect_contract"]
    data_flow = version["data_flow_contract"]
    consent = version["consent_contract"]
    prompt_policy = version["prompt_context_policy"]
    scanner = version["scanner"]
    b1_category = descriptor["category"]
    b1_side_effect = effect["side_effect_class"]
    b1_risk = version["risk_class"]
    b1_status = head["status"]
    b1_prompt_exposure = prompt_policy["effective_exposure"]
    quarantined = head["quarantine_status"] == "QUARANTINED"

    ir = build_formal_ir(
        descriptor=descriptor, tenant_id=tid, tool_id=tool_id,
        tool_version_id=tool_version_id,
        source_descriptor_hash=version["descriptor_hash"],
        b1_category=b1_category, b1_side_effect=b1_side_effect, b1_risk=b1_risk,
        b1_prompt_exposure=b1_prompt_exposure)
    fingerprint = build_semantic_intent_fingerprint(
        descriptor=descriptor, tenant_id=tid, tool_id=tool_id, ir=ir)
    semantic_record = build_canonical_semantic_record(
        descriptor=descriptor, ir=ir, fingerprint=fingerprint, tenant_id=tid,
        tool_id=tool_id, tool_version_id=tool_version_id)

    findings = []
    findings += lint_descriptor(descriptor)
    findings += lint_schema(schema_env, b1_risk=b1_risk)
    findings += lint_prompt_context(descriptor, prompt_policy, scanner=scanner)
    findings += detect_contradictions(
        descriptor, ir, b1_side_effect=b1_side_effect, b1_category=b1_category,
        b1_risk=b1_risk, effect_contract=effect, data_flow=data_flow,
        consent=consent)
    findings += detect_capability_downgrade(descriptor, b1_risk=b1_risk)
    findings += detect_overbroad(ir, b1_category=b1_category)
    # IR mismatch → hard-fail finding.
    if not ir["ir_matches_tool_b1_truth"]:
        findings.append(_finding("formal_ir_mismatch", "BLOCKER",
                                 "FORMAL_IR_MISMATCH", "FORMAL_IR_ALIGNMENT",
                                 "; ".join(ir["ir_mismatch_reasons"])))

    confusion = build_planner_confusion_matrix(
        tool_id=tool_id, tenant_id=tid,
        candidate={"tool_id": tool_id, "tool_key": head["tool_key"],
                   "tool_name": head["tool_name"], "aliases": head.get(
                       "aliases", []),
                   "purpose": descriptor.get("purpose_contract", {}).get(
                       "allowed_purposes", []),
                   "risk_rank": _tr.RISK_RANK.get(b1_risk, 0),
                   "side_effect_rank": effect.get("side_effect_rank", 0)},
        existing=existing_summaries)
    counterfactual = counterfactual_planner_simulation(
        tool_id=tool_id, tenant_id=tid, category=b1_category, ir=ir,
        b1_side_effect=b1_side_effect)
    findings += detect_tool_selection_misrouting(confusion, counterfactual)

    boundary = build_selection_boundary(
        tool_id=tool_id, tenant_id=tid, b1_status=b1_status, b1_risk=b1_risk,
        quarantined=quarantined, prompt_exposure=b1_prompt_exposure,
        ir_mismatch=not ir["ir_matches_tool_b1_truth"])
    if boundary["minimal_context_status"] == "NEVER_EXPOSE" and quarantined:
        findings.append(_finding("context_never_expose", "BLOCKER",
                                 "CONTEXT_EXPOSURE_UNSAFE", "PROMPT_CONTEXT_SAFETY",
                                 "descriptor is never safe for model context"))

    mutation = mutation_harness(tool_id=tool_id, tenant_id=tid)
    if mutation["mutation_harness_status"] != "CLEAR":
        findings.append(_finding("mutation_weakness", "BLOCKER",
                                 "ADVERSARIAL_MUTATION_FAIL",
                                 "ADVERSARIAL_MUTATION_ROBUSTNESS",
                                 "a dangerous mutation bypassed detection"))
    metamorphic = metamorphic_testing(tool_id=tool_id, tenant_id=tid)
    if metamorphic["metamorphic_status"] != "PASSED":
        findings.append(_finding("metamorphic_failure", "BLOCKER",
                                 "METAMORPHIC_FAILED", "METAMORPHIC_SAFETY",
                                 "a metamorphic relation failed"))
    monotonic = monotonic_risk_proof(
        tenant_id=tid, tool_id=tool_id, tool_version_id=tool_version_id,
        b1_risk=b1_risk, b1_side_effect=b1_side_effect, ir=ir)
    if monotonic["monotonicity_status"] != "MATCHED":
        findings.append(_finding("monotonic_risk_fail", "BLOCKER",
                                 "CAPABILITY_DOWNGRADE", "MONOTONIC_RISK",
                                 "risk/effect fell below TOOL-B1 truth"))

    blockers = [f for f in findings if f["severity"] == "BLOCKER"]
    warnings = [f for f in findings if f["severity"] == "WARNING"]
    reviews = [f for f in findings if f["severity"] == "REVIEW"]

    source_hashes = {
        "tool_descriptor_hash": version["descriptor_hash"],
        "input_schema_hash": schema_env["input_schema_hash"],
        "output_schema_hash": schema_env["output_schema_hash"],
        "effect_contract_hash": effect["effect_contract_hash"],
        "data_flow_contract_hash": data_flow["data_flow_contract_hash"],
        "purpose_contract_hash": descriptor["purpose_contract"][
            "purpose_contract_hash"],
        "prompt_context_policy_hash": prompt_policy[
            "prompt_context_policy_hash"],
        "security_case_hash": version["security_case"]["security_case_hash"],
        "negative_capability_proof_hash": version["negative_capabilities"][
            "negative_capability_hash"],
        "policy_capsule_hash": version["policy_capsule"]["policy_capsule_hash"],
        "risk_capsule_hash": version["risk_capsule"]["risk_capsule_hash"],
    }
    linter_result = {"findings": findings}
    linter_hash = _sha(linter_result)

    checks = [
        {"id": "linter", "type": "LINTER_RESULT", "source":
         "tool_descriptor_hash", "result": "run"},
        {"id": "schema", "type": "SCHEMA_CHECK", "source": "input_schema_hash",
         "result": "run"},
        {"id": "contradiction", "type": "CONTRADICTION_CHECK", "source":
         "effect_contract_hash", "result": "run"},
        {"id": "prompt_context", "type": "PROMPT_CONTEXT_CHECK", "source":
         "prompt_context_policy_hash", "result": "run"},
        {"id": "mutation", "type": "MUTATION_CHECK", "source":
         "tool_descriptor_hash", "result": mutation["mutation_harness_status"]},
        {"id": "metamorphic", "type": "METAMORPHIC_CHECK", "source":
         "tool_descriptor_hash", "result": metamorphic["metamorphic_status"]},
        {"id": "monotonic", "type": "MONOTONIC_RISK_CHECK", "source":
         "risk_capsule_hash", "result": monotonic["monotonicity_status"]},
        {"id": "counterfactual", "type": "COUNTERFACTUAL_CHECK", "source":
         "policy_capsule_hash", "result": (
             "misrouting" if counterfactual["misrouting_detected"] else "ok")},
    ]
    positive_claims = [
        {"text": "descriptor is clear enough for planner use",
         "supported_by": ["linter"] if not blockers else []},
        {"text": "descriptor risk not downgraded",
         "supported_by": ["monotonic"] if monotonic[
             "monotonicity_status"] == "MATCHED" else []},
        {"text": "descriptor robust to adversarial mutation",
         "supported_by": ["mutation"] if mutation[
             "mutation_harness_status"] == "CLEAR" else []},
    ]
    assurance_graph = build_assurance_graph(
        tool_id=tool_id, tenant_id=tid, tool_version_id=tool_version_id,
        source_hashes=source_hashes, checks=checks, blockers=blockers,
        warnings=warnings, positive_claims=positive_claims)
    if assurance_graph["assurance_graph_status"] == "FAILED":
        findings.append(_finding("assurance_graph_failed", "BLOCKER",
                                 "ASSURANCE_GRAPH_FAILED",
                                 "ASSURANCE_GRAPH_COMPLETENESS",
                                 "assurance graph is cyclic/inconsistent"))
        blockers = [f for f in findings if f["severity"] == "BLOCKER"]

    score_vector = compute_score_vector(
        findings=findings, ir=ir, assurance_graph=assurance_graph,
        mutation=mutation, metamorphic=metamorphic, monotonic=monotonic,
        non_regression=None, boundary=boundary, confusion=confusion)

    status, dominant_cat = quality_dominant_status(findings)
    # No-Goodhart: a security-blocked TOOL-B1 state can never yield PASS.
    if b1_status in _SECURITY_BLOCKED_STATUSES and status in (
            "QUALITY_PASS", "QUALITY_PASS_WITH_WARNINGS"):
        status = "QUALITY_BLOCKED"
        dominant_cat = "POLICY_MISMATCH"

    safety_score = 0 if blockers else (3 if (warnings or reviews) else 5)
    report_hash_core = {
        "tool_descriptor_hash": version["descriptor_hash"],
        "quality_status": status, "score_total": score_vector["total"],
        "blockers": sorted(b["code"] for b in blockers),
        "ir_hash": ir["formal_descriptor_ir_hash"],
        "assurance_graph_hash": assurance_graph["assurance_graph_hash"],
        **source_hashes,
    }

    non_regression = non_regression_proof(
        tenant_id=tid, tool_id=tool_id, tool_version_id=tool_version_id,
        previous=previous_report,
        current_blockers=blockers,
        current_report_hash=_sha(report_hash_core),
        current_score_total=score_vector["total"], current_risk=monotonic[
            "quality_detected_risk_class"],
        current_descriptor_hash=version["descriptor_hash"])
    # Non-regression is HISTORY-dependent, so it must not flip the
    # descriptor-deterministic quality_status (that would break "same descriptor
    # → same report hash"). A NEEDS_REVIEW regression is surfaced as a separate
    # advisory flag (excluded from the report hash) that a consumer combines
    # with the status; it never turns a real hard-fail into a pass.
    non_regression_review_required = (
        non_regression["non_regression_status"] == "NEEDS_REVIEW")

    evidence = build_evidence_package(
        tenant_id=tid, tool_id=tool_id, tool_version_id=tool_version_id,
        source_hashes=source_hashes, ir_hash=ir["formal_descriptor_ir_hash"],
        assurance_graph_hash=assurance_graph["assurance_graph_hash"],
        score_vector_hash=score_vector["score_vector_hash"],
        fingerprint_hash=fingerprint["semantic_intent_fingerprint_hash"],
        mutation_hash=mutation["mutation_harness_hash"],
        metamorphic_hash=metamorphic["metamorphic_test_hash"],
        monotonic_hash=monotonic["monotonic_risk_proof_hash"],
        non_regression_hash=non_regression["non_regression_proof_hash"],
        linter_hash=linter_hash, blockers=blockers, warnings=warnings)
    assurance_case = build_assurance_case(
        tenant_id=tid, tool_id=tool_id, tool_version_id=tool_version_id,
        status=status, blockers=blockers, warnings=warnings,
        assurance_graph_hash=assurance_graph["assurance_graph_hash"],
        mutation=mutation, metamorphic=metamorphic, monotonic=monotonic,
        non_regression=non_regression)

    report = {
        "quality_report_id": tool_version_id + "-quality",
        "tenant_id": tid, "tool_id": tool_id,
        "tool_version_id": tool_version_id,
        "tool_descriptor_hash": version["descriptor_hash"],
        "tool_policy_capsule_hash": source_hashes["policy_capsule_hash"],
        "tool_risk_capsule_hash": source_hashes["risk_capsule_hash"],
        "tool_security_case_hash": source_hashes["security_case_hash"],
        "tool_negative_capability_proof_hash": source_hashes[
            "negative_capability_proof_hash"],
        "tool_prompt_context_policy_hash": source_hashes[
            "prompt_context_policy_hash"],
        "quality_gate_version": QUALITY_GATE_VERSION,
        "quality_status": status, "dominant_blocker_category": dominant_cat,
        "quality_score_vector": score_vector["scores"],
        "quality_score_total": score_vector["total"],
        "descriptor_safety_score": safety_score,
        "formal_descriptor_ir": ir,
        "canonical_descriptor_semantic_record": semantic_record,
        "descriptor_assurance_graph": assurance_graph,
        "semantic_intent_fingerprint": fingerprint,
        "quality_blockers": blockers, "quality_warnings": warnings,
        "quality_recommendations": _recommendations(blockers, warnings),
        "quality_evidence_package": evidence,
        "quality_assurance_case": assurance_case,
        "planner_confusion_matrix": confusion,
        "descriptor_confusion_set": confusion["confusable_tool_ids"],
        "planner_selection_boundary": boundary,
        "planner_misuse_flags": [f["code"] for f in findings
                                 if f["category"] == "PLANNER_MISUSE"],
        "tool_selection_misrouting_flags": [
            f["code"] for f in findings
            if f["dimension"] == "TOOL_SELECTION_MISROUTING_RISK"],
        "ambiguity_flags": [f["code"] for f in findings
                            if f["category"] == "AMBIGUOUS"],
        "contradiction_flags": [f["code"] for f in findings
                                if f["category"] == "CONTRADICTION"],
        "hidden_instruction_flags": [f["code"] for f in findings
                                     if f["category"] == "HIDDEN_INSTRUCTION"],
        "overbroad_capability_flags": [f["code"] for f in findings
                                       if f["category"] == "OVERBROAD"],
        "overclaim_flags": [f["code"] for f in findings
                            if f["category"] == "OVERCLAIM"],
        "capability_downgrade_flags": [f["code"] for f in findings
                                       if f["category"] == "CAPABILITY_DOWNGRADE"],
        "side_effect_mismatch_flags": [f["code"] for f in findings
                                       if f["category"] == "SIDE_EFFECT_MISMATCH"],
        "schema_quality_flags": [f["code"] for f in findings
                                 if f["category"] == "SCHEMA_MISMATCH"],
        "prompt_context_flags": [f["code"] for f in findings
                                 if f["dimension"] == "PROMPT_CONTEXT_SAFETY"],
        "counterfactual_planner": counterfactual,
        "mutation_test_summary": {"status": mutation["mutation_harness_status"],
                                  "cases": mutation["mutation_cases_run"],
                                  "findings": len(mutation["mutation_findings"])},
        "metamorphic_test_summary": {
            "status": metamorphic["metamorphic_status"],
            "failures": metamorphic["metamorphic_failures"]},
        "monotonic_risk_summary": monotonic,
        "non_regression_summary": non_regression,
        "quality_evidence_package_hash": evidence[
            "quality_evidence_package_hash"],
        "quality_assurance_case_hash": assurance_case[
            "quality_assurance_case_hash"],
        "formal_descriptor_ir_hash": ir["formal_descriptor_ir_hash"],
        "canonical_semantic_record_hash": semantic_record[
            "canonical_semantic_record_hash"],
        "assurance_graph_hash": assurance_graph["assurance_graph_hash"],
        "score_vector_hash": score_vector["score_vector_hash"],
        "semantic_intent_fingerprint_hash": fingerprint[
            "semantic_intent_fingerprint_hash"],
        "linter_result_hash": linter_hash,
        "planner_confusion_hash": confusion["planner_confusion_hash"],
        "planner_selection_boundary_hash": boundary["selection_boundary_hash"],
        "counterfactual_planner_proof_hash": counterfactual[
            "counterfactual_planner_proof_hash"],
        "mutation_harness_hash": mutation["mutation_harness_hash"],
        "metamorphic_test_hash": metamorphic["metamorphic_test_hash"],
        "monotonic_risk_proof_hash": monotonic["monotonic_risk_proof_hash"],
        "non_regression_proof_hash": non_regression["non_regression_proof_hash"],
        "non_regression_review_required": non_regression_review_required,
        "created_at": created_at, "honesty_labels": HONESTY_LABELS,
    }
    # The report hash is deterministic given the DESCRIPTOR + current registry
    # snapshot: it excludes the derived hashes computed after it, plus every
    # HISTORY-dependent field (non-regression, its advisory flag, and the
    # evidence package / assurance case which embed the non-regression hash) and
    # every PEER-dependent field (the planner confusion matrix + confusion set,
    # which depend on sibling tools). Each excluded object carries its own
    # integrity hash that verify checks independently, so re-checking an
    # unchanged descriptor against an unchanged registry yields an identical
    # report hash while sub-object tampering is still caught.
    report["quality_report_hash"] = _core_hash(
        report, *_REPORT_HASH_EXCLUDED)
    report["quality_decision_hash"] = _sha(
        {"status": status, "descriptor_hash": version["descriptor_hash"],
         "blockers": sorted(b["code"] for b in blockers)})
    report["quality_gate_state_hash"] = _sha({
        "tool_id": tool_id, "tool_version_id": tool_version_id,
        "quality_status": status,
        "quality_report_hash": report["quality_report_hash"],
        "quality_decision_hash": report["quality_decision_hash"]})
    return report


def _recommendations(blockers, warnings):
    recs = []
    for f in blockers + warnings:
        recs.append({"code": f["code"], "dimension": f["dimension"],
                     "hint": f["detail"]})
    return recs


# --- Quality binding event ledger ------------------------------------------
QUALITY_EVENT_TYPES = {
    "QUALITY_CHECK_STARTED", "QUALITY_CHECK_COMPLETED", "QUALITY_PASS_RECORDED",
    "QUALITY_FAIL_RECORDED", "QUALITY_BLOCKER_RECORDED",
    "QUALITY_MUTATION_FAILED", "QUALITY_METAMORPHIC_FAILED",
    "QUALITY_IR_MISMATCH", "QUALITY_ASSURANCE_GRAPH_FAILED",
    "QUALITY_BINDING_UPDATED",
}


def build_quality_event(*, event_type, tool_id, tenant_id, actor_id, actor_type,
                        quality_gate_state_hash, previous_event_hash, sequence,
                        detail, created_at) -> dict:
    if event_type not in QUALITY_EVENT_TYPES:
        raise ValueError(f"unknown quality event_type {event_type}")
    ev = {
        "quality_event_version": QUALITY_EVENT_VERSION, "event_type": event_type,
        "tool_id": tool_id, "tenant_id": tenant_id, "actor_id": actor_id,
        "actor_type": actor_type,
        "quality_gate_state_hash": quality_gate_state_hash,
        "previous_event_hash": previous_event_hash or GENESIS,
        "sequence": sequence, "detail": detail, "created_at": created_at,
    }
    ev["event_hash"] = _sha({k: v for k, v in ev.items() if k != "event_hash"})
    return ev

