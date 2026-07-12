"""SP0006 provider-neutral authorization projections (§5.4/5.6, D-0006-63,
INV-0006-45). External authorization standards are projections / transport /
evidence, NEVER internal authority. Covers the external-projection criteria."""
from __future__ import annotations

from tools.governed_work.projections import (PROJECTION_FORMATS, project_lease,
                                             validate_projection,
                                             anti_corruption_import)
from tools.governed_work.validate import validate_all
from tools.governed_work.model import INVALID_WORK_SCHEMA


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


def _lease():
    return {"lease_id": "L", "targets": ["a"], "allowed_operations": ["read"],
            "effect_classes": ["READ"],
            "attenuation_delta": {"removed_operations": ["send"]}}


def test_all_formats_projectable():
    for fmt in PROJECTION_FORMATS:
        proj = project_lease(_lease(), fmt)
        assert proj["format"] == fmt
        assert proj["non_authoritative"] is True
        assert proj["projected_from_lease"] == "L"


def test_macaroon_ucan_carry_attenuation_caveats():
    for fmt in ("MACAROON", "UCAN"):
        proj = project_lease(_lease(), fmt)
        assert proj.get("caveats")   # attenuation carried as caveats


def test_clean_projection_validates():
    assert not validate_projection(project_lease(_lease(), "GNAP"))


def test_projection_claiming_authority_is_rejected():
    proj = project_lease(_lease(), "GNAP")
    assert INVALID_WORK_SCHEMA in _k(validate_projection(
        dict(proj, grants_authority=True)))
    assert INVALID_WORK_SCHEMA in _k(validate_projection(
        dict(proj, authoritative=True)))


def test_unknown_format_flagged():
    assert INVALID_WORK_SCHEMA in _k(validate_projection(
        project_lease(_lease(), "BOGUS_FORMAT")))


def test_anti_corruption_import_is_untrusted():
    imp = anti_corruption_import({"token": "external"}, "GNAP")
    assert imp["status"] == "UNTRUSTED_PROJECTION"
    assert imp["requires_internal_admission"] is True


def test_projections_wired_into_aggregate_gate():
    # a committed projection claiming authority must be caught by validate_all
    bad = dict(project_lease(_lease(), "GNAP"), grants_authority=True)
    rep = validate_all({"projections": [bad]})
    assert not rep.valid
    assert INVALID_WORK_SCHEMA in _k(rep)
