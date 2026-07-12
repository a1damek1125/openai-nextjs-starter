"""Proof Envelopes (SP0006 §9, §10.13, D-0006-62, INV-0006-44).

Work / Delegation / Outcome / Accountability proof envelopes bind the material
governance artifacts by hash into a deterministic, bit-reproducible record. A
proof envelope is EVIDENCE, never authority (D-0006-62, INV-0006-44): it cannot
grant future capability, approval, or accountability. Any envelope that claims to
authorize is a PROOF_ENVELOPE_MISMATCH.
"""
from __future__ import annotations

from .model import Finding, P1, PROOF_ENVELOPE_MISMATCH
from .canon import canonical_json, core_hash, sha256_hex

ENVELOPE_VERSION = "1.0.0"
VALIDATOR_VERSION = "governed-work-validator-1"


def _h(obj) -> str:
    return core_hash(obj) if obj is not None else ""


def _seal(core: dict) -> dict:
    env = dict(core)
    env["envelope_hash"] = sha256_hex(canonical_json(core))
    env["classification"] = "EVIDENCE_NOT_AUTHORITY"
    return env


def work_proof_envelope(work: dict, *, plan=None, delegation_graph=None,
                        leases=None, budget_ledger=None, approvals=None,
                        execution_evidence=None, outcome_contract=None,
                        outcome_evidence=None, defeaters=None,
                        accountability_chain=None) -> dict:
    """§10.13 Work Proof Envelope — binds every governance artifact by hash."""
    core = {
        "envelope_version": ENVELOPE_VERSION,
        "envelope_kind": "WORK",
        "work_instance_hash": work.get("work_instance_hash", ""),
        "semantic_work_hash": work.get("semantic_work_hash", ""),
        "work_order_hash": _h(work),
        "plan_envelope_hash": _h(plan),
        "delegation_graph_hash": _h(delegation_graph),
        "lease_set_hash": _h(leases),
        "budget_ledger_hash": _h(budget_ledger),
        "approval_set_hash": _h(approvals),
        "execution_evidence_hash": _h(execution_evidence),
        "outcome_contract_hash": _h(outcome_contract),
        "outcome_evidence_hash": _h(outcome_evidence),
        "defeater_set_hash": _h(defeaters),
        "accountability_chain_hash": _h(accountability_chain),
        "validator_version": VALIDATOR_VERSION,
    }
    return _seal(core)


def delegation_proof_envelope(work_instance_hash: str, edges, leases,
                              attenuation_proofs) -> dict:
    core = {"envelope_version": ENVELOPE_VERSION, "envelope_kind": "DELEGATION",
            "work_instance_hash": work_instance_hash,
            "delegation_edges_hash": _h(edges),
            "lease_set_hash": _h(leases),
            "attenuation_proofs_hash": _h(attenuation_proofs),
            "validator_version": VALIDATOR_VERSION}
    return _seal(core)


def outcome_proof_envelope(work_instance_hash: str, outcome_contract,
                           outcome_evidence, predicate_results,
                           defeaters=None) -> dict:
    core = {"envelope_version": ENVELOPE_VERSION, "envelope_kind": "OUTCOME",
            "work_instance_hash": work_instance_hash,
            "outcome_contract_hash": _h(outcome_contract),
            "outcome_evidence_hash": _h(outcome_evidence),
            "predicate_results_hash": _h(predicate_results),
            "defeater_set_hash": _h(defeaters),
            "validator_version": VALIDATOR_VERSION}
    return _seal(core)


def accountability_proof_envelope(work_instance_hash: str,
                                  accountability_chain, reassignments=None) -> dict:
    core = {"envelope_version": ENVELOPE_VERSION,
            "envelope_kind": "ACCOUNTABILITY",
            "work_instance_hash": work_instance_hash,
            "accountability_chain_hash": _h(accountability_chain),
            "reassignments_hash": _h(reassignments),
            "validator_version": VALIDATOR_VERSION}
    return _seal(core)


def validate_envelope(envelope: dict) -> list[Finding]:
    """An envelope is evidence, not authority (INV-0006-44). Recompute the hash;
    a claim to grant authority is a mismatch."""
    out: list[Finding] = []
    eid = envelope.get("envelope_kind", "-")
    core = {k: v for k, v in envelope.items()
            if k not in ("envelope_hash", "classification")}
    if envelope.get("envelope_hash") \
            and envelope["envelope_hash"] != sha256_hex(canonical_json(core)):
        out.append(Finding(PROOF_ENVELOPE_MISMATCH, P1, eid,
                           "envelope hash does not match its content", {}))
    if envelope.get("classification") not in (None, "EVIDENCE_NOT_AUTHORITY"):
        out.append(Finding(PROOF_ENVELOPE_MISMATCH, P1, eid,
                           "envelope must be classified EVIDENCE_NOT_AUTHORITY "
                           "(INV-0006-44)", {}))
    # allowlist: any key that even hints at conferring authority/capability is a
    # mismatch — a blocklist of a few names is bypassable with a synonym
    # (SWARM-M E11; D-0006-62). Flag any unrecognized key whose name implies
    # authority/capability/grant/permission.
    _AUTHORITY_HINTS = ("authorit", "authoriz", "grant", "capabilit", "confer",
                        "permission", "permit", "entitle", "power")
    for key, val in envelope.items():
        if key in ("envelope_hash", "classification"):
            continue
        low = key.lower()
        if any(h in low for h in _AUTHORITY_HINTS) and val:
            out.append(Finding(PROOF_ENVELOPE_MISMATCH, P1, eid,
                               f"envelope key {key!r} implies authority — proof "
                               "is evidence, not authority (D-0006-62)", {}))
    return out
