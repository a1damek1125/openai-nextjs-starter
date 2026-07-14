"""Canonical normalization + stable identity resolution (SP0008 §8,
D-0008-11/12).

The union of raw detector observations is reconciled here into canonical surface
records whose identity is resolved AGAINST the SP0007 Contract Registry — the
inventory POPULATES that registry, it never stands up a parallel one
(PARALLEL_REGISTRY_DETECTED, D-0008-12). Each discovered surface is placed under
its parent SP0007 contract descriptor (CT-*) when its kind and source path fall
within a descriptor's declared scope, and is otherwise a genuinely NEW_SURFACE
that the registry did not yet name. Alias/duplicate/ambiguous outcomes are
recorded, never silently merged (D-0008-11).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .discover import Observation
from .model import (MATCHED_EXISTING, NEW_SURFACE, ALIAS_CANDIDATE,
                    DUPLICATE_CANDIDATE, AMBIGUOUS_IDENTITY)


# surface kind -> SP0007 contract_kind (the registry's coarse taxonomy)
KIND_TO_CONTRACT_KIND = {
    "HTTP_ROUTE": "HTTP_API",
    "REQUEST_SHAPE": "HTTP_API",
    "RESPONSE_SHAPE": "HTTP_API",
    "AUDIT_EVENT": "EVENT_MESSAGE",
    "RUN_LEDGER_EVENT": "EVENT_MESSAGE",
    "DB_TABLE": "DB_SCHEMA",
    "DB_MIGRATION": "DB_SCHEMA",
    "STATE_MACHINE": "WORKFLOW_HISTORY",
    "STATE_TRANSITION": "WORKFLOW_HISTORY",
    "PROOF_ARTIFACT": "PROOF_HASH",
    "UI_SURFACE": "UI_PROJECTION",
    "PROVIDER_BINDING": "PROVIDER",
    "CONFIG_KEY": "CLI_CONFIG",
    "CLI_COMMAND": "CLI_CONFIG",
    "BACKGROUND_JOB": "EVENT_MESSAGE",
}


@dataclass(frozen=True)
class CanonicalSurface:
    """A reconciled surface: one identity, the detectors that saw it, its parent
    registry contract (if resolved), and its identity-resolution outcome."""
    surface_id: str
    surface_kind: str
    canonical_name: str
    contract_kind: str
    parent_contract_id: str | None
    identity_outcome: str
    detectors: tuple
    evidence: tuple            # ((path, line), ...) — every grounding site
    structural_fingerprints: tuple
    notes: tuple = ()

    def as_dict(self) -> dict:
        return {
            "surface_id": self.surface_id,
            "surface_kind": self.surface_kind,
            "canonical_name": self.canonical_name,
            "contract_kind": self.contract_kind,
            "parent_contract_id": self.parent_contract_id,
            "identity_outcome": self.identity_outcome,
            "detectors": list(self.detectors),
            "evidence": [{"path": p, "line": ln} for p, ln in self.evidence],
            "structural_fingerprints": list(self.structural_fingerprints),
            "notes": list(self.notes),
        }


def _descriptor_index(descriptors: Iterable[dict]) -> dict:
    """Index registry descriptors by contract_kind -> [(contract_id, paths)]."""
    idx: dict[str, list] = {}
    for d in descriptors:
        ck = d.get("contract_kind")
        paths = tuple(d.get("source_paths") or [])
        idx.setdefault(ck, []).append((d.get("contract_id"), paths))
    return idx


def _resolve_parent(contract_kind: str, evidence_paths: Iterable[str],
                    idx: dict):
    """Resolve the parent CT-* descriptor for a surface.

    A surface MATCHES an existing descriptor when its contract_kind matches and
    at least one evidence path lies within a descriptor's declared source_paths.
    Multiple matching descriptors => AMBIGUOUS_IDENTITY (never guess).
    """
    candidates = idx.get(contract_kind) or []
    ev = list(evidence_paths)
    matched = []
    for contract_id, paths in candidates:
        for dp in paths:
            if not dp:
                continue                 # empty descriptor path never matches
            # match only on path-component boundaries: an evidence path is
            # under a descriptor path iff it equals it or is a child directory
            # entry (dp + "/"). No bare startswith (which would let
            # ".../app" match ".../approvals.py") — red-team P2.
            if any(p == dp or p.startswith(dp + "/") or dp.startswith(p + "/")
                   for p in ev):
                matched.append(contract_id)
                break
    matched = sorted(set(m for m in matched if m))
    if len(matched) == 1:
        return matched[0], MATCHED_EXISTING
    if len(matched) > 1:
        return None, AMBIGUOUS_IDENTITY
    return None, NEW_SURFACE


def reconcile(observations: Iterable[Observation],
              descriptors: Iterable[dict]) -> list[CanonicalSurface]:
    """Union detector observations into canonical surfaces and resolve identity
    against the SP0007 registry (D-0008-11/12)."""
    idx = _descriptor_index(descriptors)
    grouped: dict[str, list[Observation]] = {}
    for o in observations:
        grouped.setdefault(o.surface_id, []).append(o)

    # structural fingerprint -> surface_ids, to flag alias/duplicate candidates
    fp_map: dict[str, set] = {}
    for sid, obs in grouped.items():
        for o in obs:
            fp_map.setdefault(o.as_dict()["structural_fingerprint"],
                              set()).add((o.surface_kind, sid))

    out: list[CanonicalSurface] = []
    for sid in sorted(grouped):
        obs = grouped[sid]
        kind = obs[0].surface_kind
        name = obs[0].canonical_name
        contract_kind = KIND_TO_CONTRACT_KIND.get(kind, "UNKNOWN")
        detectors = tuple(sorted({o.detector for o in obs}))
        evidence = tuple(sorted({(o.evidence_path, o.evidence_line)
                                 for o in obs}))
        ev_paths = [p for p, _ in evidence]
        fps = tuple(sorted({o.as_dict()["structural_fingerprint"]
                            for o in obs}))
        parent, outcome = _resolve_parent(contract_kind, ev_paths, idx)

        notes: list[str] = []
        # duplicate/alias candidate: same structural fingerprint, same kind,
        # different surface_id — a possible duplicate the registry should review
        for fp in fps:
            peers = {psid for (pk, psid) in fp_map.get(fp, ())
                     if pk == kind and psid != sid}
            if peers:
                # a genuine duplicate suspicion only when names differ
                notes.append(f"shares structural fingerprint with "
                             f"{len(peers)} other {kind} surface(s)")
                if outcome == NEW_SURFACE:
                    outcome = DUPLICATE_CANDIDATE
                break

        out.append(CanonicalSurface(
            surface_id=sid, surface_kind=kind, canonical_name=name,
            contract_kind=contract_kind, parent_contract_id=parent,
            identity_outcome=outcome, detectors=detectors, evidence=evidence,
            structural_fingerprints=fps, notes=tuple(notes)))
    return out


def parallel_registry_paths(surfaces: Iterable[CanonicalSurface],
                            *, known_contract_ids: Iterable[str] | None = None
                            ) -> list[str]:
    """Detect a parallel registry (D-0008-12): the inventory must reference the
    SP0007 registry, never persist competing contract_ids of its own.

    A surface is a parallel-registry violation if EITHER it mints a CT-* id of
    its own (canonical_name looks like a registry id), OR it claims a
    parent_contract_id that is NOT in the loaded SP0007 descriptor set (a
    fabricated parent). `known_contract_ids` is the authoritative id set; when
    omitted only the minted-id check runs."""
    known = set(known_contract_ids) if known_contract_ids is not None else None
    bad = []
    for s in surfaces:
        if s.canonical_name.startswith("CT-"):
            bad.append(s.surface_id)
        elif known is not None and s.parent_contract_id is not None \
                and s.parent_contract_id not in known:
            bad.append(s.surface_id)
    return sorted(set(bad))


def parallel_registry_findings(surfaces, descriptors):
    """Emit PARALLEL_REGISTRY_DETECTED findings, wired into the pipeline."""
    from .model import Finding, P0, PARALLEL_REGISTRY_DETECTED
    known = {d.get("contract_id") for d in descriptors}
    out = []
    for sid in parallel_registry_paths(surfaces, known_contract_ids=known):
        out.append(Finding(
            PARALLEL_REGISTRY_DETECTED, P0, sid,
            "surface mints or references a contract id outside the SP0007 "
            "registry: the inventory must populate SP0007, never a parallel "
            "registry (D-0008-12)", {}))
    return out
