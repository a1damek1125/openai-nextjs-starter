"""Evidence-provenance algebra (SP0010 FUNCTION G, §10.4/10.5, §11.7/11.8,
§12.4/12.5, D-0010-08/09/10, AC-0010-101..115).

Support is algebraic: each claim is backed by minimal ANTICHAIN sets of evidence
atoms. AND composition is the minimized Cartesian union of prerequisite support
sets; OR composition is the minimized union of alternatives; strict supersets
are removed (D-0010-09). Independence is DOMAIN-based: many evidence files from
one generator/parser are ONE common-mode support domain and count once for
quorum (D-0010-10). Self-referential evidence (an atom whose producer is the
claim's own generator) cannot close a critical claim (INV-0010-14). Stale
evidence cannot close a current claim (INV-0010-16). Exact bounds are reported;
truncation is an explicit SUPPORT_SET_LIMIT_REACHED, never silent.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, P1, P2

SUPPORT_SET_LIMIT = 256


def evidence_atom(*, claim_refs: list, source_ref: str, producer: str,
                  tool: str, parser_family: str, trust_domain: str,
                  repository_commit: str, valid_from: str, valid_to=None,
                  self_referential: bool = False) -> dict:
    a = {"claim_refs": sorted(claim_refs), "source_ref": source_ref,
         "producer": producer, "tool": tool, "parser_family": parser_family,
         "trust_domain": trust_domain, "repository_commit": repository_commit,
         "valid_from": valid_from, "valid_to": valid_to,
         "self_referential": self_referential is True}
    a["evidence_atom_id"] = "EA-" + hash_obj(a)[:16]
    return a


def _minimize(sets: list) -> list:
    """Remove strict supersets; keep the minimal antichain (D-0010-09)."""
    frozen = [frozenset(s) for s in sets]
    keep = []
    for s in frozen:
        if any(other < s for other in frozen if other != s):
            continue
        if s not in keep:
            keep.append(s)
    return [sorted(s) for s in sorted(keep, key=lambda x: (len(x), sorted(x)))]


def and_support(a_sets: list, b_sets: list) -> list:
    """AND: Cartesian union of prerequisite support sets, then minimized."""
    out = []
    for x in a_sets:
        for y in b_sets:
            out.append(sorted(set(x) | set(y)))
            if len(out) > SUPPORT_SET_LIMIT:
                return _minimize(out)[:SUPPORT_SET_LIMIT]
    return _minimize(out)


def or_support(a_sets: list, b_sets: list) -> list:
    """OR: union of alternatives, minimized."""
    return _minimize(list(a_sets) + list(b_sets))


def trust_domains(support_set: list, atoms_by_id: dict) -> list:
    return sorted({atoms_by_id[a]["trust_domain"] for a in support_set
                   if a in atoms_by_id})


def independence_class(support_set: list, atoms_by_id: dict, *,
                       required_domains: int = 2) -> str:
    """A support set is INDEPENDENT only when its atoms span >= required_domains
    distinct trust domains AFTER common-mode quotienting (D-0010-10).

    Common-mode quotient (red-team P1/P2-5): atoms sharing the SAME producer are
    ONE effective domain regardless of differing trust_domain labels — many
    files from one generator are one common-mode support domain. Independence is
    counted over distinct PRODUCERS, not label strings."""
    if any(atoms_by_id.get(a, {}).get("self_referential") for a in support_set):
        return "SELF_REFERENTIAL"
    producers = {atoms_by_id[a]["producer"] for a in support_set
                 if a in atoms_by_id}
    if len(producers) >= required_domains:
        return "INDEPENDENT"
    return "COMMON_MODE"


def common_mode_graph(atoms: list) -> dict:
    """Group atoms sharing a producer/tool/parser_family — shared dependency
    domains whose agreement is weaker evidence."""
    shared = {}
    for key in ("producer", "tool", "parser_family"):
        buckets = {}
        for a in atoms:
            buckets.setdefault(a.get(key), []).append(a["evidence_atom_id"])
        dupes = {k: sorted(v) for k, v in buckets.items() if len(v) > 1 and k}
        if dupes:
            shared[key] = dupes
    return shared


def minimal_support_set(*, claim_id: str, evidence_sets: list,
                        atoms_by_id: dict) -> dict:
    minimal = _minimize(evidence_sets)
    limited = len(evidence_sets) > SUPPORT_SET_LIMIT
    return {
        "support_set_id": "SS-" + hash_obj(
            {"c": claim_id, "m": minimal})[:16],
        "claim_id": claim_id,
        "sets": minimal,
        "trust_domains": sorted({d for s in minimal
                                 for d in trust_domains(s, atoms_by_id)}),
        "independence_class": (independence_class(minimal[0], atoms_by_id)
                               if minimal else "UNKNOWN"),
        "current": True,
        "limit_reached": limited,
    }


def evidence_findings(atoms_by_id: dict, support_sets: list, *,
                      critical: set, now: str) -> list[Finding]:
    out: list[Finding] = []
    for ss in support_sets:
        cid = ss["claim_id"]
        crit = cid in critical
        if ss.get("limit_reached"):
            out.append(Finding(
                "SUPPORT_SET_LIMIT_REACHED", P1, cid,
                "minimal support-set enumeration hit its bound; the reported "
                "sets are a lower bound, not complete (§11.7)", {}))
        if not ss["sets"]:
            continue
        if crit and ss["independence_class"] == "SELF_REFERENTIAL":
            out.append(Finding(
                "EVIDENCE_SELF_REFERENCE", P0, cid,
                "critical claim closed only by self-referential evidence: "
                "insufficient (INV-0010-14)", {}))
        if crit and ss["independence_class"] == "COMMON_MODE":
            # ADVISORY (P2): the guarantee is deterministically SUPPORTED, but
            # its support is single-producer (its own kernel). We DISCLOSE the
            # common-mode honestly rather than falsely claim independent quorum
            # (D-0010-10); it is assurance debt / a single point of assurance,
            # not a contradiction, so it does not invalidate the closure.
            out.append(Finding(
                "EVIDENCE_COMMON_MODE_RISK", P2, cid,
                "critical claim support is single-producer (common-mode): not "
                "independent quorum — recorded as assurance debt, not counted "
                "as independent corroboration (D-0010-10)",
                {"trust_domains": ss["trust_domains"],
                 "independence_class": ss["independence_class"]}))
        # staleness
        for s in ss["sets"]:
            for a in s:
                atom = atoms_by_id.get(a, {})
                vt = atom.get("valid_to")
                if vt is not None and str(vt) <= str(now):
                    out.append(Finding(
                        "EVIDENCE_STALE", P1 if crit else P1, cid,
                        f"support atom {a} expired ({vt}); stale evidence "
                        "cannot close a current claim (INV-0010-16)", {}))
    return out


def evidence_root(atoms_by_id: dict) -> str:
    return hash_obj(sorted(atoms_by_id))
