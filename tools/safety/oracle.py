"""Safety Oracle Hierarchy (SP0005 D-0005-61/62/66, §11.8, INV-0005-11).

For a hard safety property, prefer the strongest applicable oracle: environment
state → artifact/crypto evidence → independent formal/rule checker → calibrated
statistical → human specialist → LLM judge → agent self-report. AGENT_SELF_REPORT
(and an LLM_JUDGE that is the acting model / not independently validated) can
NEVER be the SOLE oracle for a hard property (INV-0005-11, AC-0005-143). Prefer
observable environment evidence over "the model says it behaved safely"
(D-0005-66).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, ORACLE_TYPES, NON_PRIMARY_ORACLES,
                    INVALID_SAFETY_SCHEMA, SAFETY_ORACLE_INSUFFICIENT,
                    SELF_REPORT_AS_SOLE_ORACLE)


def _oracle_type(o) -> str | None:
    return o.get("type") if isinstance(o, dict) else o


def rank(oracle_type: str) -> int:
    """Lower rank = stronger oracle."""
    return ORACLE_TYPES.index(oracle_type) if oracle_type in ORACLE_TYPES \
        else len(ORACLE_TYPES)


def strongest(oracles: list[str]) -> str | None:
    valid = [o for o in oracles if o in ORACLE_TYPES]
    return min(valid, key=rank) if valid else None


def validate_hard_property(prop: dict) -> list[Finding]:
    """A hard safety property must be backed by at least one oracle that is not
    self-report / a non-validated LLM judge (INV-0005-11)."""
    out: list[Finding] = []
    pid = prop.get("property_id", "-")
    oracles = prop.get("oracles", [])
    kinds = {_oracle_type(o) for o in oracles}
    # An unrecognized/typeless oracle must NEVER be trusted as a strong primary
    # oracle — otherwise a junk entry launders self-report into "sufficient"
    # (SWARM-N E2; INV-0005-11). Flag it and exclude it from `non_self`.
    for o in oracles:
        if _oracle_type(o) not in ORACLE_TYPES:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, pid,
                               f"unrecognized safety oracle "
                               f"{_oracle_type(o)!r}", {}))
    # the acting model as sole judge is forbidden; only a RECOGNIZED strong
    # oracle (in ORACLE_TYPES, not a non-primary one) counts as primary
    non_self = [o for o in oracles
                if _oracle_type(o) in ORACLE_TYPES
                and _oracle_type(o) not in NON_PRIMARY_ORACLES]
    # an LLM judge counts as primary only if independently validated for this
    validated_llm = [o for o in oracles if isinstance(o, dict)
                     and o.get("type") == "LLM_JUDGE"
                     and o.get("independently_validated")]
    if not non_self and not validated_llm:
        out.append(Finding(SELF_REPORT_AS_SOLE_ORACLE, P0, pid,
                           "hard safety property relies solely on agent self-"
                           "report / non-validated LLM judge (INV-0005-11)", {}))
    elif "AGENT_SELF_REPORT" in kinds and len(kinds) == 1:
        out.append(Finding(SELF_REPORT_AS_SOLE_ORACLE, P0, pid,
                           "agent self-report is the only oracle", {}))
    if not oracles:
        out.append(Finding(SAFETY_ORACLE_INSUFFICIENT, P1, pid,
                           "hard property has no oracle", {}))
    return out
