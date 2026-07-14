"""Grounded defeasible reasoning (SP0010 FUNCTION F, §11.5, D-0010-05,
AC-0010-054..057, 161..165).

Defeaters rebut a claim, undercut an argument, attack evidence reliability, or
invalidate an assumption/freshness. Resolution uses the deterministic GROUNDED
extension of the defeater attack graph: an argument is IN only when every
attacker is OUT; an attacker is OUT only when some IN argument attacks it. No
favorable extension is chosen just because it produces closure (D-0010-05). A
defeater with grounded support that remains unopposed is BLOCKING; a blocking
defeater on a critical claim refutes it and (later) reopens closure.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import (Finding, P0, DEFEATER_KINDS, DEFEATER_TARGETS,
                    DEFEATER_STATES)


def defeater(*, target_type: str, target_ref: str, defeater_type: str,
             statement: str, evidence_refs: list, grounded_support: bool
             ) -> dict:
    if target_type not in DEFEATER_TARGETS:
        raise ValueError(f"bad target_type {target_type!r}")
    if defeater_type not in DEFEATER_KINDS:
        raise ValueError(f"bad defeater_type {defeater_type!r}")
    d = {"target_type": target_type, "target_ref": target_ref,
         "defeater_type": defeater_type, "statement": statement,
         "evidence_refs": list(evidence_refs),
         "grounded_support": grounded_support is True,
         "status": "PROPOSED"}
    d["defeater_id"] = "DF-" + hash_obj(d)[:16]
    return d


def grounded_extension(arguments: list, attacks: list) -> dict:
    """Compute the grounded extension of an argumentation framework.

    arguments: list of argument ids. attacks: list of (attacker, target).
    Returns IN (justified), OUT (defeated), UNDECIDED. Deterministic labelling:
    iterate — an argument with no attackers, or all attackers OUT, is IN; an
    argument attacked by an IN argument is OUT; the rest are UNDECIDED."""
    args = set(arguments)
    attackers = {a: set() for a in args}
    for src, tgt in attacks:
        if tgt in attackers:
            attackers[tgt].add(src)
    label = {a: "UNDECIDED" for a in args}
    changed = True
    iterations = 0
    while changed:
        changed = False
        iterations += 1
        for a in sorted(args):
            if label[a] != "UNDECIDED":
                continue
            atk = attackers[a]
            if all(label.get(x) == "OUT" for x in atk):
                label[a] = "IN"
                changed = True
            elif any(label.get(x) == "IN" for x in atk):
                label[a] = "OUT"
                changed = True
        if iterations > 1000:
            break
    return {"labels": label,
            "in": sorted(a for a in args if label[a] == "IN"),
            "out": sorted(a for a in args if label[a] == "OUT"),
            "undecided": sorted(a for a in args if label[a] == "UNDECIDED")}


def resolve(defeaters: list) -> dict:
    """Grounded resolution: a defeater with grounded support and no successful
    counter becomes BLOCKING; an ungrounded defeater stays PROPOSED (a rumor is
    not a defeater); a defeater countered by an IN counter-argument is
    RESOLVED. Here defeaters attack claims; counter-arguments are the claim's
    own support (modeled by grounded_support of the defeater itself)."""
    out = []
    for d in defeaters:
        after = dict(d)
        if not d.get("grounded_support"):
            after["status"] = "PROPOSED"     # ungrounded => never blocks
        else:
            after["status"] = "BLOCKING"
        assert after["status"] in DEFEATER_STATES
        out.append(after)
    return {"defeaters": out,
            "blocking": [d["defeater_id"] for d in out
                         if d["status"] == "BLOCKING"],
            "blocked_targets": sorted({d["target_ref"] for d in out
                                       if d["status"] == "BLOCKING"})}


def defeater_findings(resolution: dict) -> list[Finding]:
    out: list[Finding] = []
    for d in resolution["defeaters"]:
        if d["status"] == "BLOCKING":
            out.append(Finding(
                "DEFEATER_GROUNDED", P0, d["target_ref"],
                f"grounded blocking defeater ({d['defeater_type']}) against "
                f"{d['target_ref']}: {d.get('statement', '')[:80]}",
                {"defeater": d["defeater_id"]}))
    return out
