"""Approval Topology + Class Lattice + Context-Bound Token + No-Self-Approval +
Quorum (SP0006 §9.8, §11.8, D-0006-32..38, INV-0006-23..27).

Approval authority is a lattice of classes A0..A5 (D-0006-34). The REQUIRED class
is the conservative JOIN (max) over independent floors — effect, risk,
irreversibility, data, authority, regulatory, tenant (D-0006-35); a lower class
can never satisfy a higher floor. A token binds the exact material action
(fingerprints over target / amount / parameters, INV-0006-23/24/25): any material
change or expiry INVALIDATES the token (§11.8, D-0006-33). The approver must be
independent of the execution identity — approving one's own work is a hard
violation (D-0006-36). Multi-party actions additionally require a satisfied
QUORUM: count, roles, distinct identities, no shared owner (D-0006-37).

Module note (D-0006-38): approval is authorization to ACT, NOT proof of OUTCOME.
A valid token never asserts the work succeeded; outcome verification is a
separate concern (§9.4) and the two must never be conflated here.

Governance tooling only; product runtime must never import it (INV-0006-46).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, APPROVAL_CLASSES, APPROVAL_CLASS_RANK,
                    APPROVAL_STATES, APPROVAL_CLASS_INSUFFICIENT,
                    APPROVAL_CONTEXT_MISMATCH, SELF_APPROVAL_DETECTED)
from .canon import (core_hash, action_fingerprint, target_fingerprint,
                    material_parameters_hash)

_A0 = APPROVAL_CLASSES[0]
_AMAX = APPROVAL_CLASSES[-1]

# Each floor maps a context signal to the minimum approval class it demands.
# Fail-closed: an UNKNOWN or unrecognized signal maps to the top class.
_LEVEL_TO_CLASS = {"NONE": "A0", "LOW": "A1", "MEDIUM": "A2", "HIGH": "A4",
                   "CRITICAL": "A5", "UNKNOWN": "A5"}
_EFFECT_TO_CLASS = {"READ": "A0", "DRAFT": "A0", "SIMULATE": "A0",
                    "LOCAL_WRITE": "A1", "LOCAL_COMMIT": "A2",
                    "REVERSIBLE_EXTERNAL": "A2", "COMMUNICATION": "A3",
                    "IRREVERSIBLE_EXTERNAL": "A4", "PAYMENT": "A5"}


def _as_set(v) -> set:
    if isinstance(v, (list, set, tuple)):
        return {str(x) for x in v}
    if v is None:
        return set()
    return {str(v)}


def _to_class(v, table: dict, *, fail_closed: bool = True) -> str:
    """Resolve a context signal to an approval class. A class passes through; a
    known level/effect maps via `table`; None is the floor (A0); anything else is
    fail-closed to the top class (or A0 if `fail_closed` is False)."""
    if v is None:
        return _A0
    if v in APPROVAL_CLASS_RANK:
        return v
    key = str(v).upper()
    if key in table:
        return table[key]
    return _AMAX if fail_closed else _A0


def _max_class(classes) -> str:
    best = _A0
    for c in classes:
        if APPROVAL_CLASS_RANK.get(c, -1) > APPROVAL_CLASS_RANK.get(best, -1):
            best = c
    return best


def _floor_components(context: dict) -> dict:
    """The class demanded by each independent floor (D-0006-35). The required
    class is the JOIN (max) of these; helper is exposed for auditability."""
    ctx = context or {}
    risk_vec = ctx.get("risk_vector")
    if isinstance(risk_vec, dict) and risk_vec:
        risk = _max_class(_to_class(v, _LEVEL_TO_CLASS) for v in risk_vec.values())
    else:
        risk = _to_class(ctx.get("risk_level"), _LEVEL_TO_CLASS)
    return {
        "EffectFloor": _to_class(ctx.get("effect_class"), _EFFECT_TO_CLASS),
        "RiskFloor": risk,
        "IrreversibilityFloor": _to_class(ctx.get("irreversibility"),
                                          _LEVEL_TO_CLASS),
        "DataFloor": _to_class(ctx.get("data_sensitivity"), _LEVEL_TO_CLASS),
        "AuthorityFloor": _to_class(ctx.get("authority_required"),
                                    _LEVEL_TO_CLASS),
        "RegulatoryFloor": _to_class(ctx.get("regulatory_sensitivity"),
                                     _LEVEL_TO_CLASS),
        "TenantFloor": _to_class(ctx.get("tenant_floor"), _LEVEL_TO_CLASS),
    }


def approval_floor(context: dict) -> str:
    """The single required approval class: conservative JOIN over all floors
    (D-0006-35). A lower class can never satisfy a higher floor."""
    return _max_class(_floor_components(context).values())


def class_sufficient(provided: str, required: str) -> bool:
    """provided >= required in the class lattice. Fail-closed on unknown values:
    an unknown provided class never suffices; an unknown required class is never
    satisfied (D-0006-34)."""
    pr = APPROVAL_CLASS_RANK.get(provided, -1)
    rr = APPROVAL_CLASS_RANK.get(required, len(APPROVAL_CLASSES))
    return pr >= rr


def _material_core(*, work_instance_hash, action, required_class,
                   approver_class, risk_snapshot) -> dict:
    params = action.get("parameters") if isinstance(action, dict) else None
    return {
        "work_instance_hash": work_instance_hash,
        "action_fingerprint": action_fingerprint(action),
        "target_fingerprint": target_fingerprint(action),
        "material_parameters_hash": material_parameters_hash(params),
        "effect_class": action.get("effect_class")
        if isinstance(action, dict) else None,
        "risk_snapshot_hash": core_hash(risk_snapshot),
        "required_class": required_class,
        "approver_class": approver_class,
    }


def issue_token(*, work_instance_hash, action, required_class, approver_id,
                approver_class, issued_at, expires_at, maximum_uses=1,
                risk_snapshot=None, token_id=None) -> dict:
    """Mint a context-bound approval token (D-0006-32). The integrity hash digests
    exactly the material fields, so any later material change is detectable."""
    core = _material_core(work_instance_hash=work_instance_hash, action=action,
                          required_class=required_class,
                          approver_class=approver_class,
                          risk_snapshot=risk_snapshot)
    token = dict(core)
    token.update({
        "token_id": token_id,
        "approver_id": approver_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "maximum_uses": maximum_uses,
        "current_uses": 0,
        "status": "ACTIVE",  # APPROVAL_STATES
        "integrity_hash": core_hash(core),
    })
    return token


def validate_token(token: dict, *, action, work_instance_hash, now,
                   provided_context=None) -> tuple[bool, list[Finding]]:
    """ApprovalValid = ContextMatch ∧ ClassSufficient ∧ ApproverEligible ∧
    NotExpired ∧ UseAvailable ∧ IntegrityValid (§11.8). Returns (ok, findings);
    ok is False whenever any blocking (P0/P1) finding is raised."""
    out: list[Finding] = []
    tid = token.get("token_id") or "-"

    # --- ContextMatch: bound work instance + recomputed material fingerprints ---
    recomputed = {
        "action_fingerprint": action_fingerprint(action),
        "target_fingerprint": target_fingerprint(action),
        "material_parameters_hash": material_parameters_hash(
            action.get("parameters") if isinstance(action, dict) else None),
    }
    if token.get("work_instance_hash") != work_instance_hash:
        out.append(Finding(APPROVAL_CONTEXT_MISMATCH, P0, tid,
                           "token bound to a different work instance",
                           {"reason": "work_instance_hash"}))
    for field, label in (("action_fingerprint", "action"),
                         ("target_fingerprint", "target"),
                         ("material_parameters_hash", "material parameters")):
        if token.get(field) != recomputed[field]:
            out.append(Finding(APPROVAL_CONTEXT_MISMATCH, P0, tid,
                               f"{label} changed since approval — token void",
                               {"reason": field,
                                "approved": token.get(field),
                                "observed": recomputed[field]}))

    # optional caller-supplied context deltas (e.g. required_class re-derivation)
    if provided_context:
        rc = provided_context.get("required_class")
        if rc is not None and rc != token.get("required_class"):
            out.append(Finding(APPROVAL_CONTEXT_MISMATCH, P0, tid,
                               "required class re-derived to a different value",
                               {"reason": "required_class",
                                "approved": token.get("required_class"),
                                "observed": rc}))

    # --- IntegrityValid ---
    core = {k: token.get(k) for k in ("work_instance_hash", "action_fingerprint",
                                      "target_fingerprint",
                                      "material_parameters_hash", "effect_class",
                                      "risk_snapshot_hash", "required_class",
                                      "approver_class")}
    if token.get("integrity_hash") != core_hash(core):
        out.append(Finding(APPROVAL_CONTEXT_MISMATCH, P0, tid,
                           "token integrity hash mismatch — tampered/void",
                           {"reason": "integrity"}))

    # --- NotExpired ---
    exp = token.get("expires_at")
    if exp is not None and now is not None and now > exp:
        out.append(Finding(APPROVAL_CONTEXT_MISMATCH, P1, tid,
                           f"token expired at {exp}",
                           {"reason": "expired", "expires_at": exp, "now": now}))

    # --- ApproverEligible + status ---
    if token.get("status") not in ("ACTIVE", "ISSUED"):
        out.append(Finding(APPROVAL_CONTEXT_MISMATCH, P1, tid,
                           f"token not in an active state: {token.get('status')}",
                           {"reason": "status", "status": token.get("status")}))
    if not token.get("approver_id"):
        out.append(Finding(APPROVAL_CLASS_INSUFFICIENT, P1, tid,
                           "token has no eligible approver identity",
                           {"reason": "approver_missing"}))

    # --- ClassSufficient ---
    if not class_sufficient(token.get("approver_class"),
                            token.get("required_class")):
        out.append(Finding(APPROVAL_CLASS_INSUFFICIENT, P1, tid,
                           "approver class below required class",
                           {"provided": token.get("approver_class"),
                            "required": token.get("required_class")}))
    # re-derive the required class from the LIVE action/risk context and reject a
    # token whose stored required_class was downgraded below the true floor — the
    # integrity_hash is not a secret-keyed signature, so a self-consistent
    # tampered token must still be re-checked against context (SWARM-M E2)
    ctx = {"effect_class": (action.get("effect_class")
                            if isinstance(action, dict) else None)
           or token.get("effect_class"),
           "risk": (provided_context or {}).get("risk")
           or (action.get("risk") if isinstance(action, dict) else None)}
    derived_floor = approval_floor(ctx)
    if not class_sufficient(token.get("required_class"), derived_floor):
        out.append(Finding(APPROVAL_CLASS_INSUFFICIENT, P0, tid,
                           "token required_class is below the class floor "
                           "derived from the live action context",
                           {"token_required": token.get("required_class"),
                            "derived_floor": derived_floor}))
    if not class_sufficient(token.get("approver_class"), derived_floor):
        out.append(Finding(APPROVAL_CLASS_INSUFFICIENT, P0, tid,
                           "approver class below the context-derived floor",
                           {"approver_class": token.get("approver_class"),
                            "derived_floor": derived_floor}))

    # --- UseAvailable ---
    mu = token.get("maximum_uses")
    cu = token.get("current_uses", 0)
    if isinstance(mu, int) and isinstance(cu, int) and cu >= mu:
        out.append(Finding(APPROVAL_CONTEXT_MISMATCH, P1, tid,
                           "token uses exhausted",
                           {"reason": "uses", "current_uses": cu,
                            "maximum_uses": mu}))

    ok = not any(f.severity in (P0, P1) for f in out)
    return ok, out


def no_self_approval(*, proposer, planner, executor, approver, verifier,
                     independence_required=True) -> list[Finding]:
    """The approver must be independent of the execution identity (D-0006-36).
    If the approver is also the proposer, planner or executor of the same work,
    that is SELF_APPROVAL_DETECTED (P0)."""
    out: list[Finding] = []
    if not independence_required or approver is None:
        return out

    def _canon(x):
        return str(x).strip().casefold() if x is not None else None
    approver_c = _canon(approver)
    for role, ident in (("proposer", proposer), ("planner", planner),
                        ("executor", executor)):
        if ident is not None and approver_c == _canon(ident):
            out.append(Finding(SELF_APPROVAL_DETECTED, P0, str(approver),
                               f"approver is also the {role} — self-approval",
                               {"role": role, "identity": approver,
                                "verifier": verifier}))
    return out


def quorum_satisfied(approvers: list[dict],
                     policy: dict) -> tuple[bool, list[Finding]]:
    """Multi-party approval requires a satisfied quorum (D-0006-37): the declared
    number of approvers, any required roles, DISTINCT identities (independence),
    and no shared owner (conflict-of-interest). Returns (ok, findings)."""
    out: list[Finding] = []
    approvers = approvers or []
    policy = policy or {}
    subj = str(policy.get("policy_id") or "quorum")

    need = policy.get("number_of_approvers", policy.get("required_approvers", 1))
    if isinstance(need, int) and len(approvers) < need:
        out.append(Finding(APPROVAL_CLASS_INSUFFICIENT, P1, subj,
                           f"quorum needs {need} approvers, got {len(approvers)}",
                           {"required": need, "actual": len(approvers)}))

    present_roles = {a.get("role") for a in approvers if a.get("role")}
    missing = [r for r in _as_set(policy.get("required_roles"))
               if r not in present_roles]
    if missing:
        out.append(Finding(APPROVAL_CLASS_INSUFFICIENT, P1, subj,
                           f"quorum missing required roles: {sorted(missing)}",
                           {"missing_roles": sorted(missing)}))

    # independence: distinct identities
    ids = [a.get("approver_id") for a in approvers if a.get("approver_id")]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        out.append(Finding(SELF_APPROVAL_DETECTED, P0, subj,
                           "quorum approvers are not distinct identities",
                           {"reason": "independence", "duplicates": dupes}))

    # conflict-of-interest: no shared owner
    if policy.get("independence_required", True):
        owners: dict[str, list] = {}
        for a in approvers:
            owner = a.get("owner") or a.get("org")
            if owner is not None:
                owners.setdefault(str(owner), []).append(a.get("approver_id"))
        shared = {o: v for o, v in owners.items() if len(v) > 1}
        if shared:
            out.append(Finding(SELF_APPROVAL_DETECTED, P0, subj,
                               "quorum approvers share an owner (conflict)",
                               {"reason": "conflict_of_interest",
                                "shared_owners": shared}))

    ok = not any(f.severity in (P0, P1) for f in out)
    return ok, out
