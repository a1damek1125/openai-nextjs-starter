"""Contract Difference Engine + Breaking-Change Classifier (SP0007 §11.2,
D-0007-10/11/12/18/19/20/21/22/23, AC-0007-071..081).

Diffs two contract version dicts FIELD-BY-FIELD (never a text diff, D-0007-10)
and classifies every difference DIRECTIONALLY: each record states its impact
separately for NEW_PRODUCER_TO_OLD_CONSUMER and OLD_PRODUCER_TO_NEW_CONSUMER —
a bare "breaking" boolean is constitutionally invalid (D-0007-01). Fail-closed:
a change that cannot be proven SAFE is REVIEW_REQUIRED or BREAKING (D-0007-11).
Enum evolution is consumer-world-aware (D-0007-18); default changes are always
behavioral (D-0007-19); requiredness/nullability are direction-specific
(D-0007-20); temporal meaning changes require review (D-0007-21); event
identity and idempotency changes are hard breaks (D-0007-22/23); any change to
a security_relevant field gets the security hard review (AC-0007-090).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, BREAKING_CHANGE_DETECTED,
                    DEFAULT_VALUE_BEHAVIOR_CHANGED, ENUM_EVOLUTION_BREAKING,
                    EVENT_IDENTITY_CHANGED, IDEMPOTENCY_CONTRACT_CHANGED,
                    SEMANTIC_COMPATIBILITY_REQUIRED)

# the two payload directions a producer/consumer diff speaks about (D-0007-01)
N2O = "NEW_PRODUCER_TO_OLD_CONSUMER"
O2N = "OLD_PRODUCER_TO_NEW_CONSUMER"

SAFE = "SAFE"
REVIEW = "REVIEW_REQUIRED"
BREAKING = "BREAKING"
_RANK = {SAFE: 0, REVIEW: 1, BREAKING: 2}

# type pairs (old -> new) that are pure widenings; the reverse is a narrowing
_WIDENINGS = frozenset({("int", "float"), ("int", "number"), ("int", "long"),
                        ("int", "decimal"), ("int32", "int64"),
                        ("float", "number"), ("float", "decimal"),
                        ("long", "decimal")})

_MIN_KEYS = frozenset({"minimum", "min", "min_length", "minLength",
                       "min_items", "minItems", "exclusive_minimum"})
_MAX_KEYS = frozenset({"maximum", "max", "max_length", "maxLength",
                       "max_items", "maxItems", "exclusive_maximum"})

_ENUM_KINDS = frozenset({"ENUM_VALUE_ADDED", "ENUM_VALUE_REMOVED",
                         "ENUM_CONSTRAINT_INTRODUCED",
                         "ENUM_CONSTRAINT_REMOVED"})


def _b(v) -> bool:
    """Strict schema-boolean parse: a truthy STRING like "false" must not read
    as True (SWARM-M E4). Only real True / canonical true tokens are True."""
    if v is True:
        return True
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v) if not isinstance(v, str) else False


def _rec(kind: str, path: str, old, new, n2o: str, o2n: str,
         **details) -> dict:
    return {"kind": kind, "path": path, "old": old, "new": new,
            "direction_impact": {N2O: n2o, O2N: o2n}, "details": details}


def _type_records(name: str, old_t, new_t) -> list[dict]:
    if old_t == new_t:
        return []
    path = f"fields.{name}.type"
    if (old_t, new_t) in _WIDENINGS:
        # new producer may emit values the old consumer's narrower type rejects
        return [_rec("TYPE_WIDENED", path, old_t, new_t, BREAKING, SAFE)]
    if (new_t, old_t) in _WIDENINGS:
        # old payloads may exceed the new consumer's narrower type
        return [_rec("TYPE_NARROWED", path, old_t, new_t, SAFE, BREAKING)]
    # fail-closed: an unproven type change breaks both directions
    return [_rec("TYPE_CHANGED", path, old_t, new_t, BREAKING, BREAKING)]


def _constraint_records(name: str, old_c: dict, new_c: dict) -> list[dict]:
    out: list[dict] = []
    for key in sorted(set(old_c) | set(new_c)):
        ov, nv = old_c.get(key), new_c.get(key)
        if ov == nv:
            continue
        path = f"fields.{name}.constraints.{key}"
        numeric = (isinstance(ov, (int, float)) and isinstance(nv, (int, float))
                   and not isinstance(ov, bool) and not isinstance(nv, bool))
        if ov is None:                                # constraint introduced
            out.append(_rec("CONSTRAINT_TIGHTENED", path, ov, nv, SAFE,
                            BREAKING))
        elif nv is None:                              # constraint dropped
            out.append(_rec("CONSTRAINT_LOOSENED", path, ov, nv, BREAKING,
                            SAFE))
        elif numeric and key in _MIN_KEYS:
            out.append(_rec("CONSTRAINT_TIGHTENED", path, ov, nv, SAFE,
                            BREAKING) if nv > ov else
                       _rec("CONSTRAINT_LOOSENED", path, ov, nv, BREAKING,
                            SAFE))
        elif numeric and key in _MAX_KEYS:
            out.append(_rec("CONSTRAINT_TIGHTENED", path, ov, nv, SAFE,
                            BREAKING) if nv < ov else
                       _rec("CONSTRAINT_LOOSENED", path, ov, nv, BREAKING,
                            SAFE))
        else:
            # pattern / format / unknown constraint: cannot prove direction
            out.append(_rec("CONSTRAINT_CHANGED", path, ov, nv, REVIEW,
                            REVIEW))
    return out


def _enum_records(name: str, old_e, new_e) -> list[dict]:
    out: list[dict] = []
    path = f"fields.{name}.enum"
    if old_e is None and new_e is not None:
        # old payloads may carry values outside the newly closed set
        out.append(_rec("ENUM_CONSTRAINT_INTRODUCED", path, old_e, new_e,
                        SAFE, BREAKING))
    elif old_e is not None and new_e is None:
        # new producer may now emit anything at the old consumer
        out.append(_rec("ENUM_CONSTRAINT_REMOVED", path, old_e, new_e,
                        BREAKING, SAFE))
    elif old_e is not None and new_e is not None:
        added = sorted(set(new_e) - set(old_e), key=str)
        removed = sorted(set(old_e) - set(new_e), key=str)
        if added:
            # world-dependent (D-0007-18): closed-world old consumers break;
            # fail-closed to REVIEW when the consumer's world is unknown
            out.append(_rec("ENUM_VALUE_ADDED", path, old_e, new_e, REVIEW,
                            SAFE, added=added))
        if removed:
            out.append(_rec("ENUM_VALUE_REMOVED", path, old_e, new_e, SAFE,
                            BREAKING, removed=removed))
    return out


def _field_records(name: str, o: dict, n: dict) -> list[dict]:
    path = f"fields.{name}"
    recs: list[dict] = []
    recs.extend(_type_records(name, o.get("type"), n.get("type")))

    o_req, n_req = _b(o.get("required", False)), _b(n.get("required", False))
    if not o_req and n_req:
        recs.append(_rec("REQUIREDNESS_TIGHTENED", f"{path}.required", o_req,
                         n_req, SAFE, BREAKING))     # old payloads may omit it
    elif o_req and not n_req:
        recs.append(_rec("REQUIREDNESS_RELAXED", f"{path}.required", o_req,
                         n_req, BREAKING, SAFE))     # new producer may omit it

    o_nul, n_nul = _b(o.get("nullable", False)), _b(n.get("nullable", False))
    if o_nul and not n_nul:
        recs.append(_rec("NULLABILITY_TIGHTENED", f"{path}.nullable", o_nul,
                         n_nul, SAFE, BREAKING))     # old payloads may be null
    elif not o_nul and n_nul:
        recs.append(_rec("NULLABILITY_RELAXED", f"{path}.nullable", o_nul,
                         n_nul, BREAKING, SAFE))     # new producer may send null

    recs.extend(_constraint_records(name, o.get("constraints") or {},
                                    n.get("constraints") or {}))
    recs.extend(_enum_records(name, o.get("enum"), n.get("enum")))

    if o.get("default") != n.get("default"):
        # a default is behavior, not decoration (D-0007-19): never SAFE
        recs.append(_rec("DEFAULT_CHANGED", f"{path}.default",
                         o.get("default"), n.get("default"), REVIEW, REVIEW,
                         security_relevant=bool(o.get("security_relevant") or
                                                n.get("security_relevant"))))

    o_fn, n_fn = o.get("field_number"), n.get("field_number")
    if o_fn != n_fn and (o_fn is not None or n_fn is not None):
        recs.append(_rec("FIELD_NUMBER_CHANGED", f"{path}.field_number",
                         o_fn, n_fn, BREAKING, BREAKING))  # wire identity

    if bool(o.get("security_relevant", False)) != \
            bool(n.get("security_relevant", False)):
        recs.append(_rec("SECURITY_RELEVANT_FLAG_CHANGED",
                         f"{path}.security_relevant",
                         bool(o.get("security_relevant", False)),
                         bool(n.get("security_relevant", False)),
                         BREAKING, BREAKING, security_relevant=True))

    # security hard review (AC-0007-090): no change on a security_relevant
    # field may pass as SAFE; a security default change is BREAKING (§20.35 M6)
    if o.get("security_relevant") or n.get("security_relevant"):
        for r in recs:
            r["details"]["security_relevant"] = True
            for direction, impact in list(r["direction_impact"].items()):
                if r["kind"] == "DEFAULT_CHANGED":
                    r["direction_impact"][direction] = BREAKING
                elif impact == SAFE:
                    r["direction_impact"][direction] = REVIEW
    return recs


def _dict_part_records(kind: str, path: str, old_d: dict,
                       new_d: dict) -> list[dict]:
    """One record when a bridged-aware schema part (event_identity /
    idempotency) materially differs (D-0007-22/23). `bridged` must be the
    boolean True to soften the break — anything else fails closed."""
    old_d, new_d = old_d or {}, new_d or {}
    changed = [k for k in sorted(set(old_d) | set(new_d)) if k != "bridged"
               and old_d.get(k) != new_d.get(k)]
    if not changed:
        return []
    bridged = new_d.get("bridged") is True
    impact = REVIEW if bridged else BREAKING
    return [_rec(kind, path, old_d, new_d, impact, impact,
                 changed_keys=changed, bridged=bridged)]


def diff_contracts(old: dict, new: dict) -> list[dict]:
    """Classified, directional difference records between two contract version
    dicts (§11.2). Deterministic: fields and keys are walked in sorted order."""
    old_s = (old or {}).get("schema") or {}
    new_s = (new or {}).get("schema") or {}
    old_f = old_s.get("fields") or {}
    new_f = new_s.get("fields") or {}
    recs: list[dict] = []

    for name in sorted(set(old_f) | set(new_f)):
        o, n = old_f.get(name), new_f.get(name)
        path = f"fields.{name}"
        if o is None:
            if n.get("required", False):
                # old requests won't carry it (D-0007-12)
                recs.append(_rec("REQUIRED_FIELD_ADDED", path, None, n,
                                 SAFE, BREAKING))
            else:
                recs.append(_rec("FIELD_ADDED", path, None, n, SAFE, SAFE))
        elif n is None:
            # new producer stops sending it: breaks old consumers that require
            # it; consumer-aware refinement happens in classify()
            recs.append(_rec("FIELD_REMOVED", path, o, None, BREAKING, REVIEW,
                             required=bool(o.get("required", False)),
                             security_relevant=bool(
                                 o.get("security_relevant", False))))
        else:
            recs.extend(_field_records(name, o, n))

    if (old_s.get("ordering") or []) != (new_s.get("ordering") or []):
        recs.append(_rec("ORDERING_CHANGED", "ordering",
                         old_s.get("ordering") or [],
                         new_s.get("ordering") or [], REVIEW, REVIEW))

    old_t, new_t = old_s.get("temporal") or {}, new_s.get("temporal") or {}
    for key in sorted(set(old_t) | set(new_t)):
        if old_t.get(key) != new_t.get(key):
            recs.append(_rec("TEMPORAL_MEANING_CHANGED", f"temporal.{key}",
                             old_t.get(key), new_t.get(key), REVIEW, REVIEW))

    recs.extend(_dict_part_records("EVENT_IDENTITY_CHANGED", "event_identity",
                                   old_s.get("event_identity"),
                                   new_s.get("event_identity")))
    recs.extend(_dict_part_records("IDEMPOTENCY_CHANGED", "idempotency",
                                   old_s.get("idempotency"),
                                   new_s.get("idempotency")))
    return recs


def _classify_one(d: dict, consumer: dict | None) -> str:
    base = max(d["direction_impact"].values(), key=_RANK.__getitem__)
    kind = d["kind"]
    if kind == "ENUM_VALUE_ADDED" and not d["details"].get("security_relevant"):
        # D-0007-18: breaking iff the consumer lives in a closed enum world;
        # unknown world fails closed to REVIEW_REQUIRED
        world = (consumer or {}).get("enum_world")
        if world == "CLOSED":
            return BREAKING
        if world == "OPEN":
            return SAFE
        return REVIEW
    if kind == "FIELD_REMOVED" and consumer is not None:
        field = d["path"].split(".", 1)[-1]
        reads = consumer.get("reads_removed_field")
        needs = (field in (consumer.get("required_fields") or [])
                 or reads is True
                 or (isinstance(reads, (list, tuple, set)) and field in reads))
        return BREAKING if needs else REVIEW
    if kind == "DEFAULT_CHANGED":
        # ALWAYS at least review (D-0007-19); breaking when security-relevant
        if d["details"].get("security_relevant"):
            return BREAKING
        return max(base, REVIEW, key=_RANK.__getitem__)
    return base


def classify(diffs: list[dict], *, consumer: dict | None = None) -> dict:
    """Bucket diff records into breaking / review_required / safe, optionally
    refined by a concrete consumer (enum_world, required_fields,
    reads_removed_field). Without a consumer the classification is the
    fail-closed worst case over both directions."""
    out: dict = {"breaking": [], "review_required": [], "safe": []}
    for d in diffs:
        cls = _classify_one(d, consumer)
        annotated = dict(d)
        annotated["classification"] = cls
        out[{BREAKING: "breaking", REVIEW: "review_required",
             SAFE: "safe"}[cls]].append(annotated)
    out["is_breaking"] = bool(out["breaking"])
    return out


def breaking_findings(old: dict, new: dict, *, consumer: dict | None = None,
                      old_label: str = "old",
                      new_label: str = "new") -> list[Finding]:
    """Findings for the old->new evolution: BREAKING_CHANGE_DETECTED (P0) per
    breaking diff, ENUM_EVOLUTION_BREAKING (P0) for enum breaks,
    EVENT_IDENTITY_CHANGED / IDEMPOTENCY_CONTRACT_CHANGED (P0, D-0007-22/23),
    DEFAULT_VALUE_BEHAVIOR_CHANGED (P1; P0 when security-relevant, D-0007-19),
    and review-level P2 findings for temporal/ordering meaning changes
    (D-0007-21)."""
    buckets = classify(diff_contracts(old, new), consumer=consumer)
    out: list[Finding] = []
    for bucket in ("breaking", "review_required", "safe"):
        for d in buckets[bucket]:
            subject = f"{old_label}->{new_label}:{d['path']}"
            details = {"diff": d, "old_label": old_label,
                       "new_label": new_label}
            kind = d["kind"]
            if kind == "DEFAULT_CHANGED":
                sev = P0 if d["details"].get("security_relevant") else P1
                out.append(Finding(DEFAULT_VALUE_BEHAVIOR_CHANGED, sev,
                                   subject, "default value changed — defaults "
                                   "are behavior (D-0007-19)", details))
            elif kind in ("TEMPORAL_MEANING_CHANGED", "ORDERING_CHANGED"):
                out.append(Finding(SEMANTIC_COMPATIBILITY_REQUIRED, P2,
                                   subject, "temporal/ordering meaning changed "
                                   "— semantic review required (D-0007-21)",
                                   details))
            elif kind == "EVENT_IDENTITY_CHANGED":
                sev = P0 if bucket == "breaking" else P2
                out.append(Finding(EVENT_IDENTITY_CHANGED, sev, subject,
                                   "event identity contract changed "
                                   "(D-0007-22)", details))
            elif kind == "IDEMPOTENCY_CHANGED":
                sev = P0 if bucket == "breaking" else P2
                out.append(Finding(IDEMPOTENCY_CONTRACT_CHANGED, sev, subject,
                                   "idempotency contract changed (D-0007-23)",
                                   details))
            elif bucket == "breaking" and kind in _ENUM_KINDS:
                out.append(Finding(ENUM_EVOLUTION_BREAKING, P0, subject,
                                   "enum evolution breaks a consumer "
                                   "(D-0007-18)", details))
            elif kind in _ENUM_KINDS:
                # a fail-closed / open-world enum change is not silently SAFE —
                # it still requires review (SWARM-M E9; D-0007-18)
                out.append(Finding(SEMANTIC_COMPATIBILITY_REQUIRED, P1, subject,
                                   "enum evolution requires consumer-aware "
                                   "review (D-0007-18)", details))
            elif bucket == "breaking":
                out.append(Finding(BREAKING_CHANGE_DETECTED, P0, subject,
                                   f"breaking change {kind} at {d['path']}",
                                   details))
    return out
