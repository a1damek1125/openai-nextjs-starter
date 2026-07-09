"""Finalis ViktorAI Zero-Trust Tool Capability Governance Registry (TOOL-B1).

Pure, deterministic logic for a security-first internal registry of tool
CAPABILITY DESCRIPTORS destined for a FUTURE Tool Broker.

This registry DESCRIBES and GOVERNS tool capabilities. It is NOT a Tool Broker,
NOT a tool executor, NOT an MCP server or client, and it calls NO external
provider, NO LLM, NO payment rail, NO CRM, and sends NO customer message. There
is NO execute endpoint and NO dry-run execution anywhere in this mission. A
descriptor being ADMITTED or AVAILABLE_FOR_FUTURE_BROKER means only that a
future broker MAY consider it — nothing here runs it.

Descriptor content is UNTRUSTED declared input (a tool descriptor is a classic
prompt-injection / tool-poisoning carrier). Descriptor text can never change
server policy: the scanners and detectors are advisory-to-quarantine only, and
admission is fail-closed — a descriptor is admissible only when every admission
invariant holds. Hard-fail dominance always wins over any positive signal.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata

TOOL_MODEL_VERSION = "finalis-tool-descriptor-v1"
SCHEMA_ENVELOPE_VERSION = "finalis-tool-schema-envelope-v1"
EFFECT_CONTRACT_VERSION = "finalis-tool-effect-contract-v1"
DATA_FLOW_CONTRACT_VERSION = "finalis-tool-data-flow-contract-v1"
PURPOSE_CONTRACT_VERSION = "finalis-tool-purpose-contract-v1"
CONSENT_CONTRACT_VERSION = "finalis-tool-consent-contract-v1"
PROMPT_CONTEXT_POLICY_VERSION = "finalis-tool-prompt-context-policy-v1"
TBOM_VERSION = "finalis-tbom-v1"
SECURITY_CASE_VERSION = "finalis-tool-security-case-v1"
NEGATIVE_CAPABILITY_VERSION = "finalis-tool-negative-capability-v1"
INVARIANT_MATRIX_VERSION = "finalis-tool-invariant-matrix-v1"
POLICY_CAPSULE_VERSION = "finalis-tool-policy-capsule-v1"
RISK_CAPSULE_VERSION = "finalis-tool-risk-capsule-v1"
ADMISSION_PACKAGE_VERSION = "finalis-tool-admission-package-v1"
LATTICE_VERSION = "finalis-tool-capability-lattice-v1"
REGISTRY_EVENT_VERSION = "finalis-tool-registry-event-v1"
SCANNER_VERSION = "finalis-tool-descriptor-scanner-v1"
GENESIS = "0" * 64

# --- Taxonomies ------------------------------------------------------------
TOOL_CATEGORIES = {
    "DATA_READ", "DATA_SEARCH", "INTERNAL_COMPUTE", "INTERNAL_WRITE",
    "ANALYTICS", "SCHEDULING", "NOTIFICATION_INTERNAL", "CUSTOMER_MESSAGING",
    "PAYMENT", "CRM_WRITE", "EVIDENCE_ACCESS", "EVIDENCE_MUTATION",
    "DOCUMENT_EXPORT", "EXTERNAL_API_READ", "EXTERNAL_API_WRITE",
    "LLM_INFERENCE", "FILE_IO", "WORKFLOW_CONTROL", "IDENTITY_ACCESS",
    "ADMIN_OPERATION", "NOT_IMPLEMENTED_PLACEHOLDER",
}
# Categories that are never admissible in this mission — a future-broker
# fantasy that must be refused, never faked as working.
FORBIDDEN_CATEGORIES = {
    "PAYMENT", "CRM_WRITE", "EVIDENCE_MUTATION", "CUSTOMER_MESSAGING",
    "DOCUMENT_EXPORT", "IDENTITY_ACCESS", "ADMIN_OPERATION",
}

SIDE_EFFECT_CLASSES = {
    "PURE_READ", "INTERNAL_WRITE", "EXTERNAL_READ", "EXTERNAL_WRITE",
    "CUSTOMER_MESSAGING", "PAYMENT_MOVEMENT", "CRM_MUTATION",
    "EVIDENCE_MUTATION", "IRREVERSIBLE", "DESTRUCTIVE",
}
# Side-effect classes a descriptor may never DECLARE and still be admitted;
# their presence forces FORBIDDEN_CAPABILITY.
FORBIDDEN_SIDE_EFFECTS = {
    "CUSTOMER_MESSAGING", "PAYMENT_MOVEMENT", "CRM_MUTATION",
    "EVIDENCE_MUTATION", "DESTRUCTIVE",
}
# Ordered from least to most dangerous — used for escalation / rug-pull checks.
SIDE_EFFECT_RANK = {
    "PURE_READ": 0, "INTERNAL_WRITE": 1, "EXTERNAL_READ": 2,
    "EXTERNAL_WRITE": 3, "CUSTOMER_MESSAGING": 4, "CRM_MUTATION": 5,
    "EVIDENCE_MUTATION": 6, "PAYMENT_MOVEMENT": 7, "IRREVERSIBLE": 8,
    "DESTRUCTIVE": 9,
}

RISK_CLASSES = {"TRIVIAL", "LOW", "MEDIUM", "HIGH", "CRITICAL", "PROHIBITED"}
RISK_RANK = {"TRIVIAL": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4,
             "PROHIBITED": 5}

DATA_CLASSES = {
    "PUBLIC", "INTERNAL", "PII", "SENSITIVE_PII", "PAYMENT_DATA",
    "CREDENTIALS", "EVIDENCE", "LEGAL", "SECRET",
}
# Data classes that must never leave the tenant boundary (egress-forbidden).
EGRESS_FORBIDDEN_DATA = {"CREDENTIALS", "SECRET", "PAYMENT_DATA",
                         "SENSITIVE_PII", "EVIDENCE", "LEGAL"}

TOOL_STATUSES = {
    "DRAFT", "NEEDS_REVIEW", "ADMITTED", "AVAILABLE_FOR_FUTURE_BROKER",
    "BLOCKED", "QUARANTINED", "DISABLED", "DEPRECATED", "SUPERSEDED",
    "TAMPERED", "RUG_PULL_DETECTED", "DRIFT_DETECTED", "FORBIDDEN_CAPABILITY",
    "CROSS_TENANT_REJECTED", "NOT_IMPLEMENTED",
}
# Terminal / non-reversible-by-normal-flow statuses.
TERMINAL_STATUSES = {"SUPERSEDED", "TAMPERED", "NOT_IMPLEMENTED"}
# Statuses in which a descriptor may never be offered to a future broker.
NON_OFFERABLE_STATUSES = {
    "DRAFT", "NEEDS_REVIEW", "BLOCKED", "QUARANTINED", "DISABLED",
    "DEPRECATED", "SUPERSEDED", "TAMPERED", "RUG_PULL_DETECTED",
    "DRIFT_DETECTED", "FORBIDDEN_CAPABILITY", "CROSS_TENANT_REJECTED",
    "NOT_IMPLEMENTED",
}

# Hard-fail dominance: the FIRST matching status (lowest index) wins over every
# status after it and over every positive admission signal. A single security
# hard-fail can never be out-voted by an otherwise-clean descriptor.
STATUS_DOMINANCE = [
    "TAMPERED", "RUG_PULL_DETECTED", "DRIFT_DETECTED", "CROSS_TENANT_REJECTED",
    "FORBIDDEN_CAPABILITY", "QUARANTINED", "BLOCKED", "NEEDS_REVIEW", "DRAFT",
    "DISABLED", "DEPRECATED", "SUPERSEDED", "ADMITTED",
    "AVAILABLE_FOR_FUTURE_BROKER", "NOT_IMPLEMENTED",
]

TRUST_TIERS = {
    "UNTRUSTED_DECLARED", "AI_PROPOSED_UNVERIFIED", "HUMAN_REVIEW_REQUIRED",
    "HUMAN_REVIEWED", "INTERNAL_VERIFIED", "REFERENCE_ONLY",
    "QUARANTINED", "REVOKED",
}

CONSENT_REQUIREMENTS = {"NONE", "IMPLIED_ELIGIBLE", "EXPLICIT_REQUIRED",
                        "EXPLICIT_NON_OVERRIDABLE", "PROHIBITED"}
PURPOSE_TAGS = {
    "CASE_TRIAGE", "DRAFTING", "RESEARCH", "SCHEDULING_SUPPORT",
    "INTERNAL_ANALYTICS", "SUMMARIZATION", "QUALITY_REVIEW",
    "MARKETING", "COLLECTIONS", "LEGAL_ACTION", "DATA_EXPORT",
}
FORBIDDEN_PURPOSES = {"MARKETING", "COLLECTIONS", "LEGAL_ACTION", "DATA_EXPORT"}

PROMPT_CONTEXT_EXPOSURE = {
    "NEVER_EXPOSE", "NAME_ONLY", "NAME_AND_SUMMARY", "SCHEMA_SHAPE_ONLY",
    "FULL_DESCRIPTOR",
}

HONESTY_LABELS = [
    "This is a tool capability registry, not a Tool Broker.",
    "Registering a tool descriptor does not execute the tool.",
    "There is no execute endpoint and no dry-run execution in this mission.",
    "The registry calls no external provider, no LLM and no MCP server.",
    "The registry sends no customer message, moves no payment and writes no "
    "CRM.",
    "The registry rewrites no evidence and exports no document.",
    "Admission means a FUTURE broker may consider the tool; nothing runs it "
    "here.",
    "Tool descriptor content is untrusted declared input and can carry "
    "tool-poisoning; it never changes server policy.",
    "Descriptor scanning is deterministic pattern matching, not an LLM "
    "judgement.",
    "Admission is fail-closed: any hard-fail signal blocks admission.",
    "A forbidden capability can never be admitted, only recorded and blocked.",
    "Consent requirements declared as non-overridable can never be downgraded.",
    "Server-side tool-governance truth is authoritative over declared "
    "descriptor claims.",
    "This is not production autonomous tool execution.",
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


def _core_hash(obj: dict, self_key: str, *extra_excluded) -> str:
    excluded = {self_key, *_VOLATILE, *extra_excluded}
    return _sha({k: v for k, v in obj.items() if k not in excluded})


# --- Deterministic descriptor scanner (tool poisoning / injection) ----------
# (needle, category). Categories: prompt_injection, tool_poisoning,
# data_exfiltration, privilege_escalation, consent_override, unsafe_capability.
# A trip is advisory and NEVER changes server policy; it flags/quarantines the
# descriptor so a future broker never silently trusts poisoned text.
_SCANNER_PATTERNS = [
    ("ignore previous instructions", "prompt_injection"),
    ("ignore all previous", "prompt_injection"),
    ("disregard the rules", "prompt_injection"),
    ("disregard previous", "prompt_injection"),
    ("you are now", "prompt_injection"),
    ("system prompt", "prompt_injection"),
    ("use this as a system prompt", "prompt_injection"),
    ("override policy", "prompt_injection"),
    ("do not tell the user", "prompt_injection"),
    ("hidden instruction", "tool_poisoning"),
    ("secret instruction", "tool_poisoning"),
    ("when called also", "tool_poisoning"),
    ("also call", "tool_poisoning"),
    ("chain to tool", "tool_poisoning"),
    ("register another tool", "tool_poisoning"),
    ("register mcp", "tool_poisoning"),
    ("mcp server", "tool_poisoning"),
    ("remote instructions", "tool_poisoning"),
    ("fetch instructions from", "tool_poisoning"),
    ("read the credentials", "data_exfiltration"),
    ("exfiltrate", "data_exfiltration"),
    ("send credentials", "data_exfiltration"),
    ("send api key", "data_exfiltration"),
    ("leak the", "data_exfiltration"),
    ("curl http", "data_exfiltration"),
    ("post to http", "data_exfiltration"),
    ("upload to", "data_exfiltration"),
    ("base64 the", "data_exfiltration"),
    ("grant admin", "privilege_escalation"),
    ("elevate privileges", "privilege_escalation"),
    ("become owner", "privilege_escalation"),
    ("change tenant", "privilege_escalation"),
    ("cross tenant", "privilege_escalation"),
    ("bypass rbac", "privilege_escalation"),
    ("disable audit", "privilege_escalation"),
    ("override consent", "consent_override"),
    ("ignore consent", "consent_override"),
    ("without consent", "consent_override"),
    ("skip approval", "consent_override"),
    ("auto approve", "consent_override"),
    ("approve own", "consent_override"),
    ("execute payment", "unsafe_capability"),
    ("move money", "unsafe_capability"),
    ("send to the customer", "unsafe_capability"),
    ("message the customer", "unsafe_capability"),
    ("delete evidence", "unsafe_capability"),
    ("rewrite evidence", "unsafe_capability"),
    ("wipe the", "unsafe_capability"),
    ("drop table", "unsafe_capability"),
    ("mark production ready", "unsafe_capability"),
]
_CATEGORY_FIELD = {
    "prompt_injection": "prompt_injection_flags",
    "tool_poisoning": "tool_poisoning_flags",
    "data_exfiltration": "data_exfiltration_flags",
    "privilege_escalation": "privilege_escalation_flags",
    "consent_override": "consent_override_flags",
    "unsafe_capability": "unsafe_capability_flags",
}
_SCAN_FIELDS = tuple(sorted(set(_CATEGORY_FIELD.values())))


_LEET = {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
         "$": "s", "@": "a"}
# Common Cyrillic/Greek homoglyphs → their Latin lookalike. NFKC does NOT fold
# these (they are distinct letters, not compatibility forms), so a confusable
# map is required to stop homoglyph evasion ("ignоre" with a Cyrillic о).
_CONFUSABLES = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
    "х": "x", "у": "y", "к": "k", "м": "m", "т": "t",
    "н": "h", "в": "b", "і": "i", "ѕ": "s", "Ѕ": "s",
    "ο": "o", "α": "a", "ν": "v", "ε": "e", "ρ": "p",
    "τ": "t", "ι": "i", "κ": "k", "Ι": "i", "Ο": "o",
}
_FOLD = str.maketrans({**_LEET, **_CONFUSABLES})


def _normalize(text: str) -> str:
    """Lowercase and collapse every non-alphanumeric run to a single space so
    spacing / punctuation / newline tricks cannot evade the scanner. Also apply
    NFKC normalization + leet + homoglyph folding so leetspeak ("1gnore",
    "m0ve money") and Cyrillic/Greek homoglyph ("ignоre") variants still match.
    This only ever TIGHTENS detection; descriptor text never loosens policy."""
    folded = unicodedata.normalize("NFKC", text or "").lower().translate(_FOLD)
    return " " + re.sub(r"[^a-z0-9]+", " ", folded) + " "


def scan_descriptor(*, tool_name="", tool_summary="", tool_description="",
                    parameter_texts=None, purpose_texts=None,
                    output_texts=None, extra_texts=None) -> dict:
    """Deterministic, pattern-based descriptor scan across every declared text
    surface (name, summary, description, parameter descriptions, purpose and
    output notes). No LLM. Returns advisory flags + a quarantine verdict; the
    descriptor is preserved regardless."""
    surfaces = [tool_name, tool_summary, tool_description]
    surfaces += list(parameter_texts or [])
    surfaces += list(purpose_texts or [])
    surfaces += list(output_texts or [])
    surfaces += list(extra_texts or [])
    blob = " ".join(_normalize(s) for s in surfaces)
    found = {f: [] for f in _SCAN_FIELDS}
    for needle, category in _SCANNER_PATTERNS:
        if needle in blob:
            field = _CATEGORY_FIELD[category]
            if needle not in found[field]:
                found[field].append(needle)
    any_flag = any(found[f] for f in _SCAN_FIELDS)
    result = {
        **{f: sorted(found[f]) for f in _SCAN_FIELDS},
        "quarantine_status": "QUARANTINED" if any_flag else "CLEAN",
        "quarantine_reason": ("descriptor poisoning patterns detected: "
                              + ", ".join(sorted(n for f in _SCAN_FIELDS
                                                 for n in found[f]))
                              if any_flag else None),
        "scanner_version": SCANNER_VERSION,
    }
    result["scanner_hash"] = _core_hash(result, "scanner_hash")
    return result


# --- Schema envelope -------------------------------------------------------
def build_schema_envelope(*, input_schema, output_schema, parameters=None,
                          declared_side_effects=None,
                          declared_data_reads=None,
                          declared_data_writes=None) -> dict:
    """Wrap the tool's declared JSON-schema shapes with content hashes. The
    schema is DECLARED, untrusted, and never validated by execution here."""
    params = []
    for p in parameters or []:
        # `default` / `example` are preserved (as declared strings) so the
        # downstream quality gate can inspect them for dangerous/poisoned
        # content; they are DECLARED and never evaluated or executed here.
        params.append({
            "name": str(p.get("name", "")),
            "type": str(p.get("type", "string")),
            "required": bool(p.get("required", False)),
            "description": str(p.get("description", "")),
            "data_class": p.get("data_class", "INTERNAL"),
            "sensitive": bool(p.get("sensitive", False)),
            "default": p.get("default"),
            "example": p.get("example"),
        })
    env = {
        "schema_envelope_version": SCHEMA_ENVELOPE_VERSION,
        "input_schema": input_schema or {}, "output_schema": output_schema or {},
        "input_schema_hash": _sha(input_schema or {}),
        "output_schema_hash": _sha(output_schema or {}),
        "parameters": params,
        "declared_side_effects": sorted(set(declared_side_effects or [])),
        "declared_data_reads": sorted(set(declared_data_reads or [])),
        "declared_data_writes": sorted(set(declared_data_writes or [])),
        "validated_by_execution": False,
    }
    env["schema_envelope_hash"] = _core_hash(env, "schema_envelope_hash")
    return env


# --- Effect contract -------------------------------------------------------
def build_effect_contract(*, side_effect_class, reversibility, idempotent,
                          blast_radius, touches_external, touches_customer,
                          touches_payment, touches_crm, touches_evidence,
                          declared_summary="") -> dict:
    if side_effect_class not in SIDE_EFFECT_CLASSES:
        raise ValueError(f"unknown side_effect_class {side_effect_class}")
    contract = {
        "effect_contract_version": EFFECT_CONTRACT_VERSION,
        "side_effect_class": side_effect_class,
        "side_effect_rank": SIDE_EFFECT_RANK[side_effect_class],
        "reversibility": reversibility,             # REVERSIBLE / IRREVERSIBLE
        "idempotent": bool(idempotent),
        "blast_radius": blast_radius,               # SELF / TENANT / EXTERNAL
        "touches_external": bool(touches_external),
        "touches_customer": bool(touches_customer),
        "touches_payment": bool(touches_payment),
        "touches_crm": bool(touches_crm),
        "touches_evidence": bool(touches_evidence),
        "declared_summary": declared_summary,
        "execution_performed": False,
    }
    contract["effect_contract_hash"] = _core_hash(contract,
                                                  "effect_contract_hash")
    return contract


# --- Data-flow contract ----------------------------------------------------
def build_data_flow_contract(*, reads_data_classes, writes_data_classes,
                             egress_targets, ingress_sources,
                             crosses_tenant_boundary, retains_data,
                             prompt_context_inputs=None) -> dict:
    reads = sorted(set(reads_data_classes or []))
    writes = sorted(set(writes_data_classes or []))
    egress = sorted(set(egress_targets or []))
    # Any egress-forbidden data class that leaves via a non-empty egress target
    # is an exfiltration hazard flag (advisory to the risk/admission layer).
    egressed_forbidden = sorted(
        (set(reads) | set(writes)) & EGRESS_FORBIDDEN_DATA) if egress else []
    contract = {
        "data_flow_contract_version": DATA_FLOW_CONTRACT_VERSION,
        "reads_data_classes": reads, "writes_data_classes": writes,
        "egress_targets": egress,
        "ingress_sources": sorted(set(ingress_sources or [])),
        "crosses_tenant_boundary": bool(crosses_tenant_boundary),
        "retains_data": bool(retains_data),
        "prompt_context_inputs": sorted(set(prompt_context_inputs or [])),
        "egress_forbidden_data_flagged": egressed_forbidden,
        "exfiltration_hazard": bool(egressed_forbidden)
        or bool(crosses_tenant_boundary),
    }
    contract["data_flow_contract_hash"] = _core_hash(
        contract, "data_flow_contract_hash")
    return contract


# --- Purpose contract ------------------------------------------------------
def build_purpose_contract(*, allowed_purposes, forbidden_purposes=None,
                           declared_intent="") -> dict:
    allowed = sorted(set(allowed_purposes or []))
    # Forbidden purposes always include the global forbidden set — a descriptor
    # cannot opt out of them, and any overlap with allowed is a conflict.
    forbidden = sorted(set(forbidden_purposes or []) | FORBIDDEN_PURPOSES)
    conflict = sorted(set(allowed) & set(forbidden))
    contract = {
        "purpose_contract_version": PURPOSE_CONTRACT_VERSION,
        "allowed_purposes": allowed, "forbidden_purposes": forbidden,
        "declared_intent": declared_intent,
        "purpose_conflict": conflict,
        "has_forbidden_purpose": bool(conflict),
    }
    contract["purpose_contract_hash"] = _core_hash(contract,
                                                   "purpose_contract_hash")
    return contract


# --- Consent contract ------------------------------------------------------
def build_consent_contract(*, consent_requirement, non_overridable,
                           lawful_basis="", declared_note="") -> dict:
    if consent_requirement not in CONSENT_REQUIREMENTS:
        raise ValueError(f"unknown consent_requirement {consent_requirement}")
    # EXPLICIT_NON_OVERRIDABLE and PROHIBITED force non_overridable True — a
    # descriptor can raise the bar but never lower a non-overridable one.
    forced = consent_requirement in ("EXPLICIT_NON_OVERRIDABLE", "PROHIBITED")
    contract = {
        "consent_contract_version": CONSENT_CONTRACT_VERSION,
        "consent_requirement": consent_requirement,
        "non_overridable": bool(non_overridable) or forced,
        "lawful_basis": lawful_basis, "declared_note": declared_note,
        "consent_can_be_overridden": False,
    }
    contract["consent_contract_hash"] = _core_hash(contract,
                                                   "consent_contract_hash")
    return contract


# --- Prompt-context exposure policy ----------------------------------------
def build_prompt_context_policy(*, exposure_level, category, side_effect_class,
                                data_flow) -> dict:
    """Deterministic, fail-closed exposure policy: the MOST restrictive of the
    declared exposure and what the capability class allows. Sensitive data,
    forbidden categories and dangerous side-effects clamp exposure down."""
    if exposure_level not in PROMPT_CONTEXT_EXPOSURE:
        raise ValueError(f"unknown exposure_level {exposure_level}")
    order = ["NEVER_EXPOSE", "NAME_ONLY", "NAME_AND_SUMMARY",
             "SCHEMA_SHAPE_ONLY", "FULL_DESCRIPTOR"]
    declared_idx = order.index(exposure_level)
    ceiling_idx = len(order) - 1
    reasons = []
    reads = set(data_flow.get("reads_data_classes", []))
    writes = set(data_flow.get("writes_data_classes", []))
    if (reads | writes) & {"CREDENTIALS", "SECRET", "PAYMENT_DATA"}:
        ceiling_idx = min(ceiling_idx, order.index("NAME_ONLY"))
        reasons.append("handles credentials/secret/payment data")
    if category in FORBIDDEN_CATEGORIES:
        ceiling_idx = min(ceiling_idx, order.index("NAME_ONLY"))
        reasons.append("forbidden capability category")
    if side_effect_class in FORBIDDEN_SIDE_EFFECTS:
        ceiling_idx = min(ceiling_idx, order.index("NAME_ONLY"))
        reasons.append("forbidden side-effect class")
    if data_flow.get("exfiltration_hazard"):
        ceiling_idx = min(ceiling_idx, order.index("NAME_ONLY"))
        reasons.append("exfiltration hazard")
    effective_idx = min(declared_idx, ceiling_idx)
    policy = {
        "prompt_context_policy_version": PROMPT_CONTEXT_POLICY_VERSION,
        "declared_exposure": exposure_level,
        "effective_exposure": order[effective_idx],
        "clamped": effective_idx < declared_idx,
        "clamp_reasons": reasons,
        "expose_full_descriptor_to_model": order[effective_idx]
        == "FULL_DESCRIPTOR",
    }
    policy["prompt_context_policy_hash"] = _core_hash(
        policy, "prompt_context_policy_hash")
    return policy


# --- TBOM (Tool Bill of Materials) — NOT an SBOM ---------------------------
def build_tbom(*, tool_id, tool_version_id, tenant_id, tool_key, category,
               side_effect_class, risk_class, trust_tier,
               schema_envelope_hash, effect_contract_hash,
               data_flow_contract_hash, purpose_contract_hash,
               consent_contract_hash, prompt_context_policy_hash,
               declared_dependencies, declared_provider, declared_version,
               scanner_hash) -> dict:
    tbom = {
        "tbom_version": TBOM_VERSION, "tool_id": tool_id,
        "tool_version_id": tool_version_id, "tenant_id": tenant_id,
        "tool_key": tool_key, "category": category,
        "side_effect_class": side_effect_class, "risk_class": risk_class,
        "trust_tier": trust_tier,
        "schema_envelope_hash": schema_envelope_hash,
        "effect_contract_hash": effect_contract_hash,
        "data_flow_contract_hash": data_flow_contract_hash,
        "purpose_contract_hash": purpose_contract_hash,
        "consent_contract_hash": consent_contract_hash,
        "prompt_context_policy_hash": prompt_context_policy_hash,
        "declared_dependencies": sorted(set(declared_dependencies or [])),
        "declared_provider": declared_provider,
        "declared_version": declared_version, "scanner_hash": scanner_hash,
        "generation_method": "LOCAL_DETERMINISTIC",
        "external_provider_used": False, "llm_used": False,
        "tool_executed": False,
        "not_an_sbom": "TBOM is local Finalis tool-composition metadata; it is "
        "not an SBOM and claims no SPDX/CycloneDX/SLSA/in-toto compliance.",
    }
    tbom["tbom_hash"] = _core_hash(tbom, "tbom_hash")
    return tbom


# --- Negative capability proof vector --------------------------------------
# The set of things EVERY registered tool descriptor must NOT be able to do.
# Each entry is proven by a deterministic predicate over the descriptor; a
# failed predicate is a hard admission block, not a warning.
NEGATIVE_CAPABILITIES = [
    "cannot_execute_here",
    "cannot_send_customer_message",
    "cannot_move_payment",
    "cannot_write_crm",
    "cannot_mutate_evidence",
    "cannot_export_document",
    "cannot_override_consent",
    "cannot_self_approve",
    "cannot_escalate_privilege",
    "cannot_cross_tenant",
    "cannot_exfiltrate_secrets",
    "cannot_change_server_policy",
]


def build_negative_capabilities(*, category, effect_contract, data_flow,
                                consent_contract, scanner) -> dict:
    """Prove each negative capability holds. `cannot_execute_here` and
    `cannot_change_server_policy` are structural (always true — nothing
    executes and descriptors never change policy). The rest are derived from
    the declared contracts + scanner flags, fail-closed."""
    ec, df = effect_contract, data_flow
    proofs = {
        "cannot_execute_here": True,
        "cannot_change_server_policy": True,
        "cannot_send_customer_message":
            not ec["touches_customer"]
            and ec["side_effect_class"] != "CUSTOMER_MESSAGING"
            and category != "CUSTOMER_MESSAGING",
        "cannot_move_payment":
            not ec["touches_payment"]
            and ec["side_effect_class"] != "PAYMENT_MOVEMENT"
            and category != "PAYMENT",
        "cannot_write_crm":
            not ec["touches_crm"]
            and ec["side_effect_class"] != "CRM_MUTATION"
            and category != "CRM_WRITE",
        "cannot_mutate_evidence":
            not ec["touches_evidence"]
            and ec["side_effect_class"] != "EVIDENCE_MUTATION"
            and category != "EVIDENCE_MUTATION",
        "cannot_export_document": category != "DOCUMENT_EXPORT",
        "cannot_override_consent":
            not consent_contract["consent_can_be_overridden"]
            and not scanner["consent_override_flags"],
        "cannot_self_approve": not scanner["consent_override_flags"],
        "cannot_escalate_privilege": not scanner["privilege_escalation_flags"]
            and category not in ("IDENTITY_ACCESS", "ADMIN_OPERATION"),
        "cannot_cross_tenant": not df["crosses_tenant_boundary"]
            and not scanner["privilege_escalation_flags"],
        "cannot_exfiltrate_secrets": not df["exfiltration_hazard"]
            and not scanner["data_exfiltration_flags"],
    }
    violated = sorted(k for k, ok in proofs.items() if not ok)
    vector = {
        "negative_capability_version": NEGATIVE_CAPABILITY_VERSION,
        "proofs": {k: bool(v) for k, v in proofs.items()},
        "violated": violated, "all_hold": not violated,
    }
    vector["negative_capability_hash"] = _core_hash(
        vector, "negative_capability_hash")
    return vector


# --- Security invariant matrix ---------------------------------------------
# Each invariant maps to a boolean predicate resolved at build time. An unmet
# applicable invariant blocks admission (fail-closed).
SECURITY_INVARIANTS = [
    "no_execution_capability",
    "no_forbidden_category",
    "no_forbidden_side_effect",
    "declared_effects_match_dataflow",
    "no_undeclared_egress_of_secrets",
    "consent_not_overridable",
    "no_purpose_conflict",
    "prompt_exposure_clamped_for_sensitive",
    "scanner_clean",
    "tenant_scoped",
    "negative_capabilities_hold",
    "trust_tier_not_overtrusted",
]


def build_invariant_matrix(*, category, effect_contract, data_flow,
                           schema_envelope, purpose_contract, consent_contract,
                           prompt_context_policy, scanner,
                           negative_capabilities, trust_tier,
                           declared_tenant_id, actor_tenant_id,
                           actor_type) -> dict:
    ec, df, se = effect_contract, data_flow, schema_envelope
    declared_effects = set(se["declared_side_effects"]) | {
        ec["side_effect_class"]}
    dataflow_implies_write = bool(df["writes_data_classes"]
                                  or df["egress_targets"])
    effects_consistent = not (
        ec["side_effect_class"] == "PURE_READ" and dataflow_implies_write)
    overtrusted = (actor_type != "human"
                   and trust_tier in ("HUMAN_REVIEWED", "INTERNAL_VERIFIED"))
    results = {
        "no_execution_capability": not ec["execution_performed"],
        "no_forbidden_category": category not in FORBIDDEN_CATEGORIES,
        "no_forbidden_side_effect": not (
            declared_effects & FORBIDDEN_SIDE_EFFECTS),
        "declared_effects_match_dataflow": effects_consistent,
        "no_undeclared_egress_of_secrets": not df["egress_forbidden_data_flagged"],
        "consent_not_overridable": not consent_contract[
            "consent_can_be_overridden"],
        "no_purpose_conflict": not purpose_contract["has_forbidden_purpose"],
        "prompt_exposure_clamped_for_sensitive": not (
            prompt_context_policy["expose_full_descriptor_to_model"]
            and (set(df["reads_data_classes"]) | set(df["writes_data_classes"]))
            & {"CREDENTIALS", "SECRET", "PAYMENT_DATA", "SENSITIVE_PII"}),
        "scanner_clean": scanner["quarantine_status"] == "CLEAN",
        "tenant_scoped": declared_tenant_id == actor_tenant_id,
        "negative_capabilities_hold": negative_capabilities["all_hold"],
        "trust_tier_not_overtrusted": not overtrusted,
    }
    failed = sorted(k for k, ok in results.items() if not ok)
    matrix = {
        "invariant_matrix_version": INVARIANT_MATRIX_VERSION,
        "results": {k: bool(v) for k, v in results.items()},
        "failed_invariants": failed, "all_pass": not failed,
    }
    matrix["invariant_matrix_hash"] = _core_hash(matrix,
                                                 "invariant_matrix_hash")
    return matrix


# --- Risk capsule ----------------------------------------------------------
def compute_risk_class(*, category, effect_contract, data_flow,
                       scanner) -> str:
    """Deterministic risk classification. Forbidden categories/side-effects and
    any hard scanner hit are PROHIBITED. Otherwise risk rises with side-effect
    rank and sensitive data handling."""
    ec = effect_contract
    declared = ec["side_effect_class"]
    if category in FORBIDDEN_CATEGORIES or declared in FORBIDDEN_SIDE_EFFECTS:
        return "PROHIBITED"
    if scanner["quarantine_status"] == "QUARANTINED":
        return "PROHIBITED"
    if data_flow["exfiltration_hazard"]:
        return "CRITICAL"
    rank = ec["side_effect_rank"]
    sensitive = bool((set(data_flow["reads_data_classes"])
                      | set(data_flow["writes_data_classes"]))
                     & {"CREDENTIALS", "SECRET", "PAYMENT_DATA",
                        "SENSITIVE_PII", "EVIDENCE", "LEGAL"})
    if rank >= SIDE_EFFECT_RANK["EXTERNAL_WRITE"]:
        return "HIGH"
    if rank >= SIDE_EFFECT_RANK["EXTERNAL_READ"] or sensitive:
        return "MEDIUM"
    if rank >= SIDE_EFFECT_RANK["INTERNAL_WRITE"]:
        return "LOW"
    return "TRIVIAL"


def build_risk_capsule(*, tool_id, tenant_id, category, effect_contract,
                       data_flow, scanner, risk_class,
                       invariant_matrix) -> dict:
    drivers = []
    if category in FORBIDDEN_CATEGORIES:
        drivers.append(f"forbidden category {category}")
    if effect_contract["side_effect_class"] in FORBIDDEN_SIDE_EFFECTS:
        drivers.append("forbidden side-effect "
                       + effect_contract["side_effect_class"])
    if data_flow["exfiltration_hazard"]:
        drivers.append("exfiltration hazard")
    if scanner["quarantine_status"] == "QUARANTINED":
        drivers.append("descriptor poisoning detected")
    for inv in invariant_matrix["failed_invariants"]:
        drivers.append(f"invariant failed: {inv}")
    capsule = {
        "risk_capsule_version": RISK_CAPSULE_VERSION, "tool_id": tool_id,
        "tenant_id": tenant_id, "risk_class": risk_class,
        "risk_rank": RISK_RANK[risk_class],
        "side_effect_rank": effect_contract["side_effect_rank"],
        "risk_drivers": drivers,
        "is_prohibited": risk_class == "PROHIBITED",
    }
    capsule["risk_capsule_hash"] = _core_hash(capsule, "risk_capsule_hash")
    return capsule


# --- Policy capsule --------------------------------------------------------
def build_policy_capsule(*, tool_id, tenant_id, category, side_effect_class,
                         risk_class, trust_tier, consent_contract,
                         purpose_contract, prompt_context_policy,
                         invariant_matrix, negative_capabilities,
                         created_at) -> dict:
    policy_input = {
        "category": category, "side_effect_class": side_effect_class,
        "risk_class": risk_class, "trust_tier": trust_tier,
        "consent_requirement": consent_contract["consent_requirement"],
        "consent_non_overridable": consent_contract["non_overridable"],
    }
    admissible = (invariant_matrix["all_pass"]
                  and negative_capabilities["all_hold"]
                  and risk_class != "PROHIBITED"
                  and category not in FORBIDDEN_CATEGORIES)
    policy_output = {
        "admissible": admissible,
        "requires_human_admission": True,
        "may_be_offered_to_future_broker": admissible,
        "may_execute_now": False,
        "requires_consent": consent_contract["consent_requirement"] not in (
            "NONE",),
        "consent_overridable": False,
        "allowed_purposes": purpose_contract["allowed_purposes"],
        "forbidden_purposes": purpose_contract["forbidden_purposes"],
        "prompt_context_exposure": prompt_context_policy["effective_exposure"],
        "blocking_invariants": invariant_matrix["failed_invariants"],
        "violated_negative_capabilities": negative_capabilities["violated"],
    }
    capsule = {
        "policy_capsule_version": POLICY_CAPSULE_VERSION, "tool_id": tool_id,
        "tenant_id": tenant_id, **policy_input, **policy_output,
        "policy_input_hash": _sha(policy_input),
        "policy_output_hash": _sha(policy_output), "created_at": created_at,
    }
    capsule["policy_capsule_hash"] = _core_hash(
        capsule, "policy_capsule_hash", "policy_input_hash",
        "policy_output_hash")
    return capsule


# --- Security case ---------------------------------------------------------
def build_security_case(*, tool_id, tenant_id, invariant_matrix,
                        negative_capabilities, risk_capsule, scanner,
                        implicit_findings, admission_decision) -> dict:
    argument = []
    argument.append({"claim": "no_execution_here",
                     "supported": True,
                     "evidence": "registry has no execute path"})
    argument.append({"claim": "all_security_invariants_hold",
                     "supported": invariant_matrix["all_pass"],
                     "evidence": "invariant_matrix"})
    argument.append({"claim": "negative_capabilities_hold",
                     "supported": negative_capabilities["all_hold"],
                     "evidence": "negative_capability_vector"})
    argument.append({"claim": "not_prohibited_risk",
                     "supported": risk_capsule["risk_class"] != "PROHIBITED",
                     "evidence": "risk_capsule"})
    argument.append({"claim": "descriptor_not_poisoned",
                     "supported": scanner["quarantine_status"] == "CLEAN",
                     "evidence": "descriptor_scanner"})
    argument.append({"claim": "no_implicit_poisoning",
                     "supported": not implicit_findings,
                     "evidence": "implicit_poisoning_detector"})
    unsupported = [a["claim"] for a in argument if not a["supported"]]
    case = {
        "security_case_version": SECURITY_CASE_VERSION, "tool_id": tool_id,
        "tenant_id": tenant_id, "argument": argument,
        "unsupported_claims": unsupported,
        "security_case_holds": not unsupported,
        "admission_decision": admission_decision,
        "note": "Local structured security argument; not a formal proof and "
        "not a production attestation.",
    }
    case["security_case_hash"] = _core_hash(case, "security_case_hash")
    return case


# --- Implicit poisoning detector -------------------------------------------
def detect_implicit_poisoning(*, category, effect_contract, data_flow,
                              schema_envelope, purpose_contract,
                              consent_contract, tool_description="") -> list:
    """Cross-checks DECLARED fields against each other for hidden / mismatched
    capability — poisoning that no single-field scanner would catch. Each
    finding is a dict {code, detail}. Deterministic; no LLM."""
    findings = []
    ec, df, se = effect_contract, data_flow, schema_envelope
    desc = _normalize(tool_description)

    if ec["side_effect_class"] == "PURE_READ" and (
            df["writes_data_classes"] or df["egress_targets"]):
        findings.append({"code": "read_declared_but_writes",
                         "detail": "declared PURE_READ but data-flow writes or "
                         "egresses data"})
    # Description implies a capability the effect contract denies.
    verb_map = {
        " send ": ("touches_customer", "CUSTOMER_MESSAGING"),
        " email ": ("touches_customer", "CUSTOMER_MESSAGING"),
        " pay ": ("touches_payment", "PAYMENT_MOVEMENT"),
        " charge ": ("touches_payment", "PAYMENT_MOVEMENT"),
        " refund ": ("touches_payment", "PAYMENT_MOVEMENT"),
        " delete ": (None, "DESTRUCTIVE"),
        " export ": (None, None),
    }
    for verb, (flag, se_class) in verb_map.items():
        if verb in desc:
            declared = ((flag and ec.get(flag))
                        or (se_class and ec["side_effect_class"] == se_class)
                        or (se_class and se_class in se["declared_side_effects"]))
            if not declared:
                findings.append({
                    "code": "undeclared_capability_in_description",
                    "detail": f"description implies '{verb.strip()}' but effect "
                    "contract does not declare it"})
    # Sensitive data read with no consent requirement.
    sensitive = (set(df["reads_data_classes"]) | set(df["writes_data_classes"])) \
        & {"PII", "SENSITIVE_PII", "PAYMENT_DATA", "EVIDENCE", "LEGAL"}
    if sensitive and consent_contract["consent_requirement"] == "NONE":
        findings.append({"code": "sensitive_data_without_consent",
                         "detail": f"handles {sorted(sensitive)} but declares "
                         "no consent requirement"})
    # A parameter marked sensitive but declared as public/egressed.
    for p in se["parameters"]:
        if p["sensitive"] and p["data_class"] == "PUBLIC":
            findings.append({"code": "sensitive_param_marked_public",
                             "detail": f"parameter {p['name']} is sensitive but "
                             "declared PUBLIC"})
    # Benign category but dangerous effect.
    if category in ("DATA_READ", "DATA_SEARCH", "INTERNAL_COMPUTE",
                    "ANALYTICS") and ec["side_effect_rank"] >= SIDE_EFFECT_RANK[
                        "EXTERNAL_WRITE"]:
        findings.append({"code": "benign_category_dangerous_effect",
                         "detail": f"category {category} but side-effect "
                         f"{ec['side_effect_class']}"})
    return findings


# --- Alias / collision / shadowing detection -------------------------------
def normalize_tool_key(name: str) -> str:
    """Canonical tool key: lowercase, alnum runs joined by single hyphen. Makes
    'Send_Email', 'send email' and 'send-email' collide by design."""
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def detect_collisions(*, candidate, existing) -> dict:
    """Detect name/alias collisions and shadowing between a candidate descriptor
    and the existing registry. `candidate` and each `existing` entry are dicts
    with keys: tool_id, tool_key, aliases (list), trust_tier, risk_rank,
    status. Deterministic set logic; no LLM."""
    cand_keys = {candidate["tool_key"]} | {normalize_tool_key(a)
                                           for a in candidate.get("aliases", [])}
    cand_keys.discard("")
    collisions, shadowing = [], []
    trust_order = {"UNTRUSTED_DECLARED": 0, "AI_PROPOSED_UNVERIFIED": 1,
                   "QUARANTINED": 0, "REVOKED": 0, "REFERENCE_ONLY": 2,
                   "HUMAN_REVIEW_REQUIRED": 3, "HUMAN_REVIEWED": 4,
                   "INTERNAL_VERIFIED": 5}
    for e in existing:
        if e.get("tool_id") == candidate.get("tool_id"):
            continue
        e_keys = {e["tool_key"]} | {normalize_tool_key(a)
                                    for a in e.get("aliases", [])}
        e_keys.discard("")
        overlap = sorted(cand_keys & e_keys)
        if overlap:
            collisions.append({"tool_id": e["tool_id"],
                               "colliding_keys": overlap,
                               "existing_status": e.get("status")})
            # Shadowing: candidate claims a key already held by a
            # higher-or-equal-trust ADMITTED/offerable tool.
            e_offerable = e.get("status") in (
                "ADMITTED", "AVAILABLE_FOR_FUTURE_BROKER")
            if e_offerable and trust_order.get(
                    candidate.get("trust_tier"), 0) <= trust_order.get(
                    e.get("trust_tier"), 0):
                shadowing.append({"tool_id": e["tool_id"],
                                  "shadowed_keys": overlap,
                                  "reason": "candidate shadows an "
                                  "equal-or-higher-trust offerable tool"})
    return {"collisions": collisions, "shadowing": shadowing,
            "has_collision": bool(collisions),
            "has_shadowing": bool(shadowing)}


# --- Multi-tool poisoning detector -----------------------------------------
def detect_multi_tool_poisoning(descriptors: list) -> dict:
    """Given the tenant's candidate + existing descriptor summaries, find
    cross-tool hazards that no single descriptor exposes: capability-escalation
    chains (a secret/credential reader feeding an egress writer) and
    key-collision confusion. Each descriptor: {tool_id, tool_key, side_effect_
    class, reads_data_classes, writes_data_classes, egress, risk_rank, status}.
    Deterministic pairwise scan; no LLM."""
    findings = []
    offerable = [d for d in descriptors
                 if d.get("status") in ("ADMITTED",
                                        "AVAILABLE_FOR_FUTURE_BROKER", "DRAFT",
                                        "NEEDS_REVIEW")]
    secret = {"CREDENTIALS", "SECRET", "PAYMENT_DATA", "SENSITIVE_PII",
              "EVIDENCE", "LEGAL"}
    readers = [d for d in offerable
               if set(d.get("reads_data_classes", [])) & secret]
    writers = [d for d in offerable
               if d.get("egress") or d.get("side_effect_class") in (
                   "EXTERNAL_WRITE", "CUSTOMER_MESSAGING")]
    for r in readers:
        for w in writers:
            if r.get("tool_id") == w.get("tool_id"):
                continue
            findings.append({
                "code": "escalation_chain",
                "reader_tool_id": r.get("tool_id"),
                "writer_tool_id": w.get("tool_id"),
                "detail": "a secret/sensitive reader combined with an "
                "egress/messaging writer forms an exfiltration chain"})
    # Key-collision confusion across the offerable set.
    by_key = {}
    for d in offerable:
        by_key.setdefault(d.get("tool_key"), []).append(d.get("tool_id"))
    for key, ids in sorted(by_key.items()):
        if key and len(ids) > 1:
            findings.append({"code": "key_confusion", "tool_key": key,
                             "tool_ids": sorted(ids),
                             "detail": "multiple offerable tools share one "
                             "canonical key"})
    return {"findings": findings, "has_findings": bool(findings)}


# --- Capability lattice / reachability -------------------------------------
def build_capability_lattice(*, tool_id, tenant_id, category, effect_contract,
                             data_flow) -> dict:
    """A small partial-order lattice from declared inputs → capabilities →
    effects, plus a reachability set of the effect nodes a future broker call
    could reach. Used to prove no forbidden effect is reachable."""
    nodes = [{"node": "INPUT", "id": f"{tool_id}:input"},
             {"node": "CATEGORY", "id": category},
             {"node": "SIDE_EFFECT", "id": effect_contract["side_effect_class"]}]
    edges = [{"from": f"{tool_id}:input", "to": category},
             {"from": category, "to": effect_contract["side_effect_class"]}]
    reachable = {effect_contract["side_effect_class"]}
    for dc in data_flow["writes_data_classes"]:
        nodes.append({"node": "DATA_WRITE", "id": dc})
        edges.append({"from": effect_contract["side_effect_class"], "to": dc})
    for tgt in data_flow["egress_targets"]:
        nodes.append({"node": "EGRESS", "id": tgt})
        edges.append({"from": effect_contract["side_effect_class"],
                      "to": f"egress:{tgt}"})
        reachable.add("EGRESS")
    forbidden_reachable = sorted(reachable & FORBIDDEN_SIDE_EFFECTS)
    lattice = {
        "capability_lattice_version": LATTICE_VERSION, "tool_id": tool_id,
        "tenant_id": tenant_id, "nodes": nodes, "edges": edges,
        "reachable_effects": sorted(reachable),
        "forbidden_effect_reachable": forbidden_reachable,
        "has_forbidden_reachable": bool(forbidden_reachable),
    }
    lattice["capability_lattice_hash"] = _core_hash(
        lattice, "capability_lattice_hash")
    return lattice


def reachable_forbidden(lattice: dict) -> bool:
    return bool(lattice.get("forbidden_effect_reachable"))


# --- Supply-chain guard (drift / rug-pull) ---------------------------------
def supply_chain_guard(*, admitted_snapshot, new_snapshot) -> dict:
    """Compare a previously-admitted descriptor snapshot to a new proposed
    version. Any change to security-relevant hashes on a supposedly-pinned
    descriptor is DRIFT; an increase in side-effect danger, risk, a new
    forbidden capability, or a newly-tripped scanner is a RUG_PULL. Rug-pull
    dominates drift. Deterministic; fail-closed on missing fields.

    Each snapshot: {descriptor_hash, effect_contract_hash,
    data_flow_contract_hash, side_effect_rank, risk_rank, category,
    scanner_clean, forbidden_capability}."""
    a, n = admitted_snapshot or {}, new_snapshot or {}
    reasons = []
    watched = ["descriptor_hash", "effect_contract_hash",
               "data_flow_contract_hash"]
    drift = any(a.get(k) != n.get(k) for k in watched)
    for k in watched:
        if a.get(k) != n.get(k):
            reasons.append(f"{k} changed")
    rug = False
    # Fail-closed: a missing new rank is treated as maximally dangerous.
    a_se = a.get("side_effect_rank", 0)
    n_se = n.get("side_effect_rank", max(SIDE_EFFECT_RANK.values()))
    a_risk = a.get("risk_rank", 0)
    n_risk = n.get("risk_rank", RISK_RANK["PROHIBITED"])
    if n_se > a_se:
        rug = True
        reasons.append("side-effect danger escalated")
    if n_risk > a_risk:
        rug = True
        reasons.append("risk class escalated")
    if n.get("category") in FORBIDDEN_CATEGORIES and a.get(
            "category") not in FORBIDDEN_CATEGORIES:
        rug = True
        reasons.append("new forbidden category introduced")
    if n.get("forbidden_capability") and not a.get("forbidden_capability"):
        rug = True
        reasons.append("new forbidden capability introduced")
    if a.get("scanner_clean") and not n.get("scanner_clean", False):
        rug = True
        reasons.append("descriptor newly trips the poisoning scanner")
    if rug:
        verdict = "RUG_PULL_DETECTED"
    elif drift:
        verdict = "DRIFT_DETECTED"
    else:
        verdict = "STABLE"
    result = {"verdict": verdict, "drift": drift, "rug_pull": rug,
              "reasons": reasons}
    result["supply_chain_hash"] = _sha(result)
    return result


# --- Admission evaluation (fail-closed) ------------------------------------
def evaluate_admission(*, category, invariant_matrix, negative_capabilities,
                       risk_capsule, scanner, implicit_findings,
                       lattice, collision, multi_tool, supply_chain,
                       declared_tenant_id, actor_tenant_id,
                       requested_by_human) -> dict:
    """Decide the admission outcome as a dominant status + reasons. Every
    hard-fail is collected; the dominant (highest-precedence) status is
    returned. Positive admission is only possible when NO hard-fail fires and
    a human requested it. Nothing executes."""
    signals = set()
    reasons = []

    if declared_tenant_id != actor_tenant_id:
        signals.add("CROSS_TENANT_REJECTED")
        reasons.append("declared tenant does not match actor tenant")
    if supply_chain and supply_chain.get("verdict") == "RUG_PULL_DETECTED":
        signals.add("RUG_PULL_DETECTED")
        reasons.append("supply-chain rug-pull detected")
    if supply_chain and supply_chain.get("verdict") == "DRIFT_DETECTED":
        signals.add("DRIFT_DETECTED")
        reasons.append("supply-chain drift detected")
    if (category in FORBIDDEN_CATEGORIES
            or risk_capsule["risk_class"] == "PROHIBITED"
            or negative_capabilities["violated"]
            or lattice["has_forbidden_reachable"]):
        signals.add("FORBIDDEN_CAPABILITY")
        reasons.append("forbidden capability declared or reachable")
    if scanner["quarantine_status"] == "QUARANTINED":
        signals.add("QUARANTINED")
        reasons.append("descriptor tripped the poisoning scanner")
    if (collision and collision.get("has_shadowing")) or (
            multi_tool and multi_tool.get("has_findings")):
        signals.add("BLOCKED")
        reasons.append("collision/shadowing or multi-tool hazard")
    if implicit_findings:
        signals.add("NEEDS_REVIEW")
        reasons.append("implicit poisoning findings require review")
    if not invariant_matrix["all_pass"]:
        signals.add("BLOCKED")
        reasons.append("security invariant(s) failed: "
                       + ", ".join(invariant_matrix["failed_invariants"]))
    if not requested_by_human:
        signals.add("NEEDS_REVIEW")
        reasons.append("admission must be requested by a human")

    if signals:
        status = dominant_status(signals)
        admitted = False
    else:
        status = "AVAILABLE_FOR_FUTURE_BROKER"
        admitted = True
    return {"admission_status": status, "admitted": admitted,
            "hard_fail_signals": sorted(signals), "reasons": reasons,
            "may_execute_now": False,
            "admission_hash": _sha({"status": status, "admitted": admitted,
                                    "signals": sorted(signals)})}


def dominant_status(statuses) -> str:
    """Return the highest-precedence status per STATUS_DOMINANCE. Unknown
    statuses are treated as maximally dominant (fail-closed): an unknown status
    can never be out-ranked by a positive/benign known status (ADMITTED,
    AVAILABLE_FOR_FUTURE_BROKER, NOT_IMPLEMENTED). Known hard-fail statuses
    (everything strictly before ADMITTED) already block, so they may win."""
    present = set(statuses)
    admit_idx = STATUS_DOMINANCE.index("ADMITTED")
    for s in STATUS_DOMINANCE:
        if s in present:
            # If any present status is unknown to the ladder, it must not be
            # silently out-ranked by a known benign/positive one. Using >= so
            # ADMITTED itself (index == admit_idx) also yields the unknown.
            unknown = present - set(STATUS_DOMINANCE)
            if unknown and STATUS_DOMINANCE.index(s) >= admit_idx:
                return sorted(unknown)[0]
            return s
    return sorted(present)[0] if present else "DRAFT"


# --- Admission package ------------------------------------------------------
def build_admission_package(*, tool_id, tool_version_id, tenant_id,
                            descriptor_hash, tbom_hash, invariant_matrix,
                            negative_capabilities, risk_capsule, policy_capsule,
                            security_case_hash, admission_decision,
                            requested_by_actor_id, requested_by_actor_type,
                            created_at) -> dict:
    pkg = {
        "admission_package_version": ADMISSION_PACKAGE_VERSION,
        "tool_id": tool_id, "tool_version_id": tool_version_id,
        "tenant_id": tenant_id, "descriptor_hash": descriptor_hash,
        "tbom_hash": tbom_hash,
        "invariant_matrix_hash": invariant_matrix["invariant_matrix_hash"],
        "negative_capability_hash": negative_capabilities[
            "negative_capability_hash"],
        "risk_capsule_hash": risk_capsule["risk_capsule_hash"],
        "policy_capsule_hash": policy_capsule["policy_capsule_hash"],
        "security_case_hash": security_case_hash,
        "admission_status": admission_decision["admission_status"],
        "admitted": admission_decision["admitted"],
        "hard_fail_signals": admission_decision["hard_fail_signals"],
        "requested_by_actor_id": requested_by_actor_id,
        "requested_by_actor_type": requested_by_actor_type,
        "may_execute_now": False, "created_at": created_at,
    }
    pkg["admission_package_hash"] = _core_hash(pkg, "admission_package_hash")
    return pkg


# --- Descriptor + version hashing ------------------------------------------
def descriptor_hash(descriptor: dict) -> str:
    # Excludes version_hash to break the descriptor<->version hash cycle.
    return _core_hash(descriptor, "descriptor_hash", "version_hash")


def version_hash(*, tool_id, version_number, descriptor_hash, tbom_hash,
                 policy_capsule_hash, admission_package_hash,
                 previous_version_hash, created_by_actor_id) -> str:
    return _sha({"tool_id": tool_id, "version_number": version_number,
                 "descriptor_hash": descriptor_hash, "tbom_hash": tbom_hash,
                 "policy_capsule_hash": policy_capsule_hash,
                 "admission_package_hash": admission_package_hash,
                 "previous_version_hash": previous_version_hash or GENESIS,
                 "created_by_actor_id": created_by_actor_id})


def version_chain_hash(previous_chain: str, this_version_hash: str) -> str:
    return _sha({"previous_version_chain_hash": previous_chain or GENESIS,
                 "version_hash": this_version_hash})


def tool_state_hash(*, tool_id, tenant_id, tool_key, category,
                    side_effect_class, risk_class, trust_tier, status,
                    latest_version_id, version_number, descriptor_hash,
                    tbom_hash, policy_capsule_hash, risk_capsule_hash,
                    invariant_matrix_hash, negative_capability_hash,
                    admission_package_hash, capability_lattice_hash,
                    version_chain_hash) -> str:
    return _sha({
        "tool_id": tool_id, "tenant_id": tenant_id, "tool_key": tool_key,
        "category": category, "side_effect_class": side_effect_class,
        "risk_class": risk_class, "trust_tier": trust_tier, "status": status,
        "latest_version_id": latest_version_id, "version_number": version_number,
        "descriptor_hash": descriptor_hash, "tbom_hash": tbom_hash,
        "policy_capsule_hash": policy_capsule_hash,
        "risk_capsule_hash": risk_capsule_hash,
        "invariant_matrix_hash": invariant_matrix_hash,
        "negative_capability_hash": negative_capability_hash,
        "admission_package_hash": admission_package_hash,
        "capability_lattice_hash": capability_lattice_hash,
        "version_chain_hash": version_chain_hash})


# --- Registry event ledger -------------------------------------------------
REGISTRY_EVENT_TYPES = {
    "TOOL_REGISTERED", "TOOL_VERSION_ADDED", "TOOL_ADMITTED",
    "TOOL_ADMISSION_REJECTED", "TOOL_DISABLED", "TOOL_DEPRECATED",
    "TOOL_SUPERSEDED", "TOOL_QUARANTINED", "TOOL_DRIFT_DETECTED",
    "TOOL_RUG_PULL_DETECTED", "TOOL_TAMPER_DETECTED", "TOOL_VERIFIED",
}


def build_registry_event(*, event_type, tool_id, tenant_id, actor_id,
                         actor_type, tool_state_hash, previous_event_hash,
                         sequence, detail, created_at) -> dict:
    if event_type not in REGISTRY_EVENT_TYPES:
        raise ValueError(f"unknown registry event_type {event_type}")
    ev = {
        "registry_event_version": REGISTRY_EVENT_VERSION,
        "event_type": event_type, "tool_id": tool_id, "tenant_id": tenant_id,
        "actor_id": actor_id, "actor_type": actor_type,
        "tool_state_hash": tool_state_hash,
        "previous_event_hash": previous_event_hash or GENESIS,
        "sequence": sequence, "detail": detail, "created_at": created_at,
    }
    ev["event_hash"] = _sha({k: v for k, v in ev.items()
                             if k not in ("event_hash",)})
    return ev


def registry_snapshot_hash(tool_state_hashes: list) -> str:
    """Deterministic snapshot over the tenant's tool state hashes (order-
    independent: sorted before hashing)."""
    return _sha({"tool_state_hashes": sorted(tool_state_hashes or []),
                 "count": len(tool_state_hashes or [])})


# --- Trust-tier derivation (fail-closed) -----------------------------------
def default_trust_tier(actor_type: str) -> str:
    # Fail-closed: a descriptor authored by anything other than a human is
    # AI_PROPOSED_UNVERIFIED and can never start life as reviewed/verified.
    if actor_type == "human":
        return "HUMAN_REVIEW_REQUIRED"
    return "AI_PROPOSED_UNVERIFIED"
