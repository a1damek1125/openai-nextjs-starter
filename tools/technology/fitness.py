"""Technology Fitness Functions + waiver governance (SP0004 D-0004-43..46, §11.11,
INV-0004-22).

Deterministic, continuously-evaluable checks over the technology model. Hard and
advisory fitness are SEPARATE (D-0004-45): a hard fitness failure (raw-secret
exposure, provider-ID as canonical identity, critical TDR missing exit plan,
unsupported protocol) is P0/P1; advisory drift is P2. A fitness function detects,
reports and may block architecture change — it NEVER grants runtime authority
(INV-0004-22). Waivers reuse SP0001 principles: owner + rationale + expiry +
scope, and can never waive a constitutional P0 (§17.6).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, FITNESS_MODES,
                    TECHNOLOGY_FITNESS_FAILED, TECHNOLOGY_FITNESS_DEGRADED,
                    WAIVER_INVALID, CRITICAL_DEPENDENCY_WITHOUT_EXIT_PLAN,
                    PROVIDER_IDENTITY_LEAKAGE, RAW_SECRET_EXPOSURE,
                    PROTOCOL_VERSION_UNSUPPORTED)
from .contracts import validate_contract
from .exit_readiness import evaluate_exit
from .decisions import tdr_index

# constitutional P0 fitness ids that can NEVER be waived (§17.6)
UNWAIVABLE = {"FIT-NO-RAW-SECRET", "FIT-NO-PROVIDER-IDENTITY",
              "FIT-CRITICAL-EXIT-PLAN"}


def validate_fitness_defs(defs: list[dict]) -> list[Finding]:
    out: list[Finding] = []
    for f in defs:
        fid = f.get("fitness_id", "-")
        if f.get("mode") not in FITNESS_MODES:
            out.append(Finding(TECHNOLOGY_FITNESS_FAILED, P1, fid,
                               f"invalid fitness mode {f.get('mode')!r}", {}))
        if f.get("severity") not in (P0, P1, P2):
            out.append(Finding(TECHNOLOGY_FITNESS_FAILED, P1, fid,
                               f"invalid severity {f.get('severity')!r}", {}))
    return out


def validate_waiver(w: dict, *, today: str) -> list[Finding]:
    """A waiver must have owner + rationale + expiry + scope; anonymous, eternal,
    expired, or constitutional-P0 waivers are invalid (§17.6, AC-0004-020 set)."""
    out: list[Finding] = []
    wid = w.get("waiver_id", "-")
    if not w.get("owner"):
        out.append(Finding(WAIVER_INVALID, P1, wid, "waiver has no owner", {}))
    if not w.get("rationale"):
        out.append(Finding(WAIVER_INVALID, P1, wid, "waiver has no rationale", {}))
    if not w.get("scope"):
        out.append(Finding(WAIVER_INVALID, P1, wid, "waiver has no scope", {}))
    exp = w.get("expiry")
    if not exp:
        out.append(Finding(WAIVER_INVALID, P1, wid,
                           "waiver has no expiry (eternal waivers forbidden)", {}))
    elif str(exp) < str(today):
        out.append(Finding(WAIVER_INVALID, P1, wid, "waiver is expired", {}))
    if w.get("fitness_id") in UNWAIVABLE:
        out.append(Finding(WAIVER_INVALID, P0, wid,
                           f"constitutional fitness {w.get('fitness_id')!r} cannot "
                           "be waived (§17.6)", {}))
    return out


def waived(fitness_id: str, waivers: list[dict], *, today: str) -> bool:
    for w in waivers:
        if w.get("fitness_id") != fitness_id:
            continue
        if fitness_id in UNWAIVABLE:
            return False
        if validate_waiver(w, today=today):
            continue   # invalid waiver does not waive
        return True
    return False


def evaluate_fitness(program: dict, *, today: str) -> list[Finding]:
    """Run the built-in hard fitness functions over the technology model.
    `program` bundles inventory / contracts / decisions / exit_profiles /
    protocols / substitution_evidence / waivers."""
    out: list[Finding] = []
    waivers = program.get("waivers", [])

    # FIT-NO-RAW-SECRET + FIT-NO-PROVIDER-IDENTITY (via contract validation)
    for c in program.get("contracts", {}).get("contracts", []):
        for f in validate_contract(c):
            if f.kind in (RAW_SECRET_EXPOSURE, PROVIDER_IDENTITY_LEAKAGE):
                out.append(f)

    # FIT-CRITICAL-EXIT-PLAN
    out.extend(evaluate_exit(program.get("inventory", {}),
                             program.get("exit_profiles", [])))

    # FIT-PROTOCOL-SUPPORTED (unsupported protocol version fails closed)
    for p in program.get("protocols", {}).get("protocols", []):
        if p.get("status") == "UNSUPPORTED":
            fid = "FIT-PROTOCOL-SUPPORTED"
            if not waived(fid, waivers, today=today):
                out.append(Finding(PROTOCOL_VERSION_UNSUPPORTED, P1,
                                   p.get("protocol_id", "-"),
                                   "an unsupported protocol version is in use "
                                   "(AC-0004-094)", {}))
    return out


def fitness_summary(findings: list[Finding]) -> dict:
    hard = [f for f in findings if f.severity in (P0, P1)]
    advisory = [f for f in findings if f.severity == P2]
    return {"hard_failures": len(hard), "advisory": len(advisory),
            "status": "ACTIVE_AND_FIT" if not hard else "ACTIVE_DEGRADED"}
