"""Provider Capability Contracts + Profiles (SP0004 D-0004-20..30, §10.4/§10.5,
INV-0004-03/04/05/06/14).

Contracts are capability-SPECIFIC (ModelProvider, TelephonyProvider, …) — never a
universal `Provider.execute(anything)` (AC-0004-047). Each contract has stable
CORE capabilities plus NAMESPACED optional extensions that cannot silently
redefine core semantics (D-0004-22, INV-0004-14). The tooling enforces the
sovereignty invariants: provider ID is never canonical identity (INV-0004-04),
provider error is never business state (INV-0004-05), and a raw provider secret
must never enter a model-facing contract (INV-0004-06).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, ERROR_TAXONOMY, PROVIDER_OUTCOMES,
                    INVALID_TDR, PROVIDER_IDENTITY_LEAKAGE, RAW_SECRET_EXPOSURE,
                    CREDENTIAL_SCOPE_VIOLATION, EXTENSION_REDEFINES_CORE,
                    UNIVERSAL_PROVIDER_CONTRACT, PROVIDER_ERROR_AS_BUSINESS_STATE)

# tokens that indicate a raw secret leaking into a model-facing schema. Field
# names are normalized (hyphens/spaces -> underscores, lowercased) before matching
# so "x-api-key", "Authorization" and "access-key" cannot evade (red-team hardening).
SECRET_TOKENS = ("api_key", "apikey", "secret", "password", "passwd", "token",
                 "private_key", "client_secret", "bearer", "credential_value",
                 "authorization", "access_key", "accesskey", "session_key",
                 "session_token", "auth_token", "cookie", "x_api", "sas_token",
                 "connection_string", "signing_key", "encryption_key")
# a field named like a provider primary key masquerading as canonical identity
CANONICAL_IDENTITY_FIELDS = ("employee_id", "case_id", "work_id", "tenant_id",
                             "run_id", "outcome_id", "identity")
# provider business-state confusion (an error code used as a business status)
BUSINESS_STATE_FIELDS = ("case_status", "work_status", "outcome_status",
                         "business_state")
# a too-generic core operation name = universal-provider smell
UNIVERSAL_OPS = {"execute", "call", "invoke", "run", "do", "any", "anything"}


def validate_contract(contract: dict) -> list[Finding]:
    out: list[Finding] = []
    cid = contract.get("contract_id", "-")
    if not contract.get("provider_class"):
        out.append(Finding(INVALID_TDR, P1, cid,
                           "contract missing provider_class", {}))
    core = contract.get("core_capabilities", [])
    # AC-0004-047: no universal "execute(anything)" core contract
    core_names = {c.get("name", c) if isinstance(c, dict) else c for c in core}
    if core_names & UNIVERSAL_OPS:
        out.append(Finding(UNIVERSAL_PROVIDER_CONTRACT, P1, cid,
                           "core contract exposes a universal operation "
                           f"{sorted(core_names & UNIVERSAL_OPS)} — contracts "
                           "must be capability-specific (D-0004-20)", {}))
    # error taxonomy must be a subset of the canonical Finalis taxonomy
    for e in contract.get("error_taxonomy", []):
        if e not in ERROR_TAXONOMY:
            out.append(Finding(INVALID_TDR, P1, cid,
                               f"error {e!r} not in canonical taxonomy", {}))
    # UNKNOWN_OUTCOME must exist for effectful contracts (D-0004-26)
    if contract.get("effectful") and "UNKNOWN_OUTCOME" not in \
            contract.get("error_taxonomy", []):
        out.append(Finding(INVALID_TDR, P0, cid,
                           "effectful contract must define UNKNOWN_OUTCOME "
                           "(AC-0004-055)", {}))
    out.extend(check_credential_isolation(contract))
    out.extend(check_identity_and_error_leakage(contract))
    out.extend(check_extensions(contract))
    return out


# dict keys whose STRING VALUE names a field (JSON-Schema / OpenAPI style:
# {"fields":[{"name":"api_key"}]}, {"parameters":[{"name":"authorization"}]}).
# A raw secret can hide as a value under these keys, not only as a dict key
# (red-team F1).
NAME_BEARING_KEYS = {"name", "field", "parameter", "property", "key", "title",
                     "header", "param"}


def _walk_field_names(schema, prefix="") -> list[str]:
    names = []
    if isinstance(schema, dict):
        for k, v in schema.items():
            names.append(str(k).lower())
            if str(k).lower() in NAME_BEARING_KEYS and isinstance(v, str):
                names.append(v.lower())          # the field-name-as-value
            names.extend(_walk_field_names(v, k))
    elif isinstance(schema, list):
        for v in schema:
            names.extend(_walk_field_names(v, prefix))
    return names


def check_credential_isolation(contract: dict) -> list[Finding]:
    """A raw secret must never appear in the model-facing request schema
    (INV-0004-06). Credentials pass by reference only."""
    out: list[Finding] = []
    cid = contract.get("contract_id", "-")
    model_facing = contract.get("request_schema", {})
    for raw in _walk_field_names(model_facing):
        # normalize separators so hyphen/space variants cannot evade
        n = raw.replace("-", "_").replace(" ", "_")
        has_secret = any(tok in n for tok in SECRET_TOKENS)
        # A field is a genuine reference only if it ends in a reference suffix AND
        # the stem (before that suffix) carries no secret token — so
        # "credential_reference" is exempt but "api_key_for_reference" is NOT
        # (red-team F1c).
        stem = n
        for suf in ("_reference", "_ref"):
            if n.endswith(suf):
                stem = n[: -len(suf)]
                break
        is_reference = (n == "ref" or (stem != n and not any(
            tok in stem for tok in SECRET_TOKENS)))
        if has_secret and not is_reference:
            out.append(Finding(RAW_SECRET_EXPOSURE, P0, cid,
                               f"model-facing request schema exposes raw secret "
                               f"field {raw!r}; use a credential reference "
                               "(AC-0004-057)", {}))
    cc = contract.get("credential_contract", {})
    if cc:
        for req in ("tenant_scope", "read_write_separation"):
            if req not in cc:
                out.append(Finding(CREDENTIAL_SCOPE_VIOLATION, P1, cid,
                                   f"credential_contract missing {req} "
                                   "(AC-0004-058/060)", {}))
    return out


def check_identity_and_error_leakage(contract: dict) -> list[Finding]:
    """Provider ID must be an external_reference, not canonical identity
    (INV-0004-04); provider error must not map to business state (INV-0004-05)."""
    out: list[Finding] = []
    cid = contract.get("contract_id", "-")
    for m in contract.get("provider_id_mappings", []):
        if m.get("maps_to") in CANONICAL_IDENTITY_FIELDS \
                and m.get("kind") != "external_reference":
            out.append(Finding(PROVIDER_IDENTITY_LEAKAGE, P0, cid,
                               f"provider id maps to canonical identity "
                               f"{m.get('maps_to')!r} (AC-0004-052)", {}))
    for m in contract.get("error_mappings", []):
        if m.get("maps_to") in BUSINESS_STATE_FIELDS:
            out.append(Finding(PROVIDER_ERROR_AS_BUSINESS_STATE, P0, cid,
                               f"provider error maps directly to business state "
                               f"{m.get('maps_to')!r} (AC-0004-053)", {}))
    return out


def check_extensions(contract: dict) -> list[Finding]:
    """Extensions must be namespaced and cannot redefine a core capability name
    (D-0004-22, INV-0004-14, AC-0004-049/050)."""
    out: list[Finding] = []
    cid = contract.get("contract_id", "-")
    core = {c.get("name", c) if isinstance(c, dict) else c
            for c in contract.get("core_capabilities", [])}
    for ext in contract.get("extensions", []):
        ns = ext.get("namespace")
        name = ext.get("name")
        if not ns:
            out.append(Finding(INVALID_TDR, P1, cid,
                               f"extension {name!r} is not namespaced "
                               "(AC-0004-049)", {}))
        if name in core:
            out.append(Finding(EXTENSION_REDEFINES_CORE, P0, cid,
                               f"extension {name!r} redefines a core capability "
                               "(AC-0004-050)", {}))
    return out


def validate_profile(profile: dict, contracts: dict) -> list[Finding]:
    out: list[Finding] = []
    pid = profile.get("provider_id", "-")
    cidx = {c["contract_id"]: c for c in contracts.get("contracts", [])}
    ref = profile.get("contract_id")
    if ref not in cidx:
        out.append(Finding(INVALID_TDR, P1, pid,
                           f"profile references unknown contract {ref!r}", {}))
        return out
    contract = cidx[ref]
    core_names = {c.get("name", c) if isinstance(c, dict) else c
                  for c in contract.get("core_capabilities", [])}
    # a profile may only claim extensions declared by the contract's namespace
    prof_ext = profile.get("extensions", {})
    for ext_key in prof_ext:
        if "." not in ext_key:
            out.append(Finding(INVALID_TDR, P1, pid,
                               f"profile extension {ext_key!r} not namespaced",
                               {}))
    return out
