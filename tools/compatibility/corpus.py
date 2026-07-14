"""Historical Compatibility Corpus (SP0007 §11, D-0007-29/30,
AC-0007-091..100).

Fixtures are recorded historical evidence: identified, versioned, epoch-bound,
provenance-carrying, and immutable — a fixture whose content diverges from its
recorded hash is a corrupted corpus (D-0007-29). The corpus must cover common,
edge, adversarial, and rare-critical classes for a contract to count as
sufficiently evidenced (D-0007-30). Production-raw tenant data never enters
the corpus: only SYNTHETIC or ANONYMIZED fixtures are admissible.

model.py defines no HISTORICAL_CORPUS_INSUFFICIENT constant, so insufficiency
findings use INVALID_COMPAT_SCHEMA with a 'corpus insufficient' message.
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, FIXTURE_KINDS, CORPUS_CLASSES,
                    INVALID_COMPAT_SCHEMA)
from .canon import fixture_hash

ALLOWED_TENANT_CLASSES = ("SYNTHETIC", "ANONYMIZED")
# the classes whose absence blocks sufficiency (D-0007-30)
REQUIRED_CLASSES = ("COMMON", "EDGE", "ADVERSARIAL", "RARE_CRITICAL")


def validate_fixture(fx: dict) -> list[Finding]:
    """Validate a corpus fixture (D-0007-29, AC-0007-091..096)."""
    out: list[Finding] = []
    subject = str(fx.get("fixture_id") or "-")

    for fld in ("fixture_id", "contract_id", "contract_version",
                "semantic_epoch"):
        if not fx.get(fld):
            out.append(Finding(
                INVALID_COMPAT_SCHEMA, P1, subject,
                f"fixture missing required field {fld!r}", {"missing": fld}))
    if fx.get("fixture_kind") not in FIXTURE_KINDS:
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P1, subject,
            f"unknown fixture_kind {fx.get('fixture_kind')!r}; expected one "
            f"of {list(FIXTURE_KINDS)}", {}))
    if "payload" not in fx and not fx.get("payload_ref"):
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P1, subject,
            "fixture has neither payload nor payload_ref", {}))
    provenance = fx.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P1, subject,
            "fixture missing non-empty provenance record (D-0007-29)", {}))
    if fx.get("corpus_class") not in CORPUS_CLASSES:
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P1, subject,
            f"unknown corpus_class {fx.get('corpus_class')!r}; expected one "
            f"of {list(CORPUS_CLASSES)}", {}))

    # only SYNTHETIC / ANONYMIZED fixtures are admissible; ANY other tenant_class
    # (PRODUCTION_RAW, PRODUCTION, PROD, LIVE, RAW, …) is a P0 poisoned-corpus /
    # sensitivity violation — matching a single literal is bypassable
    # (SWARM-M E8; fail-closed allowlist)
    tenant_class = fx.get("tenant_class")
    if tenant_class not in ("SYNTHETIC", "ANONYMIZED"):
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P0, subject,
            f"fixture tenant_class {tenant_class!r} is not SYNTHETIC or "
            "ANONYMIZED: poisoned corpus / sensitivity violation — only "
            "SYNTHETIC or ANONYMIZED fixtures are admissible",
            {"tenant_class": tenant_class}))
    elif tenant_class not in ALLOWED_TENANT_CLASSES:
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P1, subject,
            f"fixture tenant_class {tenant_class!r} is not SYNTHETIC or "
            "ANONYMIZED", {"tenant_class": tenant_class}))

    recorded = fx.get("fixture_hash")
    if recorded and recorded != fixture_hash(fx):
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P1, subject,
            "fixture content does not match its recorded fixture_hash "
            "(corpus integrity)", {"recorded": recorded,
                                   "recomputed": fixture_hash(fx)}))
    return out


def corpus_sufficiency(fixtures: list[dict], *, contract_id) -> list[Finding]:
    """Corpus coverage for one contract (D-0007-30): every corpus class should
    be represented; missing COMMON/EDGE/ADVERSARIAL/RARE_CRITICAL is P1."""
    out: list[Finding] = []
    present = {fx.get("corpus_class") for fx in fixtures
               if fx.get("contract_id") == contract_id}
    for cls in CORPUS_CLASSES:
        if cls in present:
            continue
        if cls in REQUIRED_CLASSES:
            out.append(Finding(
                INVALID_COMPAT_SCHEMA, P1, str(contract_id),
                f"HISTORICAL corpus insufficient for {contract_id!r}: no "
                f"{cls} fixtures (D-0007-30)",
                {"missing_class": cls, "present": sorted(
                    c for c in present if c)}))
        else:
            out.append(Finding(
                INVALID_COMPAT_SCHEMA, P2, str(contract_id),
                f"corpus for {contract_id!r} has no {cls} fixtures",
                {"missing_class": cls}))
    return out


def corpus_stats(fixtures) -> dict:
    """Observable corpus composition: counts by kind, class, and contract."""
    fixtures = list(fixtures)
    by_kind: dict = {}
    by_class: dict = {}
    by_contract: dict = {}
    for fx in fixtures:
        k = fx.get("fixture_kind")
        c = fx.get("corpus_class")
        cid = fx.get("contract_id")
        by_kind[k] = by_kind.get(k, 0) + 1
        by_class[c] = by_class.get(c, 0) + 1
        by_contract[cid] = by_contract.get(cid, 0) + 1
    return {"total": len(fixtures),
            "by_kind": by_kind, "by_class": by_class,
            "by_contract": by_contract}


def immutability_findings(fixture: dict, recorded_hash: str) -> list[Finding]:
    """Corpus fixtures never change (D-0007-29): a recomputed hash that
    diverges from the recorded one is corpus mutation, P0."""
    out: list[Finding] = []
    subject = str(fixture.get("fixture_id") or "-")
    recomputed = fixture_hash(fixture)
    if recomputed != recorded_hash:
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P0, subject,
            "corpus fixture content diverges from its recorded hash: "
            "fixtures are immutable historical evidence (D-0007-29)",
            {"recorded": recorded_hash, "recomputed": recomputed}))
    return out
