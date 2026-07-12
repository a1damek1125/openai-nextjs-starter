"""Evolution Policies (SP0007 §11.3, D-0007-16/17/18/19/20/21/22/23,
AC-0007-082..090).

Every contract declares its unknown-field policy explicitly (D-0007-16) — a
silent discard under PRESERVE is UNKNOWN_FIELD_LOSS (P0). Retired identifiers
(field numbers, enum codes, event ids, field names) are reserved FOREVER; any
reuse with a new meaning is RESERVED_IDENTIFIER_REUSED (P0, D-0007-17,
INV-0007-14/15). Enum evolution is world-aware and fails closed (D-0007-18);
default changes are behavioral, and a security-relevant default change is a
security downgrade (D-0007-19, §20.35 M6); nullability/requiredness changes
are direction-specific breaks (D-0007-20); temporal meaning changes require
review (D-0007-21); event identity and idempotency changes are hard breaks
unless explicitly bridged with boolean True (D-0007-22/23).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, UNKNOWN_FIELD_POLICIES,
                    UNKNOWN_FIELD_LOSS, RESERVED_IDENTIFIER_REUSED,
                    DEFAULT_VALUE_BEHAVIOR_CHANGED, EVENT_IDENTITY_CHANGED,
                    IDEMPOTENCY_CONTRACT_CHANGED, BREAKING_CHANGE_DETECTED,
                    SEMANTIC_COMPATIBILITY_REQUIRED, CONSUMER_INCOMPATIBLE,
                    SECURITY_DOWNGRADE_BLOCKED, INVALID_COMPAT_SCHEMA)

# name fragments that make an unknown field security-ish — IGNORE_SAFELY must
# never silently drop one of these (fail-closed, §20.35)
_SECURITY_MARKERS = ("auth", "token", "secret", "security", "permission",
                     "role", "scope", "acl", "cred", "password", "sign",
                     "priv")


def _is_security_ish(name: str) -> bool:
    low = str(name).lower()
    return any(m in low for m in _SECURITY_MARKERS)


def _strict_bool(v) -> bool:
    """Parse a schema boolean strictly so a truthy STRING like "false" is not
    read as True (SWARM-M E4). Only real booleans and the canonical true tokens
    count as True; everything else (including "false"/"no"/"0") is False."""
    if v is True:
        return True
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v) if not isinstance(v, str) else False


def apply_unknown_field_policy(payload: dict, known_fields,
                               policy: str) -> tuple[dict, list[Finding]]:
    """Apply a declared unknown-field policy (D-0007-16) and return
    (processed_payload, findings). PRESERVE keeps unknowns; IGNORE_SAFELY
    drops them only if none is security-ish; REJECT flags every unknown;
    QUARANTINE moves them under "_quarantined"; REVIEW_REQUIRED flags them for
    review. An undeclared/unknown policy fails closed: nothing is dropped."""
    known = set(known_fields)
    payload = dict(payload or {})
    unknown = [k for k in sorted(payload, key=str) if k not in known]
    findings: list[Finding] = []

    if policy not in UNKNOWN_FIELD_POLICIES:
        findings.append(Finding(INVALID_COMPAT_SCHEMA, P1, str(policy),
                                f"unknown unknown-field policy {policy!r} — "
                                "fail-closed, nothing dropped (D-0007-16)",
                                {"unknown_fields": unknown}))
        return payload, findings
    if not unknown or policy == "PRESERVE":
        return payload, findings

    if policy == "IGNORE_SAFELY":
        security_ish = [k for k in unknown if _is_security_ish(k)]
        if security_ish:
            for k in security_ish:
                findings.append(Finding(
                    SECURITY_DOWNGRADE_BLOCKED, P0, k,
                    "refusing to silently drop security-relevant unknown "
                    "field (§20.35, AC-0007-090)", {"policy": policy}))
            return payload, findings          # keep everything, fail-closed
        return {k: v for k, v in payload.items() if k in known}, findings

    if policy == "REJECT":
        for k in unknown:
            findings.append(Finding(CONSUMER_INCOMPATIBLE, P1, k,
                                    "unknown field rejected under REJECT "
                                    "policy (D-0007-16)", {"policy": policy}))
        return payload, findings

    if policy == "QUARANTINE":
        processed = {k: v for k, v in payload.items() if k in known}
        processed["_quarantined"] = {k: payload[k] for k in unknown}
        return processed, findings

    # REVIEW_REQUIRED: keep the payload intact, flag every unknown
    for k in unknown:
        findings.append(Finding(SEMANTIC_COMPATIBILITY_REQUIRED, P1, k,
                                "unknown field requires review before "
                                "processing (D-0007-16)", {"policy": policy}))
    return payload, findings


def unknown_field_findings(payload: dict, known_fields,
                           policy: str) -> list[Finding]:
    return apply_unknown_field_policy(payload, known_fields, policy)[1]


def preservation_findings(original: dict, roundtripped: dict, known_fields,
                          policy: str) -> list[Finding]:
    """Under PRESERVE (and QUARANTINE), an unknown field present in the
    original that is gone — or mutated — after a round-trip is silent data
    loss: UNKNOWN_FIELD_LOSS (P0, D-0007-16, AC-0007-083)."""
    if policy not in ("PRESERVE", "QUARANTINE"):
        return []
    known = set(known_fields)
    original = original or {}
    roundtripped = roundtripped or {}
    quarantined = roundtripped.get("_quarantined") or {} \
        if policy == "QUARANTINE" else {}
    out: list[Finding] = []
    for k in sorted((k for k in original if k not in known), key=str):
        if k in roundtripped:
            survived, value = True, roundtripped[k]
        elif policy == "QUARANTINE" and k in quarantined:
            survived, value = True, quarantined[k]
        else:
            survived, value = False, None
        if not survived:
            out.append(Finding(UNKNOWN_FIELD_LOSS, P0, k,
                               f"unknown field {k!r} silently discarded in "
                               f"round-trip under {policy} policy "
                               "(D-0007-16)", {"policy": policy}))
        elif value != original[k]:
            out.append(Finding(UNKNOWN_FIELD_LOSS, P0, k,
                               f"unknown field {k!r} mutated in round-trip "
                               f"under {policy} policy (D-0007-16)",
                               {"policy": policy, "old": original[k],
                                "new": value}))
    return out


def reserved_identifier_findings(registry: dict,
                                 candidate: dict) -> list[Finding]:
    """Retired identifiers are reserved forever (D-0007-17, INV-0007-14/15):
    a candidate contract reusing a reserved field number, enum code, event id
    or field name with a new meaning is RESERVED_IDENTIFIER_REUSED (P0)."""
    registry = registry or {}
    # normalize identifiers to strings so a reused field_number cannot evade via
    # int/str type confusion ("7" vs 7) (SWARM-M E5; INV-0007-14/15)
    numbers = {str(x) for x in (registry.get("reserved_field_numbers") or [])}
    enum_codes = {str(x) for x in (registry.get("reserved_enum_codes") or [])}
    event_ids = {str(x) for x in (registry.get("reserved_event_ids") or [])}
    names = {str(x) for x in (registry.get("reserved_field_names") or [])}
    candidate = candidate or {}
    schema = candidate.get("schema") or candidate
    fields = (schema.get("fields") or {}) if isinstance(schema, dict) else {}
    out: list[Finding] = []

    def _hit(identifier, id_kind, subject):
        out.append(Finding(RESERVED_IDENTIFIER_REUSED, P0, subject,
                           f"reserved {id_kind} {identifier!r} reused with a "
                           "new meaning — retired identifiers are reserved "
                           "forever (D-0007-17, INV-0007-14/15)",
                           {"identifier": identifier, "id_kind": id_kind}))

    for name in sorted(fields, key=str):
        spec = fields[name] or {}
        if str(name) in names:
            _hit(name, "field_name", str(name))
        fn = spec.get("field_number")
        if fn is not None and str(fn) in numbers:
            _hit(fn, "field_number", str(name))
        for code in spec.get("enum") or []:
            if str(code) in enum_codes:
                _hit(code, "enum_code", str(name))

    declared_events = list(candidate.get("event_ids") or [])
    if candidate.get("event_id") is not None:
        declared_events.append(candidate["event_id"])
    for ev in declared_events:
        if str(ev) in event_ids:
            _hit(ev, "event_id", str(ev))
    return out


def enum_evolution(old_values: list, new_values: list, world: str) -> dict:
    """World-aware enum evolution verdict (D-0007-18): removal is always
    BREAKING; addition is BREAKING for a CLOSED world, REVIEW_REQUIRED for an
    OPEN world, and fails closed to REVIEW_REQUIRED for an unknown world."""
    added = sorted(set(new_values or []) - set(old_values or []), key=str)
    removed = sorted(set(old_values or []) - set(new_values or []), key=str)
    if removed:
        classification = "BREAKING"
    elif added:
        classification = "BREAKING" if world == "CLOSED" else "REVIEW_REQUIRED"
    else:
        classification = "SAFE"
    return {"added": added, "removed": removed,
            "classification": classification}


def default_change_findings(old_field: dict, new_field: dict, *,
                            name: str) -> list[Finding]:
    """A default is behavior (D-0007-19): any change is at least P1; a change
    to a security_relevant field's default is a security default weakening —
    P0 (§20.35 M6, AC-0007-090)."""
    old_field, new_field = old_field or {}, new_field or {}
    if old_field.get("default") == new_field.get("default"):
        return []
    security = bool(old_field.get("security_relevant") or
                    new_field.get("security_relevant"))
    return [Finding(DEFAULT_VALUE_BEHAVIOR_CHANGED, P0 if security else P1,
                    name, "default value changed — defaults are behavior "
                    "(D-0007-19)" + (" on a security-relevant field "
                                     "(§20.35 M6)" if security else ""),
                    {"old_default": old_field.get("default"),
                     "new_default": new_field.get("default"),
                     "security_relevant": security})]


def nullability_findings(old_field: dict, new_field: dict, *, name: str,
                         direction: str) -> list[Finding]:
    """Direction-specific nullability/requiredness breaks (D-0007-20):
    tightening (nullable->non-null, optional->required) breaks payloads coming
    from the OLD side; relaxing breaks payloads going to the OLD side."""
    old_field, new_field = old_field or {}, new_field or {}
    from_old = direction in ("OLD_PRODUCER_TO_NEW_CONSUMER",
                             "OLD_WRITER_TO_NEW_READER")
    out: list[Finding] = []

    def _break(msg, old, new):
        out.append(Finding(BREAKING_CHANGE_DETECTED, P0, name,
                           msg + f" (D-0007-20, {direction})",
                           {"direction": direction, "old": old, "new": new}))

    o_nul = _strict_bool(old_field.get("nullable", False))
    n_nul = _strict_bool(new_field.get("nullable", False))
    if o_nul and not n_nul and from_old:
        _break("nullable->non-null: old payloads may carry null", o_nul, n_nul)
    elif not o_nul and n_nul and not from_old:
        _break("non-null->nullable: new producer may send null to a consumer "
               "that cannot handle it", o_nul, n_nul)

    o_req = _strict_bool(old_field.get("required", False))
    n_req = _strict_bool(new_field.get("required", False))
    if not o_req and n_req and from_old:
        _break("optional->required: old payloads may omit the field",
               o_req, n_req)
    elif o_req and not n_req and not from_old:
        _break("required->optional: new producer may omit a field the old "
               "consumer requires", o_req, n_req)
    return out


# temporal keys whose change alters MEANING, not presentation (D-0007-21)
_TEMPORAL_SIGNIFICANT = frozenset({"timezone", "precision", "ordering",
                                   "late_event_policy", "late_events",
                                   "deadline", "deadline_semantics", "clock",
                                   "time_basis"})


def temporal_findings(old_temporal: dict, new_temporal: dict) -> list[Finding]:
    """Timezone / precision / ordering / late-event / deadline semantics
    changes require semantic review (D-0007-21) — P1 for meaning-bearing keys,
    P2 for the rest."""
    old_temporal, new_temporal = old_temporal or {}, new_temporal or {}
    out: list[Finding] = []
    for key in sorted(set(old_temporal) | set(new_temporal), key=str):
        ov, nv = old_temporal.get(key), new_temporal.get(key)
        if ov == nv:
            continue
        sev = P1 if key in _TEMPORAL_SIGNIFICANT else P2
        out.append(Finding(SEMANTIC_COMPATIBILITY_REQUIRED, sev,
                           f"temporal.{key}",
                           f"temporal meaning changed for {key!r} — review "
                           "required (D-0007-21)", {"old": ov, "new": nv}))
    return out


def _bridged_change_findings(old_d: dict, new_d: dict, kind: str, subject: str,
                             decision: str) -> list[Finding]:
    old_d, new_d = old_d or {}, new_d or {}
    changed = [k for k in sorted(set(old_d) | set(new_d), key=str)
               if k != "bridged" and old_d.get(k) != new_d.get(k)]
    if not changed:
        return []
    # a bridge must be the boolean True — truthy strings fail closed
    bridged = new_d.get("bridged") is True
    sev = P2 if bridged else P0
    return [Finding(kind, sev, f"{subject}.{k}",
                    f"{subject} contract changed for {k!r}"
                    + (" — bridged" if bridged else " without a bridge")
                    + f" ({decision})",
                    {"old": old_d.get(k), "new": new_d.get(k),
                     "bridged": bridged}) for k in changed]


def event_identity_findings(old_ident: dict,
                            new_ident: dict) -> list[Finding]:
    """Event id meaning / correlation / dedup / causation / partition key
    changes are EVENT_IDENTITY_CHANGED P0 unless explicitly bridged with
    boolean True (D-0007-22)."""
    return _bridged_change_findings(old_ident, new_ident,
                                    EVENT_IDENTITY_CHANGED, "event_identity",
                                    "D-0007-22")


def idempotency_findings(old: dict, new: dict) -> list[Finding]:
    """Idempotency key scope / interpretation changes are
    IDEMPOTENCY_CONTRACT_CHANGED P0 unless explicitly bridged (D-0007-23)."""
    return _bridged_change_findings(old, new, IDEMPOTENCY_CONTRACT_CHANGED,
                                    "idempotency", "D-0007-23")
