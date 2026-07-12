"""Consumer Bindings, the Producer-Consumer Graph, and Blast Radius
(SP0007 §10.3, §11.10, D-0007-05/53, AC-0007-041..046).

Compatibility is consumer-specific (D-0007-05): every consumer of a protected
contract is registered as a binding with an owner, a pinned version range, a
usage profile, and an unknown-field policy. The producer-consumer graph makes
the blast radius of a contract change computable (§11.10, D-0007-53), and a
contract that may have unknown consumers is flagged fail-closed — an unknown
consumer can never be assumed migrated (AC-0007-046).
"""
from __future__ import annotations

from .model import (Finding, P1, CRITICALITY, UNKNOWN_FIELD_POLICIES,
                    CONTRACT_OWNER_MISSING, UNKNOWN_CONSUMER,
                    INVALID_COMPAT_SCHEMA)

_BINDING_REQUIRED = ("consumer_id", "contract_id", "version_range",
                     "usage_profile", "unknown_field_policy")
_CRITICAL = ("C3", "C4")


def validate_binding(b: dict) -> list[Finding]:
    """A consumer binding declares who consumes what, under which version
    range and policies (D-0007-05, AC-0007-041..043)."""
    out: list[Finding] = []
    subject = str(b.get("consumer_id") or b.get("binding_id") or "-")
    for fld in _BINDING_REQUIRED:
        if b.get(fld) in (None, "", [], {}):
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, subject,
                               f"consumer binding missing {fld} "
                               "(D-0007-05)", {"missing": fld}))
    if not (b.get("owner") or b.get("owner_capability")):
        out.append(Finding(CONTRACT_OWNER_MISSING, P1, subject,
                           "consumer binding has no owner", {}))
    if not isinstance(b.get("usage_profile", {}), dict):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, subject,
                           "usage_profile must be a dict",
                           {"usage_profile": b.get("usage_profile")}))
    if "required_fields" in b and not isinstance(b.get("required_fields"),
                                                 list):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, subject,
                           "required_fields must be a list",
                           {"required_fields": b.get("required_fields")}))
    policy = b.get("unknown_field_policy")
    if policy is not None and policy not in UNKNOWN_FIELD_POLICIES:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, subject,
                           f"unknown unknown_field_policy {policy!r}",
                           {"unknown_field_policy": policy}))
    crit = b.get("criticality")
    if crit is not None and crit not in CRITICALITY:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, subject,
                           f"unknown criticality {crit!r}", {}))
    return out


def build_graph(descriptors: list[dict], bindings: list[dict]) -> dict:
    """Producer-consumer adjacency over the contract registry (§11.10,
    D-0007-53). Also carries the may-have-unknown-consumers descriptor flags
    so blast radius stays fail-closed."""
    producers: dict = {}
    unknown_flags: dict = {}
    for d in descriptors or []:
        cid = d.get("contract_id")
        if not cid:
            continue
        producers[cid] = list(d.get("producer_refs") or d.get("producers")
                              or [])
        unknown_flags[cid] = bool(d.get("may_have_unknown_consumers"))
    consumers_of: dict = {}
    for b in bindings or []:
        cid = b.get("contract_id")
        if not cid:
            continue
        consumers_of.setdefault(cid, [])
        con = b.get("consumer_id")
        if con is not None and con not in consumers_of[cid]:
            consumers_of[cid].append(con)
    return {"producers": producers, "consumers_of": consumers_of,
            "may_have_unknown_consumers": unknown_flags}


def blast_radius(graph: dict, contract_id: str, *,
                 bindings: list[dict]) -> dict:
    """Blast radius of a change to `contract_id` (§11.10): direct consumers,
    critical (C3/C4) consumers, unknown-consumer exposure, unowned consumers,
    and historical readers that read old stored data (D-0007-53)."""
    graph = graph or {}
    direct = list((graph.get("consumers_of") or {}).get(contract_id, []))
    relevant = [b for b in (bindings or [])
                if b.get("contract_id") == contract_id]
    critical = [b.get("consumer_id") for b in relevant
                if b.get("criticality") in _CRITICAL]
    unknown = bool((graph.get("may_have_unknown_consumers") or {})
                   .get(contract_id)) or \
        any(b.get("consumer_id") == "UNKNOWN" for b in relevant)
    unowned = [b.get("consumer_id") for b in relevant
               if not (b.get("owner") or b.get("owner_capability"))]
    historical = [b.get("consumer_id") for b in relevant
                  if (b.get("usage_profile") or {}).get("historical_reader")]
    return {"direct_consumers": direct,
            "critical_consumers": critical,
            "unknown_consumers": unknown,
            "unowned_consumers": unowned,
            "historical_readers": historical}


def unknown_consumer_findings(descriptor: dict,
                              bindings: list[dict]) -> list[Finding]:
    """A contract that may have unknown consumers — an explicit descriptor
    flag, or a STABLE critical (C3/C4) contract with zero registered bindings
    — is UNKNOWN_CONSUMER (AC-0007-046). Unknown consumers can never be
    assumed migrated; fail-closed."""
    out: list[Finding] = []
    cid = descriptor.get("contract_id", "-")
    relevant = [b for b in (bindings or []) if b.get("contract_id") == cid]
    if descriptor.get("may_have_unknown_consumers"):
        out.append(Finding(UNKNOWN_CONSUMER, P1, cid,
                           "contract declares it may have unknown consumers "
                           "(AC-0007-046); blast radius is not fully known",
                           {}))
    elif not relevant and descriptor.get("stability") == "STABLE" \
            and descriptor.get("criticality") in _CRITICAL:
        out.append(Finding(UNKNOWN_CONSUMER, P1, cid,
                           "STABLE critical contract has zero registered "
                           "consumer bindings — consumers are unknown, not "
                           "absent (AC-0007-046)", {}))
    return out
