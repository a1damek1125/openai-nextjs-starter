"""Evidence-First store + Paraconsistent Claim Ledger + Provenance/Influence/
Common-Mode graphs + Semantic Taint + Authority Air-Gap + Memory Writeback
Firewall (TOOL-B10 §N/O/P/R/S/T/X/Y/AA/AB, §11.3, D-B6-008/009, 022..047,
101..120, 141..160).

EVIDENCE BEFORE BELIEF: immutable content-addressed evidence is recorded before
any derived claim; claims never overwrite evidence (D-B6-008/009). Claims are
FOUR-VALUED (support & refutation tracked independently; BOTH is not TRUE, NEITHER
is not FALSE). Provenance + influence graphs record where each claim came from and
what it influenced; the common-mode graph quotients mirrored/shared-model/shared-
provider sources so corroboration is not double-counted. Semantic taint propagates
through paraphrase/summary/translation and survives until removal is PROVEN. The
Authority Air-Gap keeps external content in the INFORMATION channel — it can never
create authority. Memory writeback candidates start QUARANTINED and never
auto-promote.

This layer REFERENCES the canonical evidence authority (finalis/evidence,
finalis/crm/memory) by id/hash; it does not duplicate storage.
"""
from __future__ import annotations

from itertools import combinations

from .canon import hash_obj, content_address
from .model import (Finding, P0, P1, P2, claim_state, closes_critical,
                    taint_join, CHANNELS)


def evidence_record(*, source_id: str, source_version: str, tenant_id: str,
                    content: str, observed_at: str, valid_from=None,
                    valid_to=None, taint: str = "EXTERNAL") -> dict:
    """Immutable, content-addressed evidence. External content is INFORMATION-
    channel only and carries taint by default."""
    e = {"source_id": source_id, "source_version": source_version,
         "tenant_id": tenant_id, "content_hash": content_address(content),
         "observed_at": observed_at, "valid_from": valid_from,
         "valid_to": valid_to, "channel": "INFORMATION", "taint": taint}
    e["evidence_root"] = hash_obj({k: e[k] for k in e if k != "observed_at"})
    e["evidence_id"] = "EV-" + e["evidence_root"][:16]
    return e


def claim(*, evidence_refs: list, tenant_id: str, subject: dict, predicate: str,
          obj: dict, polarity: str, quantity=None, unit=None, scope: dict = None,
          language: str = "EN", support: bool = False, refute: bool = False,
          taint_refs: list = None, valid_from=None, valid_to=None,
          observed_at: str = "") -> dict:
    """A derived claim (never replaces evidence). Four-valued support state; taint
    inherited from evidence."""
    state = claim_state(support, refute)
    c = {"evidence_refs": sorted(evidence_refs), "tenant_id": tenant_id,
         "subject": subject, "predicate": predicate, "object": obj,
         "polarity": polarity, "quantity": quantity, "unit": unit,
         "scope": scope or {}, "language": language, "support_state": state,
         "taint_refs": sorted(taint_refs or []), "valid_from": valid_from,
         "valid_to": valid_to, "observed_at": observed_at}
    c["claim_hash"] = hash_obj({k: c[k] for k in c if k != "observed_at"})
    c["claim_id"] = "CL-" + c["claim_hash"][:16]
    return c


def claim_findings(claims: list, *, critical_ids: set) -> list[Finding]:
    """A critical claim in BOTH/NEITHER cannot satisfy its requirement; kept
    VISIBLE (contradictions never silently resolved, D-B6-034)."""
    out: list[Finding] = []
    for c in claims:
        if c["claim_id"] in critical_ids and not closes_critical(
                c["support_state"]):
            kind = "CLAIM_BOTH" if c["support_state"] == "BOTH" \
                else "CLAIM_NEITHER"
            out.append(Finding(kind, P1, c["claim_id"],
                               f"critical claim is {c['support_state']}: not "
                               "SUPPORTED_ONLY (visible, not resolved)", {}))
    return out


# --- provenance / influence / common-mode ------------------------------------
def provenance_edge(*, from_ref: str, to_ref: str, relation: str) -> dict:
    """relation in {GENERATED_BY, DERIVED_FROM, TRANSFORMED_BY, INFLUENCED}."""
    e = {"from_ref": from_ref, "to_ref": to_ref, "relation": relation}
    e["edge_hash"] = hash_obj(e)
    return e


def provenance_root(edges: list) -> str:
    return hash_obj(sorted(e["edge_hash"] for e in edges))


def common_mode_graph(evidence: list) -> dict:
    """Group evidence sharing an ORIGIN (mirror), extraction MODEL, or PROVIDER —
    agreement among common-mode sources is weaker (mirrors/shared models/shared
    providers do NOT multiply independence, D-B6-036/037/038)."""
    shared = {}
    for key in ("origin", "extraction_model", "provider"):
        buckets = {}
        for e in evidence:
            buckets.setdefault(e.get(key), []).append(e["evidence_id"])
        dupes = {k: sorted(v) for k, v in buckets.items() if len(v) > 1 and k}
        if dupes:
            shared[key] = dupes
    return shared


def independence_class(evidence_ids: list, evidence_by_id: dict) -> str:
    """Independence quotiented by PRODUCER/origin (common-mode = one domain)."""
    producers = {evidence_by_id[e].get("provider") or evidence_by_id[e].get(
        "source_id") for e in evidence_ids if e in evidence_by_id}
    if not producers:
        return "UNKNOWN"
    if len(producers) == 1:
        return "SINGLE_SOURCE" if len(evidence_ids) == 1 else "COMMON_MODE"
    return "INDEPENDENT"


# --- semantic taint ----------------------------------------------------------
def propagate_taint(input_taints: list, *, removal_proven: bool = False) -> str:
    """Taint join over inputs; a transformation (summary/translation/paraphrase)
    does NOT clear taint unless removal is explicitly PROVEN (D-B6-042/043/044)."""
    level = "UNTAINTED"
    for t in input_taints:
        level = taint_join(level, t)
    if removal_proven:
        return "UNTAINTED"
    return level


# taints that are merely informational provenance and do not block by themselves
_BENIGN_TAINTS = frozenset({"UNTAINTED", "EXTERNAL", "TOOL_OUTPUT",
                            "UNTRUSTED_DERIVED"})


def taint_findings(claims: list, *, critical_ids: set) -> list[Finding]:
    """Any taint that is NOT a benign provenance marker — SUSPECTED_INJECTION,
    QUARANTINED, or an UNRECOGNIZED label (fail-closed, consistent with the
    taint_join lattice) — is a removal-unproven finding; P0 on a critical claim."""
    out: list[Finding] = []
    for c in claims:
        for t in c.get("taint_refs", []):
            if t not in _BENIGN_TAINTS:
                sev = P0 if c["claim_id"] in critical_ids else P1
                out.append(Finding("TAINT_REMOVAL_UNPROVEN", sev, c["claim_id"],
                                   f"claim carries unremoved/unknown taint {t}",
                                   {}))
    return out


# --- authority air-gap -------------------------------------------------------
def authority_air_gap(records: list) -> list[Finding]:
    """External/information-channel content that tries to assert authority is
    rejected (external content is never authority, D-B6-022..027, INV-21..25)."""
    out: list[Finding] = []
    for r in records:
        # anything that ASSERTS authority while NOT genuinely in the AUTHORITY
        # channel is rejected — a missing/unknown channel fails closed too
        if r.get("asserts_authority") and r.get("channel") != "AUTHORITY":
            out.append(Finding("AUTHORITY_INFERENCE_REJECTED", P0,
                               r.get("evidence_id", "-"),
                               "non-authority-channel content cannot create "
                               "authority (air-gap)", {}))
    return out


# --- memory writeback quarantine ---------------------------------------------
def memory_candidate(*, proposed_fact: dict, evidence_refs: list,
                     work_succeeded: bool) -> dict:
    """A memory-write candidate starts QUARANTINED; successful work does NOT
    auto-admit it (D-B6-046/047, quarantine cannot self-release)."""
    return {"proposed_fact": proposed_fact, "evidence_refs": sorted(evidence_refs),
            "has_evidence_lineage": bool(evidence_refs),
            "work_succeeded": bool(work_succeeded), "state": "QUARANTINED",
            "auto_admitted": False,
            "candidate_hash": hash_obj({"f": proposed_fact,
                                        "e": sorted(evidence_refs)})}


def memory_findings(candidates: list) -> list[Finding]:
    out: list[Finding] = []
    for c in candidates:
        if c["auto_admitted"] is True:
            out.append(Finding("MEMORY_WRITEBACK_QUARANTINED", P0,
                               c["candidate_hash"],
                               "memory writeback was auto-admitted: forbidden "
                               "(quarantine cannot self-release)", {}))
    return out
