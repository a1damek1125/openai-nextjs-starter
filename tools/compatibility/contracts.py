"""Contract Descriptor + Version registries (SP0007 §10.1/10.2, §13.1,
D-0007-03/04/06/08).

Contract surfaces stay distinct (D-0007-08); a released contract version is
IMMUTABLE — any material change is a new version (D-0007-06, INV-0007-01);
contract version is distinct from implementation/deployment/provider/protocol/
epoch/validator versions (D-0007-03); SemVer is a declaration of intent, never
compatibility proof (D-0007-04, INV-0007-03).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, CONTRACT_KINDS, STABILITY, CRITICALITY,
                    VERSION_STATES, IMMUTABLE_STATES, CONTRACT_OWNER_MISSING,
                    CONTRACT_VERSION_MUTATED, SEMVER_MISMATCH,
                    INVALID_COMPAT_SCHEMA)
from .canon import version_content_hash


def validate_descriptor(d: dict) -> list[Finding]:
    out: list[Finding] = []
    cid = d.get("contract_id", "-")
    if not d.get("contract_id"):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, "-",
                           "contract descriptor missing contract_id", {}))
    if d.get("contract_kind") not in CONTRACT_KINDS:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, cid,
                           f"unknown contract_kind {d.get('contract_kind')!r}",
                           {}))
    # every protected contract needs an owner (D-0007-63 fitness, AC-0007-032)
    if not (d.get("owner_capability") or d.get("owner")):
        out.append(Finding(CONTRACT_OWNER_MISSING, P1, cid,
                           "contract has no owner (AC-0007-032)", {}))
    if d.get("stability") not in STABILITY:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, cid,
                           f"unknown stability {d.get('stability')!r}", {}))
    if d.get("criticality") not in CRITICALITY:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, cid,
                           f"unknown criticality {d.get('criticality')!r}", {}))
    return out


def validate_version(v: dict) -> list[Finding]:
    out: list[Finding] = []
    vid = f"{v.get('contract_id','-')}@{v.get('version','-')}"
    for f in ("contract_id", "version"):
        if not v.get(f):
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, vid,
                               f"contract version missing {f}", {}))
    st = v.get("status", "DRAFT")
    if st not in VERSION_STATES:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, vid,
                           f"unknown version status {st!r}", {}))
    # immutability witness: a released version whose recorded content hash no
    # longer matches its content has been MUTATED (INV-0007-01)
    if st in IMMUTABLE_STATES and v.get("content_hash"):
        if v["content_hash"] != version_content_hash(v):
            out.append(Finding(CONTRACT_VERSION_MUTATED, P0, vid,
                               "released contract version content diverges "
                               "from its sealed content hash (D-0007-06)", {}))
    # released versions must be sealed with a content hash
    if st in IMMUTABLE_STATES and not v.get("content_hash"):
        out.append(Finding(CONTRACT_VERSION_MUTATED, P1, vid,
                           "released version has no sealed content hash", {}))
    return out


def release(version: dict) -> dict:
    """Seal a DRAFT/REVIEWED version: stamp the content hash and mark RELEASED.
    From here the content is immutable (D-0007-06)."""
    sealed = dict(version)
    sealed["status"] = "RELEASED"
    sealed["immutable"] = True
    sealed["content_hash"] = version_content_hash(sealed)
    return sealed


def mutation_findings(released: dict, current: dict) -> list[Finding]:
    """Compare a sealed released version against its current content — any
    material divergence is CONTRACT_VERSION_MUTATED (P0)."""
    if version_content_hash(released) != version_content_hash(current):
        vid = f"{released.get('contract_id','-')}@{released.get('version','-')}"
        return [Finding(CONTRACT_VERSION_MUTATED, P0, vid,
                        "released contract version was mutated in place — a "
                        "material change requires a NEW version (D-0007-06)",
                        {})]
    return []


# --- SemVer as declaration, not proof (D-0007-04) ----------------------------
def parse_semver(v: str) -> tuple[int, int, int] | None:
    try:
        parts = str(v).split("-")[0].split("+")[0].split(".")
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def semver_declaration_findings(old_version: str, new_version: str,
                                classified_breaking: bool) -> list[Finding]:
    """A breaking change labeled as a patch/minor bump is SEMVER_MISMATCH —
    the label declared intent the evidence refutes (D-0007-04, §20.35 M1)."""
    o, n = parse_semver(old_version), parse_semver(new_version)
    if o is None or n is None:
        return [Finding(INVALID_COMPAT_SCHEMA, P2, f"{old_version}->{new_version}",
                        "non-semver version labels — intent undeclared", {})]
    major_bumped = n[0] > o[0]
    if classified_breaking and not major_bumped:
        return [Finding(SEMVER_MISMATCH, P0, f"{old_version}->{new_version}",
                        "breaking change hidden inside a non-major release "
                        "(D-0007-04; no breaking change inside a patch)", {})]
    return []
