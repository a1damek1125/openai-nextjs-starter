"""Migration Plans, Expand–Migrate–Contract, Dual-Read/Dual-Write, and Shadow
modes (SP0007 §10.8/10.9, §11.6, D-0007-42..47, AC-0007-146..157).

Every migration runs expand → migrate → verify → contract (D-0007-42): EXPAND
must keep old consumers operating (AC-0007-151); CONTRACT is gated on all
known critical consumers being migrated and no unknown critical consumers
(D-0007-43, AC-0007-152). Dual-read divergence must be reconciled before it is
trusted (D-0007-44, AC-0007-155); dual-write requires idempotency, ordering,
conflict policy, drift detection and reconciliation declared up front
(D-0007-45, AC-0007-156/157). A shadow reader/writer observes — it never
creates authoritative or externally visible state (D-0007-46/47,
AC-0007-153/154).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, PLAN_STATES, PHASES,
                    CONSUMER_INCOMPATIBLE, UNKNOWN_CONSUMER,
                    DUAL_READ_DIVERGENCE, DUAL_WRITE_DIVERGENCE,
                    INVALID_COMPAT_SCHEMA)
from .canon import core_hash

_PLAN_REQUIRED = ("migration_plan_id", "source_versions", "target_version")
_PHASE_DICTS = ("expand_phase", "migrate_phase", "verify_phase",
                "contract_phase")
_STEP_REQUIRED = ("step_id", "idempotency_key")
_GATED_CRITICALITY = ("C2", "C3", "C4")
_DUAL_WRITE_REQUIRED = ("idempotency", "ordering", "conflict_policy",
                        "drift_detection", "reconciliation")


def validate_plan(plan: dict) -> list[Finding]:
    """A migration plan names its versions, carries all four phases of
    expand–migrate–contract, a lifecycle status, and idempotent steps
    (D-0007-42, AC-0007-146..150)."""
    out: list[Finding] = []
    pid = str(plan.get("migration_plan_id") or "-")
    for fld in _PLAN_REQUIRED:
        if plan.get(fld) in (None, "", []):
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, pid,
                               f"migration plan missing {fld}",
                               {"missing": fld}))
    for phase in _PHASE_DICTS:
        if not isinstance(plan.get(phase), dict):
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, pid,
                               f"migration plan missing {phase} dict — every "
                               "migration runs expand-migrate-verify-contract "
                               "(D-0007-42)", {"missing": phase}))
    status = plan.get("status", "DRAFT")
    if status not in PLAN_STATES:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, pid,
                           f"unknown plan status {status!r}", {}))
    for step in plan.get("steps") or []:
        sid = str(step.get("step_id") or "-")
        for fld in _STEP_REQUIRED:
            if step.get(fld) in (None, ""):
                out.append(Finding(INVALID_COMPAT_SCHEMA, P1,
                                   f"{pid}/{sid}",
                                   f"migration step missing {fld}",
                                   {"missing": fld}))
        if step.get("phase") not in PHASES:
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, f"{pid}/{sid}",
                               f"unknown step phase {step.get('phase')!r}",
                               {}))
    return out


def expand_phase_findings(plan: dict, *,
                          old_consumer_check=None) -> list[Finding]:
    """EXPAND must keep every old consumer operating unchanged (D-0007-42,
    AC-0007-151). A plan whose expand phase breaks old consumers — declared
    or observed via `old_consumer_check` — is P0."""
    out: list[Finding] = []
    pid = str(plan.get("migration_plan_id") or "-")
    expand = plan.get("expand_phase") or {}
    if expand.get("breaks_old_consumers"):
        out.append(Finding(CONSUMER_INCOMPATIBLE, P0, pid,
                           "expand phase declares it breaks old consumers — "
                           "EXPAND must keep old consumers operating "
                           "(D-0007-42, AC-0007-151)", {}))
    if old_consumer_check is not None:
        try:
            ok = old_consumer_check(plan)
        except TypeError:
            ok = old_consumer_check()
        if not ok:
            out.append(Finding(CONSUMER_INCOMPATIBLE, P0, pid,
                               "old-consumer check failed during expand phase "
                               "(AC-0007-151)", {}))
    return out


def contract_phase_findings(plan: dict, *,
                            bindings: list[dict]) -> list[Finding]:
    """CONTRACT is gated (D-0007-43, AC-0007-152): every known consumer of
    criticality C2+ must be migrated, and there must be no unknown critical
    consumers. Fail-closed on both."""
    out: list[Finding] = []
    pid = str(plan.get("migration_plan_id") or "-")
    for b in bindings or []:
        if b.get("criticality") in _GATED_CRITICALITY \
                and b.get("migrated") is not True:   # SWARM-M E3: require True
            out.append(Finding(
                CONSUMER_INCOMPATIBLE, P0,
                str(b.get("consumer_id") or "-"),
                "contract phase requires migrated consumers — critical "
                f"consumer {b.get('consumer_id')!r} is not migrated "
                "(D-0007-43, AC-0007-152)",
                {"plan": pid, "criticality": b.get("criticality")}))
    if plan.get("unknown_critical_consumers"):
        out.append(Finding(UNKNOWN_CONSUMER, P0, pid,
                           "contract phase blocked: unknown critical "
                           "consumers may still depend on the old surface "
                           "(D-0007-43)", {}))
    return out


def dual_read(old_reader, new_reader, fixtures: list[dict]) -> dict:
    """Run old and new read paths over the fixture corpus and compare their
    canonical hashes (D-0007-44, AC-0007-155). Any hash difference is recorded
    as an unreconciled divergence."""
    differences: list[dict] = []
    fixtures = fixtures or []
    for fx in fixtures:
        payload = fx.get("payload")
        old_hash = core_hash(old_reader(payload))
        new_hash = core_hash(new_reader(payload))
        if old_hash != new_hash:
            differences.append({"fixture_id": fx.get("fixture_id", "-"),
                                "old_hash": old_hash,
                                "new_hash": new_hash})
    return {"fixtures": len(fixtures), "differences": differences,
            "reconciled": not differences}


def dual_read_findings(result: dict) -> list[Finding]:
    """Each dual-read divergence is DUAL_READ_DIVERGENCE (P1) until it is
    explained by a reconciliation record, after which it is informational
    (D-0007-44, AC-0007-155)."""
    out: list[Finding] = []
    reconciled_ref = (result or {}).get("reconciliation_ref")
    for diff in (result or {}).get("differences", []):
        if reconciled_ref:
            out.append(Finding(DUAL_READ_DIVERGENCE, P2,
                               str(diff.get("fixture_id", "-")),
                               "dual-read divergence explained by "
                               f"reconciliation {reconciled_ref!r} "
                               "(AC-0007-155)", dict(diff)))
        else:
            out.append(Finding(DUAL_READ_DIVERGENCE, P1,
                               str(diff.get("fixture_id", "-")),
                               "old and new read paths returned different "
                               "results with no reconciliation (D-0007-44)",
                               dict(diff)))
    return out


def dual_write_findings(contract: dict) -> list[Finding]:
    """Dual-write demands idempotency, ordering, conflict policy, drift
    detection and reconciliation declared BEFORE writes fan out (D-0007-45,
    AC-0007-156). Observed divergence without reconciliation is P0
    (AC-0007-157)."""
    out: list[Finding] = []
    subject = str(contract.get("contract_id") or
                  contract.get("migration_plan_id") or "-")
    for fld in _DUAL_WRITE_REQUIRED:
        if contract.get(fld) in (None, "", {}):
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, subject,
                               f"dual-write contract missing {fld} "
                               "(D-0007-45, AC-0007-156)",
                               {"missing": fld}))
    divergence = contract.get("divergence") or []
    if divergence and not contract.get("reconciliation"):
        out.append(Finding(DUAL_WRITE_DIVERGENCE, P0, subject,
                           f"{len(divergence)} observed dual-write "
                           "divergence(s) with no reconciliation "
                           "(AC-0007-157)", {"divergence": list(divergence)}))
    return out


def shadow_findings(shadow: dict) -> list[Finding]:
    """A shadow reader/writer is observation only: it must never create
    authoritative state or externally visible effects (D-0007-46/47,
    AC-0007-153/154)."""
    out: list[Finding] = []
    subject = str(shadow.get("shadow_id") or shadow.get("contract_id") or "-")
    if shadow.get("creates_authoritative_state"):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P0, subject,
                           "shadow mode creates authoritative state — "
                           "shadows are observation only (D-0007-46, "
                           "AC-0007-153)", {}))
    if shadow.get("externally_visible"):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P0, subject,
                           "shadow mode is externally visible — shadow "
                           "effects must never escape (D-0007-47, "
                           "AC-0007-154)", {}))
    return out
